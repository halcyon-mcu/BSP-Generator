/**
 * @file vim.h
 * @brief Vectored Interrupt Manager (VIM) driver for TI RM46
 */

#ifndef VIM_H
#define VIM_H

#include <stdint.h>

/**
 * @defgroup BSP_VIM Vectored Interrupt Manager
 * @brief VIM driver providing interrupt controller initialization and channel management.
 *
 * The VIM driver manages the TI RM46 Vectored Interrupt Manager, supporting:
 * - Initialization of the VIM vector table in RAM for vectored mode
 * - Registration of user ISR handlers for individual interrupt channels
 * - Enabling and disabling of interrupt channels
 * - Optional FIQ routing for selected channels
 *
 * The VIM vector table occupies 128 entries in RAM, with entry 0 being a phantom entry.
 * Channel N corresponds to vector table entry (N + 1). Channel 127 is reserved and unusable.
 * Valid user channels are 0..126.
 *
 * @{
 */

/**
 * @brief Function pointer type for VIM interrupt service routines (ISRs).
 *
 * User ISRs must conform to this signature (void return, no parameters).
 */
typedef void (*vim_isr_t)(void);

/**
 * @brief Initialize the VIM for vectored interrupt operation.
 *
 * This function:
 * - Enables VIM parity checking (if supported by hardware)
 * - Initializes all vector table entries to a default handler
 * - Does NOT enable any interrupt channels (all channels remain masked)
 *
 * @note Must be called once during system initialization, before registering or enabling any ISRs.
 * @ingroup BSP_VIM
 */
void vim_init(void);

/**
 * @brief Register a user ISR for a specific interrupt channel.
 *
 * Stores the provided ISR function pointer into the VIM vector table entry for the given channel.
 * The channel must be in the valid range (0..126) and must not be a reserved channel (e.g. 127).
 *
 * @param[in] channel_id  VIM interrupt channel number (0..126, excluding reserved channels)
 * @param[in] isr         Function pointer to the user ISR (must be non-NULL)
 * @return 0 on success, -1 if channel_id is invalid or isr is NULL
 * @note This function does not enable the channel; call vim_enable_channel() to enable the interrupt.
 * @ingroup BSP_VIM
 */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr);

/**
 * @brief Enable an interrupt channel in the VIM.
 *
 * Sets the corresponding bit in the REQENASET register bank to unmask the channel.
 *
 * @param[in] channel_id  VIM interrupt channel number (0..126, excluding reserved channels)
 * @return 0 on success, -1 if channel_id is invalid
 * @warning Ensure the ISR is registered via vim_register_isr() before enabling the channel.
 * @ingroup BSP_VIM
 */
int vim_enable_channel(uint32_t channel_id);

/**
 * @brief Disable an interrupt channel in the VIM.
 *
 * Sets the corresponding bit in the REQENACLR register bank to mask the channel.
 *
 * @param[in] channel_id  VIM interrupt channel number (0..126, excluding reserved channels)
 * @return 0 on success, -1 if channel_id is invalid
 * @ingroup BSP_VIM
 */
int vim_disable_channel(uint32_t channel_id);

/**
 * @brief Route an interrupt channel to FIQ or IRQ mode.
 *
 * Configures the FIRQPR register bank to select FIQ routing (if enable_fiq is non-zero)
 * or IRQ routing (if enable_fiq is zero) for the given channel.
 *
 * @param[in] channel_id   VIM interrupt channel number (0..126, excluding reserved channels)
 * @param[in] enable_fiq   Non-zero to route to FIQ, zero to route to IRQ
 * @return 0 on success, -1 if channel_id is invalid
 * @note By default all channels are routed to IRQ after vim_init().
 * @ingroup BSP_VIM
 */
int vim_set_fiq(uint32_t channel_id, int enable_fiq);

/** @} */ /* end of BSP_VIM */

#endif /* VIM_H */
