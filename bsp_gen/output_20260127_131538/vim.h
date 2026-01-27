/**
 * @file vim.h
 * @brief Vectored Interrupt Manager (VIM) driver for TI RM46
 */

#ifndef VIM_H
#define VIM_H

#include <stdint.h>

/**
 * @defgroup BSP_VIM Vectored Interrupt Manager
 * @brief VIM interrupt controller driver for RM46
 *
 * This module provides APIs to initialize the VIM interrupt controller,
 * register interrupt service routines (ISRs), and enable/disable individual
 * interrupt channels. The VIM operates in vectored mode with a RAM-based
 * vector table.
 * @{
 */

/**
 * @brief Function pointer type for VIM interrupt service routines.
 * @ingroup BSP_VIM
 */
typedef void (*vim_isr_t)(void);

/**
 * @brief Initialize the VIM interrupt controller.
 * @ingroup BSP_VIM
 *
 * This function:
 * - Enables parity checking on the VIM RAM vector table (if supported).
 * - Initializes all vector table entries to a default handler.
 * - Does NOT enable any interrupt channels (all channels remain disabled).
 *
 * @note Must be called before registering ISRs or enabling channels.
 * @note Does not initialize peripheral clocks or the ARM interrupt controller.
 */
void vim_init(void);

/**
 * @brief Register an ISR for a specific VIM channel.
 * @ingroup BSP_VIM
 *
 * Stores the provided ISR function pointer into the VIM vector table entry
 * corresponding to the given channel ID. The channel is not automatically
 * enabled; call vim_enable_channel() to enable it.
 *
 * @param[in] channel_id VIM channel number (0..126)
 * @param[in] isr        Pointer to the interrupt service routine
 * @return 0 on success, -1 if channel_id is invalid (>= 127 or reserved)
 *
 * @note Channel 127 is reserved and cannot be used.
 * @note This function does not enable the channel.
 */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr);

/**
 * @brief Enable a VIM interrupt channel.
 * @ingroup BSP_VIM
 *
 * Sets the corresponding bit in the VIM REQENASET register to enable the
 * specified channel. The channel will begin generating interrupts when the
 * associated peripheral raises its interrupt request.
 *
 * @param[in] channel_id VIM channel number (0..126)
 * @return 0 on success, -1 if channel_id is invalid
 *
 * @note Ensure an ISR is registered via vim_register_isr() before enabling.
 */
int vim_enable_channel(uint32_t channel_id);

/**
 * @brief Disable a VIM interrupt channel.
 * @ingroup BSP_VIM
 *
 * Clears the corresponding bit in the VIM REQENACLR register to disable the
 * specified channel. The channel will no longer generate interrupts.
 *
 * @param[in] channel_id VIM channel number (0..126)
 * @return 0 on success, -1 if channel_id is invalid
 */
int vim_disable_channel(uint32_t channel_id);

/**
 * @brief Route a VIM channel to FIQ or IRQ.
 * @ingroup BSP_VIM
 *
 * Configures whether the specified channel is routed to FIQ (fast interrupt)
 * or IRQ (normal interrupt) by setting or clearing the corresponding bit in
 * the VIM FIRQPR register.
 *
 * @param[in] channel_id  VIM channel number (0..126)
 * @param[in] enable_fiq  1 to route to FIQ, 0 to route to IRQ
 * @return 0 on success, -1 if channel_id is invalid
 *
 * @note By default, all channels are routed to IRQ.
 */
int vim_set_fiq(uint32_t channel_id, int enable_fiq);

/** @} */ /* end of BSP_VIM */

#endif /* VIM_H */

