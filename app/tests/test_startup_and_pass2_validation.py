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


def test_pass2_lin_uses_bringup_contract_scipio0_value(tmp_path):
    lin_c = _write(
        tmp_path,
        "lin_driver.c",
        """
#include "lin_driver.h"

lin_status_t LIN_Init(const lin_config_t* config)
{
    (void)config;
    linREG->SCIPIO0 = 0x00000003U;
    return LIN_STATUS_OK;
}
""".strip()
        + "\n",
    )

    manifest_entry = {
        "init_function": "LIN_Init",
        "api_functions": [{"name": "LIN_Init"}],
        "dependencies": [],
    }
    soc_data = {"peripherals": [{"name": "LIN"}]}
    regs_data = {}
    bringup_contract = {
        "lin": {
            "required_registers": {
                "SCIPIO0": {"required_value": "0x00000006"}
            }
        }
    }

    result = validate_driver_implementation(
        module_name="LIN",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[lin_c],
        soc_data=soc_data,
        regs_data=regs_data,
        bringup_contract=bringup_contract,
    )

    assert result.is_valid is False
    assert any("SCIPIO0" in e and "00000006" in e for e in result.critical_errors)


def test_pass2_lin_accepts_scipio0_macro_composition(tmp_path):
    lin_c = _write(
        tmp_path,
        "lin_driver.c",
        """
#include "lin_driver.h"

lin_status_t LIN_Init(const lin_config_t* config)
{
    (void)config;
    linREG->SCIPIO0 = LIN_SCIPIO0_SCITXFUNC | LIN_SCIPIO0_SCIRXFUNC;
    return LIN_STATUS_OK;
}
""".strip()
        + "\n",
    )

    manifest_entry = {
        "init_function": "LIN_Init",
        "api_functions": [{"name": "LIN_Init"}],
        "dependencies": [],
    }
    soc_data = {"peripherals": [{"name": "LIN"}]}
    regs_data = {}
    bringup_contract = {
        "lin": {
            "required_registers": {
                "SCIPIO0": {"required_value": "0x00000006"}
            }
        }
    }

    result = validate_driver_implementation(
        module_name="LIN",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[lin_c],
        soc_data=soc_data,
        regs_data=regs_data,
        bringup_contract=bringup_contract,
    )

    assert not any("SCIPIO0" in e for e in result.critical_errors)


def test_pass2_pll_contract_requires_hal_decode_behavior(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"

void PLL_Init(void)
{
    SYSREG->CSDISSET = 1U;
    SYSREG->PLLCTL1 = 0x1234U;
    SYSREG->PLLCTL2 = 0x10U;
    while ((SYSREG->CSVSTAT & 2U) == 0U) {}
    SYSREG->GHVSRC = 1U;
    SYSREG->RCLKSRC = 9U;
    SYSREG->VCLKASRC = 9U;
    SYSREG->CLKCNTL = 0x10000U;
    SYSREG->CLKCNTL |= SYSTEM_CLKCNTL_PENA;
}

uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    uint32_t nf_raw = 0U;
    (void)domain;
    if ((SYSREG->GHVSRC & 0xFU) == 1U) {
        return (16000000U * nf_raw);
    }
    return 0U;
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
    bringup_contract = {
        "pll": {
            "required_sequence": [
                "disable/set source bits",
                "write PLLCTL1/PLLCTL2(/PLLCTL3 if used)",
                "poll CSVSTAT",
                "write GHVSRC",
                "write RCLKSRC",
                "write VCLKASRC",
                "write CLKCNTL",
                "set PENA",
            ],
            "frequency_decode": {
                "allow_hal_encoded_pllmul": True,
                "required_behavior": {
                    "supports_hal_encoded_pllmul_literal": True,
                    "uses_uint64_intermediate_math": True,
                    "derives_active_source_from_ghvsrc": True,
                },
            },
        }
    }

    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[pll_c],
        soc_data=soc_data,
        regs_data=regs_data,
        bringup_contract=bringup_contract,
    )

    assert result.is_valid is False
    assert any("HAL-encoded PLLMUL literal/decode guard" in e for e in result.critical_errors)
    assert any("uint64_t intermediate math" in e for e in result.critical_errors)


def test_pass2_pll_contract_accepts_hal_decode_behavior(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"
#include <stdint.h>

void PLL_Init(void)
{
    SYSREG->CSDISSET = 1U;
    SYSREG->PLLCTL1 = 0xA400U;
    SYSREG->PLLCTL2 = 0x200U;
    while ((SYSREG->CSVSTAT & 2U) == 0U) {}
    SYSREG->GHVSRC = 1U;
    SYSREG->RCLKSRC = 9U;
    SYSREG->VCLKASRC = 9U;
    SYSREG->CLKCNTL = 0x10000U;
    SYSREG->CLKCNTL |= SYSTEM_CLKCNTL_PENA;
}

uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    uint32_t pllctl1;
    uint32_t nf_raw;
    uint32_t nf;
    (void)domain;
    pllctl1 = SYSREG->PLLCTL1;
    nf_raw = pllctl1 & 0xFFFFU;
    nf = nf_raw;
    if (nf_raw == 0xA400U) {
        nf = 120U;
    }
    if ((SYSREG->GHVSRC & 0xFU) == 1U) {
        uint64_t f_pll = ((uint64_t)16000000U * (uint64_t)nf) / (uint64_t)2U;
        return (uint32_t)f_pll;
    }
    return 0U;
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
    bringup_contract = {
        "pll": {
            "required_sequence": [
                "disable/set source bits",
                "write PLLCTL1/PLLCTL2(/PLLCTL3 if used)",
                "poll CSVSTAT",
                "write GHVSRC",
                "write RCLKSRC",
                "write VCLKASRC",
                "write CLKCNTL",
                "set PENA",
            ],
            "frequency_decode": {
                "allow_hal_encoded_pllmul": True,
                "required_behavior": {
                    "supports_hal_encoded_pllmul_literal": True,
                    "uses_uint64_intermediate_math": True,
                    "derives_active_source_from_ghvsrc": True,
                },
            },
        }
    }

    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[pll_c],
        soc_data=soc_data,
        regs_data=regs_data,
        bringup_contract=bringup_contract,
    )

    assert result.is_valid is True


def test_pass2_pll_trm_dynamic_profile_rejects_literal_only_programming(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"

void PLL_Init(void)
{
    SYSREG->PLLCTL1 = 0xA400U;
    SYSREG->PLLCTL2 = 0x200U;
    SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF;
    while ((SYSREG->CSVSTAT & 2U) == 0U) {}
    SYSREG->GHVSRC = 1U;
}

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
    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry=manifest_entry,
        preamble="",
        written_files=[pll_c],
        soc_data={"peripherals": [{"name": "PLL"}]},
        regs_data={},
        bringup_contract={
            "pll": {
                "init_profile": "rm46_trm_dynamic",
                "frequency_decode": {
                    "required_behavior": {
                        "uses_trm_field_decoding": True,
                        "uses_trm_enable_disable_sequence": True,
                        "uses_uint64_intermediate_math": True,
                        "derives_active_source_from_ghvsrc": True,
                    }
                },
            }
        },
    )

    assert result.is_valid is False
    assert any("TRM dynamic profile" in e for e in result.critical_errors)


def test_pass2_pll_accepts_wait_for_pll_lock_checkpoint(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"
#include <stdint.h>

static void wait_for_pll_lock(void)
{
    while ((SYSREG->CSVSTAT & 2U) == 0U) {}
}

void PLL_Init(void)
{
    SYSREG->CSDISSET = 1U;
    SYSREG->PLLCTL1 = 0x20000000U;
    SYSREG->PLLCTL2 = 0x1U;
    wait_for_pll_lock();
    SYSREG->GHVSRC = 1U;
    SYSREG->RCLKSRC = 1U;
    SYSREG->VCLKASRC = 1U;
    SYSREG->CLKCNTL = SYSTEM_CLKCNTL_PENA;
}

uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    (void)domain;
    return 0U;
}
""".strip()
        + "\n",
    )
    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry={"init_function": "PLL_Init", "api_functions": [{"name": "PLL_Init"}, {"name": "PLL_GetFrequency"}], "dependencies": []},
        preamble="",
        written_files=[pll_c],
        soc_data={"peripherals": [{"name": "PLL"}]},
        regs_data={},
        bringup_contract={"pll": {"required_sequence": ["poll CSVSTAT"]}},
    )
    assert not any("poll CSVSTAT" in e for e in result.critical_errors)


def test_pass2_pll_accepts_ghvsrc_helper_path(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"
#include <stdint.h>

static uint32_t calculate_hclk_frequency(void)
{
    if ((SYSREG->GHVSRC & 0xFU) == 1U) {
        return 80000000U;
    }
    return 16000000U;
}

void PLL_Init(void) {}

uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    (void)domain;
    return calculate_hclk_frequency();
}
""".strip()
        + "\n",
    )
    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry={"init_function": "PLL_Init", "api_functions": [{"name": "PLL_Init"}, {"name": "PLL_GetFrequency"}], "dependencies": []},
        preamble="",
        written_files=[pll_c],
        soc_data={"peripherals": [{"name": "PLL"}]},
        regs_data={},
        bringup_contract={"pll": {"frequency_decode": {"required_behavior": {"derives_active_source_from_ghvsrc": True}}}},
    )
    assert not any("GHVSRC-driven" in e or "does not reference GHVSRC" in e for e in result.critical_errors)


def test_pass2_pll_accepts_parenthesized_hal_macro_decode_guard(tmp_path):
    pll_c = _write(
        tmp_path,
        "pll_driver.c",
        """
#include "pll_driver.h"
#include "reg_system.h"
#include <stdint.h>

#define HAL_PLLMUL_LITERAL (0xA400U)

void PLL_Init(void) {}

uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    uint32_t nf_raw = SYSREG->PLLCTL1 & 0xFFFFU;
    (void)domain;
    if (nf_raw == HAL_PLLMUL_LITERAL) {
        return 220000000U;
    }
    return 0U;
}
""".strip()
        + "\n",
    )
    result = validate_driver_implementation(
        module_name="PLL",
        manifest_entry={"init_function": "PLL_Init", "api_functions": [{"name": "PLL_Init"}, {"name": "PLL_GetFrequency"}], "dependencies": []},
        preamble="",
        written_files=[pll_c],
        soc_data={"peripherals": [{"name": "PLL"}]},
        regs_data={},
        bringup_contract={"pll": {"frequency_decode": {"required_behavior": {"supports_hal_encoded_pllmul_literal": True}}}},
    )
    assert not any("HAL-encoded PLLMUL literal/decode guard" in e for e in result.critical_errors)


def test_pass2_lin_fails_when_scipio0_functional_bits_are_conditional(tmp_path):
    lin_c = _write(
        tmp_path,
        "lin_driver.c",
        """
#include "lin_driver.h"

lin_status_t LIN_Init(const lin_config_t* config)
{
    linREG->SCIPIO0 =
        (config->pin_config.tx_func_mode ? LIN_SCIPIO0_SCITXFUNC : 0U) |
        (config->pin_config.rx_func_mode ? LIN_SCIPIO0_SCIRXFUNC : 0U);
    return LIN_STATUS_OK;
}
""".strip()
        + "\n",
    )
    result = validate_driver_implementation(
        module_name="LIN",
        manifest_entry={"init_function": "LIN_Init", "api_functions": [{"name": "LIN_Init"}], "dependencies": []},
        preamble="",
        written_files=[lin_c],
        soc_data={"peripherals": [{"name": "LIN"}]},
        regs_data={},
        bringup_contract={"lin": {"required_registers": {"SCIPIO0": {"required_value": "0x00000006"}}}},
    )
    assert any("must force SCIPIO0 TX/RX functional bits unconditionally" in e for e in result.critical_errors)
