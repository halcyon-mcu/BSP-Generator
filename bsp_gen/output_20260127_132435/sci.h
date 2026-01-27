/**
 * @file sci.h
 * @brief Serial Communication Interface (SCI) / LIN driver for TI RM46
 */

#ifndef SCI_H
#define SCI_H

#include <stdint.h>

/**
 * @defgroup BSP_SCI Serial Communication Interface (SCI/LIN)
 * @brief SCI/LIN peripheral driver for UART and LIN communication.
 * @{
 */

/**
 * @brief SCI interrupt service routine callback type.
 */
typedef void (*sci_isr_t)(void);

/**
 * @brief SCI error flags bitfield.
 */
typedef enum {
    SCI_ERROR_NONE      = 0x00u,      /**< No error. */
    SCI_ERROR_PARITY    = (1u << 24), /**< Parity error. */
    SCI_ERROR_OVERRUN   = (1u << 25), /**< Overrun error. */
    SCI_ERROR_FRAME     = (1u << 26)  /**< Frame error. */
} sci_error_t;

/**
 * @brief Initialize the SCI module.
 * @ingroup BSP_SCI
 *
 * Enables the VCLK clock and performs the multi-step hardware initialization
 * sequence (reset, configure pins, enable RX/TX).
 *
 * @note Must be called before any other SCI functions.
 */
void sci_init(void);

/**
 * @brief Configure SCI baud rate using raw BRS fields.
 * @ingroup BSP_SCI
 *
 * @param u Super fractional divider (3 bits).
 * @param m Fractional divider (4 bits).
 * @param p Prescaler (24 bits).
 *
 * @note Baud rate = VCLK / ((M+1) * P * 2^U). Typical baud: 115200, 9600, etc.
 */
void sci_set_baud_raw(uint32_t u, uint32_t m, uint32_t p);

/**
 * @brief Configure SCI baud rate from a target baud value and VCLK frequency.
 * @ingroup BSP_SCI
 *
 * Computes BRS register fields to achieve the closest baud rate.
 *
 * @param target_baud Desired baud rate in bits per second.
 * @param vclk_hz VCLK frequency in Hz (use clock_get_hz(CLOCKREF_VCLK)).
 *
 * @return 0 on success, -1 if baud rate is out of range.
 */
int sci_set_baud(uint32_t target_baud, uint32_t vclk_hz);

/**
 * @brief Configure SCI frame format.
 * @ingroup BSP_SCI
 *
 * @param char_len Character length (0=1 bit, 7=8 bits).
 * @param stop_bits Stop bits (0=1 stop bit, 1=2 stop bits).
 * @param parity_enable Enable parity (0=disabled, 1=enabled).
 * @param parity_odd Parity type (0=even, 1=odd). Ignored if parity_enable=0.
 */
void sci_set_format(uint32_t char_len, uint32_t stop_bits, uint32_t parity_enable, uint32_t parity_odd);

/**
 * @brief Read the SCI flags register (errors, RX/TX ready, etc.).
 * @ingroup BSP_SCI
 *
 * @return Current SCIFLR register value.
 */
uint32_t sci_get_flags(void);

/**
 * @brief Clear specified error flags in SCIFLR.
 * @ingroup BSP_SCI
 *
 * @param flags Mask of flags to clear (use sci_error_t bits).
 */
void sci_clear_flags(uint32_t flags);

/**
 * @brief Check if transmit buffer is ready.
 * @ingroup BSP_SCI
 *
 * @return 1 if TXRDY is set, 0 otherwise.
 */
int sci_tx_ready(void);

/**
 * @brief Check if receive buffer has data ready.
 * @ingroup BSP_SCI
 *
 * @return 1 if RXRDY is set, 0 otherwise.
 */
int sci_rx_ready(void);

/**
 * @brief Write a single byte to the transmit buffer (non-blocking).
 * @ingroup BSP_SCI
 *
 * @param data Byte to transmit.
 *
 * @note Does NOT wait for TXRDY. Call sci_tx_ready() first.
 */
void sci_write_byte(uint8_t data);

/**
 * @brief Read a single byte from the receive buffer (non-blocking).
 * @ingroup BSP_SCI
 *
 * @return Received byte.
 *
 * @note Does NOT wait for RXRDY. Call sci_rx_ready() first.
 */
uint8_t sci_read_byte(void);

/**
 * @brief Blocking transmit of a single byte.
 * @ingroup BSP_SCI
 *
 * Waits (with timeout) for TXRDY, then writes the byte.
 *
 * @param data Byte to transmit.
 * @param timeout_cycles Maximum polling iterations (0 = no timeout).
 *
 * @return 0 on success, -1 on timeout.
 *
 * @warning Spins until TXRDY or timeout. Not IRQ-safe.
 */
int sci_transmit_byte(uint8_t data, uint32_t timeout_cycles);

/**
 * @brief Blocking receive of a single byte.
 * @ingroup BSP_SCI
 *
 * Waits (with timeout) for RXRDY, then reads the byte.
 *
 * @param data Pointer to store received byte.
 * @param timeout_cycles Maximum polling iterations (0 = no timeout).
 *
 * @return 0 on success, -1 on timeout, -2 on error (parity/overrun/frame).
 *
 * @warning Spins until RXRDY or timeout. Not IRQ-safe.
 */
int sci_receive_byte(uint8_t *data, uint32_t timeout_cycles);

/**
 * @brief Blocking transmit of a buffer.
 * @ingroup BSP_SCI
 *
 * @param buf Buffer to transmit.
 * @param len Number of bytes to transmit.
 * @param timeout_cycles Timeout per byte (0 = no timeout).
 *
 * @return Number of bytes successfully transmitted, or -1 on timeout/error.
 */
int sci_transmit(const uint8_t *buf, uint32_t len, uint32_t timeout_cycles);

/**
 * @brief Blocking receive of a buffer.
 * @ingroup BSP_SCI
 *
 * @param buf Buffer to store received bytes.
 * @param len Number of bytes to receive.
 * @param timeout_cycles Timeout per byte (0 = no timeout).
 *
 * @return Number of bytes successfully received, or -1 on timeout/error.
 */
int sci_receive(uint8_t *buf, uint32_t len, uint32_t timeout_cycles);

/**
 * @brief Enable internal loopback mode for testing.
 * @ingroup BSP_SCI
 *
 * Routes TX to RX internally. Useful for self-test.
 *
 * @param enable 1 to enable loopback, 0 to disable.
 */
void sci_set_loopback(uint32_t enable);

/**
 * @brief Enable IODFT (I/O diagnostic and test) module loopback.
 * @ingroup BSP_SCI
 *
 * @param enable 1 to enable IODFT loopback, 0 to disable.
 *
 * @note Requires IODFTENA key (0xA) to be set.
 */
void sci_set_iodft_loopback(uint32_t enable);

/**
 * @brief Perform a simple loopback self-test.
 * @ingroup BSP_SCI
 *
 * Enables loopback, transmits a byte, receives it, and verifies match.
 *
 * @param test_byte Byte to transmit and verify.
 * @param timeout_cycles Timeout for each operation.
 *
 * @return 0 on success, -1 on mismatch or timeout.
 *
 * @warning Temporarily enables loopback mode. Restores original state.
 */
int sci_loopback_test(uint8_t test_byte, uint32_t timeout_cycles);

/**
 * @brief Register an interrupt service routine for a specific SCI/LIN channel.
 * @ingroup BSP_SCI
 *
 * @param channel_id VIM channel ID (e.g., IRQ_SCI_LVL0, IRQ_SCI_LVL1, IRQ_LIN_LVL0, IRQ_LIN_LVL1).
 * @param isr Function pointer to the ISR.
 *
 * @return 0 on success, non-zero on failure.
 *
 * @note Uses the VIM API. Does not enable interrupts; call sci_enable_irq() separately.
 */
int sci_register_isr(uint32_t channel_id, sci_isr_t isr);

/**
 * @brief Enable SCI interrupt for a specific VIM channel.
 * @ingroup BSP_SCI
 *
 * @param channel_id VIM channel ID.
 *
 * @return 0 on success, non-zero on failure.
 */
int sci_enable_irq(uint32_t channel_id);

/**
 * @brief Disable SCI interrupt for a specific VIM channel.
 * @ingroup BSP_SCI
 *
 * @param channel_id VIM channel ID.
 *
 * @return 0 on success, non-zero on failure.
 */
int sci_disable_irq(uint32_t channel_id);

/**
 * @brief Enable specific SCI interrupt sources.
 * @ingroup BSP_SCI
 *
 * @param int_mask Mask of interrupt bits (e.g., (1u << 9) for RX_INT).
 */
void sci_enable_interrupts(uint32_t int_mask);

/**
 * @brief Disable specific SCI interrupt sources.
 * @ingroup BSP_SCI
 *
 * @param int_mask Mask of interrupt bits.
 */
void sci_disable_interrupts(uint32_t int_mask);

/**
 * @brief Set interrupt priority level for specific sources.
 * @ingroup BSP_SCI
 *
 * @param int_mask Mask of interrupt bits to assign to level 1 (high priority).
 *
 * @note By default, interrupts are level 0. Setting a bit assigns it to level 1.
 */
void sci_set_interrupt_level(uint32_t int_mask);

/**
 * @brief Clear interrupt priority level for specific sources.
 * @ingroup BSP_SCI
 *
 * @param int_mask Mask of interrupt bits to assign to level 0.
 */
void sci_clear_interrupt_level(uint32_t int_mask);

/** @} */ /* end of BSP_SCI */

#endif /* SCI_H */

