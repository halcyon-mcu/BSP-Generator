/**
 * @file sci_loopback_example.c
 * @brief Example demonstrating SCI loopback self-test.
 * 
 * This example initializes the SCI module, enables transmitter and receiver,
 * configures the frame format and baud rate, then performs a loopback self-test.
 */

#include <stdint.h>
#include "sci.h"

int main(void)
{
    int ret;

    /* Initialize SCI */
    sci_init();

    /* Configure frame format: 8 bits, no parity, 1 stop bit */
    sci_configure_format(8u, SCI_PARITY_NONE, SCI_STOP_BITS_1);

    /* Set baud rate to 115200 */
    sci_set_baudrate(115200u);

    /* Enable transmitter and receiver */
    sci_enable_tx();
    sci_enable_rx();

    /* Perform loopback self-test */
    ret = sci_loopback_test();

    if (ret == 0) {
        /* Test passed */
        while (1) {
            /* Success loop */
        }
    } else {
        /* Test failed */
        while (1) {
            /* Failure loop */
        }
    }

    return 0;
}
