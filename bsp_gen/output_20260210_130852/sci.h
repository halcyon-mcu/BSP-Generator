/**
 * @file sci.h
 * @brief RM46 Serial Communication Interface (SCI) / LIN driver
 */

#ifndef SCI_H
#define SCI_H

#include <stdint.h>

/**
 * @defgroup BSP_SCI Serial Communication Interface (SCI)
 * @brief SCI/LIN peripheral driver for TI RM46 (Cortex-R4).
 *
 * This driver provides blocking transmit/receive, interrupt support, baud rate configuration,
 * and loopback/self-test functionality for the SCI/LIN module.
 *
 * @note sci_init() must be called before any other SCI API. It will enable the VCLK clock reference,
 *       bring the module out of reset, and configure the pins and enables.
 *
 * @{
 */

/**
 * @brief SCI parity modes.
 * @ingroup BSP_SCI
 */
typedef enum {
    SCI_PARITY_NONE = 0, /**< No parity */
    SCI_PARITY_ODD  = 1, /**< Odd parity */
    SCI_PARITY_EVEN = 2  /**< Even parity */
} sci_parity_t;

/**
 * @brief SCI configuration structure.
 * @ingroup BSP_SCI
 */
typedef struct {
    uint32_t baud_rate;     /**< Desired baud rate in Hz */
    uint8_t data_bits;      /**< Number of data bits (1..8) */
    uint8_t stop_bits;      /**< Number of stop bits: 0=1 stop bit, 1=2 stop bits */
    sci_parity_t parity;    /**< Parity mode */
    uint8_t loopback;       /**< Internal loopback enable (1=enabled, 0=disabled) */
} sci_config_t;

/**
 * @brief SCI user ISR callback type.
 * @ingroup BSP_SCI
 */
typedef void (*sci_isr_t)(void);

/**
 * @brief Initialize the SCI module.
 * @ingroup BSP_SCI
 *
 * Enables the VCLK clock, brings the module out of reset, configures pins,
 * and enables transmit and receive.
 *
 * @note Must be called before any other SCI API functions.
 */
void sci_init(void);

/**
 * @brief Configure the SCI module.
 * @ingroup BSP_SCI
 *
 * Configures baud rate, frame format (data bits, stop bits, parity), and optional loopback.
 * Computes the baud-rate prescaler using the VCLK frequency.
 *
 * @param[in] cfg Pointer to configuration structure.
 * @return 0 on success, -1 if cfg is NULL or parameters are invalid.
 *
 * @note sci_init() must be called first.
 */
int sci_configure(const sci_config_t *cfg);

/**
 * @brief Transmit a single byte (blocking).
 * @ingroup BSP_SCI
 *
 * Waits for TXRDY flag, writes data, then waits for TX_EMPTY.
 *
 * @param[in] data Byte to transmit.
 * @return 0 on success, -1 on timeout.
 *
 * @note This function blocks until the transmit completes or times out.
 */
int sci_transmit_byte(uint8_t data);

/**
 * @brief Receive a single byte (blocking).
 * @ingroup BSP_SCI
 *
 * Waits for RXRDY flag, reads data, clears RXRDY.
 *
 * @param[out] data Pointer to store received byte.
 * @return 0 on success, -1 on timeout or error (FE/OE/PE).
 *
 * @note This function blocks until a byte is received or times out.
 */
int sci_receive_byte(uint8_t *data);

/**
 * @brief Transmit a buffer (blocking).
 * @ingroup BSP_SCI
 *
 * Transmits up to len bytes from buf using sci_transmit_byte().
 *
 * @param[in] buf Buffer to transmit.
 * @param[in] len Number of bytes to transmit.
 * @return Number of bytes actually transmitted (may be less than len on timeout).
 *
 * @note Stops on first timeout.
 */
uint32_t sci_transmit(const uint8_t *buf, uint32_t len);

/**
 * @brief Receive a buffer (blocking).
 * @ingroup BSP_SCI
 *
 * Receives up to len bytes into buf using sci_receive_byte().
 *
 * @param[out] buf Buffer to store received data.
 * @param[in] len Maximum number of bytes to receive.
 * @return Number of bytes actually received (may be less than len on timeout or error).
 *
 * @note Stops on first timeout or frame error.
 */
uint32_t sci_receive(uint8_t *buf, uint32_t len);

/**
 * @brief Check if transmitter is ready.
 * @ingroup BSP_SCI
 *
 * @return 1 if TXRDY is set, 0 otherwise.
 */
int sci_tx_ready(void);

/**
 * @brief Check if receiver has data ready.
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
 * @brief Read SCI flags register.
 * @ingroup BSP_SCI
 *
 * @return Current value of SCIFLR.
 */
uint32_t sci_get_flags(void);

/**
 * @brief Clear specific SCI flags.
 * @ingroup BSP_SCI
 *
 * Writes mask to SCIFLR to clear flags (RWC semantics).
 *
 * @param[in] mask Bitmask of flags to clear.
 */
void sci_clear_flags(uint32_t mask);

/**
 * @brief Enable SCI loopback mode.
 * @ingroup BSP_SCI
 *
 * Sets SCIGCR1.LOOP_BACK and IODFTCTRL.LPB_ENA for internal loopback testing.
 *
 * @note Useful for self-test; TX data loops back to RX internally.
 */
void sci_loopback_enable(void);

/**
 * @brief Disable SCI loopback mode.
 * @ingroup BSP_SCI
 *
 * Clears SCIGCR1.LOOP_BACK and IODFTCTRL.LPB_ENA.
 */
void sci_loopback_disable(void);

/**
 * @brief Run SCI loopback self-test.
 * @ingroup BSP_SCI
 *
 * Enables loopback, transmits a test pattern, receives it, verifies match, disables loopback.
 *
 * @return 0 if test passes (all bytes echoed correctly), -1 if any mismatch or timeout.
 *
 * @note Temporarily modifies module configuration (loopback); restore config if needed.
 */
int sci_self_test_loopback(void);

/**
 * @brief Register user ISR for SCI level 0 interrupt.
 * @ingroup BSP_SCI
 *
 * Registers the provided callback with the VIM for SCI_LVL0 channel.
 *
 * @param[in] isr User ISR callback (may be NULL to unregister).
 * @return 0 on success, non-zero on VIM error.
 *
 * @note Does NOT enable the interrupt; call sci_enable_rx_interrupt() or sci_enable_tx_interrupt() as needed.
 */
int sci_register_isr_level0(sci_isr_t isr);

/**
 * @brief Register user ISR for SCI level 1 interrupt.
 * @ingroup BSP_SCI
 *
 * Registers the provided callback with the VIM for SCI_LVL1 channel.
 *
 * @param[in] isr User ISR callback (may be NULL to unregister).
 * @return 0 on success, non-zero on VIM error.
 *
 * @note Does NOT enable the interrupt; call sci_set_interrupt_level() and sci_enable_*_interrupt() as needed.
 */
int sci_register_isr_level1(sci_isr_t isr);

/**
 * @brief Enable receive interrupt (INT0).
 * @ingroup BSP_SCI
 *
 * Sets SCISETINT.SET_RX_INT and enables VIM channel for SCI_LVL0.
 *
 * @return 0 on success, non-zero on VIM error.
 *
 * @note User must register ISR via sci_register_isr_level0() first.
 */
int sci_enable_rx_interrupt(void);

/**
 * @brief Disable receive interrupt (INT0).
 * @ingroup BSP_SCI
 *
 * Clears SCICLEARINT.CLR_RX_INT and disables VIM channel for SCI_LVL0.
 *
 * @return 0 on success, non-zero on VIM error.
 */
int sci_disable_rx_interrupt(void);

/**
 * @brief Enable transmit interrupt (INT0).
 * @ingroup BSP_SCI
 *
 * Sets SCISETINT.SET_TX_INT and enables VIM channel for SCI_LVL0.
 *
 * @return 0 on success, non-zero on VIM error.
 *
 * @note User must register ISR via sci_register_isr_level0() first.
 */
int sci_enable_tx_interrupt(void);

/**
 * @brief Disable transmit interrupt (INT0).
 * @ingroup BSP_SCI
 *
 * Clears SCICLEARINT.CLR_TX_INT and disables VIM channel for SCI_LVL0.
 *
 * @return 0 on success, non-zero on VIM error.
 */
int sci_disable_tx_interrupt(void);

/**
 * @brief Set receive interrupt to level 1 (INT1).
 * @ingroup BSP_SCI
 *
 * Sets SCISETINTLVL.SET_RX_INT_LVL so RX interrupt routes to SCI_LVL1.
 *
 * @note User must register sci_register_isr_level1() and enable via sci_enable_rx_interrupt_level1().
 */
void sci_set_rx_interrupt_level1(void);

/**
 * @brief Set transmit interrupt to level 1 (INT1).
 * @ingroup BSP_SCI
 *
 * Sets SCISETINTLVL.SET_TX_INT_LVL so TX interrupt routes to SCI_LVL1.
 *
 * @note User must register sci_register_isr_level1() and enable via sci_enable_tx_interrupt_level1().
 */
void sci_set_tx_interrupt_level1(void);

/**
 * @brief Enable receive interrupt on level 1 (INT1).
 * @ingroup BSP_SCI
 *
 * Sets SCISETINT.SET_RX_INT and enables VIM channel for SCI_LVL1.
 *
 * @return 0 on success, non-zero on VIM error.
 *
 * @note Call sci_set_rx_interrupt_level1() and sci_register_isr_level1() first.
 */
int sci_enable_rx_interrupt_level1(void);

/**
 * @brief Enable transmit interrupt on level 1 (INT1).
 * @ingroup BSP_SCI
 *
 * Sets SCISETINT.SET_TX_INT and enables VIM channel for SCI_LVL1.
 *
 * @return 0 on success, non-zero on VIM error.
 *
 * @note Call sci_set_tx_interrupt_level1() and sci_register_isr_level1() first.
 */
int sci_enable_tx_interrupt_level1(void);

/**
 * @brief Read the interrupt vector offset for INT0.
 * @ingroup BSP_SCI
 *
 * @return INTVECT0 field value (0..15).
 */
uint32_t sci_get_intvect0(void);

/**
 * @brief Read the interrupt vector offset for INT1.
 * @ingroup BSP_SCI
 *
 * @return INTVECT1 field value (0..15).
 */
uint32_t sci_get_intvect1(void);

/** @} */ /* end of BSP_SCI */

#endif /* SCI_H */

