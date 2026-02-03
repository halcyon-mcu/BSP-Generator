#!/usr/bin/env python3
"""
register_scanner.py

Pre-scan PDF text for register patterns using regex.
Helps catch registers that Claude might miss or verify extraction completeness.
"""

import re
from typing import Dict, List, Any, Tuple


def scan_for_registers(pdf_text: str) -> Dict[str, Any]:
    """
    Pre-scan PDF text for register patterns before sending to Claude.

    Looks for:
    - Register map tables with offsets
    - Register section headers
    - Base addresses

    Args:
        pdf_text: Extracted text from PDF

    Returns:
        Dictionary with:
        - registers: List of found registers with offset, name, access
        - count: Number of registers found
        - register_names: List of register names only
        - has_register_map: Whether a register map section was found
        - base_address: Detected base address if found
    """
    registers_found = []
    register_names_set = set()  # Track unique names

    # Pattern 1: Register map tables (most common)
    # Format: "0x00    SYS_PC      System PC Register       RW      0x00000000"
    # Or:     "00h     GIOGCR0     GIO Global Control       R/W     0000 0000h"
    table_patterns = [
        # Hex with 0x prefix: "0x00  SYS_PC  ...  RW  0x00000000"
        r'(0x[0-9A-Fa-f]+)\s+([A-Z][A-Z0-9_]{1,20})\s+.*?\s+(R[OW/]{1,3}|WO|RWC?)\s+(0x[0-9A-Fa-f]+)?',

        # Hex without 0x: "00h  SYS_PC  ...  R/W  0000h"
        r'([0-9A-Fa-f]+h)\s+([A-Z][A-Z0-9_]{1,20})\s+.*?\s+(R[OW/]{1,3}|WO|RWC?)\s+([0-9A-Fa-f]+h)?',

        # Decimal: "0  SYS_PC  ...  RW"
        r'\b(\d+)\s+([A-Z][A-Z0-9_]{1,20})\s+.*?\s+(R[OW/]{1,3}|WO|RWC?)',
    ]

    for pattern in table_patterns:
        for match in re.finditer(pattern, pdf_text, re.MULTILINE):
            offset = match.group(1)
            name = match.group(2)
            access = match.group(3)
            reset = match.group(4) if len(match.groups()) >= 4 else None

            # Filter out common false positives
            if name in ['TABLE', 'REGISTER', 'OFFSET', 'ADDRESS', 'TYPE', 'RESET', 'NAME']:
                continue

            # Normalize offset to 0x format
            if offset.endswith('h'):
                offset = '0x' + offset[:-1].upper().zfill(2)
            elif not offset.startswith('0x'):
                offset = f'0x{int(offset):02X}'

            # Normalize access mode
            access = access.replace('/', '').upper()
            if access == 'R':
                access = 'RO'

            if name not in register_names_set:
                register_names_set.add(name)
                registers_found.append({
                    'name': name,
                    'offset': offset,
                    'access': access,
                    'reset': reset,
                })

    # Pattern 2: Register section headers
    # Format: "SYS_PC Register (Offset 0x00)"
    # Or:     "SYS_PC (address offset 00h)"
    header_patterns = [
        r'([A-Z][A-Z0-9_]{1,20})\s+Register\s+(?:\()?(?:Offset|offset|Address|address)?\s*(0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h)',
        r'([A-Z][A-Z0-9_]{1,20})\s+\((?:address\s+)?(?:offset\s+)?(0x[0-9A-Fa-f]+|[0-9A-Fa-f]+h)',
    ]

    for pattern in header_patterns:
        for match in re.finditer(pattern, pdf_text, re.IGNORECASE):
            name = match.group(1).upper()
            offset = match.group(2)

            if name in ['TABLE', 'REGISTER', 'OFFSET', 'ADDRESS']:
                continue

            # Normalize offset
            if offset.endswith('h'):
                offset = '0x' + offset[:-1].upper().zfill(2)
            elif not offset.startswith('0x'):
                offset = '0x' + offset.upper()

            if name not in register_names_set:
                register_names_set.add(name)
                registers_found.append({
                    'name': name,
                    'offset': offset,
                    'access': 'RW',  # Default
                })

    # Pattern 3: Base address detection
    # Format: "Base Address: 0xFFF7BC00"
    # Or:     "Peripheral Base: 0xFFF7BC00"
    # Or:     "Module Base Address = 0xFFF7_BC00"
    base_address = None
    base_patterns = [
        r'(?:Base Address|Peripheral Base|Module Base Address)\s*[:=]\s*(0x[0-9A-Fa-f_]+)',
        r'(?:mapped at|located at)\s+(?:address\s+)?(0x[0-9A-Fa-f_]+)',
    ]

    for pattern in base_patterns:
        match = re.search(pattern, pdf_text, re.IGNORECASE)
        if match:
            base_address = match.group(1).replace('_', '').upper()
            break

    # Check if register map section exists
    has_register_map = any(keyword in pdf_text.lower() for keyword in [
        'register map',
        'register summary',
        'memory map',
        'register description',
    ])

    return {
        'registers': registers_found,
        'count': len(registers_found),
        'register_names': sorted(register_names_set),
        'has_register_map': has_register_map,
        'base_address': base_address,
    }


def validate_extraction(
    scanned: Dict[str, Any],
    extracted_yaml: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Validate Claude's extraction against pre-scan results.

    Args:
        scanned: Results from scan_for_registers()
        extracted_yaml: Parsed YAML from Claude

    Returns:
        Tuple of (is_valid, warnings)
        - is_valid: True if extraction looks reasonable
        - warnings: List of warning messages about discrepancies
    """
    warnings = []

    if not extracted_yaml or 'peripherals' not in extracted_yaml:
        return False, ["No peripherals found in extracted YAML"]

    # Get extracted register names
    extracted_regs = set()
    for periph_name, periph_data in extracted_yaml['peripherals'].items():
        if 'registers' in periph_data:
            extracted_regs.update(periph_data['registers'].keys())

    scanned_regs = set(scanned['register_names'])

    # Check for significant discrepancies
    if scanned['count'] > 0:
        missing_from_extraction = scanned_regs - extracted_regs
        extra_in_extraction = extracted_regs - scanned_regs

        # Warning if > 30% of scanned registers are missing
        if len(missing_from_extraction) > scanned['count'] * 0.3:
            warnings.append(
                f"Missing {len(missing_from_extraction)}/{scanned['count']} scanned registers: "
                f"{', '.join(sorted(list(missing_from_extraction))[:5])}"
            )

        # Info if extraction found more (might be good or false positives)
        if len(extra_in_extraction) > 5:
            warnings.append(
                f"Extraction found {len(extra_in_extraction)} additional registers not in pre-scan"
            )

        # Warning if extraction found way fewer registers
        if len(extracted_regs) < scanned['count'] * 0.5:
            warnings.append(
                f"Extraction found only {len(extracted_regs)} registers vs {scanned['count']} in pre-scan"
            )

    is_valid = len(warnings) == 0 or scanned['count'] == 0
    return is_valid, warnings


def format_scan_summary(scan_results: Dict[str, Any]) -> str:
    """
    Format scan results for inclusion in prompt to Claude.

    Args:
        scan_results: Results from scan_for_registers()

    Returns:
        Formatted string for prompt enhancement
    """
    if scan_results['count'] == 0:
        return ""

    summary = f"""
REGISTER PRE-SCAN RESULTS:
The following {scan_results['count']} registers were detected in the PDF:

"""

    # Show first 20 registers
    for reg in scan_results['registers'][:20]:
        summary += f"  - {reg['name']:<20s} (offset: {reg['offset']}, access: {reg['access']})\n"

    if scan_results['count'] > 20:
        summary += f"  ... and {scan_results['count'] - 20} more registers\n"

    summary += f"""
IMPORTANT: Ensure ALL of these registers are included in your extraction.
If you cannot find details for some registers, include them with basic information.
"""

    if scan_results['base_address']:
        summary += f"\nDetected base address: {scan_results['base_address']}\n"

    return summary


# Example usage and testing
if __name__ == "__main__":
    # Test with sample text
    sample_text = """
    Register Map

    Table 5-1. System Module Registers

    Offset  Acronym      Register Name               Type    Reset Value
    0x00    SYS_PC       System PC Register          RW      0x00000000
    0x04    SYS_PCR      System Peripheral Control   RW      0x00000001
    0x08    SYS_PCR2     System Peripheral Control 2 RW      0x00000000
    0x20    SYS_CLKCNTL  Clock Control Register      RW      0x00000100

    Base Address: 0xFFFFFF00
    """

    print("Testing register scanner:")
    print("=" * 80)

    results = scan_for_registers(sample_text)

    print(f"Registers found: {results['count']}")
    print(f"Base address: {results['base_address']}")
    print(f"Has register map: {results['has_register_map']}")
    print()

    print("Register details:")
    for reg in results['registers']:
        print(f"  {reg['name']:<20s} @ {reg['offset']:<10s} {reg['access']:<5s}")

    print()
    print("Formatted summary for prompt:")
    print(format_scan_summary(results))
    print("=" * 80)
