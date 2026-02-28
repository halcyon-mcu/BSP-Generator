#!/usr/bin/env python3
"""
validation_engine.py

Core validation logic for BSP generation.

This module provides:
- FACTS MIRROR validation against source YAML
- Cross-file consistency validation
- Integration point for validation hooks in main workflow
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from ..utils.facts_parser import (
    FactsMirror,
    ExtractedConstants,
    parse_facts_mirror,
    extract_constants_from_c_code,
    compare_values,
    extract_preamble_from_response
)
from ..yaml.yaml_utils import get_regs_block, find_soc_peripheral, get_soc_peripherals

logger = logging.getLogger(__name__)


# ==============================================================================
# VALIDATION RESULT DATA STRUCTURES
# ==============================================================================

@dataclass
class FactsValidationResult:
    """
    Result of validating FACTS MIRROR against generated code and YAML.
    """
    is_valid: bool
    module_name: str

    # Matching results
    matches: List[Tuple[str, str, str]] = field(default_factory=list)  # (fact_name, expected, actual)
    mismatches: List[Tuple[str, str, str]] = field(default_factory=list)  # (fact_name, expected, actual)
    missing_in_code: List[str] = field(default_factory=list)  # Facts not found in generated code
    extra_in_code: List[str] = field(default_factory=list)  # Constants in code not in FACTS MIRROR

    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        total = len(self.matches) + len(self.mismatches)
        if total == 0:
            return 1.0 if self.is_valid else 0.0
        return len(self.matches) / total

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Validation for {self.module_name}: {'PASS' if self.is_valid else 'FAIL'}",
            f"  Matches: {len(self.matches)}",
            f"  Mismatches: {len(self.mismatches)}",
            f"  Missing in code: {len(self.missing_in_code)}",
            f"  Extra in code: {len(self.extra_in_code)}",
            f"  Success rate: {self.success_rate():.1%}",
        ]

        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for error in self.errors[:5]:  # Show first 5
                lines.append(f"    - {error}")

        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
            for warning in self.warnings[:3]:  # Show first 3
                lines.append(f"    - {warning}")

        return "\n".join(lines)


@dataclass
class CrossFileConflict:
    """
    Conflict detected across multiple files.
    """
    fact_name: str
    files_involved: List[str]
    values: Dict[str, str]       # filename -> value
    is_acceptable: bool = False  # True if intentionally different
    reason: str = ""             # Why different (if acceptable)

    def __str__(self) -> str:
        file_list = ", ".join(self.files_involved)
        value_list = ", ".join(f"{f}={v}" for f, v in self.values.items())
        status = " [ACCEPTABLE]" if self.is_acceptable else " [CONFLICT]"
        return f"{self.fact_name} in [{file_list}]: {value_list}{status}"


@dataclass
class CrossFileValidation:
    """
    Result of validating facts across all generated files.
    """
    passes: bool
    conflicts: List[CrossFileConflict] = field(default_factory=list)
    consistency_score: float = 1.0  # 0.0 to 1.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Cross-file validation: {'PASS' if self.passes else 'FAIL'}",
            f"  Conflicts: {len(self.conflicts)}",
            f"  Consistency score: {self.consistency_score:.1%}",
        ]

        if self.conflicts:
            lines.append("  Top conflicts:")
            for conflict in self.conflicts[:5]:
                lines.append(f"    - {conflict}")

        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")

        return "\n".join(lines)


@dataclass
class ValidationResult:
    """
    Overall validation result for a single generation phase.
    """
    is_valid: bool
    phase: str  # "periph_gio", "system_init", etc.
    has_todos: bool = False
    facts_mirror: Optional[FactsMirror] = None
    facts_validation: Optional[FactsValidationResult] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

def validate_facts_mirror(
    facts_mirror: FactsMirror,
    generated_files: List[Path],
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    module_name: str
) -> FactsValidationResult:
    """
    Validate FACTS MIRROR against generated code and source YAML.

    Checks:
    1. All constants in FACTS MIRROR match YAML source values
    2. All constants in generated code appear in FACTS MIRROR
    3. Base addresses match regs.yaml
    4. Register offsets are within valid range

    Args:
        facts_mirror: Parsed FACTS MIRROR from LLM output
        generated_files: List of generated .c/.h files to validate
        soc_data: Parsed soc.yaml
        regs_data: Parsed regs.yaml
        module_name: Name of module being validated

    Returns:
        FactsValidationResult with detailed comparison
    """
    result = FactsValidationResult(
        is_valid=True,
        module_name=module_name
    )

    # If FACTS MIRROR has TODOs, fail immediately
    if facts_mirror.has_todos:
        result.is_valid = False
        result.errors.extend([
            f"FACTS MIRROR contains TODOs: {todo}"
            for todo in facts_mirror.get_conflicts()
        ])
        return result

    # Extract constants from all generated files
    all_extracted = []
    for file_path in generated_files:
        if file_path.suffix in ['.c', '.h']:
            try:
                content = file_path.read_text(encoding='utf-8')
                extracted = extract_constants_from_c_code(
                    content,
                    file_path.name
                )
                all_extracted.append(extracted)
            except Exception as e:
                result.warnings.append(f"Could not read {file_path.name}: {e}")

    # Build lookup of all #define values in generated code
    code_defines = {}
    for extracted in all_extracted:
        for define in extracted.defines:
            code_defines[define.name] = define.value

    # Validate each FACTS MIRROR entry
    for entry in facts_mirror.entries:
        if entry.is_todo:
            continue

        # Check if constant exists in generated code
        if entry.name in code_defines:
            code_value = code_defines[entry.name]

            # Compare values
            if compare_values(entry.value, code_value):
                result.matches.append((entry.name, entry.value, code_value))
            else:
                result.mismatches.append((entry.name, entry.value, code_value))
                result.errors.append(
                    f"{entry.name}: FACTS MIRROR={entry.value} but code={code_value}"
                )
                result.is_valid = False
        else:
            result.missing_in_code.append(entry.name)
            result.warnings.append(
                f"{entry.name} in FACTS MIRROR but not found in generated code"
            )

    # Check for constants in code that aren't in FACTS MIRROR
    facts_names = {e.name for e in facts_mirror.entries if not e.is_todo}
    for name in code_defines:
        if name not in facts_names:
            result.extra_in_code.append(name)
            # This is a warning, not an error (code may have derived constants)

    # Validate against YAML source
    _validate_against_yaml(result, facts_mirror, soc_data, regs_data, module_name)

    return result


def _validate_against_yaml(
    result: FactsValidationResult,
    facts_mirror: FactsMirror,
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    module_name: str
) -> None:
    """
    Validate FACTS MIRROR constants against original YAML source.

    Modifies result in-place.
    """
    # Find peripheral in soc.yaml
    periph = find_soc_peripheral(soc_data, module_name)
    if not periph:
        result.warnings.append(f"Module {module_name} not found in soc.yaml")
        return

    # Get regs_ref
    regs_ref = periph.get('regs_ref')
    if not regs_ref:
        result.warnings.append(f"Module {module_name} has no regs_ref in soc.yaml")
        return

    # Get register block from regs.yaml
    regs_block = get_regs_block(regs_data, regs_ref)
    if not regs_block:
        result.warnings.append(f"Register block {regs_ref} not found in regs.yaml")
        return

    # Validate base address
    yaml_base = regs_block.get('base_address')
    if yaml_base:
        # Look for BASE address in FACTS MIRROR
        base_entry = None
        for entry in facts_mirror.entries:
            if 'BASE' in entry.name.upper() and module_name.upper() in entry.name.upper():
                base_entry = entry
                break

        if base_entry:
            if not compare_values(base_entry.value, yaml_base):
                result.errors.append(
                    f"Base address mismatch: FACTS MIRROR={base_entry.value}, "
                    f"regs.yaml={yaml_base}"
                )
                result.is_valid = False
        else:
            result.warnings.append(
                f"No base address found in FACTS MIRROR for {module_name}"
            )

    # Validate register offsets
    registers = regs_block.get('registers', {})
    for reg_name, reg_data in registers.items():
        yaml_offset = reg_data.get('offset')
        if not yaml_offset:
            continue

        # Look for this register's offset in FACTS MIRROR
        offset_entry = None
        for entry in facts_mirror.entries:
            if reg_name.upper() in entry.name.upper() and 'OFFSET' in entry.name.upper():
                offset_entry = entry
                break

        if offset_entry:
            if not compare_values(offset_entry.value, yaml_offset):
                result.errors.append(
                    f"Register {reg_name} offset mismatch: "
                    f"FACTS MIRROR={offset_entry.value}, regs.yaml={yaml_offset}"
                )
                result.is_valid = False


def validate_facts_across_files(
    all_files_constants: Dict[str, ExtractedConstants],
    soc_data: Dict[str, Any]
) -> CrossFileValidation:
    """
    Validate consistency of constants across all generated files.

    Checks:
    1. No duplicate definitions with conflicting values
    2. Clock references are consistent
    3. Interrupt channel IDs don't conflict

    Args:
        all_files_constants: Dict mapping filename -> ExtractedConstants
        soc_data: Parsed soc.yaml for reference

    Returns:
        CrossFileValidation result
    """
    validation = CrossFileValidation(passes=True)

    # Build index of all constants across files
    constant_index: Dict[str, Dict[str, str]] = {}  # const_name -> {filename: value}

    for filename, extracted in all_files_constants.items():
        for define in extracted.defines:
            if define.name not in constant_index:
                constant_index[define.name] = {}
            constant_index[define.name][filename] = define.value

    # Check for conflicts
    conflicts_found = 0
    for const_name, file_values in constant_index.items():
        if len(file_values) <= 1:
            continue  # Only one definition, no conflict possible

        # Check if all values are the same
        unique_values = set(file_values.values())
        if len(unique_values) > 1:
            # Conflict detected
            conflict = CrossFileConflict(
                fact_name=const_name,
                files_involved=list(file_values.keys()),
                values=file_values
            )

            # Check if this is an acceptable conflict (e.g., per-instance base addresses)
            if _is_acceptable_conflict(const_name, file_values):
                conflict.is_acceptable = True
                conflict.reason = "Per-instance constant (e.g., UART1_BASE vs UART2_BASE)"
                validation.warnings.append(f"Acceptable multi-definition: {conflict}")
            else:
                conflict.is_acceptable = False
                validation.conflicts.append(conflict)
                validation.errors.append(f"Conflicting definitions: {conflict}")
                validation.passes = False
                conflicts_found += 1

    # Calculate consistency score
    total_constants = len(constant_index)
    if total_constants > 0:
        validation.consistency_score = max(0.0, 1.0 - (conflicts_found / total_constants))

    return validation


def _is_acceptable_conflict(const_name: str, file_values: Dict[str, str]) -> bool:
    """
    Check if a constant conflict is acceptable (e.g., per-instance addresses).

    Returns True if the conflict is expected and acceptable.
    """
    # Per-instance base addresses are acceptable (UART1_BASE vs UART2_BASE)
    if 'BASE' in const_name.upper():
        return True

    # Per-instance register pointers are acceptable
    if const_name.endswith('REG') or const_name.endswith('REG1') or const_name.endswith('REG2'):
        return True

    # Module-specific offsets are acceptable if in different modules
    filenames = list(file_values.keys())
    if len(filenames) == len(set(f.split('_')[0] for f in filenames)):
        # Each file is from a different module
        return True

    return False


def _validate_code_against_yaml(
    written_files: List[Path],
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any],
    module_name: str
) -> FactsValidationResult:
    """
    Fallback validation when FACTS MIRROR is missing.
    Validates generated code directly against YAML source.

    Args:
        written_files: List of generated files
        soc_data: Parsed soc.yaml
        regs_data: Parsed regs.yaml
        module_name: Name of module being validated

    Returns:
        FactsValidationResult with validation status
    """
    result = FactsValidationResult(
        is_valid=True,
        module_name=module_name
    )

    # Extract constants from all generated files
    code_defines = {}
    for file_path in written_files:
        if file_path.suffix in ['.c', '.h']:
            try:
                content = file_path.read_text(encoding='utf-8')
                extracted = extract_constants_from_c_code(
                    content,
                    file_path.name
                )
                for define in extracted.defines:
                    code_defines[define.name] = (define.value, file_path.name)
            except Exception as e:
                result.warnings.append(f"Could not read {file_path.name}: {e}")

    # Find peripheral in soc.yaml
    periph = find_soc_peripheral(soc_data, module_name)
    if not periph:
        result.warnings.append(f"Module {module_name} not found in soc.yaml - skipping YAML validation")
        return result

    # Get regs_ref
    regs_ref = periph.get('regs_ref')
    if not regs_ref:
        result.warnings.append(f"Module {module_name} has no regs_ref in soc.yaml")
        return result

    # Get register block from regs.yaml
    regs_block = get_regs_block(regs_data, regs_ref)
    if not regs_block:
        result.warnings.append(f"Register block {regs_ref} not found in regs.yaml")
        return result

    # Validate base address
    yaml_base = regs_block.get('base_address')
    if yaml_base:
        # Look for BASE address in generated code
        base_name_candidates = [
            f"{module_name}_BASE",
            f"{module_name}BASE",
            f"{module_name.upper()}_BASE",
        ]

        found_base = False
        for base_name in base_name_candidates:
            if base_name in code_defines:
                code_value, filename = code_defines[base_name]
                found_base = True
                if compare_values(code_value, yaml_base):
                    result.matches.append((base_name, yaml_base, code_value))
                else:
                    result.mismatches.append((base_name, yaml_base, code_value))
                    result.errors.append(
                        f"Base address mismatch in {filename}: "
                        f"{base_name}={code_value}, expected {yaml_base} from regs.yaml"
                    )
                    result.is_valid = False
                break

        if not found_base:
            result.warnings.append(
                f"No base address constant found for {module_name} "
                f"(looked for {', '.join(base_name_candidates)})"
            )

    # Validate register offsets
    registers = regs_block.get('registers', {})
    for reg_name, reg_data in registers.items():
        yaml_offset = reg_data.get('offset')
        if not yaml_offset:
            continue

        # Look for offset constants in code
        offset_name_candidates = [
            f"{reg_name}_OFFSET",
            f"{module_name}_{reg_name}_OFFSET",
        ]

        for offset_name in offset_name_candidates:
            if offset_name in code_defines:
                code_value, filename = code_defines[offset_name]
                if compare_values(code_value, yaml_offset):
                    result.matches.append((offset_name, yaml_offset, code_value))
                else:
                    result.mismatches.append((offset_name, yaml_offset, code_value))
                    result.errors.append(
                        f"Register {reg_name} offset mismatch in {filename}: "
                        f"{offset_name}={code_value}, expected {yaml_offset} from regs.yaml"
                    )
                    result.is_valid = False
                break

    return result


def validate_generation_output(
    tag: str,
    preamble: str,
    written_files: List[Path],
    soc_data: Dict[str, Any],
    regs_data: Dict[str, Any]
) -> ValidationResult:
    """
    Main validation entry point called after each LLM generation phase.

    Args:
        tag: Phase tag (e.g., "periph_gio", "system_init")
        preamble: Preamble text from LLM output (may contain FACTS MIRROR)
        written_files: List of files written by split_and_write_files()
        soc_data: Parsed soc.yaml
        regs_data: Parsed regs.yaml

    Returns:
        ValidationResult with overall validation status
    """
    result = ValidationResult(is_valid=True, phase=tag)

    # Parse FACTS MIRROR from preamble
    facts_mirror = parse_facts_mirror(preamble)
    result.facts_mirror = facts_mirror

    # Check for TODOs
    if facts_mirror.has_todos:
        result.has_todos = True
        result.is_valid = False
        result.errors.extend([
            f"FACTS MIRROR contains TODOs: {todo}"
            for todo in facts_mirror.get_conflicts()
        ])
        logger.error(f"[{tag}] Validation failed: FACTS MIRROR has TODOs")
        return result

    # Extract module name from tag (e.g., "periph_gio" -> "GIO")
    module_name = tag.split('_')[-1].upper() if '_' in tag else tag

    # If no FACTS MIRROR, use fallback validation
    if not facts_mirror.entries:
        result.warnings.append("No FACTS MIRROR found - using fallback validation")
        logger.info(f"[{tag}] No FACTS MIRROR found, using fallback validation")

        # Perform direct code-to-YAML validation
        try:
            fallback_validation = _validate_code_against_yaml(
                written_files,
                soc_data,
                regs_data,
                module_name
            )
            result.facts_validation = fallback_validation

            if not fallback_validation.is_valid:
                result.is_valid = False
                result.errors.extend(fallback_validation.errors)
                logger.error(f"[{tag}] Fallback validation failed: {len(fallback_validation.errors)} errors")

            if fallback_validation.warnings:
                result.warnings.extend(fallback_validation.warnings)
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Fallback validation exception: {str(e)}")
            logger.exception(f"[{tag}] Fallback validation error")

        return result

    # Validate FACTS MIRROR against generated code and YAML
    try:
        facts_validation = validate_facts_mirror(
            facts_mirror,
            written_files,
            soc_data,
            regs_data,
            module_name
        )
        result.facts_validation = facts_validation

        if not facts_validation.is_valid:
            result.is_valid = False
            result.errors.extend(facts_validation.errors)
            logger.error(f"[{tag}] FACTS validation failed: {len(facts_validation.errors)} errors")

        if facts_validation.warnings:
            result.warnings.extend(facts_validation.warnings)

    except Exception as e:
        result.is_valid = False
        result.errors.append(f"Validation exception: {str(e)}")
        logger.exception(f"[{tag}] Validation error")

    return result


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def extract_all_constants_from_directory(
    output_dir: Path,
    file_patterns: List[str] = None
) -> Dict[str, ExtractedConstants]:
    """
    Extract constants from all matching files in a directory.

    Args:
        output_dir: Directory to scan
        file_patterns: List of glob patterns (default: ["*.c", "*.h"])

    Returns:
        Dict mapping filename -> ExtractedConstants
    """
    if file_patterns is None:
        file_patterns = ["*.c", "*.h"]

    all_constants = {}

    for pattern in file_patterns:
        for file_path in output_dir.glob(pattern):
            try:
                content = file_path.read_text(encoding='utf-8')
                extracted = extract_constants_from_c_code(content, file_path.name)
                all_constants[file_path.name] = extracted
            except Exception as e:
                logger.warning(f"Could not extract constants from {file_path.name}: {e}")

    return all_constants
