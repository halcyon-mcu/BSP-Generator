import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .prompt import build_pass2_driver_h_prompt, build_pass2_driver_c_prompt, invoke_model, Model

from ..utils.utils import extract_text_from_bedrock_response
from ..yaml.yaml_utils import dump_yaml_str, find_soc_peripheral

logger = logging.getLogger(__name__)

async def run_implementation_pass(
    manifest: Dict[str, Any],
    soc_data: Dict[str, Any],
    bus_data: Dict[str, Any],
    model: Model,
    output_dir: Path,
    max_tokens: int = 20000,
    allowed_modules: Optional[List[str]] = None,
    regs_data: Optional[Dict[str, Any]] = None,
    enable_validation: bool = True
):
    """
    Pass 2: Driver Implementation.

    Iterates through the Manifest created in Pass 1.
    Generates .h and .c files for each module.

    :param allowed_modules: If provided, only implement modules with names in this list.
    :param regs_data: Register definitions for validation
    :param enable_validation: Whether to run validation on generated files
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
                print(f"  [retry] Pass2 header {mod_name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                prompt = build_pass2_driver_h_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

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

    async def _generate_source(mod_name: str, mod_data: Dict, reg_content: str, soc_slice: str, bus_slice: str):
        """Generate driver source with retry logic"""
        from ..regeneration.retry_policy import RetryPolicy, FailureReason
        from ..regeneration.truncation_detector import detect_simple_truncation

        retry_policy = RetryPolicy()
        current_tokens = max_tokens

        for attempt in range(retry_policy.max_retries + 1):
            if attempt > 0:
                print(f"  [retry] Pass2 source {mod_name} - Attempt {attempt + 1} (tokens: {current_tokens})")

            try:
                prompt = build_pass2_driver_c_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content, soc_slice, bus_slice)
                resp = await invoke_model(model, current_tokens, [{"role": "user", "content": prompt}])
                text = extract_text_from_bedrock_response(resp)

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
        # 1. Load Register Header Context
        reg_filename = mod_data.get("reg_header_file", f"reg_{mod_name.lower()}.h")
        reg_path = output_dir / "include" / reg_filename

        reg_content = "// Register header not found"
        if reg_path.exists():
            reg_content = reg_path.read_text(encoding="utf-8")
            # print(f"[debug] {mod_name}: Loaded register context from {reg_filename} ({len(reg_content)} bytes)")
        else:
            logger.warning(f"Pass 2: Could not find {reg_path} for {mod_name}")
            # print(f"[warn] {mod_name}: REG HEADER MISSING. Driver may hallucinate struct members.")

        # 2. Get Hardware Info (for Base Address)
        soc_periph = find_soc_peripheral(soc_data, mod_name)
        soc_slice = dump_yaml_str(soc_periph) if soc_periph else ""
        
        # 3. Get Bus Info (for Clocks/Baud Rates)
        # We pass the whole bus structure as a string, it's usually small enough. 
        # Or we filters it if it grows too large. For now, dump all.
        bus_slice = dump_yaml_str(bus_data)

        # 4. Launch Parallel Gens
        t_h = asyncio.create_task(_generate_header(mod_name, mod_data, reg_content))
        t_c = asyncio.create_task(_generate_source(mod_name, mod_data, reg_content, soc_slice, bus_slice))
        
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
        print(f".", end="", flush=True)

        # Collect written files and raw responses for validation
        written_files = []
        raw_responses = []

        for type_tag, content, raw_response in results:
            if type_tag == "error":
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
                fpath.write_text(clean_code, encoding="utf-8")
                written_files.append(fpath)
                raw_responses.append(raw_response)
            elif type_tag == "c":
                fname = f"{mod_name.lower()}_driver.c"
                fpath = src_dir / fname
                fpath.write_text(clean_code, encoding="utf-8")
                written_files.append(fpath)
                raw_responses.append(raw_response)

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

    print("\n[pass2] Implementation Complete.")

    if enable_validation and validation_results:
        failed_count = sum(1 for _, vr in validation_results if not vr.is_valid)
        logger.info(f"Pass 2 Validation: {len(validation_results)} modules checked, {failed_count} failed")

    # Return validation results for final report
    return validation_results if enable_validation else []
