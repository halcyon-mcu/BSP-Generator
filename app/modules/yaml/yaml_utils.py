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
    BringupContractYAML,
    GenerationProfileYAML,
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
    """Load board.yaml and enforce required board-capability schema fields."""
    data = _load_yaml(path)

    # Strict schema for capability-header completeness (extra keys still allowed).
    is_valid, errors = validate_yaml_schema(data, BoardYAML)
    if not is_valid:
        error_msg = f"board.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("board.yaml validation passed")
    return data


def load_bringup_contract(path: Path) -> Dict[str, Any]:
    """Load optional bringup_contract.yaml and validate if present."""
    data = _load_yaml(path)

    is_valid, errors = validate_yaml_schema(data, BringupContractYAML)
    if not is_valid:
        error_msg = f"bringup_contract.yaml validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug("bringup_contract.yaml validation passed")
    return data


def load_generation_profile(path: Path) -> Dict[str, Any]:
    """
    Load optional generation profile YAML with minimal validation.

    Expected shape (all keys optional):
      target_board: str
      modules.enabled: [str, ...]
      sci.default_baud: int
      pins.lock_board_mapping: bool
      clocks.mode: "board_default"
      strict_validation: bool
      contract_mode: "auto_fix_then_fail" | "hard_fail" | "warn_only"
      require_ccs_proof: bool
      bringup.{mode,contract_file,fail_on_contract_mismatch,emit_debug_probes}
    bringup_mode.default: direct_init|validation
    startup_contract.gate_mode: warn|fail
    parity_guard.{mode,baseline_path,critical_registers}
      app_intent.{enabled,critical_file_freeze,allow_llm_on_critical,task_library_path,intent_refs_mode,generate_firmware_pass,post_gen_max_tokens}
      build_gate.{enabled,mode,external_workspace_path,project_name,configuration,max_fix_rounds,allow_targeted_llm_rewrite,fail_on_compile_error,clean_build,llm_rewrite.*}
      bsp_validation.{enabled,baud,primary_serial_path,frame,banners,timing}
    """
    data = _load_yaml(path)

    is_valid, errors = validate_yaml_schema(data, GenerationProfileYAML)
    if not is_valid:
        raise ValueError(
            "generation_profile.yaml schema validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

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
    if "baud" in bsp_validation and not isinstance(bsp_validation["baud"], int):
        raise ValueError("generation_profile.yaml: 'bsp_validation.baud' must be integer")
    if "primary_serial_path" in bsp_validation and bsp_validation["primary_serial_path"] not in ("lin_only", "sci_only", "dual"):
        raise ValueError(
            "generation_profile.yaml: 'bsp_validation.primary_serial_path' must be "
            "'lin_only', 'sci_only', or 'dual'"
        )

    frame = bsp_validation.get("frame", {})
    if frame and not isinstance(frame, dict):
        raise ValueError("generation_profile.yaml: 'bsp_validation.frame' must be a mapping")
    if "data_bits" in frame and not isinstance(frame["data_bits"], int):
        raise ValueError("generation_profile.yaml: 'bsp_validation.frame.data_bits' must be integer")
    if "stop_bits" in frame and not isinstance(frame["stop_bits"], int):
        raise ValueError("generation_profile.yaml: 'bsp_validation.frame.stop_bits' must be integer")
    if "parity" in frame and frame["parity"] not in ("none", "even", "odd"):
        raise ValueError("generation_profile.yaml: 'bsp_validation.frame.parity' must be one of 'none', 'even', 'odd'")

    banners = bsp_validation.get("banners", {})
    if banners and not isinstance(banners, dict):
        raise ValueError("generation_profile.yaml: 'bsp_validation.banners' must be a mapping")
    if "sci" in banners and not isinstance(banners["sci"], str):
        raise ValueError("generation_profile.yaml: 'bsp_validation.banners.sci' must be a string")
    if "lin" in banners and not isinstance(banners["lin"], str):
        raise ValueError("generation_profile.yaml: 'bsp_validation.banners.lin' must be a string")

    timing = bsp_validation.get("timing", {})
    if timing and not isinstance(timing, dict):
        raise ValueError("generation_profile.yaml: 'bsp_validation.timing' must be a mapping")
    for key in ("heartbeat_ticks", "tx_period_ticks", "busy_delay"):
        if key in timing and not isinstance(timing[key], int):
            raise ValueError(f"generation_profile.yaml: 'bsp_validation.timing.{key}' must be integer")

    bringup_mode = data.get("bringup_mode", {})
    if bringup_mode and not isinstance(bringup_mode, dict):
        raise ValueError("generation_profile.yaml: 'bringup_mode' must be a mapping")
    if "default" in bringup_mode and bringup_mode["default"] not in ("direct_init", "validation"):
        raise ValueError("generation_profile.yaml: 'bringup_mode.default' must be 'direct_init' or 'validation'")

    startup_contract = data.get("startup_contract", {})
    if startup_contract and not isinstance(startup_contract, dict):
        raise ValueError("generation_profile.yaml: 'startup_contract' must be a mapping")
    if "gate_mode" in startup_contract and startup_contract["gate_mode"] not in ("warn", "fail"):
        raise ValueError("generation_profile.yaml: 'startup_contract.gate_mode' must be 'warn' or 'fail'")

    parity_guard = data.get("parity_guard", {})
    if parity_guard and not isinstance(parity_guard, dict):
        raise ValueError("generation_profile.yaml: 'parity_guard' must be a mapping")
    if "mode" in parity_guard and parity_guard["mode"] not in ("critical_only", "strict", "off"):
        raise ValueError("generation_profile.yaml: 'parity_guard.mode' must be 'critical_only', 'strict', or 'off'")
    if "baseline_path" in parity_guard and not isinstance(parity_guard["baseline_path"], str):
        raise ValueError("generation_profile.yaml: 'parity_guard.baseline_path' must be a string")
    if "critical_registers" in parity_guard:
        regs = parity_guard["critical_registers"]
        if not isinstance(regs, list) or not all(isinstance(x, str) for x in regs):
            raise ValueError("generation_profile.yaml: 'parity_guard.critical_registers' must be a list of strings")

    app_intent = data.get("app_intent", {})
    if app_intent and not isinstance(app_intent, dict):
        raise ValueError("generation_profile.yaml: 'app_intent' must be a mapping")
    if "enabled" in app_intent and not isinstance(app_intent["enabled"], bool):
        raise ValueError("generation_profile.yaml: 'app_intent.enabled' must be boolean")
    if "critical_file_freeze" in app_intent and not isinstance(app_intent["critical_file_freeze"], bool):
        raise ValueError("generation_profile.yaml: 'app_intent.critical_file_freeze' must be boolean")
    if "allow_llm_on_critical" in app_intent and not isinstance(app_intent["allow_llm_on_critical"], bool):
        raise ValueError("generation_profile.yaml: 'app_intent.allow_llm_on_critical' must be boolean")
    if "task_library_path" in app_intent and not isinstance(app_intent["task_library_path"], str):
        raise ValueError("generation_profile.yaml: 'app_intent.task_library_path' must be a string")
    if "intent_refs_mode" in app_intent and app_intent["intent_refs_mode"] not in ("proven_only", "include_unverified"):
        raise ValueError(
            "generation_profile.yaml: 'app_intent.intent_refs_mode' must be "
            "'proven_only' or 'include_unverified'"
        )
    if "generate_firmware_pass" in app_intent and not isinstance(app_intent["generate_firmware_pass"], bool):
        raise ValueError("generation_profile.yaml: 'app_intent.generate_firmware_pass' must be boolean")
    if "post_gen_max_tokens" in app_intent and (
        not isinstance(app_intent["post_gen_max_tokens"], int)
        or app_intent["post_gen_max_tokens"] < 1024
    ):
        raise ValueError("generation_profile.yaml: 'app_intent.post_gen_max_tokens' must be an integer >= 1024")

    if "contract_mode" in data:
        valid_modes = {"auto_fix_then_fail", "hard_fail", "warn_only"}
        if data["contract_mode"] not in valid_modes:
            raise ValueError(
                "generation_profile.yaml: 'contract_mode' must be one of "
                "'auto_fix_then_fail', 'hard_fail', 'warn_only'"
            )

    if "require_ccs_proof" in data and not isinstance(data["require_ccs_proof"], bool):
        raise ValueError("generation_profile.yaml: 'require_ccs_proof' must be boolean")

    bringup = data.get("bringup", {})
    if bringup and not isinstance(bringup, dict):
        raise ValueError("generation_profile.yaml: 'bringup' must be a mapping")
    if "mode" in bringup and bringup["mode"] not in ("strict", "relaxed"):
        raise ValueError("generation_profile.yaml: 'bringup.mode' must be 'strict' or 'relaxed'")
    if "contract_file" in bringup and not isinstance(bringup["contract_file"], str):
        raise ValueError("generation_profile.yaml: 'bringup.contract_file' must be a string")
    if "fail_on_contract_mismatch" in bringup and not isinstance(bringup["fail_on_contract_mismatch"], bool):
        raise ValueError("generation_profile.yaml: 'bringup.fail_on_contract_mismatch' must be boolean")
    if "emit_debug_probes" in bringup and not isinstance(bringup["emit_debug_probes"], bool):
        raise ValueError("generation_profile.yaml: 'bringup.emit_debug_probes' must be boolean")

    build_gate = data.get("build_gate", {})
    if build_gate and not isinstance(build_gate, dict):
        raise ValueError("generation_profile.yaml: 'build_gate' must be a mapping")
    if "enabled" in build_gate and not isinstance(build_gate["enabled"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.enabled' must be boolean")
    if "mode" in build_gate and build_gate["mode"] not in ("strict", "advisory", "off"):
        raise ValueError("generation_profile.yaml: 'build_gate.mode' must be 'strict', 'advisory', or 'off'")
    if "external_workspace_path" in build_gate and not isinstance(build_gate["external_workspace_path"], str):
        raise ValueError("generation_profile.yaml: 'build_gate.external_workspace_path' must be a string")
    if "project_name" in build_gate and not isinstance(build_gate["project_name"], str):
        raise ValueError("generation_profile.yaml: 'build_gate.project_name' must be a string")
    if "configuration" in build_gate and build_gate["configuration"] not in ("Debug", "Release"):
        raise ValueError("generation_profile.yaml: 'build_gate.configuration' must be 'Debug' or 'Release'")
    if "max_fix_rounds" in build_gate and (
        not isinstance(build_gate["max_fix_rounds"], int) or build_gate["max_fix_rounds"] < 0
    ):
        raise ValueError("generation_profile.yaml: 'build_gate.max_fix_rounds' must be a non-negative integer")
    if "allow_targeted_llm_rewrite" in build_gate and not isinstance(build_gate["allow_targeted_llm_rewrite"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.allow_targeted_llm_rewrite' must be boolean")
    if "fail_on_compile_error" in build_gate and not isinstance(build_gate["fail_on_compile_error"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.fail_on_compile_error' must be boolean")
    if "clean_stale_project_files" in build_gate and not isinstance(build_gate["clean_stale_project_files"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.clean_stale_project_files' must be boolean")
    if "clean_build" in build_gate and not isinstance(build_gate["clean_build"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.clean_build' must be boolean")
    llm_rewrite = build_gate.get("llm_rewrite", {})
    if llm_rewrite and not isinstance(llm_rewrite, dict):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite' must be a mapping")
    if "enabled" in llm_rewrite and not isinstance(llm_rewrite["enabled"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite.enabled' must be boolean")
    if "scope" in llm_rewrite and llm_rewrite["scope"] not in ("top_files",):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite.scope' must be 'top_files'")
    if "top_k_files" in llm_rewrite and (
        not isinstance(llm_rewrite["top_k_files"], int) or llm_rewrite["top_k_files"] < 1
    ):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite.top_k_files' must be a positive integer")
    if "apply_policy" in llm_rewrite and llm_rewrite["apply_policy"] not in ("hybrid", "diff_only", "full_file_only"):
        raise ValueError(
            "generation_profile.yaml: 'build_gate.llm_rewrite.apply_policy' must be "
            "'hybrid', 'diff_only', or 'full_file_only'"
        )
    if "model" in llm_rewrite and llm_rewrite["model"] not in ("inherit", "haiku4.5", "sonnet4.5", "opus4.5", "opus4.6"):
        raise ValueError(
            "generation_profile.yaml: 'build_gate.llm_rewrite.model' must be "
            "'inherit', 'haiku4.5', 'sonnet4.5', 'opus4.5', or 'opus4.6'"
        )
    if "max_tokens" in llm_rewrite and (
        not isinstance(llm_rewrite["max_tokens"], int) or llm_rewrite["max_tokens"] < 256
    ):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite.max_tokens' must be an integer >= 256")
    if "max_attempts" in llm_rewrite and (
        not isinstance(llm_rewrite["max_attempts"], int) or llm_rewrite["max_attempts"] < 0
    ):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite.max_attempts' must be a non-negative integer")
    if "include_contract_context" in llm_rewrite and not isinstance(llm_rewrite["include_contract_context"], bool):
        raise ValueError("generation_profile.yaml: 'build_gate.llm_rewrite.include_contract_context' must be boolean")

    # Backward-compat: legacy boolean toggle maps to llm_rewrite.enabled.
    if isinstance(build_gate, dict) and "llm_rewrite" not in build_gate and "allow_targeted_llm_rewrite" in build_gate:
        build_gate["llm_rewrite"] = {
            "enabled": bool(build_gate.get("allow_targeted_llm_rewrite", True))
        }

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
