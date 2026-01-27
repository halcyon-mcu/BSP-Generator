SCI (Serial Communication Interface) Driver for TI RM46 (Cortex-R4)
=====================================================================

This driver provides a complete implementation of the SCI/LIN peripheral,
including:

- Initialization and configuration (frame format, baud rate)
- Blocking transmit and receive APIs with timeout
- Interrupt support for level 0 and level 1 IRQs via VIM
- Loopback mode (internal digital and IODFT analog loopback)
- Loopback self-test function for diagnostic purposes
- Status flag reading and clearing
- Example code for polling, interrupt-driven, and loopback modes

USAGE
-----
1. Call sci_init() to initialize the module (enables VCLK, resets, configures pins).
2. Call sci_configure_format() to set character length, parity, and stop bits.
3. Call sci_set_baudrate() to configure the baud rate (uses clock service to get VCLK).
4. Enable TX and RX using sci_enable_tx() and sci_enable_rx().
5. Use sci_write_byte() / sci_read_byte() or sci_write() / sci_read() for data transfer.
6. Optionally, use interrupt APIs to register handlers and enable IRQs.
7. For testing, use sci_loopback_test() to verify the data path.

EXAMPLES
--------
- sci_polling_example.c: Demonstrates blocking transmit and receive.
- sci_interrupt_example.c: Demonstrates interrupt-driven echo operation.
- sci_loopback_example.c: Demonstrates internal loopback self-test.

DEPENDENCIES
------------
- clock.h / clock.c: Provides clock_enable() and clock_get_hz().
- vim.h / vim.c: Provides vim_register_isr(), vim_enable_channel(), vim_disable_channel().

NOTES
-----
- All blocking APIs include bounded timeouts to prevent infinite loops.
- Loopback modes are intended for diagnostic and testing purposes only.
- The driver supports both SCI and LIN modes; LIN-specific features are exposed
  via dedicated registers (LINCOMPARE, LINRD0, LINRD1, LINTD0, LINTD1, etc.).

For more information, refer to the TI RM46L852 Technical Reference Manual.
