"""
Unit tests for startup contract and pass2 module-specific validation rules.
"""

from pathlib import Path

from modules.validation.validation_engine import (
    ValidationResult,
    _validate_start_asm_contract,
    _validate_system_init_startup_contract,
)
from modules.validation.pass2_validator import validate_driver_implementation


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_system_init_startup_contract_valid_order(tmp_path):
    system_c = _write(
        tmp_path,
        "system.c",
        """
void system_init(void)
{
    system_setup_flash_waitstates();
    PCR_Init();
    PCR_EnableAllPeripherals();
    PLL_Init();
}
""".strip()
        + "\n",
    )

    result = ValidationResult(is_valid=True, phase="system_init")
    _validate_system_init_startup_contract([system_c], result)

    assert result.is_valid is True
    assert result.errors == []


def test_system_init_startup_contract_detects_wrong_order(tmp_path):
    system_c = _write(
        tmp_path,
        "system.c",
        """
void system_init(void)
{
    PLL_Init();
    PCR_Init();
    PCR_EnableAllPeripherals();
}
""".strip()
        + "\n",
    )

    result = ValidationResult(is_valid=True, phase="system_init")
    _validate_system_init_startup_contract([system_c], result)

    assert result.is_valid is False
    assert any("Startup ordering violation" in e for e in result.errors)


def test_start_asm_contract_detects_address_word_vectors(tmp_path):
    start_s = _write(
        tmp_path,
        "start.s",
        """
.sect   ".intvecs"
.align  4
.long   end_of_stack
.long   Reset_Handler
.long   Reset_Handler
.long   Reset_Handler
.long   Reset_Handler
.long   0
.long   Reset_Handler
.long   Reset_Handler
""".strip()
        + "\n",
    )

    result = ValidationResult(is_valid=True, phase="start_asm")
    _validate_start_asm_contract([start_s], result)

    assert result.is_valid is False
    assert any(".long Reset_Handler" in e for e in result.errors)


def test_pass2_pll_requires_ghvsrc_awareness(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"

void PLL_Init(void) {}
uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    (void)domain;
    return 80000000U;
}
""".strip()
        + "\n",
    )

    manifest_entry = {
        "init_function": "PLL_Init",
        "api_functions": [{"name": "PLL_Init"}, {"name": "PLL_GetFrequency"}],
        "dependencies": [],
    }
    soc_data = {"peripherals": [{"name": "PLL"}]}
    regs_data = {}

    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[pll_c],
        soc_data=soc_data,
        regs_data=regs_data,
    )

    assert result.is_valid is False
    assert any("GHVSRC" in e for e in result.critical_errors)


def test_pass2_lin_requires_nonblocking_timeout_zero(tmp_path):
    lin_c = _write(
        tmp_path,
        "lin_driver.c",
        """
#include "lin_driver.h"
#include "pll_driver.h"

lin_status_t LIN_Init(const lin_config_t* config)
{
    (void)config;
    linREG->SCIPIO0 = (1U << 2U) | (1U << 1U);
    return LIN_STATUS_OK;
}

lin_status_t LIN_ReceiveByte(uint8_t* data, uint32_t timeout_ms)
{
    while ((linREG->SCIFLR & LIN_SCIFLR_RXRDY) == 0U) { (void)timeout_ms; }
    *data = (uint8_t)(linREG->SCIRD & LIN_SCIRD_RD_MASK);
    return LIN_STATUS_OK;
}
""".strip()
        + "\n",
    )

    manifest_entry = {
        "init_function": "LIN_Init",
        "api_functions": [{"name": "LIN_Init"}, {"name": "LIN_ReceiveByte"}],
        "dependencies": ["PLL"],
    }
    soc_data = {"peripherals": [{"name": "LIN", "clock_ref": "VCLK"}]}
    regs_data = {}

    result = validate_driver_implementation(
        module_name="LIN",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[lin_c],
        soc_data=soc_data,
        regs_data=regs_data,
    )

    assert result.is_valid is False
    assert any("timeout_ms==0" in e or "timeout_ms==0" in e.replace(" ", "") for e in result.critical_errors)
