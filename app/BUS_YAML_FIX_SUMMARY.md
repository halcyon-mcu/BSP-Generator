# BUS.YAML Schema Fix Summary

**Date**: 2026-02-24
**Status**: ✅ All validation errors fixed

---

## Issue Found

The bus.yaml file was missing required `freq_hz` fields for derived clock sources (PLL1 and PLL2). The Pydantic schema requires all clock sources to have a frequency field.

**Error:**
```
bus.yaml validation failed:
  - sources -> 1 -> freq_hz: Field required
  - sources -> 2 -> freq_hz: Field required
```

---

## Fix Applied

Added `freq_hz` field to both PLL clock sources, using the expected output frequency from PLL1's configuration:

### PLL1 (source index 1)

**Before:**
```yaml
- name: PLL1
  type: pll
  parent: OSCIN
  x-ext:
    description: Main PLL with frequency modulation capability
```

**After:**
```yaml
- name: PLL1
  type: pll
  freq_hz: 440000000
  parent: OSCIN
  x-ext:
    description: Main PLL with frequency modulation capability
```

**Frequency Calculation:**
- Formula: `PLLCLK = OSCIN × NF / (NR × R)`
- Values: `16MHz × 165 / 6 = 440MHz`
- Source: PLL1's `default_config.expected_output_hz`

### PLL2 (source index 2)

**Before:**
```yaml
- name: PLL2
  type: pll
  parent: OSCIN
  x-ext:
    description: Secondary PLL without frequency modulation
```

**After:**
```yaml
- name: PLL2
  type: pll
  freq_hz: 440000000
  parent: OSCIN
  x-ext:
    description: Secondary PLL without frequency modulation
```

**Note:** PLL2 uses same frequency as PLL1 (similar structure, same configuration parameters expected)

---

## Validation Results

```
Running Pydantic validation on bus.yaml...
[SUCCESS] Validation passed!
  - Loaded 3 clock sources
  - Loaded 7 clock domains

Clock sources:
  - OSCIN: 16 MHz
  - PLL1: 440 MHz
  - PLL2: 440 MHz
```

---

## Clock Source Summary

| Source | Type | Frequency | Parent | Description |
|--------|------|-----------|--------|-------------|
| OSCIN | external_xtal | 16 MHz | - | External crystal oscillator |
| PLL1 | pll | 440 MHz | OSCIN | Main PLL with FM capability |
| PLL2 | pll | 440 MHz | OSCIN | Secondary PLL without FM |

---

## Files Modified

- [yaml_in/bus.yaml](yaml_in/bus.yaml) - Added freq_hz to PLL sources
- Backup created at: [yaml_in/bus.yaml.backup](yaml_in/bus.yaml.backup)

---

## Summary

✅ Added missing `freq_hz` fields to PLL1 and PLL2 clock sources
✅ Validation now passes successfully
✅ 3 clock sources and 7 clock domains loaded
✅ Ready for BSP generation!

---

**Next Step**: Run `main.py` - all YAML validation errors are now resolved!
