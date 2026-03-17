#!/usr/bin/env python3
"""
Fix placeholder base addresses in regs.yaml

This script replaces all '0x00000000' base addresses with correct values
cross-referenced from soc.yaml and RM46_Hardware_Info.md.
"""

import sys
from pathlib import Path
import yaml

# Base address mapping from soc.yaml and RM46_Hardware_Info.md
BASE_ADDRESSES = {
    'ADC': '0xFFF7C000',      # From soc.yaml line 1101
    'CCM': '0xFFFFF600',      # From soc.yaml line 68
    'CRC': '0xFE000000',      # From soc.yaml line 101
    'DCAN': '0xFFF7DC00',     # From soc.yaml line 1134 (DCAN1)
    'DCC': '0xFFFFEC00',      # From soc.yaml line 1497 (DCC1)
    'ECAP': '0xFCF79300',     # From soc.yaml line 1397 (ECAP1)
    'EFUSE': '0xFFF8C000',    # From soc.yaml line 287
    'EMACMDIO': '0xFCF78900', # From soc.yaml line 1288 (MDIO)
    'EMIF': '0xFCFFE800',     # From soc.yaml line 344
    'EPWM': '0xFCF78C00',     # From soc.yaml line 1321 (EPWM1)
    'ESM': '0xFFFFF500',      # From soc.yaml line 383
    'FMC': '0xFFF87000',      # From soc.yaml line 403
    'HTU': '0xFFF7A400',      # From soc.yaml line 1243 (HTU1)
    'INTER': '0xFFF7D400',    # From soc.yaml line 519 (I2C)
    'IOMM': '0xFFFFEA00',     # From soc.yaml line 538
    'LIN': '0xFFF7E400',      # From soc.yaml line 655
    'PBIST': '0xFFFFE400',    # From soc.yaml line 682
    'SPI': '0xFFF7F400',      # From soc.yaml line 1167 (MIBSPI1)
    'PLL': '0xFFFFFF70',      # From RM46_Hardware_Info.md (PLLCTL1)
    'PMM': '0xFFFF0000',      # From soc.yaml line 751
    'POM': '0xFFA04000',      # From soc.yaml line 770
    'PULSE': '0xFCF79900',    # From soc.yaml line 1463 (EQEP1)
    'RAM': '0x08000000',      # From RM46_Hardware_Info.md line 76
    'STC': '0xFFFFE600',      # From soc.yaml line 976
    'TIMER': '0xFFF7B800',    # From soc.yaml line 1222 (N2HET1)
    'USB': '0xFCF78A00',      # From soc.yaml line 1299 (USB_DEVICE)
}


def fix_base_addresses(input_file: Path, output_file: Path = None, backup: bool = True):
    """Fix all placeholder base addresses in regs.yaml"""

    if output_file is None:
        output_file = input_file

    # Create backup if requested
    if backup and output_file == input_file:
        backup_file = input_file.with_suffix('.yaml.backup')
        print(f"Creating backup: {backup_file}")
        backup_file.write_text(input_file.read_text(encoding='utf-8'), encoding='utf-8')

    # Load YAML
    print(f"Loading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Fix base addresses
    fixed_count = 0
    peripherals = data.get('peripherals', {})

    for periph_name, periph_data in peripherals.items():
        if 'base_address' in periph_data:
            current_addr = periph_data['base_address']

            if current_addr == '0x00000000':
                if periph_name in BASE_ADDRESSES:
                    new_addr = BASE_ADDRESSES[periph_name]
                    periph_data['base_address'] = new_addr
                    print(f"  {periph_name}: {current_addr} → {new_addr}")
                    fixed_count += 1
                else:
                    print(f"  WARNING: {periph_name} has placeholder address but no mapping found")

    # Write output
    print(f"\nFixed {fixed_count} base addresses")
    print(f"Writing to {output_file}...")

    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print("Done!")
    return fixed_count


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fix placeholder base addresses in regs.yaml')
    parser.add_argument('--input', type=Path, default=Path('yaml_in/regs.yaml'),
                       help='Input regs.yaml file (default: yaml_in/regs.yaml)')
    parser.add_argument('--output', type=Path, default=None,
                       help='Output file (default: same as input)')
    parser.add_argument('--backup', action='store_true', default=True,
                       help='Create backup before modifying (default: True)')
    parser.add_argument('--no-backup', action='store_false', dest='backup',
                       help='Do not create backup')

    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    try:
        fixed_count = fix_base_addresses(args.input, args.output, args.backup)
        print(f"\nSuccess! Fixed {fixed_count} base addresses.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
