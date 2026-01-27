/**
 * @file sci.h
 * @brief Serial Communication Interface (SCI) / LIN driver for TI RM46
 */

#ifndef SCI_H
#define SCI_H

#include <stdint.h>

/**
 * @defgroup BSP_SCI Serial Communication Interface (SCI/LIN)
 * @brief Driver for RM46 SCI/LIN peripheral providing UART and LIN communication.
 *
 * This module provides APIs for configuring and using the SCI peripheral in both
 * SCI (UART) mode and LIN mode. It supports blocking transmit/receive, interrupt
 * handling, loopback testing, and baud rate configuration.
 *
 * Typical usage:
 * @code
 * sci_init();
 * sci_configure(8, SCI_PARITY_NONE, 1);
 * sci_set_baudrate(115200);
 * sci_putc('H');
 * uint8_t ch = sci_getc();
 * @endcode
 * @{
 */

/**
 * @brief SCI parity mode enumeration.
 */
typedef enum {
    SCI_PARITY_NONE = 0, /**< No parity */
    SCI_PARITY_ODD  = 1, /**< Odd parity */
    SCI_PARITY_EVEN = 2  /**< Even parity */
} sci_parity_t;

/**
 * @brief SCI interrupt callback function type.
 */
typedef void (*sci_isr_t)(void);

/**
 * @brief Initialize the SCI peripheral.
 * @ingroup BSP_SCI
 *
 * Enables the VCLK clock, brings the SCI module out of reset, configures
 * TX/RX pins as functional, and enables TX/RX.
 *
 * @note Must be called before any other SCI functions.
 * @note Does not configure baud rate or frame format; use sci_configure() and sci_set_baudrate().
 */
void sci_init(void);

/**
 * @brief Configure SCI frame format.
 * @ingroup BSP_SCI
 *
 * Sets the character length, parity mode, and number of stop bits.
 *
 * @param char_length Character length in bits (1..8).
 * @param parity Parity mode (none, odd, even).
 * @param stop_bits Number of stop bits (0 = 1 stop bit, 1 = 2 stop bits).
 *
 * @note Call after sci_init() and before transmitting or receiving data.
 */
void sci_configure(uint8_t char_length, sci_parity_t parity, uint8_t stop_bits);

/**
 * @brief Set SCI baud rate.
 * @ingroup BSP_SCI
 *
 * Computes and writes the prescaler and fractional divider (M) for the desired baud rate.
 * Uses the VCLK frequency obtained from clock_get_hz().
 *
 * @param baudrate Desired baud rate in bits per second.
 * @return 0 on success, -1 on error (invalid baud rate or clock not available).
 *
 * @note Must be called after sci_init().
 */
int sci_set_baudrate(uint32_t baudrate);

/**
 * @brief Transmit a single byte (blocking).
 * @ingroup BSP_SCI
 *
 * Waits (with timeout) until the TXRDY flag is set, then writes the byte to SCITD.
 *
 * @param byte Byte to transmit.
 * @return 0 on success, -1 on timeout.
 *
 * @warning Blocks until TX buffer is ready or timeout occurs.
 */
int sci_putc(uint8_t byte);

/**
 * @brief Receive a single byte (blocking).
 * @ingroup BSP_SCI
 *
 * Waits (with timeout) until the RXRDY flag is set, then reads the byte from SCIRD.
 *
 * @return Received byte (0..255), or -1 on timeout or error (parity, framing, overrun).
 *
 * @warning Blocks until RX data is ready or timeout occurs.
 * @note Clears any pending error flags before returning on error.
 */
int sci_getc(void);

/**
 * @brief Transmit a buffer of bytes (blocking).
 * @ingroup BSP_SCI
 *
 * Transmits up to len bytes using sci_putc().
 *
 * @param buf Pointer to data buffer.
 * @param len Number of bytes to send.
 * @return Number of bytes successfully transmitted (may be less than len on timeout).
 *
 * @warning Blocks until all bytes are sent or a timeout occurs.
 */
uint32_t sci_write(const uint8_t *buf, uint32_t len);

/**
 * @brief Receive a buffer of bytes (blocking).
 * @ingroup BSP_SCI
 *
 * Receives up to len bytes using sci_getc().
 *
 * @param buf Pointer to destination buffer.
 * @param len Maximum number of bytes to receive.
 * @return Number of bytes successfully received (may be less than len on timeout or error).
 *
 * @warning Blocks until requested bytes are received or a timeout/error occurs.
 */
uint32_t sci_read(uint8_t *buf, uint32_t len);

/**
 * @brief Check if transmitter is ready.
 * @ingroup BSP_SCI
 *
 * @return 1 if TXRDY flag is set, 0 otherwise.
 */
int sci_tx_ready(void);

/**
 * @brief Check if receiver has data ready.
 * @ingroup BSP_SCI
 *
 * @return 1 if RXRDY flag is set, 0 otherwise.
 */
int sci_rx_ready(void);

/**
 * @brief Check if transmitter is completely empty.
 * @ingroup BSP_SCI
 *
 * @return 1 if TX_EMPTY flag is set, 0 otherwise.
 */
int sci_tx_empty(void);

/**
 * @brief Read SCI flags register.
 * @ingroup BSP_SCI
 *
 * @return Current value of SCIFLR (all flags).
 */
uint32_t sci_get_flags(void);

/**
 * @brief Clear specific SCI error flags.
 * @ingroup BSP_SCI
 *
 * Clears parity, overrun, and framing error flags by writing 1s to their bit positions.
 *
 * @param flags Bitmask of flags to clear (PE=bit 24, OE=bit 25, FE=bit 26).
 */
void sci_clear_flags(uint32_t flags);

/**
 * @brief Enable internal loopback mode.
 * @ingroup BSP_SCI
 *
 * Connects TX output to RX input internally for self-test.
 *
 * @note Use sci_disable_loopback() to return to normal operation.
 */
void sci_enable_loopback(void);

/**
 * @brief Disable internal loopback mode.
 * @ingroup BSP_SCI
 *
 * Returns SCI to normal (non-loopback) operation.
 */
void sci_disable_loopback(void);

/**
 * @brief Run a loopback self-test.
 * @ingroup BSP_SCI
 *
 * Enables loopback, transmits a test pattern, receives it, and verifies.
 *
 * @return 0 if test passes, -1 if mismatch or timeout occurs.
 *
 * @warning Temporarily enables loopback mode and may disrupt normal communication.
 */
int sci_loopback_test(void);

/**
 * @brief Register an interrupt handler for a given SCI channel.
 * @ingroup BSP_SCI
 *
 * Registers a user ISR with the VIM for the specified SCI interrupt channel.
 *
 * @param channel_id VIM channel ID (e.g., 64 for SCI_LVL0, 74 for SCI_LVL1).
 * @param isr Pointer to ISR callback function.
 * @return 0 on success, non-zero on failure.
 *
 * @note Does not enable the interrupt; call sci_enable_irq() afterward.
 */
int sci_register_isr(uint32_t channel_id, sci_isr_t isr);

/**
 * @brief Enable SCI interrupt on a given VIM channel.
 * @ingroup BSP_SCI
 *
 * Enables the specified VIM channel for SCI interrupts.
 *
 * @param channel_id VIM channel ID.
 * @return 0 on success, non-zero on failure.
 */
int sci_enable_irq(uint32_t channel_id);

/**
 * @brief Disable SCI interrupt on a given VIM channel.
 * @ingroup BSP_SCI
 *
 * Disables the specified VIM channel for SCI interrupts.
 *
 * @param channel_id VIM channel ID.
 * @return 0 on success, non-zero on failure.
 */
int sci_disable_irq(uint32_t channel_id);

/**
 * @brief Enable SCI RX interrupt.
 * @ingroup BSP_SCI
 *
 * Sets the SET_RX_INT bit in SCISETINT, enabling receive interrupts.
 *
 * @note Does not configure VIM routing or priority; use sci_register_isr() and sci_enable_irq().
 */
void sci_enable_rx_int(void);

/**
 * @brief Disable SCI RX interrupt.
 * @ingroup BSP_SCI
 *
 * Clears the CLR_RX_INT bit in SCICLEARINT, disabling receive interrupts.
 */
void sci_disable_rx_int(void);

/**
 * @brief Enable SCI TX interrupt.
 * @ingroup BSP_SCI
 *
 * Sets the SET_TX_INT bit in SCISETINT, enabling transmit interrupts.
 */
void sci_enable_tx_int(void);

/**
 * @brief Disable SCI TX interrupt.
 * @ingroup BSP_SCI
 *
 * Clears the CLR_TX_INT bit in SCICLEARINT, disabling transmit interrupts.
 */
void sci_disable_tx_int(void);

/**
 * @brief Read SCI interrupt vector offset 0.
 * @ingroup BSP_SCI
 *
 * Returns the 5-bit vector offset for INT0, indicating the highest-priority pending interrupt.
 *
 * @return Interrupt vector offset (0..31).
 */
uint32_t sci_get_intvect0(void);

/**
 * @brief Read SCI interrupt vector offset 1.
 * @ingroup BSP_SCI
 *
 * Returns the 5-bit vector offset for INT1, indicating the highest-priority pending interrupt.
 *
 * @return Interrupt vector offset (0..31).
 */
uint32_t sci_get_intvect1(void);

/** @} */ /* end of BSP_SCI */

#endif /* SCI_H */

