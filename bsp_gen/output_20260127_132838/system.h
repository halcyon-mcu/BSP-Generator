/**
 * @file system.h
 * @brief System initialization and control for TI RM46 MCU
 */

#ifndef SYSTEM_H
#define SYSTEM_H

/**
 * @defgroup BSP_SYSTEM System Control
 * @brief Low-level system initialization (peripherals power-up, base clocks).
 * @{
 */

/**
 * @brief Initialize the system hardware.
 *
 * This function performs early hardware initialization required before
 * main() can safely run:
 * - Brings peripherals out of power-down via PCR registers.
 * - Sets essential SYSTEM control registers.
 * - Enables minimal base clocks (OSCIN, HF/LF LPO, GCLK, HCLK, VCLK).
 *
 * @note Must be called before any peripheral drivers are used.
 * @note Does NOT configure PLL, dividers, or clock mux settings.
 *       Application code should call clock_configure* APIs if needed.
 * @warning This function is not re-entrant and must only be called once,
 *          typically from Reset_Handler_C before main().
 *
 * @ingroup BSP_SYSTEM
 */
void system_init(void);

/** @} */

#endif /* SYSTEM_H */

