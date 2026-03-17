/* BSP-GEN-META: created_at=2026-03-04T23:27:00-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file lin_driver.c
 * @brief LIN peripheral driver implementation
 * @details Complete implementation including initialization, configuration,
 *          and operational functions for SCI/LIN module.
 */

#include "lin_driver.h"
#include "reg_lin.h"
#include "pll_driver.h"
#include "iomm_driver.h"
#include <stddef.h>

/*==============================================================================
                                PRIVATE DEFINES
==============================================================================*/

/* Base address definition */
#define LIN_BASE_ADDR (0xFFF7E400U)
#define LIN ((LIN_REG_MAP_t *)LIN_BASE_ADDR)

/* Timeout definitions */
#define LIN_TIMEOUT_INFINITE 0xFFFFFFFFU

/*==============================================================================
                             PRIVATE VARIABLES
==============================================================================*/

/** @brief Registered callback for int_type events */
static lin_callback_t g_lin_callback = NULL;

/** @brief Current DMA configuration */
static lin_dma_config_t g_dma_config = {0};

/*==============================================================================
                         PRIVATE FUNCTION PROTOTYPES
==============================================================================*/

/**
 * @brief Calculate BRS register value for target baud rate
 * @internal
 */
static uint32_t LIN_CalculateBRS(uint32_t vclk_hz, uint32_t baud_rate);

/**
 * @brief Check if TX is ready
 * @internal
 */
static bool LIN_CheckTxReady(void);

/**
 * @brief Check if RX is ready
 * @internal
 */
static bool LIN_CheckRxReady(void);

/*==============================================================================
                         PUBLIC FUNCTION IMPLEMENTATIONS
==============================================================================*/

/**
 * @brief Configure IOMM pins for LIN module
 *
 * Configures package pins 38 (SCIRX) and 39 (SCITX) for LIN functionality.
 * This function must be called before LIN_Init().
 */
void LIN_EnablePins(void)
{
    iomm_status_t status;

    /* Unlock IOMM registers */
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
 * @brief Initialize LIN module with specified configuration
 *
 * Performs complete initialization sequence:
 * 1. Enable peripheral clock
 * 2. Reset module
 * 3. Clear interrupts
 * 4. Configure SCIPIO registers
 * 5. Configure communication parameters
 * 6. Set data format
 * 7. Enable module
 *
 * @param config Pointer to configuration structure
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_INVALID_PARAM Invalid configuration parameter
 */
lin_status_t LIN_Init(const lin_config_t* config)
{
    uint32_t gcr1_value;
    uint32_t format_value;
    uint32_t brs_value;
    uint32_t vclk_hz;

    /* Parameter validation */
    if (config == NULL) {
        return LIN_STATUS_INVALID_PARAM;
    }

    if (config->data_bits < 1U || config->data_bits > 8U) {
        return LIN_STATUS_INVALID_PARAM;
    }

    /* Step 1: Enable peripheral clock (MANDATORY - must be first) */
    PLL_EnableClock(CLOCKDOMAIN_VCLK);

    /* Step 2: Reset module */
    LIN->SCIGCR0 = 0x00000000U;  /* Put in reset */
    LIN->SCIGCR0 = 0x00000001U;  /* Release from reset */

    /* Step 3: Clear all interrupts */
    LIN->SCICLEARINT = 0xFFFFFFFFU;
    LIN->SCICLEARINTLVL = 0xFFFFFFFFU;

    /* Step 4: Configure SCIPIO registers (pin electrical properties) */
    /* CRITICAL: SCIPIO0 must always enable TX/RX functional bits in SCI mode */
    LIN->SCIPIO0 = 0x00000006U;  /* TX (bit 2) and RX (bit 1) in SCI functional mode */
    LIN->SCIPIO1 = 0x00000000U;  /* Pin directions (handled by SCI module) */
    LIN->SCIPIO3 = 0x00000000U;  /* Pin output default values */

    /* Configure pin modes (push-pull vs open-drain) */
    if (config->tx_pin_mode == LIN_PIN_OPENDRAIN) {
        LIN->SCIPIO6 = LIN->SCIPIO6 | 0x00000004U;  /* TX open drain */
    } else {
        LIN->SCIPIO6 = LIN->SCIPIO6 & ~0x00000004U;  /* TX push-pull */
    }

    if (config->rx_pin_mode == LIN_PIN_OPENDRAIN) {
        LIN->SCIPIO6 = LIN->SCIPIO6 | 0x00000002U;  /* RX open drain */
    } else {
        LIN->SCIPIO6 = LIN->SCIPIO6 & ~0x00000002U;  /* RX push-pull */
    }

    /* Configure pull resistors */
    if (config->enable_tx_pullup) {
        LIN->SCIPIO7 = LIN->SCIPIO7 | 0x00000004U;  /* TX pull enable */
        LIN->SCIPIO8 = LIN->SCIPIO8 | 0x00000004U;  /* TX pull-up select */
    } else {
        LIN->SCIPIO7 = LIN->SCIPIO7 & ~0x00000004U;  /* TX pull disable */
    }

    if (config->enable_rx_pullup) {
        LIN->SCIPIO7 = LIN->SCIPIO7 | 0x00000002U;  /* RX pull enable */
        LIN->SCIPIO8 = LIN->SCIPIO8 | 0x00000002U;  /* RX pull-up select */
    } else {
        LIN->SCIPIO7 = LIN->SCIPIO7 & ~0x00000002U;  /* RX pull disable */
    }

    /* Step 5: Configure communication parameters */
    gcr1_value = 0x00000000U;

    /* CRITICAL: COMM_MODE bit (bit 0) MUST remain 0 for standard 8N1 SCI mode */
    /* DO NOT SET bit 0 - setting it enables 9-bit address-bit mode which causes framing errors */

    /* Set mode (SCI or LIN) */
    if (config->mode == LIN_MODE_LIN) {
        gcr1_value |= LIN_SCIGCR1_LIN_MODE;
    }
    /* else: SCI mode, LIN_MODE bit remains 0 */

    /* Set clock source (internal) */
    gcr1_value |= LIN_SCIGCR1_CLOCK;

    /* Set timing mode (asynchronous) */
    gcr1_value |= LIN_SCIGCR1_TIMING_MODE;

    /* Set parity */
    if (config->parity != LIN_PARITY_NONE) {
        gcr1_value |= LIN_SCIGCR1_PARITY_ENA;
        if (config->parity == LIN_PARITY_ODD) {
            gcr1_value |= LIN_SCIGCR1_PARITY;
        }
    }

    /* Set stop bits */
    if (config->stop_bits == LIN_STOP_BITS_2) {
        gcr1_value |= LIN_SCIGCR1_STOP;
    }

    /* Enable multibuffer mode if requested */
    if (config->enable_multibuffer) {
        gcr1_value |= LIN_SCIGCR1_MBUF_MODE;
    }

    /* Enable transmitter and receiver */
    gcr1_value |= LIN_SCIGCR1_TXENA;
    gcr1_value |= LIN_SCIGCR1_RXENA;

    /* Write SCIGCR1 (but do not set SWnRST yet) */
    LIN->SCIGCR1 = gcr1_value;

    /* Step 6: Set data format */
    format_value = (uint32_t)(config->data_bits - 1U) & 0x07U;
    LIN->SCIFORMAT = format_value;

    /* Configure baud rate */
    vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);
    brs_value = LIN_CalculateBRS(vclk_hz, config->baud_rate);
    LIN->BRS = brs_value;

    /* Configure interrupts if requested */
    if (config->interrupt_mask != 0U) {
        LIN->SCISETINT = config->interrupt_mask;
    }

    /* Step 7: Enable module by setting SWnRST bit */
    LIN->SCIGCR1 = gcr1_value | LIN_SCIGCR1_SWnRST;

    return LIN_STATUS_OK;
}

/**
 * @brief Deinitialize LIN module
 *
 * Disables module, clears interrupts, and resets to default state.
 */
void LIN_Deinit(void)
{
    /* Put module in reset */
    LIN->SCIGCR1 &= ~LIN_SCIGCR1_SWnRST;

    /* Disable transmitter and receiver */
    LIN->SCIGCR1 &= ~(LIN_SCIGCR1_TXENA | LIN_SCIGCR1_RXENA);

    /* Clear all interrupts */
    LIN->SCICLEARINT = 0xFFFFFFFFU;
    LIN->SCICLEARINTLVL = 0xFFFFFFFFU;

    /* Clear callback */
    g_lin_callback = NULL;

    /* Reset module */
    LIN->SCIGCR0 = 0x00000000U;
}

/**
 * @brief Configure baud rate dynamically
 *
 * Updates baud rate without full module reinitialization.
 * Module must be temporarily disabled during rate change.
 *
 * @param baud_rate Target baud rate in bps
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_INVALID_PARAM Invalid baud rate
 */
lin_status_t LIN_SetBaudRate(uint32_t baud_rate)
{
    uint32_t vclk_hz;
    uint32_t brs_value;
    uint32_t gcr1_backup;

    if (baud_rate == 0U) {
        return LIN_STATUS_INVALID_PARAM;
    }

    /* Get current VCLK frequency */
    vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);

    /* Calculate BRS value */
    brs_value = LIN_CalculateBRS(vclk_hz, baud_rate);

    /* Disable module temporarily */
    gcr1_backup = LIN->SCIGCR1;
    LIN->SCIGCR1 &= ~LIN_SCIGCR1_SWnRST;

    /* Update baud rate */
    LIN->BRS = brs_value;

    /* Re-enable module */
    LIN->SCIGCR1 = gcr1_backup;

    return LIN_STATUS_OK;
}

/**
 * @brief Transmit a single byte
 *
 * Blocks until transmitter is ready, then sends byte.
 *
 * @param data Byte to transmit
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_TIMEOUT Transmitter not ready
 */
lin_status_t LIN_TransmitByte(uint8_t data)
{
    uint32_t timeout;

    /* Wait for TX ready */
    timeout = 100000U;
    while (!LIN_CheckTxReady()) {
        timeout--;
        if (timeout == 0U) {
            return LIN_STATUS_TIMEOUT;
        }
    }

    /* Write data to transmit buffer */
    LIN->SCITD = (uint32_t)data & 0xFFU;

    return LIN_STATUS_OK;
}

/**
 * @brief Receive a single byte
 *
 * Blocks until receiver has data available, then reads byte.
 *
 * @param data Pointer to store received byte
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_INVALID_PARAM Null pointer
 * @retval LIN_STATUS_TIMEOUT No data received
 */
lin_status_t LIN_ReceiveByte(uint8_t* data)
{
    uint32_t timeout;

    if (data == NULL) {
        return LIN_STATUS_INVALID_PARAM;
    }

    /* Wait for RX ready */
    timeout = 100000U;
    while (!LIN_CheckRxReady()) {
        timeout--;
        if (timeout == 0U) {
            return LIN_STATUS_TIMEOUT;
        }
    }

    /* Read data from receive buffer */
    *data = (uint8_t)(LIN->SCIRD & 0xFFU);

    return LIN_STATUS_OK;
}

/**
 * @brief Transmit multiple bytes with timeout
 *
 * Sends data array with per-byte timeout. Does NOT abort transmission
 * if RX_EMPTY status is encountered (per LIN transmit loop safety contract).
 *
 * @param data Pointer to data buffer
 * @param length Number of bytes to transmit
 * @param timeout_ms Timeout in milliseconds (0 = infinite)
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_INVALID_PARAM Invalid parameters
 * @retval LIN_STATUS_TIMEOUT Timeout occurred
 * @retval LIN_STATUS_FRAME_ERROR Frame error detected
 * @retval LIN_STATUS_PARITY_ERROR Parity error detected
 * @retval LIN_STATUS_OVERRUN_ERROR Overrun error detected
 */
lin_status_t LIN_Transmit(const uint8_t* data, uint16_t length, uint32_t timeout_ms)
{
    uint16_t i;
    uint32_t timeout_count;
    uint32_t flags;

    if (data == NULL || length == 0U) {
        return LIN_STATUS_INVALID_PARAM;
    }

    /* Calculate timeout count (approximate, depends on VCLK) */
    if (timeout_ms == 0U) {
        timeout_count = LIN_TIMEOUT_INFINITE;
    } else {
        timeout_count = timeout_ms * 1000U;
    }

    /* Transmit each byte */
    for (i = 0U; i < length; i++) {
        uint32_t byte_timeout;

        byte_timeout = timeout_count;

        /* Wait for TX ready */
        while (!LIN_CheckTxReady()) {
            if (byte_timeout != LIN_TIMEOUT_INFINITE) {
                byte_timeout--;
                if (byte_timeout == 0U) {
                    return LIN_STATUS_TIMEOUT;
                }
            }
        }

        /* Write data to transmit buffer */
        LIN->SCITD = (uint32_t)data[i] & 0xFFU;

        /* Check for TX-relevant hard errors (not RX_EMPTY) */
        flags = LIN->SCIFLR;
        if ((flags & LIN_SCIFLR_FE) != 0U) {
            return LIN_STATUS_FRAME_ERROR;
        }
        if ((flags & LIN_SCIFLR_PE) != 0U) {
            return LIN_STATUS_PARITY_ERROR;
        }
        if ((flags & LIN_SCIFLR_OE) != 0U) {
            return LIN_STATUS_OVERRUN_ERROR;
        }
    }

    return LIN_STATUS_OK;
}

/**
 * @brief Receive multiple bytes with timeout
 *
 * Receives data array with per-byte timeout.
 * If timeout_ms is 0, performs non-blocking poll (returns immediately if no data ready).
 *
 * @param data Pointer to data buffer
 * @param length Number of bytes to receive
 * @param timeout_ms Timeout in milliseconds (0 = non-blocking poll)
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_INVALID_PARAM Invalid parameters
 * @retval LIN_STATUS_TIMEOUT Timeout occurred (or no data in non-blocking mode)
 * @retval LIN_STATUS_FRAME_ERROR Frame error detected
 * @retval LIN_STATUS_PARITY_ERROR Parity error detected
 * @retval LIN_STATUS_OVERRUN_ERROR Overrun error detected
 */
lin_status_t LIN_Receive(uint8_t* data, uint16_t length, uint32_t timeout_ms)
{
    uint16_t i;
    uint32_t timeout_count;
    uint32_t flags;

    if (data == NULL || length == 0U) {
        return LIN_STATUS_INVALID_PARAM;
    }

    /* Non-blocking mode: timeout_ms == 0 */
    if (timeout_ms == 0U) {
        /* Check if RX data is ready without waiting */
        if (!LIN_CheckRxReady()) {
            return LIN_STATUS_TIMEOUT;  /* No data ready, return immediately */
        }
        timeout_count = 0U;  /* Single poll per byte */
    } else {
        /* Calculate timeout count (approximate, depends on VCLK) */
        timeout_count = timeout_ms * 1000U;
    }

    /* Receive each byte */
    for (i = 0U; i < length; i++) {
        uint32_t byte_timeout;

        byte_timeout = timeout_count;

        /* Wait for RX ready */
        while (!LIN_CheckRxReady()) {
            if (timeout_ms == 0U || byte_timeout == 0U) {
                /* Non-blocking mode or timeout expired */
                return LIN_STATUS_TIMEOUT;
            }
            byte_timeout--;
        }

        /* Read data from receive buffer */
        data[i] = (uint8_t)(LIN->SCIRD & 0xFFU);

        /* Check for errors */
        flags = LIN->SCIFLR;
        if ((flags & LIN_SCIFLR_FE) != 0U) {
            return LIN_STATUS_FRAME_ERROR;
        }
        if ((flags & LIN_SCIFLR_PE) != 0U) {
            return LIN_STATUS_PARITY_ERROR;
        }
        if ((flags & LIN_SCIFLR_OE) != 0U) {
            return LIN_STATUS_OVERRUN_ERROR;
        }
    }

    return LIN_STATUS_OK;
}

/**
 * @brief Transmit a complete frame using frame descriptor
 *
 * @param frame Pointer to frame descriptor
 * @return lin_status_t Status code
 */
lin_status_t LIN_TransmitFrame(const lin_frame_t* frame)
{
    if (frame == NULL || frame->data == NULL) {
        return LIN_STATUS_INVALID_PARAM;
    }

    return LIN_Transmit(frame->data, frame->length, frame->timeout_ms);
}

/**
 * @brief Receive a complete frame using frame descriptor
 *
 * @param frame Pointer to frame descriptor
 * @return lin_status_t Status code
 */
lin_status_t LIN_ReceiveFrame(lin_frame_t* frame)
{
    if (frame == NULL || frame->data == NULL) {
        return LIN_STATUS_INVALID_PARAM;
    }

    return LIN_Receive(frame->data, frame->length, frame->timeout_ms);
}

/**
 * @brief Check if transmitter is ready for new data
 *
 * @return bool True if TX ready, false otherwise
 */
bool LIN_IsTxReady(void)
{
    return LIN_CheckTxReady();
}

/**
 * @brief Check if receiver has data available
 *
 * @return bool True if RX ready, false otherwise
 */
bool LIN_IsRxReady(void)
{
    return LIN_CheckRxReady();
}

/**
 * @brief Get number of bytes available in receive buffer
 *
 * Note: Hardware does not provide FIFO depth, returns 1 if data available, 0 otherwise.
 *
 * @return uint16_t Number of bytes available (0 or 1)
 */
uint16_t LIN_GetRxCount(void)
{
    if (LIN_CheckRxReady()) {
        return 1U;
    }
    return 0U;
}

/**
 * @brief Flush receive buffer
 *
 * Reads and discards all pending receive data.
 */
void LIN_FlushRx(void)
{
    volatile uint32_t dummy;

    /* Read data while available */
    while (LIN_CheckRxReady()) {
        dummy = LIN->SCIRD;
        (void)dummy;  /* Suppress unused variable warning */
    }
}

/**
 * @brief Flush transmit buffer
 *
 * Waits for transmitter to complete all pending transmissions.
 */
void LIN_FlushTx(void)
{
    /* Wait for TX empty */
    while ((LIN->SCIFLR & LIN_SCIFLR_TX_EMPTY) == 0U) {
        /* Wait */
    }
}

/**
 * @brief Enable specified interrupts
 *
 * @param interrupt_mask Interrupt flags to enable (bitwise OR of lin_interrupt_t values)
 */
void LIN_EnableInterrupt(uint32_t interrupt_mask)
{
    LIN->SCISETINT = interrupt_mask;
}

/**
 * @brief Disable specified interrupts
 *
 * @param interrupt_mask Interrupt flags to disable
 */
void LIN_DisableInterrupt(uint32_t interrupt_mask)
{
    LIN->SCICLEARINT = interrupt_mask;
}

/**
 * @brief Get current int_type status flags
 *
 * @return uint32_t Current int_type status flags
 */
uint32_t LIN_GetInterruptStatus(void)
{
    return LIN->SCIFLR;
}

/**
 * @brief Clear specified int_type flags
 *
 * @param interrupt_mask Interrupt flags to clear
 */
void LIN_ClearInterrupt(uint32_t interrupt_mask)
{
    LIN->SCIFLR = interrupt_mask;
}

/**
 * @brief Register callback function for int_type events
 *
 * @param callback Callback function pointer (NULL to unregister)
 */
void LIN_RegisterCallback(lin_callback_t callback)
{
    g_lin_callback = callback;
}

/**
 * @brief Configure DMA channels for TX/RX operations
 *
 * @param dma_config Pointer to DMA configuration structure
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 * @retval LIN_STATUS_INVALID_PARAM Invalid configuration
 */
lin_status_t LIN_ConfigureDMA(const lin_dma_config_t* dma_config)
{
    if (dma_config == NULL) {
        return LIN_STATUS_INVALID_PARAM;
    }

    /* Store configuration */
    g_dma_config = *dma_config;

    return LIN_STATUS_OK;
}

/**
 * @brief Enable or disable DMA for transmit and/or receive
 *
 * @param enable_tx Enable TX DMA
 * @param enable_rx Enable RX DMA
 */
void LIN_EnableDMA(bool enable_tx, bool enable_rx)
{
    uint32_t setint_value;

    setint_value = 0U;

    if (enable_tx) {
        setint_value |= LIN_SCISETINT_SET_TX_DMA;
    }

    if (enable_rx) {
        setint_value |= LIN_SCISETINT_SET_RX_DMA;
    }

    if (setint_value != 0U) {
        LIN->SCISETINT = setint_value;
    } else {
        /* Disable DMA */
        LIN->SCICLEARINT = LIN_SCISETINT_SET_TX_DMA | LIN_SCISETINT_SET_RX_DMA;
    }
}

/**
 * @brief Get error flags
 *
 * Returns frame error, parity error, and overrun flags.
 *
 * @return uint32_t Error flags from SCIFLR register
 */
uint32_t LIN_GetError(void)
{
    uint32_t flags;

    flags = LIN->SCIFLR;
    return flags & (LIN_SCIFLR_FE | LIN_SCIFLR_PE | LIN_SCIFLR_OE |
                    LIN_SCIFLR_BE | LIN_SCIFLR_CE);
}

/**
 * @brief Clear error flags
 *
 * @param error_mask Error flags to clear
 */
void LIN_ClearError(uint32_t error_mask)
{
    LIN->SCIFLR = error_mask;
}

/**
 * @brief Switch between SCI and LIN modes
 *
 * @param mode Target operating mode
 * @return lin_status_t Status code
 * @retval LIN_STATUS_OK Success
 */
lin_status_t LIN_SetMode(lin_mode_t mode)
{
    uint32_t gcr1_value;

    /* Disable module */
    gcr1_value = LIN->SCIGCR1;
    LIN->SCIGCR1 = gcr1_value & ~LIN_SCIGCR1_SWnRST;

    /* Update mode */
    if (mode == LIN_MODE_LIN) {
        gcr1_value |= LIN_SCIGCR1_LIN_MODE;
    } else {
        gcr1_value &= ~LIN_SCIGCR1_LIN_MODE;
    }

    /* Re-enable module */
    LIN->SCIGCR1 = gcr1_value;

    return LIN_STATUS_OK;
}

/**
 * @brief Send LIN break signal
 *
 * Sends LIN break (13 dominant bits) for LIN protocol.
 * Only valid in LIN mode.
 */
void LIN_SendBreak(void)
{
    /* Set GEN_WU bit to generate break field */
    LIN->SCIGCR2 |= LIN_SCIGCR2_GEN_WU;
}

/**
 * @brief Interrupt service routine for LIN module
 *
 * Called by VIM when LIN int_type occurs. Reads int_type vector,
 * dispatches to callback, and clears flags.
 */
void LIN_IRQHandler(void)
{
    uint32_t vec0;
    uint32_t flags;

    /* Read int_type vector */
    vec0 = LIN->SCIINTVECT0 & LIN_SCIINTVECT0_INTVECT0_MASK;

    /* Get flags */
    flags = LIN->SCIFLR;

    /* Call registered callback */
    if (g_lin_callback != NULL) {
        g_lin_callback(flags);
    }

    /* Clear int_type flags */
    LIN->SCIFLR = flags;
}

/*==============================================================================
                        PRIVATE FUNCTION IMPLEMENTATIONS
==============================================================================*/

/**
 * @brief Calculate BRS register value for target baud rate
 *
 * Uses standard SCI baud rate formula: VCLK / (16 * (P + 1))
 * where P is the 24-bit prescaler value.
 *
 * @param vclk_hz VCLK frequency in Hz
 * @param baud_rate Target baud rate in bps
 * @return uint32_t BRS register value
 * @internal
 */
static uint32_t LIN_CalculateBRS(uint32_t vclk_hz, uint32_t baud_rate)
{
    uint32_t prescaler;

    /* Calculate prescaler: P = (VCLK / (16 * baud)) - 1 */
    prescaler = (vclk_hz / (16U * baud_rate));

    if (prescaler > 0U) {
        prescaler = prescaler - 1U;
    }

    /* Limit to 24-bit value */
    if (prescaler > 0x00FFFFFFU) {
        prescaler = 0x00FFFFFFU;
    }

    return prescaler;
}

/**
 * @brief Check if TX is ready
 *
 * @return bool True if transmitter ready, false otherwise
 * @internal
 */
static bool LIN_CheckTxReady(void)
{
    return ((LIN->SCIFLR & LIN_SCIFLR_TXRDY) != 0U);
}

/**
 * @brief Check if RX is ready
 *
 * @return bool True if receiver has data, false otherwise
 * @internal
 */
static bool LIN_CheckRxReady(void)
{
    return ((LIN->SCIFLR & LIN_SCIFLR_RXRDY) != 0U);
}
