# YAML Schemas Directory

This directory contains **auto-generated JSON Schema files** for IDE support and documentation.

## ⚠️ Important

**DO NOT EDIT THESE FILES MANUALLY**

These JSON schemas are automatically generated from the Pydantic models in `modules/yaml/schemas.py`. Any manual changes will be overwritten when the schemas are regenerated.

## Source of Truth

The **authoritative schemas** are the Pydantic models in:
- `modules/yaml/schemas.py`

These Pydantic models provide:
- Runtime validation in `main.py`
- Type safety throughout the codebase
- Custom validation logic
- Comprehensive unit tests

## JSON Schemas Purpose

The JSON Schema files in this directory serve these purposes:

1. **IDE Support** - Enable real-time validation and autocomplete in VSCode/IntelliJ
2. **Documentation** - Human-readable schema documentation
3. **External Tooling** - Allow non-Python tools to validate YAML files
4. **CI/CD** - Enable pre-commit hooks and validation without Python

## Regenerating Schemas

To regenerate all JSON schemas from the Pydantic models:

```bash
cd app
python scripts/generate_json_schemas.py
```

This should be run whenever you modify the Pydantic models in `modules/yaml/schemas.py`.

## Using with VSCode

To enable IDE validation while editing YAML files:

1. **Install Extension**: "YAML" by Red Hat

2. **Configure** `.vscode/settings.json`:
   ```json
   {
     "yaml.schemas": {
       "yaml_schemas/bus.schema.json": "yaml_in/bus.yaml",
       "yaml_schemas/soc.schema.json": "yaml_in/soc.yaml",
       "yaml_schemas/regs.schema.json": "yaml_in/regs.yaml",
       "yaml_schemas/irq.schema.json": "yaml_in/irq.yaml",
       "yaml_schemas/pinmux.schema.json": "yaml_in/pinmux.yaml",
       "yaml_schemas/memmap.schema.json": "yaml_in/memmap.yaml",
       "yaml_schemas/board.schema.json": "yaml_in/board.yaml"
     }
   }
   ```

3. **Reload VSCode** - YAML files will now show validation errors and autocomplete

## Schema Files

| File | Generated From | Purpose |
|------|----------------|---------|
| `bus.schema.json` | `BusYAML` | Clock sources and domains |
| `soc.schema.json` | `SocYAML` | SoC and peripheral definitions |
| `regs.schema.json` | `RegsYAML` | Register definitions |
| `irq.schema.json` | `IrqYAML` | Interrupt definitions |
| `pinmux.schema.json` | `PinmuxYAML` | Pin multiplexing |
| `memmap.schema.json` | `MemmapYAML` | Memory map |
| `board.schema.json` | `BoardYAML` | Board configuration |

## Legacy Files

The `*.schema.yaml` files in this directory are legacy JSON Schema files that were manually created. They are kept for reference but are **not used** by the application.

**Active validation**: Pydantic models in `modules/yaml/schemas.py`
**Generated for IDE**: `*.schema.json` files (this directory)
**Deprecated**: `*.schema.yaml` files (manual, not maintained)

---

**Last Generated**: Run `python scripts/generate_json_schemas.py` to update
