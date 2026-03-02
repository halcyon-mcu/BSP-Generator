from pathlib import Path

from modules.build.ti_diagnostics import apply_deterministic_fixes


def test_deterministic_fix_reorders_clkcntl_before_ghvsrc(tmp_path: Path):
    pll_c = tmp_path / "pll_driver.c"
    pll_c.write_text(
        (
            "void PLL_Init(void)\n"
            "{\n"
            "    SYSREG->GHVSRC = 0x1U;\n"
            "    SYSREG->CLKCNTL = 0x2U;\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    result = apply_deterministic_fixes(tmp_path, diagnostics=[])
    assert result["applied"] is True
    updated = pll_c.read_text(encoding="utf-8")
    assert updated.find("SYSREG->CLKCNTL") < updated.find("SYSREG->GHVSRC")
