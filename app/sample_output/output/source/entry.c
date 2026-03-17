/* BSP-GEN-META: created_at=2026-03-04T23:27:31-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/**
 * @file entry.c
 * @brief C reset handler for TI RM46 MCU - initializes .data and .bss, then calls main.
 */

#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Linker-defined symbols */
extern uint32_t start_of_data;
extern uint32_t end_of_data;
extern uint32_t start_of_data_in_flash;
extern uint32_t start_of_bss;
extern uint32_t end_of_bss;
extern uint32_t end_of_stack;

/* External functions */
extern void system_init(void);
extern int main(void);

/**
 * @brief C-level reset handler called from assembly startup code.
 *
 * This function performs the following initialization sequence:
 * 1. Copies initialized data from flash to RAM (.data section).
 * 2. Zeros the .bss section in RAM.
 * 3. Calls system_init() to configure clocks and peripherals.
 * 4. Calls main().
 * 5. Enters an infinite loop if main() returns.
 *
 * @note This function is called directly from the assembly Reset_Handler
 *       after stack pointer initialization.
 * @warning Do not call this function directly from user code.
 */
void Reset_Handler_C(void)
{
    size_t data_size;
    size_t bss_size;

    /* Initialize .data section by copying from flash to RAM */
    data_size = (size_t)(&end_of_data - &start_of_data) * sizeof(uint32_t);
    memcpy(&start_of_data, &start_of_data_in_flash, data_size);

    /* Zero-initialize .bss section */
    bss_size = (size_t)(&end_of_bss - &start_of_bss) * sizeof(uint32_t);
    memset(&start_of_bss, 0, bss_size);

    /* Initialize system (clocks, peripherals, etc.) */
    system_init();

    /* Call application entry point */
    main();

    /* If main returns, enter infinite loop to avoid undefined behavior */
    for (;;)
    {
        /* Intentionally empty */
    }
}
