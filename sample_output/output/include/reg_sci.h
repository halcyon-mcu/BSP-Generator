/* BSP-GEN-META: created_at=2026-03-04T23:24:58-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file reg_sci.h
 * @brief SCI (Serial Communication Interface) Register Map Header File
 * @details This file contains the register map structure and bit field definitions
 *          for the SCI/LIN peripheral module.
 *
 * Base Address: 0xFFF7E400
 * Module: Serial Communication Interface (SCI) / Local Interconnect Network (LIN) Module
 */

#ifndef REG_SCI_H
#define REG_SCI_H

#include <stdint.h>

/**
 * @brief SCI Register Map Structure
 * @note All registers are 32-bit wide and must be accessed as volatile
 */
typedef struct {
    volatile uint32_t SCIGCR0;          /**< 0x00 - SCI Global Control Register 0 */
    volatile uint32_t SCIGCR1;          /**< 0x04 - SCI Global Control Register 1 */
    volatile uint32_t RESERVED0[1];     /**< 0x08 - Reserved */
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
    volatile uint32_t SCITD;            /**< 0x38 - Transmit Data Buffer Register */
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
    volatile uint32_t RESERVED1[4];     /**< 0x80-0x8C - Reserved */
    volatile uint32_t IODFTCTRL;        /**< 0x90 - Input/Output Error Enable Register */
} SCI_REG_MAP_t;

/* ========================================================================== */
/*                          SCIGCR0 - SCI Global Control Register 0          */
/* ========================================================================== */
#define SCI_SCIGCR0_RESET                   (0x00000001u)  /**< SCI module reset - 0=in reset, 1=out of reset */

/* ========================================================================== */
/*                          SCIGCR1 - SCI Global Control Register 1          */
/* ========================================================================== */
#define SCI_SCIGCR1_TXENA                   (0x02000000u)  /**< Transmit enable - 0=disable, 1=enable */
#define SCI_SCIGCR1_RXENA                   (0x01000000u)  /**< Receive enable - 0=disable, 1=enable */
#define SCI_SCIGCR1_CONT                    (0x00020000u)  /**< Continue on suspend - 0=halt on debug, 1=continue */
#define SCI_SCIGCR1_LOOP_BACK               (0x00010000u)  /**< Loopback mode - 0=disabled, 1=enabled */
#define SCI_SCIGCR1_POWERDOWN               (0x00000200u)  /**< Power down mode - 0=normal, 1=low-power */
#define SCI_SCIGCR1_SLEEP                   (0x00000100u)  /**< SCI sleep mode - 0=disabled, 1=enabled */
#define SCI_SCIGCR1_SWnRST                  (0x00000080u)  /**< Software reset (active low) */
#define SCI_SCIGCR1_CLOCK                   (0x00000020u)  /**< SCI internal clock enable */
#define SCI_SCIGCR1_STOP                    (0x00000010u)  /**< Number of stop bits - 0=one, 1=two */
#define SCI_SCIGCR1_PARITY                  (0x00000008u)  /**< Parity odd/even - 0=odd, 1=even */
#define SCI_SCIGCR1_PARITY_ENA              (0x00000004u)  /**< Parity enable - 0=disabled, 1=enabled */
#define SCI_SCIGCR1_TIMING_MODE             (0x00000002u)  /**< SCI timing mode - 0=sync, 1=async */
#define SCI_SCIGCR1_COMM_MODE               (0x00000001u)  /**< SCI communication mode - 0=idle-line, 1=address-bit */

/* ========================================================================== */
/*                      SCISETINT - SCI Set Interrupt Register                */
/* ========================================================================== */
#define SCI_SCISETINT_SET_FE_INT            (0x04000000u)  /**< Set framing-error interrupt */
#define SCI_SCISETINT_SET_OE_INT            (0x02000000u)  /**< Set overrun-error interrupt */
#define SCI_SCISETINT_SET_PE_INT            (0x01000000u)  /**< Set parity error interrupt */
#define SCI_SCISETINT_SET_RX_DMA_ALL        (0x00040000u)  /**< Set receive DMA for all frames */
#define SCI_SCISETINT_SET_RX_DMA            (0x00020000u)  /**< Set receiver DMA */
#define SCI_SCISETINT_SET_TX_DMA            (0x00010000u)  /**< Set transmit DMA */
#define SCI_SCISETINT_SET_RX_INT            (0x00000200u)  /**< Receiver interrupt enable */
#define SCI_SCISETINT_SET_TX_INT            (0x00000100u)  /**< Transmitter interrupt enable */
#define SCI_SCISETINT_SET_WAKEUP_INT        (0x00000002u)  /**< Set wakeup interrupt */
#define SCI_SCISETINT_SET_BRKDT_INT         (0x00000001u)  /**< Set break detect interrupt */

/* ========================================================================== */
/*                   SCICLEARINT - SCI Clear Interrupt Register               */
/* ========================================================================== */
#define SCI_SCICLEARINT_CLR_FE_INT          (0x04000000u)  /**< Clear framing-error interrupt */
#define SCI_SCICLEARINT_CLR_OE_INT          (0x02000000u)  /**< Clear overrun-error interrupt */
#define SCI_SCICLEARINT_CLR_PE_INT          (0x01000000u)  /**< Clear parity error interrupt */
#define SCI_SCICLEARINT_CLR_RX_DMA_ALL      (0x00040000u)  /**< Clear receive DMA all */
#define SCI_SCICLEARINT_CLR_RX_DMA          (0x00020000u)  /**< Clear receive DMA request */
#define SCI_SCICLEARINT_CLR_TX_DMA          (0x00010000u)  /**< Clear transmit DMA request */
#define SCI_SCICLEARINT_CLR_RX_INT          (0x00000200u)  /**< Clear receiver interrupt */
#define SCI_SCICLEARINT_CLR_TX_INT          (0x00000100u)  /**< Clear transmitter interrupt */
#define SCI_SCICLEARINT_CLR_WAKEUP_INT      (0x00000002u)  /**< Clear wakeup interrupt */
#define SCI_SCICLEARINT_CLR_BRKDT_INT       (0x00000001u)  /**< Clear break detect interrupt */

/* ========================================================================== */
/*                 SCISETINTLVL - SCI Set Interrupt Level Register            */
/* ========================================================================== */
#define SCI_SCISETINTLVL_SET_FE_INT_LVL     (0x04000000u)  /**< Set framing-error interrupt level */
#define SCI_SCISETINTLVL_SET_OE_INT_LVL     (0x02000000u)  /**< Set overrun-error interrupt level */
#define SCI_SCISETINTLVL_SET_PE_INT_LVL     (0x01000000u)  /**< Set parity error interrupt level */
#define SCI_SCISETINTLVL_SET_RX_DMA_ALL_LVL (0x00040000u)  /**< Set receive DMA all interrupt level */
#define SCI_SCISETINTLVL_SET_RX_INT_LVL     (0x00000200u)  /**< Set receiver interrupt level */
#define SCI_SCISETINTLVL_SET_TX_INT_LVL     (0x00000100u)  /**< Set transmitter interrupt level */
#define SCI_SCISETINTLVL_SET_WAKEUP_INT_LVL (0x00000002u)  /**< Set wakeup interrupt level */
#define SCI_SCISETINTLVL_SET_BRKDT_INT_LVL  (0x00000001u)  /**< Set break detect interrupt level */

/* ========================================================================== */
/*              SCICLEARINTLVL - SCI Clear Interrupt Level Register           */
/* ========================================================================== */
#define SCI_SCICLEARINTLVL_CLR_FE_INT_LVL     (0x04000000u)  /**< Clear framing-error interrupt level */
#define SCI_SCICLEARINTLVL_CLR_OE_INT_LVL     (0x02000000u)  /**< Clear overrun-error interrupt level */
#define SCI_SCICLEARINTLVL_CLR_PE_INT_LVL     (0x01000000u)  /**< Clear parity error interrupt level */
#define SCI_SCICLEARINTLVL_CLR_RX_DMA_ALL_LVL (0x00040000u)  /**< Clear receive DMA all interrupt level */
#define SCI_SCICLEARINTLVL_CLR_RX_INT_LVL     (0x00000200u)  /**< Clear receiver interrupt level */
#define SCI_SCICLEARINTLVL_CLR_TX_INT_LVL     (0x00000100u)  /**< Clear transmitter interrupt level */
#define SCI_SCICLEARINTLVL_CLR_WAKEUP_INT_LVL (0x00000002u)  /**< Clear wakeup interrupt level */
#define SCI_SCICLEARINTLVL_CLR_BRKDT_INT_LVL  (0x00000001u)  /**< Clear break detect interrupt level */

/* ========================================================================== */
/*                          SCIFLR - SCI Flags Register                       */
/* ========================================================================== */
#define SCI_SCIFLR_FE                       (0x04000000u)  /**< Framing error flag */
#define SCI_SCIFLR_OE                       (0x02000000u)  /**< Overrun error flag */
#define SCI_SCIFLR_PE                       (0x01000000u)  /**< Parity error flag */
#define SCI_SCIFLR_RXWAKE                   (0x00001000u)  /**< Receiver wakeup detect flag */
#define SCI_SCIFLR_TX_EMPTY                 (0x00000800u)  /**< Transmitter empty flag */
#define SCI_SCIFLR_TXWAKE                   (0x00000400u)  /**< Transmitter wakeup method select */
#define SCI_SCIFLR_RXRDY                    (0x00000200u)  /**< Receiver ready flag */
#define SCI_SCIFLR_TXRDY                    (0x00000100u)  /**< Transmitter buffer register ready */
#define SCI_SCIFLR_BUSY                     (0x00000008u)  /**< Bus busy flag */
#define SCI_SCIFLR_IDLE                     (0x00000004u)  /**< SCI receiver in idle state */
#define SCI_SCIFLR_WAKEUP                   (0x00000002u)  /**< Wakeup flag */
#define SCI_SCIFLR_BRKDT                    (0x00000001u)  /**< Break detect flag */

/* ========================================================================== */
/*                 SCIINTVECT0 - SCI Interrupt Vector Offset 0                */
/* ========================================================================== */
#define SCI_SCIINTVECT0_INTVECT0_MASK       (0x0000000Fu)  /**< Interrupt vector offset for INT0 line */

/* ========================================================================== */
/*                 SCIINTVECT1 - SCI Interrupt Vector Offset 1                */
/* ========================================================================== */
#define SCI_SCIINTVECT1_INTVECT1_MASK       (0x0000000Fu)  /**< Interrupt vector offset for INT1 line */

/* ========================================================================== */
/*                   SCIFORMAT - SCI Format Control Register                  */
/* ========================================================================== */
#define SCI_SCIFORMAT_CHAR_MASK             (0x00000007u)  /**< Character length control - 0=1 bit, 7=8 bits */

/* ========================================================================== */
/*                      BRS - Baud Rate Selection Register                    */
/* ========================================================================== */
#define SCI_BRS_BAUD_MASK                   (0x00FFFFFFu)  /**< 24-bit baud rate prescaler value */

/* ========================================================================== */
/*                     SCIED - Receiver Emulation Data Buffer                 */
/* ========================================================================== */
#define SCI_SCIED_ED_MASK                   (0x000000FFu)  /**< Emulator data */

/* ========================================================================== */
/*                        SCIRD - Receiver Data Buffer                        */
/* ========================================================================== */
#define SCI_SCIRD_RD_MASK                   (0x000000FFu)  /**< Receiver data */

/* ========================================================================== */
/*                    SCITD - Transmit Data Buffer Register                   */
/* ========================================================================== */
#define SCI_SCITD_TD_MASK                   (0x000000FFu)  /**< Transmit data */

/* ========================================================================== */
/*                  SCIPIO0 - SCI Pin I/O Control Register 0                  */
/* ========================================================================== */
#define SCI_SCIPIO0_TX_FUNC                 (0x00000004u)  /**< SCITX pin function - 0=GPIO, 1=SCI transmit */
#define SCI_SCIPIO0_RX_FUNC                 (0x00000002u)  /**< SCIRX pin function - 0=GPIO, 1=SCI receive */

/* ========================================================================== */
/*                  SCIPIO1 - SCI Pin I/O Control Register 1                  */
/* ========================================================================== */
#define SCI_SCIPIO1_TX_DIR                  (0x00000004u)  /**< SCITX pin direction - 0=input, 1=output */
#define SCI_SCIPIO1_RX_DIR                  (0x00000002u)  /**< SCIRX pin direction - 0=input, 1=output */

/* ========================================================================== */
/*                  SCIPIO2 - SCI Pin I/O Control Register 2                  */
/* ========================================================================== */
#define SCI_SCIPIO2_TX_IN                   (0x00000004u)  /**< SCITX pin input value */
#define SCI_SCIPIO2_RX_IN                   (0x00000002u)  /**< SCIRX pin input value */

/* ========================================================================== */
/*                  SCIPIO3 - SCI Pin I/O Control Register 3                  */
/* ========================================================================== */
#define SCI_SCIPIO3_TX_OUT                  (0x00000004u)  /**< SCITX pin output value */
#define SCI_SCIPIO3_RX_OUT                  (0x00000002u)  /**< SCIRX pin output value */

/* ========================================================================== */
/*                  SCIPIO4 - SCI Pin I/O Control Register 4                  */
/* ========================================================================== */
#define SCI_SCIPIO4_TX_SET                  (0x00000004u)  /**< SCITX pin set - write 1 to set output high */
#define SCI_SCIPIO4_RX_SET                  (0x00000002u)  /**< SCIRX pin set - write 1 to set output high */

/* ========================================================================== */
/*                  SCIPIO5 - SCI Pin I/O Control Register 5                  */
/* ========================================================================== */
#define SCI_SCIPIO5_TX_CLR                  (0x00000004u)  /**< SCITX pin clear - write 1 to set output low */
#define SCI_SCIPIO5_RX_CLR                  (0x00000002u)  /**< SCIRX pin clear - write 1 to set output low */

/* ========================================================================== */
/*                  SCIPIO6 - SCI Pin I/O Control Register 6                  */
/* ========================================================================== */
#define SCI_SCIPIO6_TX_PDR                  (0x00000004u)  /**< SCITX pin open drain enable - 1=open drain */
#define SCI_SCIPIO6_RX_PDR                  (0x00000002u)  /**< SCIRX pin open drain enable - 1=open drain */

/* ========================================================================== */
/*                  SCIPIO7 - SCI Pin I/O Control Register 7                  */
/* ========================================================================== */
#define SCI_SCIPIO7_TX_PD                   (0x00000004u)  /**< SCITX pin pull control disable - 0=enabled, 1=disabled */
#define SCI_SCIPIO7_RX_PD                   (0x00000002u)  /**< SCIRX pin pull control disable - 0=enabled, 1=disabled */

/* ========================================================================== */
/*                  SCIPIO8 - SCI Pin I/O Control Register 8                  */
/* ========================================================================== */
#define SCI_SCIPIO8_TX_PSL                  (0x00000004u)  /**< SCITX pin pull select - 0=pull down, 1=pull up */
#define SCI_SCIPIO8_RX_PSL                  (0x00000002u)  /**< SCIRX pin pull select - 0=pull down, 1=pull up */

/* ========================================================================== */
/*                 IODFTCTRL - Input/Output Error Enable Register             */
/* ========================================================================== */
#define SCI_IODFTCTRL_FEN                   (0x04000000u)  /**< Frame error enable - 1=create frame error */
#define SCI_IODFTCTRL_PEN                   (0x02000000u)  /**< Parity error enable - 1=create parity error */
#define SCI_IODFTCTRL_BRKDTENA              (0x01000000u)  /**< Break detect error enable - 1=create BRKDT error */
#define SCI_IODFTCTRL_PIN_SAMPLE_MASK_MASK  (0x00180000u)  /**< Pin sample mask */
#define SCI_IODFTCTRL_PIN_SAMPLE_MASK_SHIFT (19u)
#define SCI_IODFTCTRL_TX_SHIFT_MASK         (0x00070000u)  /**< Transmit shift - delay TX pin value by 0-6 SCLK */
#define SCI_IODFTCTRL_TX_SHIFT_SHIFT        (16u)
#define SCI_IODFTCTRL_IODFTENA_MASK         (0x00000F00u)  /**< IODFT enable key - 0xA=enabled */
#define SCI_IODFTCTRL_IODFTENA_SHIFT        (8u)
#define SCI_IODFTCTRL_IODFTENA_ENABLE       (0x00000A00u)  /**< IODFT enable value */
#define SCI_IODFTCTRL_LPBENA                (0x00000002u)  /**< Module loopback enable - 0=digital, 1=analog */
#define SCI_IODFTCTRL_RXPENA                (0x00000001u)  /**< Module analog loopback through receive pin */

/* ========================================================================== */
/*                   LINCOMPARE - LIN Compare Register                        */
/* ========================================================================== */
#define SCI_LINCOMPARE_SBREAK_MASK          (0x0000E000u)  /**< Synch break extend. 0-7 = 13-20 bits */
#define SCI_LINCOMPARE_SBREAK_SHIFT         (13u)
#define SCI_LINCOMPARE_SDEL_MASK            (0x00000300u)  /**< Synch delimiter. 0-3 = 1-4 bits */
#define SCI_LINCOMPARE_SDEL_SHIFT           (8u)

/* ========================================================================== */
/*                   LINRD0 - LIN Receive Buffer 0 Register                   */
/* ========================================================================== */
#define SCI_LINRD0_RD3_MASK                 (0xFF000000u)  /**< Receive data byte 3 */
#define SCI_LINRD0_RD3_SHIFT                (24u)
#define SCI_LINRD0_RD2_MASK                 (0x00FF0000u)  /**< Receive data byte 2 */
#define SCI_LINRD0_RD2_SHIFT                (16u)
#define SCI_LINRD0_RD1_MASK                 (0x0000FF00u)  /**< Receive data byte 1 */
#define SCI_LINRD0_RD1_SHIFT                (8u)
#define SCI_LINRD0_RD0_MASK                 (0x000000FFu)  /**< Receive data byte 0 */
#define SCI_LINRD0_RD0_SHIFT                (0u)

/* ========================================================================== */
/*                   LINRD1 - LIN Receive Buffer 1 Register                   */
/* ========================================================================== */
#define SCI_LINRD1_RD7_MASK                 (0xFF000000u)  /**< Receive data byte 7 */
#define SCI_LINRD1_RD7_SHIFT                (24u)
#define SCI_LINRD1_RD6_MASK                 (0x00FF0000u)  /**< Receive data byte 6 */
#define SCI_LINRD1_RD6_SHIFT                (16u)
#define SCI_LINRD1_RD5_MASK                 (0x0000FF00u)  /**< Receive data byte 5 */
#define SCI_LINRD1_RD5_SHIFT                (8u)
#define SCI_LINRD1_RD4_MASK                 (0x000000FFu)  /**< Receive data byte 4 */
#define SCI_LINRD1_RD4_SHIFT                (0u)

/* ========================================================================== */
/*                      LINMASK - LIN Mask Register                           */
/* ========================================================================== */
#define SCI_LINMASK_TX_ID_MASK_MASK         (0x0000FF00u)  /**< Transmit ID mask. Bits to filter for TX match */
#define SCI_LINMASK_TX_ID_MASK_SHIFT        (8u)
#define SCI_LINMASK_RX_ID_MASK_MASK         (0x000000FFu)  /**< Receive ID mask. Bits to filter for RX match */
#define SCI_LINMASK_RX_ID_MASK_SHIFT        (0u)

/* ========================================================================== */
/*                  LINID - LIN Identification Register                       */
/* ========================================================================== */
#define SCI_LINID_RECEIVED_ID_MASK          (0x00FF0000u)  /**< Received identifier byte */
#define SCI_LINID_RECEIVED_ID_SHIFT         (16u)
#define SCI_LINID_ID_BYTE_MASK              (0x000000FFu)  /**< ID byte for comparison or transmission */
#define SCI_LINID_ID_BYTE_SHIFT             (0u)

/* ========================================================================== */
/*                   LINTD0 - LIN Transmit Buffer 0                           */
/* ========================================================================== */
#define SCI_LINTD0_TD3_MASK                 (0xFF000000u)  /**< Transmit data byte 3 */
#define SCI_LINTD0_TD3_SHIFT                (24u)
#define SCI_LINTD0_TD2_MASK                 (0x00FF0000u)  /**< Transmit data byte 2 */
#define SCI_LINTD0_TD2_SHIFT                (16u)
#define SCI_LINTD0_TD1_MASK                 (0x0000FF00u)  /**< Transmit data byte 1 */
#define SCI_LINTD0_TD1_SHIFT                (8u)
#define SCI_LINTD0_TD0_MASK                 (0x000000FFu)  /**< Transmit data byte 0 */
#define SCI_LINTD0_TD0_SHIFT                (0u)

/* ========================================================================== */
/*                   LINTD1 - LIN Transmit Buffer 1                           */
/* ========================================================================== */
#define SCI_LINTD1_TD7_MASK                 (0xFF000000u)  /**< Transmit data byte 7 */
#define SCI_LINTD1_TD7_SHIFT                (24u)
#define SCI_LINTD1_TD6_MASK                 (0x00FF0000u)  /**< Transmit data byte 6 */
#define SCI_LINTD1_TD6_SHIFT                (16u)
#define SCI_LINTD1_TD5_MASK                 (0x0000FF00u)  /**< Transmit data byte 5 */
#define SCI_LINTD1_TD5_SHIFT                (8u)
#define SCI_LINTD1_TD4_MASK                 (0x000000FFu)  /**< Transmit data byte 4 */
#define SCI_LINTD1_TD4_SHIFT                (0u)

/* ========================================================================== */
/*              MBRS - Maximum Baud Rate Selection Register                   */
/* ========================================================================== */
#define SCI_MBRS_MBR_MASK                   (0x00001FFFu)  /**< Maximum baud rate prescaler value */

#endif /* REG_SCI_H */
