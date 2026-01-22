# Validation Test Generation - Quick Reference

## What Was Created

Three new modules for validating generated BSP code:

### 1. `app/modules/validation_prompt.py` (580 lines)

**Purpose**: Builds LLM prompts that ask Claude to generate unit tests

**Key Functions**:

- `build_validation_system_prompt()` - System instructions for test generation
- `build_validation_user_prompt()` - Prompt for single peripheral test
- `build_integration_test_prompt()` - Prompt for startup/system init tests
- `build_cross_file_validation_prompt()` - Prompt for cross-file consistency

**What it does**:

- Takes generated C code and YAML specs
- Creates detailed instructions for Claude to analyze code
- Specifies test framework (Unity), mocking strategy, and expected outputs
- Generates prompts that ask for 8-12+ test cases per module

### 2. `app/modules/validation_integration.py` (320 lines)

**Purpose**: Orchestrates test generation workflow

**Key Functions**:

- `generate_peripheral_validation_test()` - Generate tests for one driver
- `generate_integration_tests()` - Generate startup sequence tests
- `generate_cross_file_validation()` - Generate cross-file consistency tests
- `collect_generated_peripherals()` - Find all generated drivers
- `write_test_manifest()` - Create JSON summary of tests

**What it does**:

- Reads generated BSP files from disk
- Extracts relevant YAML specifications
- Calls Claude via Bedrock to generate tests
- Writes test files to output directory
- Creates manifest JSON

### 3. `VALIDATION_TESTING.md` (400+ lines)

**Purpose**: Complete documentation and usage guide

**Includes**:

- Architecture overview with diagrams
- Detailed API documentation
- Step-by-step usage examples
- Sample test output
- Integration with main workflow
- Troubleshooting guide

## Quick Start

### 1. Generate BSP (as before)

```bash
uv run -m app.main --out ./bsp_gen --model sonnet4.5
```

### 2. Generate Validation Tests

Create `generate_tests.py`:

```python
from pathlib import Path
from app.modules.validation_integration import *
from app.modules.prompt import Model
from app.modules.yaml_utils import *

bsp_out = Path("./bsp_gen/output_20250122T153042")
yaml_in = Path("./app/yaml_in")

# Load YAML
soc = load_soc_yaml(yaml_in / "soc.yaml")
regs = load_regs_yaml(yaml_in / "regs.yaml")
memmap = load_memmap_yaml(yaml_in / "memmap.yaml")

# Generate tests
peripherals = collect_generated_peripherals(bsp_out)
for periph in peripherals:
    generate_peripheral_validation_test(
        bsp_out, periph.upper(), soc, regs, Model.SONNET_4_5, 12000
    )

# Generate integration tests
generate_integration_tests(bsp_out, memmap, Model.SONNET_4_5, 12000)
```

### 3. Run Tests

```bash
cd bsp_gen/output_20250122T153042/tests
make test  # or cmake + ctest
```

## How It Works

### Per-Peripheral Tests

For each generated driver (e.g., `gio.c`/`gio.h`):

1. **Read** the generated source and header
2. **Extract** YAML specification for that peripheral
3. **Build prompt** showing code + expected behavior
4. **Call Claude** to generate tests
5. **Write** `gio_test.c` with 10+ test cases

**Tests verify**:

- ✅ Register base addresses match YAML
- ✅ Register offsets match YAML
- ✅ Initialization sequence is correct
- ✅ Public API functions work as expected
- ✅ All pins/ports are handled
- ✅ Edge cases work

### Integration Tests

For startup sequence (start.s → entry.c → system.c → main):

1. **Read** assembly startup, C entry, system init, linker script
2. **Extract** memory map specification
3. **Build prompt** with all startup code
4. **Call Claude** to generate tests
5. **Write** `startup_integration_test.c`

**Tests verify**:

- ✅ Stack pointer initialization
- ✅ Data section copy (flash → RAM)
- ✅ BSS section zeroing
- ✅ System initialization before main
- ✅ Memory layout from linker script

### Cross-File Validation

For all generated files together:

1. **Collect** all .c, .h, .cmd, .s files
2. **Extract** all YAML specs
3. **Build prompt** with complete BSP
4. **Call Claude** to generate tests
5. **Write** `cross_validation_test.c`

**Tests verify**:

- ✅ No conflicting register definitions
- ✅ All macros use consistent naming
- ✅ Base addresses don't collide
- ✅ All peripherals are initialized
- ✅ Linker symbols match code expectations

## Test Output Structure

```
bsp_gen/output_20250122T153042/
├── gio.c                          (generated driver)
├── gio.h
├── uart1.c
├── uart1.h
├── system.c
├── system.h
├── entry.c
├── start.s
├── linker.cmd
├── _artifacts/                    (LLM artifacts)
│   ├── llm_raw_*.txt
│   └── llm_preamble_*.txt
└── tests/                         (generated tests)
    ├── gio_test.c                 (10+ tests)
    ├── uart1_test.c               (10+ tests)
    ├── startup_integration_test.c (8+ tests)
    ├── cross_validation_test.c    (8+ tests)
    └── validation_tests_manifest.json
```

## Integration with Main Workflow

### Option 1: Standalone Script

```bash
# After BSP generation:
python generate_tests.py
```

### Option 2: CLI Flag

```bash
# Add --generate-tests flag to main.py:
uv run -m app.main --out ./bsp_gen --generate-tests
```

### Option 3: Automated CI/CD

```bash
# GitHub Actions / GitLab CI:
- Generate BSP
- Generate tests
- Build tests with gcc/cmake
- Run tests with ctest
- Report results
```

## Sample Test Cases

### Register Address Verification

```c
void test_gio_base_address_matches_yaml(void) {
    // YAML: GIO_BASE = 0xFFF7BC00
    TEST_ASSERT_EQUAL_HEX32(0xFFF7BC00u, GIO_BASE);
}
```

### Initialization Correctness

```c
void test_gio_init_sets_gcr0_bit0(void) {
    // YAML: GIO.GCR0 |= 0x00000001
    gio_init();
    TEST_ASSERT_BIT_SET(0, REG32(GIO_BASE + GIO_GCR0_OFFSET));
}
```

### API Behavior

```c
void test_gio_set_pin_writes_to_dset(void) {
    gio_set(GIO_PORT_A, 5);
    TEST_ASSERT_BIT_SET(5, REG32(GIO_BASE + GIO_DSET_A_OFFSET));
}
```

### Edge Cases

```c
void test_gio_handles_all_32_pins(void) {
    int i;
    for (i = 0; i < 32; ++i) {
        gio_set(GIO_PORT_A, i);
        TEST_ASSERT_BIT_SET(i, REG32(GIO_BASE + GIO_DSET_A_OFFSET));
    }
}
```

## Key Design Features

✅ **Automated**: No manual test writing needed
✅ **Comprehensive**: 8-12+ tests per peripheral
✅ **Rigorous**: Checks register access, initialization, and API behavior
✅ **Standalone**: Tests run on desktop (with mocked registers)
✅ **Deterministic**: No timing assumptions or flakiness
✅ **Traceable**: Each test tied to specific YAML requirement
✅ **Portable**: Generated with standard C and Unity framework

## Next Steps

1. **Implement test build system** (CMakeLists.txt / Makefile)
2. **Add Unity framework** to project dependencies
3. **Integrate into main.py** with `--generate-tests` flag
4. **Run tests in CI/CD** pipeline
5. **Extend to firmware-level tests** (with actual hardware)

## Files Modified/Created

| File                        | Status | Lines | Purpose         |
| --------------------------- | ------ | ----- | --------------- |
| `validation_prompt.py`      | ✨ NEW | 580   | Prompt builders |
| `validation_integration.py` | ✨ NEW | 320   | Orchestration   |
| `VALIDATION_TESTING.md`     | ✨ NEW | 400+  | Documentation   |
| `QUICKSTART_VALIDATION.md`  | ✨ NEW | 200+  | Quick reference |

## Questions?

See `VALIDATION_TESTING.md` for:

- Detailed API documentation
- Complete usage examples
- Sample test output
- Integration patterns
- Troubleshooting guide
