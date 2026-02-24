"""
Unit tests for YAML schema validation.
"""

import pytest
from modules.yaml.schemas import (
    SocYAML,
    RegsYAML,
    BusYAML,
    IrqYAML,
    PinmuxYAML,
    validate_yaml_schema
)


class TestSocYAMLSchema:
    """Test SocYAML schema validation."""

    def test_valid_soc_yaml(self):
        """Test that valid soc.yaml data passes validation."""
        data = {
            "chip": "RM46L852",
            "family": "Hercules RM46",
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO",
                        "type": "gpio"
                    }
                ]
            }
        }
        is_valid, errors = validate_yaml_schema(data, SocYAML)
        assert is_valid
        assert errors == []

    def test_missing_chip_field(self):
        """Test that missing chip field is caught."""
        data = {
            "family": "Hercules RM46",
            "soc": {"peripherals": []}
        }
        is_valid, errors = validate_yaml_schema(data, SocYAML)
        assert not is_valid
        assert any("chip" in err.lower() for err in errors)

    def test_empty_peripherals(self):
        """Test that empty peripherals list is rejected."""
        data = {
            "chip": "RM46L852",
            "family": "Hercules RM46",
            "soc": {"peripherals": []}
        }
        is_valid, errors = validate_yaml_schema(data, SocYAML)
        assert not is_valid
        assert any("empty" in err.lower() for err in errors)

    def test_duplicate_peripheral_names(self):
        """Test that duplicate peripheral names are rejected."""
        data = {
            "chip": "RM46L852",
            "family": "Hercules RM46",
            "soc": {
                "peripherals": [
                    {"name": "GIO", "regs_ref": "GIO"},
                    {"name": "GIO", "regs_ref": "GIO"}  # Duplicate
                ]
            }
        }
        is_valid, errors = validate_yaml_schema(data, SocYAML)
        assert not is_valid
        assert any("duplicate" in err.lower() for err in errors)

    def test_empty_peripheral_name(self):
        """Test that empty peripheral name is rejected."""
        data = {
            "chip": "RM46L852",
            "family": "Hercules RM46",
            "soc": {
                "peripherals": [
                    {"name": "", "regs_ref": "GIO"}  # Empty name
                ]
            }
        }
        is_valid, errors = validate_yaml_schema(data, SocYAML)
        assert not is_valid


class TestRegsYAMLSchema:
    """Test RegsYAML schema validation."""

    def test_valid_regs_yaml(self):
        """Test that valid regs.yaml data passes validation."""
        data = {
            "peripherals": {
                "GIO": {
                    "base_address": "0xFFF7BC00",
                    "desc": "General I/O",
                    "registers": {
                        "GIODIR": {
                            "offset": "0x00",
                            "access": "RW",
                            "reset": "0x00000000",
                            "desc": "Direction register"
                        }
                    }
                }
            }
        }
        is_valid, errors = validate_yaml_schema(data, RegsYAML)
        assert is_valid
        assert errors == []

    def test_invalid_hex_address(self):
        """Test that invalid hex address is rejected."""
        data = {
            "peripherals": {
                "GIO": {
                    "base_address": "FFF7BC00",  # Missing 0x prefix
                    "desc": "General I/O",
                    "registers": {}
                }
            }
        }
        is_valid, errors = validate_yaml_schema(data, RegsYAML)
        assert not is_valid
        assert any("0x" in err for err in errors)

    def test_invalid_access_type(self):
        """Test that invalid access type is rejected."""
        data = {
            "peripherals": {
                "GIO": {
                    "base_address": "0xFFF7BC00",
                    "desc": "General I/O",
                    "registers": {
                        "GIODIR": {
                            "offset": "0x00",
                            "access": "INVALID",  # Invalid access type
                            "reset": "0x00000000",
                            "desc": "Direction register"
                        }
                    }
                }
            }
        }
        is_valid, errors = validate_yaml_schema(data, RegsYAML)
        assert not is_valid
        assert any("access" in err.lower() for err in errors)


class TestBusYAMLSchema:
    """Test BusYAML schema validation."""

    def test_valid_bus_yaml(self):
        """Test that valid bus.yaml data passes validation."""
        data = {
            "sources": [
                {"name": "OSCIN", "freq_hz": 16000000}
            ],
            "domains": [
                {"name": "GCLK", "divider": 1}
            ]
        }
        is_valid, errors = validate_yaml_schema(data, BusYAML)
        assert is_valid
        assert errors == []

    def test_zero_frequency_rejected(self):
        """Test that zero frequency is rejected."""
        data = {
            "sources": [
                {"name": "OSCIN", "freq_hz": 0}  # Invalid: must be > 0
            ],
            "domains": []
        }
        is_valid, errors = validate_yaml_schema(data, BusYAML)
        assert not is_valid

    def test_empty_sources_rejected(self):
        """Test that empty sources list is rejected."""
        data = {
            "sources": [],
            "domains": [{"name": "GCLK"}]
        }
        is_valid, errors = validate_yaml_schema(data, BusYAML)
        assert not is_valid


class TestIrqYAMLSchema:
    """Test IrqYAML schema validation."""

    def test_valid_irq_yaml(self):
        """Test that valid irq.yaml data passes validation."""
        data = {
            "interrupt_controller": "VIM",
            "irqs": [
                {"name": "ESM_HIGH", "number": 0},
                {"name": "RTI_COMPARE_0", "number": 2}
            ]
        }
        is_valid, errors = validate_yaml_schema(data, IrqYAML)
        assert is_valid
        assert errors == []

    def test_duplicate_irq_names_rejected(self):
        """Test that duplicate IRQ names are rejected."""
        data = {
            "interrupt_controller": "VIM",
            "irqs": [
                {"name": "ESM_HIGH", "number": 0},
                {"name": "ESM_HIGH", "number": 1}  # Duplicate name
            ]
        }
        is_valid, errors = validate_yaml_schema(data, IrqYAML)
        assert not is_valid
        assert any("duplicate" in err.lower() and "name" in err.lower() for err in errors)

    def test_duplicate_irq_numbers_rejected(self):
        """Test that duplicate IRQ numbers are rejected."""
        data = {
            "interrupt_controller": "VIM",
            "irqs": [
                {"name": "ESM_HIGH", "number": 0},
                {"name": "RTI_COMPARE_0", "number": 0}  # Duplicate number
            ]
        }
        is_valid, errors = validate_yaml_schema(data, IrqYAML)
        assert not is_valid
        assert any("duplicate" in err.lower() and "number" in err.lower() for err in errors)

    def test_negative_irq_number_rejected(self):
        """Test that negative IRQ numbers are rejected."""
        data = {
            "interrupt_controller": "VIM",
            "irqs": [
                {"name": "ESM_HIGH", "number": -1}  # Invalid
            ]
        }
        is_valid, errors = validate_yaml_schema(data, IrqYAML)
        assert not is_valid


class TestPinmuxYAMLSchema:
    """Test PinmuxYAML schema validation."""

    def test_valid_pinmux_yaml(self):
        """Test that valid pinmux.yaml data passes validation."""
        data = {
            "pins": [
                {"pin": 1, "signals": ["GIOA0", "ETPWM1A"]},
                {"pin": 2, "signals": ["GIOA1", "ETPWM1B"]}
            ]
        }
        is_valid, errors = validate_yaml_schema(data, PinmuxYAML)
        assert is_valid
        assert errors == []

    def test_empty_signals_rejected(self):
        """Test that empty signals list is rejected."""
        data = {
            "pins": [
                {"pin": 1, "signals": []}  # Empty signals
            ]
        }
        is_valid, errors = validate_yaml_schema(data, PinmuxYAML)
        assert not is_valid

    def test_string_pin_name(self):
        """Test that string pin names are accepted."""
        data = {
            "pins": [
                {"pin": "GIOA0", "signals": ["FUNC1", "FUNC2"]}
            ]
        }
        is_valid, errors = validate_yaml_schema(data, PinmuxYAML)
        assert is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
