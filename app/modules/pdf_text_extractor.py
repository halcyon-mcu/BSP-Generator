#!/usr/bin/env python3
"""
pdf_text_extractor.py

Utilities for extracting text content from TRM PDFs for register extraction.
Uses PyMuPDF (fitz) to parse PDF pages and extract structured text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Tuple

import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: Path, max_pages: Optional[int] = None) -> str:
    """
    Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        max_pages: Optional limit on number of pages to extract (for testing)

    Returns:
        Extracted text as a single string

    Raises:
        FileNotFoundError: If PDF doesn't exist
        ValueError: If PDF cannot be opened
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        raise ValueError(f"Failed to open PDF {pdf_path}: {e}")

    text_parts = []
    page_limit = min(doc.page_count, max_pages) if max_pages else doc.page_count

    for page_num in range(page_limit):
        page = doc[page_num]
        page_text = page.get_text("text")

        # Add page separator for context
        text_parts.append(f"\n{'='*80}\n")
        text_parts.append(f"PAGE {page_num + 1}\n")
        text_parts.append(f"{'='*80}\n\n")
        text_parts.append(page_text)

    doc.close()
    return "".join(text_parts)


def extract_peripheral_name_from_filename(pdf_filename: str) -> Tuple[str, str]:
    """
    Extract peripheral name from TRM PDF filename.

    TRM split PDFs typically have names like:
    - "25 General-Purpose InputOutput GIO Module.pdf"
    - "10 Oscillator and PLL.pdf"
    - "28 Serial Communication Interface SCI Local Interconnect Network LIN Module.pdf"

    Args:
        pdf_filename: Name of the PDF file (with or without .pdf extension)

    Returns:
        Tuple of (abbreviated_name, full_name)
        - abbreviated_name: Short identifier (e.g., "GIO", "PLL", "SCI_LIN")
        - full_name: Full peripheral name from filename

    Examples:
        "25 General-Purpose InputOutput GIO Module.pdf" -> ("GIO", "General-Purpose InputOutput GIO Module")
        "10 Oscillator and PLL.pdf" -> ("PLL", "Oscillator and PLL")
        "15 Vectored Interrupt Manager VIM Module.pdf" -> ("VIM", "Vectored Interrupt Manager VIM Module")
    """
    # Remove .pdf extension if present
    name = pdf_filename
    if name.lower().endswith('.pdf'):
        name = name[:-4]

    # Remove leading chapter number (e.g., "25 " or "25_" -> "")
    # Handle both space and underscore separators
    name = re.sub(r'^\d+[\s_]+', '', name)

    # Remove trailing "Module" or "module" (with space or underscore)
    full_name = re.sub(r'[\s_]+[Mm]odule\s*$', '', name).strip()

    # Try to extract abbreviated name from common patterns
    abbreviated = _extract_abbreviated_name(full_name)

    return abbreviated, full_name


def _extract_abbreviated_name(full_name: str) -> str:
    """
    Extract abbreviated peripheral name from full name.

    Looks for (in priority order):
    1. Special case: Architecture PDFs -> "SYSTEM" (contains system registers)
    2. Abbreviations in parentheses (e.g., "System Module (SYS)" -> "SYS")
    3. Uppercase acronyms (e.g., "GIO", "VIM", "DMA")
    4. CamelCase abbreviations (e.g., "MibSPI")
    5. Last significant word if no acronym found

    Args:
        full_name: Full peripheral name

    Returns:
        Abbreviated name (uppercase)
    """
    # PRIORITY 0: Special case for Architecture PDFs
    # Architecture PDFs contain SYSTEM and SYSTEM2 register blocks
    if 'architecture' in full_name.lower():
        return 'SYSTEM'

    # PRIORITY 1: Words in parentheses (most explicit abbreviation)
    # e.g., "System Module (SYS)" -> "SYS"
    # e.g., "Vectored Interrupt Manager (VIM)" -> "VIM"
    paren_pattern = r'\(([^)]+)\)'
    paren_matches = re.findall(paren_pattern, full_name)
    if paren_matches:
        for match in paren_matches:
            # Check if it looks like an abbreviation
            # Accept uppercase acronyms or mixed case like "ePWM"
            match_stripped = match.strip()
            if 2 <= len(match_stripped) <= 8:
                # If mostly uppercase or starts with lowercase and has uppercase
                if match_stripped.isupper() or (match_stripped[0].islower() and any(c.isupper() for c in match_stripped)):
                    return match_stripped.upper()

    # PRIORITY 2: Standalone uppercase acronyms (2-6 letters)
    # e.g., "General-Purpose InputOutput GIO Module" -> "GIO"
    acronym_pattern = r'(?:^|[\s_\-])([A-Z]{2,6})(?:[\s_\-]|$)'
    acronyms = re.findall(acronym_pattern, full_name)

    # Filter out common false positives
    excluded = {'AND', 'OR', 'THE', 'TO', 'FOR', 'WITH', 'MODULE', 'CONTROLLER'}
    acronyms = [a for a in acronyms if a not in excluded]

    if acronyms:
        # Prefer acronyms that appear at the end or are longer
        # Last acronym is usually the peripheral abbreviation
        return acronyms[-1]

    # PRIORITY 3: CamelCase abbreviations
    # e.g., "MibSPI" or "ePWM"
    camel_pattern = r'(?:^|[\s_\-])([a-z]*[A-Z][a-zA-Z]{1,5})(?:[\s_\-]|$)'
    camel_matches = re.findall(camel_pattern, full_name)
    if camel_matches:
        return camel_matches[-1].upper()

    # PRIORITY 4: Last significant word (fallback)
    # Split on space, underscore, or hyphen
    words = re.split(r'[\s_\-]+', full_name)
    if words:
        # Find last significant word (not 'module', 'controller', etc.)
        for word in reversed(words):
            word = word.strip()
            if word and word.lower() not in ['module', 'controller', 'interface']:
                return word.upper()

    # Ultimate fallback: use full name uppercased, replace spaces/hyphens with underscores
    # Keep it short by taking first 20 chars
    fallback = full_name.upper().replace(' ', '_').replace('-', '_')
    return fallback[:20] if len(fallback) > 20 else fallback


def should_skip_pdf(filename: str, pdf_path: Optional[Path] = None) -> bool:
    """
    Determine if a PDF should be skipped (not a peripheral chapter).

    Skips:
    - Introduction, Preface, Table of Contents
    - Revision History, Important Notice, History
    - Appendices, Abstract, Overview chapters
    - Device information, ordering information

    Special handling:
    - Architecture PDFs: Only process if they contain system registers

    Args:
        filename: PDF filename
        pdf_path: Optional path to PDF file (for content-based checks)

    Returns:
        True if PDF should be skipped, False if it should be processed
    """
    filename_lower = filename.lower()

    # Special case: Architecture PDFs may contain system registers
    # Check content before skipping
    if 'architecture' in filename_lower:
        if pdf_path and pdf_path.exists():
            try:
                # Quick check for system register keywords
                text = extract_text_from_pdf(pdf_path, max_pages=15)
                text_lower = text.lower()

                # Look for system register indicators
                has_system_regs = any(keyword in text_lower for keyword in [
                    'system register',
                    'system control',
                    'sys_pc',
                    'sys_pcr',
                    'system control register',
                    'peripheral frame',
                    'sysctrl',  # Additional keyword
                    'system module',
                ])

                if has_system_regs:
                    # Don't skip - contains system registers
                    print(f"  -> Processing Architecture PDF (contains system registers)")
                    return False
                else:
                    # No system registers found
                    print(f"  -> Skipping Architecture PDF (no system registers detected in first 15 pages)")
                    return True
            except Exception as e:
                print(f"  -> Error checking Architecture PDF content: {e}")
                pass  # If check fails, fall through to skip

        # Skip architecture PDFs that don't have system registers
        return True

    skip_keywords = [
        'introduction',
        'preface',
        'table of contents',
        'table_of_contents',
        'toc',
        'revision history',
        'revision_history',
        'history',  # Catch general history PDFs
        'important notice',
        'important_notice',
        'notice',
        'appendix',
        'appendices',
        'index',
        'glossary',
        'abstract',
        'overview',  # Generic overview chapters without peripheral details
        'device_information',
        'device information',
        'ordering_information',
        'ordering information',
        'specifications',  # Generic specs without registers
        'references',
        'bibliography',
    ]

    for keyword in skip_keywords:
        if keyword in filename_lower:
            return True

    return False


def validate_pdf_for_register_extraction(pdf_path: Path) -> Tuple[bool, str]:
    """
    Quick validation to check if a PDF likely contains register information.

    NOTE: This validation is now VERY PERMISSIVE by default since many
    peripheral PDFs have register information deeper in the document
    (pages 15-20+), not in the first few pages.

    Looks for common indicators like:
    - "Register Map" or "Memory Map" sections
    - Hex addresses (0x...)
    - Register names and offsets

    Args:
        pdf_path: Path to PDF file

    Returns:
        Tuple of (is_valid, reason)
        - is_valid: True if PDF appears to contain register info
        - reason: Explanation string
    """
    try:
        # Extract first 20 pages to check content (increased from 10)
        # Many peripheral chapters have intro/overview before register tables
        text = extract_text_from_pdf(pdf_path, max_pages=20)
        text_lower = text.lower()

        # Positive indicators (expanded keywords)
        has_register_map = any(keyword in text_lower for keyword in [
            'register map',
            'memory map',
            'register summary',
            'register description',
            'control register',
            'status register',
            'configuration register',
        ])

        has_hex_addresses = bool(re.search(r'0x[0-9A-Fa-f]{4,8}', text))

        has_offset_column = 'offset' in text_lower

        # Be VERY permissive - process unless clearly not a peripheral
        if has_register_map:
            return True, "Contains register keywords"

        if has_hex_addresses and has_offset_column:
            return True, "Contains offsets and hex addresses"

        if has_hex_addresses:
            return True, "Contains hex addresses (likely registers)"

        # Even without clear indicators, still try to extract
        # Claude can determine if registers are present
        # Only skip if validation is explicitly enabled
        return True, "Will attempt extraction (validation is permissive)"

    except Exception as e:
        return False, f"Error reading PDF: {e}"


# Example usage and testing
if __name__ == "__main__":
    # Test peripheral name extraction
    test_files = [
        "25 General-Purpose InputOutput GIO Module.pdf",
        "10 Oscillator and PLL.pdf",
        "15 Vectored Interrupt Manager VIM Module.pdf",
        "28 Serial Communication Interface SCI Local Interconnect Network LIN Module.pdf",
        "13 Real-Time Interrupt RTI Module.pdf",
    ]

    print("Testing peripheral name extraction:")
    print("=" * 80)
    for filename in test_files:
        abbrev, full = extract_peripheral_name_from_filename(filename)
        print(f"File: {filename}")
        print(f"  Abbreviated: {abbrev}")
        print(f"  Full Name: {full}")
        print()
