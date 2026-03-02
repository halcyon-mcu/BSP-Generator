from pathlib import Path

from modules.utils.dependency_resolver import InitOrder
from modules.validation.startup_contract_validator import validate_startup_contract


def test_startup_contract_validator_passes_for_valid_sequence(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI", "GIO", "LIN"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();system_setup_flash_waitstates();PLL_Init();}\n",
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")
    result = validate_startup_contract(init_order, tmp_path)
    assert result["passes"] is True
    assert result["errors"] == []


def test_startup_contract_validator_fails_when_pcr_after_pll(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PLL", "PCR", "IOMM", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PLL_Init();PCR_Init();PCR_EnableAllPeripherals();}\n",
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")
    result = validate_startup_contract(init_order, tmp_path)
    assert result["passes"] is False
    assert any("PCR must initialize before PLL" in e or "startup ordering" in e for e in result["errors"])


def test_startup_contract_validator_reads_system_from_include_dir(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI", "GIO", "LIN"])
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();system_setup_flash_waitstates();PLL_Init();}\n",
        encoding="utf-8",
    )
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")
    result = validate_startup_contract(init_order, tmp_path)
    assert result["passes"] is True


def test_startup_contract_validator_flags_missing_pcr_enable_symbol(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();PLL_Init();}\n",
        encoding="utf-8",
    )
    result = validate_startup_contract(init_order, tmp_path)
    assert result["passes"] is False
    assert any("missing in pcr_driver.h" in e or "missing in pcr_driver.c" in e for e in result["errors"])


def test_startup_contract_validator_flags_m_style_vectors(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();system_setup_flash_waitstates();PLL_Init();}\n",
        encoding="utf-8",
    )

    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")
    (tmp_path / "start.s").write_text(
        ".sect \".intvecs\"\n.long end_of_stack\n.long Reset_Handler\n.long Reset_Handler\n.long Reset_Handler\n",
        encoding="utf-8",
    )

    result = validate_startup_contract(init_order, tmp_path)
    assert result["passes"] is False
    assert any("address-word vectors" in e for e in result["errors"])


def test_startup_contract_validator_enforces_bringup_required_order(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();PLL_Init();system_setup_flash_waitstates();}\n",
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")

    bringup_contract = {
        "startup": {
            "required_order": [
                "PCR_Init",
                "PCR_EnableAllPeripherals",
                "flash_waitstates",
                "PLL_Init",
            ]
        }
    }
    result = validate_startup_contract(init_order, tmp_path, bringup_contract=bringup_contract)
    assert result["passes"] is False
    assert any("bring-up ordering violation" in e for e in result["errors"])


def test_startup_contract_validator_enforces_trm_dynamic_pll_profile(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "PLL", "VIM"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();system_setup_flash_waitstates();PLL_Init();}\n",
        encoding="utf-8",
    )
    (tmp_path / "pll_driver.c").write_text(
        (
            "void PLL_Init(void){SYSREG->PLLCTL1=0xA400U;SYSREG->PLLCTL2=0x200U;SYSREG->GHVSRC=1U;}\n"
            "uint32_t PLL_GetFrequency(clock_domain_t d){(void)d;return 80000000U;}\n"
        ),
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")

    contract = {
        "pll": {
            "init_profile": "rm46_trm_dynamic",
            "frequency_decode": {
                "required_behavior": {
                    "uses_trm_field_decoding": True,
                    "uses_trm_enable_disable_sequence": True,
                }
            },
        }
    }
    result = validate_startup_contract(init_order, tmp_path, bringup_contract=contract)
    assert result["passes"] is False
    assert any("TRM dynamic profile" in e for e in result["errors"])


def test_startup_contract_validator_uses_flash_callsite_not_helper_definition(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        (
            "static void system_setup_flash_waitstates(void){FLASH_FRDCNTL = 0x1U;}\n"
            "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();"
            "system_setup_flash_waitstates();PLL_Init();}\n"
        ),
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")

    bringup_contract = {
        "startup": {
            "required_order": [
                "PCR_Init",
                "PCR_EnableAllPeripherals",
                "flash_waitstates",
                "PLL_Init",
            ]
        }
    }
    result = validate_startup_contract(init_order, tmp_path, bringup_contract=bringup_contract)
    assert not any("bring-up ordering violation" in e for e in result["errors"])


def test_startup_contract_validator_accepts_wait_for_pll_lock_and_macro_literals(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();system_setup_flash_waitstates();PLL_Init();}\n",
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")
    (tmp_path / "pll_driver.c").write_text(
        (
            "#define HAL_PLLMUL_LITERAL (0xA400U)\n"
            "#define HAL_ALIGNED_GLBSTAT_CLEAR_VALUE (0x00000301U)\n"
            "#define HAL_ALIGNED_CSDIS_VALUE (0x0000008CU)\n"
            "#define HAL_ALIGNED_CDDIS_VALUE (0x00000020U)\n"
            "static void wait_for_pll_lock(void){while((SYSREG->CSVSTAT & 2U)==0U){}}\n"
            "void PLL_Init(void){"
            "SYSREG->GLBSTAT = HAL_ALIGNED_GLBSTAT_CLEAR_VALUE;"
            "SYSREG->PLLCTL1 = HAL_PLLMUL_LITERAL;"
            "SYSREG->PLLCTL2 = 0x1U;"
            "SYSREG->CSDIS = HAL_ALIGNED_CSDIS_VALUE;"
            "SYSREG->CDDIS = HAL_ALIGNED_CDDIS_VALUE;"
            "wait_for_pll_lock();"
            "SYSREG->GHVSRC = 1U;"
            "SYSREG->RCLKSRC = 1U;"
            "SYSREG->VCLKASRC = 1U;"
            "SYSREG->CLKCNTL |= SYSTEM_CLKCNTL_PENA;"
            "}\n"
            "uint32_t PLL_GetFrequency(clock_domain_t d){uint32_t nf_raw=0U;(void)d;"
            "if(nf_raw==HAL_PLLMUL_LITERAL){return 220000000U;}return 0U;}\n"
        ),
        encoding="utf-8",
    )

    contract = {
        "pll": {
            "init_profile": "rm46_hal_aligned",
            "required_sequence": [
                "poll CSVSTAT",
                "write GHVSRC",
                "write RCLKSRC",
                "write VCLKASRC",
                "write CLKCNTL",
                "set PENA",
            ],
            "frequency_decode": {
                "required_behavior": {
                    "supports_hal_encoded_pllmul_literal": True,
                }
            },
        }
    }

    result = validate_startup_contract(init_order, tmp_path, bringup_contract=contract)
    assert not any("poll CSVSTAT" in e for e in result["errors"])
    assert not any("HAL-encoded PLLMUL literal/decode guard" in e for e in result["errors"])


def test_startup_contract_validator_detects_early_return_before_required_checkpoint(tmp_path: Path):
    init_order = InitOrder(order=["SYSTEM", "PCR", "IOMM", "PLL", "VIM", "SCI"])
    (tmp_path / "system.c").write_text(
        "void system_init(void){PCR_Init();PCR_EnableAllPeripherals();system_setup_flash_waitstates();PLL_Init();}\n",
        encoding="utf-8",
    )
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir()
    source_dir.mkdir()
    (include_dir / "pcr_driver.h").write_text("void PCR_EnableAllPeripherals(void);\n", encoding="utf-8")
    (source_dir / "pcr_driver.c").write_text("void PCR_EnableAllPeripherals(void){}\n", encoding="utf-8")
    (tmp_path / "pll_driver.c").write_text(
        (
            "void PLL_Init(void){"
            "SYSREG->CLKCNTL = 0x1U;"
            "return;"
            "SYSREG->GHVSRC = 0x2U;"
            "}\n"
        ),
        encoding="utf-8",
    )
    contract = {
        "pll": {
            "required_sequence": [
                "write CLKCNTL",
                "write GHVSRC",
            ]
        }
    }
    result = validate_startup_contract(init_order, tmp_path, bringup_contract=contract)
    assert result["passes"] is False
    assert any("control_flow:return_before:write GHVSRC" in e for e in result["errors"])
