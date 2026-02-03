#!/usr/bin/env python3
"""
extract_single_pdf.py

Utility script for extracting register definitions from a single TRM PDF.
Useful for testing, debugging, or processing specific peripherals.
"""

import asyncio
import sys
from pathlib import Path

import yaml

from modules.register_extraction_prompt import (
    build_register_extraction_system_prompt,
    build_register_extraction_user_prompt,
)
from modules.pdf_text_extractor import (
    extract_text_from_pdf,
    extract_peripheral_name_from_filename,
)
from modules.yaml_validator import (
    validate_yaml_against_schema,
)
from modules.yaml_formatter import format_regs_yaml_manual
from pdf_to_yaml_extractor import invoke_model, extract_yaml_from_response, Model


async def extract_single_pdf(
    pdf_path: Path,
    output_path: Path,
    schema_path: Path,
    model: Model = Model.SONNET_4_5,
    verbose: bool = True,
) -> bool:
    """
    Extract register definitions from a single PDF.

    Args:
        pdf_path: Path to PDF file
        output_path: Path to save YAML output
        schema_path: Path to regs.schema.yaml
        model: Model to use
        verbose: Print detailed progress

    Returns:
        True if successful, False otherwise
    """
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        return False

    if not schema_path.exists():
        print(f"Error: Schema not found: {schema_path}")
        return False

    # Extract peripheral name
    peripheral_abbrev, peripheral_full = extract_peripheral_name_from_filename(pdf_path.name)

    if verbose:
        print("=" * 80)
        print(f"Extracting registers from: {pdf_path.name}")
        print(f"Peripheral: {peripheral_abbrev} ({peripheral_full})")
        print(f"Model: {model.value}")
        print("=" * 80)

    try:
        # Step 1: Extract text
        if verbose:
            print("\n[1/4] Extracting text from PDF...")
        pdf_text = extract_text_from_pdf(pdf_path)

        if verbose:
            print(f"  Extracted {len(pdf_text)} characters")

        # Truncate if too long
        max_chars = 180000
        if len(pdf_text) > max_chars:
            if verbose:
                print(f"  Warning: Text is large, truncating to {max_chars} chars")
            pdf_text = pdf_text[:max_chars] + "\n\n[... content truncated ...]"

        # Step 2: Build prompts
        if verbose:
            print("\n[2/4] Building prompts...")

        schema_yaml_str = schema_path.read_text(encoding='utf-8')
        system_prompt = build_register_extraction_system_prompt()
        user_prompt = build_register_extraction_user_prompt(
            pdf_text=pdf_text,
            peripheral_name=peripheral_abbrev,
            schema_yaml=schema_yaml_str,
        )

        if verbose:
            print(f"  System prompt: {len(system_prompt)} chars")
            print(f"  User prompt: {len(user_prompt)} chars")

        # Step 3: Call Claude API
        if verbose:
            print("\n[3/4] Calling Claude API...")
            print("  (this may take 10-30 seconds)")

        response = await invoke_model(
            model=model,
            max_tokens=16000,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        if verbose:
            print(f"  Received response: {len(response)} chars")

        # Extract YAML
        yaml_content = extract_yaml_from_response(response)
        if yaml_content is None:
            print("Error: Failed to extract YAML from response")
            if verbose:
                print("\nRaw response:")
                print(response[:1000])
            return False

        # Step 4: Validate
        if verbose:
            print("\n[4/4] Validating YAML...")

        try:
            yaml_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            print(f"Error: Invalid YAML generated: {e}")
            return False

        schema = yaml.safe_load(schema_yaml_str)
        is_valid, validation_errors = validate_yaml_against_schema(yaml_data, schema)

        if is_valid:
            if verbose:
                print("  ✓ YAML is valid!")
        else:
            print(f"  ⚠ YAML has {len(validation_errors)} validation error(s):")
            for i, error in enumerate(validation_errors[:10], 1):
                print(f"    {i}. {error}")
            if len(validation_errors) > 10:
                print(f"    ... and {len(validation_errors) - 10} more errors")

        # Format YAML with inline field style
        if verbose:
            print("  Formatting YAML with inline fields...")
        try:
            formatted_yaml = format_regs_yaml_manual(yaml_data)
            yaml_content = formatted_yaml
        except Exception as e:
            if verbose:
                print(f"  Warning: Formatting failed ({e}), using original YAML")

        # Save output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml_content, encoding='utf-8')

        if verbose:
            print(f"\n✓ Saved to: {output_path}")

        # Print summary
        if verbose:
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)
            if 'peripherals' in yaml_data and yaml_data['peripherals']:
                for periph_name, periph_data in yaml_data['peripherals'].items():
                    reg_count = len(periph_data.get('registers', {}))
                    print(f"Peripheral: {periph_name}")
                    print(f"  Base Address: {periph_data.get('base_address', 'N/A')}")
                    print(f"  Registers: {reg_count}")

                    # Count total fields
                    total_fields = 0
                    for reg in periph_data.get('registers', {}).values():
                        total_fields += len(reg.get('fields', []))
                    print(f"  Total Fields: {total_fields}")
            print("=" * 80)

        return is_valid

    except Exception as e:
        print(f"Error during extraction: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python extract_single_pdf.py <pdf_file> [output_file]")
        print()
        print("Examples:")
        print("  python extract_single_pdf.py \"modules/pdfs/TRM_split/25 General-Purpose InputOutput GIO Module.pdf\"")
        print("  python extract_single_pdf.py \"modules/pdfs/TRM_split/10 Oscillator and PLL.pdf\" output/pll_regs.yaml")
        print()
        print("If output_file is not specified, uses yaml_out/extracted_regs/<peripheral>_regs.yaml")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    # Determine output path
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        # Auto-generate output filename
        peripheral_abbrev, _ = extract_peripheral_name_from_filename(pdf_path.name)
        output_dir = Path(__file__).parent / "yaml_out" / "extracted_regs"
        output_path = output_dir / f"{peripheral_abbrev.lower()}_regs.yaml"

    # Schema path
    schema_path = Path(__file__).parent / "yaml_schemas" / "regs.schema.yaml"

    # Run extraction
    success = asyncio.run(extract_single_pdf(
        pdf_path=pdf_path,
        output_path=output_path,
        schema_path=schema_path,
        model=Model.SONNET_4_5,
        verbose=True,
    ))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
