/* BSP-GEN-META: created_at=2026-03-04T23:24:26-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_lin.h
 * @brief LIN Peripheral Register Map Header File
 * 
 * This file contains the register map structure and bit-field definitions
 * for the LIN (Local Interconnect Network) peripheral.
 * 
 * Base Address: 0xFFF7E400
 */

#ifndef REG_LIN_H
#define REG_LIN_H

#include <stdint.h>

/**
 * @brief LIN Register Map Structure
 * 
 * Each register is declared as volatile uint32_t to prevent compiler
 * optimization of hardware register access.
 */
typedef struct {
    volatile uint32_t SCIGCR0;          /**< 0x00 - SCI Global Control Register 0 */
    volatile uint32_t SCIGCR1;          /**< 0x04 - SCI Global Control Register 1 */
    volatile uint32_t SCIGCR2;          /**< 0x08 - SCI Global Control Register 2 */
    volatile uint32_t SCISETINT;        /**< 0x0C - SCI Set Interrupt Register */
    volatile uint32_t SCICLEARINT;      /**< 0x10 - SCI Clear Interrupt Register */
    volatile uint32_t SCISETINTLVL;     /**< 0x14 - SCI Set Interrupt Level Register */
    volatile uint32_t SCICLEARINTLVL;   /**< 0x18 - SCI Clear Interrupt Level Register */
    volatile uint32_t SCIFLR;           /**< 0x1C - SCI Flags Register */
    volatile uint32_t SCIINTVECT0;      /**< 0x20 - SCI Interrupt Vector Offset 0 */
    volatile uint32_t SCIINTVECT1;      /**< 0x24 - SCI Interrupt Vector Offset 1 */
    volatile uint32_t SCIFORMAT;        /**< 0x28 - SCI Format Control Register */
    volatile uint32_t BRS;              /**< 0x2C - Baud Rate Selection Register */
    volatile uint32_t SCIED;            /**< 0x30 - Receiver Emulation Data Buffer */
    volatile uint32_t SCIRD;            /**< 0x34 - Receiver Data Buffer */
    volatile uint32_t SCITD;            /**< 0x38 - Transmit Data Buffer */
    volatile uint32_t SCIPIO0;          /**< 0x3C - SCI Pin I/O Control Register 0 */
    volatile uint32_t SCIPIO1;          /**< 0x40 - SCI Pin I/O Control Register 1 */
    volatile uint32_t SCIPIO2;          /**< 0x44 - SCI Pin I/O Control Register 2 */
    volatile uint32_t SCIPIO3;          /**< 0x48 - SCI Pin I/O Control Register 3 */
    volatile uint32_t SCIPIO4;          /**< 0x4C - SCI Pin I/O Control Register 4 */
    volatile uint32_t SCIPIO5;          /**< 0x50 - SCI Pin I/O Control Register 5 */
    volatile uint32_t SCIPIO6;          /**< 0x54 - SCI Pin I/O Control Register 6 */
    volatile uint32_t SCIPIO7;          /**< 0x58 - SCI Pin I/O Control Register 7 */
    volatile uint32_t SCIPIO8;          /**< 0x5C - SCI Pin I/O Control Register 8 */
    volatile uint32_t LINCOMPARE;       /**< 0x60 - LIN Compare Register */
    volatile uint32_t LINRD0;           /**< 0x64 - LIN Receive Buffer 0 Register */
    volatile uint32_t LINRD1;           /**< 0x68 - LIN Receive Buffer 1 Register */
    volatile uint32_t LINMASK;          /**< 0x6C - LIN Mask Register */
    volatile uint32_t LINID;            /**< 0x70 - LIN Identification Register */
    volatile uint32_t LINTD0;           /**< 0x74 - LIN Transmit Buffer 0 */
    volatile uint32_t LINTD1;           /**< 0x78 - LIN Transmit Buffer 1 */
    volatile uint32_t MBRS;             /**< 0x7C - Maximum Baud Rate Selection Register */
    volatile uint32_t RESERVED0[4];     /**< 0x80-0x8C - Reserved */
    volatile uint32_t IODFTCTRL;        /**< 0x90 - Input/Output Error Enable Register */
} LIN_REG_MAP_t;

/*==============================================================================
                        SCIGCR0 - SCI Global Control Register 0
==============================================================================*/
#define LIN_SCIGCR0_RESET                       (0x00000001u)

/*==============================================================================
                        SCIGCR1 - SCI Global Control Register 1
==============================================================================*/
#define LIN_SCIGCR1_TXENA                       (0x02000000u)
#define LIN_SCIGCR1_RXENA                       (0x01000000u)
#define LIN_SCIGCR1_CONT                        (0x00020000u)
#define LIN_SCIGCR1_LOOP_BACK                   (0x00010000u)
#define LIN_SCIGCR1_STOP_EXT_FRAME              (0x00002000u)
#define LIN_SCIGCR1_HGEN_CTRL                   (0x00001000u)
#define LIN_SCIGCR1_CTYPE                       (0x00000800u)
#define LIN_SCIGCR1_MBUF_MODE                   (0x00000400u)
#define LIN_SCIGCR1_ADAPT                       (0x00000200u)
#define LIN_SCIGCR1_SLEEP                       (0x00000100u)
#define LIN_SCIGCR1_SWnRST                      (0x00000080u)
#define LIN_SCIGCR1_LIN_MODE                    (0x00000040u)
#define LIN_SCIGCR1_CLOCK                       (0x00000020u)
#define LIN_SCIGCR1_STOP                        (0x00000010u)
#define LIN_SCIGCR1_PARITY                      (0x00000008u)
#define LIN_SCIGCR1_PARITY_ENA                  (0x00000004u)
#define LIN_SCIGCR1_TIMING_MODE                 (0x00000002u)
#define LIN_SCIGCR1_COMM_MODE                   (0x00000001u)

/*==============================================================================
                        SCIGCR2 - SCI Global Control Register 2
==============================================================================*/
#define LIN_SCIGCR2_CC                          (0x00020000u)
#define LIN_SCIGCR2_SC                          (0x00010000u)
#define LIN_SCIGCR2_GEN_WU                      (0x00000100u)
#define LIN_SCIGCR2_POWERDOWN                   (0x00000001u)

/*==============================================================================
                        SCISETINT - SCI Set Interrupt Register
==============================================================================*/
#define LIN_SCISETINT_SET_BE_INT                (0x80000000u)
#define LIN_SCISETINT_SET_PBE_INT               (0x40000000u)
#define LIN_SCISETINT_SET_CE_INT                (0x20000000u)
#define LIN_SCISETINT_SET_ISFE_INT              (0x10000000u)
#define LIN_SCISETINT_SET_NRE_INT               (0x08000000u)
#define LIN_SCISETINT_SET_FE_INT                (0x04000000u)
#define LIN_SCISETINT_SET_OE_INT                (0x02000000u)
#define LIN_SCISETINT_SET_PE_INT                (0x01000000u)
#define LIN_SCISETINT_SET_RX_DMA_ALL            (0x00040000u)
#define LIN_SCISETINT_SET_RX_DMA                (0x00020000u)
#define LIN_SCISETINT_SET_TX_DMA                (0x00010000u)
#define LIN_SCISETINT_SET_ID_INT                (0x00002000u)
#define LIN_SCISETINT_SET_RX_INT                (0x00000200u)
#define LIN_SCISETINT_SET_TX_INT                (0x00000100u)
#define LIN_SCISETINT_SET_TOA3WUS_INT           (0x00000080u)
#define LIN_SCISETINT_SET_TOAWUS_INT            (0x00000040u)
#define LIN_SCISETINT_SET_TIMEOUT_INT           (0x00000010u)
#define LIN_SCISETINT_SET_WAKEUP_INT            (0x00000002u)
#define LIN_SCISETINT_SET_BRKDT_INT             (0x00000001u)

/*==============================================================================
                        SCICLEARINT - SCI Clear Interrupt Register
==============================================================================*/
#define LIN_SCICLEARINT_CLR_BE_INT              (0x80000000u)
#define LIN_SCICLEARINT_CLR_RX_INT              (0x00000200u)
#define LIN_SCICLEARINT_CLR_TX_INT              (0x00000100u)

/*==============================================================================
                        SCISETINTLVL - SCI Set Interrupt Level Register
==============================================================================*/
#define LIN_SCISETINTLVL_SET_BE_INT_LVL         (0x80000000u)
#define LIN_SCISETINTLVL_SET_RX_INT_LVL         (0x00000200u)
#define LIN_SCISETINTLVL_SET_TX_INT_LVL         (0x00000100u)

/*==============================================================================
                        SCIFLR - SCI Flags Register
==============================================================================*/
#define LIN_SCIFLR_BE                           (0x80000000u)
#define LIN_SCIFLR_PBE                          (0x40000000u)
#define LIN_SCIFLR_CE                           (0x20000000u)
#define LIN_SCIFLR_ISFE                         (0x10000000u)
#define LIN_SCIFLR_NRE                          (0x08000000u)
#define LIN_SCIFLR_FE                           (0x04000000u)
#define LIN_SCIFLR_OE                           (0x02000000u)
#define LIN_SCIFLR_PE                           (0x01000000u)
#define LIN_SCIFLR_ID_RX_FLAG                   (0x00004000u)
#define LIN_SCIFLR_ID_TX_FLAG                   (0x00002000u)
#define LIN_SCIFLR_RXWAKE                       (0x00001000u)
#define LIN_SCIFLR_TX_EMPTY                     (0x00000800u)
#define LIN_SCIFLR_TXWAKE                       (0x00000400u)
#define LIN_SCIFLR_RXRDY                        (0x00000200u)
#define LIN_SCIFLR_TXRDY                        (0x00000100u)
#define LIN_SCIFLR_TOA3WUS                      (0x00000080u)
#define LIN_SCIFLR_TOAWUS                       (0x00000040u)
#define LIN_SCIFLR_TIMEOUT                      (0x00000010u)
#define LIN_SCIFLR_BUSY                         (0x00000008u)
#define LIN_SCIFLR_IDLE                         (0x00000004u)
#define LIN_SCIFLR_WAKEUP                       (0x00000002u)
#define LIN_SCIFLR_BRKDT                        (0x00000001u)

/*==============================================================================
                        SCIINTVECT0 - SCI Interrupt Vector Offset 0
==============================================================================*/
#define LIN_SCIINTVECT0_INTVECT0_MASK           (0x0000001Fu)

/*==============================================================================
                        SCIINTVECT1 - SCI Interrupt Vector Offset 1
==============================================================================*/
#define LIN_SCIINTVECT1_INTVECT1_MASK           (0x0000001Fu)

/*==============================================================================
                        SCIFORMAT - SCI Format Control Register
==============================================================================*/
#define LIN_SCIFORMAT_LENGTH_MASK               (0x00070000u)
#define LIN_SCIFORMAT_LENGTH_SHIFT              (16u)
#define LIN_SCIFORMAT_CHAR_MASK                 (0x00000007u)
#define LIN_SCIFORMAT_CHAR_SHIFT                (0u)

/*==============================================================================
                        BRS - Baud Rate Selection Register
==============================================================================*/
#define LIN_BRS_U_MASK                          (0x70000000u)
#define LIN_BRS_U_SHIFT                         (28u)
#define LIN_BRS_M_MASK                          (0x0F000000u)
#define LIN_BRS_M_SHIFT                         (24u)
#define LIN_BRS_PRESCALER_P_MASK                (0x00FFFFFFu)
#define LIN_BRS_PRESCALER_P_SHIFT               (0u)

/*==============================================================================
                        SCIED - Receiver Emulation Data Buffer
==============================================================================*/
#define LIN_SCIED_ED_MASK                       (0x000000FFu)

/*==============================================================================
                        SCIRD - Receiver Data Buffer
==============================================================================*/
#define LIN_SCIRD_RD_MASK                       (0x000000FFu)

/*==============================================================================
                        SCITD - Transmit Data Buffer
==============================================================================*/
#define LIN_SCITD_TD_MASK                       (0x000000FFu)

/*==============================================================================
                        SCIPIO0 - SCI Pin I/O Control Register 0
==============================================================================*/
#define LIN_SCIPIO0_TX_FUNC                     (0x00000004u)
#define LIN_SCIPIO0_RX_FUNC                     (0x00000002u)

/*==============================================================================
                        LINMASK - LIN Mask Register
==============================================================================*/
#define LIN_LINMASK_TX_ID_MASK_MASK             (0x00FF0000u)
#define LIN_LINMASK_TX_ID_MASK_SHIFT            (16u)
#define LIN_LINMASK_RX_ID_MASK_MASK             (0x000000FFu)
#define LIN_LINMASK_RX_ID_MASK_SHIFT            (0u)

/*==============================================================================
                        LINID - LIN Identification Register
==============================================================================*/
#define LIN_LINID_RECEIVED_ID_MASK              (0x00FF0000u)
#define LIN_LINID_RECEIVED_ID_SHIFT             (16u)
#define LIN_LINID_ID_SLAVETASK_BYTE_MASK        (0x000000FFu)
#define LIN_LINID_ID_SLAVETASK_BYTE_SHIFT       (0u)
#define LIN_LINID_IDBYTE_MASK                   (0x000000FFu)
#define LIN_LINID_IDBYTE_SHIFT                  (0u)

/*==============================================================================
                        LINTD0 - LIN Transmit Buffer 0
==============================================================================*/
#define LIN_LINTD0_TD0_MASK                     (0xFF000000u)
#define LIN_LINTD0_TD0_SHIFT                    (24u)

#endif /* REG_LIN_H */
