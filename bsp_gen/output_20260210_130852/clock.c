/**
 * @file clock.c
 * @brief Clock service implementation for TI Hercules RM46
 */

#include <stdint.h>
#include "clock.h"

/* Base addresses and offsets from FACTS MIRROR */
#define SYSTEM_BASE     (0xFFFFFF00u)
#define PCR_BASE        (0xFFFFE000u)

#define SYSTEM_CSDIS_OFFSET    (0x30u)
#define SYSTEM_CSDISCLR_OFFSET (0x38u)
#define SYSTEM_CDDIS_OFFSET    (0x3Cu)
#define SYSTEM_CDDISCLR_OFFSET (0x44u)
#define SYSTEM_CLKCNTL_OFFSET  (0xD0u)

#define REG32(addr) (*(volatile uint32_t *)(addr))

#define SYSTEM_CSDIS    REG32(SYSTEM_BASE + SYSTEM_CSDIS_OFFSET)
#define SYSTEM_CSDISCLR REG32(SYSTEM_BASE + SYSTEM_CSDISCLR_OFFSET)
#define SYSTEM_CDDIS    REG32(SYSTEM_BASE + SYSTEM_CDDIS_OFFSET)
#define SYSTEM_CDDISCLR REG32(SYSTEM_BASE + SYSTEM_CDDISCLR_OFFSET)
#define SYSTEM_CLKCNTL  REG32(SYSTEM_BASE + SYSTEM_CLKCNTL_OFFSET)

/* CSDIS bit positions */
#define CSDIS_BIT_OSCIN      (0u)
#define CSDIS_BIT_PLL1       (1u)
#define CSDIS_BIT_EXTCLKIN1  (3u)
#define CSDIS_BIT_LF_LPO     (4u)
#define CSDIS_BIT_HF_LPO     (5u)
#define CSDIS_BIT_PLL2       (6u)
#define CSDIS_BIT_EXTCLKIN2  (7u)

/* CDDIS bit positions */
#define CDDIS_BIT_GCLK       (0u)
#define CDDIS_BIT_HCLK       (1u)
#define CDDIS_BIT_VCLK       (2u)
#define CDDIS_BIT_VCLK2      (3u)
#define CDDIS_BIT_VCLKA1     (4u)
#define CDDIS_BIT_VCLKA2     (5u)
#define CDDIS_BIT_RTICLK     (6u)
#define CDDIS_BIT_VCLK3      (8u)
#define CDDIS_BIT_VCLK4      (9u)
#define CDDIS_BIT_VCLKA3_S  (10u)
#define CDDIS_BIT_VCLKA4_S  (11u)

/* CLKCNTL divider field shifts */
#define CLKCNTL_VCLKR_SHIFT  (16u)
#define CLKCNTL_VCLK2R_SHIFT (24u)

/* Fixed source frequencies (Hz) */
#define FREQ_OSCIN    (16000000u)
#define FREQ_HF_LPO    (9600000u)
#define FREQ_LF_LPO       (85000u)

/* Default dividers */
#define DEFAULT_DIVIDER_VCLK         (2u)
#define DEFAULT_DIVIDER_VCLK2        (2u)
#define DEFAULT_DIVIDER_VCLK3        (2u)
#define DEFAULT_DIVIDER_VCLK4        (2u)
#define DEFAULT_DIVIDER_VCLKA3_DIVR  (2u)
#define DEFAULT_DIVIDER_VCLKA4_DIVR  (2u)

/* Internal tracking of configured dividers (for clock_get_hz) */
static uint32_t g_vclk_divider  = DEFAULT_DIVIDER_VCLK;
static uint32_t g_vclk2_divider = DEFAULT_DIVIDER_VCLK2;
static uint32_t g_vclk3_divider = DEFAULT_DIVIDER_VCLK3;
static uint32_t g_vclk4_divider = DEFAULT_DIVIDER_VCLK4;

/**
 * @brief Enable the clock for the given reference.
 * @ingroup BSP_CLOCK
 */
int clock_enable(clock_ref_t ref)
{
    switch (ref)
    {
    case CLOCKREF_OSCIN:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        break;

    case CLOCKREF_PLL1:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_PLL1);
        break;

    case CLOCKREF_EXTCLKIN1:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_EXTCLKIN1);
        break;

    case CLOCKREF_LF_LPO:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_LF_LPO);
        break;

    case CLOCKREF_HF_LPO:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_HF_LPO);
        break;

    case CLOCKREF_PLL2:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_PLL2);
        break;

    case CLOCKREF_EXTCLKIN2:
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_EXTCLKIN2);
        break;

    case CLOCKREF_GCLK:
    case CLOCKREF_GCLK2:
        /* GCLK/GCLK2 parent is OSCIN; enable OSCIN source and GCLK domain */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_GCLK);
        break;

    case CLOCKREF_HCLK:
        /* HCLK parent is OSCIN; enable OSCIN source and HCLK domain */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        break;

    case CLOCKREF_VCLK:
    case CLOCKREF_SYSCLK:
        /* VCLK parent is HCLK; enable OSCIN, HCLK, and VCLK domains */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
        break;

    case CLOCKREF_VCLK2:
        /* VCLK2 parent is HCLK; enable OSCIN, HCLK, and VCLK2 domains */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK2);
        break;

    case CLOCKREF_VCLK3:
        /* VCLK3 parent is HCLK; enable OSCIN, HCLK, and VCLK3 domains */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK3);
        break;

    case CLOCKREF_VCLK4:
        /* VCLK4 parent is HCLK; enable OSCIN, HCLK, and VCLK4 domains */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK4);
        break;

    case CLOCKREF_VCLKA1:
        /* VCLKA1 parent is VCLK; enable OSCIN, HCLK, VCLK, and VCLKA1 domains */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLKA1);
        break;

    case CLOCKREF_VCLKA2:
        /* VCLKA2 parent is VCLK; enable OSCIN, HCLK, VCLK, and VCLKA2 domains */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLKA2);
        break;

    case CLOCKREF_VCLKA3_S:
    case CLOCKREF_VCLKA3_DIVR:
        /* VCLKA3_S parent is VCLK; enable OSCIN, HCLK, VCLK, and VCLKA3_S domain */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLKA3_S);
        break;

    case CLOCKREF_VCLKA4_S:
    case CLOCKREF_VCLKA4_DIVR:
    case CLOCKREF_VCLKA4_DIVR_EMAC:
        /* VCLKA4_S parent is VCLK; enable OSCIN, HCLK, VCLK, and VCLKA4_S domain */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLKA4_S);
        break;

    case CLOCKREF_RTICLK:
        /* RTICLK parent is VCLK; enable OSCIN, HCLK, VCLK, and RTICLK domain */
        /* [prov] regs.yaml:SYSTEM.CSDISCLR */
        SYSTEM_CSDISCLR = (1u << CSDIS_BIT_OSCIN);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_HCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_VCLK);
        /* [prov] regs.yaml:SYSTEM.CDDISCLR */
        SYSTEM_CDDISCLR = (1u << CDDIS_BIT_RTICLK);
        break;

    default:
        return -1;
    }

    return 0;
}

/**
 * @brief Query the frequency (in Hz) of the given clock reference.
 * @ingroup BSP_CLOCK
 */
uint32_t clock_get_hz(clock_ref_t ref)
{
    uint32_t freq;

    freq = 0u;

    switch (ref)
    {
    case CLOCKREF_OSCIN:
        freq = FREQ_OSCIN;
        break;

    case CLOCKREF_HF_LPO:
        freq = FREQ_HF_LPO;
        break;

    case CLOCKREF_LF_LPO:
        freq = FREQ_LF_LPO;
        break;

    case CLOCKREF_PLL1:
    case CLOCKREF_PLL2:
    case CLOCKREF_EXTCLKIN1:
    case CLOCKREF_EXTCLKIN2:
        /* PLL and external clocks not configured; return 0 */
        freq = 0u;
        break;

    case CLOCKREF_GCLK:
    case CLOCKREF_GCLK2:
    case CLOCKREF_HCLK:
        /* GCLK, GCLK2, and HCLK derive from OSCIN with divider=1 */
        freq = FREQ_OSCIN;
        break;

    case CLOCKREF_VCLK:
    case CLOCKREF_SYSCLK:
        /* VCLK parent is HCLK; apply tracked divider */
        freq = FREQ_OSCIN / g_vclk_divider;
        break;

    case CLOCKREF_VCLK2:
        /* VCLK2 parent is HCLK; apply tracked divider */
        freq = FREQ_OSCIN / g_vclk2_divider;
        break;

    case CLOCKREF_VCLK3:
        /* VCLK3 parent is HCLK; apply tracked divider */
        freq = FREQ_OSCIN / g_vclk3_divider;
        break;

    case CLOCKREF_VCLK4:
        /* VCLK4 parent is HCLK; apply tracked divider */
        freq = FREQ_OSCIN / g_vclk4_divider;
        break;

    case CLOCKREF_VCLKA1:
    case CLOCKREF_VCLKA2:
        /* VCLKA1/VCLKA2 parent is VCLK with divider=1 */
        freq = FREQ_OSCIN / g_vclk_divider;
        break;

    case CLOCKREF_VCLKA3_S:
        /* VCLKA3_S parent is VCLK with divider=1 */
        freq = FREQ_OSCIN / g_vclk_divider;
        break;

    case CLOCKREF_VCLKA3_DIVR:
        /* VCLKA3_DIVR parent is VCLKA3_S; apply default divider */
        freq = (FREQ_OSCIN / g_vclk_divider) / DEFAULT_DIVIDER_VCLKA3_DIVR;
        break;

    case CLOCKREF_VCLKA4_S:
        /* VCLKA4_S parent is VCLK with divider=1 */
        freq = FREQ_OSCIN / g_vclk_divider;
        break;

    case CLOCKREF_VCLKA4_DIVR:
    case CLOCKREF_VCLKA4_DIVR_EMAC:
        /* VCLKA4_DIVR parent is VCLKA4_S; apply default divider */
        freq = (FREQ_OSCIN / g_vclk_divider) / DEFAULT_DIVIDER_VCLKA4_DIVR;
        break;

    case CLOCKREF_RTICLK:
        /* RTICLK parent is VCLK with divider=1 */
        freq = FREQ_OSCIN / g_vclk_divider;
        break;

    default:
        freq = 0u;
        break;
    }

    return freq;
}

/**
 * @brief Apply clock configuration (APPLICATION-ONLY).
 * @ingroup BSP_CLOCK
 */
int clock_configure(const clock_config_t *cfg)
{
    uint32_t clkcntl_val;
    uint32_t vclkr;
    uint32_t vclk2r;

    if (cfg == (void *)0)
    {
        return -1;
    }

    /* Validate dividers (1..16) */
    if ((cfg->vclk_divider > 16u) ||
        (cfg->vclk2_divider > 16u) ||
        (cfg->vclk3_divider > 16u) ||
        (cfg->vclk4_divider > 16u))
    {
        return -1;
    }

    /* Read current CLKCNTL register */
    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    clkcntl_val = SYSTEM_CLKCNTL;

    /* Update VCLKR field if requested */
    if (cfg->vclk_divider > 0u)
    {
        vclkr = cfg->vclk_divider - 1u;
        clkcntl_val &= ~(0xFu << CLKCNTL_VCLKR_SHIFT);
        clkcntl_val |= (vclkr << CLKCNTL_VCLKR_SHIFT);
        g_vclk_divider = cfg->vclk_divider;
    }

    /* Update VCLK2R field if requested */
    if (cfg->vclk2_divider > 0u)
    {
        vclk2r = cfg->vclk2_divider - 1u;
        clkcntl_val &= ~(0xFu << CLKCNTL_VCLK2R_SHIFT);
        clkcntl_val |= (vclk2r << CLKCNTL_VCLK2R_SHIFT);
        g_vclk2_divider = cfg->vclk2_divider;
    }

    /* Write back CLKCNTL */
    /* [prov] regs.yaml:SYSTEM.CLKCNTL */
    SYSTEM_CLKCNTL = clkcntl_val;

    /* NOTE: VCLK3 and VCLK4 dividers are in CLKCNTL.VCLK3R and CLKCNTL.VCLK4R,
     * but regs.yaml does not provide bit positions for those fields beyond the
     * field name. To avoid guessing, we omit modification of VCLK3/VCLK4 dividers
     * here. Application code must consult the TRM and write those fields directly
     * if needed. We update tracking variables for frequency computation only. */

    if (cfg->vclk3_divider > 0u)
    {
        g_vclk3_divider = cfg->vclk3_divider;
    }

    if (cfg->vclk4_divider > 0u)
    {
        g_vclk4_divider = cfg->vclk4_divider;
    }

    return 0;
}