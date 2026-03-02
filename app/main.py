import argparse
import asyncio
import inspect
import json
import os
import re
import signal
import sys
from pathlib import Path
from typing import Any, List, Dict, Optional

from config import YAMLS_DIR, TARGET_FILES, FACTS_CANON, PATTERN_SNIPS

from modules.utils.file_io import split_and_write_files, write_makefile, write_manifest, write_doxyfile, run_doxygen
from modules.utils.utils import _read, extract_text_from_bedrock_response, _now_tag
from modules.generation.prompt import (
    build_clock_prompt,
    invoke_model,
    Model,
    build_system_prompt,
    build_user_prompt,            # peripheral driver prompt
    build_system_init_prompt,     # system.c/system_init
    build_linker_prompt,          # linker script
    build_entry_prompt,           # entry.c
    build_start_asm_prompt,       # start.s
    build_vim_prompt,             # VIM driver
    _progress,                    # global progress tracker
    _cost_tracker,                # global cost tracker
)
from modules.utils.user import prompt_user_for_peripherals, get_peripheral_list
from modules.contracts.api_contract_manifest import (
    build_api_contract_manifest,
    hydrate_contract_from_generated_headers,
    write_api_contract_manifest,
)
from modules.contracts.contract_checker import (
    check_generated_module_contract,
    check_bsp_validate_contract,
)
from modules.contracts.contract_autofix import (
    autofix_bsp_validate,
)
from modules.build.ccs_build_gate import (
    gate_should_fail_run,
    run_ccs_build_gate,
)
from modules.build.ti_diagnostics import apply_deterministic_fixes
from modules.validation.startup_contract_validator import validate_startup_contract
from modules.validation.register_parity_guard import (
    default_critical_registers,
    run_parity_guard,
)

from modules.yaml.yaml_utils import (
    dump_yaml_str,
    load_bus_yaml,
    load_soc_yaml,
    load_board_yaml,
    load_bringup_contract,
    load_generation_profile,
    load_pinmux_yaml,
    load_regs_yaml,
    load_memmap_yaml,
    load_irq_yaml,
    build_system_slices_for_prompt,
    build_peripheral_slices_for_prompt,
    build_memmap_slice_for_prompt,
)

# Core infrastructure modules that must always be generated
# These provide foundational APIs that peripherals depend on
CORE_MODULES = [
    "SYSTEM",    # Base system initialization
    "PCR",       # Peripheral Central Resource (power control)
    "IOMM",      # Pin multiplexing - MUST come before peripherals
    "PLL",       # Clock/PLL hardware (generates manifest entry)
    "VIM",       # Vectored interrupt manager
]

# Manifest API name aliases: Some hardware modules need API aliases in manifest
# Format: {hardware_name: api_name}
# DISABLED: Using PLL directly as the clock module for consistency
# Peripherals should reference "PLL" for clock dependencies
CORE_MANIFEST_ALIASES = {
    # Removed PLL->clock alias. PLL module provides clock APIs directly.
}
CRITICAL_BUILD_MODULES = {"SCI", "GIO", "PLL", "IOMM", "PCR"}

DEFAULT_GENERATION_PROFILE = {
    "target_board": "LAUNCHXL2-TMS57012-RM46",
    "modules": {
        "enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]
    },
    "sci": {"default_baud": 9600},
    "pins": {"lock_board_mapping": True},
    "clocks": {"mode": "board_default"},
    "strict_validation": False,
    "bringup_mode": {
        "default": "direct_init",
    },
    "startup_contract": {
        "gate_mode": "warn",
    },
    "parity_guard": {
        "mode": "critical_only",
        "baseline_path": "app/output_working_with_manual_changes",
        "critical_registers": default_critical_registers(),
    },
    "bsp_validation": {
        "enabled": False,
        "baud": 9600,
        "frame": {
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "none",
        },
        "banners": {
            "sci": "SCI path active (A)\\r\\n",
            "lin": "LIN path active (B)\\r\\n",
        },
        "timing": {
            "heartbeat_ticks": 1000,
            "tx_period_ticks": 200,
            "busy_delay": 200,
        },
    },
    "build_gate": {
        "enabled": True,
        "mode": "strict",
        "external_workspace_path": "",
        "project_name": "",
        "configuration": "Debug",
        "max_fix_rounds": 3,
        "allow_targeted_llm_rewrite": True,
        "fail_on_compile_error": True,
        "clean_stale_project_files": True,
        "clean_build": True,
        "llm_rewrite": {
            "enabled": True,
            "scope": "top_files",
            "top_k_files": 2,
            "apply_policy": "hybrid",
            "model": "inherit",
            "max_tokens": 6000,
            "max_attempts": 1,
            "include_contract_context": True,
        },
    },
    "contract_mode": "auto_fix_then_fail",
    "contract_lock_mode": "strict",
    "require_ccs_proof": True,
    "bringup": {
        "mode": "strict",
        "contract_file": "app/yaml_in/bringup_contract.yaml",
        "fail_on_contract_mismatch": True,
        "emit_debug_probes": False,
    },
}


def _merge_generation_profile(override_profile: dict | None) -> dict:
    """Merge user profile over defaults with shallow-per-section semantics."""
    merged = json.loads(json.dumps(DEFAULT_GENERATION_PROFILE))
    if not override_profile:
        return merged

    for key, value in override_profile.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def _resolve_optional_path(path_value: Optional[str], yaml_root: Path) -> Optional[Path]:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    raw_path = Path(path_value.strip())
    candidates: List[Path] = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend(
            [
                Path.cwd() / raw_path,
                yaml_root / raw_path,
                yaml_root.parent / raw_path,
                yaml_root / raw_path.name,
            ]
        )
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
    return None


def _resolve_startup_gate_mode(
    generation_profile: Dict[str, Any],
    bringup_strict: bool,
    fail_on_contract_mismatch: bool,
) -> str:
    startup_cfg = generation_profile.get("startup_contract", {})
    gate_mode = ""
    if isinstance(startup_cfg, dict):
        gate_mode = str(startup_cfg.get("gate_mode", "")).strip().lower()
    if gate_mode in {"warn", "fail"}:
        return gate_mode
    if bringup_strict and fail_on_contract_mismatch:
        return "fail"
    return "warn"


def _resolve_parity_guard_config(generation_profile: Dict[str, Any], yaml_root: Path) -> Dict[str, Any]:
    cfg = generation_profile.get("parity_guard", {})
    if not isinstance(cfg, dict):
        cfg = {}
    mode = str(cfg.get("mode", "critical_only")).strip().lower()
    if mode not in {"critical_only", "strict", "off"}:
        mode = "critical_only"
    baseline_path = _resolve_optional_path(cfg.get("baseline_path"), yaml_root)
    critical_regs = cfg.get("critical_registers")
    if not isinstance(critical_regs, list) or not all(isinstance(x, str) for x in critical_regs):
        critical_regs = default_critical_registers()
    return {
        "mode": mode,
        "baseline_path": baseline_path,
        "critical_registers": list(critical_regs),
    }


def _augment_compile_gate_report(
    out_dir: Path,
    build_gate_result: Optional[Dict[str, Any]],
    startup_contract_result: Optional[Dict[str, Any]],
    startup_gate_mode: str,
    parity_result: Optional[Dict[str, Any]],
) -> None:
    if not isinstance(build_gate_result, dict):
        return

    startup_passes = (
        bool(startup_contract_result.get("passes", True))
        if isinstance(startup_contract_result, dict)
        else None
    )
    parity_passes = (
        bool(parity_result.get("passes", True))
        if isinstance(parity_result, dict)
        else None
    )
    parity_mode = (
        str(parity_result.get("mode", "critical_only"))
        if isinstance(parity_result, dict)
        else "critical_only"
    )
    blocking_reasons: List[str] = []
    if build_gate_result.get("required") and not build_gate_result.get("passes", False):
        blocking_reasons.append("compile_gate_failed")
    if startup_gate_mode == "fail" and startup_passes is False:
        blocking_reasons.append("startup_contract_failed")
    if startup_gate_mode == "fail" and parity_passes is False:
        blocking_reasons.append("parity_guard_failed")

    build_gate_result["startup_contract_status"] = {
        "status": "evaluated",
        "passes": startup_passes,
        "gate_mode": startup_gate_mode,
        "errors": list((startup_contract_result or {}).get("errors", []))[:20],
        "warnings": list((startup_contract_result or {}).get("warnings", []))[:20],
    }
    build_gate_result["parity_guard_status"] = {
        "status": "evaluated" if isinstance(parity_result, dict) else "not_evaluated",
        "passes": parity_passes,
        "mode": parity_mode,
        "summary": dict((parity_result or {}).get("summary", {})),
        "critical_mismatch_count": len((parity_result or {}).get("critical_sequence_mismatches", [])),
    }
    build_gate_result["blocking_reasons"] = blocking_reasons

    report_path = Path(out_dir) / "compile_gate_report.json"
    report_path.write_text(json.dumps(build_gate_result, indent=2), encoding="utf-8")


def resolve_dependencies(modules: List[str], manifest: Dict) -> List[str]:
    """
    Recursively resolve all dependencies for the given modules.

    Args:
        modules: List of module names to generate
        manifest: Complete BSP manifest with api_catalog

    Returns:
        List of modules including all transitive dependencies
    """
    resolved = set(modules)
    to_process = list(modules)

    api_catalog = manifest.get("api_catalog", {})

    while to_process:
        current = to_process.pop().upper()

        if current in api_catalog:
            deps = api_catalog[current].get("dependencies", [])
            for dep in deps:
                dep_upper = dep.upper()
                if dep_upper not in resolved and dep_upper not in ["SYSTEM", "VIM"]:
                    # Don't add SYSTEM/VIM as they're already in Pass 3
                    resolved.add(dep_upper)
                    to_process.append(dep_upper)

    return sorted(resolved)


def gather_all_clock_domains(soc_data: dict, bus_data: dict = None) -> list:
    """
    Collect every unique clock domain name from soc.yaml and bus.yaml.

    Sources:
    1. soc.yaml peripherals: clock_ref and x-ext.clock_refs fields
    2. bus.yaml top-level domains (GCLK, HCLK, VCLK, VCLK2, ...)
    3. bus.yaml top-level sources (OSCIN, PLL1, PLL2, ...)
    4. bus.yaml x-ext.peripheral_clocks.SYSTEM.clock_domains (domain_number mapping)

    Returns a sorted, deduplicated list used to build the complete clock_domain_t enum.
    """
    domains = set()

    # 1. Scan soc.yaml peripherals
    for periph in soc_data.get("soc", {}).get("peripherals", []):
        ref = periph.get("clock_ref")
        if ref and isinstance(ref, str):
            domains.add(ref)
        x_ext = periph.get("x-ext") or {}
        for r in (x_ext.get("clock_refs") or []):
            if r and isinstance(r, str):
                domains.add(r)

    # 2+3. Scan bus.yaml for all named domains and sources (both are lists of {name: ...})
    if bus_data:
        for entry in (bus_data.get("domains") or []):
            name = entry.get("name") if isinstance(entry, dict) else entry
            if name and isinstance(name, str):
                domains.add(name.upper())
        for entry in (bus_data.get("sources") or []):
            name = entry.get("name") if isinstance(entry, dict) else entry
            if name and isinstance(name, str):
                domains.add(name.upper())

        # 4. Pull SYSTEM clock_domain/source names from x-ext.peripheral_clocks.SYSTEM
        x_ext_all = bus_data.get("x-ext") or {}
        periph_clocks = x_ext_all.get("peripheral_clocks") or {}
        system_clocks = periph_clocks.get("SYSTEM") or {}
        for entry in (system_clocks.get("clock_domains") or []):
            name = entry.get("name") if isinstance(entry, dict) else entry
            if name and isinstance(name, str):
                domains.add(name.upper())
        for entry in (system_clocks.get("clock_sources") or []):
            name = entry.get("name") if isinstance(entry, dict) else entry
            if name and isinstance(name, str):
                domains.add(name.upper())

    return sorted(domains)


def _build_system_bus_slice(bus_data: dict) -> str:
    """
    Build a focused bus.yaml slice for system_init prompt.
    Includes top-level sources/domains with frequencies/dividers and the
    SYSTEM x-ext.peripheral_clocks section with source/domain numbers.
    Omits per-peripheral clock entries to keep context tight.
    """
    from modules.yaml.yaml_utils import dump_yaml_str

    if not bus_data:
        return ""

    slice_data = {}

    # Top-level clock sources (with freq_hz, PLL config)
    if "sources" in bus_data:
        slice_data["sources"] = bus_data["sources"]

    # Top-level clock domains (with divider registers)
    if "domains" in bus_data:
        slice_data["domains"] = bus_data["domains"]

    # SYSTEM peripheral clocks (source_number and domain_number mappings)
    x_ext = bus_data.get("x-ext") or {}
    periph_clocks = x_ext.get("peripheral_clocks") or {}
    system_section = periph_clocks.get("SYSTEM") or {}
    pll_section_data = periph_clocks.get("PLL") or {}
    if system_section or pll_section_data:
        focused = {}
        if system_section:
            focused["SYSTEM"] = system_section
        if pll_section_data:
            focused["PLL"] = pll_section_data
        slice_data["x-ext"] = {"peripheral_clocks": focused}

    return dump_yaml_str(slice_data) if slice_data else ""


async def _invoke_and_write(
    tag: str,
    system_prompt: str,
    user_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    soc_data: dict = None,
    regs_data: dict = None,
    token_allocator = None,
    progress_manager = None,
):
    """
    Helper to:
      - save system/user prompts for this call,
      - invoke the model,
      - save raw text,
      - split and write files immediately upon completion,
      - validate FACTS MIRROR (if soc_data and regs_data provided).
      - track token usage (if token_allocator provided).
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Save prompts for reproducibility (tagged by phase)
    (artifacts_dir / f"{tag}_system_prompt.txt").write_text(
        system_prompt, encoding="utf-8"
    )
    (artifacts_dir / f"{tag}_user_prompt.txt").write_text(
        user_prompt, encoding="utf-8"
    )

    messages = [
        {
            "role": "user",
            "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}",
        }
    ]

    if progress_manager:
        progress_manager.log_or_print(f"[info] Invoking {model_enum.name} for {tag} …")
    else:
        print(f"[info] Invoking {model_enum.name} for {tag} …")

    # invoke_model is now truly async
    resp = await invoke_model(model_enum, max_tokens, messages)

    text = extract_text_from_bedrock_response(resp)
    ts = _now_tag()

    # Track token usage for Pass 3 platform files
    if token_allocator:
        try:
            from modules.utils.utils import extract_usage_from_bedrock_response
            usage = extract_usage_from_bedrock_response(resp)
            tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            if tokens_used > 0:
                token_allocator.record_success(f"pass3_{tag}", tokens_used)
        except Exception:
            pass  # Don't fail if token tracking fails

    if not text.strip():
        (artifacts_dir / f"{tag}_empty_text_{ts}.txt").write_text(
            str(resp), encoding="utf-8"
        )
        if progress_manager:
            progress_manager.log_or_print(f"[warn] Empty model text for {tag}; raw response saved.")
        else:
            print(f"[warn] Empty model text for {tag}; raw response saved.")
        return []

    (artifacts_dir / f"{tag}_llm_text_{ts}.txt").write_text(text, encoding="utf-8")

    # Write files immediately and extract preamble
    written_files, preamble = split_and_write_files(text, out_dir)
    for file in written_files:
        try:
            relative_path = file.relative_to(out_dir)
        except ValueError:
            relative_path = file
        if progress_manager:
            progress_manager.log_or_print(f"[ok] {tag}: {relative_path}")
        else:
            print(f"[ok] {tag}: {relative_path}")

    # Validate if YAML data provided
    if soc_data is not None and regs_data is not None and written_files:
        from modules.validation.validation_engine import validate_generation_output
        try:
            validation_result = validate_generation_output(
                tag=tag,
                preamble=preamble,
                written_files=written_files,
                soc_data=soc_data,
                regs_data=regs_data
            )

            if not validation_result.is_valid:
                if progress_manager:
                    progress_manager.log_or_print(f"[warn] Validation warnings for {tag}:")
                    for error in validation_result.errors[:3]:  # Show first 3
                        progress_manager.log_or_print(f"  - {error}")
                else:
                    print(f"[warn] Validation warnings for {tag}:")
                    for error in validation_result.errors[:3]:  # Show first 3
                        print(f"  - {error}")
            elif validation_result.warnings:
                if progress_manager:
                    progress_manager.log_or_print(f"[info] Validation passed with {len(validation_result.warnings)} warnings")
                else:
                    print(f"[info] Validation passed with {len(validation_result.warnings)} warnings")

        except Exception as e:
            if progress_manager:
                progress_manager.log_or_print(f"[warn] Validation error for {tag}: {e}")
            else:
                print(f"[warn] Validation error for {tag}: {e}")

    return written_files


async def _invoke_and_write_with_retry(
    tag: str,
    system_prompt: str,
    user_prompt: str,
    model_enum: Model,
    initial_max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    soc_data: dict = None,
    regs_data: dict = None,
    retry_policy=None,
    progress_manager=None
) -> tuple[list[Path], bool]:
    """
    Invoke model with automatic retry on failure.

    Returns:
        Tuple of (written_files: List[Path], success: bool)
    """
    from modules.regeneration.retry_policy import RetryPolicy, FailureReason
    from modules.regeneration.truncation_detector import detect_truncation

    if retry_policy is None:
        retry_policy = RetryPolicy()

    max_tokens = initial_max_tokens

    for attempt in range(retry_policy.max_retries + 1):
        if attempt > 0:
            if progress_manager:
                progress_manager.log_or_print(f"[retry] Attempt {attempt + 1}/{retry_policy.max_retries + 1} for {tag} (tokens: {max_tokens})")
            else:
                print(f"[retry] Attempt {attempt + 1}/{retry_policy.max_retries + 1} for {tag} (tokens: {max_tokens})")

        # Invoke model
        messages = [{
            "role": "user",
            "content": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_prompt}"
        }]

        resp = await invoke_model(model_enum, max_tokens, messages)
        text = extract_text_from_bedrock_response(resp)

        if not text.strip():
            # Transient error - retry immediately
            should_retry, max_tokens = retry_policy.should_retry(
                attempt + 1, FailureReason.TRANSIENT_ERROR, max_tokens
            )
            if should_retry:
                continue
            else:
                return ([], False)

        # Save output
        ts = _now_tag()
        attempt_tag = f"{tag}_attempt{attempt}" if attempt > 0 else tag
        (artifacts_dir / f"{attempt_tag}_llm_text_{ts}.txt").write_text(text, encoding="utf-8")

        # Write files
        written_files, preamble = split_and_write_files(text, out_dir)

        # Check for truncation
        truncation_reason = detect_truncation(text, written_files)
        if truncation_reason:
            if progress_manager:
                progress_manager.log_or_print(f"[warn] Truncation detected: {truncation_reason}")
            else:
                print(f"[warn] Truncation detected: {truncation_reason}")
            should_retry, max_tokens = retry_policy.should_retry(
                attempt + 1, FailureReason.TOKEN_TRUNCATION, max_tokens
            )
            if should_retry:
                # Delete truncated files before retry
                for f in written_files:
                    f.unlink(missing_ok=True)
                continue
            else:
                return (written_files, False)

        # Validate if YAML data provided
        if soc_data is not None and regs_data is not None and written_files:
            from modules.validation.validation_engine import validate_generation_output

            try:
                validation_result = validate_generation_output(
                    tag=tag,
                    preamble=preamble,
                    written_files=written_files,
                    soc_data=soc_data,
                    regs_data=regs_data
                )

                # Check for FACTS MIRROR TODOs
                if hasattr(validation_result, 'has_todos') and validation_result.has_todos:
                    if progress_manager:
                        progress_manager.log_or_print(f"[warn] FACTS MIRROR contains TODOs")
                    else:
                        print(f"[warn] FACTS MIRROR contains TODOs")
                    should_retry, max_tokens = retry_policy.should_retry(
                        attempt + 1, FailureReason.FACTS_MIRROR_TODO, max_tokens
                    )
                    if should_retry:
                        user_prompt += "\n\nIMPORTANT: Previous attempt had TODOs in FACTS MIRROR. Ensure all constants are extracted from YAML."
                        for f in written_files:
                            f.unlink(missing_ok=True)
                        continue
                    else:
                        return (written_files, False)

                # Check for validation errors
                if not validation_result.is_valid:
                    if progress_manager:
                        progress_manager.log_or_print(f"[warn] Validation failed: {len(validation_result.errors)} errors")
                    else:
                        print(f"[warn] Validation failed: {len(validation_result.errors)} errors")
                    should_retry, max_tokens = retry_policy.should_retry(
                        attempt + 1, FailureReason.VALIDATION_ERROR, max_tokens
                    )
                    if should_retry:
                        error_summary = "\n".join(validation_result.errors[:5])
                        user_prompt += f"\n\nIMPORTANT: Previous attempt had validation errors:\n{error_summary}\nPlease fix these issues."
                        for f in written_files:
                            f.unlink(missing_ok=True)
                        continue
                    else:
                        return (written_files, False)

                # Validation passed - show summary
                if validation_result.warnings:
                    if progress_manager:
                        progress_manager.log_or_print(f"[info] Validation passed with {len(validation_result.warnings)} warnings")
                    else:
                        print(f"[info] Validation passed with {len(validation_result.warnings)} warnings")

            except Exception as e:
                if progress_manager:
                    progress_manager.log_or_print(f"[warn] Validation error for {tag}: {e}")
                else:
                    print(f"[warn] Validation error for {tag}: {e}")

        # SUCCESS
        for file in written_files:
            try:
                relative_path = file.relative_to(out_dir)
            except ValueError:
                relative_path = file
            if progress_manager:
                progress_manager.log_or_print(f"[ok] {tag}: {relative_path}")
            else:
                print(f"[ok] {tag}: {relative_path}")

        return (written_files, True)

    # Max retries exceeded
    return ([], False)


async def _generate_startup(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    start_user_prompt: str,
    token_allocator = None,
    progress_manager = None,
):
    """Generate start.s (assembly vector / SP setup)"""
    written_files = await _invoke_and_write(
        tag="start_asm",
        system_prompt=system_prompt,
        user_prompt=start_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )
    _sanitize_start_asm_files(written_files)
    return written_files


def _sanitize_start_asm_files(written_files: List[Path]) -> None:
    """
    Normalize start.s output for TI ARM CGT compatibility.

    Rewrites GNU-style literal-immediate pseudo-ops:
      LDR Rx, =0x12345678
    into:
      MOVW Rx, #0x5678
      MOVT Rx, #0x1234
    """
    ldr_hex_re = re.compile(r"^(\s*)LDR\s+(R\d+)\s*,\s*=0x([0-9A-Fa-f]{1,8})\s*$")

    for path in written_files:
        if path.suffix.lower() != ".s":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        updated: List[str] = []
        changed = False

        for line in lines:
            match = ldr_hex_re.match(line)
            if not match:
                updated.append(line)
                continue
            indent, reg, hex_value = match.groups()
            value = int(hex_value, 16)
            low = value & 0xFFFF
            high = (value >> 16) & 0xFFFF
            updated.append(f"{indent}MOVW    {reg}, #0x{low:04X}")
            updated.append(f"{indent}MOVT    {reg}, #0x{high:04X}")
            changed = True

        if changed:
            path.write_text("\n".join(updated) + "\n", encoding="utf-8")


async def _generate_entry(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    entry_user_prompt: str,
    token_allocator = None,
    progress_manager = None,
):
    """Generate entry.c (Reset_Handler_C -> system_init() -> main())"""
    return await _invoke_and_write(
        tag="entry_c",
        system_prompt=system_prompt,
        user_prompt=entry_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )


async def _generate_clock(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    clock_user_prompt: str,
    token_allocator = None,
    progress_manager = None,
):
    """Generate clock setup code"""
    return await _invoke_and_write(
        tag="clock_setup",
        system_prompt=system_prompt,
        user_prompt=clock_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )


async def _generate_system(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    system_init_user_prompt: str,
    token_allocator = None,
    progress_manager = None,
):
    """Generate system.c / system.h"""
    return await _invoke_and_write(
        tag="system_init",
        system_prompt=system_prompt,
        user_prompt=system_init_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )


async def _generate_linker(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    linker_user_prompt: str,
    token_allocator = None,
    progress_manager = None,
):
    """Generate linker script"""
    return await _invoke_and_write(
        tag="linker",
        system_prompt=system_prompt,
        user_prompt=linker_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )


async def _generate_vim(
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    vim_user_prompt: str,
    token_allocator = None,
    progress_manager = None,
):
    """Generate VIM driver"""
    return await _invoke_and_write(
        tag="vim_driver",
        system_prompt=system_prompt,
        user_prompt=vim_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )


async def _generate_peripheral(
    periph: dict,
    system_prompt: str,
    model_enum: Model,
    max_tokens: int,
    artifacts_dir: Path,
    out_dir: Path,
    periph_user_prompt: str,
):
    """Generate driver for a single peripheral"""
    name = str(periph.get("name", "UNKNOWN"))
    tag = f"periph_{name.lower()}"
    
    return await _invoke_and_write(
        tag=tag,
        system_prompt=system_prompt,
        user_prompt=periph_user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
    )


# ---------------- Signal Handling ----------------
_shutdown_requested = False

def signal_handler(_signum, _frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    if _shutdown_requested:
        print("\n[warn] Force exit requested. Terminating immediately.")
        sys.exit(1)

    _shutdown_requested = True
    print("\n[info] Shutdown requested. Finishing current operations... (Press Ctrl+C again to force quit)")
    print("[info] Current tasks will complete, then generation will stop.")


def _resolve_validation_file(out_dir: Path, filename: str) -> Optional[Path]:
    candidates = [
        out_dir / filename,
        out_dir / "include" / filename,
        out_dir / "source" / filename,
    ]
    return next((p for p in candidates if p.exists()), None)


def _collect_validation_module_files(out_dir: Path, module_name: str) -> tuple[List[Path], Optional[Path], Optional[Path]]:
    module_lower = module_name.lower()
    source = _resolve_validation_file(out_dir, f"{module_lower}_driver.c")
    header = _resolve_validation_file(out_dir, f"{module_lower}_driver.h")
    reg_header = _resolve_validation_file(out_dir, f"reg_{module_lower}.h")

    files: List[Path] = []
    if source:
        files.append(source)
    if header:
        files.append(header)
    if reg_header:
        files.append(reg_header)
    return files, header, source


def _discover_generated_modules(out_dir: Path) -> List[str]:
    modules: set[str] = set()
    roots = [out_dir, out_dir / "include", out_dir / "source"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*_driver.c"):
            stem = path.stem
            if stem.startswith("reg_"):
                continue
            mod = stem.replace("_driver", "").strip()
            if mod:
                modules.add(mod.upper())
    return sorted(modules)


def _run_validation_only(args) -> int:
    if not args.output_dir:
        raise ValueError("--validate-only requires --output-dir <existing output_* directory>")

    out_dir = Path(args.output_dir).resolve()
    if not out_dir.exists() or not out_dir.is_dir():
        raise FileNotFoundError(f"Validation output directory not found: {out_dir}")

    print(f"[info] Validation-only mode on existing output: {out_dir}")

    yaml_root = Path(args.yamlpath)
    if not (yaml_root / "soc.yaml").exists():
        alt_yaml_root = Path("app") / args.yamlpath
        if (alt_yaml_root / "soc.yaml").exists():
            yaml_root = alt_yaml_root

    # Load YAML sources
    soc_data = load_soc_yaml(yaml_root / "soc.yaml")
    regs_data = load_regs_yaml(yaml_root / "regs.yaml")
    irq_data = load_irq_yaml(yaml_root / "irq.yaml")
    memmap_data = load_memmap_yaml(yaml_root / "memmap.yaml")
    bus_data = load_bus_yaml(yaml_root / "bus.yaml")
    pinmux_data = load_pinmux_yaml(yaml_root / "pinmux.yaml")
    board_data = load_board_yaml(yaml_root / "board.yaml")

    # Load profile and bring-up contract using same defaults
    profile_data = None
    if args.profile:
        profile_data = load_generation_profile(Path(args.profile))
        print(f"[info] Loaded generation profile: {args.profile}")
    elif (yaml_root / "generation_profile.yaml").exists():
        profile_path = yaml_root / "generation_profile.yaml"
        profile_data = load_generation_profile(profile_path)
        print(f"[info] Loaded generation profile: {profile_path}")

    generation_profile = _merge_generation_profile(profile_data)
    bringup_cfg = generation_profile.get("bringup", {}) if isinstance(generation_profile.get("bringup", {}), dict) else {}
    bringup_mode = str(bringup_cfg.get("mode", "strict")).strip().lower()
    if bringup_mode not in {"strict", "relaxed"}:
        bringup_mode = "strict"
    bringup_strict = bringup_mode == "strict"
    fail_on_contract_mismatch = bool(bringup_cfg.get("fail_on_contract_mismatch", True))
    startup_gate_mode = _resolve_startup_gate_mode(
        generation_profile,
        bringup_strict=bringup_strict,
        fail_on_contract_mismatch=fail_on_contract_mismatch,
    )
    parity_guard_cfg = _resolve_parity_guard_config(generation_profile, yaml_root)

    def _resolve_bringup_contract_path(contract_file: str) -> Optional[Path]:
        candidates = []
        raw_path = Path(contract_file)
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            candidates.append(Path.cwd() / raw_path)
            candidates.append(yaml_root / raw_path)
            candidates.append(yaml_root.parent / raw_path)
            candidates.append(yaml_root / raw_path.name)
        seen = set()
        for candidate in candidates:
            normalized = candidate.resolve()
            if normalized in seen:
                continue
            seen.add(normalized)
            if normalized.exists():
                return normalized
        return None

    bringup_contract = None
    bringup_contract_path: Optional[Path] = None
    configured_contract_file = bringup_cfg.get("contract_file")
    if isinstance(configured_contract_file, str) and configured_contract_file.strip():
        bringup_contract_path = _resolve_bringup_contract_path(configured_contract_file.strip())
    else:
        default_contract = yaml_root / "bringup_contract.yaml"
        if default_contract.exists():
            bringup_contract_path = default_contract
    if bringup_contract_path is not None:
        bringup_contract = load_bringup_contract(bringup_contract_path)
        print(f"[info] Loaded bringup contract: {bringup_contract_path}")

    strict_validation_enabled = bool(generation_profile.get("strict_validation", False))
    contract_mode = str(generation_profile.get("contract_mode", "auto_fix_then_fail"))

    # Cross-reference check
    from modules.validation.cross_reference_validator import validate_and_report_cross_references
    if not validate_and_report_cross_references(soc_data, regs_data, irq_data, bus_data, pinmux_data, board_data):
        print("[error] Cross-reference validation failed")
        return 1

    # Load manifest / contract from target output
    bsp_manifest = None
    manifest_path = out_dir / "bsp_manifest.json"
    if manifest_path.exists():
        bsp_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(f"[info] Loaded manifest: {manifest_path}")
    else:
        print("[warn] bsp_manifest.json missing in output dir; using file-discovery fallback")

    api_contract_manifest = None
    contract_path = out_dir / "api_contract_manifest.json"
    if contract_path.exists():
        api_contract_manifest = json.loads(contract_path.read_text(encoding="utf-8"))
        print(f"[info] Loaded API contract manifest: {contract_path}")
    elif bsp_manifest:
        api_contract_manifest = build_api_contract_manifest(bsp_manifest, generation_profile)
        print("[info] Rebuilt API contract manifest from bsp_manifest.json")

    # Determine modules to validate
    api_catalog = (bsp_manifest or {}).get("api_catalog", {}) if isinstance(bsp_manifest, dict) else {}
    module_names = sorted(api_catalog.keys()) if api_catalog else _discover_generated_modules(out_dir)
    print(f"[info] Validating {len(module_names)} modules")

    from modules.validation.validation_engine import (
        validate_generation_output,
        extract_all_constants_from_directory,
        validate_facts_across_files,
    )
    from modules.validation.pass2_validator import validate_driver_implementation
    from modules.validation.validation_report import (
        ValidationReport,
        ValidationSummary,
        ModuleValidation,
        write_json_report,
        write_markdown_report,
        print_console_summary,
    )
    from modules.utils.dependency_resolver import build_dependency_graph, generate_init_order, validate_dependencies

    def _evaluate_modules_and_contracts() -> tuple[
        List[tuple[str, Any]],
        List[str],
        List[str],
        int,
        Optional[Dict[str, Any]],
    ]:
        pass2_results_local: List[tuple[str, Any]] = []
        contract_errors_local: List[str] = []
        contract_warnings_local: List[str] = []
        contract_checks_local = 0

        for module_name in module_names:
            files, module_header_path, module_source_path = _collect_validation_module_files(out_dir, module_name)
            if not files:
                continue

            manifest_entry = api_catalog.get(module_name, {})
            if not manifest_entry:
                manifest_entry = {
                    "init_function": f"{module_name}_Init",
                    "api_functions": [],
                    "dependencies": [],
                }

            validation_result = validate_generation_output(
                tag=f"pass2_{module_name.lower()}",
                preamble="",
                written_files=files,
                soc_data=soc_data,
                regs_data=regs_data,
            )

            if module_name.upper() not in {"SYSTEM", "VIM"}:
                pass2_result = validate_driver_implementation(
                    module_name=module_name,
                    manifest_entry=manifest_entry,
                    preamble="",
                    written_files=files,
                    soc_data=soc_data,
                    regs_data=regs_data,
                    bringup_contract=bringup_contract,
                )

                if not pass2_result.is_valid:
                    validation_result.is_valid = False
                    validation_result.errors.extend(pass2_result.critical_errors)
                    validation_result.warnings.extend(pass2_result.warnings)
            else:
                validation_result.warnings.append(
                    f"{module_name}: pass2 init-name check skipped in validate-only mode (covered by startup contract)"
                )

            module_contract_result = None
            if (
                api_contract_manifest
                and module_header_path
                and module_source_path
                and module_header_path.exists()
                and module_source_path.exists()
            ):
                module_contract_result = check_generated_module_contract(
                    module_name,
                    module_header_path,
                    module_source_path,
                    api_contract_manifest,
                )
                contract_checks_local += 1
                if module_contract_result and not module_contract_result.get("passed", True):
                    if contract_mode == "warn_only":
                        validation_result.warnings.extend(module_contract_result.get("errors", []))
                        validation_result.warnings.extend(module_contract_result.get("warnings", []))
                    else:
                        validation_result.is_valid = False
                        validation_result.errors.extend(module_contract_result.get("errors", []))
                        validation_result.warnings.extend(module_contract_result.get("warnings", []))
                    contract_errors_local.extend(module_contract_result.get("errors", []))
                    contract_warnings_local.extend(module_contract_result.get("warnings", []))

            setattr(validation_result, "compile_contract", module_contract_result)
            setattr(validation_result, "autofix_actions", [])
            pass2_results_local.append((module_name, validation_result))

        bsp_validate_contract_local: Optional[Dict[str, Any]] = None
        if api_contract_manifest:
            bsp_validate_candidates = [
                out_dir / "bsp_validate.c",
                out_dir / "include" / "bsp_validate.c",
                out_dir / "source" / "bsp_validate.c",
            ]
            bsp_validate_path = next((p for p in bsp_validate_candidates if p.exists()), bsp_validate_candidates[0])
            bsp_validate_contract_local = check_bsp_validate_contract(
                bsp_validate_path,
                api_contract_manifest,
            )
            if bsp_validate_contract_local:
                contract_checks_local += 1
                contract_errors_local.extend(bsp_validate_contract_local.get("errors", []))
                contract_warnings_local.extend(bsp_validate_contract_local.get("warnings", []))

        return (
            pass2_results_local,
            contract_errors_local,
            contract_warnings_local,
            contract_checks_local,
            bsp_validate_contract_local,
        )

    pass2_validation_results: List[tuple[str, Any]]
    compile_contract_errors: List[str]
    compile_contract_warnings: List[str]
    compile_contract_checks: int
    bsp_validate_contract_result: Optional[Dict[str, Any]]
    (
        pass2_validation_results,
        compile_contract_errors,
        compile_contract_warnings,
        compile_contract_checks,
        bsp_validate_contract_result,
    ) = _evaluate_modules_and_contracts()
    autofix_actions = []

    # Startup contract check (requires dependency graph)
    startup_contract_result = {
        "passes": True,
        "errors": [],
        "warnings": ["startup contract not evaluated"],
        "checks": {},
    }
    init_order = None
    dep_graph = None
    if bsp_manifest:
        try:
            dep_graph = build_dependency_graph(
                bsp_manifest,
                soc_data,
                selected_modules=module_names,
            )
            dep_errors = validate_dependencies(dep_graph, bsp_manifest)
            if dep_errors:
                startup_contract_result = {
                    "passes": False,
                    "errors": dep_errors,
                    "warnings": [],
                    "checks": {},
                }
            else:
                init_order = generate_init_order(dep_graph)
                startup_contract_result = validate_startup_contract(
                    init_order,
                    out_dir,
                    bringup_contract=bringup_contract,
                )
        except Exception as e:
            startup_contract_result = {
                "passes": False,
                "errors": [f"startup contract validation exception: {e}"],
                "warnings": [],
                "checks": {},
            }

    # Optional compile gate in validation-only mode
    build_gate_result = None
    build_gate_failed = False
    if args.run_build_gate:
        build_gate_overrides = {
            "ccs_workspace": args.ccs_workspace,
            "ccs_project": args.ccs_project,
            "ccs_config": args.ccs_config,
            "build_gate": args.build_gate,
            "build_gate_llm": args.build_gate_llm,
            "build_gate_llm_top_k": args.build_gate_llm_top_k,
            "build_gate_llm_model": args.build_gate_llm_model,
            "model": args.model,
        }
        build_gate_result = run_ccs_build_gate(
            output_dir=out_dir,
            generation_profile=generation_profile,
            overrides=build_gate_overrides,
            api_contract_manifest=api_contract_manifest,
            bringup_contract=bringup_contract,
            run_model_name=args.model,
            progress_callback=print,
        )
        print(
            f"[info] Compile gate status: {build_gate_result.get('status')} "
            f"(passes={bool(build_gate_result.get('passes', False))}, "
            f"rounds={len(build_gate_result.get('rounds', []))})"
        )
        build_gate_failed = gate_should_fail_run(build_gate_result)

        # Re-evaluate startup contract against post-build-gate fixed files.
        if init_order is not None:
            startup_contract_result = validate_startup_contract(
                init_order,
                out_dir,
                bringup_contract=bringup_contract,
            )

        gate_applied_fixes = any(
            bool(round_entry.get("fix_actions"))
            for round_entry in (build_gate_result.get("rounds", []) if isinstance(build_gate_result, dict) else [])
        )
        if gate_applied_fixes:
            print("[info] Re-running validate-only module/contract checks after build-gate fixes...")
            (
                pass2_validation_results,
                compile_contract_errors,
                compile_contract_warnings,
                compile_contract_checks,
                bsp_validate_contract_result,
            ) = _evaluate_modules_and_contracts()

    parity_result = run_parity_guard(
        out_dir,
        parity_guard_cfg.get("baseline_path"),
        mode=parity_guard_cfg.get("mode", "critical_only"),
        critical_registers=parity_guard_cfg.get("critical_registers"),
    )
    if not bool((parity_result or {}).get("passes", True)):
        print("[warn] Parity guard detected critical register sequence drift in validate-only mode")

    # Build final report
    final_report = ValidationReport(
        timestamp=_now_tag(),
        bsp_output_dir=str(out_dir),
    )

    for module_name, validation_result in sorted(pass2_validation_results, key=lambda item: item[0]):
        constants_validated = 0
        mismatches = 0
        if validation_result.facts_validation:
            constants_validated = len(validation_result.facts_validation.matches) + len(validation_result.facts_validation.mismatches)
            mismatches = len(validation_result.facts_validation.mismatches)

        module_validation = ModuleValidation(
            module_name=module_name,
            facts_mirror_valid=validation_result.is_valid and len(validation_result.errors) == 0,
            constants_validated=constants_validated,
            mismatches=mismatches,
            tests_generated=False,
            critical_errors=list(validation_result.errors[:10]),
            warnings=list(validation_result.warnings[:10]),
        )
        final_report.peripheral_validations[module_name] = module_validation

    final_report.validation_summary = ValidationSummary(
        total_modules=len(final_report.peripheral_validations),
        modules_valid=sum(1 for v in final_report.peripheral_validations.values() if v.facts_mirror_valid),
        modules_invalid=sum(1 for v in final_report.peripheral_validations.values() if not v.facts_mirror_valid),
        critical_errors=sum(len(v.critical_errors) for v in final_report.peripheral_validations.values()),
        warnings=sum(len(v.warnings) for v in final_report.peripheral_validations.values()),
        success_rate=(
            (sum(1 for v in final_report.peripheral_validations.values() if v.facts_mirror_valid) / len(final_report.peripheral_validations)) * 100.0
            if final_report.peripheral_validations
            else 0.0
        ),
    )

    compile_contract_passes = len(compile_contract_errors) == 0 or contract_mode == "warn_only"
    if contract_mode == "warn_only" and compile_contract_errors:
        compile_contract_warnings.extend(compile_contract_errors)
        compile_contract_errors = []

    final_report.compile_contract = {
        "passes": compile_contract_passes,
        "checks": compile_contract_checks,
        "errors": compile_contract_errors,
        "warnings": compile_contract_warnings,
    }
    final_report.autofix_actions = autofix_actions
    final_report.startup_contract = startup_contract_result
    final_report.critical_sequence_mismatches = list(
        (parity_result or {}).get("critical_sequence_mismatches", [])
    )

    if build_gate_result:
        final_report.build_evidence = {
            "mode": "generator_ccs_build_gate",
            "required": bool(build_gate_result.get("required", False)),
            "status": build_gate_result.get("status"),
            "passes": bool(build_gate_result.get("passes", False)),
            "rounds": len(build_gate_result.get("rounds", [])),
            "error_summary": build_gate_result.get("error_summary", {}),
            "configuration": build_gate_result.get("configuration"),
            "external_workspace_path": build_gate_result.get("external_workspace_path"),
            "project_name": build_gate_result.get("project_name"),
            "llm_rewrite_attempted": bool(build_gate_result.get("llm_rewrite_attempted", False)),
            "llm_rewrite_applied": bool(build_gate_result.get("llm_rewrite_applied", False)),
            "llm_rewrite_target_files": list(build_gate_result.get("llm_rewrite_target_files", [])),
            "llm_rewrite_tokens": dict(build_gate_result.get("llm_rewrite_tokens", {})),
            "llm_rewrite_failure_reason": build_gate_result.get("llm_rewrite_failure_reason"),
        }
    else:
        final_report.build_evidence = {
            "mode": "validation_only",
            "required": False,
            "status": "not_run",
        }

    if api_contract_manifest:
        final_report.api_contract_hash = api_contract_manifest.get("api_contract_hash")

    final_report.runtime_invariants = {
        "validation_only_mode": True,
        "bringup_contract_loaded": bool(bringup_contract),
        "bringup_mode": bringup_mode,
        "fail_on_contract_mismatch": fail_on_contract_mismatch,
        "startup_contract_gate_mode": startup_gate_mode,
        "run_build_gate": bool(args.run_build_gate),
        "parity_guard_mode": parity_guard_cfg.get("mode"),
        "parity_guard_passes": bool((parity_result or {}).get("passes", True)),
        "parity_guard_baseline": str(parity_guard_cfg.get("baseline_path") or ""),
        "serial_primary_path": (
            (bringup_contract or {}).get("serial", {}).get("primary_path")
            if isinstance(bringup_contract, dict)
            else None
        ),
        "startup_contract_passes": startup_contract_result.get("passes", True),
    }

    # Cross-file validation
    try:
        all_constants = extract_all_constants_from_directory(out_dir)
        if all_constants:
            cross_file_validation = validate_facts_across_files(all_constants, soc_data)
            final_report.cross_file_validation = {
                "passes": cross_file_validation.passes,
                "conflicts": [str(c) for c in cross_file_validation.conflicts],
                "consistency_score": cross_file_validation.consistency_score,
                "errors": cross_file_validation.errors,
                "warnings": cross_file_validation.warnings,
            }
    except Exception as e:
        print(f"[warn] Cross-file validation failed: {e}")

    if dep_graph and init_order:
        final_report.dependency_graph_info = {
            "total_nodes": len(dep_graph.nodes),
            "has_cycles": init_order.has_cycles,
            "init_order": init_order.order if init_order.is_valid() else [],
            "cycle_nodes": init_order.cycle_nodes if init_order.has_cycles else [],
        }

    json_path = out_dir / "validation_report.json"
    md_path = out_dir / "validation_report.md"
    write_json_report(final_report, json_path)
    write_markdown_report(final_report, md_path)

    print(f"[ok] Validation report updated: {json_path}")
    print(f"[ok] Validation report updated: {md_path}")
    print_console_summary(final_report)

    _augment_compile_gate_report(
        out_dir,
        build_gate_result,
        startup_contract_result,
        startup_gate_mode,
        parity_result,
    )

    if startup_gate_mode == "fail" and not startup_contract_result.get("passes", True):
        print("[error] Startup contract gate failed in validate-only mode.")
        return 2
    if startup_gate_mode == "fail" and not bool((parity_result or {}).get("passes", True)):
        print("[error] Parity guard gate failed in validate-only mode.")
        return 2
    if build_gate_failed:
        print("[error] Strict CCS compile gate failed in validate-only mode.")
        return 3

    return 0

# ---------------- Main ----------------
async def main():
    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(
        description="YAML-in -> Claude -> BSP-out (multi-peripheral BSP)"
    )
    parser.add_argument(
        "--out",
        default=".",
        help="Base output directory. A subdir output_<timestamp> will be created.",
    )
    parser.add_argument(
        "--model",
        default="sonnet4.5",
        choices=["haiku3.0", "haiku4.5", "sonnet3.5", "sonnet4.5", "opus4.5", "opus4.6"],
        help="Which Claude model to use for generation. Default: sonnet4.5",
    )
    parser.add_argument(
        "--yamlpath",
        default="yaml_in",
        help="Origin directory for YAML files used in code generation",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=20000,
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["all"],
        choices=["all", "startup", "entry", "system", "clock", "linker", "vim", "peripherals"],
        help=(
            "Which components to generate. "
            "Choices: all, startup (start.s), entry (entry.c), "
            "system (system.c/h), linker (linker.cmd), vim (VIM driver), peripherals (drivers). "
            "Default: all."
        ),
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip cost confirmation prompt and proceed automatically",
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        help=(
            "Specify peripheral modules to generate (e.g., --modules SCI LIN GIO). "
            "If not specified, will prompt interactively. "
            "Use with --targets peripherals or --targets all."
        ),
    )
    parser.add_argument(
        "--include-tests",
        action="store_true",
        help="Include test harness in main.c (conditional on BSP_RUN_TESTS define)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock API responses for testing (no real API calls, no cost)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run validation/reporting only on an existing generated output directory (no LLM generation).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Existing output_<timestamp> directory to validate when --validate-only is set.",
    )
    parser.add_argument(
        "--run-build-gate",
        action="store_true",
        help="When --validate-only is set, also run external CCS compile gate on the existing output.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional generation profile YAML path (e.g., yaml_in/generation_profile.yaml)",
    )
    parser.add_argument(
        "--ccs-workspace",
        default=None,
        help="Override build_gate.external_workspace_path for external CCS compile gate",
    )
    parser.add_argument(
        "--ccs-project",
        default=None,
        help="Override build_gate.project_name for external CCS compile gate",
    )
    parser.add_argument(
        "--ccs-config",
        default=None,
        choices=["Debug", "Release"],
        help="Override build_gate.configuration (Debug/Release)",
    )
    parser.add_argument(
        "--build-gate",
        default=None,
        choices=["strict", "advisory", "off"],
        help="Override build_gate.mode (strict/advisory/off)",
    )
    parser.add_argument(
        "--build-gate-llm",
        default=None,
        choices=["on", "off"],
        help="Override build_gate.llm_rewrite.enabled (on/off)",
    )
    parser.add_argument(
        "--build-gate-llm-top-k",
        type=int,
        default=None,
        help="Override build_gate.llm_rewrite.top_k_files",
    )
    parser.add_argument(
        "--build-gate-llm-model",
        default=None,
        choices=["inherit", "haiku4.5", "sonnet4.5", "opus4.5", "opus4.6"],
        help="Override build_gate.llm_rewrite.model",
    )
    args = parser.parse_args()

    if args.validate_only:
        return _run_validation_only(args)

    # Enable mock mode if requested
    if args.mock:
        import os
        os.environ["BSP_MOCK_MODE"] = "1"

    # Parse target flags
    targets = set(args.targets)
    generate_start = "all" in targets or "startup" in targets
    generate_entry = "all" in targets or "entry" in targets
    generate_system = "all" in targets or "system" in targets
    generate_linker = "all" in targets or "linker" in targets
    generate_vim = "all" in targets or "vim" in targets
    # Clock generation disabled - PLL module provides clock APIs directly
    generate_clock = False  # "all" in targets or "clock" in targets
    generate_peripherals = "all" in targets or "peripherals" in targets

    # Setup output directories
    base_out = Path(args.out)
    run_tag = _now_tag()
    out_dir = base_out / f"output_{run_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Initialize unified progress manager EARLY (before any print statements)
    import os
    from modules.utils.unified_progress import UnifiedProgressManager
    progress_mode = os.getenv("BSP_PROGRESS_MODE", "fancy")
    enable_fancy = progress_mode == "fancy" and sys.stdout.isatty()

    passes = ["Discovery", "Implementation", "Platform", "Validation"]
    progress_manager = UnifiedProgressManager(
        passes=passes,
        output_dir=out_dir,
        enable_fancy=enable_fancy,
        enable_color=True,  # Enable colors for better visual distinction
        cost_tracker=None  # Will set later after cost tracker is initialized
    )

    # Print initial messages
    if args.mock:
        progress_manager.log_or_print("[info] Mock mode enabled - using simulated API responses (no cost)")

    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Load YAMLs
    soc_data = load_soc_yaml(Path(args.yamlpath) / "soc.yaml")
    regs_data = load_regs_yaml(Path(args.yamlpath) / "regs.yaml")
    irq_data = load_irq_yaml(Path(args.yamlpath) / "irq.yaml")
    memmap_data = load_memmap_yaml(Path(args.yamlpath) / "memmap.yaml")
    bus_data = load_bus_yaml(Path(args.yamlpath) / "bus.yaml")
    pinmux_data = load_pinmux_yaml(Path(args.yamlpath) / "pinmux.yaml")
    board_data = load_board_yaml(Path(args.yamlpath) / "board.yaml")

    # Load optional profile and merge with defaults
    profile_data = None
    if args.profile:
        profile_data = load_generation_profile(Path(args.profile))
        print(f"[info] Loaded generation profile: {args.profile}")
    elif (Path(args.yamlpath) / "generation_profile.yaml").exists():
        profile_path = Path(args.yamlpath) / "generation_profile.yaml"
        profile_data = load_generation_profile(profile_path)
        print(f"[info] Loaded generation profile: {profile_path}")

    generation_profile = _merge_generation_profile(profile_data)
    bringup_cfg = generation_profile.get("bringup", {}) if isinstance(generation_profile.get("bringup", {}), dict) else {}
    bringup_mode = str(bringup_cfg.get("mode", "strict")).strip().lower()
    if bringup_mode not in {"strict", "relaxed"}:
        print(f"[warn] Unknown bringup.mode '{bringup_mode}', defaulting to 'strict'")
        bringup_mode = "strict"
    bringup_strict = bringup_mode == "strict"
    fail_on_contract_mismatch = bool(bringup_cfg.get("fail_on_contract_mismatch", True))
    startup_gate_mode = _resolve_startup_gate_mode(
        generation_profile,
        bringup_strict=bringup_strict,
        fail_on_contract_mismatch=fail_on_contract_mismatch,
    )
    parity_guard_cfg = _resolve_parity_guard_config(generation_profile, Path(args.yamlpath))

    bringup_contract = None
    bringup_contract_path: Optional[Path] = None

    def _resolve_bringup_contract_path(contract_file: str) -> Optional[Path]:
        candidates = []
        raw_path = Path(contract_file)
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            candidates.append(Path.cwd() / raw_path)
            candidates.append(Path(args.yamlpath) / raw_path)
            candidates.append(Path(args.yamlpath).parent / raw_path)
            candidates.append(Path(args.yamlpath) / raw_path.name)

        seen = set()
        for candidate in candidates:
            normalized = candidate.resolve()
            if normalized in seen:
                continue
            seen.add(normalized)
            if normalized.exists():
                return normalized
        return None

    configured_contract_file = bringup_cfg.get("contract_file")
    if isinstance(configured_contract_file, str) and configured_contract_file.strip():
        bringup_contract_path = _resolve_bringup_contract_path(configured_contract_file.strip())
        if bringup_contract_path is None:
            print(f"[warn] bringup.contract_file not found: {configured_contract_file}")
    else:
        default_contract = Path(args.yamlpath) / "bringup_contract.yaml"
        if default_contract.exists():
            bringup_contract_path = default_contract

    if startup_gate_mode == "fail" and bringup_contract_path is None:
        raise ValueError(
            "startup_contract.gate_mode=fail requires a valid bringup_contract file, but none was found."
        )

    if bringup_contract_path is not None:
        bringup_contract = load_bringup_contract(bringup_contract_path)
        print(f"[info] Loaded bringup contract: {bringup_contract_path}")

    strict_validation_enabled = bool(generation_profile.get("strict_validation", False))
    contract_mode = str(generation_profile.get("contract_mode", "auto_fix_then_fail"))
    contract_lock_mode = str(generation_profile.get("contract_lock_mode", "strict")).strip().lower()
    if contract_lock_mode not in {"strict", "relaxed"}:
        print(f"[warn] Unknown contract_lock_mode '{contract_lock_mode}', defaulting to 'strict'")
        contract_lock_mode = "strict"
    require_ccs_proof = bool(generation_profile.get("require_ccs_proof", True))
    build_gate_cfg = generation_profile.get("build_gate", {}) if isinstance(generation_profile.get("build_gate", {}), dict) else {}
    build_gate_mode = str(args.build_gate or build_gate_cfg.get("mode", "strict")).strip().lower()
    if build_gate_mode not in {"strict", "advisory", "off"}:
        print(f"[warn] Unknown build_gate.mode '{build_gate_mode}', defaulting to 'strict'")
        build_gate_mode = "strict"
    build_gate_enabled = bool(build_gate_cfg.get("enabled", True)) and build_gate_mode != "off"
    ccs_workspace_override = args.ccs_workspace
    ccs_project_override = args.ccs_project
    ccs_config_override = args.ccs_config
    build_gate_overrides = {
        "ccs_workspace": ccs_workspace_override,
        "ccs_project": ccs_project_override,
        "ccs_config": ccs_config_override,
        "build_gate": build_gate_mode,
        "build_gate_llm": args.build_gate_llm,
        "build_gate_llm_top_k": args.build_gate_llm_top_k,
        "build_gate_llm_model": args.build_gate_llm_model,
        "model": args.model,
    }
    if build_gate_enabled and build_gate_mode == "strict":
        strict_workspace = str(ccs_workspace_override or build_gate_cfg.get("external_workspace_path", "")).strip()
        strict_project = str(ccs_project_override or build_gate_cfg.get("project_name", "")).strip()
        if not strict_workspace or not strict_project:
            raise ValueError(
                "build_gate.mode=strict requires both build_gate.external_workspace_path and build_gate.project_name "
                "(or --ccs-workspace/--ccs-project overrides)."
            )
        if not Path(strict_workspace).exists():
            raise ValueError(
                f"build_gate.mode=strict external workspace path does not exist: {strict_workspace}"
            )
        strict_project_path = Path(strict_workspace) / strict_project
        if not strict_project_path.exists():
            raise ValueError(
                f"build_gate.mode=strict CCS project path does not exist: {strict_project_path}"
            )

    target_board_name = generation_profile.get("target_board")
    actual_board_name = board_data.get("board", {}).get("name")
    if target_board_name and actual_board_name and target_board_name != actual_board_name:
        print(f"[warn] Profile target_board '{target_board_name}' != board.yaml name '{actual_board_name}'")

    # Inject profile/bring-up defaults into SOC slices consumed by prompts
    default_baud = generation_profile.get("sci", {}).get("default_baud")
    if not isinstance(default_baud, int) and isinstance(bringup_contract, dict):
        serial_cfg = bringup_contract.get("serial", {})
        if isinstance(serial_cfg, dict) and isinstance(serial_cfg.get("baud_default"), int):
            default_baud = serial_cfg.get("baud_default")
    if isinstance(default_baud, int):
        for periph in soc_data.get("soc", {}).get("peripherals", []):
            if periph.get("name", "").upper() in {"SCI", "LIN"}:
                x_ext = periph.setdefault("x-ext", {})
                if isinstance(x_ext, dict):
                    x_ext["default_baud"] = default_baud

    # Validate cross-file references
    from modules.validation.cross_reference_validator import validate_and_report_cross_references
    if not validate_and_report_cross_references(soc_data, regs_data, irq_data, bus_data, pinmux_data, board_data):
        print("[error] Cross-reference validation failed - see errors above")
        return 1

    # Setup model and system prompt
    system_prompt = build_system_prompt()
    model_enum = {
        "haiku3.0": Model.HAIKU_3_0,
        "haiku4.5": Model.HAIKU_4_5,
        "sonnet3.5": Model.SONNET_3_5,
        "sonnet4.5": Model.SONNET_4_5,
        "opus4.5": Model.OPUS_4_5,
        "opus4.6": Model.OPUS_4_6,
    }[args.model]

    # Load adaptive token allocator
    from modules.regeneration.token_strategy import AdaptiveTokenAllocator
    token_allocator = AdaptiveTokenAllocator()
    token_history_path = out_dir.parent / ".token_history.json"
    if args.mock:
        progress_manager.log_or_print("[info] Mock mode: skipping token history load/save")
    else:
        token_allocator.load_history(token_history_path)
        progress_manager.log_or_print(f"[info] Loaded token history from {token_history_path.name}")

    # Reset cost tracker for this generation run
    _cost_tracker.reset()

    # Update progress manager with cost tracker and model name
    progress_manager.cost_tracker = _cost_tracker
    progress_manager.model_name = model_enum.get_display_name()

    # Suppress Python logging output in fancy mode to avoid cluttering display
    if progress_manager.should_suppress_prints():
        import logging
        logging.basicConfig(level=logging.CRITICAL)  # Only show critical errors

    # --- SELECT PERIPHERALS FIRST ---
    from modules.generation.discovery import run_discovery_pass
    from modules.generation.implementation import run_implementation_pass

    # Peripheral selection strategy:
    # - Pass 1 (Manifest): Generate API catalog for CORE + user selections
    # - Pass 2 (Drivers): Generate drivers for PLL, IOMM, PCR + user selections
    #   - PLL driver provides clock APIs (PLL_EnableClock, PLL_GetFrequency)
    #   - IOMM driver provides pin multiplexing (IOMM_Init, IOMM_ConfigurePin)
    #   - PCR driver provides power control (PCR_Init, PCR_EnablePeripheral)
    #   - SYSTEM and VIM are platform files (Pass 3)
    # - Pass 3 (Platform): Always generate system.c, vim.c, entry.c, start.s, linker.cmd

    user_selected_peripherals = []  # User-chosen peripherals only
    pass1_modules = list(CORE_MODULES)  # Pass 1: Always include core for manifest
    pass2_modules = ["PLL", "IOMM", "PCR"]  # Pass 2: Core infrastructure drivers

    if generate_peripherals:
        profile_enabled = generation_profile.get("modules", {}).get("enabled", [])

        # Selection priority:
        # 1) explicit CLI modules
        # 2) profile modules
        # 3) interactive prompt
        if args.modules:
            progress_manager.log_or_print(f"[info] Using peripherals from command line: {', '.join(args.modules)}")
            # Filter soc_data to only include specified modules
            all_peripherals = get_peripheral_list(soc_data)
            chosen_peripherals = [p for p in all_peripherals if p.get("name", "").upper() in [m.upper() for m in args.modules]]
            if len(chosen_peripherals) != len(args.modules):
                found_names = [p.get("name") for p in chosen_peripherals]
                missing = set(m.upper() for m in args.modules) - set(n.upper() for n in found_names)
                print(f"[warn] Could not find modules: {', '.join(missing)}")
        elif profile_enabled:
            enabled_upper = {m.upper() for m in profile_enabled}
            all_peripherals = get_peripheral_list(soc_data)
            chosen_peripherals = [p for p in all_peripherals if p.get("name", "").upper() in enabled_upper]
            progress_manager.log_or_print(
                f"[info] Using modules from profile: {', '.join(profile_enabled)}"
            )
        else:
            print("\n[user] Select Peripherals for BSP Generation:")
            print("[info] Core infrastructure (SYSTEM, VIM) are platform files; PLL driver provides clock APIs")
            chosen_peripherals = prompt_user_for_peripherals(soc_data)

        if chosen_peripherals:
            user_selected_peripherals = [p.get("name") for p in chosen_peripherals]
            # Add user selections to pass1 for manifest, avoiding duplicates
            pass1_modules.extend([m for m in user_selected_peripherals if m not in pass1_modules])
            # Pass 2 implements core drivers + user peripherals (exclude SYSTEM and VIM which are Pass 3 platform files)
            pass2_modules.extend([m for m in user_selected_peripherals if m not in ["SYSTEM", "VIM"]])
            progress_manager.log_or_print(f"[info] Manifest will include {len(pass1_modules)} modules ({len(CORE_MODULES)} core + {len(user_selected_peripherals)} peripheral)")
            progress_manager.log_or_print(f"[info] Will implement {len(pass2_modules)} drivers (PLL/IOMM/PCR + {len(user_selected_peripherals)} peripherals)")
        else:
            print(f"[info] No peripherals selected. Will generate core drivers: PLL, IOMM, PCR")
    else:
        print("[info] Skipping peripheral driver selection due to --targets flag.")

    # --- COST ESTIMATION ---
    # IMPORTANT: Always show cost estimation and confirmation, regardless of progress mode
    if pass1_modules:
        print("\n[info] Cost Estimation:")

        pricing = model_enum.get_pricing()
        estimate = token_allocator.estimate_cost(len(pass1_modules), pricing)

        print(f"  Model: {model_enum.get_display_name()}")
        print(f"  Modules to generate: {estimate['num_modules']}")
        print(f"  Estimated tokens: {estimate['total_tokens']:,}")

        # Show breakdown by pass
        if 'breakdown' in estimate:
            breakdown = estimate['breakdown']
            print(f"    Pass 1 (headers):    {breakdown['pass1_tokens']:,}")
            print(f"    Pass 2 (drivers):    {breakdown['pass2_tokens']:,}")
            print(f"    Pass 3 (platform):   {breakdown['pass3_tokens']:,}")

        print(f"  Estimated cost: ${estimate['cost_usd']:.2f} USD")

        if not estimate['has_history']:
            print(f"  [note] No historical data available - estimate based on default values")

        # Ask for confirmation (unless --yes flag is set)
        if not args.yes:
            try:
                response = input("\n[user] Proceed with generation? [Y/n]: ").strip().lower()
                if response in ['n', 'no', 'exit', 'quit']:
                    print("[info] Generation cancelled by user.")
                    return
            except (KeyboardInterrupt, EOFError):
                print("\n[info] Generation cancelled by user.")
                return
        else:
            print("  [auto] Proceeding automatically (--yes flag set)")

    # NOW clear screen and start fancy progress display (after user has confirmed)
    # Add a small delay so user can see the confirmation message
    import time
    time.sleep(0.3)

    if progress_manager.mode == "fancy" and progress_manager.supports_ansi:
        sys.stdout.write('\033[2J')  # Clear screen
        sys.stdout.write('\033[H')   # Move to top
        sys.stdout.flush()

    # --- PRE-INJECT CLOCK DOMAINS INTO PLL ---
    # Collect all clock_ref values from all peripherals so the PLL manifest
    # can generate a complete clock_domain_t enum without needing to see all
    # peripherals during its isolated manifest generation step.
    all_clock_domains = gather_all_clock_domains(soc_data, bus_data)
    if all_clock_domains:
        print(f"[info] Discovered {len(all_clock_domains)} clock domains: {', '.join(all_clock_domains)}")
        # Inject into PLL peripheral's x-ext so the manifest prompt can find it
        for periph in soc_data.get("peripherals", []):
            if periph.get("name", "").upper() == "PLL":
                if "x-ext" not in periph or periph["x-ext"] is None:
                    periph["x-ext"] = {}
                periph["x-ext"]["all_clock_domains"] = all_clock_domains
                break

    # --- PASS 1: Architecture Discovery ---
    bsp_manifest = None
    api_contract_manifest = None
    startup_contract_result = None
    bringup_contract_failed = False
    parity_result: Optional[Dict[str, Any]] = None
    bsp_validate_contract_result = None
    bsp_validate_autofix_actions = []
    build_gate_result: Optional[Dict[str, Any]] = None
    build_gate_failed = False
    if pass1_modules or not generate_peripherals:
        progress_manager.log_or_print("\n[info] Starting Pass 1: Architecture Discovery...")
        bsp_manifest = await run_discovery_pass(
            soc_data,
            regs_data,
            model_enum,
            out_dir,
            max_tokens=args.max_tokens,
            token_allocator=token_allocator,
            enable_validation=True,
            allowed_modules=pass1_modules if pass1_modules else None,
            bus_data=bus_data,
            progress_manager=progress_manager
        )
        progress_manager.log_or_print("\n[info] Pass 1 Complete.")

        # Check for shutdown request
        if _shutdown_requested:
            print("[info] Shutdown requested. Stopping after Pass 1.")
            return

        # --- CREATE MANIFEST ALIASES ---
        # Some hardware modules need API aliases so peripherals can reference them
        # Example: PLL hardware -> clock API (peripherals call clock_enable, not PLL_Enable)
        if bsp_manifest and CORE_MANIFEST_ALIASES:
            api_catalog = bsp_manifest.get("api_catalog", {})
            for hw_name, api_name in CORE_MANIFEST_ALIASES.items():
                if hw_name in api_catalog and api_name not in api_catalog:
                    # Create alias entry (copy of hardware entry with different name)
                    alias_entry = api_catalog[hw_name].copy()
                    alias_entry["module_name"] = api_name
                    # Update function names to use alias (PLL_Init -> clock_init)
                    if "init_function" in alias_entry:
                        alias_entry["init_function"] = alias_entry["init_function"].replace(hw_name, api_name)
                    # Update header file names
                    if "driver_header_file" in alias_entry:
                        alias_entry["driver_header_file"] = alias_entry["driver_header_file"].replace(hw_name.lower(), api_name.lower())
                    if "reg_header_file" in alias_entry:
                        alias_entry["reg_header_file"] = alias_entry["reg_header_file"].replace(hw_name.lower(), api_name.lower())

                    api_catalog[api_name] = alias_entry
                    print(f"[info] Created manifest alias: {hw_name} -> {api_name}")

            # Save updated manifest with aliases
            manifest_path = out_dir / "bsp_manifest.json"
            manifest_path.write_text(json.dumps(bsp_manifest, indent=2), encoding="utf-8")

        if bsp_manifest:
            api_contract_manifest = build_api_contract_manifest(bsp_manifest, generation_profile)
            contract_path = write_api_contract_manifest(out_dir, api_contract_manifest)
            print(f"[ok] API contract manifest written: {contract_path}")

        # --- DEPENDENCY RESOLUTION ---
        # Resolve dependencies to include PCR and other required modules
        if generate_peripherals and pass2_modules and bsp_manifest:
            print("[info] Resolving module dependencies...")
            original_count = len(pass2_modules)
            pass2_modules = resolve_dependencies(pass2_modules, bsp_manifest)

            if len(pass2_modules) > original_count:
                added = set(pass2_modules) - set([m.upper() for m in pass2_modules[:original_count]])
                print(f"[info] Auto-included dependencies: {', '.join(sorted(added))}")

        # --- PASS 2: Implementation ---
        pass2_validation_results = []
        if pass2_modules:
            progress_manager.log_or_print(f"\n[info] Starting Pass 2: Implementation for {len(pass2_modules)} peripheral drivers...")
            pass2_validation_results = await run_implementation_pass(
                bsp_manifest,
                soc_data,
                board_data,
                bus_data,
                pinmux_data,
                model_enum,
                out_dir,
                max_tokens=args.max_tokens,
                allowed_modules=pass2_modules,
                regs_data=regs_data,
                enable_validation=True,
                strict_validation=strict_validation_enabled,
                contract_mode=contract_mode,
                api_contract_manifest=api_contract_manifest,
                bringup_contract=bringup_contract,
                bringup_strict=bringup_strict,
                token_allocator=token_allocator,
                progress_manager=progress_manager
            )
            progress_manager.log_or_print("\n[info] Pass 2 Complete.")

            if api_contract_manifest:
                if contract_lock_mode == "relaxed":
                    api_contract_manifest = hydrate_contract_from_generated_headers(
                        out_dir,
                        api_contract_manifest,
                    )
                    write_api_contract_manifest(out_dir, api_contract_manifest)
                    print("[ok] API contract manifest hydrated from generated headers (relaxed lock mode)")
                else:
                    print("[info] Contract lock mode is strict: skipping header hydration to preserve canonical contract")

            # Check for shutdown request
            if _shutdown_requested:
                print("[info] Shutdown requested. Stopping after Pass 2.")
                return
        else:
            print("\n[info] Skipping Pass 2 (No modules selected).")
    else:
        print("\n[info] Skipping Pass 1 and Pass 2 (No modules selected).")

    # Check for shutdown request before continuing
    if _shutdown_requested:
        print("[info] Shutdown requested. Stopping before platform generation.")
        return

    # --- DEPENDENCY RESOLUTION & INIT ORDERING ---
    print("\n[info] Building dependency graph and generating initialization sequence...")

    try:
        from modules.utils.dependency_resolver import (
            build_dependency_graph,
            generate_init_order,
            validate_dependencies,
            generate_main_c
        )

        # Build dependency graph for ALL modules (core + peripherals)
        # main.c needs to initialize both platform files (core) and drivers (peripherals)
        dep_graph = build_dependency_graph(
            bsp_manifest,
            soc_data,
            selected_modules=pass1_modules
        )

        # Validate dependencies before resolution
        dep_errors = validate_dependencies(dep_graph, bsp_manifest)
        if dep_errors:
            print(f"[error] Invalid dependencies found:")
            for error in dep_errors:
                print(f"  - {error}")
            raise ValueError("Dependency validation failed")

        # Generate initialization order
        init_order = generate_init_order(dep_graph)

        if init_order.is_valid():
            print(f"[ok] Dependency graph valid - {len(init_order.order)} modules")
            print(f"[info] Init order: {' -> '.join(init_order.order[:5])}{'...' if len(init_order.order) > 5 else ''}")
            startup_contract_result = validate_startup_contract(
                init_order,
                out_dir,
                bringup_contract=bringup_contract,
            )
            if not startup_contract_result.get("passes", True):
                print("[warn] Startup contract validation failed before main.c generation")
                for err in startup_contract_result.get("errors", [])[:5]:
                    print(f"  - {err}")

            # Generate main.c with correct init sequence
            main_c_path = generate_main_c(
                init_order,
                dep_graph,
                out_dir,
                include_tests=args.include_tests,
                manifest=bsp_manifest,
                generation_profile=generation_profile,
                board_data=board_data,
                bringup_contract=bringup_contract,
                api_contract_manifest=api_contract_manifest,
            )
            test_msg = " with test harness" if args.include_tests else ""
            print(f"[ok] Generated {main_c_path.name} with dependency-ordered init sequence{test_msg}")

            # Validate and autofix bsp_validate helper contract drift deterministically
            if api_contract_manifest:
                bsp_validate_candidates = [
                    out_dir / "bsp_validate.c",
                    out_dir / "include" / "bsp_validate.c",
                    out_dir / "source" / "bsp_validate.c",
                ]
                bsp_validate_path = next((p for p in bsp_validate_candidates if p.exists()), bsp_validate_candidates[0])
                bsp_validate_contract_result = check_bsp_validate_contract(
                    bsp_validate_path,
                    api_contract_manifest,
                )
                if not bsp_validate_contract_result.get("passed", True):
                    if contract_mode == "auto_fix_then_fail":
                        fix_result = autofix_bsp_validate(bsp_validate_path, api_contract_manifest)
                        for action in fix_result.get("actions", []):
                            bsp_validate_autofix_actions.append(
                                {"module": "BSP_VALIDATE", "action": action}
                            )
                        bsp_validate_contract_result = check_bsp_validate_contract(
                            bsp_validate_path,
                            api_contract_manifest,
                        )
        else:
            print(f"[error] Circular dependency detected!")
            print(f"[error] Cycle: {' -> '.join(init_order.cycle_nodes)}")
            print(f"[warn] Skipping main.c generation due to dependency cycle")

    except Exception as e:
        print(f"[warn] Dependency resolution error: {e}")
        import traceback
        traceback.print_exc()

    print("\n[info] Proceeding to Platform Generation...")

    # --- PASS 3: Platform & System Files ---
    # Restoring logic for linker, startup, system, etc.
    
    # Re-setup model/prompt if needed (mostly reusing existing)
    system_prompt = build_system_prompt()
    
    print("[info] Preparing Platform prompts...")
    
    start_user_prompt = None
    if generate_start:
        start_user_prompt = build_start_asm_prompt()

    entry_user_prompt = None
    if generate_entry:
        entry_user_prompt = build_entry_prompt()

    clock_user_prompt = None
    if generate_clock:
        system_soc_slice, system_regs_slice = build_system_slices_for_prompt(
            soc_data, regs_data
        )
        clock_user_prompt = build_clock_prompt(
            soc_yaml=system_soc_slice,
            regs_yaml=system_regs_slice,
            bus_yaml=dump_yaml_str(bus_data),
            manifest=bsp_manifest
        )

    system_init_user_prompt = None
    if generate_system:
        system_soc_slice, system_regs_slice = build_system_slices_for_prompt(
            soc_data, regs_data
        )
        # Build a focused bus slice (sources, domains, SYSTEM clock numbers only)
        system_bus_slice = _build_system_bus_slice(bus_data) if bus_data else ""
        system_init_user_prompt = build_system_init_prompt(
            system_soc_slice, system_regs_slice,
            manifest=bsp_manifest,
            bus_yaml=system_bus_slice,
            bringup_contract=bringup_contract,
        )

    linker_user_prompt = None
    if generate_linker:
        memmap_slice_str = build_memmap_slice_for_prompt(memmap_data)
        linker_user_prompt = build_linker_prompt(memmap_slice_str)

    vim_user_prompt = None
    if generate_vim:
        vim_soc_slice, vim_regs_slice, _ = build_peripheral_slices_for_prompt(
            soc_data, regs_data, irq_data, "VIM"
        )
        # Note: We keep VIM here because it often needs IRQ data which generic Pass 2 might not fully utilize yet.
        vim_user_prompt = build_vim_prompt(
            vim_soc_slice, vim_regs_slice, dump_yaml_str(irq_data)
        )

    # Build generation tasks for Platform files
    generation_tasks = []

    if generate_start:
        generation_tasks.append(
            _generate_startup(
                system_prompt, model_enum, args.max_tokens, artifacts, out_dir,
                start_user_prompt, token_allocator, progress_manager
            )
        )
        progress_manager.log_or_print("[debug] Added task: start_asm")

    if generate_entry:
        generation_tasks.append(
            _generate_entry(
                system_prompt, model_enum, args.max_tokens, artifacts, out_dir,
                entry_user_prompt, token_allocator, progress_manager
            )
        )
        progress_manager.log_or_print("[debug] Added task: entry_c")

    if generate_clock:
        generation_tasks.append(
            _generate_clock(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                clock_user_prompt,
                token_allocator,
                progress_manager,
            )
        )
        progress_manager.log_or_print("[debug] Added task: clock_setup")

    if generate_system:
        # This may overlap with system_driver.c from Pass 2, but usually contains sys_init/clocks logic.
        generation_tasks.append(
            _generate_system(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                system_init_user_prompt,
                token_allocator,
                progress_manager,
            )
        )
        progress_manager.log_or_print("[debug] Added task: system_init")

    if generate_linker:
        generation_tasks.append(
            _generate_linker(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                linker_user_prompt,
                token_allocator,
                progress_manager,
            )
        )
        progress_manager.log_or_print("[debug] Added task: linker")

    if generate_vim:
        generation_tasks.append(
            _generate_vim(
                system_prompt,
                model_enum,
                args.max_tokens,
                artifacts,
                out_dir,
                vim_user_prompt,
                token_allocator,
                progress_manager,
            )
        )
        progress_manager.log_or_print("[debug] Added task: vim_driver")

    # Check for shutdown request before platform generation
    if _shutdown_requested:
        print("[info] Shutdown requested. Skipping platform generation.")
        return

    # Run platform tasks
    if generation_tasks:
        # Setup progress tracker for Platform pass
        tracker = progress_manager.start_pass("Platform")
        if tracker:
            tracker.set_total_tasks(len(generation_tasks))

        try:
            # Run all generation tasks with progress tracking as they complete
            results = []
            for coro in asyncio.as_completed(generation_tasks):
                try:
                    result = await coro
                    results.append(result)
                    if tracker:
                        tracker.increment_success()
                except Exception as e:
                    results.append(e)
                    if tracker:
                        tracker.increment_failure()
                        tracker.add_message(f"Task failed: {str(e)}", level="error")

        except KeyboardInterrupt:
            if tracker:
                tracker.add_message("Platform generation interrupted by user", level="warning")
            else:
                print("\n[info] Platform generation interrupted by user.")
            progress_manager.complete_pass("Platform", success=False)
            return
        finally:
            # Complete the pass
            progress_manager.complete_pass("Platform", success=True)
    else:
        if progress_manager:
            # Still mark as complete even if no tasks
            progress_manager.complete_pass("Platform", success=True)
        else:
            print("[info] No additional platform tasks to run.")

    # Re-run startup contract after platform generation so validation reflects final files.
    validation_tracker = None
    if progress_manager:
        validation_tracker = progress_manager.start_pass("Validation")
        if validation_tracker:
            validation_tracker.set_total_tasks(4)
            validation_tracker.update_task_name("Startup contract checks")

    if "init_order" in locals() and init_order is not None and hasattr(init_order, "is_valid"):
        try:
            startup_contract_result = validate_startup_contract(
                init_order,
                out_dir,
                bringup_contract=bringup_contract,
            )
            if not startup_contract_result.get("passes", True):
                print("[warn] Startup contract validation failed after platform generation")
                for err in startup_contract_result.get("errors", [])[:8]:
                    print(f"  - {err}")
            if validation_tracker:
                validation_tracker.increment_success()
        except Exception as e:
            print(f"[warn] Post-platform startup contract validation failed: {e}")
            if validation_tracker:
                validation_tracker.increment_failure()

    deterministic_fix_result = apply_deterministic_fixes(
        out_dir,
        diagnostics=[],
        api_contract_manifest=api_contract_manifest,
    )
    if deterministic_fix_result.get("actions"):
        print(
            f"[info] Applied deterministic post-generation fixes: "
            f"{len(deterministic_fix_result.get('actions', []))}"
        )
    if validation_tracker:
        validation_tracker.update_task_name("Deterministic post-generation fixes")
        validation_tracker.increment_success()

    # External CCS compile gate (Generate -> Compile -> Fix -> Ready)
    if build_gate_enabled:
        print("[info] Running external CCS compile gate...")
        if validation_tracker:
            validation_tracker.update_task_name("External CCS compile gate")
        def _build_gate_progress(msg: str) -> None:
            if validation_tracker:
                stage_text = str(msg).replace("[build-gate]", "").strip()
                validation_tracker.update_task_name(f"Build gate: {stage_text}")
            if progress_manager:
                progress_manager.log_or_print(msg)
            else:
                print(msg)
        build_gate_result = run_ccs_build_gate(
            output_dir=out_dir,
            generation_profile=generation_profile,
            overrides=build_gate_overrides,
            api_contract_manifest=api_contract_manifest,
            bringup_contract=bringup_contract,
            run_model_name=model_enum.value,
            progress_callback=_build_gate_progress,
        )
        status = build_gate_result.get("status", "unknown")
        passes = bool(build_gate_result.get("passes", False))
        rounds = len(build_gate_result.get("rounds", []))
        print(f"[info] Compile gate status: {status} (passes={passes}, rounds={rounds})")
        llm_tokens = dict(build_gate_result.get("llm_rewrite_tokens", {}) or {})
        llm_total_tokens = int(llm_tokens.get("input_tokens", 0)) + int(llm_tokens.get("output_tokens", 0))
        if llm_total_tokens > 0:
            print(
                f"[info] Compile-gate LLM usage: input={int(llm_tokens.get('input_tokens', 0))}, "
                f"output={int(llm_tokens.get('output_tokens', 0))}, total={llm_total_tokens}"
            )
            if progress_manager:
                stats_now = _cost_tracker.get_stats()
                progress_manager.add_cost_info(
                    int(stats_now.get("total_tokens", 0)),
                    float(stats_now.get("cost_usd", 0.0)),
                    model_enum.name,
                )
        if validation_tracker:
            if passes:
                validation_tracker.increment_success()
            else:
                validation_tracker.increment_failure()
        if gate_should_fail_run(build_gate_result):
            build_gate_failed = True

    # Final startup contract verdict is based on post-fix (and post-build-gate) files.
    if "init_order" in locals() and init_order is not None and hasattr(init_order, "is_valid"):
        try:
            startup_contract_result = validate_startup_contract(
                init_order,
                out_dir,
                bringup_contract=bringup_contract,
            )
            if not startup_contract_result.get("passes", True):
                print("[warn] Startup contract validation still failing after deterministic fixes/build gate")
                for err in startup_contract_result.get("errors", [])[:8]:
                    print(f"  - {err}")
                if startup_gate_mode == "fail":
                    print("[error] startup_contract.gate_mode=fail: startup contract mismatch detected")
                    bringup_contract_failed = True
            else:
                bringup_contract_failed = False
        except Exception as e:
            print(f"[warn] Final startup contract validation failed: {e}")

    parity_result = run_parity_guard(
        out_dir,
        parity_guard_cfg.get("baseline_path"),
        mode=parity_guard_cfg.get("mode", "critical_only"),
        critical_registers=parity_guard_cfg.get("critical_registers"),
    )
    if not bool((parity_result or {}).get("passes", True)):
        print("[warn] Parity guard detected critical register sequence drift")
        for mismatch in list((parity_result or {}).get("critical_sequence_mismatches", []))[:6]:
            baseline = (mismatch or {}).get("baseline") or {}
            candidate = (mismatch or {}).get("candidate") or {}
            print(
                "  - "
                f"{mismatch.get('kind')}: "
                f"baseline={baseline.get('file')}:{baseline.get('line')} {baseline.get('canonical_symbol')} "
                f"candidate={candidate.get('file')}:{candidate.get('line')} {candidate.get('canonical_symbol')}"
            )
        if startup_gate_mode == "fail":
            bringup_contract_failed = True

    # Check for shutdown request before documentation
    if _shutdown_requested:
        print("[info] Shutdown requested. Skipping documentation generation.")
        if validation_tracker and progress_manager:
            progress_manager.complete_pass("Validation", success=False)
        return

    # Generate documentation
    await _generate_documentation(out_dir, progress_manager)

    # --- FINAL VALIDATION REPORT ---
    if validation_tracker:
        validation_tracker.update_task_name("Final validation report")
    progress_manager.log_or_print("\n[info] Generating final validation report...")

    try:
        from modules.validation.validation_report import (
            create_validation_report,
            write_json_report,
            write_markdown_report,
            print_console_summary
        )

        # Create comprehensive report
        from modules.validation.validation_report import ValidationReport, ValidationSummary, ModuleValidation

        final_report = ValidationReport(
            timestamp=_now_tag(),
            bsp_output_dir=str(out_dir)
        )

        # Add Pass 2 validation results
        compile_contract_errors = []
        compile_contract_warnings = []
        compile_contract_checks = 0
        autofix_actions = []
        if 'pass2_validation_results' in locals() and pass2_validation_results:
            for module_name, validation_result in sorted(pass2_validation_results, key=lambda item: item[0]):
                # Extract facts validation details if available
                constants_validated = 0
                mismatches = 0
                if validation_result.facts_validation:
                    constants_validated = len(validation_result.facts_validation.matches) + len(validation_result.facts_validation.mismatches)
                    mismatches = len(validation_result.facts_validation.mismatches)

                module_errors = list(validation_result.errors[:10])
                module_warnings = list(validation_result.warnings[:10])
                module_contract_result = getattr(validation_result, "compile_contract", None)
                module_autofix_actions = getattr(validation_result, "autofix_actions", [])

                if module_contract_result:
                    compile_contract_checks += 1
                    compile_contract_errors.extend(module_contract_result.get("errors", []))
                    compile_contract_warnings.extend(module_contract_result.get("warnings", []))
                    for action in module_autofix_actions:
                        autofix_actions.append({"module": module_name, "action": action})

                    if not module_contract_result.get("passed", True):
                        module_errors.append(
                            f"[contract] {module_name}: compile contract check failed"
                        )

                # Strict mode: promote key warnings to critical failures for core build-readiness modules
                if strict_validation_enabled and module_name.upper() in CRITICAL_BUILD_MODULES:
                    for warn in list(module_warnings):
                        warn_lower = warn.lower()
                        if (
                            "missing init function" in warn_lower
                            or "missing #include" in warn_lower
                            or "function '" in warn_lower and "not found in implementation" in warn_lower
                        ):
                            promoted = f"[strict] {warn}"
                            if promoted not in module_errors:
                                module_errors.append(promoted)

                    if module_contract_result and not module_contract_result.get("passed", True):
                        module_errors.extend(
                            [f"[strict] {e}" for e in module_contract_result.get("errors", [])[:5]]
                        )

                module_is_valid = validation_result.is_valid and len(module_errors) == 0

                module_validation = ModuleValidation(
                    module_name=module_name,
                    facts_mirror_valid=module_is_valid,
                    constants_validated=constants_validated,
                    mismatches=mismatches,
                    tests_generated=False,  # Not tracking test generation currently
                    critical_errors=module_errors[:10],  # Limit to 10
                    warnings=module_warnings[:10]  # Limit to 10
                )
                final_report.peripheral_validations[module_name] = module_validation

            # Update summary
            final_report.validation_summary.total_modules = len(pass2_validation_results)
            final_report.validation_summary.modules_valid = sum(
                1 for val in final_report.peripheral_validations.values() if val.facts_mirror_valid
            )
            final_report.validation_summary.modules_invalid = (
                final_report.validation_summary.total_modules - final_report.validation_summary.modules_valid
            )
            final_report.validation_summary.critical_errors = sum(
                len(val.critical_errors) for val in final_report.peripheral_validations.values()
            )
            final_report.validation_summary.warnings = sum(
                len(val.warnings) for val in final_report.peripheral_validations.values()
            )
            if final_report.validation_summary.total_modules > 0:
                final_report.validation_summary.success_rate = (
                    final_report.validation_summary.modules_valid /
                    final_report.validation_summary.total_modules
                ) * 100.0

        if bsp_validate_contract_result:
            compile_contract_checks += 1
            compile_contract_errors.extend(bsp_validate_contract_result.get("errors", []))
            compile_contract_warnings.extend(bsp_validate_contract_result.get("warnings", []))
        if bsp_validate_autofix_actions:
            autofix_actions.extend(bsp_validate_autofix_actions)

        compile_contract_passes = len(compile_contract_errors) == 0 or contract_mode == "warn_only"
        if contract_mode == "warn_only" and compile_contract_errors:
            compile_contract_warnings.extend(compile_contract_errors)
            compile_contract_errors = []

        final_report.compile_contract = {
            "passes": compile_contract_passes,
            "checks": compile_contract_checks,
            "errors": compile_contract_errors,
            "warnings": compile_contract_warnings,
        }
        final_report.autofix_actions = autofix_actions
        final_report.startup_contract = startup_contract_result or {
            "passes": True,
            "errors": [],
            "warnings": ["startup contract not evaluated"],
            "checks": {},
        }
        final_report.critical_sequence_mismatches = list(
            (parity_result or {}).get("critical_sequence_mismatches", [])
        )
        if build_gate_result:
            final_report.build_evidence = {
                "mode": "generator_ccs_build_gate",
                "required": bool(build_gate_result.get("required", False)),
                "status": build_gate_result.get("status"),
                "passes": bool(build_gate_result.get("passes", False)),
                "rounds": len(build_gate_result.get("rounds", [])),
                "error_summary": build_gate_result.get("error_summary", {}),
                "configuration": build_gate_result.get("configuration"),
                "external_workspace_path": build_gate_result.get("external_workspace_path"),
                "project_name": build_gate_result.get("project_name"),
                "llm_rewrite_attempted": bool(build_gate_result.get("llm_rewrite_attempted", False)),
                "llm_rewrite_applied": bool(build_gate_result.get("llm_rewrite_applied", False)),
                "llm_rewrite_target_files": list(build_gate_result.get("llm_rewrite_target_files", [])),
                "llm_rewrite_tokens": dict(build_gate_result.get("llm_rewrite_tokens", {})),
                "llm_rewrite_failure_reason": build_gate_result.get("llm_rewrite_failure_reason"),
            }
        else:
            final_report.build_evidence = {
                "mode": "user_ccs_compile_log_required",
                "required": require_ccs_proof,
                "status": "not_provided_in_this_run" if require_ccs_proof else "optional_not_provided",
            }
        if api_contract_manifest:
            final_report.api_contract_hash = api_contract_manifest.get("api_contract_hash")
        final_report.runtime_invariants = {
            "bringup_contract_loaded": bool(bringup_contract),
            "bringup_mode": bringup_mode,
            "fail_on_contract_mismatch": fail_on_contract_mismatch,
            "startup_contract_gate_mode": startup_gate_mode,
            "build_gate_enabled": build_gate_enabled,
            "build_gate_mode": build_gate_mode,
            "build_gate_passes": (
                bool(build_gate_result.get("passes", False))
                if isinstance(build_gate_result, dict)
                else None
            ),
            "parity_guard_mode": parity_guard_cfg.get("mode"),
            "parity_guard_passes": bool((parity_result or {}).get("passes", True)),
            "parity_guard_baseline": str(parity_guard_cfg.get("baseline_path") or ""),
            "serial_primary_path": (
                (bringup_contract or {}).get("serial", {}).get("primary_path")
                if isinstance(bringup_contract, dict)
                else None
            ),
            "startup_contract_passes": (
                startup_contract_result.get("passes", True)
                if isinstance(startup_contract_result, dict)
                else True
            ),
        }

        if strict_validation_enabled:
            if not final_report.compile_contract.get("passes", True):
                final_report.validation_summary.critical_errors += len(final_report.compile_contract.get("errors", []))
            if not final_report.startup_contract.get("passes", True):
                final_report.validation_summary.critical_errors += len(final_report.startup_contract.get("errors", []))
            if not bool((parity_result or {}).get("passes", True)):
                final_report.validation_summary.critical_errors += len(
                    (parity_result or {}).get("critical_sequence_mismatches", [])
                )
            if build_gate_result and not bool(build_gate_result.get("passes", False)):
                diag_errors = int((build_gate_result.get("error_summary", {}) or {}).get("errors", 1))
                final_report.validation_summary.critical_errors += max(1, diag_errors)

        # Add cross-file validation
        try:
            from modules.validation.validation_engine import (
                extract_all_constants_from_directory,
                validate_facts_across_files
            )

            # Extract constants from all generated files
            all_constants = extract_all_constants_from_directory(out_dir)

            # Perform cross-file validation
            if all_constants:
                cross_file_validation = validate_facts_across_files(all_constants, soc_data)
                final_report.cross_file_validation = {
                    "passes": cross_file_validation.passes,
                    "conflicts": [str(c) for c in cross_file_validation.conflicts],
                    "consistency_score": cross_file_validation.consistency_score,
                    "errors": cross_file_validation.errors,
                    "warnings": cross_file_validation.warnings
                }
        except Exception as e:
            progress_manager.log_or_print(f"[warn] Cross-file validation failed: {e}")

        # Add dependency graph info if available
        if 'dep_graph' in locals() and 'init_order' in locals():
            final_report.dependency_graph_info = {
                "total_nodes": len(dep_graph.nodes),
                "has_cycles": init_order.has_cycles,
                "init_order": init_order.order if init_order.is_valid() else [],
                "cycle_nodes": init_order.cycle_nodes if init_order.has_cycles else []
            }

        # Write reports
        json_path = out_dir / "validation_report.json"
        md_path = out_dir / "validation_report.md"

        write_json_report(final_report, json_path)
        write_markdown_report(final_report, md_path)

        progress_manager.log_or_print(f"[ok] Validation report: {json_path.name}")
        progress_manager.log_or_print(f"[ok] Validation report: {md_path.name}")
        if validation_tracker:
            validation_tracker.increment_success()
            progress_manager.complete_pass("Validation", success=True)

        # Cleanup progress display before printing validation results
        progress_manager.cleanup()

        # Print console summary (always show final validation results)
        print_console_summary(final_report)

        _augment_compile_gate_report(
            out_dir,
            build_gate_result,
            final_report.startup_contract,
            startup_gate_mode,
            parity_result,
        )

    except Exception as e:
        progress_manager.log_or_print(f"[warn] Could not generate final validation report: {e}")
        if validation_tracker:
            validation_tracker.increment_failure()
            progress_manager.complete_pass("Validation", success=False)

    # Save token history for future runs
    if not args.mock:
        token_allocator.save_history(token_history_path)
        progress_manager.log_or_print(f"[info] Saved token history to {token_history_path.name}")

    # Display cost summary (always show final costs)
    try:
        stats = _cost_tracker.get_stats()
        print(f"\n[info] API Usage Summary:")

        # Show per-model breakdown if multiple models were used
        if stats.get('models'):
            for model_info in stats['models']:
                print(f"\n  {model_info['model_name']}:")
                print(f"    Input tokens:  {model_info['input_tokens']:,}")
                print(f"    Output tokens: {model_info['output_tokens']:,}")
                print(f"    Total tokens:  {model_info['total_tokens']:,}")
                print(f"    Cost: ${model_info['cost_usd']:.2f} USD")

        # Show totals
        print(f"\n  Total Usage:")
        print(f"    Input tokens:  {stats['input_tokens']:,}")
        print(f"    Output tokens: {stats['output_tokens']:,}")
        print(f"    Total tokens:  {stats['total_tokens']:,}")
        print(f"    Actual cost: ${stats['cost_usd']:.2f} USD")
    except Exception as e:
        print(f"[warn] Could not display cost summary: {e}")

    if startup_gate_mode == "fail" and bringup_contract_failed:
        print("[error] Startup/parity contract gate failed; see validation_report for details.")
        _progress.stop_spinner()
        return 2
    if build_gate_failed:
        print("[error] Strict CCS compile gate failed; see compile_gate_report.json and ccs_build_log.txt for details.")
        _progress.stop_spinner()
        return 3

    # Ensure any remaining spinner threads are stopped
    _progress.stop_spinner()

    # Update cost metrics and cleanup progress manager
    if progress_manager:
        stats = _cost_tracker.get_stats()
        total_tokens = stats.get("total_tokens", 0)
        total_cost = stats.get("cost_usd", 0.0)
        progress_manager.add_cost_info(total_tokens, total_cost, model_enum.name)

        # Print final messages (cleanup already called before validation output)
        print(f"\n[info] Generation log saved to: {progress_manager.logger.log_file}")
        print(f"\n[ok] BSP generation complete!")
        print(f"[info] Output directory: {out_dir}")
    else:
        print(f"\n[ok] BSP generation complete!")
        print(f"[info] Output directory: {out_dir}")

    if not progress_manager or not progress_manager.should_suppress_prints():
        print("[debug] main() function returning...")


async def _generate_documentation(out_dir: Path, progress_manager=None):
    """Generate Doxygen documentation (optional, skipped if doxygen not available)"""
    log = progress_manager.log_or_print if progress_manager else print

    log(f"\n[info] Creating documentation with Doxygen")

    docs_dir = out_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write Doxyfile to docs directory
        doxy_path = write_doxyfile(docs_dir)
        log(f"[info] Doxyfile created at {doxy_path}")

        # Run doxygen from BSP root
        run_doxygen(out_dir, doxy_path)

        # Verify output was created
        html_dir = docs_dir / "html"
        index_file = html_dir / "index.html"

        if not index_file.exists():
            log(f"[warn] Doxygen completed but index.html not found at {index_file}")
            return

        # Count generated HTML files for sanity check
        html_files = list(html_dir.glob("*.html"))
        log(f"[ok] Documentation generated: {len(html_files)} HTML files in {html_dir}")

        # Success metric: Should see 50+ HTML files for a complete BSP
        if len(html_files) < 10:
            log(f"[warn] Only {len(html_files)} HTML files generated - documentation may be incomplete")

        abs_path = index_file.resolve()
        log(f"[info] Open documentation at: file:///{abs_path}")

    except FileNotFoundError as e:
        if "doxygen" in str(e).lower():
            log(f"[warn] Doxygen not found in system PATH. Install doxygen to generate documentation.")
        else:
            log(f"[warn] Documentation generation failed: {e}")
    except RuntimeError as e:
        # Specific doxygen or validation errors
        log(f"[warn] Doxygen generation failed: {e}")
        log(f"[info] Documentation skipped. BSP code generation was successful.")
    except Exception as e:
        log(f"[warn] Unexpected error during documentation generation: {e}")
        log(f"[info] Documentation skipped. BSP code generation was successful.")


if __name__ == "__main__":
    try:
        # Use asyncio.run which handles event loop creation and cleanup
        rc = asyncio.run(main())
        print("[debug] asyncio.run() completed, exiting normally.")
        if isinstance(rc, int):
            sys.exit(rc)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n[info] Generation interrupted by user. Exiting.")
        _progress.stop_spinner()
        sys.exit(0)
    except Exception as e:
        controlled_messages = (
            "Strict bring-up contract validation failed",
            "Strict CCS compile gate failed",
        )
        if any(msg in str(e) for msg in controlled_messages):
            print(f"[error] {e}")
            _progress.stop_spinner()
            sys.exit(1)
        print(f"\n[error] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        _progress.stop_spinner()
        sys.exit(1)
