#!/usr/bin/env python3
"""
Generate JSON Schema files from Pydantic models.

This script generates JSON Schema (Draft 2020-12) files from the Pydantic
models defined in modules/yaml/schemas.py. These JSON schemas are used for:
- IDE autocomplete and validation
- Documentation
- External tooling

The Pydantic models remain the authoritative source of truth for runtime validation.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.yaml.schemas import (
    SocYAML,
    RegsYAML,
    BusYAML,
    IrqYAML,
    PinmuxYAML,
    MemmapYAML,
    BoardYAML,
)


def generate_json_schema(model_class, output_path: Path):
    """
    Generate JSON Schema from Pydantic model.

    Args:
        model_class: Pydantic BaseModel class
        output_path: Path to write JSON schema file
    """
    # Generate JSON Schema from Pydantic model
    schema = model_class.model_json_schema(
        mode='validation',
        by_alias=True,
        ref_template='#/$defs/{model}'
    )

    # Add metadata
    schema['$id'] = output_path.name
    schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'

    # Add generation comment
    schema['$comment'] = (
        'Auto-generated from Pydantic models in modules/yaml/schemas.py. '
        'DO NOT EDIT MANUALLY - changes will be overwritten. '
        'Modify the Pydantic models instead and regenerate.'
    )

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"[OK] Generated {output_path.name}")
    return schema


def main():
    """Generate all JSON schemas."""
    # Define schemas to generate
    schemas = [
        (SocYAML, 'soc.schema.json'),
        (RegsYAML, 'regs.schema.json'),
        (BusYAML, 'bus.schema.json'),
        (IrqYAML, 'irq.schema.json'),
        (PinmuxYAML, 'pinmux.schema.json'),
        (MemmapYAML, 'memmap.schema.json'),
        (BoardYAML, 'board.schema.json'),
    ]

    # Output directory
    output_dir = Path(__file__).parent.parent / 'yaml_schemas'

    print(f"Generating JSON schemas from Pydantic models...")
    print(f"Output directory: {output_dir}")
    print()

    # Generate each schema
    for model_class, filename in schemas:
        output_path = output_dir / filename
        try:
            schema = generate_json_schema(model_class, output_path)

            # Print summary
            properties = schema.get('properties', {})
            print(f"  - {len(properties)} top-level properties")

        except Exception as e:
            print(f"[ERROR] Failed to generate {filename}: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 70)
    print("JSON Schema Generation Complete!")
    print("=" * 70)
    print()
    print("These schemas are auto-generated for IDE support and documentation.")
    print("The Pydantic models in modules/yaml/schemas.py are the authoritative source.")
    print()
    print("To use in VSCode:")
    print("  1. Install 'YAML' extension by Red Hat")
    print("  2. Add to .vscode/settings.json:")
    print('     "yaml.schemas": {')
    print('       "yaml_schemas/bus.schema.json": "yaml_in/bus.yaml",')
    print('       "yaml_schemas/soc.schema.json": "yaml_in/soc.yaml",')
    print('       ...')
    print('     }')


if __name__ == '__main__':
    main()
