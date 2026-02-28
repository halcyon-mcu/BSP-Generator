#!/usr/bin/env python3
"""
Test script to validate the improved validation system against existing BSP output.
"""

import sys
from pathlib import Path

# Add app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from modules.validation.validation_engine import (
    validate_generation_output,
    extract_all_constants_from_directory,
    validate_facts_across_files
)
from modules.validation.validation_report import (
    create_validation_report,
    write_json_report,
    write_markdown_report,
    print_console_summary,
    ValidationReport
)
from modules.yaml.yaml_utils import load_soc_yaml, load_regs_yaml
from modules.utils.dependency_resolver import build_dependency_graph, generate_init_order

def test_validation():
    """Test validation on existing BSP output."""

    # Paths
    output_dir = Path("c:/Users/dovyd/Documents/GitHub/BSP-Generator/app/output_20260223_200046")
    yaml_dir = Path("app/yaml_in")

    print("=" * 70)
    print("Testing Improved Validation System")
    print("=" * 70)
    print(f"Output directory: {output_dir}")
    print(f"YAML directory: {yaml_dir}\n")

    # Load YAML files
    print("[1/5] Loading YAML files...")
    try:
        soc_data = load_soc_yaml(yaml_dir / "soc.yaml")
        regs_data = load_regs_yaml(yaml_dir / "regs.yaml")
        print(f"  [OK] Loaded soc.yaml: {len(soc_data.get('peripherals', []))} peripherals")
        print(f"  [OK] Loaded regs.yaml: {len(regs_data.get('peripherals', {}))} peripheral blocks\n")
    except Exception as e:
        print(f"  [FAIL] Failed to load YAML files: {e}")
        return 1

    # Simulate validation for each module (using existing files)
    print("[2/5] Running fallback validation on generated files...")
    validation_results = {}

    # Get list of driver files
    driver_files = list(output_dir.glob("*_driver.c"))
    print(f"  Found {len(driver_files)} driver files\n")

    for driver_file in driver_files:
        module_name = driver_file.stem.replace("_driver", "").upper()
        header_file = output_dir / f"{module_name.lower()}_driver.h"
        reg_header = output_dir / f"reg_{module_name.lower()}.h"

        written_files = [f for f in [driver_file, header_file, reg_header] if f.exists()]

        # Run validation
        tag = f"periph_{module_name.lower()}"
        validation_result = validate_generation_output(
            tag=tag,
            preamble="",  # No FACTS MIRROR - will use fallback
            written_files=written_files,
            soc_data=soc_data,
            regs_data=regs_data
        )

        validation_results[tag] = validation_result

        status = "[OK]" if validation_result.is_valid else "[FAIL]"
        print(f"  {status} {module_name}: {len(validation_result.errors)} errors, {len(validation_result.warnings)} warnings")

        if validation_result.facts_validation:
            fv = validation_result.facts_validation
            print(f"    - Constants validated: {len(fv.matches)}")
            print(f"    - Mismatches: {len(fv.mismatches)}")

    print()

    # Cross-file validation
    print("[3/5] Running cross-file validation...")
    try:
        all_constants = extract_all_constants_from_directory(output_dir)
        cross_file_validation = validate_facts_across_files(all_constants, soc_data)

        status = "[OK]" if cross_file_validation.passes else "[FAIL]"
        print(f"  {status} Consistency score: {cross_file_validation.consistency_score:.1%}")
        print(f"    - Conflicts: {len(cross_file_validation.conflicts)}")
        print(f"    - Files analyzed: {len(all_constants)}\n")
    except Exception as e:
        print(f"  [FAIL] Cross-file validation failed: {e}\n")
        cross_file_validation = None

    # Dependency graph
    print("[4/5] Analyzing dependency graph...")
    try:
        dep_graph = build_dependency_graph(soc_data)
        init_order = generate_init_order(dep_graph)
        status = "[OK]" if not init_order.has_cycles else "[FAIL]"
        print(f"  {status} Dependency graph: {len(dep_graph.nodes)} nodes")
        print(f"    - Has cycles: {init_order.has_cycles}\n")
    except Exception as e:
        print(f"  [FAIL] Dependency analysis failed: {e}\n")
        dep_graph = None
        init_order = None

    # Create comprehensive report
    print("[5/5] Generating validation report...")
    try:
        final_report = ValidationReport(
            timestamp="test_run",
            bsp_output_dir=str(output_dir)
        )

        # Build report from validation results
        for tag, vr in validation_results.items():
            if vr.facts_validation:
                from modules.validation.validation_report import ModuleValidation
                module_name = tag.split('_')[-1].upper()
                mv = ModuleValidation(
                    module_name=module_name,
                    facts_mirror_valid=vr.is_valid,
                    constants_validated=len(vr.facts_validation.matches) + len(vr.facts_validation.mismatches),
                    mismatches=len(vr.facts_validation.mismatches),
                    tests_generated=False,
                    critical_errors=vr.errors[:10],
                    warnings=vr.warnings[:10]
                )
                final_report.peripheral_validations[module_name] = mv

        # Update summary
        from modules.validation.validation_report import ValidationSummary
        summary = ValidationSummary()
        summary.total_modules = len(final_report.peripheral_validations)
        summary.modules_valid = sum(1 for v in final_report.peripheral_validations.values() if v.facts_mirror_valid)
        summary.modules_invalid = summary.total_modules - summary.modules_valid
        summary.critical_errors = sum(len(v.critical_errors) for v in final_report.peripheral_validations.values())
        summary.warnings = sum(len(v.warnings) for v in final_report.peripheral_validations.values())
        if summary.total_modules > 0:
            summary.success_rate = (summary.modules_valid / summary.total_modules) * 100
        final_report.validation_summary = summary

        # Add cross-file validation
        if cross_file_validation:
            final_report.cross_file_validation = {
                "passes": cross_file_validation.passes,
                "conflicts": [str(c) for c in cross_file_validation.conflicts],
                "consistency_score": cross_file_validation.consistency_score,
                "errors": cross_file_validation.errors,
                "warnings": cross_file_validation.warnings
            }

        # Add dependency graph
        if dep_graph and init_order:
            final_report.dependency_graph_info = {
                "total_nodes": len(dep_graph.nodes),
                "has_cycles": init_order.has_cycles,
                "init_order": init_order.order if init_order.is_valid() else [],
                "cycle_nodes": init_order.cycle_nodes if init_order.has_cycles else []
            }

        # Write reports
        test_output_dir = Path("test_validation_output")
        test_output_dir.mkdir(exist_ok=True)

        json_path = test_output_dir / "validation_report_improved.json"
        md_path = test_output_dir / "validation_report_improved.md"

        write_json_report(final_report, json_path)
        write_markdown_report(final_report, md_path)

        print(f"  [OK] JSON report: {json_path}")
        print(f"  [OK] Markdown report: {md_path}\n")

        # Print console summary
        print_console_summary(final_report)

    except Exception as e:
        print(f"  [FAIL] Report generation failed: {e}\n")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 70)
    print("Validation test complete!")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(test_validation())
