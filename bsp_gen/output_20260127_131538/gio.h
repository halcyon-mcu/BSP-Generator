/**
 * @file gio.h
 * @brief GIO (General-Purpose Input/Output) driver for RM46
 */

#ifndef GIO_H
#define GIO_H

#include <stdint.h>

/**
 * @defgroup BSP_GIO GIO (General-Purpose Input/Output)
 * @brief Driver for the GIO peripheral on RM46
 *
 * The GIO module provides up to four 8-bit ports (A, B, C, D) with configurable
 * direction, pull-up/down, open-drain output, and interrupt capabilities.
 * Each port supports both high-priority (A) and low-priority (B) interrupts
 * with configurable edge or level triggering.
 *
 * @note This driver assumes system clocks and VIM are initialized externally.
 * @{
 */

/**
 * @brief GIO port identifier
 */
typedef enum {
    GIO_PORT_A = 0, /**< Port A (GIOA[7:0]) */
    GIO_PORT_B = 1  /**< Port B (GIOB[7:0]) */
} gio_port_t;

/**
 * @brief GIO pin direction
 */
typedef enum {
    GIO_DIR_INPUT  = 0, /**< Configure pin as input */
    GIO_DIR_OUTPUT = 1  /**< Configure pin as output */
} gio_dir_t;

/**
 * @brief GIO pull configuration
 */
typedef enum {
    GIO_PULL_DOWN = 0, /**< Enable pull-down resistor */
    GIO_PULL_UP   = 1  /**< Enable pull-up resistor */
} gio_pull_t;

/**
 * @brief GIO output mode
 */
typedef enum {
    GIO_OUTPUT_PUSHPULL  = 0, /**< Push-pull output */
    GIO_OUTPUT_OPENDRAIN = 1  /**< Open-drain output */
} gio_output_mode_t;

/**
 * @brief GIO interrupt detection mode
 */
typedef enum {
    GIO_INT_SINGLE_EDGE = 0, /**< Single edge (polarity controlled by GIOPOL) */
    GIO_INT_BOTH_EDGES  = 1  /**< Both rising and falling edges */
} gio_int_detect_t;

/**
 * @brief GIO interrupt polarity (for single-edge mode)
 */
typedef enum {
    GIO_INT_FALLING = 0, /**< Falling edge or low level */
    GIO_INT_RISING  = 1  /**< Rising edge or high level */
} gio_int_polarity_t;

/**
 * @brief GIO interrupt priority level
 */
typedef enum {
    GIO_INT_PRIO_LOW  = 0, /**< Low priority (interrupt B) */
    GIO_INT_PRIO_HIGH = 1  /**< High priority (interrupt A) */
} gio_int_priority_t;

/**
 * @brief GIO interrupt service routine callback type
 * @ingroup BSP_GIO
 */
typedef void (*gio_isr_t)(void);

/**
 * @brief Initialize the GIO peripheral
 * @ingroup BSP_GIO
 *
 * Enables the VCLK clock for GIO and brings the module out of reset.
 * Must be called before any other GIO functions.
 */
void gio_init(void);

/**
 * @brief Configure pin direction for a port
 * @ingroup BSP_GIO
 *
 * @param port Port identifier (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask of pins to configure (bit 0 = pin 0, etc.)
 * @param dir Direction (GIO_DIR_INPUT or GIO_DIR_OUTPUT)
 */
void gio_set_direction(gio_port_t port, uint8_t pin_mask, gio_dir_t dir);

/**
 * @brief Write data to output pins using DOUT register
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param value 8-bit value to write
 * @note Prefer gio_set_pins() or gio_clear_pins() to avoid read-modify-write hazards.
 */
void gio_write_port(gio_port_t port, uint8_t value);

/**
 * @brief Set (drive high) selected output pins
 * @ingroup BSP_GIO
 *
 * Uses the DSET register for atomic set operation.
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to set
 */
void gio_set_pins(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Clear (drive low) selected output pins
 * @ingroup BSP_GIO
 *
 * Uses the DCLR register for atomic clear operation.
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to clear
 */
void gio_clear_pins(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Read current input state of a port
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @return 8-bit input data
 */
uint8_t gio_read_port(gio_port_t port);

/**
 * @brief Toggle output pins
 * @ingroup BSP_GIO
 *
 * Reads current output state from DOUT and inverts the specified pins.
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to toggle
 */
void gio_toggle_pins(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Configure pull resistors for a port
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to configure
 * @param enable 1 to enable pull resistor, 0 to disable (high-impedance)
 * @param pull GIO_PULL_UP or GIO_PULL_DOWN (only relevant if enable=1)
 */
void gio_configure_pull(gio_port_t port, uint8_t pin_mask, uint32_t enable, gio_pull_t pull);

/**
 * @brief Configure output mode (push-pull or open-drain)
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to configure
 * @param mode GIO_OUTPUT_PUSHPULL or GIO_OUTPUT_OPENDRAIN
 */
void gio_set_output_mode(gio_port_t port, uint8_t pin_mask, gio_output_mode_t mode);

/**
 * @brief Configure interrupt detection mode
 * @ingroup BSP_GIO
 *
 * @param port Port identifier (only A and B support interrupts)
 * @param pin_mask Bit mask of pins to configure
 * @param detect GIO_INT_SINGLE_EDGE or GIO_INT_BOTH_EDGES
 */
void gio_set_interrupt_detect(gio_port_t port, uint8_t pin_mask, gio_int_detect_t detect);

/**
 * @brief Configure interrupt polarity (for single-edge mode)
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to configure
 * @param polarity GIO_INT_FALLING or GIO_INT_RISING
 */
void gio_set_interrupt_polarity(gio_port_t port, uint8_t pin_mask, gio_int_polarity_t polarity);

/**
 * @brief Set interrupt priority level for pins
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to configure
 * @param priority GIO_INT_PRIO_HIGH (interrupt A) or GIO_INT_PRIO_LOW (interrupt B)
 */
void gio_set_interrupt_priority(gio_port_t port, uint8_t pin_mask, gio_int_priority_t priority);

/**
 * @brief Enable interrupts for selected pins
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to enable interrupts for
 */
void gio_enable_interrupt(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Disable interrupts for selected pins
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of pins to disable interrupts for
 */
void gio_disable_interrupt(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Read and clear interrupt flags for a port
 * @ingroup BSP_GIO
 *
 * Reading the flag register shows which pins triggered an interrupt.
 * Writing 1 to a bit clears that flag.
 *
 * @param port Port identifier
 * @return 8-bit flag register value (1 = interrupt occurred)
 */
uint8_t gio_get_interrupt_flags(gio_port_t port);

/**
 * @brief Clear interrupt flags for selected pins
 * @ingroup BSP_GIO
 *
 * @param port Port identifier
 * @param pin_mask Bit mask of flags to clear
 */
void gio_clear_interrupt_flags(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Read high-priority interrupt offset register
 * @ingroup BSP_GIO
 *
 * Returns the offset (0-31) of the highest-priority pending interrupt.
 * Reading this register automatically clears the corresponding interrupt flag.
 *
 * @return Offset value (0-31)
 */
uint32_t gio_get_offset1(void);

/**
 * @brief Read low-priority interrupt offset register
 * @ingroup BSP_GIO
 *
 * Returns the offset (0-31) of the highest-priority pending low-priority interrupt.
 * Reading this register automatically clears the corresponding interrupt flag.
 *
 * @return Offset value (0-31)
 */
uint32_t gio_get_offset2(void);

/**
 * @brief Read high-priority emulation offset register
 * @ingroup BSP_GIO
 *
 * Returns the offset (0-31) of the highest-priority pending interrupt
 * WITHOUT clearing the interrupt flag (for debugging).
 *
 * @return Offset value (0-31)
 */
uint32_t gio_get_emu1(void);

/**
 * @brief Read low-priority emulation offset register
 * @ingroup BSP_GIO
 *
 * Returns the offset (0-31) of the highest-priority pending low-priority interrupt
 * WITHOUT clearing the interrupt flag (for debugging).
 *
 * @return Offset value (0-31)
 */
uint32_t gio_get_emu2(void);

/**
 * @brief Register ISR callback for GIO interrupt A (high-priority)
 * @ingroup BSP_GIO
 *
 * Registers a user callback with the VIM for GIO interrupt A (channel 9).
 *
 * @param isr Function pointer to interrupt service routine
 * @return 0 on success, non-zero on error
 */
int gio_register_isr_a(gio_isr_t isr);

/**
 * @brief Register ISR callback for GIO interrupt B (low-priority)
 * @ingroup BSP_GIO
 *
 * Registers a user callback with the VIM for GIO interrupt B (channel 23).
 *
 * @param isr Function pointer to interrupt service routine
 * @return 0 on success, non-zero on error
 */
int gio_register_isr_b(gio_isr_t isr);

/**
 * @brief Enable GIO interrupt A in VIM
 * @ingroup BSP_GIO
 *
 * @return 0 on success, non-zero on error
 */
int gio_enable_irq_a(void);

/**
 * @brief Enable GIO interrupt B in VIM
 * @ingroup BSP_GIO
 *
 * @return 0 on success, non-zero on error
 */
int gio_enable_irq_b(void);

/**
 * @brief Disable GIO interrupt A in VIM
 * @ingroup BSP_GIO
 *
 * @return 0 on success, non-zero on error
 */
int gio_disable_irq_a(void);

/**
 * @brief Disable GIO interrupt B in VIM
 * @ingroup BSP_GIO
 *
 * @return 0 on success, non-zero on error
 */
int gio_disable_irq_b(void);

/**
 * @brief Perform a simple loopback self-test on a port
 * @ingroup BSP_GIO
 *
 * Configures the specified port pins as outputs, writes a test pattern,
 * reads back from the DOUT register, and verifies the value.
 *
 * @param port Port identifier
 * @param pin_mask Pins to test (should be configured for loopback externally if needed)
 * @param test_pattern 8-bit test pattern to write
 * @return 0 on success (readback matches), non-zero on mismatch
 *
 * @warning This test writes to the port. Ensure pins are safe to drive.
 * @note For true loopback, external wiring or internal test mode may be required.
 */
int gio_self_test_loopback(gio_port_t port, uint8_t pin_mask, uint8_t test_pattern);

/** @} */ /* end of BSP_GIO */

#endif /* GIO_H */

