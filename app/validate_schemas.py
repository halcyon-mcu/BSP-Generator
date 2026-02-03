#!/usr/bin/env python3
"""
validate_schemas.py

Validate YAML files against their JSON schemas.

Usage:
    python validate_schemas.py --yaml-dir yaml_in_transformed
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Tuple


class SchemaValidator:
    """Validate YAML files against JSON schemas."""

    def __init__(self, yaml_dir: Path, schema_dir: Path):
        self.yaml_dir = Path(yaml_dir)
        self.schema_dir = Path(schema_dir)
        self.errors = []
        self.warnings = []

    def validate_all(self) -> bool:
        """Validate all YAML files. Returns True if all valid."""
        print("="*80)
        print("YAML SCHEMA VALIDATION")
        print("="*80)
        print(f"YAML dir:   {self.yaml_dir}")
        print(f"Schema dir: {self.schema_dir}")
        print()

        yaml_files = [
            'soc.yaml',
            'regs.yaml',
            'irq.yaml',
            'bus.yaml',
            'memmap.yaml',
            'pinmux.yaml',
            'board.yaml'
        ]

        all_valid = True

        for yaml_file in yaml_files:
            yaml_path = self.yaml_dir / yaml_file
            schema_path = self.schema_dir / yaml_file.replace('.yaml', '.schema.yaml')

            if not yaml_path.exists():
                print(f"[SKIP] {yaml_file} - file not found")
                continue

            if not schema_path.exists():
                print(f"[SKIP] {yaml_file} - schema not found")
                continue

            valid = self.validate_file(yaml_path, schema_path)
            if not valid:
                all_valid = False

        print()
        print("="*80)
        if all_valid:
            print("[OK] ALL FILES VALID")
        else:
            print("[FAIL] VALIDATION ERRORS FOUND")
        print("="*80)

        if self.warnings:
            print()
            print("WARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print()
            print("ERRORS:")
            for error in self.errors[:10]:  # Show first 10
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... and {len(self.errors) - 10} more errors")

        return all_valid

    def validate_file(self, yaml_path: Path, schema_path: Path) -> bool:
        """Validate one YAML file against its schema."""
        print(f"Validating {yaml_path.name}...", end=" ")

        try:
            # Load YAML
            with open(yaml_path) as f:
                yaml_data = yaml.safe_load(f)

            # Load schema
            with open(schema_path) as f:
                schema = yaml.safe_load(f)

            # Basic validation (manual - jsonschema library may not be installed)
            errors = self.manual_validate(yaml_data, schema, yaml_path.name)

            if errors:
                print("[FAIL]")
                for error in errors:
                    self.errors.append(f"{yaml_path.name}: {error}")
                return False
            else:
                print("[OK]")
                return True

        except Exception as e:
            print(f"[FAIL] {e}")
            self.errors.append(f"{yaml_path.name}: {e}")
            return False

    def manual_validate(self, data: Dict, schema: Dict, filename: str) -> List[str]:
        """Manual schema validation (basic checks)."""
        errors = []

        # Check required fields
        required = schema.get('required', [])
        for req_field in required:
            if req_field not in data:
                errors.append(f"Missing required field: {req_field}")

        # Check ir_schema_version
        if 'ir_schema_version' in data:
            if data['ir_schema_version'] != '1.1.0':
                errors.append(f"Invalid ir_schema_version: {data['ir_schema_version']} (expected 1.1.0)")

        # File-specific checks
        if filename == 'soc.yaml':
            errors.extend(self.validate_soc(data))
        elif filename == 'regs.yaml':
            errors.extend(self.validate_regs(data))

        return errors

    def validate_soc(self, data: Dict) -> List[str]:
        """Validate soc.yaml structure."""
        errors = []

        # Check soc section
        if 'soc' not in data:
            errors.append("Missing 'soc' section")
            return errors

        soc = data['soc']

        # Check cpu
        if 'cpu' not in soc:
            errors.append("Missing 'soc.cpu' section")
        else:
            cpu = soc['cpu']
            if 'cores' not in cpu:
                errors.append("Missing 'soc.cpu.cores' section")
            elif not isinstance(cpu['cores'], list):
                errors.append("'soc.cpu.cores' must be a list")

        # Check peripherals
        if 'peripherals' not in soc:
            errors.append("Missing 'soc.peripherals' section")
        else:
            peripherals = soc['peripherals']
            if not isinstance(peripherals, list):
                errors.append("'soc.peripherals' must be a list (not dict)")
            else:
                for i, periph in enumerate(peripherals):
                    # Check required fields
                    for req in ['name', 'type', 'regs_ref', 'clock_ref']:
                        if req not in periph:
                            errors.append(f"Peripheral {i}: missing '{req}' field")

        return errors

    def validate_regs(self, data: Dict) -> List[str]:
        """Validate regs.yaml structure."""
        errors = []

        # Check peripherals
        if 'peripherals' not in data:
            errors.append("Missing 'peripherals' section")
            return errors

        peripherals = data['peripherals']
        if not isinstance(peripherals, dict):
            errors.append("'peripherals' must be a dict")
            return errors

        # Check each peripheral
        for periph_name, periph_data in peripherals.items():
            if not isinstance(periph_data, dict):
                continue

            # Check required fields
            if 'base_address' not in periph_data:
                errors.append(f"{periph_name}: missing 'base_address'")
            if 'registers' not in periph_data:
                errors.append(f"{periph_name}: missing 'registers'")
                continue

            registers = periph_data['registers']
            if not isinstance(registers, dict):
                errors.append(f"{periph_name}: 'registers' must be a dict")
                continue

            # Check first register structure
            for reg_name, reg_data in list(registers.items())[:1]:  # Check first reg only
                if not isinstance(reg_data, dict):
                    continue

                # Check required fields
                for req in ['offset', 'access']:
                    if req not in reg_data:
                        errors.append(f"{periph_name}.{reg_name}: missing '{req}' field")

                # Check fields format
                if 'fields' in reg_data:
                    fields = reg_data['fields']
                    if not isinstance(fields, list):
                        errors.append(f"{periph_name}.{reg_name}: 'fields' must be a list (not dict)")

        return errors


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate YAML files against JSON schemas"
    )
    parser.add_argument(
        '--yaml-dir',
        type=Path,
        default=Path('yaml_in_transformed'),
        help='Directory with YAML files to validate'
    )
    parser.add_argument(
        '--schema-dir',
        type=Path,
        default=Path('yaml_schemas'),
        help='Directory with JSON schema files'
    )

    args = parser.parse_args()

    validator = SchemaValidator(yaml_dir=args.yaml_dir, schema_dir=args.schema_dir)
    valid = validator.validate_all()

    exit(0 if valid else 1)


if __name__ == '__main__':
    main()
