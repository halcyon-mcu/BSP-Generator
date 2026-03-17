/* BSP-GEN-META: created_at=2026-03-04T23:27:31-08:00; output_folder=output_20260304_232329; output_tag=20260304_232329 */
/*******************************************************************************
 * TI ARM CGT Linker Command File for TI Hercules RM46
 * Generated for Code Composer Studio (CCS) / TI ARM CGT toolchain
 ******************************************************************************/

/* Entry point */
--entry_point=Reset_Handler

/* Memory regions from MEMMAP.yaml */
MEMORY
{
    FLASH (RX)  : origin = 0x00000000, length = 0x00140000
    RAM   (RWX) : origin = 0x08000000, length = 0x00030000
}

/* Absolute symbol for top of stack */
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

    /* C initialization tables in FLASH */
    .cinit :
    {
        . = ALIGN(4);
    } > FLASH

    /* C++ initialization in FLASH */
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
