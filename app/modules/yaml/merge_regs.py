#!/usr/bin/env python3
"""
merge_regs_yaml.py

Merge original manual registers with extracted registers.
Use original for SYSTEM, SYSTEM2, PCR (complete, verified)
Use extracted for all others (comprehensive AI extraction)

Usage:
    python merge_regs_yaml.py
"""

import yaml
from pathlib import Path
from typing import Dict, List, Set


def merge_regs_yaml(
    original_path: Path,
    extracted_path: Path,
    output_path: Path,
    keep_from_original: Set[str] = None
):
    """Merge register YAMLs, prioritizing original for specific peripherals."""

    if keep_from_original is None:
        keep_from_original = {'SYSTEM', 'SYSTEM2', 'PCR', 'VIM_PARITY'}

    print("="*80)
    print("MERGING REGISTER YAML FILES")
    print("="*80)
    print(f"Original:  {original_path}")
    print(f"Extracted: {extracted_path}")
    print(f"Output:    {output_path}")
    print(f"Keep from original: {', '.join(sorted(keep_from_original))}")
    print()

    # Load both files
    with open(original_path) as f:
        original = yaml.safe_load(f)

    with open(extracted_path) as f:
        extracted = yaml.safe_load(f)

    # Start with extracted structure
    merged = {
        'peripherals': {}
    }

    # Add peripherals from original (priority list)
    print("Adding peripherals from ORIGINAL (verified):")
    for periph_name in sorted(keep_from_original):
        if periph_name in original.get('peripherals', {}):
            merged['peripherals'][periph_name] = original['peripherals'][periph_name]
            reg_count = len(original['peripherals'][periph_name].get('registers', {}))
            print(f"  [OK] {periph_name}: {reg_count} registers")
        else:
            print(f"  [WARN] {periph_name}: not found in original")

    # Add peripherals from extracted (all others)
    print()
    print("Adding peripherals from EXTRACTED (AI-generated):")
    extracted_count = 0
    for periph_name, periph_data in extracted.get('peripherals', {}).items():
        if periph_name not in keep_from_original:
            merged['peripherals'][periph_name] = periph_data
            reg_count = len(periph_data.get('registers', {}))
            extracted_count += 1
            if extracted_count <= 5:  # Show first 5
                print(f"  [OK] {periph_name}: {reg_count} registers")

    if extracted_count > 5:
        print(f"  ... and {extracted_count - 5} more peripherals")

    # Write merged YAML
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        yaml.dump(merged, f, default_flow_style=False, sort_keys=False)

    # Summary
    print()
    print("="*80)
    print("MERGE COMPLETE")
    print("="*80)
    print(f"Total peripherals: {len(merged['peripherals'])}")
    print(f"  From original: {len(keep_from_original & set(merged['peripherals'].keys()))}")
    print(f"  From extracted: {len(set(merged['peripherals'].keys()) - keep_from_original)}")
    print()

    total_regs = sum(
        len(p.get('registers', {}))
        for p in merged['peripherals'].values()
    )
    print(f"Total registers: {total_regs}")
    print()
    print(f"Output: {output_path}")
    print("="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge original and extracted register YAMLs"
    )
    parser.add_argument(
        '--original',
        type=Path,
        default=Path('yaml_in/original/regs.yaml'),
        help='Original manual regs.yaml'
    )
    parser.add_argument(
        '--extracted',
        type=Path,
        default=Path('yaml_in/regs.yaml'),
        help='Extracted regs.yaml'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('yaml_in/regs.yaml'),
        help='Output merged regs.yaml'
    )
    parser.add_argument(
        '--keep-from-original',
        type=str,
        default='SYSTEM,SYSTEM2,PCR,VIM_PARITY',
        help='Comma-separated list of peripherals to keep from original'
    )

    args = parser.parse_args()

    keep_set = set(p.strip() for p in args.keep_from_original.split(','))

    merge_regs_yaml(
        original_path=args.original,
        extracted_path=args.extracted,
        output_path=args.output,
        keep_from_original=keep_set
    )


if __name__ == '__main__':
    main()
