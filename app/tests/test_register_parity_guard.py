from pathlib import Path

from modules.validation.register_parity_guard import (
    collect_register_accesses,
    compare_register_sequences,
    run_parity_guard,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _minimal_reg_system(path: Path) -> None:
    _write(
        path,
        """
typedef struct {
    volatile uint32_t CLKCNTL;      /**< 0xD0: Clock Control Register. */
    volatile uint32_t GHVSRC;       /**< 0x48: Source Register. */
} SYSTEM_REG_MAP_t;
        """,
    )


def test_collect_register_accesses_resolves_struct_offsets_and_macro_addresses(tmp_path: Path):
    out_dir = tmp_path / "candidate"
    _minimal_reg_system(out_dir / "include" / "reg_system.h")
    _write(
        out_dir / "source" / "pll_driver.c",
        """
#include <stdint.h>
static SYSTEM_REG_MAP_t * const SYSREG = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;
#define FLASH_FRDCNTL_REG      (*(volatile uint32_t *)0xFFF87000u)
void PLL_Init(void) {
    SYSREG->CLKCNTL = 0x1u;
    SYSREG->GHVSRC = 0x2u;
    FLASH_FRDCNTL_REG = 0x00000311u;
}
        """,
    )

    accesses = collect_register_accesses(out_dir)
    assert any(a.canonical_symbol == "CLKCNTL" and a.address == "0xFFFFFFD0" for a in accesses)
    assert any(a.canonical_symbol == "GHVSRC" and a.address == "0xFFFFFF48" for a in accesses)
    assert any(a.canonical_symbol == "FLASH_FRDCNTL" and a.address == "0xFFF87000" for a in accesses)


def test_compare_register_sequences_detects_order_swap_for_critical_tokens(tmp_path: Path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _minimal_reg_system(baseline / "include" / "reg_system.h")
    _minimal_reg_system(candidate / "include" / "reg_system.h")
    _write(
        baseline / "source" / "pll_driver.c",
        """
static SYSTEM_REG_MAP_t * const SYSREG = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;
void PLL_Init(void) {
    SYSREG->CLKCNTL = 0x1u;
    SYSREG->GHVSRC = 0x2u;
}
        """,
    )
    _write(
        candidate / "source" / "pll_driver.c",
        """
static SYSTEM_REG_MAP_t * const SYSREG = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;
void PLL_Init(void) {
    SYSREG->GHVSRC = 0x2u;
    SYSREG->CLKCNTL = 0x1u;
}
        """,
    )

    base_accesses = collect_register_accesses(baseline)
    cand_accesses = collect_register_accesses(candidate)
    cmp = compare_register_sequences(
        base_accesses,
        cand_accesses,
        mode="critical_only",
        critical_registers={"CLKCNTL", "GHVSRC"},
    )
    assert cmp["passes"] is False
    assert cmp["summary"]["mismatch_count"] > 0


def test_run_parity_guard_writes_artifacts_and_mismatches(tmp_path: Path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _minimal_reg_system(baseline / "include" / "reg_system.h")
    _minimal_reg_system(candidate / "include" / "reg_system.h")
    _write(
        baseline / "source" / "pll_driver.c",
        """
static SYSTEM_REG_MAP_t * const SYSREG = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;
void PLL_Init(void) {
    SYSREG->CLKCNTL = 0x1u;
    SYSREG->GHVSRC = 0x2u;
}
        """,
    )
    _write(
        candidate / "source" / "pll_driver.c",
        """
static SYSTEM_REG_MAP_t * const SYSREG = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;
void PLL_Init(void) {
    SYSREG->GHVSRC = 0x2u;
    SYSREG->CLKCNTL = 0x1u;
}
        """,
    )

    result = run_parity_guard(
        candidate,
        baseline,
        mode="critical_only",
        critical_registers=["CLKCNTL", "GHVSRC"],
    )
    assert result["passes"] is False
    assert result["critical_sequence_mismatches"]
    assert (candidate / "forensics" / "register_accesses_candidate.csv").exists()
    assert (candidate / "forensics" / "critical_sequence_diff.md").exists()
