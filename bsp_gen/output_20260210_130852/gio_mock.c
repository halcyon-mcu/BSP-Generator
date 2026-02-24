/**
 * @file gio_mock.c
 * @brief Mock hardware register implementations for GPIO testing
 */

#include "gio_mock.h"
#include <string.h>

/* ============================================================================
 * Mock Register Instance (Global)
 * ========================================================================== */

gio_mock_registers_t gio_mock_regs = {0};

/* ============================================================================
 * Mock Implementation Functions
 * ========================================================================== */

void gio_mock_init(void)
{
    /**
     * Initialize mock registers to default safe state:
     * - All pins set to input mode
     * - All outputs are low
     * - Interrupts disabled
     */
    memset(&gio_mock_regs, 0, sizeof(gio_mock_regs));

    /* Set all pins as inputs (DIR=1) by default */
    gio_mock_regs.GIO_DIR_A = 0xFFFFFFFFU;
    gio_mock_regs.GIO_DIR_B = 0xFFFFFFFFU;

    /* Data lines start low */
    gio_mock_regs.GIO_DOUT_A = 0x00000000U;
    gio_mock_regs.GIO_DOUT_B = 0x00000000U;

    /* Input state reflects output state initially */
    gio_mock_regs.GIO_DIN_A = gio_mock_regs.GIO_DOUT_A;
    gio_mock_regs.GIO_DIN_B = gio_mock_regs.GIO_DOUT_B;
}

void gio_mock_reset(void)
{
    /**
     * Hard reset - clears all mock state
     */
    memset(&gio_mock_regs, 0, sizeof(gio_mock_regs));
}

void gio_mock_set_pin(uint8_t port, uint8_t pin)
{
    /**
     * Set a pin high in the output register
     * This updates both DOUT and DIN to simulate the actual pin state
     */
    if (pin > 31)
        return; /* Invalid pin */

    uint32_t mask = (1U << pin);

    if (port == 0)
    {
        gio_mock_regs.GIO_DOUT_A |= mask;
        gio_mock_regs.GIO_DIN_A |= mask;
    }
    else if (port == 1)
    {
        gio_mock_regs.GIO_DOUT_B |= mask;
        gio_mock_regs.GIO_DIN_B |= mask;
    }
}

void gio_mock_clear_pin(uint8_t port, uint8_t pin)
{
    /**
     * Clear a pin (set to low) in the output register
     */
    if (pin > 31)
        return; /* Invalid pin */

    uint32_t mask = (1U << pin);

    if (port == 0)
    {
        gio_mock_regs.GIO_DOUT_A &= ~mask;
        gio_mock_regs.GIO_DIN_A &= ~mask;
    }
    else if (port == 1)
    {
        gio_mock_regs.GIO_DOUT_B &= ~mask;
        gio_mock_regs.GIO_DIN_B &= ~mask;
    }
}

bool gio_mock_read_pin(uint8_t port, uint8_t pin)
{
    /**
     * Read the current state of a GPIO pin
     */
    if (pin > 31)
        return false;

    uint32_t mask = (1U << pin);
    uint32_t reg_value = 0;

    if (port == 0)
    {
        reg_value = gio_mock_regs.GIO_DIN_A;
    }
    else if (port == 1)
    {
        reg_value = gio_mock_regs.GIO_DIN_B;
    }

    return (reg_value & mask) != 0;
}

void gio_mock_write_port(uint8_t port, uint32_t mask)
{
    /**
     * Write multiple pins at once using a bitmask
     */
    if (port == 0)
    {
        gio_mock_regs.GIO_DOUT_A = mask;
        gio_mock_regs.GIO_DIN_A = mask;
    }
    else if (port == 1)
    {
        gio_mock_regs.GIO_DOUT_B = mask;
        gio_mock_regs.GIO_DIN_B = mask;
    }
}

uint32_t gio_mock_read_port(uint8_t port)
{
    /**
     * Read the entire port state
     */
    if (port == 0)
    {
        return gio_mock_regs.GIO_DIN_A;
    }
    else if (port == 1)
    {
        return gio_mock_regs.GIO_DIN_B;
    }

    return 0;
}

bool gio_mock_verify_pin(uint8_t port, uint8_t pin, bool expected)
{
    /**
     * Verify that a pin has the expected state
     * Useful for test assertions
     */
    bool actual = gio_mock_read_pin(port, pin);
    return actual == expected;
}
