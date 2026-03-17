/* BSP-GEN-META: created_at=2026-03-04T23:26:46-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file sci_driver.c
 * @brief SCI peripheral driver implementation
 * @details Complete implementation of the Serial Communication Interface (SCI) driver
 *          including initialization, configuration, transmit/receive operations, int_type
 *          handling, and DMA support. Implements UART functionality with configurable
 *          baud rate, parity, data bits, and stop bits.
 */

#include "sci_driver.h"
#include "reg_sci.h"
#include "pll_driver.h"
#include "iomm_driver.h"
#include <stddef.h>

/* SCI peripheral base address and register access */
#define SCI_BASE_ADDR (0xFFF7E400U)
#define SCI ((SCI_REG_MAP_t *)SCI_BASE_ADDR)

/* Static callback storage */
static sci_callback_t g_sci_callback = NULL;

/* Static configuration cache for re-initialization */
static sci_config_t g_sci_config;

/**
 * @brief Configure IOMM pins for SCI instance
 * @details Configures TX and RX pins using IOMM driver:
 *          - Pin 39: SCITX (PINMMR8[1], AF1)
 *          - Pin 38: SCIRX (PINMMR7[17], AF1)
 */
void SCI_EnablePins(void)
{
    iomm_status_t status;

    /* Unlock IOMM registers for pin configuration */
    IOMM_Unlock();

    /* Configure pin 39 for SCITX (AF1) */
    status = IOMM_ConfigurePin(39, IOMM_PIN_FUNCTION_1);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Configure pin 38 for SCIRX (AF1) */
    status = IOMM_ConfigurePin(38, IOMM_PIN_FUNCTION_1);
    if (status != IOMM_STATUS_OK) {
        IOMM_Lock();
        return;
    }

    /* Lock IOMM registers */
    IOMM_Lock();
}

/**
 * @brief Initialize the SCI module with specified configuration
 * @details Performs complete SCI initialization sequence:
 *          1. Enable VCLK peripheral clock
 *          2. Reset SCI module
 *          3. Clear all interrupts
 *          4. Configure SCIPIO pins for SCI functional mode
 *          5. Configure communication parameters
 *          6. Set data format
 *          7. Enable SCI module
 * @param config Pointer to SCI configuration structure
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Initialization successful
 * @retval SCI_STATUS_INVALID_PARAM Invalid configuration parameter
 */
sci_status_t SCI_Init(const sci_config_t* config)
{
    uint32_t gcr1_value;
    uint32_t format_value;
    sci_status_t status;

    if (config == NULL) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Validate parameters */
    if (config->baud_rate == 0U) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Store configuration for later use */
    g_sci_config = *config;

    /* STEP 1: Enable peripheral clock (MANDATORY - must be first) */
    PLL_EnableClock(CLOCKDOMAIN_VCLK);

    /* STEP 2: Reset module - Put in reset */
    SCI->SCIGCR0 = 0U;

    /* Release from reset */
    SCI->SCIGCR0 = SCI_SCIGCR0_RESET;

    /* STEP 3: Clear all interrupts */
    SCI->SCICLEARINT = 0xFFFFFFFFU;
    SCI->SCICLEARINTLVL = 0xFFFFFFFFU;

    /* STEP 4: Configure SCIPIO registers (pin electrical properties) */
    /* SCIPIO0: TX (bit 2) and RX (bit 1) in SCI functional mode */
    SCI->SCIPIO0 = SCI_SCIPIO0_TX_FUNC | SCI_SCIPIO0_RX_FUNC;

    /* SCIPIO1: Pin directions (handled by SCI module) */
    SCI->SCIPIO1 = 0U;

    /* SCIPIO3: Pin output default values */
    SCI->SCIPIO3 = 0U;

    /* SCIPIO6: Push-pull mode (open drain disabled) */
    SCI->SCIPIO6 = 0U;

    /* SCIPIO7: Pull resistors disabled */
    SCI->SCIPIO7 = 0U;

    /* SCIPIO8: Pull-up select (if enabled by SCIPIO7) */
    SCI->SCIPIO8 = SCI_SCIPIO8_TX_PSL | SCI_SCIPIO8_RX_PSL;

    /* STEP 5: Configure communication parameters */
    gcr1_value = SCI_SCIGCR1_CLOCK | SCI_SCIGCR1_TIMING_MODE;

    /* Configure parity */
    if (config->parity != SCI_PARITY_NONE) {
        gcr1_value |= SCI_SCIGCR1_PARITY_ENA;
        if (config->parity == SCI_PARITY_ODD) {
            gcr1_value |= SCI_SCIGCR1_PARITY;
        }
    }

    /* Configure stop bits */
    if (config->stop_bits == SCI_STOPBITS_2) {
        gcr1_value |= SCI_SCIGCR1_STOP;
    }

    /* Enable TX and RX */
    if (config->enable_tx) {
        gcr1_value |= SCI_SCIGCR1_TXENA;
    }
    if (config->enable_rx) {
        gcr1_value |= SCI_SCIGCR1_RXENA;
    }

    SCI->SCIGCR1 = gcr1_value;

    /* STEP 6: Set data format */
    if (config->data_bits == SCI_DATABITS_7) {
        format_value = 6U;  /* 7-1=6 */
    } else {
        format_value = 7U;  /* 8-1=7 */
    }
    SCI->SCIFORMAT = format_value & SCI_SCIFORMAT_CHAR_MASK;

    /* Set baud rate */
    status = SCI_SetBaudRate(config->baud_rate);
    if (status != SCI_STATUS_OK) {
        return status;
    }

    /* STEP 7: Enable module */
    SCI->SCIGCR1 |= SCI_SCIGCR1_SWnRST;

    return SCI_STATUS_OK;
}

/**
 * @brief Deinitialize the SCI module
 * @details Puts the SCI module in reset state by clearing SWnRST bit
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Deinitialization successful
 */
sci_status_t SCI_Deinit(void)
{
    /* Disable module by clearing SWnRST */
    SCI->SCIGCR1 &= ~SCI_SCIGCR1_SWnRST;

    /* Put in reset */
    SCI->SCIGCR0 = 0U;

    /* Clear callback */
    g_sci_callback = NULL;

    return SCI_STATUS_OK;
}

/**
 * @brief Configure electrical properties of TX and RX pins
 * @details Configures push-pull/open-drain mode and pull resistor settings
 * @param pin_config Pointer to pin configuration structure
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Configuration successful
 * @retval SCI_STATUS_INVALID_PARAM Invalid pin configuration
 */
sci_status_t SCI_ConfigurePins(const sci_pin_config_t* pin_config)
{
    uint32_t scipio6_value;
    uint32_t scipio7_value;
    uint32_t scipio8_value;

    if (pin_config == NULL) {
        return SCI_STATUS_INVALID_PARAM;
    }

    scipio6_value = 0U;
    scipio7_value = 0U;
    scipio8_value = 0U;

    /* Configure push-pull/open-drain mode (SCIPIO6) */
    if (!pin_config->tx_push_pull) {
        scipio6_value |= SCI_SCIPIO6_TX_PDR;
    }
    if (!pin_config->rx_push_pull) {
        scipio6_value |= SCI_SCIPIO6_RX_PDR;
    }

    /* Configure pull resistor enable (SCIPIO7) */
    if (pin_config->tx_pull_enable) {
        scipio7_value |= SCI_SCIPIO7_TX_PD;
    }
    if (pin_config->rx_pull_enable) {
        scipio7_value |= SCI_SCIPIO7_RX_PD;
    }

    /* Configure pull-up/pull-down select (SCIPIO8) */
    if (pin_config->tx_pull_up) {
        scipio8_value |= SCI_SCIPIO8_TX_PSL;
    }
    if (pin_config->rx_pull_up) {
        scipio8_value |= SCI_SCIPIO8_RX_PSL;
    }

    /* Apply configuration */
    SCI->SCIPIO6 = scipio6_value;
    SCI->SCIPIO7 = scipio7_value;
    SCI->SCIPIO8 = scipio8_value;

    return SCI_STATUS_OK;
}

/**
 * @brief Set the baud rate
 * @details Calculates and configures baud rate divisor using VCLK frequency.
 *          Baud rate formula: VCLK / (16 * (BAUD + 1))
 * @param baud_rate Desired baud rate in bits per second
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Baud rate set successfully
 * @retval SCI_STATUS_INVALID_PARAM Invalid baud rate (0 or too high)
 */
sci_status_t SCI_SetBaudRate(uint32_t baud_rate)
{
    uint32_t vclk_hz;
    uint32_t baud_divisor;

    if (baud_rate == 0U) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Get VCLK frequency from PLL service */
    vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);

    if (vclk_hz == 0U) {
        return SCI_STATUS_ERROR;
    }

    /* Calculate baud rate divisor: VCLK / (16 * baud_rate) - 1 */
    baud_divisor = (vclk_hz / (16U * baud_rate));

    if (baud_divisor == 0U) {
        return SCI_STATUS_INVALID_PARAM;
    }

    baud_divisor -= 1U;

    /* Check if divisor fits in 24-bit field */
    if (baud_divisor > SCI_BRS_BAUD_MASK) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Write baud rate divisor */
    SCI->BRS = baud_divisor & SCI_BRS_BAUD_MASK;

    return SCI_STATUS_OK;
}

/**
 * @brief Send a single byte
 * @details Blocking call that waits for TX ready flag before sending
 * @param data Byte to send
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Byte sent successfully
 */
sci_status_t SCI_SendByte(uint8_t data)
{
    /* Wait for TX ready */
    while ((SCI->SCIFLR & SCI_SCIFLR_TXRDY) == 0U) {
        /* Blocking wait */
    }

    /* Write data to transmit register */
    SCI->SCITD = (uint32_t)data & SCI_SCITD_TD_MASK;

    return SCI_STATUS_OK;
}

/**
 * @brief Receive a single byte
 * @details Blocking call that waits for RX ready flag and checks for errors
 * @param data Pointer to store received byte
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Byte received successfully
 * @retval SCI_STATUS_INVALID_PARAM Null pointer
 * @retval SCI_STATUS_FRAME_ERROR Frame error detected
 * @retval SCI_STATUS_PARITY_ERROR Parity error detected
 * @retval SCI_STATUS_OVERRUN_ERROR Overrun error detected
 */
sci_status_t SCI_ReceiveByte(uint8_t* data)
{
    uint32_t flags;

    if (data == NULL) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Wait for RX ready */
    while ((SCI->SCIFLR & SCI_SCIFLR_RXRDY) == 0U) {
        /* Blocking wait */
    }

    /* Check for errors */
    flags = SCI->SCIFLR;

    if ((flags & SCI_SCIFLR_FE) != 0U) {
        return SCI_STATUS_FRAME_ERROR;
    }
    if ((flags & SCI_SCIFLR_PE) != 0U) {
        return SCI_STATUS_PARITY_ERROR;
    }
    if ((flags & SCI_SCIFLR_OE) != 0U) {
        return SCI_STATUS_OVERRUN_ERROR;
    }

    /* Read received data */
    *data = (uint8_t)(SCI->SCIRD & SCI_SCIRD_RD_MASK);

    return SCI_STATUS_OK;
}

/**
 * @brief Send multiple bytes with timeout
 * @details Sends data with timeout protection. Updates length with actual bytes sent.
 * @param data Pointer to data buffer
 * @param length Number of bytes to send (updated with actual count)
 * @param timeout_ms Timeout in milliseconds (0 = non-blocking poll)
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK All bytes sent successfully
 * @retval SCI_STATUS_TIMEOUT Timeout occurred
 * @retval SCI_STATUS_INVALID_PARAM Invalid parameters
 */
sci_status_t SCI_SendData(const uint8_t* data, uint32_t length, uint32_t timeout_ms)
{
    uint32_t i;
    uint32_t timeout_count;
    uint32_t vclk_hz;
    uint32_t ticks_per_ms;

    if (data == NULL || length == 0U) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Get VCLK frequency for timeout calculation */
    vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);
    if (vclk_hz == 0U) {
        return SCI_STATUS_ERROR;
    }

    /* Calculate approximate ticks per millisecond (divide by 1000 for safety margin) */
    ticks_per_ms = vclk_hz / 1000U;

    for (i = 0U; i < length; i++) {
        timeout_count = timeout_ms * ticks_per_ms;

        /* Wait for TX ready with timeout */
        while ((SCI->SCIFLR & SCI_SCIFLR_TXRDY) == 0U) {
            if (timeout_ms != 0U) {
                if (timeout_count == 0U) {
                    return SCI_STATUS_TIMEOUT;
                }
                timeout_count--;
            }
        }

        /* Write data */
        SCI->SCITD = (uint32_t)data[i] & SCI_SCITD_TD_MASK;
    }

    return SCI_STATUS_OK;
}

/**
 * @brief Receive multiple bytes with timeout
 * @details Receives data with timeout and error checking. Updates length with actual bytes received.
 * @param data Pointer to data buffer
 * @param length Number of bytes to receive (updated with actual count)
 * @param timeout_ms Timeout in milliseconds (0 = non-blocking poll)
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK All bytes received successfully
 * @retval SCI_STATUS_TIMEOUT Timeout occurred
 * @retval SCI_STATUS_INVALID_PARAM Invalid parameters
 * @retval SCI_STATUS_FRAME_ERROR Frame error detected
 * @retval SCI_STATUS_PARITY_ERROR Parity error detected
 * @retval SCI_STATUS_OVERRUN_ERROR Overrun error detected
 */
sci_status_t SCI_ReceiveData(uint8_t* data, uint32_t length, uint32_t timeout_ms)
{
    uint32_t i;
    uint32_t timeout_count;
    uint32_t flags;
    uint32_t vclk_hz;
    uint32_t ticks_per_ms;

    if (data == NULL || length == 0U) {
        return SCI_STATUS_INVALID_PARAM;
    }

    /* Get VCLK frequency for timeout calculation */
    vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);
    if (vclk_hz == 0U) {
        return SCI_STATUS_ERROR;
    }

    /* Calculate approximate ticks per millisecond */
    ticks_per_ms = vclk_hz / 1000U;

    for (i = 0U; i < length; i++) {
        timeout_count = timeout_ms * ticks_per_ms;

        /* Wait for RX ready with timeout */
        while ((SCI->SCIFLR & SCI_SCIFLR_RXRDY) == 0U) {
            if (timeout_ms != 0U) {
                if (timeout_count == 0U) {
                    return SCI_STATUS_TIMEOUT;
                }
                timeout_count--;
            }
        }

        /* Check for errors */
        flags = SCI->SCIFLR;

        if ((flags & SCI_SCIFLR_FE) != 0U) {
            return SCI_STATUS_FRAME_ERROR;
        }
        if ((flags & SCI_SCIFLR_PE) != 0U) {
            return SCI_STATUS_PARITY_ERROR;
        }
        if ((flags & SCI_SCIFLR_OE) != 0U) {
            return SCI_STATUS_OVERRUN_ERROR;
        }

        /* Read data */
        data[i] = (uint8_t)(SCI->SCIRD & SCI_SCIRD_RD_MASK);
    }

    return SCI_STATUS_OK;
}

/**
 * @brief Check if transmitter is ready
 * @return bool True if TX ready, false otherwise
 */
bool SCI_IsTxReady(void)
{
    return ((SCI->SCIFLR & SCI_SCIFLR_TXRDY) != 0U);
}

/**
 * @brief Check if receiver has data available
 * @return bool True if RX ready, false otherwise
 */
bool SCI_IsRxReady(void)
{
    return ((SCI->SCIFLR & SCI_SCIFLR_RXRDY) != 0U);
}

/**
 * @brief Get current status flags
 * @details Returns raw SCIFLR register value with all status flags
 * @return uint32_t Status flags register value
 */
uint32_t SCI_GetStatus(void)
{
    return SCI->SCIFLR;
}

/**
 * @brief Clear error flags
 * @details Clears frame error, parity error, and overrun error flags by reading SCIED
 */
void SCI_ClearErrors(void)
{
    volatile uint32_t dummy;

    /* Reading SCIED clears error flags */
    dummy = SCI->SCIED;
    (void)dummy;  /* Prevent unused variable warning */
}

/**
 * @brief Enable specified interrupts
 * @details Enables interrupts using sci_int_flags_t mask values
 * @param int_mask Interrupt mask using SCI_INT_* flags
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Interrupts enabled successfully
 */
sci_status_t SCI_EnableInterrupt(uint32_t int_mask)
{
    uint32_t set_value;

    set_value = 0U;

    /* Map generic flags to hardware bits */
    if ((int_mask & (1U << SCI_INT_RXRDY)) != 0U) {
        set_value |= SCI_SCISETINT_SET_RX_INT;
    }
    if ((int_mask & (1U << SCI_INT_TXRDY)) != 0U) {
        set_value |= SCI_SCISETINT_SET_TX_INT;
    }
    if ((int_mask & (1U << SCI_INT_FRAME_ERROR)) != 0U) {
        set_value |= SCI_SCISETINT_SET_FE_INT;
    }
    if ((int_mask & (1U << SCI_INT_PARITY_ERROR)) != 0U) {
        set_value |= SCI_SCISETINT_SET_PE_INT;
    }
    if ((int_mask & (1U << SCI_INT_OVERRUN_ERROR)) != 0U) {
        set_value |= SCI_SCISETINT_SET_OE_INT;
    }
    if ((int_mask & (1U << SCI_INT_BREAK_DETECT)) != 0U) {
        set_value |= SCI_SCISETINT_SET_BRKDT_INT;
    }

    SCI->SCISETINT = set_value;

    return SCI_STATUS_OK;
}

/**
 * @brief Disable specified interrupts
 * @details Disables interrupts using sci_int_flags_t mask values
 * @param int_mask Interrupt mask using SCI_INT_* flags
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Interrupts disabled successfully
 */
sci_status_t SCI_DisableInterrupt(uint32_t int_mask)
{
    uint32_t clear_value;

    clear_value = 0U;

    /* Map generic flags to hardware bits */
    if ((int_mask & (1U << SCI_INT_RXRDY)) != 0U) {
        clear_value |= SCI_SCICLEARINT_CLR_RX_INT;
    }
    if ((int_mask & (1U << SCI_INT_TXRDY)) != 0U) {
        clear_value |= SCI_SCICLEARINT_CLR_TX_INT;
    }
    if ((int_mask & (1U << SCI_INT_FRAME_ERROR)) != 0U) {
        clear_value |= SCI_SCICLEARINT_CLR_FE_INT;
    }
    if ((int_mask & (1U << SCI_INT_PARITY_ERROR)) != 0U) {
        clear_value |= SCI_SCICLEARINT_CLR_PE_INT;
    }
    if ((int_mask & (1U << SCI_INT_OVERRUN_ERROR)) != 0U) {
        clear_value |= SCI_SCICLEARINT_CLR_OE_INT;
    }
    if ((int_mask & (1U << SCI_INT_BREAK_DETECT)) != 0U) {
        clear_value |= SCI_SCICLEARINT_CLR_BRKDT_INT;
    }

    SCI->SCICLEARINT = clear_value;

    return SCI_STATUS_OK;
}

/**
 * @brief Register callback function for int_type events
 * @param callback Callback function pointer (NULL to unregister)
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK Callback registered successfully
 */
sci_status_t SCI_RegisterCallback(sci_callback_t callback)
{
    g_sci_callback = callback;
    return SCI_STATUS_OK;
}

/**
 * @brief Clear specified int_type flags
 * @details Clears int_type flags by reading appropriate registers
 * @param flags Flags to clear using SCI_INT_* definitions
 */
void SCI_ClearInterruptFlags(uint32_t flags)
{
    volatile uint32_t dummy;

    /* Clear flags by reading data registers */
    if ((flags & ((1U << SCI_INT_RXRDY) | (1U << SCI_INT_FRAME_ERROR) | 
                  (1U << SCI_INT_PARITY_ERROR) | (1U << SCI_INT_OVERRUN_ERROR))) != 0U) {
        dummy = SCI->SCIRD;
        dummy = SCI->SCIED;
        (void)dummy;
    }

    /* Clear break detect flag */
    if ((flags & (1U << SCI_INT_BREAK_DETECT)) != 0U) {
        SCI->SCIFLR = SCI_SCIFLR_BRKDT;
    }
}

/**
 * @brief Configure DMA channels for RX and TX operations
 * @param dma_config Pointer to DMA configuration structure
 * @return sci_status_t Status code
 * @retval SCI_STATUS_OK DMA configured successfully
 * @retval SCI_STATUS_INVALID_PARAM Invalid DMA configuration
 */
sci_status_t SCI_ConfigureDMA(const sci_dma_config_t* dma_config)
{
    uint32_t set_value;
    uint32_t clear_value;

    if (dma_config == NULL) {
        return SCI_STATUS_INVALID_PARAM;
    }

    set_value = 0U;
    clear_value = 0U;

    /* Configure RX DMA */
    if (dma_config->enable_rx_dma) {
        set_value |= SCI_SCISETINT_SET_RX_DMA;
    } else {
        clear_value |= SCI_SCICLEARINT_CLR_RX_DMA;
    }

    /* Configure TX DMA */
    if (dma_config->enable_tx_dma) {
        set_value |= SCI_SCISETINT_SET_TX_DMA;
    } else {
        clear_value |= SCI_SCICLEARINT_CLR_TX_DMA;
    }

    /* Apply configuration */
    if (set_value != 0U) {
        SCI->SCISETINT = set_value;
    }
    if (clear_value != 0U) {
        SCI->SCICLEARINT = clear_value;
    }

    return SCI_STATUS_OK;
}

/**
 * @brief Enable or disable transmitter
 * @param enable True to enable, false to disable
 */
void SCI_EnableTx(bool enable)
{
    if (enable) {
        SCI->SCIGCR1 |= SCI_SCIGCR1_TXENA;
    } else {
        SCI->SCIGCR1 &= ~SCI_SCIGCR1_TXENA;
    }
}

/**
 * @brief Enable or disable receiver
 * @param enable True to enable, false to disable
 */
void SCI_EnableRx(bool enable)
{
    if (enable) {
        SCI->SCIGCR1 |= SCI_SCIGCR1_RXENA;
    } else {
        SCI->SCIGCR1 &= ~SCI_SCIGCR1_RXENA;
    }
}
