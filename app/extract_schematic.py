#!/usr/bin/env python3
"""
extract_schematic.py

Extract board-level information from RM46 schematic PDF for BSP integration.
"""

from pathlib import Path
import fitz  # PyMuPDF
import yaml
from datetime import datetime

def extract_schematic_text(pdf_path: Path) -> str:
    """Extract all text from schematic PDF with page context."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(str(pdf_path))
    text_parts = []

    print(f"Extracting text from {doc.page_count} pages...")

    for page_num in range(doc.page_count):
        page = doc[page_num]

        # Try to get text with layout preservation
        page_text = page.get_text("text")

        # Add page separator
        text_parts.append(f"\n{'='*80}\n")
        text_parts.append(f"SCHEMATIC PAGE {page_num + 1}\n")
        text_parts.append(f"{'='*80}\n\n")
        text_parts.append(page_text)

    doc.close()
    return "".join(text_parts)

def extract_schematic_images(pdf_path: Path, output_dir: Path):
    """Extract images from schematic for visual analysis."""
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))

    print(f"Extracting images from {doc.page_count} pages...")

    image_count = 0
    for page_num in range(doc.page_count):
        page = doc[page_num]

        # Render page as image for better analysis
        # 2x zoom for better quality
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)

        image_path = output_dir / f"schematic_page_{page_num + 1}.png"
        pix.save(str(image_path))
        image_count += 1
        print(f"  Saved: {image_path}")

    doc.close()
    return image_count

def main():
    # Paths
    repo_root = Path(__file__).parent.parent
    schematic_pdf = repo_root / "app" / "input_docs" / "RM46_schematic.pdf"
    output_dir = repo_root / "app" / "schematic_extracted"
    text_output = output_dir / "schematic_text.txt"

    print(f"Schematic PDF: {schematic_pdf}")
    print(f"Output directory: {output_dir}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract text
    print("\n" + "="*80)
    print("EXTRACTING TEXT")
    print("="*80)
    schematic_text = extract_schematic_text(schematic_pdf)

    # Save text
    with open(text_output, 'w', encoding='utf-8') as f:
        f.write(schematic_text)
    print(f"\nText saved to: {text_output}")
    print(f"Text length: {len(schematic_text)} characters")

    # Extract images
    print("\n" + "="*80)
    print("EXTRACTING IMAGES")
    print("="*80)
    image_count = extract_schematic_images(schematic_pdf, output_dir)
    print(f"\nExtracted {image_count} schematic pages as images")

    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
    print(f"\nNext steps:")
    print(f"1. Review extracted text: {text_output}")
    print(f"2. Review schematic images in: {output_dir}")
    print(f"3. Manually analyze schematics to extract component information")

if __name__ == "__main__":
    main()
