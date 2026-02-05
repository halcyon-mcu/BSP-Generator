#!/usr/bin/env python3
"""
validation_prompt.py

Prompt builders for generating C unit tests that validate already-generated BSP code.

This module reads:
- Previously generated C/H files (from file_io output)
- Original YAML specifications (soc.yaml, regs.yaml, etc.)
- Project configuration

And constructs LLM prompts that ask Claude to:
1. Analyze the generated code
2. Identify test-worthy functions and behaviors
3. Generate comprehensive unit test code (using unity or cmock frameworks)
4. Verify register access, initialization sequences, and API contracts
"""

from __future__ import annotations

from typing import List, Optional


def build_validation_system_prompt() -> str:
    """
    System prompt for BSP code validation test generation.
    Instructs Claude to analyze generated code and create rigorous unit tests.
    """
    return """You are an embedded systems test engineer specializing in validating Board Support Package (BSP) code for ARM microcontrollers.

Your task is to generate unit tests for already-generated C BSP driver code targeting the TI RM46 (Cortex-R4).

VALIDATION STRATEGY
-------------------
You will be given:
1. Generated BSP source files (.c and .h) already created by a code generator
2. Original hardware specification YAML (soc.yaml, regs.yaml, memmap.yaml)
3. Specification of what was supposed to be generated (facts, initialization steps)

Your role is to:
- Analyze the generated code for correctness against the specification
- Design comprehensive unit tests that verify:
  * Register addresses and offsets match YAML specs
  * Initialization sequences are correct and complete
  * Public API functions behave as documented
  * Edge cases and error conditions are handled
  * Bitfield operations are correct
  * Memory layout matches linker script expectations
- Generate runnable C unit test code using industry-standard frameworks

TEST FRAMEWORK CONSTRAINTS
--------------------------
- Target framework: Unity (https://github.com/ThrowTheSwitch/Unity) or cmock for mocking
- Generate tests that can run on:
  * Native C compiler (gcc/clang) for unit testing
  * Target ARM compiler (arm-none-eabi-gcc) if needed
- Assume arm-none-eabi-gcc toolchain or GCC with stdint.h
- Tests MUST be:
  * Stateless and independent (run in any order)
  * Deterministic (no flaky timing assumptions)
  * Focused on logical correctness, not exhaustive coverage

CODE ANALYSIS REQUIREMENTS
--------------------------
For each generated file, you MUST:
1. Extract all register macro definitions and base addresses
   - Verify they match provided YAML facts
   - Check offset calculations
2. Analyze all public API functions:
   - Verify function signatures match header
   - Check that each register access uses correct offsets
   - Validate initialization order (dependencies)
   - Ensure no undefined behavior (NULL pointer checks, bounds)
3. Validate initialization sequences:
   - Verify all x-ext.init operations are performed
   - Check bit operations (set_bits, clear_bits, write) are correct
   - Ensure proper sequencing (e.g., disable before configure)

UNIT TEST STRUCTURE
-------------------
Generate a single test file per peripheral or module, named:
  <periph>_test.c

Each test file MUST include:
- Standard headers:
    #include <stdint.h>
    #include <stdbool.h>
    #include <unity.h>
    #include "cmock.h"    // only if mocking hardware register access
    #include "<periph>.h"  // the module under test

- Setup/teardown functions (optional):
    void setUp(void) { /* reset state before each test */ }
    void tearDown(void) { /* cleanup after each test */ }

- Test functions with descriptive names:
    void test_<module>_<function>_<scenario>() { ... }
    void test_<module>_<function>_<expected_behavior>() { ... }

- Each test MUST:
    * Have a single logical focus (one behavior to verify)
    * Use TEST_ASSERT_* macros from Unity
    * Be independent of other tests
    * Not make assumptions about timing or hardware state

MOCK REGISTER ACCESS (CRITICAL)
--------------------------------
Since tests run on a native PC (not hardware), you MUST mock hardware register access.

Recommended pattern:

  // In the test file, define mock register storage:
  #define NUM_REGISTERS 128
  static volatile uint32_t mock_registers[NUM_REGISTERS];

  // Redefine the register macro:
  #undef REG32
  #define REG32(addr) (mock_registers[((addr - BASE_ADDR) / 4)])

  // Or use cmock to intercept read/write functions

Then in tests:
  - Set mock_registers to expected initial states
  - Call the function under test
  - Assert that mock_registers changed as expected

REGISTER VERIFICATION TEST PATTERNS
------------------------------------
For each register accessed in the generated code:

1. Address/Offset Verification:
    void test_gio_base_address_is_correct(void) {
        // From YAML: GIO_BASE = 0xFFF7BC00
        TEST_ASSERT_EQUAL_HEX32(0xFFF7BC00u, GIO_BASE);
    }

    void test_gio_gcr0_offset_is_correct(void) {
        // From YAML: GIO_GCR0_OFFSET = 0x0000
        TEST_ASSERT_EQUAL_HEX32(0x0000u, GIO_GCR0_OFFSET);
    }

2. Initialization Correctness:
    void test_gio_init_sets_gcr0_correctly(void) {
        // From spec: x-ext.init says GIO.GCR0 |= 0x00000001
        memset(mock_registers, 0, sizeof(mock_registers));
        gio_init();
        uint32_t gcr0_offset = GIO_GCR0_OFFSET / 4;
        TEST_ASSERT_BIT_SET(0, mock_registers[gcr0_offset]);
    }

3. API Behavior:
    void test_gio_set_dir_configures_direction_register(void) {
        memset(mock_registers, 0, sizeof(mock_registers));
        gio_set_dir(GIO_PORT_A, 5, 1);  // Port A, pin 5, output
        // Verify DIR_A register bit 5 is set
        uint32_t dir_offset = GIO_DIR_A_OFFSET / 4;
        TEST_ASSERT_BIT_SET(5, mock_registers[dir_offset]);
    }

4. Edge Cases:
    void test_gio_set_handles_port_b(void) {
        // Test port B in addition to port A
        ...
    }

    void test_gio_set_handles_all_pins(void) {
        // Test pins 0-31 (typical GPIO width)
        ...
    }

GENERATED TEST FILE OUTPUT CONTRACT
------------------------------------
You MUST emit:

  ===== FILE: <periph>_test.c =====
  <complete unit test source code>

Do NOT emit header files (.h) for tests; they are standalone.

Each test file MUST:
- Be valid C code (C11, but C90-compatible style)
- Have all required #includes at top
- Define or mock all register addresses used
- Use only standard integer types (uint32_t, etc.) and Unity macros
- End with a single trailing newline
- Include at least 8–12 meaningful test cases per generated peripheral file

FACTS VERIFICATION (CRITICAL)
------------------------------
Before generating test code, emit a FACTS MIRROR block listing:
- All base addresses verified
- All register offsets verified
- All initialization masks/values verified
- Any discrepancies between generated code and YAML spec (if found, emit as TODO)

Example:

  ===== FACTS MIRROR =====
  GIO_BASE = 0xFFF7BC00 (from YAML)
  GIO_GCR0_OFFSET = 0x0000 (from YAML)
  GIO_DIR_A_OFFSET = 0x0034 (from YAML, verified in gio.c)
  GIO_INIT_MASK = 0x00000001 (from x-ext.init, verified in gio_init)
  ===== END FACTS MIRROR =====

If the generated code does NOT match YAML specs, emit a TODO instead of the test, e.g.:

  ===== FACTS MIRROR =====
  TODO: gio.c uses GIO_BASE = 0xFFFFFFFF but YAML specifies 0xFFF7BC00
  ===== END FACTS MIRROR =====

INPUTS TO EXPECT
----------------
You will receive:

1) Generated C source/header for a peripheral (e.g., gio.c, gio.h)
2) Corresponding YAML specification (soc.yaml slice + regs.yaml slice)
3) Expected initialization operations from soc.x-ext.init
4) Reference facts (base address, register offsets, etc.)

Process:
- Compare generated code against YAML
- Identify all testable behaviors
- Design tests to verify correctness
- Emit FACTS MIRROR
- Emit test file

NO EXTERNAL DEPENDENCIES
------------------------
Generated tests must NOT depend on:
- CCS-specific libraries
- HALCoGen runtime
- Vendor headers beyond <stdint.h>, <stdbool.h>, <string.h>

The goal is to create standalone, portable unit tests that verify logical correctness
of the generated BSP code on a desktop machine before deploying to hardware.
"""


def build_validation_user_prompt(
    generated_source: str,
    generated_header: str,
    soc_yaml_slice: str,
    regs_yaml_slice: str,
    expected_init_ops: List[dict],
    periph_name: str,
) -> str:
    """
    User prompt for validating a single generated peripheral driver.

    Args:
        generated_source: The complete generated .c file (e.g., gio.c)
        generated_header: The complete generated .h file (e.g., gio.h)
        soc_yaml_slice: Relevant slice of soc.yaml for this peripheral
        regs_yaml_slice: Relevant slice of regs.yaml for this peripheral
        expected_init_ops: List of expected init operations from x-ext.init
        periph_name: Name of peripheral (e.g., "GIO", "UART1")

    Returns:
        A detailed user prompt asking for validation tests
    """
    return f"""
    VALIDATION TEST GENERATION REQUEST
    ===================================

    Peripheral: {periph_name}
    Task: Generate comprehensive unit tests to validate the generated driver code.

    GENERATED CODE
    --------------

    File: {periph_name.lower()}.h
    ────────────────────
    {generated_header}

    File: {periph_name.lower()}.c
    ────────────────────
    {generated_source}

    SPECIFICATION SOURCES
    ---------------------

    From soc.yaml (this peripheral):
    ────────────────────────────────
    {soc_yaml_slice}

    From regs.yaml (this peripheral):
    ────────────────────────────────
    {regs_yaml_slice}

    EXPECTED INITIALIZATION OPERATIONS
    -----------------------------------

    Per soc.peripherals[*].x-ext.init for {periph_name}:
    {_format_init_ops(expected_init_ops)}

    YOUR TASK
    ---------

    1. VERIFY the generated code matches the specification:
       - Check that all #define macros for base address and register offsets
         match the values in regs.yaml.
       - Check that the init function ({periph_name.lower()}_init) implements
         all operations in x-ext.init correctly.
       - Check that all public API functions are declared in the header
         and implemented in the source.

    2. DESIGN test cases covering:
       - Macro value correctness (base address, offsets, masks)
       - Initialization sequence correctness (including bit operations)
       - All public API functions (parameters, register access, behavior)
       - Edge cases (boundary pins, invalid ports if applicable)
       - Any error-handling or state-dependent behavior

    3. GENERATE unit test file ({periph_name.lower()}_test.c) containing:
       - At least 8–12 test cases
       - Mock register storage and access patterns
       - setUp/tearDown if needed
       - Comprehensive assertions using Unity TEST_ASSERT_* macros

    4. EMIT output in the format:

       ===== FACTS MIRROR =====
       <verify all constants>
       ===== END FACTS MIRROR =====

       ===== FILE: {periph_name.lower()}_test.c =====
       <complete test code>

    VALIDATION CHECKLIST
    --------------------

    Before emitting the test file, verify:

    [ ] All register base addresses in generated code match YAML
    [ ] All register offsets in generated code match YAML
    [ ] All initialization bit operations in gio_init() match x-ext.init
    [ ] All public functions from header are tested
    [ ] Mock register storage is properly sized
    [ ] Tests are independent (no inter-test dependencies)
    [ ] Each test has a single focus
    [ ] All assertions use appropriate TEST_ASSERT_* variants
    [ ] No hardcoded timing assumptions
    [ ] No undefined behavior (pointer safety, bounds checking)
    [ ] File ends with trailing newline

    NOW GENERATE THE TEST FILE.
    """


def build_integration_test_prompt(
    system_init_source: str,
    system_init_header: str,
    linker_script: str,
    entry_c: str,
    start_asm: str,
    memmap_yaml_slice: str,
) -> str:
    """
    User prompt for generating integration tests across startup, system init, and linker script.

    Args:
        system_init_source: Generated system.c
        system_init_header: Generated system.h
        linker_script: Generated linker.cmd
        entry_c: Generated entry.c
        start_asm: Generated start.s
        memmap_yaml_slice: Memory map YAML slice

    Returns:
        Integration test generation prompt
    """
    return f"""
    INTEGRATION TEST GENERATION REQUEST
    ====================================

    Task: Generate tests to validate startup sequence, system initialization,
    memory layout, and integration between start.s → entry.c → system.c → main().

    GENERATED STARTUP INFRASTRUCTURE
    ---------------------------------

    File: start.s (ARM assembly startup)
    ────────────────────────────────────
    {start_asm}

    File: entry.c (C reset handler)
    ───────────────────────────────
    {entry_c}

    File: system.h (system init header)
    ───────────────────────────────────
    {system_init_header}

    File: system.c (system init implementation)
    ────────────────────────────────────────────
    {system_init_source}

    File: linker.cmd (TI linker script)
    ────────────────────────────────────
    {linker_script}

    MEMORY MAP SPECIFICATION
    ------------------------
    {memmap_yaml_slice}

    YOUR TASK
    ---------

    Generate a comprehensive integration test file: startup_integration_test.c

    This test should verify:

    1. STARTUP SEQUENCE:
       - Reset_Handler entry point is correct
       - Stack pointer (SP) is loaded from end_of_stack symbol
       - Reset_Handler_C() is called
       - No jumping to invalid addresses

    2. ENTRY.C BEHAVIOR:
       - .data section copy from flash to RAM is correct
       - .bss section zeroing is complete
       - Linker symbols (start_of_data, end_of_data, etc.) are properly declared
       - main() is called

    3. SYSTEM INITIALIZATION:
       - system_init() is called before main()
       - Clock control (CLKCNTL) operations are performed
       - Power domain operations (PCR) are performed
       - All register writes in system_init match expectations

    4. LINKER SCRIPT LAYOUT:
       - MEMORY block defines FLASH and RAM with correct origin/length
       - SECTIONS places .intvecs at start of FLASH
       - .text, .const, .cinit, .pinit are in FLASH
       - .data is in RAM with correct load address in FLASH
       - .bss is in RAM, zero-initialized
       - Stack size is reasonable
       - Linker symbols (end_of_stack, etc.) are defined

    5. MEMORY LAYOUT CORRECTNESS:
       - Flash origin/length match MEMMAP.yaml
       - RAM origin/length match MEMMAP.yaml
       - end_of_stack = RAM.origin + RAM.length
       - No overlap between sections

    GENERATED TEST FILE: startup_integration_test.c
    ================================================

    Include:
    - Mocked linker symbols (as extern const variables)
    - Mocked memory regions (simulated FLASH and RAM arrays)
    - Test cases for each behavioral requirement above
    - Verification of symbol values against memmap.yaml
    - Simulation of data copy and bss zero-fill
    - Call sequence verification

    Example test structure:

      #include <unity.h>
      #include <stdint.h>
      #include <string.h>

      // Mock linker symbols
      extern uint32_t start_of_data;
      extern uint32_t end_of_data;
      extern uint32_t start_of_data_in_flash;
      ...

      // Mock memory regions
      static uint8_t mock_flash[FLASH_SIZE];
      static uint8_t mock_ram[RAM_SIZE];

      void setUp(void) { ... }
      void tearDown(void) { ... }

      void test_startup_end_of_stack_is_at_ram_end(void) { ... }
      void test_entry_copies_initialized_data_correctly(void) { ... }
      void test_system_init_sets_clkcntl(void) { ... }
      ...

    EMIT OUTPUT:

      ===== FACTS MIRROR =====
      <verify memory regions, symbol values>
      ===== END FACTS MIRROR =====

      ===== FILE: startup_integration_test.c =====
      <complete integration test code>
    """


def _format_init_ops(ops: List[dict]) -> str:
    """Format initialization operations list for readability in prompts."""
    if not ops:
        return "(none)"
    lines = []
    for i, op in enumerate(ops, 1):
        reg = op.get("reg", "?")
        operation = op.get("op", "?")
        value = op.get("value", "?")
        lines.append(f"  {i}. {reg} {operation} {value}")
    return "\n".join(lines)


def build_cross_file_validation_prompt(
    all_generated_files: List[tuple[str, str]],
    all_yaml_specs: List[tuple[str, str]],
    facts_canon: str,
) -> str:
    """
    Generate a meta-validation prompt that checks consistency across all generated files.

    Args:
        all_generated_files: List of (filename, content) tuples for all generated code
        all_yaml_specs: List of (spec_name, content) tuples for all YAML inputs
        facts_canon: The canonical facts/constants from project config

    Returns:
        Cross-file validation prompt
    """
    files_str = "\n".join(
        [f"### {name}\n{content[:500]}..." for name, content in all_generated_files]
    )
    yaml_str = "\n".join(
        [f"### {name}\n{content[:300]}..." for name, content in all_yaml_specs]
    )

    return f"""
    CROSS-FILE VALIDATION TEST GENERATION
    ======================================

    Task: Generate tests to verify consistency and correctness across ALL generated files.

    GENERATED FILES (summary)
    -------------------------
    {files_str}

    YAML SPECIFICATIONS (summary)
    -----------------------------
    {yaml_str}

    FACTS CANON (reference constants)
    ----------------------------------
    {facts_canon}

    VALIDATION REQUIREMENTS
    -----------------------

    1. CONSISTENCY CHECKS:
       - All peripheral headers include <stdint.h>
       - All register macros in all .c files have identical naming conventions
       - All base addresses are used consistently (no conflicting definitions)
       - All x-ext.init operations are performed (no missing registers)
       - Linker symbols match between linker.cmd and entry.c

    2. COMPLETENESS CHECKS:
       - All peripherals declared in soc.yaml have corresponding .c and .h files
       - All registers in x-ext.init are accessed in respective init functions
       - All public API functions are documented with Doxygen
       - All macros used are defined before use

    3. SPECIFICATION ADHERENCE:
       - Every numeric constant matches YAML or facts_canon
       - No invented addresses or offsets
       - Initialization order respects dependencies
       - Memory layout respects MEMMAP.yaml

    Generate a comprehensive test file: cross_validation_test.c

    This file should:
    - Load all generated artifacts (simulated)
    - Verify macro consistency across files
    - Check that all base addresses are correct
    - Validate that all peripherals are fully initialized
    - Ensure linker script matches entry.c expectations
    - Report any violations as test failures

    Emit:

      ===== FILE: cross_validation_test.c =====
      <complete cross-file validation test code>
    """
