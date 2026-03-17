/* BSP-GEN-META: created_at=2026-03-04T23:27:00-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
#ifndef LIN_DRIVER_H
#define LIN_DRIVER_H

/**
 * @file lin_driver.h
 * @brief Public API for LIN peripheral driver
 * @details Complete public interface for the LIN module including
 *          types, enumerations, structures, and function prototypes.
 *          Supports both SCI (UART) and LIN protocol modes with int_type
 *          and DMA capabilities.
 */

#include <stdint.h>
#include <stdbool.h>
#include "reg_lin.h"

/*==============================================================================
                                TYPE DEFINITIONS
==============================================================================*/

/**
 * @brief LIN driver status codes
 * @details Return values for LIN driver API functions indicating
 *          operation success or specific error conditions.
 */
typedef enum {
    LIN_STATUS_OK,              /**< Operation completed successfully */
    LIN_STATUS_ERROR,           /**< General error occurred */
    LIN_STATUS_BUSY,            /**< Peripheral is busy */
    LIN_STATUS_TIMEOUT,         /**< Operation timed out */
    LIN_STATUS_INVALID_PARAM,   /**< Invalid parameter provided */
    LIN_STATUS_TX_FULL,         /**< Transmit buffer is full */
    LIN_STATUS_RX_EMPTY,        /**< Receive buffer is empty */
    LIN_STATUS_FRAME_ERROR,     /**< Frame error detected */
    LIN_STATUS_PARITY_ERROR,    /**< Parity error detected */
    LIN_STATUS_OVERRUN_ERROR    /**< Data overrun error */
} lin_status_t;

/**
 * @brief Operating mode: SCI (UART) or LIN protocol
 * @details Selects between standard UART communication mode
 *          and LIN protocol mode with break/sync field handling.
 */
typedef enum {
    LIN_MODE_SCI,   /**< SCI (UART) mode */
    LIN_MODE_LIN    /**< LIN protocol mode */
} lin_mode_t;

/**
 * @brief Parity configuration
 * @details Parity bit selection for error detection.
 */
typedef enum {
    LIN_PARITY_NONE,    /**< No parity bit */
    LIN_PARITY_EVEN,    /**< Even parity */
    LIN_PARITY_ODD      /**< Odd parity */
} lin_parity_t;

/**
 * @brief Stop bits configuration
 * @details Number of stop bits to append after data transmission.
 */
typedef enum {
    LIN_STOP_BITS_1,    /**< 1 stop bit */
    LIN_STOP_BITS_2     /**< 2 stop bits */
} lin_stop_bits_t;

/**
 * @brief Pin output driver mode
 * @details Configures the electrical characteristics of TX/RX pins.
 */
typedef enum {
    LIN_PIN_PUSHPULL,   /**< Push-pull output driver */
    LIN_PIN_OPENDRAIN   /**< Open-drain output driver */
} lin_pin_mode_t;

/**
 * @brief Interrupt enable flags (bitwise OR combinable)
 * @details Bit flags for enabling/disabling specific int_type sources.
 *          Multiple flags can be combined using bitwise OR.
 */
typedef enum {
    LIN_INT_NONE            = 0x00000000u,  /**< No interrupts */
    LIN_INT_TX_READY        = 0x00000001u,  /**< Transmit ready int_type */
    LIN_INT_RX_READY        = 0x00000002u,  /**< Receive ready int_type */
    LIN_INT_FRAME_ERROR     = 0x00000004u,  /**< Frame error int_type */
    LIN_INT_PARITY_ERROR    = 0x00000008u,  /**< Parity error int_type */
    LIN_INT_OVERRUN_ERROR   = 0x00000010u,  /**< Overrun error int_type */
    LIN_INT_BREAK_DETECT    = 0x00000020u,  /**< Break detect int_type */
    LIN_INT_ALL             = 0xFFFFFFFFu   /**< All interrupts enabled */
} lin_interrupt_t;

/**
 * @brief LIN module configuration structure
 * @details Contains all parameters needed to initialize the LIN peripheral
 *          including communication settings, pin modes, and int_type configuration.
 */
typedef struct {
    lin_mode_t mode;                /**< Operating mode (SCI or LIN) */
    uint32_t baud_rate;             /**< Baud rate in bits per second */
    uint8_t data_bits;              /**< Number of data bits (typically 8) */
    lin_parity_t parity;            /**< Parity configuration */
    lin_stop_bits_t stop_bits;      /**< Stop bits configuration */
    lin_pin_mode_t tx_pin_mode;     /**< TX pin driver mode */
    lin_pin_mode_t rx_pin_mode;     /**< RX pin driver mode */
    bool enable_tx_pullup;          /**< Enable TX pin pull-up resistor */
    bool enable_rx_pullup;          /**< Enable RX pin pull-up resistor */
    bool enable_multibuffer;        /**< Enable multi-buffer mode */
    uint32_t interrupt_mask;        /**< Interrupt enable mask (lin_interrupt_t flags) */
} lin_config_t;

/**
 * @brief LIN/SCI data frame descriptor
 * @details Describes a data frame for transmission or reception including
 *          pointer to data buffer, length, and timeout parameters.
 */
typedef struct {
    uint8_t* data;          /**< Pointer to data buffer */
    uint16_t length;        /**< Number of bytes in frame */
    uint32_t timeout_ms;    /**< Timeout in milliseconds */
} lin_frame_t;

/**
 * @brief DMA configuration for LIN module
 * @details Configuration parameters for DMA-based transfers on TX and RX channels.
 */
typedef struct {
    bool enable_rx_dma;         /**< Enable DMA for receive operations */
    bool enable_tx_dma;         /**< Enable DMA for transmit operations */
    uint8_t rx_dma_channel;     /**< DMA channel number for RX */
    uint8_t tx_dma_channel;     /**< DMA channel number for TX */
} lin_dma_config_t;

/**
 * @brief Callback function pointer for int_type events
 * @details User-provided callback invoked from ISR when enabled interrupts occur.
 *          Parameter contains active int_type flags.
 */
typedef void (*lin_callback_t)(uint32_t flags);

/*==============================================================================
                            FUNCTION PROTOTYPES
==============================================================================*/

/**
 * @brief Initialize LIN module with specified configuration
 * @details Enables peripheral clock, resets module, configures pins and
 *          communication parameters according to provided configuration structure.
 *
 * @param[in] config Pointer to LIN configuration structure
 * @return Operation status
 * @retval LIN_STATUS_OK Initialization successful
 * @retval LIN_STATUS_INVALID_PARAM Invalid configuration parameter
 * @retval LIN_STATUS_ERROR Initialization failed
 */
lin_status_t LIN_Init(const lin_config_t* config);

/**
 * @brief Deinitialize LIN module, disable clocks and reset to default state
 * @details Disables the LIN peripheral, resets all registers to default values,
 *          and disables peripheral clock to save power.
 */
void LIN_Deinit(void);

/**
 * @brief Configure baud rate dynamically
 * @details Calculates and sets the baud rate prescaler and dividers based on
 *          the VCLK frequency obtained from PLL driver.
 *
 * @param[in] baud_rate Desired baud rate in bits per second
 * @return Operation status
 * @retval LIN_STATUS_OK Baud rate set successfully
 * @retval LIN_STATUS_INVALID_PARAM Baud rate out of supported range
 */
lin_status_t LIN_SetBaudRate(uint32_t baud_rate);

/**
 * @brief Transmit a single byte (blocking until TX ready)
 * @details Waits for transmit buffer to be ready and sends one byte.
 *
 * @param[in] data Byte to transmit
 * @return Operation status
 * @retval LIN_STATUS_OK Byte transmitted successfully
 * @retval LIN_STATUS_TIMEOUT Timeout waiting for TX ready
 */
lin_status_t LIN_TransmitByte(uint8_t data);

/**
 * @brief Receive a single byte (blocking until RX ready)
 * @details Waits for receive buffer to contain data and reads one byte.
 *
 * @param[out] data Pointer to store received byte
 * @return Operation status
 * @retval LIN_STATUS_OK Byte received successfully
 * @retval LIN_STATUS_TIMEOUT Timeout waiting for RX data
 * @retval LIN_STATUS_INVALID_PARAM NULL pointer provided
 */
lin_status_t LIN_ReceiveByte(uint8_t* data);

/**
 * @brief Transmit multiple bytes with timeout
 * @details Sends specified number of bytes from buffer with timeout protection.
 *
 * @param[in] data Pointer to data buffer to transmit
 * @param[in] length Number of bytes to transmit
 * @param[in] timeout_ms Timeout in milliseconds
 * @return Operation status
 * @retval LIN_STATUS_OK All bytes transmitted successfully
 * @retval LIN_STATUS_TIMEOUT Timeout occurred during transmission
 * @retval LIN_STATUS_INVALID_PARAM NULL pointer or invalid length
 */
lin_status_t LIN_Transmit(const uint8_t* data, uint16_t length, uint32_t timeout_ms);

/**
 * @brief Receive multiple bytes with timeout
 * @details Receives specified number of bytes into buffer with timeout protection.
 *
 * @param[out] data Pointer to buffer for received data
 * @param[in] length Number of bytes to receive
 * @param[in] timeout_ms Timeout in milliseconds
 * @return Operation status
 * @retval LIN_STATUS_OK All bytes received successfully
 * @retval LIN_STATUS_TIMEOUT Timeout occurred during reception
 * @retval LIN_STATUS_INVALID_PARAM NULL pointer or invalid length
 */
lin_status_t LIN_Receive(uint8_t* data, uint16_t length, uint32_t timeout_ms);

/**
 * @brief Transmit a complete frame using frame descriptor
 * @details Transmits data frame described by lin_frame_t structure.
 *
 * @param[in] frame Pointer to frame descriptor
 * @return Operation status
 * @retval LIN_STATUS_OK Frame transmitted successfully
 * @retval LIN_STATUS_TIMEOUT Timeout occurred
 * @retval LIN_STATUS_INVALID_PARAM Invalid frame descriptor
 */
lin_status_t LIN_TransmitFrame(const lin_frame_t* frame);

/**
 * @brief Receive a complete frame using frame descriptor
 * @details Receives data frame into buffer described by lin_frame_t structure.
 *
 * @param[in,out] frame Pointer to frame descriptor (data buffer must be allocated)
 * @return Operation status
 * @retval LIN_STATUS_OK Frame received successfully
 * @retval LIN_STATUS_TIMEOUT Timeout occurred
 * @retval LIN_STATUS_INVALID_PARAM Invalid frame descriptor
 */
lin_status_t LIN_ReceiveFrame(lin_frame_t* frame);

/**
 * @brief Check if transmitter is ready for new data
 * @details Non-blocking check of TX ready status flag.
 *
 * @return true if transmitter ready, false otherwise
 */
bool LIN_IsTxReady(void);

/**
 * @brief Check if receiver has data available
 * @details Non-blocking check of RX ready status flag.
 *
 * @return true if data available, false otherwise
 */
bool LIN_IsRxReady(void);

/**
 * @brief Get number of bytes available in receive buffer
 * @details Returns count of bytes currently in RX FIFO or buffer.
 *
 * @return Number of bytes available
 */
uint16_t LIN_GetRxCount(void);

/**
 * @brief Flush receive buffer
 * @details Clears all data from receive buffer/FIFO.
 */
void LIN_FlushRx(void);

/**
 * @brief Flush transmit buffer
 * @details Clears all data from transmit buffer/FIFO.
 */
void LIN_FlushTx(void);

/**
 * @brief Enable specified interrupts (use lin_interrupt_t flags)
 * @details Enables int_type sources specified by bitwise OR of lin_interrupt_t flags.
 *
 * @param[in] interrupt_mask Interrupt flags to enable
 */
void LIN_EnableInterrupt(uint32_t interrupt_mask);

/**
 * @brief Disable specified interrupts
 * @details Disables int_type sources specified by bitwise OR of lin_interrupt_t flags.
 *
 * @param[in] interrupt_mask Interrupt flags to disable
 */
void LIN_DisableInterrupt(uint32_t interrupt_mask);

/**
 * @brief Get current int_type status flags
 * @details Reads and returns pending int_type status bits.
 *
 * @return Interrupt status flags (bitwise OR of lin_interrupt_t values)
 */
uint32_t LIN_GetInterruptStatus(void);

/**
 * @brief Clear specified int_type flags
 * @details Clears (acknowledges) specified int_type status bits.
 *
 * @param[in] interrupt_mask Interrupt flags to clear
 */
void LIN_ClearInterrupt(uint32_t interrupt_mask);

/**
 * @brief Register callback function for int_type events
 * @details Sets user callback to be invoked from ISR when interrupts occur.
 *
 * @param[in] callback Function pointer to callback (NULL to unregister)
 */
void LIN_RegisterCallback(lin_callback_t callback);

/**
 * @brief Configure DMA channels for TX/RX operations
 * @details Configures DMA controller channels for LIN transmit and receive operations.
 *
 * @param[in] dma_config Pointer to DMA configuration structure
 * @return Operation status
 * @retval LIN_STATUS_OK DMA configured successfully
 * @retval LIN_STATUS_INVALID_PARAM Invalid DMA configuration
 */
lin_status_t LIN_ConfigureDMA(const lin_dma_config_t* dma_config);

/**
 * @brief Enable or disable DMA for transmit and/or receive
 * @details Runtime control to enable/disable DMA transfers.
 *
 * @param[in] enable_tx Enable DMA for transmit if true
 * @param[in] enable_rx Enable DMA for receive if true
 */
void LIN_EnableDMA(bool enable_tx, bool enable_rx);

/**
 * @brief Get error flags (frame error, parity error, overrun)
 * @details Reads and returns current error status flags.
 *
 * @return Error flags (bitwise OR of error conditions)
 */
uint32_t LIN_GetError(void);

/**
 * @brief Clear error flags
 * @details Clears specified error status bits.
 *
 * @param[in] error_mask Error flags to clear
 */
void LIN_ClearError(uint32_t error_mask);

/**
 * @brief Switch between SCI and LIN modes
 * @details Dynamically changes operating mode between standard SCI (UART)
 *          and LIN protocol mode.
 *
 * @param[in] mode Desired operating mode
 * @return Operation status
 * @retval LIN_STATUS_OK Mode changed successfully
 * @retval LIN_STATUS_BUSY Cannot change mode while busy
 */
lin_status_t LIN_SetMode(lin_mode_t mode);

/**
 * @brief Send LIN break signal (for LIN mode)
 * @details Transmits LIN break field (dominant level for >13 bit times).
 *          Used for LIN frame synchronization.
 */
void LIN_SendBreak(void);

/**
 * @brief Interrupt service routine for LIN module (called by VIM)
 * @details ISR that handles all LIN interrupts, clears flags, and invokes
 *          registered callback with active int_type flags.
 */
void LIN_IRQHandler(void);

void LIN_EnablePins(void);

/**
 * @brief App-intent usage recipe
 * @details Generated from bringup_contract.app_intent.api_reuse.
 *          Recommended app-level init sequence:
 *          1) LIN_EnablePins (if available)
 *          2) LIN_Init
 *          Recommended string TX path:
 *          - Preferred: LIN_Transmit
 *          - Fallback: LIN_TransmitByte
 *          Avoid manual per-byte string loops when preferred buffer API exists.
 *          Policy mode: warn_only
 */

#endif /* LIN_DRIVER_H */
