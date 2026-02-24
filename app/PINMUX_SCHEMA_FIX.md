# Pinmux Schema Fix Summary

**Date**: 2026-02-24
**Status**: ✅ Complete

---

## Issue

After fixing bus.yaml, irq.yaml, and regs.yaml validation errors, running `main.py` revealed pinmux.yaml validation failures:

```
pinmux.yaml validation failed:
  - pins -> 0 -> pin: Field required
  - pins -> 0 -> signals: Field required
  - pins -> 1 -> pin: Field required
  - pins -> 1 -> signals: Field required
  ...
  (54 pin entries × 2 fields = 108 validation errors)
```

---

## Root Cause

The Pydantic schema was **completely incorrect** for pinmux.yaml structure.

### What the Schema Expected (WRONG)
```python
class PinDefinition(BaseModel):
    pin: Union[int, str]     # Field required
    signals: List[str]       # Field required
```

### What pinmux.yaml Actually Contains (CORRECT)
```yaml
pins:
  - package_pin: 132              # Physical pin number
    name: "GIOB[3]"              # Pin name
    board:                       # Board-specific info
      net: "GIOB[3]"
    functions:                   # Alternate functions
      - af: "0"
        signal: "GIOB[3]"
        mux:
          register: "PINMMR0"
          bit: 0
      - af: "1"
        signal: "USB2.RCV"
        mux:
          register: "PINMMR0"
          bit: 1
```

The schema was created with a simplified/incorrect understanding of the pinmux structure.

---

## Fix Applied

Updated Pydantic schema to match the actual YAML structure:

### New Schema Models

#### 1. MuxInfo
```python
class MuxInfo(BaseModel):
    """Multiplexer configuration for a pin function."""
    register: str  # Mux control register name
    bit: int       # Bit position in register
```

#### 2. PinFunction
```python
class PinFunction(BaseModel):
    """Pin function/alternate function definition."""
    af: str            # Alternate function number
    signal: str        # Signal name for this function
    mux: MuxInfo       # Mux register configuration
```

#### 3. BoardInfo
```python
class BoardInfo(BaseModel):
    """Board-specific pin information."""
    net: Optional[str]  # Net name on board
```

#### 4. PinDefinition (Updated)
```python
class PinDefinition(BaseModel):
    """Pin definition in pinmux.yaml."""
    package_pin: int                    # Physical package pin number
    name: str                          # Pin name/primary signal
    board: Optional[BoardInfo]         # Board-specific info
    functions: List[PinFunction]       # Available alternate functions
```

#### 5. PinmuxYAML (Root)
```python
class PinmuxYAML(BaseModel):
    """Root schema for pinmux.yaml."""
    pins: List[PinDefinition]
```

All models use `model_config = ConfigDict(extra='allow')` to allow additional fields like `ir_schema_version`, `package`, and `provenance` at the root level, plus any `x-ext` fields.

---

## Validation Results

### Before Fix
```
pinmux.yaml validation failed:
  - 108 validation errors (54 pins × 2 required fields)
```

### After Fix
```
[SUCCESS] pinmux.yaml validation passed!
  - Loaded 54 pin definitions

Sample pins:
  - Pin 132 (GIOB[3]): 5 functions
  - Pin 5 (GIOA[0]): 5 functions
  - Pin 3 (MIBSPI3NCS[3]): 5 functions
```

---

## Files Modified

1. **[modules/yaml/schemas.py](modules/yaml/schemas.py)** (lines 221-271)
   - Added imports: `ConfigDict` from pydantic
   - Created new models: `MuxInfo`, `PinFunction`, `BoardInfo`
   - Rewrote `PinDefinition` to match actual YAML structure
   - Updated `PinmuxYAML` with flexible config

2. **[yaml_schemas/pinmux.schema.json](yaml_schemas/pinmux.schema.json)**
   - Regenerated from updated Pydantic models
   - Now reflects correct structure for IDE support

---

## Complete YAML Validation Status

After all fixes applied:

| YAML File | Status | Notes |
|-----------|--------|-------|
| **regs.yaml** | ✅ Pass | Fixed 64 placeholders (base addresses, reset values) |
| **irq.yaml** | ✅ Pass | Fixed structure (interrupt_controller, id→number, duplicates) |
| **bus.yaml** | ✅ Pass | Made freq_hz optional for configurable PLLs |
| **pinmux.yaml** | ✅ Pass | Fixed schema to match actual structure |
| **soc.yaml** | ✅ Pass | No issues |
| **memmap.yaml** | ✅ Pass | No issues |
| **board.yaml** | ✅ Pass | No issues (optional file) |

---

## Current Status

**Schema Validation**: ✅ All YAML files pass Pydantic validation

**Next Issue**: Cross-reference validation (different type of validation)
- Checks if peripherals in soc.yaml have corresponding entries in regs.yaml
- 38 peripherals missing register definitions
- This is a **data completeness** issue, not a schema validation error
- Expected behavior for incomplete dataset

Example cross-reference errors:
```
Cross-reference validation failed:
  - PIN: regs_ref 'PIN' not found in regs.yaml
  - MIBADC1: regs_ref 'MIBADC1' not found in regs.yaml
  - I2C: regs_ref 'I2C' not found in regs.yaml
  ...
```

These require adding register definitions for each peripheral, which is separate from schema fixes.

---

## Technical Details

### Nested Model Structure

The pinmux schema now has 4 levels of nesting:

```
PinmuxYAML
  └── pins: List[PinDefinition]
        ├── package_pin: int
        ├── name: str
        ├── board: Optional[BoardInfo]
        │     └── net: Optional[str]
        └── functions: List[PinFunction]
              ├── af: str
              ├── signal: str
              └── mux: MuxInfo
                    ├── register: str
                    └── bit: int
```

### Field Name Warning

There is a harmless warning:
```
UserWarning: Field name "register" in "MuxInfo" shadows an attribute in parent "BaseModel"
```

This occurs because `register` is a common Python name that shadows a BaseModel internal method. The field still works correctly - it's just a warning. Options to silence it:
1. Rename field to `reg_name` or `register_name`
2. Suppress the warning
3. Ignore it (recommended - no functional impact)

---

## Timeline

1. ✅ Fixed regs.yaml (64 placeholders)
2. ✅ Fixed irq.yaml (structure mismatch)
3. ✅ Fixed bus.yaml (freq_hz optional)
4. ✅ Implemented JSON schema auto-generation
5. ✅ Fixed pinmux.yaml (schema completely wrong)
6. ⚠️ **NEW**: Cross-reference validation errors (data completeness)

---

## Summary

Successfully fixed pinmux.yaml validation by correcting the Pydantic schema to match the actual YAML structure. The schema now properly validates:
- Package pin numbers
- Pin names and board net assignments
- Alternate function configurations
- Multiplexer register settings

**All 7 YAML schema validations now pass!** 🎉

The remaining cross-reference errors are a separate issue related to data completeness, not schema validation.

---

**Status**: ✅ Complete - All schema validation errors resolved
