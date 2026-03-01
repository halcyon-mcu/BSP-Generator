from pathlib import Path

from modules.contracts.contract_checker import (
    check_bsp_validate_contract,
    check_generated_module_contract,
)


def _write(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _lin_contract():
    return {
        "modules": {
            "LIN": {
                "functions": {
                    "LIN_ReceiveByte": {"arity": 2},
                    "LIN_Send": {"arity": 2},
                    "LIN_Init": {"arity": 1},
                },
                "types": {
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
                    }
                },
                "compatibility_wrappers": [
                    {"name": "LIN_SendData", "arity": 2},
                ],
            },
            "SCI": {
                "functions": {
                    "SCI_Send": {"arity": 2},
                },
                "types": {},
                "compatibility_wrappers": [],
            },
        }
    }


def test_contract_checker_detects_header_source_drift(tmp_path: Path):
    header = _write(
        tmp_path / "lin_driver.h",
        """
        lin_status_t LIN_ReceiveByte(uint8_t* data);
        lin_status_t LIN_Send(const uint8_t* data, uint32_t length);
        lin_status_t LIN_Init(const lin_config_t* config);
        """,
    )
    source = _write(
        tmp_path / "lin_driver.c",
        """
        lin_status_t LIN_ReceiveByte(uint8_t* data, uint32_t timeout_ms) { (void)timeout_ms; return LIN_STATUS_OK; }
        lin_status_t LIN_Send(const uint8_t* data, uint32_t length) { (void)data; (void)length; return LIN_STATUS_OK; }
        lin_status_t LIN_Init(const lin_config_t* config) { (void)config; return LIN_STATUS_OK; }
        """,
    )

    result = check_generated_module_contract("LIN", header, source, _lin_contract())
    assert result["passed"] is False
    assert any("LIN_ReceiveByte" in err for err in result["errors"])


def test_contract_checker_detects_bsp_validate_invalid_lin_fields(tmp_path: Path):
    bsp_validate = _write(
        tmp_path / "bsp_validate.c",
        """
        void test(void) {
            lin_config_t lin_cfg;
            lin_cfg.data_length = LIN_DATA_8BIT;
            (void)LIN_SendData((const uint8_t*)0, 0U);
        }
        """,
    )

    result = check_bsp_validate_contract(bsp_validate, _lin_contract())
    assert result["passed"] is False
    assert any("lin_cfg.data_length" in err for err in result["errors"])


def test_contract_checker_detects_undeclared_timeout_usage(tmp_path: Path):
    header = _write(
        tmp_path / "lin_driver.h",
        """
        lin_status_t LIN_ReceiveByte(uint8_t* data);
        """,
    )
    source = _write(
        tmp_path / "lin_driver.c",
        """
        lin_status_t LIN_ReceiveByte(uint8_t* data)
        {
            if (timeout_ms == 0U) {
                return LIN_STATUS_OK;
            }
            return LIN_STATUS_TIMEOUT;
        }
        """,
    )

    result = check_generated_module_contract("LIN", header, source, _lin_contract())
    assert result["passed"] is False
    assert any("timeout_ms" in err for err in result["errors"])


def test_contract_checker_ignores_comment_only_function_call_mentions(tmp_path: Path):
    contract = {
        "modules": {
            "GIO": {
                "functions": {
                    "GIO_EnableInterrupt": {"arity": 2},
                    "GIO_ConfigureInterrupt": {"arity": 1},
                },
                "types": {},
                "compatibility_wrappers": [],
            }
        }
    }
    header = _write(
        tmp_path / "gio_driver.h",
        """
        gio_status_t GIO_EnableInterrupt(gio_port_t port, uint8_t pin);
        gio_status_t GIO_ConfigureInterrupt(const gio_interrupt_config_t* config);
        """,
    )
    source = _write(
        tmp_path / "gio_driver.c",
        """
        /*
         * Configure first, then call GIO_EnableInterrupt().
         * Pin must be configured via GIO_ConfigureInterrupt().
         */
        gio_status_t GIO_EnableInterrupt(gio_port_t port, uint8_t pin)
        { (void)port; (void)pin; return GIO_STATUS_OK; }

        gio_status_t GIO_ConfigureInterrupt(const gio_interrupt_config_t* config)
        { (void)config; return GIO_STATUS_OK; }
        """,
    )

    result = check_generated_module_contract("GIO", header, source, contract)
    assert result["passed"] is True
