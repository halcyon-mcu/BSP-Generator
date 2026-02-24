"""
Unit tests for field validation helpers.
"""

import pytest
from modules.validation.field_validator import (
    validate_required_fields,
    validate_peripheral_data,
    validate_register_data,
    validate_manifest_completeness
)


class TestValidateRequiredFields:
    """Test validate_required_fields function."""

    def test_valid_data(self):
        """Test that valid data passes validation."""
        data = {"name": "GIO", "regs_ref": "GIO", "type": "gpio"}
        errors = validate_required_fields(data, ["name", "regs_ref"], "Test")
        assert errors == []

    def test_missing_field(self):
        """Test that missing field is detected."""
        data = {"name": "GIO"}  # Missing regs_ref
        errors = validate_required_fields(data, ["name", "regs_ref"], "Test")
        assert len(errors) == 1
        assert "regs_ref" in errors[0]

    def test_null_field(self):
        """Test that null field is detected."""
        data = {"name": "GIO", "regs_ref": None}
        errors = validate_required_fields(data, ["name", "regs_ref"], "Test")
        assert len(errors) == 1
        assert "regs_ref" in errors[0]

    def test_empty_string(self):
        """Test that empty string is detected."""
        data = {"name": "", "regs_ref": "GIO"}
        errors = validate_required_fields(data, ["name"], "Test")
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    def test_whitespace_only_string(self):
        """Test that whitespace-only string is detected."""
        data = {"name": "   ", "regs_ref": "GIO"}
        errors = validate_required_fields(data, ["name"], "Test")
        assert len(errors) == 1

    def test_empty_dict(self):
        """Test that empty dictionary is detected."""
        data = {"config": {}, "name": "GIO"}
        errors = validate_required_fields(data, ["config"], "Test")
        assert len(errors) == 1
        assert "empty dictionary" in errors[0].lower()

    def test_empty_list(self):
        """Test that empty list is detected."""
        data = {"items": [], "name": "GIO"}
        errors = validate_required_fields(data, ["items"], "Test")
        assert len(errors) == 1
        assert "empty list" in errors[0].lower()

    def test_multiple_missing_fields(self):
        """Test that multiple missing fields are all detected."""
        data = {}
        errors = validate_required_fields(data, ["name", "regs_ref", "type"], "Test")
        assert len(errors) == 3

    def test_context_in_error_message(self):
        """Test that context appears in error messages."""
        data = {}
        errors = validate_required_fields(data, ["name"], "Peripheral GIO")
        assert "Peripheral GIO" in errors[0]


class TestValidatePeripheralData:
    """Test validate_peripheral_data function."""

    def test_valid_peripheral(self):
        """Test that valid peripheral passes validation."""
        periph = {"name": "GIO", "regs_ref": "GIO", "type": "gpio"}
        errors = validate_peripheral_data(periph)
        assert errors == []

    def test_missing_name(self):
        """Test that missing name is detected."""
        periph = {"regs_ref": "GIO"}
        errors = validate_peripheral_data(periph)
        assert len(errors) >= 1
        assert any("name" in err for err in errors)

    def test_missing_regs_ref(self):
        """Test that missing regs_ref is detected."""
        periph = {"name": "GIO"}
        errors = validate_peripheral_data(periph)
        assert len(errors) >= 1
        assert any("regs_ref" in err for err in errors)

    def test_uses_peripheral_name_in_error(self):
        """Test that peripheral name is used in error messages."""
        periph = {"name": "GIO"}  # Missing regs_ref
        errors = validate_peripheral_data(periph)
        assert any("GIO" in err for err in errors)


class TestValidateRegisterData:
    """Test validate_register_data function."""

    def test_valid_register(self):
        """Test that valid register passes validation."""
        reg = {"offset": "0x00", "access": "RW", "desc": "Description"}
        errors = validate_register_data("GIODIR", reg)
        assert errors == []

    def test_missing_offset(self):
        """Test that missing offset is detected."""
        reg = {"access": "RW", "desc": "Description"}
        errors = validate_register_data("GIODIR", reg)
        assert len(errors) >= 1
        assert any("offset" in err for err in errors)

    def test_missing_access(self):
        """Test that missing access is detected."""
        reg = {"offset": "0x00", "desc": "Description"}
        errors = validate_register_data("GIODIR", reg)
        assert len(errors) >= 1
        assert any("access" in err for err in errors)

    def test_missing_desc(self):
        """Test that missing desc is detected."""
        reg = {"offset": "0x00", "access": "RW"}
        errors = validate_register_data("GIODIR", reg)
        assert len(errors) >= 1
        assert any("desc" in err for err in errors)


class TestValidateManifestCompleteness:
    """Test validate_manifest_completeness function."""

    def test_valid_manifest(self):
        """Test that valid manifest passes validation."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": [
                {"name": "GIO_Init", "prototype": "void GIO_Init(void);"}
            ],
            "types": [
                {"name": "gio_config_t", "type": "struct"}
            ]
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert errors == []

    def test_missing_init_function(self):
        """Test that missing init_function is detected."""
        manifest = {
            "functions": [],
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("init_function" in err for err in errors)

    def test_missing_functions(self):
        """Test that missing functions array is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("functions" in err for err in errors)

    def test_missing_types(self):
        """Test that missing types array is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("types" in err for err in errors)

    def test_empty_init_function(self):
        """Test that empty init_function is detected."""
        manifest = {
            "init_function": "",
            "functions": [],
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("empty" in err.lower() for err in errors)

    def test_null_init_function(self):
        """Test that null init_function is detected."""
        manifest = {
            "init_function": None,
            "functions": [],
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("null" in err.lower() or "init_function" in err for err in errors)

    def test_functions_not_list(self):
        """Test that non-list functions is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": "not a list",
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("list" in err.lower() and "functions" in err for err in errors)

    def test_function_missing_name(self):
        """Test that function without name is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": [
                {"prototype": "void GIO_Init(void);"}  # Missing name
            ],
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("name" in err for err in errors)

    def test_function_missing_prototype(self):
        """Test that function without prototype is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": [
                {"name": "GIO_Init"}  # Missing prototype
            ],
            "types": []
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("prototype" in err for err in errors)

    def test_type_missing_name(self):
        """Test that type without name is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": [],
            "types": [
                {"type": "struct"}  # Missing name
            ]
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert any("name" in err for err in errors)

    def test_type_missing_type(self):
        """Test that type without type field is detected."""
        manifest = {
            "init_function": "GIO_Init",
            "functions": [],
            "types": [
                {"name": "config_t"}  # Missing type
            ]
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        # Note: Looking for 'type' field errors, but message might say "missing 'type'"
        assert len(errors) > 0

    def test_multiple_errors(self):
        """Test that multiple errors are all detected."""
        manifest = {
            "init_function": "",  # Empty
            "functions": "not a list",  # Wrong type
            "types": [
                {"name": "config_t"}  # Missing type field
            ]
        }
        errors = validate_manifest_completeness(manifest, "GIO")
        assert len(errors) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
