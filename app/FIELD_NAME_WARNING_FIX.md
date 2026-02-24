# Field Name Shadow Warning Fix

**Date**: 2026-02-24
**Status**: ✅ Fixed

---

## Issue

Warning appeared on every run:
```
UserWarning: Field name "register" in "MuxInfo" shadows an attribute in parent "BaseModel"
```

---

## Root Cause

The `MuxInfo` class had a field named `register`:

```python
class MuxInfo(BaseModel):
    register: str  # ← Shadows BaseModel.register method
    bit: int
```

Pydantic's `BaseModel` has an internal method called `register`, so using `register` as a field name causes a naming collision.

---

## Solution

Renamed the Python field to `register_name` and used Pydantic's `alias` feature to map the YAML field name:

### Before
```python
class MuxInfo(BaseModel):
    model_config = ConfigDict(extra='allow')

    register: str = Field(..., description="Mux control register name")
    bit: int = Field(..., ge=0, description="Bit position in register")
```

### After
```python
class MuxInfo(BaseModel):
    model_config = ConfigDict(extra='allow', populate_by_name=True)

    register_name: str = Field(..., description="Mux control register name", alias='register')
    bit: int = Field(..., ge=0, description="Bit position in register")
```

### Key Changes
1. **Field name**: `register` → `register_name` (no collision)
2. **Alias**: `alias='register'` (YAML still uses `register`)
3. **Config**: Added `populate_by_name=True` (accepts both names)

---

## Compatibility

### YAML Structure (Unchanged)
```yaml
mux:
  register: "PINMMR0"  # ← Still uses 'register'
  bit: 0
```

### Python Access
```python
func.mux.register_name  # ← Access via new field name
# Result: "PINMMR0"
```

The YAML field name `register` automatically maps to Python's `register_name` via the alias.

---

## Validation

### Before Fix
```bash
$ python main.py
UserWarning: Field name "register" in "MuxInfo" shadows an attribute in parent "BaseModel"
[info] Loaded token history...
```

### After Fix
```bash
$ python main.py
[info] Loaded token history...
# No warning!
```

---

## Files Modified

1. **[modules/yaml/schemas.py](modules/yaml/schemas.py)** (line 229)
   - Renamed field: `register` → `register_name`
   - Added alias: `alias='register'`
   - Added config: `populate_by_name=True`

2. **[yaml_schemas/pinmux.schema.json](yaml_schemas/pinmux.schema.json)**
   - Regenerated with updated schema
   - JSON schema still uses "register" (via alias)

---

## Testing

```python
from modules.yaml.schemas import PinmuxYAML
import yaml

data = yaml.safe_load(open('yaml_in/pinmux.yaml'))
result = PinmuxYAML(**data)

# ✅ No warnings
# ✅ Validation passes
# ✅ Data accessible via register_name

print(result.pins[0].functions[0].mux.register_name)
# Output: PINMMR0
```

---

## Summary

- ✅ Warning eliminated
- ✅ YAML structure unchanged
- ✅ Full backward compatibility
- ✅ Clean validation output
- ✅ JSON schemas regenerated

**Result**: Clean startup with no warnings or errors!

---

**Status**: ✅ Complete
