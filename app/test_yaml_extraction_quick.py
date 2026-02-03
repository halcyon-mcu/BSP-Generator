#!/usr/bin/env python3
"""
Quick test: Extract one peripheral and validate YAML.
Use this to quickly test if fixes are working.
"""

import asyncio
from pathlib import Path
import yaml as pyyaml

from extract_to_yaml import extract_all_peripherals
from modules.prompt import Model


async def quick_test():
    """Quick extraction test on GIO only."""
    print("="*80)
    print("QUICK YAML EXTRACTION TEST - GIO Only")
    print("="*80)
    print()

    # Extract just GIO
    await extract_all_peripherals(
        trm_dir=Path("modules/pdfs/TRM_split"),
        datasheet_path=None,
        output_dir=Path("yaml_out_quick_test"),
        model=Model.SONNET_4_5,
        max_concurrent=1,
        max_budget=5.0,
        test_peripherals=["GIO"]
    )

    # Validate output
    print("\n" + "="*80)
    print("VALIDATION")
    print("="*80)

    yaml_file = Path("yaml_out_quick_test/extracted/GIO/GIO_extracted.yaml")

    if not yaml_file.exists():
        print("[FAIL] FAIL: Output file not created")
        return False

    try:
        with open(yaml_file) as f:
            data = pyyaml.safe_load(f)

        if not data:
            print("[FAIL] FAIL: Empty YAML")
            return False

        print("[OK] YAML is valid and parseable")

        # Check for all 7 sections
        expected_sections = [
            "registers",
            "clock_config",
            "pins",
            "init_sequence",
            "dma_channels",
            "interrupts",
            "peripheral_metadata"
        ]

        found_sections = []
        missing_sections = []

        for section in expected_sections:
            if section in data:
                found_sections.append(section)
            else:
                missing_sections.append(section)

        print(f"\nSections found: {len(found_sections)}/7")
        for section in found_sections:
            print(f"  [OK] {section}")

        if missing_sections:
            print(f"\nMissing sections: {len(missing_sections)}")
            for section in missing_sections:
                print(f"  [FAIL] {section}")

        # Check for x-source
        has_source = False
        if 'registers' in data and isinstance(data['registers'], dict):
            for reg_name, reg_data in list(data['registers'].items())[:3]:  # Check first 3
                if isinstance(reg_data, dict) and 'x-source' in reg_data:
                    has_source = True
                    break

        if has_source:
            print("\n[OK] Source attribution found")
        else:
            print("\n[WARN] WARNING: No x-source found (check provenance)")

        # Summary
        print("\n" + "="*80)
        if len(found_sections) >= 5 and has_source:
            print("[OK] PASS: Extraction is working correctly")
            print("  - Valid YAML")
            print(f"  - {len(found_sections)}/7 sections present")
            print("  - Source attribution present")
            print("\nReady to run full test: python test_extraction_system.py")
            return True
        else:
            print("[FAIL] FAIL: Extraction needs fixes")
            if len(found_sections) < 5:
                print(f"  - Only {len(found_sections)}/7 sections extracted")
            if not has_source:
                print("  - Missing source attribution")
            return False

    except pyyaml.YAMLError as e:
        print(f"[FAIL] FAIL: Invalid YAML")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] FAIL: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(quick_test())
    exit(0 if success else 1)
