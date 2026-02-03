#!/usr/bin/env python3
"""
yaml_formatter.py

Utilities for formatting register YAML files to match the project's style:
- Inline/flow style for bitfield definitions
- Consistent indentation and spacing
- Human-readable output
"""

from __future__ import annotations

from io import StringIO
from typing import Any, Dict, List

import yaml


class InlineFieldDumper(yaml.SafeDumper):
    """
    Custom YAML dumper that formats bitfield arrays in inline/flow style.

    This makes register definitions much more readable:

    Good (inline):
      fields:
        - { name: RESET, bit: 0, access: RW, desc: "Reset bit" }

    Bad (block):
      fields:
        - name: RESET
          bit: 0
          access: RW
          desc: "Reset bit"
    """
    pass


def _represent_field_inline(dumper, data):
    """Represent field dictionaries in inline/flow style."""
    # Force flow style for field objects
    return dumper.represent_mapping('tag:yaml.org,2002:map', data, flow_style=True)


def _represent_list(dumper, data):
    """
    Represent lists intelligently:
    - If list contains dicts with 'name' key (likely fields), use block style for the list
      but each item will be inline (handled by _represent_field_inline)
    - Otherwise, use default representation
    """
    # Check if this is a fields array (list of dicts with 'name' key)
    if data and isinstance(data[0], dict) and 'name' in data[0]:
        # This is likely a fields array - use block style for the list itself
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)

    # Default list representation
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)


# Register custom representers
InlineFieldDumper.add_representer(dict, _represent_field_inline)
InlineFieldDumper.add_representer(list, _represent_list)


def format_regs_yaml(yaml_data: Dict[str, Any]) -> str:
    """
    Format register YAML data with inline field definitions.

    Args:
        yaml_data: Parsed YAML data (dict)

    Returns:
        Formatted YAML string with inline fields
    """
    # First pass: Use custom dumper for fields
    output = StringIO()

    # Dump with our custom formatter
    yaml.dump(
        yaml_data,
        output,
        Dumper=InlineFieldDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,  # Wider lines for inline fields
        indent=2,
    )

    result = output.getvalue()

    # Post-process to ensure consistent formatting
    lines = result.split('\n')
    formatted_lines = []

    in_fields_section = False

    for line in lines:
        # Detect fields section
        if line.strip().startswith('fields:'):
            in_fields_section = True
            formatted_lines.append(line)
            continue

        # Exit fields section when we hit a non-indented line or another register key
        if in_fields_section and line and not line.startswith('    '):
            in_fields_section = False

        # If we're in a fields section and line starts with '- ', ensure it's inline
        if in_fields_section and line.strip().startswith('- ') and '{' not in line:
            # This might be a block-style field that needs to be inline
            # Skip it - the custom dumper should have handled this
            pass

        formatted_lines.append(line)

    return '\n'.join(formatted_lines)


def convert_fields_to_inline_style(yaml_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert field definitions from block style to inline style in-place.

    This modifies the yaml_data dict to ensure all field arrays use
    inline style when dumped.

    Args:
        yaml_data: Parsed YAML data (dict)

    Returns:
        Modified yaml_data (same object, modified in-place)
    """
    if 'peripherals' not in yaml_data:
        return yaml_data

    for periph_name, periph_data in yaml_data['peripherals'].items():
        if 'registers' not in periph_data:
            continue

        for reg_name, reg_data in periph_data['registers'].items():
            if 'fields' not in reg_data:
                continue

            # Fields are already a list of dicts, but we mark them
            # for inline formatting by adding a custom tag
            # (This is handled by our custom dumper)
            fields = reg_data['fields']

            # Ensure each field is a dict (should already be)
            if isinstance(fields, list):
                for field in fields:
                    if isinstance(field, dict):
                        # Field is already a dict, will be formatted inline
                        # by our custom dumper
                        pass

    return yaml_data


def format_regs_yaml_simple(yaml_content: str) -> str:
    """
    Simple formatter that parses YAML and re-dumps with inline fields.

    Args:
        yaml_content: YAML string (possibly with block-style fields)

    Returns:
        Formatted YAML string with inline fields
    """
    try:
        # Parse YAML
        data = yaml.safe_load(yaml_content)

        # Convert to inline style
        data = convert_fields_to_inline_style(data)

        # Re-dump with inline formatter
        return format_regs_yaml(data)

    except Exception as e:
        # If formatting fails, return original
        print(f"Warning: YAML formatting failed: {e}")
        return yaml_content


def format_field_inline(field: Dict[str, Any]) -> str:
    """
    Manually format a single field dict as an inline YAML string.

    Args:
        field: Field dictionary

    Returns:
        Inline YAML string like: { name: FOO, bit: 0, access: RW, desc: "..." }
    """
    parts = []

    # Order: name, bit/msb/lsb, access, reset, desc, other fields
    field_order = ['name', 'bit', 'msb', 'lsb', 'access', 'reset', 'desc']

    for key in field_order:
        if key in field:
            value = field[key]
            if isinstance(value, str):
                # Escape quotes in strings
                value_str = value.replace('"', '\\"')
                parts.append(f'{key}: "{value_str}"')
            else:
                parts.append(f'{key}: {value}')

    # Add any remaining fields not in the standard order
    for key, value in field.items():
        if key not in field_order:
            if isinstance(value, str):
                value_str = value.replace('"', '\\"')
                parts.append(f'{key}: "{value_str}"')
            else:
                parts.append(f'{key}: {value}')

    return '{ ' + ', '.join(parts) + ' }'


def format_regs_yaml_manual(yaml_data: Dict[str, Any]) -> str:
    """
    Manually format register YAML with inline fields.

    This builds the YAML string line by line for maximum control
    over formatting.

    Args:
        yaml_data: Parsed YAML data

    Returns:
        Formatted YAML string
    """
    lines = []

    # Header
    lines.append(f"ir_schema_version: \"{yaml_data.get('ir_schema_version', '1.1.0')}\"")
    lines.append("")

    # Provenance (if exists)
    if 'provenance' in yaml_data:
        lines.append("provenance:")
        prov = yaml_data['provenance']
        for key, value in prov.items():
            if isinstance(value, str):
                lines.append(f'  {key}: "{value}"')
            else:
                lines.append(f'  {key}: {value}')
        lines.append("")

    # Peripherals
    lines.append("peripherals:")

    peripherals = yaml_data.get('peripherals', {})
    for periph_name, periph_data in peripherals.items():
        lines.append(f"  {periph_name}:")

        # Base address
        if 'base_address' in periph_data:
            lines.append(f"    base_address: \"{periph_data['base_address']}\"")

        # Description
        if 'desc' in periph_data:
            desc = periph_data['desc'].replace('"', '\\"')
            lines.append(f"    desc: \"{desc}\"")

        # Registers
        if 'registers' in periph_data:
            lines.append("    registers:")

            for reg_name, reg_data in periph_data['registers'].items():
                lines.append(f"      {reg_name}:")

                # Offset
                if 'offset' in reg_data:
                    lines.append(f"        offset: \"{reg_data['offset']}\"")

                # Access
                if 'access' in reg_data:
                    lines.append(f"        access: {reg_data['access']}")

                # Reset
                if 'reset' in reg_data:
                    lines.append(f"        reset: \"{reg_data['reset']}\"")

                # Description
                if 'desc' in reg_data:
                    desc = reg_data['desc'].replace('"', '\\"')
                    lines.append(f"        desc: \"{desc}\"")

                # Fields (inline!)
                if 'fields' in reg_data and reg_data['fields']:
                    lines.append("        fields:")
                    for field in reg_data['fields']:
                        field_str = format_field_inline(field)
                        lines.append(f"          - {field_str}")

    return '\n'.join(lines)


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python yaml_formatter.py <input.yaml> [output.yaml]")
        print("  Reformats register YAML to use inline field style")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    # Load YAML
    with open(input_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Format
    formatted = format_regs_yaml_manual(data)

    # Output
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted)
        print(f"Formatted YAML written to: {output_file}")
    else:
        print(formatted)
