#!/usr/bin/env python3
"""
Quick test to check Architecture PDF system register detection.
"""

from pathlib import Path
from modules.pdf_text_extractor import extract_text_from_pdf, should_skip_pdf

# Path to Architecture PDF
pdf_path = Path("modules/pdfs/TRM_split/2_Architecture.pdf")

print("=" * 80)
print("Testing Architecture PDF Detection")
print("=" * 80)
print(f"PDF: {pdf_path}")
print()

# Test should_skip_pdf function
should_skip = should_skip_pdf(pdf_path.name, pdf_path)
print(f"Should skip: {should_skip}")
print()

# Extract first 15 pages and check keywords
print("Checking first 15 pages for system register keywords...")
text = extract_text_from_pdf(pdf_path, max_pages=15)
text_lower = text.lower()

keywords = [
    'system register',
    'system control',
    'sys_pc',
    'sys_pcr',
    'system control register',
    'peripheral frame',
    'sysctrl',
    'system module',
]

print("\nKeyword search results:")
for keyword in keywords:
    if keyword in text_lower:
        # Find first occurrence for context
        idx = text_lower.find(keyword)
        context_start = max(0, idx - 50)
        context_end = min(len(text), idx + 50)
        context = text[context_start:context_end].replace('\n', ' ')
        print(f"  [FOUND] '{keyword}'")
        print(f"    Context: ...{context}...")
    else:
        print(f"  [NOT FOUND] '{keyword}'")

print()

# Search for variations
print("Searching for variations:")
variations = ['system', 'register', 'control', 'peripheral']
for var in variations:
    count = text_lower.count(var)
    print(f"  '{var}': {count} occurrences")

print()
print("=" * 80)
