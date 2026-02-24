import argparse
import asyncio
import inspect
import json
import os
import signal
import sys
from pathlib import Path
from typing import List, Dict

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

from modules.yaml.yaml_utils import (
    dump_yaml_str,
    load_bus_yaml,
    load_soc_yaml,
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
    for periph in soc_data.get("peripherals", []):
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
    return await _invoke_and_write(
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
    args = parser.parse_args()

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

    # Validate cross-file references
    from modules.validation.cross_reference_validator import validate_and_report_cross_references
    if not validate_and_report_cross_references(soc_data, regs_data, irq_data, bus_data, pinmux_data):
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
        # Use --modules argument if provided, otherwise prompt interactively
        if args.modules:
            progress_manager.log_or_print(f"[info] Using peripherals from command line: {', '.join(args.modules)}")
            # Filter soc_data to only include specified modules
            all_peripherals = get_peripheral_list(soc_data)
            chosen_peripherals = [p for p in all_peripherals if p.get("name", "").upper() in [m.upper() for m in args.modules]]
            if len(chosen_peripherals) != len(args.modules):
                found_names = [p.get("name") for p in chosen_peripherals]
                missing = set(m.upper() for m in args.modules) - set(n.upper() for n in found_names)
                print(f"[warn] Could not find modules: {', '.join(missing)}")
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
                bus_data,
                pinmux_data,
                model_enum,
                out_dir,
                max_tokens=args.max_tokens,
                allowed_modules=pass2_modules,
                regs_data=regs_data,
                enable_validation=True,
                token_allocator=token_allocator,
                progress_manager=progress_manager
            )
            progress_manager.log_or_print("\n[info] Pass 2 Complete.")

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

            # Generate main.c with correct init sequence
            main_c_path = generate_main_c(
                init_order,
                dep_graph,
                out_dir,
                include_tests=args.include_tests,
                manifest=bsp_manifest
            )
            test_msg = " with test harness" if args.include_tests else ""
            print(f"[ok] Generated {main_c_path.name} with dependency-ordered init sequence{test_msg}")
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
            bus_yaml=system_bus_slice
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

    # Check for shutdown request before documentation
    if _shutdown_requested:
        print("[info] Shutdown requested. Skipping documentation generation.")
        return

    # Generate documentation
    await _generate_documentation(out_dir, progress_manager)

    # --- FINAL VALIDATION REPORT ---
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
        if 'pass2_validation_results' in locals() and pass2_validation_results:
            for module_name, validation_result in pass2_validation_results:
                # Extract facts validation details if available
                constants_validated = 0
                mismatches = 0
                if validation_result.facts_validation:
                    constants_validated = len(validation_result.facts_validation.matches) + len(validation_result.facts_validation.mismatches)
                    mismatches = len(validation_result.facts_validation.mismatches)

                module_validation = ModuleValidation(
                    module_name=module_name,
                    facts_mirror_valid=validation_result.is_valid,
                    constants_validated=constants_validated,
                    mismatches=mismatches,
                    tests_generated=False,  # Not tracking test generation currently
                    critical_errors=validation_result.errors[:10],  # Limit to 10
                    warnings=validation_result.warnings[:10]  # Limit to 10
                )
                final_report.peripheral_validations[module_name] = module_validation

            # Update summary
            final_report.validation_summary.total_modules = len(pass2_validation_results)
            final_report.validation_summary.modules_valid = sum(
                1 for _, vr in pass2_validation_results if vr.is_valid
            )
            final_report.validation_summary.modules_invalid = sum(
                1 for _, vr in pass2_validation_results if not vr.is_valid
            )
            final_report.validation_summary.critical_errors = sum(
                len(vr.errors) for _, vr in pass2_validation_results
            )
            final_report.validation_summary.warnings = sum(
                len(vr.warnings) for _, vr in pass2_validation_results
            )
            if final_report.validation_summary.total_modules > 0:
                final_report.validation_summary.success_rate = (
                    final_report.validation_summary.modules_valid /
                    final_report.validation_summary.total_modules
                ) * 100.0

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

        # Cleanup progress display before printing validation results
        progress_manager.cleanup()

        # Print console summary (always show final validation results)
        print_console_summary(final_report)

    except Exception as e:
        progress_manager.log_or_print(f"[warn] Could not generate final validation report: {e}")

    # Save token history for future runs
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
        print(f"\n[info] ✓ BSP generation complete!")
        print(f"[info] Output directory: {out_dir}")
    else:
        print(f"\n[info] ✓ BSP generation complete!")
        print(f"[info] Output directory: {out_dir}")

    if not progress_manager or not progress_manager.should_suppress_prints():
        print("[debug] main() function returning...")


async def _generate_documentation(out_dir: Path, progress_manager=None):
    """Generate Doxygen documentation (optional, skipped if doxygen not available)"""
    if progress_manager:
        progress_manager.log_or_print(f"\n[info] Creating documentation with Doxygen")
    else:
        print(f"\n[info] Creating documentation with Doxygen")
    docs_dir = out_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        doxy_path = write_doxyfile(docs_dir)
        run_doxygen(out_dir, doxy_path)
        if progress_manager:
            progress_manager.log_or_print(f"[ok] Documentation generated in {docs_dir / 'html'}.")
        else:
            print(f"[ok] Documentation generated in {docs_dir / 'html'}.")

        if (docs_dir / "html" / "index.html").exists():
            abs_path = os.path.abspath(docs_dir / "html" / "index.html")
            if progress_manager:
                progress_manager.log_or_print(f"[info] Docs index located at {abs_path}.")
            else:
                print(f"[info] Docs index located at {abs_path}.")
    except FileNotFoundError as e:
        msg = f"[warn] Doxygen not found in system PATH. Install doxygen to generate documentation."
        if progress_manager:
            progress_manager.log_or_print(msg)
        else:
            print(msg)
    except Exception as e:
        msg = f"[warn] Doxygen generation failed (documentation skipped)."
        if progress_manager:
            progress_manager.log_or_print(msg)
        else:
            print(msg)
        print(f"       Details: {e}")


if __name__ == "__main__":
    try:
        # Use asyncio.run which handles event loop creation and cleanup
        asyncio.run(main())
        print("[debug] asyncio.run() completed, exiting normally.")
    except KeyboardInterrupt:
        print("\n[info] Generation interrupted by user. Exiting.")
        _progress.stop_spinner()
        sys.exit(0)
    except Exception as e:
        print(f"\n[error] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        _progress.stop_spinner()
        sys.exit(1)
