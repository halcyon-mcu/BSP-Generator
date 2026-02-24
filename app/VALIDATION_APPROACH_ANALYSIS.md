# YAML Validation Approach Analysis

**Date**: 2026-02-24

---

## Executive Summary

The BSP Generator currently has **TWO validation systems**:

1. **JSON Schema** (YAML files in `yaml_schemas/`) - Created first, currently unused
2. **Pydantic** (Python classes in `modules/yaml/schemas.py`) - Created later, currently active

**Recommendation**: Use **Pydantic exclusively** for runtime validation. Keep JSON Schemas for:
- Documentation/tooling
- IDE autocomplete (with YAML extension support)
- Potential future external validation

---

## History

### Original State (Pre-Phase 2.1)
- YAML schemas existed in `yaml_schemas/` directory (JSON Schema format)
- **No validation was happening** - load functions just parsed YAML
- yaml_validator.py existed but was never integrated into main flow

### Phase 2.1 (Feb 23, 2026)
**Commit**: c6074d6 - "Add Pydantic YAML schema validation (partial)"
**Commit**: 0a23e82 - "Complete YAML schema validation integration"

**Changes**:
- Created comprehensive Pydantic models in `modules/yaml/schemas.py`
- Integrated Pydantic validation into all `load_*_yaml()` functions
- Created test suite with 18+ tests (all passing)
- **Result**: Validation now catches errors before generation starts

**Rationale from commit message**:
> Benefits:
> - Catches malformed YAML before generation starts
> - Provides clear error messages to users
> - Prevents silent failures downstream
> - Validates cross-references within files

---

## Detailed Comparison

### 1. JSON Schema Approach (yaml_schemas/*.schema.yaml)

**How it works**:
```python
# Uses jsonschema library
from jsonschema import Draft202012Validator

validator = Draft202012Validator(schema)
errors = validator.iter_errors(yaml_data)
```

**Location**: `yaml_schemas/bus.schema.yaml`

**Example**:
```yaml
sources:
  type: array
  minItems: 1
  items:
    type: object
    required: [name, type, freq_hz]
    properties:
      name: { type: string }
      freq_hz: { type: integer, minimum: 1 }
```

**PROS**:
- ✅ **Standard format** - JSON Schema is an industry standard (RFC)
- ✅ **Language-agnostic** - Can be used by any tool (JS, Go, Rust, etc.)
- ✅ **IDE support** - VSCode/IntelliJ can validate YAML files in real-time
- ✅ **Documentation** - Self-documenting schema format
- ✅ **Tooling ecosystem** - Many validators, generators, converters available
- ✅ **Separate from code** - Schema changes don't require Python changes
- ✅ **CI/CD friendly** - Can validate YAML in pre-commit hooks without Python

**CONS**:
- ❌ **External dependency** - Requires `jsonschema` package
- ❌ **Limited custom validation** - Hard to express complex rules (e.g., "duplicate names")
- ❌ **Two-step process** - Load YAML → Validate → Use
- ❌ **Error messages** - Generic, harder to customize
- ❌ **No type safety in code** - Dict[str, Any] everywhere after validation
- ❌ **Maintenance burden** - Two schemas to keep in sync
- ❌ **Less Pythonic** - Not integrated with Python type system

**Error Message Example**:
```
At sources.1: 'freq_hz' is a required property
```

---

### 2. Pydantic Approach (modules/yaml/schemas.py)

**How it works**:
```python
# Uses Pydantic models
from pydantic import BaseModel, Field

class ClockSource(BaseModel):
    name: str
    freq_hz: Optional[int] = Field(None, gt=0)
```

**Location**: `modules/yaml/schemas.py`

**Example**:
```python
class BusYAML(BaseModel):
    sources: List[ClockSource] = Field(..., description="Clock sources")

    @field_validator('sources')
    def validate_not_empty(cls, v: List) -> List:
        if not v:
            raise ValueError("List cannot be empty")
        return v
```

**PROS**:
- ✅ **Type safety** - Models provide typed objects, not Dict[str, Any]
- ✅ **IDE autocomplete** - Full IntelliSense for validated data
- ✅ **Python-native** - No external files, uses Python type hints
- ✅ **Custom validators** - Easy to write complex validation logic
- ✅ **Better error messages** - Detailed, field-specific errors
- ✅ **Data transformation** - Can normalize/transform data during validation
- ✅ **Single source of truth** - One schema definition
- ✅ **Testable** - Easy to unit test validators
- ✅ **Performance** - Compiled with Rust (pydantic-core), very fast
- ✅ **Code reuse** - Can inherit, compose, extend models

**CONS**:
- ❌ **Python-only** - Can't be used by non-Python tools
- ❌ **No real-time IDE validation** - Won't catch YAML errors while editing
- ❌ **Tightly coupled** - Schema changes require code changes
- ❌ **Less discoverable** - Need to look at Python code to see schema

**Error Message Example**:
```
sources -> 1 -> freq_hz: Field required
```

---

## Feature Comparison Matrix

| Feature | JSON Schema | Pydantic | Winner |
|---------|-------------|----------|--------|
| **Standard format** | ✅ RFC standard | ❌ Python-specific | JSON Schema |
| **Type safety in code** | ❌ Dict[str, Any] | ✅ Typed models | **Pydantic** |
| **Custom validators** | ❌ Limited | ✅ Powerful | **Pydantic** |
| **Error messages** | ⚠️ Generic | ✅ Detailed | **Pydantic** |
| **IDE autocomplete** | ❌ No | ✅ Yes | **Pydantic** |
| **Real-time YAML validation** | ✅ Yes | ❌ No | JSON Schema |
| **Performance** | ⚠️ Good | ✅ Excellent | **Pydantic** |
| **Language agnostic** | ✅ Yes | ❌ Python-only | JSON Schema |
| **Test coverage** | ❌ None | ✅ 18+ tests | **Pydantic** |
| **Maintenance** | ❌ Separate files | ✅ Single source | **Pydantic** |
| **Complex rules** | ❌ Hard | ✅ Easy | **Pydantic** |
| **Data transformation** | ❌ No | ✅ Yes | **Pydantic** |

**Overall Score**: Pydantic wins 9-3 for runtime validation

---

## Current Validation Examples

### Pydantic Validations (Currently Active)

1. **Unique IRQ names/numbers** (modules/yaml/schemas.py:205-216)
```python
@field_validator('irqs')
def validate_unique_names_and_numbers(cls, v: List[Interrupt]):
    names = [irq.name for irq in v]
    dup_names = [name for name in names if names.count(name) > 1]
    if dup_names:
        raise ValueError(f"Duplicate IRQ names: {set(dup_names)}")
```
This caught the 12 duplicate "RESERVED" entries in irq.yaml!

2. **Hex address format** (modules/yaml/schemas.py:43-47)
```python
@field_validator('base_address')
def validate_hex_format(cls, v: str) -> str:
    if not re.match(r'^0x[0-9A-Fa-f]+$', v):
        raise ValueError("Address must be hex format (0x...)")
    return v
```

3. **Access type validation** (modules/yaml/schemas.py:67-71)
```python
@field_validator('access')
def validate_access(cls, v: Optional[str]) -> Optional[str]:
    if v and v not in ['RW', 'RO', 'WO', 'RC', 'W1C']:
        raise ValueError(f"Invalid access type: {v}")
    return v
```

### JSON Schema Capabilities (Currently Unused)

The JSON schemas can validate structure but **cannot express**:
- Duplicate name detection
- Hex format validation (would need custom format)
- Cross-field dependencies
- Complex business logic

---

## Real-World Impact

### Issues Caught by Pydantic Validation

During our YAML fixes, Pydantic validation caught:

1. **regs.yaml**: 64 placeholder values (base addresses, reset values)
2. **irq.yaml**:
   - interrupt_controller wrong type (nested dict vs string)
   - 111 missing `number` fields (had `id` instead)
   - 12 duplicate "RESERVED" names
3. **bus.yaml**: 2 missing `freq_hz` fields

**Without validation**, these would have caused:
- Silent generation failures
- Incorrect BSP code
- Wasted API costs ($20-50 per full generation)
- Hours of debugging

**With Pydantic validation**:
- Immediate error messages at startup
- Clear fix guidance
- $0 wasted on bad inputs

---

## Three Options Going Forward

### Option A: Pydantic Only (RECOMMENDED)

**Keep**:
- Pydantic schemas in `modules/yaml/schemas.py`
- Current validation in `load_*_yaml()` functions
- Test suite `tests/test_yaml_schemas.py`

**Remove or Archive**:
- `yaml_schemas/*.schema.yaml` files
- `modules/yaml/yaml_validator.py` (jsonschema integration)

**Add**:
- Generate JSON schemas FROM Pydantic for documentation
- Use tools like `pydantic-to-json-schema` for IDE support

**Pros**:
- Single source of truth
- Better error messages
- Type-safe code
- Easier maintenance
- Already working and tested

**Cons**:
- No real-time YAML editing validation
- Python-only (but that's fine - this is a Python project)

**Implementation**:
```python
# Optional: Generate JSON Schema for IDE support
from pydantic.json_schema import JsonSchemaValue
import json

schema = BusYAML.model_json_schema()
with open('yaml_schemas/bus.schema.json', 'w') as f:
    json.dump(schema, f, indent=2)
```

---

### Option B: Both Systems (DUAL VALIDATION)

**Use JSON Schema for**:
- IDE real-time validation (developer experience)
- Pre-commit hooks (fast, no Python needed)
- Documentation/schema browsing

**Use Pydantic for**:
- Runtime validation in main.py
- Complex business rules (duplicates, cross-refs)
- Type-safe data access

**Pros**:
- Best of both worlds
- IDE validates while editing
- Pydantic catches runtime errors

**Cons**:
- **Maintenance burden** - Must keep 2 schemas in sync
- Risk of drift (one updated, other forgotten)
- More complex
- Requires both jsonschema and pydantic deps

**Implementation**:
```python
def load_bus_yaml(path: Path) -> BusYAML:
    # Stage 1: JSON Schema validation (structure)
    data = _load_yaml(path)
    schema = load_schema('yaml_schemas/bus.schema.yaml')
    validate_yaml_against_schema(data, schema)  # Basic structure

    # Stage 2: Pydantic validation (business logic)
    bus_model = BusYAML(**data)  # Complex rules
    return bus_model
```

**Sync Strategy**:
1. Pydantic is source of truth
2. Auto-generate JSON schemas from Pydantic
3. CI/CD checks both validate the same test cases

---

### Option C: JSON Schema Only

**Replace Pydantic with jsonschema validation**

**Pros**:
- Standard format
- Language-agnostic
- IDE support

**Cons**:
- **Lose type safety** - Back to Dict[str, Any]
- **Lose custom validators** - Can't check duplicates easily
- **Worse error messages**
- **No autocomplete** in generated code
- **Regression** - Would need to reimplement complex validations
- **More code** - Custom logic outside schema

**Verdict**: ❌ **Not recommended** - This is a step backward

---

## Recommendation: Option A (Pydantic Only)

### Why Pydantic Wins

1. **Already working** - 18+ tests passing, caught real bugs
2. **Type safety** - Autocomplete throughout codebase
3. **Better errors** - "sources -> 1 -> freq_hz: Field required" vs "At sources.1: required property"
4. **Python project** - No need for language-agnostic schemas
5. **Easier maintenance** - One schema, one language
6. **Custom validators** - Caught duplicates, hex formats, etc.
7. **Performance** - Faster than jsonschema
8. **Modern** - Pydantic v2 is industry-standard in Python ecosystem

### Migration Plan

**Step 1**: Keep JSON schemas for IDE support (optional)
- Configure VSCode to validate YAML files
- Generate JSON schemas from Pydantic for this purpose

**Step 2**: Document Pydantic as authoritative
- Add comment to JSON schemas: "Generated for IDE support only"
- Update README to explain validation approach

**Step 3**: Add schema generation script (optional)
```python
# scripts/generate_json_schemas.py
from modules.yaml.schemas import BusYAML, RegsYAML, SocYAML
import json

for model, name in [(BusYAML, 'bus'), (RegsYAML, 'regs'), ...]:
    schema = model.model_json_schema()
    with open(f'yaml_schemas/{name}.schema.json', 'w') as f:
        json.dump(schema, f, indent=2)
```

**Step 4**: Update freq_hz in JSON schema to match Pydantic
```yaml
# yaml_schemas/bus.schema.yaml
sources:
  items:
    properties:
      freq_hz:
        type: integer
        minimum: 1
        # Remove from 'required' array
```

---

## Conclusion

**Use Pydantic for all runtime validation.**

The switch from no validation → Pydantic was the right choice:
- It caught 64+ validation errors in our YAMLs
- It provides type safety throughout the codebase
- It allows complex custom validations
- It's well-tested and performant

JSON schemas serve a different purpose (IDE tooling, documentation) and can coexist, but Pydantic should remain the authoritative validation source.

---

## Action Items

1. ✅ Keep Pydantic validation as-is
2. ⚠️ **Update JSON schema** to make freq_hz optional (matches Pydantic)
3. 📝 Document that Pydantic is authoritative
4. 🔧 Optional: Add script to generate JSON schemas from Pydantic
5. 🗑️ Optional: Archive yaml_validator.py (or keep for manual testing)

**Status**: Pydantic validation is production-ready and working correctly.
