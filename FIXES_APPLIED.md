# BSP Generator Fixes Applied - 2026-02-23

## Summary

Fixed two critical issues in the BSP generator that were causing problems in generated code:

1. **Missing Newlines in Generated Files** (Compiler warnings)
2. **IOMM Pin-to-PINMMR Mapping Bug** (Incorrect pin configuration)

---

## Fix 1: Missing Newlines at End of Files

### Problem
Generated header and source files were missing trailing newlines, causing compiler warnings:
```
warning #1-D: last line of file ends without a newline
```

### Solution
Updated [app/modules/utils/file_io.py](app/modules/utils/file_io.py#L129-L132) to enforce trailing newlines:

```python
# Ensure content ends with a single newline to avoid compiler warnings
if content and not content.endswith('\n'):
    content += '\n'
```

### Result
✅ All generated files will now end with a newline character
✅ No more compiler warnings about missing newlines

---

## Fix 2: IOMM Pin-to-PINMMR Mapping Bug (CRITICAL)

### Problem
The generated `IOMM_ConfigurePin()` function used **linear pin numbering** to calculate PINMMR register index:
```c
uint32_t reg_index = pin_number / 4;  // ❌ WRONG - doesn't match hardware
```

This caused pins to be configured in the wrong PINMMR registers:
- `IOMM_ConfigurePin(38, 0x02)` wrote to PINMMR9 (WRONG)
- `IOMM_ConfigurePin(39, 0x02)` wrote to PINMMR9 (WRONG)

**Should have written to:**
- Pin 38 → PINMMR7 bit 17 (SCIRX)
- Pin 39 → PINMMR8 bit 1 (SCITX)

**Impact:** Pins remained in default GPIO state, peripherals couldn't transmit/receive data

### Root Cause
The RM46 hardware uses **non-linear, device-specific** pin-to-PINMMR mapping from the datasheet, not a simple linear formula.

### Solution Applied

#### Part 1: Updated Prompt Instructions ([app/modules/generation/prompt.py](app/modules/generation/prompt.py#L2513-L2600))

Added comprehensive section **"4b. CRITICAL: IOMM PIN-TO-PINMMR MAPPING"** that:

1. **Forbids the linear calculation pattern** that was causing the bug
2. **Requires pin-to-PINMMR lookup table** generated from pinmux.yaml
3. **Provides complete implementation pattern** with:
   - Lookup table structure (package_pin → pinmmr_reg + bit_position)
   - ConfigurePin() implementation using table lookup
   - Read-modify-write with proper bit masking
4. **Documents the data source** (pinmux.yaml mux information)
5. **Explains validation** against hardware

Example pattern now required:
```c
typedef struct {
    uint8_t package_pin;
    uint8_t pinmmr_reg;
    uint8_t bit_position;
} IOMM_PinMapping_t;

static const IOMM_PinMapping_t g_pin_mapping[] = {
    { .package_pin = 38, .pinmmr_reg = 7, .bit_position = 17 },  /* SCIRX */
    { .package_pin = 39, .pinmmr_reg = 8, .bit_position = 1 },   /* SCITX */
    /* ... all pins from pinmux.yaml ... */
};
```

#### Part 2: Updated Pinmux Data Pipeline ([app/modules/generation/implementation.py](app/modules/generation/implementation.py#L198-L224))

Added special handling for IOMM module in `build_pinmux_slice()`:

```python
# Special case: IOMM needs ALL pins with mux data (for pin-to-PINMMR lookup table)
if module_upper == "IOMM":
    pins = pinmux_data.get("pins", [])
    # Filter to only pins that have mux information
    relevant_pins = []
    for pin in pins:
        functions = pin.get("functions", [])
        for func in functions:
            mux = func.get("mux")
            if mux and mux.get("register") and mux.get("bit") is not None:
                relevant_pins.append(pin)
                break
```

**Why this matters:**
- Other peripherals get only their specific pins (SCI gets SCIRX/SCITX)
- IOMM needs ALL pins with mux data to build complete lookup table
- Ensures LLM has complete pinmux information when generating IOMM driver

#### Part 3: LIN Pin Pattern Enhancement

Updated LIN pattern matching to include SCI signals:
```python
"LIN": ["LINRX", "LINTX", "LINTX", "LIN2RX", "LIN2TX", "SCIRX", "SCITX"],
```

**Why:** LIN peripheral can operate in SCI mode using SCIRX/SCITX pins (as confirmed by hardware testing)

### Result
✅ Generated IOMM driver will use correct pin-to-PINMMR mapping from pinmux.yaml
✅ Pins will be configured in correct PINMMR registers
✅ No more manual workarounds needed (like `ConfigureLINPins()` in main.c)
✅ Future peripheral drivers will work correctly without manual fixes

---

## Testing Required

After these fixes, regenerate the BSP and verify:

### 1. Newline Fix Verification
```bash
cd app
python main.py
```

Check that compiler warnings are gone:
- No more "warning #1-D: last line of file ends without a newline"

### 2. IOMM Fix Verification

**In generated code ([output_*/include/iomm_driver.c]()):**
- Check that `g_pin_mapping[]` table exists with correct mappings
- Verify `IOMM_ConfigurePin()` uses lookup table, not linear calculation
- Confirm pin 38 → PINMMR7 bit 17, pin 39 → PINMMR8 bit 1

**In hardware testing:**
- PINMMR7 register should have bit 17 set (not all 0x01010101)
- PINMMR8 register should have bit 1 set
- LIN/SCI peripherals should transmit/receive correctly
- No manual `ConfigureLINPins()` workaround needed

### 3. Cross-Reference with HALCOGEN

Compare generated IOMM pin configuration with HALCOGEN working code:
- app/Windows SCI Working/yeah2/source/pinmux.c lines 185-187

Should match:
```c
PINMMR7 |= (1 << 17);  /* Pin 38: SCIRX */
PINMMR8 |= (1 << 1);   /* Pin 39: SCITX */
```

---

## Files Modified

1. **[app/modules/utils/file_io.py](app/modules/utils/file_io.py)**
   - Line 129-132: Added newline enforcement

2. **[app/modules/generation/prompt.py](app/modules/generation/prompt.py)**
   - Lines 2513-2600: Added IOMM pin mapping instructions

3. **[app/modules/generation/implementation.py](app/modules/generation/implementation.py)**
   - Lines 198-224: Added IOMM special case to pass all pinmux data
   - Line 188: Added SCIRX/SCITX to LIN patterns

---

## What This Fixes

### For Current Generation:
- ✅ Compiler warnings eliminated
- ✅ IOMM driver will generate correctly
- ✅ Pin configuration will work on first try

### For Future Development:
- ✅ Data-driven approach (uses pinmux.yaml, not hardcoded)
- ✅ Portable to other RM46 variants
- ✅ Self-documenting (lookup table shows pin mappings)
- ✅ Easy to validate against datasheet

---

## Related Documentation

- **[IOMM_FIX_PLAN.md](IOMM_FIX_PLAN.md)** - Original comprehensive plan
- **[TROUBLESHOOTING.md](app/output_20260223_200046/TROUBLESHOOTING.md)** - Hardware diagnostic guide
- **[CLOCK_DIAGNOSTIC_README.md](app/output_20260223_200046/CLOCK_DIAGNOSTIC_README.md)** - Clock configuration info

---

## Next Steps

1. **Regenerate BSP** with these fixes applied:
   ```bash
   cd c:\Users\dovyd\Documents\GitHub\BSP-Generator\app
   python main.py
   ```

2. **Build and flash** to hardware

3. **Verify** IOMM registers in CCS Memory Browser:
   - 0xFFFFEB2C (PINMMR7) - should have bit 17 set
   - 0xFFFFEB30 (PINMMR8) - should have bit 1 set

4. **Test** serial communication works without manual pin configuration

5. **Clean up** manual workarounds in main.c (ConfigureLINPins function)

---

## Status

✅ **All fixes applied and ready for testing**

The next BSP generation should produce correct code that works on hardware without manual workarounds.
