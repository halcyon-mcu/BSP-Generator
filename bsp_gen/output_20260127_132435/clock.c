/**
 * @file clock.c
 * @brief Clock management service implementation for TI Hercules RM46
 */

#include <stdint.h>
#include "clock.h"

/* ============================================================================
 * REGISTER ACCESS MACROS
 * ========================================================================= */

#define REG32(addr) (*(volatile uint32_t *)(addr))

#define SYSTEM_BASE             (0xFFFFFF00u)
#define PCR_BASE                (0xFFFFE000u)

#define SYSTEM_CSDIS            REG32(SYSTEM_BASE + 0x30u)
#define SYSTEM_CSDISCLR         REG32(SYSTEM_BASE + 0x38u)
#define SYSTEM_CDDIS            REG32(SYSTEM_BASE + 0x3Cu)
#define SYSTEM_CDDISCLR         REG32(SYSTEM_BASE + 0x44u)
#define SYSTEM_GHVSRC           REG32(SYSTEM_BASE + 0x48u)
#define SYSTEM_VCLKASRC         REG32(SYSTEM_BASE + 0x4Cu)
#define SYSTEM_RCLKSRC          REG32(SYSTEM_BASE + 0x50u)
#define SYSTEM_CLKCNTL          REG32(SYSTEM_BASE + 0xD0u)

/* ============================================================================
 * BIT POSITIONS AND MASKS
 * ========================================================================= */

#define CSDIS_BIT_OSCIN         (0u)
#define CSDIS_BIT_PLL1          (1u)
#define CSDIS_BIT_EXTCLKIN1     (3u)
#define CSDIS_BIT_LF_LPO        (4u)
#define CSDIS_BIT_HF_LPO        (5u)
#define CSDIS_BIT_PLL2          (6u)
#define CSDIS_BIT_EXTCLKIN2     (7u)

#define CDDIS_BIT_GCLK          (0u)
#define CDDIS_BIT_HCLK          (1u)
#define CDDIS_BIT_VCLK          (2u)
#define CDDIS_BIT_VCLK2         (3u)
#define CDDIS_BIT_VCLKA1        (4u)
#define CDDIS_BIT_VCLKA2        (5u)
#define CDDIS_BIT_RTICLK        (6u)
#define CDDIS_BIT_VCLK3         (8u)
#define CDDIS_BIT_VCLK4         (9u)
#define CDDIS_BIT_VCLKA3        (10u)
#define CDDIS_BIT_VCLKA4        (11u)

#define CLKCNTL_VCLKR_SHIFT     (16u)
#define CLKCNTL_VCLK2R_SHIFT    (24u)

/* ============================================================================
 * FIXED FREQUENCIES (Hz)
 * ========================================================================= */

#define FREQ_OSCIN              (16000000u)
#define FREQ_HF_LPO             (9600000u)
#define FREQ_LF_LPO             (85000u)

/* ============================================================================
 * DEFAULT DIVIDER VALUES
 * ========================================================================= */

#define DEFAULT_DIVIDER_VCLK    (2u)
#define DEFAULT_DIVIDER_VCLK2   (2u)
#define DEFAULT_DIVIDER_VCLK3   (2u)
#define DEFAULT_DIVIDER_VCLK4   (2u)

/* ============================================================================
 * CLOCK ENABLE IMPLEMENTATION
 * ========================================================================= */

/**
 * @brief Enable a clock domain.
 * @ingroup BSP_CLOCK
 */
int clock_enable(clock_ref_t ref)
{
    switch (ref) {
        case CLOCKREF_OSCIN:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
            break;

        case CLOCKREF_HF_LPO:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            SYSTEM_CSDISCLR = (1u << CSDIS_BIT_HF_LPO);
            break;

        case CLOCKREF_LF_LPO:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            SYSTEM_CSDISCLR = (1u << CSDIS_BIT_LF_LPO);
            break;

        case CLOCKREF_GCLK:
            /* GCLK requires OSCIN source enabled and GCLK domain enabled */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            SYSTEM_CDDISCLR = (1u << CDDIS_BIT_GCLK);
            break;

        case CLOCKREF_HCLK:
            /* HCLK requires OSCIN source enabled and HCLK domain enabled */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
            break;

        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* VCLK requires OSCIN enabled, HCLK domain enabled, VCLK domain enabled */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
            break;

        default:
            return -1;
    }

    return 0;
}

/* ============================================================================
 * CLOCK FREQUENCY QUERY IMPLEMENTATION
 * ========================================================================= */

/**
 * @brief Query clock frequency.
 * @ingroup BSP_CLOCK
 */
uint32_t clock_get_hz(clock_ref_t ref)
{
    uint32_t hclk_hz;
    uint32_t vclk_divider;
    uint32_t vclk2_divider;
    uint32_t clkcntl_val;

    switch (ref) {
        case CLOCKREF_OSCIN:
            return FREQ_OSCIN;

        case CLOCKREF_HF_LPO:
            return FREQ_HF_LPO;

        case CLOCKREF_LF_LPO:
            return FREQ_LF_LPO;

        case CLOCKREF_GCLK:
            /* GCLK defaults to OSCIN, same frequency as HCLK */
            return FREQ_OSCIN;

        case CLOCKREF_HCLK:
            /* HCLK defaults to OSCIN (no divider) */
            return FREQ_OSCIN;

        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* VCLK = HCLK / divider */
            hclk_hz = FREQ_OSCIN;
            /* [prov] regs.yaml:SYSTEM.CLKCNTL */
            clkcntl_val = SYSTEM_CLKCNTL;
            vclk_divider = ((clkcntl_val >> CLKCNTL_VCLKR_SHIFT) & 0xFu);
            if (vclk_divider == 0u) {
                vclk_divider = 1u;
            }
            return hclk_hz / vclk_divider;

        default:
            return 0u;
    }
}

/* ============================================================================
 * APPLICATION-ONLY CLOCK CONFIGURATION API
 * ========================================================================= */

/**
 * @brief Set VCLK divider.
 * @ingroup BSP_CLOCK
 * @warning APPLICATION-ONLY. Do not call from peripheral drivers.
 */
int clock_set_vclk_divider(uint32_t divider)
{
    uint32_t clkcntl_val;
    uint32_t encoded_divider;

    if (divider < 1u || divider > 16u) {
        return -1;
    }

    encoded_divider = divider - 1u;

    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    clkcntl_val = SYSTEM_CLKCNTL;
    clkcntl_val &= ~(0xFu << CLKCNTL_VCLKR_SHIFT);
    clkcntl_val |= (encoded_divider << CLKCNTL_VCLKR_SHIFT);
    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    SYSTEM_CLKCNTL = clkcntl_val;

    return 0;
}

/**
 * @brief Set VCLK2 divider.
 * @ingroup BSP_CLOCK
 * @warning APPLICATION-ONLY. Do not call from peripheral drivers.
 */
int clock_set_vclk2_divider(uint32_t divider)
{
    uint32_t clkcntl_val;
    uint32_t encoded_divider;

    if (divider < 1u || divider > 16u) {
        return -1;
    }

    encoded_divider = divider - 1u;

    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    clkcntl_val = SYSTEM_CLKCNTL;
    clkcntl_val &= ~(0xFu << CLKCNTL_VCLK2R_SHIFT);
    clkcntl_val |= (encoded_divider << CLKCNTL_VCLK2R_SHIFT);
    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    SYSTEM_CLKCNTL = clkcntl_val;

    return 0;
}