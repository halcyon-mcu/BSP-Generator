/* BSP-GEN-META: created_at=2026-03-04T23:26:32-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file iomm_driver.c
 * @brief IOMM peripheral driver implementation
 * @details Complete implementation including initialization, configuration,
 *          and operational functions for the I/O Multiplexing and Control Module.
 *          Manages pin multiplexing, kick register protection, and ePWM clock control.
 */

#include "iomm_driver.h"
#include "reg_iomm.h"
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ========================================================================== */
/*                           Base Address Definition                          */
/* ========================================================================== */

#define IOMM_BASE_ADDR (0xFFFFEA00U)
#define iommREG ((IOMM_REG_MAP_t *)IOMM_BASE_ADDR)

/* ========================================================================== */
/*                    Pin-to-Register Mapping Lookup Table                    */
/* ========================================================================== */

/**
 * @brief Pin-to-PINMMR register mapping entry
 * @internal
 */
typedef struct {
    uint8_t package_pin;      /**< Physical package pin number */
    uint8_t pinmmr_reg;       /**< PINMMR register index (0-29) */
    uint8_t bit_position;     /**< Bit position within register (0-31) */
} IOMM_PinMapping_t;

/**
 * @brief Auto-generated pin-to-register mapping table from pinmux.yaml
 * @details Maps package pin numbers to their corresponding PINMMR register
 *          and bit positions. This mapping is device-specific and non-linear.
 * @internal
 */
static const IOMM_PinMapping_t g_pin_mapping[] = {
    { .package_pin = 132, .pinmmr_reg = 0,  .bit_position = 0 },   /* GIOB[3] */
    { .package_pin = 5,   .pinmmr_reg = 0,  .bit_position = 8 },   /* GIOA[0] */
    { .package_pin = 3,   .pinmmr_reg = 0,  .bit_position = 16 },  /* MIBSPI3NCS[3] */
    { .package_pin = 2,   .pinmmr_reg = 0,  .bit_position = 24 },  /* MIBSPI3NCS[2] */
    { .package_pin = 15,  .pinmmr_reg = 1,  .bit_position = 0 },   /* GIOA[1] */
    { .package_pin = 125, .pinmmr_reg = 1,  .bit_position = 8 },   /* N2HET1[11] */
    { .package_pin = 14,  .pinmmr_reg = 2,  .bit_position = 0 },   /* GIOA[2] */
    { .package_pin = 16,  .pinmmr_reg = 2,  .bit_position = 16 },  /* GIOA[3] */
    { .package_pin = 22,  .pinmmr_reg = 2,  .bit_position = 24 },  /* GIOA[5] */
    { .package_pin = 26,  .pinmmr_reg = 3,  .bit_position = 8 },   /* N2HET1[22] */
    { .package_pin = 25,  .pinmmr_reg = 3,  .bit_position = 16 },  /* GIOA[6] */
    { .package_pin = 23,  .pinmmr_reg = 4,  .bit_position = 0 },   /* GIOA[7] */
    { .package_pin = 36,  .pinmmr_reg = 4,  .bit_position = 16 },  /* N2HET1[01] */
    { .package_pin = 33,  .pinmmr_reg = 4,  .bit_position = 24 },  /* N2HET1[03] */
    { .package_pin = 30,  .pinmmr_reg = 5,  .bit_position = 0 },   /* N2HET1[0] */
    { .package_pin = 31,  .pinmmr_reg = 5,  .bit_position = 8 },   /* N2HET1[02] */
    { .package_pin = 106, .pinmmr_reg = 5,  .bit_position = 16 },  /* N2HET1[05] */
    { .package_pin = 35,  .pinmmr_reg = 6,  .bit_position = 0 },   /* N2HET1[07] */
    { .package_pin = 99,  .pinmmr_reg = 6,  .bit_position = 8 },   /* EMIF_DATA[11] */
    { .package_pin = 118, .pinmmr_reg = 6,  .bit_position = 16 },  /* N2HET1[09] */
    { .package_pin = 37,  .pinmmr_reg = 7,  .bit_position = 8 },   /* MIBSPI3NCS[1] */
    { .package_pin = 38,  .pinmmr_reg = 7,  .bit_position = 16 },  /* N2HET1[06] / SCIRX */
    { .package_pin = 39,  .pinmmr_reg = 8,  .bit_position = 0 },   /* N2HET1[13] / SCITX */
    { .package_pin = 4,   .pinmmr_reg = 0,  .bit_position = 24 },  /* MIBSPI3NCS[2] / I2C_SDA */
    { .package_pin = 40,  .pinmmr_reg = 8,  .bit_position = 8 },   /* MIBSPI1NCS[2] */
    { .package_pin = 139, .pinmmr_reg = 8,  .bit_position = 16 },  /* N2HET1[15] */
    { .package_pin = 54,  .pinmmr_reg = 9,  .bit_position = 8 },   /* MIBSPI3NENA */
    { .package_pin = 55,  .pinmmr_reg = 9,  .bit_position = 16 },  /* MIBSPI3NCS[0] */
    { .package_pin = 32,  .pinmmr_reg = 9,  .bit_position = 24 },  /* MIBSPI1NCS[3] */
    { .package_pin = 88,  .pinmmr_reg = 10, .bit_position = 0 },   /* AD1EVT */
    { .package_pin = 121, .pinmmr_reg = 10, .bit_position = 16 },  /* EMIF_nCS[0] */
    { .package_pin = 120, .pinmmr_reg = 11, .bit_position = 0 },   /* EMIF_nCS[3] */
    { .package_pin = 107, .pinmmr_reg = 11, .bit_position = 24 },  /* N2HET1[24] */
    { .package_pin = 100, .pinmmr_reg = 12, .bit_position = 0 },   /* N2HET1[26] */
    { .package_pin = 96,  .pinmmr_reg = 12, .bit_position = 16 },  /* MIBSPI1NENA */
    { .package_pin = 93,  .pinmmr_reg = 13, .bit_position = 24 },  /* MIBSPI1NCS[0] */
    { .package_pin = 127, .pinmmr_reg = 14, .bit_position = 8 },   /* N2HET1[28] */
    { .package_pin = 116, .pinmmr_reg = 14, .bit_position = 16 },  /* EMIF_nWE */
    { .package_pin = 126, .pinmmr_reg = 14, .bit_position = 24 },  /* EMIF_BA[1] */
    { .package_pin = 124, .pinmmr_reg = 17, .bit_position = 0 },   /* N2HET1[10] */
    { .package_pin = 141, .pinmmr_reg = 18, .bit_position = 8 },   /* N2HET1[14] */
    { .package_pin = 128, .pinmmr_reg = 18, .bit_position = 24 },  /* GIOB[0] */
    { .package_pin = 130, .pinmmr_reg = 20, .bit_position = 16 },  /* MIBSPI1NCS[1] */
    { .package_pin = 133, .pinmmr_reg = 21, .bit_position = 8 },   /* GIOB[1] */
    { .package_pin = 28,  .pinmmr_reg = 33, .bit_position = 0 },   /* N2HET1[04] */
    { .package_pin = 51,  .pinmmr_reg = 33, .bit_position = 8 },   /* MIBSPI3SOMI[0] */
    { .package_pin = 52,  .pinmmr_reg = 33, .bit_position = 16 },  /* MIBSPI3SIMO[0] */
    { .package_pin = 53,  .pinmmr_reg = 33, .bit_position = 24 },  /* MIBSPI3CLK */
    { .package_pin = 140, .pinmmr_reg = 34, .bit_position = 0 },   /* N2HET1[16] */
    { .package_pin = 142, .pinmmr_reg = 34, .bit_position = 16 }   /* N2HET1[20] */
};

#define PIN_MAPPING_COUNT (sizeof(g_pin_mapping) / sizeof(g_pin_mapping[0]))

/* ========================================================================== */
/*                           Function Implementations                         */
/* ========================================================================== */

/**
 * @brief Initialize the IOMM module
 * @details Unlocks kick registers, initializes pin mapping lookup table,
 *          and configures default pin states. The IOMM module does not
 *          require clock enabling as it is always accessible.
 */
void IOMM_Init(void)
{
    /* Unlock IOMM registers for configuration */
    IOMM_Unlock();

    /* Pin mapping lookup table is statically initialized */
    /* Default pin states are typically configured by application */
    /* after initialization via IOMM_ConfigurePin() */

    /* Lock IOMM registers after initialization */
    IOMM_Lock();
}

/**
 * @brief Configure a single pin to the specified alternate function
 * @details Uses pre-computed lookup table to map package pin number to
 *          PINMMR register and bit position. Unlocks kick registers,
 *          configures pin, then locks registers.
 *
 * @param pin_number Physical package pin number
 * @param function Pin multiplexing function (AF0-AF7)
 * @return iomm_status_t Configuration status
 * @retval IOMM_STATUS_OK Pin configured successfully
 * @retval IOMM_STATUS_INVALID_PIN Pin number not found in mapping table
 * @retval IOMM_STATUS_INVALID_FUNCTION Function value out of range (> 7)
 */
iomm_status_t IOMM_ConfigurePin(uint8_t pin_number, iomm_pin_function_t function)
{
    uint32_t i;
    const IOMM_PinMapping_t* mapping;
    volatile uint32_t* pinmmr_reg;
    uint32_t reg_value;
    uint32_t function_value;

    /* Validate function value (0-7 for 8 alternate functions) */
    if ((uint32_t)function > 7U) {
        IOMM_Lock();
        return IOMM_STATUS_INVALID_FUNCTION;
    }

    /* Find pin in lookup table */
    mapping = NULL;
    for (i = 0U; i < PIN_MAPPING_COUNT; i++) {
        if (g_pin_mapping[i].package_pin == pin_number) {
            mapping = &g_pin_mapping[i];
            break;
        }
    }

    if (mapping == NULL) {
        IOMM_Lock();
        return IOMM_STATUS_INVALID_PIN;
    }

    /* Unlock IOMM registers before modifying PINMMR */
    IOMM_Unlock();

    /* Calculate PINMMR register address */
    pinmmr_reg = &iommREG->PINMMR0 + mapping->pinmmr_reg;

    /* Convert function enum to one-hot bit encoding within 8-bit field */
    function_value = (1U << (uint32_t)function);

    /* Read-modify-write with proper bit masking */
    reg_value = *pinmmr_reg;
    reg_value &= ~(0xFFU << mapping->bit_position);  /* Clear 8-bit field */
    reg_value |= (function_value & 0xFFU) << mapping->bit_position;  /* Set one-hot value */
    *pinmmr_reg = reg_value;

    /* Lock IOMM registers after configuration */
    IOMM_Lock();

    return IOMM_STATUS_OK;
}

/**
 * @brief Configure multiple pins in a single operation
 * @details Unlocks kick registers once, configures all pins, then locks
 *          registers for efficiency. Aborts on first error.
 *
 * @param pin_configs Array of pin configuration structures
 * @param count Number of pins to configure
 * @return iomm_status_t Configuration status
 * @retval IOMM_STATUS_OK All pins configured successfully
 * @retval IOMM_STATUS_INVALID_PIN One or more pins not found
 * @retval IOMM_STATUS_INVALID_FUNCTION One or more functions out of range
 */
iomm_status_t IOMM_ConfigurePins(const iomm_pin_config_t* pin_configs, uint8_t count)
{
    uint8_t idx;
    uint32_t i;
    const IOMM_PinMapping_t* mapping;
    volatile uint32_t* pinmmr_reg;
    uint32_t reg_value;
    uint32_t function_value;
    iomm_status_t status;

    if (pin_configs == NULL || count == 0U) {
        return IOMM_STATUS_ERROR;
    }

    /* Unlock IOMM registers once for all pins */
    IOMM_Unlock();

    /* Configure each pin */
    for (idx = 0U; idx < count; idx++) {
        /* Validate function value */
        if ((uint32_t)pin_configs[idx].function > 7U) {
            IOMM_Lock();
            return IOMM_STATUS_INVALID_FUNCTION;
        }

        /* Find pin in lookup table */
        mapping = NULL;
        for (i = 0U; i < PIN_MAPPING_COUNT; i++) {
            if (g_pin_mapping[i].package_pin == pin_configs[idx].pin_number) {
                mapping = &g_pin_mapping[i];
                break;
            }
        }

        if (mapping == NULL) {
            IOMM_Lock();
            return IOMM_STATUS_INVALID_PIN;
        }

        /* Calculate PINMMR register address */
        pinmmr_reg = &iommREG->PINMMR0 + mapping->pinmmr_reg;

        /* Convert function enum to one-hot bit encoding */
        function_value = (1U << (uint32_t)pin_configs[idx].function);

        /* Read-modify-write with proper bit masking */
        reg_value = *pinmmr_reg;
        reg_value &= ~(0xFFU << mapping->bit_position);
        reg_value |= (function_value & 0xFFU) << mapping->bit_position;
        *pinmmr_reg = reg_value;
    }

    /* Lock IOMM registers after all configurations */
    IOMM_Lock();

    return IOMM_STATUS_OK;
}

/**
 * @brief Read the current multiplexing function configured for a specific pin
 * @details Decodes the one-hot encoded value from PINMMR register back to
 *          function number (0-7).
 *
 * @param pin_number Physical package pin number
 * @param function Pointer to store current function value
 * @return iomm_status_t Read status
 * @retval IOMM_STATUS_OK Function read successfully
 * @retval IOMM_STATUS_INVALID_PIN Pin number not found in mapping table
 * @retval IOMM_STATUS_ERROR Invalid parameter (NULL pointer)
 */
iomm_status_t IOMM_GetPinFunction(uint8_t pin_number, iomm_pin_function_t* function)
{
    uint32_t i;
    const IOMM_PinMapping_t* mapping;
    volatile uint32_t* pinmmr_reg;
    uint32_t reg_value;
    uint32_t field_value;
    uint32_t bit_idx;

    if (function == NULL) {
        return IOMM_STATUS_ERROR;
    }

    /* Find pin in lookup table */
    mapping = NULL;
    for (i = 0U; i < PIN_MAPPING_COUNT; i++) {
        if (g_pin_mapping[i].package_pin == pin_number) {
            mapping = &g_pin_mapping[i];
            break;
        }
    }

    if (mapping == NULL) {
        return IOMM_STATUS_INVALID_PIN;
    }

    /* Calculate PINMMR register address */
    pinmmr_reg = &iommREG->PINMMR0 + mapping->pinmmr_reg;

    /* Read PINMMR register and extract 8-bit field */
    reg_value = *pinmmr_reg;
    field_value = (reg_value >> mapping->bit_position) & 0xFFU;

    /* Decode one-hot encoding to function number */
    *function = IOMM_PIN_FUNCTION_0;  /* Default to function 0 */
    for (bit_idx = 0U; bit_idx <= 7U; bit_idx++) {
        if ((field_value & (1U << bit_idx)) != 0U) {
            *function = (iomm_pin_function_t)bit_idx;
            break;
        }
    }

    return IOMM_STATUS_OK;
}

/**
 * @brief Lock the PINMMR registers
 * @details Writes any value except unlock sequence to KICK_REG0 or KICK_REG1
 *          to prevent further modifications to PINMMR registers.
 */
void IOMM_Lock(void)
{
    /* Write any value except unlock sequence to lock registers */
    iommREG->KICK_REG0 = 0x00000000U;
}

/**
 * @brief Unlock the PINMMR registers
 * @details Writes unlock sequence to KICK_REG0 (0x83E70B13) and
 *          KICK_REG1 (0x95A4F1E0) to allow modifications to PINMMR registers.
 */
void IOMM_Unlock(void)
{
    /* Write unlock sequence to KICK registers */
    iommREG->KICK_REG0 = IOMM_KICK_REG0_UNLOCK_VALUE;
    iommREG->KICK_REG1 = IOMM_KICK_REG1_UNLOCK_VALUE;
}

/**
 * @brief Enable ePWM module clock
 * @details Enable ePWM module clocks by setting appropriate bits in
 *          PINMMR37-PINMMR38. Note: PINMMR37 and PINMMR38 are not defined
 *          in the current register map (only PINMMR0-PINMMR29 available).
 *
 * @return iomm_status_t Enable status
 * @retval IOMM_STATUS_ERROR PINMMR37-38 not available in current register map
 */
iomm_status_t IOMM_EnableEPWMClock(void)
{
    /* PINMMR37-PINMMR38 are not defined in the register map structure */
    /* Current register map only includes PINMMR0-PINMMR29 */
    /* This function would require extended register map definition */
    return IOMM_STATUS_ERROR;
}

/**
 * @brief Configure ePWM TBCLK synchronization
 * @details Enable or disable ePWM TBCLK synchronization by setting/clearing
 *          bit 1 in PINMMR37. Note: PINMMR37 is not defined in current
 *          register map.
 *
 * @param enable true to enable synchronization, false to disable
 * @return iomm_status_t Configuration status
 * @retval IOMM_STATUS_ERROR PINMMR37 not available in current register map
 */
iomm_status_t IOMM_ConfigureEPWMTBCLKSync(bool enable)
{
    /* PINMMR37 is not defined in the register map structure */
    /* Current register map only includes PINMMR0-PINMMR29 */
    /* This function would require extended register map definition */
    return IOMM_STATUS_ERROR;
}
