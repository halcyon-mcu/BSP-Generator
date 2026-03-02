from modules.generation.prompt import build_pass2_driver_c_prompt


def test_pass2_pll_prompt_enforces_hal_encoded_contract_strategy():
    prompt = build_pass2_driver_c_prompt(
        module_name="PLL",
        manifest_json='{"module_name":"PLL","dependencies":[]}',
        reg_header_content="",
        soc_slice="",
        bus_slice="",
        pinmux_yaml="",
        manifest={"api_catalog": {"SYSTEM": {"register_typedefs": ["SYSTEM_REG_MAP_t", "SYSTEM2_REG_MAP_t"]}}},
        dependency_manifests={},
        dependency_signatures={},
        header_snippets="",
        bringup_contract={
            "pll": {
                "init_profile": "rm46_hal_aligned",
                "frequency_decode": {
                    "allow_hal_encoded_pllmul": True,
                    "required_behavior": {
                        "supports_hal_encoded_pllmul_literal": True,
                        "uses_uint64_intermediate_math": True,
                        "derives_active_source_from_ghvsrc": True,
                    },
                    "required_tokens": ["0xA400", "uint64_t"],
                },
            }
        },
    )

    assert "Do NOT infer PLLMUL semantics from generic formulas when contract metadata is present." in prompt
    assert "if (nf_raw == 0xA400U)" in prompt
    assert "Multiplier value (use as-is)" not in prompt


def test_pass2_pll_prompt_supports_trm_dynamic_profile():
    prompt = build_pass2_driver_c_prompt(
        module_name="PLL",
        manifest_json='{"module_name":"PLL","dependencies":[]}',
        reg_header_content="",
        soc_slice="",
        bus_slice="",
        pinmux_yaml="",
        manifest={"api_catalog": {"SYSTEM": {"register_typedefs": ["SYSTEM_REG_MAP_t"]}}},
        dependency_manifests={},
        dependency_signatures={},
        header_snippets="",
        bringup_contract={
            "pll": {
                "init_profile": "rm46_trm_dynamic",
                "frequency_decode": {
                    "allow_hal_encoded_pllmul": False,
                    "required_behavior": {
                        "uses_trm_field_decoding": True,
                        "uses_trm_enable_disable_sequence": True,
                        "uses_uint64_intermediate_math": True,
                        "derives_active_source_from_ghvsrc": True,
                    },
                },
            }
        },
    )

    assert "Current bring-up pll.init_profile: rm46_trm_dynamic" in prompt
    assert "RM46 TRM-DYNAMIC PROFILE" in prompt
    assert "NOT required when allow_hal_encoded_pllmul=false" in prompt
