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
    allowed_modules: Optional[List[str]] = None
):
    """
    Pass 2: Driver Implementation.
    
    Iterates through the Manifest created in Pass 1.
    Generates .h and .c files for each module.
    
    :param allowed_modules: If provided, only implement modules with names in this list.
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
        prompt = build_pass2_driver_h_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content)
        try:
            resp = await invoke_model(model, max_tokens, [{"role": "user", "content": prompt}])
            text = extract_text_from_bedrock_response(resp)
            return ("h", text)
        except Exception as e:
            return ("error", f"Header Gen Failed: {e}")

    async def _generate_source(mod_name: str, mod_data: Dict, reg_content: str, soc_slice: str, bus_slice: str):
        prompt = build_pass2_driver_c_prompt(mod_name, json.dumps(mod_data, indent=2), reg_content, soc_slice, bus_slice)
        try:
            resp = await invoke_model(model, max_tokens, [{"role": "user", "content": prompt}])
            text = extract_text_from_bedrock_response(resp)
            return ("c", text)
        except Exception as e:
            return ("error", f"Source Gen Failed: {e}")

    async def _implement_module(mod_name: str, mod_data: Dict):
        # 1. Load Register Header Context
        reg_filename = mod_data.get("reg_header_file", f"reg_{mod_name.lower()}.h")
        reg_path = output_dir / "include" / "regs" / reg_filename
        
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
    for f in asyncio.as_completed(tasks):
        mod_name, results = await f
        print(f".", end="", flush=True)
        
        for type_tag, content in results:
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
                (inc_dir / fname).write_text(clean_code, encoding="utf-8")
            elif type_tag == "c":
                fname = f"{mod_name.lower()}_driver.c"
                (src_dir / fname).write_text(clean_code, encoding="utf-8")

    print("\n[pass2] Implementation Complete.")
