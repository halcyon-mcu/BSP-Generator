/**
 * @file gio.h
 * @brief General-Purpose Input/Output (GIO) driver for TI RM46
 */

#ifndef GIO_H
#define GIO_H

#include <stdint.h>

/**
 * @defgroup BSP_GIO GIO
 * @brief General-Purpose Input/Output (GIO) driver
 * 
 * This module provides low-level control for the GIO peripheral, including
 * pin configuration, data I/O, interrupt management, and open-drain/pull
 * configuration for ports A and B.
 * @{
 */

/**
 * @brief GIO port identifiers
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PORT_A = 0, /**< Port A (GIOA[7:0]) */
    GIO_PORT_B = 1  /**< Port B (GIOB[7:0]) */
} gio_port_t;

/**
 * @brief GIO interrupt priority level
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_INT_PRIO_LOW  = 0, /**< Low-priority (Level B) */
    GIO_INT_PRIO_HIGH = 1  /**< High-priority (Level A) */
} gio_int_prio_t;

/**
 * @brief GIO interrupt detection mode
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_INT_EDGE_SINGLE = 0, /**< Single edge (polarity controlled by GIOPOL) */
    GIO_INT_EDGE_BOTH   = 1  /**< Both edges */
} gio_int_detect_t;

/**
 * @brief GIO interrupt polarity
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_INT_POL_FALLING = 0, /**< Falling edge (normal mode) / Low level (low-power) */
    GIO_INT_POL_RISING  = 1  /**< Rising edge (normal mode) / High level (low-power) */
} gio_int_pol_t;

/**
 * @brief GIO pin direction
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_DIR_INPUT  = 0, /**< Configure pin as input */
    GIO_DIR_OUTPUT = 1  /**< Configure pin as output */
} gio_dir_t;

/**
 * @brief GIO open-drain mode
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_MODE_PUSH_PULL = 0, /**< Push-pull output */
    GIO_MODE_OPEN_DRAIN = 1 /**< Open-drain output */
} gio_open_drain_t;

/**
 * @brief GIO pull configuration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PULL_DOWN = 0, /**< Pull-down enabled */
    GIO_PULL_UP   = 1  /**< Pull-up enabled */
} gio_pull_sel_t;

/**
 * @brief GIO interrupt service routine callback type
 * @ingroup BSP_GIO
 */
typedef void (*gio_isr_t)(void);

/**
 * @brief Initialize the GIO peripheral
 * @ingroup BSP_GIO
 * 
 * Enables the VCLK clock and brings the GIO module out of reset by setting
 * the RESET bit in GIOGCRO. Must be called before any other GIO functions.
 * 
 * @note This function does not configure individual pins. Use gio_set_direction()
 *       and other configuration functions after initialization.
 */
void gio_init(void);

/**
 * @brief Configure pin direction (input or output)
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins to configure (bits [7:0])
 * @param dir     Direction (input or output)
 */
void gio_set_direction(gio_port_t port, uint8_t pin_mask, gio_dir_t dir);

/**
 * @brief Read input data from a GIO port
 * @ingroup BSP_GIO
 * 
 * @param port  GIO port (A or B)
 * @return 8-bit input value from GIODIN register
 */
uint8_t gio_read_port(gio_port_t port);

/**
 * @brief Write output data to a GIO port
 * @ingroup BSP_GIO
 * 
 * Directly writes to the GIODOUT register. For atomic set/clear operations,
 * use gio_set_pins() or gio_clear_pins().
 * 
 * @param port  GIO port (A or B)
 * @param value 8-bit value to write to GIODOUT
 */
void gio_write_port(gio_port_t port, uint8_t value);

/**
 * @brief Atomically set output pins
 * @ingroup BSP_GIO
 * 
 * Uses the GIODSET register to set output bits without read-modify-write.
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins to set high (bits [7:0])
 */
void gio_set_pins(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Atomically clear output pins
 * @ingroup BSP_GIO
 * 
 * Uses the GIODCLR register to clear output bits without read-modify-write.
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins to clear low (bits [7:0])
 */
void gio_clear_pins(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Toggle output pins
 * @ingroup BSP_GIO
 * 
 * Reads current output state from GIODOUT and toggles specified pins.
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins to toggle (bits [7:0])
 */
void gio_toggle_pins(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Configure open-drain mode for pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 * @param mode    Push-pull or open-drain
 */
void gio_set_open_drain(gio_port_t port, uint8_t pin_mask, gio_open_drain_t mode);

/**
 * @brief Enable or disable pull resistors
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 * @param disable 0 to enable pull, 1 to disable pull
 */
void gio_set_pull_disable(gio_port_t port, uint8_t pin_mask, uint8_t disable);

/**
 * @brief Select pull-up or pull-down for pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 * @param sel     Pull-down or pull-up
 */
void gio_set_pull_select(gio_port_t port, uint8_t pin_mask, gio_pull_sel_t sel);

/**
 * @brief Configure interrupt detection mode for port pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 * @param detect  Single-edge or both-edges
 */
void gio_set_int_detect(gio_port_t port, uint8_t pin_mask, gio_int_detect_t detect);

/**
 * @brief Configure interrupt polarity for port pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 * @param pol     Falling/Low or Rising/High
 */
void gio_set_int_polarity(gio_port_t port, uint8_t pin_mask, gio_int_pol_t pol);

/**
 * @brief Enable interrupts for port pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 */
void gio_enable_int(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Disable interrupts for port pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 */
void gio_disable_int(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Set interrupt priority level for port pins
 * @ingroup BSP_GIO
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of pins (bits [7:0])
 * @param prio    High-priority (Level A) or Low-priority (Level B)
 */
void gio_set_int_priority(gio_port_t port, uint8_t pin_mask, gio_int_prio_t prio);

/**
 * @brief Read interrupt flags for a port
 * @ingroup BSP_GIO
 * 
 * @param port  GIO port (A or B)
 * @return 8-bit flag register value
 */
uint8_t gio_get_int_flags(gio_port_t port);

/**
 * @brief Clear interrupt flags for port pins
 * @ingroup BSP_GIO
 * 
 * Writes 1 to clear the corresponding flag bits.
 * 
 * @param port    GIO port (A or B)
 * @param pin_mask  Bitmask of flags to clear (bits [7:0])
 */
void gio_clear_int_flags(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Read high-priority interrupt offset
 * @ingroup BSP_GIO
 * 
 * Returns the offset of the highest-priority pending interrupt. Reading this
 * register clears the corresponding interrupt flag.
 * 
 * @return Offset [5:0] for high-priority interrupt
 */
uint32_t gio_read_offset1(void);

/**
 * @brief Read low-priority interrupt offset
 * @ingroup BSP_GIO
 * 
 * Returns the offset of the highest-priority pending low-priority interrupt.
 * Reading this register clears the corresponding interrupt flag.
 * 
 * @return Offset [5:0] for low-priority interrupt
 */
uint32_t gio_read_offset2(void);

/**
 * @brief Read emulation high-priority interrupt offset
 * @ingroup BSP_GIO
 * 
 * Similar to gio_read_offset1() but does not clear the interrupt flag.
 * 
 * @return Offset [5:0] for high-priority interrupt (emulation mode)
 */
uint32_t gio_read_emu1(void);

/**
 * @brief Read emulation low-priority interrupt offset
 * @ingroup BSP_GIO
 * 
 * Similar to gio_read_offset2() but does not clear the interrupt flag.
 * 
 * @return Offset [5:0] for low-priority interrupt (emulation mode)
 */
uint32_t gio_read_emu2(void);

/**
 * @brief Register an interrupt service routine for a GIO channel
 * @ingroup BSP_GIO
 * 
 * @param channel_id  VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @param isr         Callback function pointer
 * @return 0 on success, negative on error
 */
int gio_register_isr(uint32_t channel_id, gio_isr_t isr);

/**
 * @brief Enable a GIO interrupt channel in the VIM
 * @ingroup BSP_GIO
 * 
 * @param channel_id  VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @return 0 on success, negative on error
 */
int gio_enable_irq(uint32_t channel_id);

/**
 * @brief Disable a GIO interrupt channel in the VIM
 * @ingroup BSP_GIO
 * 
 * @param channel_id  VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @return 0 on success, negative on error
 */
int gio_disable_irq(uint32_t channel_id);

/** @} */ /* end of BSP_GIO */

#endif /* GIO_H */

