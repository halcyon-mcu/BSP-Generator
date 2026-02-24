/**
 * @file sci_mock.c
 * @brief Mock hardware register implementations for SCI (UART) testing
 */

#include "sci_mock.h"
#include <string.h>

sci_mock_registers_t sci_mock_regs = {0};

void sci_mock_init(void)
{
    memset(&sci_mock_regs, 0, sizeof(sci_mock_registers_t));

    /* Set default register values */
    sci_mock_regs.GCR = 0x00000000U;
    sci_mock_regs.FORMAT = 0x00000007U; /* 8 bits, no parity, 1 stop bit */
    sci_mock_regs.BRR = 0x00000001U;    /* Default baud rate divisor */
    sci_mock_regs.tx_head = 0;
    sci_mock_regs.tx_tail = 0;
    sci_mock_regs.tx_count = 0;
    sci_mock_regs.rx_head = 0;
    sci_mock_regs.rx_tail = 0;
    sci_mock_regs.rx_count = 0;
}

void sci_mock_reset(void)
{
    sci_mock_init();
}

bool sci_mock_transmit(uint8_t data)
{
    if (sci_mock_regs.tx_count >= 16)
    {
        return false; /* Buffer full */
    }

    sci_mock_regs.TX_BUFFER[sci_mock_regs.tx_tail] = data;
    sci_mock_regs.tx_tail = (sci_mock_regs.tx_tail + 1) % 16;
    sci_mock_regs.tx_count++;

    return true;
}

bool sci_mock_receive(uint8_t *data)
{
    if (sci_mock_regs.rx_count == 0)
    {
        return false; /* No data available */
    }

    *data = sci_mock_regs.RX_BUFFER[sci_mock_regs.rx_head];
    sci_mock_regs.rx_head = (sci_mock_regs.rx_head + 1) % 16;
    sci_mock_regs.rx_count--;

    return true;
}

bool sci_mock_tx_empty(void)
{
    return sci_mock_regs.tx_count == 0;
}

bool sci_mock_rx_ready(void)
{
    return sci_mock_regs.rx_count > 0;
}

uint32_t sci_mock_get_tx_count(void)
{
    return sci_mock_regs.tx_count;
}

uint32_t sci_mock_get_rx_count(void)
{
    return sci_mock_regs.rx_count;
}

void sci_mock_receive_from_hardware(uint8_t data)
{
    if (sci_mock_regs.rx_count < 16)
    {
        sci_mock_regs.RX_BUFFER[sci_mock_regs.rx_tail] = data;
        sci_mock_regs.rx_tail = (sci_mock_regs.rx_tail + 1) % 16;
        sci_mock_regs.rx_count++;
    }
}
