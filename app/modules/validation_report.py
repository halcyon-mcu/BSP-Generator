#!/usr/bin/env python3
"""
validation_report.py

Validation reporting infrastructure for BSP generation.

This module provides:
- JSON report generation
- Markdown report generation
- Console output formatting
- Validation manifest management
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .validation_engine import (
    FactsValidationResult,
    CrossFileValidation,
    ValidationResult
)
from .dependency_resolver import InitOrder, DependencyGraph


# ==============================================================================
# REPORT DATA STRUCTURES
# ==============================================================================

@dataclass
class ValidationSummary:
    """
    High-level summary of validation results.
    """
    total_modules: int = 0
    modules_valid: int = 0
    modules_invalid: int = 0
    critical_errors: int = 0
    warnings: int = 0
    success_rate: float = 0.0

    def is_successful(self) -> bool:
        """True if no critical errors."""
        return self.critical_errors == 0


@dataclass
class ModuleValidation:
    """
    Validation results for a single module.
    """
    module_name: str
    facts_mirror_valid: bool
    constants_validated: int
    mismatches: int
    tests_generated: bool
    critical_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    """
    Complete validation report for BSP generation.
    """
    timestamp: str
    bsp_output_dir: str

    validation_summary: ValidationSummary = field(default_factory=ValidationSummary)
    peripheral_validations: Dict[str, ModuleValidation] = field(default_factory=dict)
    cross_file_validation: Optional[Dict[str, Any]] = None
    dependency_graph_info: Optional[Dict[str, Any]] = None

    def is_successful(self) -> bool:
        """True if validation passed with no critical errors."""
        return self.validation_summary.is_successful()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "bsp_output_dir": self.bsp_output_dir,
            "validation_summary": asdict(self.validation_summary),
            "peripheral_validations": {
                name: asdict(val) for name, val in self.peripheral_validations.items()
            },
            "cross_file_validation": self.cross_file_validation,
            "dependency_graph": self.dependency_graph_info
        }


# ==============================================================================
# REPORT GENERATION
# ==============================================================================

def create_validation_report(
    output_dir: Path,
    validation_results: Dict[str, ValidationResult],
    cross_file_validation: Optional[CrossFileValidation] = None,
    dependency_graph: Optional[DependencyGraph] = None,
    init_order: Optional[InitOrder] = None
) -> ValidationReport:
    """
    Create comprehensive validation report from all validation results.

    Args:
        output_dir: BSP output directory
        validation_results: Dict mapping phase tag -> ValidationResult
        cross_file_validation: Cross-file validation results
        dependency_graph: Dependency graph (if available)
        init_order: Init order (if available)

    Returns:
        ValidationReport with all data aggregated
    """
    report = ValidationReport(
        timestamp=datetime.now().isoformat(),
        bsp_output_dir=str(output_dir)
    )

    # Aggregate module validations
    for tag, val_result in validation_results.items():
        if val_result.facts_validation:
            module_name = val_result.facts_validation.module_name

            module_val = ModuleValidation(
                module_name=module_name,
                facts_mirror_valid=val_result.facts_validation.is_valid,
                constants_validated=len(val_result.facts_validation.matches),
                mismatches=len(val_result.facts_validation.mismatches),
                tests_generated=False,  # Updated later if tests run
                critical_errors=val_result.errors,
                warnings=val_result.warnings
            )

            report.peripheral_validations[module_name] = module_val

    # Calculate summary statistics
    summary = ValidationSummary()
    summary.total_modules = len(report.peripheral_validations)
    summary.modules_valid = sum(
        1 for v in report.peripheral_validations.values() if v.facts_mirror_valid
    )
    summary.modules_invalid = summary.total_modules - summary.modules_valid

    # Count errors and warnings
    for val in report.peripheral_validations.values():
        summary.critical_errors += len(val.critical_errors)
        summary.warnings += len(val.warnings)

    # Calculate success rate
    if summary.total_modules > 0:
        summary.success_rate = summary.modules_valid / summary.total_modules

    report.validation_summary = summary

    # Add cross-file validation
    if cross_file_validation:
        report.cross_file_validation = {
            "passes": cross_file_validation.passes,
            "conflicts": [str(c) for c in cross_file_validation.conflicts],
            "consistency_score": cross_file_validation.consistency_score,
            "errors": cross_file_validation.errors,
            "warnings": cross_file_validation.warnings
        }

    # Add dependency graph info
    if dependency_graph and init_order:
        report.dependency_graph_info = {
            "total_nodes": len(dependency_graph.nodes),
            "has_cycles": init_order.has_cycles,
            "init_order": init_order.order if init_order.is_valid() else [],
            "cycle_nodes": init_order.cycle_nodes if init_order.has_cycles else []
        }

    return report


def write_json_report(report: ValidationReport, output_path: Path) -> Path:
    """
    Write validation report as JSON file.

    Args:
        report: ValidationReport to write
        output_path: Path to JSON file

    Returns:
        Path to written file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report.to_dict(), f, indent=2)

    return output_path


def write_markdown_report(report: ValidationReport, output_path: Path) -> Path:
    """
    Write validation report as Markdown file.

    Args:
        report: ValidationReport to write
        output_path: Path to Markdown file

    Returns:
        Path to written file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    # Title
    lines.append("# BSP Generation Validation Report")
    lines.append("")
    lines.append(f"**Generated:** {report.timestamp}")
    lines.append(f"**Output Directory:** `{report.bsp_output_dir}`")
    lines.append("")

    # Overall status
    status_emoji = "✅" if report.is_successful() else "❌"
    lines.append(f"## Overall Status: {status_emoji}")
    lines.append("")

    # Summary
    summary = report.validation_summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Modules:** {summary.total_modules}")
    lines.append(f"- **Valid Modules:** {summary.modules_valid} ✅")
    lines.append(f"- **Invalid Modules:** {summary.modules_invalid} ❌")
    lines.append(f"- **Success Rate:** {summary.success_rate:.1%}")
    lines.append(f"- **Critical Errors:** {summary.critical_errors}")
    lines.append(f"- **Warnings:** {summary.warnings}")
    lines.append("")

    # Per-module results
    lines.append("## Module Validation Results")
    lines.append("")
    lines.append("| Module | Status | Constants | Mismatches | Errors | Warnings |")
    lines.append("|--------|--------|-----------|------------|--------|----------|")

    for module_name, val in sorted(report.peripheral_validations.items()):
        status = "✅" if val.facts_mirror_valid else "❌"
        lines.append(
            f"| {module_name} | {status} | {val.constants_validated} | "
            f"{val.mismatches} | {len(val.critical_errors)} | {len(val.warnings)} |"
        )

    lines.append("")

    # Detailed errors
    has_errors = any(
        len(v.critical_errors) > 0 for v in report.peripheral_validations.values()
    )

    if has_errors:
        lines.append("## Detailed Errors")
        lines.append("")

        for module_name, val in sorted(report.peripheral_validations.items()):
            if val.critical_errors:
                lines.append(f"### {module_name}")
                lines.append("")
                for error in val.critical_errors:
                    lines.append(f"- ❌ {error}")
                lines.append("")

    # Cross-file validation
    if report.cross_file_validation:
        cross = report.cross_file_validation
        status = "✅" if cross["passes"] else "❌"
        lines.append(f"## Cross-File Validation: {status}")
        lines.append("")
        lines.append(f"- **Consistency Score:** {cross['consistency_score']:.1%}")
        lines.append(f"- **Conflicts:** {len(cross['conflicts'])}")
        lines.append("")

        if cross["conflicts"]:
            lines.append("### Conflicts")
            lines.append("")
            for conflict in cross["conflicts"]:
                lines.append(f"- {conflict}")
            lines.append("")

    # Dependency graph
    if report.dependency_graph_info:
        dep = report.dependency_graph_info
        status = "✅" if not dep["has_cycles"] else "❌"
        lines.append(f"## Dependency Graph: {status}")
        lines.append("")
        lines.append(f"- **Total Nodes:** {dep['total_nodes']}")
        lines.append(f"- **Has Cycles:** {'Yes ❌' if dep['has_cycles'] else 'No ✅'}")
        lines.append("")

        if dep["has_cycles"]:
            cycle_str = " → ".join(dep["cycle_nodes"] + [dep["cycle_nodes"][0]])
            lines.append(f"**Circular Dependency Detected:** {cycle_str}")
            lines.append("")
        else:
            lines.append("### Initialization Order")
            lines.append("")
            for i, module in enumerate(dep["init_order"], 1):
                lines.append(f"{i}. {module}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*This report was auto-generated by the BSP Generator validation system.*")
    lines.append("")

    # Write to file
    output_path.write_text("\n".join(lines), encoding="utf-8")

    return output_path


def print_console_summary(report: ValidationReport) -> None:
    """
    Print validation summary to console with color coding.

    Args:
        report: ValidationReport to print
    """
    # ANSI color codes
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    print("\n" + "=" * 70)
    print(f"{BOLD}BSP Generation Validation Report{RESET}")
    print("=" * 70)

    # Overall status
    if report.is_successful():
        status_str = f"{GREEN}✓ PASS{RESET}"
    else:
        status_str = f"{RED}✗ FAIL{RESET}"

    print(f"\nOverall Status: {status_str}")

    # Summary
    summary = report.validation_summary
    print(f"\n{BOLD}Summary:{RESET}")
    print(f"  Total Modules:    {summary.total_modules}")
    print(f"  Valid Modules:    {GREEN}{summary.modules_valid}{RESET}")
    print(f"  Invalid Modules:  {RED if summary.modules_invalid > 0 else ''}{summary.modules_invalid}{RESET}")
    print(f"  Success Rate:     {summary.success_rate:.1%}")

    if summary.critical_errors > 0:
        print(f"  Critical Errors:  {RED}{summary.critical_errors}{RESET}")
    if summary.warnings > 0:
        print(f"  Warnings:         {YELLOW}{summary.warnings}{RESET}")

    # Per-module summary
    if report.peripheral_validations:
        print(f"\n{BOLD}Module Results:{RESET}")
        for module_name, val in sorted(report.peripheral_validations.items()):
            if val.facts_mirror_valid:
                status = f"{GREEN}✓{RESET}"
            else:
                status = f"{RED}✗{RESET}"

            print(f"  {status} {module_name:12s} - {val.constants_validated} constants, "
                  f"{val.mismatches} mismatches")

            # Show first error if present
            if val.critical_errors:
                print(f"      {RED}Error: {val.critical_errors[0]}{RESET}")

    # Cross-file validation
    if report.cross_file_validation:
        cross = report.cross_file_validation
        status = f"{GREEN}✓{RESET}" if cross["passes"] else f"{RED}✗{RESET}"
        print(f"\n{BOLD}Cross-File Validation:{RESET} {status}")
        print(f"  Consistency Score: {cross['consistency_score']:.1%}")

        if cross["conflicts"]:
            print(f"  {YELLOW}Conflicts: {len(cross['conflicts'])}{RESET}")

    # Dependency graph
    if report.dependency_graph_info:
        dep = report.dependency_graph_info
        status = f"{RED}✗{RESET}" if dep["has_cycles"] else f"{GREEN}✓{RESET}"
        print(f"\n{BOLD}Dependency Graph:{RESET} {status}")

        if dep["has_cycles"]:
            cycle_str = " → ".join(dep["cycle_nodes"][:3]) + "..."
            print(f"  {RED}Circular dependency: {cycle_str}{RESET}")
        else:
            init_preview = " → ".join(dep["init_order"][:5])
            if len(dep["init_order"]) > 5:
                init_preview += "..."
            print(f"  Init order: {init_preview}")

    print("\n" + "=" * 70 + "\n")


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def save_validation_manifest(
    report: ValidationReport,
    output_dir: Path,
    filename: str = "validation_manifest.json"
) -> Path:
    """
    Save validation report as a manifest file.

    Args:
        report: ValidationReport to save
        output_dir: Output directory
        filename: Name of manifest file

    Returns:
        Path to saved manifest
    """
    manifest_path = output_dir / filename
    return write_json_report(report, manifest_path)


def update_module_test_status(
    report: ValidationReport,
    module_name: str,
    tests_generated: bool
) -> None:
    """
    Update test generation status for a module.

    Args:
        report: ValidationReport to update
        module_name: Name of module
        tests_generated: True if tests were generated
    """
    if module_name in report.peripheral_validations:
        report.peripheral_validations[module_name].tests_generated = tests_generated
