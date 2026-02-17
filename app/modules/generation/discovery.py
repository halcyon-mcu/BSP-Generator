import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from .prompt import (
    build_manifest_prompt,
    build_reg_header_prompt,
    invoke_model,
    Model,
    Message
)
from ..utils.utils import extract_text_from_bedrock_response
from ..yaml.yaml_utils import dump_yaml_str, get_soc_peripherals

logger = logging.getLogger(__name__)


def clean_json_string(json_str: str) -> str:
    """
    Clean common JSON formatting issues that LLMs sometimes produce.

    Args:
        json_str: Potentially malformed JSON string

    Returns:
        Cleaned JSON string
    """
    import re

    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    # Remove single-line comments (// ...)
    json_str = re.sub(r'//[^\n]*\n', '\n', json_str)

    # Remove multi-line comments (/* ... */)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

    return json_str


def extract_typedef_from_header(header_content: str) -> Optional[str]:
    """
    Extract the register typedef name from a generated register header.
    Looks for patterns like:
      typedef volatile struct { ... } typename_t;
    or
      } typename_t;

    Returns the typedef name (e.g., "pll_reg_map_t", "SYSTEM_REGS_t") or None if not found.
    """
    if not header_content:
        return None

    import re

    # Pattern 1: typedef volatile struct { ... } name_t;
    # Match the closing brace and typedef name
    pattern1 = r'}\s*(\w+_t)\s*;'
    matches = re.findall(pattern1, header_content)

    # Return the last match (usually the main struct typedef)
    if matches:
        # Filter out common non-register typedefs
        register_typedefs = [m for m in matches if not m.endswith('_type_t') and not m.startswith('vim_')]
        if register_typedefs:
            return register_typedefs[-1]  # Return last match (main typedef)
        elif matches:
            return matches[-1]  # Fallback to any typedef

    return None

async def run_discovery_pass(
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    model: Model,
    output_dir: Path,
    max_tokens: int = 20000,
    token_allocator=None,
    enable_validation: bool = True,
    allowed_modules: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Pass 1: Architecture Discovery & Registry Build.
    Splits the work into two parallel calls per module:
      1A. Manifest Generation (JSON)
      1B. Header Generation (C Code)

    Args:
        token_allocator: Optional AdaptiveTokenAllocator for learning optimal token counts
        enable_validation: Whether to run validation on generated files
        allowed_modules: If provided, only process modules with names in this list
    """
    
    # 1. Setup Output
    include_dir = output_dir / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "api_catalog": {}
    }
    
    # 2. Prepare Async Tasks
    tasks = []
    peripherals = get_soc_peripherals(soc_data)

    # Filter peripherals if allowed_modules specified
    if allowed_modules is not None:
        # Normalize to upper case for comparison
        allowed_set = set(m.upper() for m in allowed_modules)
        peripherals = [p for p in peripherals if p.get("name", "").upper() in allowed_set]

        # Improved logging to show core vs peripheral breakdown
        core_count = len([m for m in allowed_modules if m.upper() in ['SYSTEM', 'PLL', 'VIM']])
        periph_count = len(peripherals) - core_count
        logger.info(f"Generating manifests for {len(peripherals)} modules ({core_count} core + {periph_count} peripheral)")
    else:
        logger.info(f"Generating manifests for all {len(peripherals)} modules")

    logger.info(f"Starting Pass 1 (Discovery) for {len(peripherals)} modules...")

    async def _process_module_manifest(name: str, soc_slice: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON Manifest with retry logic"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        retry_policy = RetryPolicy(max_retries=2)  # Manifests are small, fewer retries
        current_tokens = 4096

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                print(f"  [retry] Pass1 manifest {name} - Attempt {attempt + 1}")

            try:
                prompt = build_manifest_prompt(name, soc_slice)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

                # Check for truncation
                truncation_reason = detect_simple_truncation(text)
                if truncation_reason:
                    should_retry, current_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        current_tokens
                    )
                    if should_retry:
                        continue

                # Parse JSON
                clean_text = text.replace("```json", "").replace("```", "").strip()
                start = clean_text.find("{")
                end = clean_text.rfind("}")

                if start == -1 or end == -1:
                    # JSON not found - might be truncation
                    logger.warning(f"Could not find JSON braces in manifest response for {name}")
                    logger.debug(f"Response preview: {text[:200]}")
                    return None

                json_text = clean_text[start:end+1]

                # Try parsing as-is first
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    # Try with cleaning
                    try:
                        cleaned_json = clean_json_string(json_text)
                        return json.loads(cleaned_json)
                    except json.JSONDecodeError as json_err:
                        # Log the actual JSON that failed to parse
                        logger.error(f"Manifest JSON Error {name}: {json_err}")
                        logger.debug(f"Failed JSON (first 500 chars): {json_text[:500]}")

                        # Save problematic response to debug file
                        try:
                            debug_dir = output_dir / "_debug"
                            debug_dir.mkdir(parents=True, exist_ok=True)
                            debug_file = debug_dir / f"manifest_{name}_failed.txt"
                            debug_file.write_text(f"Original response:\n{text}\n\n"
                                                f"Extracted JSON:\n{json_text}\n\n"
                                                f"Error: {json_err}", encoding='utf-8')
                            logger.info(f"Saved problematic response to {debug_file}")
                        except Exception:
                            pass  # Don't fail on debug file write

                        # Retry on JSON parse errors
                        should_retry, current_tokens = retry_policy.should_retry(
                            attempt + 1,
                            FailureReason.VALIDATION_ERROR,
                            current_tokens
                        )
                        if should_retry:
                            continue
                        return None

            except json.JSONDecodeError as e:
                # This shouldn't be reached now, but keep it as fallback
                logger.error(f"Manifest JSON Error {name}: {e}")
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.VALIDATION_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                return None

            except Exception as e:
                logger.error(f"Manifest Error {name}: {e}")
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.TRANSIENT_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                return None

        return None  # Max retries exceeded

    async def _process_module_header(name: str, soc_slice: str, regs_slice: str) -> Optional[tuple]:
        """Fetch C Header Content with retry logic. Returns (extracted_code, raw_response)"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        # Get adaptive token allocation
        initial_tokens = max_tokens
        if token_allocator:
            initial_tokens = token_allocator.get_initial_tokens(f"pass1_{name}_header", default=max_tokens)

        retry_policy = RetryPolicy()
        current_tokens = initial_tokens

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                print(f"  [retry] Pass1 header {name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                prompt = build_reg_header_prompt(name, soc_slice, regs_slice)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

                # Check for truncation before parsing
                truncation_reason = detect_simple_truncation(text)
                if truncation_reason:
                    print(f"  [warn] Truncation in {name} header: {truncation_reason}")
                    should_retry, current_tokens = retry_policy.should_retry(
                        attempt + 1,
                        FailureReason.TOKEN_TRUNCATION,
                        current_tokens
                    )
                    if should_retry:
                        continue
                    else:
                        # Return what we have even if truncated
                        logger.warning(f"Max retries exceeded for {name} header")

                # Extract C code
                # 1. Try finding markdown block
                start_block = text.find("```c")
                if start_block != -1:
                    code_text = text[start_block+4:]
                    end_block = code_text.find("```")
                    if end_block != -1:
                        extracted = code_text[:end_block].strip()
                        # Record success
                        if token_allocator:
                            token_allocator.record_success(f"pass1_{name}_header", current_tokens)
                        return (extracted, text)

                # 2. Try generic markdown
                start_block = text.find("```")
                if start_block != -1:
                    code_text = text[start_block+3:]
                    end_block = code_text.find("```")
                    if end_block != -1:
                        extracted = code_text[:end_block].strip()
                        if token_allocator:
                            token_allocator.record_success(f"pass1_{name}_header", current_tokens)
                        return (extracted, text)

                # 3. Fallback: If it looks like a header, return full text
                if "#ifndef" in text or "typedef" in text:
                    extracted = text.replace("```c", "").replace("```", "").strip()
                    if token_allocator:
                        token_allocator.record_success(f"pass1_{name}_header", current_tokens)
                    return (extracted, text)

                # Could not parse
                logger.warning(f"Could not parse C code from response for {name}")
                error_code = "// [WARN] Could not parse C code from AI response.\n/*\n" + text + "\n*/"
                return (error_code, text)

            except Exception as e:
                logger.error(f"Header Error {name}: {e}")
                # Check if we should retry on error
                should_retry, current_tokens = retry_policy.should_retry(
                    attempt + 1,
                    FailureReason.TRANSIENT_ERROR,
                    current_tokens
                )
                if should_retry:
                    continue
                else:
                    error_msg = f"// Error generating header for {name}: {e}"
                    return (error_msg, error_msg)

        # Max retries exceeded
        error_msg = f"// Max retries exceeded for {name}"
        return (error_msg, error_msg)

    async def _process_module_full(periph: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = periph.get("name", "UNKNOWN")
        p_type = periph.get("type", "").lower()
        
        # Prepare Context Slices
        soc_slice = dump_yaml_str(periph)
        
        # --- FIX: More Robust Lookup Logic ---
        regs_slice = ""

        # Access the 'peripherals' dictionary (ignoring top-level wrappers if any)
        # Note: load_regs_yaml() returns the whole file content.
        # Based on user context, regs.yaml structure is likely:
        # peripherals:
        #   sci: ...
        #   gio: ...

        all_peripherals = regs_data.get("peripherals", {})

        # Helper: strip trailing numbers (e.g., "MIBSPI1" -> "MIBSPI", "N2HET1" -> "N2HET")
        import re
        def strip_trailing_number(s):
            return re.sub(r'\d+$', '', s) if s else s

        # Name mapping for peripherals with different names in soc.yaml vs regs.yaml
        name_mapping = {
            'MIBSPI': 'SPI',
            'N2HET': 'TIMER',
            'MIBADC': 'ADC',
            'FLASH_MODULE': 'FMC',
            'USB_DEVICE': 'USB',
            'USB_OHCI': 'USB',
            'MDIO': 'EMACMDIO',
            'EMAC': 'EMACMDIO',
        }

        # 1. Try exact match on 'type' (e.g. type='sci' -> regs['sci'])
        # Handle case-sensitivity by trying both raw and lower
        if p_type and p_type in all_peripherals:
            regs_slice = dump_yaml_str({p_type: all_peripherals[p_type]})
        elif p_type and p_type.lower() in all_peripherals:
            regs_slice = dump_yaml_str({p_type.lower(): all_peripherals[p_type.lower()]})

        # 2. If 'type' lookup failed, try looking up by 'name' (e.g. name='SYSTEM' -> regs['system'])
        elif name in all_peripherals:
             regs_slice = dump_yaml_str({name: all_peripherals[name]})
        elif name.lower() in all_peripherals:
             regs_slice = dump_yaml_str({name.lower(): all_peripherals[name.lower()]})

        # 3. Try stripped versions (remove trailing numbers)
        # e.g., "MIBSPI1" -> try "MIBSPI", "mibspi"
        if not regs_slice and name:
            name_stripped = strip_trailing_number(name)
            if name_stripped != name:  # Only if we actually stripped something
                if name_stripped in all_peripherals:
                    regs_slice = dump_yaml_str({name_stripped: all_peripherals[name_stripped]})
                elif name_stripped.lower() in all_peripherals:
                    regs_slice = dump_yaml_str({name_stripped.lower(): all_peripherals[name_stripped.lower()]})

        # 4. Try name mapping (e.g., "MIBSPI" -> "SPI", "N2HET" -> "TIMER")
        if not regs_slice and name:
            name_stripped = strip_trailing_number(name)
            mapped_name = name_mapping.get(name_stripped.upper())
            if mapped_name:
                if mapped_name in all_peripherals:
                    regs_slice = dump_yaml_str({mapped_name: all_peripherals[mapped_name]})
                elif mapped_name.lower() in all_peripherals:
                    regs_slice = dump_yaml_str({mapped_name.lower(): all_peripherals[mapped_name.lower()]})


        # 5. SPECIAL CASE: SYSTEM Aggregation
        # If this is the "SYSTEM" module, we want to include "system2" definitions as well
        # so they appear in the same reg_system.h file.
        if name.upper() == "SYSTEM":
            extra_slice = ""
            if "system2" in all_peripherals:
                extra_slice = dump_yaml_str({"system2": all_peripherals["system2"]})
                # Append to existing slice
                regs_slice = regs_slice + "\n" + extra_slice
                logger.info("Merged 'system2' registers into SYSTEM discovery context.")

        # 6. Warn if no registers found
        # (This is expected for some peripherals that may not have register definitions yet)
        if not regs_slice:
            logger.warning(f"Discovery: No register definition found for module '{name}' (type='{p_type}'). Header will likely be empty.")

        # Run both tasks in parallel
        man_task = asyncio.create_task(_process_module_manifest(name, soc_slice))
        head_task = asyncio.create_task(_process_module_header(name, soc_slice, regs_slice))

        man_res, head_res_tuple = await asyncio.gather(man_task, head_task)

        # Unpack header result (extracted_code, raw_response)
        if head_res_tuple:
            head_content, head_raw = head_res_tuple
        else:
            head_content, head_raw = None, None

        if man_res:
            return {
                "manifest": man_res,
                "reg_header_content": head_content,
                "reg_header_raw": head_raw,  # Store raw response for validation
                "module_name": name
            }
        return None

    # 3. Scatter (Launch all tasks)
    for p in peripherals:
        tasks.append(_process_module_full(p))

    print(f"[pass1] Launched {len(peripherals)} tasks (double-threaded). Waiting for results...")
    
    # Use as_completed to show progress
    results = []
    for f in asyncio.as_completed(tasks):
        res = await f
        results.append(res)
        print(".", end="", flush=True)
    print("\n")
    
    # 5. Process Results
    success_count = 0
    validation_results = []

    for res in results:
        if not res:
            continue

        # Extract Manifest
        mod_manifest = res.get("manifest", {})
        mod_name = mod_manifest.get("module_name") or res.get("module_name")

        if mod_name:
            if mod_manifest:
                # Extract typedef name from register header and add to manifest
                header_content = res.get("reg_header_content")
                if header_content:
                    typedef_name = extract_typedef_from_header(header_content)
                    if typedef_name:
                        mod_manifest["register_typedef"] = typedef_name
                        logger.info(f"Extracted typedef '{typedef_name}' for {mod_name}")
                    else:
                        logger.warning(f"Could not extract typedef from register header for {mod_name}")

                manifest["api_catalog"][mod_name] = mod_manifest
            success_count += 1

            # Write Register Header
            header_content = res.get("reg_header_content")
            header_name = mod_manifest.get("reg_header_file", f"reg_{mod_name.lower()}.h") if mod_manifest else f"reg_{mod_name.lower()}.h"

            if header_content:
                header_path = include_dir / header_name
                header_path.write_text(header_content, encoding="utf-8")
                # logger.info(f"Generated {header_name}")

                # Run validation if enabled
                if enable_validation and soc_data and regs_data:
                    from ..validation.validation_engine import validate_generation_output

                    try:
                        header_raw = res.get("reg_header_raw", "")
                        validation_result = validate_generation_output(
                            tag=f"pass1_{mod_name.lower()}",
                            preamble=header_raw,
                            written_files=[header_path],
                            soc_data=soc_data,
                            regs_data=regs_data
                        )
                        validation_results.append((mod_name, validation_result))

                        # Log validation summary
                        if not validation_result.is_valid:
                            logger.warning(f"Pass 1 validation failed for {mod_name}")
                            for error in validation_result.errors[:3]:  # Show first 3 errors
                                logger.warning(f"  - {error}")
                    except Exception as e:
                        logger.error(f"Validation error for {mod_name}: {e}")

    # 6. Write Source of Truth
    manifest_path = output_dir / "bsp_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.info(f"Pass 1 Complete. Registry built with {success_count} modules.")
    logger.info(f"Manifest: {manifest_path}")

    if enable_validation and validation_results:
        failed_count = sum(1 for _, vr in validation_results if not vr.is_valid)
        logger.info(f"Pass 1 Validation: {len(validation_results)} modules checked, {failed_count} failed")

    return manifest
