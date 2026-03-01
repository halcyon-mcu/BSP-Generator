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
