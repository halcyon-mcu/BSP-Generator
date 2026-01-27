/**
 * @file system.h
 * @brief System initialization and control for TI Hercules RM46
 */

#ifndef SYSTEM_H
#define SYSTEM_H

/**
 * @defgroup BSP_SYSTEM System Initialization
 * @brief Low-level system initialization (peripherals, power, base clocks).
 * @{
 */

/**
 * @brief Initialize the system.
 * @ingroup BSP_SYSTEM
 *
 * Performs low-level hardware initialization:
 * - Powers up peripheral domains (PCR).
 * - Enables peripheral clock control.
 * - Enables base clocks (OSCIN, HF_LPO, LF_LPO, GCLK, HCLK, VCLK).
 *
 * This function must be called before any peripheral initialization.
 * It does NOT configure PLLs, dividers, or clock muxes; those are
 * application responsibilities via the clock module APIs.
 *
 * @note Must be called early in startup, before main().
 * @note Clock configuration (PLL/dividers/mux) is application-owned;
 *       see clock_configure* APIs in clock.h (do not call here).
 */
void system_init(void);

/** @} */

#endif /* SYSTEM_H */

