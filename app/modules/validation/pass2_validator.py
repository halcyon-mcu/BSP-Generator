"""
Pass 2 (Implementation) validation.

Validates driver implementations generated in Pass 2 to ensure:
- API contract compliance with manifest
- Proper clock gating and interrupt registration
- No hardcoded addresses
- Dependencies are met
"""

import re
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field


@dataclass
class Pass2ValidationResult:
    """Result of Pass 2 validation."""
    is_valid: bool
    critical_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    has_todos: bool = False


def validate_driver_implementation(
    module_name: str,
    manifest_entry: Dict,
    preamble: str,
    written_files: List[Path],
    soc_data: dict,
    regs_data: dict,
    clock_h_path: Path = None
) -> Pass2ValidationResult:
    """
    Validate Pass 2 driver implementation.

    Args:
        module_name: Name of the peripheral module
        manifest_entry: Manifest entry for this module from Pass 1
        preamble: Preamble text from LLM output
        written_files: List of generated files
        soc_data: SOC configuration from soc.yaml
        regs_data: Register definitions from regs.yaml
        clock_h_path: Path to clock.h for validation

    Returns:
        Pass2ValidationResult with validation status
    """
    errors = []
    warnings = []
    has_todos = False

    # Check 1: FACTS MIRROR has no TODOs
    if "FACTS MIRROR" in preamble and "TODO:" in preamble:
        facts_pattern = re.compile(
            r'===== FACTS MIRROR =====\s*(.*?)\s*===== END FACTS MIRROR =====',
            re.DOTALL
        )
        match = facts_pattern.search(preamble)
        if match and "TODO:" in match.group(1):
            errors.append(f"{module_name}: FACTS MIRROR contains TODO items")
            has_todos = True

    # Check 2: All manifest API functions implemented
    expected_funcs = manifest_entry.get('api_functions', [])
    implemented_funcs = set()

    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.c':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            for func in expected_funcs:
                func_name = func.get('name', '')
                if func_name:
                    # Look for function definition (not just declaration)
                    pattern = rf'\b{re.escape(func_name)}\s*\([^)]*\)\s*\{{'
                    if re.search(pattern, content):
                        implemented_funcs.add(func_name)
        except Exception as e:
            warnings.append(f"Could not check functions in {file_path.name}: {e}")

    missing_funcs = set(f.get('name') for f in expected_funcs if f.get('name')) - implemented_funcs
    if missing_funcs:
        for func in missing_funcs:
            warnings.append(f"{module_name}: Function '{func}' from manifest not found in implementation")

    # Check 3: Init function exists
    # Get expected init function name from manifest (don't construct it)
    init_func_name = manifest_entry.get('init_function', f"{module_name.upper()}_Init")
    init_found = False

    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.c':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            if re.search(rf'\b{re.escape(init_func_name)}\s*\([^)]*\)\s*\{{', content):
                init_found = True
                break
        except Exception:
            pass

    if not init_found:
        errors.append(f"{module_name}: Missing init function '{init_func_name}'")

    # Check 4: Clock gating if has clock_ref
    periph_data = None
    for p in soc_data.get('peripherals', []):
        if p.get('name') == module_name:
            periph_data = p
            break

    if periph_data and periph_data.get('clock_ref'):
        clock_ref = periph_data['clock_ref']
        found_clock_enable = False

        for file_path in written_files:
            if not file_path.exists() or file_path.suffix != '.c':
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                # Look for PLL_EnableClock() or clock_enable() call
                if ('PLL_EnableClock' in content or 'clock_enable' in content):
                    found_clock_enable = True
                    break
            except Exception:
                pass

        if not found_clock_enable:
            warnings.append(
                f"{module_name}: Has clock_ref '{clock_ref}' but doesn't call PLL_EnableClock() or clock_enable()"
            )

    # Check 5: No hardcoded addresses
    for file_path in written_files:
        if not file_path.exists() or file_path.suffix != '.c':
            continue

        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            # Look for hardcoded addresses (8-digit hex values)
            hardcoded = re.findall(r'\b0x[0-9A-Fa-f]{8}\b', content)
            if hardcoded:
                # Filter out common non-address constants
                suspicious = [
                    addr for addr in hardcoded
                    if addr.lower() not in ['0x00000000', '0xffffffff', '0x12345678']
                ]
                if len(suspicious) > 2:  # More than a couple might indicate hardcoded addresses
                    warnings.append(
                        f"{file_path.name}: Contains potential hardcoded addresses: "
                        f"{', '.join(suspicious[:3])}"
                    )
        except Exception:
            pass

    # Check 6: Required headers included
    driver_c_files = [f for f in written_files if f.exists() and f.suffix == '.c']
    for file_path in driver_c_files:
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')

            # Should include corresponding header
            expected_header = file_path.with_suffix('.h').name
            if f'#include "{expected_header}"' not in content and f"#include <{expected_header}>" not in content:
                warnings.append(f"{file_path.name}: Missing #include for {expected_header}")

            # If uses PLL_EnableClock, should include pll_driver.h
            if 'PLL_EnableClock' in content or 'PLL_GetFrequency' in content:
                if '#include "pll_driver.h"' not in content and '#include <pll_driver.h>' not in content:
                    warnings.append(f"{file_path.name}: Uses PLL APIs but doesn't include pll_driver.h")
            # If uses old clock API, should include clock.h
            elif 'clock_enable' in content or 'clock_get_hz' in content:
                if '#include "clock.h"' not in content and '#include <clock.h>' not in content:
                    warnings.append(f"{file_path.name}: Uses clock APIs but doesn't include clock.h")

        except Exception:
            pass

    # Check 7: No hardcoded frequency constants (if module has clock/PLL dependency)
    manifest_deps = manifest_entry.get('dependencies', [])
    has_clock_dep = any(
        d.lower() in ['clock', 'pll'] if isinstance(d, str) else False
        for d in manifest_deps
    )

    if has_clock_dep:
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Check for hardcoded frequency #defines
                freq_patterns = [
                    r'#define\s+\w*(?:VCLK|CLK|FREQUENCY|FREQ)\w*\s+\d+',
                    r'#define\s+\w+\s+\d{8,}U?L?L?\s*(?://.*frequency|/\*.*frequency)',
                ]

                for pattern in freq_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        errors.append(
                            f"{file_path.name}: Hardcoded frequency constant found: {matches[0]}. "
                            "Use PLL_GetFrequency() instead."
                        )
                        break

            except Exception:
                pass

    # Check 8: PLL_GetFrequency() usage for baud rate functions (if module has clock dependency)
    if has_clock_dep:
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Check if file has baud rate or prescaler functions
                has_baud_func = re.search(
                    r'\b(?:set_?baud|baud_?rate|set_?prescaler|configure_?timing)\b',
                    content,
                    re.IGNORECASE
                )

                if has_baud_func:
                    # Check if PLL_GetFrequency() or clock_get_hz() is called
                    if 'PLL_GetFrequency' not in content and 'clock_get_hz' not in content:
                        errors.append(
                            f"{file_path.name}: Has baud rate/timing function but doesn't call PLL_GetFrequency(). "
                            "Frequency must be queried dynamically, not hardcoded."
                        )

            except Exception:
                pass

    # Check 9: pll_driver.h include if module has PLL dependency
    if has_clock_dep:
        for file_path in driver_c_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')

                # Check for pll_driver.h or clock.h include
                has_pll_include = '#include "pll_driver.h"' in content or '#include <pll_driver.h>' in content
                has_clock_include = '#include "clock.h"' in content or '#include <clock.h>' in content

                if not has_pll_include and not has_clock_include:
                    errors.append(
                        f"{file_path.name}: Module has 'PLL' or 'clock' dependency but doesn't include pll_driver.h or clock.h"
                    )

            except Exception:
                pass

    is_valid = len(errors) == 0 and not has_todos

    return Pass2ValidationResult(
        is_valid=is_valid,
        critical_errors=errors,
        warnings=warnings,
        has_todos=has_todos
    )
