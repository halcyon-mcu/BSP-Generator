/**
 * @file sci.h
 * @brief Serial Communication Interface (SCI) / LIN driver for TI RM46
 */

#ifndef SCI_H
#define SCI_H

#include <stdint.h>

/**
 * @defgroup BSP_SCI Serial Communication Interface (SCI) / LIN
 * @brief SCI/LIN peripheral driver for TI RM46 (Cortex-R4)
 * 
 * This module provides control and data transfer APIs for the SCI/LIN module,
 * including configuration, transmit/receive operations, interrupt management,
 * and loopback/diagnostic features.
 * 
 * @note Before calling any SCI functions, ensure the system clock is initialized
 *       and the VCLK clock reference is enabled via the clock driver.
 * @{
 */

/**
 * @brief SCI interrupt callback type.
 */
typedef void (*sci_isr_t)(void);

/**
 * @brief SCI parity mode enumeration.
 * @ingroup BSP_SCI
 */
typedef enum {
    SCI_PARITY_NONE = 0,     /**< No parity */
    SCI_PARITY_ODD  = 1,     /**< Odd parity */
    SCI_PARITY_EVEN = 2      /**< Even parity */
} sci_parity_t;

/**
 * @brief SCI stop bits enumeration.
 * @ingroup BSP_SCI
 */
typedef enum {
    SCI_STOP_BITS_1 = 0,     /**< 1 stop bit */
    SCI_STOP_BITS_2 = 1      /**< 2 stop bits */
} sci_stop_bits_t;

/**
 * @brief Initialize the SCI peripheral.
 * @ingroup BSP_SCI
 * 
 * Enables the VCLK clock, performs module reset, configures pin functions,
 * and brings the SCI out of reset. Must be called before any other SCI functions.
 * 
 * @note This function does NOT configure baud rate or frame format.
 *       Use sci_configure_format() and sci_set_baudrate() after initialization.
 */
void sci_init(void);

/**
 * @brief Configure SCI frame format.
 * @ingroup BSP_SCI
 * 
 * @param char_length Character length in bits (1..8).
 * @param parity Parity mode (none, odd, even).
 * @param stop_bits Number of stop bits (1 or 2).
 */
void sci_configure_format(uint32_t char_length, sci_parity_t parity, sci_stop_bits_t stop_bits);

/**
 * @brief Set SCI baud rate.
 * @ingroup BSP_SCI
 * 
 * Computes and programs the prescaler and fractional divider values to achieve
 * the desired baud rate based on the VCLK frequency.
 * 
 * @param baudrate Desired baud rate in bits per second (e.g. 115200).
 * 
 * @note Requires the clock service to retrieve VCLK frequency.
 * @warning Must be called after sci_init() and before enabling transmit/receive.
 */
void sci_set_baudrate(uint32_t baudrate);

/**
 * @brief Enable SCI transmitter.
 * @ingroup BSP_SCI
 */
void sci_enable_tx(void);

/**
 * @brief Disable SCI transmitter.
 * @ingroup BSP_SCI
 */
void sci_disable_tx(void);

/**
 * @brief Enable SCI receiver.
 * @ingroup BSP_SCI
 */
void sci_enable_rx(void);

/**
 * @brief Disable SCI receiver.
 * @ingroup BSP_SCI
 */
void sci_disable_rx(void);

/**
 * @brief Transmit a single byte (blocking).
 * @ingroup BSP_SCI
 * 
 * Waits for the TXRDY flag, writes the byte to the transmit buffer,
 * and waits for TX_EMPTY to confirm transmission.
 * 
 * @param data Byte to transmit.
 * @return 0 on success, -1 on timeout.
 * 
 * @warning This function will block until the hardware is ready or timeout occurs.
 * @note Timeout is bounded to prevent infinite loops.
 */
int sci_write_byte(uint8_t data);

/**
 * @brief Receive a single byte (blocking).
 * @ingroup BSP_SCI
 * 
 * Waits for the RXRDY flag and reads one byte from the receive buffer.
 * 
 * @param data Pointer to store the received byte.
 * @return 0 on success, -1 on timeout.
 * 
 * @warning This function will block until data is available or timeout occurs.
 * @note Timeout is bounded to prevent infinite loops.
 */
int sci_read_byte(uint8_t *data);

/**
 * @brief Transmit multiple bytes (blocking).
 * @ingroup BSP_SCI
 * 
 * @param buf Pointer to data buffer.
 * @param len Number of bytes to transmit.
 * @return Number of bytes successfully transmitted (0..len), or -1 on error.
 */
int sci_write(const uint8_t *buf, uint32_t len);

/**
 * @brief Receive multiple bytes (blocking).
 * @ingroup BSP_SCI
 * 
 * @param buf Pointer to destination buffer.
 * @param len Maximum number of bytes to receive.
 * @return Number of bytes successfully received (0..len), or -1 on error.
 */
int sci_read(uint8_t *buf, uint32_t len);

/**
 * @brief Check if transmitter is ready.
 * @ingroup BSP_SCI
 * 
 * @return 1 if TXRDY is set, 0 otherwise.
 */
int sci_tx_ready(void);

/**
 * @brief Check if receiver has data available.
 * @ingroup BSP_SCI
 * 
 * @return 1 if RXRDY is set, 0 otherwise.
 */
int sci_rx_ready(void);

/**
 * @brief Check if transmitter is empty.
 * @ingroup BSP_SCI
 * 
 * @return 1 if TX_EMPTY is set, 0 otherwise.
 */
int sci_tx_empty(void);

/**
 * @brief Check if SCI is busy.
 * @ingroup BSP_SCI
 * 
 * @return 1 if BUSY flag is set, 0 otherwise.
 */
int sci_is_busy(void);

/**
 * @brief Read SCI flags register.
 * @ingroup BSP_SCI
 * 
 * @return Current value of SCIFLR register.
 */
uint32_t sci_get_flags(void);

/**
 * @brief Clear specific error flags.
 * @ingroup BSP_SCI
 * 
 * Clears the specified bits in the SCIFLR register.
 * 
 * @param flags Bit mask of flags to clear (e.g. FE, OE, PE).
 */
void sci_clear_flags(uint32_t flags);

/**
 * @brief Enable loopback mode (internal digital loopback).
 * @ingroup BSP_SCI
 * 
 * Sets the LOOP_BACK bit in SCIGCR1 to enable internal loopback for diagnostic
 * and self-test purposes.
 * 
 * @note In loopback mode, the TX output is internally connected to the RX input.
 * @warning Loopback mode is intended for testing only. Disable before normal operation.
 */
void sci_enable_loopback(void);

/**
 * @brief Disable loopback mode.
 * @ingroup BSP_SCI
 */
void sci_disable_loopback(void);

/**
 * @brief Enable IODFT module loopback (analog loopback via pins).
 * @ingroup BSP_SCI
 * 
 * Enables the LPB_ENA bit in IODFTCTRL to route the transmit signal externally
 * through the physical pins back to the receiver for analog path testing.
 * 
 * @note This is distinct from the internal digital loopback.
 */
void sci_enable_iodft_loopback(void);

/**
 * @brief Disable IODFT module loopback.
 * @ingroup BSP_SCI
 */
void sci_disable_iodft_loopback(void);

/**
 * @brief Perform a loopback self-test (blocking).
 * @ingroup BSP_SCI
 * 
 * Enables internal loopback, transmits a test pattern, receives it back,
 * and verifies the data matches. Restores the original loopback state.
 * 
 * @return 0 on success (all bytes matched), -1 on failure (timeout or mismatch).
 * 
 * @note This function temporarily enables loopback mode and disables it upon completion.
 * @warning Ensure transmitter and receiver are enabled before calling this function.
 */
int sci_loopback_test(void);

/**
 * @brief Enable SCI interrupt (level 0 or level 1).
 * @ingroup BSP_SCI
 * 
 * Sets the specified interrupt bit in SCISETINT.
 * 
 * @param int_flag Interrupt flag bit (e.g. SET_RX_INT_BIT, SET_TX_INT_BIT).
 */
void sci_enable_interrupt(uint32_t int_flag);

/**
 * @brief Disable SCI interrupt.
 * @ingroup BSP_SCI
 * 
 * Clears the specified interrupt bit in SCICLEARINT.
 * 
 * @param int_flag Interrupt flag bit to clear.
 */
void sci_disable_interrupt(uint32_t int_flag);

/**
 * @brief Set interrupt to level 0 or level 1.
 * @ingroup BSP_SCI
 * 
 * @param int_flag Interrupt flag bit.
 * @param level 0 for level 0, 1 for level 1.
 */
void sci_set_interrupt_level(uint32_t int_flag, uint32_t level);

/**
 * @brief Register ISR for SCI level 0 interrupt.
 * @ingroup BSP_SCI
 * 
 * Registers a user-provided callback for the SCI level 0 interrupt (VIM channel 64).
 * 
 * @param isr Function pointer to the interrupt handler.
 * @return 0 on success, non-zero on failure.
 * 
 * @note Requires VIM driver to be initialized.
 */
int sci_register_isr_lvl0(sci_isr_t isr);

/**
 * @brief Register ISR for SCI level 1 interrupt.
 * @ingroup BSP_SCI
 * 
 * Registers a user-provided callback for the SCI level 1 interrupt (VIM channel 74).
 * 
 * @param isr Function pointer to the interrupt handler.
 * @return 0 on success, non-zero on failure.
 * 
 * @note Requires VIM driver to be initialized.
 */
int sci_register_isr_lvl1(sci_isr_t isr);

/**
 * @brief Enable SCI level 0 interrupt in VIM.
 * @ingroup BSP_SCI
 * 
 * @return 0 on success, non-zero on failure.
 */
int sci_enable_irq_lvl0(void);

/**
 * @brief Enable SCI level 1 interrupt in VIM.
 * @ingroup BSP_SCI
 * 
 * @return 0 on success, non-zero on failure.
 */
int sci_enable_irq_lvl1(void);

/**
 * @brief Disable SCI level 0 interrupt in VIM.
 * @ingroup BSP_SCI
 * 
 * @return 0 on success, non-zero on failure.
 */
int sci_disable_irq_lvl0(void);

/**
 * @brief Disable SCI level 1 interrupt in VIM.
 * @ingroup BSP_SCI
 * 
 * @return 0 on success, non-zero on failure.
 */
int sci_disable_irq_lvl1(void);

/** @} */ /* end of BSP_SCI */

#endif /* SCI_H */
