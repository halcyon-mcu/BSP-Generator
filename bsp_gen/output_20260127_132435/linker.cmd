/**
 * @file linker.cmd
 * @brief TI ARM CGT linker command file for RM46 (Cortex-R4)
 *
 * Defines memory regions (FLASH, RAM) and section placement for
 * interrupt vectors, code, data, BSS, stack, and heap.
 *
 * Provides linker symbols:
 *   - start_of_data_in_flash, start_of_data, end_of_data
 *   - start_of_bss, end_of_bss
 *   - end_of_stack
 */

/* Entry point */
--entry_point=Reset_Handler

/* Memory regions from MEMMAP.yaml */
MEMORY
{
    FLASH (RX)  : origin = 0x00000000, length = 0x00150000
    RAM   (RWX) : origin = 0x08000000, length = 0x00030000
}

/* Top-of-stack symbol (RAM origin + length) */
end_of_stack = 0x08000000 + 0x00030000;

SECTIONS
{
    /* Interrupt vector table at start of FLASH */
    .intvecs :
    {
        . = ALIGN(4);
    } > FLASH

    /* Code in FLASH */
    .text :
    {
        . = ALIGN(4);
    } > FLASH

    /* Read-only data in FLASH */
    .const :
    {
        . = ALIGN(4);
    } > FLASH

    /* C initialization tables in FLASH */
    .cinit :
    {
        . = ALIGN(4);
    } > FLASH

    /* C++ static constructor tables in FLASH */
    .pinit :
    {
        . = ALIGN(4);
    } > FLASH

    /* Initialized data: load in FLASH, run in RAM */
    .data :
    {
        . = ALIGN(4);
    } load = FLASH, run = RAM,
      LOAD_START(start_of_data_in_flash),
      RUN_START(start_of_data),
      RUN_END(end_of_data)

    /* Zero-initialized data in RAM */
    .bss :
    {
        . = ALIGN(4);
    } > RAM,
      RUN_START(start_of_bss),
      RUN_END(end_of_bss)

    /* Stack section in RAM (size controlled by --stack_size) */
    .stack :
    {
        __stack_start = .;
    } > RAM

    /* Heap section in RAM (size controlled by --heap_size) */
    .sysmem :
    {
        __sysmem_start = .;
    } > RAM
}