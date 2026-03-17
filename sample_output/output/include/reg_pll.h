/* BSP-GEN-META: created_at=2026-03-04T23:24:29-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_pll.h
 * @brief PLL Peripheral Register Map Header File
 * 
 * This file contains the register map structure and bit definitions
 * for the PLL peripheral.
 * 
 * @note Auto-generated register definitions
 * @warning Do not modify this file directly
 */

#ifndef REG_PLL_H
#define REG_PLL_H

#include <stdint.h>

/******************************************************************************/
/*                         PLL Register Map Structure                         */
/******************************************************************************/

/**
 * @brief PLL Register Map (Base Address: 0xFFFFFF00)
 * 
 * This structure defines the memory-mapped registers for the PLL peripheral
 * at base address 0xFFFFFF00.
 */
typedef struct {
    volatile uint32_t RESERVED0[12];     /**< Reserved (0x00 - 0x2C) */
    volatile uint32_t CSDIS;             /**< Clock Source Disable Register (0x30) */
    volatile uint32_t CSDISSET;          /**< Clock Source Disable Set Register (0x34) */
    volatile uint32_t CSDISCLR;          /**< Clock Source Disable Clear Register (0x38) */
    volatile uint32_t RESERVED1[6];      /**< Reserved (0x3C - 0x50) */
    volatile uint32_t CSVSTAT;           /**< Clock Source Valid Status Register (0x54) */
    volatile uint32_t RESERVED2[6];      /**< Reserved (0x58 - 0x6C) */
    volatile uint32_t PLLCTL1;           /**< PLL Control 1 Register (0x70) */
    volatile uint32_t PLLCTL2;           /**< PLL Control 2 Register (0x74) */
    volatile uint32_t RESERVED3[4];      /**< Reserved (0x78 - 0x84) */
    volatile uint32_t LPOMONCTL;         /**< LPO/Clock Monitor Control Register (0x88) */
    volatile uint32_t CLKTEST;           /**< Clock Test Register (0x8C) */
    volatile uint32_t RESERVED4[23];     /**< Reserved (0x90 - 0xE8) */
    volatile uint32_t GLBSTAT;           /**< Global Status Register (0xEC) */
    volatile uint32_t RESERVED5[4];      /**< Reserved (0xF0 - 0xFC) */
    volatile uint32_t GPREG1;            /**< General Purpose Register (0x100) */
} PLL_REG_MAP_t;

/**
 * @brief PLL2 Register Map (Base Address: 0xFFFFE100)
 * 
 * This structure defines the memory-mapped registers for the PLL peripheral
 * at base address 0xFFFFE100.
 */
typedef struct {
    volatile uint32_t PLLCTL3;           /**< PLL Control 3 Register (0x00) */
    volatile uint32_t RESERVED0[27];     /**< Reserved (0x04 - 0x6C) */
    volatile uint32_t CLKSLIP;           /**< PLL Clock Slip Control Register (0x70) */
} PLL2_REG_MAP_t;

/******************************************************************************/
/*                    CSDIS - Clock Source Disable Register                   */
/******************************************************************************/

#define PLL_CSDIS_OSC_DISABLE_SHIFT         (0U)
#define PLL_CSDIS_OSC_DISABLE_MASK          (0x00000001UL << PLL_CSDIS_OSC_DISABLE_SHIFT)
#define PLL_CSDIS_OSC_DISABLE               PLL_CSDIS_OSC_DISABLE_MASK

#define PLL_CSDIS_PLL1_DISABLE_SHIFT        (1U)
#define PLL_CSDIS_PLL1_DISABLE_MASK         (0x00000001UL << PLL_CSDIS_PLL1_DISABLE_SHIFT)
#define PLL_CSDIS_PLL1_DISABLE              PLL_CSDIS_PLL1_DISABLE_MASK

#define PLL_CSDIS_LF_LPO_DISABLE_SHIFT      (4U)
#define PLL_CSDIS_LF_LPO_DISABLE_MASK       (0x00000001UL << PLL_CSDIS_LF_LPO_DISABLE_SHIFT)
#define PLL_CSDIS_LF_LPO_DISABLE            PLL_CSDIS_LF_LPO_DISABLE_MASK

#define PLL_CSDIS_HF_LPO_DISABLE_SHIFT      (5U)
#define PLL_CSDIS_HF_LPO_DISABLE_MASK       (0x00000001UL << PLL_CSDIS_HF_LPO_DISABLE_SHIFT)
#define PLL_CSDIS_HF_LPO_DISABLE            PLL_CSDIS_HF_LPO_DISABLE_MASK

#define PLL_CSDIS_PLL2_DISABLE_SHIFT        (6U)
#define PLL_CSDIS_PLL2_DISABLE_MASK         (0x00000001UL << PLL_CSDIS_PLL2_DISABLE_SHIFT)
#define PLL_CSDIS_PLL2_DISABLE              PLL_CSDIS_PLL2_DISABLE_MASK

/******************************************************************************/
/*                CSDISSET - Clock Source Disable Set Register                */
/******************************************************************************/

/* CSDISSET uses same bit definitions as CSDIS */

/******************************************************************************/
/*               CSDISCLR - Clock Source Disable Clear Register               */
/******************************************************************************/

#define PLL_CSDISCLR_OSC_ENABLE_SHIFT       (0U)
#define PLL_CSDISCLR_OSC_ENABLE_MASK        (0x00000001UL << PLL_CSDISCLR_OSC_ENABLE_SHIFT)
#define PLL_CSDISCLR_OSC_ENABLE             PLL_CSDISCLR_OSC_ENABLE_MASK

#define PLL_CSDISCLR_PLL1_ENABLE_SHIFT      (1U)
#define PLL_CSDISCLR_PLL1_ENABLE_MASK       (0x00000001UL << PLL_CSDISCLR_PLL1_ENABLE_SHIFT)
#define PLL_CSDISCLR_PLL1_ENABLE            PLL_CSDISCLR_PLL1_ENABLE_MASK

#define PLL_CSDISCLR_PLL2_ENABLE_SHIFT      (6U)
#define PLL_CSDISCLR_PLL2_ENABLE_MASK       (0x00000001UL << PLL_CSDISCLR_PLL2_ENABLE_SHIFT)
#define PLL_CSDISCLR_PLL2_ENABLE            PLL_CSDISCLR_PLL2_ENABLE_MASK

/******************************************************************************/
/*               CSVSTAT - Clock Source Valid Status Register                 */
/******************************************************************************/

#define PLL_CSVSTAT_CLKSR0V_SHIFT           (0U)
#define PLL_CSVSTAT_CLKSR0V_MASK            (0x00000001UL << PLL_CSVSTAT_CLKSR0V_SHIFT)
#define PLL_CSVSTAT_CLKSR0V                 PLL_CSVSTAT_CLKSR0V_MASK

#define PLL_CSVSTAT_CLKSRnV_SHIFT           (0U)
#define PLL_CSVSTAT_CLKSRnV_MASK            (0x00000001UL << PLL_CSVSTAT_CLKSRnV_SHIFT)
#define PLL_CSVSTAT_CLKSRnV                 PLL_CSVSTAT_CLKSRnV_MASK

/******************************************************************************/
/*                      PLLCTL1 - PLL Control 1 Register                      */
/******************************************************************************/

#define PLL_PLLCTL1_REFCLKDIV_SHIFT         (0U)
#define PLL_PLLCTL1_REFCLKDIV_MASK          (0x0000003FUL << PLL_PLLCTL1_REFCLKDIV_SHIFT)

#define PLL_PLLCTL1_PLLMUL_SHIFT            (0U)
#define PLL_PLLCTL1_PLLMUL_MASK             (0x0000FFFFUL << PLL_PLLCTL1_PLLMUL_SHIFT)

#define PLL_PLLCTL1_ROF_SHIFT               (23U)
#define PLL_PLLCTL1_ROF_MASK                (0x00000001UL << PLL_PLLCTL1_ROF_SHIFT)
#define PLL_PLLCTL1_ROF                     PLL_PLLCTL1_ROF_MASK

#define PLL_PLLCTL1_BPOS_SHIFT              (29U)
#define PLL_PLLCTL1_BPOS_MASK               (0x00000003UL << PLL_PLLCTL1_BPOS_SHIFT)

/******************************************************************************/
/*                      PLLCTL2 - PLL Control 2 Register                      */
/******************************************************************************/

#define PLL_PLLCTL2_PLLDIV_SHIFT            (0U)
#define PLL_PLLCTL2_PLLDIV_MASK             (0x0000001FUL << PLL_PLLCTL2_PLLDIV_SHIFT)

#define PLL_PLLCTL2_ODPLL_SHIFT             (0U)
#define PLL_PLLCTL2_ODPLL_MASK              (0x00000007UL << PLL_PLLCTL2_ODPLL_SHIFT)

#define PLL_PLLCTL2_SPR_AMOUNT_SHIFT        (0U)
#define PLL_PLLCTL2_SPR_AMOUNT_MASK         (0x000001FFUL << PLL_PLLCTL2_SPR_AMOUNT_SHIFT)

#define PLL_PLLCTL2_SPREADINGRATE_SHIFT     (0U)
#define PLL_PLLCTL2_SPREADINGRATE_MASK      (0x000001FFUL << PLL_PLLCTL2_SPREADINGRATE_SHIFT)

#define PLL_PLLCTL2_FMENA_SHIFT             (31U)
#define PLL_PLLCTL2_FMENA_MASK              (0x00000001UL << PLL_PLLCTL2_FMENA_SHIFT)
#define PLL_PLLCTL2_FMENA                   PLL_PLLCTL2_FMENA_MASK

#define PLL_PLLCTL2_MULMOD_SHIFT            (0U)
#define PLL_PLLCTL2_MULMOD_MASK             (0x000001FFUL << PLL_PLLCTL2_MULMOD_SHIFT)

/******************************************************************************/
/*                      PLLCTL3 - PLL Control 3 Register                      */
/******************************************************************************/

/* PLLCTL3 uses same bit definitions as PLLCTL1 */

/******************************************************************************/
/*             LPOMONCTL - LPO/Clock Monitor Control Register                 */
/******************************************************************************/

#define PLL_LPOMONCTL_TRIM_INITIAL_SHIFT    (0U)
#define PLL_LPOMONCTL_TRIM_INITIAL_MASK     (0x0000FFFFUL << PLL_LPOMONCTL_TRIM_INITIAL_SHIFT)

#define PLL_LPOMONCTL_HFTRIM_SHIFT          (0U)
#define PLL_LPOMONCTL_HFTRIM_MASK           (0x0000001FUL << PLL_LPOMONCTL_HFTRIM_SHIFT)

#define PLL_LPOMONCTL_LFTRIM_SHIFT          (0U)
#define PLL_LPOMONCTL_LFTRIM_MASK           (0x0000001FUL << PLL_LPOMONCTL_LFTRIM_SHIFT)

#define PLL_LPOMONCTL_BIASEN_SHIFT          (24U)
#define PLL_LPOMONCTL_BIASEN_MASK           (0x00000001UL << PLL_LPOMONCTL_BIASEN_SHIFT)
#define PLL_LPOMONCTL_BIASEN                PLL_LPOMONCTL_BIASEN_MASK

/******************************************************************************/
/*                      CLKTEST - Clock Test Register                         */
/******************************************************************************/

#define PLL_CLKTEST_RANGE_DET_CTRL_SHIFT    (25U)
#define PLL_CLKTEST_RANGE_DET_CTRL_MASK     (0x00000001UL << PLL_CLKTEST_RANGE_DET_CTRL_SHIFT)
#define PLL_CLKTEST_RANGE_DET_CTRL          PLL_CLKTEST_RANGE_DET_CTRL_MASK

#define PLL_CLKTEST_RANGE_DET_ENA_SSET_SHIFT (24U)
#define PLL_CLKTEST_RANGE_DET_ENA_SSET_MASK (0x00000001UL << PLL_CLKTEST_RANGE_DET_ENA_SSET_SHIFT)
#define PLL_CLKTEST_RANGE_DET_ENA_SSET      PLL_CLKTEST_RANGE_DET_ENA_SSET_MASK

/******************************************************************************/
/*                     GLBSTAT - Global Status Register                       */
/******************************************************************************/

#define PLL_GLBSTAT_OSCFAIL_SHIFT           (0U)
#define PLL_GLBSTAT_OSCFAIL_MASK            (0x00000001UL << PLL_GLBSTAT_OSCFAIL_SHIFT)
#define PLL_GLBSTAT_OSCFAIL                 PLL_GLBSTAT_OSCFAIL_MASK

#define PLL_GLBSTAT_RFSLIP_SHIFT            (0U)
#define PLL_GLBSTAT_RFSLIP_MASK             (0x00000001UL << PLL_GLBSTAT_RFSLIP_SHIFT)
#define PLL_GLBSTAT_RFSLIP                  PLL_GLBSTAT_RFSLIP_MASK

#define PLL_GLBSTAT_FBSLIP_SHIFT            (0U)
#define PLL_GLBSTAT_FBSLIP_MASK             (0x00000001UL << PLL_GLBSTAT_FBSLIP_SHIFT)
#define PLL_GLBSTAT_FBSLIP                  PLL_GLBSTAT_FBSLIP_MASK

/******************************************************************************/
/*                CLKSLIP - PLL Clock Slip Control Register                   */
/******************************************************************************/

/* No specific bit fields defined for CLKSLIP */

/******************************************************************************/
/*      SSWPLL1 - PLL Modulation Depth Measurement Control Register          */
/******************************************************************************/

#define PLL_SSWPLL1_CAPTURE_WINDOW_INDEX_SHIFT (8U)
#define PLL_SSWPLL1_CAPTURE_WINDOW_INDEX_MASK  (0x000000FFUL << PLL_SSWPLL1_CAPTURE_WINDOW_INDEX_SHIFT)

#define PLL_SSWPLL1_COUNTER_READ_READY_SHIFT (6U)
#define PLL_SSWPLL1_COUNTER_READ_READY_MASK (0x00000001UL << PLL_SSWPLL1_COUNTER_READ_READY_SHIFT)
#define PLL_SSWPLL1_COUNTER_READ_READY      PLL_SSWPLL1_COUNTER_READ_READY_MASK

#define PLL_SSWPLL1_COUNTER_RESET_SHIFT     (5U)
#define PLL_SSWPLL1_COUNTER_RESET_MASK      (0x00000001UL << PLL_SSWPLL1_COUNTER_RESET_SHIFT)
#define PLL_SSWPLL1_COUNTER_RESET           PLL_SSWPLL1_COUNTER_RESET_MASK

#define PLL_SSWPLL1_COUNTER_EN_SHIFT        (4U)
#define PLL_SSWPLL1_COUNTER_EN_MASK         (0x00000001UL << PLL_SSWPLL1_COUNTER_EN_SHIFT)
#define PLL_SSWPLL1_COUNTER_EN              PLL_SSWPLL1_COUNTER_EN_MASK

#define PLL_SSWPLL1_TAP_COUNTER_DIS_SHIFT   (1U)
#define PLL_SSWPLL1_TAP_COUNTER_DIS_MASK    (0x00000007UL << PLL_SSWPLL1_TAP_COUNTER_DIS_SHIFT)

#define PLL_SSWPLL1_EXT_COUNTER_EN_SHIFT    (0U)
#define PLL_SSWPLL1_EXT_COUNTER_EN_MASK     (0x00000001UL << PLL_SSWPLL1_EXT_COUNTER_EN_SHIFT)
#define PLL_SSWPLL1_EXT_COUNTER_EN          PLL_SSWPLL1_EXT_COUNTER_EN_MASK

/******************************************************************************/
/*            SSWPLL2 - SSW PLL BIST Control Register 2                       */
/******************************************************************************/

#define PLL_SSWPLL2_SSW_CAPTURE_COUNT_SHIFT (0U)
#define PLL_SSWPLL2_SSW_CAPTURE_COUNT_MASK  (0xFFFFFFFFUL << PLL_SSWPLL2_SSW_CAPTURE_COUNT_SHIFT)

/******************************************************************************/
/*            SSWPLL3 - SSW PLL BIST Control Register 3                       */
/******************************************************************************/

#define PLL_SSWPLL3_SSW_CLKOUT_COUNT_SHIFT  (0U)
#define PLL_SSWPLL3_SSW_CLKOUT_COUNT_MASK   (0xFFFFFFFFUL << PLL_SSWPLL3_SSW_CLKOUT_COUNT_SHIFT)

/******************************************************************************/
/*                    GPREG1 - General Purpose Register                       */
/******************************************************************************/

/* No specific bit fields defined for GPREG1 */

#endif /* REG_PLL_H */
