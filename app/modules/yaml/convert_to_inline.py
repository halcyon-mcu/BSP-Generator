#!/usr/bin/env python3
"""
convert_yaml_to_inline.py

Utility to convert existing register YAML files to inline field format.
Useful for:
- Converting generated YAML files to match project style
- Reformatting manually edited YAML files
- Batch converting multiple files
"""

import sys
from pathlib import Path

import yaml

from .yaml_formatter import format_regs_yaml_manual


def convert_file(input_path: Path, output_path: Path = None, verbose: bool = True):
    """
    Convert a single YAML file to inline field format.

    Args:
        input_path: Input YAML file
        output_path: Output file (defaults to overwriting input)
        verbose: Print progress messages
    """
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return False

    if output_path is None:
        output_path = input_path

    try:
        # Load YAML
        if verbose:
            print(f"Loading: {input_path}")

        with input_path.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Format with inline fields
        if verbose:
            print("  Formatting with inline fields...")

        formatted = format_regs_yaml_manual(data)

        # Save
        with output_path.open('w', encoding='utf-8') as f:
            f.write(formatted)

        if verbose:
            print(f"  ✓ Saved to: {output_path}")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def convert_directory(input_dir: Path, output_dir: Path = None, pattern: str = "*.yaml"):
    """
    Convert all YAML files in a directory.

    Args:
        input_dir: Input directory
        output_dir: Output directory (defaults to same as input)
        pattern: File pattern to match (default: *.yaml)
    """
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Directory not found: {input_dir}")
        return

    if output_dir is None:
        output_dir = input_dir
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    yaml_files = list(input_dir.glob(pattern))

    if not yaml_files:
        print(f"No files matching '{pattern}' found in {input_dir}")
        return

    print(f"Found {len(yaml_files)} YAML files to convert")
    print("=" * 80)

    success_count = 0
    fail_count = 0

    for yaml_file in yaml_files:
        output_file = output_dir / yaml_file.name
        if convert_file(yaml_file, output_file, verbose=True):
            success_count += 1
        else:
            fail_count += 1
        print()

    print("=" * 80)
    print(f"Conversion complete: {success_count} succeeded, {fail_count} failed")


def show_example():
    """Show example of block vs inline style."""
    block_style = """registers:
  GCR0:
    offset: "0x00"
    access: RW
    fields:
      - name: RESET
        bit: 0
        access: RW
        desc: "Module reset"
      - name: ENABLE
        bit: 1
        access: RW
        desc: "Module enable"
"""

    inline_style = """registers:
  GCR0:
    offset: "0x00"
    access: RW
    fields:
      - { name: RESET, bit: 0, access: RW, desc: "Module reset" }
      - { name: ENABLE, bit: 1, access: RW, desc: "Module enable" }
"""

    print("=" * 80)
    print("YAML FIELD FORMATTING STYLES")
    print("=" * 80)
    print("\nBlock Style (verbose, harder to read):")
    print("-" * 80)
    print(block_style)
    print("\nInline Style (compact, easier to read):")
    print("-" * 80)
    print(inline_style)
    print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python convert_yaml_to_inline.py <file.yaml>")
        print("  python convert_yaml_to_inline.py <file.yaml> <output.yaml>")
        print("  python convert_yaml_to_inline.py --dir <directory>")
        print("  python convert_yaml_to_inline.py --example")
        print()
        print("Examples:")
        print("  # Convert single file (overwrite)")
        print("  python convert_yaml_to_inline.py yaml_out/extracted_regs/gio_regs.yaml")
        print()
        print("  # Convert single file (save to new file)")
        print("  python convert_yaml_to_inline.py input.yaml output.yaml")
        print()
        print("  # Convert all YAML files in a directory")
        print("  python convert_yaml_to_inline.py --dir yaml_out/extracted_regs")
        print()
        print("  # Show example of block vs inline style")
        print("  python convert_yaml_to_inline.py --example")
        sys.exit(1)

    if sys.argv[1] == "--example":
        show_example()
        sys.exit(0)

    if sys.argv[1] == "--dir":
        if len(sys.argv) < 3:
            print("Error: --dir requires directory path")
            sys.exit(1)

        input_dir = Path(sys.argv[2])
        output_dir = Path(sys.argv[3]) if len(sys.argv) > 3 else None

        convert_directory(input_dir, output_dir)
        sys.exit(0)

    # Single file conversion
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    success = convert_file(input_file, output_file, verbose=True)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
