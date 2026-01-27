/**
 * @file gio.h
 * @brief General-Purpose Input/Output (GIO) Module Driver
 */

#ifndef GIO_H
#define GIO_H

#include <stdint.h>

/**
 * @defgroup BSP_GIO General-Purpose Input/Output (GIO)
 * @brief Driver for the GIO module providing GPIO and interrupt functionality.
 * @{
 */

/**
 * @brief GIO port enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PORT_A = 0, /**< GIO Port A (pins GIOA[7:0]) */
    GIO_PORT_B = 1  /**< GIO Port B (pins GIOB[7:0]) */
} gio_port_t;

/**
 * @brief GIO pin direction enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_DIR_INPUT  = 0, /**< Pin configured as input */
    GIO_DIR_OUTPUT = 1  /**< Pin configured as output */
} gio_dir_t;

/**
 * @brief GIO pin pull configuration enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PULL_DOWN = 0, /**< Pull-down enabled */
    GIO_PULL_UP   = 1  /**< Pull-up enabled */
} gio_pull_t;

/**
 * @brief GIO open drain mode enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PUSH_PULL  = 0, /**< Push-pull output mode */
    GIO_OPEN_DRAIN = 1  /**< Open drain output mode */
} gio_od_t;

/**
 * @brief GIO interrupt detection mode enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_INT_SINGLE_EDGE = 0, /**< Single edge detection (polarity controlled by GIOPOL) */
    GIO_INT_BOTH_EDGES  = 1  /**< Both edges detection */
} gio_int_det_t;

/**
 * @brief GIO interrupt polarity enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_POL_FALLING = 0, /**< Falling edge / Low level */
    GIO_POL_RISING  = 1  /**< Rising edge / High level */
} gio_int_pol_t;

/**
 * @brief GIO interrupt priority level enumeration
 * @ingroup BSP_GIO
 */
typedef enum {
    GIO_PRIO_LOW  = 0, /**< Low priority (interrupt B) */
    GIO_PRIO_HIGH = 1  /**< High priority (interrupt A) */
} gio_int_prio_t;

/**
 * @brief GIO interrupt service routine function pointer type
 * @ingroup BSP_GIO
 */
typedef void (*gio_isr_t)(void);

/**
 * @brief Initialize the GIO module.
 * @ingroup BSP_GIO
 *
 * Enables the VCLK clock for GIO and brings the module out of reset.
 * Must be called before using any other GIO functions.
 */
void gio_init(void);

/**
 * @brief Configure pin direction for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port    GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure (bit 0 = pin 0, etc.)
 * @param dir     Direction (GIO_DIR_INPUT or GIO_DIR_OUTPUT)
 */
void gio_set_direction(gio_port_t port, uint8_t pin_mask, gio_dir_t dir);

/**
 * @brief Read input data from a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port GIO port (GIO_PORT_A or GIO_PORT_B)
 * @return 8-bit input data value
 */
uint8_t gio_read_port(gio_port_t port);

/**
 * @brief Write output data to a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port  GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param value 8-bit output data value
 */
void gio_write_port(gio_port_t port, uint8_t value);

/**
 * @brief Set output bits for a GIO port.
 * @ingroup BSP_GIO
 *
 * Writes 1 to the GIODSET register to set corresponding GIODOUT bits.
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to set high
 */
void gio_set_bits(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Clear output bits for a GIO port.
 * @ingroup BSP_GIO
 *
 * Writes 1 to the GIODCLR register to clear corresponding GIODOUT bits.
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to clear
 */
void gio_clear_bits(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Toggle output bits for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to toggle
 */
void gio_toggle_bits(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Configure open drain mode for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure
 * @param mode     Open drain mode (GIO_PUSH_PULL or GIO_OPEN_DRAIN)
 */
void gio_set_open_drain(gio_port_t port, uint8_t pin_mask, gio_od_t mode);

/**
 * @brief Configure pull resistor enable for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure
 * @param enable   1 to enable pull resistors, 0 to disable
 */
void gio_set_pull_enable(gio_port_t port, uint8_t pin_mask, uint8_t enable);

/**
 * @brief Configure pull resistor direction for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure
 * @param pull     Pull direction (GIO_PULL_DOWN or GIO_PULL_UP)
 */
void gio_set_pull_select(gio_port_t port, uint8_t pin_mask, gio_pull_t pull);

/**
 * @brief Configure interrupt detection mode for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure
 * @param det      Detection mode (GIO_INT_SINGLE_EDGE or GIO_INT_BOTH_EDGES)
 */
void gio_set_int_detect(gio_port_t port, uint8_t pin_mask, gio_int_det_t det);

/**
 * @brief Configure interrupt polarity for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure
 * @param pol      Polarity (GIO_POL_FALLING or GIO_POL_RISING)
 */
void gio_set_int_polarity(gio_port_t port, uint8_t pin_mask, gio_int_pol_t pol);

/**
 * @brief Enable interrupts for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to enable interrupts for
 */
void gio_enable_int(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Disable interrupts for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to disable interrupts for
 */
void gio_disable_int(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Configure interrupt priority for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which pins to configure
 * @param prio     Priority level (GIO_PRIO_LOW or GIO_PRIO_HIGH)
 */
void gio_set_int_priority(gio_port_t port, uint8_t pin_mask, gio_int_prio_t prio);

/**
 * @brief Read interrupt flags for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port GIO port (GIO_PORT_A or GIO_PORT_B)
 * @return 8-bit interrupt flag value (1 = interrupt occurred)
 */
uint8_t gio_read_int_flags(gio_port_t port);

/**
 * @brief Clear interrupt flags for a GIO port.
 * @ingroup BSP_GIO
 *
 * @param port     GIO port (GIO_PORT_A or GIO_PORT_B)
 * @param pin_mask Bit mask indicating which interrupt flags to clear
 */
void gio_clear_int_flags(gio_port_t port, uint8_t pin_mask);

/**
 * @brief Read high-priority interrupt offset (GIOOFF1).
 * @ingroup BSP_GIO
 *
 * Reading this register returns the offset of the highest-priority pending
 * high-priority interrupt and clears that interrupt flag.
 *
 * @return 6-bit offset value (0–63)
 */
uint8_t gio_read_offset1(void);

/**
 * @brief Read low-priority interrupt offset (GIOOFF2).
 * @ingroup BSP_GIO
 *
 * Reading this register returns the offset of the highest-priority pending
 * low-priority interrupt and clears that interrupt flag.
 *
 * @return 6-bit offset value (0–63)
 */
uint8_t gio_read_offset2(void);

/**
 * @brief Read high-priority emulation offset (GIOEMU1).
 * @ingroup BSP_GIO
 *
 * Reading this register returns the offset of the highest-priority pending
 * high-priority interrupt WITHOUT clearing the interrupt flag.
 *
 * @return 6-bit offset value (0–63)
 */
uint8_t gio_read_emu1(void);

/**
 * @brief Read low-priority emulation offset (GIOEMU2).
 * @ingroup BSP_GIO
 *
 * Reading this register returns the offset of the highest-priority pending
 * low-priority interrupt WITHOUT clearing the interrupt flag.
 *
 * @return 6-bit offset value (0–63)
 */
uint8_t gio_read_emu2(void);

/**
 * @brief Register an interrupt service routine for a GIO VIM channel.
 * @ingroup BSP_GIO
 *
 * @param channel_id VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @param isr        Function pointer to interrupt service routine
 * @return 0 on success, negative on error
 */
int gio_register_isr(uint32_t channel_id, gio_isr_t isr);

/**
 * @brief Enable a GIO VIM channel.
 * @ingroup BSP_GIO
 *
 * @param channel_id VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @return 0 on success, negative on error
 */
int gio_enable_vim_channel(uint32_t channel_id);

/**
 * @brief Disable a GIO VIM channel.
 * @ingroup BSP_GIO
 *
 * @param channel_id VIM channel ID (9 for GIO_A, 23 for GIO_B)
 * @return 0 on success, negative on error
 */
int gio_disable_vim_channel(uint32_t channel_id);

/** @} */ /* end of BSP_GIO */

#endif /* GIO_H */

