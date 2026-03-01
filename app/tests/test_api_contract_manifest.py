from modules.contracts.api_contract_manifest import (
    build_api_contract_manifest,
    hydrate_contract_from_generated_headers,
)


def test_api_contract_manifest_derives_lin_capabilities_without_forcing_names():
    bsp_manifest = {
        "api_catalog": {
            "LIN": {
                "driver_header_file": "lin_driver.h",
                "types": [
                    {
                        "name": "lin_config_t",
                        "type": "struct",
                        "members": [
                            {"name": "mode", "type": "lin_mode_t"},
                            {"name": "baud_rate", "type": "uint32_t"},
                            {"name": "data_bits", "type": "lin_data_bits_t"},
                        ],
                    }
                ],
                "functions": [
                    {"prototype": "lin_status_t LIN_ReceiveByte(uint8_t* data);"},
                    {"prototype": "lin_status_t LIN_Send(const uint8_t* data, uint32_t length);"},
                ],
            }
        }
    }
    profile = {"target_board": "LAUNCHXL2-TMS57012-RM46", "strict_validation": True}

    contract = build_api_contract_manifest(bsp_manifest, profile)
    lin = contract["modules"]["LIN"]

    assert lin["functions"]["LIN_ReceiveByte"]["arity"] == 1
    assert lin["functions"]["LIN_Send"]["arity"] == 2
    assert lin["capabilities"]["tx_buffer"] == "LIN_Send"
    assert lin["capabilities"]["rx_byte"] == "LIN_ReceiveByte"
    assert any(w["name"] == "LIN_SendData" for w in lin["compatibility_wrappers"])
    assert contract["api_contract_hash"]


def test_api_contract_manifest_hash_is_stable_for_same_input():
    bsp_manifest = {
        "api_catalog": {
            "SCI": {
                "functions": [
                    {"prototype": "sci_status_t SCI_Init(const sci_config_t* config);"},
                    {"prototype": "sci_status_t SCI_Send(const uint8_t* data, uint32_t length);"},
                ],
                "types": [],
            }
        }
    }
    profile = {"target_board": "RM46"}

    contract_a = build_api_contract_manifest(bsp_manifest, profile)
    contract_b = build_api_contract_manifest(bsp_manifest, profile)

    assert contract_a["api_contract_hash"] == contract_b["api_contract_hash"]


def test_api_contract_manifest_derives_ready_capabilities_from_get_status_names():
    bsp_manifest = {
        "api_catalog": {
            "SCI": {
                "functions": [
                    {"prototype": "bool SCI_GetTxStatus(void);"},
                    {"prototype": "bool SCI_GetRxStatus(void);"},
                    {"prototype": "sci_status_t SCI_SendData(const uint8_t* data, uint32_t length);"},
                ],
                "types": [],
            }
        }
    }
    profile = {"target_board": "RM46"}

    contract = build_api_contract_manifest(bsp_manifest, profile)
    sci = contract["modules"]["SCI"]
    assert sci["capabilities"]["tx_ready"] == "SCI_GetTxStatus"
    assert sci["capabilities"]["rx_ready"] == "SCI_GetRxStatus"
    assert any(w["name"] == "SCI_IsTxReady" for w in sci["compatibility_wrappers"])
    assert any(w["name"] == "SCI_IsRxReady" for w in sci["compatibility_wrappers"])


def test_api_contract_manifest_does_not_map_tx_buffer_to_sendbyte():
    bsp_manifest = {
        "api_catalog": {
            "LIN": {
                "functions": [
                    {"prototype": "lin_status_t LIN_SendByte(uint8_t data);"},
                    {"prototype": "lin_status_t LIN_ReceiveByte(uint8_t* data);"},
                ],
                "types": [],
            }
        }
    }
    profile = {"target_board": "RM46"}

    contract = build_api_contract_manifest(bsp_manifest, profile)
    lin = contract["modules"]["LIN"]

    assert lin["capabilities"]["tx_byte"] == "LIN_SendByte"
    assert "tx_buffer" not in lin["capabilities"]


def test_hydrate_contract_ignores_inline_wrapper_return_statements(tmp_path):
    out_dir = tmp_path / "out"
    include_dir = out_dir / "include"
    include_dir.mkdir(parents=True)
    (include_dir / "lin_driver.h").write_text(
        """
        #ifndef LIN_DRIVER_H
        #define LIN_DRIVER_H
        typedef enum { LIN_STATUS_OK } lin_status_t;
        lin_status_t LIN_SendData(const uint8_t* data, uint32_t length);
        static inline lin_status_t LIN_Send(const uint8_t* data, uint32_t length)
        {
            return LIN_SendData(data, length);
        }
        #endif /* LIN_DRIVER_H */
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    contract = {
        "modules": {
            "LIN": {
                "driver_header_file": "lin_driver.h",
                "functions": {},
                "types": {},
                "compatibility_wrappers": [],
                "capabilities": {},
            }
        }
    }

    hydrated = hydrate_contract_from_generated_headers(out_dir, contract)
    lin_funcs = hydrated["modules"]["LIN"]["functions"]

    assert "LIN_SendData" in lin_funcs
    assert lin_funcs["LIN_SendData"]["return_type"] == "lin_status_t"
