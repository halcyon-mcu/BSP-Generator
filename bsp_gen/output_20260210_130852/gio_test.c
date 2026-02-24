/**
 * @file gio_test.c
 * @brief Unit tests for GPIO (GIO) driver with mocked hardware
 *
 * This test suite validates the GIO driver implementation against
 * the TI RM46 hardware specification using mocked registers.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include "gio_mock.h"

/* ============================================================================
 * Test Framework Macros
 * ========================================================================== */

#define TEST_PASS (1)
#define TEST_FAIL (0)

typedef struct
{
    int total;
    int passed;
    int failed;
} test_stats_t;

test_stats_t stats = {0, 0, 0};

#define ASSERT(condition, message)                                \
    do                                                            \
    {                                                             \
        stats.total++;                                            \
        if (condition)                                            \
        {                                                         \
            stats.passed++;                                       \
            printf("  [PASS] %s\n", message);                     \
        }                                                         \
        else                                                      \
        {                                                         \
            stats.failed++;                                       \
            printf("  [FAIL] %s (line %d)\n", message, __LINE__); \
        }                                                         \
    } while (0)

#define ASSERT_EQUAL(actual, expected, message)                                \
    do                                                                         \
    {                                                                          \
        stats.total++;                                                         \
        if ((actual) == (expected))                                            \
        {                                                                      \
            stats.passed++;                                                    \
            printf("  [PASS] %s\n", message);                                  \
        }                                                                      \
        else                                                                   \
        {                                                                      \
            stats.failed++;                                                    \
            printf("  [FAIL] %s: got 0x%08X, expected 0x%08X\n",               \
                   message, (unsigned int)(actual), (unsigned int)(expected)); \
        }                                                                      \
    } while (0)

#define TEST_SUITE(name)                                                                            \
    printf("\n================================================================================\n"); \
    printf(" Test Suite: %s\n", name);                                                              \
    printf("================================================================================\n")

#define TEST_CASE(name) \
    printf("\nTest Case: %s\n", name)

/* ============================================================================
 * Test Cases
 * ========================================================================== */

void test_mock_initialization(void)
{
    TEST_CASE("Mock Initialization");

    gio_mock_init();

    ASSERT_EQUAL(gio_mock_regs.GIO_DOUT_A, 0x00000000U,
                 "Port A output starts at 0");
    ASSERT_EQUAL(gio_mock_regs.GIO_DIR_A, 0xFFFFFFFFU,
                 "Port A all pins configured as inputs");
    ASSERT_EQUAL(gio_mock_regs.GIO_DOUT_B, 0x00000000U,
                 "Port B output starts at 0");
    ASSERT_EQUAL(gio_mock_regs.GIO_DIR_B, 0xFFFFFFFFU,
                 "Port B all pins configured as inputs");
}

void test_mock_reset(void)
{
    TEST_CASE("Mock Reset");

    /* Set some state */
    gio_mock_regs.GIO_DOUT_A = 0xDEADBEEFU;
    gio_mock_regs.GIO_DOUT_B = 0xCAFEBABEU;

    /* Reset */
    gio_mock_reset();

    ASSERT_EQUAL(gio_mock_regs.GIO_DOUT_A, 0x00000000U,
                 "Port A cleared after reset");
    ASSERT_EQUAL(gio_mock_regs.GIO_DOUT_B, 0x00000000U,
                 "Port B cleared after reset");
}

void test_set_single_pin(void)
{
    TEST_CASE("Set Single Pin");

    gio_mock_init();

    /* Set pin 0 */
    gio_mock_set_pin(0, 0);
    ASSERT(gio_mock_read_pin(0, 0), "Pin 0 set to high");

    /* Set pin 15 */
    gio_mock_set_pin(0, 15);
    ASSERT(gio_mock_read_pin(0, 15), "Pin 15 set to high");

    /* Set pin 31 */
    gio_mock_set_pin(0, 31);
    ASSERT(gio_mock_read_pin(0, 31), "Pin 31 set to high");
}

void test_clear_single_pin(void)
{
    TEST_CASE("Clear Single Pin");

    gio_mock_init();

    /* Set all pins first */
    gio_mock_write_port(0, 0xFFFFFFFFU);
    ASSERT_EQUAL(gio_mock_read_port(0), 0xFFFFFFFFU,
                 "Port A all pins set to high");

    /* Clear pin 5 */
    gio_mock_clear_pin(0, 5);
    ASSERT(!gio_mock_read_pin(0, 5), "Pin 5 cleared to low");
    ASSERT(gio_mock_read_pin(0, 4), "Adjacent pin 4 still high");
    ASSERT(gio_mock_read_pin(0, 6), "Adjacent pin 6 still high");
}

void test_toggle_pin(void)
{
    TEST_CASE("Toggle Pin Operation");

    gio_mock_init();

    uint8_t pin = 7;

    /* Toggle 0->1 */
    gio_mock_set_pin(0, pin);
    ASSERT(gio_mock_read_pin(0, pin), "Pin toggled to high");

    /* Toggle 1->0 */
    gio_mock_clear_pin(0, pin);
    ASSERT(!gio_mock_read_pin(0, pin), "Pin toggled back to low");

    /* Toggle 0->1 again */
    gio_mock_set_pin(0, pin);
    ASSERT(gio_mock_read_pin(0, pin), "Pin toggled to high again");
}

void test_multiple_pins(void)
{
    TEST_CASE("Multiple Pins");

    gio_mock_init();

    /* Set even pins */
    gio_mock_set_pin(0, 0);
    gio_mock_set_pin(0, 2);
    gio_mock_set_pin(0, 4);
    gio_mock_set_pin(0, 6);

    ASSERT(gio_mock_read_pin(0, 0), "Pin 0 is high");
    ASSERT(!gio_mock_read_pin(0, 1), "Pin 1 is low");
    ASSERT(gio_mock_read_pin(0, 2), "Pin 2 is high");
    ASSERT(!gio_mock_read_pin(0, 3), "Pin 3 is low");
    ASSERT(gio_mock_read_pin(0, 4), "Pin 4 is high");
}

void test_port_write(void)
{
    TEST_CASE("Port Write Operation");

    gio_mock_init();

    uint32_t pattern = 0xAAAAAAAAU; /* Alternating bits */
    gio_mock_write_port(0, pattern);

    ASSERT_EQUAL(gio_mock_read_port(0), pattern,
                 "Port A shows written pattern");

    /* Write to port B */
    uint32_t pattern2 = 0x55555555U;
    gio_mock_write_port(1, pattern2);

    ASSERT_EQUAL(gio_mock_read_port(1), pattern2,
                 "Port B shows written pattern");
    ASSERT_EQUAL(gio_mock_read_port(0), pattern,
                 "Port A pattern unchanged");
}

void test_port_isolation(void)
{
    TEST_CASE("Port Isolation");

    gio_mock_init();

    /* Modify port A */
    gio_mock_set_pin(0, 5);
    gio_mock_set_pin(0, 10);
    gio_mock_set_pin(0, 15);

    /* Port B should be unaffected */
    ASSERT(!gio_mock_read_pin(1, 5), "Port B pin 5 not affected");
    ASSERT(!gio_mock_read_pin(1, 10), "Port B pin 10 not affected");
    ASSERT(!gio_mock_read_pin(1, 15), "Port B pin 15 not affected");
}

void test_verify_pin(void)
{
    TEST_CASE("Verify Pin Assertion");

    gio_mock_init();

    gio_mock_set_pin(0, 3);

    ASSERT(gio_mock_verify_pin(0, 3, true),
           "Verify pin 3 is high (expected: true)");
    ASSERT(gio_mock_verify_pin(0, 4, false),
           "Verify pin 4 is low (expected: false)");
    ASSERT(!gio_mock_verify_pin(0, 3, false),
           "Verify fails when pin doesn't match");
}

void test_all_pins(void)
{
    TEST_CASE("All Pins in Port");

    gio_mock_init();

    /* Set each pin individually and verify */
    for (int i = 0; i < 32; i++)
    {
        gio_mock_clear_pin(0, i);
        gio_mock_set_pin(0, i);
        ASSERT(gio_mock_read_pin(0, i), "Pin set correctly");
    }
}

void test_port_register_state(void)
{
    TEST_CASE("Register State Consistency");

    gio_mock_init();

    /* Set some pins */
    gio_mock_set_pin(0, 0);
    gio_mock_set_pin(0, 7);
    gio_mock_set_pin(0, 15);

    uint32_t expected = (1U << 0) | (1U << 7) | (1U << 15);
    ASSERT_EQUAL(gio_mock_regs.GIO_DOUT_A, expected,
                 "DOUT register matches set pins");
    ASSERT_EQUAL(gio_mock_regs.GIO_DIN_A, expected,
                 "DIN register reflects DOUT state");
}

/* ============================================================================
 * Test Runner
 * ========================================================================== */

int main(void)
{
    printf("\n");
    printf("╔════════════════════════════════════════════════════════════════════════════════╗\n");
    printf("║                    GPIO (GIO) Driver Unit Test Suite                          ║\n");
    printf("║                         TI RM46 Cortex-R4 MCU                                  ║\n");
    printf("╚════════════════════════════════════════════════════════════════════════════════╝\n");

    TEST_SUITE("GPIO Mock Register Implementation");

    /* Run all test cases */
    test_mock_initialization();
    test_mock_reset();
    test_set_single_pin();
    test_clear_single_pin();
    test_toggle_pin();
    test_multiple_pins();
    test_port_write();
    test_port_isolation();
    test_verify_pin();
    test_all_pins();
    test_port_register_state();

    /* Print summary */
    printf("\n");
    printf("╔════════════════════════════════════════════════════════════════════════════════╗\n");
    printf("║                          Test Summary                                          ║\n");
    printf("╠════════════════════════════════════════════════════════════════════════════════╣\n");
    printf("║  Total Tests:    %3d                                                           ║\n", stats.total);
    printf("║  Passed:         %3d  ✓                                                        ║\n", stats.passed);
    printf("║  Failed:         %3d  %s                                                        ║\n",
           stats.failed, stats.failed > 0 ? "✗" : " ");
    printf("║  Success Rate:   %.1f%%                                                         ║\n",
           (float)stats.passed / stats.total * 100.0);
    printf("╚════════════════════════════════════════════════════════════════════════════════╝\n");
    printf("\n");

    /* Return appropriate exit code */
    return (stats.failed == 0) ? EXIT_SUCCESS : EXIT_FAILURE;
}
