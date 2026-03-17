/* BSP-GEN-META: created_at=2026-03-04T23:27:22-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file pll_driver.c
 * @brief PLL peripheral driver implementation
 * @details Complete implementation including initialization, configuration,
 *          and operational functions for the RM46 PLL and clock system.
 *          Implements HAL-aligned initialization profile with proven literal
 *          register sequences and dynamic frequency calculation.
 */

#include "pll_driver.h"
#include "reg_system.h"
#include <stdint.h>
#include <stdbool.h>

/******************************************************************************/
/*                            FACTS MIRROR                                    */
/******************************************************************************/
/*
 * AUTHORITATIVE VALUES FROM bus.yaml:
 * - OSCIN_HZ = 16000000 (16 MHz external crystal)
 * - HF_LPO_HZ = 9600000 (9.6 MHz high-frequency LPO)
 * - LF_LPO_HZ = 85000 (85 kHz low-frequency LPO)
 *
 * PLL1 CONFIGURATION (HAL-ALIGNED PROFILE):
 * - pllmul_register_encoding: hal_encoded
 * - pllmul_hal_literal: 0xA400
 * - pllmul_effective_nf: 120
 * - refclkdiv_register_value: 5 (NR-1, actual NR=6)
 * - plldiv_register_value: 1 (actual R=2^1=2)
 * - odpll_register_value: 1 (ODPLL-1, actual ODPLL=2)
 * - hal_literal_hclk_hz: 220000000 (220 MHz - authoritative for bringup)
 *
 * GHVSRC SOURCE IDS:
 * - OSCIN: 0
 * - PLL1: 1
 * - LF_LPO: 4
 * - HF_LPO: 5
 * - PLL2: 6
 *
 * RCLKSRC/VCLKASRC SYS SOURCE ID: 9
 */

#define OSCIN_HZ           16000000U
#define HF_LPO_HZ          9600000U
#define LF_LPO_HZ          85000U

#define PLL_LOCK_TIMEOUT   10000U  /* Iteration count for lock polling */

/******************************************************************************/
/*                         REGISTER BASE POINTERS                             */
/******************************************************************************/

static SYSTEM_REG_MAP_t * const SYSREG = (SYSTEM_REG_MAP_t *)0xFFFFFF00u;
static SYSTEM2_REG_MAP_t * const SYSREG2 = (SYSTEM2_REG_MAP_t *)0xFFFFE100u;

/******************************************************************************/
/*                         INTERNAL HELPER FUNCTIONS                          */
/******************************************************************************/

/**
 * @brief Wait for PLL1 lock with bounded iteration counter
 * @internal
 * @return pll_status_t PLL_STATUS_OK on lock, PLL_STATUS_TIMEOUT on failure
 */
static pll_status_t wait_for_pll1_lock(void)
{
    uint32_t timeout;
    
    timeout = PLL_LOCK_TIMEOUT;
    while (((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) == 0U) && (timeout > 0U)) {
        timeout--;
    }
    
    return (timeout > 0U) ? PLL_STATUS_OK : PLL_STATUS_TIMEOUT;
}

/**
 * @brief Wait for PLL2 lock with bounded iteration counter
 * @internal
 * @return pll_status_t PLL_STATUS_OK on lock, PLL_STATUS_TIMEOUT on failure
 */
static pll_status_t wait_for_pll2_lock(void)
{
    uint32_t timeout;
    
    timeout = PLL_LOCK_TIMEOUT;
    while (((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) == 0U) && (timeout > 0U)) {
        timeout--;
    }
    
    return (timeout > 0U) ? PLL_STATUS_OK : PLL_STATUS_TIMEOUT;
}

/**
 * @brief Get active clock source from GHVSRC register
 * @internal
 * @return uint32_t Source ID (0=OSCIN, 1=PLL1, 4=LF_LPO, 5=HF_LPO, 6=PLL2)
 */
static uint32_t get_active_ghv_source(void)
{
    return (SYSREG->GHVSRC & SYSTEM_GHVSRC_GHVSRC_MASK) >> SYSTEM_GHVSRC_GHVSRC_SHIFT;
}

/**
 * @brief Calculate HCLK frequency from active source
 * @internal
 * @return uint32_t HCLK frequency in Hz
 */
static uint32_t calculate_hclk_frequency(void)
{
    uint32_t source_id;
    uint32_t pllctl1;
    uint32_t pllctl2;
    uint32_t nf_raw;
    uint32_t nr_raw;
    uint32_t plldiv_raw;
    uint32_t odpll_raw;
    uint32_t NF;
    uint32_t NR;
    uint32_t R;
    uint32_t ODPLL;
    uint64_t f_pll;
    uint32_t f_hclk;
    
    source_id = get_active_ghv_source();
    
    switch (source_id) {
        case 0U:  /* OSCIN */
            return OSCIN_HZ;
            
        case 1U:  /* PLL1 */
            pllctl1 = SYSREG->PLLCTL1;
            pllctl2 = SYSREG->PLLCTL2;
            
            /* Extract bit fields */
            nf_raw = (pllctl1 & SYSTEM_PLLCTL1_PLLMUL_MASK) >> SYSTEM_PLLCTL1_PLLMUL_SHIFT;
            nr_raw = (pllctl1 & SYSTEM_PLLCTL1_REFCLKDIV_MASK) >> SYSTEM_PLLCTL1_REFCLKDIV_SHIFT;
            plldiv_raw = (pllctl1 & SYSTEM_PLLCTL1_PLLDIV_MASK) >> SYSTEM_PLLCTL1_PLLDIV_SHIFT;
            odpll_raw = (pllctl2 & SYSTEM_PLLCTL2_ODPLL_MASK) >> SYSTEM_PLLCTL2_ODPLL_SHIFT;
            
            /* HAL-encoded decode branch (authoritative for bringup) */
            if (nf_raw == 0xA400U) {
                /* Bring-up contract: use hal_literal_hclk_hz when encoded literal detected */
                return 220000000U;  /* hal_literal_hclk_hz from bus.yaml */
            }
            
            /* TRM dynamic decode path (fallback) */
            NF = nf_raw;
            NR = nr_raw + 1U;        /* Register stores NR-1 */
            R = 1U << plldiv_raw;    /* Output divider (2^PLLDIV) */
            ODPLL = odpll_raw + 1U;  /* Register stores ODPLL-1 */
            
            /* Calculate PLL frequency using 64-bit intermediates */
            f_pll = ((uint64_t)OSCIN_HZ * (uint64_t)NF) / ((uint64_t)NR * (uint64_t)R);
            f_hclk = (uint32_t)(f_pll / (uint64_t)ODPLL);
            
            return f_hclk;
            
        case 4U:  /* LF_LPO */
            return LF_LPO_HZ;
            
        case 5U:  /* HF_LPO */
            return HF_LPO_HZ;
            
        case 6U:  /* PLL2 */
            /* PLL2 uses same calculation as PLL1 but with PLLCTL3 */
            pllctl1 = SYSREG2->PLLCTL3;
            pllctl2 = SYSREG->PLLCTL2;  /* ODPLL is in PLLCTL2 for both PLLs */
            
            nf_raw = (pllctl1 & SYSTEM2_PLLCTL3_PLLMUL2_MASK) >> SYSTEM2_PLLCTL3_PLLMUL2_SHIFT;
            nr_raw = (pllctl1 & SYSTEM2_PLLCTL3_REFCLKDIV2_MASK) >> SYSTEM2_PLLCTL3_REFCLKDIV2_SHIFT;
            odpll_raw = (pllctl1 & SYSTEM2_PLLCTL3_ODPLL2_MASK) >> SYSTEM2_PLLCTL3_ODPLL2_SHIFT;
            
            NF = nf_raw;
            NR = nr_raw + 1U;
            R = 1U;  /* PLL2 uses ODPLL2 field, no separate PLLDIV */
            ODPLL = odpll_raw + 1U;
            
            f_pll = ((uint64_t)OSCIN_HZ * (uint64_t)NF) / ((uint64_t)NR * (uint64_t)R);
            f_hclk = (uint32_t)(f_pll / (uint64_t)ODPLL);
            
            return f_hclk;
            
        default:
            return OSCIN_HZ;  /* Safe default */
    }
}

/******************************************************************************/
/*                         PUBLIC API FUNCTIONS                               */
/******************************************************************************/

/**
 * @brief Initialize the PLL and clock system with HAL-aligned configuration
 * @details Implements the complete RM46 HAL-aligned initialization sequence:
 *          1. Disable PLL1/PLL2 sources and acknowledge
 *          2. Clear GLBSTAT slip flags
 *          3. Program PLLCTL1/PLLCTL2/PLLCTL3 with proven literals
 *          4. Program source/domain disable snapshots
 *          5. Enable sources and poll CSVSTAT for validity
 *          6. Program CLKCNTL VCLK/VCLK2 dividers BEFORE GHVSRC switch
 *          7. Switch GHVSRC to PLL1 source
 *          8. Program RCLKSRC and VCLKASRC
 *          9. Program CLK2CNTRL for VCLK3/VCLK4 dividers
 *          10. Program VCLKACON1 for VCLKA3/VCLKA4
 *          11. Clear PLLDIV fields in PLLCTL1/PLLCTL3
 *          12. Enable peripheral clock enable (PENA)
 */
void PLL_Init(void)
{
    /* Step 1: Disable PLL1 and PLL2 sources before reconfiguration */
    SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF | SYSTEM_CSDISSET_SETCLKSR6OFF;
    
    /* Step 2: Clear global status slip detection flags */
    SYSREG->GLBSTAT = 0x00000301U;
    
    /* Step 3: Program PLL control registers with HAL-aligned literals */
    /* PLLCTL1: ROS=0, MASK_SLIP=2, PLLDIV=31, ROF=0, REFCLKDIV=5, PLLMUL=0xA400 */
    SYSREG->PLLCTL1 = 0x20000000U | (0x1FU << 24) | ((6U - 1U) << 16) | 0xA400U;
    
    /* PLLCTL2: FMENA=0, SPREADINGRATE=255, MULMOD=7, ODPLL=1, SPR_AMOUNT=61 */
    SYSREG->PLLCTL2 = (255U << 22) | (7U << 12) | ((2U - 1U) << 9) | 61U;
    
    /* PLLCTL3: ODPLL2=1, REFCLKDIV2=5, PLLMUL2=0xA400 */
    SYSREG2->PLLCTL3 = ((2U - 1U) << 29) | (0x1FU << 24) | ((6U - 1U) << 16) | 0xA400U;
    
    /* Step 4: Program source and domain disable states */
    SYSREG->CSDIS = 0x0000008CU;
    SYSREG->CDDIS = 0x00000020U;
    
    /* Step 5: Enable OSCIN source */
    SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR0OFF;
    
    /* Enable PLL1 and PLL2 sources */
    SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF | SYSTEM_CSDISCLR_CLRCLKSR6OFF;
    
    /* Poll CSVSTAT for PLL1 and PLL2 validity */
    wait_for_pll1_lock();
    wait_for_pll2_lock();
    
    /* Step 6: Program VCLK and VCLK2 dividers BEFORE GHVSRC switch */
    /* CRITICAL: This prevents VCLK from exceeding 110MHz when HCLK switches to 220MHz */
    SYSREG->CLKCNTL = (SYSREG->CLKCNTL & 0xF0F0FFFFU) | (1U << 24) | (1U << 16);
    
    /* Step 7: Switch GHVSRC to PLL1 (source ID = 1) */
    SYSREG->GHVSRC = 0x00000001U;
    
    /* Step 8: Program RCLKSRC and VCLKASRC (source ID = 9 for sys/VCLK) */
    SYSREG->RCLKSRC = 0x01090109U;
    SYSREG->VCLKASRC = 0x00000909U;
    
    /* Step 9: Program CLK2CNTRL for VCLK3 and VCLK4 dividers */
    SYSREG2->CLK2CNTRL = (SYSREG2->CLK2CNTRL & 0xFFFFF0F0U) | (1U << 8) | (1U << 0);
    
    /* Step 10: Program VCLKACON1 for VCLKA3 and VCLKA4 */
    SYSREG2->VCLKACON1 = 0x00020002U;
    
    /* Step 11: Clear PLLDIV fields in PLLCTL1 and PLLCTL3 */
    SYSREG->PLLCTL1 &= ~0x1F000000U;
    SYSREG2->PLLCTL3 &= ~0x1F000000U;
    
    /* Step 12: Enable peripheral clock enable */
    SYSREG->CLKCNTL |= SYSTEM_CLKCNTL_PENA;
    
    /* Enable core clock domains */
    SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF | 
                       SYSTEM_CDDISCLR_CLRHCLKOFF | 
                       SYSTEM_CDDISCLR_CLRVCLKPOFF | 
                       SYSTEM_CDDISCLR_CLRVCLK2OFF;
}

/**
 * @brief Get the frequency in Hz for the specified clock domain
 * @details Calculates frequency dynamically from hardware registers and
 *          active clock source configuration. Supports HAL-encoded PLLMUL
 *          decode with authoritative literal override for bringup.
 *
 * @param domain Clock domain identifier
 * @return uint32_t Frequency in Hz, or 0 if domain is invalid/disabled
 */
uint32_t PLL_GetFrequency(clock_domain_t domain)
{
    uint32_t hclk_hz;
    uint32_t vclkr;
    uint32_t vclk2r;
    uint32_t vclk3r;
    uint32_t vclk4r;
    
    hclk_hz = calculate_hclk_frequency();
    
    switch (domain) {
        case CLOCKDOMAIN_OSCIN:
            return OSCIN_HZ;
            
        case CLOCKDOMAIN_HF_LPO:
            return HF_LPO_HZ;
            
        case CLOCKDOMAIN_LF_LPO:
            return LF_LPO_HZ;
            
        case CLOCKDOMAIN_PLL1:
        case CLOCKDOMAIN_GCLK:
        case CLOCKDOMAIN_HCLK:
            return hclk_hz;
            
        case CLOCKDOMAIN_PLL2:
            /* PLL2 treated as same frequency for this implementation */
            return hclk_hz;
            
        case CLOCKDOMAIN_VCLK:
        case CLOCKDOMAIN_VCLKA1:
        case CLOCKDOMAIN_RTICLK:
            vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT;
            return hclk_hz / (vclkr + 1U);
            
        case CLOCKDOMAIN_VCLK2:
            vclk2r = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLK2R_MASK) >> SYSTEM_CLKCNTL_VCLK2R_SHIFT;
            return hclk_hz / (vclk2r + 1U);
            
        case CLOCKDOMAIN_VCLK3:
        case CLOCKDOMAIN_VCLKA3:
            vclk3r = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK3R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT;
            return hclk_hz / (vclk3r + 1U);
            
        case CLOCKDOMAIN_VCLK4:
        case CLOCKDOMAIN_VCLKA4:
            vclk4r = (SYSREG2->CLK2CNTRL & SYSTEM2_CLK2CNTRL_VCLK4R_MASK) >> SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT;
            return hclk_hz / (vclk4r + 1U);
            
        case CLOCKDOMAIN_EXTCLKIN1:
        case CLOCKDOMAIN_EXTCLKIN2:
            /* External clock inputs - frequency not determinable from registers */
            return 0U;
            
        default:
            return 0U;
    }
}

/**
 * @brief Enable the specified clock domain
 * @details Clears the disable bit for the specified clock source or domain.
 *          Idempotent operation - safe to call multiple times.
 *
 * @param domain Clock domain to enable
 * @return pll_status_t PLL_STATUS_OK on success, PLL_STATUS_INVALID_PARAM if domain invalid
 */
pll_status_t PLL_EnableClock(clock_domain_t domain)
{
    switch (domain) {
        case CLOCKDOMAIN_OSCIN:
        case CLOCKDOMAIN_EXTCLKIN1:
        case CLOCKDOMAIN_EXTCLKIN2:
            /* Always enabled - no action needed */
            return PLL_STATUS_OK;
            
        case CLOCKDOMAIN_PLL1:
            SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF;
            break;
            
        case CLOCKDOMAIN_PLL2:
            SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF;
            break;
            
        case CLOCKDOMAIN_HF_LPO:
            SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR5OFF;
            break;
            
        case CLOCKDOMAIN_LF_LPO:
            SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR4OFF;
            break;
            
        case CLOCKDOMAIN_GCLK:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF;
            break;
            
        case CLOCKDOMAIN_HCLK:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRHCLKOFF;
            break;
            
        case CLOCKDOMAIN_VCLK:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKPOFF;
            break;
            
        case CLOCKDOMAIN_VCLK2:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK2OFF;
            break;
            
        case CLOCKDOMAIN_VCLK3:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK3OFF;
            break;
            
        case CLOCKDOMAIN_VCLK4:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK4OFF;
            break;
            
        case CLOCKDOMAIN_VCLKA1:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA1OFF;
            break;
            
        case CLOCKDOMAIN_VCLKA3:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA3OFF;
            break;
            
        case CLOCKDOMAIN_VCLKA4:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA4OFF;
            break;
            
        case CLOCKDOMAIN_RTICLK:
            SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRRTI1CLKOFF;
            break;
            
        default:
            return PLL_STATUS_INVALID_PARAM;
    }
    
    return PLL_STATUS_OK;
}

/**
 * @brief Disable the specified clock domain
 * @details Sets the disable bit for the specified clock source or domain.
 *          Use with caution - only disable when peripheral is confirmed inactive.
 *
 * @param domain Clock domain to disable
 * @return pll_status_t PLL_STATUS_OK on success, PLL_STATUS_INVALID_PARAM if domain invalid
 */
pll_status_t PLL_DisableClock(clock_domain_t domain)
{
    switch (domain) {
        case CLOCKDOMAIN_OSCIN:
        case CLOCKDOMAIN_EXTCLKIN1:
        case CLOCKDOMAIN_EXTCLKIN2:
            /* Cannot disable primary clock sources */
            return PLL_STATUS_INVALID_PARAM;
            
        case CLOCKDOMAIN_PLL1:
            SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF;
            break;
            
        case CLOCKDOMAIN_PLL2:
            SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF;
            break;
            
        case CLOCKDOMAIN_HF_LPO:
            SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR5OFF;
            break;
            
        case CLOCKDOMAIN_LF_LPO:
            SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR4OFF;
            break;
            
        case CLOCKDOMAIN_GCLK:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETGCLKOFF;
            break;
            
        case CLOCKDOMAIN_HCLK:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETHCLKOFF;
            break;
            
        case CLOCKDOMAIN_VCLK:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKPOFF;
            break;
            
        case CLOCKDOMAIN_VCLK2:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK2OFF;
            break;
            
        case CLOCKDOMAIN_VCLK3:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK3OFF;
            break;
            
        case CLOCKDOMAIN_VCLK4:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLK4OFF;
            break;
            
        case CLOCKDOMAIN_VCLKA1:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA1OFF;
            break;
            
        case CLOCKDOMAIN_VCLKA3:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA3OFF;
            break;
            
        case CLOCKDOMAIN_VCLKA4:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETVCLKA4OFF;
            break;
            
        case CLOCKDOMAIN_RTICLK:
            SYSREG->CDDISSET = SYSTEM_CDDISSET_SETRTI1CLKOFF;
            break;
            
        default:
            return PLL_STATUS_INVALID_PARAM;
    }
    
    return PLL_STATUS_OK;
}

/**
 * @brief Configure PLL parameters at runtime
 * @details Disables PLL, applies new configuration, waits for lock.
 *          Advanced use only - typically not needed after PLL_Init().
 *
 * @param config Pointer to PLL configuration structure
 * @return pll_status_t Status code
 */
pll_status_t PLL_ConfigurePLL(const pll_config_t* config)
{
    uint32_t pllctl1_value;
    uint32_t pllctl2_value;
    pll_status_t status;
    
    if (config == (const pll_config_t*)0) {
        return PLL_STATUS_INVALID_PARAM;
    }
    
    /* Validate parameters */
    if ((config->nf_multiplier == 0U) || (config->nf_multiplier > 255U) ||
        (config->nr_ref_divider > 63U) || (config->r_post_divider > 15U) ||
        (config->odpll_output_divider == 0U) || (config->odpll_output_divider > 31U)) {
        return PLL_STATUS_INVALID_PARAM;
    }
    
    if (config->pll_instance == PLL_INSTANCE_1) {
        /* Disable PLL1 */
        SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF;
        
        /* Build PLLCTL1 value */
        pllctl1_value = ((config->r_post_divider & 0x1FU) << 24) |
                        ((config->nr_ref_divider & 0x3FU) << 16) |
                        (config->nf_multiplier & 0xFFFFU);
        
        /* Build PLLCTL2 value */
        pllctl2_value = ((config->odpll_output_divider - 1U) & 0x07U) << 9;
        if (config->enable_modulation) {
            pllctl2_value |= SYSTEM_PLLCTL2_FMENA;
        }
        
        /* Write configuration */
        SYSREG->PLLCTL1 = pllctl1_value;
        SYSREG->PLLCTL2 = pllctl2_value;
        
        /* Enable PLL1 */
        SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF;
        
        /* Wait for lock */
        status = wait_for_pll1_lock();
        
    } else if (config->pll_instance == PLL_INSTANCE_2) {
        /* Disable PLL2 */
        SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF;
        
        /* Build PLLCTL3 value */
        pllctl1_value = (((config->odpll_output_divider - 1U) & 0x07U) << 29) |
                        ((config->nr_ref_divider & 0x3FU) << 16) |
                        (config->nf_multiplier & 0xFFFFU);
        
        /* Write configuration */
        SYSREG2->PLLCTL3 = pllctl1_value;
        
        /* Enable PLL2 */
        SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF;
        
        /* Wait for lock */
        status = wait_for_pll2_lock();
        
    } else {
        return PLL_STATUS_INVALID_PARAM;
    }
    
    return status;
}

/**
 * @brief Configure clock domain divider ratio
 * @details Applies to configurable domains (VCLK, VCLK2, VCLK3, VCLK4).
 *
 * @param config Pointer to divider configuration structure
 * @return pll_status_t Status code
 */
pll_status_t PLL_SetClockDivider(const clock_divider_config_t* config)
{
    uint32_t reg_value;
    
    if (config == (const clock_divider_config_t*)0) {
        return PLL_STATUS_INVALID_PARAM;
    }
    
    if (config->divider > 15U) {
        return PLL_STATUS_INVALID_PARAM;
    }
    
    switch (config->domain) {
        case CLOCKDOMAIN_VCLK:
            reg_value = SYSREG->CLKCNTL;
            reg_value &= ~SYSTEM_CLKCNTL_VCLKR_MASK;
            reg_value |= (config->divider << SYSTEM_CLKCNTL_VCLKR_SHIFT);
            SYSREG->CLKCNTL = reg_value;
            break;
            
        case CLOCKDOMAIN_VCLK2:
            reg_value = SYSREG->CLKCNTL;
            reg_value &= ~SYSTEM_CLKCNTL_VCLK2R_MASK;
            reg_value |= (config->divider << SYSTEM_CLKCNTL_VCLK2R_SHIFT);
            SYSREG->CLKCNTL = reg_value;
            break;
            
        case CLOCKDOMAIN_VCLK3:
            reg_value = SYSREG2->CLK2CNTRL;
            reg_value &= ~SYSTEM2_CLK2CNTRL_VCLK3R_MASK;
            reg_value |= (config->divider << SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT);
            SYSREG2->CLK2CNTRL = reg_value;
            break;
            
        case CLOCKDOMAIN_VCLK4:
            reg_value = SYSREG2->CLK2CNTRL;
            reg_value &= ~SYSTEM2_CLK2CNTRL_VCLK4R_MASK;
            reg_value |= (config->divider << SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT);
            SYSREG2->CLK2CNTRL = reg_value;
            break;
            
        default:
            return PLL_STATUS_INVALID_PARAM;
    }
    
    return PLL_STATUS_OK;
}

/**
 * @brief Read PLL lock status and clock slip detection flags
 * @details Populates the provided status structure with current state.
 *
 * @param status Pointer to status structure to populate
 */
void PLL_GetLockStatus(pll_lock_status_t* status)
{
    uint32_t csvstat;
    uint32_t glbstat;
    
    if (status == (pll_lock_status_t*)0) {
        return;
    }
    
    csvstat = SYSREG->CSVSTAT;
    glbstat = SYSREG->GLBSTAT;
    
    status->pll1_locked = ((csvstat & SYSTEM_CSVSTAT_CLKSR1V) != 0U);
    status->pll2_locked = ((csvstat & SYSTEM_CSVSTAT_CLKSR6V) != 0U);
    status->clock_slip_detected = ((glbstat & (SYSTEM_GLBSTAT_RFSLIP | SYSTEM_GLBSTAT_FBSLIP)) != 0U);
}

/**
 * @brief Poll for PLL lock with timeout
 * @details Waits for specified PLL to achieve lock state.
 *
 * @param pll PLL instance to wait for
 * @param timeout_us Timeout in microseconds (0 = infinite)
 * @return pll_status_t PLL_STATUS_OK when locked, PLL_STATUS_TIMEOUT on timeout
 */
pll_status_t PLL_WaitForLock(pll_instance_t pll, uint32_t timeout_us)
{
    uint32_t timeout;
    
    /* Convert timeout to iteration count (rough approximation) */
    timeout = (timeout_us == 0U) ? 0xFFFFFFFFU : (timeout_us / 10U);
    if (timeout == 0U) {
        timeout = 1U;
    }
    
    if (pll == PLL_INSTANCE_1) {
        while (((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR1V) == 0U) && (timeout > 0U)) {
            timeout--;
        }
    } else if (pll == PLL_INSTANCE_2) {
        while (((SYSREG->CSVSTAT & SYSTEM_CSVSTAT_CLKSR6V) == 0U) && (timeout > 0U)) {
            timeout--;
        }
    } else {
        return PLL_STATUS_INVALID_PARAM;
    }
    
    return (timeout > 0U) ? PLL_STATUS_OK : PLL_STATUS_TIMEOUT;
}

/**
 * @brief Enable the specified PLL instance
 * @details Enables PLL and waits for lock before returning.
 *
 * @param pll PLL instance to enable
 * @return pll_status_t Status code
 */
pll_status_t PLL_EnablePLL(pll_instance_t pll)
{
    if (pll == PLL_INSTANCE_1) {
        SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF;
        return wait_for_pll1_lock();
    } else if (pll == PLL_INSTANCE_2) {
        SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF;
        return wait_for_pll2_lock();
    } else {
        return PLL_STATUS_INVALID_PARAM;
    }
}

/**
 * @brief Disable the specified PLL instance
 * @details Use with extreme caution - may affect system clocks.
 *
 * @param pll PLL instance to disable
 * @return pll_status_t Status code
 */
pll_status_t PLL_DisablePLL(pll_instance_t pll)
{
    if (pll == PLL_INSTANCE_1) {
        SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR1OFF;
        return PLL_STATUS_OK;
    } else if (pll == PLL_INSTANCE_2) {
        SYSREG->CSDISSET = SYSTEM_CSDISSET_SETCLKSR6OFF;
        return PLL_STATUS_OK;
    } else {
        return PLL_STATUS_INVALID_PARAM;
    }
}

/**
 * @brief Clear clock slip detection flags
 * @details Should be called after handling a clock slip event.
 */
void PLL_ClearClockSlipStatus(void)
{
    SYSREG->GLBSTAT = SYSTEM_GLBSTAT_RFSLIP | SYSTEM_GLBSTAT_FBSLIP;
}

/**
 * @brief Get the external oscillator frequency
 * @details Returns the configured OSCIN frequency (typically 16 MHz).
 *
 * @return uint32_t OSCIN frequency in Hz
 */
uint32_t PLL_GetOscillatorFrequency(void)
{
    return OSCIN_HZ;
}

/**
 * @brief Select clock source for a configurable clock domain
 * @details Source_id values are device-specific (see register mappings).
 *
 * @param domain Clock domain to configure
 * @param source_id Source ID value
 * @return pll_status_t Status code
 */
pll_status_t PLL_SelectClockSource(clock_domain_t domain, uint32_t source_id)
{
    uint32_t reg_value;
    
    switch (domain) {
        case CLOCKDOMAIN_GCLK:
        case CLOCKDOMAIN_HCLK:
            /* Configure GHVSRC */
            reg_value = SYSREG->GHVSRC;
            reg_value &= ~SYSTEM_GHVSRC_GHVSRC_MASK;
            reg_value |= (source_id << SYSTEM_GHVSRC_GHVSRC_SHIFT);
            SYSREG->GHVSRC = reg_value;
            break;
            
        case CLOCKDOMAIN_VCLKA1:
            /* Configure VCLKASRC */
            reg_value = SYSREG->VCLKASRC;
            reg_value &= ~SYSTEM_VCLKASRC_VCLKA1S_MASK;
            reg_value |= (source_id << SYSTEM_VCLKASRC_VCLKA1S_SHIFT);
            SYSREG->VCLKASRC = reg_value;
            break;
            
        case CLOCKDOMAIN_RTICLK:
            /* Configure RCLKSRC */
            reg_value = SYSREG->RCLKSRC;
            reg_value &= ~SYSTEM_RCLKSRC_RTI1SRC_MASK;
            reg_value |= (source_id << SYSTEM_RCLKSRC_RTI1SRC_SHIFT);
            SYSREG->RCLKSRC = reg_value;
            break;
            
        case CLOCKDOMAIN_VCLKA3:
            /* Configure VCLKACON1 VCLKA3S */
            reg_value = SYSREG2->VCLKACON1;
            reg_value &= ~SYSTEM2_VCLKACON1_VCLKA3S_MASK;
            reg_value |= (source_id << SYSTEM2_VCLKACON1_VCLKA3S_SHIFT);
            SYSREG2->VCLKACON1 = reg_value;
            break;
            
        case CLOCKDOMAIN_VCLKA4:
            /* Configure VCLKACON1 VCLKA4S */
            reg_value = SYSREG2->VCLKACON1;
            reg_value &= ~SYSTEM2_VCLKACON1_VCLKA4S_MASK;
            reg_value |= (source_id << SYSTEM2_VCLKACON1_VCLKA4S_SHIFT);
            SYSREG2->VCLKACON1 = reg_value;
            break;
            
        default:
            return PLL_STATUS_INVALID_PARAM;
    }
    
    return PLL_STATUS_OK;
}
