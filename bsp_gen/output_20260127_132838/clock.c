/**
 * @file clock.c
 * @brief Clock Service Implementation for TI Hercules RM46
 */

#include <stdint.h>
#include "clock.h"

/* ========================================================================== */
/* Register access macros                                                      */
/* ========================================================================== */

#define REG32(addr) (*(volatile uint32_t *)(addr))

#define SYSTEM_BASE   (0xFFFFFF00u)
#define PCR_BASE      (0xFFFFE000u)

#define SYSTEM_CSDIS_OFFSET    (0x30u)
#define SYSTEM_CSDISCLR_OFFSET (0x38u)
#define SYSTEM_CDDIS_OFFSET    (0x3Cu)
#define SYSTEM_CDDISCLR_OFFSET (0x44u)
#define SYSTEM_CLKCNTL_OFFSET  (0xD0u)

#define SYSTEM_CSDIS    REG32(SYSTEM_BASE + SYSTEM_CSDIS_OFFSET)
#define SYSTEM_CSDISCLR REG32(SYSTEM_BASE + SYSTEM_CSDISCLR_OFFSET)
#define SYSTEM_CDDIS    REG32(SYSTEM_BASE + SYSTEM_CDDIS_OFFSET)
#define SYSTEM_CDDISCLR REG32(SYSTEM_BASE + SYSTEM_CDDISCLR_OFFSET)
#define SYSTEM_CLKCNTL  REG32(SYSTEM_BASE + SYSTEM_CLKCNTL_OFFSET)

/* ========================================================================== */
/* Clock source / domain bit positions                                         */
/* ========================================================================== */

#define CSDIS_BIT_OSCIN      (0u)
#define CSDIS_BIT_PLL1       (1u)
#define CSDIS_BIT_EXTCLKIN1  (3u)
#define CSDIS_BIT_LF_LPO     (4u)
#define CSDIS_BIT_HF_LPO     (5u)
#define CSDIS_BIT_PLL2       (6u)
#define CSDIS_BIT_EXTCLKIN2  (7u)

#define CDDIS_BIT_GCLK    (0u)
#define CDDIS_BIT_HCLK    (1u)
#define CDDIS_BIT_VCLK    (2u)
#define CDDIS_BIT_VCLK2   (3u)
#define CDDIS_BIT_VCLKA1  (4u)
#define CDDIS_BIT_VCLKA2  (5u)
#define CDDIS_BIT_RTICLK  (6u)
#define CDDIS_BIT_VCLK3   (8u)
#define CDDIS_BIT_VCLK4   (9u)
#define CDDIS_BIT_VCLKA3  (10u)
#define CDDIS_BIT_VCLKA4  (11u)

/* ========================================================================== */
/* Fixed frequencies and default dividers                                      */
/* ========================================================================== */

#define FREQ_OSCIN      (16000000u)
#define FREQ_HF_LPO     (9600000u)
#define FREQ_LF_LPO     (85000u)
#define FREQ_PLL1       (1u)
#define FREQ_PLL2       (1u)
#define FREQ_EXTCLKIN1  (1u)
#define FREQ_EXTCLKIN2  (1u)

#define DEFAULT_DIVIDER_VCLK  (2u)
#define DEFAULT_DIVIDER_VCLK2 (2u)
#define DEFAULT_DIVIDER_VCLK3 (2u)
#define DEFAULT_DIVIDER_VCLK4 (2u)

#define CLKCNTL_VCLKR_SHIFT  (16u)
#define CLKCNTL_VCLK2R_SHIFT (24u)

/* ========================================================================== */
/* clock_enable implementation                                                 */
/* ========================================================================== */

/**
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

    case CLOCKREF_PLL1:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN) | (1u << CSDIS_BIT_PLL1);
        break;

    case CLOCKREF_PLL2:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN) | (1u << CSDIS_BIT_PLL2);
        break;

    case CLOCKREF_EXTCLKIN1:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_EXTCLKIN1);
        break;

    case CLOCKREF_EXTCLKIN2:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_EXTCLKIN2);
        break;

    case CLOCKREF_GCLK:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_GCLK);
        break;

    case CLOCKREF_HCLK:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        break;

    case CLOCKREF_VCLK:
    case CLOCKREF_SYSCLK:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK);
        break;

    case CLOCKREF_VCLK2:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK2);
        break;

    case CLOCKREF_VCLK3:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK3);
        break;

    case CLOCKREF_VCLK4:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK4);
        break;

    case CLOCKREF_VCLKA1:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_VCLKA1);
        break;

    case CLOCKREF_VCLKA2:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_VCLKA2);
        break;

    case CLOCKREF_VCLKA3_S:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_VCLKA3);
        break;

    case CLOCKREF_VCLKA3_DIVR:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_VCLKA3);
        break;

    case CLOCKREF_VCLKA4_S:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_VCLKA4);
        break;

    case CLOCKREF_VCLKA4_DIVR:
    case CLOCKREF_VCLKA4_DIVR_EMAC:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_VCLKA4);
        break;

    case CLOCKREF_RTICLK:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR, SYSTEM.CDDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK) | (1u << CDDIS_BIT_VCLK) | (1u << CDDIS_BIT_RTICLK);
        break;

    default:
        return -1;
    }

    return 0;
}

/* ========================================================================== */
/* clock_get_hz implementation                                                 */
/* ========================================================================== */

/**
 * @ingroup BSP_CLOCK
 */
uint32_t clock_get_hz(clock_ref_t ref)
{
    uint32_t parent_hz;
    uint32_t divider;
    uint32_t clkcntl;

    switch (ref) {
    case CLOCKREF_OSCIN:
        return FREQ_OSCIN;

    case CLOCKREF_HF_LPO:
        return FREQ_HF_LPO;

    case CLOCKREF_LF_LPO:
        return FREQ_LF_LPO;

    case CLOCKREF_PLL1:
        return FREQ_PLL1;

    case CLOCKREF_PLL2:
        return FREQ_PLL2;

    case CLOCKREF_EXTCLKIN1:
        return FREQ_EXTCLKIN1;

    case CLOCKREF_EXTCLKIN2:
        return FREQ_EXTCLKIN2;

    case CLOCKREF_GCLK:
        return FREQ_OSCIN;

    case CLOCKREF_HCLK:
        return FREQ_OSCIN;

    case CLOCKREF_VCLK:
    case CLOCKREF_SYSCLK:
        parent_hz = FREQ_OSCIN;
        /* [prov] regs.yaml:SYSTEM.CLKCNTL */
        clkcntl = SYSTEM_CLKCNTL;
        divider = ((clkcntl >> CLKCNTL_VCLKR_SHIFT) & 0xFu) + 1u;
        if (divider == 0u) {
            divider = DEFAULT_DIVIDER_VCLK;
        }
        return parent_hz / divider;

    case CLOCKREF_VCLK2:
        parent_hz = FREQ_OSCIN;
        /* [prov] regs.yaml:SYSTEM.CLKCNTL */
        clkcntl = SYSTEM_CLKCNTL;
        divider = ((clkcntl >> CLKCNTL_VCLK2R_SHIFT) & 0xFu) + 1u;
        if (divider == 0u) {
            divider = DEFAULT_DIVIDER_VCLK2;
        }
        return parent_hz / divider;

    case CLOCKREF_VCLK3:
        parent_hz = FREQ_OSCIN;
        return parent_hz / DEFAULT_DIVIDER_VCLK3;

    case CLOCKREF_VCLK4:
        parent_hz = FREQ_OSCIN;
        return parent_hz / DEFAULT_DIVIDER_VCLK4;

    case CLOCKREF_VCLKA1:
    case CLOCKREF_VCLKA2:
    case CLOCKREF_RTICLK:
        parent_hz = FREQ_OSCIN;
        /* [prov] regs.yaml:SYSTEM.CLKCNTL */
        clkcntl = SYSTEM_CLKCNTL;
        divider = ((clkcntl >> CLKCNTL_VCLKR_SHIFT) & 0xFu) + 1u;
        if (divider == 0u) {
            divider = DEFAULT_DIVIDER_VCLK;
        }
        return parent_hz / divider;

    case CLOCKREF_VCLKA3_S:
    case CLOCKREF_VCLKA4_S:
        parent_hz = FREQ_OSCIN;
        /* [prov] regs.yaml:SYSTEM.CLKCNTL */
        clkcntl = SYSTEM_CLKCNTL;
        divider = ((clkcntl >> CLKCNTL_VCLKR_SHIFT) & 0xFu) + 1u;
        if (divider == 0u) {
            divider = DEFAULT_DIVIDER_VCLK;
        }
        return parent_hz / divider;

    case CLOCKREF_VCLKA3_DIVR:
    case CLOCKREF_VCLKA4_DIVR:
    case CLOCKREF_VCLKA4_DIVR_EMAC:
        return 0u;

    default:
        return 0u;
    }
}

/* ========================================================================== */
/* Application-only configuration API                                          */
/* ========================================================================== */

/**
 * @ingroup BSP_CLOCK
 */
int clock_set_divider(clock_ref_t ref, uint32_t divider)
{
    uint32_t clkcntl;
    uint32_t field_val;

    if (divider == 0u || divider > 16u) {
        return -1;
    }

    field_val = (divider - 1u) & 0xFu;

    switch (ref) {
    case CLOCKREF_VCLK:
    case CLOCKREF_SYSCLK:
        /* [prov] regs.yaml:SYSTEM.CLKCNTL */
        clkcntl = SYSTEM_CLKCNTL;
        clkcntl &= ~(0xFu << CLKCNTL_VCLKR_SHIFT);
        clkcntl |= (field_val << CLKCNTL_VCLKR_SHIFT);
        SYSTEM_CLKCNTL = clkcntl;
        break;

    case CLOCKREF_VCLK2:
        /* [prov] regs.yaml:SYSTEM.CLKCNTL */
        clkcntl = SYSTEM_CLKCNTL;
        clkcntl &= ~(0xFu << CLKCNTL_VCLK2R_SHIFT);
        clkcntl |= (field_val << CLKCNTL_VCLK2R_SHIFT);
        SYSTEM_CLKCNTL = clkcntl;
        break;

    default:
        return -1;
    }

    return 0;
}