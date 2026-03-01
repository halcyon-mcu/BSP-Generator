from pathlib import Path

from modules.contracts.contract_autofix import autofix_bsp_validate, autofix_module_contract
from modules.contracts.contract_checker import check_bsp_validate_contract, check_generated_module_contract


def _write(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _contract_manifest():
    return {
        "modules": {
            "LIN": {
                "functions": {
                    "LIN_ReceiveByte": {
                        "name": "LIN_ReceiveByte",
                        "return_type": "lin_status_t",
                        "params": [
                            {"name": "data", "type": "uint8_t*"},
                            {"name": "timeout_ms", "type": "uint32_t"},
                        ],
                        "arity": 2,
                    },
                    "LIN_Transmit": {
                        "name": "LIN_Transmit",
                        "return_type": "lin_status_t",
                        "params": [
                            {"name": "data", "type": "const uint8_t*"},
                            {"name": "length", "type": "uint32_t"},
                        ],
                        "arity": 2,
                    },
                    "LIN_TransmitByte": {
                        "name": "LIN_TransmitByte",
                        "return_type": "lin_status_t",
                        "params": [{"name": "data", "type": "uint8_t"}],
                        "arity": 1,
                    },
                    "LIN_Init": {"name": "LIN_Init", "return_type": "lin_status_t", "params": [{"name": "config", "type": "const lin_config_t*"}], "arity": 1},
                },
                "capabilities": {
                    "tx_buffer": "LIN_Transmit",
                    "tx_byte": "LIN_TransmitByte",
                    "rx_byte": "LIN_ReceiveByte",
                    "rx_byte_arity": 2,
                },
                "types": {
                    "lin_data_bits_t": {"values": ["LIN_DATA_BITS_7", "LIN_DATA_BITS_8"]},
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
            "SCI": {
                "functions": {"SCI_Send": {"arity": 2}},
                "types": {},
                "compatibility_wrappers": [],
            },
        }
    }


def test_autofix_module_contract_repairs_lin_signature_drift(tmp_path: Path):
    header = _write(
        tmp_path / "lin_driver.h",
        """
        #ifndef LIN_DRIVER_H
        #define LIN_DRIVER_H
        lin_status_t LIN_ReceiveByte(uint8_t* data);
        lin_status_t LIN_Transmit(const uint8_t* data, uint32_t length);
        lin_status_t LIN_TransmitByte(uint8_t data);
        lin_status_t LIN_Init(const lin_config_t* config);
        #endif /* LIN_DRIVER_H */
        """,
    )
    source = _write(
        tmp_path / "lin_driver.c",
        """
        lin_status_t LIN_ReceiveByte(uint8_t* data) { return LIN_STATUS_OK; }
        lin_status_t LIN_Transmit(const uint8_t* data, uint32_t length) { (void)data; (void)length; return LIN_STATUS_OK; }
        lin_status_t LIN_TransmitByte(uint8_t data) { (void)data; return LIN_STATUS_OK; }
        lin_status_t LIN_Init(const lin_config_t* config) { (void)config; return LIN_STATUS_OK; }
        """,
    )

    autofix_module_contract("LIN", header, source, _contract_manifest())
    result = check_generated_module_contract("LIN", header, source, _contract_manifest())
    assert result["passed"] is True
    assert "LIN_SendData" in header.read_text(encoding="utf-8")
    assert "LIN_SendByte" in header.read_text(encoding="utf-8")


def test_autofix_bsp_validate_rewrites_stale_lin_api_and_fields(tmp_path: Path):
    bsp_validate = _write(
        tmp_path / "bsp_validate.c",
        """
        void test(void) {
            uint8_t rx_byte = 0U;
            lin_config_t lin_cfg;
            lin_cfg.mode = LIN_MODE_SCI;
            lin_cfg.baud_rate = 9600U;
            lin_cfg.data_length = LIN_DATA_8BIT;
            lin_cfg.enable_rx = true;
            (void)LIN_SendData((const uint8_t*)0, 0U);
            (void)LIN_ReceiveByte(&rx_byte);
        }
        """,
    )

    before = check_bsp_validate_contract(bsp_validate, _contract_manifest())
    assert before["passed"] is False

    autofix_bsp_validate(bsp_validate, _contract_manifest())
    after = check_bsp_validate_contract(bsp_validate, _contract_manifest())
    assert after["passed"] is True


def test_autofix_bsp_validate_normalizes_lin_tx_byte_arity(tmp_path: Path):
    bsp_validate = _write(
        tmp_path / "bsp_validate.c",
        """
        void test(void) {
            static const uint8_t msg[] = "AB";
            (void)LIN_TransmitByte(msg, 2U);
        }
        """,
    )

    before = check_bsp_validate_contract(bsp_validate, _contract_manifest())
    assert before["passed"] is False

    autofix_bsp_validate(bsp_validate, _contract_manifest())
    after = check_bsp_validate_contract(bsp_validate, _contract_manifest())
    assert after["passed"] is True
    text = bsp_validate.read_text(encoding="utf-8")
    assert "LIN_TransmitByte(msg);" in text


def test_autofix_module_contract_promotes_timeout_signature_when_source_uses_timeout(tmp_path: Path):
    header = _write(
        tmp_path / "lin_driver.h",
        """
        #ifndef LIN_DRIVER_H
        #define LIN_DRIVER_H
        lin_status_t LIN_ReceiveByte(uint8_t* data);
        #endif /* LIN_DRIVER_H */
        """,
    )
    source = _write(
        tmp_path / "lin_driver.c",
        """
        lin_status_t LIN_ReceiveByte(uint8_t* data)
        {
            if (timeout_ms == 0U) { return LIN_STATUS_OK; }
            return LIN_STATUS_TIMEOUT;
        }
        """,
    )

    autofix_module_contract("LIN", header, source, _contract_manifest())
    assert "uint32_t timeout_ms" in header.read_text(encoding="utf-8")
    assert "uint32_t timeout_ms" in source.read_text(encoding="utf-8")


def test_autofix_module_contract_rewrites_undefined_lin_clear_macros(tmp_path: Path):
    header = _write(
        tmp_path / "lin_driver.h",
        """
        #ifndef LIN_DRIVER_H
        #define LIN_DRIVER_H
        lin_status_t LIN_ReceiveByte(uint8_t* data, uint32_t timeout_ms);
        lin_status_t LIN_Transmit(const uint8_t* data, uint32_t length);
        lin_status_t LIN_TransmitByte(uint8_t data);
        lin_status_t LIN_Init(const lin_config_t* config);
        #endif /* LIN_DRIVER_H */
        """,
    )
    source = _write(
        tmp_path / "lin_driver.c",
        """
        lin_status_t LIN_DisableInterrupt(void)
        {
            uint32_t mask = LIN_SCICLEARINT_CLR_BRKDT_INT;
            return (lin_status_t)mask;
        }
        """,
    )
    _write(
        tmp_path / "reg_lin.h",
        """
        #ifndef REG_LIN_H
        #define REG_LIN_H
        #define LIN_SCICLEARINT_CLR_BE_INT (1U << 31)
        #define LIN_SCICLEARINT_CLR_RX_INT (1U << 9)
        #define LIN_SCICLEARINT_CLR_TX_INT (1U << 8)
        #endif
        """,
    )

    result = autofix_module_contract("LIN", header, source, _contract_manifest())
    text = source.read_text(encoding="utf-8")
    assert "LIN_SCICLEARINT_CLR_BRKDT_INT" not in text
    assert "LIN_SCICLEARINT_CLR_BE_INT" in text
    assert any("Replaced undefined LIN_SCICLEARINT_CLR_BRKDT_INT" in a for a in result["actions"])
