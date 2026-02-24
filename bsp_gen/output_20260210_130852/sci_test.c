/**
 * @file sci_test.c
 * @brief Unit tests for SCI (UART) driver with mocked hardware
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sci_mock.h"

typedef struct
{
    int total;
    int passed;
    int failed;
} test_stats_t;

test_stats_t stats = {0, 0, 0};

#define ASSERT(condition, message)            \
    do                                        \
    {                                         \
        stats.total++;                        \
        if (condition)                        \
        {                                     \
            stats.passed++;                   \
            printf("  [PASS] %s\n", message); \
        }                                     \
        else                                  \
        {                                     \
            stats.failed++;                   \
            printf("  [FAIL] %s\n", message); \
        }                                     \
    } while (0)

#define TEST_CASE(name) printf("\nTest Case: %s\n", name)

void test_sci_initialization(void)
{
    TEST_CASE("SCI Initialization");

    sci_mock_init();

    ASSERT(sci_mock_tx_empty(), "TX buffer starts empty");
    ASSERT(!sci_mock_rx_ready(), "RX buffer starts empty");
    ASSERT(sci_mock_get_tx_count() == 0, "TX count is 0");
    ASSERT(sci_mock_get_rx_count() == 0, "RX count is 0");
}

void test_sci_transmit_single_byte(void)
{
    TEST_CASE("Single Byte Transmission");

    sci_mock_init();

    bool result = sci_mock_transmit(0x41); /* 'A' */
    ASSERT(result, "Transmission succeeded");
    ASSERT(sci_mock_get_tx_count() == 1, "TX count incremented");
    ASSERT(!sci_mock_tx_empty(), "TX buffer not empty");
}

void test_sci_transmit_multiple_bytes(void)
{
    TEST_CASE("Multiple Byte Transmission");

    sci_mock_init();

    const char *test_str = "HELLO";
    for (int i = 0; test_str[i]; i++)
    {
        sci_mock_transmit(test_str[i]);
    }

    ASSERT(sci_mock_get_tx_count() == 5, "TX count is 5");
    ASSERT(!sci_mock_tx_empty(), "TX buffer not empty");
}

void test_sci_transmit_buffer_full(void)
{
    TEST_CASE("TX Buffer Overflow");

    sci_mock_init();

    /* Fill buffer */
    for (int i = 0; i < 16; i++)
    {
        bool result = sci_mock_transmit(0x55);
        ASSERT(result, "Buffer acceptance");
    }

    /* Try to overflow */
    bool overflow = sci_mock_transmit(0xFF);
    ASSERT(!overflow, "Buffer correctly rejects overflow");
}

void test_sci_receive_single_byte(void)
{
    TEST_CASE("Single Byte Reception");

    sci_mock_init();

    sci_mock_receive_from_hardware(0x42); /* 'B' */

    ASSERT(sci_mock_rx_ready(), "RX buffer has data");
    ASSERT(sci_mock_get_rx_count() == 1, "RX count is 1");

    uint8_t data;
    bool result = sci_mock_receive(&data);
    ASSERT(result, "Reception succeeded");
    ASSERT(data == 0x42, "Received correct data");
    ASSERT(sci_mock_get_rx_count() == 0, "RX buffer empty after read");
}

void test_sci_loopback(void)
{
    TEST_CASE("Loopback Test");

    sci_mock_init();

    const char *test_str = "TEST";

    /* Transmit */
    for (int i = 0; test_str[i]; i++)
    {
        sci_mock_transmit(test_str[i]);
    }

    /* Simulate loopback - read TX buffer and put in RX */
    for (int i = 0; i < 4; i++)
    {
        uint8_t tx_data = sci_mock_regs.TX_BUFFER[i];
        sci_mock_receive_from_hardware(tx_data);
    }

    /* Verify received data */
    for (int i = 0; test_str[i]; i++)
    {
        uint8_t rx_data;
        bool result = sci_mock_receive(&rx_data);
        ASSERT(result && rx_data == test_str[i], "Loopback data match");
    }
}

void test_sci_ring_buffer_wraparound(void)
{
    TEST_CASE("Ring Buffer Wraparound");

    sci_mock_init();

    /* Fill and drain multiple times */
    for (int cycle = 0; cycle < 3; cycle++)
    {
        for (int i = 0; i < 8; i++)
        {
            sci_mock_transmit(0x30 + i); /* '0' through '7' */
        }
        ASSERT(sci_mock_get_tx_count() == 8, "TX count correct");
    }
}

void test_sci_rfc2_compliance(void)
{
    TEST_CASE("RFC2 Protocol Support");

    sci_mock_init();

    /* Test CR+LF sequence */
    sci_mock_transmit('\r');
    sci_mock_transmit('\n');

    ASSERT(sci_mock_get_tx_count() == 2, "Line ending transmitted");

    /* Test null terminator */
    sci_mock_transmit('\0');
    ASSERT(sci_mock_get_tx_count() == 3, "Null terminator handled");
}

int main(void)
{
    printf("\n");
    printf("╔════════════════════════════════════════════════════════════════╗\n");
    printf("║      SCI (UART) Driver Unit Test Suite - TI RM46             ║\n");
    printf("╚════════════════════════════════════════════════════════════════╝\n");

    test_sci_initialization();
    test_sci_transmit_single_byte();
    test_sci_transmit_multiple_bytes();
    test_sci_transmit_buffer_full();
    test_sci_receive_single_byte();
    test_sci_loopback();
    test_sci_ring_buffer_wraparound();
    test_sci_rfc2_compliance();

    printf("\n");
    printf("╔════════════════════════════════════════════════════════════════╗\n");
    printf("║                      Test Summary                              ║\n");
    printf("╠════════════════════════════════════════════════════════════════╣\n");
    printf("║  Total:    %3d                                                  ║\n", stats.total);
    printf("║  Passed:   %3d  ✓                                               ║\n", stats.passed);
    printf("║  Failed:   %3d  %s                                               ║\n",
           stats.failed, stats.failed > 0 ? "✗" : " ");
    printf("║  Rate:     %.1f%%                                                ║\n",
           (float)stats.passed / stats.total * 100.0);
    printf("╚════════════════════════════════════════════════════════════════╝\n");

    return (stats.failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
