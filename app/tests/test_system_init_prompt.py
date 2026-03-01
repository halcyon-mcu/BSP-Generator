from modules.generation.prompt import build_system_init_prompt


def test_system_init_prompt_uses_manifest_pcr_typedef_and_avoids_hardcoded_pcr_regs_t():
    manifest = {
        "api_catalog": {
            "SYSTEM": {
                "register_typedefs": ["SYSTEM_REG_MAP_t"],
            },
            "PCR": {
                "register_typedefs": ["PCR_REG_MAP_t"],
            },
        }
    }

    prompt = build_system_init_prompt("soc: {}\n", "peripherals: {}\n", manifest=manifest, bus_yaml="")

    assert "PCR register struct typedef (only if PCR pointer is needed): PCR_REG_MAP_t" in prompt
    assert "PCR_REGS_t" not in prompt
