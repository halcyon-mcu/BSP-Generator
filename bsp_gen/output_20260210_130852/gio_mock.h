/**
 * @file gio_mock.h
 * @brief Mock hardware register definitions for GPIO (GIO) testing
 *
 * This header provides mock implementations of hardware registers
 * to enable unit testing without actual hardware.
 */

#ifndef GIO_MOCK_H
#define GIO_MOCK_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/* ============================================================================
 * Mock Register Structure
 * ========================================================================== */

/**
 * @brief Mock GIO register set
 *
 * Simulates the actual TI RM46 GIO hardware registers in RAM
 */
typedef struct
{
    uint32_t GIO_GCTR_A;     /*!< Port A Global Control */
    uint32_t GIO_GINTFLAG_A; /*!< Port A Global Interrupt Flag */
    uint32_t GIO_GINTLVL_A;  /*!< Port A Global Interrupt Level */
    uint32_t GIO_GINTPOL_A;  /*!< Port A Global Interrupt Polarity */
    uint32_t GIO_INTCTRL;    /*!< Interrupt Control */

    uint32_t GIO_DIR_A;  /*!< Port A Direction (0=output, 1=input) */
    uint32_t GIO_DIN_A;  /*!< Port A Data In (read actual pin state) */
    uint32_t GIO_DOUT_A; /*!< Port A Data Out (write pin state) */
    uint32_t GIO_DSET_A; /*!< Port A Data Set */
    uint32_t GIO_DCLR_A; /*!< Port A Data Clear */

    uint32_t GIO_PDR_A;    /*!< Port A Pull Disable */
    uint32_t GIO_PULDIS_A; /*!< Port A Pull Disable Control */

    uint32_t GIO_DIR_B;  /*!< Port B Direction */
    uint32_t GIO_DIN_B;  /*!< Port B Data In */
    uint32_t GIO_DOUT_B; /*!< Port B Data Out */
    uint32_t GIO_DSET_B; /*!< Port B Data Set */
    uint32_t GIO_DCLR_B; /*!< Port B Data Clear */
} gio_mock_registers_t;

/* ============================================================================
 * Mock Register Instance
 * ========================================================================== */

extern gio_mock_registers_t gio_mock_regs;

/* ============================================================================
 * Mock Helper Functions
 * ========================================================================== */

/**
 * @brief Initialize mock GIO registers to default state
 */
void gio_mock_init(void);

/**
 * @brief Reset all mock registers to zero
 */
void gio_mock_reset(void);

/**
 * @brief Set a GPIO pin to high in the mock
 * @param port Port number (0 or 1)
 * @param pin Pin number (0-31)
 */
void gio_mock_set_pin(uint8_t port, uint8_t pin);

/**
 * @brief Clear a GPIO pin to low in the mock
 * @param port Port number (0 or 1)
 * @param pin Pin number (0-31)
 */
void gio_mock_clear_pin(uint8_t port, uint8_t pin);

/**
 * @brief Read a GPIO pin state from the mock
 * @param port Port number (0 or 1)
 * @param pin Pin number (0-31)
 * @return true if pin is high, false if low
 */
bool gio_mock_read_pin(uint8_t port, uint8_t pin);

/**
 * @brief Set multiple pins at once
 * @param port Port number (0 or 1)
 * @param mask Bitmask of pins to set (1 = set to high)
 */
void gio_mock_write_port(uint8_t port, uint32_t mask);

/**
 * @brief Read entire port state
 * @param port Port number (0 or 1)
 * @return Register value showing pin states
 */
uint32_t gio_mock_read_port(uint8_t port);

/**
 * @brief Verify that a pin was set to the expected state
 * @param port Port number (0 or 1)
 * @param pin Pin number (0-31)
 * @param expected Expected state (true=high, false=low)
 * @return true if pin matches expected state
 */
bool gio_mock_verify_pin(uint8_t port, uint8_t pin, bool expected);

#endif /* GIO_MOCK_H */
