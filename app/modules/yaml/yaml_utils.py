#!/usr/bin/env python3
"""
yaml_utils.py

Helpers for:
- Loading the GA BSP YAML files (SOC, REGS, MEMMAP, BUS, IRQ, PINMUX).
- Extracting specific peripherals or sets of peripherals.
- Building minimal YAML "slices" to pass into LLM prompts
  (e.g. soc/regs fragments for a single peripheral, or system+PCR).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging

import yaml

from .schemas import (
    SocYAML,
    RegsYAML,
    BusYAML,
    IrqYAML,
    PinmuxYAML,
    MemmapYAML,
    BoardYAML,
    validate_yaml_schema
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic loaders
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file into a Python dict."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level mapping in {path}, got {type(data)}")
    return data


def load_soc_yaml(path: Path) -> Dict[str, Any]:
    """Load soc.yaml and perform schema validation."""
    data = _load_yaml(path)

    # Validate with Pydantic schema
    is_valid, errors = validate_yaml_schema(data, SocYAML)
    if not is_valid:
        error_msg = f"soc.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"soc.yaml validation passed: {len(data.get('soc', {}).get('peripherals', []))} peripherals")
    return data


def load_regs_yaml(path: Path) -> Dict[str, Any]:
    """Load regs.yaml and perform schema validation."""
    data = _load_yaml(path)

    # Validate with Pydantic schema
    is_valid, errors = validate_yaml_schema(data, RegsYAML)
    if not is_valid:
        error_msg = f"regs.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"regs.yaml validation passed: {len(data.get('peripherals', {}))} peripheral blocks")
    return data


def load_memmap_yaml(path: Path) -> Dict[str, Any]:
    """Load memmap.yaml matching the array-based schema."""
    data = _load_yaml(path)
    mem = data.get("memory")
    if not isinstance(mem, list) or not mem:
        raise ValueError("memmap.yaml missing non-empty 'memory' array")
    # Basic validation of each region
    for idx, region in enumerate(mem):
        if not isinstance(region, dict):
            raise ValueError(f"memmap.yaml memory[{idx}] is not a mapping")
        for key in ("name", "origin", "length", "attrs"):
            if key not in region:
                raise ValueError(
                    f"memmap.yaml memory[{idx}] missing required field '{key}'"
                )
    return data


def load_bus_yaml(path: Path) -> Dict[str, Any]:
    """Load bus.yaml and perform schema validation."""
    data = _load_yaml(path)

    # Validate with Pydantic schema
    is_valid, errors = validate_yaml_schema(data, BusYAML)
    if not is_valid:
        error_msg = f"bus.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"bus.yaml validation passed: {len(data.get('sources', []))} sources, {len(data.get('domains', []))} domains")
    return data


def load_irq_yaml(path: Path) -> Dict[str, Any]:
    """Load irq.yaml and perform schema validation."""
    data = _load_yaml(path)

    # Validate with Pydantic schema
    is_valid, errors = validate_yaml_schema(data, IrqYAML)
    if not is_valid:
        error_msg = f"irq.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"irq.yaml validation passed: {len(data.get('irqs', []))} interrupts")
    return data


def load_pinmux_yaml(path: Path) -> Dict[str, Any]:
    """Load pinmux.yaml and perform schema validation."""
    data = _load_yaml(path)

    # Validate with Pydantic schema
    is_valid, errors = validate_yaml_schema(data, PinmuxYAML)
    if not is_valid:
        error_msg = f"pinmux.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"pinmux.yaml validation passed: {len(data.get('pins', []))} pins")
    return data


def load_board_yaml(path: Path) -> Dict[str, Any]:
    """Load board.yaml and perform lightweight schema validation."""
    data = _load_yaml(path)

    # Optional schema, allow extra fields for board-specific metadata.
    is_valid, errors = validate_yaml_schema(data, BoardYAML)
    if not is_valid:
        error_msg = f"board.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("board.yaml validation passed")
    return data


def load_generation_profile(path: Path) -> Dict[str, Any]:
    """
    Load optional generation profile YAML with minimal validation.

    Expected shape (all keys optional):
      target_board: str
      modules:
        enabled: [str, ...]
      sci:
        default_baud: int
      pins:
        lock_board_mapping: bool
      clocks:
        mode: "board_default"
      strict_validation: bool
      bsp_validation:
        enabled: bool
      contract_mode: "auto_fix_then_fail" | "hard_fail" | "warn_only"
      require_ccs_proof: bool
    """
    data = _load_yaml(path)

    if "target_board" in data and not isinstance(data["target_board"], str):
        raise ValueError("generation_profile.yaml: 'target_board' must be a string")

    modules = data.get("modules", {})
    if modules and not isinstance(modules, dict):
        raise ValueError("generation_profile.yaml: 'modules' must be a mapping")
    enabled = modules.get("enabled", [])
    if enabled and (not isinstance(enabled, list) or not all(isinstance(m, str) for m in enabled)):
        raise ValueError("generation_profile.yaml: 'modules.enabled' must be a list of strings")

    sci = data.get("sci", {})
    if sci and not isinstance(sci, dict):
        raise ValueError("generation_profile.yaml: 'sci' must be a mapping")
    if "default_baud" in sci and not isinstance(sci["default_baud"], int):
        raise ValueError("generation_profile.yaml: 'sci.default_baud' must be an integer")

    pins = data.get("pins", {})
    if pins and not isinstance(pins, dict):
        raise ValueError("generation_profile.yaml: 'pins' must be a mapping")
    if "lock_board_mapping" in pins and not isinstance(pins["lock_board_mapping"], bool):
        raise ValueError("generation_profile.yaml: 'pins.lock_board_mapping' must be boolean")

    clocks = data.get("clocks", {})
    if clocks and not isinstance(clocks, dict):
        raise ValueError("generation_profile.yaml: 'clocks' must be a mapping")
    if "mode" in clocks and clocks["mode"] not in ("board_default",):
        raise ValueError("generation_profile.yaml: 'clocks.mode' must be 'board_default'")

    if "strict_validation" in data and not isinstance(data["strict_validation"], bool):
        raise ValueError("generation_profile.yaml: 'strict_validation' must be boolean")

    bsp_validation = data.get("bsp_validation", {})
    if bsp_validation and not isinstance(bsp_validation, dict):
        raise ValueError("generation_profile.yaml: 'bsp_validation' must be a mapping")
    if "enabled" in bsp_validation and not isinstance(bsp_validation["enabled"], bool):
        raise ValueError("generation_profile.yaml: 'bsp_validation.enabled' must be boolean")

    if "contract_mode" in data:
        valid_modes = {"auto_fix_then_fail", "hard_fail", "warn_only"}
        if data["contract_mode"] not in valid_modes:
            raise ValueError(
                "generation_profile.yaml: 'contract_mode' must be one of "
                "'auto_fix_then_fail', 'hard_fail', 'warn_only'"
            )

    if "require_ccs_proof" in data and not isinstance(data["require_ccs_proof"], bool):
        raise ValueError("generation_profile.yaml: 'require_ccs_proof' must be boolean")

    return data


# ---------------------------------------------------------------------------
# SOC helpers
# ---------------------------------------------------------------------------

def get_soc_peripherals(soc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the list of peripherals from soc.yaml."""
    return list(soc_data.get("soc", {}).get("peripherals", []))


def find_soc_peripheral(
    soc_data: Dict[str, Any],
    name: str,
    case_insensitive: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Find a single peripheral by its 'name' field in soc.yaml.

    If case_insensitive is True, matching is done on uppercased names.
    """
    name_key = name.upper() if case_insensitive else name
    for p in get_soc_peripherals(soc_data):
        p_name = p.get("name", "")
        if case_insensitive:
            if str(p_name).upper() == name_key:
                return p
        else:
            if p_name == name_key:
                return p
    return None


def list_peripheral_names(
    soc_data: Dict[str, Any],
    exclude: Optional[List[str]] = None,
) -> List[str]:
    """
    List peripheral names from soc.yaml, optionally excluding some
    (e.g. ["SYSTEM", "PCR"]).
    """
    exclude_set = {e.upper() for e in (exclude or [])}
    names: List[str] = []
    for p in get_soc_peripherals(soc_data):
        name = str(p.get("name", ""))
        if name and name.upper() not in exclude_set:
            names.append(name)
    return names


def make_soc_slice_for_peripherals(
    soc_data: Dict[str, Any],
    periph_names: List[str],
) -> Dict[str, Any]:
    """
    Build a minimal soc.yaml-like dict containing only the given
    peripherals (by name) plus cpu/metadata.

    This is what you pass to LLMs for system / peripheral calls.

    Shape:
      {
        "ir_schema_version": "...",
        "chip": "...",
        "vendor": "...",
        "family": "...",
        "revision": "...",
        "soc": {
          "cpu": { ... },
          "peripherals": [ <matching peripherals> ]
        }
      }
    """
    top_keys = ["ir_schema_version", "chip", "vendor", "family", "revision"]
    out: Dict[str, Any] = {}

    for k in top_keys:
        if k in soc_data:
            out[k] = soc_data[k]

    soc_out: Dict[str, Any] = {}
    cpu = soc_data.get("soc", {}).get("cpu")
    if cpu is not None:
        soc_out["cpu"] = cpu

    periphs_all = get_soc_peripherals(soc_data)
    name_set = {n.upper() for n in periph_names}
    periphs_selected: List[Dict[str, Any]] = []
    for p in periphs_all:
        p_name = str(p.get("name", ""))
        if p_name.upper() in name_set:
            periphs_selected.append(p)

    soc_out["peripherals"] = periphs_selected
    out["soc"] = soc_out
    return out


# ---------------------------------------------------------------------------
# REGS helpers
# ---------------------------------------------------------------------------

def get_regs_block(
    regs_data: Dict[str, Any],
    regs_ref: str,
) -> Optional[Dict[str, Any]]:
    """Return the register block (peripherals.<regs_ref>) from regs.yaml."""
    periphs = regs_data.get("peripherals", {})
    block = periphs.get(regs_ref)
    if block is None:
        return None
    return block


def make_regs_slice_for_refs(
    regs_data: Dict[str, Any],
    refs: List[str],
) -> Dict[str, Any]:
    
    """
    Build a minimal regs.yaml-like dict containing only the requested
    register blocks.

      {
        "ir_schema_version": "...",
        "peripherals": {
          "REF1": { ... },
          "REF2": { ... }
        }
      }

    """

    out: Dict[str, Any] = {}
    if "ir_schema_version" in regs_data:
        out["ir_schema_version"] = regs_data["ir_schema_version"]

    periphs_in = regs_data.get("peripherals", {})
    periphs_out: Dict[str, Any] = {}
    for r in refs:
        block = periphs_in.get(r)
        if block is not None:
            periphs_out[r] = block
    out["peripherals"] = periphs_out
    return out


# ---------------------------------------------------------------------------
# MEMMAP helpers (for linker script generation)
# ---------------------------------------------------------------------------

def find_flash_and_ram_regions(
    memmap_data: Dict[str, Any],
    flash_name_hint: str = "FLASH",
    ram_name_hint: str = "RAM",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Find FLASH and RAM regions in memmap.yaml.

    Schema:
      memory: [ { name, origin, length, attrs, ... }, ... ]

    Strategy:
      1) Prefer regions whose 'name' matches flash_name_hint / ram_name_hint.
      2) Otherwise, fall back to heuristic:
         - FLASH = first region with "FLASH" in name (case-insensitive)
         - RAM   = first region with "RAM" or "SRAM" in name (case-insensitive)

    Returns:
      (flash_region_dict, ram_region_dict)  -- shallow copies
    Raises:
      ValueError if not found.
    """
    regions = memmap_data.get("memory", [])
    if not isinstance(regions, list):
        raise ValueError("memmap.yaml 'memory' must be a list")

    flash_region: Optional[Dict[str, Any]] = None
    ram_region: Optional[Dict[str, Any]] = None

    # 1) Try by exact name hints
    for region in regions:
        name = str(region.get("name", ""))
        if not name:
            continue
        if flash_region is None and name == flash_name_hint:
            flash_region = region
        if ram_region is None and name == ram_name_hint:
            ram_region = region
        if flash_region is not None and ram_region is not None:
            break

    # 2) Fallback heuristics by name content
    if flash_region is None:
        for region in regions:
            name = str(region.get("name", "")).upper()
            if "FLASH" in name:
                flash_region = region
                break

    if ram_region is None:
        for region in regions:
            name = str(region.get("name", "")).upper()
            if "RAM" in name or "SRAM" in name:
                ram_region = region
                break

    if flash_region is None or ram_region is None:
        raise ValueError("Could not identify FLASH and/or RAM regions in memmap.yaml")

    # Return shallow copies so callers can modify if needed without
    # mutating the original memmap_data
    return dict(flash_region), dict(ram_region)


def make_memmap_slice_for_linker(
    memmap_data: Dict[str, Any],
    flash_name_hint: str = "FLASH",
    ram_name_hint: str = "RAM",
) -> Dict[str, Any]:
    """
    Build a minimal memmap.yaml-like dict containing only FLASH and RAM
    regions, suitable to pass to the linker-script LLM prompt.

    Output shape (still conforms to your schema):

      {
        "ir_schema_version": "...",
        "memory": [
          { name: "<FLASH_NAME>", origin: "...", length: "...", attrs: "..." },
          { name: "<RAM_NAME>",   origin: "...", length: "...", attrs: "..." }
        ],
        "link": { ... }      # OPTIONAL: copied from original if present
        "startup": { ... }   # OPTIONAL: copied from original if present
      }
    """
    out: Dict[str, Any] = {}
    if "ir_schema_version" in memmap_data:
        out["ir_schema_version"] = memmap_data["ir_schema_version"]

    flash_reg, ram_reg = find_flash_and_ram_regions(
        memmap_data,
        flash_name_hint=flash_name_hint,
        ram_name_hint=ram_name_hint,
    )

    # Keep just FLASH & RAM regions in a small memory array
    out["memory"] = [flash_reg, ram_reg]

    # Optionally propagate link/startup metadata if the linker prompt wants it
    if "link" in memmap_data:
        out["link"] = memmap_data["link"]
    if "startup" in memmap_data:
        out["startup"] = memmap_data["startup"]

    return out


def build_memmap_slice_for_prompt(
    memmap_data: Dict[str, Any],
) -> str:
    """
    Build YAML slice for linker-script call:
      - only FLASH and RAM regions, plus optional link/startup.

    Returns:
      memmap_yaml_str
    """
    mem_slice = make_memmap_slice_for_linker(memmap_data)
    return dump_yaml_str(mem_slice)


# ---------------------------------------------------------------------------
# YAML -> string helper for prompts
# ---------------------------------------------------------------------------

def dump_yaml_str(data: Dict[str, Any]) -> str:
    """
    Dump a YAML dict to a compact string for embedding in prompts.
    Uses safe_dump with a stable, human-readable style.
    """
    return yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
    )


# ---------------------------------------------------------------------------
# Convenience helpers for specific Claude calls
# ---------------------------------------------------------------------------

def build_system_slices_for_prompt(
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
) -> Tuple[str, str]:
    """
    Build YAML slices for a system-init call:
      - soc slice with SYSTEM and PCR peripherals
      - regs slice with SYSTEM and PCR register blocks

    Returns:
      (soc_yaml_str, regs_yaml_str)
    """
    # Names in soc.yaml
    periph_names = ["SYSTEM", "PCR"]
    soc_slice = make_soc_slice_for_peripherals(soc_data, periph_names)

    # refs in regs.yaml match regs_ref (SYSTEM, PCR)
    regs_refs = ["SYSTEM", "PCR"]
    regs_slice = make_regs_slice_for_refs(regs_data, regs_refs)

    return dump_yaml_str(soc_slice), dump_yaml_str(regs_slice)


def build_peripheral_slices_for_prompt(
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    irq_data: Dict[str, Any],
    peripheral_name: str,
) -> Tuple[str, str]:
    """
    Build YAML slices for a single peripheral driver call:
      - soc slice with only that peripheral
      - regs slice with its regs_ref block

    Returns:
      (soc_yaml_str, regs_yaml_str)
    """
    p = find_soc_peripheral(soc_data, peripheral_name)
    if p is None:
        raise ValueError(f"Peripheral '{peripheral_name}' not found in soc.yaml")

    # soc slice: just this peripheral (plus cpu/metadata)
    soc_slice = make_soc_slice_for_peripherals(soc_data, [peripheral_name])

    # regs slice: use the regs_ref from soc.yaml
    regs_ref = str(p.get("regs_ref", ""))
    if not regs_ref:
        raise ValueError(
            f"Peripheral '{peripheral_name}' in soc.yaml missing 'regs_ref'"
        )
    regs_slice = make_regs_slice_for_refs(regs_data, [regs_ref])

    # Search for additional regs_ref in x-ext (e.g., for VIM parity, GPIO expander peripherals)
    x_ext = p.get("x-ext", {})
    if isinstance(x_ext, dict):
        # Recursively search through x-ext dictionary values for regs_ref fields
        def find_regs_refs(obj, found_refs):
            """Recursively find all regs_ref values in nested dict/list structures."""
            if isinstance(obj, dict):
                if "regs_ref" in obj:
                    ref = str(obj["regs_ref"])
                    if ref and ref != regs_ref:
                        found_refs.add(ref)
                for value in obj.values():
                    find_regs_refs(value, found_refs)
            elif isinstance(obj, list):
                for item in obj:
                    find_regs_refs(item, found_refs)
        
        additional_refs = set()
        find_regs_refs(x_ext, additional_refs)
        
        # Add all found regs blocks to the regs slice
        for ext_regs_ref in additional_refs:
            extra_regs_slice = make_regs_slice_for_refs(regs_data, [ext_regs_ref])
            if "peripherals" not in regs_slice:
                regs_slice["peripherals"] = {}
            regs_slice["peripherals"].update(extra_regs_slice.get("peripherals", {}))

    irq_slice = ""

    irq_refs = p.get("irq_ref", [])
    if irq_refs and isinstance(irq_refs, list):
        irq_slice = make_irq_slices_for_refs(irq_data, irq_refs)

    return dump_yaml_str(soc_slice), dump_yaml_str(regs_slice), dump_yaml_str(irq_slice)


def make_irq_slices_for_refs(irq_yaml, refs: List[str]) -> Dict[str, Any]:
    """
    Build a minimal irq.yaml-like dict containing only the requested
    IRQ blocks.

    irq.yaml has irqs as a list where each item has a 'name' field.
    We filter to only include IRQs whose 'name' matches one of the refs.

      {
        "ir_schema_version": "...",
        "interrupt_controller": { ... },
        "irqs": [
          { "name": "REF1", ... },
          { "name": "REF2", ... }
        ]
      }
    """
    out: Dict[str, Any] = {}
    if "ir_schema_version" in irq_yaml:
        out["ir_schema_version"] = irq_yaml["ir_schema_version"]
    
    if "interrupt_controller" in irq_yaml:
        out["interrupt_controller"] = irq_yaml["interrupt_controller"]

    irqs_in = irq_yaml.get("irqs", [])
    refs_set = {r.upper() for r in refs}
    irqs_out: List[Dict[str, Any]] = []
    
    if isinstance(irqs_in, list):
        for irq_entry in irqs_in:
            if isinstance(irq_entry, dict):
                name = str(irq_entry.get("name", "")).upper()
                if name in refs_set:
                    irqs_out.append(irq_entry)
    
    out["irqs"] = irqs_out
    return out
