/* BSP-GEN-META: created_at=2026-03-04T23:24:27-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_vim.h
 * @brief VIM (Vectored Interrupt Manager) Register Map Header File
 * 
 * This file contains the register map structure and bit field definitions
 * for the VIM peripheral.
 * 
 * Base Address: 0xFFFFFE00
 */

#ifndef REG_VIM_H
#define REG_VIM_H

#include <stdint.h>

/**
 * @brief VIM Register Map Structure
 * 
 * Each register is declared as volatile to prevent compiler optimization
 * of hardware register access.
 */
typedef struct {
    volatile uint32_t IRQINDEX;      /**< 0x00: IRQ Index Offset Vector Register */
    volatile uint32_t FIQINDEX;      /**< 0x04: FIQ Index Offset Vector Register */
    volatile uint32_t RESERVED0[2];  /**< 0x08-0x0C: Reserved */
    volatile uint32_t FIRQPR0;       /**< 0x10: FIQ/IRQ Program Control Register 0 */
    volatile uint32_t FIRQPR1;       /**< 0x14: FIQ/IRQ Program Control Register 1 */
    volatile uint32_t FIRQPR2;       /**< 0x18: FIQ/IRQ Program Control Register 2 */
    volatile uint32_t FIRQPR3;       /**< 0x1C: FIQ/IRQ Program Control Register 3 */
    volatile uint32_t INTREQ0;       /**< 0x20: Pending Interrupt Read Location Register 0 */
    volatile uint32_t INTREQ1;       /**< 0x24: Pending Interrupt Read Location Register 1 */
    volatile uint32_t INTREQ2;       /**< 0x28: Pending Interrupt Read Location Register 2 */
    volatile uint32_t INTREQ3;       /**< 0x2C: Pending Interrupt Read Location Register 3 */
    volatile uint32_t REQENASET0;    /**< 0x30: Interrupt Enable Set Register 0 */
    volatile uint32_t REQENASET1;    /**< 0x34: Interrupt Enable Set Register 1 */
    volatile uint32_t REQENASET2;    /**< 0x38: Interrupt Enable Set Register 2 */
    volatile uint32_t REQENASET3;    /**< 0x3C: Interrupt Enable Set Register 3 */
    volatile uint32_t REQENACLR0;    /**< 0x40: Interrupt Enable Clear Register 0 */
    volatile uint32_t REQENACLR1;    /**< 0x44: Interrupt Enable Clear Register 1 */
    volatile uint32_t REQENACLR2;    /**< 0x48: Interrupt Enable Clear Register 2 */
    volatile uint32_t REQENACLR3;    /**< 0x4C: Interrupt Enable Clear Register 3 */
    volatile uint32_t WAKEENASET0;   /**< 0x50: Wake-up Enable Set Register 0 */
    volatile uint32_t WAKEENASET1;   /**< 0x54: Wake-up Enable Set Register 1 */
    volatile uint32_t WAKEENASET2;   /**< 0x58: Wake-up Enable Set Register 2 */
    volatile uint32_t WAKEENASET3;   /**< 0x5C: Wake-up Enable Set Register 3 */
    volatile uint32_t WAKEENACLR0;   /**< 0x60: Wake-up Enable Clear Register 0 */
    volatile uint32_t WAKEENACLR1;   /**< 0x64: Wake-up Enable Clear Register 1 */
    volatile uint32_t WAKEENACLR2;   /**< 0x68: Wake-up Enable Clear Register 2 */
    volatile uint32_t WAKEENACLR3;   /**< 0x6C: Wake-up Enable Clear Register 3 */
    volatile uint32_t IRQVECREG;     /**< 0x70: IRQ Interrupt Vector Register */
    volatile uint32_t FIQVECREG;     /**< 0x74: FIQ Interrupt Vector Register */
    volatile uint32_t CAPEVT;        /**< 0x78: Capture Event Register */
    volatile uint32_t RESERVED1;     /**< 0x7C: Reserved */
    volatile uint32_t CHANCTRL0;     /**< 0x80: VIM Interrupt Control Register 0 */
    volatile uint32_t RESERVED2[26]; /**< 0x84-0xE8: Reserved */
    volatile uint32_t PARFLG;        /**< 0xEC: Interrupt Vector Table Parity Flag Register */
    volatile uint32_t PARCTL;        /**< 0xF0: Interrupt Vector Table Parity Control Register */
    volatile uint32_t ADDERR;        /**< 0xF4: Address Parity Error Register */
    volatile uint32_t FBPARERR;      /**< 0xF8: Fall-Back Address Parity Error Register */
} VIM_REG_MAP_t;

/* ========================================================================== */
/*                    PARFLG Register Bit Definitions                         */
/* ========================================================================== */
#define VIM_PARFLG_PARFLG_SHIFT         (0U)
#define VIM_PARFLG_PARFLG_MASK          (0x00000001U)

/* ========================================================================== */
/*                    PARCTL Register Bit Definitions                         */
/* ========================================================================== */
#define VIM_PARCTL_PARENA_SHIFT         (0U)
#define VIM_PARCTL_PARENA_MASK          (0x0000000FU)
#define VIM_PARCTL_PARENA_DISABLED      (0x00000005U)
#define VIM_PARCTL_PARENA_ENABLED       (0x0000000AU)

#define VIM_PARCTL_TEST_SHIFT           (8U)
#define VIM_PARCTL_TEST_MASK            (0x00000100U)

/* ========================================================================== */
/*                    ADDERR Register Bit Definitions                         */
/* ========================================================================== */
#define VIM_ADDERR_WORD_OFFSET_SHIFT    (0U)
#define VIM_ADDERR_WORD_OFFSET_MASK     (0x00000003U)

#define VIM_ADDERR_ADDERR_SHIFT         (2U)
#define VIM_ADDERR_ADDERR_MASK          (0x000001FCU)

#define VIM_ADDERR_IVT_OFFSET_SHIFT     (9U)
#define VIM_ADDERR_IVT_OFFSET_MASK      (0xFFFFFE00U)

/* ========================================================================== */
/*                    FBPARERR Register Bit Definitions                       */
/* ========================================================================== */
#define VIM_FBPARERR_FBPARERR_SHIFT     (0U)
#define VIM_FBPARERR_FBPARERR_MASK      (0xFFFFFFFFU)

/* ========================================================================== */
/*                    IRQINDEX Register Bit Definitions                       */
/* ========================================================================== */
#define VIM_IRQINDEX_IRQINDEX_SHIFT     (0U)
#define VIM_IRQINDEX_IRQINDEX_MASK      (0x000000FFU)

/* ========================================================================== */
/*                    FIQINDEX Register Bit Definitions                       */
/* ========================================================================== */
#define VIM_FIQINDEX_FIQINDEX_SHIFT     (0U)
#define VIM_FIQINDEX_FIQINDEX_MASK      (0x000000FFU)

/* ========================================================================== */
/*                    FIRQPR0 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_FIRQPR0_FIRQPR0_SHIFT       (2U)
#define VIM_FIRQPR0_FIRQPR0_MASK        (0xFFFFFFFCU)

/* ========================================================================== */
/*                    FIRQPR1 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_FIRQPR1_FIRQPR1_SHIFT       (0U)
#define VIM_FIRQPR1_FIRQPR1_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    FIRQPR2 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_FIRQPR2_FIRQPR2_SHIFT       (0U)
#define VIM_FIRQPR2_FIRQPR2_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    FIRQPR3 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_FIRQPR3_FIRQPR3_SHIFT       (0U)
#define VIM_FIRQPR3_FIRQPR3_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    INTREQ0 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_INTREQ0_INTREQ0_SHIFT       (0U)
#define VIM_INTREQ0_INTREQ0_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    INTREQ1 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_INTREQ1_INTREQ1_SHIFT       (0U)
#define VIM_INTREQ1_INTREQ1_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    INTREQ2 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_INTREQ2_INTREQ2_SHIFT       (0U)
#define VIM_INTREQ2_INTREQ2_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    INTREQ3 Register Bit Definitions                        */
/* ========================================================================== */
#define VIM_INTREQ3_INTREQ3_SHIFT       (0U)
#define VIM_INTREQ3_INTREQ3_MASK        (0xFFFFFFFFU)

/* ========================================================================== */
/*                    REQENASET0 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENASET0_REQENASET0_SHIFT (2U)
#define VIM_REQENASET0_REQENASET0_MASK  (0xFFFFFFFCU)

/* ========================================================================== */
/*                    REQENASET1 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENASET1_REQENASET1_SHIFT (0U)
#define VIM_REQENASET1_REQENASET1_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    REQENASET2 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENASET2_REQENASET2_SHIFT (0U)
#define VIM_REQENASET2_REQENASET2_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    REQENASET3 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENASET3_REQENASET3_SHIFT (0U)
#define VIM_REQENASET3_REQENASET3_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    REQENACLR0 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENACLR0_REQENACLR0_SHIFT (2U)
#define VIM_REQENACLR0_REQENACLR0_MASK  (0xFFFFFFFCU)

/* ========================================================================== */
/*                    REQENACLR1 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENACLR1_REQENACLR1_SHIFT (0U)
#define VIM_REQENACLR1_REQENACLR1_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    REQENACLR2 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENACLR2_REQENACLR2_SHIFT (0U)
#define VIM_REQENACLR2_REQENACLR2_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    REQENACLR3 Register Bit Definitions                     */
/* ========================================================================== */
#define VIM_REQENACLR3_REQENACLR3_SHIFT (0U)
#define VIM_REQENACLR3_REQENACLR3_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENASET0 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENASET0_WAKEENASET0_SHIFT (0U)
#define VIM_WAKEENASET0_WAKEENASET0_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENASET1 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENASET1_WAKEENASET1_SHIFT (0U)
#define VIM_WAKEENASET1_WAKEENASET1_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENASET2 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENASET2_WAKEENASET2_SHIFT (0U)
#define VIM_WAKEENASET2_WAKEENASET2_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENASET3 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENASET3_WAKEENASET3_SHIFT (0U)
#define VIM_WAKEENASET3_WAKEENASET3_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENACLR0 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENACLR0_WAKEENACLR0_SHIFT (0U)
#define VIM_WAKEENACLR0_WAKEENACLR0_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENACLR1 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENACLR1_WAKEENACLR1_SHIFT (0U)
#define VIM_WAKEENACLR1_WAKEENACLR1_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENACLR2 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENACLR2_WAKEENACLR2_SHIFT (0U)
#define VIM_WAKEENACLR2_WAKEENACLR2_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    WAKEENACLR3 Register Bit Definitions                    */
/* ========================================================================== */
#define VIM_WAKEENACLR3_WAKEENACLR3_SHIFT (0U)
#define VIM_WAKEENACLR3_WAKEENACLR3_MASK  (0xFFFFFFFFU)

/* ========================================================================== */
/*                    IRQVECREG Register Bit Definitions                      */
/* ========================================================================== */
#define VIM_IRQVECREG_IRQVECREG_SHIFT   (0U)
#define VIM_IRQVECREG_IRQVECREG_MASK    (0xFFFFFFFFU)

/* ========================================================================== */
/*                    FIQVECREG Register Bit Definitions                      */
/* ========================================================================== */
#define VIM_FIQVECREG_FIQVECREG_SHIFT   (0U)
#define VIM_FIQVECREG_FIQVECREG_MASK    (0xFFFFFFFFU)

/* ========================================================================== */
/*                    CAPEVT Register Bit Definitions                         */
/* ========================================================================== */
#define VIM_CAPEVT_CAPEVTSRC0_SHIFT     (0U)
#define VIM_CAPEVT_CAPEVTSRC0_MASK      (0x0000007FU)

#define VIM_CAPEVT_CAPEVTSRC1_SHIFT     (16U)
#define VIM_CAPEVT_CAPEVTSRC1_MASK      (0x007F0000U)

/* ========================================================================== */
/*                    CHANCTRL0 Register Bit Definitions                      */
/* ========================================================================== */
#define VIM_CHANCTRL0_CHANMAP0_SHIFT    (24U)
#define VIM_CHANCTRL0_CHANMAP0_MASK     (0x7F000000U)

#define VIM_CHANCTRL0_CHANMAP1_SHIFT    (16U)
#define VIM_CHANCTRL0_CHANMAP1_MASK     (0x007F0000U)

#define VIM_CHANCTRL0_CHANMAP2_SHIFT    (8U)
#define VIM_CHANCTRL0_CHANMAP2_MASK     (0x00007F00U)

#define VIM_CHANCTRL0_CHANMAP3_SHIFT    (0U)
#define VIM_CHANCTRL0_CHANMAP3_MASK     (0x0000007FU)

#endif /* REG_VIM_H */
