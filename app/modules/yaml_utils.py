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

import yaml


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
    """Load soc.yaml and perform basic schema sanity checks."""
    data = _load_yaml(path)
    if "soc" not in data or not isinstance(data["soc"], dict):
        raise ValueError("soc.yaml missing top-level 'soc' key")
    if "peripherals" not in data["soc"] or not isinstance(data["soc"]["peripherals"], list):
        raise ValueError("soc.yaml missing 'soc.peripherals' array")
    return data


def load_regs_yaml(path: Path) -> Dict[str, Any]:
    """Load regs.yaml."""
    data = _load_yaml(path)
    if "peripherals" not in data or not isinstance(data["peripherals"], dict):
        raise ValueError("regs.yaml missing top-level 'peripherals' mapping")
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
    """Load bus.yaml (light validation)."""
    return _load_yaml(path)


def load_irq_yaml(path: Path) -> Dict[str, Any]:
    """Load irq.yaml (light validation)."""
    return _load_yaml(path)


def load_pinmux_yaml(path: Path) -> Dict[str, Any]:
    """Load pinmux.yaml (light validation)."""
    return _load_yaml(path)


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

    return dump_yaml_str(soc_slice), dump_yaml_str(regs_slice)

