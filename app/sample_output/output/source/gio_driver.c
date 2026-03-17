/* BSP-GEN-META: created_at=2026-03-04T23:26:36-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file gio_driver.c
 * @brief GIO peripheral driver implementation
 * @details Complete implementation including initialization, configuration,
 *          and operational functions for the GIO (General-Purpose Input/Output) module.
 */

#include "gio_driver.h"
#include "reg_gio.h"
#include "iomm_driver.h"
#include <stddef.h>

/* Base address for GIO peripheral */
#define GIO_BASE_ADDR (0xFFF7BC00U)
#define GIO ((GIO_REG_MAP_t *)GIO_BASE_ADDR)

/* Maximum pins per port */
#define GIO_MAX_PINS_PER_PORT (8U)

/* Interrupt callback storage */
static gio_interrupt_callback_t g_interrupt_callbacks[2][GIO_MAX_PINS_PER_PORT];

/* Static helper functions */
static volatile uint32_t* GIO_GetDirReg(gio_port_t port);
static volatile uint32_t* GIO_GetDinReg(gio_port_t port);
static volatile uint32_t* GIO_GetDoutReg(gio_port_t port);
static volatile uint32_t* GIO_GetDsetReg(gio_port_t port);
static volatile uint32_t* GIO_GetDclrReg(gio_port_t port);
static volatile uint32_t* GIO_GetPdrReg(gio_port_t port);
static volatile uint32_t* GIO_GetPuldisReg(gio_port_t port);
static volatile uint32_t* GIO_GetPslReg(gio_port_t port);

/**
 * @brief Initialize the GIO module
 * @details Configure clock control register and set up default port configuration.
 *          Initializes GIO global control register, clears all int_type flags,
 *          and resets int_type callbacks.
 *
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Initialization successful
 */
gio_status_t GIO_Init(void)
{
    uint32_t i;
    uint32_t j;

    /* Initialize GIO global control register */
    GIO->GIOGCR0 = 0x00000001U;

    /* Clear all int_type flags */
    GIO->GIOFLG = 0xFFFFFFFFU;

    /* Initialize all ports to default state (all pins as inputs) */
    GIO->GIODIRA = 0x00000000U;
    GIO->GIODIRB = 0x00000000U;

    /* Disable all pull resistors by default */
    GIO->GIOPULDISA = 0xFFFFFFFFU;
    GIO->GIOPULDISB = 0xFFFFFFFFU;

    /* Set all pins to push-pull mode */
    GIO->GIOPDRA = 0x00000000U;
    GIO->GIOPDRB = 0x00000000U;

    /* Clear all int_type enables */
    GIO->GIOENACLR = 0xFFFFFFFFU;

    /* Initialize int_type callbacks to NULL */
    for (i = 0; i < 2; i++) {
        for (j = 0; j < GIO_MAX_PINS_PER_PORT; j++) {
            g_interrupt_callbacks[i][j] = NULL;
        }
    }

    return GIO_STATUS_OK;
}

/**
 * @brief Configure a single GPIO pin
 * @details Configure pin direction, pull resistors, drive mode, and initial output value.
 *          Configures all pin attributes in a single operation.
 *
 * @param config Pointer to pin configuration structure
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Configuration successful
 * @retval GIO_STATUS_ERROR Configuration failed (NULL pointer)
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_ConfigurePin(const gio_pin_config_t* config)
{
    volatile uint32_t* dir_reg;
    volatile uint32_t* puldis_reg;
    volatile uint32_t* psl_reg;
    volatile uint32_t* pdr_reg;
    volatile uint32_t* dout_reg;
    uint32_t pin_mask;

    if (config == NULL) {
        return GIO_STATUS_ERROR;
    }

    if (config->pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (config->port != GIO_PORT_A && config->port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << config->pin;

    /* Get register pointers for the specified port */
    dir_reg = GIO_GetDirReg(config->port);
    puldis_reg = GIO_GetPuldisReg(config->port);
    psl_reg = GIO_GetPslReg(config->port);
    pdr_reg = GIO_GetPdrReg(config->port);
    dout_reg = GIO_GetDoutReg(config->port);

    /* Configure direction */
    if (config->direction == GIO_DIRECTION_OUTPUT) {
        *dir_reg |= pin_mask;
    } else {
        *dir_reg &= ~pin_mask;
    }

    /* Configure pull resistors */
    if (config->pull == GIO_PULL_DISABLE) {
        *puldis_reg |= pin_mask;
    } else {
        *puldis_reg &= ~pin_mask;
        if (config->pull == GIO_PULL_UP) {
            *psl_reg |= pin_mask;
        } else {
            *psl_reg &= ~pin_mask;
        }
    }

    /* Configure drive mode */
    if (config->drive == GIO_DRIVE_OPEN_DRAIN) {
        *pdr_reg |= pin_mask;
    } else {
        *pdr_reg &= ~pin_mask;
    }

    /* Set initial output value if configured as output */
    if (config->direction == GIO_DIRECTION_OUTPUT) {
        if (config->initial_value) {
            *dout_reg |= pin_mask;
        } else {
            *dout_reg &= ~pin_mask;
        }
    }

    return GIO_STATUS_OK;
}

/**
 * @brief Write a digital value to an output pin
 * @details Set or clear a specific GPIO pin output state.
 *
 * @param port GIO port identifier
 * @param pin Pin number (0-7)
 * @param value Output value (true = high, false = low)
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Write successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_WritePin(gio_port_t port, uint8_t pin, bool value)
{
    volatile uint32_t* dset_reg;
    volatile uint32_t* dclr_reg;
    uint32_t pin_mask;

    if (pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << pin;
    dset_reg = GIO_GetDsetReg(port);
    dclr_reg = GIO_GetDclrReg(port);

    if (value) {
        *dset_reg = pin_mask;
    } else {
        *dclr_reg = pin_mask;
    }

    return GIO_STATUS_OK;
}

/**
 * @brief Read the current state of a GPIO pin
 * @details Read input data register for the specified pin.
 *
 * @param port GIO port identifier
 * @param pin Pin number (0-7)
 * @return bool Pin state (true = high, false = low)
 */
bool GIO_ReadPin(gio_port_t port, uint8_t pin)
{
    volatile uint32_t* din_reg;
    uint32_t pin_mask;
    uint32_t reg_value;

    if (pin >= GIO_MAX_PINS_PER_PORT) {
        return false;
    }

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return false;
    }

    pin_mask = 1U << pin;
    din_reg = GIO_GetDinReg(port);
    reg_value = *din_reg;

    return (reg_value & pin_mask) != 0U;
}

/**
 * @brief Toggle the output state of a GPIO pin
 * @details Read current output state and invert it.
 *
 * @param port GIO port identifier
 * @param pin Pin number (0-7)
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Toggle successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_TogglePin(gio_port_t port, uint8_t pin)
{
    volatile uint32_t* dout_reg;
    uint32_t pin_mask;
    uint32_t reg_value;

    if (pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << pin;
    dout_reg = GIO_GetDoutReg(port);
    reg_value = *dout_reg;

    *dout_reg = reg_value ^ pin_mask;

    return GIO_STATUS_OK;
}

/**
 * @brief Write a 32-bit value to an entire GPIO port
 * @details Write all pins of a port simultaneously.
 *
 * @param port GIO port identifier
 * @param value 32-bit value to write
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Write successful
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_WritePort(gio_port_t port, uint32_t value)
{
    volatile uint32_t* dout_reg;

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    dout_reg = GIO_GetDoutReg(port);
    *dout_reg = value;

    return GIO_STATUS_OK;
}

/**
 * @brief Read the current state of an entire GPIO port
 * @details Read all pins of a port as a 32-bit value.
 *
 * @param port GIO port identifier
 * @return uint32_t Port state value
 */
uint32_t GIO_ReadPort(gio_port_t port)
{
    volatile uint32_t* din_reg;

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return 0U;
    }

    din_reg = GIO_GetDinReg(port);
    return *din_reg;
}

/**
 * @brief Configure int_type settings for a GPIO pin
 * @details Configure edge/level detection, polarity, and callback function.
 *
 * @param config Pointer to int_type configuration structure
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Configuration successful
 * @retval GIO_STATUS_ERROR Configuration failed (NULL pointer)
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_ConfigureInterrupt(const gio_interrupt_config_t* config)
{
    uint32_t pin_mask;
    uint32_t port_offset;
    uint32_t intdet_value;
    uint32_t pol_value;
    uint32_t lvl_value;

    if (config == NULL) {
        return GIO_STATUS_ERROR;
    }

    if (config->pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (config->port != GIO_PORT_A && config->port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << config->pin;
    port_offset = (config->port == GIO_PORT_A) ? 0U : 8U;

    /* Configure int_type detection mode */
    intdet_value = GIO->GIOINTDET;
    if (config->edge == GIO_INT_BOTH_EDGES) {
        intdet_value |= (pin_mask << port_offset);
    } else {
        intdet_value &= ~(pin_mask << port_offset);
    }
    GIO->GIOINTDET = intdet_value;

    /* Configure polarity */
    pol_value = GIO->GIOPOL;
    if (config->edge == GIO_INT_RISING_EDGE) {
        pol_value |= (pin_mask << port_offset);
    } else {
        pol_value &= ~(pin_mask << port_offset);
    }
    GIO->GIOPOL = pol_value;

    /* Configure level detection */
    lvl_value = GIO->GIOLVLSET;
    if (config->level == GIO_INT_LEVEL_HIGH) {
        GIO->GIOLVLSET = (pin_mask << port_offset);
    } else {
        GIO->GIOLVLCLR = (pin_mask << port_offset);
    }

    /* Store callback function */
    g_interrupt_callbacks[config->port][config->pin] = config->callback;

    /* Clear any pending int_type flag */
    GIO->GIOFLG = (pin_mask << port_offset);

    return GIO_STATUS_OK;
}

/**
 * @brief Enable int_type for a specific GPIO pin
 * @details Enable int_type generation for the specified pin.
 *
 * @param port GIO port identifier
 * @param pin Pin number (0-7)
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Enable successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_EnableInterrupt(gio_port_t port, uint8_t pin)
{
    uint32_t pin_mask;
    uint32_t port_offset;

    if (pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << pin;
    port_offset = (port == GIO_PORT_A) ? 0U : 8U;

    GIO->GIOENASET = (pin_mask << port_offset);

    return GIO_STATUS_OK;
}

/**
 * @brief Disable int_type for a specific GPIO pin
 * @details Disable int_type generation for the specified pin.
 *
 * @param port GIO port identifier
 * @param pin Pin number (0-7)
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Disable successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_DisableInterrupt(gio_port_t port, uint8_t pin)
{
    uint32_t pin_mask;
    uint32_t port_offset;

    if (pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << pin;
    port_offset = (port == GIO_PORT_A) ? 0U : 8U;

    GIO->GIOENACLR = (pin_mask << port_offset);

    return GIO_STATUS_OK;
}

/**
 * @brief Clear the int_type flag for a specific GPIO pin
 * @details Clear pending int_type flag by writing 1 to the flag register.
 *
 * @param port GIO port identifier
 * @param pin Pin number (0-7)
 * @return gio_status_t Status code
 * @retval GIO_STATUS_OK Clear successful
 * @retval GIO_STATUS_INVALID_PIN Invalid pin number
 * @retval GIO_STATUS_INVALID_PORT Invalid port
 */
gio_status_t GIO_ClearInterruptFlag(gio_port_t port, uint8_t pin)
{
    uint32_t pin_mask;
    uint32_t port_offset;

    if (pin >= GIO_MAX_PINS_PER_PORT) {
        return GIO_STATUS_INVALID_PIN;
    }

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return GIO_STATUS_INVALID_PORT;
    }

    pin_mask = 1U << pin;
    port_offset = (port == GIO_PORT_A) ? 0U : 8U;

    GIO->GIOFLG = (pin_mask << port_offset);

    return GIO_STATUS_OK;
}

/**
 * @brief Get the int_type status register for a GPIO port
 * @details Read the int_type flag register for the specified port.
 *
 * @param port GIO port identifier
 * @return uint32_t Interrupt status value (8 bits per port)
 */
uint32_t GIO_GetInterruptStatus(gio_port_t port)
{
    uint32_t port_offset;
    uint32_t status;

    if (port != GIO_PORT_A && port != GIO_PORT_B) {
        return 0U;
    }

    port_offset = (port == GIO_PORT_A) ? 0U : 8U;
    status = (GIO->GIOFLG >> port_offset) & 0xFFU;

    return status;
}

/**
 * @brief Configure IOMM pins for GIO module
 * @details Unlock IOMM, configure GPIO pins to GPIO function (AF0),
 *          then lock IOMM registers.
 */
void GIO_EnablePins(void)
{
    iomm_status_t status;

    /* Unlock IOMM registers */
    IOMM_Unlock();

    /* Configure GIOB[2] - Package pin 55, PINMMR9[18], AF2 */
    status = IOMM_ConfigurePin(55, IOMM_PIN_FUNCTION_2);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOB[1] - Package pin 133, PINMMR21[8], AF0 */
    status = IOMM_ConfigurePin(133, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOB[3] - Package pin 132, PINMMR0[0], AF0 */
    status = IOMM_ConfigurePin(132, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOB[0] - Package pin 128, PINMMR18[24], AF0 */
    status = IOMM_ConfigurePin(128, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[0] - Package pin 5, PINMMR0[8], AF0 */
    status = IOMM_ConfigurePin(5, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[1] - Package pin 15, PINMMR1[0], AF0 */
    status = IOMM_ConfigurePin(15, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[2] - Package pin 14, PINMMR2[0], AF0 */
    status = IOMM_ConfigurePin(14, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[3] - Package pin 16, PINMMR2[16], AF0 */
    status = IOMM_ConfigurePin(16, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[5] - Package pin 22, PINMMR2[24], AF0 */
    status = IOMM_ConfigurePin(22, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[6] - Package pin 25, PINMMR3[16], AF0 */
    status = IOMM_ConfigurePin(25, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure GIOA[7] - Package pin 23, PINMMR4[0], AF0 */
    status = IOMM_ConfigurePin(23, IOMM_PIN_FUNCTION_0);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Lock IOMM registers */
    IOMM_Lock();
}

/* Static helper functions implementation */

/**
 * @brief Get direction register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetDirReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIODIRA : &GIO->GIODIRB;
}

/**
 * @brief Get data input register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetDinReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIODINA : &GIO->GIODINB;
}

/**
 * @brief Get data output register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetDoutReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIODOUTA : &GIO->GIODOUTB;
}

/**
 * @brief Get data set register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetDsetReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIODSETA : &GIO->GIODSETB;
}

/**
 * @brief Get data clear register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetDclrReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIODCLRA : &GIO->GIODCLRB;
}

/**
 * @brief Get open drain register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetPdrReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIOPDRA : &GIO->GIOPDRB;
}

/**
 * @brief Get pull disable register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetPuldisReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIOPULDISA : &GIO->GIOPULDISB;
}

/**
 * @brief Get pull select register for specified port
 * @internal
 */
static volatile uint32_t* GIO_GetPslReg(gio_port_t port)
{
    return (port == GIO_PORT_A) ? &GIO->GIOPSLA : &GIO->GIOPSLB;
}
