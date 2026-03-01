from modules.generation.prompt import build_pass2_driver_c_prompt


def test_pass2_prompt_does_not_emit_legacy_iomm_pin_function_tokens():
    prompt = build_pass2_driver_c_prompt(
        module_name="SCI",
        manifest_json='{"module_name":"SCI","dependencies":["IOMM"]}',
        reg_header_content="",
        soc_slice="",
        bus_slice="",
        pinmux_yaml="",
        manifest={},
        dependency_manifests={},
        dependency_signatures={},
        header_snippets="",
        bringup_contract={},
    )

    assert "IOMM_PIN_FUNCTION_" not in prompt
