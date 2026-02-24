"""
Field validation helpers for checking empty/null values.

Provides functions to validate that required fields are present and non-empty
before processing begins.
"""

from typing import Dict, List, Any


def validate_required_fields(
    data: Dict[str, Any],
    required: List[str],
    context: str
) -> List[str]:
    """
    Validate that required fields are present and non-empty.

    Args:
        data: Dictionary to validate
        required: List of required field names
        context: Context string for error messages (e.g., "peripheral GIO")

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    for field in required:
        value = data.get(field)

        # Check if field is missing or None
        if value is None:
            errors.append(f"{context}: Missing required field '{field}'")
            continue

        # Check if field is empty string
        if isinstance(value, str) and not value.strip():
            errors.append(f"{context}: Required field '{field}' is empty")
            continue

        # Check if field is empty dict
        if isinstance(value, dict) and not value:
            errors.append(f"{context}: Required field '{field}' is empty dictionary")
            continue

        # Check if field is empty list
        if isinstance(value, list) and not value:
            errors.append(f"{context}: Required field '{field}' is empty list")
            continue

    return errors


def validate_peripheral_data(periph: Dict[str, Any]) -> List[str]:
    """
    Validate that a peripheral has all required fields.

    Args:
        periph: Peripheral data dictionary

    Returns:
        List of error messages (empty if valid)
    """
    periph_name = periph.get("name", "unknown_peripheral")
    required_fields = ["name", "regs_ref"]

    return validate_required_fields(periph, required_fields, f"Peripheral {periph_name}")


def validate_register_data(reg_name: str, reg_data: Dict[str, Any]) -> List[str]:
    """
    Validate that register data has required fields.

    Args:
        reg_name: Register name
        reg_data: Register data dictionary

    Returns:
        List of error messages (empty if valid)
    """
    required_fields = ["offset", "access", "desc"]

    return validate_required_fields(reg_data, required_fields, f"Register {reg_name}")


def validate_manifest_completeness(manifest: Dict[str, Any], module_name: str) -> List[str]:
    """
    Validate that a generated manifest has all required fields.

    Args:
        manifest: Manifest dictionary
        module_name: Module name for error messages

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check top-level required fields
    required_top_level = ["init_function", "functions", "types"]
    for field in required_top_level:
        if field not in manifest:
            errors.append(f"{module_name} manifest: Missing required field '{field}'")
        elif manifest.get(field) is None:
            errors.append(f"{module_name} manifest: Field '{field}' is null")

    # Validate init_function is not empty
    init_func = manifest.get("init_function", "")
    if isinstance(init_func, str) and not init_func.strip():
        errors.append(f"{module_name} manifest: init_function is empty")

    # Validate functions array
    functions = manifest.get("functions", [])
    if not isinstance(functions, list):
        errors.append(f"{module_name} manifest: 'functions' must be a list")
    else:
        for idx, func in enumerate(functions):
            if not isinstance(func, dict):
                errors.append(f"{module_name} manifest: functions[{idx}] is not a dictionary")
                continue

            # Each function needs name and prototype
            if not func.get("name"):
                errors.append(f"{module_name} manifest: functions[{idx}] missing 'name'")
            if not func.get("prototype"):
                errors.append(f"{module_name} manifest: functions[{idx}] missing 'prototype'")

    # Validate types array
    types = manifest.get("types", [])
    if not isinstance(types, list):
        errors.append(f"{module_name} manifest: 'types' must be a list")
    else:
        for idx, typ in enumerate(types):
            if not isinstance(typ, dict):
                errors.append(f"{module_name} manifest: types[{idx}] is not a dictionary")
                continue

            # Each type needs name and type
            if not typ.get("name"):
                errors.append(f"{module_name} manifest: types[{idx}] missing 'name'")
            if not typ.get("type"):
                errors.append(f"{module_name} manifest: types[{idx}] missing 'type'")

    return errors
