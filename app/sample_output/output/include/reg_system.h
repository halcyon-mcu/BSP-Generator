/* BSP-GEN-META: created_at=2026-03-04T23:25:39-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_system.h
 * @brief Register Map Header for SYSTEM Peripheral
 * 
 * This file contains the register map definitions for the SYSTEM peripheral.
 * - Base Address: 0xFFFFFF00 (SYSTEM)
 * - Base Address: 0xFFFFE100 (SYSTEM2)
 * 
 * @note Auto-generated from YAML register definition
 * @warning Do not modify this file directly
 */

#ifndef REG_SYSTEM_H
#define REG_SYSTEM_H

#include <stdint.h>

/* ========================================================================== */
/*                            SYSTEM Register Map                             */
/*                          Base Address: 0xFFFFFF00                          */
/* ========================================================================== */

/**
 * @brief SYSTEM Register Map Structure
 * 
 * Primary System Control Registers (SYS). Controls clocks, resets, and global
 * system configurations.
 */
typedef struct {
    volatile uint32_t SYSPC1;       /**< 0x00: SYS Pin Control Register 1. Controls ECLK pin function. */
    volatile uint32_t SYSPC2;       /**< 0x04: SYS Pin Control Register 2. Controls ECLK direction in GIO mode. */
    volatile uint32_t SYSPC3;       /**< 0x08: SYS Pin Control Register 3. ECLK input data. */
    volatile uint32_t SYSPC4;       /**< 0x0C: SYS Pin Control Register 4. ECLK output data. */
    volatile uint32_t SYSPC5;       /**< 0x10: SYS Pin Control Register 5. ECLK output set. */
    volatile uint32_t SYSPC6;       /**< 0x14: SYS Pin Control Register 6. ECLK output clear. */
    volatile uint32_t SYSPC7;       /**< 0x18: SYS Pin Control Register 7. ECLK open drain enable. */
    volatile uint32_t SYSPC8;       /**< 0x1C: SYS Pin Control Register 8. ECLK pull enable. */
    volatile uint32_t SYSPC9;       /**< 0x20: SYS Pin Control Register 9. ECLK pull select. */
    volatile uint32_t RESERVED0[3]; /**< 0x24-0x2C: Reserved */
    volatile uint32_t CSDIS;        /**< 0x30: Clock Source Disable Register. */
    volatile uint32_t CSDISSET;     /**< 0x34: Clock Source Disable Set Register. Writing 1 disables the clock source. */
    volatile uint32_t CSDISCLR;     /**< 0x38: Clock Source Disable Clear Register. Writing 1 enables the clock source. */
    volatile uint32_t CDDIS;        /**< 0x3C: Clock Domain Disable Register. */
    volatile uint32_t CDDISSET;     /**< 0x40: Clock Domain Disable Set Register. Writing 1 disables the clock domain. */
    volatile uint32_t CDDISCLR;     /**< 0x44: Clock Domain Disable Clear Register. Writing 1 enables the clock domain. */
    volatile uint32_t GHVSRC;       /**< 0x48: GCLK, HCLK, VCLK, and VCLK2 Source Register. */
    volatile uint32_t VCLKASRC;     /**< 0x4C: Peripheral Asynchronous Clock Source Register. */
    volatile uint32_t RCLKSRC;      /**< 0x50: RTI Clock Source Register. */
    volatile uint32_t CSVSTAT;      /**< 0x54: Clock Source Valid Status Register. */
    volatile uint32_t MSTGCR;       /**< 0x58: Memory Self-Test Global Control Register. */
    volatile uint32_t MINITGCR;     /**< 0x5C: Memory Hardware Initialization Global Control Register. */
    volatile uint32_t MSINENA;      /**< 0x60: Memory Self-Test/Initialization Enable Register. */
    volatile uint32_t MSTFAIL;      /**< 0x64: Memory Self-Test Fail Status Register. */
    volatile uint32_t MSTCGSTAT;    /**< 0x68: MSTC Global Status Register. */
    volatile uint32_t MINISTAT;     /**< 0x6C: Memory Hardware Initialization Status Register. */
    volatile uint32_t PLLCTL1;      /**< 0x70: PLL Control Register 1. */
    volatile uint32_t PLLCTL2;      /**< 0x74: PLL Control Register 2. */
    volatile uint32_t SYSPC10;      /**< 0x78: SYS Pin Control Register 10. */
    volatile uint32_t DIEIDL;       /**< 0x7C: Die Identification Register Lower Word. */
    volatile uint32_t DIEIDH;       /**< 0x80: Die Identification Register Upper Word. */
    volatile uint32_t RESERVED1;    /**< 0x84: Reserved */
    volatile uint32_t LPOMONCTL;    /**< 0x88: LPO/Clock Monitor Control Register. */
    volatile uint32_t CLKTEST;      /**< 0x8C: Clock Test Register. */
    volatile uint32_t DFTCTRLREG;   /**< 0x90: DFT Control Register. */
    volatile uint32_t DFTCTRLREG2;  /**< 0x94: DFT Control Register 2. */
    volatile uint32_t RESERVED2[2]; /**< 0x98-0x9C: Reserved */
    volatile uint32_t GPREG1;       /**< 0xA0: General Purpose Register 1. */
    volatile uint32_t RESERVED3;    /**< 0xA4: Reserved */
    volatile uint32_t IMPFASTS;     /**< 0xA8: Imprecise Fault Status Register. */
    volatile uint32_t IMPFTADD;     /**< 0xAC: Imprecise Fault Write Address Register. */
    volatile uint32_t SSIR1;        /**< 0xB0: System Software Interrupt Request 1. */
    volatile uint32_t SSIR2;        /**< 0xB4: System Software Interrupt Request 2. */
    volatile uint32_t SSIR3;        /**< 0xB8: System Software Interrupt Request 3. */
    volatile uint32_t SSIR4;        /**< 0xBC: System Software Interrupt Request 4. */
    volatile uint32_t RAMGCR;       /**< 0xC0: RAM Control Register. */
    volatile uint32_t BMMCR1;       /**< 0xC4: Bus Matrix Module Control Register 1. */
    volatile uint32_t RESERVED4;    /**< 0xC8: Reserved */
    volatile uint32_t CPURSTCR;     /**< 0xCC: CPU Reset Control Register. */
    volatile uint32_t CLKCNTL;      /**< 0xD0: Clock Control Register. */
    volatile uint32_t ECPCNTL;      /**< 0xD4: ECP Control Register. */
    volatile uint32_t RESERVED5;    /**< 0xD8: Reserved */
    volatile uint32_t DEVCR1;       /**< 0xDC: DEV Parity Control Register 1. */
    volatile uint32_t SYSECR;       /**< 0xE0: System Exception Control Register. */
    volatile uint32_t SYSESR;       /**< 0xE4: System Exception Status Register. Write 1 to clear flags. */
    volatile uint32_t SYSTASR;      /**< 0xE8: System Test Abort Status Register. */
    volatile uint32_t GLBSTAT;      /**< 0xEC: Global Status Register. Write 1 to clear flags. */
    volatile uint32_t DEVID;        /**< 0xF0: Device Identification Register. */
    volatile uint32_t SSIVEC;       /**< 0xF4: Software Interrupt Vector Register. */
    volatile uint32_t SSIF;         /**< 0xF8: System Software Interrupt Flag Register. Write 1 to clear. */
} SYSTEM_REG_MAP_t;

/* ========================================================================== */
/*                         SYSTEM Register Bit Masks                          */
/* ========================================================================== */

/* SYSPC1 - SYS Pin Control Register 1 */
#define SYSTEM_SYSPC1_ECPCLKFUN                 (1U << 0)

/* SYSPC2 - SYS Pin Control Register 2 */
#define SYSTEM_SYSPC2_ECPCLKDIR                 (1U << 0)

/* SYSPC3 - SYS Pin Control Register 3 */
#define SYSTEM_SYSPC3_ECPCLKDIN                 (1U << 0)

/* SYSPC4 - SYS Pin Control Register 4 */
#define SYSTEM_SYSPC4_ECPCLKDOUT                (1U << 0)

/* SYSPC5 - SYS Pin Control Register 5 */
#define SYSTEM_SYSPC5_ECPCLKSET                 (1U << 0)

/* SYSPC6 - SYS Pin Control Register 6 */
#define SYSTEM_SYSPC6_ECPCLKCLR                 (1U << 0)

/* SYSPC7 - SYS Pin Control Register 7 */
#define SYSTEM_SYSPC7_ECPCLKODE                 (1U << 0)

/* SYSPC8 - SYS Pin Control Register 8 */
#define SYSTEM_SYSPC8_ECPCLKPUE                 (1U << 0)

/* SYSPC9 - SYS Pin Control Register 9 */
#define SYSTEM_SYSPC9_ECPCLKPS                  (1U << 0)

/* CSDIS - Clock Source Disable Register */
#define SYSTEM_CSDIS_CLKSR7OFF                  (1U << 7)
#define SYSTEM_CSDIS_CLKSR6OFF                  (1U << 6)
#define SYSTEM_CSDIS_CLKSR5OFF                  (1U << 5)
#define SYSTEM_CSDIS_CLKSR4OFF                  (1U << 4)
#define SYSTEM_CSDIS_CLKSR3OFF                  (1U << 3)
#define SYSTEM_CSDIS_CLKSR1OFF                  (1U << 1)
#define SYSTEM_CSDIS_CLKSR0OFF                  (1U << 0)

/* CSDISSET - Clock Source Disable Set Register */
#define SYSTEM_CSDISSET_SETCLKSR7OFF            (1U << 7)
#define SYSTEM_CSDISSET_SETCLKSR6OFF            (1U << 6)
#define SYSTEM_CSDISSET_SETCLKSR5OFF            (1U << 5)
#define SYSTEM_CSDISSET_SETCLKSR4OFF            (1U << 4)
#define SYSTEM_CSDISSET_SETCLKSR3OFF            (1U << 3)
#define SYSTEM_CSDISSET_SETCLKSR1OFF            (1U << 1)
#define SYSTEM_CSDISSET_SETCLKSR0OFF            (1U << 0)

/* CSDISCLR - Clock Source Disable Clear Register */
#define SYSTEM_CSDISCLR_CLRCLKSR7OFF            (1U << 7)
#define SYSTEM_CSDISCLR_CLRCLKSR6OFF            (1U << 6)
#define SYSTEM_CSDISCLR_CLRCLKSR5OFF            (1U << 5)
#define SYSTEM_CSDISCLR_CLRCLKSR4OFF            (1U << 4)
#define SYSTEM_CSDISCLR_CLRCLKSR3OFF            (1U << 3)
#define SYSTEM_CSDISCLR_CLRCLKSR1OFF            (1U << 1)
#define SYSTEM_CSDISCLR_CLRCLKSR0OFF            (1U << 0)

/* CDDIS - Clock Domain Disable Register */
#define SYSTEM_CDDIS_VCLKA4OFF                  (1U << 11)
#define SYSTEM_CDDIS_VCLKA3OFF                  (1U << 10)
#define SYSTEM_CDDIS_VCLK4OFF                   (1U << 9)
#define SYSTEM_CDDIS_VCLK3OFF                   (1U << 8)
#define SYSTEM_CDDIS_RTICLK1OFF                 (1U << 6)
#define SYSTEM_CDDIS_VCLKA1OFF                  (1U << 4)
#define SYSTEM_CDDIS_VCLK2OFF                   (1U << 3)
#define SYSTEM_CDDIS_VCLKPOFF                   (1U << 2)
#define SYSTEM_CDDIS_HCLKOFF                    (1U << 1)
#define SYSTEM_CDDIS_GCLKOFF                    (1U << 0)

/* CDDISSET - Clock Domain Disable Set Register */
#define SYSTEM_CDDISSET_SETVCLKA4OFF            (1U << 11)
#define SYSTEM_CDDISSET_SETVCLKA3OFF            (1U << 10)
#define SYSTEM_CDDISSET_SETVCLK4OFF             (1U << 9)
#define SYSTEM_CDDISSET_SETVCLK3OFF             (1U << 8)
#define SYSTEM_CDDISSET_SETRTI1CLKOFF           (1U << 6)
#define SYSTEM_CDDISSET_SETVCLKA1OFF            (1U << 4)
#define SYSTEM_CDDISSET_SETVCLK2OFF             (1U << 3)
#define SYSTEM_CDDISSET_SETVCLKPOFF             (1U << 2)
#define SYSTEM_CDDISSET_SETHCLKOFF              (1U << 1)
#define SYSTEM_CDDISSET_SETGCLKOFF              (1U << 0)

/* CDDISCLR - Clock Domain Disable Clear Register */
#define SYSTEM_CDDISCLR_CLRVCLKA4OFF            (1U << 11)
#define SYSTEM_CDDISCLR_CLRVCLKA3OFF            (1U << 10)
#define SYSTEM_CDDISCLR_CLRVCLK4OFF             (1U << 9)
#define SYSTEM_CDDISCLR_CLRVCLK3OFF             (1U << 8)
#define SYSTEM_CDDISCLR_CLRRTI1CLKOFF           (1U << 6)
#define SYSTEM_CDDISCLR_CLRVCLKA1OFF            (1U << 4)
#define SYSTEM_CDDISCLR_CLRVCLK2OFF             (1U << 3)
#define SYSTEM_CDDISCLR_CLRVCLKPOFF             (1U << 2)
#define SYSTEM_CDDISCLR_CLRHCLKOFF              (1U << 1)
#define SYSTEM_CDDISCLR_CLRGCLKOFF              (1U << 0)

/* GHVSRC - GCLK, HCLK, VCLK, and VCLK2 Source Register */
#define SYSTEM_GHVSRC_GHVWAKE_MASK              (0x0FU << 24)
#define SYSTEM_GHVSRC_GHVWAKE_SHIFT             (24U)
#define SYSTEM_GHVSRC_HVLPM_MASK                (0x0FU << 16)
#define SYSTEM_GHVSRC_HVLPM_SHIFT               (16U)
#define SYSTEM_GHVSRC_GHVSRC_MASK               (0x0FU << 0)
#define SYSTEM_GHVSRC_GHVSRC_SHIFT              (0U)

/* VCLKASRC - Peripheral Asynchronous Clock Source Register */
#define SYSTEM_VCLKASRC_VCLKA1S_MASK            (0x0FU << 0)
#define SYSTEM_VCLKASRC_VCLKA1S_SHIFT           (0U)

/* RCLKSRC - RTI Clock Source Register */
#define SYSTEM_RCLKSRC_RTI1DIV_MASK             (0x03U << 8)
#define SYSTEM_RCLKSRC_RTI1DIV_SHIFT            (8U)
#define SYSTEM_RCLKSRC_RTI1SRC_MASK             (0x0FU << 0)
#define SYSTEM_RCLKSRC_RTI1SRC_SHIFT            (0U)

/* CSVSTAT - Clock Source Valid Status Register */
#define SYSTEM_CSVSTAT_CLKSR7V                  (1U << 7)
#define SYSTEM_CSVSTAT_CLKSR6V                  (1U << 6)
#define SYSTEM_CSVSTAT_CLKSR5V                  (1U << 5)
#define SYSTEM_CSVSTAT_CLKSR4V                  (1U << 4)
#define SYSTEM_CSVSTAT_CLKSR3V                  (1U << 3)
#define SYSTEM_CSVSTAT_CLKSR1V                  (1U << 1)
#define SYSTEM_CSVSTAT_CLKSR0V                  (1U << 0)

/* MSTGCR - Memory Self-Test Global Control Register */
#define SYSTEM_MSTGCR_MBIST_ALGSEL_MASK         (0xFFU << 16)
#define SYSTEM_MSTGCR_MBIST_ALGSEL_SHIFT        (16U)
#define SYSTEM_MSTGCR_ROM_DIV_MASK              (0x03U << 8)
#define SYSTEM_MSTGCR_ROM_DIV_SHIFT             (8U)
#define SYSTEM_MSTGCR_MSTGENA_MASK              (0x0FU << 0)
#define SYSTEM_MSTGCR_MSTGENA_SHIFT             (0U)

/* MINITGCR - Memory Hardware Initialization Global Control Register */
#define SYSTEM_MINITGCR_MINITGENA_MASK          (0x0FU << 0)
#define SYSTEM_MINITGCR_MINITGENA_SHIFT         (0U)

/* MSINENA - Memory Self-Test/Initialization Enable Register */
#define SYSTEM_MSINENA_MSIENA_MASK              (0xFFFFFFFFU << 0)
#define SYSTEM_MSINENA_MSIENA_SHIFT             (0U)

/* MSTFAIL - Memory Self-Test Fail Status Register */
#define SYSTEM_MSTFAIL_MSTF_MASK                (0xFFFFFFFFU << 0)
#define SYSTEM_MSTFAIL_MSTF_SHIFT               (0U)

/* MSTCGSTAT - MSTC Global Status Register */
#define SYSTEM_MSTCGSTAT_MINIDONE               (1U << 8)
#define SYSTEM_MSTCGSTAT_MSTDONE                (1U << 0)

/* MINISTAT - Memory Hardware Initialization Status Register */
#define SYSTEM_MINISTAT_MIDONE_MASK             (0xFFFFFFFFU << 0)
#define SYSTEM_MINISTAT_MIDONE_SHIFT            (0U)

/* PLLCTL1 - PLL Control Register 1 */
#define SYSTEM_PLLCTL1_ROS                      (1U << 31)
#define SYSTEM_PLLCTL1_MASK_SLIP_MASK           (0x03U << 29)
#define SYSTEM_PLLCTL1_MASK_SLIP_SHIFT          (29U)
#define SYSTEM_PLLCTL1_PLLDIV_MASK              (0x1FU << 24)
#define SYSTEM_PLLCTL1_PLLDIV_SHIFT             (24U)
#define SYSTEM_PLLCTL1_ROF                      (1U << 23)
#define SYSTEM_PLLCTL1_REFCLKDIV_MASK           (0x3FU << 16)
#define SYSTEM_PLLCTL1_REFCLKDIV_SHIFT          (16U)
#define SYSTEM_PLLCTL1_PLLMUL_MASK              (0xFFFFU << 0)
#define SYSTEM_PLLCTL1_PLLMUL_SHIFT             (0U)

/* PLLCTL2 - PLL Control Register 2 */
#define SYSTEM_PLLCTL2_FMENA                    (1U << 31)
#define SYSTEM_PLLCTL2_SPREADINGRATE_MASK       (0x1FFU << 22)
#define SYSTEM_PLLCTL2_SPREADINGRATE_SHIFT      (22U)
#define SYSTEM_PLLCTL2_MULMOD_MASK              (0x1FFU << 12)
#define SYSTEM_PLLCTL2_MULMOD_SHIFT             (12U)
#define SYSTEM_PLLCTL2_ODPLL_MASK               (0x07U << 9)
#define SYSTEM_PLLCTL2_ODPLL_SHIFT              (9U)
#define SYSTEM_PLLCTL2_SPR_AMOUNT_MASK          (0x1FFU << 0)
#define SYSTEM_PLLCTL2_SPR_AMOUNT_SHIFT         (0U)

/* SYSPC10 - SYS Pin Control Register 10 */
#define SYSTEM_SYSPC10_ECPCLK_SLEW              (1U << 0)

/* DIEIDL - Die Identification Register Lower Word */
#define SYSTEM_DIEIDL_WAFER_NUM_MASK            (0xFFU << 24)
#define SYSTEM_DIEIDL_WAFER_NUM_SHIFT           (24U)
#define SYSTEM_DIEIDL_Y_COORD_MASK              (0xFFFU << 12)
#define SYSTEM_DIEIDL_Y_COORD_SHIFT             (12U)
#define SYSTEM_DIEIDL_X_COORD_MASK              (0xFFFU << 0)
#define SYSTEM_DIEIDL_X_COORD_SHIFT             (0U)

/* DIEIDH - Die Identification Register Upper Word */
#define SYSTEM_DIEIDH_LOT_NUM_MASK              (0xFFFFFFU << 0)
#define SYSTEM_DIEIDH_LOT_NUM_SHIFT             (0U)

/* LPOMONCTL - LPO/Clock Monitor Control Register */
#define SYSTEM_LPOMONCTL_BIAS_ENABLE            (1U << 24)
#define SYSTEM_LPOMONCTL_OSCFRQCONFIGCNT        (1U << 16)
#define SYSTEM_LPOMONCTL_HFTRIM_MASK            (0x1FU << 8)
#define SYSTEM_LPOMONCTL_HFTRIM_SHIFT           (8U)
#define SYSTEM_LPOMONCTL_LFTRIM_MASK            (0x1FU << 0)
#define SYSTEM_LPOMONCTL_LFTRIM_SHIFT           (0U)

/* CLKTEST - Clock Test Register */
#define SYSTEM_CLKTEST_ALTLIMPCLOCKENABLE       (1U << 26)
#define SYSTEM_CLKTEST_RANGEDETCTRL             (1U << 25)
#define SYSTEM_CLKTEST_RANGEDETENASSEL          (1U << 24)
#define SYSTEM_CLKTEST_CLK_TEST_EN_MASK         (0x0FU << 16)
#define SYSTEM_CLKTEST_CLK_TEST_EN_SHIFT        (16U)
#define SYSTEM_CLKTEST_SEL_GIO_PIN_MASK         (0x0FU << 8)
#define SYSTEM_CLKTEST_SEL_GIO_PIN_SHIFT        (8U)
#define SYSTEM_CLKTEST_SEL_ECP_PIN_MASK         (0x0FU << 0)
#define SYSTEM_CLKTEST_SEL_ECP_PIN_SHIFT        (0U)

/* DFTCTRLREG - DFT Control Register */
#define SYSTEM_DFTCTRLREG_DFTWRITE_MASK         (0x03U << 12)
#define SYSTEM_DFTCTRLREG_DFTWRITE_SHIFT        (12U)
#define SYSTEM_DFTCTRLREG_DFTREAD_MASK          (0x03U << 8)
#define SYSTEM_DFTCTRLREG_DFTREAD_SHIFT         (8U)
#define SYSTEM_DFTCTRLREG_TEST_MODE_KEY_MASK    (0x0FU << 0)
#define SYSTEM_DFTCTRLREG_TEST_MODE_KEY_SHIFT   (0U)

/* DFTCTRLREG2 - DFT Control Register 2 */
#define SYSTEM_DFTCTRLREG2_IMPDF_MASK           (0x0FFFFFFFU << 4)
#define SYSTEM_DFTCTRLREG2_IMPDF_SHIFT          (4U)
#define SYSTEM_DFTCTRLREG2_TEST_MODE_KEY_MASK   (0x0FU << 0)
#define SYSTEM_DFTCTRLREG2_TEST_MODE_KEY_SHIFT  (0U)

/* GPREG1 - General Purpose Register 1 */
#define SYSTEM_GPREG1_EMIF_FUNC                         (1U << 31)
#define SYSTEM_GPREG1_PLL1_FBSLIP_FILTER_COUNT_MASK     (0x3FU << 20)
#define SYSTEM_GPREG1_PLL1_FBSLIP_FILTER_COUNT_SHIFT    (20U)
#define SYSTEM_GPREG1_PLL1_FBSLIP_FILTER_KEY_MASK       (0x0FU << 16)
#define SYSTEM_GPREG1_PLL1_FBSLIP_FILTER_KEY_SHIFT      (16U)
#define SYSTEM_GPREG1_OUTPUT_BUFFER_LOW_EMI_MODE_MASK   (0xFFFFU << 0)
#define SYSTEM_GPREG1_OUTPUT_BUFFER_LOW_EMI_MODE_SHIFT  (0U)

/* IMPFASTS - Imprecise Fault Status Register */
#define SYSTEM_IMPFASTS_MASTERID_MASK           (0xFFU << 16)
#define SYSTEM_IMPFASTS_MASTERID_SHIFT          (16U)
#define SYSTEM_IMPFASTS_EMIFA                   (1U << 10)
#define SYSTEM_IMPFASTS_NCBA                    (1U << 9)
#define SYSTEM_IMPFASTS_VBUSA                   (1U << 8)
#define SYSTEM_IMPFASTS_ATYPE                   (1U << 0)

/* IMPFTADD - Imprecise Fault Write Address Register */
#define SYSTEM_IMPFTADD_IMPFTADD_MASK           (0xFFFFFFFFU << 0)
#define SYSTEM_IMPFTADD_IMPFTADD_SHIFT          (0U)

/* SSIR1 - System Software Interrupt Request 1 */
#define SYSTEM_SSIR1_SSKEY1_MASK                (0xFFU << 8)
#define SYSTEM_SSIR1_SSKEY1_SHIFT               (8U)
#define SYSTEM_SSIR1_SSDATA1_MASK               (0xFFU << 0)
#define SYSTEM_SSIR1_SSDATA1_SHIFT              (0U)

/* SSIR2 - System Software Interrupt Request 2 */
#define SYSTEM_SSIR2_SSKEY2_MASK                (0xFFU << 8)
#define SYSTEM_SSIR2_SSKEY2_SHIFT               (8U)
#define SYSTEM_SSIR2_SSDATA2_MASK               (0xFFU << 0)
#define SYSTEM_SSIR2_SSDATA2_SHIFT              (0U)

/* SSIR3 - System Software Interrupt Request 3 */
#define SYSTEM_SSIR3_SSKEY3_MASK                (0xFFU << 8)
#define SYSTEM_SSIR3_SSKEY3_SHIFT               (8U)
#define SYSTEM_SSIR3_SSDATA3_MASK               (0xFFU << 0)
#define SYSTEM_SSIR3_SSDATA3_SHIFT              (0U)

/* SSIR4 - System Software Interrupt Request 4 */
#define SYSTEM_SSIR4_SSKEY4_MASK                (0xFFU << 8)
#define SYSTEM_SSIR4_SSKEY4_SHIFT               (8U)
#define SYSTEM_SSIR4_SSDATA4_MASK               (0xFFU << 0)
#define SYSTEM_SSIR4_SSDATA4_SHIFT              (0U)

/* RAMGCR - RAM Control Register */
#define SYSTEM_RAMGCR_RAM_DFT_EN_MASK           (0x0FU << 16)
#define SYSTEM_RAMGCR_RAM_DFT_EN_SHIFT          (16U)
#define SYSTEM_RAMGCR_WST_AENA0                 (1U << 2)
#define SYSTEM_RAMGCR_WST_DENA0                 (1U << 0)

/* BMMCR1 - Bus Matrix Module Control Register 1 */
#define SYSTEM_BMMCR1_MEMSW_MASK                (0x0FU << 0)
#define SYSTEM_BMMCR1_MEMSW_SHIFT               (0U)

/* CPURSTCR - CPU Reset Control Register */
#define SYSTEM_CPURSTCR_CPU_RESET               (1U << 0)

/* CLKCNTL - Clock Control Register */
#define SYSTEM_CLKCNTL_VCLK2R_MASK              (0x0FU << 24)
#define SYSTEM_CLKCNTL_VCLK2R_SHIFT             (24U)
#define SYSTEM_CLKCNTL_VCLKR_MASK               (0x0FU << 16)
#define SYSTEM_CLKCNTL_VCLKR_SHIFT              (16U)
#define SYSTEM_CLKCNTL_PENA                     (1U << 8)

/* ECPCNTL - ECP Control Register */
#define SYSTEM_ECPCNTL_ECPSSEL                  (1U << 24)
#define SYSTEM_ECPCNTL_ECPCOS                   (1U << 23)
#define SYSTEM_ECPCNTL_ECPINSEL_MASK            (0x03U << 16)
#define SYSTEM_ECPCNTL_ECPINSEL_SHIFT           (16U)
#define SYSTEM_ECPCNTL_ECPDIV_MASK              (0xFFFFU << 0)
#define SYSTEM_ECPCNTL_ECPDIV_SHIFT             (0U)

/* DEVCR1 - DEV Parity Control Register 1 */
#define SYSTEM_DEVCR1_DEVPARSEL_MASK            (0x0FU << 0)
#define SYSTEM_DEVCR1_DEVPARSEL_SHIFT           (0U)

/* SYSECR - System Exception Control Register */
#define SYSTEM_SYSECR_RESET_MASK                (0x03U << 14)
#define SYSTEM_SYSECR_RESET_SHIFT               (14U)

/* SYSESR - System Exception Status Register */
#define SYSTEM_SYSESR_PORST                     (1U << 15)
#define SYSTEM_SYSESR_OSCRST                    (1U << 14)
#define SYSTEM_SYSESR_WDRST                     (1U << 13)
#define SYSTEM_SYSESR_CPURST                    (1U << 5)
#define SYSTEM_SYSESR_SWRST                     (1U << 4)
#define SYSTEM_SYSESR_EXTRST                    (1U << 3)

/* SYSTASR - System Test Abort Status Register */
#define SYSTEM_SYSTASR_EFUSE_Abort_MASK         (0x1FU << 0)
#define SYSTEM_SYSTASR_EFUSE_Abort_SHIFT        (0U)

/* GLBSTAT - Global Status Register */
#define SYSTEM_GLBSTAT_FBSLIP                   (1U << 9)
#define SYSTEM_GLBSTAT_RFSLIP                   (1U << 8)
#define SYSTEM_GLBSTAT_OSCFAIL                  (1U << 0)

/* DEVID - Device Identification Register */
#define SYSTEM_DEVID_CP15                       (1U << 31)
#define SYSTEM_DEVID_UNIQUE_ID_MASK             (0x3FFFU << 17)
#define SYSTEM_DEVID_UNIQUE_ID_SHIFT            (17U)
#define SYSTEM_DEVID_TECH_MASK                  (0x0FU << 13)
#define SYSTEM_DEVID_TECH_SHIFT                 (13U)
#define SYSTEM_DEVID_IO_VOLTAGE                 (1U << 12)
#define SYSTEM_DEVID_PERIPHERAL_PARITY          (1U << 11)
#define SYSTEM_DEVID_FLASH_ECC                  (1U << 10)
#define SYSTEM_DEVID_RAM_ECC                    (1U << 9)
#define SYSTEM_DEVID_VERSION_MASK               (0x3FU << 3)
#define SYSTEM_DEVID_VERSION_SHIFT              (3U)
#define SYSTEM_DEVID_PLATFORM_ID_MASK           (0x07U << 0)
#define SYSTEM_DEVID_PLATFORM_ID_SHIFT          (0U)

/* SSIVEC - Software Interrupt Vector Register */
#define SYSTEM_SSIVEC_SSIDATA_MASK              (0xFFU << 8)
#define SYSTEM_SSIVEC_SSIDATA_SHIFT             (8U)
#define SYSTEM_SSIVEC_SSIVECT_MASK              (0xFFU << 0)
#define SYSTEM_SSIVEC_SSIVECT_SHIFT             (0U)

/* SSIF - System Software Interrupt Flag Register */
#define SYSTEM_SSIF_SSI_FLAG4                   (1U << 3)
#define SYSTEM_SSIF_SSI_FLAG3                   (1U << 2)
#define SYSTEM_SSIF_SSI_FLAG2                   (1U << 1)
#define SYSTEM_SSIF_SSI_FLAG1                   (1U << 0)

/* ========================================================================== */
/*                           SYSTEM2 Register Map                             */
/*                          Base Address: 0xFFFFE100                          */
/* ========================================================================== */

/**
 * @brief SYSTEM2 Register Map Structure
 * 
 * Secondary System Control Registers (SYS2). Additional control for PLL, clocks,
 * and EFUSE.
 */
typedef struct {
    volatile uint32_t PLLCTL3;      /**< 0x00: PLL Control Register 3. */
    volatile uint32_t RESERVED0;    /**< 0x04: Reserved */
    volatile uint32_t STCCLKDIV;    /**< 0x08: CPU Logic BIST Clock Divider. */
    volatile uint32_t RESERVED1[12]; /**< 0x0C-0x38: Reserved */
    volatile uint32_t CLK2CNTRL;    /**< 0x3C: Clock 2 Control Register. */
    volatile uint32_t VCLKACON1;    /**< 0x40: Peripheral Asynchronous Clock Configuration 1 Register. */
    volatile uint32_t RESERVED2[11]; /**< 0x44-0x6C: Reserved */
    volatile uint32_t CLKSLIP;      /**< 0x70: Clock Slip Register. */
    volatile uint32_t RESERVED3[30]; /**< 0x74-0xE8: Reserved */
    volatile uint32_t EFC_CTLREG;   /**< 0xEC: EFUSE Controller Control Register. */
    volatile uint32_t DIEIDL_REG0;  /**< 0xF0: Die Identification Register Lower Word (Mirrored). */
    volatile uint32_t DIEIDH_REG1;  /**< 0xF4: Die Identification Register Upper Word (Mirrored). */
} SYSTEM2_REG_MAP_t;

/* ========================================================================== */
/*                        SYSTEM2 Register Bit Masks                          */
/* ========================================================================== */

/* PLLCTL3 - PLL Control Register 3 */
#define SYSTEM2_PLLCTL3_ODPLL2_MASK             (0x07U << 29)
#define SYSTEM2_PLLCTL3_ODPLL2_SHIFT            (29U)
#define SYSTEM2_PLLCTL3_REFCLKDIV2_MASK         (0x3FU << 16)
#define SYSTEM2_PLLCTL3_REFCLKDIV2_SHIFT        (16U)
#define SYSTEM2_PLLCTL3_PLLMUL2_MASK            (0xFFFFU << 0)
#define SYSTEM2_PLLCTL3_PLLMUL2_SHIFT           (0U)

/* STCCLKDIV - CPU Logic BIST Clock Divider */
#define SYSTEM2_STCCLKDIV_CLKDIV_MASK           (0x07U << 24)
#define SYSTEM2_STCCLKDIV_CLKDIV_SHIFT          (24U)

/* CLK2CNTRL - Clock 2 Control Register */
#define SYSTEM2_CLK2CNTRL_VCLK4R_MASK           (0x0FU << 8)
#define SYSTEM2_CLK2CNTRL_VCLK4R_SHIFT          (8U)
#define SYSTEM2_CLK2CNTRL_VCLK3R_MASK           (0x0FU << 0)
#define SYSTEM2_CLK2CNTRL_VCLK3R_SHIFT          (0U)

/* VCLKACON1 - Peripheral Asynchronous Clock Configuration 1 Register */
#define SYSTEM2_VCLKACON1_VCLKA4R_MASK          (0x07U << 24)
#define SYSTEM2_VCLKACON1_VCLKA4R_SHIFT         (24U)
#define SYSTEM2_VCLKACON1_VCLKA4_DIV_CDDIS      (1U << 20)
#define SYSTEM2_VCLKACON1_VCLKA4S_MASK          (0x0FU << 16)
#define SYSTEM2_VCLKACON1_VCLKA4S_SHIFT         (16U)
#define SYSTEM2_VCLKACON1_VCLKA3R_MASK          (0x07U << 8)
#define SYSTEM2_VCLKACON1_VCLKA3R_SHIFT         (8U)
#define SYSTEM2_VCLKACON1_VCLKA3_DIV_CDDIS      (1U << 4)
#define SYSTEM2_VCLKACON1_VCLKA3S_MASK          (0x0FU << 0)
#define SYSTEM2_VCLKACON1_VCLKA3S_SHIFT         (0U)

/* CLKSLIP - Clock Slip Register */
#define SYSTEM2_CLKSLIP_PLL1_SLIP_FILTER_COUNT_MASK     (0x3FU << 8)
#define SYSTEM2_CLKSLIP_PLL1_SLIP_FILTER_COUNT_SHIFT    (8U)
#define SYSTEM2_CLKSLIP_PLL1_SLIP_FILTER_KEY_MASK       (0x0FU << 0)
#define SYSTEM2_CLKSLIP_PLL1_SLIP_FILTER_KEY_SHIFT      (0U)

/* EFC_CTLREG - EFUSE Controller Control Register */
#define SYSTEM2_EFC_CTLREG_EFC_INSTR_WEN_MASK   (0x0FU << 0)
#define SYSTEM2_EFC_CTLREG_EFC_INSTR_WEN_SHIFT  (0U)

/* DIEIDL_REG0 - Die Identification Register Lower Word (Mirrored) */
#define SYSTEM2_DIEIDL_REG0_WAFER_NUM_MASK      (0xFFU << 24)
#define SYSTEM2_DIEIDL_REG0_WAFER_NUM_SHIFT     (24U)

/* DIEIDH_REG1 - Die Identification Register Upper Word (Mirrored) */
#define SYSTEM2_DIEIDH_REG1_LOT_NUM_MASK        (0xFFFFFFU << 0)
#define SYSTEM2_DIEIDH_REG1_LOT_NUM_SHIFT       (0U)

#endif /* REG_SYSTEM_H */
