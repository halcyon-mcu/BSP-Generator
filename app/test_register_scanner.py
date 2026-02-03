#!/usr/bin/env python3
"""
Test the register scanner on Architecture PDF to find SYS2 and other registers.
"""

from pathlib import Path
from modules.pdf_text_extractor import extract_text_from_pdf
from modules.register_scanner import scan_for_registers, format_scan_summary

# Path to Architecture PDF
pdf_path = Path("modules/pdfs/TRM_split/2_Architecture.pdf")

print("=" * 80)
print("Testing Register Scanner on Architecture PDF")
print("=" * 80)
print(f"PDF: {pdf_path}")
print()

if not pdf_path.exists():
    print(f"Error: PDF not found at {pdf_path}")
    exit(1)

# Extract text (full PDF, not just first 15 pages)
print("Extracting text from PDF (this may take a moment)...")
pdf_text = extract_text_from_pdf(pdf_path)
print(f"Extracted {len(pdf_text):,} characters")
print()

# Scan for registers
print("Scanning for register patterns...")
scan_results = scan_for_registers(pdf_text)

print()
print("=" * 80)
print("SCAN RESULTS")
print("=" * 80)
print(f"Total registers found: {scan_results['count']}")
print(f"Base address detected: {scan_results['base_address']}")
print(f"Has register map section: {scan_results['has_register_map']}")
print()

if scan_results['count'] > 0:
    print("Register list:")
    print("-" * 80)
    for i, reg in enumerate(scan_results['registers'], 1):
        print(f"{i:3d}. {reg['name']:<25s} @ {reg['offset']:<10s} {reg['access']:<5s} Reset: {reg.get('reset', 'N/A')}")

    print()
    print("=" * 80)

    # Check for specific registers
    register_names = set(scan_results['register_names'])

    check_regs = ['SYS_PC', 'SYS_PCR', 'SYS2', 'CLKCNTL', 'PLLCTL1', 'LPOMONCTL']
    print("\nChecking for specific registers:")
    for reg in check_regs:
        status = "✓ FOUND" if reg in register_names else "✗ NOT FOUND"
        print(f"  {reg:<20s}: {status}")

    print()
    print("=" * 80)
    print("Formatted summary (for Claude prompt):")
    print("=" * 80)
    print(format_scan_summary(scan_results))

else:
    print("⚠ No registers found by scanner")
    print("This could mean:")
    print("  - PDF doesn't contain register tables")
    print("  - Register format doesn't match patterns")
    print("  - Text extraction lost structure")

print()
print("=" * 80)
print("Done!")
print("=" * 80)
