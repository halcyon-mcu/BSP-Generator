/**
 * @file gio.h
 * @brief GIO (General-Purpose Input/Output) Driver for TI RM46
 */

#ifndef GIO_H
#define GIO_H

#include <stdint.h>

/**
 * @defgroup BSP_GIO GIO (GPIO)
 * @brief General-Purpose Input/Output driver providing pin configuration, data I/O,
 *        interrupt management, and port control for the RM46 GIO module.
 * @{
 */

/**
 * @brief GIO port enumeration.
 */
typedef enum {
    GIO_PORT_A = 0, /**< GIO Port A */
    GIO_PORT_B = 1  /**< GIO Port B */
} gio_port_t;

/**
 * @brief GIO pin direction.
 */
typedef enum {
    GIO_DIR_INPUT  = 0, /**< Pin configured as input */
    GIO_DIR_OUTPUT = 1  /**< Pin configured as output */
} gio_dir_t;

/**
 * @brief GIO interrupt detection mode.
 */
typedef enum {
    GIO_INT_SINGLE_EDGE = 0, /**< Single edge detection (polarity set by GIOPOL) */
    GIO_INT_BOTH_EDGES  = 1  /**< Both edges detection */
} gio_int_det_t;

/**
 * @brief GIO interrupt polarity.
 */
typedef enum {
    GIO_POL_FALLING = 0, /**< Falling edge or low level */
    GIO_POL_RISING  = 1  /**< Rising edge or high level */
} gio_pol_t;

/**
 * @brief GIO interrupt priority level.
 */
typedef enum {
    GIO_INT_LOW  = 0, /**< Low priority (interrupt B) */
    GIO_INT_HIGH = 1  /**< High priority (interrupt A) */
} gio_int_lvl_t;

/**
 * @brief GIO open drain mode.
 */
typedef enum {
    GIO_PUSH_PULL  = 0, /**< Push-pull output */
    GIO_OPEN_DRAIN = 1  /**< Open drain output */
} gio_opendrain_t;

/**
 * @brief GIO pull configuration.
 */
typedef enum {
    GIO_PULL_DISABLED = 1, /**< Pull resistor disabled */
    GIO_PULL_ENABLED  = 0  /**< Pull resistor enabled (direction set by GIOPSL) */
} gio_pull_dis_t;

/**
 * @brief GIO pull direction.
 */
typedef enum {
    GIO_PULL_DOWN = 0, /**< Pull-down */
    GIO_PULL_UP   = 1  /**< Pull-up */
} gio_pull_sel_t;

/**
 * @brief GIO user ISR callback type.
 */
typedef void (*gio_isr_t)(void);

/**
 * @brief Initialize the GIO module.
 * @ingroup BSP_GIO
 *
 * This function enables the required VCLK clock and brings the GIO module
 * out of reset by setting the RESET bit in GIOGCR0.
 *
 * @note Must be called before any other GIO functions.
 */
void gio_init(void);

/**
 * @brief Configure pin direction for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port  GIO port (GIO_PORT_A or GIO_PORT_B).
 * @param mask  Bit mask of pins to configure.
 * @param dir   Direction (GIO_DIR_INPUT or GIO_DIR_OUTPUT).
 */
void gio_set_direction(gio_port_t port, uint8_t mask, gio_dir_t dir);

/**
 * @brief Write data to a GIO port output register.
 * @ingroup BSP_GIO
 *
 * This function writes to GIODOUTA or GIODOUTB. For atomic set/clear operations,
 * prefer gio_set_pins() or gio_clear_pins().
 *
 * @param port  GIO port.
 * @param value 8-bit value to write to the port.
 */
void gio_write_port(gio_port_t port, uint8_t value);

/**
 * @brief Read data from a GIO port input register.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @return 8-bit input data read from the port.
 */
uint8_t gio_read_port(gio_port_t port);

/**
 * @brief Atomically set output pins (write to GIODSET register).
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param mask Bit mask of pins to set high.
 */
void gio_set_pins(gio_port_t port, uint8_t mask);

/**
 * @brief Atomically clear output pins (write to GIODCLR register).
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param mask Bit mask of pins to clear low.
 */
void gio_clear_pins(gio_port_t port, uint8_t mask);

/**
 * @brief Configure open-drain mode for pins.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param mask Bit mask of pins to configure.
 * @param mode GIO_PUSH_PULL or GIO_OPEN_DRAIN.
 */
void gio_set_opendrain(gio_port_t port, uint8_t mask, gio_opendrain_t mode);

/**
 * @brief Enable or disable pull resistors.
 * @ingroup BSP_GIO
 *
 * @param port    GIO port.
 * @param mask    Bit mask of pins to configure.
 * @param pull_dis GIO_PULL_ENABLED or GIO_PULL_DISABLED.
 */
void gio_set_pull_disable(gio_port_t port, uint8_t mask, gio_pull_dis_t pull_dis);

/**
 * @brief Select pull direction (up or down).
 * @ingroup BSP_GIO
 *
 * @param port     GIO port.
 * @param mask     Bit mask of pins to configure.
 * @param pull_sel GIO_PULL_DOWN or GIO_PULL_UP.
 */
void gio_set_pull_select(gio_port_t port, uint8_t mask, gio_pull_sel_t pull_sel);

/**
 * @brief Configure interrupt detection mode for a pin.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param pin  Pin number (0-7).
 * @param det  GIO_INT_SINGLE_EDGE or GIO_INT_BOTH_EDGES.
 */
void gio_set_int_detect(gio_port_t port, uint8_t pin, gio_int_det_t det);

/**
 * @brief Configure interrupt polarity for a pin.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param pin  Pin number (0-7).
 * @param pol  GIO_POL_FALLING or GIO_POL_RISING.
 */
void gio_set_int_polarity(gio_port_t port, uint8_t pin, gio_pol_t pol);

/**
 * @brief Enable interrupt for a pin.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param pin  Pin number (0-7).
 */
void gio_enable_int(gio_port_t port, uint8_t pin);

/**
 * @brief Disable interrupt for a pin.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param pin  Pin number (0-7).
 */
void gio_disable_int(gio_port_t port, uint8_t pin);

/**
 * @brief Set interrupt priority level for a pin.
 * @ingroup BSP_GIO
 *
 * @param port GIO port.
 * @param pin  Pin number (0-7).
 * @param lvl  GIO_INT_LOW or GIO_INT_HIGH.
 */
void gio_set_int_level(gio_port_t port, uint8_t pin, gio_int_lvl_t lvl);

/**
 * @brief Read and clear interrupt flag for a pin.
 * @ingroup BSP_GIO
 *
 * Reads the GIOFLG register to check if an interrupt has occurred, then
 * clears the flag by writing 1.
 *
 * @param port GIO port.
 * @param pin  Pin number (0-7).
 * @return 1 if interrupt was pending, 0 otherwise.
 */
uint8_t gio_get_and_clear_int_flag(gio_port_t port, uint8_t pin);

/**
 * @brief Read the high-priority interrupt offset (GIOOFF1).
 * @ingroup BSP_GIO
 *
 * Reading this register clears the pending interrupt.
 *
 * @return Offset index [0-31] of the pending high-priority interrupt.
 */
uint8_t gio_get_offset1(void);

/**
 * @brief Read the low-priority interrupt offset (GIOOFF2).
 * @ingroup BSP_GIO
 *
 * Reading this register clears the pending interrupt.
 *
 * @return Offset index [0-31] of the pending low-priority interrupt.
 */
uint8_t gio_get_offset2(void);

/**
 * @brief Read the emulation high-priority interrupt offset (GIOEMU1).
 * @ingroup BSP_GIO
 *
 * Reading this register does NOT clear the pending interrupt.
 *
 * @return Offset index [0-31] of the pending high-priority interrupt.
 */
uint8_t gio_get_emu1(void);

/**
 * @brief Read the emulation low-priority interrupt offset (GIOEMU2).
 * @ingroup BSP_GIO
 *
 * Reading this register does NOT clear the pending interrupt.
 *
 * @return Offset index [0-31] of the pending low-priority interrupt.
 */
uint8_t gio_get_emu2(void);

/**
 * @brief Register ISR callback and enable the GIO high-priority (A) interrupt channel.
 * @ingroup BSP_GIO
 *
 * This function registers the user ISR with the VIM and enables VIM channel 9 (GIO_A).
 *
 * @param isr User ISR callback.
 * @return 0 on success, non-zero on failure.
 */
int gio_register_isr_a(gio_isr_t isr);

/**
 * @brief Register ISR callback and enable the GIO low-priority (B) interrupt channel.
 * @ingroup BSP_GIO
 *
 * This function registers the user ISR with the VIM and enables VIM channel 23 (GIO_B).
 *
 * @param isr User ISR callback.
 * @return 0 on success, non-zero on failure.
 */
int gio_register_isr_b(gio_isr_t isr);

/**
 * @brief Disable the GIO high-priority (A) interrupt channel in the VIM.
 * @ingroup BSP_GIO
 *
 * @return 0 on success, non-zero on failure.
 */
int gio_disable_irq_a(void);

/**
 * @brief Disable the GIO low-priority (B) interrupt channel in the VIM.
 * @ingroup BSP_GIO
 *
 * @return 0 on success, non-zero on failure.
 */
int gio_disable_irq_b(void);

/** @} */ /* end of BSP_GIO */

#endif /* GIO_H */

