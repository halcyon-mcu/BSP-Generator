/* BSP-GEN-META: created_at=2026-03-04T23:24:16-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_pcr.h
 * @brief PCR (Peripheral Central Resource Controller) Register Map Header File
 * @details This file contains the register map structure and bit-field definitions
 *          for the PCR peripheral.
 *
 * Base Address: 0xFFFFE000
 *
 * @note Auto-generated register map - DO NOT EDIT MANUALLY
 */

#ifndef REG_PCR_H
#define REG_PCR_H

#include <stdint.h>

/*===========================================================================*/
/* Register Map Structure                                                   */
/*===========================================================================*/

/**
 * @brief PCR Register Map Structure
 * @details Peripheral Central Resource (PCR) Controller register layout
 */
typedef struct {
    volatile uint32_t PMPROTSET0;      /**< 0x00: Peripheral Memory Protection Set Register 0 */
    volatile uint32_t PMPROTSET1;      /**< 0x04: Peripheral Memory Protection Set Register 1 */
    volatile uint32_t RESERVED0[2];    /**< 0x08-0x0C: Reserved */
    volatile uint32_t PMPROTCLR0;      /**< 0x10: Peripheral Memory Protection Clear Register 0 */
    volatile uint32_t PMPROTCLR1;      /**< 0x14: Peripheral Memory Protection Clear Register 1 */
    volatile uint32_t RESERVED1[2];    /**< 0x18-0x1C: Reserved */
    volatile uint32_t PPROTSET0;       /**< 0x20: Peripheral Protection Set Register 0 */
    volatile uint32_t PPROTSET1;       /**< 0x24: Peripheral Protection Set Register 1 */
    volatile uint32_t PPROTSET2;       /**< 0x28: Peripheral Protection Set Register 2 */
    volatile uint32_t PPROTSET3;       /**< 0x2C: Peripheral Protection Set Register 3 */
    volatile uint32_t RESERVED2[4];    /**< 0x30-0x3C: Reserved */
    volatile uint32_t PPROTCLR0;       /**< 0x40: Peripheral Protection Clear Register 0 */
    volatile uint32_t PPROTCLR1;       /**< 0x44: Peripheral Protection Clear Register 1 */
    volatile uint32_t PPROTCLR2;       /**< 0x48: Peripheral Protection Clear Register 2 */
    volatile uint32_t PPROTCLR3;       /**< 0x4C: Peripheral Protection Clear Register 3 */
    volatile uint32_t RESERVED3[4];    /**< 0x50-0x5C: Reserved */
    volatile uint32_t PCSPWRDWNSET0;   /**< 0x60: Peripheral Memory Power-Down Set Register 0 */
    volatile uint32_t PCSPWRDWNSET1;   /**< 0x64: Peripheral Memory Power-Down Set Register 1 */
    volatile uint32_t RESERVED4[2];    /**< 0x68-0x6C: Reserved */
    volatile uint32_t PCSPWRDWNCLR0;   /**< 0x70: Peripheral Memory Power-Down Clear Register 0 */
    volatile uint32_t PCSPWRDWNCLR1;   /**< 0x74: Peripheral Memory Power-Down Clear Register 1 */
    volatile uint32_t RESERVED5[2];    /**< 0x78-0x7C: Reserved */
    volatile uint32_t PSPWRDWNSET0;    /**< 0x80: Peripheral Power-Down Set Register 0 */
    volatile uint32_t PSPWRDWNSET1;    /**< 0x84: Peripheral Power-Down Set Register 1 */
    volatile uint32_t PSPWRDWNSET2;    /**< 0x88: Peripheral Power-Down Set Register 2 */
    volatile uint32_t PSPWRDWNSET3;    /**< 0x8C: Peripheral Power-Down Set Register 3 */
    volatile uint32_t RESERVED6[4];    /**< 0x90-0x9C: Reserved */
    volatile uint32_t PSPWRDWNCLR0;    /**< 0xA0: Peripheral Power-Down Clear Register 0 */
    volatile uint32_t PSPWRDWNCLR1;    /**< 0xA4: Peripheral Power-Down Clear Register 1 */
    volatile uint32_t PSPWRDWNCLR2;    /**< 0xA8: Peripheral Power-Down Clear Register 2 */
    volatile uint32_t PSPWRDWNCLR3;    /**< 0xAC: Peripheral Power-Down Clear Register 3 */
} PCR_REG_MAP_t;

/*===========================================================================*/
/* Register Bit-Field Definitions                                           */
/*===========================================================================*/

/* PMPROTSET0 - Peripheral Memory Protection Set Register 0 (0x00) */
#define PCR_PMPROTSET0_MP_PROTSET_MASK          (0xFFFFFFFFu)
#define PCR_PMPROTSET0_MP_PROTSET_SHIFT         (0u)

/* PMPROTSET1 - Peripheral Memory Protection Set Register 1 (0x04) */
#define PCR_PMPROTSET1_MP_PROTSET_MASK          (0xFFFFFFFFu)
#define PCR_PMPROTSET1_MP_PROTSET_SHIFT         (0u)

/* PMPROTCLR0 - Peripheral Memory Protection Clear Register 0 (0x10) */
#define PCR_PMPROTCLR0_MP_PROTCLR_MASK          (0xFFFFFFFFu)
#define PCR_PMPROTCLR0_MP_PROTCLR_SHIFT         (0u)

/* PMPROTCLR1 - Peripheral Memory Protection Clear Register 1 (0x14) */
#define PCR_PMPROTCLR1_MP_PROTCLR_MASK          (0xFFFFFFFFu)
#define PCR_PMPROTCLR1_MP_PROTCLR_SHIFT         (0u)

/* PPROTSET0 - Peripheral Protection Set Register 0 (0x20) */
#define PCR_PPROTSET0_P_PROTSET_MASK            (0xFFFFFFFFu)
#define PCR_PPROTSET0_P_PROTSET_SHIFT           (0u)

/* PPROTSET1 - Peripheral Protection Set Register 1 (0x24) */
#define PCR_PPROTSET1_P_PROTSET_MASK            (0xFFFFFFFFu)
#define PCR_PPROTSET1_P_PROTSET_SHIFT           (0u)

/* PPROTSET2 - Peripheral Protection Set Register 2 (0x28) */
#define PCR_PPROTSET2_P_PROTSET_MASK            (0xFFFFFFFFu)
#define PCR_PPROTSET2_P_PROTSET_SHIFT           (0u)

/* PPROTSET3 - Peripheral Protection Set Register 3 (0x2C) */
#define PCR_PPROTSET3_P_PROTSET_MASK            (0xFFFFFFFFu)
#define PCR_PPROTSET3_P_PROTSET_SHIFT           (0u)

/* PPROTCLR0 - Peripheral Protection Clear Register 0 (0x40) */
#define PCR_PPROTCLR0_P_PROTCLR_MASK            (0xFFFFFFFFu)
#define PCR_PPROTCLR0_P_PROTCLR_SHIFT           (0u)

/* PPROTCLR1 - Peripheral Protection Clear Register 1 (0x44) */
#define PCR_PPROTCLR1_P_PROTCLR_MASK            (0xFFFFFFFFu)
#define PCR_PPROTCLR1_P_PROTCLR_SHIFT           (0u)

/* PPROTCLR2 - Peripheral Protection Clear Register 2 (0x48) */
#define PCR_PPROTCLR2_P_PROTCLR_MASK            (0xFFFFFFFFu)
#define PCR_PPROTCLR2_P_PROTCLR_SHIFT           (0u)

/* PPROTCLR3 - Peripheral Protection Clear Register 3 (0x4C) */
#define PCR_PPROTCLR3_P_PROTCLR_MASK            (0xFFFFFFFFu)
#define PCR_PPROTCLR3_P_PROTCLR_SHIFT           (0u)

/* PCSPWRDWNSET0 - Peripheral Memory Power-Down Set Register 0 (0x60) */
#define PCR_PCSPWRDWNSET0_PCSPWRDWNSET_MASK     (0xFFFFFFFFu)
#define PCR_PCSPWRDWNSET0_PCSPWRDWNSET_SHIFT    (0u)

/* PCSPWRDWNSET1 - Peripheral Memory Power-Down Set Register 1 (0x64) */
#define PCR_PCSPWRDWNSET1_PCSPWRDWNSET_MASK     (0xFFFFFFFFu)
#define PCR_PCSPWRDWNSET1_PCSPWRDWNSET_SHIFT    (0u)

/* PCSPWRDWNCLR0 - Peripheral Memory Power-Down Clear Register 0 (0x70) */
#define PCR_PCSPWRDWNCLR0_PCSPWRDWNCLR_MASK     (0xFFFFFFFFu)
#define PCR_PCSPWRDWNCLR0_PCSPWRDWNCLR_SHIFT    (0u)

/* PCSPWRDWNCLR1 - Peripheral Memory Power-Down Clear Register 1 (0x74) */
#define PCR_PCSPWRDWNCLR1_PCSPWRDWNCLR_MASK     (0xFFFFFFFFu)
#define PCR_PCSPWRDWNCLR1_PCSPWRDWNCLR_SHIFT    (0u)

/* PSPWRDWNSET0 - Peripheral Power-Down Set Register 0 (0x80) */
#define PCR_PSPWRDWNSET0_PSPWRDWNSET_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNSET0_PSPWRDWNSET_SHIFT      (0u)

/* PSPWRDWNSET1 - Peripheral Power-Down Set Register 1 (0x84) */
#define PCR_PSPWRDWNSET1_PSPWRDWNSET_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNSET1_PSPWRDWNSET_SHIFT      (0u)

/* PSPWRDWNSET2 - Peripheral Power-Down Set Register 2 (0x88) */
#define PCR_PSPWRDWNSET2_PSPWRDWNSET_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNSET2_PSPWRDWNSET_SHIFT      (0u)

/* PSPWRDWNSET3 - Peripheral Power-Down Set Register 3 (0x8C) */
#define PCR_PSPWRDWNSET3_PSPWRDWNSET_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNSET3_PSPWRDWNSET_SHIFT      (0u)

/* PSPWRDWNCLR0 - Peripheral Power-Down Clear Register 0 (0xA0) */
#define PCR_PSPWRDWNCLR0_PSPWRDWNCLR_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNCLR0_PSPWRDWNCLR_SHIFT      (0u)

/* PSPWRDWNCLR1 - Peripheral Power-Down Clear Register 1 (0xA4) */
#define PCR_PSPWRDWNCLR1_PSPWRDWNCLR_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNCLR1_PSPWRDWNCLR_SHIFT      (0u)

/* PSPWRDWNCLR2 - Peripheral Power-Down Clear Register 2 (0xA8) */
#define PCR_PSPWRDWNCLR2_PSPWRDWNCLR_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNCLR2_PSPWRDWNCLR_SHIFT      (0u)

/* PSPWRDWNCLR3 - Peripheral Power-Down Clear Register 3 (0xAC) */
#define PCR_PSPWRDWNCLR3_PSPWRDWNCLR_MASK       (0xFFFFFFFFu)
#define PCR_PSPWRDWNCLR3_PSPWRDWNCLR_SHIFT      (0u)

/*===========================================================================*/
/* Helper Macros                                                             */
/*===========================================================================*/

/**
 * @brief Base Address
 * @note This is for reference only. Define the base pointer in the driver.
 */
#define PCR_BASE_ADDRESS                        (0xFFFFE000u)

#endif /* REG_PCR_H */
