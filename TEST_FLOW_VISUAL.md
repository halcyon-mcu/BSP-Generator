# Test Architecture - One Page Visual Summary

## The Simple Answer

```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  YAML (What hardware should do)                             │
│         ↓                                                     │
│  BSP Generator → C Code (Implementation)                    │
│         ↓                                                     │
│  Validation Test Generator → Unit Tests                     │
│         ↓                                                     │
│  Test Execution with Mocks                                  │
│         ↓                                                     │
│  ✅ Result: "C Code matches YAML spec"                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Where Tests Run

```
TESTS RUN ON:     Generated C code (gio.c, sci.c, system.c, etc.)
TESTS VALIDATE:   Against YAML specifications (soc.yaml, regs.yaml, etc.)
TEST METHOD:      Mock register access, verify correct behavior
```

---

## Example: GPIO Driver

### YAML Says (Input)

```yaml
GIO:
  base_address: "0xFFF7BC00"
  registers:
    DOUT_A: offset "0x3C"
    DIR_A: offset "0x34"
```

### C Code Does (Generated)

```c
void gio_set(uint32_t port, uint32_t pin)
{
    uint32_t addr = GIO_BASE + GIO_DOUT_A_OFFSET;  // 0xFFF7BC00 + 0x3C
    REG32(addr) |= (1u << pin);
}
```

### Tests Check (Validation)

```c
void test_gio_set_writes_to_correct_register(void)
{
    gio_set(GIO_PORT_A, 3);

    // Verify register at correct address was written
    TEST_ASSERT_EQUAL_HEX32(expected_value, mock_registers[offset]);
    //                                        ^^^ MOCKED hardware
}
```

---

## The Testing Pipeline

```
Step 1: YAML Input
═══════════════════════════════════════════════════════════════
soc.yaml, regs.yaml, memmap.yaml
(Your hardware specification)


Step 2: Generate C Code
═══════════════════════════════════════════════════════════════
Run: python app/main.py

Output:
- gio.c / gio.h (GPIO driver)
- sci.c / sci.h (UART driver)
- clock.c / clock.h (Clock driver)
- vim.c / vim.h (Interrupt manager)
- system.c / system.h (System init)
- entry.c, start.s, linker.cmd (Startup)
- _artifacts/llm_preamble_*.txt (FACTS MIRROR)


Step 3: Generate Tests
═══════════════════════════════════════════════════════════════
Run: python generate_validation_tests.py

Input:
- Generated C files (gio.c, gio.h, etc.)
- YAML specifications (soc.yaml, regs.yaml)
- FACTS MIRROR (hardware constants)

Output:
- tests/gio_test.c (GPIO unit tests)
- tests/sci_test.c (UART unit tests)
- tests/startup_integration_test.c (Startup sequence tests)
- tests/cross_validation_test.c (Cross-file consistency tests)


Step 4: Run Tests
═══════════════════════════════════════════════════════════════
Build tests:
$ gcc gio_test.c gio.c -o gio_test

Run tests:
$ ./gio_test

Output:
test_gio_set_writes_to_correct_register ........... PASS
test_gio_read_reads_from_correct_register ........ PASS
test_gio_addresses_match_yaml_specification ...... PASS
...
All tests passed! (45 tests)


Step 5: Report
═══════════════════════════════════════════════════════════════
Summary:
✅ GIO Driver: 12/12 tests pass
✅ SCI Driver: 10/10 tests pass
✅ System Init: 8/8 tests pass
✅ Startup Sequence: 15/15 tests pass

Total: 45/45 tests pass ✅
```

---

## What Gets Tested (Checklist)

### ✅ Register Address Tests

- [ ] All register base addresses match YAML
- [ ] All register offsets match YAML
- [ ] Calculated addresses are correct
- [ ] No off-by-one errors

### ✅ Function Behavior Tests

- [ ] `gio_set()` writes to DOUT_A
- [ ] `gio_clear()` clears in DOUT_A
- [ ] `gio_read()` reads from DIN_A
- [ ] `gio_set_dir()` modifies DIR_A
- [ ] `sci_send()` writes to TX register
- [ ] `sci_recv()` reads from RX register

### ✅ Initialization Tests

- [ ] `gio_init()` calls GCR0 setup
- [ ] `system_init()` powers up all domains
- [ ] Initialization order is correct
- [ ] No registers accessed before init

### ✅ Startup Sequence Tests

- [ ] Vector table at 0x00000000
- [ ] Reset handler loads stack
- [ ] Entry.c copies .data from FLASH
- [ ] Entry.c zeros .bss
- [ ] system_init() called before main()
- [ ] main() is called

### ✅ Cross-File Tests

- [ ] No conflicting register definitions
- [ ] No macro name collisions
- [ ] Symbol definitions match usage
- [ ] Linker script matches startup code

---

## Test Results Format

```json
{
  "generation_id": "output_20260127_133938",
  "test_run_timestamp": "20260203T150000",
  "total_tests": 45,
  "passed": 45,
  "failed": 0,
  "skipped": 0,
  "status": "PASS",
  "test_results": [
    {
      "file": "gio_test.c",
      "name": "test_gio_set_writes_to_correct_register",
      "status": "PASS",
      "duration_ms": 2
    },
    {
      "file": "sci_test.c",
      "name": "test_sci_baudrate_configuration",
      "status": "PASS",
      "duration_ms": 1
    },
    ...
  ],
  "coverage": {
    "gio_c": 95,
    "sci_c": 88,
    "system_c": 92,
    "average": 91.7
  }
}
```

---

## Why This Matters

| Without Tests                           | With Tests                         |
| --------------------------------------- | ---------------------------------- |
| 🤔 "Did the LLM generate correct code?" | ✅ "Tests prove correctness"       |
| 🤔 "Does it match the YAML spec?"       | ✅ "Tests verify against YAML"     |
| 🤔 "Will it work on the hardware?"      | ✅ "Tests simulate hardware"       |
| 😰 "What if I modify code?"             | ✅ "Regression tests catch breaks" |

---

## The Three Validation Levels

```
Level 1: FACTS MIRROR (Already done)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Extracted constants from generated code
✅ Proves what hardware values were used
🟡 Requires manual cross-check to YAML


Level 2: Unit Tests (What validation_prompt.py creates)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Mock register access + verify C code behavior
✅ Automatically tests each function
✅ Cross-checks against YAML
✅ Provides pass/fail report


Level 3: Integration Tests (Advanced)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Simulate full startup sequence + cross-file interaction
✅ Verifies startup works end-to-end
✅ Tests all files work together
✅ Catches cross-file issues
```

---

## Key Points

1. **Tests are generated by LLM** (same as the C code)
2. **Tests run ON the generated C code** (not the YAML)
3. **Tests VALIDATE against YAML** (compare expected vs actual)
4. **Tests use mocked registers** (no real hardware needed)
5. **Tests catch generation bugs** (automated quality assurance)

---

## Next Step

To generate validation tests for your current BSP:

```bash
# After you have generated BSP files:
python generate_validation_tests.py

# This will:
# 1. Read generated .c/.h files
# 2. Read your YAML specifications
# 3. Generate unit tests
# 4. Output: tests/gio_test.c, tests/sci_test.c, etc.
```

See `VALIDATION_TESTING.md` for complete implementation guide.
