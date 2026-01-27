/**
 * @file gio.h
 * @brief General-Purpose Input/Output (GIO) driver for RM46
 */

#ifndef GIO_H
#define GIO_H

#include <stdint.h>

/**
 * @defgroup BSP_GIO General-Purpose Input/Output (GIO)
 * @brief GIO driver providing configuration, data I/O, and interrupt management
 * for GPIO ports A and B on RM46.
 * @{
 */

/**
 * @brief GIO port identifiers.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PORT_A = 0, /**< GIO Port A */
    GIO_PORT_B = 1  /**< GIO Port B */
} gio_port_t;

/**
 * @brief GIO pin direction.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_DIR_INPUT  = 0, /**< Configure pin as input */
    GIO_DIR_OUTPUT = 1  /**< Configure pin as output */
} gio_dir_t;

/**
 * @brief GIO open-drain mode.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PUSH_PULL  = 0, /**< Push-pull output */
    GIO_OPEN_DRAIN = 1  /**< Open-drain output */
} gio_output_mode_t;

/**
 * @brief GIO pull configuration.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PULL_DISABLED = 0, /**< Pull resistor disabled */
    GIO_PULL_ENABLED  = 1  /**< Pull resistor enabled */
} gio_pull_enable_t;

/**
 * @brief GIO pull direction.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PULL_DOWN = 0, /**< Pull down */
    GIO_PULL_UP   = 1  /**< Pull up */
} gio_pull_select_t;

/**
 * @brief GIO interrupt detection mode.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_INT_SINGLE_EDGE = 0, /**< Single edge, polarity controlled by GIOPOL */
    GIO_INT_BOTH_EDGES  = 1  /**< Both edges trigger interrupt */
} gio_int_detect_t;

/**
 * @brief GIO interrupt polarity.
 * @ingroup BSP_GIO
 *
 * In normal mode: 0 = falling edge, 1 = rising edge.
 * In low-power mode: 0 = low level, 1 = high level.
 */
typedef enum {
    GIO_INT_POL_FALLING_OR_LOW = 0, /**< Falling edge or low level */
    GIO_INT_POL_RISING_OR_HIGH = 1  /**< Rising edge or high level */
} gio_int_polarity_t;

/**
 * @brief GIO interrupt priority level.
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_INT_PRIORITY_LOW  = 0, /**< Low priority (B) */
    GIO_INT_PRIORITY_HIGH = 1  /**< High priority (A) */
} gio_int_priority_t;

/**
 * @brief GIO interrupt service routine callback type.
 * @ingroup BSP_GIO
 */
typedef void (*gio_isr_t)(void);

/**
 * @brief Initialize the GIO peripheral.
 * @ingroup BSP_GIO
 *
 * Enables the required clock (VCLK) and sets GIO module to normal operation
 * by setting GCR0 RESET bit.
 *
 * @note Must be called before any other GIO functions.
 * @note Assumes system-level clock and VIM initialization are already complete.
 */
void gio_init(void);

/**
 * @brief Configure pin direction.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier (GIO_PORT_A or GIO_PORT_B)
 * @param pin Pin number (0..7)
 * @param dir Direction (GIO_DIR_INPUT or GIO_DIR_OUTPUT)
 */
void gio_set_direction(gio_port_t port, uint8_t pin, gio_dir_t dir);

/**
 * @brief Configure multiple pins direction at once.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param mask 8-bit mask: 0 = input, 1 = output
 */
void gio_set_direction_mask(gio_port_t port, uint8_t mask);

/**
 * @brief Set output pin to logic high.
 * @ingroup BSP_GIO
 *
 * Uses GIODSET register for atomic write.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 */
void gio_set_pin(gio_port_t port, uint8_t pin);

/**
 * @brief Set output pin to logic low.
 * @ingroup BSP_GIO
 *
 * Uses GIODCLR register for atomic write.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 */
void gio_clear_pin(gio_port_t port, uint8_t pin);

/**
 * @brief Toggle output pin.
 * @ingroup BSP_GIO
 *
 * Reads current output state from GIODOUT and toggles the specified pin.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 */
void gio_toggle_pin(gio_port_t port, uint8_t pin);

/**
 * @brief Write multiple output pins at once.
 * @ingroup BSP_GIO
 *
 * Writes to GIODOUT register.
 *
 * @param port Port identifier
 * @param value 8-bit value to write to port output
 */
void gio_write_port(gio_port_t port, uint8_t value);

/**
 * @brief Read input pin state.
 * @ingroup BSP_GIO
 *
 * Reads from GIODIN register.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @return Pin state: 0 = low, 1 = high
 */
uint8_t gio_read_pin(gio_port_t port, uint8_t pin);

/**
 * @brief Read all input pins from port.
 * @ingroup BSP_GIO
 *
 * Reads from GIODIN register.
 *
 * @param port Port identifier
 * @return 8-bit input value
 */
uint8_t gio_read_port(gio_port_t port);

/**
 * @brief Configure output mode (push-pull or open-drain).
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @param mode Output mode
 */
void gio_set_output_mode(gio_port_t port, uint8_t pin, gio_output_mode_t mode);

/**
 * @brief Configure pull resistor enable.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @param enable Pull enable state
 */
void gio_set_pull_enable(gio_port_t port, uint8_t pin, gio_pull_enable_t enable);

/**
 * @brief Configure pull resistor direction.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @param select Pull direction (up or down)
 */
void gio_set_pull_select(gio_port_t port, uint8_t pin, gio_pull_select_t select);

/**
 * @brief Configure interrupt detection mode.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @param detect Detection mode (single edge or both edges)
 */
void gio_set_int_detect(gio_port_t port, uint8_t pin, gio_int_detect_t detect);

/**
 * @brief Configure interrupt polarity.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @param polarity Polarity (falling/low or rising/high)
 */
void gio_set_int_polarity(gio_port_t port, uint8_t pin, gio_int_polarity_t polarity);

/**
 * @brief Enable interrupt for a pin.
 * @ingroup BSP_GIO
 *
 * Writes to GIOENASET register.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 */
void gio_enable_int(gio_port_t port, uint8_t pin);

/**
 * @brief Disable interrupt for a pin.
 * @ingroup BSP_GIO
 *
 * Writes to GIOENACLR register.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 */
void gio_disable_int(gio_port_t port, uint8_t pin);

/**
 * @brief Set interrupt priority level for a pin.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @param priority Priority level (low or high)
 */
void gio_set_int_priority(gio_port_t port, uint8_t pin, gio_int_priority_t priority);

/**
 * @brief Clear interrupt flag for a pin.
 * @ingroup BSP_GIO
 *
 * Writes 1 to the corresponding bit in GIOFLG to clear the flag.
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 */
void gio_clear_int_flag(gio_port_t port, uint8_t pin);

/**
 * @brief Read interrupt flag status for a pin.
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin Pin number (0..7)
 * @return 1 if interrupt occurred, 0 otherwise
 */
uint8_t gio_get_int_flag(gio_port_t port, uint8_t pin);

/**
 * @brief Get offset of pending high-priority interrupt.
 * @ingroup BSP_GIO
 *
 * Reads GIOOFF1 register. Reading this register clears the corresponding
 * interrupt flag.
 *
 * @return 6-bit offset value (0..63 corresponding to ports/pins)
 */
uint8_t gio_get_offset_high(void);

/**
 * @brief Get offset of pending low-priority interrupt.
 * @ingroup BSP_GIO
 *
 * Reads GIOOFF2 register. Reading this register clears the corresponding
 * interrupt flag.
 *
 * @return 6-bit offset value (0..63 corresponding to ports/pins)
 */
uint8_t gio_get_offset_low(void);

/**
 * @brief Get emulation offset for high-priority interrupt.
 * @ingroup BSP_GIO
 *
 * Reads GIOEMU1 register. Reading this register does NOT clear the interrupt flag.
 * Useful for debugging and emulation.
 *
 * @return 6-bit offset value
 */
uint8_t gio_get_emu_offset_high(void);

/**
 * @brief Get emulation offset for low-priority interrupt.
 * @ingroup BSP_GIO
 *
 * Reads GIOEMU2 register. Reading this register does NOT clear the interrupt flag.
 * Useful for debugging and emulation.
 *
 * @return 6-bit offset value
 */
uint8_t gio_get_emu_offset_low(void);

/**
 * @brief Register ISR for GIO interrupt channel.
 * @ingroup BSP_GIO
 *
 * Uses VIM API to register the interrupt service routine.
 *
 * @param channel_id VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @param isr Callback function pointer
 * @return 0 on success, negative on error
 */
int gio_register_isr(uint32_t channel_id, gio_isr_t isr);

/**
 * @brief Enable GIO interrupt at VIM level.
 * @ingroup BSP_GIO
 *
 * Enables the specified VIM channel.
 *
 * @param channel_id VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @return 0 on success, negative on error
 */
int gio_enable_irq(uint32_t channel_id);

/**
 * @brief Disable GIO interrupt at VIM level.
 * @ingroup BSP_GIO
 *
 * Disables the specified VIM channel.
 *
 * @param channel_id VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @return 0 on success, negative on error
 */
int gio_disable_irq(uint32_t channel_id);

/** @} */ /* end of BSP_GIO */

#endif /* GIO_H */

