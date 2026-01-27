/**
 * @file entry.c
 * @brief C-level reset handler for TI RM46 MCU.
 *
 * This file implements the high-level reset sequence called from assembly startup code.
 * It initializes the .data and .bss sections, calls system initialization, and then
 * transfers control to the user's main() function.
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Linker-defined symbols marking section boundaries */
extern uint32_t start_of_data;
extern uint32_t end_of_data;
extern uint32_t start_of_data_in_flash;
extern uint32_t start_of_bss;
extern uint32_t end_of_bss;

/* External functions */
extern void system_init(void);
extern int main(void);

/**
 * @brief C-level reset handler.
 * @ingroup BSP_SYSTEM
 *
 * This function is called by the assembly-level Reset_Handler after initial stack setup.
 * It performs the following steps in order:
 * 1. Copies initialized data from flash to RAM (.data section).
 * 2. Zeros the uninitialized data region in RAM (.bss section).
 * 3. Calls system_init() to configure clocks and peripherals.
 * 4. Calls the user's main() function.
 * 5. Enters an infinite loop if main() returns (to prevent undefined behavior).
 *
 * @note This function does not return under normal operation.
 * @warning All code executed before system_init() runs with default/reset clock settings.
 */
void Reset_Handler_C(void) {
    size_t data_size;
    size_t bss_size;

    /* Step 1: Copy initialized data from flash to RAM */
    data_size = (size_t)(&end_of_data - &start_of_data) * sizeof(uint32_t);
    memcpy(&start_of_data, &start_of_data_in_flash, data_size);

    /* Step 2: Zero the .bss section */
    bss_size = (size_t)(&end_of_bss - &start_of_bss) * sizeof(uint32_t);
    memset(&start_of_bss, 0, bss_size);

    /* Step 3: Initialize system clocks and peripherals */
    system_init();

    /* Step 4: Call user application entry point */
    main();

    /* Step 5: Infinite loop to prevent undefined behavior if main() returns */
    for (;;) {
        /* Intentionally empty */
    }
}