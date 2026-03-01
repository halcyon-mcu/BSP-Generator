"""
Unit tests for auto-generated BSP validation module/main wiring.
"""

from pathlib import Path

from modules.utils.dependency_resolver import (
    DependencyGraph,
    DependencyNode,
    InitOrder,
    generate_main_c,
)


def _graph_with_rm46_modules() -> tuple[DependencyGraph, InitOrder]:
    graph = DependencyGraph()
    graph.add_node(DependencyNode("SYSTEM", [], "system_init", "system"))
    graph.add_node(DependencyNode("PCR", ["SYSTEM"], "PCR_Init", "pcr"))
    graph.add_node(DependencyNode("IOMM", ["PCR"], "IOMM_Init", "pinmux"))
    graph.add_node(DependencyNode("PLL", ["SYSTEM"], "PLL_Init", "pll"))
    graph.add_node(DependencyNode("VIM", ["SYSTEM"], "vim_init", "vim"))
    graph.add_node(DependencyNode("GIO", ["VIM", "IOMM"], "GIO_Init", "peripheral"))
    graph.add_node(DependencyNode("SCI", ["IOMM", "PLL"], "SCI_Init", "peripheral"))
    graph.add_node(DependencyNode("LIN", ["IOMM", "PLL", "VIM"], "LIN_Init", "peripheral"))

    order = InitOrder(
        order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "GIO", "SCI", "LIN"],
        has_cycles=False,
        cycle_nodes=[],
    )
    return graph, order


def test_generate_main_c_emits_bsp_validate_mode(tmp_path: Path):
    graph, order = _graph_with_rm46_modules()

    manifest = {
        "api_catalog": {
            "SYSTEM": {},
            "PCR": {},
            "IOMM": {},
            "PLL": {},
            "VIM": {},
            "GIO": {},
            "SCI": {},
            "LIN": {},
        }
    }
    generation_profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "sci": {"default_baud": 9600},
        "bsp_validation": {"enabled": True},
    }
    board_data = {"leds": [{"function": "USER LED", "gpio": "GIOB[1]"}]}

    main_c = generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile=generation_profile,
        board_data=board_data,
    )

    assert main_c.exists()
    main_text = main_c.read_text(encoding="utf-8")
    assert '#include "bsp_validate.h"' in main_text
    assert "BSP_ValidateInit();" in main_text
    assert "BSP_ValidateStep();" in main_text
    assert "TODO: Configure pins" not in main_text

    bsp_h = tmp_path / "bsp_validate.h"
    bsp_c = tmp_path / "bsp_validate.c"
    assert bsp_h.exists()
    assert bsp_c.exists()

    bsp_c_text = bsp_c.read_text(encoding="utf-8")
    assert "LIN path active (B)" in bsp_c_text
    assert "SCI path active (A)" in bsp_c_text
    assert "BSP_VALIDATE_BAUD              (9600U)" in bsp_c_text


def test_generate_main_c_default_mode_unchanged(tmp_path: Path):
    graph, order = _graph_with_rm46_modules()
    manifest = {"api_catalog": {"SYSTEM": {}, "GIO": {}, "SCI": {}, "LIN": {}}}

    main_c = generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile={"target_board": "GENERIC-BOARD", "modules": {"enabled": ["GIO"]}},
        board_data={},
    )

    text = main_c.read_text(encoding="utf-8")
    assert '#include "bsp_validate.h"' not in text
    assert "Auto-generated based on dependency analysis" in text
    assert "TODO: Add your application logic here" in text
    assert not (tmp_path / "bsp_validate.h").exists()
