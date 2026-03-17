#!/usr/bin/env python3
"""Fix irq.yaml to match schema expectations."""

import sys
from pathlib import Path

def fix_irq_yaml(input_file: Path):
    """Fix irq.yaml structure and data."""

    print(f"Reading {input_file}...")
    lines = input_file.read_text(encoding='utf-8').splitlines()

    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fix interrupt_controller - skip the nested structure
        if line.strip() == 'interrupt_controller:':
            fixed_lines.append('interrupt_controller: VIM')
            # Skip lines until we hit 'irqs:'
            i += 1
            while i < len(lines) and lines[i].strip() != 'irqs:':
                i += 1
            continue

        # Fix id -> number
        if line.startswith('  id:'):
            line = line.replace('  id:', '  number:')

        # Fix RESERVED names to be unique
        if '- name: RESERVED' in line and line.strip() == '- name: RESERVED':
            # Look ahead for the number field
            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j]
                if 'number:' in next_line:
                    try:
                        number = next_line.split(':')[1].strip()
                        line = f'- name: RESERVED_{number}'
                        print(f"  Fixed RESERVED -> RESERVED_{number}")
                        break
                    except:
                        pass

        fixed_lines.append(line)
        i += 1

    # Write fixed content
    print(f"Writing fixed content to {input_file}...")
    input_file.write_text('\n'.join(fixed_lines) + '\n', encoding='utf-8')
    print("Done!")

if __name__ == '__main__':
    irq_file = Path('yaml_in/irq.yaml')
    fix_irq_yaml(irq_file)
