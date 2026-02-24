/**
 * @file sci_mock.h
 * @brief Mock hardware register definitions for SCI (UART) testing
 */

#ifndef SCI_MOCK_H
#define SCI_MOCK_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/* ============================================================================
 * Mock SCI Register Structure
 * ========================================================================== */

typedef struct
{
    uint32_t GCR;         /*!< Global Control Register */
    uint32_t SETINT;      /*!< Set Interrupt Register */
    uint32_t CLEARINT;    /*!< Clear Interrupt Register */
    uint32_t SETINTLVL;   /*!< Set Interrupt Level Register */
    uint32_t CLEARINTLVL; /*!< Clear Interrupt Level Register */
    uint32_t FLR;         /*!< Flag Register */
    uint32_t INTVECT0;    /*!< Interrupt Vector 0 */
    uint32_t INTVECT1;    /*!< Interrupt Vector 1 */

    uint32_t BRR;   /*!< Baud Rate Register */
    uint32_t CCR;   /*!< Clock Control Register */
    uint32_t FBAUD; /*!< Fractional Baud Rate Register */
    uint32_t RESERVED1;

    uint32_t SCIRX; /*!< Serial Control Interface RX */
    uint32_t SCITX; /*!< Serial Control Interface TX */

    uint32_t FORMAT;     /*!< Format Control Register */
    uint32_t BRS;        /*!< Baud Rate Selection Register */
    uint32_t SCIMAXBAUD; /*!< SCI Maximum Baud Rate */
    uint32_t RESERVED2;
    uint32_t RESERVED3;

    /* RD register */
    uint32_t RD; /*!< Receiver Data Register */

    /* Transmitter buffers (ring buffer simulation) */
    uint32_t TX_BUFFER[16];
    uint32_t tx_head;
    uint32_t tx_tail;
    uint32_t tx_count;

    /* Receiver buffers (ring buffer simulation) */
    uint32_t RX_BUFFER[16];
    uint32_t rx_head;
    uint32_t rx_tail;
    uint32_t rx_count;

} sci_mock_registers_t;

extern sci_mock_registers_t sci_mock_regs;

/* ============================================================================
 * Mock Helper Functions
 * ========================================================================== */

void sci_mock_init(void);
void sci_mock_reset(void);

/**
 * @brief Transmit a character
 */
bool sci_mock_transmit(uint8_t data);

/**
 * @brief Receive a character
 */
bool sci_mock_receive(uint8_t *data);

/**
 * @brief Check if transmit buffer is empty
 */
bool sci_mock_tx_empty(void);

/**
 * @brief Check if receive buffer has data
 */
bool sci_mock_rx_ready(void);

/**
 * @brief Get TX buffer count
 */
uint32_t sci_mock_get_tx_count(void);

/**
 * @brief Get RX buffer count
 */
uint32_t sci_mock_get_rx_count(void);

/**
 * @brief Simulate receiving data from hardware
 */
void sci_mock_receive_from_hardware(uint8_t data);

#endif /* SCI_MOCK_H */
