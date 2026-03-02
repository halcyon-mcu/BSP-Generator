from pathlib import Path

from modules.utils.dependency_resolver import (
    DependencyGraph,
    DependencyNode,
    InitOrder,
    generate_main_c,
)


def _graph() -> tuple[DependencyGraph, InitOrder]:
    graph = DependencyGraph()
    graph.add_node(DependencyNode("SYSTEM", [], "system_init", "system"))
    graph.add_node(DependencyNode("PCR", ["SYSTEM"], "PCR_Init", "pcr"))
    graph.add_node(DependencyNode("IOMM", ["PCR"], "IOMM_Init", "pinmux"))
    graph.add_node(DependencyNode("PLL", ["SYSTEM"], "PLL_Init", "pll"))
    graph.add_node(DependencyNode("VIM", ["SYSTEM"], "vim_init", "vim"))
    graph.add_node(DependencyNode("GIO", ["VIM", "IOMM"], "GIO_Init", "peripheral"))
    graph.add_node(DependencyNode("SCI", ["IOMM", "PLL"], "SCI_Init", "peripheral"))
    graph.add_node(DependencyNode("LIN", ["IOMM", "PLL", "VIM"], "LIN_Init", "peripheral"))
    order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "GIO", "SCI", "LIN"])
    return graph, order


def _manifest() -> dict:
    return {
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


def test_main_defaults_to_direct_init_mode(tmp_path: Path):
    graph, order = _graph()
    profile = {"target_board": "LAUNCHXL2-TMS57012-RM46"}
    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=_manifest(),
        generation_profile=profile,
        board_data={},
        api_contract_manifest={},
    )

    main_c = (tmp_path / "main.c").read_text(encoding="utf-8")
    assert "BSP_ValidateInit()" not in main_c
    assert "system_init()" in main_c
    assert not (tmp_path / "bsp_validate.c").exists()


def test_main_uses_validation_mode_when_bringup_mode_requests_it(tmp_path: Path):
    graph, order = _graph()
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "bringup_mode": {"default": "validation"},
    }
    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=_manifest(),
        generation_profile=profile,
        board_data={},
        api_contract_manifest={},
    )

    main_c = (tmp_path / "main.c").read_text(encoding="utf-8")
    assert "BSP_ValidateInit();" in main_c
    assert (tmp_path / "bsp_validate.c").exists()


def test_explicit_bsp_validation_toggle_overrides_bringup_mode(tmp_path: Path):
    graph, order = _graph()
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "bringup_mode": {"default": "direct_init"},
        "bsp_validation": {"enabled": True},
    }
    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=_manifest(),
        generation_profile=profile,
        board_data={},
        api_contract_manifest={},
    )

    main_c = (tmp_path / "main.c").read_text(encoding="utf-8")
    assert "BSP_ValidateInit();" in main_c
    assert (tmp_path / "bsp_validate.c").exists()
