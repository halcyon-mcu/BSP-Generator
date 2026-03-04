"""
Pin Configuration Builder Module

Extracts per-instance pin configurations from board.yaml and pinmux.yaml.
Handles incomplete pinmux data with three-tier fallback strategy.

Author: BSP Generator
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class PinMapping:
    """
    Represents a pin configuration mapping.

    Attributes:
        package_pin: Physical pin number on the package
        signal: Signal name (e.g., "DCAN1RX", "SCITX")
        register: PINMMR register name (e.g., "PINMMR15"), may be None
        bit: Bit position in register, may be None
        af_number: Alternate function number (0-3), may be None
        af_enum: Enum constant name for IOMM (e.g., "IOMM_PIN_FUNC_ALT1"), may be None
        data_source: Origin of data ("pinmux_complete", "pinmux_partial", "board_only")
    """
    package_pin: int
    signal: str
    register: Optional[str]
    bit: Optional[int]
    af_number: Optional[int]
    af_enum: Optional[str]
    data_source: str


def get_af_enum_name(af_number: Optional[int], iomm_manifest: Optional[Dict] = None) -> Optional[str]:
    """
    Convert AF number to iomm_pin_function_t enum constant name.

    Uses IOMM manifest enum values if available, falls back to standard RM46 naming.

    Args:
        af_number: Alternate function number (0-3)
        iomm_manifest: IOMM module manifest from Pass 1 (contains actual enum value names)

    Returns:
        Actual enum constant name from IOMM driver (e.g., "IOMM_PIN_FUNC_ALT1"), or None if af_number is None

    Example:
        >>> get_af_enum_name(1)
        'IOMM_PIN_FUNC_ALT1'
        >>> get_af_enum_name(0)
        'IOMM_PIN_FUNC_GPIO'
        >>> get_af_enum_name(None)
        None
    """
    if af_number is None:
        return None

    # Extract actual enum values from IOMM manifest if available
    if iomm_manifest:
        types = iomm_manifest.get('types', [])
        for type_def in types:
            if type_def.get('name') == 'iomm_pin_function_t':
                values = type_def.get('values', [])
                # Standard RM46 mapping: AF0=GPIO, AF1=ALT1, AF2=ALT2, AF3=ALT3
                if af_number == 0 and len(values) > 0:
                    return values[0]  # IOMM_PIN_FUNC_GPIO
                elif 1 <= af_number <= 3 and len(values) > af_number:
                    return values[af_number]  # IOMM_PIN_FUNC_ALT1/2/3

    # Fallback to standard RM46 naming convention
    # This matches the typical Pass 1 IOMM output
    mapping = {
        0: "IOMM_PIN_FUNC_GPIO",
        1: "IOMM_PIN_FUNC_ALT1",
        2: "IOMM_PIN_FUNC_ALT2",
        3: "IOMM_PIN_FUNC_ALT3"
    }
    return mapping.get(af_number)


def find_pin_in_pinmux(package_pin: int, pinmux_data: List[Dict], signal_hint: str = None) -> Optional[Dict]:
    """
    Find a pin in pinmux data with three-tier fallback strategy.

    Args:
        package_pin: Physical pin number to find
        pinmux_data: List of pin definitions from pinmux.yaml
        signal_hint: Expected signal name to match (e.g., "DCAN1RX")

    Returns:
        Pin dict if found, None otherwise
    """
    for pin in pinmux_data:
        if pin.get('package_pin') == package_pin:
            return pin
    return None


def parse_signal_name(signal: str) -> str:
    """
    Extract clean signal name from various formats.

    Handles formats like:
    - "DCAN1RX / CAN1RX"
    - "SCITX"
    - "N2HET1[20]"

    Args:
        signal: Raw signal string

    Returns:
        Cleaned signal name
    """
    if '/' in signal:
        return signal.split('/')[0].strip()
    return signal.strip()


def find_signal_in_pin(pin_data: Dict, signal_hint: str) -> Optional[Dict]:
    """
    Find a specific signal function in a pin's function list.

    Args:
        pin_data: Pin dictionary from pinmux.yaml
        signal_hint: Signal name to search for (e.g., "DCAN1RX")

    Returns:
        Function dict if found, None otherwise
    """
    functions = pin_data.get('functions', [])
    signal_upper = signal_hint.upper()

    for func in functions:
        func_signal = parse_signal_name(func.get('signal', ''))
        if signal_upper in func_signal.upper():
            return func

    return None


def find_signal_in_pinmux(pinmux_data: List[Dict], signal_hint: str) -> Optional[tuple[Dict, Dict]]:
    """
    Find a pin/function pair in pinmux by matching signal name.

    Returns:
        Tuple of (pin_dict, function_dict) when found, otherwise None.
    """
    signal_upper = parse_signal_name(signal_hint).upper()
    if not signal_upper:
        return None

    for pin in pinmux_data:
        for func in pin.get('functions', []):
            func_signal = parse_signal_name(func.get('signal', '')).upper()
            if func_signal == signal_upper:
                return pin, func
    return None


def extract_can_instances(board_data: Dict, pinmux_data: List[Dict], iomm_manifest: Optional[Dict] = None) -> Dict[str, List[PinMapping]]:
    """
    Extract CAN peripheral instances (DCAN1, DCAN2, DCAN3).

    Args:
        board_data: Parsed board.yaml
        pinmux_data: Parsed pinmux.yaml pin list
        iomm_manifest: IOMM module manifest from Pass 1

    Returns:
        Dict mapping instance names to pin lists
    """
    instances = {}

    can_config = board_data.get('communication', {}).get('can', {})

    for instance_name, instance_config in can_config.items():
        if not isinstance(instance_config, dict):
            continue

        pins = []
        instance_upper = instance_name.upper()

        # Extract RX pin
        rx_pin_num = instance_config.get('rx_pin')
        if rx_pin_num:
            signal = f"{instance_upper}RX"
            pin_data = find_pin_in_pinmux(rx_pin_num, pinmux_data)

            if pin_data:
                func = find_signal_in_pin(pin_data, signal)
                if func and func.get('mux'):
                    # Tier 1: Complete match
                    mux = func['mux']
                    af_num = int(func.get('af', 0))
                    pins.append(PinMapping(
                        package_pin=rx_pin_num,
                        signal=signal,
                        register=mux.get('register'),
                        bit=mux.get('bit'),
                        af_number=af_num,
                        af_enum=get_af_enum_name(af_num, iomm_manifest),
                        data_source="pinmux_complete"
                    ))
                else:
                    # Tier 2: Partial match (pin exists, signal missing)
                    pins.append(PinMapping(
                        package_pin=rx_pin_num,
                        signal=signal,
                        register=None,
                        bit=None,
                        af_number=None,
                        af_enum=None,
                        data_source="pinmux_partial"
                    ))
            else:
                # Tier 3: Board only
                pins.append(PinMapping(
                    package_pin=rx_pin_num,
                    signal=signal,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="board_only"
                ))

        # Extract TX pin
        tx_pin_num = instance_config.get('tx_pin')
        if tx_pin_num:
            signal = f"{instance_upper}TX"
            pin_data = find_pin_in_pinmux(tx_pin_num, pinmux_data)

            if pin_data:
                func = find_signal_in_pin(pin_data, signal)
                if func and func.get('mux'):
                    # Tier 1: Complete match
                    mux = func['mux']
                    af_num = int(func.get('af', 0))
                    pins.append(PinMapping(
                        package_pin=tx_pin_num,
                        signal=signal,
                        register=mux.get('register'),
                        bit=mux.get('bit'),
                        af_number=af_num,
                        af_enum=get_af_enum_name(af_num, iomm_manifest),
                        data_source="pinmux_complete"
                    ))
                else:
                    # Tier 2: Partial match
                    pins.append(PinMapping(
                        package_pin=tx_pin_num,
                        signal=signal,
                        register=None,
                        bit=None,
                        af_number=None,
                        af_enum=None,
                        data_source="pinmux_partial"
                    ))
            else:
                # Tier 3: Board only
                pins.append(PinMapping(
                    package_pin=tx_pin_num,
                    signal=signal,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="board_only"
                ))

        if pins:
            instances[instance_name] = pins

    return instances


def extract_lin_instances(board_data: Dict, pinmux_data: List[Dict], iomm_manifest: Optional[Dict] = None) -> Dict[str, List[PinMapping]]:
    """
    Extract LIN peripheral instances (LIN1, LIN2).

    Args:
        board_data: Parsed board.yaml
        pinmux_data: Parsed pinmux.yaml pin list
        iomm_manifest: IOMM module manifest from Pass 1

    Returns:
        Dict mapping instance names to pin lists
    """
    instances = {}

    lin_config = board_data.get('communication', {}).get('lin', {})

    for instance_name, instance_config in lin_config.items():
        if not isinstance(instance_config, dict):
            continue

        pins = []
        instance_upper = instance_name.upper()

        # Extract RX pin
        rx_pin_num = instance_config.get('rx_pin')
        if rx_pin_num:
            signal = f"{instance_upper}RX"
            pin_data = find_pin_in_pinmux(rx_pin_num, pinmux_data)

            if pin_data:
                func = find_signal_in_pin(pin_data, signal)

                # Try alternative signal name if LIN signal not found
                # (LIN can use SCI pins when operating in SCI/UART mode)
                if not func or not func.get('mux'):
                    func = find_signal_in_pin(pin_data, "SCIRX")
                    if func and func.get('mux'):
                        signal = "SCIRX"  # Update signal name to match pinmux

                if func and func.get('mux'):
                    mux = func['mux']
                    af_num = int(func.get('af', 0))
                    pins.append(PinMapping(
                        package_pin=rx_pin_num,
                        signal=signal,
                        register=mux.get('register'),
                        bit=mux.get('bit'),
                        af_number=af_num,
                        af_enum=get_af_enum_name(af_num, iomm_manifest),
                        data_source="pinmux_complete"
                    ))
                else:
                    pins.append(PinMapping(
                        package_pin=rx_pin_num,
                        signal=signal,
                        register=None,
                        bit=None,
                        af_number=None,
                        af_enum=None,
                        data_source="pinmux_partial"
                    ))
            else:
                pins.append(PinMapping(
                    package_pin=rx_pin_num,
                    signal=signal,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="board_only"
                ))

        # Extract TX pin
        tx_pin_num = instance_config.get('tx_pin')
        if tx_pin_num:
            signal = f"{instance_upper}TX"
            pin_data = find_pin_in_pinmux(tx_pin_num, pinmux_data)

            if pin_data:
                func = find_signal_in_pin(pin_data, signal)

                # Try alternative signal name if LIN signal not found
                # (LIN can use SCI pins when operating in SCI/UART mode)
                if not func or not func.get('mux'):
                    func = find_signal_in_pin(pin_data, "SCITX")
                    if func and func.get('mux'):
                        signal = "SCITX"  # Update signal name to match pinmux

                if func and func.get('mux'):
                    mux = func['mux']
                    af_num = int(func.get('af', 0))
                    pins.append(PinMapping(
                        package_pin=tx_pin_num,
                        signal=signal,
                        register=mux.get('register'),
                        bit=mux.get('bit'),
                        af_number=af_num,
                        af_enum=get_af_enum_name(af_num, iomm_manifest),
                        data_source="pinmux_complete"
                    ))
                else:
                    pins.append(PinMapping(
                        package_pin=tx_pin_num,
                        signal=signal,
                        register=None,
                        bit=None,
                        af_number=None,
                        af_enum=None,
                        data_source="pinmux_partial"
                    ))
            else:
                pins.append(PinMapping(
                    package_pin=tx_pin_num,
                    signal=signal,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="board_only"
                ))

        if pins:
            instances[instance_name] = pins

    return instances


def extract_sci_instances(board_data: Dict, pinmux_data: List[Dict], iomm_manifest: Optional[Dict] = None) -> Dict[str, List[PinMapping]]:
    """
    Extract SCI (UART) peripheral instance.

    Args:
        board_data: Parsed board.yaml
        pinmux_data: Parsed pinmux.yaml pin list
        iomm_manifest: IOMM module manifest from Pass 1

    Returns:
        Dict with single "sci" instance
    """
    instances = {}
    pins = []

    sci_config = board_data.get('communication', {}).get('uart', {}).get('sci', {})

    # Extract RX pin
    rx_pin_num = sci_config.get('rx_pin')
    if rx_pin_num:
        signal = "SCIRX"
        pin_data = find_pin_in_pinmux(rx_pin_num, pinmux_data)

        if pin_data:
            func = find_signal_in_pin(pin_data, signal)
            if func and func.get('mux'):
                mux = func['mux']
                af_num = int(func.get('af', 0))
                pins.append(PinMapping(
                    package_pin=rx_pin_num,
                    signal=signal,
                    register=mux.get('register'),
                    bit=mux.get('bit'),
                    af_number=af_num,
                    af_enum=get_af_enum_name(af_num, iomm_manifest),
                    data_source="pinmux_complete"
                ))
            else:
                pins.append(PinMapping(
                    package_pin=rx_pin_num,
                    signal=signal,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="pinmux_partial"
                ))
        else:
            pins.append(PinMapping(
                package_pin=rx_pin_num,
                signal=signal,
                register=None,
                bit=None,
                af_number=None,
                af_enum=None,
                data_source="board_only"
            ))

    # Extract TX pin
    tx_pin_num = sci_config.get('tx_pin')
    if tx_pin_num:
        signal = "SCITX"
        pin_data = find_pin_in_pinmux(tx_pin_num, pinmux_data)

        if pin_data:
            func = find_signal_in_pin(pin_data, signal)
            if func and func.get('mux'):
                mux = func['mux']
                af_num = int(func.get('af', 0))
                pins.append(PinMapping(
                    package_pin=tx_pin_num,
                    signal=signal,
                    register=mux.get('register'),
                    bit=mux.get('bit'),
                    af_number=af_num,
                    af_enum=get_af_enum_name(af_num, iomm_manifest),
                    data_source="pinmux_complete"
                ))
            else:
                pins.append(PinMapping(
                    package_pin=tx_pin_num,
                    signal=signal,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="pinmux_partial"
                ))
        else:
            pins.append(PinMapping(
                package_pin=tx_pin_num,
                signal=signal,
                register=None,
                bit=None,
                af_number=None,
                af_enum=None,
                data_source="board_only"
            ))

    if pins:
        instances['sci'] = pins

    return instances


def extract_gpio_instances(board_data: Dict, pinmux_data: List[Dict], iomm_manifest: Optional[Dict] = None) -> Dict[str, List[PinMapping]]:
    """
    Extract GPIO pins from LEDs, buttons, and other GPIO sources.

    Args:
        board_data: Parsed board.yaml
        pinmux_data: Parsed pinmux.yaml pin list
        iomm_manifest: IOMM module manifest from Pass 1

    Returns:
        Dict with single "gio" instance containing all GPIO pins
    """
    instances = {}
    pins = []

    # Extract LED pins
    leds = board_data.get('leds', [])
    for led in leds:
        if not isinstance(led, dict):
            continue

        pin_num = led.get('mcu_pin')
        gpio_name = led.get('gpio', '')

        if pin_num and gpio_name:
            pin_data = find_pin_in_pinmux(pin_num, pinmux_data)
            fallback_match = None

            if pin_data:
                func = find_signal_in_pin(pin_data, gpio_name)
                if (not func or not func.get('mux')):
                    fallback_match = find_signal_in_pinmux(pinmux_data, gpio_name)
                    if fallback_match:
                        fallback_pin, fallback_func = fallback_match
                        if fallback_pin.get('package_pin') != pin_num:
                            logger.warning(
                                "GPIO mapping conflict for LED '%s': board mcu_pin=%s but signal %s resolves to pin %s in pinmux. "
                                "Using signal fallback.",
                                led.get('designator', '?'),
                                pin_num,
                                gpio_name,
                                fallback_pin.get('package_pin'),
                            )
                        pin_data = fallback_pin
                        func = fallback_func

                if func and func.get('mux'):
                    mux = func['mux']
                    af_num = int(func.get('af', 0))
                    pins.append(PinMapping(
                        package_pin=int(pin_data.get('package_pin', pin_num)),
                        signal=gpio_name,
                        register=mux.get('register'),
                        bit=mux.get('bit'),
                        af_number=af_num,
                        af_enum=get_af_enum_name(af_num, iomm_manifest),
                        data_source="pinmux_signal_fallback" if fallback_match else "pinmux_complete"
                    ))
                else:
                    pins.append(PinMapping(
                        package_pin=pin_num,
                        signal=gpio_name,
                        register=None,
                        bit=None,
                        af_number=None,
                        af_enum=None,
                        data_source="pinmux_partial"
                    ))
            else:
                pins.append(PinMapping(
                    package_pin=pin_num,
                    signal=gpio_name,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="board_only"
                ))

    # Extract button pins
    buttons = board_data.get('buttons', [])
    for button in buttons:
        if not isinstance(button, dict):
            continue

        pin_num = button.get('mcu_pin')
        gpio_name = button.get('gpio', '')

        if pin_num and gpio_name:
            pin_data = find_pin_in_pinmux(pin_num, pinmux_data)
            fallback_match = None

            if pin_data:
                func = find_signal_in_pin(pin_data, gpio_name)
                if (not func or not func.get('mux')):
                    fallback_match = find_signal_in_pinmux(pinmux_data, gpio_name)
                    if fallback_match:
                        fallback_pin, fallback_func = fallback_match
                        if fallback_pin.get('package_pin') != pin_num:
                            logger.warning(
                                "GPIO mapping conflict for button '%s': board mcu_pin=%s but signal %s resolves to pin %s in pinmux. "
                                "Using signal fallback.",
                                button.get('designator', '?'),
                                pin_num,
                                gpio_name,
                                fallback_pin.get('package_pin'),
                            )
                        pin_data = fallback_pin
                        func = fallback_func

                if func and func.get('mux'):
                    mux = func['mux']
                    af_num = int(func.get('af', 0))
                    pins.append(PinMapping(
                        package_pin=int(pin_data.get('package_pin', pin_num)),
                        signal=gpio_name,
                        register=mux.get('register'),
                        bit=mux.get('bit'),
                        af_number=af_num,
                        af_enum=get_af_enum_name(af_num, iomm_manifest),
                        data_source="pinmux_signal_fallback" if fallback_match else "pinmux_complete"
                    ))
                else:
                    pins.append(PinMapping(
                        package_pin=pin_num,
                        signal=gpio_name,
                        register=None,
                        bit=None,
                        af_number=None,
                        af_enum=None,
                        data_source="pinmux_partial"
                    ))
            else:
                pins.append(PinMapping(
                    package_pin=pin_num,
                    signal=gpio_name,
                    register=None,
                    bit=None,
                    af_number=None,
                    af_enum=None,
                    data_source="board_only"
                ))

    if pins:
        instances['gio'] = pins

    return instances


def extract_peripheral_instances(
    board_data: Dict[str, Any],
    pinmux_data: Dict[str, Any],
    peripheral: str,
    iomm_manifest: Optional[Dict] = None
) -> Optional[Dict[str, List[PinMapping]]]:
    """
    Main dispatcher function to extract per-instance pin configurations.

    Args:
        board_data: Parsed board.yaml
        pinmux_data: Parsed pinmux.yaml (contains 'pins' list)
        peripheral: Peripheral name (e.g., "CAN", "SCI", "GIO", "LIN")
        iomm_manifest: IOMM module manifest from Pass 1 (for correct enum value names)

    Returns:
        Dict mapping instance names to pin lists, or None if peripheral not found

    Example return:
        {
            "dcan1": [PinMapping(90, "DCAN1RX", ...), PinMapping(89, "DCAN1TX", ...)],
            "dcan2": [PinMapping(129, "DCAN2RX", ...), PinMapping(128, "DCAN2TX", ...)]
        }
    """
    if not board_data or not pinmux_data:
        logger.warning("Missing board_data or pinmux_data")
        return None

    # Extract pins list from pinmux_data
    pins_list = pinmux_data.get('pins', [])
    if not pins_list:
        logger.warning("No pins found in pinmux_data")
        return None

    peripheral_upper = peripheral.upper()

    # Dispatch to appropriate extractor (passing iomm_manifest through)
    if peripheral_upper in ['CAN', 'DCAN']:
        instances = extract_can_instances(board_data, pins_list, iomm_manifest)
    elif peripheral_upper == 'LIN':
        instances = extract_lin_instances(board_data, pins_list, iomm_manifest)
    elif peripheral_upper in ['SCI', 'UART']:
        instances = extract_sci_instances(board_data, pins_list, iomm_manifest)
    elif peripheral_upper in ['GIO', 'GPIO']:
        instances = extract_gpio_instances(board_data, pins_list, iomm_manifest)
    else:
        logger.warning(f"Unknown peripheral: {peripheral}")
        return None

    if not instances:
        logger.info(f"No instances found for peripheral: {peripheral}")
        return None

    return instances


def format_instance_data_for_llm(instance_pin_config: Dict[str, List[PinMapping]]) -> str:
    """
    Format instance pin configuration data into readable text for LLM prompts.

    Args:
        instance_pin_config: Dict of instance names to pin mappings

    Returns:
        Formatted string with pin configuration details and data source warnings

    Example output:
        Instance: dcan1
          Pin 90: DCAN1RX [Board only - see TRM for PINMMR configuration]
          Pin 89: DCAN1TX [Board only - see TRM for PINMMR configuration]

        Note: Pinmux data incomplete. Consult TRM Section 4 for complete register definitions.
    """
    if not instance_pin_config:
        return ""

    lines = []
    has_incomplete_data = False

    for instance_name, pins in instance_pin_config.items():
        lines.append(f"\nInstance: {instance_name}")

        for pin in pins:
            pin_info = f"  Pin {pin.package_pin}: {pin.signal}"

            if pin.data_source == "pinmux_complete":
                # Use enum name if available, otherwise fall back to AF number
                if pin.af_enum:
                    pin_info += f" ({pin.register}[{pin.bit}], {pin.af_enum})"
                else:
                    pin_info += f" ({pin.register}[{pin.bit}], AF{pin.af_number})"
            elif pin.data_source == "pinmux_signal_fallback":
                if pin.af_enum:
                    pin_info += f" ({pin.register}[{pin.bit}], {pin.af_enum})"
                else:
                    pin_info += f" ({pin.register}[{pin.bit}], AF{pin.af_number})"
                pin_info += " [Signal fallback: board pin mismatch corrected via pinmux signal mapping]"
            elif pin.data_source == "pinmux_partial":
                if pin.register and pin.bit is not None:
                    pin_info += f" ({pin.register}[{pin.bit}]"
                    if pin.af_enum:
                        pin_info += f", {pin.af_enum}"
                    elif pin.af_number is not None:
                        pin_info += f", AF{pin.af_number}"
                    pin_info += ")"
                pin_info += " [Partial: Check TRM for alternate function]"
                has_incomplete_data = True
            else:  # board_only
                pin_info += " [Board only - see TRM for PINMMR configuration]"
                has_incomplete_data = True

            lines.append(pin_info)

    if has_incomplete_data:
        lines.append("\nNote: Pinmux data incomplete. Consult TRM Section 4 for complete register definitions.")

    return '\n'.join(lines)
