/**
 * @file system.h
 * @brief System initialization module for TI Hercules RM46
 */

#ifndef SYSTEM_H
#define SYSTEM_H

/**
 * @defgroup BSP_SYSTEM System Initialization
 * @brief System-level initialization and configuration.
 *
 * This module provides early hardware initialization for the RM46 MCU,
 * including peripheral power control and base clock enable.
 * @{
 */

/**
 * @brief Initialize the system.
 * @ingroup BSP_SYSTEM
 *
 * Performs low-level system initialization by:
 * - Bringing peripherals out of power-down via PCR registers
 * - Configuring system clock control
 * - Enabling base clocks (OSCIN, HF_LPO, LF_LPO, GCLK, HCLK, VCLK)
 *
 * This function must be called early during startup, before any peripheral
 * drivers are initialized.
 *
 * @note Clock configuration (PLL/dividers/mux) is application-owned;
 *       see clock_configure* APIs in clock.h (do not call here).
 * @warning Must be called before main() and before using any peripherals.
 */
void system_init(void);

/** @} */

#endif /* SYSTEM_H */

