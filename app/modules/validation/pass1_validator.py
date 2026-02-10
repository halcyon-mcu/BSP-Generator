"""
Pass 1 (Discovery) validation.

Validates register headers and manifests generated in Pass 1 before
proceeding to Pass 2 implementation.
"""

import re
from pathlib import Path
from typing import List
from dataclasses import dataclass, field


@dataclass
class Pass1ValidationResult:
    """Result of Pass 1 validation."""
    is_valid: bool
    critical_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    has_todos: bool = False


def validate_register_header(
    module_name: str,
    preamble: str,
    written_files: List[Path],
    regs_data: dict
) -> Pass1ValidationResult:
    """
    Validate Pass 1 register header generation.

    Args:
        module_name: Name of the peripheral module
        preamble: Preamble text from LLM output
        written_files: List of generated files
        regs_data: Register definitions from regs.yaml

    Returns:
        Pass1ValidationResult with validation status
    """
    errors = []
    warnings = []
    has_todos = False

    # Check 1: FACTS MIRROR has no TODOs
    if "FACTS MIRROR" in preamble and "TODO:" in preamble:
        # Extract FACTS MIRROR block to verify TODO is actually in it
        facts_pattern = re.compile(
            r'===== FACTS MIRROR =====\s*(.*?)\s*===== END FACTS MIRROR =====',
            re.DOTALL
        )
        match = facts_pattern.search(preamble)
        if match and "TODO:" in match.group(1):
            errors.append(f"{module_name}: FACTS MIRROR contains TODO items")
            has_todos = True

    # Check 2: Base address matches YAML
    periph_data = regs_data.get('peripherals', {}).get(module_name, {})
    yaml_base = periph_data.get('base_address')

    if yaml_base:
        # Search for base address #define in generated files
        for file_path in written_files:
            if not file_path.exists() or file_path.suffix != '.h':
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                base_define = f"#define {module_name.upper()}_BASE"

                if base_define in content:
                    # Extract value
                    pattern = rf"{base_define}\s+(0x[0-9A-Fa-f]+)"
                    match = re.search(pattern, content)
                    if match:
                        code_base = match.group(1)
                        # Normalize for comparison (handle case differences)
                        if code_base.lower() != yaml_base.lower():
                            errors.append(
                                f"{module_name}: Base address mismatch - "
                                f"YAML: {yaml_base}, Code: {code_base}"
                            )
            except Exception as e:
                warnings.append(f"Could not validate {file_path.name}: {e}")

    # Check 3: Header guards present
    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.h':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if "#ifndef" not in content or "#define" not in content:
                warnings.append(f"{file_path.name}: Missing header guards")
        except Exception as e:
            warnings.append(f"Could not check header guards in {file_path.name}: {e}")

    # Check 4: No hardcoded addresses in generated code
    for file_path in written_files:
        if not file_path.exists():
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Look for standalone hex addresses that might be hardcoded
            # Pattern: 0x followed by 8 hex digits (typical peripheral base addresses)
            hardcoded = re.findall(r'\b0x[0-9A-Fa-f]{8}\b', content)
            if hardcoded:
                # Filter out common non-address constants
                suspicious = [addr for addr in hardcoded if addr.lower() not in ['0x00000000', '0xffffffff']]
                if suspicious:
                    warnings.append(
                        f"{file_path.name}: Contains potential hardcoded addresses: "
                        f"{', '.join(suspicious[:3])}"
                    )
        except Exception as e:
            pass  # Silently skip validation errors

    is_valid = len(errors) == 0 and not has_todos

    return Pass1ValidationResult(
        is_valid=is_valid,
        critical_errors=errors,
        warnings=warnings,
        has_todos=has_todos
    )
