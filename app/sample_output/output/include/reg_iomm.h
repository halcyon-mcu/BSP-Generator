/* BSP-GEN-META: created_at=2026-03-04T23:24:27-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_iomm.h
 * @brief IOMM Register Map Header File
 * 
 * This file contains the register map definition for the IOMM peripheral.
 * Base Address: 0xFFFFEA00
 * 
 * @note Auto-generated register definitions - DO NOT EDIT MANUALLY
 */

#ifndef REG_IOMM_H
#define REG_IOMM_H

#include <stdint.h>

/* ========================================================================== */
/*                           Register Map Structure                           */
/* ========================================================================== */

/**
 * @brief IOMM Register Map Structure
 * 
 * This structure defines the memory-mapped registers for the IOMM peripheral.
 * Base Address: 0xFFFFEA00
 */
typedef struct {
    volatile uint32_t REVISION_REG;           /**< 0x000: Revision Register - provides revision information about the IOMM */
    volatile uint32_t RESERVED0[7];           /**< 0x004-0x01C: Reserved */
    volatile uint32_t ENDIAN_REG;             /**< 0x020: Device Endianness Register - reflects the state of device endianness */
    volatile uint32_t RESERVED1[5];           /**< 0x024-0x034: Reserved */
    volatile uint32_t KICK_REG0;              /**< 0x038: Kicker Register 0 - first part of unlock sequence for PINMMRn registers */
    volatile uint32_t KICK_REG1;              /**< 0x03C: Kicker Register 1 - second part of unlock sequence for PINMMRn registers */
    volatile uint32_t RESERVED2[40];          /**< 0x040-0x0DC: Reserved */
    volatile uint32_t ERR_RAW_STATUS_REG;     /**< 0x0E0: Error Raw Status / Set Register - shows status of error conditions before enabling */
    volatile uint32_t ERR_ENABLED_STATUS_REG; /**< 0x0E4: Error Enabled Status / Clear Register - shows status and allows clearing of error status */
    volatile uint32_t ERR_ENABLE_REG;         /**< 0x0E8: Error Signaling Enable Register - shows and allows enabling of interrupts */
    volatile uint32_t ERR_ENABLE_CLR_REG;     /**< 0x0EC: Error Signaling Enable Clear Register - shows status and allows disabling of error signaling */
    volatile uint32_t RESERVED3[1];           /**< 0x0F0: Reserved */
    volatile uint32_t FAULT_ADDRESS_REG;      /**< 0x0F4: Fault Address Register - holds address of first fault transfer */
    volatile uint32_t FAULT_STATUS_REG;       /**< 0x0F8: Fault Status Register - holds status and attributes of first fault transfer */
    volatile uint32_t FAULT_CLEAR_REG;        /**< 0x0FC: Fault Clear Register - allows clearing current fault to capture another */
    volatile uint32_t RESERVED4[4];           /**< 0x100-0x10C: Reserved */
    volatile uint32_t PINMMR0;                /**< 0x110: Pin Multiplexing Control Register 0 */
    volatile uint32_t PINMMR1;                /**< 0x114: Pin Multiplexing Control Register 1 */
    volatile uint32_t PINMMR2;                /**< 0x118: Pin Multiplexing Control Register 2 */
    volatile uint32_t PINMMR3;                /**< 0x11C: Pin Multiplexing Control Register 3 */
    volatile uint32_t PINMMR4;                /**< 0x120: Pin Multiplexing Control Register 4 */
    volatile uint32_t PINMMR5;                /**< 0x124: Pin Multiplexing Control Register 5 */
    volatile uint32_t PINMMR6;                /**< 0x128: Pin Multiplexing Control Register 6 */
    volatile uint32_t PINMMR7;                /**< 0x12C: Pin Multiplexing Control Register 7 */
    volatile uint32_t PINMMR8;                /**< 0x130: Pin Multiplexing Control Register 8 */
    volatile uint32_t PINMMR9;                /**< 0x134: Pin Multiplexing Control Register 9 */
    volatile uint32_t PINMMR10;               /**< 0x138: Pin Multiplexing Control Register 10 */
    volatile uint32_t PINMMR11;               /**< 0x13C: Pin Multiplexing Control Register 11 */
    volatile uint32_t PINMMR12;               /**< 0x140: Pin Multiplexing Control Register 12 */
    volatile uint32_t PINMMR13;               /**< 0x144: Pin Multiplexing Control Register 13 */
    volatile uint32_t PINMMR14;               /**< 0x148: Pin Multiplexing Control Register 14 */
    volatile uint32_t PINMMR15;               /**< 0x14C: Pin Multiplexing Control Register 15 */
    volatile uint32_t PINMMR16;               /**< 0x150: Pin Multiplexing Control Register 16 */
    volatile uint32_t PINMMR17;               /**< 0x154: Pin Multiplexing Control Register 17 */
    volatile uint32_t PINMMR18;               /**< 0x158: Pin Multiplexing Control Register 18 */
    volatile uint32_t PINMMR19;               /**< 0x15C: Pin Multiplexing Control Register 19 */
    volatile uint32_t PINMMR20;               /**< 0x160: Pin Multiplexing Control Register 20 */
    volatile uint32_t PINMMR21;               /**< 0x164: Pin Multiplexing Control Register 21 */
    volatile uint32_t PINMMR22;               /**< 0x168: Pin Multiplexing Control Register 22 */
    volatile uint32_t PINMMR23;               /**< 0x16C: Pin Multiplexing Control Register 23 */
    volatile uint32_t PINMMR24;               /**< 0x170: Pin Multiplexing Control Register 24 */
    volatile uint32_t PINMMR25;               /**< 0x174: Pin Multiplexing Control Register 25 */
    volatile uint32_t PINMMR26;               /**< 0x178: Pin Multiplexing Control Register 26 */
    volatile uint32_t PINMMR27;               /**< 0x17C: Pin Multiplexing Control Register 27 */
    volatile uint32_t PINMMR28;               /**< 0x180: Pin Multiplexing Control Register 28 */
    volatile uint32_t RESERVED5[20];          /**< 0x184-0x1D0: Reserved */
    volatile uint32_t PINMMR29;               /**< 0x1D4: Pin Multiplexing Control Register 29 - controls EMIF CLK, EMIF fast mode, Ethernet mode */
} IOMM_REG_MAP_t;

/* ========================================================================== */
/*                    REVISION_REG Register Bit Masks                         */
/* ========================================================================== */

#define IOMM_REVISION_REG_REV_SCHEME_SHIFT       (30U)
#define IOMM_REVISION_REG_REV_SCHEME_MASK        (0xC0000000U)

#define IOMM_REVISION_REG_REV_MODULE_SHIFT       (16U)
#define IOMM_REVISION_REG_REV_MODULE_MASK        (0x0FFF0000U)

#define IOMM_REVISION_REG_REV_RTL_SHIFT          (11U)
#define IOMM_REVISION_REG_REV_RTL_MASK           (0x0000F800U)

#define IOMM_REVISION_REG_REV_MAJOR_SHIFT        (8U)
#define IOMM_REVISION_REG_REV_MAJOR_MASK         (0x00000700U)

#define IOMM_REVISION_REG_REV_CUSTOM_SHIFT       (6U)
#define IOMM_REVISION_REG_REV_CUSTOM_MASK        (0x000000C0U)

#define IOMM_REVISION_REG_REV_MINOR_SHIFT        (0U)
#define IOMM_REVISION_REG_REV_MINOR_MASK         (0x0000003FU)

/* ========================================================================== */
/*                     ENDIAN_REG Register Bit Masks                          */
/* ========================================================================== */

#define IOMM_ENDIAN_REG_ENDIAN_SHIFT             (0U)
#define IOMM_ENDIAN_REG_ENDIAN_MASK              (0x00000001U)

/* ========================================================================== */
/*                     KICK_REG0 Register Bit Masks                           */
/* ========================================================================== */

#define IOMM_KICK_REG0_KICK0_SHIFT               (0U)
#define IOMM_KICK_REG0_KICK0_MASK                (0xFFFFFFFFU)
#define IOMM_KICK_REG0_UNLOCK_VALUE              (0x83E70B13U)

/* ========================================================================== */
/*                     KICK_REG1 Register Bit Masks                           */
/* ========================================================================== */

#define IOMM_KICK_REG1_KICK1_SHIFT               (0U)
#define IOMM_KICK_REG1_KICK1_MASK                (0xFFFFFFFFU)
#define IOMM_KICK_REG1_UNLOCK_VALUE              (0x95A4F1E0U)

/* ========================================================================== */
/*                 ERR_RAW_STATUS_REG Register Bit Masks                      */
/* ========================================================================== */

#define IOMM_ERR_RAW_STATUS_REG_ADDR_ERR_SHIFT   (1U)
#define IOMM_ERR_RAW_STATUS_REG_ADDR_ERR_MASK    (0x00000002U)

#define IOMM_ERR_RAW_STATUS_REG_PROT_ERR_SHIFT   (0U)
#define IOMM_ERR_RAW_STATUS_REG_PROT_ERR_MASK    (0x00000001U)

/* ========================================================================== */
/*              ERR_ENABLED_STATUS_REG Register Bit Masks                     */
/* ========================================================================== */

#define IOMM_ERR_ENABLED_STATUS_REG_ENABLED_ADDR_ERR_SHIFT  (1U)
#define IOMM_ERR_ENABLED_STATUS_REG_ENABLED_ADDR_ERR_MASK   (0x00000002U)

#define IOMM_ERR_ENABLED_STATUS_REG_ENABLED_PROT_ERR_SHIFT  (0U)
#define IOMM_ERR_ENABLED_STATUS_REG_ENABLED_PROT_ERR_MASK   (0x00000001U)

/* ========================================================================== */
/*                  ERR_ENABLE_REG Register Bit Masks                         */
/* ========================================================================== */

#define IOMM_ERR_ENABLE_REG_ADDR_ERR_EN_SHIFT    (1U)
#define IOMM_ERR_ENABLE_REG_ADDR_ERR_EN_MASK     (0x00000002U)

#define IOMM_ERR_ENABLE_REG_PROT_ERR_EN_SHIFT    (0U)
#define IOMM_ERR_ENABLE_REG_PROT_ERR_EN_MASK     (0x00000001U)

/* ========================================================================== */
/*                ERR_ENABLE_CLR_REG Register Bit Masks                       */
/* ========================================================================== */

#define IOMM_ERR_ENABLE_CLR_REG_ADDR_ERR_EN_CLR_SHIFT  (1U)
#define IOMM_ERR_ENABLE_CLR_REG_ADDR_ERR_EN_CLR_MASK   (0x00000002U)

#define IOMM_ERR_ENABLE_CLR_REG_PROT_ERR_EN_CLR_SHIFT  (0U)
#define IOMM_ERR_ENABLE_CLR_REG_PROT_ERR_EN_CLR_MASK   (0x00000001U)

/* ========================================================================== */
/*                FAULT_ADDRESS_REG Register Bit Masks                        */
/* ========================================================================== */

#define IOMM_FAULT_ADDRESS_REG_FAULT_ADDR_SHIFT  (0U)
#define IOMM_FAULT_ADDRESS_REG_FAULT_ADDR_MASK   (0x000001FFU)

/* ========================================================================== */
/*                 FAULT_STATUS_REG Register Bit Masks                        */
/* ========================================================================== */

#define IOMM_FAULT_STATUS_REG_FAULT_ID_SHIFT     (24U)
#define IOMM_FAULT_STATUS_REG_FAULT_ID_MASK      (0x0F000000U)

#define IOMM_FAULT_STATUS_REG_FAULT_MSTID_SHIFT  (16U)
#define IOMM_FAULT_STATUS_REG_FAULT_MSTID_MASK   (0x00FF0000U)

#define IOMM_FAULT_STATUS_REG_FAULT_PRIVID_SHIFT (9U)
#define IOMM_FAULT_STATUS_REG_FAULT_PRIVID_MASK  (0x00001E00U)

#define IOMM_FAULT_STATUS_REG_FAULT_TYPE_SHIFT   (0U)
#define IOMM_FAULT_STATUS_REG_FAULT_TYPE_MASK    (0x0000003FU)

/* Fault Type Values */
#define IOMM_FAULT_TYPE_NO_FAULT                 (0x00U)
#define IOMM_FAULT_TYPE_USER_EXEC                (0x01U)
#define IOMM_FAULT_TYPE_USER_WRITE               (0x02U)
#define IOMM_FAULT_TYPE_USER_READ                (0x04U)
#define IOMM_FAULT_TYPE_SUPER_EXEC               (0x08U)
#define IOMM_FAULT_TYPE_SUPER_WRITE              (0x10U)
#define IOMM_FAULT_TYPE_SUPER_READ               (0x20U)

/* ========================================================================== */
/*                 FAULT_CLEAR_REG Register Bit Masks                         */
/* ========================================================================== */

#define IOMM_FAULT_CLEAR_REG_FAULT_CLEAR_SHIFT   (0U)
#define IOMM_FAULT_CLEAR_REG_FAULT_CLEAR_MASK    (0x00000001U)

/* ========================================================================== */
/*                      PINMMR0 Register Bit Masks                            */
/* ========================================================================== */

#define IOMM_PINMMR0_31_24_SHIFT                 (24U)
#define IOMM_PINMMR0_31_24_MASK                  (0xFF000000U)

#define IOMM_PINMMR0_23_16_SHIFT                 (16U)
#define IOMM_PINMMR0_23_16_MASK                  (0x00FF0000U)

#define IOMM_PINMMR0_15_8_SHIFT                  (8U)
#define IOMM_PINMMR0_15_8_MASK                   (0x0000FF00U)

#define IOMM_PINMMR0_7_0_SHIFT                   (0U)
#define IOMM_PINMMR0_7_0_MASK                    (0x000000FFU)

/* ========================================================================== */
/*                      PINMMR29 Register Bit Masks                           */
/* ========================================================================== */

#define IOMM_PINMMR29_24_SHIFT                   (24U)
#define IOMM_PINMMR29_24_MASK                    (0x01000000U)

#define IOMM_PINMMR29_18_SHIFT                   (18U)
#define IOMM_PINMMR29_18_MASK                    (0x00040000U)

#define IOMM_PINMMR29_17_SHIFT                   (17U)
#define IOMM_PINMMR29_17_MASK                    (0x00020000U)

#define IOMM_PINMMR29_16_SHIFT                   (16U)
#define IOMM_PINMMR29_16_MASK                    (0x00010000U)

#define IOMM_PINMMR29_8_SHIFT                    (8U)
#define IOMM_PINMMR29_8_MASK                     (0x00000100U)

/* ========================================================================== */
/*                         Base Address Definition                            */
/* ========================================================================== */

#define IOMM_BASE_ADDR                           (0xFFFFEA00U)

#endif /* REG_IOMM_H */
