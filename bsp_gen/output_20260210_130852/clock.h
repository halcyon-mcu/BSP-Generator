/**
 * @file clock.h
 * @brief Clock service for TI Hercules RM46 (Cortex-R4)
 */

#ifndef CLOCK_H
#define CLOCK_H

#include <stdint.h>

/**
 * @defgroup BSP_CLOCK Clock Service
 * @brief Shared clock enable and query service for all peripheral drivers.
 * @{
 */

/**
 * @brief Clock reference enumeration.
 *
 * Each peripheral driver references clocks by these symbolic constants.
 * Enum values are explicit and stable (sorted lexicographically).
 *
 * @ingroup BSP_CLOCK
 */
typedef enum {
    CLOCKREF_EXTCLKIN1 = 0,
    CLOCKREF_EXTCLKIN2 = 1,
    CLOCKREF_GCLK = 2,
    CLOCKREF_GCLK2 = 3,
    CLOCKREF_HCLK = 4,
    CLOCKREF_HF_LPO = 5,
    CLOCKREF_LF_LPO = 6,
    CLOCKREF_OSCIN = 7,
    CLOCKREF_PLL1 = 8,
    CLOCKREF_PLL2 = 9,
    CLOCKREF_RTICLK = 10,
    CLOCKREF_SYSCLK = 11,
    CLOCKREF_VCLK = 12,
    CLOCKREF_VCLK2 = 13,
    CLOCKREF_VCLK3 = 14,
    CLOCKREF_VCLK4 = 15,
    CLOCKREF_VCLKA1 = 16,
    CLOCKREF_VCLKA2 = 17,
    CLOCKREF_VCLKA3_DIVR = 18,
    CLOCKREF_VCLKA3_S = 19,
    CLOCKREF_VCLKA4_DIVR = 20,
    CLOCKREF_VCLKA4_DIVR_EMAC = 21,
    CLOCKREF_VCLKA4_S = 22
} clock_ref_t;

/**
 * @brief Enable the clock for the given reference.
 *
 * This function is SAFE for use by peripheral drivers. It is idempotent and
 * performs ONLY enabling actions (clears disable bits for required sources
 * and domains). It does NOT modify dividers, muxes, or PLL settings.
 *
 * @ingroup BSP_CLOCK
 * @param[in] ref  The clock reference to enable.
 * @return 0 on success, -1 if ref is unknown or unsupported.
 *
 * @note Must be called before using the peripheral associated with ref.
 */
int clock_enable(clock_ref_t ref);

/**
 * @brief Query the frequency (in Hz) of the given clock reference.
 *
 * This function is SAFE for use by peripheral drivers. It returns the
 * best-known frequency derived from YAML facts (fixed source frequencies
 * and default dividers). If the frequency cannot be determined (e.g., PLL
 * not configured, divider unknown), returns 0.
 *
 * @ingroup BSP_CLOCK
 * @param[in] ref  The clock reference to query.
 * @return Frequency in Hz, or 0 if unknown or unsupported.
 *
 * @note This function does NOT read hardware registers; it computes frequency
 *       from compile-time defaults and recorded configuration state.
 */
uint32_t clock_get_hz(clock_ref_t ref);

/**
 * @brief Configuration structure for clock modification (APPLICATION-ONLY).
 *
 * This structure allows application code (e.g., main.c) to optionally
 * reconfigure clock dividers. All fields are optional; a value of 0 means
 * "do not change."
 *
 * @ingroup BSP_CLOCK
 */
typedef struct {
    uint32_t vclk_divider;   /**< VCLK divider (1..16), 0=no change */
    uint32_t vclk2_divider;  /**< VCLK2 divider (1..16), 0=no change */
    uint32_t vclk3_divider;  /**< VCLK3 divider (1..16), 0=no change */
    uint32_t vclk4_divider;  /**< VCLK4 divider (1..16), 0=no change */
} clock_config_t;

/**
 * @brief Apply clock configuration (APPLICATION-ONLY).
 *
 * This function is intended ONLY for application code (e.g., main.c or
 * board initialization). Peripheral drivers MUST NOT call this function.
 *
 * Modifies the VCLK, VCLK2, VCLK3, VCLK4 dividers according to the provided
 * configuration. Fields set to 0 are ignored (no change). Dividers out of
 * range (1..16) are rejected.
 *
 * @ingroup BSP_CLOCK
 * @param[in] cfg  Pointer to configuration structure.
 * @return 0 on success, -1 if cfg is NULL or any divider is out of range.
 *
 * @warning APPLICATION-ONLY: Do not call from peripheral drivers.
 * @note This function updates internal tracking state used by clock_get_hz().
 */
int clock_configure(const clock_config_t *cfg);

/**
 * @brief Inline helper: enable VCLK domain.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_vclk(void)
{
    return clock_enable(CLOCKREF_VCLK);
}

/**
 * @brief Inline helper: query VCLK frequency.
 * @ingroup BSP_CLOCK
 */
static inline uint32_t clock_get_vclk_hz(void)
{
    return clock_get_hz(CLOCKREF_VCLK);
}

/**
 * @brief Inline helper: enable HCLK domain.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_hclk(void)
{
    return clock_enable(CLOCKREF_HCLK);
}

/**
 * @brief Inline helper: query HCLK frequency.
 * @ingroup BSP_CLOCK
 */
static inline uint32_t clock_get_hclk_hz(void)
{
    return clock_get_hz(CLOCKREF_HCLK);
}

/**
 * @brief Inline helper: enable GCLK domain.
 * @ingroup BSP_CLOCK
 */
static inline int clock_enable_gclk(void)
{
    return clock_enable(CLOCKREF_GCLK);
}

/**
 * @brief Inline helper: query GCLK frequency.
 * @ingroup BSP_CLOCK
 */
static inline uint32_t clock_get_gclk_hz(void)
{
    return clock_get_hz(CLOCKREF_GCLK);
}

/** @} */ /* end of BSP_CLOCK */

#endif /* CLOCK_H */

