"""
Unit tests for cross-reference validation between YAML files.
"""

import pytest
from modules.validation.cross_reference_validator import validate_cross_references


class TestCrossReferenceValidation:
    """Test cross-file reference validation."""

    def test_valid_all_references(self):
        """Test that all valid references pass validation."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO",
                        "clock_ref": "VCLK",
                        "irq_ref": ["GIO_HIGH"]
                    }
                ]
            }
        }
        regs_data = {
            "peripherals": {
                "GIO": {}
            }
        }
        irq_data = {
            "irqs": [
                {"name": "GIO_HIGH", "number": 9}
            ]
        }
        bus_data = {
            "sources": [{"name": "OSCIN"}],
            "domains": [{"name": "VCLK"}]
        }
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert errors == []

    def test_missing_regs_ref(self):
        """Test that missing regs_ref is detected."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "NONEXISTENT"  # Does not exist in regs.yaml
                    }
                ]
            }
        }
        regs_data = {"peripherals": {}}
        irq_data = {"irqs": []}
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert len(errors) == 1
        assert "NONEXISTENT" in errors[0]
        assert "regs_ref" in errors[0]

    def test_missing_clock_ref(self):
        """Test that missing clock_ref is detected."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO",
                        "clock_ref": "NONEXISTENT_CLOCK"
                    }
                ]
            }
        }
        regs_data = {"peripherals": {"GIO": {}}}
        irq_data = {"irqs": []}
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert len(errors) == 1
        assert "NONEXISTENT_CLOCK" in errors[0]
        assert "clock_ref" in errors[0]

    def test_missing_irq_ref(self):
        """Test that missing irq_ref is detected."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO",
                        "irq_ref": ["NONEXISTENT_IRQ"]
                    }
                ]
            }
        }
        regs_data = {"peripherals": {"GIO": {}}}
        irq_data = {"irqs": []}
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert len(errors) == 1
        assert "NONEXISTENT_IRQ" in errors[0]
        assert "irq_ref" in errors[0]

    def test_multiple_missing_references(self):
        """Test that multiple missing references are all detected."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "MISSING_REGS",
                        "clock_ref": "MISSING_CLOCK",
                        "irq_ref": ["MISSING_IRQ1", "MISSING_IRQ2"]
                    }
                ]
            }
        }
        regs_data = {"peripherals": {}}
        irq_data = {"irqs": []}
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert len(errors) == 4  # regs + clock + 2 irqs
        error_text = " ".join(errors)
        assert "MISSING_REGS" in error_text
        assert "MISSING_CLOCK" in error_text
        assert "MISSING_IRQ1" in error_text
        assert "MISSING_IRQ2" in error_text

    def test_clock_from_source(self):
        """Test that clocks from sources are recognized."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "PLL",
                        "regs_ref": "PLL",
                        "clock_ref": "OSCIN"  # From sources
                    }
                ]
            }
        }
        regs_data = {"peripherals": {"PLL": {}}}
        irq_data = {"irqs": []}
        bus_data = {
            "sources": [{"name": "OSCIN"}],
            "domains": []
        }
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert errors == []

    def test_clock_from_domain(self):
        """Test that clocks from domains are recognized."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO",
                        "clock_ref": "VCLK"  # From domains
                    }
                ]
            }
        }
        regs_data = {"peripherals": {"GIO": {}}}
        irq_data = {"irqs": []}
        bus_data = {
            "sources": [],
            "domains": [{"name": "VCLK"}]
        }
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert errors == []

    def test_optional_fields_not_required(self):
        """Test that optional fields (clock_ref, irq_ref) can be omitted."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO"
                        # No clock_ref or irq_ref
                    }
                ]
            }
        }
        regs_data = {"peripherals": {"GIO": {}}}
        irq_data = {"irqs": []}
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert errors == []

    def test_single_irq_ref_string(self):
        """Test that single IRQ reference as string is handled."""
        soc_data = {
            "soc": {
                "peripherals": [
                    {
                        "name": "GIO",
                        "regs_ref": "GIO",
                        "irq_ref": "GIO_HIGH"  # String, not array
                    }
                ]
            }
        }
        regs_data = {"peripherals": {"GIO": {}}}
        irq_data = {
            "irqs": [{"name": "GIO_HIGH", "number": 9}]
        }
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert errors == []

    def test_flat_soc_structure(self):
        """Test that flat soc structure (without nested 'soc' key) works."""
        soc_data = {
            "peripherals": [  # Flat structure, not nested in "soc"
                {
                    "name": "GIO",
                    "regs_ref": "GIO"
                }
            ]
        }
        regs_data = {"peripherals": {"GIO": {}}}
        irq_data = {"irqs": []}
        bus_data = {"sources": [], "domains": []}
        pinmux_data = {"pins": []}

        errors = validate_cross_references(
            soc_data, regs_data, irq_data, bus_data, pinmux_data
        )
        assert errors == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
