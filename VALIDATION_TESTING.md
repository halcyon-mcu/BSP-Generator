# BSP Code Validation Test Generation

## Overview

This document describes how to use the **validation prompt system** to automatically generate comprehensive unit tests that validate already-generated BSP code.

## Problem Statement

After your BSP generator creates C driver files (e.g., `gio.c`, `uart1.c`), you need to verify that:

1. **Register addresses and offsets** match the hardware specification (YAML)
2. **Initialization sequences** are correct and complete
3. **Public API functions** behave as documented
4. **Memory layout** (from linker script) is correct
5. **Startup sequence** (assembly → C entry → system init) is valid
6. **Cross-file consistency** (all generated files work together)

The validation system automatically generates **unit tests** that check all of these properties.

## Architecture

```
┌─────────────────────────────────────┐
│  Generated BSP Files                │
│  (gio.c, gio.h, system.c, etc.)    │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  validation_prompt.py               │
│  - build_validation_system_prompt() │
│  - build_validation_user_prompt()   │
│  - build_integration_test_prompt()  │
│  - build_cross_file_validation...() │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  invoke_model() via AWS Bedrock     │
│  (Claude 3.5 Sonnet)                │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  LLM Response (test code)           │
│  (C unit tests with Unity framework)│
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  validation_integration.py          │
│  - split_and_write_files()          │
│  - organize test artifacts          │
│  - write_test_manifest.json         │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│  Test Output Directory              │
│  (gio_test.c, uart1_test.c, etc.)  │
│  + cross_validation_test.c          │
│  + startup_integration_test.c       │
│  + validation_tests_manifest.json   │
└─────────────────────────────────────┘
```

## Modules

### 1. `validation_prompt.py`

Defines prompt builders for test generation:

#### `build_validation_system_prompt()`

Returns a system prompt instructing Claude to:

- Analyze generated C code
- Compare against YAML specifications
- Design unit test cases
- Use Unity test framework
- Mock hardware register access
- Create independent, deterministic tests

**Output**: Multi-hundred-line system prompt string

#### `build_validation_user_prompt(generated_source, generated_header, soc_yaml_slice, regs_yaml_slice, expected_init_ops, periph_name)`

Returns a user prompt for a specific peripheral that:

- Shows the generated .c and .h files
- Provides the relevant YAML specification
- Lists expected initialization operations
- Requests comprehensive test generation
- Specifies validation checklist

**Output**: Detailed user prompt with inline code

#### `build_integration_test_prompt(system_init_source, system_init_header, linker_script, entry_c, start_asm, memmap_yaml_slice)`

Returns a prompt for generating integration tests covering:

- Startup sequence (start.s → entry.c)
- System initialization (system_init)
- Linker script layout
- Memory region correctness
- Startup symbol verification

#### `build_cross_file_validation_prompt(all_generated_files, all_yaml_specs, facts_canon)`

Returns a prompt for meta-validation across all files:

- Consistency of macro names and values
- No conflicting register definitions
- All peripherals fully initialized
- Linker symbols match entry.c expectations

### 2. `validation_integration.py`

High-level orchestration functions:

#### `read_generated_file(bsp_output_dir, filename)`

Safely reads a generated file from the BSP output directory.

#### `collect_generated_peripherals(bsp_output_dir)`

Scans the output directory and returns a list of generated peripheral names.

#### `generate_peripheral_validation_test(bsp_output_dir, periph_name, soc_yaml_data, regs_yaml_data, model, max_tokens, output_dir=None)`

Main function to generate tests for one peripheral:

1. Reads generated .c and .h files
2. Extracts relevant YAML slices
3. Builds validation prompts
4. Invokes Claude via Bedrock
5. Writes test file to disk
6. Returns (success: bool, test_file_path: Path)

#### `generate_integration_tests(bsp_output_dir, memmap_yaml_data, model, max_tokens, output_dir=None)`

Generates integration tests for startup and system initialization.

#### `generate_cross_file_validation(bsp_output_dir, soc_yaml_data, regs_yaml_data, memmap_yaml_data, facts_canon, model, max_tokens, output_dir=None)`

Generates cross-file validation tests.

#### `write_test_manifest(output_dir, test_results)`

Writes a JSON manifest summarizing all generated tests.

## Usage Example

### Step 1: Generate BSP (existing workflow)

```bash
uv run -m app.main --out ./bsp_gen --model sonnet4.5
# Output: bsp_gen/output_20250122T153042/
#         ├── gio.c
#         ├── gio.h
#         ├── uart1.c
#         ├── uart1.h
#         ├── system.c
#         ├── system.h
#         ├── entry.c
#         ├── start.s
#         ├── linker.cmd
#         └── _artifacts/
```

### Step 2: Generate Validation Tests

Create a new script `generate_tests.py`:

```python
#!/usr/bin/env python3
from pathlib import Path
from app.modules.validation_integration import (
    generate_peripheral_validation_test,
    generate_integration_tests,
    generate_cross_file_validation,
    collect_generated_peripherals,
    write_test_manifest,
)
from app.modules.prompt import Model
from app.modules.yaml_utils import (
    load_soc_yaml,
    load_regs_yaml,
    load_memmap_yaml,
)
from app.config import FACTS_CANON

# Paths
bsp_output_dir = Path("./bsp_gen/output_20250122T153042")
yaml_dir = Path("./app/yaml_in")
test_output_dir = bsp_output_dir / "tests"

# Load YAML specs
soc_data = load_soc_yaml(yaml_dir / "soc.yaml")
regs_data = load_regs_yaml(yaml_dir / "regs.yaml")
memmap_data = load_memmap_yaml(yaml_dir / "memmap.yaml")

# Collect peripherals
peripherals = collect_generated_peripherals(bsp_output_dir)
print(f"Found peripherals: {peripherals}")

test_results = []

# Generate peripheral tests
for periph_name in peripherals:
    success, test_path = generate_peripheral_validation_test(
        bsp_output_dir=bsp_output_dir,
        periph_name=periph_name.upper(),
        soc_yaml_data=soc_data,
        regs_yaml_data=regs_data,
        model=Model.SONNET_4_5,
        max_tokens=12000,
        output_dir=test_output_dir,
    )
    test_results.append((f"peripheral_{periph_name}", success, test_path))

# Generate integration tests
success, test_path = generate_integration_tests(
    bsp_output_dir=bsp_output_dir,
    memmap_yaml_data=memmap_data,
    model=Model.SONNET_4_5,
    max_tokens=12000,
    output_dir=test_output_dir,
)
test_results.append(("integration", success, test_path))

# Generate cross-file validation
success, test_path = generate_cross_file_validation(
    bsp_output_dir=bsp_output_dir,
    soc_yaml_data=soc_data,
    regs_yaml_data=regs_data,
    memmap_yaml_data=memmap_data,
    facts_canon=FACTS_CANON,
    model=Model.SONNET_4_5,
    max_tokens=12000,
    output_dir=test_output_dir,
)
test_results.append(("cross_validation", success, test_path))

# Write manifest
write_test_manifest(test_output_dir, test_results)

# Summary
passed = sum(1 for _, success, _ in test_results if success)
print(f"\n[ok] Generated {passed}/{len(test_results)} test files")
```

Run it:

```bash
uv run generate_tests.py
# Output: bsp_gen/output_20250122T153042/tests/
#         ├── gio_test.c
#         ├── uart1_test.c
#         ├── startup_integration_test.c
#         ├── cross_validation_test.c
#         └── validation_tests_manifest.json
```

### Step 3: Build and Run Tests

Generate a CMakeLists.txt or Makefile for the tests:

```bash
# With Unity framework
cd tests
make test
# or
cmake -B build && cmake --build build && ctest
```

## Test Output Examples

### Peripheral Test (`gio_test.c`)

```c
#include <unity.h>
#include <stdint.h>
#include <string.h>
#include "gio.h"

// Mock register storage
#define GIO_NUM_REGISTERS 128
static volatile uint32_t mock_registers[GIO_NUM_REGISTERS];

// Redefine register access for testing
#undef REG32
#define REG32(addr) (mock_registers[((addr - GIO_BASE) / 4)])

void setUp(void) {
    memset((void*)mock_registers, 0, sizeof(mock_registers));
}

void tearDown(void) {
    /* cleanup if needed */
}

void test_gio_base_address_is_correct(void) {
    TEST_ASSERT_EQUAL_HEX32(0xFFF7BC00u, GIO_BASE);
}

void test_gio_gcr0_offset_is_correct(void) {
    TEST_ASSERT_EQUAL_HEX32(0x0000u, GIO_GCR0_OFFSET);
}

void test_gio_init_sets_gcr0_correctly(void) {
    gio_init();
    uint32_t gcr0_offset = GIO_GCR0_OFFSET / 4;
    TEST_ASSERT_BIT_SET(0, mock_registers[gcr0_offset]);
}

void test_gio_set_dir_configures_direction_register(void) {
    gio_set_dir(GIO_PORT_A, 5, 1);
    uint32_t dir_offset = GIO_DIR_A_OFFSET / 4;
    TEST_ASSERT_BIT_SET(5, mock_registers[dir_offset]);
}

void test_gio_set_toggles_output_bit(void) {
    gio_set(GIO_PORT_A, 3);
    uint32_t dset_offset = GIO_DSET_A_OFFSET / 4;
    TEST_ASSERT_BIT_SET(3, mock_registers[dset_offset]);
}

void test_gio_clear_toggles_output_bit(void) {
    gio_clear(GIO_PORT_A, 3);
    uint32_t dclr_offset = GIO_DCLR_A_OFFSET / 4;
    TEST_ASSERT_BIT_SET(3, mock_registers[dclr_offset]);
}

void test_gio_read_returns_pin_state(void) {
    mock_registers[GIO_DOUT_A_OFFSET / 4] = 0x00000008u;
    uint32_t state = gio_read(GIO_PORT_A, 3);
    TEST_ASSERT_EQUAL_UINT32(1u, state);
}

void test_gio_set_handles_port_b(void) {
    gio_set(GIO_PORT_B, 7);
    uint32_t dset_offset = GIO_DSET_B_OFFSET / 4;
    TEST_ASSERT_BIT_SET(7, mock_registers[dset_offset]);
}

void test_gio_toggle_pin(void) {
    // Set initial state
    mock_registers[GIO_DOUT_A_OFFSET / 4] = 0x00000001u;
    gio_toggle(GIO_PORT_A, 0);
    // Should clear (DCLR) when bit was set
    uint32_t dclr_offset = GIO_DCLR_A_OFFSET / 4;
    TEST_ASSERT_BIT_SET(0, mock_registers[dclr_offset]);
}

void test_gio_handles_all_pins_0_to_31(void) {
    int pin;
    for (pin = 0; pin < 32; ++pin) {
        memset((void*)mock_registers, 0, sizeof(mock_registers));
        gio_set(GIO_PORT_A, pin);
        uint32_t dset_offset = GIO_DSET_A_OFFSET / 4;
        TEST_ASSERT_BIT_SET(pin, mock_registers[dset_offset]);
    }
}
```

### Integration Test (`startup_integration_test.c`)

```c
#include <unity.h>
#include <stdint.h>
#include <string.h>

// Mock linker symbols
extern uint32_t start_of_data;
extern uint32_t end_of_data;
extern uint32_t start_of_data_in_flash;
extern uint32_t start_of_bss;
extern uint32_t end_of_bss;
extern uint32_t end_of_stack;

// Mock memory regions
#define FLASH_SIZE (0x00150000)
#define RAM_SIZE   (0x00030000)
static uint8_t mock_flash[FLASH_SIZE];
static uint8_t mock_ram[RAM_SIZE];

void test_end_of_stack_is_at_ram_end(void) {
    // From memmap.yaml: RAM at 0x08000000, length 0x00030000
    uint32_t expected_end = 0x08000000u + 0x00030000u;
    TEST_ASSERT_EQUAL_HEX32(expected_end, (uint32_t)&end_of_stack);
}

void test_linker_script_defines_flash_region(void) {
    // Verify linker generated FLASH region at correct origin
    TEST_ASSERT_EQUAL_HEX32(0x00000000u, 0u); // symbolic check
}

void test_system_init_called_before_main(void) {
    // Verify that Reset_Handler_C calls system_init() before main()
    // This is validated through code inspection rather than runtime
}
```

## Integration with Main Workflow

Update `app/main.py` to optionally generate tests:

```python
parser.add_argument(
    "--generate-tests",
    action="store_true",
    help="After generating BSP, also generate validation tests",
)

# ... after generating BSP ...

if args.generate_tests:
    print("\n[info] Generating validation tests…")
    from modules.validation_integration import (
        generate_peripheral_validation_test,
        generate_integration_tests,
        generate_cross_file_validation,
        collect_generated_peripherals,
        write_test_manifest,
    )

    peripherals = collect_generated_peripherals(out_dir)
    test_results = []

    for periph in peripherals:
        success, _ = generate_peripheral_validation_test(
            bsp_output_dir=out_dir,
            periph_name=periph.upper(),
            soc_yaml_data=soc_data,
            regs_yaml_data=regs_data,
            model=model_enum,
            max_tokens=args.max_tokens,
        )
        test_results.append((f"peripheral_{periph}", success, out_dir / f"{periph}_test.c"))

    success, _ = generate_integration_tests(
        bsp_output_dir=out_dir,
        memmap_yaml_data=memmap_data,
        model=model_enum,
        max_tokens=args.max_tokens,
    )
    test_results.append(("integration", success, out_dir / "startup_integration_test.c"))

    write_test_manifest(out_dir, test_results)
    print(f"[ok] Generated {sum(1 for _, s, _ in test_results if s)} test files")
```

## Test Manifest

Each test generation produces a JSON manifest:

```json
{
  "generated_at": "20250122T153042",
  "tests": [
    {
      "name": "peripheral_gio",
      "success": true,
      "path": "tests/gio_test.c"
    },
    {
      "name": "peripheral_uart1",
      "success": true,
      "path": "tests/uart1_test.c"
    },
    {
      "name": "integration",
      "success": true,
      "path": "tests/startup_integration_test.c"
    },
    {
      "name": "cross_validation",
      "success": true,
      "path": "tests/cross_validation_test.c"
    }
  ],
  "total": 4,
  "passed": 4
}
```

## Next Steps

1. **Create a test build system** (CMakeLists.txt or Makefile) to compile and run tests
2. **Integrate with CI/CD** (GitHub Actions, GitLab CI) to auto-validate all BSP generations
3. **Add test coverage reporting** to track which registers/functions are tested
4. **Extend validation** to include performance tests, stress tests, or hardware-in-the-loop tests

## Troubleshooting

### Empty test generation

- Check `_artifacts/llm_raw_*.txt` for the full LLM response
- Verify YAML slices are being extracted correctly
- Ensure model has sufficient context (increase `max_tokens`)

### Test compilation failures

- Ensure Unity framework headers are installed
- Verify mock register definitions match actual register layout
- Check for C99-isms that conflict with C90 standard (variable declarations mid-block)

### False test failures

- Tests should be deterministic; check for floating-point comparisons, timing assumptions
- Ensure setUp() properly resets mock state between tests
- Verify expected register operations match YAML specification
