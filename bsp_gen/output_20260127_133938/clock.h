/**
 * @file clock.h
 * @brief Clock service for TI Hercules RM46 peripherals
 */

#ifndef CLOCK_H
#define CLOCK_H

#include <stdint.h>

/**
 * @defgroup BSP_CLOCK Clock Service
 * @brief Clock enable and query service for peripheral drivers
 * @{
 */

/**
 * @brief Clock reference identifier
 * @ingroup BSP_CLOCK
 *
 * Each peripheral clock reference is assigned a stable enum value.
 * Peripheral drivers use these identifiers to enable clocks and query frequencies.
 */
typedef enum {
    CLOCKREF_GCLK       = 0,  /**< CPU clock (GCLK) */
    CLOCKREF_HCLK       = 1,  /**< System module clock (HCLK) */
    CLOCKREF_HF_LPO     = 2,  /**< High-frequency low-power oscillator */
    CLOCKREF_LF_LPO     = 3,  /**< Low-frequency low-power oscillator */
    CLOCKREF_OSCIN      = 4,  /**< External crystal oscillator input (16 MHz) */
    CLOCKREF_SYSCLK     = 5,  /**< System clock (used by PCR) */
    CLOCKREF_VCLK       = 6   /**< Peripheral bus clock (VCLK) */
} clock_ref_t;

/**
 * @brief Enable a peripheral clock
 * @ingroup BSP_CLOCK
 *
 * Enables the clock source and domain required for the given clock reference.
 * This function is idempotent and will not disable clocks.
 *
 * @note Must be called before using the peripheral associated with the clock reference.
 * @note This function only enables clocks; it does not modify dividers or source selections.
 *
 * @param[in] ref  Clock reference identifier
 * @return 0 on success, -1 on invalid reference
 */
int clock_enable(clock_ref_t ref);

/**
 * @brief Query the frequency of a clock
 * @ingroup BSP_CLOCK
 *
 * Returns the best-known frequency for the given clock reference.
 * Frequencies are computed from default dividers specified in bus.yaml.
 *
 * @param[in] ref  Clock reference identifier
 * @return Frequency in Hz, or 0 if unknown or not configured
 */
uint32_t clock_get_hz(clock_ref_t ref);

/**
 * @brief Set the divider for a peripheral clock (APPLICATION-ONLY)
 * @ingroup BSP_CLOCK
 *
 * @warning APPLICATION-ONLY: Do not call from peripheral drivers.
 * @warning This function is intended for application code (e.g., main.c) to configure
 *          clock dividers before enabling peripherals.
 *
 * Configures the clock divider for the specified clock reference.
 * Only VCLK and VCLK2 are currently supported.
 *
 * @note The divider value is the actual divisor (1..16), not a register encoding.
 * @note After calling this function, clock_get_hz() will return the updated frequency.
 *
 * @param[in] ref      Clock reference identifier
 * @param[in] divider  Divider value (1..16)
 * @return 0 on success, -1 on invalid reference or divider
 */
int clock_set_divider(clock_ref_t ref, uint32_t divider);

/**
 * @brief Inline helper: Enable OSCIN clock
 * @ingroup BSP_CLOCK
 * @return 0 on success, -1 on error
 */
static inline int clock_enable_oscin(void) {
    return clock_enable(CLOCKREF_OSCIN);
}

/**
 * @brief Inline helper: Get OSCIN frequency
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz
 */
static inline uint32_t clock_get_oscin_hz(void) {
    return clock_get_hz(CLOCKREF_OSCIN);
}

/**
 * @brief Inline helper: Enable HCLK clock
 * @ingroup BSP_CLOCK
 * @return 0 on success, -1 on error
 */
static inline int clock_enable_hclk(void) {
    return clock_enable(CLOCKREF_HCLK);
}

/**
 * @brief Inline helper: Get HCLK frequency
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz
 */
static inline uint32_t clock_get_hclk_hz(void) {
    return clock_get_hz(CLOCKREF_HCLK);
}

/**
 * @brief Inline helper: Enable VCLK clock
 * @ingroup BSP_CLOCK
 * @return 0 on success, -1 on error
 */
static inline int clock_enable_vclk(void) {
    return clock_enable(CLOCKREF_VCLK);
}

/**
 * @brief Inline helper: Get VCLK frequency
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz
 */
static inline uint32_t clock_get_vclk_hz(void) {
    return clock_get_hz(CLOCKREF_VCLK);
}

/** @} */ /* end of BSP_CLOCK */

#endif /* CLOCK_H */

