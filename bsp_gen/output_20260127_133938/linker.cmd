/**
 * @file linker.cmd
 * @brief TI ARM CGT linker command file for TI Hercules RM46 MCU
 */

/* Entry point */
--entry_point=Reset_Handler

/* Memory regions from MEMMAP.yaml */
MEMORY
{
    FLASH (RX)  : origin = 0x00000000, length = 0x00150000
    RAM   (RWX) : origin = 0x08000000, length = 0x00030000
}

/* Top-of-stack symbol (end of RAM) */
end_of_stack = 0x08000000 + 0x00030000;

/* Section placement */
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

    /* Constructor initialization tables in FLASH */
    .cinit :
    {
        . = ALIGN(4);
    } > FLASH

    /* Pointer initialization tables in FLASH */
    .pinit :
    {
        . = ALIGN(4);
    } > FLASH

    /* Initialized data: load from FLASH, run in RAM */
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

    /* Stack section in RAM */
    .stack :
    {
        __stack_start = .;
    } > RAM

    /* Heap section in RAM */
    .sysmem :
    {
        __sysmem_start = .;
    } > RAM
}