#!/usr/bin/env python3
"""
inline_yaml_format.py

Format YAML files to use inline/flow style where appropriate for compactness.

Usage:
    python inline_yaml_format.py --yaml-dir yaml_in_transformed
    python inline_yaml_format.py --yaml-dir yaml_in_transformed --files regs.yaml soc.yaml
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List
import sys
import re


def format_field_inline(field: Dict) -> str:
    """Format a register field as an inline dictionary."""
    parts = []

    # Always include name first
    if 'name' in field:
        parts.append(f"name: \"{field['name']}\"")

    # Add bit/msb/lsb
    if 'bit' in field:
        parts.append(f"bit: {field['bit']}")
    elif 'msb' in field and 'lsb' in field:
        parts.append(f"msb: {field['msb']}, lsb: {field['lsb']}")
    elif 'msb' in field:
        parts.append(f"msb: {field['msb']}")
    elif 'lsb' in field:
        parts.append(f"lsb: {field['lsb']}")

    # Add access if present
    if 'access' in field:
        parts.append(f"access: {field['access']}")

    # Add reset if present
    if 'reset' in field:
        parts.append(f"reset: \"{field['reset']}\"")

    # Add desc last (may be long)
    if 'desc' in field:
        desc = field['desc']
        # Escape quotes in description
        desc = desc.replace('"', '\\"')
        parts.append(f"desc: \"{desc}\"")

    return "{ " + ", ".join(parts) + " }"


def format_init_step_inline(step: Dict) -> str:
    """Format an init sequence step as inline."""
    parts = []
    if 'reg' in step:
        parts.append(f"reg: \"{step['reg']}\"")
    if 'op' in step:
        parts.append(f"op: {step['op']}")
    if 'value' in step:
        parts.append(f"value: \"{step['value']}\"")
    if 'field' in step:
        parts.append(f"field: \"{step['field']}\"")
    if 'delay_us' in step:
        parts.append(f"delay_us: {step['delay_us']}")
    return "{ " + ", ".join(parts) + " }"


def format_x_source_inline(source: Dict, indent: int = 0) -> str:
    """Format x-source metadata as inline if simple enough."""
    if not isinstance(source, dict):
        return None

    # Get pages
    pages = source.get('pages', [])

    # Only inline if pages list is reasonable length
    if len(pages) > 10:
        return None

    parts = []
    if 'pdf' in source:
        pdf_name = source['pdf']
        parts.append(f"pdf: \"{pdf_name}\"")

    if pages:
        pages_str = ", ".join(str(p) for p in pages)
        parts.append(f"pages: [{pages_str}]")

    if 'confidence' in source:
        parts.append(f"confidence: {source['confidence']}")

    if 'table' in source:
        parts.append(f"table: \"{source['table']}\"")

    return "{ " + ", ".join(parts) + " }"


def format_soc_yaml(data: Dict) -> str:
    """Format soc.yaml with inline init sequences and x-source."""
    lines = []

    # Header
    lines.append(f"ir_schema_version: {data['ir_schema_version']}")
    lines.append(f"chip: {data['chip']}")
    lines.append(f"vendor: {data['vendor']}")
    lines.append(f"family: {data['family']}")
    if 'revision' in data:
        lines.append(f"revision: {data['revision']}")
    lines.append("")

    # SOC section
    lines.append("soc:")

    # CPU section
    if 'cpu' in data.get('soc', {}):
        cpu = data['soc']['cpu']
        lines.append("  cpu:")
        lines.append("    cores:")
        for core in cpu.get('cores', []):
            lines.append(f"    - name: {core['name']}")
            lines.append(f"      arch: {core['arch']}")
            lines.append(f"      endianness: {core['endianness']}")
            lines.append(f"      word_size_bits: {core['word_size_bits']}")
            if 'fpu' in core:
                lines.append(f"      fpu: {core['fpu']}")
        lines.append("")

    # Peripherals
    lines.append("  peripherals:")
    for periph in data.get('soc', {}).get('peripherals', []):
        lines.append(f"  - name: {periph['name']}")
        lines.append(f"    type: {periph['type']}")
        lines.append(f"    instance: {periph['instance']}")
        if 'regs_ref' in periph:
            lines.append(f"    regs_ref: {periph['regs_ref']}")
        if 'clock_ref' in periph:
            lines.append(f"    clock_ref: {periph['clock_ref']}")
        if 'irq_ref' in periph:
            lines.append(f"    irq_ref: {periph['irq_ref']}")

        # x-ext section (with inline formatting)
        if 'x-ext' in periph:
            x_ext = periph['x-ext']
            lines.append("    x-ext:")

            # Init sequences (inline)
            if 'init' in x_ext:
                lines.append("      init:")
                for step in x_ext['init']:
                    lines.append(f"        - {format_init_step_inline(step)}")

            # DMA refs
            if 'dma_refs' in x_ext:
                lines.append("      dma_refs:")
                for dma_ref in x_ext['dma_refs']:
                    if dma_ref is None:
                        lines.append("      - null")
                        continue
                    lines.append("      -")
                    if 'channel' in dma_ref:
                        if dma_ref['channel'] is None:
                            lines.append("        channel: null")
                        else:
                            lines.append(f"        channel: {dma_ref['channel']}")
                    if 'description' in dma_ref:
                        desc = dma_ref['description']
                        if len(desc) > 80:
                            lines.append("        description: >-")
                            lines.append(f"          {desc}")
                        else:
                            lines.append(f"        description: {desc}")
                    if 'trigger' in dma_ref:
                        lines.append(f"        trigger: {dma_ref['trigger']}")
                    if 'control_register' in dma_ref:
                        lines.append(f"        control_register: {dma_ref['control_register']}")

                    # x-source inline
                    if 'x-source' in dma_ref:
                        x_source_inline = format_x_source_inline(dma_ref['x-source'])
                        if x_source_inline:
                            lines.append(f"        x-source: {x_source_inline}")
                        else:
                            # Fall back to block format
                            lines.append("        x-source:")
                            src = dma_ref['x-source']
                            if 'pdf' in src:
                                lines.append(f"          pdf: {src['pdf']}")
                            if 'pages' in src:
                                pages_str = ", ".join(str(p) for p in src['pages'])
                                lines.append(f"          pages: [{pages_str}]")
                            if 'confidence' in src:
                                lines.append(f"          confidence: {src['confidence']}")

                    if 'x-note' in dma_ref:
                        note = dma_ref['x-note']
                        if len(note) > 80:
                            lines.append("        x-note: >-")
                            lines.append(f"          {note}")
                        else:
                            lines.append(f"        x-note: {note}")

            # Other x-ext fields
            if 'base_address' in x_ext:
                base_addr = x_ext['base_address']
                if isinstance(base_addr, dict):
                    # Complex base_address (with size, x-source, etc.)
                    lines.append("      base_address:")
                    for key, value in base_addr.items():
                        if key == 'x-source' and isinstance(value, dict):
                            x_source_inline = format_x_source_inline(value)
                            if x_source_inline:
                                lines.append(f"        {key}: {x_source_inline}")
                            else:
                                lines.append(f"        {key}:")
                                for k2, v2 in value.items():
                                    if isinstance(v2, list):
                                        v2_str = ", ".join(str(x) for x in v2)
                                        lines.append(f"          {k2}: [{v2_str}]")
                                    else:
                                        lines.append(f"          {k2}: {v2}")
                        else:
                            if isinstance(value, str):
                                lines.append(f"        {key}: '{value}'")
                            else:
                                lines.append(f"        {key}: {value}")
                else:
                    # Simple base_address string
                    lines.append(f"      base_address: '{base_addr}'")

            if 'features' in x_ext:
                lines.append("      features:")
                for feature in x_ext['features']:
                    lines.append(f"        - {feature}")

            if 'clock_config' in x_ext:
                clock_cfg = x_ext['clock_config']
                lines.append("      clock_config:")
                for key, value in clock_cfg.items():
                    if isinstance(value, str):
                        lines.append(f"        {key}: \"{value}\"")
                    else:
                        lines.append(f"        {key}: {value}")

            if 'interrupts' in x_ext:
                interrupts = x_ext['interrupts']
                lines.append("      interrupts:")
                for key, value in interrupts.items():
                    if isinstance(value, dict):
                        lines.append(f"        {key}:")
                        for k2, v2 in value.items():
                            lines.append(f"          {k2}: {v2}")
                    else:
                        lines.append(f"        {key}: {value}")

            # x-source at peripheral level (inline if possible)
            if 'x-source' in x_ext:
                x_source_inline = format_x_source_inline(x_ext['x-source'])
                if x_source_inline:
                    lines.append(f"      x-source: {x_source_inline}")
                else:
                    # Fall back to block format
                    lines.append("      x-source:")
                    src = x_ext['x-source']
                    if 'pdf' in src:
                        lines.append(f"        pdf: {src['pdf']}")
                    if 'pages' in src:
                        pages_str = ", ".join(str(p) for p in src['pages'])
                        lines.append(f"        pages: [{pages_str}]")
                    if 'confidence' in src:
                        lines.append(f"        confidence: {src['confidence']}")

        lines.append("")  # Blank line between peripherals

    return '\n'.join(lines)


def format_regs_yaml(data: Dict) -> str:
    """Format regs.yaml with inline style for fields."""
    lines = []

    # Header
    lines.append(f"ir_schema_version: {data['ir_schema_version']}")
    lines.append("")
    lines.append("peripherals:")

    # Process each peripheral
    for periph_name, periph_data in data.get('peripherals', {}).items():
        lines.append(f"  {periph_name}:")

        if 'base_address' in periph_data:
            lines.append(f"    base_address: '{periph_data['base_address']}'")

        if 'desc' in periph_data:
            desc = periph_data['desc']
            if desc:
                lines.append(f"    desc: {yaml.dump(desc, default_style='\"').strip()}")
            else:
                lines.append(f"    desc: ''")

        # Registers
        lines.append("    registers:")
        for reg_name, reg_data in periph_data.get('registers', {}).items():
            lines.append(f"      {reg_name}:")

            if 'offset' in reg_data:
                lines.append(f"        offset: '{reg_data['offset']}'")
            if 'access' in reg_data:
                lines.append(f"        access: {reg_data['access']}")
            if 'reset' in reg_data:
                lines.append(f"        reset: '{reg_data['reset']}'")
            if 'desc' in reg_data:
                desc = reg_data['desc']
                if '\n' in str(desc) or len(str(desc)) > 80:
                    # Multi-line description
                    lines.append("        desc: >-")
                    for line in str(desc).split('\n'):
                        lines.append(f"          {line}")
                else:
                    lines.append(f"        desc: {yaml.dump(desc, default_style='\"').strip()}")

            # Fields - inline format
            if 'fields' in reg_data:
                lines.append("        fields:")
                for field in reg_data['fields']:
                    lines.append(f"          - {format_field_inline(field)}")

        lines.append("")  # Blank line between peripherals

    return '\n'.join(lines)


class InlineYAMLDumper(yaml.SafeDumper):
    """Custom YAML dumper that uses flow style for small dictionaries/lists."""

    def represent_dict(self, data):
        """Use flow style for small dicts (< 4 keys)."""
        if len(data) <= 3 and all(isinstance(v, (str, int, type(None))) for v in data.values()):
            return self.represent_mapping('tag:yaml.org,2002:map', data.items(), flow_style=True)
        return self.represent_mapping('tag:yaml.org,2002:map', data.items(), flow_style=False)

    def represent_list(self, data):
        """Use flow style for simple lists of scalars."""
        if len(data) <= 3 and all(isinstance(item, (str, int, type(None))) for item in data):
            return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)
        return self.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)


def format_pinmux_yaml(data: Dict) -> str:
    """Format pinmux.yaml with inline style for functions."""
    lines = []

    # Header
    if '$id' in data:
        lines.append(f"$id: {data['$id']}")
    if '$schema' in data:
        lines.append(f"$schema: {data['$schema']}")
    lines.append(f"ir_schema_version: \"{data['ir_schema_version']}\"")

    if 'package' in data:
        lines.append(f"package: \"{data['package']}\"")

    # Provenance
    if 'provenance' in data:
        lines.append("provenance:")
        prov = data['provenance']
        if 'source' in prov:
            lines.append(f"  source: \"{prov['source']}\"")
        if 'schematic_source' in prov:
            lines.append(f"  schematic_source: \"{prov['schematic_source']}\"")
        if 'table' in prov:
            lines.append(f"  table: \"{prov['table']}\"")

    # Pins (with inline functions)
    lines.append("pins:")
    for pin in data.get('pins', []):
        lines.append(f"  - package_pin: {pin['package_pin']}")
        lines.append(f"    name: \"{pin['name']}\"")

        if 'board' in pin:
            board = pin['board']
            lines.append(f"    board:")
            lines.append(f"      net: \"{board.get('net', '')}\"")

        lines.append(f"    functions:")
        for func in pin.get('functions', []):
            # Inline format for functions
            af = func.get('af', '0')
            signal = func.get('signal', '')
            mux = func.get('mux', {})
            register = mux.get('register', '')
            bit = mux.get('bit', 0)

            lines.append(f"      - {{ af: \"{af}\", signal: \"{signal}\", mux: {{ register: \"{register}\", bit: {bit} }} }}")

        lines.append("")  # Blank line between pins

    return '\n'.join(lines)


def format_irq_yaml_inline(data: Dict) -> str:
    """Format IRQ YAML with inline x-source where appropriate."""
    # Use custom dumper for most content
    output = yaml.dump(data, Dumper=InlineYAMLDumper, default_flow_style=False,
                      sort_keys=False, allow_unicode=True, width=120)
    return output


def format_yaml_file(filepath: Path):
    """Format a YAML file with inline style where appropriate."""

    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    filename = filepath.name

    # Special handling for different file types
    if filename == 'pinmux.yaml':
        formatted = format_pinmux_yaml(data)
    elif filename == 'regs.yaml':
        formatted = format_regs_yaml(data)
    elif filename == 'soc.yaml':
        formatted = format_soc_yaml(data)
    else:
        # Use default flow-style dumper for other files
        formatted = yaml.dump(data, default_flow_style=False, sort_keys=False,
                             allow_unicode=True, width=120)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(formatted)

    print(f"[OK] Formatted {filename}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Format YAML files with inline/flow style where appropriate"
    )
    parser.add_argument(
        '--yaml-dir',
        type=Path,
        default=Path('yaml_in_transformed'),
        help='Directory containing YAML files to format'
    )
    parser.add_argument(
        '--files',
        nargs='+',
        default=['regs.yaml', 'soc.yaml', 'pinmux.yaml'],
        help='Which files to format (default: regs.yaml, soc.yaml, pinmux.yaml)'
    )

    args = parser.parse_args()

    print("="*80)
    print("FORMATTING YAML FILES WITH INLINE STYLE")
    print("="*80)
    print(f"Directory: {args.yaml_dir}")
    print(f"Files: {', '.join(args.files)}")
    print()

    for filename in args.files:
        filepath = args.yaml_dir / filename
        if filepath.exists():
            format_yaml_file(filepath)
        else:
            print(f"[SKIP] {filename} not found")

    print()
    print("="*80)
    print("[OK] FORMATTING COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
