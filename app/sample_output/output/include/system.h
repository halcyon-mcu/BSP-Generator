/* BSP-GEN-META: created_at=2026-03-04T23:27:58-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file system.h
 * @brief TI RM46 System Initialization and Control
 */

#ifndef SYSTEM_H
#define SYSTEM_H

#include <stdint.h>

/**
 * @defgroup BSP_SYSTEM System Initialization and Control
 * @brief System-level initialization and device control APIs for TI RM46
 * @{
 */

/**
 * @brief Initialize the system (chip bring-up sequence)
 * @ingroup BSP_SYSTEM
 *
 * Performs the complete chip bring-up sequence:
 * 1. PCR power domain initialization
 * 2. Flash wait-state configuration
 * 3. Memory initialization and self-test setup
 * 4. PLL configuration and activation
 *
 * This function MUST be called before main() and before any peripheral use.
 * The entry.c Reset_Handler_C will call this automatically.
 *
 * @note This function does NOT configure PLL multiplier/divider settings.
 *       PLL_Init() is called internally with default safe settings.
 *       For custom clock frequencies, call PLL_Configure* APIs in main().
 *
 * @warning Do NOT call this function more than once.
 */
void system_init(void);

/**
 * @brief Get the reset cause from the System Exception Status Register
 * @ingroup BSP_SYSTEM
 *
 * Reads the SYSESR register to determine the reason for the last reset.
 * Possible flags include:
 * - Bit 15: Power-On Reset
 * - Bit 14: Oscillator Fail / PLL Slip Reset
 * - Bit 13: Watchdog Reset
 * - Bit 5: CPU Reset
 * - Bit 4: Software Reset
 * - Bit 3: External Reset
 *
 * @return uint32_t SYSESR register value containing reset cause flags
 *
 * @note Call system_clear_status_flags() after reading to clear the flags.
 */
uint32_t system_get_reset_cause(void);

/**
 * @brief Trigger a software reset of the device
 * @ingroup BSP_SYSTEM
 *
 * Writes the SYSECR register to request a system-wide reset.
 * This function will not return.
 *
 * @warning All volatile state will be lost.
 */
void system_soft_reset(void);

/**
 * @brief Get the device identification value
 * @ingroup BSP_SYSTEM
 *
 * Reads the DEVID register which contains device-specific information:
 * - Platform ID
 * - Device version
 * - Feature flags (ECC, parity, etc.)
 * - Unique device ID
 *
 * @return uint32_t DEVID register value
 */
uint32_t system_get_device_id(void);

/**
 * @brief Clear system exception status flags
 * @ingroup BSP_SYSTEM
 *
 * Writes the SYSESR register back to itself to clear all status flags.
 * This is a write-1-to-clear operation.
 *
 * @note Should be called after reading reset cause with system_get_reset_cause().
 */
void system_clear_status_flags(void);

/** @} */ /* end of BSP_SYSTEM */

#endif /* SYSTEM_H */
