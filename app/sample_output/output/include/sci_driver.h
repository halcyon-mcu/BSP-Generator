/* BSP-GEN-META: created_at=2026-03-04T23:26:46-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
#ifndef SCI_DRIVER_H
#define SCI_DRIVER_H

/**
 * @file sci_driver.h
 * @brief Public API for SCI peripheral driver
 * @details Complete public interface for the SCI module including
 *          types, enumerations, structures, and function prototypes.
 *          Provides UART/Serial Communication Interface functionality with
 *          configurable baud rate, parity, data bits, and stop bits.
 */

#include <stdint.h>
#include <stdbool.h>
#include "reg_sci.h"

/**
 * @brief SCI operation status codes
 * @details Return values for SCI driver API functions indicating
 *          success, error conditions, or peripheral state.
 */
typedef enum {
    SCI_STATUS_OK,              /**< Operation completed successfully */
    SCI_STATUS_ERROR,           /**< General error occurred */
    SCI_STATUS_BUSY,            /**< Peripheral is busy */
    SCI_STATUS_TIMEOUT,         /**< Operation timed out */
    SCI_STATUS_INVALID_PARAM,   /**< Invalid parameter provided */
    SCI_STATUS_TX_FULL,         /**< Transmit buffer is full */
    SCI_STATUS_RX_EMPTY,        /**< Receive buffer is empty */
    SCI_STATUS_FRAME_ERROR,     /**< Frame error detected */
    SCI_STATUS_PARITY_ERROR,    /**< Parity error detected */
    SCI_STATUS_OVERRUN_ERROR    /**< Data overrun error detected */
} sci_status_t;

/**
 * @brief Parity configuration options
 * @details Specifies parity bit generation and checking mode.
 */
typedef enum {
    SCI_PARITY_NONE,    /**< No parity bit */
    SCI_PARITY_EVEN,    /**< Even parity */
    SCI_PARITY_ODD      /**< Odd parity */
} sci_parity_t;

/**
 * @brief Stop bits configuration
 * @details Specifies number of stop bits in UART frame.
 */
typedef enum {
    SCI_STOPBITS_1,     /**< 1 stop bit */
    SCI_STOPBITS_2      /**< 2 stop bits */
} sci_stop_bits_t;

/**
 * @brief Data bits configuration
 * @details Specifies number of data bits per frame.
 */
typedef enum {
    SCI_DATABITS_7,     /**< 7 data bits per frame */
    SCI_DATABITS_8      /**< 8 data bits per frame */
} sci_data_bits_t;

/**
 * @brief Interrupt flag options
 * @details Bit flags for enabling/disabling specific int_type sources.
 */
typedef enum {
    SCI_INT_RXRDY,          /**< Receive data ready int_type */
    SCI_INT_TXRDY,          /**< Transmit ready int_type */
    SCI_INT_FRAME_ERROR,    /**< Frame error int_type */
    SCI_INT_PARITY_ERROR,   /**< Parity error int_type */
    SCI_INT_OVERRUN_ERROR,  /**< Overrun error int_type */
    SCI_INT_BREAK_DETECT    /**< Break detection int_type */
} sci_int_flags_t;

/**
 * @brief SCI configuration structure
 * @details Contains all parameters needed to configure the SCI peripheral
 *          for basic UART communication.
 */
typedef struct {
    uint32_t baud_rate;             /**< Baud rate in bits per second */
    sci_data_bits_t data_bits;      /**< Number of data bits (7 or 8) */
    sci_parity_t parity;            /**< Parity mode */
    sci_stop_bits_t stop_bits;      /**< Number of stop bits (1 or 2) */
    bool enable_tx;                 /**< Enable transmitter */
    bool enable_rx;                 /**< Enable receiver */
} sci_config_t;

/**
 * @brief SCI pin electrical configuration
 * @details Configures electrical properties of TX and RX pins including
 *          output driver type and pull resistors.
 */
typedef struct {
    bool tx_push_pull;      /**< TX pin in push-pull mode (true) or open-drain (false) */
    bool rx_push_pull;      /**< RX pin in push-pull mode (true) or open-drain (false) */
    bool tx_pull_enable;    /**< Enable pull resistor on TX pin */
    bool rx_pull_enable;    /**< Enable pull resistor on RX pin */
    bool tx_pull_up;        /**< TX pull resistor direction: pull-up (true) or pull-down (false) */
    bool rx_pull_up;        /**< RX pull resistor direction: pull-up (true) or pull-down (false) */
} sci_pin_config_t;

/**
 * @brief Callback function pointer for int_type events
 * @details User-defined callback invoked from ISR when enabled interrupts occur.
 *
 * @param[in] flags Bitmask of active int_type flags
 */
typedef void (*sci_callback_t)(uint32_t flags);

/**
 * @brief DMA configuration for SCI transfers
 * @details Enables and configures DMA channels for automated RX and TX transfers.
 */
typedef struct {
    bool enable_rx_dma;         /**< Enable DMA for reception */
    bool enable_tx_dma;         /**< Enable DMA for transmission */
    uint8_t rx_dma_channel;     /**< DMA channel number for RX */
    uint8_t tx_dma_channel;     /**< DMA channel number for TX */
} sci_dma_config_t;

/**
 * @brief Initialize the SCI module with specified configuration
 * @details Enables VCLK clock domain, resets module, configures pins and
 *          communication parameters including baud rate, parity, data bits,
 *          and stop bits.
 *
 * @param[in] config Pointer to configuration structure
 * @return Status of initialization
 * @retval SCI_STATUS_OK Initialization successful
 * @retval SCI_STATUS_INVALID_PARAM Invalid configuration parameter
 * @retval SCI_STATUS_ERROR Initialization failed
 */
sci_status_t SCI_Init(const sci_config_t* config);

/**
 * @brief Deinitialize the SCI module and put it in reset state
 * @details Disables the SCI peripheral and places it in low-power reset mode.
 *
 * @return Status of deinitialization
 * @retval SCI_STATUS_OK Deinitialization successful
 */
sci_status_t SCI_Deinit(void);

/**
 * @brief Configure electrical properties of TX and RX pins
 * @details Sets pin modes including push-pull/open-drain output and pull resistors.
 *
 * @param[in] pin_config Pointer to pin configuration structure
 * @return Status of configuration
 * @retval SCI_STATUS_OK Configuration successful
 * @retval SCI_STATUS_INVALID_PARAM Invalid pin configuration
 */
sci_status_t SCI_ConfigurePins(const sci_pin_config_t* pin_config);

/**
 * @brief Set the baud rate
 * @details Calculates and programs baud rate divisor based on VCLK frequency
 *          obtained from PLL service.
 *
 * @param[in] baud_rate Desired baud rate in bits per second
 * @return Status of baud rate configuration
 * @retval SCI_STATUS_OK Baud rate set successfully
 * @retval SCI_STATUS_INVALID_PARAM Baud rate out of valid range
 */
sci_status_t SCI_SetBaudRate(uint32_t baud_rate);

/**
 * @brief Send a single byte
 * @details Blocking call that waits for TX ready before sending data.
 *
 * @param[in] data Byte to transmit
 * @return Status of transmission
 * @retval SCI_STATUS_OK Byte sent successfully
 * @retval SCI_STATUS_TX_FULL Transmit buffer full
 */
sci_status_t SCI_SendByte(uint8_t data);

/**
 * @brief Receive a single byte
 * @details Blocking call that waits for RX ready before reading data.
 *
 * @param[out] data Pointer to store received byte
 * @return Status of reception
 * @retval SCI_STATUS_OK Byte received successfully
 * @retval SCI_STATUS_RX_EMPTY Receive buffer empty
 * @retval SCI_STATUS_FRAME_ERROR Frame error detected
 * @retval SCI_STATUS_PARITY_ERROR Parity error detected
 * @retval SCI_STATUS_OVERRUN_ERROR Overrun error detected
 */
sci_status_t SCI_ReceiveByte(uint8_t* data);

/**
 * @brief Send multiple bytes with timeout
 * @details Transmits a buffer of data with timeout protection. Updates length
 *          parameter with actual number of bytes sent.
 *
 * @param[in] data Pointer to data buffer to transmit
 * @param[in,out] length Number of bytes to send; updated with bytes actually sent
 * @param[in] timeout_ms Timeout in milliseconds
 * @return Status of transmission
 * @retval SCI_STATUS_OK All data sent successfully
 * @retval SCI_STATUS_TIMEOUT Timeout occurred before all data sent
 * @retval SCI_STATUS_INVALID_PARAM Invalid pointer or length
 */
sci_status_t SCI_SendData(const uint8_t* data, uint32_t length, uint32_t timeout_ms);

/**
 * @brief Receive multiple bytes with timeout
 * @details Receives data into buffer with timeout protection. Updates length
 *          parameter with actual number of bytes received.
 *
 * @param[out] data Pointer to buffer for received data
 * @param[in,out] length Number of bytes to receive; updated with bytes actually received
 * @param[in] timeout_ms Timeout in milliseconds
 * @return Status of reception
 * @retval SCI_STATUS_OK All data received successfully
 * @retval SCI_STATUS_TIMEOUT Timeout occurred before all data received
 * @retval SCI_STATUS_INVALID_PARAM Invalid pointer or length
 */
sci_status_t SCI_ReceiveData(uint8_t* data, uint32_t length, uint32_t timeout_ms);

/**
 * @brief Check if transmitter is ready to accept new data
 *
 * @return Transmitter ready status
 * @retval true Transmitter ready for new data
 * @retval false Transmitter busy or disabled
 */
bool SCI_IsTxReady(void);

/**
 * @brief Check if receiver has data available
 *
 * @return Receiver data available status
 * @retval true Data available in receive buffer
 * @retval false No data available
 */
bool SCI_IsRxReady(void);

/**
 * @brief Get current status flags
 * @details Returns bitmask of current status including TX/RX ready, errors, etc.
 *
 * @return Status flags register value
 */
uint32_t SCI_GetStatus(void);

/**
 * @brief Clear frame error, parity error, and overrun error flags
 * @details Clears all error condition flags in the status register.
 */
void SCI_ClearErrors(void);

/**
 * @brief Enable specified interrupts
 * @details Enables int_type sources specified by bitmask using sci_int_flags_t values.
 *
 * @param[in] int_mask Bitmask of interrupts to enable
 * @return Status of operation
 * @retval SCI_STATUS_OK Interrupts enabled successfully
 */
sci_status_t SCI_EnableInterrupt(uint32_t int_mask);

/**
 * @brief Disable specified interrupts
 * @details Disables int_type sources specified by bitmask using sci_int_flags_t values.
 *
 * @param[in] int_mask Bitmask of interrupts to disable
 * @return Status of operation
 * @retval SCI_STATUS_OK Interrupts disabled successfully
 */
sci_status_t SCI_DisableInterrupt(uint32_t int_mask);

/**
 * @brief Register callback function for int_type events
 * @details Sets user-defined callback to be invoked from ISR when enabled interrupts occur.
 *
 * @param[in] callback Function pointer to callback handler
 * @return Status of registration
 * @retval SCI_STATUS_OK Callback registered successfully
 * @retval SCI_STATUS_INVALID_PARAM NULL callback pointer
 */
sci_status_t SCI_RegisterCallback(sci_callback_t callback);

/**
 * @brief Clear specified int_type flags
 * @details Acknowledges and clears int_type flags specified by bitmask.
 *
 * @param[in] flags Bitmask of int_type flags to clear
 */
void SCI_ClearInterruptFlags(uint32_t flags);

/**
 * @brief Configure DMA channels for RX and TX operations
 * @details Enables and configures DMA for automated data transfers.
 *
 * @param[in] dma_config Pointer to DMA configuration structure
 * @return Status of configuration
 * @retval SCI_STATUS_OK DMA configured successfully
 * @retval SCI_STATUS_INVALID_PARAM Invalid DMA configuration
 */
sci_status_t SCI_ConfigureDMA(const sci_dma_config_t* dma_config);

/**
 * @brief Enable or disable transmitter
 * @details Controls the transmitter enable state.
 *
 * @param[in] enable True to enable transmitter, false to disable
 */
void SCI_EnableTx(bool enable);

/**
 * @brief Enable or disable receiver
 * @details Controls the receiver enable state.
 *
 * @param[in] enable True to enable receiver, false to disable
 */
void SCI_EnableRx(bool enable);

void SCI_EnablePins(void);

/**
 * @brief App-intent usage recipe
 * @details Generated from bringup_contract.app_intent.api_reuse.
 *          Recommended app-level init sequence:
 *          1) SCI_EnablePins (if available)
 *          2) SCI_Init
 *          Recommended string TX path:
 *          - Preferred: SCI_SendData
 *          - Fallback: SCI_SendByte
 *          Avoid manual per-byte string loops when preferred buffer API exists.
 *          Policy mode: warn_only
 */

#endif /* SCI_DRIVER_H */
