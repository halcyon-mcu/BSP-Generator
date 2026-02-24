#!/usr/bin/env python3
"""
Generate validation tests for the latest BSP output.

Usage:
    python generate_validation_tests.py [output_dir]

If output_dir is not provided, uses the latest output_* directory.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.modules.validation_integration import (
    collect_generated_peripherals,
    generate_peripheral_validation_test,
    generate_integration_tests,
    generate_cross_file_validation,
    write_test_manifest,
)
from app.modules.prompt import Model
from app.modules.yaml_utils import (
    load_soc_yaml,
    load_regs_yaml,
    load_memmap_yaml,
)
from app.config import YAMLS_DIR, FACTS_CANON


async def main():
    """Main entry point for test generation."""
    
    # Determine output directory
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    else:
        # Find latest output_* directory
        bsp_gen_dir = Path(__file__).parent / "bsp_gen"
        output_dirs = sorted(bsp_gen_dir.glob("output_*"))
        if not output_dirs:
            print("[error] No BSP output directories found in bsp_gen/")
            return False
        output_dir = output_dirs[-1]  # Latest by name
    
    print(f"[info] Using BSP output: {output_dir}")
    
    if not output_dir.exists():
        print(f"[error] Output directory not found: {output_dir}")
        return False
    
    # Create tests directory
    tests_dir = output_dir / "validation_tests"
    tests_dir.mkdir(exist_ok=True)
    print(f"[info] Tests will be written to: {tests_dir}")
    
    # Load YAML data
    print("[info] Loading YAML configuration...")
    try:
        soc_data = load_soc_yaml(YAMLS_DIR / "soc.yaml")
        regs_data = load_regs_yaml(YAMLS_DIR / "regs.yaml")
        memmap_data = load_memmap_yaml(YAMLS_DIR / "memmap.yaml")
        print("[ok] YAML data loaded")
    except Exception as e:
        print(f"[error] Failed to load YAML: {e}")
        return False
    
    # Collect generated peripherals
    peripherals = collect_generated_peripherals(output_dir)
    print(f"[info] Found peripherals: {peripherals}")
    
    if not peripherals:
        print("[warn] No peripherals found to test")
        return False
    
    test_results = []
    
    # Model and tokens config
    model = Model.SONNET_4_5
    max_tokens = 4096
    
    # Generate unit tests for each peripheral
    print("\n[info] Generating unit tests for peripherals...")
    for peripheral in peripherals:
        print(f"  - Testing {peripheral}...")
        try:
            success, test_file = generate_peripheral_validation_test(
                output_dir, 
                peripheral,
                soc_data,
                regs_data,
                model,
                max_tokens,
                tests_dir
            )
            test_results.append((f"unit_{peripheral}", success, test_file))
            if success:
                print(f"    [ok] Generated unit test: {test_file.name}")
            else:
                print(f"    [warn] Failed to generate unit test")
        except Exception as e:
            print(f"    [error] {e}")
            test_results.append((f"unit_{peripheral}", False, tests_dir / f"{peripheral}_test.c"))
    
    # Generate integration test
    print("\n[info] Generating integration test...")
    try:
        success, test_file = generate_integration_tests(
            output_dir,
            soc_data,
            regs_data,
            model,
            max_tokens,
            tests_dir
        )
        test_results.append(("integration", success, test_file))
        if success:
            print(f"  [ok] Generated integration test: {test_file.name}")
        else:
            print(f"  [warn] Failed to generate integration test")
    except Exception as e:
        print(f"  [error] {e}")
        test_results.append(("integration", False, tests_dir / "integration_test.c"))
    
    # Generate cross-file validation
    print("\n[info] Generating cross-file validation test...")
    try:
        success, test_file = generate_cross_file_validation(
            output_dir,
            regs_data,
            memmap_data,
            FACTS_CANON,
            model,
            max_tokens,
            tests_dir
        )
        test_results.append(("cross_file_validation", success, test_file))
        if success:
            print(f"  [ok] Generated cross-file validation: {test_file.name}")
        else:
            print(f"  [warn] Failed to generate cross-file validation")
    except Exception as e:
        print(f"  [error] {e}")
        test_results.append(("cross_file_validation", False, tests_dir / "cross_validation_test.c"))
    
    # Write manifest
    print("\n[info] Writing test manifest...")
    manifest_path = write_test_manifest(tests_dir, test_results)
    
    # Summary
    passed = sum(1 for _, success, _ in test_results if success)
    total = len(test_results)
    print(f"\n{'='*60}")
    print(f"Validation Test Generation Summary")
    print(f"{'='*60}")
    print(f"Total tests generated: {total}")
    print(f"Successful: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Output directory: {tests_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"{'='*60}")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[info] Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"[error] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
