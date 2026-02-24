import asyncio
import logging
import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path

from .prompt import build_pass2_driver_h_prompt, build_pass2_driver_c_prompt, invoke_model, Model

from ..utils.utils import extract_text_from_bedrock_response
from ..yaml.yaml_utils import dump_yaml_str, find_soc_peripheral
from ..utils.file_locking import FileLock

logger = logging.getLogger(__name__)


# ============================================================================
# Register Header Token Optimization
# ============================================================================

def strip_c_comments(content: str) -> str:
    """
    Remove all C/C++ style comments from header file while preserving all code.

    Removes:
    - Multi-line comments /* ... */
    - Single-line comments // ...

    Preserves:
    - All typedef declarations
    - All struct definitions
    - All #define statements (ALL bit field definitions)
    - All enum definitions
    - All actual code

    This removes 60-80% of file size (verbose documentation) while preserving
    100% of the context the LLM needs for accurate code generation.
    """
    # Remove multi-line comments /* ... */
    # Handle multi-line with DOTALL flag
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    # Remove single-line comments // ...
    # But be careful not to remove // in string literals (rare in headers)
    content = re.sub(r'//[^\n]*', '', content)

    return content


def compact_whitespace(content: str) -> str:
    """
    Compact excessive whitespace to reduce tokens further.

    - Removes empty lines (more than 2 consecutive newlines)
    - Preserves single blank lines for readability
    - Does not affect code structure or semantics
    """
    # Replace 3+ consecutive newlines with just 2
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

    # Remove trailing whitespace on each line
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

    return content


def extract_register_essentials(reg_header_path: Path, size_threshold: int = 15000) -> str:
    """
    Optimize register header by removing comments but preserving ALL code.

    Returns either:
    - Full header content (for simple peripherals < 15KB)
    - Comment-stripped version (for complex peripherals >= 15KB)

    CRITICAL: This preserves ALL context needed for accurate generation:
    - ALL typedef declarations
    - ALL struct members
    - ALL bit field #define statements (not just a subset)
    - ALL enum definitions
    - ALL macros

    Only documentation comments are removed, which typically account for
    60-80% of file size but provide redundant information (bit names are
    usually self-documenting, e.g., "SCI_SCIGCR1_TXENA" = transmit enable).

    Token reduction: ~70-80% for complex peripherals (>15KB)
    Accuracy impact: NONE - all code context preserved

    :param reg_header_path: Path to the register header file
    :param size_threshold: Size threshold in bytes (default 15KB)
    :return: Either full or optimized header content
    """
    if not reg_header_path.exists():
        return "// Register header not found"

    content = reg_header_path.read_text(encoding="utf-8")

    # Use full header if small enough
    if len(content) < size_threshold:
        return content

    # Strip comments but preserve ALL code
    optimized = strip_c_comments(content)

    # Compact excessive whitespace
    optimized = compact_whitespace(optimized)

    # Add header to indicate optimization was applied
    header = "// REGISTER HEADER - Comments stripped for token optimization\n"
    header += "// ALL code context preserved (typedefs, structs, ALL bit definitions)\n\n"
    optimized = header + optimized

    # Log the reduction
    original_size = len(content)
    optimized_size = len(optimized)
    reduction_pct = ((original_size - optimized_size) / original_size) * 100

    logger.info(f"Register header optimization: {reg_header_path.name} "
                f"{original_size} -> {optimized_size} bytes ({reduction_pct:.1f}% reduction)")

    return optimized

def build_pll_bus_slice(bus_data: Dict[str, Any]) -> str:
    """
    Extract a focused bus.yaml slice for PLL context.

    Includes only what PLL Pass1 manifest and Pass2 code-gen need:
    - Top-level sources with freq_hz and PLL sub-keys
    - Top-level domains with divider_register/field/bits
    - x-ext.peripheral_clocks.SYSTEM (source_number + domain_number mappings)
    - x-ext.peripheral_clocks.PLL (LPO frequencies)

    Omits per-peripheral clock entries (~750 lines of noise).
    Typical reduction: 826 lines → ~60 focused lines.
    """
    if not bus_data:
        return ""

    from ..yaml.yaml_utils import dump_yaml_str

    slice_data: Dict[str, Any] = {}

    # Sources: OSCIN freq, PLL1/PLL2 config
    if "sources" in bus_data:
        slice_data["sources"] = bus_data["sources"]

    # Domains: GCLK, HCLK, VCLK, VCLK2, VCLK3, VCLK4, RTICLK with dividers
    if "domains" in bus_data:
        slice_data["domains"] = bus_data["domains"]

    # SYSTEM + PLL sections from x-ext.peripheral_clocks
    x_ext = bus_data.get("x-ext") or {}
    periph_clocks = x_ext.get("peripheral_clocks") or {}
    focused: Dict[str, Any] = {}
    if "SYSTEM" in periph_clocks:
        focused["SYSTEM"] = periph_clocks["SYSTEM"]
    if "PLL" in periph_clocks:
        focused["PLL"] = periph_clocks["PLL"]
    if focused:
        slice_data["x-ext"] = {"peripheral_clocks": focused}

    return dump_yaml_str(slice_data) if slice_data else ""


def build_pinmux_slice(pinmux_data: Dict[str, Any], module_name: str) -> str:
    """
    Extract relevant pins from pinmux.yaml for a specific peripheral.

    Searches for pins where any function.signal matches common peripheral patterns:
    - SCI: SCIRX, SCITX
    - LIN: LINRX, LINTX
    - GIO: GIOA[n], GIOB[n]
    - SPI: MIBSPI*SCLK, MIBSPI*MISO, MIBSPI*MOSI, MIBSPI*NCS
    - I2C: I2C_SCL, I2C_SDA
    - CAN: CANTX, CANRX
    - PWM/EPWM: EPWM*A, EPWM*B
    - N2HET: N2HET*[n]

    Returns a YAML string containing only the relevant pins.
    """
    if not pinmux_data:
        return ""

    from ..yaml.yaml_utils import dump_yaml_str

    # Map module names to signal patterns
    signal_patterns = {
        "SCI": ["SCIRX", "SCITX"],
        "LIN": ["LINRX", "LINTX", "LINTX", "LIN2RX", "LIN2TX", "SCIRX", "SCITX"],  # LIN can use SCI pins
        "GIO": ["GIOA", "GIOB"],
        "SPI": ["MIBSPI", "SPI"],
        "I2C": ["I2C_SCL", "I2C_SDA"],
        "CAN": ["CANTX", "CANRX", "DCAN"],
        "PWM": ["EPWM", "PWMSYNC"],
        "EPWM": ["EPWM"],
        "N2HET": ["N2HET"],
    }

    module_upper = module_name.upper()

    # Special case: IOMM needs ALL pins with mux data (for pin-to-PINMMR lookup table)
    if module_upper == "IOMM":
        pins = pinmux_data.get("pins", [])
        # Filter to only pins that have mux information
        relevant_pins = []
        for pin in pins:
            functions = pin.get("functions", [])
            for func in functions:
                mux = func.get("mux")
                if mux and mux.get("register") and mux.get("bit") is not None:
                    relevant_pins.append(pin)
                    break  # Don't add same pin twice

        if not relevant_pins:
            return ""

        # Build complete pinmux data for IOMM
        slice_data = {
            "$id": pinmux_data.get("$id", "pinmux.schema.yaml"),
            "package": pinmux_data.get("package", ""),
            "pins": relevant_pins
        }
        return dump_yaml_str(slice_data)

    patterns = signal_patterns.get(module_upper, [])

    if not patterns:
        return ""

    # Find matching pins
    pins = pinmux_data.get("pins", [])
    relevant_pins = []

    for pin in pins:
        functions = pin.get("functions", [])
        for func in functions:
            signal = func.get("signal", "")
            # Check if this signal matches any of our patterns
            for pattern in patterns:
                if pattern in signal.upper():
                    relevant_pins.append(pin)
                    break  # Don't add the same pin twice
            if pin in relevant_pins:
                break  # Move to next pin

    if not relevant_pins:
        return ""

    # Build a minimal pinmux slice
    slice_data = {
        "$id": pinmux_data.get("$id", "pinmux.schema.yaml"),
        "package": pinmux_data.get("package", ""),
        "pins": relevant_pins
    }

    return dump_yaml_str(slice_data)


async def run_implementation_pass(
    manifest: Dict[str, Any],
    soc_data: Dict[str, Any],
    bus_data: Dict[str, Any],
    pinmux_data: Dict[str, Any],
    model: Model,
    output_dir: Path,
    max_tokens: int = 20000,
    allowed_modules: Optional[List[str]] = None,
    regs_data: Optional[Dict[str, Any]] = None,
    enable_validation: bool = True,
    token_allocator = None,
    progress_manager = None
):
    """
    Pass 2: Driver Implementation.

    Iterates through the Manifest created in Pass 1.
    Generates .h and .c files for each module.

    :param allowed_modules: If provided, only implement modules with names in this list.
    :param regs_data: Register definitions for validation
    :param enable_validation: Whether to run validation on generated files
    :param token_allocator: Optional token allocator for tracking token usage
    """
    
    api_catalog = manifest.get("api_catalog", {})
    
    # Filter catalog if needed
    if allowed_modules is not None:
        # Normalize to upper case for comparison
        allowed_set = set(m.upper() for m in allowed_modules)
        # Filter api_catalog
        api_catalog = {k: v for k, v in api_catalog.items() if k.upper() in allowed_set}
        print(f"[pass2] Filtered to {len(api_catalog)} modules based on user selection.")
    
    logger.info(f"Starting Pass 2 (Implementation) for {len(api_catalog)} modules...")

    # Setup progress tracker
    tracker = None
    if progress_manager:
        tracker = progress_manager.start_pass("Implementation")
        if tracker:
            tracker.set_total_tasks(len(api_catalog) * 2)  # header + source per module

    # Folder setup
    inc_dir = output_dir / "include"
    src_dir = output_dir / "source"
    inc_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(parents=True, exist_ok=True)

    tasks = []

    async def _generate_header(mod_name: str, mod_data: Dict, reg_content: str):
        """Generate driver header with retry logic"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        retry_policy = RetryPolicy()
        current_tokens = max_tokens

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                if tracker:
                    tracker.add_message(f"Retrying {mod_name} header - Attempt {attempt + 1} ({current_tokens} tokens)", level="warning")
                else:
                    print(f"  [retry] Pass2 header {mod_name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                prompt = build_pass2_driver_h_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

                # Track token usage for cost estimation
                if token_allocator:
                    try:
                        from ..utils.utils import extract_usage_from_bedrock_response
                        usage = extract_usage_from_bedrock_response(resp)
                        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                        if tokens_used > 0:
                            token_allocator.record_success(f"pass2_{mod_name.lower()}_header", tokens_used)
                    except Exception:
                        pass  # Don't fail if token tracking fails

                # Check for truncation
                truncation_reason = detect_simple_truncation(text)
                if truncation_reason:
                    print(f"  [warn] Truncation in {mod_name} header: {truncation_reason}")
                    should_retry, current_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        current_tokens
                    )
                    if should_retry:
                        continue
                    else:
                        logger.warning(f"Max retries exceeded for {mod_name} header")

                return ("h", text, text)  # (type, content, raw_response)

            except Exception as e:
                logger.error(f"Header Error {mod_name}: {e}")
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.TRANSIENT_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                return ("error", f"Header Gen Failed: {e}", "")

        return ("error", f"Max retries exceeded for {mod_name} header", "")

    async def _generate_source(mod_name: str, mod_data: Dict, reg_content: str, soc_slice: str, bus_slice: str, pinmux_slice: str, instance_pin_config: dict = None, dependency_manifests: dict = None):
        """Generate driver source with retry logic"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        retry_policy = RetryPolicy()
        current_tokens = max_tokens

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                if tracker:
                    tracker.add_message(f"Retrying {mod_name} source - Attempt {attempt + 1} ({current_tokens} tokens)", level="warning")
                else:
                    print(f"  [retry] Pass2 source {mod_name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                prompt = build_pass2_driver_c_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content, soc_slice, bus_slice, pinmux_slice, manifest=manifest, instance_pin_config=instance_pin_config, dependency_manifests=dependency_manifests)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

                # Track token usage for cost estimation
                if token_allocator:
                    try:
                        from ..utils.utils import extract_usage_from_bedrock_response
                        usage = extract_usage_from_bedrock_response(resp)
                        tokens_used = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                        if tokens_used > 0:
                            token_allocator.record_success(f"pass2_{mod_name.lower()}_source", tokens_used)
                    except Exception:
                        pass  # Don't fail if token tracking fails

                # Check for truncation
                truncation_reason = detect_simple_truncation(text)
                if truncation_reason:
                    print(f"  [warn] Truncation in {mod_name} source: {truncation_reason}")
                    should_retry, current_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        current_tokens
                    )
                    if should_retry:
                        continue
                    else:
                        logger.warning(f"Max retries exceeded for {mod_name} source")

                return ("c", text, text)  # (type, content, raw_response)

            except Exception as e:
                logger.error(f"Source Error {mod_name}: {e}")
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.TRANSIENT_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                return ("error", f"Source Gen Failed: {e}", "")

        return ("error", f"Max retries exceeded for {mod_name} source", "")

    async def _implement_module(mod_name: str, mod_data: Dict):
        # 1. Load Register Header Context (with token optimization)
        reg_filename = mod_data.get("reg_header_file", f"reg_{mod_name.lower()}.h")
        reg_path = output_dir / "include" / reg_filename

        reg_content = "// Register header not found"
        if reg_path.exists():
            # Use optimized extraction (full header for <15KB, essentials for >=15KB)
            reg_content = extract_register_essentials(reg_path)
            # print(f"[debug] {mod_name}: Loaded register context from {reg_filename} ({len(reg_content)} bytes)")
        else:
            logger.warning(f"Pass 2: Could not find {reg_path} for {mod_name}")
            # print(f"[warn] {mod_name}: REG HEADER MISSING. Driver may hallucinate struct members.")

        # PLL uses SYSTEM registers (PLLCTL1/2, CSDIS, GHVSRC, LPOMONCTL, CLKTEST etc.)
        # Append reg_system.h so LLM sees authoritative SYSTEM_ macro names alongside reg_pll.h
        if mod_name.upper() == "PLL":
            sys_reg_path = output_dir / "include" / "reg_system.h"
            if sys_reg_path.exists():
                sys_content = extract_register_essentials(sys_reg_path)
                reg_content = reg_content + "\n\n// === SYSTEM REGISTERS (PLLCTL1/2, CSDIS, GHVSRC etc.) ===\n" + sys_content

        # 2. Get Hardware Info (for Base Address)
        soc_periph = find_soc_peripheral(soc_data, mod_name)
        soc_slice = dump_yaml_str(soc_periph) if soc_periph else ""
        
        # 3. Get Bus Info (for Clocks/Baud Rates)
        # PLL gets a focused slice (sources + domains + SYSTEM/PLL numbers only).
        # Other peripherals get the full bus dump (usually small enough).
        if mod_name.upper() == "PLL":
            bus_slice = build_pll_bus_slice(bus_data)
        else:
            bus_slice = dump_yaml_str(bus_data)

        # 4. Get Pinmux Info (for Pin Configuration)
        pinmux_slice = build_pinmux_slice(pinmux_data, mod_name)

        # 4a. Extract per-instance pin configurations
        instance_pin_config = None
        try:
            from .pin_config_builder import extract_peripheral_instances
            instance_pin_config = extract_peripheral_instances(
                board_data=soc_data,
                pinmux_data=pinmux_data,
                peripheral=mod_name
            )
        except Exception as e:
            if tracker:
                tracker.add_message(f"Warning: Could not extract pin config for {mod_name}: {e}", level="warning")
            # Continue with None - graceful degradation

        # 4b. Collect dependency manifests
        dependency_manifests = {}
        if mod_data and 'dependencies' in mod_data:
            for dep_name in mod_data['dependencies']:
                if dep_name in api_catalog:
                    dependency_manifests[dep_name] = api_catalog[dep_name]

        # 5. Launch Parallel Gens
        t_h = asyncio.create_task(_generate_header(mod_name, mod_data, reg_content))
        t_c = asyncio.create_task(_generate_source(mod_name, mod_data, reg_content, soc_slice, bus_slice, pinmux_slice, instance_pin_config, dependency_manifests))
        
        results = await asyncio.gather(t_h, t_c)
        
        return mod_name, results

    # Launch all modules
    for name, data in api_catalog.items():
        tasks.append(_implement_module(name, data))
        
    print(f"[pass2] Implementing {len(tasks)} modules...")
    
    # Process results as they come in
    validation_results = []

    for f in asyncio.as_completed(tasks):
        mod_name, results = await f

        # Track progress
        if tracker:
            tracker.update_task_name(f"Completed {mod_name}")
        else:
            print(f".", end="", flush=True)

        # Collect written files and raw responses for validation
        written_files = []
        raw_responses = []
        has_error = False

        for type_tag, content, raw_response in results:
            if type_tag == "error":
                has_error = True
                if tracker:
                    tracker.add_message(f"{mod_name}: {content}", level="error")
                    tracker.increment_failure()
                else:
                    logger.error(f"[{mod_name}] {content}")
                continue

            # Clean Code Block
            clean_code = content
            if "```" in content:
                import re
                match = re.search(r"```c?(.*?)```", content, re.DOTALL)
                if match:
                    clean_code = match.group(1).strip()

            # Write File
            if type_tag == "h":
                fname = f"{mod_name.lower()}_driver.h"
                fpath = inc_dir / fname

                # Use file locking to prevent race conditions
                with FileLock(fpath):
                    fpath.write_text(clean_code, encoding="utf-8")

                written_files.append(fpath)
                raw_responses.append(raw_response)
                if tracker:
                    tracker.increment_success()
            elif type_tag == "c":
                fname = f"{mod_name.lower()}_driver.c"
                fpath = src_dir / fname

                # Use file locking to prevent race conditions
                with FileLock(fpath):
                    fpath.write_text(clean_code, encoding="utf-8")

                written_files.append(fpath)
                raw_responses.append(raw_response)
                if tracker:
                    tracker.increment_success()

        # Run validation if enabled
        if enable_validation and written_files and soc_data and regs_data:
            from ..validation.validation_engine import validate_generation_output
            from ..validation.pass2_validator import validate_driver_implementation

            try:
                # Combine raw responses for validation preamble
                combined_raw = "\n\n".join(raw_responses)

                # Run FACTS MIRROR validation
                validation_result = validate_generation_output(
                    tag=f"pass2_{mod_name.lower()}",
                    preamble=combined_raw,
                    written_files=written_files,
                    soc_data=soc_data,
                    regs_data=regs_data
                )

                # Run Pass 2 driver-specific validation (clock usage, API compliance)
                manifest_entry = api_catalog.get(mod_name, {})
                pass2_result = validate_driver_implementation(
                    module_name=mod_name,
                    manifest_entry=manifest_entry,
                    preamble=combined_raw,
                    written_files=written_files,
                    soc_data=soc_data,
                    regs_data=regs_data
                )

                # Merge validation results
                if not pass2_result.is_valid:
                    validation_result.is_valid = False
                    validation_result.errors.extend(pass2_result.critical_errors)
                    validation_result.warnings.extend(pass2_result.warnings)

                validation_results.append((mod_name, validation_result))

                # Log validation summary
                if not validation_result.is_valid:
                    logger.warning(f"Pass 2 validation failed for {mod_name}")
                    for error in validation_result.errors[:3]:  # Show first 3 errors
                        logger.warning(f"  - {error}")
                if pass2_result.warnings:
                    for warning in pass2_result.warnings[:3]:  # Show first 3 warnings
                        logger.info(f"  - {warning}")
            except Exception as e:
                logger.error(f"Validation error for {mod_name}: {e}")

    # Complete pass tracking
    if progress_manager:
        progress_manager.complete_pass("Implementation", success=True)

    if not tracker:
        print("\n[pass2] Implementation Complete.")

    if enable_validation and validation_results:
        failed_count = sum(1 for _, vr in validation_results if not vr.is_valid)
        logger.info(f"Pass 2 Validation: {len(validation_results)} modules checked, {failed_count} failed")

    # Return validation results for final report
    return validation_results if enable_validation else []
