from pathlib import Path

from modules.build.ti_diagnostics import (
    apply_deterministic_fixes,
    apply_targeted_rewrite,
    parse_ti_diagnostics,
)


def test_parse_ti_diagnostics_parses_c_and_asm_formats():
    log = """
"../bsp_validate.c", line 89: warning #551-D: variable "lin_banner_idx" is used before its value is set
"../start.s", ERROR!   at line 32: [E0200] Bad term in expression
error #10234-D: unresolved symbols remain
    """.strip()

    diags = parse_ti_diagnostics(log)
    assert len(diags) == 3
    assert any(d.file_path.endswith("bsp_validate.c") and d.severity == "warning" for d in diags)
    assert any(d.file_path.endswith("start.s") and d.code == "E0200" for d in diags)
    assert any(d.file_path == "" and d.code == "10234-D" for d in diags)


def test_parse_ti_diagnostics_parses_fatal_error_with_file_context():
    log = '"../source/gio_driver.c", line 12: fatal error #1965: cannot open source file "vim.h"'
    diags = parse_ti_diagnostics(log)
    assert len(diags) == 1
    diag = diags[0]
    assert diag.file_path.endswith("gio_driver.c")
    assert diag.severity == "error"
    assert diag.code == "1965"
    assert "cannot open source file" in diag.message


def test_apply_deterministic_fixes_repairs_system_pcr_and_lin(tmp_path: Path):
    system_c = tmp_path / "system.c"
    system_c.write_text(
        """
#include "system.h"
void system_init(void)
{
    PLL_Init();
    system_setup_flash_waitstates();
    PCR_EnableAllPeripherals();
    PCR_Init();
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    start_s = tmp_path / "start.s"
    start_s.write_text(
        """
        .sect ".intvecs"
        .align 4
        .long end_of_stack
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    pcr_h = tmp_path / "pcr_driver.h"
    pcr_h.write_text("#ifndef PCR_DRIVER_H\n#define PCR_DRIVER_H\n#endif /* PCR_DRIVER_H */\n", encoding="utf-8")
    pcr_c = tmp_path / "pcr_driver.c"
    pcr_c.write_text(
        """
#include "pcr_driver.h"
void PCR_EnableAllPeripherals(void)
{
    PCR_Init();
}
/* PSPWRDWNCLR0 PSPWRDWNCLR1 */
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    reg_lin_h = tmp_path / "reg_lin.h"
    reg_lin_h.write_text("#define LIN_SCICLEARINT_CLR_BE_INT (1U << 0U)\n", encoding="utf-8")
    lin_c = tmp_path / "lin_driver.c"
    lin_c.write_text(
        "linREG->SCICLEARINT = LIN_SCICLEARINT_CLR_BRKDT_INT;\n",
        encoding="utf-8",
    )

    result = apply_deterministic_fixes(tmp_path, diagnostics=[])
    assert result["applied"] is True

    system_text = system_c.read_text(encoding="utf-8")
    assert "static void system_setup_flash_waitstates(void)" in system_text
    assert "FLASH_FRDCNTL" in system_text
    assert system_text.find("PCR_Init();") < system_text.find("PCR_EnableAllPeripherals();")
    assert system_text.find("PCR_EnableAllPeripherals();") < system_text.find("system_setup_flash_waitstates();")
    assert system_text.find("system_setup_flash_waitstates();") < system_text.find("PLL_Init();")

    pcr_text = pcr_c.read_text(encoding="utf-8")
    assert "PSPWRDWNCLR0" in pcr_text
    assert "PSPWRDWNCLR1" in pcr_text
    assert "PCR_Init();" not in pcr_text

    pcr_header_text = pcr_h.read_text(encoding="utf-8")
    assert "void PCR_EnableAllPeripherals(void);" in pcr_header_text

    lin_text = lin_c.read_text(encoding="utf-8")
    assert "LIN_SCICLEARINT_CLR_BRKDT_INT" not in lin_text
    assert "LIN_SCICLEARINT_CLR_BE_INT" in lin_text

    start_text = start_s.read_text(encoding="utf-8")
    assert "B       Reset_Handler" in start_text


def test_apply_targeted_rewrite_handles_start_literals(tmp_path: Path):
    start_s = tmp_path / "start.s"
    start_s.write_text("    LDR     R0, =0x08000000\n", encoding="utf-8")
    diagnostics = parse_ti_diagnostics(
        '"../start.s", ERROR!   at line 32: [E0200] Bad term in expression'
    )
    result = apply_targeted_rewrite(tmp_path, diagnostics)
    assert result["applied"] is True
    text = start_s.read_text(encoding="utf-8")
    assert "MOVW" in text
    assert "MOVT" in text


def test_apply_deterministic_fixes_repairs_entry_and_pll_runtime_regressions(tmp_path: Path):
    entry_c = tmp_path / "entry.c"
    entry_c.write_text(
        """
#include <stdint.h>
#include <string.h>
extern uint32_t start_of_data, end_of_data, start_of_data_in_flash;
extern uint32_t start_of_bss, end_of_bss;
void Reset_Handler_C(void)
{
    size_t data_size;
    size_t bss_size;
    data_size = (size_t)(&end_of_data - &start_of_data);
    memcpy(&start_of_data, &start_of_data_in_flash, data_size * sizeof(uint32_t));
    bss_size = (size_t)(&end_of_bss - &start_of_bss);
    memset(&start_of_bss, 0, bss_size * sizeof(uint32_t));
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    pll_c = tmp_path / "pll_driver.c"
    pll_c.write_text(
        """
#include <stdint.h>
void PLL_Init(void)
{
    uint32_t lock_timeout;
    uint32_t pllctl1_value;
    uint32_t pllctl2_value;
    pllctl2_value = ((PLL1_ODPLL_DEFAULT << SYSTEM_PLLCTL2_ODPLL_SHIFT) & SYSTEM_PLLCTL2_ODPLL_MASK);
    SYSREG->CLKCNTL = ((1u << SYSTEM_CLKCNTL_VCLKR_SHIFT) & SYSTEM_CLKCNTL_VCLKR_MASK)
                    | ((1u << SYSTEM_CLKCNTL_VCLK2R_SHIFT) & SYSTEM_CLKCNTL_VCLK2R_MASK);
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = apply_deterministic_fixes(tmp_path, diagnostics=[])
    assert result["applied"] is True

    entry_text = entry_c.read_text(encoding="utf-8")
    assert "data_size = (size_t)(&end_of_data - &start_of_data) * sizeof(uint32_t);" in entry_text
    assert "bss_size = (size_t)(&end_of_bss - &start_of_bss) * sizeof(uint32_t);" in entry_text
    assert "memcpy(&start_of_data, &start_of_data_in_flash, data_size);" in entry_text
    assert "memset(&start_of_bss, 0, bss_size);" in entry_text

    pll_text = pll_c.read_text(encoding="utf-8")
    assert "PLL1_ODPLL_DEFAULT - 1u" in pll_text
    assert "uint32_t clkcntl_value;" in pll_text
    assert "clkcntl_value = SYSREG->CLKCNTL;" in pll_text
    assert "clkcntl_value &= ~(SYSTEM_CLKCNTL_VCLKR_MASK | SYSTEM_CLKCNTL_VCLK2R_MASK);" in pll_text


def test_apply_deterministic_fixes_normalizes_driver_base_alias_to_canonical_macro(tmp_path: Path):
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    (include_dir / "reg_pcr.h").write_text(
        "typedef struct { volatile unsigned int PSPWRDWNCLR0; } PCR_REG_MAP_t;\n"
        "#define PCR ((PCR_REG_MAP_t *)0xFFFFE000U)\n",
        encoding="utf-8",
    )
    (source_dir / "pcr_driver.c").write_text(
        '#include "reg_pcr.h"\n'
        "void PCR_Init(void)\n"
        "{\n"
        "    pcrREG->PSPWRDWNCLR0 = 0xFFFFFFFFU;\n"
        "}\n",
        encoding="utf-8",
    )

    result = apply_deterministic_fixes(tmp_path, diagnostics=[])
    assert result["applied"] is True
    updated = (source_dir / "pcr_driver.c").read_text(encoding="utf-8")
    assert "pcrREG->" not in updated
    assert "PCR->PSPWRDWNCLR0" in updated


def test_apply_deterministic_fixes_canonicalizes_vim_filenames_and_includes(tmp_path: Path):
    include_dir = tmp_path / "include"
    source_dir = tmp_path / "source"
    include_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    (include_dir / "vim.h").write_text("void vim_init(void);\n", encoding="utf-8")
    (source_dir / "vim.c").write_text('#include "vim.h"\nvoid vim_init(void) {}\n', encoding="utf-8")
    (source_dir / "gio_driver.c").write_text('#include "vim.h"\n', encoding="utf-8")

    result = apply_deterministic_fixes(tmp_path, diagnostics=[])
    assert result["applied"] is True
    assert (include_dir / "vim_driver.h").exists()
    assert (source_dir / "vim_driver.c").exists()
    assert not (include_dir / "vim.h").exists()
    assert not (source_dir / "vim.c").exists()
    gio_text = (source_dir / "gio_driver.c").read_text(encoding="utf-8")
    assert '#include "vim_driver.h"' in gio_text


def test_apply_deterministic_fixes_injects_lin_zero_timeout_nonblocking_branch(tmp_path: Path):
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    lin_c = source_dir / "lin_driver.c"
    lin_c.write_text(
        """
static bool wait_rx_ready(uint32_t timeout_ms)
{
    uint32_t elapsed_ms;
    elapsed_ms = 0U;
    while (elapsed_ms < timeout_ms) {
        if ((LIN->SCIFLR & LIN_SCIFLR_RXRDY) != 0U) {
            return true;
        }
        elapsed_ms++;
    }
    return false;
}
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = apply_deterministic_fixes(tmp_path, diagnostics=[])
    assert result["applied"] is True
    updated = lin_c.read_text(encoding="utf-8")
    assert "if (timeout_ms == 0U)" in updated
    assert "return ((LIN->SCIFLR & LIN_SCIFLR_RXRDY) != 0U);" in updated
