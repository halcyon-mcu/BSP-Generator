"""
Test suite for pin_config_builder module.

Tests the extraction of per-instance pin configurations from board.yaml and pinmux.yaml.
"""

import pytest
import yaml
import os
from modules.generation.pin_config_builder import (
    extract_peripheral_instances,
    extract_can_instances,
    extract_lin_instances,
    extract_sci_instances,
    extract_gpio_instances,
    find_pin_in_pinmux,
    parse_signal_name,
    PinMapping
)


@pytest.fixture
def board_data():
    """Load actual board.yaml data"""
    board_yaml_path = os.path.join(os.path.dirname(__file__), '..', 'yaml_in', 'board.yaml')
    with open(board_yaml_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def pinmux_data():
    """Load actual pinmux.yaml data"""
    pinmux_yaml_path = os.path.join(os.path.dirname(__file__), '..', 'yaml_in', 'pinmux.yaml')
    with open(pinmux_yaml_path, 'r') as f:
        return yaml.safe_load(f)


def test_multi_instance_can(board_data, pinmux_data):
    """
    Test that DCAN1 and DCAN2 have separate pin configurations.

    Verifies:
    - DCAN1 has pins 90 (RX) and 89 (TX)
    - DCAN2 has pins 129 (RX) and 128 (TX)
    - Instances are separate (not mixed)
    """
    instances = extract_peripheral_instances(board_data, pinmux_data, "CAN")

    assert instances is not None, "CAN instances should be found"
    assert "dcan1" in instances, "DCAN1 instance should exist"
    assert "dcan2" in instances, "DCAN2 instance should exist"

    # Check DCAN1 pins
    dcan1_pins = instances["dcan1"]
    assert len(dcan1_pins) == 2, "DCAN1 should have 2 pins (RX + TX)"

    dcan1_pin_numbers = {pin.package_pin for pin in dcan1_pins}
    assert 90 in dcan1_pin_numbers, "DCAN1 should have pin 90 (RX)"
    assert 89 in dcan1_pin_numbers, "DCAN1 should have pin 89 (TX)"

    # Check DCAN2 pins
    dcan2_pins = instances["dcan2"]
    assert len(dcan2_pins) == 2, "DCAN2 should have 2 pins (RX + TX)"

    dcan2_pin_numbers = {pin.package_pin for pin in dcan2_pins}
    assert 129 in dcan2_pin_numbers, "DCAN2 should have pin 129 (RX)"
    assert 128 in dcan2_pin_numbers, "DCAN2 should have pin 128 (TX)"

    # Verify signals are correct
    for pin in dcan1_pins:
        assert "DCAN1" in pin.signal.upper(), f"DCAN1 pin should have DCAN1 in signal: {pin.signal}"

    for pin in dcan2_pins:
        assert "DCAN2" in pin.signal.upper(), f"DCAN2 pin should have DCAN2 in signal: {pin.signal}"


def test_single_instance_sci(board_data, pinmux_data):
    """
    Test that SCI has one instance with all pins.

    Verifies:
    - SCI has single instance named "sci"
    - Has RX pin (38) and TX pin (39)
    """
    instances = extract_peripheral_instances(board_data, pinmux_data, "SCI")

    assert instances is not None, "SCI instance should be found"
    assert "sci" in instances, "SCI should have 'sci' instance"
    assert len(instances) == 1, "SCI should have exactly one instance"

    sci_pins = instances["sci"]
    assert len(sci_pins) == 2, "SCI should have 2 pins (RX + TX)"

    pin_numbers = {pin.package_pin for pin in sci_pins}
    assert 38 in pin_numbers, "SCI should have pin 38 (RX)"
    assert 39 in pin_numbers, "SCI should have pin 39 (TX)"

    # Verify signals
    signals = {pin.signal for pin in sci_pins}
    assert "SCIRX" in signals, "Should have SCIRX signal"
    assert "SCITX" in signals, "Should have SCITX signal"


def test_gpio_collection(board_data, pinmux_data):
    """
    Test that GIO collects all GPIO pins from LEDs, buttons, etc.

    Verifies:
    - GIO has single "gio" instance
    - Contains at least LED2 (pin 142, GIOB[2])
    - Contains at least LED3 (pin 133, GIOB[1])
    """
    instances = extract_peripheral_instances(board_data, pinmux_data, "GIO")

    assert instances is not None, "GIO instance should be found"
    assert "gio" in instances, "GIO should have 'gio' instance"

    gio_pins = instances["gio"]
    assert len(gio_pins) >= 2, "GIO should have at least 2 pins (LED2, LED3)"

    pin_numbers = {pin.package_pin for pin in gio_pins}
    assert 142 in pin_numbers, "GIO should include LED2 pin (142)"
    assert 133 in pin_numbers, "GIO should include LED3 pin (133)"

    # Verify GPIO signals
    for pin in gio_pins:
        assert "GIO" in pin.signal.upper(), f"GPIO pin should have GIO in signal: {pin.signal}"


def test_missing_pin_handling(pinmux_data):
    """
    Test that missing pins are handled gracefully.

    Verifies:
    - When a pin doesn't exist in pinmux.yaml, function doesn't crash
    - Returns None or handles appropriately
    """
    pins_list = pinmux_data.get('pins', [])

    # Test with pin that shouldn't exist
    result = find_pin_in_pinmux(9999, pins_list)
    assert result is None, "Non-existent pin should return None"


def test_invalid_peripheral(board_data, pinmux_data):
    """
    Test behavior with invalid peripheral name.

    Verifies:
    - Returns None or empty dict for unknown peripheral
    - Does not raise exception
    """
    instances = extract_peripheral_instances(board_data, pinmux_data, "INVALID_PERIPHERAL")
    assert instances is None or instances == {}, "Invalid peripheral should return None or empty dict"


def test_parse_signal_name():
    """Test signal name parsing from various formats"""
    assert parse_signal_name("DCAN1RX / CAN1RX") == "DCAN1RX"
    assert parse_signal_name("SCITX") == "SCITX"
    assert parse_signal_name("N2HET1[20]") == "N2HET1[20]"
    assert parse_signal_name("  LINTX  ") == "LINTX"


def test_data_source_tracking(board_data, pinmux_data):
    """
    Test that data source is properly tracked for each pin.

    Verifies:
    - Pins with complete data have "pinmux_complete"
    - Pins with partial data have "pinmux_partial"
    - Pins with no pinmux data have "board_only"
    """
    instances = extract_peripheral_instances(board_data, pinmux_data, "CAN")

    if instances:
        for instance_name, pins in instances.items():
            for pin in pins:
                assert pin.data_source in ["pinmux_complete", "pinmux_partial", "board_only"], \
                    f"Invalid data source: {pin.data_source}"

                # If data_source is pinmux_complete, register and bit should be set
                if pin.data_source == "pinmux_complete":
                    assert pin.register is not None, f"Complete pin {pin.package_pin} should have register"
                    assert pin.bit is not None, f"Complete pin {pin.package_pin} should have bit"


def test_can_instances_direct(board_data, pinmux_data):
    """Test extract_can_instances function directly"""
    pins_list = pinmux_data.get('pins', [])
    instances = extract_can_instances(board_data, pins_list)

    assert isinstance(instances, dict), "Should return dict"
    assert all(isinstance(v, list) for v in instances.values()), "All values should be lists"
    assert all(isinstance(pin, PinMapping) for pins in instances.values() for pin in pins), \
        "All pins should be PinMapping objects"


def test_lin_instances_direct(board_data, pinmux_data):
    """Test extract_lin_instances function directly"""
    pins_list = pinmux_data.get('pins', [])
    instances = extract_lin_instances(board_data, pins_list)

    assert isinstance(instances, dict), "Should return dict"

    if instances:
        # LIN1 should exist
        assert "lin1" in instances, "LIN1 instance should exist"

        lin1_pins = instances["lin1"]
        assert len(lin1_pins) == 2, "LIN1 should have 2 pins (RX + TX)"

        pin_numbers = {pin.package_pin for pin in lin1_pins}
        assert 131 in pin_numbers, "LIN1 should have pin 131 (RX)"
        assert 132 in pin_numbers, "LIN1 should have pin 132 (TX)"


def test_sci_instances_direct(board_data, pinmux_data):
    """Test extract_sci_instances function directly"""
    pins_list = pinmux_data.get('pins', [])
    instances = extract_sci_instances(board_data, pins_list)

    assert isinstance(instances, dict), "Should return dict"
    assert "sci" in instances, "Should have 'sci' instance"

    sci_pins = instances["sci"]
    assert all(isinstance(pin, PinMapping) for pin in sci_pins), "All should be PinMapping objects"


def test_gpio_instances_direct(board_data, pinmux_data):
    """Test extract_gpio_instances function directly"""
    pins_list = pinmux_data.get('pins', [])
    instances = extract_gpio_instances(board_data, pins_list)

    assert isinstance(instances, dict), "Should return dict"

    if instances:
        assert "gio" in instances, "Should have 'gio' instance"
        gio_pins = instances["gio"]
        assert len(gio_pins) > 0, "Should have at least one GPIO pin"


def test_pin_mapping_dataclass():
    """Test PinMapping dataclass creation"""
    pin = PinMapping(
        package_pin=90,
        signal="DCAN1RX",
        register="PINMMR15",
        bit=8,
        af_number=1,
        data_source="pinmux_complete"
    )

    assert pin.package_pin == 90
    assert pin.signal == "DCAN1RX"
    assert pin.register == "PINMMR15"
    assert pin.bit == 8
    assert pin.af_number == 1
    assert pin.data_source == "pinmux_complete"


def test_empty_board_data():
    """Test with empty board data"""
    empty_board = {}
    pinmux = {"pins": []}

    instances = extract_peripheral_instances(empty_board, pinmux, "CAN")
    assert instances is None or instances == {}, "Empty board should return None or empty dict"


def test_empty_pinmux_data():
    """Test with empty pinmux data"""
    board = {"communication": {"can": {"dcan1": {"rx_pin": 90, "tx_pin": 89}}}}
    empty_pinmux = {"pins": []}

    instances = extract_peripheral_instances(board, empty_pinmux, "CAN")

    # Should still extract from board.yaml even if pinmux.yaml is empty
    if instances:
        assert "dcan1" in instances
        # All pins should have data_source "board_only"
        for pin in instances["dcan1"]:
            assert pin.data_source == "board_only"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
