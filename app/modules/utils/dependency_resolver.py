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
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

logger = logging.getLogger(__name__)


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
    """
    # SYSTEM has no dependencies (base of dependency tree)
    system_node = DependencyNode(
        name="SYSTEM",
        dependencies=[],
        init_function="system_init",
        module_type="system"
    )
    graph.add_node(system_node)

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
    peripherals = soc_data.get("soc", {}).get("peripherals", [])

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

def generate_main_c(
    init_order: InitOrder,
    graph: DependencyGraph,
    out_dir: Path,
    include_tests: bool = False
) -> Path:
    """
    Generate main.c with correct initialization sequence.

    Args:
        init_order: Resolved initialization order
        graph: Dependency graph (for metadata)
        out_dir: Output directory
        include_tests: If True, add test stubs

    Returns:
        Path to generated main.c
    """
    if not init_order.is_valid():
        raise ValueError(f"Cannot generate main.c: {init_order}")

    lines = []

    # Header
    lines.append("/**")
    lines.append(" * @file main.c")
    lines.append(" * @brief Main application entry point with auto-generated initialization sequence")
    lines.append(" *")
    lines.append(" * This file was auto-generated by the BSP Generator.")
    lines.append(" * Initialization order is based on dependency analysis.")
    lines.append(" */")
    lines.append("")
    lines.append("#include <stdint.h>")
    lines.append("#include <stddef.h>")
    lines.append("")

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
            lines.append("#include \"vim.h\"")
        else:
            # Peripheral driver
            header_name = f"{module_name.lower()}_driver.h"
            lines.append(f"#include \"{header_name}\"")

    lines.append("")
    lines.append("/**")
    lines.append(" * @brief Main application entry point")
    lines.append(" *")
    lines.append(" * Initializes all BSP modules in dependency order:")

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

        # Call init function
        init_func = node.init_function
        if not init_func.endswith("()"):
            init_func += "()"
        lines.append(f"    {init_func};")
        lines.append("")

    lines.append("    /* ===== Application Code ===== */")
    lines.append("    /* TODO: Add your application logic here */")
    lines.append("")

    if include_tests:
        lines.append("    /* Run basic tests (if enabled) */")
        lines.append("    #ifdef BSP_RUN_TESTS")
        lines.append("    // TODO: Call test functions")
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
    main_c_path.write_text("\n".join(lines), encoding="utf-8")

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
