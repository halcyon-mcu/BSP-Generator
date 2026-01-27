/**
 * @file sci_interrupt_example.c
 * @brief Example demonstrating SCI interrupt-driven operation.
 * 
 * This example registers interrupt handlers for SCI level 0 and level 1,
 * enables interrupts, and demonstrates how to handle transmit/receive events.
 */

#include <stdint.h>
#include "sci.h"

/* Simple interrupt handler for SCI level 0 (receive) */
void sci_lvl0_handler(void)
{
    uint8_t data;
    int ret;

    /* Check if receive ready */
    if (sci_rx_ready()) {
        ret = sci_read_byte(&data);
        if (ret == 0) {
            /* Echo received byte (simple loopback in ISR) */
            sci_write_byte(data);
        }
    }

    /* Clear interrupt flags as needed */
    sci_clear_flags((1u << 9u)); /* RXRDY bit */
}

int main(void)
{
    /* Initialize SCI */
    sci_init();

    /* Configure frame format: 8 bits, no parity, 1 stop bit */
    sci_configure_format(8u, SCI_PARITY_NONE, SCI_STOP_BITS_1);

    /* Set baud rate to 115200 */
    sci_set_baudrate(115200u);

    /* Enable transmitter and receiver */
    sci_enable_tx();
    sci_enable_rx();

    /* Register ISR for level 0 (receive) */
    sci_register_isr_lvl0(sci_lvl0_handler);

    /* Enable receive interrupt and set to level 0 */
    sci_set_interrupt_level(9u, 0u); /* RX_INT to level 0 */
    sci_enable_interrupt(9u);

    /* Enable IRQ in VIM */
    sci_enable_irq_lvl0();

    /* Main loop (interrupts handle RX/TX) */
    while (1) {
        /* Idle or perform background tasks */
    }

    return 0;
}
