/* BSP-GEN-META: created_at=2026-03-04T23:29:00-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file app_intent.h
 * @brief Application intent: Interactive LED control via terminal commands
 */

#ifndef APP_INTENT_H
#define APP_INTENT_H

/**
 * @defgroup APP_INTENT Application Intent
 * @brief Interactive LED control application
 * @{
 */

/**
 * @brief Initialize the application intent
 * @details Configures LIN (in SCI mode) for terminal I/O, configures GPIO
 *          for LED control, and prints a welcome screen with instructions.
 *
 * @note Must be called once during startup, after system_init() and PLL_Init().
 */
void APP_INTENT_Init(void);

/**
 * @brief Non-blocking application step function
 * @details Polls for UART input, processes commands, and controls LEDs.
 *          Must be called repeatedly from the main loop.
 *
 * @note This function is non-blocking and returns immediately if no input is available.
 */
void APP_INTENT_Step(void);

/** @} */

#endif /* APP_INTENT_H */
