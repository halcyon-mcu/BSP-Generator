/**
 * @file sci.h
 * @brief Serial Communication Interface (SCI) / Local Interconnect Network (LIN) driver for TI RM46
 */

#ifndef SCI_H
#define SCI_H

#include <stdint.h>

/**
 * @defgroup BSP_SCI Serial Communication Interface (SCI/LIN)
 * @brief Low-level driver for the RM46 SCI/LIN module.
 * 
 * This module provides:
 * - SCI (UART) and LIN protocol support
 * - Blocking transmit and receive APIs with timeout
 * - Interrupt registration for level 0 and level 1 interrupts
 * - Baud rate configuration
 * - Loopback / self-test support
 * @{
 */

/**
 * @brief SCI error flags
 */
typedef enum {
    SCI_ERR_NONE     = 0x00u, /**< No error */
    SCI_ERR_FRAMING  = 0x01u, /**< Framing error */
    SCI_ERR_OVERRUN  = 0x02u, /**< Overrun error */
    SCI_ERR_PARITY   = 0x04u, /**< Parity error */
    SCI_ERR_TIMEOUT  = 0x08u  /**< Timeout error */
} sci_error_t;

/**
 * @brief SCI frame configuration
 */
typedef struct {
    uint8_t char_length; /**< Character length (1-8 bits) */
    uint8_t stop_bits;   /**< Stop bits: 0 = 1 stop bit, 1 = 2 stop bits */
    uint8_t parity_en;   /**< Parity enable: 0 = disabled, 1 = enabled */
    uint8_t parity_odd;  /**< Parity type: 0 = even, 1 = odd */
} sci_frame_config_t;

/**
 * @brief SCI ISR callback type
 */
typedef void (*sci_isr_t)(void);

/**
 * @brief Initialize the SCI module
 * @ingroup BSP_SCI
 * 
 * Enables the VCLK clock, brings the SCI out of reset, configures pin functions,
 * and enables transmit and receive. This function must be called before any other
 * SCI operations.
 * 
 * @note This function does NOT configure baud rate or frame format. Use sci_configure_baud()
 *       and sci_configure_frame() after initialization.
 */
void sci_init(void);

/**
 * @brief Configure the SCI baud rate
 * @ingroup BSP_SCI
 * 
 * Computes and sets the baud rate divisor from the current VCLK frequency.
 * Assumes SCI module is out of reset and SWnRST bit is clear during configuration.
 * 
 * @param[in] baud_rate Desired baud rate in bits per second
 * 
 * @note Must be called after sci_init() and before enabling transmit/receive.
 * @warning Re-enters reset during configuration (clears SWnRST), then restores it.
 */
void sci_configure_baud(uint32_t baud_rate);

/**
 * @brief Configure the SCI frame format
 * @ingroup BSP_SCI
 * 
 * Sets character length, stop bits, parity enable, and parity type.
 * 
 * @param[in] config Pointer to frame configuration structure
 * 
 * @return 0 on success, -1 if config is NULL or parameters are invalid
 * 
 * @note Must be called after sci_init().
 */
int sci_configure_frame(const sci_frame_config_t *config);

/**
 * @brief Transmit a single byte (blocking with timeout)
 * @ingroup BSP_SCI
 * 
 * Waits for the transmit buffer (TXRDY flag) to become ready, writes the byte,
 * then waits for the transmitter to become empty (TX_EMPTY flag).
 * 
 * @param[in] data Byte to transmit
 * @param[in] timeout_cycles Maximum polling iterations before timeout
 * 
 * @return 0 on success, SCI_ERR_TIMEOUT if transmit buffer or empty flag times out
 * 
 * @note Blocking call. Not IRQ-safe.
 */
int sci_transmit_byte(uint8_t data, uint32_t timeout_cycles);

/**
 * @brief Receive a single byte (blocking with timeout)
 * @ingroup BSP_SCI
 * 
 * Polls the RXRDY flag until a byte is ready, then reads it from the receive buffer.
 * Checks and clears any error flags (framing, overrun, parity).
 * 
 * @param[out] data Pointer to store received byte
 * @param[in] timeout_cycles Maximum polling iterations before timeout
 * 
 * @return SCI_ERR_NONE on success, or bitwise OR of error flags (SCI_ERR_FRAMING, etc.)
 * 
 * @note Blocking call. Not IRQ-safe.
 */
int sci_receive_byte(uint8_t *data, uint32_t timeout_cycles);

/**
 * @brief Enable loopback mode
 * @ingroup BSP_SCI
 * 
 * Enables internal digital loopback for self-test. Transmitted data is routed directly
 * to the receiver without external pin activity.
 * 
 * @note Module must be in reset (SWnRST cleared) before calling this function.
 */
void sci_enable_loopback(void);

/**
 * @brief Disable loopback mode
 * @ingroup BSP_SCI
 * 
 * Disables internal loopback, restoring normal pin operation.
 */
void sci_disable_loopback(void);

/**
 * @brief Enable analog loopback through receive pin
 * @ingroup BSP_SCI
 * 
 * Routes TX output to RX input through the physical pin for external loopback testing.
 * 
 * @note Requires IODFT enable key to be set.
 */
void sci_enable_analog_loopback(void);

/**
 * @brief Disable analog loopback through receive pin
 * @ingroup BSP_SCI
 */
void sci_disable_analog_loopback(void);

/**
 * @brief Run a simple loopback self-test
 * @ingroup BSP_SCI
 * 
 * Enables internal digital loopback, transmits a test byte, receives it,
 * and verifies the result. Restores the original loopback state.
 * 
 * @return 0 on success, non-zero on mismatch or timeout
 * 
 * @note Module must be initialized and configured before calling.
 * @warning This function temporarily places the module in reset.
 */
int sci_self_test(void);

/**
 * @brief Register an ISR for SCI level 0 interrupt
 * @ingroup BSP_SCI
 * 
 * Registers a user-provided ISR for the SCI level 0 interrupt channel.
 * 
 * @param[in] isr Function pointer to the interrupt handler
 * 
 * @return 0 on success, non-zero on VIM registration failure
 */
int sci_register_isr_lvl0(sci_isr_t isr);

/**
 * @brief Register an ISR for SCI level 1 interrupt
 * @ingroup BSP_SCI
 * 
 * Registers a user-provided ISR for the SCI level 1 interrupt channel.
 * 
 * @param[in] isr Function pointer to the interrupt handler
 * 
 * @return 0 on success, non-zero on VIM registration failure
 */
int sci_register_isr_lvl1(sci_isr_t isr);

/**
 * @brief Enable SCI level 0 interrupt channel
 * @ingroup BSP_SCI
 * 
 * Enables the VIM channel for SCI level 0 interrupts.
 * 
 * @return 0 on success, non-zero on VIM enable failure
 */
int sci_enable_irq_lvl0(void);

/**
 * @brief Enable SCI level 1 interrupt channel
 * @ingroup BSP_SCI
 * 
 * Enables the VIM channel for SCI level 1 interrupts.
 * 
 * @return 0 on success, non-zero on VIM enable failure
 */
int sci_enable_irq_lvl1(void);

/**
 * @brief Disable SCI level 0 interrupt channel
 * @ingroup BSP_SCI
 * 
 * Disables the VIM channel for SCI level 0 interrupts.
 * 
 * @return 0 on success, non-zero on VIM disable failure
 */
int sci_disable_irq_lvl0(void);

/**
 * @brief Disable SCI level 1 interrupt channel
 * @ingroup BSP_SCI
 * 
 * Disables the VIM channel for SCI level 1 interrupts.
 * 
 * @return 0 on success, non-zero on VIM disable failure
 */
int sci_disable_irq_lvl1(void);

/**
 * @brief Enable receive interrupt at level 0
 * @ingroup BSP_SCI
 * 
 * Routes the RX interrupt to level 0 and enables it.
 */
void sci_enable_rx_interrupt_lvl0(void);

/**
 * @brief Enable transmit interrupt at level 0
 * @ingroup BSP_SCI
 * 
 * Routes the TX interrupt to level 0 and enables it.
 */
void sci_enable_tx_interrupt_lvl0(void);

/**
 * @brief Enable receive interrupt at level 1
 * @ingroup BSP_SCI
 * 
 * Routes the RX interrupt to level 1 and enables it.
 */
void sci_enable_rx_interrupt_lvl1(void);

/**
 * @brief Enable transmit interrupt at level 1
 * @ingroup BSP_SCI
 * 
 * Routes the TX interrupt to level 1 and enables it.
 */
void sci_enable_tx_interrupt_lvl1(void);

/**
 * @brief Disable receive interrupt
 * @ingroup BSP_SCI
 * 
 * Clears the RX interrupt enable and level bits.
 */
void sci_disable_rx_interrupt(void);

/**
 * @brief Disable transmit interrupt
 * @ingroup BSP_SCI
 * 
 * Clears the TX interrupt enable and level bits.
 */
void sci_disable_tx_interrupt(void);

/**
 * @brief Check if receiver is ready
 * @ingroup BSP_SCI
 * 
 * @return Non-zero if RXRDY flag is set, 0 otherwise
 */
int sci_is_rx_ready(void);

/**
 * @brief Check if transmitter is ready
 * @ingroup BSP_SCI
 * 
 * @return Non-zero if TXRDY flag is set, 0 otherwise
 */
int sci_is_tx_ready(void);

/**
 * @brief Check if transmitter is empty
 * @ingroup BSP_SCI
 * 
 * @return Non-zero if TX_EMPTY flag is set, 0 otherwise
 */
int sci_is_tx_empty(void);

/**
 * @brief Read and clear error flags
 * @ingroup BSP_SCI
 * 
 * Reads the current error flags (framing, overrun, parity) and clears them.
 * 
 * @return Bitwise OR of active error flags (SCI_ERR_FRAMING | SCI_ERR_OVERRUN | SCI_ERR_PARITY)
 */
int sci_get_and_clear_errors(void);

/** @} */ /* end of BSP_SCI */

#endif /* SCI_H */
