/**
 * @file entry.c
 * @brief C-level reset handler for TI RM46 BSP.
 *
 * This module implements the C portion of the reset handler, which is invoked
 * by the assembly startup code. It initializes the .data and .bss sections,
 * calls the system initialization routine, and then transfers control to main().
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
 * This function is called from the assembly reset vector. It performs the
 * following initialization steps:
 * 1. Copies the .data section from flash to RAM.
 * 2. Zeroes the .bss section in RAM.
 * 3. Calls system_init() to initialize clocks and peripherals.
 * 4. Calls main() to enter the application.
 * 5. If main() returns, enters an infinite loop to avoid undefined behavior.
 *
 * @note This function must be called before any access to initialized or
 *       uninitialized global variables.
 */
void Reset_Handler_C(void) {
    size_t data_size;
    size_t bss_size;

    /* Initialize .data section by copying from flash to RAM */
    data_size = (size_t)(&end_of_data - &start_of_data) * sizeof(uint32_t);
    memcpy(&start_of_data, &start_of_data_in_flash, data_size);

    /* Zero-initialize .bss section */
    bss_size = (size_t)(&end_of_bss - &start_of_bss) * sizeof(uint32_t);
    memset(&start_of_bss, 0, bss_size);

    /* Initialize system clocks and peripherals */
    system_init();

    /* Enter application */
    main();

    /* If main() returns, loop forever */
    for (;;) {
        /* Prevent undefined behavior */
    }
}