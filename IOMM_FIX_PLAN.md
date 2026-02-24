# IOMM Driver Pin Mapping Fix - Implementation Plan

## Problem Summary

**Current Issue**: The generated `IOMM_ConfigurePin()` function uses **linear pin numbering** (pin_number / 4) to calculate PINMMR register index, but the RM46 hardware uses **non-linear hardware-specific mapping** from the datasheet.

**Result**: Pin configuration writes to wrong PINMMR registers, causing pins to remain in default state.

**Example**:
- `IOMM_ConfigurePin(38, 0x02)` → Calculates PINMMR9, but pin 38 is actually in PINMMR7
- `IOMM_ConfigurePin(39, 0x02)` → Calculates PINMMR9, but pin 39 is actually in PINMMR8

## Root Cause Analysis

The IOMM driver was generated with the assumption that package pins map sequentially to PINMMR registers, but:

1. **Hardware Reality**: Each device has a unique pin-to-PINMMR mapping defined in the datasheet
2. **Data Source**: This mapping is correctly defined in `pinmux.yaml` with register and bit information
3. **Gap**: The IOMM driver doesn't use the pinmux.yaml data; it assumes linear mapping

## Solution Approaches

### Option 1: Generate Pin-to-Register Lookup Table (RECOMMENDED)

**Approach**: Generate a lookup table from pinmux.yaml during code generation

**Implementation**:

1. **Parse pinmux.yaml during generation** to extract pin-to-PINMMR mappings
2. **Generate lookup table** in iomm_driver.c:

```c
/* Auto-generated from pinmux.yaml */
typedef struct {
    uint8_t package_pin;
    uint8_t pinmmr_reg;      /* PINMMR register number (0-29) */
    uint8_t bit_position;    /* Bit position within register (0-31) */
} IOMM_PinMapping_t;

static const IOMM_PinMapping_t pin_to_pinmmr_map[] = {
    { .package_pin = 38, .pinmmr_reg = 7, .bit_position = 17 },
    { .package_pin = 39, .pinmmr_reg = 8, .bit_position = 1 },
    { .package_pin = 4, .pinmmr_reg = 0, .bit_position = 25 },
    /* ... all pins from pinmux.yaml ... */
};
```

3. **Update IOMM_ConfigurePin()** to use lookup table:

```c
IOMM_Status_t IOMM_ConfigurePin(IOMM_PinNumber_t pin, IOMM_PinFunction_t function)
{
    uint32_t i;
    const IOMM_PinMapping_t* mapping = NULL;
    volatile uint32_t* pinmmr_reg;
    uint32_t reg_value;

    /* Find pin in lookup table */
    for (i = 0; i < ARRAY_SIZE(pin_to_pinmmr_map); i++) {
        if (pin_to_pinmmr_map[i].package_pin == pin) {
            mapping = &pin_to_pinmmr_map[i];
            break;
        }
    }

    if (mapping == NULL) {
        return IOMM_STATUS_INVALID_PIN;
    }

    /* Unlock IOMM */
    IOMM_Unlock();

    /* Get pointer to PINMMR register */
    pinmmr_reg = &iommREG->PINMMR0 + mapping->pinmmr_reg;

    /* Read-modify-write with proper bit masking */
    reg_value = *pinmmr_reg;
    reg_value &= ~(0xFFU << mapping->bit_position);  /* Clear function bits */
    reg_value |= (function & 0xFFU) << mapping->bit_position;  /* Set new function */
    *pinmmr_reg = reg_value;

    /* Lock IOMM */
    IOMM_Lock();

    return IOMM_STATUS_OK;
}
```

**Advantages**:
- ✅ Correct for all pins
- ✅ Data-driven from pinmux.yaml
- ✅ Portable to other RM46 variants
- ✅ Self-documenting
- ✅ Easy to validate against datasheet

**Disadvantages**:
- Requires lookup (O(n) search) - could optimize with binary search or hash
- Larger code size due to table

---

### Option 2: Generate Direct Pin Configuration Functions

**Approach**: Generate specific functions for each peripheral instance

**Implementation**:

```c
/* Auto-generated for LIN instance from pinmux.yaml */
void LIN_EnablePins(void)
{
    IOMM_Unlock();

    /* Pin 38: SCIRX - PINMMR7 bit 17 */
    iommREG->PINMMR7 |= (0x02U << 16);

    /* Pin 39: SCITX - PINMMR8 bit 1 */
    iommREG->PINMMR8 |= (0x02U << 0);

    IOMM_Lock();
}

/* Auto-generated for SCI instance */
void SCI_EnablePins(void)
{
    /* Same pins as LIN in this case */
    IOMM_Unlock();
    iommREG->PINMMR7 |= (0x02U << 16);
    iommREG->PINMMR8 |= (0x02U << 0);
    IOMM_Lock();
}
```

**Advantages**:
- ✅ Fastest execution (no lookup)
- ✅ Smallest code per peripheral
- ✅ Most readable
- ✅ Already attempted (but generation failed)

**Disadvantages**:
- Requires fixing the peripheral-specific EnablePins generation
- No generic IOMM_ConfigurePin() for dynamic use

---

### Option 3: Fix Linear Calculation with Device-Specific Offset Table

**Approach**: Add device-specific offset table to convert package pins to PINMMR indices

**Not Recommended**: This is more complex and error-prone than Option 1.

---

## Recommended Implementation: Option 1 (Lookup Table)

### Phase 1: Add Lookup Table Generation

**File**: `app/modules/generation/iomm_generator.py` (new or modify existing)

**Function**: `generate_pin_lookup_table(pinmux_data)`

```python
def generate_pin_lookup_table(pinmux_data: List[Dict]) -> str:
    """
    Generate C lookup table from pinmux.yaml data.

    Args:
        pinmux_data: Parsed pinmux.yaml pin definitions

    Returns:
        C code string for lookup table
    """
    entries = []

    for pin in pinmux_data:
        package_pin = pin.get('package_pin')
        functions = pin.get('functions', [])

        # For each alternate function, we need to extract register and bit
        for func in functions:
            mux = func.get('mux', {})
            register = mux.get('register')  # e.g., "PINMMR7"
            bit = mux.get('bit')            # e.g., 17

            if register and bit is not None:
                # Extract register number from "PINMMRx"
                reg_num = int(register.replace('PINMMR', ''))

                entries.append(
                    f"    {{ .package_pin = {package_pin}, "
                    f".pinmmr_reg = {reg_num}, "
                    f".bit_position = {bit} }}"
                )

    # Generate C array
    table = "static const IOMM_PinMapping_t pin_to_pinmmr_map[] = {\n"
    table += ",\n".join(entries)
    table += "\n};\n"
    table += f"#define PIN_MAPPING_COUNT {len(entries)}\n"

    return table
```

### Phase 2: Update IOMM Driver Template

**File**: `app/modules/generation/prompt.py` (IOMM driver section)

Add to the IOMM generation instructions:

```python
IOMM PIN MAPPING REQUIREMENTS:
================================
The IOMM driver MUST use the actual pin-to-PINMMR register mapping from pinmux.yaml.
DO NOT use linear pin number calculation (pin/4).

REQUIRED PATTERN:
1. Generate pin lookup table from pinmux.yaml with structure:
   - package_pin: Physical pin number
   - pinmmr_reg: PINMMR register index (0-29)
   - bit_position: Bit position within register

2. IOMM_ConfigurePin() implementation:
   - Search lookup table for package pin
   - Use pinmmr_reg and bit_position from table
   - Apply function value at correct bit position

3. If pinmux.yaml data is incomplete:
   - Document missing pins in comments
   - Return IOMM_STATUS_INVALID_PIN for unmapped pins
```

### Phase 3: Integration with Pin Config Builder

**File**: `app/modules/generation/pin_config_builder.py`

Add function to generate IOMM lookup table data:

```python
def generate_iomm_lookup_data(pinmux_data: List[Dict]) -> Dict[int, Dict]:
    """
    Extract pin-to-PINMMR mapping from pinmux.yaml.

    Returns:
        Dict mapping package_pin → {register, bit, functions}
    """
    lookup = {}

    for pin in pinmux_data:
        package_pin = pin.get('package_pin')
        functions = pin.get('functions', [])

        pin_mappings = []
        for func in functions:
            mux = func.get('mux', {})
            if mux:
                pin_mappings.append({
                    'signal': func.get('signal'),
                    'af': func.get('af'),
                    'register': mux.get('register'),
                    'bit': mux.get('bit')
                })

        if pin_mappings:
            lookup[package_pin] = {
                'name': pin.get('name'),
                'mappings': pin_mappings
            }

    return lookup
```

### Phase 4: Validation

**Test Cases**:
1. Generate BSP with LIN/SCI peripherals
2. Verify IOMM_ConfigurePin(38, 0x02) writes to PINMMR7 bit 17
3. Verify IOMM_ConfigurePin(39, 0x02) writes to PINMMR8 bit 1
4. Test with other peripherals (CAN, SPI, I2C)
5. Compare register values with HALCOGEN output

---

## Implementation Priority

1. **Immediate** (Current Session):
   - ✅ Manual workaround in main.c (DONE)
   - ✅ Document the issue (this file)

2. **High Priority** (Next Sprint):
   - Implement Option 1: Generate pin lookup table
   - Update IOMM driver template
   - Add validation tests

3. **Medium Priority**:
   - Fix peripheral-specific EnablePins generation (Option 2)
   - Add IOMM driver validation to BSP generator tests

4. **Low Priority**:
   - Optimize lookup with binary search or perfect hash
   - Add IOMM configuration validation report

---

## Files to Modify

1. **app/modules/generation/prompt.py**
   - Add IOMM pin mapping requirements to generation instructions
   - Include lookup table generation pattern

2. **app/modules/generation/pin_config_builder.py**
   - Add `generate_iomm_lookup_data()` function
   - Export lookup data for IOMM driver generation

3. **app/modules/generation/implementation.py**
   - Pass IOMM lookup data to LLM context
   - Ensure pinmux.yaml is available during IOMM generation

4. **app/yaml_in/pinmux.yaml** (validation)
   - Verify all pins have complete mux data
   - Fix any missing register/bit information

---

## Success Criteria

✅ **IOMM_ConfigurePin(38, 0x02)** writes to PINMMR7 bit 17 (not PINMMR9)
✅ **IOMM_ConfigurePin(39, 0x02)** writes to PINMMR8 bit 1 (not PINMMR9)
✅ **Generated code matches HALCOGEN** pin configuration
✅ **No hardcoded pin mappings** - all from pinmux.yaml
✅ **Works for all peripherals** - CAN, SPI, I2C, GIO, etc.

---

## Alternative: Peripheral-Specific EnablePins (Parallel Track)

While fixing the generic IOMM driver, also improve peripheral-specific EnablePins generation:

**Enhancement**: Make pin_config_builder.py return complete PINMMR register data instead of just pin numbers, so generated EnablePins functions can write directly to correct registers without calling IOMM_ConfigurePin().

This gives us both:
- Working generic IOMM driver (Option 1)
- Optimized peripheral-specific functions (Option 2)
