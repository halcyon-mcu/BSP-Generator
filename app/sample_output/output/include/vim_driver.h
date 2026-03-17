/* BSP-GEN-META: created_at=2026-03-04T23:28:06-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file vim_driver.h
 * @brief VIM (Vectored Interrupt Manager) driver for TI RM46
 */

#ifndef VIM_DRIVER_H
#define VIM_DRIVER_H

#include <stdint.h>

/**
 * @defgroup BSP_VIM VIM Driver
 * @brief Vectored Interrupt Manager (VIM) driver providing interrupt controller initialization and channel management.
 * @{
 */

/**
 * @brief VIM ISR function pointer type
 * @ingroup BSP_VIM
 *
 * User interrupt service routines must match this signature.
 */
typedef void (*vim_isr_t)(void);

/**
 * @brief Initialize the VIM for vectored interrupt mode
 * @ingroup BSP_VIM
 *
 * This function:
 * - Enables VIM parity checking if supported
 * - Initializes all vector table entries to a default handler
 * - Does NOT enable any interrupt channels by default
 *
 * @note Must be called before registering ISRs or enabling channels
 * @warning Does not configure system-level interrupt enable (CPSR I/F bits)
 */
void vim_init(void);

/**
 * @brief Register an ISR for a specific VIM channel
 * @ingroup BSP_VIM
 *
 * Writes the ISR address into the VIM vector table entry corresponding to the given channel.
 *
 * @param[in] channel_id VIM channel number (valid range: 2..126, excluding reserved channels)
 * @param[in] isr Pointer to the interrupt service routine
 * @return 0 on success, -1 if channel_id is invalid or reserved
 *
 * @note Channel 0 is phantom and channel 127 is reserved
 * @note This does not enable the channel; call vim_enable_channel() separately
 */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr);

/**
 * @brief Enable a VIM interrupt channel
 * @ingroup BSP_VIM
 *
 * Sets the corresponding bit in the VIM REQENASET registers to enable the channel.
 *
 * @param[in] channel_id VIM channel number (valid range: 2..126, excluding reserved channels)
 * @return 0 on success, -1 if channel_id is invalid or reserved
 *
 * @note An ISR should be registered with vim_register_isr() before enabling the channel
 */
int vim_enable_channel(uint32_t channel_id);

/**
 * @brief Disable a VIM interrupt channel
 * @ingroup BSP_VIM
 *
 * Sets the corresponding bit in the VIM REQENACLR registers to disable the channel.
 *
 * @param[in] channel_id VIM channel number (valid range: 2..126, excluding reserved channels)
 * @return 0 on success, -1 if channel_id is invalid or reserved
 */
int vim_disable_channel(uint32_t channel_id);

/**
 * @brief Configure a VIM channel as FIQ or IRQ
 * @ingroup BSP_VIM
 *
 * Routes the specified channel to either FIQ or IRQ using the FIRQPR registers.
 *
 * @param[in] channel_id VIM channel number (valid range: 2..126, excluding reserved channels)
 * @param[in] enable_fiq 1 to route to FIQ, 0 to route to IRQ
 * @return 0 on success, -1 if channel_id is invalid or reserved
 *
 * @note Channels 0 and 1 are hardwired to FIQ and cannot be changed
 */
int vim_set_fiq(uint32_t channel_id, int enable_fiq);

/** @} */

#endif /* VIM_DRIVER_H */
