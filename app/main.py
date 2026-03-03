import argparse
import asyncio
import builtins
import inspect
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Dict, Optional

from config import YAMLS_DIR, TARGET_FILES, FACTS_CANON, PATTERN_SNIPS

from modules.utils.file_io import (
    evaluate_doxygen_output,
    normalize_generated_text,
    run_doxygen,
    split_and_write_files,
    write_doxyfile,
    write_makefile,
    write_manifest,
)
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
from modules.intent.board_capabilities import (
    build_board_capability_header,
    build_board_capability_manifest,
    format_allowed_references_for_console,
    validate_intent_references,
)
from modules.intent.post_generation_prompt import build_post_generation_firmware_prompt
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
ACTION_CHOICES = [
    "generate",
    "validate",
    "postgen_prompt",
    "postgen_generate",
    "compile_only",
    "docs_only",
    "reflash",
]

_ORIGINAL_PRINT = builtins.print
_COLORED_PRINT_INSTALLED = False
_COLOR_PREFIX_RE = re.compile(r"^(\s*)\[(ok|warn|error)\]", re.IGNORECASE)


def _stdout_supports_ansi_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False

    color_mode = str(os.getenv("BSP_COLOR_LOGS", "auto")).strip().lower()
    if color_mode in {"0", "off", "false", "no"}:
        return False
    if color_mode not in {"1", "on", "true", "yes", "auto"}:
        color_mode = "auto"

    if color_mode == "auto" and not sys.stdout.isatty():
        return False

    if sys.platform != "win32":
        return True

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        enable_vt = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        processed = 0x0001  # ENABLE_PROCESSED_OUTPUT
        new_mode = mode.value | enable_vt | processed
        if kernel32.SetConsoleMode(handle, new_mode) == 0:
            return False
        return True
    except Exception:
        return False


def _colorize_prefixed_log_message(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    if "\033[" in text:
        return text

    match = _COLOR_PREFIX_RE.match(text)
    if not match:
        return text

    level = match.group(2).lower()
    color = {
        "ok": "\033[32m",      # green
        "warn": "\033[33m",    # yellow
        "error": "\033[31m",   # red
    }.get(level, "")
    if not color:
        return text
    return f"{match.group(1)}{color}{text[len(match.group(1)):]}\033[0m"


def _install_colored_print() -> None:
    global _COLORED_PRINT_INSTALLED
    if _COLORED_PRINT_INSTALLED:
        return
    if not _stdout_supports_ansi_color():
        return

    def _colored_print(*args, **kwargs):
        if args:
            first = args[0]
            if isinstance(first, str):
                args = (_colorize_prefixed_log_message(first),) + args[1:]
        return _ORIGINAL_PRINT(*args, **kwargs)

    builtins.print = _colored_print
    _COLORED_PRINT_INSTALLED = True

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
    "app_intent": {
        "enabled": True,
        "critical_file_freeze": True,
        "allow_llm_on_critical": False,
        "task_library_path": "app/yaml_in/firmware_tasks.yaml",
        "intent_refs_mode": "proven_only",
        "generate_firmware_pass": True,
        "post_gen_max_tokens": 8000,
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
        "max_fix_rounds": 4,
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
            "max_attempts": 2,
            "include_contract_context": True,
        },
    },
    "flash": {
        "enabled": False,
        "command_template": "",
        "working_dir": "",
        "env": {},
        "timeout_sec": 120,
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


def _load_profile_data(
    *,
    args_profile: Optional[str],
    no_profile: bool,
    yaml_root: Path,
) -> tuple[Optional[Dict[str, Any]], Optional[Path]]:
    """
    Resolve profile source for a run.
    Returns (profile_data, loaded_path). When no profile is used, both are None.
    """
    if no_profile:
        return None, None

    if args_profile:
        profile_path = Path(args_profile)
        return load_generation_profile(profile_path), profile_path

    default_path = Path(yaml_root) / "generation_profile.yaml"
    if default_path.exists():
        return load_generation_profile(default_path), default_path

    return None, None


def _should_use_profile_module_selection(
    *,
    loaded_profile_path: Optional[Path],
    no_profile: bool,
    profile_enabled_modules: Any,
) -> bool:
    """
    Use profile module selection only when an actual profile file was loaded.
    This avoids treating in-code defaults as an explicit profile selection.
    """
    if no_profile:
        return False
    if loaded_profile_path is None:
        return False
    if not isinstance(profile_enabled_modules, list):
        return False
    return len(profile_enabled_modules) > 0


def _should_open_auto_menu(argv: List[str], *, stdin_tty: bool, stdout_tty: bool, explicit_menu: bool) -> bool:
    """
    Auto-open interactive menu only for a bare interactive launch.
    """
    if explicit_menu:
        return True
    return bool(stdin_tty and stdout_tty and len(argv) == 0)


def _read_json_file_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _extract_output_tag(path: Path) -> str:
    name = path.name
    if name.startswith("output_"):
        return name[len("output_"):]
    return name


def _derive_validation_status(validation: Dict[str, Any]) -> str:
    """
    Derive a user-facing validation status for UI summary:
      PASS: no notable issues
      WARN: non-blocking issues present
      FAIL: blocking validation/build conditions
      n/a: insufficient data
    """
    if not isinstance(validation, dict) or not validation:
        return "n/a"

    summary = validation.get("validation_summary", {}) if isinstance(validation.get("validation_summary", {}), dict) else {}
    compile_contract = validation.get("compile_contract", {}) if isinstance(validation.get("compile_contract", {}), dict) else {}
    startup_contract = validation.get("startup_contract", {}) if isinstance(validation.get("startup_contract", {}), dict) else {}
    build_evidence = validation.get("build_evidence", {}) if isinstance(validation.get("build_evidence", {}), dict) else {}
    runtime_invariants = validation.get("runtime_invariants", {}) if isinstance(validation.get("runtime_invariants", {}), dict) else {}

    build_passes = build_evidence.get("passes")
    if build_passes is False:
        return "FAIL"

    compile_contract_passes = compile_contract.get("passes")
    if compile_contract_passes is False:
        return "FAIL"

    startup_gate_mode = str(runtime_invariants.get("startup_contract_gate_mode", "warn")).strip().lower()
    startup_passes = startup_contract.get("passes")
    if startup_passes is False and startup_gate_mode == "fail":
        return "FAIL"

    parity_mode = str(runtime_invariants.get("parity_guard_mode", "critical_only")).strip().lower()
    parity_passes = runtime_invariants.get("parity_guard_passes")
    if parity_passes is False and parity_mode == "strict":
        return "FAIL"

    try:
        critical_errors = int(summary.get("critical_errors", 0) or 0)
    except (TypeError, ValueError):
        critical_errors = 0
    try:
        warnings = int(summary.get("warnings", 0) or 0)
    except (TypeError, ValueError):
        warnings = 0

    if critical_errors > 0:
        return "WARN"
    if startup_passes is False and startup_gate_mode != "fail":
        return "WARN"
    if parity_passes is False and parity_mode != "strict":
        return "WARN"
    if warnings > 0:
        return "WARN"

    return "PASS"


def _discover_recent_output_dirs(limit: int = 10, roots: Optional[List[Path]] = None) -> List[Path]:
    if roots is None:
        cwd = Path.cwd()
        roots = [cwd, cwd / "app"]

    found: Dict[Path, Path] = {}
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if not child.name.startswith("output_"):
                continue
            try:
                resolved = child.resolve()
            except Exception:
                resolved = child
            found[resolved] = child

    def _sort_key(p: Path) -> tuple:
        tag = _extract_output_tag(p)
        ts_match = re.match(r"^\d{8}[_T]\d{6}$", tag)
        try:
            mtime = p.stat().st_mtime
        except Exception:
            mtime = 0.0
        # Timestamp-style names sort lexicographically for recency.
        return (1 if ts_match else 0, tag if ts_match else "", mtime)

    sorted_paths = sorted(found.keys(), key=_sort_key, reverse=True)
    if limit > 0:
        sorted_paths = sorted_paths[:limit]
    return sorted_paths


def _summarize_output_dir(path: Path) -> Dict[str, Any]:
    compile_gate = _read_json_file_if_exists(path / "compile_gate_report.json") or {}
    validation = _read_json_file_if_exists(path / "validation_report.json") or {}
    post_gen = _read_json_file_if_exists(path / "post_gen_firmware_report.json") or {}
    docs_index = path / "docs" / "html" / "index.html"
    docs_quality = _read_json_file_if_exists(path / "docs" / "doxygen_quality_report.json") or {}
    validation_status = _derive_validation_status(validation)

    return {
        "path": str(path),
        "name": path.name,
        "tag": _extract_output_tag(path),
        "timestamp": _extract_output_tag(path),
        "compile_status": str(compile_gate.get("status", "n/a")),
        "compile_passes": compile_gate.get("passes"),
        "validation_status": validation_status,
        "post_gen": bool(post_gen),
        "docs_index": docs_index.exists(),
        "docs_quality_passes": docs_quality.get("passes"),
    }


def _print_recent_outputs(limit: int = 10) -> List[Dict[str, Any]]:
    outputs = [_summarize_output_dir(p) for p in _discover_recent_output_dirs(limit=limit)]
    if not outputs:
        print("[info] No output_* folders found.")
        return []

    print("\nRecent outputs:")
    print("Idx | Folder                | Timestamp       | Compile        | Validation | PostGen | Docs")
    print("----+-----------------------+-----------------+----------------+------------+---------+------")
    for idx, item in enumerate(outputs, start=1):
        folder = item["name"][:21].ljust(21)
        timestamp = str(item.get("timestamp", ""))[:15].ljust(15)
        comp = str(item["compile_status"])[:14].ljust(14)
        val = str(item.get("validation_status", "n/a")).ljust(10)
        pg = ("yes" if item["post_gen"] else "no").ljust(7)
        docs = ("yes" if item["docs_index"] else "no").ljust(4)
        print(f"{idx:>3} | {folder} | {timestamp} | {comp} | {val} | {pg} | {docs}")
    print("")
    return outputs


def _resolve_output_dir_from_index(output_index: int, *, limit: int = 10) -> Optional[Path]:
    outputs = _discover_recent_output_dirs(limit=limit)
    if output_index < 1 or output_index > len(outputs):
        return None
    return outputs[output_index - 1]


def _pick_output_dir_interactive(limit: int = 10) -> Optional[Path]:
    outputs = _print_recent_outputs(limit=limit)
    if not outputs and not sys.stdin.isatty():
        return None

    while True:
        choice = input(
            "[user] Select output index, or enter full path (blank to cancel): "
        ).strip()
        if not choice:
            return None
        if choice.isdigit():
            idx = int(choice)
            picked = _resolve_output_dir_from_index(idx, limit=limit)
            if picked is None:
                print(f"[warn] Invalid index: {idx}")
                continue
            return picked

        candidate = Path(choice).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
        print(f"[warn] Output directory not found: {candidate}")


def _apply_menu_selection(args: argparse.Namespace) -> bool:
    """
    Interactive action picker for bare runs.
    Returns False when user cancels.
    """
    print("\nBSP Generator Menu")
    print("1) Full generation")
    print("2) Validate existing output")
    print("3) Post-gen prompt only (existing output)")
    print("4) Post-gen prompt + firmware generation (existing output)")
    print("5) Compile gate only (existing output)")
    print("6) Docs only (Doxygen + quality report)")
    print("7) Reflash existing output")

    selection = input("[user] Choose action [1-7] (blank to cancel): ").strip()
    if not selection:
        return False
    if selection not in {"1", "2", "3", "4", "5", "6", "7"}:
        print(f"[warn] Invalid selection: {selection}")
        return False

    menu_to_action = {
        "1": "generate",
        "2": "validate",
        "3": "postgen_prompt",
        "4": "postgen_generate",
        "5": "compile_only",
        "6": "docs_only",
        "7": "reflash",
    }
    args.action = menu_to_action[selection]

    if args.action in {"validate", "postgen_prompt", "postgen_generate", "compile_only", "docs_only", "reflash"}:
        picked = _pick_output_dir_interactive(limit=10)
        if picked is None:
            print("[info] Menu canceled.")
            return False
        args.output_dir = str(picked)

    if args.action == "postgen_prompt":
        args.post_gen_prompt = True
        args.post_gen_generate = False
        args.validate_only = True
    elif args.action == "postgen_generate":
        args.post_gen_prompt = True
        args.post_gen_generate = True
        args.validate_only = True
    elif args.action == "validate":
        args.validate_only = True
    return True


def _resolve_action_from_args(args: argparse.Namespace) -> str:
    if args.action:
        return str(args.action)
    if args.validate_only:
        if args.post_gen_generate:
            return "postgen_generate"
        if args.post_gen_prompt:
            return "postgen_prompt"
        return "validate"
    return "generate"


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


def _prompt_for_ccs_workspace_project(
    workspace_value: Optional[str],
    project_value: Optional[str],
    *,
    context_label: str = "compile gate",
) -> tuple[str, str]:
    """
    Prompt interactively for CCS workspace/project when values are missing/invalid.
    Returns empty strings when user intentionally skips.
    """
    workspace = str(workspace_value or "").strip()
    project = str(project_value or "").strip()

    # Non-interactive sessions cannot be prompted.
    if not sys.stdin.isatty():
        return workspace, project

    if not workspace:
        workspace = input(
            f"[user] Enter CCS workspace path for {context_label} (blank to skip): "
        ).strip()
    while workspace and not Path(workspace).exists():
        print(f"[warn] CCS workspace path does not exist: {workspace}")
        workspace = input(
            f"[user] Re-enter existing CCS workspace path for {context_label} (blank to skip): "
        ).strip()

    if workspace and not project:
        project = input(
            f"[user] Enter CCS project name in that workspace for {context_label} (blank to skip): "
        ).strip()

    while workspace and project and not (Path(workspace) / project).exists():
        print(f"[warn] CCS project path does not exist: {Path(workspace) / project}")
        project = input(
            f"[user] Re-enter CCS project name for {context_label} (blank to skip): "
        ).strip()

    return workspace, project


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


def _build_build_evidence_from_gate_result(
    build_gate_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(build_gate_result, dict):
        return {
            "mode": "validation_only",
            "required": False,
            "status": "not_run",
        }
    return {
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


def _recompute_strict_critical_errors(
    report_data: Dict[str, Any],
    build_gate_result: Optional[Dict[str, Any]],
) -> int:
    modules = report_data.get("peripheral_validations", {}) or {}
    critical_errors = 0
    if isinstance(modules, dict):
        for _, module in modules.items():
            if isinstance(module, dict):
                critical_errors += len(module.get("critical_errors", []) or [])

    compile_contract = report_data.get("compile_contract", {}) or {}
    if isinstance(compile_contract, dict) and not bool(compile_contract.get("passes", True)):
        critical_errors += len(compile_contract.get("errors", []) or [])

    startup_contract = report_data.get("startup_contract", {}) or {}
    if isinstance(startup_contract, dict) and not bool(startup_contract.get("passes", True)):
        critical_errors += len(startup_contract.get("errors", []) or [])

    runtime_invariants = report_data.get("runtime_invariants", {}) or {}
    parity_passes = bool(runtime_invariants.get("parity_guard_passes", True))
    if not parity_passes:
        critical_errors += len(report_data.get("critical_sequence_mismatches", []) or [])

    if isinstance(build_gate_result, dict) and not bool(build_gate_result.get("passes", False)):
        diag_errors = int((build_gate_result.get("error_summary", {}) or {}).get("errors", 1))
        critical_errors += max(1, diag_errors)

    return critical_errors


def _sync_validation_report_build_evidence(
    out_dir: Path,
    build_gate_result: Optional[Dict[str, Any]],
    *,
    strict_validation_enabled: bool = False,
) -> bool:
    """
    Keep validation_report.{json,md} aligned with the latest compile-gate result.
    This avoids stale false-positive build evidence after post-generation compile reruns.
    """
    json_path = Path(out_dir) / "validation_report.json"
    md_path = Path(out_dir) / "validation_report.md"
    if not json_path.exists():
        return False

    try:
        report_data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(report_data, dict):
        return False

    report_data["build_evidence"] = _build_build_evidence_from_gate_result(build_gate_result)
    runtime = report_data.get("runtime_invariants")
    if not isinstance(runtime, dict):
        runtime = {}
        report_data["runtime_invariants"] = runtime
    runtime["build_gate_passes"] = (
        bool(build_gate_result.get("passes", False))
        if isinstance(build_gate_result, dict)
        else None
    )

    summary = report_data.get("validation_summary")
    if strict_validation_enabled and isinstance(summary, dict):
        summary["critical_errors"] = _recompute_strict_critical_errors(report_data, build_gate_result)

    try:
        from modules.validation.validation_report import (
            ModuleValidation,
            ValidationReport,
            ValidationSummary,
            write_json_report,
            write_markdown_report,
        )

        summary_dict = report_data.get("validation_summary", {}) or {}
        summary_obj = ValidationSummary(
            total_modules=int(summary_dict.get("total_modules", 0) or 0),
            modules_valid=int(summary_dict.get("modules_valid", 0) or 0),
            modules_invalid=int(summary_dict.get("modules_invalid", 0) or 0),
            critical_errors=int(summary_dict.get("critical_errors", 0) or 0),
            warnings=int(summary_dict.get("warnings", 0) or 0),
            success_rate=float(summary_dict.get("success_rate", 0.0) or 0.0),
        )

        periph_objs: Dict[str, ModuleValidation] = {}
        periph_data = report_data.get("peripheral_validations", {}) or {}
        if isinstance(periph_data, dict):
            for module_name, raw in periph_data.items():
                if not isinstance(raw, dict):
                    continue
                periph_objs[module_name] = ModuleValidation(
                    module_name=str(raw.get("module_name", module_name)),
                    facts_mirror_valid=bool(raw.get("facts_mirror_valid", False)),
                    constants_validated=int(raw.get("constants_validated", 0) or 0),
                    mismatches=int(raw.get("mismatches", 0) or 0),
                    tests_generated=bool(raw.get("tests_generated", False)),
                    critical_errors=list(raw.get("critical_errors", []) or []),
                    warnings=list(raw.get("warnings", []) or []),
                )

        report_obj = ValidationReport(
            timestamp=str(report_data.get("timestamp", "")),
            bsp_output_dir=str(report_data.get("bsp_output_dir", "")),
            validation_summary=summary_obj,
            peripheral_validations=periph_objs,
            cross_file_validation=report_data.get("cross_file_validation"),
            dependency_graph_info=(
                report_data.get("dependency_graph")
                if isinstance(report_data.get("dependency_graph"), dict)
                else report_data.get("dependency_graph_info")
            ),
            compile_contract=report_data.get("compile_contract"),
            autofix_actions=list(report_data.get("autofix_actions", []) or []),
            startup_contract=report_data.get("startup_contract"),
            build_evidence=report_data.get("build_evidence"),
            api_contract_hash=report_data.get("api_contract_hash"),
            runtime_invariants=report_data.get("runtime_invariants"),
            critical_sequence_mismatches=list(report_data.get("critical_sequence_mismatches", []) or []),
        )

        write_json_report(report_obj, json_path)
        write_markdown_report(report_obj, md_path)
        return True
    except Exception:
        return False


def _emit_board_capability_manifest(out_dir: Path, board_data: Dict[str, Any]) -> Dict[str, Any]:
    manifest = build_board_capability_manifest(board_data or {})
    manifest_path = Path(out_dir) / "board_capability_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    include_dir = Path(out_dir) / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    header_path = include_dir / "board_capabilities.h"
    header_content = build_board_capability_header(board_data or {}, capability_manifest=manifest)
    header_path.write_text(
        normalize_generated_text(header_content, header_path),
        encoding="utf-8",
    )
    return manifest


def _run_post_generation_intent_prompt(
    out_dir: Path,
    capability_manifest: Dict[str, Any],
    *,
    refs_mode: str,
    initial_intent: str = "",
    task_library_path: Optional[Path] = None,
    progress_manager=None,
) -> Dict[str, Any]:
    def _log(msg: str) -> None:
        if progress_manager:
            progress_manager.emit_message(msg, force_console=True)
        else:
            print(msg)

    def _prompt(msg: str) -> str:
        if progress_manager:
            progress_manager.pause_for_input()
            try:
                return input(msg)
            finally:
                progress_manager.resume_after_input()
        return input(msg)

    for line in format_allowed_references_for_console(capability_manifest, mode=refs_mode):
        _log(line)

    non_interactive = bool(initial_intent.strip())
    prompt = (
        "\n[user] Enter app intent (for example: 'blink LED2 and print S3 presses over terminal'): "
    )
    intent_text = initial_intent.strip()
    cancelled = False
    validation_result: Dict[str, Any] = {
        "mode": refs_mode,
        "valid": False,
        "recognized_refs": [],
        "rejected_refs": [{"reference": "<none>", "reason": "no_input"}],
        "suggested_refs": {},
        "matched_aliases": [],
    }

    while True:
        if not intent_text:
            intent_text = _prompt(prompt).strip()
            if not intent_text:
                cancelled = True
                break

        validation_result = validate_intent_references(
            intent_text,
            capability_manifest,
            mode=refs_mode,
        )
        if validation_result.get("valid", False):
            _log(
                "[ok] Intent references validated: "
                + ", ".join(validation_result.get("recognized_refs", []))
            )
            break

        rejected = validation_result.get("rejected_refs", [])
        _log("[warn] Intent contains unknown or disallowed component references:")
        for item in rejected:
            if not isinstance(item, dict):
                continue
            _log(f"  - {item.get('reference')}: {item.get('reason')}")
        suggestions = validation_result.get("suggested_refs", {})
        if isinstance(suggestions, dict) and suggestions:
            _log("[info] Suggested references:")
            for token, values in suggestions.items():
                if isinstance(values, list) and values:
                    _log(f"  - {token} -> {', '.join(values)}")

        if non_interactive:
            break

        retry = _prompt("[user] Re-enter app intent? [Y/n]: ").strip().lower()
        if retry in {"n", "no"}:
            cancelled = True
            break
        intent_text = ""

    firmware_prompt_path: Optional[Path] = None
    board_header_path = Path(out_dir) / "include" / "board_capabilities.h"
    if validation_result.get("valid", False) and not cancelled:
        if board_header_path.exists():
            board_header_text = board_header_path.read_text(encoding="utf-8")
            driver_headers_context = _build_driver_headers_context(Path(out_dir))
            task_library_text = ""
            if isinstance(task_library_path, Path):
                if task_library_path.exists():
                    task_library_text = task_library_path.read_text(encoding="utf-8")
                else:
                    _log(f"[warn] app_intent task library not found: {task_library_path}")

            prompt_text = build_post_generation_firmware_prompt(
                intent_text=intent_text,
                board_capabilities_header=board_header_text,
                driver_headers_context=driver_headers_context,
                task_library_text=task_library_text,
                task_library_source=str(task_library_path) if isinstance(task_library_path, Path) else "",
            )
            artifacts_dir = Path(out_dir) / "_artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            firmware_prompt_path = artifacts_dir / f"post_gen_firmware_prompt_{_now_tag()}.txt"
            firmware_prompt_path.write_text(prompt_text, encoding="utf-8")
            _log(f"[ok] Post-generation firmware prompt written: {firmware_prompt_path}")
        else:
            _log(
                "[warn] Skipping post-generation firmware prompt build; missing "
                f"{board_header_path}"
            )

    report = {
        "enabled": True,
        "mode": refs_mode,
        "intent_text": intent_text,
        "cancelled": cancelled,
        "intent_reference_validation": validation_result,
        "board_mapping_source": str(board_header_path),
        "task_library_path": str(task_library_path) if isinstance(task_library_path, Path) else "",
        "firmware_prompt_path": str(firmware_prompt_path) if firmware_prompt_path else "",
    }
    report_path = Path(out_dir) / "app_intent_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _build_driver_headers_context(out_dir: Path) -> str:
    """
    Collect key driver headers so post-generation prompt can call existing APIs
    instead of inventing low-level/manual operations.
    """
    include_dir = Path(out_dir) / "include"
    header_names = [
        "system.h",
        "pll_driver.h",
        "pcr_driver.h",
        "iomm_driver.h",
        "gio_driver.h",
        "lin_driver.h",
        "sci_driver.h",
        "vim.h",
    ]
    sections: List[str] = []
    for name in header_names:
        header_path = include_dir / name
        if not header_path.exists():
            continue
        content = header_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not content:
            continue
        sections.extend(
            [
                f"===== BEGIN HEADER: include/{name} =====",
                content,
                f"===== END HEADER: include/{name} =====",
            ]
        )

    source_symbols = _extract_driver_source_symbols(Path(out_dir))
    if source_symbols:
        sections.append("===== BEGIN DRIVER_SOURCE_SYMBOLS =====")
        for filename in sorted(source_symbols.keys()):
            symbols = source_symbols.get(filename, [])
            if not symbols:
                continue
            preview = ", ".join(symbols[:40])
            suffix = " ..." if len(symbols) > 40 else ""
            sections.append(f"{filename}: {preview}{suffix}")
        sections.append("===== END DRIVER_SOURCE_SYMBOLS =====")
    return "\n".join(sections)


def _extract_driver_source_symbols(out_dir: Path) -> Dict[str, List[str]]:
    """
    Discover non-static BSP-like function symbols from generated source files so
    post-generation prompt can use helper APIs that may be missing from headers.
    """
    source_dir = Path(out_dir) / "source"
    if not source_dir.exists():
        return {}

    symbol_map: Dict[str, List[str]] = {}
    source_files = [
        "lin_driver.c",
        "sci_driver.c",
        "gio_driver.c",
        "iomm_driver.c",
        "pll_driver.c",
        "pcr_driver.c",
        "system.c",
        "vim.c",
    ]
    func_re = re.compile(
        r"^\s*(?!static\b)[A-Za-z_][\w\s\*]*?\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
        re.MULTILINE,
    )
    keep_prefixes = ("LIN_", "SCI_", "GIO_", "IOMM_", "PLL_", "PCR_", "system_", "vim_")

    for filename in source_files:
        path = source_dir / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        symbols = []
        for match in func_re.finditer(text):
            name = match.group(1)
            if name.startswith(keep_prefixes):
                symbols.append(name)
        unique_symbols = sorted(set(symbols))
        if unique_symbols:
            symbol_map[filename] = unique_symbols

    return symbol_map


def _build_post_gen_contract_slice(api_contract_manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(api_contract_manifest, dict):
        return {}
    modules = api_contract_manifest.get("modules", {})
    if not isinstance(modules, dict):
        return {}

    keep_modules = {"SYSTEM", "PLL", "PCR", "IOMM", "VIM", "GIO", "LIN", "SCI"}
    sliced_modules = {
        name: value
        for name, value in modules.items()
        if str(name).upper() in keep_modules and isinstance(value, dict)
    }
    if not sliced_modules:
        return {}

    return {
        "version": api_contract_manifest.get("version", ""),
        "generated_at": api_contract_manifest.get("generated_at", ""),
        "modules": sliced_modules,
    }


def _wire_app_intent_into_main(out_dir: Path) -> bool:
    """
    Deterministically wire APP_INTENT_Init/Step hooks into generated main.c.
    """
    main_c_path = Path(out_dir) / "main.c"
    if not main_c_path.exists():
        return False

    lines = main_c_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    changed = False

    if '#include "app_intent.h"' not in lines:
        include_indices = [idx for idx, line in enumerate(lines) if line.strip().startswith("#include ")]
        insert_at = include_indices[-1] + 1 if include_indices else 0
        lines.insert(insert_at, '#include "app_intent.h"')
        changed = True

    if not any("APP_INTENT_Init();" in line for line in lines):
        inserted_init = False
        for idx, line in enumerate(lines):
            if "BSP_ValidateInit();" in line:
                lines.insert(idx + 1, "    APP_INTENT_Init();")
                changed = True
                inserted_init = True
                break
        if not inserted_init:
            for idx, line in enumerate(lines):
                if line.strip() == "while (1)":
                    lines.insert(idx, "    APP_INTENT_Init();")
                    lines.insert(idx + 1, "")
                    changed = True
                    inserted_init = True
                    break

    if not any("APP_INTENT_Step();" in line for line in lines):
        inserted_step = False
        for idx, line in enumerate(lines):
            if "BSP_ValidateStep();" in line:
                lines.insert(idx + 1, "        APP_INTENT_Step();")
                changed = True
                inserted_step = True
                break
        if not inserted_step:
            for idx, line in enumerate(lines):
                if line.strip() == "while (1)":
                    for j in range(idx + 1, min(idx + 6, len(lines))):
                        if lines[j].strip() == "{":
                            lines.insert(j + 1, "        APP_INTENT_Step();")
                            changed = True
                            inserted_step = True
                            break
                    if inserted_step:
                        break

    if changed:
        main_c_path.write_text(
            normalize_generated_text("\n".join(lines), main_c_path),
            encoding="utf-8",
        )
    return changed


async def _run_post_generation_firmware_pass(
    *,
    out_dir: Path,
    intent_report: Dict[str, Any],
    model_enum: Model,
    max_tokens: int,
    generation_profile: Dict[str, Any],
    api_contract_manifest: Optional[Dict[str, Any]],
    bringup_contract: Optional[Dict[str, Any]],
    task_library_path: Optional[Path],
    token_allocator=None,
    progress_manager=None,
) -> Dict[str, Any]:
    intent_validation = intent_report.get("intent_reference_validation", {})
    if not bool(intent_validation.get("valid", False)):
        return {
            "enabled": True,
            "success": False,
            "reason": "invalid_intent_references",
            "written_files": [],
        }

    board_header_path = Path(out_dir) / "include" / "board_capabilities.h"
    if not board_header_path.exists():
        return {
            "enabled": True,
            "success": False,
            "reason": "missing_board_capabilities_header",
            "written_files": [],
        }

    board_header_text = board_header_path.read_text(encoding="utf-8")
    driver_headers_context = _build_driver_headers_context(Path(out_dir))
    task_library_text = ""
    if isinstance(task_library_path, Path) and task_library_path.exists():
        task_library_text = task_library_path.read_text(encoding="utf-8")

    bringup_contract_yaml = ""
    if isinstance(bringup_contract, dict):
        bringup_contract_yaml = dump_yaml_str(bringup_contract)

    profile_slice = {
        "app_intent": generation_profile.get("app_intent", {}),
        "bsp_validation": generation_profile.get("bsp_validation", {}),
        "bringup_mode": generation_profile.get("bringup_mode", {}),
    }
    profile_yaml = dump_yaml_str(profile_slice)

    contract_slice = _build_post_gen_contract_slice(api_contract_manifest)
    contract_slice_json = json.dumps(contract_slice, indent=2) if contract_slice else ""

    main_c_text = ""
    main_c_path = Path(out_dir) / "main.c"
    if main_c_path.exists():
        main_c_text = main_c_path.read_text(encoding="utf-8", errors="ignore")

    user_prompt = build_post_generation_firmware_prompt(
        intent_text=str(intent_report.get("intent_text", "")),
        board_capabilities_header=board_header_text,
        api_contract_manifest_json=contract_slice_json,
        bringup_contract_yaml=bringup_contract_yaml,
        generation_profile_yaml=profile_yaml,
        existing_main_c=main_c_text,
        driver_headers_context=driver_headers_context,
        task_library_text=task_library_text,
        task_library_source=str(task_library_path) if isinstance(task_library_path, Path) else "",
    )

    artifacts_dir = Path(out_dir) / "_artifacts"
    written_files = await _invoke_and_write(
        tag="post_gen_firmware",
        system_prompt=build_system_prompt(),
        user_prompt=user_prompt,
        model_enum=model_enum,
        max_tokens=max_tokens,
        artifacts_dir=artifacts_dir,
        out_dir=out_dir,
        token_allocator=token_allocator,
        progress_manager=progress_manager,
    )

    expected = {
        Path(out_dir) / "include" / "app_intent.h",
        Path(out_dir) / "source" / "app_intent.c",
    }
    produced = set(written_files or [])
    missing_expected = [str(path) for path in expected if path not in produced and not path.exists()]

    main_wired = _wire_app_intent_into_main(out_dir)
    if main_wired:
        print(f"[ok] Wired APP_INTENT hooks into {Path(out_dir) / 'main.c'}")

    report = {
        "enabled": True,
        "success": len(missing_expected) == 0 and len(written_files or []) > 0,
        "reason": "" if len(missing_expected) == 0 else "missing_expected_files",
        "written_files": [str(path) for path in (written_files or [])],
        "missing_expected_files": missing_expected,
        "main_hook_injected": main_wired,
        "expected_files": sorted(str(path) for path in expected),
        "max_tokens": int(max_tokens),
    }
    report_path = Path(out_dir) / "post_gen_firmware_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


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


def _resolve_yaml_root_for_args(args) -> Path:
    yaml_root = Path(args.yamlpath)
    if (yaml_root / "soc.yaml").exists():
        return yaml_root
    alt_yaml_root = Path("app") / args.yamlpath
    if (alt_yaml_root / "soc.yaml").exists():
        return alt_yaml_root
    return yaml_root


def _resolve_output_dir_for_action(args, *, interactive_fallback: bool = False) -> Optional[Path]:
    if args.output_dir:
        candidate = Path(args.output_dir).expanduser()
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    if getattr(args, "output_index", None):
        picked = _resolve_output_dir_from_index(int(args.output_index), limit=10)
        if picked is not None:
            return picked.resolve()
    if interactive_fallback and sys.stdin.isatty():
        return _pick_output_dir_interactive(limit=10)
    return None


def _load_bringup_contract_for_action(generation_profile: Dict[str, Any], yaml_root: Path) -> Optional[Dict[str, Any]]:
    bringup_cfg = generation_profile.get("bringup", {}) if isinstance(generation_profile.get("bringup", {}), dict) else {}
    configured_contract_file = bringup_cfg.get("contract_file")
    candidates: List[Path] = []
    if isinstance(configured_contract_file, str) and configured_contract_file.strip():
        raw = Path(configured_contract_file.strip())
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.extend(
                [
                    Path.cwd() / raw,
                    yaml_root / raw,
                    yaml_root.parent / raw,
                    yaml_root / raw.name,
                ]
            )
    else:
        candidates.append(yaml_root / "bringup_contract.yaml")

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate
        if resolved.exists():
            return load_bringup_contract(resolved)
    return None


def _load_generation_profile_for_action(args, yaml_root: Path) -> Dict[str, Any]:
    if args.no_profile and args.profile:
        print("[warn] --no-profile set; ignoring --profile.")
    profile_data, loaded_profile_path = _load_profile_data(
        args_profile=args.profile,
        no_profile=bool(args.no_profile),
        yaml_root=yaml_root,
    )
    if args.no_profile:
        print("[info] --no-profile set: using in-code defaults (no generation profile loaded).")
    elif loaded_profile_path is not None:
        print(f"[info] Loaded generation profile: {loaded_profile_path}")
    return _merge_generation_profile(profile_data)


def _write_reflash_log(out_dir: Path, content: str) -> Path:
    artifacts = out_dir / "_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / f"reflash_log_{_now_tag()}.txt"
    path.write_text(content, encoding="utf-8")
    return path


async def _run_compile_only_action(args) -> int:
    out_dir = _resolve_output_dir_for_action(args, interactive_fallback=sys.stdin.isatty())
    if out_dir is None:
        print("[error] compile_only requires --output-dir or --output-index.")
        return 2
    print(f"[info] Compile-only mode on output: {out_dir}")

    yaml_root = _resolve_yaml_root_for_args(args)
    generation_profile = _load_generation_profile_for_action(args, yaml_root)
    build_gate_cfg = generation_profile.get("build_gate", {}) if isinstance(generation_profile.get("build_gate", {}), dict) else {}

    workspace_seed = str(args.ccs_workspace or build_gate_cfg.get("external_workspace_path", "")).strip()
    project_seed = str(args.ccs_project or build_gate_cfg.get("project_name", "")).strip()
    workspace, project = _prompt_for_ccs_workspace_project(
        workspace_seed,
        project_seed,
        context_label="compile-only gate",
    )
    if not workspace or not project:
        print("[error] Missing CCS workspace/project for compile_only.")
        return 2

    bringup_contract = _load_bringup_contract_for_action(generation_profile, yaml_root)
    api_contract_manifest = _read_json_file_if_exists(Path(out_dir) / "api_contract_manifest.json")
    overrides = {
        "ccs_workspace": workspace,
        "ccs_project": project,
        "ccs_config": args.ccs_config,
        "build_gate": args.build_gate,
        "build_gate_llm": args.build_gate_llm,
        "build_gate_llm_top_k": args.build_gate_llm_top_k,
        "build_gate_llm_model": args.build_gate_llm_model,
        "model": args.model,
    }
    result = run_ccs_build_gate(
        output_dir=out_dir,
        generation_profile=generation_profile,
        overrides=overrides,
        api_contract_manifest=api_contract_manifest,
        bringup_contract=bringup_contract,
        run_model_name=args.model,
        progress_callback=print,
    )
    print(
        f"[info] Compile gate status: {result.get('status')} "
        f"(passes={bool(result.get('passes', False))}, rounds={len(result.get('rounds', []))})"
    )
    return 3 if gate_should_fail_run(result) else 0


def _emit_doxygen_quality_report(docs_dir: Path, report: Dict[str, Any]) -> Path:
    out_path = docs_dir / "doxygen_quality_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out_path


def _print_doxygen_quality_summary(report: Dict[str, Any], *, log=print) -> None:
    stats = report.get("stats", {}) if isinstance(report, dict) else {}
    log(
        "[info] Doxygen quality summary: "
        f"passes={bool(report.get('passes', False))}, "
        f"html={int(stats.get('html_files', 0))}, "
        f"source_pages={int(stats.get('source_pages', 0))}, "
        f"search_files={int(stats.get('search_files', 0))}"
    )
    for issue in list(report.get("issues", []) if isinstance(report, dict) else [])[:20]:
        log(f"[warn] Doxygen quality issue: {issue}")


async def _run_docs_only_action(args) -> int:
    out_dir = _resolve_output_dir_for_action(args, interactive_fallback=sys.stdin.isatty())
    if out_dir is None:
        print("[error] docs_only requires --output-dir or --output-index.")
        return 2
    print(f"[info] Docs-only mode on output: {out_dir}")

    docs_result = await _generate_documentation(out_dir, progress_manager=None)
    report_path = str((docs_result or {}).get("report_path", ""))
    if report_path:
        print(f"[info] Doxygen quality report: {report_path}")
    return 0


async def _run_reflash_action(args) -> int:
    out_dir = _resolve_output_dir_for_action(args, interactive_fallback=sys.stdin.isatty())
    if out_dir is None:
        print("[error] reflash requires --output-dir or --output-index.")
        return 2

    yaml_root = _resolve_yaml_root_for_args(args)
    generation_profile = _load_generation_profile_for_action(args, yaml_root)
    flash_cfg = generation_profile.get("flash", {}) if isinstance(generation_profile.get("flash", {}), dict) else {}
    if not bool(flash_cfg.get("enabled", False)):
        print("[error] flash.enabled is false in generation profile.")
        return 2

    command_template = str(flash_cfg.get("command_template", "")).strip()
    if not command_template:
        print("[error] Missing flash.command_template in generation profile.")
        return 2

    build_gate_cfg = generation_profile.get("build_gate", {}) if isinstance(generation_profile.get("build_gate", {}), dict) else {}
    workspace = str(args.ccs_workspace or build_gate_cfg.get("external_workspace_path", "")).strip()
    project = str(args.ccs_project or build_gate_cfg.get("project_name", "")).strip()
    config = str(args.ccs_config or build_gate_cfg.get("configuration", "Debug")).strip() or "Debug"

    values = {
        "output_dir": str(Path(out_dir).resolve()),
        "workspace": workspace,
        "project": project,
        "config": config,
        "timestamp_tag": _extract_output_tag(Path(out_dir)),
    }
    try:
        command = command_template.format(**values)
    except KeyError as exc:
        print(f"[error] flash.command_template contains unknown placeholder: {exc}")
        return 2

    working_dir_value = str(flash_cfg.get("working_dir", "")).strip()
    working_dir = Path(working_dir_value).expanduser().resolve() if working_dir_value else Path.cwd()
    if not working_dir.exists():
        print(f"[error] flash.working_dir not found: {working_dir}")
        return 2

    env = os.environ.copy()
    flash_env = flash_cfg.get("env", {})
    if isinstance(flash_env, dict):
        for k, v in flash_env.items():
            env[str(k)] = str(v)

    timeout_sec = int(flash_cfg.get("timeout_sec", 120) or 120)
    print(f"[info] Reflash command: {command}")
    print(f"[info] Working dir: {working_dir}")

    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_sec,
        )
        output = ""
        if proc.stdout:
            output += proc.stdout
        if proc.stderr:
            if output and not output.endswith("\n"):
                output += "\n"
            output += proc.stderr
        output += f"\n[info] exit_code={proc.returncode}\n"
        log_path = _write_reflash_log(Path(out_dir), output)
        print(f"[info] Reflash log: {log_path}")
        if proc.returncode != 0:
            print(f"[error] Reflash command failed with exit code {proc.returncode}")
            return 4
        print("[ok] Reflash command completed successfully.")
        return 0
    except subprocess.TimeoutExpired as exc:
        timeout_output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        timeout_output += f"\n[error] timeout after {timeout_sec}s\n"
        log_path = _write_reflash_log(Path(out_dir), timeout_output)
        print(f"[error] Reflash timed out after {timeout_sec}s. Log: {log_path}")
        return 4


async def _run_validation_only(args) -> int:
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
    if args.no_profile and args.profile:
        print("[warn] --no-profile set; ignoring --profile.")
    profile_data, loaded_profile_path = _load_profile_data(
        args_profile=args.profile,
        no_profile=bool(args.no_profile),
        yaml_root=yaml_root,
    )
    if args.no_profile:
        print("[info] --no-profile set: using in-code defaults (no generation profile loaded).")
    elif loaded_profile_path is not None:
        print(f"[info] Loaded generation profile: {loaded_profile_path}")

    generation_profile = _merge_generation_profile(profile_data)
    app_intent_cfg = generation_profile.get("app_intent", {}) if isinstance(generation_profile.get("app_intent", {}), dict) else {}
    app_intent_enabled = bool(app_intent_cfg.get("enabled", True))
    intent_refs_mode = str(
        args.intent_refs_mode
        or app_intent_cfg.get("intent_refs_mode", "proven_only")
    ).strip().lower()
    if intent_refs_mode not in {"proven_only", "include_unverified"}:
        intent_refs_mode = "proven_only"
    post_gen_generate = bool(args.post_gen_generate or app_intent_cfg.get("generate_firmware_pass", False))
    post_gen_max_tokens_raw = (
        args.post_gen_max_tokens
        if args.post_gen_max_tokens is not None
        else app_intent_cfg.get("post_gen_max_tokens", args.max_tokens)
    )
    try:
        post_gen_max_tokens = int(post_gen_max_tokens_raw)
    except (TypeError, ValueError):
        post_gen_max_tokens = int(args.max_tokens)
    if post_gen_max_tokens < 1024:
        post_gen_max_tokens = 1024

    configured_task_library = app_intent_cfg.get("task_library_path")
    app_intent_task_library_path: Optional[Path] = None
    if isinstance(configured_task_library, str) and configured_task_library.strip():
        app_intent_task_library_path = _resolve_optional_path(
            configured_task_library,
            yaml_root,
        )
        if app_intent_task_library_path is None:
            print(f"[warn] app_intent.task_library_path not found: {configured_task_library}")

    board_capability_manifest = _emit_board_capability_manifest(out_dir, board_data)
    print(f"[ok] Board capability manifest written: {out_dir / 'board_capability_manifest.json'}")
    print(f"[ok] Board capability header written: {out_dir / 'include' / 'board_capabilities.h'}")

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

    build_gate_cfg = generation_profile.get("build_gate", {}) if isinstance(generation_profile.get("build_gate", {}), dict) else {}
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
    run_build_gate_requested = bool(args.run_build_gate)
    if run_build_gate_requested:
        workspace_seed = str(
            args.ccs_workspace or build_gate_cfg.get("external_workspace_path", "")
        ).strip()
        project_seed = str(
            args.ccs_project or build_gate_cfg.get("project_name", "")
        ).strip()
        prompted_workspace, prompted_project = _prompt_for_ccs_workspace_project(
            workspace_seed,
            project_seed,
            context_label="validate-only compile gate",
        )
        if prompted_workspace and prompted_project:
            build_gate_overrides["ccs_workspace"] = prompted_workspace
            build_gate_overrides["ccs_project"] = prompted_project
        else:
            print("[warn] Skipping validate-only compile gate (missing CCS workspace/project).")
            run_build_gate_requested = False

    # Optional compile gate in validation-only mode
    build_gate_result = None
    build_gate_failed = False
    if run_build_gate_requested:
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

    final_report.build_evidence = _build_build_evidence_from_gate_result(build_gate_result)

    if api_contract_manifest:
        final_report.api_contract_hash = api_contract_manifest.get("api_contract_hash")

    final_report.runtime_invariants = {
        "validation_only_mode": True,
        "bringup_contract_loaded": bool(bringup_contract),
        "bringup_mode": bringup_mode,
        "fail_on_contract_mismatch": fail_on_contract_mismatch,
        "startup_contract_gate_mode": startup_gate_mode,
        "run_build_gate": bool(run_build_gate_requested),
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

    should_prompt_for_intent = bool(
        args.post_gen_prompt
        or args.post_gen_generate
        or post_gen_generate
        or str(args.app_intent or "").strip()
    )
    if app_intent_enabled and should_prompt_for_intent:
        intent_report = _run_post_generation_intent_prompt(
            out_dir,
            board_capability_manifest,
            refs_mode=intent_refs_mode,
            initial_intent=str(args.app_intent or ""),
            task_library_path=app_intent_task_library_path,
            progress_manager=None,
        )
        if not bool((intent_report or {}).get("intent_reference_validation", {}).get("valid", False)):
            print("[error] App intent reference validation failed in validate-only mode. See app_intent_report.json for details.")
            return 4

        if post_gen_generate:
            model_enum = {
                "haiku3.0": Model.HAIKU_3_0,
                "haiku4.5": Model.HAIKU_4_5,
                "sonnet3.5": Model.SONNET_3_5,
                "sonnet4.5": Model.SONNET_4_5,
                "opus4.5": Model.OPUS_4_5,
                "opus4.6": Model.OPUS_4_6,
            }[args.model]

            post_gen_report = await _run_post_generation_firmware_pass(
                out_dir=out_dir,
                intent_report=intent_report,
                model_enum=model_enum,
                max_tokens=post_gen_max_tokens,
                generation_profile=generation_profile,
                api_contract_manifest=api_contract_manifest,
                bringup_contract=bringup_contract,
                task_library_path=app_intent_task_library_path,
                token_allocator=None,
                progress_manager=None,
            )
            if not bool((post_gen_report or {}).get("success", False)):
                print("[error] Post-generation firmware pass failed in validate-only mode. See post_gen_firmware_report.json for details.")
                return 5

            if run_build_gate_requested:
                print("[info] Re-running external CCS compile gate after validate-only post-generation firmware pass...")
                build_gate_result = run_ccs_build_gate(
                    output_dir=out_dir,
                    generation_profile=generation_profile,
                    overrides=build_gate_overrides,
                    api_contract_manifest=api_contract_manifest,
                    bringup_contract=bringup_contract,
                    run_model_name=args.model,
                    progress_callback=print,
                )
                build_gate_failed = gate_should_fail_run(build_gate_result)
                print(
                    f"[info] Post-gen compile gate status (validate-only): {build_gate_result.get('status')} "
                    f"(passes={bool(build_gate_result.get('passes', False))}, "
                    f"rounds={len(build_gate_result.get('rounds', []))})"
                )
                _augment_compile_gate_report(
                    out_dir,
                    build_gate_result,
                    startup_contract_result,
                    startup_gate_mode,
                    parity_result,
                )
                synced = _sync_validation_report_build_evidence(
                    out_dir,
                    build_gate_result,
                    strict_validation_enabled=strict_validation_enabled,
                )
                if synced:
                    print("[info] Updated validation report with final post-gen compile-gate result (validate-only).")
                if build_gate_failed:
                    print("[error] Post-generation compile gate failed in validate-only mode.")
                    return 6
    elif should_prompt_for_intent and not app_intent_enabled:
        print("[warn] app_intent.enabled=false in profile; skipping post-generation intent prompt in validate-only mode.")

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
    _install_colored_print()

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
        "--menu",
        action="store_true",
        help="Open interactive run menu.",
    )
    parser.add_argument(
        "--action",
        default=None,
        choices=ACTION_CHOICES,
        help="Select high-level action flow (generate/validate/postgen/compile/docs/reflash).",
    )
    parser.add_argument(
        "--list-outputs",
        action="store_true",
        help="List the most recent output folders and exit.",
    )
    parser.add_argument(
        "--output-index",
        type=int,
        default=None,
        help="Select output folder by index from --list-outputs (1-based).",
    )
    parser.add_argument(
        "--post-gen-prompt",
        action="store_true",
        help="After BSP generation, prompt for app intent and validate board component references.",
    )
    parser.add_argument(
        "--post-gen-generate",
        action="store_true",
        help="After successful post-generation app intent validation, run an LLM firmware generation pass.",
    )
    parser.add_argument(
        "--post-gen-max-tokens",
        type=int,
        default=None,
        help="Max tokens for post-generation firmware pass (defaults to app_intent.post_gen_max_tokens or --max-tokens).",
    )
    parser.add_argument(
        "--app-intent",
        default="",
        help="Optional non-interactive app intent string to validate against board component allowlist.",
    )
    parser.add_argument(
        "--intent-refs-mode",
        default=None,
        choices=["proven_only", "include_unverified"],
        help="Reference validation mode for post-generation intent prompt. Defaults to profile or proven_only.",
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
        "--no-profile",
        action="store_true",
        help="Do not load --profile or auto-load generation_profile.yaml; use in-code defaults only.",
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

    if args.list_outputs:
        _print_recent_outputs(limit=10)
        return 0

    if args.output_index is not None and not args.output_dir:
        picked = _resolve_output_dir_from_index(int(args.output_index), limit=10)
        if picked is None:
            print(f"[error] --output-index {args.output_index} is out of range for recent outputs.")
            return 2
        args.output_dir = str(picked)

    open_menu = _should_open_auto_menu(
        sys.argv[1:],
        stdin_tty=sys.stdin.isatty(),
        stdout_tty=sys.stdout.isatty(),
        explicit_menu=bool(args.menu),
    )
    if open_menu:
        if not sys.stdin.isatty():
            print("[warn] Interactive menu requested but stdin is not a TTY; continuing without menu.")
        else:
            if not _apply_menu_selection(args):
                return 0

    action = _resolve_action_from_args(args)
    if action in {"validate", "postgen_prompt", "postgen_generate"}:
        args.validate_only = True
        if action == "postgen_prompt":
            args.post_gen_prompt = True
            args.post_gen_generate = False
        elif action == "postgen_generate":
            args.post_gen_prompt = True
            args.post_gen_generate = True
        if not args.output_dir:
            out_dir = _resolve_output_dir_for_action(args, interactive_fallback=sys.stdin.isatty())
            if out_dir is None:
                print("[error] This action requires --output-dir or --output-index.")
                return 2
            args.output_dir = str(out_dir)
        return await _run_validation_only(args)
    if action == "compile_only":
        return await _run_compile_only_action(args)
    if action == "docs_only":
        return await _run_docs_only_action(args)
    if action == "reflash":
        return await _run_reflash_action(args)

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

    passes = [
        "Discovery",
        "Implementation",
        "Platform",
        "Validation",
        "Post-Gen Intent",
        "Post-Gen Firmware",
        "Post-Gen Compile",
        "Docs",
    ]
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
    yaml_root_for_profile = Path(args.yamlpath)
    if args.no_profile and args.profile:
        print("[warn] --no-profile set; ignoring --profile.")
    profile_data, loaded_profile_path = _load_profile_data(
        args_profile=args.profile,
        no_profile=bool(args.no_profile),
        yaml_root=yaml_root_for_profile,
    )
    if args.no_profile:
        print("[info] --no-profile set: using in-code defaults (no generation profile loaded).")
    elif loaded_profile_path is not None:
        print(f"[info] Loaded generation profile: {loaded_profile_path}")

    generation_profile = _merge_generation_profile(profile_data)
    app_intent_cfg = generation_profile.get("app_intent", {}) if isinstance(generation_profile.get("app_intent", {}), dict) else {}
    app_intent_enabled = bool(app_intent_cfg.get("enabled", True))
    intent_refs_mode = str(
        args.intent_refs_mode
        or app_intent_cfg.get("intent_refs_mode", "proven_only")
    ).strip().lower()
    if intent_refs_mode not in {"proven_only", "include_unverified"}:
        intent_refs_mode = "proven_only"
    post_gen_generate = bool(args.post_gen_generate or app_intent_cfg.get("generate_firmware_pass", False))
    post_gen_max_tokens_raw = (
        args.post_gen_max_tokens
        if args.post_gen_max_tokens is not None
        else app_intent_cfg.get("post_gen_max_tokens", args.max_tokens)
    )
    try:
        post_gen_max_tokens = int(post_gen_max_tokens_raw)
    except (TypeError, ValueError):
        post_gen_max_tokens = int(args.max_tokens)
    if post_gen_max_tokens < 1024:
        post_gen_max_tokens = 1024

    configured_task_library = app_intent_cfg.get("task_library_path")
    app_intent_task_library_path: Optional[Path] = None
    if isinstance(configured_task_library, str) and configured_task_library.strip():
        app_intent_task_library_path = _resolve_optional_path(
            configured_task_library,
            Path(args.yamlpath),
        )
        if app_intent_task_library_path is None:
            print(f"[warn] app_intent.task_library_path not found: {configured_task_library}")

    board_capability_manifest = _emit_board_capability_manifest(out_dir, board_data)
    print(f"[ok] Board capability manifest written: {out_dir / 'board_capability_manifest.json'}")
    print(f"[ok] Board capability header written: {out_dir / 'include' / 'board_capabilities.h'}")

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
        strict_workspace, strict_project = _prompt_for_ccs_workspace_project(
            strict_workspace,
            strict_project,
            context_label="strict compile gate",
        )
        if strict_workspace and strict_project:
            build_gate_overrides["ccs_workspace"] = strict_workspace
            build_gate_overrides["ccs_project"] = strict_project
        elif sys.stdin.isatty():
            print("[warn] Missing CCS workspace/project; disabling compile gate for this run.")
            build_gate_enabled = False
            build_gate_mode = "off"
            build_gate_overrides["build_gate"] = "off"
        else:
            raise ValueError(
                "build_gate.mode=strict requires both build_gate.external_workspace_path and build_gate.project_name "
                "(or --ccs-workspace/--ccs-project overrides)."
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
        use_profile_modules = _should_use_profile_module_selection(
            loaded_profile_path=loaded_profile_path,
            no_profile=bool(args.no_profile),
            profile_enabled_modules=profile_enabled,
        )

        # Selection priority:
        # 1) explicit CLI modules
        # 2) loaded profile modules
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
        elif use_profile_modules:
            use_profile_selection = True
            if sys.stdin.isatty() and not args.yes:
                answer = input(
                    f"[user] Use modules from loaded profile ({', '.join(profile_enabled)})? [Y/n]: "
                ).strip().lower()
                if answer in {"n", "no"}:
                    use_profile_selection = False

            if use_profile_selection:
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

    docs_skipped_due_to_shutdown = False
    if _shutdown_requested:
        docs_skipped_due_to_shutdown = True
        print("[info] Shutdown requested. Documentation step will be skipped.")

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
            final_report.build_evidence = _build_build_evidence_from_gate_result(build_gate_result)
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

    should_prompt_for_intent = bool(
        args.post_gen_prompt
        or args.post_gen_generate
        or post_gen_generate
        or str(args.app_intent or "").strip()
    )
    defer_initial_build_gate_failure = bool(
        build_gate_failed
        and build_gate_enabled
        and app_intent_enabled
        and should_prompt_for_intent
        and post_gen_generate
    )

    def _start_optional_tracker(pass_name: str, task_name: str, total_tasks: int = 1):
        if not progress_manager:
            return None
        tracker = progress_manager.start_optional_pass(pass_name)
        if tracker:
            tracker.set_total_tasks(total_tasks)
            if task_name:
                tracker.update_task_name(task_name)
        return tracker

    def _complete_optional_tracker(pass_name: str, tracker, success: bool) -> None:
        if tracker:
            if success:
                tracker.increment_success()
            else:
                tracker.increment_failure()
        if progress_manager:
            progress_manager.complete_pass(pass_name, success=success)

    def _skip_optional(pass_name: str, reason: str) -> None:
        if progress_manager:
            progress_manager.skip_pass(pass_name, reason)

    progress_cleanup_done = False

    def _cleanup_progress_before_exit() -> None:
        nonlocal progress_cleanup_done
        if progress_cleanup_done or not progress_manager:
            return
        try:
            stats_local = _cost_tracker.get_stats()
            progress_manager.add_cost_info(
                stats_local.get("total_tokens", 0),
                stats_local.get("cost_usd", 0.0),
                model_enum.name,
            )
        except Exception:
            pass
        progress_manager.cleanup()
        progress_cleanup_done = True

    if startup_gate_mode == "fail" and bringup_contract_failed:
        print("[error] Startup/parity contract gate failed; see validation_report for details.")
        _skip_optional("Post-Gen Intent", "Skipped due to startup/parity gate failure")
        _skip_optional("Post-Gen Firmware", "Skipped due to startup/parity gate failure")
        _skip_optional("Post-Gen Compile", "Skipped due to startup/parity gate failure")
        _skip_optional("Docs", "Skipped due to startup/parity gate failure")
        _progress.stop_spinner()
        _cleanup_progress_before_exit()
        return 2
    if build_gate_failed and not defer_initial_build_gate_failure:
        print("[error] Strict CCS compile gate failed; see compile_gate_report.json and ccs_build_log.txt for details.")
        _skip_optional("Post-Gen Intent", "Skipped due to strict compile gate failure")
        _skip_optional("Post-Gen Firmware", "Skipped due to strict compile gate failure")
        _skip_optional("Post-Gen Compile", "Skipped due to strict compile gate failure")
        _skip_optional("Docs", "Skipped due to strict compile gate failure")
        _progress.stop_spinner()
        _cleanup_progress_before_exit()
        return 3
    if defer_initial_build_gate_failure:
        print(
            "[warn] Initial strict CCS compile gate failed; continuing to post-generation firmware pass "
            "and final compile-gate rerun."
        )

    # Ensure any remaining spinner threads are stopped
    _progress.stop_spinner()

    if app_intent_enabled and should_prompt_for_intent:
        intent_tracker = _start_optional_tracker(
            "Post-Gen Intent",
            "Collecting and validating app intent",
            total_tasks=1,
        )
        intent_report = _run_post_generation_intent_prompt(
            out_dir,
            board_capability_manifest,
            refs_mode=intent_refs_mode,
            initial_intent=str(args.app_intent or ""),
            task_library_path=app_intent_task_library_path,
            progress_manager=progress_manager,
        )
        intent_valid = bool((intent_report or {}).get("intent_reference_validation", {}).get("valid", False))
        _complete_optional_tracker("Post-Gen Intent", intent_tracker, success=intent_valid)
        if not intent_valid:
            _skip_optional("Post-Gen Firmware", "Skipped due to invalid app intent references")
            _skip_optional("Post-Gen Compile", "Skipped because firmware pass did not run")
            _skip_optional("Docs", "Skipped due to post-generation intent validation failure")
            print("[error] App intent reference validation failed. See app_intent_report.json for details.")
            _cleanup_progress_before_exit()
            return 4
        if post_gen_generate:
            firmware_tracker = _start_optional_tracker(
                "Post-Gen Firmware",
                "Generating app_intent firmware files",
                total_tasks=1,
            )
            post_gen_report = await _run_post_generation_firmware_pass(
                out_dir=out_dir,
                intent_report=intent_report,
                model_enum=model_enum,
                max_tokens=post_gen_max_tokens,
                generation_profile=generation_profile,
                api_contract_manifest=api_contract_manifest,
                bringup_contract=bringup_contract,
                task_library_path=app_intent_task_library_path,
                token_allocator=token_allocator,
                progress_manager=progress_manager,
            )
            firmware_success = bool((post_gen_report or {}).get("success", False))
            _complete_optional_tracker("Post-Gen Firmware", firmware_tracker, success=firmware_success)
            if not firmware_success:
                _skip_optional("Post-Gen Compile", "Skipped because firmware pass failed")
                _skip_optional("Docs", "Skipped due to firmware generation failure")
                print("[error] Post-generation firmware pass failed. See post_gen_firmware_report.json for details.")
                _cleanup_progress_before_exit()
                return 5

            # Compile gate was already run before post-gen modifications; rerun to verify new files.
            if build_gate_enabled:
                post_gen_compile_tracker = _start_optional_tracker(
                    "Post-Gen Compile",
                    "Re-running compile gate after post-gen changes",
                    total_tasks=1,
                )
                print("[info] Re-running external CCS compile gate after post-generation firmware pass...")

                def _post_gen_build_gate_progress(msg: str) -> None:
                    if progress_manager:
                        progress_manager.set_current_task(str(msg).replace("[build-gate]", "").strip() or "Compile gate")
                        progress_manager.emit_message(msg, force_console=True)
                    else:
                        print(msg)

                post_gen_build_gate_result = run_ccs_build_gate(
                    output_dir=out_dir,
                    generation_profile=generation_profile,
                    overrides=build_gate_overrides,
                    api_contract_manifest=api_contract_manifest,
                    bringup_contract=bringup_contract,
                    run_model_name=model_enum.value,
                    progress_callback=_post_gen_build_gate_progress,
                )
                post_gen_status = post_gen_build_gate_result.get("status", "unknown")
                post_gen_passes = bool(post_gen_build_gate_result.get("passes", False))
                print(
                    f"[info] Post-gen compile gate status: {post_gen_status} "
                    f"(passes={post_gen_passes})"
                )
                build_gate_result = post_gen_build_gate_result
                build_gate_failed = gate_should_fail_run(build_gate_result)
                _complete_optional_tracker(
                    "Post-Gen Compile",
                    post_gen_compile_tracker,
                    success=not build_gate_failed,
                )
                _augment_compile_gate_report(
                    out_dir,
                    build_gate_result,
                    startup_contract_result,
                    startup_gate_mode,
                    parity_result,
                )
                synced = _sync_validation_report_build_evidence(
                    out_dir,
                    build_gate_result,
                    strict_validation_enabled=strict_validation_enabled,
                )
                if synced:
                    print("[info] Updated validation report with final post-gen compile-gate result.")
                if build_gate_failed:
                    print(
                        "[error] Post-generation compile gate failed; see compile_gate_report.json "
                        "and ccs_build_log.txt for details."
                    )
                    _skip_optional("Docs", "Skipped due to post-generation compile gate failure")
                    _cleanup_progress_before_exit()
                    return 6
            else:
                _skip_optional("Post-Gen Compile", "Skipped because compile gate is disabled")
        else:
            _skip_optional("Post-Gen Firmware", "Skipped because post_gen_generate is disabled")
            _skip_optional("Post-Gen Compile", "Skipped because post_gen_generate is disabled")
    elif should_prompt_for_intent and not app_intent_enabled:
        print("[warn] app_intent.enabled=false in profile; skipping post-generation intent prompt.")
        _skip_optional("Post-Gen Intent", "Skipped because app_intent.enabled=false")
        _skip_optional("Post-Gen Firmware", "Skipped because app_intent.enabled=false")
        _skip_optional("Post-Gen Compile", "Skipped because app_intent.enabled=false")
    else:
        _skip_optional("Post-Gen Intent", "Skipped because no post-generation prompt was requested")
        _skip_optional("Post-Gen Firmware", "Skipped because no post-generation prompt was requested")
        _skip_optional("Post-Gen Compile", "Skipped because no post-generation prompt was requested")

    if docs_skipped_due_to_shutdown:
        _skip_optional("Docs", "Skipped due to shutdown request")
    else:
        docs_tracker = _start_optional_tracker("Docs", "Generating Doxygen docs and quality report", total_tasks=1)
        docs_result = await _generate_documentation(out_dir, progress_manager)
        docs_step_success = bool((docs_result or {}).get("step_success", True))
        _complete_optional_tracker("Docs", docs_tracker, success=docs_step_success)

    # Update cost metrics and cleanup progress manager
    if progress_manager:
        if not progress_cleanup_done:
            stats = _cost_tracker.get_stats()
            total_tokens = stats.get("total_tokens", 0)
            total_cost = stats.get("cost_usd", 0.0)
            progress_manager.add_cost_info(total_tokens, total_cost, model_enum.name)
            progress_manager.cleanup()
            progress_cleanup_done = True

        # Print final messages
        print(f"\n[ok] BSP generation complete!")
        print(f"[info] Output directory: {out_dir}")
    else:
        print(f"\n[ok] BSP generation complete!")
        print(f"[info] Output directory: {out_dir}")

    if not progress_manager or not progress_manager.should_suppress_prints():
        print("[debug] main() function returning...")


async def _generate_documentation(out_dir: Path, progress_manager=None) -> Dict[str, Any]:
    """Generate Doxygen documentation and always emit a quality report artifact."""
    if progress_manager:
        def log(message: str) -> None:
            progress_manager.emit_message(message, force_console=True)
    else:
        log = print

    log("\n[info] Creating documentation with Doxygen")

    docs_dir = out_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any]

    try:
        doxy_path = write_doxyfile(docs_dir)
        log(f"[info] Doxyfile created at {doxy_path}")

        run_doxygen(out_dir, doxy_path)

        report = evaluate_doxygen_output(docs_dir)
        report_path = _emit_doxygen_quality_report(docs_dir, report)
        _print_doxygen_quality_summary(report, log=log)

        html_dir = docs_dir / "html"
        index_file = html_dir / "index.html"
        if index_file.exists():
            html_files = list(html_dir.glob("*.html"))
            log(f"[ok] Documentation generated: {len(html_files)} HTML files in {html_dir}")
            log(f"[info] Open documentation at: file:///{index_file.resolve()}")
        else:
            log(f"[warn] Doxygen completed but index.html not found at {index_file}")
        log(f"[info] Doxygen quality report: {report_path}")
        return {
            "step_success": True,
            "status": "completed",
            "report": report,
            "report_path": str(report_path),
        }

    except FileNotFoundError as e:
        if "doxygen" in str(e).lower():
            log("[warn] Doxygen not found in system PATH. Install doxygen to generate documentation.")
            report = {
                "passes": False,
                "issues": ["Doxygen executable not found in PATH"],
                "checks": [],
                "stats": {"html_files": 0, "source_pages": 0, "search_files": 0},
            }
            report_path = _emit_doxygen_quality_report(docs_dir, report)
            log(f"[info] Doxygen quality report: {report_path}")
            return {
                "step_success": True,
                "status": "skipped_missing_doxygen",
                "report": report,
                "report_path": str(report_path),
            }
        log(f"[warn] Documentation generation failed: {e}")
    except RuntimeError as e:
        log(f"[warn] Doxygen generation failed: {e}")
        log("[info] Documentation skipped. BSP code generation was successful.")
    except Exception as e:
        log(f"[warn] Unexpected error during documentation generation: {e}")
        log("[info] Documentation skipped. BSP code generation was successful.")

    report = {
        "passes": False,
        "issues": ["Documentation generation failed before quality checks completed"],
        "checks": [],
        "stats": {"html_files": 0, "source_pages": 0, "search_files": 0},
    }
    report_path = _emit_doxygen_quality_report(docs_dir, report)
    log(f"[info] Doxygen quality report: {report_path}")
    return {
        "step_success": False,
        "status": "failed",
        "report": report,
        "report_path": str(report_path),
    }


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
