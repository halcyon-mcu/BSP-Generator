/* BSP-GEN-META: created_at=2026-03-04T23:26:17-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
#ifndef PCR_DRIVER_H
#define PCR_DRIVER_H

/**
 * @file pcr_driver.h
 * @brief Public API for PCR peripheral driver
 * @details Complete public interface for the PCR (Peripheral Central Resource)
 *          module including types, enumerations, structures, and function prototypes.
 *          This driver provides control over peripheral power domains and clock domains.
 */

#include <stdint.h>
#include <stdbool.h>
#include "reg_pcr.h"

/*===========================================================================*/
/* Type Definitions                                                          */
/*===========================================================================*/

/**
 * @brief Return status codes for PCR operations
 * @details Status enumeration for PCR driver function return values
 */
typedef enum {
    PCR_STATUS_OK,              /**< Operation completed successfully */
    PCR_STATUS_ERROR,           /**< General error occurred */
    PCR_STATUS_INVALID_DOMAIN   /**< Invalid domain specified */
} pcr_status_t;

/**
 * @brief Power domain identifiers for peripheral power control
 * @details Enumeration of all available peripheral power domains (PS0-PS31)
 */
typedef enum {
    PCR_DOMAIN_PS0,    /**< Peripheral power domain PS0 */
    PCR_DOMAIN_PS1,    /**< Peripheral power domain PS1 */
    PCR_DOMAIN_PS2,    /**< Peripheral power domain PS2 */
    PCR_DOMAIN_PS3,    /**< Peripheral power domain PS3 */
    PCR_DOMAIN_PS4,    /**< Peripheral power domain PS4 */
    PCR_DOMAIN_PS5,    /**< Peripheral power domain PS5 */
    PCR_DOMAIN_PS6,    /**< Peripheral power domain PS6 */
    PCR_DOMAIN_PS7,    /**< Peripheral power domain PS7 */
    PCR_DOMAIN_PS8,    /**< Peripheral power domain PS8 */
    PCR_DOMAIN_PS9,    /**< Peripheral power domain PS9 */
    PCR_DOMAIN_PS10,   /**< Peripheral power domain PS10 */
    PCR_DOMAIN_PS11,   /**< Peripheral power domain PS11 */
    PCR_DOMAIN_PS12,   /**< Peripheral power domain PS12 */
    PCR_DOMAIN_PS13,   /**< Peripheral power domain PS13 */
    PCR_DOMAIN_PS14,   /**< Peripheral power domain PS14 */
    PCR_DOMAIN_PS15,   /**< Peripheral power domain PS15 */
    PCR_DOMAIN_PS16,   /**< Peripheral power domain PS16 */
    PCR_DOMAIN_PS17,   /**< Peripheral power domain PS17 */
    PCR_DOMAIN_PS18,   /**< Peripheral power domain PS18 */
    PCR_DOMAIN_PS19,   /**< Peripheral power domain PS19 */
    PCR_DOMAIN_PS20,   /**< Peripheral power domain PS20 */
    PCR_DOMAIN_PS21,   /**< Peripheral power domain PS21 */
    PCR_DOMAIN_PS22,   /**< Peripheral power domain PS22 */
    PCR_DOMAIN_PS23,   /**< Peripheral power domain PS23 */
    PCR_DOMAIN_PS24,   /**< Peripheral power domain PS24 */
    PCR_DOMAIN_PS25,   /**< Peripheral power domain PS25 */
    PCR_DOMAIN_PS26,   /**< Peripheral power domain PS26 */
    PCR_DOMAIN_PS27,   /**< Peripheral power domain PS27 */
    PCR_DOMAIN_PS28,   /**< Peripheral power domain PS28 */
    PCR_DOMAIN_PS29,   /**< Peripheral power domain PS29 */
    PCR_DOMAIN_PS30,   /**< Peripheral power domain PS30 */
    PCR_DOMAIN_PS31    /**< Peripheral power domain PS31 */
} pcr_domain_t;

/**
 * @brief Peripheral clock domain identifiers
 * @details Enumeration of all available peripheral clock domains (PCS0-PCS31)
 */
typedef enum {
    PCR_CLKDOMAIN_PCS0,    /**< Peripheral clock domain PCS0 */
    PCR_CLKDOMAIN_PCS1,    /**< Peripheral clock domain PCS1 */
    PCR_CLKDOMAIN_PCS2,    /**< Peripheral clock domain PCS2 */
    PCR_CLKDOMAIN_PCS3,    /**< Peripheral clock domain PCS3 */
    PCR_CLKDOMAIN_PCS4,    /**< Peripheral clock domain PCS4 */
    PCR_CLKDOMAIN_PCS5,    /**< Peripheral clock domain PCS5 */
    PCR_CLKDOMAIN_PCS6,    /**< Peripheral clock domain PCS6 */
    PCR_CLKDOMAIN_PCS7,    /**< Peripheral clock domain PCS7 */
    PCR_CLKDOMAIN_PCS8,    /**< Peripheral clock domain PCS8 */
    PCR_CLKDOMAIN_PCS9,    /**< Peripheral clock domain PCS9 */
    PCR_CLKDOMAIN_PCS10,   /**< Peripheral clock domain PCS10 */
    PCR_CLKDOMAIN_PCS11,   /**< Peripheral clock domain PCS11 */
    PCR_CLKDOMAIN_PCS12,   /**< Peripheral clock domain PCS12 */
    PCR_CLKDOMAIN_PCS13,   /**< Peripheral clock domain PCS13 */
    PCR_CLKDOMAIN_PCS14,   /**< Peripheral clock domain PCS14 */
    PCR_CLKDOMAIN_PCS15,   /**< Peripheral clock domain PCS15 */
    PCR_CLKDOMAIN_PCS16,   /**< Peripheral clock domain PCS16 */
    PCR_CLKDOMAIN_PCS17,   /**< Peripheral clock domain PCS17 */
    PCR_CLKDOMAIN_PCS18,   /**< Peripheral clock domain PCS18 */
    PCR_CLKDOMAIN_PCS19,   /**< Peripheral clock domain PCS19 */
    PCR_CLKDOMAIN_PCS20,   /**< Peripheral clock domain PCS20 */
    PCR_CLKDOMAIN_PCS21,   /**< Peripheral clock domain PCS21 */
    PCR_CLKDOMAIN_PCS22,   /**< Peripheral clock domain PCS22 */
    PCR_CLKDOMAIN_PCS23,   /**< Peripheral clock domain PCS23 */
    PCR_CLKDOMAIN_PCS24,   /**< Peripheral clock domain PCS24 */
    PCR_CLKDOMAIN_PCS25,   /**< Peripheral clock domain PCS25 */
    PCR_CLKDOMAIN_PCS26,   /**< Peripheral clock domain PCS26 */
    PCR_CLKDOMAIN_PCS27,   /**< Peripheral clock domain PCS27 */
    PCR_CLKDOMAIN_PCS28,   /**< Peripheral clock domain PCS28 */
    PCR_CLKDOMAIN_PCS29,   /**< Peripheral clock domain PCS29 */
    PCR_CLKDOMAIN_PCS30,   /**< Peripheral clock domain PCS30 */
    PCR_CLKDOMAIN_PCS31    /**< Peripheral clock domain PCS31 */
} pcr_clock_domain_t;

/*===========================================================================*/
/* Function Prototypes                                                       */
/*===========================================================================*/

/**
 * @brief Initialize PCR module
 * @details Powers up all peripheral domains using CLR registers and performs
 *          initial configuration of the PCR peripheral.
 */
void PCR_Init(void);

/**
 * @brief Enable power to a specific peripheral power domain
 *
 * @param[in] domain The peripheral power domain to enable
 * @return Status of the operation
 * @retval PCR_STATUS_OK Power enabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Invalid domain specified
 * @retval PCR_STATUS_ERROR Operation failed
 */
pcr_status_t PCR_EnablePeripheralPower(pcr_domain_t domain);

/**
 * @brief Disable power to a specific peripheral power domain
 *
 * @param[in] domain The peripheral power domain to disable
 * @return Status of the operation
 * @retval PCR_STATUS_OK Power disabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Invalid domain specified
 * @retval PCR_STATUS_ERROR Operation failed
 */
pcr_status_t PCR_DisablePeripheralPower(pcr_domain_t domain);

/**
 * @brief Enable clock to a specific peripheral clock domain
 *
 * @param[in] clock_domain The peripheral clock domain to enable
 * @return Status of the operation
 * @retval PCR_STATUS_OK Clock enabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Invalid clock domain specified
 * @retval PCR_STATUS_ERROR Operation failed
 */
pcr_status_t PCR_EnablePeripheralClock(pcr_clock_domain_t clock_domain);

/**
 * @brief Disable clock to a specific peripheral clock domain
 *
 * @param[in] clock_domain The peripheral clock domain to disable
 * @return Status of the operation
 * @retval PCR_STATUS_OK Clock disabled successfully
 * @retval PCR_STATUS_INVALID_DOMAIN Invalid clock domain specified
 * @retval PCR_STATUS_ERROR Operation failed
 */
pcr_status_t PCR_DisablePeripheralClock(pcr_clock_domain_t clock_domain);

/**
 * @brief Get the power status of a specific peripheral domain
 *
 * @param[in] domain The peripheral power domain to query
 * @return Power status of the domain
 * @retval true Domain is powered
 * @retval false Domain is powered down
 */
bool PCR_GetPeripheralPowerStatus(pcr_domain_t domain);

/**
 * @brief Get the clock status of a specific peripheral clock domain
 *
 * @param[in] clock_domain The peripheral clock domain to query
 * @return Clock status of the domain
 * @retval true Clock is enabled
 * @retval false Clock is disabled
 */
bool PCR_GetPeripheralClockStatus(pcr_clock_domain_t clock_domain);

/**
 * @brief Enable all known PCR-controlled peripherals
 *
 * @details Compatibility helper used by early startup code. This performs
 *          a best-effort enable of every peripheral enum entry.
 */
void PCR_EnableAllPeripherals(void);

#endif /* PCR_DRIVER_H */
