# Your Question Answered: Tests on YAML or Code?

## 🎯 Direct Answer

**Tests are run ON the generated C code, validating it against the YAML specifications.**

---

## 📊 Visual Summary

```
┌────────────┐
│ YAML Input │ ← Specifies: "GIO base = 0xFFF7BC00, offset = 0x3C"
└─────┬──────┘
      │
      ▼
┌─────────────────────────────┐
│ BSP Generator               │ ← Creates C code from YAML
│ (prompt.py)                 │
└─────┬───────────────────────┘
      │
      ▼
┌─────────────────────────────┐
│ Generated C Code            │ ← void gio_set() {
│ (gio.c, sci.c, etc.)        │    REG32(0xFFF7BC3C) = ...
└─────┬───────────────────────┘   }
      │
      ├─────────────────────────────────────┐
      │                                     │
      ▼                                     ▼
┌───────────────────┐         ┌──────────────────────┐
│ FACTS MIRROR      │         │ Test Generator       │
│ (validate here)   │         │ (validation_prompt)  │
└───────────────────┘         └────────┬─────────────┘
                                       │
                                       ▼
                              ┌──────────────────────┐
                              │ Unit Tests           │ ← Call gio_set()
                              │ (gio_test.c)         │   with mocks
                              └────────┬─────────────┘
                                       │
                                       ▼
                              ┌──────────────────────┐
                              │ Test Execution       │ ← Mock registers
                              │ with Mocks           │   verify writes
                              └────────┬─────────────┘
                                       │
                                       ▼
                              ┌──────────────────────┐
                              │ ✅ PASS / ❌ FAIL    │ ← Result
                              └──────────────────────┘
```

---

## 🔄 The Flow Explained

### Step 1: You Provide YAML

```yaml
peripherals:
  GIO:
    base_address: "0xFFF7BC00"
    registers:
      DOUT_A:
        offset: "0x3C"
```

### Step 2: Generator Creates C Code

```c
#define GIO_BASE 0xFFF7BC00u
#define GIO_DOUT_A_OFFSET 0x3Cu

void gio_set(uint32_t port, uint32_t pin)
{
    uint32_t addr = GIO_BASE + GIO_DOUT_A_OFFSET;  // 0xFFF7BC3C
    REG32(addr) |= (1u << pin);
}
```

### Step 3: Test Generator Creates Tests

```c
void test_gio_set_writes_to_correct_register(void)
{
    // Call the C function
    gio_set(GIO_PORT_A, 3);

    // Verify it wrote to the right register
    // Expected from YAML: 0xFFF7BC00 + 0x3C = 0xFFF7BC3C
    TEST_ASSERT_EQUAL_HEX32(
        0xFFF7BC3C,
        mock_registers[calculated_offset]
    );
}
```

### Step 4: Tests Execute

```bash
$ ./gio_test
test_gio_set_writes_to_correct_register ........... PASS ✅
```

---

## 📝 Key Definitions

| Term                 | Meaning                         | Example                    |
| -------------------- | ------------------------------- | -------------------------- |
| **YAML**             | Input specification of hardware | `GIO_BASE: 0xFFF7BC00`     |
| **Generated C Code** | What the BSP generator creates  | `gio.c`, `sci.c`           |
| **Tests**            | Unit tests that validate C code | `gio_test.c`, `sci_test.c` |
| **FACTS MIRROR**     | Extracted hardware constants    | `GIO_BASE = 0xFFF7BC00`    |
| **Mock Registers**   | Fake hardware for testing       | Array of uint32_t          |
| **Validation**       | Proving C code matches YAML     | Test assertions pass ✅    |

---

## 🧪 Concrete Example: GPIO

### What YAML Specifies

```
GIO peripheral at address 0xFFF7BC00
DOUT_A register at offset 0x3C
DIR_A register at offset 0x34
```

### What Code Does

```c
void gio_set(uint32_t port, uint32_t pin)
{
    // Uses the addresses from YAML:
    REG32(0xFFF7BC00 + 0x3C) |= (1 << pin);
}
```

### What Tests Verify

```
1. Call gio_set(PORT_A, 3)
2. Mock register at 0xFFF7BC3C should have bit 3 set
3. Compare expected (from YAML) vs actual (from mock)
4. Assert they match ✅
```

---

## ✅ Three Levels of Validation

### Level 1: FACTS MIRROR ✅ (Already Done)

```
What:   Extract constants from generated code
Where:  _artifacts/llm_preamble_*.txt
Checks: GIO_BASE = 0xFFF7BC00 (from YAML? ✅)
```

### Level 2: Unit Tests (What validation_prompt.py Creates)

```
What:   Run C functions with mocked registers
Where:  tests/gio_test.c, tests/sci_test.c
Checks: Do functions write correct values? ✅
```

### Level 3: Integration Tests (Advanced)

```
What:   Test startup sequence and cross-file behavior
Where:  tests/startup_integration_test.c
Checks: Does everything work together? ✅
```

---

## 📋 What Gets Tested

### ✅ Register Addresses

- Does `gio_set()` write to the correct register?
- Is the calculated address correct?
- Do all register offsets match YAML?

### ✅ Function Behavior

- Does `gio_set()` actually set the bit?
- Does `gio_read()` read the right register?
- Are all functions implemented?

### ✅ Initialization

- Does `system_init()` power up hardware?
- Are all registers initialized?
- Is initialization order correct?

### ✅ Cross-File Consistency

- Do all files have matching definitions?
- Is the startup sequence complete?
- Do linker symbols exist?

---

## 🎓 Learning Resources I Created

| Document                   | Purpose              | Read Time |
| -------------------------- | -------------------- | --------- |
| **TEST_QUICK_ANSWER.md**   | One-page answer      | 2 min     |
| **TEST_FLOW_VISUAL.md**    | Visual flow diagram  | 5 min     |
| **TEST_ARCHITECTURE.md**   | Detailed explanation | 20 min    |
| **DOCUMENTATION_INDEX.md** | Navigation hub       | 5 min     |

---

## ✨ Bottom Line

```
Tests RUN ON:      Generated C code (gio.c, sci.c, etc.)
Tests CHECK:       Register access, function behavior, initialization
Tests VALIDATE:    Against YAML specifications
Test METHOD:       Mock hardware registers, verify writes
Test RESULT:       ✅ "C code correctly implements YAML" or ❌ Bug found
```

**That's it!** You now know everything about how testing works in this project.

---

## 🚀 Next Steps

1. **Understand the generated BSP** → See `OUTPUT_SUMMARY.md`
2. **Use the BSP in CCS** → See `QUICK_REFERENCE.md`
3. **Validate the BSP** → See `VALIDATION_TESTING.md`
4. **Create tests for the BSP** → Run `generate_validation_tests.py`

---

## 📞 Quick Reference

**Q: Tests run on what?**  
A: Generated C code (gio.c, sci.c, system.c, etc.)

**Q: Tests validate against what?**  
A: YAML specifications (soc.yaml, regs.yaml, memmap.yaml)

**Q: How do tests work?**  
A: Mock hardware registers, call C functions, verify register accesses match YAML

**Q: Who generates the tests?**  
A: LLM (Claude) via validation_prompt.py

**Q: Are tests automatic?**  
A: Yes! LLM generates them from YAML + generated code

**Q: How do I run tests?**  
A: Compile with mocks and run with Unity test framework

**Q: What if a test fails?**  
A: Bug in generated code, regenerate or fix manually

---

**You got the answer! Happy coding! 🎉**
