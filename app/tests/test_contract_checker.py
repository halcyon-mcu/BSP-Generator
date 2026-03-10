from pathlib import Path

from modules.contracts.contract_checker import (
    check_app_intent_init_before_use,
    check_bsp_validate_contract,
    check_generated_module_contract,
    summarize_api_status,
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


def test_contract_checker_requires_lin_pin_config_functional_mode_defaults(tmp_path: Path):
    bsp_validate = _write(
        tmp_path / "bsp_validate.c",
        """
        void test(void) {
            lin_config_t lin_cfg = {0};
            lin_cfg.mode = LIN_MODE_SCI;
            lin_cfg.baud_rate = 9600U;
            lin_cfg.data_bits = 8U;
            lin_cfg.parity = LIN_PARITY_NONE;
            lin_cfg.stop_bits = LIN_STOP_BITS_1;
            g_validate_lin_status = (uint32_t)LIN_Init(&lin_cfg);
        }
        """,
    )

    contract = {
        "modules": {
            "LIN": {
                "functions": {"LIN_Init": {"arity": 1}},
                "types": {
                    "lin_config_t": {
                        "fields": [
                            {"name": "mode"},
                            {"name": "baud_rate"},
                            {"name": "data_bits"},
                            {"name": "parity"},
                            {"name": "stop_bits"},
                            {"name": "pin_config", "type": "lin_pin_config_t"},
                        ]
                    },
                    "lin_pin_config_t": {
                        "fields": [
                            {"name": "tx_func_mode"},
                            {"name": "rx_func_mode"},
                        ]
                    },
                },
                "compatibility_wrappers": [],
            },
            "SCI": {"functions": {}, "types": {}, "compatibility_wrappers": []},
        }
    }

    result = check_bsp_validate_contract(bsp_validate, contract)
    assert result["passed"] is False
    assert any("tx_func_mode" in err for err in result["errors"])
    assert any("rx_func_mode" in err for err in result["errors"])


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


def test_contract_checker_flags_source_defined_public_function_missing_in_header(tmp_path: Path):
    contract = {
        "modules": {
            "LIN": {
                "functions": {
                    "LIN_Init": {"arity": 0},
                },
                "types": {},
                "compatibility_wrappers": [],
            }
        }
    }
    header = _write(
        tmp_path / "lin_driver.h",
        """
        void LIN_Init(void);
        """,
    )
    source = _write(
        tmp_path / "lin_driver.c",
        """
        void LIN_Init(void) { }
        void LIN_EnablePins(void) { }
        """,
    )

    result = check_generated_module_contract("LIN", header, source, contract)
    assert result["passed"] is False
    assert any("LIN_EnablePins" in err and "missing declaration" in err for err in result["errors"])


def test_check_app_intent_init_before_use_detects_missing_init(tmp_path: Path):
    app_intent = _write(
        tmp_path / "app_intent.c",
        """
        void APP_INTENT_Init(void)
        {
            GIO_WritePin(1U, 2U, true);
        }
        """,
    )
    result = check_app_intent_init_before_use(
        app_intent,
        {"GIO": {"init": "GIO_Init", "arity": 0}},
    )
    assert result["passed"] is False
    assert any("GIO_Init" in err for err in result["errors"])


def test_check_app_intent_init_before_use_allows_init_after_use(tmp_path: Path):
    app_intent = _write(
        tmp_path / "app_intent.c",
        """
        void APP_INTENT_Init(void)
        {
            GIO_WritePin(1U, 2U, true);
            GIO_Init();
        }
        """,
    )
    result = check_app_intent_init_before_use(
        app_intent,
        {"GIO": {"init": "GIO_Init", "arity": 0}},
    )
    assert result["passed"] is True
    assert result["errors"] == []


def test_check_app_intent_init_before_use_accepts_init_outside_app_intent_init(tmp_path: Path):
    app_intent = _write(
        tmp_path / "app_intent.c",
        """
        static void init_drivers(void)
        {
            LIN_Init();
        }

        void APP_INTENT_Init(void)
        {
            init_drivers();
            LIN_Send((const uint8_t*)0, 0U);
        }
        """,
    )
    result = check_app_intent_init_before_use(
        app_intent,
        {"LIN": {"init": "LIN_Init", "arity": 1}},
    )
    assert result["passed"] is True
    assert result["errors"] == []


def test_summarize_api_status_ready_when_no_blockers():
    status = summarize_api_status(
        blocking_errors=[],
        warnings=["LIN: inferred tx_buffer symbol used"],
    )
    assert status["ready"] is True
    assert status["blocking_count"] == 0
    assert status["warning_count"] == 1


def test_summarize_api_status_not_ready_with_blockers():
    status = summarize_api_status(
        blocking_errors=[
            "APP_INTENT: missing GIO_Init() while GIO_* APIs are used.",
            "APP_INTENT: missing GIO_Init() while GIO_* APIs are used.",
        ],
        warnings=[],
    )
    assert status["ready"] is False
    assert status["blocking_count"] == 1
    assert status["blocking_errors"] == [
        "APP_INTENT: missing GIO_Init() while GIO_* APIs are used."
    ]
