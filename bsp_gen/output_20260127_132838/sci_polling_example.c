/**
 * @file sci_polling_example.c
 * @brief Example demonstrating SCI polling transmit and receive.
 * 
 * This example initializes the SCI module, configures it, and performs
 * blocking transmit and receive operations without using interrupts.
 */

#include <stdint.h>
#include "sci.h"

int main(void)
{
    uint8_t tx_data[5];
    uint8_t rx_data[5];
    int ret;
    uint32_t i;

    /* Initialize SCI */
    sci_init();

    /* Configure frame format: 8 bits, no parity, 1 stop bit */
    sci_configure_format(8u, SCI_PARITY_NONE, SCI_STOP_BITS_1);

    /* Set baud rate to 9600 */
    sci_set_baudrate(9600u);

    /* Enable transmitter and receiver */
    sci_enable_tx();
    sci_enable_rx();

    /* Prepare test data */
    tx_data[0] = 0x48u; /* 'H' */
    tx_data[1] = 0x65u; /* 'e' */
    tx_data[2] = 0x6Cu; /* 'l' */
    tx_data[3] = 0x6Cu; /* 'l' */
    tx_data[4] = 0x6Fu; /* 'o' */

    /* Transmit data */
    ret = sci_write(tx_data, 5u);
    if (ret != 5) {
        /* Transmit failed */
        while (1) {
            /* Error loop */
        }
    }

    /* Receive data (assuming external loopback or another device) */
    ret = sci_read(rx_data, 5u);
    if (ret != 5) {
        /* Receive failed */
        while (1) {
            /* Error loop */
        }
    }

    /* Verify received data */
    for (i = 0; i < 5u; i++) {
        if (rx_data[i] != tx_data[i]) {
            /* Data mismatch */
            while (1) {
                /* Error loop */
            }
        }
    }

    /* Success */
    while (1) {
        /* Idle loop */
    }

    return 0;
}
