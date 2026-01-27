/**
 * @file clock.c
 * @brief Clock service implementation for TI Hercules RM46
 */

#include <stdint.h>
#include "clock.h"

/* Base addresses */
#define SYSTEM_BASE     (0xFFFFFF00u)
#define PCR_BASE        (0xFFFFE000u)

/* SYSTEM register offsets */
#define CSDIS_OFFSET    (0x30u)
#define CSDISCLR_OFFSET (0x38u)
#define CDDIS_OFFSET    (0x3Cu)
#define CDDISCLR_OFFSET (0x44u)
#define CLKCNTL_OFFSET  (0xD0u)

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* CSDIS bit positions (clock source disable, active-high disables) */
#define CSDIS_CLKSR0OFF (1u << 0)  /* OSCIN */
#define CSDIS_CLKSR1OFF (1u << 1)  /* PLL1 */
#define CSDIS_CLKSR3OFF (1u << 3)  /* EXTCLKIN1 */
#define CSDIS_CLKSR4OFF (1u << 4)  /* LF_LPO */
#define CSDIS_CLKSR5OFF (1u << 5)  /* HF_LPO */
#define CSDIS_CLKSR6OFF (1u << 6)  /* PLL2 */
#define CSDIS_CLKSR7OFF (1u << 7)  /* EXTCLKIN2 */

/* CDDIS bit positions (clock domain disable, active-high disables) */
#define CDDIS_GCLKOFF   (1u << 0)
#define CDDIS_HCLKOFF   (1u << 1)
#define CDDIS_VCLKPOFF  (1u << 2)
#define CDDIS_VCLK2OFF  (1u << 3)
#define CDDIS_VCLKA1OFF (1u << 4)
#define CDDIS_RTIOFF    (1u << 6)
#define CDDIS_VCLK3OFF  (1u << 8)
#define CDDIS_VCLK4OFF  (1u << 9)
#define CDDIS_VCLKA3OFF (1u << 10)
#define CDDIS_VCLKA4OFF (1u << 11)

/* Fixed source frequencies */
#define OSCIN_FREQ_HZ   (16000000u)
#define HF_LPO_FREQ_HZ  (9600000u)
#define LF_LPO_FREQ_HZ  (85000u)

/* Default dividers */
#define VCLK_DEFAULT_DIVIDER  (2u)
#define VCLK2_DEFAULT_DIVIDER (2u)
#define VCLK3_DEFAULT_DIVIDER (2u)
#define VCLK4_DEFAULT_DIVIDER (2u)

/* Tracked divider state (for clock_set_divider / clock_get_hz) */
static uint32_t vclk_divider = VCLK_DEFAULT_DIVIDER;
static uint32_t vclk2_divider = VCLK2_DEFAULT_DIVIDER;

/**
 * @brief Enable a peripheral clock
 * @ingroup BSP_CLOCK
 *
 * Clears the disable bits for required clock sources and domains.
 */
int clock_enable(clock_ref_t ref)
{
    switch (ref) {
        case CLOCKREF_OSCIN:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            REG32(SYSTEM_BASE + CSDISCLR_OFFSET) = CSDIS_CLKSR0OFF;
            break;

        case CLOCKREF_HF_LPO:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            REG32(SYSTEM_BASE + CSDISCLR_OFFSET) = CSDIS_CLKSR5OFF;
            break;

        case CLOCKREF_LF_LPO:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            REG32(SYSTEM_BASE + CSDISCLR_OFFSET) = CSDIS_CLKSR4OFF;
            break;

        case CLOCKREF_GCLK:
            /* GCLK depends on OSCIN source and GCLK domain */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            REG32(SYSTEM_BASE + CSDISCLR_OFFSET) = CSDIS_CLKSR0OFF;
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            REG32(SYSTEM_BASE + CDDISCLR_OFFSET) = CDDIS_GCLKOFF;
            break;

        case CLOCKREF_HCLK:
            /* HCLK depends on OSCIN source and HCLK domain */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            REG32(SYSTEM_BASE + CSDISCLR_OFFSET) = CSDIS_CLKSR0OFF;
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            REG32(SYSTEM_BASE + CDDISCLR_OFFSET) = CDDIS_HCLKOFF;
            break;

        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* VCLK depends on HCLK (which depends on OSCIN) and VCLK domain */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            REG32(SYSTEM_BASE + CSDISCLR_OFFSET) = CSDIS_CLKSR0OFF;
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            REG32(SYSTEM_BASE + CDDISCLR_OFFSET) = CDDIS_HCLKOFF | CDDIS_VCLKPOFF;
            break;

        default:
            return -1;
    }
    return 0;
}

/**
 * @brief Query the frequency of a clock
 * @ingroup BSP_CLOCK
 *
 * Returns the best-known frequency derived from YAML facts.
 */
uint32_t clock_get_hz(clock_ref_t ref)
{
    switch (ref) {
        case CLOCKREF_OSCIN:
            return OSCIN_FREQ_HZ;

        case CLOCKREF_HF_LPO:
            return HF_LPO_FREQ_HZ;

        case CLOCKREF_LF_LPO:
            return LF_LPO_FREQ_HZ;

        case CLOCKREF_GCLK:
            /* GCLK defaults to OSCIN at 1:1 */
            return OSCIN_FREQ_HZ;

        case CLOCKREF_HCLK:
            /* HCLK defaults to OSCIN at 1:1 */
            return OSCIN_FREQ_HZ;

        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* VCLK = HCLK / divider (defaults to /2) */
            return OSCIN_FREQ_HZ / vclk_divider;

        default:
            return 0;
    }
}

/**
 * @brief Set the divider for a peripheral clock (APPLICATION-ONLY)
 * @ingroup BSP_CLOCK
 *
 * @warning APPLICATION-ONLY: Do not call from peripheral drivers.
 */
int clock_set_divider(clock_ref_t ref, uint32_t divider)
{
    uint32_t reg_val;
    uint32_t encoded;

    /* Validate divider range (1..16) */
    if (divider < 1u || divider > 16u) {
        return -1;
    }

    /* Encode divider: register value = divider - 1 */
    encoded = divider - 1u;

    switch (ref) {
        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* [prov] regs.yaml:SYSTEM.CLKCNTL */
            reg_val = REG32(SYSTEM_BASE + CLKCNTL_OFFSET);
            reg_val &= ~(0xFu << 16);  /* Clear VCLKR field (bits 19:16) */
            reg_val |= (encoded << 16);
            REG32(SYSTEM_BASE + CLKCNTL_OFFSET) = reg_val;
            vclk_divider = divider;
            break;

        default:
            /* Unsupported clock reference */
            return -1;
    }

    return 0;
}