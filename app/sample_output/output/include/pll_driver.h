/* BSP-GEN-META: created_at=2026-03-04T23:27:22-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
#ifndef PLL_DRIVER_H
#define PLL_DRIVER_H

/**
 * @file pll_driver.h
 * @brief Public API for PLL peripheral driver
 * @details Complete public interface for the PLL module including
 *          types, enumerations, structures, and function prototypes.
 *          This driver manages PLL configuration, clock domain control,
 *          and frequency reporting for all system clocks.
 */

#include <stdint.h>
#include <stdbool.h>
#include "reg_pll.h"

/******************************************************************************/
/*                            Type Definitions                                */
/******************************************************************************/

/**
 * @brief PLL module return status codes
 * @details Status codes returned by PLL driver functions to indicate
 *          success or specific error conditions.
 */
typedef enum {
    PLL_STATUS_OK,              /**< Operation completed successfully */
    PLL_STATUS_ERROR,           /**< General error occurred */
    PLL_STATUS_INVALID_PARAM,   /**< Invalid parameter provided */
    PLL_STATUS_NOT_LOCKED,      /**< PLL failed to achieve lock */
    PLL_STATUS_TIMEOUT          /**< Operation timed out */
} pll_status_t;

/**
 * @brief Clock domain identifiers for all system clock domains
 * @details Enumerates all available clock domains in the system.
 *          Used to identify target domains for enable/disable operations
 *          and frequency queries.
 */
typedef enum {
    CLOCKDOMAIN_EXTCLKIN1,      /**< External clock input 1 */
    CLOCKDOMAIN_EXTCLKIN2,      /**< External clock input 2 */
    CLOCKDOMAIN_GCLK,           /**< System GCLK domain */
    CLOCKDOMAIN_HCLK,           /**< High-speed bus clock */
    CLOCKDOMAIN_HF_LPO,         /**< High-frequency low-power oscillator */
    CLOCKDOMAIN_LF_LPO,         /**< Low-frequency low-power oscillator */
    CLOCKDOMAIN_OSCIN,          /**< External oscillator input */
    CLOCKDOMAIN_PLL1,           /**< PLL1 output clock */
    CLOCKDOMAIN_PLL2,           /**< PLL2 output clock */
    CLOCKDOMAIN_RTICLK,         /**< Real-time int_type clock */
    CLOCKDOMAIN_VCLK,           /**< Peripheral clock domain VCLK */
    CLOCKDOMAIN_VCLK2,          /**< Peripheral clock domain VCLK2 */
    CLOCKDOMAIN_VCLK3,          /**< Peripheral clock domain VCLK3 */
    CLOCKDOMAIN_VCLK4,          /**< Peripheral clock domain VCLK4 */
    CLOCKDOMAIN_VCLKA1,         /**< Asynchronous peripheral clock VCLKA1 */
    CLOCKDOMAIN_VCLKA3,         /**< Asynchronous peripheral clock VCLKA3 */
    CLOCKDOMAIN_VCLKA4,         /**< Asynchronous peripheral clock VCLKA4 */
    CLOCKDOMAIN_MAX             /**< Maximum clock domain count (sentinel) */
} clock_domain_t;

/**
 * @brief PLL instance selector
 * @details Identifies which PLL instance (PLL1 or PLL2) to target
 *          for configuration or control operations.
 */
typedef enum {
    PLL_INSTANCE_1,             /**< PLL1 instance */
    PLL_INSTANCE_2              /**< PLL2 instance */
} pll_instance_t;

/**
 * @brief PLL configuration structure for runtime reconfiguration
 * @details Complete configuration parameters for PLL setup including
 *          multipliers, dividers, and modulation settings.
 */
typedef struct {
    pll_instance_t pll_instance;        /**< PLL instance to configure (PLL1 or PLL2) */
    uint32_t nf_multiplier;             /**< Feedback multiplier (1-255) */
    uint32_t nr_ref_divider;            /**< Reference divider (0-63), actual = NR+1 */
    uint32_t r_post_divider;            /**< Post divider exponent (0-15), actual = 2^R */
    uint32_t odpll_output_divider;      /**< Output divider (1-31) */
    bool enable_modulation;             /**< Enable frequency modulation (PLL1 only) */
} pll_config_t;

/**
 * @brief Clock domain divider configuration
 * @details Specifies divider settings for configurable clock domains.
 */
typedef struct {
    clock_domain_t domain;              /**< Target clock domain */
    uint32_t divider;                   /**< Clock divider value (domain-specific encoding) */
} clock_divider_config_t;

/**
 * @brief PLL lock and slip status information
 * @details Provides current lock status for both PLLs and clock slip
 *          detection flags.
 */
typedef struct {
    bool pll1_locked;                   /**< PLL1 lock status */
    bool pll2_locked;                   /**< PLL2 lock status */
    bool clock_slip_detected;           /**< Clock slip detection flag */
} pll_lock_status_t;

/******************************************************************************/
/*                         Function Prototypes                                */
/******************************************************************************/

/**
 * @brief Initialize the PLL and clock system with default configuration
 * @details Configures PLL1, clock sources, dividers, and enables all clock
 *          domains according to SOC YAML configuration. Implements the
 *          complete initialization sequence.
 */
void PLL_Init(void);

/**
 * @brief Get the frequency in Hz for the specified clock domain
 * @details Returns the current operating frequency of the specified clock
 *          domain. This is the primary clock service API used by all
 *          peripheral drivers.
 *
 * @param[in] domain Clock domain identifier
 * @return Frequency in Hz, or 0 if domain is invalid or disabled
 */
uint32_t PLL_GetFrequency(clock_domain_t domain);

/**
 * @brief Enable the specified clock domain
 * @details Must be called by peripheral drivers before accessing peripheral
 *          registers to ensure clock is active.
 *
 * @param[in] domain Clock domain to enable
 * @return Status code
 * @retval PLL_STATUS_OK Clock enabled successfully
 * @retval PLL_STATUS_INVALID_PARAM Invalid domain specified
 */
pll_status_t PLL_EnableClock(clock_domain_t domain);

/**
 * @brief Disable the specified clock domain
 * @details Use with caution - only disable clocks when peripheral is
 *          confirmed inactive.
 *
 * @param[in] domain Clock domain to disable
 * @return Status code
 * @retval PLL_STATUS_OK Clock disabled successfully
 * @retval PLL_STATUS_INVALID_PARAM Invalid domain specified
 */
pll_status_t PLL_DisableClock(clock_domain_t domain);

/**
 * @brief Configure PLL parameters at runtime (advanced use only)
 * @details Disables PLL, applies new configuration, and waits for lock.
 *          Use with caution as this affects system clocks.
 *
 * @param[in] config Pointer to PLL configuration structure
 * @return Status code
 * @retval PLL_STATUS_OK Configuration applied and PLL locked
 * @retval PLL_STATUS_INVALID_PARAM Invalid configuration parameters
 * @retval PLL_STATUS_NOT_LOCKED PLL failed to lock after configuration
 */
pll_status_t PLL_ConfigurePLL(const pll_config_t* config);

/**
 * @brief Configure clock domain divider ratio
 * @details Applies divider configuration to configurable domains
 *          (VCLK, VCLK2, VCLK3, VCLK4).
 *
 * @param[in] config Pointer to divider configuration structure
 * @return Status code
 * @retval PLL_STATUS_OK Divider configured successfully
 * @retval PLL_STATUS_INVALID_PARAM Invalid domain or divider value
 */
pll_status_t PLL_SetClockDivider(const clock_divider_config_t* config);

/**
 * @brief Read PLL lock status and clock slip detection flags
 * @details Populates the provided status structure with current PLL1/PLL2
 *          lock state and slip detection status.
 *
 * @param[out] status Pointer to status structure to populate
 */
void PLL_GetLockStatus(pll_lock_status_t* status);

/**
 * @brief Poll for PLL lock with timeout
 * @details Waits for the specified PLL to achieve lock status.
 *
 * @param[in] pll PLL instance to monitor
 * @param[in] timeout_us Timeout in microseconds (0 = infinite wait)
 * @return Status code
 * @retval PLL_STATUS_OK PLL locked successfully
 * @retval PLL_STATUS_TIMEOUT Timeout expired before lock achieved
 */
pll_status_t PLL_WaitForLock(pll_instance_t pll, uint32_t timeout_us);

/**
 * @brief Enable the specified PLL instance
 * @details Enables PLL and waits for lock before returning.
 *
 * @param[in] pll PLL instance to enable
 * @return Status code
 * @retval PLL_STATUS_OK PLL enabled and locked
 * @retval PLL_STATUS_NOT_LOCKED PLL failed to achieve lock
 */
pll_status_t PLL_EnablePLL(pll_instance_t pll);

/**
 * @brief Disable the specified PLL instance
 * @details Use with extreme caution - may affect system clocks.
 *
 * @param[in] pll PLL instance to disable
 * @return Status code
 * @retval PLL_STATUS_OK PLL disabled successfully
 */
pll_status_t PLL_DisablePLL(pll_instance_t pll);

/**
 * @brief Clear clock slip detection flags in GLBSTAT register
 * @details Should be called after handling a clock slip event to clear
 *          the sticky status flags.
 */
void PLL_ClearClockSlipStatus(void);

/**
 * @brief Get the external oscillator (OSCIN) frequency in Hz
 * @details Returns the configured OSCIN frequency.
 *
 * @return OSCIN frequency in Hz (typically 16 MHz)
 */
uint32_t PLL_GetOscillatorFrequency(void);

/**
 * @brief Select clock source for a configurable clock domain
 * @details Configures the clock source multiplexer for domains that support
 *          multiple input sources. Source_id values are device-specific.
 *
 * @param[in] domain Target clock domain
 * @param[in] source_id Source identifier (see GHVSRC, RCLKSRC, VCLKASRC register mappings)
 * @return Status code
 * @retval PLL_STATUS_OK Clock source selected successfully
 * @retval PLL_STATUS_INVALID_PARAM Invalid domain or source identifier
 */
pll_status_t PLL_SelectClockSource(clock_domain_t domain, uint32_t source_id);

#endif /* PLL_DRIVER_H */
