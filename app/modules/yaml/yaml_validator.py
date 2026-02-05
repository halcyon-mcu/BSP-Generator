#!/usr/bin/env python3
"""
yaml_validator.py

Utilities for validating generated register YAML files against regs.schema.yaml.
Uses jsonschema to validate structure and content.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

try:
    import jsonschema
    from jsonschema import Draft202012Validator, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    print("Warning: jsonschema not installed. Validation will be limited.")
    print("Install with: pip install jsonschema")


def load_schema(schema_path: Path) -> Dict[str, Any]:
    """
    Load the regs.schema.yaml file.

    Args:
        schema_path: Path to regs.schema.yaml

    Returns:
        Schema as a dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
        ValueError: If schema is invalid YAML
    """
    schema_path = Path(schema_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    with schema_path.open('r', encoding='utf-8') as f:
        try:
            schema = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in schema file: {e}")

    if not isinstance(schema, dict):
        raise ValueError("Schema must be a YAML mapping (dictionary)")

    return schema


def load_yaml_file(yaml_path: Path) -> Dict[str, Any]:
    """
    Load a YAML file.

    Args:
        yaml_path: Path to YAML file

    Returns:
        Parsed YAML as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If YAML is invalid
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    with yaml_path.open('r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}")

    if not isinstance(data, dict):
        raise ValueError("YAML must be a mapping (dictionary)")

    return data


def validate_yaml_against_schema(
    yaml_data: Dict[str, Any],
    schema: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Validate YAML data against the regs.schema.yaml schema.

    Args:
        yaml_data: The parsed YAML data to validate
        schema: The parsed schema

    Returns:
        Tuple of (is_valid, errors)
        - is_valid: True if validation passes
        - errors: List of error messages (empty if valid)
    """
    errors = []

    # If jsonschema is available, use it for comprehensive validation
    if HAS_JSONSCHEMA:
        try:
            # Create validator
            validator = Draft202012Validator(schema)

            # Collect all validation errors
            validation_errors = sorted(validator.iter_errors(yaml_data), key=str)

            for error in validation_errors:
                # Build a readable error message
                path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                errors.append(f"At {path}: {error.message}")

            if not errors:
                return True, []
            else:
                return False, errors

        except Exception as e:
            errors.append(f"Schema validation failed: {e}")
            return False, errors

    # Fallback: Basic manual validation if jsonschema not available
    else:
        # Basic structure checks
        if 'ir_schema_version' not in yaml_data:
            errors.append("Missing required field: ir_schema_version")

        if 'peripherals' not in yaml_data:
            errors.append("Missing required field: peripherals")
        elif not isinstance(yaml_data['peripherals'], dict):
            errors.append("Field 'peripherals' must be a dictionary")
        else:
            # Check each peripheral
            for periph_name, periph_data in yaml_data['peripherals'].items():
                errors.extend(_validate_peripheral(periph_name, periph_data))

        return len(errors) == 0, errors


def _validate_peripheral(name: str, data: Dict[str, Any]) -> List[str]:
    """
    Validate a single peripheral definition.

    Args:
        name: Peripheral name
        data: Peripheral data dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    prefix = f"peripherals.{name}"

    # Check required fields
    if 'base_address' not in data:
        errors.append(f"{prefix}: Missing required field 'base_address'")
    elif not _is_valid_hex(data['base_address']):
        errors.append(f"{prefix}.base_address: Must be hex string with 0x prefix")

    if 'registers' not in data:
        errors.append(f"{prefix}: Missing required field 'registers'")
    elif not isinstance(data['registers'], dict):
        errors.append(f"{prefix}.registers: Must be a dictionary")
    elif len(data['registers']) == 0:
        errors.append(f"{prefix}.registers: Must contain at least one register")
    else:
        # Validate each register
        for reg_name, reg_data in data['registers'].items():
            errors.extend(_validate_register(f"{prefix}.registers.{reg_name}", reg_data))

    return errors


def _validate_register(path: str, data: Dict[str, Any]) -> List[str]:
    """
    Validate a single register definition.

    Args:
        path: JSON path to this register (for error messages)
        data: Register data dictionary

    Returns:
        List of error messages
    """
    errors = []

    # Check required fields
    if 'offset' not in data:
        errors.append(f"{path}: Missing required field 'offset'")
    elif not _is_valid_hex(data['offset']):
        errors.append(f"{path}.offset: Must be hex string with 0x prefix")

    if 'access' not in data:
        errors.append(f"{path}: Missing required field 'access'")
    elif data['access'] not in ['RO', 'WO', 'RW', 'RC', 'RWC', 'R']:
        errors.append(f"{path}.access: Must be one of: RO, WO, RW, RC, RWC, R")

    # Check optional fields
    if 'reset' in data and not _is_valid_hex(data['reset']):
        errors.append(f"{path}.reset: Must be hex string with 0x prefix")

    # Validate fields array if present
    if 'fields' in data:
        if not isinstance(data['fields'], list):
            errors.append(f"{path}.fields: Must be an array")
        else:
            for i, field in enumerate(data['fields']):
                errors.extend(_validate_field(f"{path}.fields[{i}]", field))

    return errors


def _validate_field(path: str, data: Dict[str, Any]) -> List[str]:
    """
    Validate a single bitfield definition.

    Args:
        path: JSON path to this field (for error messages)
        data: Field data dictionary

    Returns:
        List of error messages
    """
    errors = []

    # Check required fields
    if 'name' not in data:
        errors.append(f"{path}: Missing required field 'name'")

    if 'access' not in data:
        errors.append(f"{path}: Missing required field 'access'")
    elif data['access'] not in ['RO', 'WO', 'RW', 'RC', 'RWC', 'R']:
        errors.append(f"{path}.access: Must be one of: RO, WO, RW, RC, RWC, R")

    # Check bit position fields (must have either 'bit' or both 'msb' and 'lsb')
    has_bit = 'bit' in data
    has_msb = 'msb' in data
    has_lsb = 'lsb' in data

    if not (has_bit or (has_msb and has_lsb)):
        errors.append(f"{path}: Must have either 'bit' or both 'msb' and 'lsb'")

    if has_bit and (has_msb or has_lsb):
        errors.append(f"{path}: Cannot have both 'bit' and 'msb'/'lsb'")

    # Validate bit positions
    if has_bit:
        if not isinstance(data['bit'], int) or not (0 <= data['bit'] <= 31):
            errors.append(f"{path}.bit: Must be an integer between 0 and 31")

    if has_msb:
        if not isinstance(data['msb'], int) or not (0 <= data['msb'] <= 31):
            errors.append(f"{path}.msb: Must be an integer between 0 and 31")

    if has_lsb:
        if not isinstance(data['lsb'], int) or not (0 <= data['lsb'] <= 31):
            errors.append(f"{path}.lsb: Must be an integer between 0 and 31")

    if has_msb and has_lsb and data['msb'] < data['lsb']:
        errors.append(f"{path}: msb ({data['msb']}) must be >= lsb ({data['lsb']})")

    # Validate reset value if present
    if 'reset' in data:
        if not isinstance(data['reset'], int) or data['reset'] < 0:
            errors.append(f"{path}.reset: Must be a non-negative integer")

    # Validate enum array if present
    if 'enum' in data:
        if not isinstance(data['enum'], list):
            errors.append(f"{path}.enum: Must be an array")
        else:
            for i, enum_entry in enumerate(data['enum']):
                if not isinstance(enum_entry, dict):
                    errors.append(f"{path}.enum[{i}]: Must be an object")
                    continue
                if 'name' not in enum_entry:
                    errors.append(f"{path}.enum[{i}]: Missing required field 'name'")
                if 'value' not in enum_entry:
                    errors.append(f"{path}.enum[{i}]: Missing required field 'value'")
                elif not isinstance(enum_entry['value'], int):
                    errors.append(f"{path}.enum[{i}].value: Must be an integer")

    return errors


def _is_valid_hex(value: Any) -> bool:
    """
    Check if a value is a valid hex string (0x...).

    Args:
        value: Value to check

    Returns:
        True if valid hex string
    """
    if not isinstance(value, str):
        return False

    # Must start with 0x and contain only hex digits
    hex_pattern = r'^0x[0-9A-Fa-f]+$'
    return bool(re.match(hex_pattern, value))


def validate_yaml_file(
    yaml_path: Path,
    schema_path: Path,
    verbose: bool = False,
) -> Tuple[bool, List[str]]:
    """
    Validate a YAML file against the schema.

    Args:
        yaml_path: Path to YAML file to validate
        schema_path: Path to regs.schema.yaml
        verbose: If True, print validation results

    Returns:
        Tuple of (is_valid, errors)
    """
    try:
        yaml_data = load_yaml_file(yaml_path)
        schema = load_schema(schema_path)
        is_valid, errors = validate_yaml_against_schema(yaml_data, schema)

        if verbose:
            if is_valid:
                print(f"✓ {yaml_path.name}: Valid")
            else:
                print(f"✗ {yaml_path.name}: Invalid")
                for error in errors:
                    print(f"  - {error}")

        return is_valid, errors

    except Exception as e:
        error_msg = f"Validation failed: {e}"
        if verbose:
            print(f"✗ {yaml_path.name}: {error_msg}")
        return False, [error_msg]


# Example usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python yaml_validator.py <yaml_file> [schema_file]")
        print("  If schema_file is not provided, uses ../yaml_schemas/regs.schema.yaml")
        sys.exit(1)

    yaml_file = Path(sys.argv[1])
    schema_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "yaml_schemas" / "regs.schema.yaml"

    is_valid, errors = validate_yaml_file(yaml_file, schema_file, verbose=True)

    sys.exit(0 if is_valid else 1)
