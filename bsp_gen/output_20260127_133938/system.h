/**
 * @file system.h
 * @brief System initialization for TI RM46 MCU
 */

#ifndef SYSTEM_H
#define SYSTEM_H

/**
 * @defgroup BSP_SYSTEM System Initialization
 * @brief Low-level system initialization module
 * 
 * Provides minimal hardware initialization including peripheral power-up and base clock enable.
 * @{
 */

/**
 * @brief Initialize the system hardware
 * @ingroup BSP_SYSTEM
 * 
 * Performs early hardware initialization in the following order:
 * 1. Powers up all peripherals via PCR registers
 * 2. Configures minimal system clock control
 * 3. Enables base clocks (OSCIN, HF_LPO, LF_LPO, GCLK, HCLK, VCLK)
 * 
 * @note This function must be called before main() and before any peripheral drivers are used.
 * @note Clock configuration (PLL, dividers, mux) is application-owned; use clock_configure* APIs after system_init().
 * @warning Must be called only once during startup.
 */
void system_init(void);

/** @} */

#endif /* SYSTEM_H */

