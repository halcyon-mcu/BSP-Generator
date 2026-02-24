/**
 * @file vim.h
 * @brief Vectored Interrupt Manager (VIM) driver for TI RM46
 */

#ifndef VIM_H
#define VIM_H

#include <stdint.h>

/**
 * @defgroup BSP_VIM Vectored Interrupt Manager (VIM)
 * @brief VIM driver for system-level interrupt handling on RM46 Cortex-R4.
 *
 * The VIM provides vectored interrupt dispatch for up to 128 channels.
 * Channel 0 is usable but phantom entry occupies table slot 0.
 * Channels 1..126 are available; channel 127 is reserved.
 * @{
 */

/**
 * @brief VIM interrupt service routine function pointer type.
 * @ingroup BSP_VIM
 */
typedef void (*vim_isr_t)(void);

/**
 * @brief Initialize the VIM for vectored interrupts.
 *
 * This function enables parity checking (if available), initializes all
 * vector table entries to a default handler, and prepares the VIM for
 * interrupt registration. No channels are enabled by default.
 *
 * @ingroup BSP_VIM
 * @warning Must be called before registering or enabling any interrupts.
 * @note This function does NOT enable any specific interrupt channels.
 */
void vim_init(void);

/**
 * @brief Register an ISR for a given VIM channel.
 *
 * Stores the ISR address into the VIM vector table entry for the specified
 * channel. The ISR will be invoked when the channel is both enabled and
 * asserted.
 *
 * @ingroup BSP_VIM
 * @param[in] channel_id VIM channel number (0..126, excluding reserved 127).
 * @param[in] isr        Function pointer to the interrupt service routine.
 * @return 0 on success, -1 if channel_id is invalid or reserved.
 * @warning The ISR must follow ARM interrupt handling conventions (save/restore context).
 */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr);

/**
 * @brief Enable a VIM interrupt channel.
 *
 * Sets the corresponding bit in the VIM REQENASET registers to enable
 * the channel. The channel's ISR must be registered before enabling.
 *
 * @ingroup BSP_VIM
 * @param[in] channel_id VIM channel number (0..126, excluding reserved 127).
 * @return 0 on success, -1 if channel_id is invalid or reserved.
 */
int vim_enable_channel(uint32_t channel_id);

/**
 * @brief Disable a VIM interrupt channel.
 *
 * Clears the corresponding bit in the VIM REQENACLR registers to disable
 * the channel. The ISR will not be invoked until re-enabled.
 *
 * @ingroup BSP_VIM
 * @param[in] channel_id VIM channel number (0..126, excluding reserved 127).
 * @return 0 on success, -1 if channel_id is invalid or reserved.
 */
int vim_disable_channel(uint32_t channel_id);

/**
 * @brief Route a VIM channel to FIQ or IRQ.
 *
 * Sets or clears the corresponding bit in the VIM FIRQPR registers to
 * route the channel to FIQ (if enable_fiq=1) or IRQ (if enable_fiq=0).
 *
 * @ingroup BSP_VIM
 * @param[in] channel_id  VIM channel number (0..126, excluding reserved 127).
 * @param[in] enable_fiq  Non-zero to route to FIQ, zero for IRQ.
 * @return 0 on success, -1 if channel_id is invalid or reserved.
 * @note By default, all channels are routed to IRQ.
 */
int vim_set_fiq(uint32_t channel_id, int enable_fiq);

/** @} */ /* end of BSP_VIM */

#endif /* VIM_H */
