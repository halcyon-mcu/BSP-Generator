# JSON Schema Auto-Generation Implementation

**Date**: 2026-02-24
**Status**: ✅ Complete

---

## Summary

Implemented **automatic JSON Schema generation from Pydantic models** to maintain a single source of truth for validation while providing IDE support.

---

## Problem Statement

The BSP Generator had **two validation systems**:

1. **Pydantic models** (`modules/yaml/schemas.py`) - Active, used by main.py
2. **JSON Schema files** (`yaml_schemas/*.schema.yaml`) - Inactive, manually maintained

This created:
- ❌ Maintenance burden (two schemas to keep in sync)
- ❌ Risk of drift (schemas becoming inconsistent)
- ❌ Confusion about which is authoritative

**Example Mismatch**:
- Pydantic: `freq_hz: Optional[int]` (optional)
- JSON Schema: `required: [name, type, freq_hz]` (required)

---

## Solution

**Single Source of Truth**: Pydantic models are authoritative

**Auto-Generation**: JSON schemas generated from Pydantic for IDE support

```
Pydantic Models          JSON Schemas
(authoritative)      →   (generated)
     ↓                        ↓
Runtime Validation      IDE Support
```

---

## Implementation

### 1. Created Generation Script

**File**: [scripts/generate_json_schemas.py](scripts/generate_json_schemas.py)

**Features**:
- Generates JSON Schema (Draft 2020-12) from Pydantic models
- Adds metadata (`$id`, `$schema`, `$comment`)
- Includes warning: "DO NOT EDIT MANUALLY"
- Outputs to `yaml_schemas/*.schema.json`

**Usage**:
```bash
cd app
python scripts/generate_json_schemas.py
```

**Output**:
```
[OK] Generated soc.schema.json
[OK] Generated regs.schema.json
[OK] Generated bus.schema.json
[OK] Generated irq.schema.json
[OK] Generated pinmux.schema.json
[OK] Generated memmap.schema.json
[OK] Generated board.schema.json
```

---

### 2. Generated JSON Schemas

All 7 schemas successfully generated in `yaml_schemas/` directory:

| Schema | Pydantic Model | Generated JSON | Size |
|--------|----------------|----------------|------|
| SoC | `SocYAML` | `soc.schema.json` | 3 properties |
| Registers | `RegsYAML` | `regs.schema.json` | 1 property |
| Bus | `BusYAML` | `bus.schema.json` | 2 properties |
| IRQ | `IrqYAML` | `irq.schema.json` | 2 properties |
| Pinmux | `PinmuxYAML` | `pinmux.schema.json` | 1 property |
| Memory Map | `MemmapYAML` | `memmap.schema.json` | 1 property |
| Board | `BoardYAML` | `board.schema.json` | 2 properties |

---

### 3. Verified Consistency

**Before (manual JSON Schema)**:
```yaml
# bus.schema.yaml
sources:
  items:
    required: [name, type, freq_hz]  # freq_hz REQUIRED
```

**After (auto-generated from Pydantic)**:
```json
// bus.schema.json
"ClockSource": {
  "required": ["name"],  // freq_hz NOT required
  "properties": {
    "freq_hz": {
      "anyOf": [
        {"type": "integer", "exclusiveMinimum": 0},
        {"type": "null"}
      ],
      "default": null
    }
  }
}
```

✅ **Consistency achieved** - JSON schema now matches Pydantic model!

---

### 4. Documentation

Created comprehensive documentation:

- **[yaml_schemas/README.md](yaml_schemas/README.md)**
  - Explains auto-generation approach
  - VSCode configuration instructions
  - Schema regeneration steps
  - Source of truth clarification

- **[yaml_schemas/DEPRECATED_YAML_SCHEMAS.txt](yaml_schemas/DEPRECATED_YAML_SCHEMAS.txt)**
  - Marks old `*.schema.yaml` files as deprecated
  - Explains current validation system
  - Migration notes

- **[VALIDATION_APPROACH_ANALYSIS.md](VALIDATION_APPROACH_ANALYSIS.md)**
  - Detailed comparison of JSON Schema vs Pydantic
  - Feature matrix and pros/cons
  - Recommendation and rationale

---

## Benefits

### ✅ Single Source of Truth
- Pydantic models in `modules/yaml/schemas.py` are authoritative
- No risk of drift between validation systems
- Changes made once, propagated automatically

### ✅ Reduced Maintenance
- No manual JSON schema editing
- Schema changes only in Python code
- Auto-regenerate with one command

### ✅ IDE Support Maintained
- VSCode can still validate YAML files in real-time
- Autocomplete works with generated schemas
- No loss of developer experience

### ✅ Type Safety Preserved
- Pydantic provides typed objects throughout code
- IDE autocomplete for Python code
- Runtime validation with detailed errors

### ✅ Guaranteed Consistency
- JSON schemas always match Pydantic
- No "which version is correct?" questions
- Regenerate after every Pydantic change

---

## Usage

### For Developers

**Modifying schemas**:
1. Edit Pydantic models in `modules/yaml/schemas.py`
2. Run tests: `pytest tests/test_yaml_schemas.py`
3. Regenerate JSON schemas: `python scripts/generate_json_schemas.py`
4. Commit both `.py` and `.json` changes

**Using in VSCode**:
1. Install "YAML" extension by Red Hat
2. Configure `.vscode/settings.json` (see yaml_schemas/README.md)
3. Get real-time YAML validation while editing

---

## Technical Details

### Pydantic → JSON Schema Mapping

| Pydantic | JSON Schema |
|----------|-------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `Optional[int]` | `{"anyOf": [{"type": "integer"}, {"type": "null"}], "default": null}` |
| `Field(..., gt=0)` | `{"exclusiveMinimum": 0}` |
| `List[Model]` | `{"type": "array", "items": {"$ref": "#/$defs/Model"}}` |
| `@field_validator` | Not translated (Python-only logic) |

**Note**: Custom validators (like duplicate detection) are Pydantic-only and don't appear in JSON schemas. This is expected - JSON Schema handles structure, Pydantic handles business logic.

---

## Files Modified/Created

### Created
- ✅ `scripts/generate_json_schemas.py` - Generation script
- ✅ `yaml_schemas/README.md` - Documentation
- ✅ `yaml_schemas/DEPRECATED_YAML_SCHEMAS.txt` - Deprecation notice
- ✅ `VALIDATION_APPROACH_ANALYSIS.md` - Technical analysis
- ✅ `SCHEMA_AUTOGENERATION_SUMMARY.md` - This file

### Generated
- ✅ `yaml_schemas/soc.schema.json`
- ✅ `yaml_schemas/regs.schema.json`
- ✅ `yaml_schemas/bus.schema.json` (freq_hz now optional!)
- ✅ `yaml_schemas/irq.schema.json`
- ✅ `yaml_schemas/pinmux.schema.json`
- ✅ `yaml_schemas/memmap.schema.json`
- ✅ `yaml_schemas/board.schema.json`

### Deprecated (kept for reference)
- ⚠️ `yaml_schemas/*.schema.yaml` (old manual schemas)

---

## Validation

### Test Results

**Pydantic Validation** (runtime):
```bash
$ pytest tests/test_yaml_schemas.py -v
==================== 18 passed ====================
```

**JSON Schema Validation** (generated):
```bash
$ python scripts/generate_json_schemas.py
[OK] Generated soc.schema.json
[OK] Generated regs.schema.json
[OK] Generated bus.schema.json
[OK] Generated irq.schema.json
[OK] Generated pinmux.schema.json
[OK] Generated memmap.schema.json
[OK] Generated board.schema.json
```

**Runtime Validation** (bus.yaml with optional freq_hz):
```python
>>> from modules.yaml.schemas import BusYAML
>>> import yaml
>>> data = yaml.safe_load(open('yaml_in/bus.yaml'))
>>> result = BusYAML(**data)
>>> print(f"Loaded {len(result.sources)} sources")
Loaded 3 sources
>>> [s.name + ": " + ("configurable" if s.freq_hz is None else f"{s.freq_hz}Hz") for s in result.sources]
['OSCIN: 16000000Hz', 'PLL1: configurable', 'PLL2: configurable']
```

✅ **All validation passing!**

---

## Comparison: Before vs After

### Before
```
Problem: Two validation systems
├── Pydantic (modules/yaml/schemas.py) ✅ Active
│   └── freq_hz: Optional[int]
└── JSON Schema (yaml_schemas/*.schema.yaml) ❌ Unused
    └── required: [name, type, freq_hz]

Issues:
- Inconsistent (freq_hz required vs optional)
- Maintenance burden (two schemas)
- Risk of drift
```

### After
```
Solution: Single source of truth
└── Pydantic (modules/yaml/schemas.py) ✅ Authoritative
    └── freq_hz: Optional[int]
    └── Auto-generates ↓
        └── JSON Schema (yaml_schemas/*.schema.json) ✅ Generated
            └── "anyOf": [int, null]

Benefits:
- Consistent (both match)
- Single source of truth
- No maintenance burden
- IDE support maintained
```

---

## Future Enhancements

1. **CI/CD Integration**
   - Add pre-commit hook to auto-regenerate schemas
   - Fail CI if JSON schemas are out of sync with Pydantic

2. **VSCode Workspace Settings**
   - Add `.vscode/settings.json` with YAML schema mappings
   - Configure for optimal developer experience

3. **Schema Documentation Site**
   - Generate HTML docs from JSON schemas
   - Publish schema reference guide

4. **Schema Versioning**
   - Track schema version in generated files
   - Alert on breaking changes

---

## Conclusion

Successfully implemented automatic JSON Schema generation from Pydantic models:

- ✅ Single source of truth (Pydantic)
- ✅ IDE support maintained (JSON schemas)
- ✅ Consistency guaranteed (auto-generated)
- ✅ Maintenance simplified (one place to edit)
- ✅ freq_hz now correctly optional in both systems

**Recommendation**: Run `python scripts/generate_json_schemas.py` after any schema changes to keep JSON schemas in sync.

---

**Status**: ✅ Complete and validated
**Date**: 2026-02-24
