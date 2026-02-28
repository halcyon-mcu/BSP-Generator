#!/usr/bin/env python3
"""
Simple test for a single module validation.
"""

import sys
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from modules.validation.validation_engine import validate_generation_output
from modules.yaml.yaml_utils import load_soc_yaml, load_regs_yaml

def test_single_module():
    """Test validation on a single module (GIO)."""

    # Use paths from original BSP output
    original_bsp = Path("c:/Users/dovyd/Documents/GitHub/BSP-Generator/app")
    output_dir = original_bsp / "output_20260223_200046"
    yaml_dir = original_bsp / "yaml_in"

    print("=" * 70)
    print("Testing Fallback Validation on GIO Module")
    print("=" * 70)

    # Load YAML
    print("Loading YAML files...")
    soc_data = load_soc_yaml(yaml_dir / "soc.yaml")
    regs_data = load_regs_yaml(yaml_dir / "regs.yaml")
    print(f"  Loaded {len(soc_data.get('peripherals', []))} peripherals from soc.yaml")
    print(f"  Loaded {len(regs_data.get('peripherals', {}))} peripheral blocks from regs.yaml\n")

    # GIO module files (in include/ subdirectory)
    gio_files = [
        output_dir / "source" / "gio_driver.c",
        output_dir / "include" / "gio_driver.h",
        output_dir / "include" / "reg_gio.h"
    ]

    # Check which files exist
    existing_files = [f for f in gio_files if f.exists()]
    print(f"Found {len(existing_files)} GIO files:")
    for f in existing_files:
        print(f"  - {f.name}")
    print()

    # Run validation
    print("Running fallback validation (no FACTS MIRROR)...")
    validation_result = validate_generation_output(
        tag="periph_gio",
        preamble="",  # Empty preamble - no FACTS MIRROR
        written_files=existing_files,
        soc_data=soc_data,
        regs_data=regs_data
    )

    # Display results
    print("\nValidation Results:")
    print("=" * 70)
    print(f"Overall Status: {'PASS' if validation_result.is_valid else 'FAIL'}")
    print(f"Has TODOs: {validation_result.has_todos}")
    print(f"Errors: {len(validation_result.errors)}")
    print(f"Warnings: {len(validation_result.warnings)}")

    if validation_result.facts_validation:
        fv = validation_result.facts_validation
        print(f"\nFacts Validation:")
        print(f"  - Module: {fv.module_name}")
        print(f"  - Valid: {fv.is_valid}")
        print(f"  - Matches: {len(fv.matches)}")
        print(f"  - Mismatches: {len(fv.mismatches)}")
        print(f"  - Missing in code: {len(fv.missing_in_code)}")
        print(f"  - Extra in code: {len(fv.extra_in_code)}")
        print(f"  - Success rate: {fv.success_rate():.1%}")

        if fv.matches:
            print(f"\n  Sample matches (first 5):")
            for name, expected, actual in fv.matches[:5]:
                print(f"    - {name}: {expected} == {actual}")

        if fv.mismatches:
            print(f"\n  Mismatches:")
            for name, expected, actual in fv.mismatches:
                print(f"    - {name}: expected {expected}, got {actual}")

    if validation_result.errors:
        print(f"\nErrors:")
        for error in validation_result.errors:
            print(f"  - {error}")

    if validation_result.warnings:
        print(f"\nWarnings:")
        for warning in validation_result.warnings[:5]:
            print(f"  - {warning}")
        if len(validation_result.warnings) > 5:
            print(f"  ... and {len(validation_result.warnings) - 5} more")

    print("\n" + "=" * 70)
    print("Test complete!")
    print("=" * 70)

if __name__ == "__main__":
    test_single_module()
