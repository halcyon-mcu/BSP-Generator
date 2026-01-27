/**
 * @file system.h
 * @brief System initialization and control for TI RM46 Hercules MCU
 */

#ifndef SYSTEM_H
#define SYSTEM_H

/**
 * @defgroup BSP_SYSTEM System Control
 * @brief System-level initialization and configuration
 * @{
 */

/**
 * @brief Initialize the system
 *
 * Performs early hardware initialization including peripheral power control
 * and base clock enablement. Must be called before any peripheral drivers
 * or application code.
 *
 * This function:
 * - Brings peripherals out of power-down state
 * - Enables base clocks (OSCIN, LPOs, GCLK, HCLK, VCLK)
 * - Does NOT configure PLLs, dividers, or clock muxes (application-owned)
 *
 * @note Must be called early in the boot sequence, before main().
 * @note Clock configuration (PLL/dividers/mux) is application-owned;
 *       see clock_configure* APIs in clock.h.
 *
 * @ingroup BSP_SYSTEM
 */
void system_init(void);

/** @} */

#endif /* SYSTEM_H */

