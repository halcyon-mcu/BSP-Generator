#!/usr/bin/env python3
"""
add_vim_wake_registers.py

Add extracted VIM wake registers to VIM peripheral in regs.yaml

Usage:
    python add_vim_wake_registers.py
"""

import yaml
from pathlib import Path


def add_vim_wake_registers():
    """Add VIM wake registers to VIM peripheral in regs.yaml"""

    regs_file = Path('yaml_in_transformed/regs.yaml')
    vim_wake_file = Path('yaml_out/vim_wake_registers.yaml')

    # Load both files
    with open(regs_file, 'r', encoding='utf-8') as f:
        regs_data = yaml.safe_load(f)

    with open(vim_wake_file, 'r', encoding='utf-8') as f:
        vim_wake_data = yaml.safe_load(f)

    # Get VIM wake registers
    vim_wake_registers = vim_wake_data['peripherals']['VIM']['registers']

    print(f"Adding {len(vim_wake_registers)} VIM wake registers to VIM peripheral:")
    for reg_name in vim_wake_registers.keys():
        print(f"  - {reg_name}")

    # Add to VIM peripheral
    if 'VIM' in regs_data['peripherals']:
        vim_registers = regs_data['peripherals']['VIM']['registers']

        # Add VIM wake registers
        for reg_name, reg_data in vim_wake_registers.items():
            if reg_name not in vim_registers:
                vim_registers[reg_name] = reg_data
                print(f"  [OK] Added {reg_name}")
            else:
                print(f"  [SKIP] {reg_name} already exists")

        # Update description if empty
        if not regs_data['peripherals']['VIM']['desc']:
            regs_data['peripherals']['VIM']['desc'] = "Vectored Interrupt Manager (VIM) Module"

        # Save updated regs.yaml
        with open(regs_file, 'w', encoding='utf-8') as f:
            yaml.dump(regs_data, f, default_flow_style=False, sort_keys=False,
                     allow_unicode=True, width=120)

        print(f"\n[OK] Updated {regs_file}")
        print(f"     Total VIM registers: {len(vim_registers)}")
    else:
        print("[ERROR] VIM peripheral not found in regs.yaml")


if __name__ == '__main__':
    print("="*80)
    print("ADDING VIM WAKE REGISTERS TO VIM PERIPHERAL")
    print("="*80)
    print()

    add_vim_wake_registers()

    print()
    print("="*80)
    print("[OK] VIM WAKE REGISTERS ADDED")
    print("="*80)
    print()
    print("Next step: Run inline formatter to format new registers")
    print("  python inline_yaml_format.py --files regs.yaml")
