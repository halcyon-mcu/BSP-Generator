/* BSP-GEN-META: created_at=2026-03-04T23:29:00-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file app_intent.c
 * @brief Application intent implementation: Interactive LED control via terminal
 */

#include "app_intent.h"
#include "lin_driver.h"
#include "gio_driver.h"
#include "iomm_driver.h"
#include "board_capabilities.h"
#include <stdint.h>
#include <stdbool.h>

/* ========================================================================== */
/*                           Macros & Constants                               */
/* ========================================================================== */

#define APP_MAGIC_INITIALIZED (0x5A5A5A5Au)

/* ========================================================================== */
/*                            Type Definitions                                */
/* ========================================================================== */

typedef struct {
    uint32_t magic;
    bool terminal_ready;
} app_state_t;

/* ========================================================================== */
/*                          File-Scope Variables                              */
/* ========================================================================== */

static app_state_t s_app_state;

/* ========================================================================== */
/*                          Forward Declarations                              */
/* ========================================================================== */

static void print_welcome_screen(void);
static void print_prompt(void);
static void print_string(const char* str);
static void toggle_led_a(void);
static void toggle_led_b(void);

/* ========================================================================== */
/*                          Function Definitions                              */
/* ========================================================================== */

void APP_INTENT_Init(void)
{    IOMM_Init();
lin_config_t lin_cfg;
    gio_pin_config_t led_cfg;

    /* Configure LIN pins via IOMM */
    {
        iomm_pin_config_t uart_pins[2];
        uart_pins[0].pin_number = BOARD_TERMINAL_UART_RX_PIN;
        uart_pins[0].function = (iomm_pin_function_t)BOARD_TERMINAL_UART_AF;
        uart_pins[1].pin_number = BOARD_TERMINAL_UART_TX_PIN;
        uart_pins[1].function = (iomm_pin_function_t)BOARD_TERMINAL_UART_AF;
        IOMM_ConfigurePins(uart_pins, 2);
    }

    /* Initialize LIN in SCI mode for terminal I/O */
    lin_cfg.mode = LIN_MODE_SCI;
    lin_cfg.baud_rate = 9600;
    lin_cfg.data_bits = 8;
    lin_cfg.parity = LIN_PARITY_NONE;
    lin_cfg.stop_bits = LIN_STOP_BITS_1;
    lin_cfg.tx_pin_mode = LIN_PIN_PUSHPULL;
    lin_cfg.rx_pin_mode = LIN_PIN_PUSHPULL;
    lin_cfg.enable_tx_pullup = false;
    lin_cfg.enable_rx_pullup = false;
    lin_cfg.enable_multibuffer = false;
    lin_cfg.interrupt_mask = 0;
    LIN_Init(&lin_cfg);

    /* Initialize GIO module */
    GIO_Init();

    /* Configure LED A (Port B, Pin 2) as output, active-low */
    led_cfg.port = GIO_PORT_B;
    led_cfg.pin = BOARD_USER_LED_A_GIO_PIN;
    led_cfg.direction = GIO_DIRECTION_OUTPUT;
    led_cfg.pull = GIO_PULL_DISABLE;
    led_cfg.drive = GIO_DRIVE_PUSH_PULL;
    led_cfg.initial_value = (BOARD_USER_LED_A_ACTIVE_LOW == 1) ? true : false; /* Start OFF */
    GIO_ConfigurePin(&led_cfg);

    /* Configure LED B (Port B, Pin 1) as output, active-low */
    led_cfg.port = GIO_PORT_B;
    led_cfg.pin = BOARD_USER_LED_B_GIO_PIN;
    led_cfg.direction = GIO_DIRECTION_OUTPUT;
    led_cfg.pull = GIO_PULL_DISABLE;
    led_cfg.drive = GIO_DRIVE_PUSH_PULL;
    led_cfg.initial_value = (BOARD_USER_LED_B_ACTIVE_LOW == 1) ? true : false; /* Start OFF */
    GIO_ConfigurePin(&led_cfg);

    /* Print welcome screen */
    print_welcome_screen();

    /* Mark state as initialized */
    s_app_state.magic = APP_MAGIC_INITIALIZED;
    s_app_state.terminal_ready = true;
}

void APP_INTENT_Step(void)
{
    uint8_t rx_byte;
    lin_status_t status;

    /* Guard: only run if initialized */
    if (s_app_state.magic != APP_MAGIC_INITIALIZED) {
        return;
    }

    /* Non-blocking check for UART input */
    if (!LIN_IsRxReady()) {
        return;
    }

    /* Read incoming character */
    status = LIN_ReceiveByte(&rx_byte);
    if (status != LIN_STATUS_OK) {
        return;
    }

    /* Process command */
    if (rx_byte == 'A' || rx_byte == 'a') {
        toggle_led_a();
        print_string("LED A toggled.\r\n");
        print_prompt();
    } else if (rx_byte == 'B' || rx_byte == 'b') {
        toggle_led_b();
        print_string("LED B toggled.\r\n");
        print_prompt();
    } else {
        print_string("Unknown command. Press 'A' to toggle LED A, 'B' to toggle LED B.\r\n");
        print_prompt();
    }
}

/* ========================================================================== */
/*                          Static Helper Functions                           */
/* ========================================================================== */

static void print_welcome_screen(void)
{
    print_string("\r\n");
    print_string("========================================\r\n");
    print_string("  LED Control Application\r\n");
    print_string("========================================\r\n");
    print_string("Commands:\r\n");
    print_string("  A or a : Toggle LED A\r\n");
    print_string("  B or b : Toggle LED B\r\n");
    print_string("========================================\r\n");
    print_prompt();
}

static void print_prompt(void)
{
    print_string("> ");
}

static void print_string(const char* str)
{
    const uint8_t* p;
    p = (const uint8_t*)str;
    while (*p != '\0') {
        /* Wait for TX ready */
        while (!LIN_IsTxReady()) {
            /* Busy wait for single-char transmit */
        }
        LIN_TransmitByte(*p);
        p++;
    }
}

static void toggle_led_a(void)
{
    GIO_TogglePin(GIO_PORT_B, BOARD_USER_LED_A_GIO_PIN);
}

static void toggle_led_b(void)
{
    GIO_TogglePin(GIO_PORT_B, BOARD_USER_LED_B_GIO_PIN);
}
