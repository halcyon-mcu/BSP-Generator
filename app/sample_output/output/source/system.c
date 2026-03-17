/* BSP-GEN-META: created_at=2026-03-04T23:27:58-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file system.c
 * @brief TI RM46 System Initialization Implementation
 */

#include <stdint.h>
#include "system.h"
#include "reg_system.h"
#include "reg_pcr.h"
#include "pll_driver.h"

/* Forward declarations of external PCR APIs */
extern void PCR_Init(void);
extern void PCR_EnableAllPeripherals(void);

/* SYSTEM register base pointer */
static SYSTEM_REG_MAP_t * const SYS = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;

/* PCR register base pointer */
static PCR_REG_MAP_t * const PCR = (PCR_REG_MAP_t *)0xFFFFE000u;

/* Flash control register addresses (not in struct-based headers) */
#define FLASH_FRDCNTL_REG     (*(volatile uint32_t *)0xFFF87000u)
#define FLASH_FBFALLBACK_REG  (*(volatile uint32_t *)0xFFF87040u)
#define FLASH_FSMWRENA_REG    (*(volatile uint32_t *)0xFFF87288u)
#define FLASH_EEPROMCONFIG_REG (*(volatile uint32_t *)0xFFF872B8u)

/**
 * @brief Configure flash wait states and EEPROM timing
 *
 * Programs flash controller registers with HAL-aligned values for RM46.
 * This MUST be called before PLL handoff to ensure safe flash access
 * at higher clock frequencies.
 */
static void system_setup_flash_waitstates(void)
{
    /* [prov] bringup_contract.yaml:flash.FLASH_FRDCNTL_REG */
    FLASH_FRDCNTL_REG = 0x00000311u;

    /* [prov] bringup_contract.yaml:flash.FLASH_FSMWRENA_REG (unlock) */
    FLASH_FSMWRENA_REG = 0x00000005u;

    /* [prov] bringup_contract.yaml:flash.FLASH_EEPROMCONFIG_REG */
    FLASH_EEPROMCONFIG_REG = 0x00030002u;

    /* [prov] bringup_contract.yaml:flash.FLASH_FSMWRENA_REG (lock) */
    FLASH_FSMWRENA_REG = 0x0000000Au;

    /* [prov] bringup_contract.yaml:flash.FLASH_FBFALLBACK_REG */
    FLASH_FBFALLBACK_REG = 0x00000000u;
}

void system_init(void)
{
    /* Step 1: PCR initialization - MANDATORY first for RM46 bring-up stability */
    PCR_Init();
    PCR_EnableAllPeripherals();

    /* Step 2: Flash wait-state configuration before PLL handoff */
    system_setup_flash_waitstates();

    /* Step 3: Apply SYSTEM.x-ext.init register operations */

    /* [prov] regs.yaml:SYSTEM.MINITGCR (set_bits 0x0000000A) */
    SYS->MINITGCR |= 0x0000000Au;

    /* [prov] regs.yaml:SYSTEM.MSINENA (write 0xFFFFFFFF) */
    SYS->MSINENA = 0xFFFFFFFFu;

    /* [prov] regs.yaml:SYSTEM.MSTCGSTAT (write 0x00000100) */
    SYS->MSTCGSTAT = 0x00000100u;

    /* [prov] regs.yaml:SYSTEM.MINITGCR (clear_bits 0x00000005) */
    SYS->MINITGCR &= ~0x00000005u;

    /* [prov] regs.yaml:SYSTEM.CSVSTAT (write 0x00000000) */
    SYS->CSVSTAT = 0x00000000u;

    /* Step 4: Call PLL_Init() to configure and activate PLL + clock tree */
    /* MANDATORY - entry.c does NOT call PLL_Init() separately */
    PLL_Init();

    /* Clock configuration (PLL multiplier/dividers/mux) is application-owned;
     * see PLL_Configure* APIs in pll_driver.h (do not call here). */
}

uint32_t system_get_reset_cause(void)
{
    /* [prov] regs.yaml:SYSTEM.SYSESR */
    return SYS->SYSESR;
}

void system_soft_reset(void)
{
    /* [prov] regs.yaml:SYSTEM.SYSECR (bit 15 = SW reset) */
    SYS->SYSECR = 0x8000u;
}

uint32_t system_get_device_id(void)
{
    /* [prov] regs.yaml:SYSTEM.DEVID */
    return SYS->DEVID;
}

void system_clear_status_flags(void)
{
    /* [prov] regs.yaml:SYSTEM.SYSESR (write-1-to-clear) */
    SYS->SYSESR = SYS->SYSESR;
}
