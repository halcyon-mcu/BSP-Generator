# Clock Source Schema Update - freq_hz Optional

**Date**: 2026-02-24
**Status**: ✅ Complete

---

## Issue

After adding `freq_hz: 440000000` to PLL1 and PLL2 in bus.yaml to fix validation errors, we identified a concern:

**Problem**: Fixed frequency values for configurable PLL sources could cause incorrect behavior during BSP generation, as these PLLs are runtime-configurable via multipliers and dividers.

**User Decision**: "Let's make freq_hz optional"

---

## Changes Made

### 1. Updated ClockSource Schema ✅

**File**: [modules/yaml/schemas.py](modules/yaml/schemas.py) (line 145)

**Before:**
```python
class ClockSource(BaseModel):
    """Clock source definition."""
    name: str
    freq_hz: int = Field(..., gt=0, description="Frequency in Hz")
    desc: Optional[str] = None
```

**After:**
```python
class ClockSource(BaseModel):
    """Clock source definition."""
    name: str
    freq_hz: Optional[int] = Field(None, gt=0, description="Frequency in Hz")
    desc: Optional[str] = None
```

**Change**: `freq_hz` is now `Optional[int]` with default value `None` instead of required.

**Validation**: When freq_hz IS provided, it must still be > 0 (enforced by `gt=0`).

---

### 2. Updated bus.yaml ✅

**File**: [yaml_in/bus.yaml](yaml_in/bus.yaml)

Removed `freq_hz` from configurable PLL sources, kept it for fixed external crystal:

| Source | Type | freq_hz | Reasoning |
|--------|------|---------|-----------|
| OSCIN | external_xtal | 16000000 | Fixed external crystal - freq_hz required |
| PLL1 | pll | *(removed)* | Configurable via NF/NR/R fields - freq_hz omitted |
| PLL2 | pll | *(removed)* | Configurable via control registers - freq_hz omitted |

**Before (PLL1):**
```yaml
- name: PLL1
  type: pll
  freq_hz: 440000000  # <-- REMOVED
  parent: OSCIN
```

**After (PLL1):**
```yaml
- name: PLL1
  type: pll
  parent: OSCIN
```

---

## Validation Results

```bash
$ python -c "from modules.yaml.schemas import BusYAML; import yaml; ..."

[SUCCESS] bus.yaml validation passed!
  - Loaded 3 clock sources
  - Loaded 7 clock domains

Clock sources:
  - OSCIN: 16 MHz
  - PLL1: configurable
  - PLL2: configurable
```

**Summary:**
- ✅ Schema change applied successfully
- ✅ bus.yaml updated to remove misleading PLL frequencies
- ✅ Validation passes with optional freq_hz
- ✅ OSCIN retains fixed frequency (external crystal)
- ✅ PLL sources marked as configurable (no freq_hz)

---

## Semantic Meaning

### When freq_hz is Present
- Indicates a **fixed, non-configurable** clock source
- Example: External crystal oscillators (OSCIN at 16 MHz)
- BSP generation uses this value directly

### When freq_hz is Absent (None)
- Indicates a **configurable** clock source
- Example: PLLs with multiplier/divider fields
- BSP generation must:
  - Calculate frequency from parent source + configuration registers
  - Use formulas like `PLLCLK = OSCIN × NF / (NR × R)`
  - Reference `default_config.expected_output_hz` if provided

---

## Impact on BSP Generation

**Generator Code Must Now Handle**:
1. Check if `ClockSource.freq_hz is None`
2. If None, calculate frequency from:
   - Parent source frequency
   - Configuration register fields (NF, NR, R, etc.)
   - Default configuration if available
3. If present, use the fixed frequency directly

**Example Logic**:
```python
def get_clock_frequency(source: ClockSource) -> int:
    if source.freq_hz is not None:
        # Fixed frequency source
        return source.freq_hz
    elif source.type == 'pll':
        # Calculate from PLL configuration
        parent_freq = get_clock_frequency(parent_source)
        nf = source.multiplier_field.default_value
        nr = source.ref_divider_field.default_value
        r = source.post_divider_field.default_value
        return int(parent_freq * nf / (nr * r))
    else:
        raise ValueError(f"Cannot determine frequency for {source.name}")
```

---

## Related Issues Fixed

This change completes the YAML validation fixes for:
- ✅ regs.yaml: 64 placeholders fixed
- ✅ irq.yaml: 3 structural issues fixed
- ✅ bus.yaml: 2 missing fields → changed to optional schema
- ⚠️ pinmux.yaml: New validation errors discovered (separate issue)

---

## Files Modified

1. [modules/yaml/schemas.py](modules/yaml/schemas.py) - Made freq_hz optional
2. [yaml_in/bus.yaml](yaml_in/bus.yaml) - Removed freq_hz from PLL sources

---

## Next Steps

1. ✅ Schema updated to make freq_hz optional
2. ✅ bus.yaml updated to reflect configurable PLLs
3. ✅ Validation passes
4. ⚠️ **New issue discovered**: pinmux.yaml validation failing
   - Missing `pin` and `signals` fields for all pin entries
   - Requires separate investigation and fix

---

**Status**: ✅ Clock source schema update complete and validated
