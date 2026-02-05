#!/usr/bin/env python3
"""
add_lin_registers.py

Add extracted LIN registers to SCI peripheral in regs.yaml

Usage:
    python add_lin_registers.py
"""

import yaml
from pathlib import Path


def add_lin_registers():
    """Add LIN registers to SCI peripheral in regs.yaml"""

    regs_file = Path('yaml_in_transformed/regs.yaml')
    lin_file = Path('yaml_out/lin_registers_requested.yaml')

    # Load both files
    with open(regs_file, 'r', encoding='utf-8') as f:
        regs_data = yaml.safe_load(f)

    with open(lin_file, 'r', encoding='utf-8') as f:
        lin_data = yaml.safe_load(f)

    # Get LIN registers (skip SCIGCR2 as it already exists)
    lin_registers = lin_data['peripherals']['LIN']['registers']
    lin_registers_to_add = {k: v for k, v in lin_registers.items() if k != 'SCIGCR2'}

    print(f"Adding {len(lin_registers_to_add)} LIN registers to SCI peripheral:")
    for reg_name in lin_registers_to_add.keys():
        print(f"  - {reg_name}")

    # Add to SCI peripheral
    if 'SCI' in regs_data['peripherals']:
        sci_registers = regs_data['peripherals']['SCI']['registers']

        # Add LIN registers (they will be added after existing registers)
        for reg_name, reg_data in lin_registers_to_add.items():
            if reg_name not in sci_registers:
                sci_registers[reg_name] = reg_data
                print(f"  [OK] Added {reg_name}")
            else:
                print(f"  [SKIP] {reg_name} already exists")

        # Update description
        regs_data['peripherals']['SCI']['desc'] = "Serial Communication Interface (SCI) / Local Interconnect Network (LIN) Module"

        # Save updated regs.yaml
        with open(regs_file, 'w', encoding='utf-8') as f:
            yaml.dump(regs_data, f, default_flow_style=False, sort_keys=False,
                     allow_unicode=True, width=120)

        print(f"\n[OK] Updated {regs_file}")
        print(f"     Total SCI registers: {len(sci_registers)}")
    else:
        print("[ERROR] SCI peripheral not found in regs.yaml")


if __name__ == '__main__':
    print("="*80)
    print("ADDING LIN REGISTERS TO SCI PERIPHERAL")
    print("="*80)
    print()

    add_lin_registers()

    print()
    print("="*80)
    print("[OK] LIN REGISTERS ADDED")
    print("="*80)
    print()
    print("Next step: Run inline formatter to format new registers")
    print("  python inline_yaml_format.py --files regs.yaml")
