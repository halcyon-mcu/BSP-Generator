/* BSP-GEN-META: created_at=2026-03-04T23:26:32-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
#ifndef IOMM_DRIVER_H
#define IOMM_DRIVER_H

/**
 * @file iomm_driver.h
 * @brief Public API for IOMM peripheral driver
 * @details Complete public interface for the IOMM module including
 *          types, enumerations, structures, and function prototypes.
 *          The IOMM (Input/Output Multiplexing Module) controls pin
 *          multiplexing configuration and peripheral clock enables.
 */

/* ========================================================================== */
/*                             Include Files                                  */
/* ========================================================================== */

#include "reg_iomm.h"
#include <stdint.h>
#include <stdbool.h>

/* ========================================================================== */
/*                           Type Definitions                                 */
/* ========================================================================== */

/**
 * @brief IOMM operation status codes
 * @details Return values for IOMM driver functions indicating success
 *          or specific error conditions during pin configuration
 */
typedef enum {
    IOMM_STATUS_OK,               /**< Operation completed successfully */
    IOMM_STATUS_ERROR,            /**< General error occurred */
    IOMM_STATUS_INVALID_PIN,      /**< Invalid pin number specified */
    IOMM_STATUS_INVALID_FUNCTION, /**< Invalid function selection for pin */
    IOMM_STATUS_LOCKED            /**< IOMM registers are locked */
} iomm_status_t;

/**
 * @brief Pin multiplexing function selection (0-7)
 * @details Each pin can be configured to one of eight possible alternate
 *          functions. The actual peripheral mapped to each function depends
 *          on the specific pin number.
 */
typedef enum {
    IOMM_PIN_FUNCTION_0, /**< Alternate function 0 */
    IOMM_PIN_FUNCTION_1, /**< Alternate function 1 */
    IOMM_PIN_FUNCTION_2, /**< Alternate function 2 */
    IOMM_PIN_FUNCTION_3, /**< Alternate function 3 */
    IOMM_PIN_FUNCTION_4, /**< Alternate function 4 */
    IOMM_PIN_FUNCTION_5, /**< Alternate function 5 */
    IOMM_PIN_FUNCTION_6, /**< Alternate function 6 */
    IOMM_PIN_FUNCTION_7  /**< Alternate function 7 */
} iomm_pin_function_t;

/**
 * @brief Pin configuration structure for single pin setup
 * @details Defines the configuration for a single pin including its
 *          number and desired alternate function
 */
typedef struct {
    uint8_t pin_number;           /**< Pin number to configure */
    iomm_pin_function_t function; /**< Alternate function to assign */
} iomm_pin_config_t;

/**
 * @brief Internal pin-to-register mapping structure (non-linear lookup table)
 * @details Maps physical pin numbers to their corresponding PINMMR register
 *          and bit positions. Used internally for pin configuration.
 */
typedef struct {
    uint8_t pin_number;             /**< Physical pin number */
    volatile uint32_t* pinmmr_reg;  /**< Pointer to PINMMR register */
    uint8_t bit_offset;             /**< Bit offset within register */
} iomm_pin_mapping_t;

/* ========================================================================== */
/*                        Function Prototypes                                 */
/* ========================================================================== */

/**
 * @brief Initialize the IOMM module
 * @details Initializes the IOMM module by unlocking kick registers,
 *          initializing the pin mapping lookup table from pinmux.yaml data,
 *          and configuring default pin states
 */
void IOMM_Init(void);

/**
 * @brief Configure a single pin to the specified alternate function
 * @details Configures a single pin using the pre-computed lookup table.
 *          Unlocks kick registers, configures the pin, then locks registers
 *
 * @param[in] pin_number Physical pin number to configure
 * @param[in] function Alternate function to assign to the pin
 * @return Operation status
 * @retval IOMM_STATUS_OK Pin configured successfully
 * @retval IOMM_STATUS_INVALID_PIN Invalid pin number specified
 * @retval IOMM_STATUS_INVALID_FUNCTION Invalid function for this pin
 * @retval IOMM_STATUS_ERROR Configuration failed
 */
iomm_status_t IOMM_ConfigurePin(uint8_t pin_number, iomm_pin_function_t function);

/**
 * @brief Configure multiple pins in a single operation
 * @details Configures multiple pins efficiently by unlocking kick registers
 *          once, configuring all pins, then locking registers
 *
 * @param[in] pin_configs Array of pin configuration structures
 * @param[in] count Number of pins to configure
 * @return Operation status
 * @retval IOMM_STATUS_OK All pins configured successfully
 * @retval IOMM_STATUS_INVALID_PIN Invalid pin number in configuration
 * @retval IOMM_STATUS_INVALID_FUNCTION Invalid function for a pin
 * @retval IOMM_STATUS_ERROR Configuration failed
 */
iomm_status_t IOMM_ConfigurePins(const iomm_pin_config_t* pin_configs, uint8_t count);

/**
 * @brief Read the current multiplexing function configured for a specific pin
 * @details Reads back the current alternate function assigned to a pin
 *
 * @param[in] pin_number Physical pin number to query
 * @param[out] function Pointer to store the current function
 * @return Operation status
 * @retval IOMM_STATUS_OK Function read successfully
 * @retval IOMM_STATUS_INVALID_PIN Invalid pin number specified
 * @retval IOMM_STATUS_ERROR Read operation failed
 */
iomm_status_t IOMM_GetPinFunction(uint8_t pin_number, iomm_pin_function_t* function);

/**
 * @brief Lock the PINMMR registers
 * @details Locks the PINMMR registers by writing any value except the unlock
 *          sequence to KICK_REG0 or KICK_REG1, preventing further modifications
 */
void IOMM_Lock(void);

/**
 * @brief Unlock the PINMMR registers
 * @details Unlocks the PINMMR registers by writing the unlock sequence:
 *          0x83E70B13 to KICK_REG0 and 0x95A4F1E0 to KICK_REG1
 */
void IOMM_Unlock(void);

/**
 * @brief Enable ePWM module clock
 * @details Enables the ePWM module clock by setting appropriate bits
 *          in PINMMR37-PINMMR38
 *
 * @return Operation status
 * @retval IOMM_STATUS_OK ePWM clock enabled successfully
 * @retval IOMM_STATUS_ERROR Failed to enable ePWM clock
 */
iomm_status_t IOMM_EnableEPWMClock(void);

/**
 * @brief Enable or disable ePWM TBCLK synchronization
 * @details Controls ePWM TBCLK synchronization by setting or clearing
 *          bit 1 in PINMMR37
 *
 * @param[in] enable True to enable synchronization, false to disable
 * @return Operation status
 * @retval IOMM_STATUS_OK TBCLK synchronization configured successfully
 * @retval IOMM_STATUS_ERROR Failed to configure TBCLK synchronization
 */
iomm_status_t IOMM_ConfigureEPWMTBCLKSync(bool enable);

/**
 * @brief App-intent pin-init guidance
 * @details Generated from bringup_contract.app_intent.api_reuse.
 *          Recommended sequence for app code:
 *          1) Prefer module-specific EnablePins wrappers where available.
 *          2) Use IOMM pin configuration fallback only when wrapper APIs are unavailable.
 *          Policy mode: warn_only
 */

#endif /* IOMM_DRIVER_H */
