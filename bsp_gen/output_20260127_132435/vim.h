/**
 * @file vim.h
 * @brief TI RM46 Vectored Interrupt Manager (VIM) driver
 */

#ifndef VIM_H
#define VIM_H

#include <stdint.h>

/**
 * @defgroup BSP_VIM Vectored Interrupt Manager (VIM)
 * @brief System-level VIM interrupt controller driver for TI RM46 (Cortex-R4).
 *
 * The VIM provides vectored interrupt support with a 128-entry vector table in RAM.
 * Channel 0 is the phantom entry and channel 127 is reserved, leaving channels 0..126
 * available for interrupt sources.
 *
 * @{
 */

/**
 * @brief VIM interrupt service routine function pointer type.
 * @ingroup BSP_VIM
 */
typedef void (*vim_isr_t)(void);

/**
 * @brief Initialize the VIM for vectored interrupts.
 * @ingroup BSP_VIM
 *
 * This function configures the VIM:
 * - Enables parity protection for the vector table (if supported)
 * - Initializes all vector table entries to a default handler
 * - Does NOT enable any specific interrupt channels
 *
 * @note Must be called before registering any ISRs or enabling channels.
 * @note Does not configure system-level clocks or PCR; those are handled elsewhere.
 */
void vim_init(void);

/**
 * @brief Register an ISR for a specific VIM channel.
 * @ingroup BSP_VIM
 *
 * Stores the ISR address into the vector table entry for the given channel.
 *
 * @param[in] channel_id VIM channel number (0..126, excluding reserved channels)
 * @param[in] isr        Pointer to the interrupt service routine
 * @return 0 on success, -1 if channel_id is invalid or reserved
 *
 * @warning Does not enable the channel; call vim_enable_channel() separately.
 */
int vim_register_isr(uint32_t channel_id, vim_isr_t isr);

/**
 * @brief Enable a VIM interrupt channel.
 * @ingroup BSP_VIM
 *
 * Enables the interrupt channel by writing to the appropriate REQENASET register.
 *
 * @param[in] channel_id VIM channel number (0..126, excluding reserved channels)
 * @return 0 on success, -1 if channel_id is invalid or reserved
 *
 * @note The ISR must be registered before enabling the channel.
 */
int vim_enable_channel(uint32_t channel_id);

/**
 * @brief Disable a VIM interrupt channel.
 * @ingroup BSP_VIM
 *
 * Disables the interrupt channel by writing to the appropriate REQENACLR register.
 *
 * @param[in] channel_id VIM channel number (0..126, excluding reserved channels)
 * @return 0 on success, -1 if channel_id is invalid or reserved
 */
int vim_disable_channel(uint32_t channel_id);

/**
 * @brief Configure a channel to route to FIQ instead of IRQ.
 * @ingroup BSP_VIM
 *
 * Uses the FIRQPR registers to route the specified channel to FIQ (fast interrupt)
 * instead of the default IRQ.
 *
 * @param[in] channel_id  VIM channel number (0..126, excluding reserved channels)
 * @param[in] enable_fiq  1 to route to FIQ, 0 to route to IRQ
 * @return 0 on success, -1 if channel_id is invalid or reserved
 */
int vim_set_fiq(uint32_t channel_id, int enable_fiq);

/** @} */ /* end of BSP_VIM */

#endif /* VIM_H */

