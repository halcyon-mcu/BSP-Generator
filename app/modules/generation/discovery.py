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

async def run_discovery_pass(
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    model: Model,
    output_dir: Path,
    max_tokens: int = 20000
) -> Dict[str, Any]:
    """
    Pass 1: Architecture Discovery & Registry Build.
    Splits the work into two parallel calls per module:
      1A. Manifest Generation (JSON)
      1B. Header Generation (C Code)
    """
    
    # 1. Setup Output
    include_dir = output_dir / "include" / "regs"
    include_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "api_catalog": {}
    }
    
    # 2. Prepare Async Tasks
    tasks = []
    peripherals = get_soc_peripherals(soc_data)
    
    logger.info(f"Starting Pass 1 (Discovery) for {len(peripherals)} modules...")

    async def _process_module_manifest(name: str, soc_slice: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON Manifest"""
        try:
            prompt = build_manifest_prompt(name, soc_slice)
            resp = await invoke_model(model, 4096, [{"role": "user", "content": prompt}])
            text = extract_text_from_bedrock_response(resp)
            # Remove MD blocks logic
            clean_text = text.replace("```json", "").replace("```", "").strip()
            # Parse JSON
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(clean_text[start:end+1])
            return None
        except Exception as e:
            logger.error(f"Manifest Error {name}: {e}")
            return None

    async def _process_module_header(name: str, soc_slice: str, regs_slice: str) -> Optional[str]:
        """Fetch C Header Content"""
        try:
            prompt = build_reg_header_prompt(name, soc_slice, regs_slice)
            # Use passed max_tokens for headers as they can be large
            resp = await invoke_model(model, max_tokens, [{"role": "user", "content": prompt}])
            text = extract_text_from_bedrock_response(resp)
            
            # Robust logic for C extraction
            # 1. Try finding markdown block
            start_block = text.find("```c")
            if start_block != -1:
                code_text = text[start_block+4:]
                end_block = code_text.find("```")
                if end_block != -1:
                    return code_text[:end_block].strip()
            
            # 2. Try generic markdown
            start_block = text.find("```")
            if start_block != -1:
                code_text = text[start_block+3:]
                end_block = code_text.find("```")
                if end_block != -1:
                     return code_text[:end_block].strip()
            
            # 3. Fallback: If it looks like a header, return full text
            if "#ifndef" in text or "typedef" in text:
                return text.replace("```c", "").replace("```", "").strip()
                
            return "// [WARN] Could not parse C code from AI response.\n/*\n" + text + "\n*/"
            
        except Exception as e:
            logger.error(f"Header Error {name}: {e}")
            return f"// Error generating header for {name}: {e}"

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
             
        # --- SPECIAL CASE: SYSTEM Aggregation ---
        # If this is the "SYSTEM" module, we want to include "system2" definitions as well 
        # so they appear in the same reg_system.h file.
        if name.upper() == "SYSTEM":
            extra_slice = ""
            if "system2" in all_peripherals:
                extra_slice = dump_yaml_str({"system2": all_peripherals["system2"]})
                # Append to existing slice
                regs_slice = regs_slice + "\n" + extra_slice
                logger.info("Merged 'system2' registers into SYSTEM discovery context.")

        # 3. Last Resort: Try 'generic_type' if user used a different schema
        # (This block strictly logs a warning if we still have no registers)
        if not regs_slice:
            logger.warning(f"Discovery: No register definition found for module '{name}' (type='{p_type}'). Header will likely be empty.")

        # Run both tasks in parallel
        man_task = asyncio.create_task(_process_module_manifest(name, soc_slice))
        head_task = asyncio.create_task(_process_module_header(name, soc_slice, regs_slice))
        
        man_res, head_res = await asyncio.gather(man_task, head_task)
        
        if man_res:
            return {
                "manifest": man_res,
                "reg_header_content": head_res
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
    for res in results:
        if not res:
            continue
            
        # Extract Manifest
        mod_manifest = res.get("manifest", {})
        mod_name = mod_manifest.get("module_name")
        
        if mod_name:
            manifest["api_catalog"][mod_name] = mod_manifest
            success_count += 1
            
            # Write Register Header
            header_content = res.get("reg_header_content")
            header_name = mod_manifest.get("reg_header_file", f"reg_{mod_name.lower()}.h")
            
            if header_content:
                header_path = include_dir / header_name
                header_path.write_text(header_content, encoding="utf-8")
                # logger.info(f"Generated {header_name}")

    # 6. Write Source of Truth
    manifest_path = output_dir / "bsp_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    
    logger.info(f"Pass 1 Complete. Registry built with {success_count} modules.")
    logger.info(f"Manifest: {manifest_path}")
    
    return manifest
