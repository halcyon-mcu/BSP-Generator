/**
 * @file clock.h
 * @brief Clock Service Module for TI Hercules RM46
 */

#ifndef CLOCK_H
#define CLOCK_H

#include <stdint.h>

/**
 * @defgroup BSP_CLOCK Clock Service
 * @brief Clock management and frequency query service for all peripherals.
 * @{
 */

/**
 * @brief Clock reference enumeration.
 * @ingroup BSP_CLOCK
 *
 * Each clock reference corresponds to a clock domain or source used by
 * peripherals in the RM46 device. Enum values are explicitly assigned
 * in lexicographic order for stability.
 */
typedef enum {
    CLOCKREF_GCLK      = 0,  /**< CPU clock domain (GCLK) */
    CLOCKREF_HF_LPO    = 1,  /**< High-frequency low-power oscillator */
    CLOCKREF_HCLK      = 2,  /**< System module clock (HCLK) */
    CLOCKREF_LF_LPO    = 3,  /**< Low-frequency low-power oscillator */
    CLOCKREF_OSCIN     = 4,  /**< External oscillator input (16 MHz on LaunchPad XL2) */
    CLOCKREF_SYSCLK    = 5,  /**< System clock for PCR module */
    CLOCKREF_VCLK      = 6   /**< Peripheral bus clock (VCLK) */
} clock_ref_t;

/**
 * @brief Enable a clock domain or source.
 * @ingroup BSP_CLOCK
 *
 * Enables the specified clock by clearing the appropriate disable bits
 * in SYSTEM.CSDIS and SYSTEM.CDDIS. This function is idempotent and safe
 * to call from peripheral drivers.
 *
 * @param ref The clock reference to enable.
 * @return 0 on success, -1 on invalid reference.
 *
 * @note This function does not modify dividers, muxes, or PLL settings.
 * @note Safe for use by peripheral init code.
 */
int clock_enable(clock_ref_t ref);

/**
 * @brief Query the frequency of a clock in Hz.
 * @ingroup BSP_CLOCK
 *
 * Returns the best-known frequency of the specified clock, computed from
 * fixed source frequencies and default divider settings. If the frequency
 * cannot be determined from available data, returns 0.
 *
 * @param ref The clock reference to query.
 * @return Clock frequency in Hz, or 0 if unknown.
 *
 * @note Frequencies are based on default divider settings unless modified
 *       by application code using clock_set_divider().
 * @note Safe for use by peripheral init code.
 */
uint32_t clock_get_hz(clock_ref_t ref);

/**
 * @brief Set the divider for a clock domain.
 * @ingroup BSP_CLOCK
 *
 * **APPLICATION-ONLY**: This function is intended ONLY for developer
 * application code (e.g., main.c or board_init()). Peripheral drivers
 * MUST NOT call this function.
 *
 * Configures the divider for VCLK or VCLK2 domains. The divider value
 * must be in the range [1, 16], corresponding to divide ratios /1 to /16.
 *
 * @param ref The clock reference (CLOCKREF_VCLK or CLOCKREF_VCLK2).
 * @param divider The divider value (1-16).
 * @return 0 on success, -1 on invalid reference or divider.
 *
 * @warning Do not call from peripheral init code.
 * @note Changes take effect immediately but may require peripheral re-init.
 */
int clock_set_divider(clock_ref_t ref, uint32_t divider);

/**
 * @brief Enable VCLK domain.
 * @ingroup BSP_CLOCK
 * @return 0 on success, -1 on error.
 */
static inline int clock_enable_vclk(void)
{
    return clock_enable(CLOCKREF_VCLK);
}

/**
 * @brief Get VCLK frequency in Hz.
 * @ingroup BSP_CLOCK
 * @return VCLK frequency in Hz, or 0 if unknown.
 */
static inline uint32_t clock_get_vclk_hz(void)
{
    return clock_get_hz(CLOCKREF_VCLK);
}

/**
 * @brief Enable HCLK domain.
 * @ingroup BSP_CLOCK
 * @return 0 on success, -1 on error.
 */
static inline int clock_enable_hclk(void)
{
    return clock_enable(CLOCKREF_HCLK);
}

/**
 * @brief Get HCLK frequency in Hz.
 * @ingroup BSP_CLOCK
 * @return HCLK frequency in Hz, or 0 if unknown.
 */
static inline uint32_t clock_get_hclk_hz(void)
{
    return clock_get_hz(CLOCKREF_HCLK);
}

/** @} */ /* end of BSP_CLOCK */

#endif /* CLOCK_H */

