# IRQ.YAML Schema Fix Summary

**Date**: 2026-02-24
**Status**: ✅ All validation errors fixed

---

## Issues Found

The irq.yaml file structure didn't match the Pydantic schema expectations:

1. **interrupt_controller** was a nested dictionary but schema expected a simple string
2. **IRQ entries** used `id` field but schema expected `number`
3. **Duplicate IRQ names** - 12 entries all named "RESERVED" violated uniqueness constraint

---

## Fixes Applied

### 1. Simplified interrupt_controller Structure

**Before:**
```yaml
interrupt_controller:
  name: VIM
  type: vim
  vector_table:
    base_address: '0xFFF82000'
    entries: 128
    entry_size_bytes: 4
    phantom_entry: 0
    valid_channels:
    - 0
    - 126
    reserved_channels:
    - 127
```

**After:**
```yaml
interrupt_controller: VIM
```

### 2. Renamed id to number in IRQ Entries

**Before:**
```yaml
- name: RTI_COMPARE0
  id: 2
  desc: ''
```

**After:**
```yaml
- name: RTI_COMPARE0
  number: 2
  desc: ''
```

### 3. Made RESERVED IRQ Names Unique

Added IRQ numbers to make each RESERVED entry unique:

| Old Name | New Name | IRQ Number |
|----------|----------|------------|
| RESERVED | RESERVED_1 | 1 |
| RESERVED | RESERVED_18 | 18 |
| RESERVED | RESERVED_32 | 32 |
| RESERVED | RESERVED_36 | 36 |
| RESERVED | RESERVED_43 | 43 |
| RESERVED | RESERVED_48 | 48 |
| RESERVED | RESERVED_52 | 52 |
| RESERVED | RESERVED_58 | 58 |
| RESERVED | RESERVED_62 | 62 |
| RESERVED | RESERVED_84 | 84 |
| RESERVED | RESERVED_86 | 86 |
| RESERVED | RESERVED_87 | 87 |

---

## Validation Results

```
Running Pydantic validation on irq.yaml...
[SUCCESS] Validation passed!
  - Interrupt controller: VIM
  - Loaded 111 IRQ definitions
```

---

## Files Modified

- [yaml_in/irq.yaml](yaml_in/irq.yaml) - Fixed structure and data
- Backup created at: [yaml_in/irq.yaml.backup](yaml_in/irq.yaml.backup)
- Fix script: [fix_irq_yaml.py](fix_irq_yaml.py)

---

## Summary

All irq.yaml validation errors have been resolved:
- ✅ interrupt_controller is now a simple string
- ✅ All IRQ entries use `number` field instead of `id`
- ✅ All RESERVED entries have unique names
- ✅ 111 IRQ definitions loaded successfully
- ✅ Ready for BSP generation!

---

**Next Step**: Run `main.py` - all YAML validation errors are now resolved!
