#!/usr/bin/env python3
"""
validation_report.py

Validation reporting infrastructure for BSP generation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .validation_engine import CrossFileValidation, ValidationResult
from ..utils.dependency_resolver import DependencyGraph, InitOrder


@dataclass
class ValidationSummary:
    total_modules: int = 0
    modules_valid: int = 0
    modules_invalid: int = 0
    critical_errors: int = 0
    warnings: int = 0
    success_rate: float = 0.0

    def is_successful(self) -> bool:
        return self.critical_errors == 0


@dataclass
class ModuleValidation:
    module_name: str
    facts_mirror_valid: bool
    constants_validated: int
    mismatches: int
    tests_generated: bool
    critical_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    timestamp: str
    bsp_output_dir: str

    validation_summary: ValidationSummary = field(default_factory=ValidationSummary)
    peripheral_validations: Dict[str, ModuleValidation] = field(default_factory=dict)
    cross_file_validation: Optional[Dict[str, Any]] = None
    dependency_graph_info: Optional[Dict[str, Any]] = None
    compile_contract: Optional[Dict[str, Any]] = None
    autofix_actions: List[Dict[str, Any]] = field(default_factory=list)
    startup_contract: Optional[Dict[str, Any]] = None
    build_evidence: Optional[Dict[str, Any]] = None
    api_contract_hash: Optional[str] = None
    runtime_invariants: Optional[Dict[str, Any]] = None
    critical_sequence_mismatches: List[Dict[str, Any]] = field(default_factory=list)

    def is_successful(self) -> bool:
        if self.compile_contract and not self.compile_contract.get("passes", True):
            return False
        if self.startup_contract and not self.startup_contract.get("passes", True):
            return False
        return self.validation_summary.is_successful()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "bsp_output_dir": self.bsp_output_dir,
            "validation_summary": asdict(self.validation_summary),
            "peripheral_validations": {
                name: asdict(val) for name, val in self.peripheral_validations.items()
            },
            "cross_file_validation": self.cross_file_validation,
            "dependency_graph": self.dependency_graph_info,
            "compile_contract": self.compile_contract,
            "autofix_actions": self.autofix_actions,
            "startup_contract": self.startup_contract,
            "build_evidence": self.build_evidence,
            "api_contract_hash": self.api_contract_hash,
            "runtime_invariants": self.runtime_invariants,
            "critical_sequence_mismatches": self.critical_sequence_mismatches,
        }


def create_validation_report(
    output_dir: Path,
    validation_results: Dict[str, ValidationResult],
    cross_file_validation: Optional[CrossFileValidation] = None,
    dependency_graph: Optional[DependencyGraph] = None,
    init_order: Optional[InitOrder] = None,
) -> ValidationReport:
    report = ValidationReport(
        timestamp=datetime.now().isoformat(),
        bsp_output_dir=str(output_dir),
    )

    for _, val_result in validation_results.items():
        if not val_result.facts_validation:
            continue

        module_name = val_result.facts_validation.module_name
        module_val = ModuleValidation(
            module_name=module_name,
            facts_mirror_valid=val_result.facts_validation.is_valid,
            constants_validated=len(val_result.facts_validation.matches),
            mismatches=len(val_result.facts_validation.mismatches),
            tests_generated=False,
            critical_errors=val_result.errors,
            warnings=val_result.warnings,
        )
        report.peripheral_validations[module_name] = module_val

    summary = ValidationSummary()
    summary.total_modules = len(report.peripheral_validations)
    summary.modules_valid = sum(
        1 for v in report.peripheral_validations.values() if v.facts_mirror_valid
    )
    summary.modules_invalid = summary.total_modules - summary.modules_valid
    for val in report.peripheral_validations.values():
        summary.critical_errors += len(val.critical_errors)
        summary.warnings += len(val.warnings)
    if summary.total_modules > 0:
        summary.success_rate = (summary.modules_valid / summary.total_modules) * 100.0

    report.validation_summary = summary

    if cross_file_validation:
        report.cross_file_validation = {
            "passes": cross_file_validation.passes,
            "conflicts": [str(c) for c in cross_file_validation.conflicts],
            "consistency_score": cross_file_validation.consistency_score,
            "errors": cross_file_validation.errors,
            "warnings": cross_file_validation.warnings,
        }

    if dependency_graph and init_order:
        report.dependency_graph_info = {
            "total_nodes": len(dependency_graph.nodes),
            "has_cycles": init_order.has_cycles,
            "init_order": init_order.order if init_order.is_valid() else [],
            "cycle_nodes": init_order.cycle_nodes if init_order.has_cycles else [],
        }

    return report


def write_json_report(report: ValidationReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    return output_path


def write_markdown_report(report: ValidationReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# BSP Generation Validation Report")
    lines.append("")
    lines.append(f"**Generated:** {report.timestamp}")
    lines.append(f"**Output Directory:** `{report.bsp_output_dir}`")
    lines.append("")

    status = "PASS" if report.is_successful() else "FAIL"
    lines.append(f"## Overall Status: {status}")
    lines.append("")

    summary = report.validation_summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Modules:** {summary.total_modules}")
    lines.append(f"- **Valid Modules:** {summary.modules_valid}")
    lines.append(f"- **Invalid Modules:** {summary.modules_invalid}")
    lines.append(f"- **Success Rate:** {summary.success_rate:.1f}%")
    lines.append(f"- **Critical Errors:** {summary.critical_errors}")
    lines.append(f"- **Warnings:** {summary.warnings}")
    lines.append("")

    lines.append("## Module Validation Results")
    lines.append("")
    lines.append("| Module | Status | Constants | Mismatches | Errors | Warnings |")
    lines.append("|--------|--------|-----------|------------|--------|----------|")
    for module_name, val in sorted(report.peripheral_validations.items()):
        module_status = "PASS" if val.facts_mirror_valid else "FAIL"
        lines.append(
            f"| {module_name} | {module_status} | {val.constants_validated} | "
            f"{val.mismatches} | {len(val.critical_errors)} | {len(val.warnings)} |"
        )
    lines.append("")

    if any(v.critical_errors for v in report.peripheral_validations.values()):
        lines.append("## Detailed Errors")
        lines.append("")
        for module_name, val in sorted(report.peripheral_validations.items()):
            if not val.critical_errors:
                continue
            lines.append(f"### {module_name}")
            lines.append("")
            for error in val.critical_errors:
                lines.append(f"- FAIL {error}")
            lines.append("")

    if report.cross_file_validation:
        cross = report.cross_file_validation
        status = "PASS" if cross.get("passes") else "FAIL"
        lines.append(f"## Cross-File Validation: {status}")
        lines.append("")
        lines.append(f"- **Consistency Score:** {cross.get('consistency_score', 0.0):.1%}")
        lines.append(f"- **Conflicts:** {len(cross.get('conflicts', []))}")
        lines.append("")

    if report.compile_contract:
        cc = report.compile_contract
        status = "PASS" if cc.get("passes") else "FAIL"
        lines.append(f"## Compile Contract: {status}")
        lines.append("")
        lines.append(f"- **Checks:** {cc.get('checks', 0)}")
        lines.append(f"- **Errors:** {len(cc.get('errors', []))}")
        lines.append(f"- **Warnings:** {len(cc.get('warnings', []))}")
        if report.api_contract_hash:
            lines.append(f"- **api_contract_hash:** `{report.api_contract_hash}`")
        lines.append("")
        for error in cc.get("errors", [])[:20]:
            lines.append(f"- FAIL {error}")
        for warning in cc.get("warnings", [])[:10]:
            lines.append(f"- WARN {warning}")
        lines.append("")

    if report.runtime_invariants:
        lines.append("## Runtime Invariants")
        lines.append("")

    if report.critical_sequence_mismatches:
        lines.append("## Critical Sequence Mismatches")
        lines.append("")
        for item in report.critical_sequence_mismatches[:200]:
            kind = item.get("kind")
            baseline = item.get("baseline") or {}
            candidate = item.get("candidate") or {}
            btxt = (
                f"{baseline.get('file')}:{baseline.get('line')} "
                f"{baseline.get('canonical_symbol')} {baseline.get('op')}"
                if baseline
                else "<missing>"
            )
            ctxt = (
                f"{candidate.get('file')}:{candidate.get('line')} "
                f"{candidate.get('canonical_symbol')} {candidate.get('op')}"
                if candidate
                else "<missing>"
            )
            lines.append(f"- **{kind}** baseline=`{btxt}` candidate=`{ctxt}`")
        if len(report.critical_sequence_mismatches) > 200:
            lines.append(
                f"- ... truncated {len(report.critical_sequence_mismatches) - 200} additional mismatches"
            )
        lines.append("")
        for key, value in report.runtime_invariants.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    if report.autofix_actions:
        lines.append("## Autofix Actions")
        lines.append("")
        for item in report.autofix_actions[:50]:
            lines.append(f"- **{item.get('module', 'UNKNOWN')}:** {item.get('action', '')}")
        lines.append("")

    if report.startup_contract:
        startup = report.startup_contract
        status = "PASS" if startup.get("passes") else "FAIL"
        lines.append(f"## Startup Contract: {status}")
        lines.append("")
        for error in startup.get("errors", []):
            lines.append(f"- FAIL {error}")
        for warning in startup.get("warnings", []):
            lines.append(f"- WARN {warning}")
        lines.append("")

    if report.build_evidence:
        lines.append("## Build Evidence")
        lines.append("")
        for key, value in report.build_evidence.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    if report.dependency_graph_info:
        dep = report.dependency_graph_info
        status = "PASS" if not dep.get("has_cycles") else "FAIL"
        lines.append(f"## Dependency Graph: {status}")
        lines.append("")
        lines.append(f"- **Total Nodes:** {dep.get('total_nodes', 0)}")
        lines.append(f"- **Has Cycles:** {dep.get('has_cycles', False)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*This report was auto-generated by the BSP Generator validation system.*")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def print_console_summary(report: ValidationReport) -> None:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    print("\n" + "=" * 70)
    print(f"{BOLD}BSP Generation Validation Report{RESET}")
    print("=" * 70)

    status_str = f"{GREEN}PASS{RESET}" if report.is_successful() else f"{RED}FAIL{RESET}"
    print(f"\nOverall Status: {status_str}")

    summary = report.validation_summary
    print(f"\n{BOLD}Summary:{RESET}")
    print(f"  Total Modules:    {summary.total_modules}")
    print(f"  Valid Modules:    {GREEN}{summary.modules_valid}{RESET}")
    print(f"  Invalid Modules:  {RED if summary.modules_invalid > 0 else ''}{summary.modules_invalid}{RESET}")
    print(f"  Success Rate:     {summary.success_rate:.1f}%")
    if summary.critical_errors > 0:
        print(f"  Critical Errors:  {RED}{summary.critical_errors}{RESET}")
    if summary.warnings > 0:
        print(f"  Warnings:         {YELLOW}{summary.warnings}{RESET}")

    if report.peripheral_validations:
        print(f"\n{BOLD}Module Results:{RESET}")
        for module_name, val in sorted(report.peripheral_validations.items()):
            status = f"{GREEN}OK{RESET}" if val.facts_mirror_valid else f"{RED}X{RESET}"
            print(f"  {status} {module_name:12s} - {val.constants_validated} constants, {val.mismatches} mismatches")
            if val.critical_errors:
                print(f"      {RED}Error: {val.critical_errors[0]}{RESET}")

    if report.compile_contract:
        cc = report.compile_contract
        status = f"{GREEN}PASS{RESET}" if cc.get("passes") else f"{RED}FAIL{RESET}"
        print(f"\n{BOLD}Compile Contract:{RESET} {status}")
        print(f"  Checks: {cc.get('checks', 0)}")
        if cc.get("errors"):
            print(f"  {RED}Errors: {len(cc['errors'])}{RESET}")
        if cc.get("warnings"):
            print(f"  {YELLOW}Warnings: {len(cc['warnings'])}{RESET}")

    if report.startup_contract:
        startup = report.startup_contract
        status = f"{GREEN}PASS{RESET}" if startup.get("passes") else f"{RED}FAIL{RESET}"
        print(f"\n{BOLD}Startup Contract:{RESET} {status}")

    if report.cross_file_validation:
        cross = report.cross_file_validation
        status = f"{GREEN}PASS{RESET}" if cross.get("passes") else f"{RED}FAIL{RESET}"
        print(f"\n{BOLD}Cross-File Validation:{RESET} {status}")
        print(f"  Consistency Score: {cross.get('consistency_score', 0.0):.1%}")

    if report.dependency_graph_info:
        dep = report.dependency_graph_info
        status = f"{RED}FAIL{RESET}" if dep.get("has_cycles") else f"{GREEN}PASS{RESET}"
        print(f"\n{BOLD}Dependency Graph:{RESET} {status}")

    print("\n" + "=" * 70 + "\n")


def save_validation_manifest(
    report: ValidationReport,
    output_dir: Path,
    filename: str = "validation_manifest.json",
) -> Path:
    manifest_path = output_dir / filename
    return write_json_report(report, manifest_path)


def update_module_test_status(
    report: ValidationReport,
    module_name: str,
    tests_generated: bool,
) -> None:
    if module_name in report.peripheral_validations:
        report.peripheral_validations[module_name].tests_generated = tests_generated
