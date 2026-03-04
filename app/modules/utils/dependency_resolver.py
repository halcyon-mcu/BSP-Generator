#!/usr/bin/env python3
"""
dependency_resolver.py

Dependency graph construction and topological sorting for BSP initialization order.

This module provides:
- Dependency graph construction from manifest and YAML
- Topological sort with cycle detection (Kahn's algorithm)
- Automatic generation of main.c with correct init order
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from .file_io import normalize_generated_text

logger = logging.getLogger(__name__)

# Core system modules that must always be initialized directly (not commented out)
# These are essential infrastructure modules that peripheral drivers depend on
CORE_SYSTEM_MODULES = {'SYSTEM', 'PLL', 'IOMM', 'VIM', 'PCR'}


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class DependencyNode:
    """
    A node in the dependency graph.
    """
    name: str
    dependencies: List[str] = field(default_factory=list)
    init_function: str = ""
    module_type: str = ""  # "peripheral", "system", "pll", "vim"

    def __str__(self) -> str:
        deps_str = ", ".join(self.dependencies) if self.dependencies else "none"
        return f"{self.name} (deps: {deps_str})"


@dataclass
class DependencyGraph:
    """
    Complete dependency graph for all BSP modules.
    """
    nodes: Dict[str, DependencyNode] = field(default_factory=dict)

    def add_node(self, node: DependencyNode) -> None:
        """Add or update a node in the graph."""
        self.nodes[node.name] = node

    def get_node(self, name: str) -> Optional[DependencyNode]:
        """Get a node by name."""
        return self.nodes.get(name)

    def get_all_dependencies(self, name: str) -> Set[str]:
        """Get all direct dependencies for a node."""
        node = self.get_node(name)
        if not node:
            return set()
        return set(node.dependencies)

    def __str__(self) -> str:
        lines = ["Dependency Graph:"]
        for name, node in sorted(self.nodes.items()):
            lines.append(f"  {node}")
        return "\n".join(lines)


@dataclass
class InitOrder:
    """
    Resolved initialization order with metadata.
    """
    order: List[str] = field(default_factory=list)
    has_cycles: bool = False
    cycle_nodes: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """True if order is valid (no cycles)."""
        return not self.has_cycles

    def __str__(self) -> str:
        if self.has_cycles:
            cycle_str = " → ".join(self.cycle_nodes + [self.cycle_nodes[0]])
            return f"InitOrder: INVALID - Circular dependency: {cycle_str}"
        return f"InitOrder: {' → '.join(self.order)}"


# ==============================================================================
# DEPENDENCY GRAPH CONSTRUCTION
# ==============================================================================

def build_dependency_graph(
    manifest: Dict[str, Any],
    soc_data: Dict[str, Any],
    selected_modules: Optional[List[str]] = None
) -> DependencyGraph:
    """
    Build dependency graph from manifest and SOC data.

    Args:
        manifest: Parsed bsp_manifest.json from Pass 1
        soc_data: Parsed soc.yaml
        selected_modules: Optional list of modules to include (from Pass 2 selection)

    Returns:
        DependencyGraph with all nodes and edges
    """
    graph = DependencyGraph()

    # Extract API catalog from manifest
    api_catalog = manifest.get("api_catalog", {})

    # Always include system-level modules
    system_modules = {"SYSTEM", "PLL", "VIM"}

    # Build set of modules to include
    if selected_modules:
        include_modules = system_modules | {m.upper() for m in selected_modules}
    else:
        # Include all modules from manifest
        include_modules = system_modules | {name.upper() for name in api_catalog.keys()}

    # Add system-level nodes first
    _add_system_nodes(graph)

    # Add peripheral nodes from manifest
    for module_name, module_manifest in api_catalog.items():
        module_upper = module_name.upper()

        if module_upper not in include_modules:
            continue

        # Skip system modules (already added)
        if module_upper in system_modules:
            continue

        # Extract dependencies
        dependencies = module_manifest.get("dependencies", [])

        # Normalize dependencies
        norm_deps = [_normalize_dependency(dep) for dep in dependencies]

        # Add clock dependencies from SOC data
        clock_deps = _extract_clock_dependencies(soc_data, module_name)
        norm_deps.extend(clock_deps)

        # Add interrupt dependencies from SOC data
        irq_deps = _extract_irq_dependencies(soc_data, module_name)
        norm_deps.extend(irq_deps)

        # Add IOMM dependencies for I/O peripherals
        iomm_deps = _extract_iomm_dependencies(soc_data, module_name)
        norm_deps.extend(iomm_deps)

        # Remove duplicates
        norm_deps = list(set(norm_deps))

        # Create node
        init_func = module_manifest.get("init_function", f"{module_upper}_Init")
        node = DependencyNode(
            name=module_upper,
            dependencies=norm_deps,
            init_function=init_func,
            module_type="peripheral"
        )
        graph.add_node(node)

    logger.info(f"Built dependency graph with {len(graph.nodes)} nodes")
    return graph


def _add_system_nodes(graph: DependencyGraph) -> None:
    """
    Add predefined system-level nodes with known dependencies.

    Initialization order:
    1. SYSTEM (base)
    2. PCR (power control for I/O)
    3. IOMM (pin multiplexing - pins configured)
    4. PLL (clocks)
    5. VIM (interrupts)
    """
    # SYSTEM has no dependencies (base of dependency tree)
    system_node = DependencyNode(
        name="SYSTEM",
        dependencies=[],
        init_function="system_init",
        module_type="system"
    )
    graph.add_node(system_node)

    # PCR depends on SYSTEM (power control for peripherals)
    pcr_node = DependencyNode(
        name="PCR",
        dependencies=["SYSTEM"],
        init_function="PCR_Init",
        module_type="pcr"
    )
    graph.add_node(pcr_node)

    # IOMM depends on PCR (I/O power domain must be active)
    iomm_node = DependencyNode(
        name="IOMM",
        dependencies=["PCR"],
        init_function="IOMM_Init",
        module_type="pinmux"
    )
    graph.add_node(iomm_node)

    # PLL depends on SYSTEM (PLL provides clock services)
    pll_node = DependencyNode(
        name="PLL",
        dependencies=["SYSTEM"],
        init_function="PLL_Init",
        module_type="pll"
    )
    graph.add_node(pll_node)

    # VIM depends on SYSTEM
    vim_node = DependencyNode(
        name="VIM",
        dependencies=["SYSTEM"],
        init_function="vim_init",
        module_type="vim"
    )
    graph.add_node(vim_node)


def _normalize_dependency(dep: str) -> str:
    """
    Normalize a dependency name to uppercase.

    Handles various formats:
    - "PCR" -> "SYSTEM" (PCR is part of SYSTEM)
    - "PLL.CLOCKDOMAIN_VCLK" -> "PLL"
    - "VIM" -> "VIM"
    """
    dep = dep.strip().upper()

    # PCR is part of SYSTEM
    if dep == "PCR":
        return "SYSTEM"

    # Clock references resolve to PLL module (PLL provides clock APIs)
    if "CLOCK" in dep and "." in dep:
        return "PLL"

    return dep


def _extract_clock_dependencies(soc_data: Dict[str, Any], module_name: str) -> List[str]:
    """
    Extract clock dependencies for a module from soc.yaml.

    Returns list of dependencies (e.g., ["PLL"]).
    PLL module provides clock services (PLL_EnableClock, PLL_GetFrequency).
    """
    peripherals = soc_data.get("peripherals", [])

    for periph in peripherals:
        if periph.get("name", "").upper() == module_name.upper():
            # Check for clock_ref
            if periph.get("clock_ref"):
                return ["PLL"]

            # Check for multiple clock_refs in x-ext
            x_ext = periph.get("x-ext", {})
            if x_ext.get("clock_refs"):
                return ["PLL"]

    return []


def _extract_iomm_dependencies(soc_data: Dict[str, Any], module_name: str) -> List[str]:
    """
    Extract IOMM dependencies for I/O-using peripherals.

    Returns ["IOMM"] if module uses external pins.

    Peripheral types that use external pins and require pin multiplexing:
    - SCI, LIN: UART/LIN communication pins
    - GIO: GPIO pins
    - SPI, I2C: Serial communication pins
    - CAN: CAN bus pins
    - PWM, EPWM, ECAP, EQEP: PWM/capture pins
    - N2HET: High-end timer event pins
    - FlexRay: FlexRay communication pins
    """
    peripherals = soc_data.get("soc", {}).get("peripherals", [])

    # Peripheral types that use external pins
    io_peripheral_types = {
        "sci", "lin", "gio", "spi", "i2c", "can",
        "pwm", "epwm", "ecap", "eqep", "n2het", "flexray"
    }

    for periph in peripherals:
        if periph.get("name", "").upper() == module_name.upper():
            periph_type = periph.get("type", "").lower()
            if periph_type in io_peripheral_types:
                return ["IOMM"]

    return []


def _extract_irq_dependencies(soc_data: Dict[str, Any], module_name: str) -> List[str]:
    """
    Extract interrupt dependencies for a module from soc.yaml.

    Returns list of dependencies (e.g., ["VIM"]).
    """
    peripherals = soc_data.get("soc", {}).get("peripherals", [])

    for periph in peripherals:
        if periph.get("name", "").upper() == module_name.upper():
            # Check for irq_ref
            irq_refs = periph.get("irq_ref", [])
            if irq_refs:
                return ["VIM"]

    return []


# ==============================================================================
# DEPENDENCY VALIDATION
# ==============================================================================

def validate_dependencies(graph: DependencyGraph, manifest: Dict[str, Any]) -> List[str]:
    """
    Validate that all dependencies reference existing modules.

    Args:
        graph: Dependency graph to validate
        manifest: BSP manifest with api_catalog

    Returns:
        List of error messages (empty if valid)
    """
    # Build set of valid module names
    valid_modules = set(manifest.get("api_catalog", {}).keys())

    # Core system modules that may not be in manifest yet
    core_modules = {"SYSTEM", "PLL", "VIM", "PCR", "IOMM"}
    valid_modules.update(core_modules)

    # Check each dependency
    errors = []
    for node in graph.nodes.values():
        for dep in node.dependencies:
            if dep not in valid_modules:
                errors.append(
                    f"{node.name} depends on non-existent module: {dep}"
                )

    return errors


# ==============================================================================
# TOPOLOGICAL SORT (KAHN'S ALGORITHM)
# ==============================================================================

def generate_init_order(graph: DependencyGraph) -> InitOrder:
    """
    Generate initialization order using topological sort.

    Uses Kahn's algorithm to detect cycles and produce valid ordering.

    Args:
        graph: Dependency graph

    Returns:
        InitOrder with resolved order or cycle information
    """
    # Calculate in-degree for each node
    in_degree = {name: 0 for name in graph.nodes}

    for node in graph.nodes.values():
        for dep in node.dependencies:
            if dep in in_degree:
                in_degree[dep] += 0  # Dependency exists

        # Count dependencies
        for dep in node.dependencies:
            if dep in graph.nodes:
                in_degree[node.name] += 1

    # Initialize queue with nodes that have no dependencies
    queue = deque([name for name, degree in in_degree.items() if degree == 0])

    init_order = InitOrder()
    processed = []

    while queue:
        # Remove a node with no incoming edges
        current = queue.popleft()
        processed.append(current)

        # For each node that depends on current
        for name, node in graph.nodes.items():
            if current in node.dependencies:
                in_degree[name] -= 1
                if in_degree[name] == 0:
                    queue.append(name)

    # Check if all nodes were processed
    if len(processed) == len(graph.nodes):
        # Valid topological order
        init_order.order = processed
        init_order.has_cycles = False
        logger.info(f"Generated init order: {' → '.join(processed)}")
    else:
        # Cycle detected
        init_order.has_cycles = True
        init_order.cycle_nodes = [name for name in graph.nodes if name not in processed]

        # Try to find actual cycle path
        cycle_path = _find_cycle(graph, init_order.cycle_nodes)
        if cycle_path:
            init_order.cycle_nodes = cycle_path

        logger.error(f"Circular dependency detected: {init_order.cycle_nodes}")

    return init_order


def _find_cycle(graph: DependencyGraph, suspected_nodes: List[str]) -> Optional[List[str]]:
    """
    Find an actual cycle path in the graph (for better error reporting).

    Uses DFS to find a cycle starting from suspected nodes.
    """
    visited = set()
    rec_stack = []

    def dfs(node_name: str) -> Optional[List[str]]:
        if node_name in rec_stack:
            # Found cycle
            cycle_start = rec_stack.index(node_name)
            return rec_stack[cycle_start:]

        if node_name in visited:
            return None

        visited.add(node_name)
        rec_stack.append(node_name)

        node = graph.get_node(node_name)
        if node:
            for dep in node.dependencies:
                if dep in graph.nodes:
                    result = dfs(dep)
                    if result:
                        return result

        rec_stack.pop()
        return None

    # Try DFS from each suspected node
    for node_name in suspected_nodes:
        cycle = dfs(node_name)
        if cycle:
            return cycle

    return None


# ==============================================================================
# MAIN.C GENERATION
# ==============================================================================

def find_enable_pins_functions(manifest: dict, module_name: str) -> list:
    """
    Discover EnablePins functions for a module from manifest.

    This function queries the manifest to find any pin enable functions
    that have been generated for a given module. These functions configure
    IOMM pin multiplexing for the peripheral.

    Args:
        manifest: The BSP manifest containing api_catalog
        module_name: Name of the module to query (e.g., "SCI", "GIO")

    Returns:
        List of dicts with keys: name, prototype, brief
        Returns empty list if no EnablePins functions found or manifest is None
    """
    if not manifest:
        return []

    api_catalog = manifest.get('api_catalog', {})
    module_manifest = api_catalog.get(module_name, {})
    functions = module_manifest.get('functions', [])

    enable_pins_funcs = []

    for func in functions:
        func_name = func.get('name', '')
        func_proto = func.get('prototype', '')

        # Check if this is an EnablePins function
        if 'EnablePins' in func_name or 'EnablePins' in func_proto:
            enable_pins_funcs.append({
                'name': func_name,
                'prototype': func_proto,
                'brief': func.get('brief', func.get('description', ''))
            })

    return enable_pins_funcs


def _parse_board_led_gpio(board_data: Optional[Dict[str, Any]]) -> tuple[str, int]:
    """
    Parse LED GPIO from board.yaml-like data.

    Returns:
        Tuple of (port_letter, pin_index), defaults to ("B", 1).
    """
    if not board_data:
        return ("B", 1)

    leds = board_data.get("leds", [])
    if not isinstance(leds, list):
        return ("B", 1)

    # Prefer GIOB[1] explicitly when available (known RM46 LaunchXL user LED path).
    for led in leds:
        if not isinstance(led, dict):
            continue
        gpio_name = led.get("gpio")
        if isinstance(gpio_name, str) and gpio_name.strip().upper() == "GIOB[1]":
            return ("B", 1)

    # Prefer USER LED entries first.
    ordered_leds = sorted(
        leds,
        key=lambda x: 0 if isinstance(x, dict) and "USER" in str(x.get("function", "")).upper() else 1,
    )

    for led in ordered_leds:
        if not isinstance(led, dict):
            continue
        gpio_name = led.get("gpio")
        if not isinstance(gpio_name, str):
            continue
        match = re.match(r"GIO([AB])\[(\d+)\]", gpio_name.strip().upper())
        if not match:
            continue
        port = match.group(1)
        pin = int(match.group(2))
        return (port, pin)

    return ("B", 1)


def _parse_board_lin_sci_pins(board_data: Optional[Dict[str, Any]]) -> tuple[int, int]:
    """
    Parse board LIN/SCI debug UART pin mapping.

    Returns:
        Tuple of (rx_pin, tx_pin). Defaults to (38, 39) for RM46 LaunchXL path.
    """
    if not board_data:
        return (38, 39)

    comms = board_data.get("communication", {}) if isinstance(board_data, dict) else {}
    if isinstance(comms, dict):
        preferred = comms.get("preferred_debug_path", {})
        if isinstance(preferred, dict):
            rx_pin = preferred.get("rx_pin")
            tx_pin = preferred.get("tx_pin")
            if isinstance(rx_pin, int) and isinstance(tx_pin, int):
                return (rx_pin, tx_pin)

    board = comms if isinstance(comms, dict) else {}
    lin = board.get("lin", {}) if isinstance(board, dict) else {}
    lin1 = lin.get("lin1", {}) if isinstance(lin, dict) else {}
    if isinstance(lin1, dict):
        rx_pin = lin1.get("rx_pin")
        tx_pin = lin1.get("tx_pin")
        if isinstance(rx_pin, int) and isinstance(tx_pin, int):
            return (rx_pin, tx_pin)

    uart = board.get("uart", {}) if isinstance(board, dict) else {}
    sci = uart.get("sci", {}) if isinstance(uart, dict) else {}
    if isinstance(sci, dict):
        rx_pin = sci.get("rx_pin")
        tx_pin = sci.get("tx_pin")
        if isinstance(rx_pin, int) and isinstance(tx_pin, int):
            return (rx_pin, tx_pin)

    return (38, 39)


def _should_generate_bsp_validation(
    generation_profile: Optional[Dict[str, Any]],
    manifest: Optional[Dict[str, Any]]
) -> bool:
    """
    Determine whether to auto-generate runtime BSP validation module.
    """
    profile = generation_profile or {}

    # Explicit profile override wins.
    bsp_validation_cfg = profile.get("bsp_validation")
    if isinstance(bsp_validation_cfg, dict) and "enabled" in bsp_validation_cfg:
        return bool(bsp_validation_cfg.get("enabled"))

    # New policy: direct init is default unless explicitly switched to validation mode.
    bringup_mode_cfg = profile.get("bringup_mode", {})
    default_mode = "direct_init"
    if isinstance(bringup_mode_cfg, dict):
        mode_value = str(bringup_mode_cfg.get("default", "direct_init")).strip().lower()
        if mode_value in {"direct_init", "validation"}:
            default_mode = mode_value
    if default_mode != "validation":
        return False

    target = str(profile.get("target_board", "")).upper()
    if "RM46" not in target:
        return False

    # Require core serial/gpio modules to be available when profile enables modules.
    enabled = {
        str(m).upper()
        for m in profile.get("modules", {}).get("enabled", [])
        if isinstance(m, str)
    }
    if enabled:
        required = {"SCI", "LIN", "GIO"}
        if not required.issubset(enabled):
            return False

    if not manifest:
        return True

    api_catalog = manifest.get("api_catalog", {})
    required_catalog = {"SCI", "LIN", "GIO", "IOMM", "VIM"}
    return required_catalog.issubset({name.upper() for name in api_catalog.keys()})


def _get_contract_module(api_contract_manifest: Optional[Dict[str, Any]], module_name: str) -> Dict[str, Any]:
    if not api_contract_manifest:
        return {}
    modules = api_contract_manifest.get("modules", {})
    if not isinstance(modules, dict):
        return {}
    return modules.get(module_name.upper(), {}) or {}


def _find_enum_value(module_contract: Dict[str, Any], enum_name: str, contains: str, fallback: str) -> str:
    types = module_contract.get("types", {}) if isinstance(module_contract, dict) else {}
    enum_def = types.get(enum_name, {})
    values = enum_def.get("values", []) if isinstance(enum_def, dict) else []
    for value in values:
        if isinstance(value, str) and contains in value:
            return value
    if values and isinstance(values[0], str):
        return values[0]
    return fallback


def _find_enum_value_any(
    module_contract: Dict[str, Any],
    enum_names: List[str],
    contains: str,
    fallback: str,
) -> str:
    for enum_name in enum_names:
        value = _find_enum_value(module_contract, enum_name, contains, "")
        if value:
            return value
    return fallback


def _find_enum_value_candidates(
    module_contract: Dict[str, Any],
    enum_names: List[str],
    contains_tokens: List[str],
    fallback: str,
    allow_first_fallback: bool = True,
) -> str:
    types = module_contract.get("types", {}) if isinstance(module_contract, dict) else {}
    values: List[str] = []
    for enum_name in enum_names:
        enum_def = types.get(enum_name, {})
        enum_values = enum_def.get("values", []) if isinstance(enum_def, dict) else []
        values.extend([v for v in enum_values if isinstance(v, str)])

    for token in contains_tokens:
        for value in values:
            if token in value:
                return value

    if allow_first_fallback and values:
        return values[0]
    return fallback


def _resolve_iomm_alt1_from_header(out_dir: Path) -> str:
    candidates = [
        out_dir / "include" / "iomm_driver.h",
        out_dir / "iomm_driver.h",
        out_dir / "source" / "iomm_driver.h",
    ]
    priority_tokens = [
        "IOMM_PIN_FUNCTION_ALT1",
        "IOMM_PIN_FUNC_ALT1",
        "IOMM_FUNC_ALT1",
        "IOMM_PIN_FUNCTION_1",
    ]
    for header in candidates:
        if not header.exists():
            continue
        text = header.read_text(encoding="utf-8", errors="ignore")
        for token in priority_tokens:
            if token in text:
                return token
    return ""


def _find_fn_in_contract(module_contract: Dict[str, Any], candidates: List[str], fallback: str) -> str:
    functions = module_contract.get("functions", {}) if isinstance(module_contract, dict) else {}
    wrappers = {
        w.get("name")
        for w in module_contract.get("compatibility_wrappers", [])
        if isinstance(w, dict) and w.get("name")
    } if isinstance(module_contract, dict) else set()

    for name in candidates:
        if name in functions or name in wrappers:
            return name
    return fallback


def _capability_fn(module_contract: Dict[str, Any], capability: str, fallback_candidates: List[str], hard_fallback: str) -> str:
    capabilities = module_contract.get("capabilities", {}) if isinstance(module_contract, dict) else {}
    name = capabilities.get(capability)
    if isinstance(name, str) and name.strip():
        return name
    found = _find_fn_in_contract(module_contract, fallback_candidates, "")
    if found:
        return found
    found = _find_fn_in_contract(module_contract, [hard_fallback], "")
    if found:
        return found
    return hard_fallback


def _contract_has_function(module_contract: Dict[str, Any], function_name: str) -> bool:
    if not function_name:
        return False
    functions = module_contract.get("functions", {}) if isinstance(module_contract, dict) else {}
    if function_name in functions:
        return True
    wrappers = module_contract.get("compatibility_wrappers", []) if isinstance(module_contract, dict) else []
    for wrapper in wrappers:
        if isinstance(wrapper, dict) and wrapper.get("name") == function_name:
            return True
    return False


def _generate_bsp_validate_module(
    out_dir: Path,
    generation_profile: Optional[Dict[str, Any]],
    board_data: Optional[Dict[str, Any]],
    bringup_contract: Optional[Dict[str, Any]] = None,
    api_contract_manifest: Optional[Dict[str, Any]] = None,
) -> tuple[Path, Path]:
    """
    Generate deterministic BSP runtime validation module.

    Produces:
      - bsp_validate.h
      - bsp_validate.c
    """
    profile = generation_profile or {}
    contract_lock_mode = str(profile.get("contract_lock_mode", "strict")).strip().lower()
    strict_contract_lock = contract_lock_mode != "relaxed" and bool(api_contract_manifest)
    bsp_validation_cfg = profile.get("bsp_validation", {}) if isinstance(profile.get("bsp_validation", {}), dict) else {}
    bringup_cfg = bringup_contract if isinstance(bringup_contract, dict) else {}
    serial_cfg = bringup_cfg.get("serial", {}) if isinstance(bringup_cfg.get("serial", {}), dict) else {}
    contract_primary_path = str(serial_cfg.get("primary_path", "")).strip().upper()
    contract_primary_tx_only = str(serial_cfg.get("primary_tx_only", "")).strip().upper()
    profile_primary_serial_path = str(bsp_validation_cfg.get("primary_serial_path", "")).strip().lower()

    if profile_primary_serial_path in {"lin_only", "sci_only", "dual"}:
        primary_serial_path = profile_primary_serial_path
    elif contract_primary_tx_only == "LIN":
        primary_serial_path = "lin_only"
    elif contract_primary_tx_only == "SCI":
        primary_serial_path = "sci_only"
    elif contract_primary_tx_only == "BOTH":
        primary_serial_path = "dual"
    elif contract_primary_path == "LIN_SCI_MODE":
        primary_serial_path = "lin_only"
    else:
        primary_serial_path = "dual"

    emit_lin_primary_tx = primary_serial_path in {"lin_only", "dual"}
    emit_sci_primary_tx = primary_serial_path in {"sci_only", "dual"}
    emit_sci_init = emit_sci_primary_tx
    emit_sci_echo = emit_sci_primary_tx
    baud = bsp_validation_cfg.get("baud", profile.get("sci", {}).get("default_baud", 9600))
    if not isinstance(baud, int) or baud <= 0:
        baud = 9600
    frame_cfg = bsp_validation_cfg.get("frame", {}) if isinstance(bsp_validation_cfg.get("frame", {}), dict) else {}
    frame_data_bits = frame_cfg.get("data_bits", 8)
    if not isinstance(frame_data_bits, int) or frame_data_bits < 5 or frame_data_bits > 9:
        frame_data_bits = 8
    frame_stop_bits = frame_cfg.get("stop_bits", 1)
    if not isinstance(frame_stop_bits, int) or frame_stop_bits not in (1, 2):
        frame_stop_bits = 1
    frame_parity = str(frame_cfg.get("parity", "none")).strip().lower()
    if frame_parity not in {"none", "even", "odd"}:
        frame_parity = "none"
    timing_cfg = bsp_validation_cfg.get("timing", {}) if isinstance(bsp_validation_cfg.get("timing", {}), dict) else {}
    force_sci_init = bool(bsp_validation_cfg.get("force_sci_init", False))
    force_sci_tx = bool(bsp_validation_cfg.get("force_sci_tx", False))
    heartbeat_ticks = timing_cfg.get("heartbeat_ticks", 1000)
    tx_period_ticks = timing_cfg.get("tx_period_ticks", 200)
    busy_delay = timing_cfg.get("busy_delay", 200)
    if not isinstance(heartbeat_ticks, int) or heartbeat_ticks <= 0:
        heartbeat_ticks = 1000
    if not isinstance(tx_period_ticks, int) or tx_period_ticks <= 0:
        tx_period_ticks = 200
    if not isinstance(busy_delay, int) or busy_delay < 0:
        busy_delay = 200
    banners_cfg = bsp_validation_cfg.get("banners", {}) if isinstance(bsp_validation_cfg.get("banners", {}), dict) else {}
    sci_banner_text = str(banners_cfg.get("sci", "SCI path active (A)\\r\\n"))
    lin_banner_text = str(banners_cfg.get("lin", "LIN path active (B)\\r\\n"))

    def _c_string_literal(raw: str) -> str:
        # Normalize user-provided escaped sequences (e.g. "\\r\\n") into C escapes.
        normalized = (
            raw.replace("\\r", "\r")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
        )
        escaped = normalized.replace("\\", "\\\\").replace("\"", "\\\"")
        return escaped.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")

    sci_contract = _get_contract_module(api_contract_manifest, "SCI")
    sci_types = sci_contract.get("types", {}) if isinstance(sci_contract, dict) else {}
    sci_cfg_fields = {
        f.get("name")
        for f in (sci_types.get("sci_config_t", {}).get("fields", []) if isinstance(sci_types.get("sci_config_t", {}), dict) else [])
        if isinstance(f, dict) and f.get("name")
    }
    lin_contract = _get_contract_module(api_contract_manifest, "LIN")
    lin_types = lin_contract.get("types", {}) if isinstance(lin_contract, dict) else {}
    lin_cfg_fields = {
        f.get("name")
        for f in (lin_types.get("lin_config_t", {}).get("fields", []) if isinstance(lin_types.get("lin_config_t", {}), dict) else [])
        if isinstance(f, dict) and f.get("name")
    }

    lin_functions = lin_contract.get("functions", {}) if isinstance(lin_contract, dict) else {}
    lin_capabilities = lin_contract.get("capabilities", {}) if isinstance(lin_contract, dict) else {}
    sci_capabilities = sci_contract.get("capabilities", {}) if isinstance(sci_contract, dict) else {}
    gio_contract = _get_contract_module(api_contract_manifest, "GIO")
    iomm_contract = _get_contract_module(api_contract_manifest, "IOMM")
    gio_capabilities = gio_contract.get("capabilities", {}) if isinstance(gio_contract, dict) else {}

    lin_send_fn = _capability_fn(
        lin_contract,
        "tx_buffer",
        ["LIN_Transmit", "LIN_SendData", "LIN_Send"],
        "LIN_SendData",
    )
    lin_send_arity = int((lin_functions.get(lin_send_fn, {}) or {}).get("arity", 2))
    lin_init_fn = _capability_fn(
        lin_contract,
        "init",
        ["LIN_Init"],
        "LIN_Init",
    )
    lin_init_arity = int((lin_functions.get(lin_init_fn, {}) or {}).get("arity", 1))
    lin_send_byte_fn = _capability_fn(
        lin_contract,
        "tx_byte",
        ["LIN_TransmitByte", "LIN_SendByte"],
        "LIN_TransmitByte",
    )
    lin_receive_fn = _capability_fn(
        lin_contract,
        "rx_byte",
        ["LIN_ReceiveByte"],
        "LIN_ReceiveByte",
    )
    lin_receive_arity = int((lin_functions.get(lin_receive_fn, {}) or {}).get("arity", lin_capabilities.get("rx_byte_arity", 2)))
    lin_tx_ready_fn = _capability_fn(
        lin_contract,
        "tx_ready",
        ["LIN_IsTxReady", "LIN_GetTxReady", "LIN_GetTxStatus"],
        "LIN_IsTxReady",
    )
    lin_rx_ready_fn = _capability_fn(
        lin_contract,
        "rx_ready",
        ["LIN_IsRxReady", "LIN_GetRxReady", "LIN_GetRxStatus"],
        "LIN_IsRxReady",
    )
    lin_send_available = _contract_has_function(lin_contract, lin_send_fn)
    lin_send_byte_available = _contract_has_function(lin_contract, lin_send_byte_fn)
    lin_receive_available = _contract_has_function(lin_contract, lin_receive_fn)
    lin_tx_ready_available = _contract_has_function(lin_contract, lin_tx_ready_fn)
    lin_rx_ready_available = _contract_has_function(lin_contract, lin_rx_ready_fn)
    lin_banner_via_tx_buffer = emit_lin_primary_tx and lin_send_available and lin_send_arity >= 2 and lin_send_fn != lin_send_byte_fn
    lin_banner_via_tx_byte = emit_lin_primary_tx and lin_send_byte_available

    sci_functions = sci_contract.get("functions", {}) if isinstance(sci_contract, dict) else {}
    sci_send_fn = _capability_fn(
        sci_contract,
        "tx_buffer",
        ["SCI_SendData", "SCI_Send", "SCI_Write"],
        "SCI_SendData",
    )
    sci_send_arity = int((sci_functions.get(sci_send_fn, {}) or {}).get("arity", 2))
    sci_init_fn = _capability_fn(
        sci_contract,
        "init",
        ["SCI_Init"],
        "SCI_Init",
    )
    sci_init_arity = int((sci_functions.get(sci_init_fn, {}) or {}).get("arity", 1))
    sci_send_byte_fn = _capability_fn(
        sci_contract,
        "tx_byte",
        ["SCI_SendByte", "SCI_WriteByte"],
        "SCI_SendByte",
    )
    sci_receive_fn = _capability_fn(
        sci_contract,
        "rx_byte",
        ["SCI_ReceiveByte", "SCI_ReadByte"],
        "SCI_ReceiveByte",
    )
    sci_tx_ready_fn = _capability_fn(
        sci_contract,
        "tx_ready",
        ["SCI_IsTxReady", "SCI_GetTxReady", "SCI_GetTxStatus"],
        "SCI_IsTxReady",
    )
    sci_rx_ready_fn = _capability_fn(
        sci_contract,
        "rx_ready",
        ["SCI_IsRxReady", "SCI_GetRxReady", "SCI_GetRxStatus"],
        "SCI_IsRxReady",
    )
    if force_sci_init:
        emit_sci_init = True
    if force_sci_tx:
        emit_sci_primary_tx = True
        emit_sci_echo = True
    sci_send_available = emit_sci_primary_tx and _contract_has_function(sci_contract, sci_send_fn)
    sci_send_byte_available = emit_sci_primary_tx and _contract_has_function(sci_contract, sci_send_byte_fn)
    sci_receive_available = emit_sci_primary_tx and _contract_has_function(sci_contract, sci_receive_fn)
    sci_tx_ready_available = emit_sci_primary_tx and _contract_has_function(sci_contract, sci_tx_ready_fn)
    sci_rx_ready_available = emit_sci_primary_tx and _contract_has_function(sci_contract, sci_rx_ready_fn)

    lin_mode_sci = _find_enum_value_any(
        lin_contract,
        ["lin_mode_t"],
        "SCI",
        "0U",
    )
    parity_token = "NONE" if frame_parity == "none" else ("EVEN" if frame_parity == "even" else "ODD")
    lin_parity_value = _find_enum_value_any(
        lin_contract,
        ["lin_parity_t"],
        parity_token,
        "0U",
    )
    lin_stop_value = _find_enum_value_any(
        lin_contract,
        ["lin_stop_bits_t", "lin_stopbits_t"],
        str(frame_stop_bits),
        "0U",
    )
    lin_dma_disabled_value = _find_enum_value_any(
        lin_contract,
        ["lin_dma_mode_t"],
        "DISABLED",
        "0U",
    )
    sci_data_bits_value = _find_enum_value_any(
        sci_contract,
        ["sci_data_bits_t", "sci_databits_t"],
        str(frame_data_bits),
        "SCI_DATABITS_8",
    )
    sci_parity_value = _find_enum_value_any(
        sci_contract,
        ["sci_parity_t"],
        parity_token,
        "SCI_PARITY_NONE",
    )
    sci_stop_bits_value = _find_enum_value_any(
        sci_contract,
        ["sci_stop_bits_t", "sci_stopbits_t"],
        str(frame_stop_bits),
        "SCI_STOPBITS_1",
    )
    gio_direction_output = _find_enum_value_any(
        gio_contract,
        ["gio_direction_t", "gio_pin_direction_t"],
        "OUTPUT",
        "1U",
    )
    gio_pull_disabled = _find_enum_value_any(
        gio_contract,
        ["gio_pull_mode_t", "gio_pull_t", "gio_pull_config_t"],
        "DISABLE",
        "0U",
    )
    gio_mode_push_pull = _find_enum_value_any(
        gio_contract,
        ["gio_drive_mode_t", "gio_drive_t", "gio_pin_mode_t"],
        "PUSH",
        "0U",
    )
    iomm_pin_function_alt1 = _find_enum_value_candidates(
        iomm_contract,
        ["iomm_pin_function_t"],
        ["ALT1", "FUNCTION_1", "_1"],
        "",
        allow_first_fallback=not strict_contract_lock,
    )
    if not iomm_pin_function_alt1:
        iomm_pin_function_alt1 = _resolve_iomm_alt1_from_header(out_dir)

    iomm_init_fn = _capability_fn(
        iomm_contract,
        "init",
        ["IOMM_Init"],
        "IOMM_Init",
    )
    iomm_configure_pin_fn = _capability_fn(
        iomm_contract,
        "configure_pin",
        ["IOMM_ConfigurePin"],
        "IOMM_ConfigurePin",
    )
    iomm_unlock_fn = _capability_fn(
        iomm_contract,
        "unlock",
        ["IOMM_Unlock"],
        "IOMM_Unlock",
    )
    iomm_lock_fn = _capability_fn(
        iomm_contract,
        "lock",
        ["IOMM_Lock"],
        "IOMM_Lock",
    )

    strict_require_iomm_af1 = strict_contract_lock and _contract_has_function(iomm_contract, "IOMM_ConfigurePin")
    if not iomm_pin_function_alt1:
        if strict_require_iomm_af1:
            raise ValueError(
                "BSP validate generation failed: could not resolve IOMM AF1 symbol from iomm_pin_function_t "
                "while contract_lock_mode=strict"
            )
        iomm_pin_function_alt1 = "1U"
    gio_port_a = _find_enum_value_any(
        gio_contract,
        ["gio_port_t"],
        "PORT_A",
        "0U",
    )
    gio_port_b = _find_enum_value_any(
        gio_contract,
        ["gio_port_t"],
        "PORT_B",
        "1U",
    )
    gio_types = gio_contract.get("types", {}) if isinstance(gio_contract, dict) else {}
    gio_cfg_fields = {
        f.get("name")
        for f in (gio_types.get("gio_pin_config_t", {}).get("fields", []) if isinstance(gio_types.get("gio_pin_config_t", {}), dict) else [])
        if isinstance(f, dict) and f.get("name")
    }
    gio_config_pin_arity = int(gio_capabilities.get("configure_pin_arity", 3))
    gio_configure_fn = _capability_fn(
        gio_contract,
        "configure_pin",
        ["GIO_ConfigurePin"],
        "GIO_ConfigurePin",
    )
    gio_write_fn = _capability_fn(
        gio_contract,
        "write_pin",
        ["GIO_WritePin"],
        "GIO_WritePin",
    )
    gio_toggle_fn = _capability_fn(
        gio_contract,
        "toggle_pin",
        ["GIO_TogglePin"],
        "GIO_TogglePin",
    )
    gio_configure_available = _contract_has_function(gio_contract, gio_configure_fn)
    gio_write_available = _contract_has_function(gio_contract, gio_write_fn)
    gio_toggle_available = _contract_has_function(gio_contract, gio_toggle_fn)

    led_port_letter, led_pin = _parse_board_led_gpio(board_data)
    lin_rx_pin, lin_tx_pin = _parse_board_lin_sci_pins(board_data)
    led_port = gio_port_b if led_port_letter == "B" else gio_port_a

    # Optional contract-driven direct pinmux writes (HAL-style RMW over 5-bit function field).
    # This is used as an authoritative bring-up path for RM46 serial pins.
    contract_pinmux_entries: List[Dict[str, int | str]] = []
    for entry in serial_cfg.get("required_pins", []) if isinstance(serial_cfg.get("required_pins", []), list) else []:
        if not isinstance(entry, dict):
            continue
        register_name = str(entry.get("register", "")).strip()
        bit_val = entry.get("bit")
        af_val = entry.get("af")
        if not register_name or not isinstance(bit_val, int) or not isinstance(af_val, int):
            continue
        if af_val < 0:
            continue
        match = re.fullmatch(r"PINMMR(\d+)", register_name, flags=re.IGNORECASE)
        if not match:
            continue
        field_start = bit_val - af_val
        if field_start < 0 or field_start > 27:
            continue
        contract_pinmux_entries.append(
            {
                "register": f"PINMMR{int(match.group(1))}",
                "field_start": field_start,
                "target_bit": bit_val,
                "pin": int(entry.get("pin", 0)),
            }
        )
    use_direct_iomm_pinmux = (
        emit_lin_primary_tx
        and bool(contract_pinmux_entries)
        and _contract_has_function(iomm_contract, iomm_unlock_fn)
        and _contract_has_function(iomm_contract, iomm_lock_fn)
    )

    header_lines = [
        "/**",
        " * @file bsp_validate.h",
        " * @brief Runtime BSP validation/smoke-test interface",
        " */",
        "",
        "#ifndef BSP_VALIDATE_H",
        "#define BSP_VALIDATE_H",
        "",
        "#include <stdint.h>",
        "",
        "void BSP_ValidateInit(void);",
        "void BSP_ValidateStep(void);",
        "uint32_t BSP_ValidateGetHeartbeatCount(void);",
        "",
        "#endif /* BSP_VALIDATE_H */",
        "",
    ]

    source_lines = [
        "/**",
        " * @file bsp_validate.c",
        " * @brief Runtime BSP validation/smoke-test implementation",
        " */",
        "",
        "#include \"bsp_validate.h\"",
        "",
        "#include <stdint.h>",
        "#include <stdbool.h>",
        "#include <stddef.h>",
        "",
        "#include \"iomm_driver.h\"",
        "#include \"vim_driver.h\"",
        "#include \"gio_driver.h\"",
        "#include \"sci_driver.h\"",
        "#include \"lin_driver.h\"",
        "",
        f"#define BSP_VALIDATE_BAUD              ({baud}U)",
        f"#define BSP_VALIDATE_LED_PORT          ({led_port})",
        f"#define BSP_VALIDATE_LED_PIN           ({led_pin}U)",
        f"#define BSP_VALIDATE_HEARTBEAT_TICKS   ({heartbeat_ticks}U)",
        f"#define BSP_VALIDATE_TX_PERIOD_TICKS   ({tx_period_ticks}U)",
        f"#define BSP_VALIDATE_BUSY_DELAY        ({busy_delay}U)",
        "#define BSP_VALIDATE_TX_RETRY_LIMIT    (4096U)",
        "",
        "static uint32_t g_validate_heartbeat_ticks = 0U;",
        "static uint32_t g_validate_tx_period = 0U;",
        "static uint32_t g_validate_heartbeat_count = 0U;",
        "static bool g_validate_initialized = false;",
        "",
        "volatile uint32_t g_validate_sci_status = 0U;",
        "volatile uint32_t g_validate_lin_status = 0U;",
        "volatile uint32_t g_validate_sci_tx_ok = 0U;",
        "volatile uint32_t g_validate_sci_tx_skip = 0U;",
        "volatile uint32_t g_validate_lin_tx_ok = 0U;",
        "volatile uint32_t g_validate_lin_tx_skip = 0U;",
        "",
        "static void bsp_validate_delay(volatile uint32_t ticks)",
        "{",
        "    while (ticks > 0U)",
        "    {",
        "        ticks--;",
        "    }",
        "}",
        "",
    ]

    if lin_banner_via_tx_byte:
        source_lines.extend(
            [
                "static bool bsp_validate_lin_send_byte_retry(uint8_t value)",
                "{",
                "    uint32_t retries = 0U;",
                "    while (retries < BSP_VALIDATE_TX_RETRY_LIMIT)",
                "    {",
            ]
        )
        if lin_tx_ready_available:
            source_lines.extend(
                [
                    f"        if ({lin_tx_ready_fn}())",
                    "        {",
                    f"            if ({lin_send_byte_fn}(value) == LIN_STATUS_OK)",
                    "            {",
                    "                return true;",
                    "            }",
                    "            g_validate_lin_tx_skip++;",
                    "        }",
                    "        else",
                    "        {",
                    "            g_validate_lin_tx_skip++;",
                    "        }",
                ]
            )
        else:
            source_lines.extend(
                [
                    f"        if ({lin_send_byte_fn}(value) == LIN_STATUS_OK)",
                    "        {",
                    "            return true;",
                    "        }",
                    "        g_validate_lin_tx_skip++;",
                ]
            )
        source_lines.extend(
            [
                "        retries++;",
                "    }",
                "    return false;",
                "}",
                "",
            ]
        )

    source_lines.extend(
        [
        "void BSP_ValidateInit(void)",
        "{",
        "    gio_pin_config_t led_cfg = {0};",
    ]
    )
    if emit_sci_init:
        source_lines.append("    sci_config_t sci_cfg = {0};")
    source_lines.extend(
        [
        "    lin_config_t lin_cfg = {0};",
        "    uint32_t lin_banner_idx = 0U;",
    ]
    )
    if use_direct_iomm_pinmux:
        source_lines.extend(
            [
                "    volatile IOMM_REG_MAP_t* iomm_regs = (volatile IOMM_REG_MAP_t*)0xFFFFEA00U;",
                "    uint32_t pinmmr_value = 0U;",
            ]
        )
    if emit_sci_primary_tx:
        source_lines.append(f"    static const uint8_t sci_banner[] = \"{_c_string_literal(sci_banner_text)}\";")
    if emit_lin_primary_tx:
        source_lines.append(f"    static const uint8_t lin_banner[] = \"{_c_string_literal(lin_banner_text)}\";")
    source_lines.extend(
        [
        "",
        f"    (void){iomm_init_fn}();",
    ])
    if use_direct_iomm_pinmux:
        source_lines.append(f"    {iomm_unlock_fn}();")
        for pinmux_entry in contract_pinmux_entries:
            register_name = str(pinmux_entry.get("register", ""))
            field_start = int(pinmux_entry.get("field_start", 0))
            target_bit = int(pinmux_entry.get("target_bit", field_start))
            source_lines.extend(
                [
                    f"    pinmmr_value = iomm_regs->{register_name};",
                    f"    pinmmr_value &= ~(0x1FU << {field_start}U);",
                    f"    pinmmr_value |= (1U << {target_bit}U);",
                    f"    iomm_regs->{register_name} = pinmmr_value;",
                ]
            )
        source_lines.append(f"    {iomm_lock_fn}();")
    else:
        source_lines.extend(
            [
                f"    (void){iomm_configure_pin_fn}({lin_tx_pin}U, {iomm_pin_function_alt1});",
                f"    (void){iomm_configure_pin_fn}({lin_rx_pin}U, {iomm_pin_function_alt1});",
            ]
        )
    source_lines.extend(
        [
        "    vim_init();",
        "    (void)GIO_Init();",
        "",
    ])

    if "direction" in gio_cfg_fields:
        source_lines.append(f"    led_cfg.direction = {gio_direction_output};")
    if "pull" in gio_cfg_fields:
        source_lines.append(f"    led_cfg.pull = {gio_pull_disabled};")
    if "pull_mode" in gio_cfg_fields:
        source_lines.append(f"    led_cfg.pull_mode = {gio_pull_disabled};")
    if "mode" in gio_cfg_fields:
        source_lines.append(f"    led_cfg.mode = {gio_mode_push_pull};")
    if "drive" in gio_cfg_fields:
        source_lines.append(f"    led_cfg.drive = {gio_mode_push_pull};")
    if "drive_mode" in gio_cfg_fields:
        source_lines.append(f"    led_cfg.drive_mode = {gio_mode_push_pull};")
    if "port" in gio_cfg_fields:
        source_lines.append("    led_cfg.port = BSP_VALIDATE_LED_PORT;")
    if "pin" in gio_cfg_fields:
        source_lines.append("    led_cfg.pin = BSP_VALIDATE_LED_PIN;")

    if gio_configure_available:
        source_lines.append(
            f"    (void){gio_configure_fn}(BSP_VALIDATE_LED_PORT, BSP_VALIDATE_LED_PIN, &led_cfg);"
            if gio_config_pin_arity >= 3
            else f"    (void){gio_configure_fn}(&led_cfg);"
        )
    else:
        source_lines.append("    /* GIO pin configuration API unavailable in current contract */")

    if gio_write_available:
        source_lines.append(f"    (void){gio_write_fn}(BSP_VALIDATE_LED_PORT, BSP_VALIDATE_LED_PIN, GIO_LEVEL_HIGH);")
    else:
        source_lines.append("    /* GIO pin write API unavailable in current contract */")
    source_lines.append("")
    if emit_sci_init:
        if "baud_rate" in sci_cfg_fields:
            source_lines.append("    sci_cfg.baud_rate = BSP_VALIDATE_BAUD;")
        if "data_bits" in sci_cfg_fields:
            source_lines.append(f"    sci_cfg.data_bits = {sci_data_bits_value};")
        if "parity" in sci_cfg_fields:
            source_lines.append(f"    sci_cfg.parity = {sci_parity_value};")
        if "stop_bits" in sci_cfg_fields:
            source_lines.append(f"    sci_cfg.stop_bits = {sci_stop_bits_value};")
        if "enable_tx" in sci_cfg_fields:
            source_lines.append("    sci_cfg.enable_tx = true;")
        if "enable_rx" in sci_cfg_fields:
            source_lines.append("    sci_cfg.enable_rx = true;")
        if "enable_loopback" in sci_cfg_fields:
            source_lines.append("    sci_cfg.enable_loopback = false;")
        if "enable_dma_tx" in sci_cfg_fields:
            source_lines.append("    sci_cfg.enable_dma_tx = false;")
        if "enable_dma_rx" in sci_cfg_fields:
            source_lines.append("    sci_cfg.enable_dma_rx = false;")

        if _contract_has_function(sci_contract, sci_init_fn):
            source_lines.append(
                f"    g_validate_sci_status = (uint32_t){sci_init_fn}(&sci_cfg);"
                if sci_init_arity >= 1
                else f"    g_validate_sci_status = (uint32_t){sci_init_fn}();"
            )
        else:
            source_lines.append("    /* SCI init API unavailable in current contract */")
        source_lines.append("")

    if "mode" in lin_cfg_fields:
        source_lines.append(f"    lin_cfg.mode = {lin_mode_sci};")
    if "baud_rate" in lin_cfg_fields:
        source_lines.append("    lin_cfg.baud_rate = BSP_VALIDATE_BAUD;")

    if "data_length" in lin_cfg_fields:
        lin_data_field = next(
            (
                f
                for f in (lin_types.get("lin_config_t", {}).get("fields", []) or [])
                if isinstance(f, dict) and f.get("name") == "data_length"
            ),
            None,
        )
        lin_data_type = str((lin_data_field or {}).get("type", ""))
        if lin_data_type in lin_types and (lin_types.get(lin_data_type, {}) or {}).get("kind") == "enum":
            lin_data_length_value = _find_enum_value(
                lin_contract,
                lin_data_type,
                str(frame_data_bits),
                "LIN_DATA_LENGTH_8",
            )
            source_lines.append(f"    lin_cfg.data_length = {lin_data_length_value};")
        else:
            frame_length_value = frame_data_bits - 1 if frame_data_bits > 0 else 7
            source_lines.append(f"    lin_cfg.data_length = {frame_length_value}U;")
    elif "data_bits" in lin_cfg_fields:
        lin_data_field = next(
            (f for f in (lin_types.get("lin_config_t", {}).get("fields", []) or []) if isinstance(f, dict) and f.get("name") == "data_bits"),
            None,
        )
        lin_data_type = str((lin_data_field or {}).get("type", ""))
        if lin_data_type in lin_types and (lin_types.get(lin_data_type, {}) or {}).get("kind") == "enum":
            lin_data_bits_value = _find_enum_value(
                lin_contract,
                lin_data_type,
                str(frame_data_bits),
                "LIN_DATA_BITS_8",
            )
            source_lines.append(f"    lin_cfg.data_bits = {lin_data_bits_value};")
        else:
            source_lines.append(f"    lin_cfg.data_bits = {frame_data_bits}U;")
    if "parity" in lin_cfg_fields:
        source_lines.append(f"    lin_cfg.parity = {lin_parity_value};")
    if "stop_bits" in lin_cfg_fields:
        source_lines.append(f"    lin_cfg.stop_bits = {lin_stop_value};")
    if "enable_loopback" in lin_cfg_fields:
        source_lines.append("    lin_cfg.enable_loopback = false;")
    if "enable_rx" in lin_cfg_fields:
        source_lines.append("    lin_cfg.enable_rx = true;")
    if "enable_tx" in lin_cfg_fields:
        source_lines.append("    lin_cfg.enable_tx = true;")
    if "enable_multibuffer" in lin_cfg_fields:
        source_lines.append("    lin_cfg.enable_multibuffer = false;")
    if "dma_mode" in lin_cfg_fields:
        source_lines.append(f"    lin_cfg.dma_mode = {lin_dma_disabled_value};")
    if "tx_dma_enable" in lin_cfg_fields:
        source_lines.append("    lin_cfg.tx_dma_enable = false;")
    if "rx_dma_enable" in lin_cfg_fields:
        source_lines.append("    lin_cfg.rx_dma_enable = false;")
    if "enable_dma_tx" in lin_cfg_fields:
        source_lines.append("    lin_cfg.enable_dma_tx = false;")
    if "enable_dma_rx" in lin_cfg_fields:
        source_lines.append("    lin_cfg.enable_dma_rx = false;")
    if "rx_callback" in lin_cfg_fields:
        source_lines.append("    lin_cfg.rx_callback = NULL;")
    if "tx_callback" in lin_cfg_fields:
        source_lines.append("    lin_cfg.tx_callback = NULL;")
    if "error_callback" in lin_cfg_fields:
        source_lines.append("    lin_cfg.error_callback = NULL;")
    if "pin_config" in lin_cfg_fields:
        pin_cfg_field = next(
            (
                f
                for f in (lin_types.get("lin_config_t", {}).get("fields", []) or [])
                if isinstance(f, dict) and f.get("name") == "pin_config"
            ),
            None,
        )
        pin_cfg_type = str((pin_cfg_field or {}).get("type", ""))
        pin_cfg_fields = {
            f.get("name")
            for f in (
                lin_types.get(pin_cfg_type, {}).get("fields", [])
                if isinstance(lin_types.get(pin_cfg_type, {}), dict)
                else []
            )
            if isinstance(f, dict) and f.get("name")
        }
        # Ensure basic SCI-over-LIN path is active when driver models pin electrical config.
        # Support both legacy and newer field naming variants to prevent terminal-output regressions.
        if "tx_functional_mode" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.tx_functional_mode = true;")
        if "rx_functional_mode" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.rx_functional_mode = true;")
        if "tx_func_mode" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.tx_func_mode = true;")
        if "rx_func_mode" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.rx_func_mode = true;")

        if "tx_open_drain" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.tx_open_drain = false;")
        if "rx_open_drain" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.rx_open_drain = false;")
        if "open_drain" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.open_drain = false;")

        if "tx_pull_enable" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.tx_pull_enable = false;")
        if "rx_pull_enable" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.rx_pull_enable = false;")
        if "pull_enable" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.pull_enable = false;")

        if "tx_pull_select" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.tx_pull_select = true;")
        if "rx_pull_select" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.rx_pull_select = true;")
        if "pull_select" in pin_cfg_fields:
            source_lines.append("    lin_cfg.pin_config.pull_select = true;")

    if _contract_has_function(lin_contract, lin_init_fn):
        source_lines.append(
            f"    g_validate_lin_status = (uint32_t){lin_init_fn}(&lin_cfg);"
            if lin_init_arity >= 1
            else f"    g_validate_lin_status = (uint32_t){lin_init_fn}();"
        )
    else:
        source_lines.append("    /* LIN init API unavailable in current contract */")
    source_lines.append("")
    if sci_send_available:
        if sci_send_arity >= 3:
            source_lines.append(f"    (void){sci_send_fn}(sci_banner, (uint32_t)(sizeof(sci_banner) - 1U), 100U);")
        else:
            source_lines.append(f"    (void){sci_send_fn}(sci_banner, (uint32_t)(sizeof(sci_banner) - 1U));")
    if lin_banner_via_tx_byte:
        source_lines.extend(
            [
                "    lin_banner_idx = 0U;",
                "    while (lin_banner_idx < (uint32_t)(sizeof(lin_banner) - 1U))",
                "    {",
                "        if (bsp_validate_lin_send_byte_retry(lin_banner[lin_banner_idx]))",
                "        {",
                "            lin_banner_idx++;",
                "        }",
                "        else",
                "        {",
                "            break;",
                "        }",
                "    }",
                "    if (lin_banner_idx < (uint32_t)(sizeof(lin_banner) - 1U))",
                "    {",
                "        g_validate_lin_tx_skip++;",
                "    }",
            ]
        )
    elif lin_banner_via_tx_buffer:
        if lin_send_arity >= 3:
            source_lines.append(f"    (void){lin_send_fn}(lin_banner, (uint16_t)(sizeof(lin_banner) - 1U), 100U);")
        else:
            source_lines.append(f"    (void){lin_send_fn}(lin_banner, (uint32_t)(sizeof(lin_banner) - 1U));")
    if not lin_banner_via_tx_byte:
        source_lines.append("    (void)lin_banner_idx;")
    source_lines.extend(
        [
            "",
            "    g_validate_heartbeat_ticks = 0U;",
            "    g_validate_tx_period = 0U;",
            "    g_validate_heartbeat_count = 0U;",
            "    g_validate_initialized = true;",
            "}",
            "",
            "void BSP_ValidateStep(void)",
            "{",
            "    uint8_t rx_byte;",
            "",
            "    if (!g_validate_initialized)",
            "    {",
            "        return;",
            "    }",
            "",
        ]
    )

    if emit_sci_echo and sci_rx_ready_available and sci_receive_available and sci_send_byte_available:
        source_lines.extend(
            [
                f"    if ({sci_rx_ready_fn}())",
                "    {",
                f"        if ({sci_receive_fn}(&rx_byte) == SCI_STATUS_OK)",
                "        {",
                f"            (void){sci_send_byte_fn}(rx_byte);",
                "        }",
                "    }",
                "",
            ]
        )

    if lin_receive_available and lin_send_byte_available:
        rx_call = (
            f"{lin_receive_fn}(&rx_byte, 0U)"
            if lin_receive_arity >= 2
            else f"{lin_receive_fn}(&rx_byte)"
        )
        if lin_rx_ready_available:
            source_lines.extend(
                [
                    f"    if ({lin_rx_ready_fn}())",
                    "    {",
                    f"        if ({rx_call} == LIN_STATUS_OK)",
                    "        {",
                    f"            (void){lin_send_byte_fn}(rx_byte);",
                    "        }",
                    "    }",
                    "",
                ]
            )
        else:
            source_lines.extend(
                [
                    f"    if ({rx_call} == LIN_STATUS_OK)",
                    "    {",
                    f"        (void){lin_send_byte_fn}(rx_byte);",
                    "    }",
                    "",
                ]
            )

    source_lines.extend(
        [
            "    g_validate_tx_period++;",
            "    if (g_validate_tx_period >= BSP_VALIDATE_TX_PERIOD_TICKS)",
            "    {",
            "        g_validate_tx_period = 0U;",
            "",
        ]
    )

    if emit_sci_primary_tx and sci_tx_ready_available and sci_send_byte_available:
        source_lines.extend(
            [
                f"        if ({sci_tx_ready_fn}())",
                "        {",
                f"            (void){sci_send_byte_fn}('A');",
                "            g_validate_sci_tx_ok++;",
                "        }",
                "        else",
                "        {",
                "            g_validate_sci_tx_skip++;",
                "        }",
                "",
            ]
        )

    if emit_lin_primary_tx and lin_send_byte_available:
        if lin_tx_ready_available:
            source_lines.extend(
                [
                    f"        if ({lin_tx_ready_fn}())",
                    "        {",
                    f"            (void){lin_send_byte_fn}('B');",
                    "            g_validate_lin_tx_ok++;",
                    "        }",
                    "        else",
                    "        {",
                    "            g_validate_lin_tx_skip++;",
                    "        }",
                ]
            )
        else:
            source_lines.extend(
                [
                    f"        if ({lin_send_byte_fn}('B') == LIN_STATUS_OK)",
                    "        {",
                    "            g_validate_lin_tx_ok++;",
                    "        }",
                    "        else",
                    "        {",
                    "            g_validate_lin_tx_skip++;",
                    "        }",
                ]
            )

    source_lines.extend(
        [
            "    }",
            "",
            "    g_validate_heartbeat_ticks++;",
            "    if (g_validate_heartbeat_ticks >= BSP_VALIDATE_HEARTBEAT_TICKS)",
            "    {",
            "        g_validate_heartbeat_ticks = 0U;",
            "        g_validate_heartbeat_count++;",
            (
                f"        (void){gio_toggle_fn}(BSP_VALIDATE_LED_PORT, BSP_VALIDATE_LED_PIN);"
                if gio_toggle_available
                else "        /* GIO toggle unavailable in current contract */"
            ),
            "    }",
            "",
            "    bsp_validate_delay(BSP_VALIDATE_BUSY_DELAY);",
            "}",
            "",
            "uint32_t BSP_ValidateGetHeartbeatCount(void)",
            "{",
            "    return g_validate_heartbeat_count;",
            "}",
            "",
        ]
    )

    header_path = out_dir / "bsp_validate.h"
    source_path = out_dir / "bsp_validate.c"

    header_path.write_text(
        normalize_generated_text("\n".join(header_lines), header_path),
        encoding="utf-8",
    )
    source_path.write_text(
        normalize_generated_text("\n".join(source_lines), source_path),
        encoding="utf-8",
    )
    return header_path, source_path


def generate_main_c(
    init_order: InitOrder,
    graph: DependencyGraph,
    out_dir: Path,
    include_tests: bool = False,
    manifest: dict = None,
    generation_profile: Optional[Dict[str, Any]] = None,
    board_data: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
    api_contract_manifest: Optional[Dict[str, Any]] = None,
) -> Path:
    """
    Generate main.c with correct initialization sequence and optional test harness.

    Args:
        init_order: Resolved initialization order
        graph: Dependency graph (for metadata)
        out_dir: Output directory
        include_tests: If True, generate test harness code
        manifest: BSP manifest with API catalog (required for test generation)
        generation_profile: Optional generation profile dict
        board_data: Optional board.yaml data for LED/pin defaults
        api_contract_manifest: Optional normalized API contract manifest

    Returns:
        Path to generated main.c
    """
    if not init_order.is_valid():
        raise ValueError(f"Cannot generate main.c: {init_order}")

    lines = []
    validation_mode = _should_generate_bsp_validation(generation_profile, manifest)
    if validation_mode:
        _generate_bsp_validate_module(
            out_dir,
            generation_profile,
            board_data,
            bringup_contract=bringup_contract,
            api_contract_manifest=api_contract_manifest,
        )

    # Header
    lines.append("/**")
    lines.append(" * @file main.c")
    if validation_mode:
        lines.append(" * @brief Main entry for auto-generated BSP runtime validation mode")
    else:
        lines.append(" * @brief Main application entry point with auto-generated initialization sequence")
    lines.append(" *")
    lines.append(" * This file was auto-generated by the BSP Generator.")
    if validation_mode:
        lines.append(" * Runtime behavior is delegated to BSP_ValidateInit/BSP_ValidateStep.")
    else:
        lines.append(" * Initialization order is based on dependency analysis.")
    lines.append(" */")
    lines.append("")
    lines.append("#include <stdint.h>")
    lines.append("#include <stddef.h>")
    if validation_mode:
        lines.append("#include \"bsp_validate.h\"")
    lines.append("")

    if not validation_mode:
        # Include headers for each module
        lines.append("// Module headers")
        for module_name in init_order.order:
            node = graph.get_node(module_name)
            if not node:
                continue

            if node.module_type == "system":
                lines.append("#include \"system.h\"")
            elif node.module_type == "pll":
                lines.append("#include \"pll_driver.h\"")
            elif node.module_type == "vim":
                lines.append("#include \"vim_driver.h\"")
            else:
                # Peripheral driver
                header_name = f"{module_name.lower()}_driver.h"
                lines.append(f"#include \"{header_name}\"")

        lines.append("")

    # Generate test harness if requested
    if include_tests and manifest and not validation_mode:
        from ..testing.bsp_test_generator import TestGenerator

        test_gen = TestGenerator()
        tests = test_gen.generate_tests(manifest, init_order.order)
        test_code = test_gen.generate_test_code(tests)
        lines.extend(test_code)

    lines.append("/**")
    lines.append(" * @brief Main application entry point")
    lines.append(" *")
    if validation_mode:
        lines.append(" * Enters generated BSP validation loop for terminal/UART smoke test.")
    else:
        lines.append(" * Initializes all BSP modules in dependency order:")

    if not validation_mode:
        # Document init order
        for i, module_name in enumerate(init_order.order, 1):
            node = graph.get_node(module_name)
            deps_str = ", ".join(node.dependencies) if node and node.dependencies else "none"
            lines.append(f" * {i}. {module_name} (dependencies: {deps_str})")

    lines.append(" *")
    lines.append(" * @return Never returns (infinite loop)")
    lines.append(" */")
    lines.append("int main(void)")
    lines.append("{")

    if validation_mode:
        lines.append("    BSP_ValidateInit();")
        lines.append("")
        lines.append("    while (1)")
        lines.append("    {")
        lines.append("        BSP_ValidateStep();")
        lines.append("    }")
    else:
        # Initialization sequence
        lines.append("    /* ===== BSP Initialization Sequence ===== */")
        lines.append("    /* Auto-generated based on dependency analysis */")
        lines.append("")

        for module_name in init_order.order:
            node = graph.get_node(module_name)
            if not node:
                continue

            # Add comment with dependencies
            if node.dependencies:
                deps_str = ", ".join(node.dependencies)
                lines.append(f"    /* Initialize {module_name} (depends on: {deps_str}) */")
            else:
                lines.append(f"    /* Initialize {module_name} (no dependencies) */")

            init_func = node.init_function
            if not init_func.endswith("()"):
                init_func += "()"

            # Check if this is a core system module or peripheral
            if module_name.upper() in CORE_SYSTEM_MODULES:
                # Core system - always call directly
                lines.append(f"    {init_func};")
            else:
                # Peripheral - add EnablePins comment prompts if available
                enable_pins_funcs = find_enable_pins_functions(manifest, module_name)

                if enable_pins_funcs:
                    lines.append("")
                    lines.append(f"    /* TODO: Configure pins for {module_name} before use */")
                    lines.append(f"    /* Uncomment the appropriate EnablePins function(s): */")

                    for func in enable_pins_funcs:
                        func_name = func.get('name', '')
                        func_brief = func.get('brief', '')

                        lines.append(f"    /* - {func_name}(); */")
                        if func_brief:
                            lines.append(f"    /*     {func_brief} */")

                    lines.append(f"    /* Then uncomment the init function: */")
                    lines.append(f"    /* {init_func}; */")
                else:
                    # No EnablePins functions - just comment out init
                    lines.append(f"    /* TODO: Uncomment to enable {module_name} */")
                    lines.append(f"    /* {init_func}; */")

            lines.append("")

        lines.append("    /* ===== Application Code ===== */")
        lines.append("    /* TODO: Add your application logic here */")
        lines.append("")

        if include_tests:
            lines.append("    /* Run BSP tests (if enabled) */")
            lines.append("    #ifdef BSP_RUN_TESTS")
            lines.append("    uint32_t failures = BSP_RunTests();")
            lines.append("    // Inspect 'failures' variable in debugger")
            lines.append("    #endif")
            lines.append("")

        lines.append("    /* Main loop */")
        lines.append("    while (1)")
        lines.append("    {")
        lines.append("        /* Application main loop */")
        lines.append("        /* TODO: Add periodic tasks, event handling, etc. */")
        lines.append("    }")

    lines.append("")
    lines.append("    return 0; /* Never reached */")
    lines.append("}")
    lines.append("")

    # Write to file
    main_c_path = out_dir / "main.c"
    main_c_path.write_text(
        normalize_generated_text("\n".join(lines), main_c_path),
        encoding="utf-8",
    )

    logger.info(f"Generated main.c with {len(init_order.order)} init calls")
    return main_c_path


def detect_circular_dependencies(graph: DependencyGraph) -> Optional[List[str]]:
    """
    Detect if circular dependencies exist in the graph.

    Returns:
        List of nodes involved in cycle, or None if no cycle
    """
    init_order = generate_init_order(graph)
    if init_order.has_cycles:
        return init_order.cycle_nodes
    return None


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def print_dependency_graph(graph: DependencyGraph) -> None:
    """
    Print dependency graph in human-readable format.
    """
    print("\n===== Dependency Graph =====")
    print(graph)
    print("============================\n")


def print_init_order(init_order: InitOrder) -> None:
    """
    Print initialization order in human-readable format.
    """
    print("\n===== Initialization Order =====")
    print(init_order)
    print("================================\n")
