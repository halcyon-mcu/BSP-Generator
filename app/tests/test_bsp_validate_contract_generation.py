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


def test_bsp_validate_generation_uses_contract_fields_and_calls(tmp_path: Path):
    graph, order = _graph()
    manifest = {"api_catalog": {k: {} for k in ["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "GIO", "SCI", "LIN"]}}
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "sci": {"default_baud": 9600},
        "bsp_validation": {"enabled": True},
    }
    contract = {
        "modules": {
            "SCI": {
                "functions": {
                    "SCI_SendData": {"arity": 2},
                    "SCI_SendByte": {"arity": 1},
                    "SCI_ReceiveByte": {"arity": 1},
                    "SCI_GetRxStatus": {"arity": 0},
                    "SCI_GetTxStatus": {"arity": 0},
                },
                "capabilities": {
                    "tx_buffer": "SCI_SendData",
                    "tx_byte": "SCI_SendByte",
                    "rx_byte": "SCI_ReceiveByte",
                    "rx_ready": "SCI_GetRxStatus",
                    "tx_ready": "SCI_GetTxStatus",
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
                "compatibility_wrappers": [],
            },
            "GIO": {
                "functions": {
                    "GIO_ConfigurePin": {"arity": 3},
                    "GIO_WritePin": {"arity": 3},
                    "GIO_TogglePin": {"arity": 2},
                },
                "capabilities": {
                    "configure_pin": "GIO_ConfigurePin",
                    "configure_pin_arity": 3,
                    "write_pin": "GIO_WritePin",
                    "toggle_pin": "GIO_TogglePin",
                },
                "types": {
                    "gio_port_t": {"values": ["GIO_PORT_A", "GIO_PORT_B"]},
                    "gio_pin_direction_t": {"values": ["GIO_DIR_INPUT", "GIO_DIR_OUTPUT"]},
                    "gio_pin_mode_t": {"values": ["GIO_MODE_PUSH_PULL"]},
                    "gio_pull_config_t": {"values": ["GIO_PULL_DISABLE"]},
                    "gio_pin_config_t": {
                        "fields": [
                            {"name": "direction"},
                            {"name": "mode"},
                            {"name": "pull"},
                        ]
                    },
                },
                "compatibility_wrappers": [],
            },
            "IOMM": {
                "functions": {
                    "IOMM_ConfigurePin": {"arity": 2},
                },
                "types": {
                    "iomm_pin_function_t": {
                        "values": ["IOMM_PIN_FUNCTION_0", "IOMM_PIN_FUNCTION_1"]
                    }
                },
                "capabilities": {},
                "compatibility_wrappers": [],
            },
            "LIN": {
                "functions": {
                    "LIN_Init": {"arity": 1},
                    "LIN_Transmit": {"arity": 2},
                    "LIN_TransmitByte": {"arity": 1},
                    "LIN_ReceiveByte": {"arity": 2},
                    "LIN_GetRxStatus": {"arity": 0},
                    "LIN_GetTxStatus": {"arity": 0},
                },
                "capabilities": {
                    "tx_buffer": "LIN_Transmit",
                    "tx_byte": "LIN_TransmitByte",
                    "rx_byte": "LIN_ReceiveByte",
                    "rx_byte_arity": 2,
                    "rx_ready": "LIN_GetRxStatus",
                    "tx_ready": "LIN_GetTxStatus",
                },
                "types": {
                    "lin_mode_t": {"values": ["LIN_MODE_SCI"]},
                    "lin_parity_t": {"values": ["LIN_PARITY_NONE"]},
                    "lin_stopbits_t": {"values": ["LIN_STOPBITS_1"]},
                    "lin_data_bits_t": {"values": ["LIN_DATA_BITS_8"]},
                    "lin_config_t": {
                        "fields": [
                            {"name": "mode"},
                            {"name": "baud_rate"},
                            {"name": "data_bits"},
                            {"name": "parity"},
                            {"name": "stop_bits"},
                            {"name": "enable_loopback"},
                            {"name": "enable_multibuffer"},
                            {"name": "tx_dma_enable"},
                            {"name": "rx_dma_enable"},
                        ]
                    },
                },
                "compatibility_wrappers": [{"name": "LIN_SendData", "arity": 2}],
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
        api_contract_manifest=contract,
    )

    bsp_validate = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "lin_cfg.data_length" not in bsp_validate
    assert "lin_cfg.enable_rx" not in bsp_validate
    assert "LIN_SendData(" not in bsp_validate
    assert "LIN_Transmit(" in bsp_validate
    assert "LIN_TransmitByte(" in bsp_validate
    assert "LIN_ReceiveByte(&rx_byte, 0U)" in bsp_validate
    assert "IOMM_PIN_FUNCTION_1" in bsp_validate
    assert "sci_cfg.enable_tx = true;" in bsp_validate
    assert "sci_cfg.enable_rx = true;" in bsp_validate
    assert "SCI_GetTxStatus()" in bsp_validate
    assert "SCI_GetRxStatus()" in bsp_validate
    assert "LIN_GetTxStatus()" in bsp_validate
    assert "LIN_GetRxStatus()" in bsp_validate
    assert "lin_cfg.stop_bits = LIN_STOPBITS_1;" in bsp_validate


def test_bsp_validate_generation_uses_byte_loop_when_lin_tx_buffer_missing(tmp_path: Path):
    graph, order = _graph()
    manifest = {"api_catalog": {k: {} for k in ["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "GIO", "SCI", "LIN"]}}
    profile = {
        "target_board": "LAUNCHXL2-TMS57012-RM46",
        "modules": {"enabled": ["SCI", "GIO", "LIN", "PLL", "IOMM", "PCR", "SYSTEM", "VIM"]},
        "sci": {"default_baud": 9600},
        "bsp_validation": {"enabled": True},
    }
    contract = {
        "modules": {
            "SCI": {
                "functions": {
                    "SCI_SendData": {"arity": 2},
                    "SCI_SendByte": {"arity": 1},
                    "SCI_ReceiveByte": {"arity": 1},
                    "SCI_IsRxReady": {"arity": 0},
                    "SCI_IsTxReady": {"arity": 0},
                    "SCI_Init": {"arity": 1},
                },
                "capabilities": {
                    "tx_buffer": "SCI_SendData",
                    "tx_byte": "SCI_SendByte",
                    "rx_byte": "SCI_ReceiveByte",
                    "rx_ready": "SCI_IsRxReady",
                    "tx_ready": "SCI_IsTxReady",
                    "init": "SCI_Init",
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
                "compatibility_wrappers": [],
            },
            "GIO": {
                "functions": {
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
                    "gio_port_t": {"values": ["GIO_PORT_A", "GIO_PORT_B"]},
                    "gio_pin_direction_t": {"values": ["GIO_DIR_INPUT", "GIO_DIR_OUTPUT"]},
                    "gio_pull_mode_t": {"values": ["GIO_PULL_DISABLE"]},
                    "gio_pin_config_t": {
                        "fields": [
                            {"name": "direction"},
                            {"name": "pull_mode"},
                            {"name": "port"},
                            {"name": "pin"},
                        ]
                    },
                },
                "compatibility_wrappers": [],
            },
            "IOMM": {
                "functions": {
                    "IOMM_ConfigurePin": {"arity": 2},
                },
                "types": {
                    "iomm_pin_function_t": {
                        "values": ["IOMM_FUNC_GPIO", "IOMM_FUNC_ALT1"]
                    }
                },
                "capabilities": {},
                "compatibility_wrappers": [],
            },
            "LIN": {
                "functions": {
                    "LIN_Init": {"arity": 1},
                    "LIN_SendByte": {"arity": 1},
                    "LIN_ReceiveByte": {"arity": 1},
                    "LIN_IsRxReady": {"arity": 0},
                    "LIN_IsTxReady": {"arity": 0},
                },
                "capabilities": {
                    "init": "LIN_Init",
                    "tx_byte": "LIN_SendByte",
                    "rx_byte": "LIN_ReceiveByte",
                    "rx_byte_arity": 1,
                    "rx_ready": "LIN_IsRxReady",
                    "tx_ready": "LIN_IsTxReady",
                },
                "types": {
                    "lin_mode_t": {"values": ["LIN_MODE_SCI"]},
                    "lin_parity_t": {"values": ["LIN_PARITY_NONE"]},
                    "lin_stopbits_t": {"values": ["LIN_STOPBITS_1"]},
                    "lin_databits_t": {"values": ["LIN_DATABITS_8"]},
                    "lin_config_t": {
                        "fields": [
                            {"name": "mode"},
                            {"name": "baud_rate"},
                            {"name": "data_bits"},
                            {"name": "parity"},
                            {"name": "stop_bits"},
                        ]
                    },
                },
                "compatibility_wrappers": [],
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
        api_contract_manifest=contract,
    )

    bsp_validate = (tmp_path / "bsp_validate.c").read_text(encoding="utf-8")
    assert "LIN_SendByte(lin_banner, " not in bsp_validate
    assert "while (lin_banner_idx < (uint32_t)(sizeof(lin_banner) - 1U))" in bsp_validate
    assert "LIN_SendByte(lin_banner[lin_banner_idx]) == LIN_STATUS_OK" in bsp_validate
