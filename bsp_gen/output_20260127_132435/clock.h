/**
 * @file clock.h
 * @brief Clock management service for TI Hercules RM46
 */

#ifndef CLOCK_H
#define CLOCK_H

#include <stdint.h>

/**
 * @defgroup BSP_CLOCK Clock Service
 * @brief Clock enabling and frequency query for all peripheral clock domains.
 * @{
 */

/**
 * @brief Clock reference enumeration.
 *
 * Stable enumeration of all clock domains referenced by peripherals or system clocks.
 * Enum values are assigned in lexicographical order for stability.
 *
 * @ingroup BSP_CLOCK
 */
typedef enum {
    CLOCKREF_GCLK = 0,       /**< CPU clock (GCLK domain) */
    CLOCKREF_HCLK = 1,       /**< System module clock (HCLK domain) */
    CLOCKREF_HF_LPO = 2,     /**< High-frequency LPO clock source */
    CLOCKREF_LF_LPO = 3,     /**< Low-frequency LPO clock source */
    CLOCKREF_OSCIN = 4,      /**< External crystal oscillator */
    CLOCKREF_SYSCLK = 5,     /**< Alias for VCLK (used by PCR) */
    CLOCKREF_VCLK = 6        /**< Peripheral bus clock (VCLK domain) */
} clock_ref_t;

/**
 * @brief Enable a clock domain.
 *
 * Enables the specified clock reference by clearing disable bits for required
 * clock sources (CSDIS) and clock domains (CDDIS). This function is idempotent
 * and safe to call multiple times. It NEVER disables clocks.
 *
 * @ingroup BSP_CLOCK
 * @param ref Clock reference to enable.
 * @return 0 on success, negative error code on failure.
 *
 * @note Safe to call from peripheral driver initialization code.
 * @warning Does not configure dividers or muxes.
 */
int clock_enable(clock_ref_t ref);

/**
 * @brief Query clock frequency.
 *
 * Returns the best-known frequency for the specified clock reference,
 * derived from fixed source frequencies and default divider values.
 * If the frequency cannot be determined, returns 0.
 *
 * @ingroup BSP_CLOCK
 * @param ref Clock reference to query.
 * @return Frequency in Hz, or 0 if unknown.
 *
 * @note Safe to call from peripheral driver code.
 * @note Returned frequency is based on default divider settings.
 */
uint32_t clock_get_hz(clock_ref_t ref);

/* ============================================================================
 * APPLICATION-ONLY CLOCK CONFIGURATION API
 * ============================================================================
 * The following functions are intended ONLY for developer application code
 * (e.g., main.c or board initialization code). Peripheral drivers MUST NOT
 * call these functions.
 * ========================================================================= */

/**
 * @brief Set VCLK divider.
 *
 * Configures the VCLK divider (HCLK / divider).
 *
 * @ingroup BSP_CLOCK
 * @param divider Divider value (1..16). VCLK = HCLK / divider.
 * @return 0 on success, negative error code if divider out of range.
 *
 * @warning APPLICATION-ONLY. Do not call from peripheral drivers.
 * @note Must be called before peripheral initialization if non-default divider is required.
 */
int clock_set_vclk_divider(uint32_t divider);

/**
 * @brief Set VCLK2 divider.
 *
 * Configures the VCLK2 divider (HCLK / divider).
 *
 * @ingroup BSP_CLOCK
 * @param divider Divider value (1..16). VCLK2 = HCLK / divider.
 * @return 0 on success, negative error code if divider out of range.
 *
 * @warning APPLICATION-ONLY. Do not call from peripheral drivers.
 * @warning VCLK2 must be an integer multiple of VCLK (constraint from bus.yaml).
 */
int clock_set_vclk2_divider(uint32_t divider);

/* ============================================================================
 * INLINE HELPER WRAPPERS
 * ========================================================================= */

/**
 * @brief Enable OSCIN clock source.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_oscin(void) {
    return clock_enable(CLOCKREF_OSCIN);
}

/**
 * @brief Query OSCIN frequency.
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz.
 */
static inline uint32_t clock_get_oscin_hz(void) {
    return clock_get_hz(CLOCKREF_OSCIN);
}

/**
 * @brief Enable GCLK clock domain.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_gclk(void) {
    return clock_enable(CLOCKREF_GCLK);
}

/**
 * @brief Query GCLK frequency.
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz.
 */
static inline uint32_t clock_get_gclk_hz(void) {
    return clock_get_hz(CLOCKREF_GCLK);
}

/**
 * @brief Enable HCLK clock domain.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_hclk(void) {
    return clock_enable(CLOCKREF_HCLK);
}

/**
 * @brief Query HCLK frequency.
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz.
 */
static inline uint32_t clock_get_hclk_hz(void) {
    return clock_get_hz(CLOCKREF_HCLK);
}

/**
 * @brief Enable VCLK clock domain.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_vclk(void) {
    return clock_enable(CLOCKREF_VCLK);
}

/**
 * @brief Query VCLK frequency.
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz.
 */
static inline uint32_t clock_get_vclk_hz(void) {
    return clock_get_hz(CLOCKREF_VCLK);
}

/**
 * @brief Enable HF_LPO clock source.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_hf_lpo(void) {
    return clock_enable(CLOCKREF_HF_LPO);
}

/**
 * @brief Query HF_LPO frequency.
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz.
 */
static inline uint32_t clock_get_hf_lpo_hz(void) {
    return clock_get_hz(CLOCKREF_HF_LPO);
}

/**
 * @brief Enable LF_LPO clock source.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_lf_lpo(void) {
    return clock_enable(CLOCKREF_LF_LPO);
}

/**
 * @brief Query LF_LPO frequency.
 * @ingroup BSP_CLOCK
 * @return Frequency in Hz.
 */
static inline uint32_t clock_get_lf_lpo_hz(void) {
    return clock_get_hz(CLOCKREF_LF_LPO);
}

/** @} */ /* end of BSP_CLOCK */

#endif /* CLOCK_H */

