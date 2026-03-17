#!/usr/bin/env python3
"""
Fix soc.yaml regs_ref mappings to match regs.yaml peripheral names.

This script adds or updates the regs_ref field for peripherals in soc.yaml
to correctly reference register definitions in regs.yaml.
"""

import yaml
from pathlib import Path
import shutil

# Mapping from soc.yaml peripheral names to regs.yaml names
REGS_REF_MAPPING = {
    # I2C
    'I2C': 'INTER',

    # ADC
    'MIBADC1': 'ADC',
    'MIBADC2': 'ADC',

    # CAN
    'DCAN1': 'DCAN',
    'DCAN2': 'DCAN',
    'DCAN3': 'DCAN',

    # Clock Comparator
    'DCC1': 'DCC',
    'DCC2': 'DCC',

    # HTU
    'HTU1': 'HTU',
    'HTU2': 'HTU',

    # SPI
    'MIBSPI1': 'SPI',
    'SPI2': 'SPI',
    'MIBSPI3': 'SPI',
    'SPI4': 'SPI',
    'MIBSPI5': 'SPI',

    # Timers (N2HET)
    'N2HET1': 'TIMER',
    'N2HET2': 'TIMER',

    # Enhanced Capture
    'ECAP1': 'ECAP',
    'ECAP2': 'ECAP',
    'ECAP3': 'ECAP',
    'ECAP4': 'ECAP',
    'ECAP5': 'ECAP',
    'ECAP6': 'ECAP',

    # Enhanced PWM
    'EPWM1': 'EPWM',
    'EPWM2': 'EPWM',
    'EPWM3': 'EPWM',
    'EPWM4': 'EPWM',
    'EPWM5': 'EPWM',
    'EPWM6': 'EPWM',
    'EPWM7': 'EPWM',

    # Quadrature Encoder
    'EQEP1': 'PULSE',
    'EQEP2': 'PULSE',

    # Ethernet
    'EMAC': 'EMACMDIO',
    'MDIO': 'EMACMDIO',

    # USB
    'USB_DEVICE': 'USB',
    'USB_OHCI': 'USB',

    # Flash
    'FLASH_MODULE': 'FMC',

    # Pin Mux
    'PIN': 'IOMM',
}


def fix_soc_yaml(soc_path: Path):
    """
    Fix regs_ref fields in soc.yaml.

    Args:
        soc_path: Path to soc.yaml file
    """
    # Backup original file
    backup_path = soc_path.with_suffix('.yaml.backup_regsref')
    shutil.copy2(soc_path, backup_path)
    print(f"Created backup: {backup_path}")

    # Load YAML
    with soc_path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Fix peripherals
    fixed_count = 0
    for periph in data['soc']['peripherals']:
        name = periph['name']

        if name in REGS_REF_MAPPING:
            correct_ref = REGS_REF_MAPPING[name]
            current_ref = periph.get('regs_ref', name)

            if current_ref != correct_ref:
                periph['regs_ref'] = correct_ref
                print(f"  {name:20} regs_ref: {current_ref:20} -> {correct_ref}")
                fixed_count += 1
            else:
                print(f"  {name:20} regs_ref: {correct_ref:20} [OK]")

    # Write fixed YAML
    with soc_path.open('w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print()
    print(f"Fixed {fixed_count} regs_ref mappings")
    print(f"Updated: {soc_path}")


def main():
    """Main entry point."""
    soc_path = Path('yaml_in/soc.yaml')

    if not soc_path.exists():
        print(f"Error: {soc_path} not found")
        return 1

    print("=" * 70)
    print("Fixing soc.yaml regs_ref mappings")
    print("=" * 70)
    print()

    fix_soc_yaml(soc_path)

    print()
    print("=" * 70)
    print("Done!")
    print("=" * 70)
    print()
    print("Run 'python main.py' to verify cross-reference validation passes.")

    return 0


if __name__ == '__main__':
    exit(main())
