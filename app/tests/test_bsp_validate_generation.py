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


def test_generate_main_c_bsp_validation_overrides(tmp_path: Path):
    graph, order = _graph_with_rm46_modules()
    manifest = {"api_catalog": {"SYSTEM": {}, "GIO": {}, "SCI": {}, "LIN": {}, "PLL": {}, "IOMM": {}, "VIM": {}, "PCR": {}}}
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "bsp_validation": {
            "enabled": True,
            "baud": 19200,
            "banners": {
                "sci": "SCI custom\\r\\n",
                "lin": "LIN custom\\r\\n",
            },
            "timing": {
                "heartbeat_ticks": 250,
                "tx_period_ticks": 75,
                "busy_delay": 10,
            },
            "frame": {
                "data_bits": 8,
                "stop_bits": 2,
                "parity": "even",
            },
        },
    }

    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile=profile,
        board_data={},
    )

    bsp_c_text = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "BSP_VALIDATE_BAUD              (19200U)" in bsp_c_text
    assert "BSP_VALIDATE_HEARTBEAT_TICKS   (250U)" in bsp_c_text
    assert "BSP_VALIDATE_TX_PERIOD_TICKS   (75U)" in bsp_c_text
    assert "BSP_VALIDATE_BUSY_DELAY        (10U)" in bsp_c_text
    assert "SCI custom" in bsp_c_text
    assert "LIN custom" in bsp_c_text
    assert "SCI custom\\r\\n" in bsp_c_text
    assert "LIN custom\\r\\n" in bsp_c_text
    assert "SCI custom\\\\r\\\\n" not in bsp_c_text
    assert "LIN custom\\\\r\\\\n" not in bsp_c_text


def test_generate_main_c_lin_only_primary_path_disables_sci_tx(tmp_path: Path):
    graph, order = _graph_with_rm46_modules()
    manifest = {"api_catalog": {"SYSTEM": {}, "GIO": {}, "SCI": {}, "LIN": {}, "PLL": {}, "IOMM": {}, "VIM": {}, "PCR": {}}}
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "bsp_validation": {
            "enabled": True,
            "primary_serial_path": "lin_only",
        },
    }
    bringup_contract = {
        "serial": {
            "primary_path": "LIN_SCI_MODE",
            "primary_tx_only": "LIN",
            "baud_default": 9600,
            "required_pins": [],
        }
    }
    api_contract_manifest = {
        "modules": {
            "IOMM": {
                "functions": {"IOMM_Init": {"arity": 0}, "IOMM_ConfigurePin": {"arity": 2}},
                "types": {"iomm_pin_function_t": {"kind": "enum", "values": ["IOMM_FUNC_GPIO", "IOMM_FUNC_ALT1"]}},
            },
            "GIO": {
                "functions": {"GIO_Init": {"arity": 0}, "GIO_WritePin": {"arity": 3}, "GIO_TogglePin": {"arity": 2}},
                "capabilities": {"write_pin": "GIO_WritePin", "toggle_pin": "GIO_TogglePin"},
                "types": {"gio_port_t": {"kind": "enum", "values": ["GIO_PORT_A", "GIO_PORT_B"]}, "gio_pin_config_t": {"fields": []}},
            },
            "LIN": {
                "functions": {"LIN_Init": {"arity": 1}, "LIN_SendByte": {"arity": 1}, "LIN_IsTxReady": {"arity": 0}},
                "capabilities": {"init": "LIN_Init", "tx_byte": "LIN_SendByte", "tx_ready": "LIN_IsTxReady"},
                "types": {"lin_mode_t": {"kind": "enum", "values": ["LIN_MODE_SCI"]}, "lin_config_t": {"fields": [{"name": "mode"}]}},
            },
            "SCI": {
                "functions": {"SCI_Init": {"arity": 1}, "SCI_SendByte": {"arity": 1}, "SCI_IsTxReady": {"arity": 0}},
                "capabilities": {"init": "SCI_Init", "tx_byte": "SCI_SendByte", "tx_ready": "SCI_IsTxReady"},
                "types": {"sci_config_t": {"fields": [{"name": "baud_rate"}]}},
            },
        }
    }

    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile=profile,
        board_data={},
        bringup_contract=bringup_contract,
        api_contract_manifest=api_contract_manifest,
    )

    bsp_c_text = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "LIN path active (B)" in bsp_c_text
    assert "SCI path active (A)" not in bsp_c_text
    assert "g_validate_sci_tx_ok++" not in bsp_c_text
    assert "g_validate_lin_tx_ok++" in bsp_c_text


def test_generate_main_c_uses_sci_write_family_when_send_family_missing(tmp_path: Path):
    graph, order = _graph_with_rm46_modules()
    manifest = {"api_catalog": {"SYSTEM": {}, "GIO": {}, "SCI": {}, "LIN": {}, "PLL": {}, "IOMM": {}, "VIM": {}, "PCR": {}}}
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "bsp_validation": {
            "enabled": True,
            "primary_serial_path": "sci_only",
        },
    }
    api_contract_manifest = {
        "modules": {
            "IOMM": {
                "functions": {"IOMM_Init": {"arity": 0}, "IOMM_ConfigurePin": {"arity": 2}},
                "types": {"iomm_pin_function_t": {"kind": "enum", "values": ["IOMM_PIN_FUNCTION_0", "IOMM_PIN_FUNCTION_1"]}},
            },
            "GIO": {
                "functions": {"GIO_Init": {"arity": 0}, "GIO_WritePin": {"arity": 3}, "GIO_TogglePin": {"arity": 2}},
                "capabilities": {"write_pin": "GIO_WritePin", "toggle_pin": "GIO_TogglePin"},
                "types": {"gio_port_t": {"kind": "enum", "values": ["GIO_PORT_A", "GIO_PORT_B"]}, "gio_pin_config_t": {"fields": []}},
            },
            "SCI": {
                "functions": {
                    "SCI_Init": {"arity": 1},
                    "SCI_Write": {"arity": 2},
                    "SCI_WriteByte": {"arity": 1},
                    "SCI_ReadByte": {"arity": 1},
                    "SCI_IsTxReady": {"arity": 0},
                    "SCI_IsRxReady": {"arity": 0},
                },
                "types": {"sci_config_t": {"fields": [{"name": "baud_rate"}, {"name": "enable_tx"}, {"name": "enable_rx"}]}},
            },
            "LIN": {
                "functions": {"LIN_Init": {"arity": 1}},
                "types": {"lin_config_t": {"fields": []}},
            },
        }
    }

    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile=profile,
        board_data={},
        api_contract_manifest=api_contract_manifest,
    )

    bsp_c_text = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "SCI_Write(sci_banner" in bsp_c_text
    assert "(void)SCI_WriteByte('A');" in bsp_c_text
    assert "if (SCI_IsRxReady())" in bsp_c_text
    assert "if (SCI_ReadByte(&rx_byte) == SCI_STATUS_OK)" in bsp_c_text


def test_generate_main_c_supports_lin_get_ready_and_data_length(tmp_path: Path):
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
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "bsp_validation": {"enabled": True},
    }
    api_contract_manifest = {
        "modules": {
            "IOMM": {
                "functions": {
                    "IOMM_Init": {"arity": 0},
                    "IOMM_ConfigurePin": {"arity": 2},
                },
                "types": {
                    "iomm_pin_function_t": {
                        "kind": "enum",
                        "values": ["IOMM_FUNC_GPIO", "IOMM_FUNC_ALT1", "IOMM_FUNC_ALT2"],
                    }
                },
            },
            "GIO": {
                "functions": {
                    "GIO_Init": {"arity": 0},
                    "GIO_ConfigurePin": {"arity": 1},
                    "GIO_WritePin": {"arity": 3},
                    "GIO_TogglePin": {"arity": 2},
                },
                "capabilities": {
                    "configure_pin": "GIO_ConfigurePin",
                    "configure_pin_arity": 1,
                    "write_pin": "GIO_WritePin",
                    "toggle_pin": "GIO_TogglePin",
                },
                "types": {
                    "gio_pin_config_t": {
                        "fields": [
                            {"name": "direction", "type": "gio_direction_t"},
                            {"name": "pull_mode", "type": "gio_pull_mode_t"},
                            {"name": "port", "type": "gio_port_t"},
                            {"name": "pin", "type": "uint32_t"},
                        ]
                    },
                    "gio_direction_t": {"kind": "enum", "values": ["GIO_PIN_INPUT", "GIO_PIN_OUTPUT"]},
                    "gio_pull_mode_t": {"kind": "enum", "values": ["GIO_PULL_DISABLE", "GIO_PULL_ENABLE"]},
                    "gio_port_t": {"kind": "enum", "values": ["GIO_PORT_A", "GIO_PORT_B"]},
                },
            },
            "SCI": {
                "functions": {
                    "SCI_Init": {"arity": 1},
                    "SCI_Send": {"arity": 2},
                    "SCI_SendByte": {"arity": 1},
                    "SCI_ReceiveByte": {"arity": 1},
                    "SCI_IsTxReady": {"arity": 0},
                    "SCI_IsRxReady": {"arity": 0},
                },
                "types": {
                    "sci_config_t": {
                        "fields": [
                            {"name": "baud_rate", "type": "uint32_t"},
                            {"name": "data_bits", "type": "sci_databits_t"},
                            {"name": "parity", "type": "sci_parity_t"},
                            {"name": "stop_bits", "type": "sci_stopbits_t"},
                            {"name": "enable_loopback", "type": "bool"},
                            {"name": "enable_dma_tx", "type": "bool"},
                            {"name": "enable_dma_rx", "type": "bool"},
                        ]
                    },
                    "sci_databits_t": {"kind": "enum", "values": ["SCI_DATABITS_7", "SCI_DATABITS_8"]},
                    "sci_parity_t": {"kind": "enum", "values": ["SCI_PARITY_NONE", "SCI_PARITY_EVEN", "SCI_PARITY_ODD"]},
                    "sci_stopbits_t": {"kind": "enum", "values": ["SCI_STOPBITS_1", "SCI_STOPBITS_2"]},
                },
            },
            "LIN": {
                "functions": {
                    "LIN_Init": {"arity": 1},
                    "LIN_SendData": {"arity": 2},
                    "LIN_SendByte": {"arity": 1},
                    "LIN_ReceiveByte": {"arity": 1},
                    "LIN_GetTxReady": {"arity": 0},
                    "LIN_GetRxReady": {"arity": 0},
                },
                "types": {
                    "lin_mode_t": {"kind": "enum", "values": ["LIN_MODE_SCI", "LIN_MODE_LIN"]},
                    "lin_parity_t": {"kind": "enum", "values": ["LIN_PARITY_NONE", "LIN_PARITY_EVEN", "LIN_PARITY_ODD"]},
                    "lin_stop_bits_t": {"kind": "enum", "values": ["LIN_STOP_BITS_1", "LIN_STOP_BITS_2"]},
                    "lin_data_length_t": {
                        "kind": "enum",
                        "values": [
                            "LIN_DATA_LENGTH_1",
                            "LIN_DATA_LENGTH_2",
                            "LIN_DATA_LENGTH_3",
                            "LIN_DATA_LENGTH_4",
                            "LIN_DATA_LENGTH_5",
                            "LIN_DATA_LENGTH_6",
                            "LIN_DATA_LENGTH_7",
                            "LIN_DATA_LENGTH_8",
                        ],
                    },
                    "lin_config_t": {
                        "fields": [
                            {"name": "mode", "type": "lin_mode_t"},
                            {"name": "baud_rate", "type": "uint32_t"},
                            {"name": "data_length", "type": "lin_data_length_t"},
                            {"name": "parity", "type": "lin_parity_t"},
                            {"name": "stop_bits", "type": "lin_stop_bits_t"},
                            {"name": "enable_loopback", "type": "bool"},
                            {"name": "enable_dma_tx", "type": "bool"},
                            {"name": "enable_dma_rx", "type": "bool"},
                        ]
                    },
                },
            },
        }
    }

    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile=profile,
        board_data={},
        api_contract_manifest=api_contract_manifest,
    )

    bsp_c_text = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "lin_cfg.data_length = LIN_DATA_LENGTH_8;" in bsp_c_text
    assert "if (LIN_GetRxReady())" in bsp_c_text
    assert "if (LIN_GetTxReady())" in bsp_c_text
    assert "(void)LIN_SendByte('B');" in bsp_c_text


def test_generate_main_c_sets_lin_pin_config_functional_mode_fields(tmp_path: Path):
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
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "bsp_validation": {"enabled": True},
    }
    api_contract_manifest = {
        "modules": {
            "IOMM": {
                "functions": {"IOMM_Init": {"arity": 0}, "IOMM_ConfigurePin": {"arity": 2}},
                "types": {"iomm_pin_function_t": {"kind": "enum", "values": ["IOMM_PIN_FUNCTION_0", "IOMM_PIN_FUNCTION_1"]}},
            },
            "GIO": {
                "functions": {"GIO_Init": {"arity": 0}, "GIO_ConfigurePin": {"arity": 1}, "GIO_WritePin": {"arity": 3}, "GIO_TogglePin": {"arity": 2}},
                "capabilities": {"configure_pin": "GIO_ConfigurePin", "configure_pin_arity": 1, "write_pin": "GIO_WritePin", "toggle_pin": "GIO_TogglePin"},
                "types": {
                    "gio_pin_config_t": {"fields": [{"name": "direction"}, {"name": "pull_mode"}, {"name": "port"}, {"name": "pin"}]},
                    "gio_direction_t": {"kind": "enum", "values": ["GIO_DIR_INPUT", "GIO_DIR_OUTPUT"]},
                    "gio_pull_mode_t": {"kind": "enum", "values": ["GIO_PULL_DISABLE"]},
                    "gio_port_t": {"kind": "enum", "values": ["GIO_PORT_A", "GIO_PORT_B"]},
                },
            },
            "SCI": {
                "functions": {
                    "SCI_Init": {"arity": 1},
                    "SCI_SendData": {"arity": 2},
                    "SCI_SendByte": {"arity": 1},
                    "SCI_ReceiveByte": {"arity": 1},
                    "SCI_IsTxReady": {"arity": 0},
                    "SCI_IsRxReady": {"arity": 0},
                },
                "capabilities": {
                    "init": "SCI_Init",
                    "tx_buffer": "SCI_SendData",
                    "tx_byte": "SCI_SendByte",
                    "rx_byte": "SCI_ReceiveByte",
                    "tx_ready": "SCI_IsTxReady",
                    "rx_ready": "SCI_IsRxReady",
                },
                "types": {
                    "sci_config_t": {
                        "fields": [
                            {"name": "baud_rate"},
                            {"name": "data_bits"},
                            {"name": "parity"},
                            {"name": "stop_bits"},
                            {"name": "enable_tx"},
                            {"name": "enable_rx"},
                        ]
                    }
                },
            },
            "LIN": {
                "functions": {
                    "LIN_Init": {"arity": 1},
                    "LIN_Send": {"arity": 2},
                    "LIN_SendByte": {"arity": 1},
                    "LIN_ReceiveByte": {"arity": 1},
                    "LIN_IsTxReady": {"arity": 0},
                    "LIN_IsRxReady": {"arity": 0},
                },
                "capabilities": {
                    "init": "LIN_Init",
                    "tx_buffer": "LIN_Send",
                    "tx_byte": "LIN_SendByte",
                    "rx_byte": "LIN_ReceiveByte",
                    "tx_ready": "LIN_IsTxReady",
                    "rx_ready": "LIN_IsRxReady",
                },
                "types": {
                    "lin_mode_t": {"kind": "enum", "values": ["LIN_MODE_SCI"]},
                    "lin_parity_t": {"kind": "enum", "values": ["LIN_PARITY_NONE"]},
                    "lin_stop_bits_t": {"kind": "enum", "values": ["LIN_STOP_BITS_1"]},
                    "lin_config_t": {
                        "fields": [
                            {"name": "mode"},
                            {"name": "baud_rate"},
                            {"name": "data_bits"},
                            {"name": "parity"},
                            {"name": "stop_bits"},
                            {"name": "pin_config", "type": "lin_pin_config_t"},
                            {"name": "enable_tx"},
                            {"name": "enable_rx"},
                            {"name": "use_dma"},
                        ]
                    },
                    "lin_pin_config_t": {
                        "fields": [
                            {"name": "tx_func_mode"},
                            {"name": "rx_func_mode"},
                            {"name": "open_drain"},
                            {"name": "pull_enable"},
                            {"name": "pull_select"},
                        ]
                    },
                },
            },
        }
    }

    generate_main_c(
        order,
        graph,
        tmp_path,
        include_tests=False,
        manifest=manifest,
        generation_profile=profile,
        board_data={},
        api_contract_manifest=api_contract_manifest,
    )

    bsp_c_text = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "lin_cfg.pin_config.tx_func_mode = true;" in bsp_c_text
    assert "lin_cfg.pin_config.rx_func_mode = true;" in bsp_c_text
    assert "lin_cfg.pin_config.open_drain = false;" in bsp_c_text
    assert "lin_cfg.pin_config.pull_enable = false;" in bsp_c_text
