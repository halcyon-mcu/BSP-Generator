/**
 * @file clock.c
 * @brief Clock Service Module Implementation
 */

#include <stdint.h>
#include "clock.h"

/* Register access macro */
#define REG32(addr) (*(volatile uint32_t *)(addr))

/* SYSTEM peripheral base and register offsets */
#define SYSTEM_BASE         (0xFFFFFF00u)
#define SYSTEM_CSDIS_OFFSET (0x30u)
#define SYSTEM_CSDISCLR_OFFSET (0x38u)
#define SYSTEM_CDDIS_OFFSET (0x3Cu)
#define SYSTEM_CDDISCLR_OFFSET (0x44u)
#define SYSTEM_CLKCNTL_OFFSET (0xD0u)

/* SYSTEM register addresses */
#define SYSTEM_CSDIS    (SYSTEM_BASE + SYSTEM_CSDIS_OFFSET)
#define SYSTEM_CSDISCLR (SYSTEM_BASE + SYSTEM_CSDISCLR_OFFSET)
#define SYSTEM_CDDIS    (SYSTEM_BASE + SYSTEM_CDDIS_OFFSET)
#define SYSTEM_CDDISCLR (SYSTEM_BASE + SYSTEM_CDDISCLR_OFFSET)
#define SYSTEM_CLKCNTL  (SYSTEM_BASE + SYSTEM_CLKCNTL_OFFSET)

/* CSDIS bit positions */
#define CSDIS_CLKSR0OFF_BIT (0u)
#define CSDIS_CLKSR4OFF_BIT (4u)
#define CSDIS_CLKSR5OFF_BIT (5u)

/* CDDIS bit positions */
#define CDDIS_GCLKOFF_BIT   (0u)
#define CDDIS_HCLKOFF_BIT   (1u)
#define CDDIS_VCLKPOFF_BIT  (2u)

/* CLKCNTL field positions */
#define CLKCNTL_VCLKR_LSB   (16u)
#define CLKCNTL_VCLKR_MSB   (19u)
#define CLKCNTL_VCLK2R_LSB  (24u)
#define CLKCNTL_VCLK2R_MSB  (27u)

/* Fixed source frequencies */
#define OSCIN_FREQ_HZ       (16000000u)
#define HF_LPO_FREQ_HZ      (9600000u)
#define LF_LPO_FREQ_HZ      (85000u)

/* Default dividers */
#define VCLK_DEFAULT_DIVIDER  (2u)
#define VCLK2_DEFAULT_DIVIDER (2u)

/* Divider tracking (application-modifiable) */
static uint32_t vclk_divider = VCLK_DEFAULT_DIVIDER;
static uint32_t vclk2_divider = VCLK2_DEFAULT_DIVIDER;

int clock_enable(clock_ref_t ref)
{
    uint32_t csdisclr_val;
    uint32_t cddisclr_val;

    csdisclr_val = 0u;
    cddisclr_val = 0u;

    switch (ref) {
        case CLOCKREF_OSCIN:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            csdisclr_val = (1u << CSDIS_CLKSR0OFF_BIT);
            REG32(SYSTEM_CSDISCLR) = csdisclr_val;
            break;

        case CLOCKREF_HF_LPO:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            csdisclr_val = (1u << CSDIS_CLKSR5OFF_BIT);
            REG32(SYSTEM_CSDISCLR) = csdisclr_val;
            break;

        case CLOCKREF_LF_LPO:
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            csdisclr_val = (1u << CSDIS_CLKSR4OFF_BIT);
            REG32(SYSTEM_CSDISCLR) = csdisclr_val;
            break;

        case CLOCKREF_GCLK:
            /* GCLK requires OSCIN source enabled and GCLK domain enabled */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            csdisclr_val = (1u << CSDIS_CLKSR0OFF_BIT);
            REG32(SYSTEM_CSDISCLR) = csdisclr_val;
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            cddisclr_val = (1u << CDDIS_GCLKOFF_BIT);
            REG32(SYSTEM_CDDISCLR) = cddisclr_val;
            break;

        case CLOCKREF_HCLK:
            /* HCLK requires OSCIN source enabled and HCLK domain enabled */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            csdisclr_val = (1u << CSDIS_CLKSR0OFF_BIT);
            REG32(SYSTEM_CSDISCLR) = csdisclr_val;
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            cddisclr_val = (1u << CDDIS_HCLKOFF_BIT);
            REG32(SYSTEM_CDDISCLR) = cddisclr_val;
            break;

        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* VCLK requires OSCIN + HCLK + VCLK domain enabled */
            /* [prov] regs.yaml:SYSTEM.CSDISCLR */
            csdisclr_val = (1u << CSDIS_CLKSR0OFF_BIT);
            REG32(SYSTEM_CSDISCLR) = csdisclr_val;
            /* [prov] regs.yaml:SYSTEM.CDDISCLR */
            cddisclr_val = (1u << CDDIS_HCLKOFF_BIT) | (1u << CDDIS_VCLKPOFF_BIT);
            REG32(SYSTEM_CDDISCLR) = cddisclr_val;
            break;

        default:
            return -1;
    }

    return 0;
}

uint32_t clock_get_hz(clock_ref_t ref)
{
    uint32_t freq;
    uint32_t hclk_freq;

    freq = 0u;

    switch (ref) {
        case CLOCKREF_OSCIN:
            freq = OSCIN_FREQ_HZ;
            break;

        case CLOCKREF_HF_LPO:
            freq = HF_LPO_FREQ_HZ;
            break;

        case CLOCKREF_LF_LPO:
            freq = LF_LPO_FREQ_HZ;
            break;

        case CLOCKREF_GCLK:
            /* GCLK defaults to OSCIN, divider = 1 */
            freq = OSCIN_FREQ_HZ;
            break;

        case CLOCKREF_HCLK:
            /* HCLK defaults to OSCIN, divider = 1 */
            freq = OSCIN_FREQ_HZ;
            break;

        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* VCLK is derived from HCLK with configurable divider */
            hclk_freq = OSCIN_FREQ_HZ;
            if (vclk_divider > 0u) {
                freq = hclk_freq / vclk_divider;
            }
            break;

        default:
            freq = 0u;
            break;
    }

    return freq;
}

int clock_set_divider(clock_ref_t ref, uint32_t divider)
{
    uint32_t clkcntl;
    uint32_t encoded;
    uint32_t mask;

    if ((divider < 1u) || (divider > 16u)) {
        return -1;
    }

    /* Encode divider: 0 = /1, 1 = /2, ... 15 = /16 */
    encoded = divider - 1u;

    switch (ref) {
        case CLOCKREF_VCLK:
        case CLOCKREF_SYSCLK:
            /* [prov] regs.yaml:SYSTEM.CLKCNTL */
            clkcntl = REG32(SYSTEM_CLKCNTL);
            mask = 0xFu << CLKCNTL_VCLKR_LSB;
            clkcntl = (clkcntl & ~mask) | (encoded << CLKCNTL_VCLKR_LSB);
            REG32(SYSTEM_CLKCNTL) = clkcntl;
            vclk_divider = divider;
            break;

        default:
            return -1;
    }

    return 0;
}