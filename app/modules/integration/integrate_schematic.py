#!/usr/bin/env python3
"""
integrate_schematic_to_yamls.py

Integrate schematic-extracted board-level information into BSP YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_yaml(filepath: Path) -> Dict:
    """Load YAML file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(filepath: Path, data: Dict):
    """Save YAML file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                 allow_unicode=True, width=120)


def integrate_clock_to_bus(bus_data: Dict, schematic_data: Dict) -> Dict:
    """Add crystal information from schematic to bus.yaml."""

    clock_sys = schematic_data['clock_system']['main_crystal']

    # Add crystal information to clock sources if not already present
    if 'clock_sources' not in bus_data:
        bus_data['clock_sources'] = {}

    # Add external crystal as a clock source
    bus_data['clock_sources']['XTAL'] = {
        'type': 'crystal',
        'frequency_hz': clock_sys['frequency_hz'],
        'x-ext': {
            'schematic': {
                'designator': clock_sys['designator'],
                'frequency_mhz': clock_sys['frequency_mhz'],
                'load_capacitors': [
                    {
                        'designator': cap['designator'],
                        'value': cap['value'],
                        'tolerance': cap['tolerance'],
                        'pin': cap['pin']
                    }
                    for cap in clock_sys['load_capacitors']
                ],
                'pins': {
                    'oscin': clock_sys['pins']['oscin']['mcu_pin'],
                    'oscout': clock_sys['pins']['oscout']['mcu_pin'],
                    'kelvin_gnd': clock_sys['pins']['kelvin_gnd']['mcu_pin']
                },
                'source': schematic_data['schematic_source']
            }
        }
    }

    return bus_data


def integrate_pins_to_pinmux(pinmux_data: Dict, schematic_data: Dict) -> Dict:
    """Add board-level information from schematic to pinmux.yaml."""

    # Build pin lookup from schematic data
    pin_info = {}

    # Extract LED connections
    if 'leds' in schematic_data:
        # Error LED
        if 'error_led' in schematic_data['leds']:
            led = schematic_data['leds']['error_led']
            pin_info[led['mcu_pin']] = {
                'board_function': f"{led['function']} ({led['color']})",
                'net_name': led['net_name'],
                'component': led['designator'],
                'series_resistor': led['series_resistor']['value'],
                'active': led['active']
            }

        # User LEDs
        if 'user_leds' in schematic_data['leds']:
            for led in schematic_data['leds']['user_leds']:
                pin_info[led['mcu_pin']] = {
                    'board_function': f"{led['function']} ({led['color']})",
                    'net_name': led['net_name'],
                    'component': led['designator'],
                    'series_resistor': led['series_resistor']['value'],
                    'gpio': led['gpio'],
                    'active': led['active']
                }

    # Extract button connections
    if 'buttons' in schematic_data:
        if 'user_buttons' in schematic_data['buttons']:
            for btn in schematic_data['buttons']['user_buttons']:
                if 'mcu_pin' in btn:
                    pin_info[btn['mcu_pin']] = {
                        'board_function': btn['function'],
                        'net_name': btn['net_name'],
                        'component': btn['designator'],
                        'pull_up': btn['pull_up']['value'],
                        'active': btn['active']
                    }

    # Extract JTAG connections
    if 'debug' in schematic_data and 'jtag_hercules' in schematic_data['debug']:
        jtag = schematic_data['debug']['jtag_hercules']['signals']
        for signal_name, signal_data in jtag.items():
            pin_info[signal_data['mcu_pin']] = {
                'board_function': f"JTAG {signal_name.upper()}",
                'net_name': signal_data['net_name'],
                'description': signal_data['description']
            }
            if 'pull_up' in signal_data:
                pin_info[signal_data['mcu_pin']]['pull_up'] = signal_data['pull_up']['value']
            if 'pull_down' in signal_data:
                pin_info[signal_data['mcu_pin']]['pull_down'] = signal_data['pull_down']['value']

    # Extract reset connections
    if 'reset' in schematic_data and 'mcu_connections' in schematic_data['reset']:
        for conn_name, conn_data in schematic_data['reset']['mcu_connections'].items():
            pin_info[conn_data['mcu_pin']] = {
                'board_function': f"RESET ({conn_name.upper()})",
                'net_name': conn_data['net_name'],
                'description': conn_data['description']
            }
            if 'pull_up' in conn_data:
                pin_info[conn_data['mcu_pin']]['pull_up'] = conn_data['pull_up']['value']
            if 'decoupling' in conn_data:
                pin_info[conn_data['mcu_pin']]['decoupling'] = {
                    'capacitor': conn_data['decoupling']['value'],
                    'to_ground': True
                }

    # Extract clock pins
    if 'clock_system' in schematic_data:
        clock_pins = schematic_data['clock_system']['main_crystal']['pins']
        for pin_name, pin_data in clock_pins.items():
            pin_info[pin_data['mcu_pin']] = {
                'board_function': f"Clock {pin_name.upper()}",
                'net_name': pin_data['net_name'],
                'description': pin_data.get('description', f'Crystal {pin_name}')
            }

    # Extract light sensor
    if 'sensors' in schematic_data and 'light_sensor' in schematic_data['sensors']:
        sensor = schematic_data['sensors']['light_sensor']
        pin_info[sensor['mcu_pin']] = {
            'board_function': "Light Sensor Input",
            'net_name': sensor['output_pin'],
            'component': f"{sensor['designator']} ({sensor['part_number']})",
            'description': sensor['description']
        }

    # Now integrate into pinmux.yaml
    if 'pins' not in pinmux_data:
        print("[WARNING] No pins found in pinmux.yaml")
        return pinmux_data

    # Add board section and x-ext to relevant pins
    pins_enhanced = 0
    for pin in pinmux_data['pins']:
        # Try to match by package_pin number
        pkg_pin = pin.get('package_pin')

        # Try to extract numeric pin if it's not already a number
        if isinstance(pkg_pin, str):
            # Handle letter-number format like "C12"
            continue

        pin_num = pkg_pin

        if pin_num in pin_info:
            info = pin_info[pin_num]

            # Add or update board section
            if 'board' not in pin:
                pin['board'] = {}

            # Update net name with schematic info
            pin['board']['net'] = info['net_name']

            # Add x-ext with schematic information
            if 'x-ext' not in pin:
                pin['x-ext'] = {}

            pin['x-ext']['schematic'] = {
                'function': info.get('board_function'),
                'description': info.get('description')
            }

            if 'component' in info:
                pin['x-ext']['schematic']['component'] = info['component']

            if 'series_resistor' in info:
                pin['x-ext']['schematic']['series_resistor'] = info['series_resistor']

            if 'pull_up' in info:
                pin['x-ext']['schematic']['pull_up'] = info['pull_up']

            if 'pull_down' in info:
                pin['x-ext']['schematic']['pull_down'] = info['pull_down']

            if 'active' in info:
                pin['x-ext']['schematic']['active_state'] = info['active']

            if 'decoupling' in info:
                pin['x-ext']['schematic']['decoupling'] = info['decoupling']

            if 'gpio' in info:
                pin['x-ext']['schematic']['gpio'] = info['gpio']

            pins_enhanced += 1

    print(f"[OK] Enhanced {pins_enhanced} pins with schematic information")

    # Add provenance for schematic data
    if 'provenance' not in pinmux_data:
        pinmux_data['provenance'] = {}

    pinmux_data['provenance']['schematic_integrated'] = {
        'source': schematic_data['schematic_source'],
        'board': schematic_data['board_name'],
        'date': schematic_data['extraction_date']
    }

    return pinmux_data


def add_board_metadata_to_soc(soc_data: Dict, schematic_data: Dict) -> Dict:
    """Add board-level metadata to soc.yaml."""

    # Add board information at top level
    soc_data['board'] = {
        'name': schematic_data['board_name'],
        'mcu': schematic_data['mcu']['part_number'],
        'package': schematic_data['mcu']['package'],
        'schematic_source': schematic_data['schematic_source'],
        'schematic_revision': schematic_data['schematic_revision_date']
    }

    # Add power supply information
    if 'power_supply' in schematic_data:
        power = schematic_data['power_supply']
        soc_data['board']['power'] = {
            'vcc': f"{power['voltage_rails']['vcc_1v2']['voltage']}V",
            'vccio': f"{power['voltage_rails']['vccio_3v3']['voltage']}V",
            'regulator': power['regulators']['main_dual_buck']['part_number']
        }

    return soc_data


def main():
    yaml_dir = Path('yaml_in_transformed')
    schematic_file = Path('../yaml_out/schematic_extracted_data.yaml')

    print("="*80)
    print("INTEGRATING SCHEMATIC DATA INTO BSP YAML FILES")
    print("="*80)
    print()

    # Load schematic data
    print(f"Loading schematic data from {schematic_file}...")
    schematic_data = load_yaml(schematic_file)
    print(f"[OK] Loaded schematic for board: {schematic_data['board_name']}")
    print()

    # Integrate into bus.yaml
    print("Integrating clock information into bus.yaml...")
    bus_file = yaml_dir / 'bus.yaml'
    bus_data = load_yaml(bus_file)
    bus_data = integrate_clock_to_bus(bus_data, schematic_data)
    save_yaml(bus_file, bus_data)
    print("[OK] bus.yaml updated with crystal information")
    print()

    # Integrate into pinmux.yaml
    print("Integrating pin information into pinmux.yaml...")
    pinmux_file = yaml_dir / 'pinmux.yaml'
    pinmux_data = load_yaml(pinmux_file)
    pinmux_data = integrate_pins_to_pinmux(pinmux_data, schematic_data)
    save_yaml(pinmux_file, pinmux_data)
    print("[OK] pinmux.yaml updated with board-level pin information")
    print()

    # Integrate into soc.yaml
    print("Adding board metadata to soc.yaml...")
    soc_file = yaml_dir / 'soc.yaml'
    soc_data = load_yaml(soc_file)
    soc_data = add_board_metadata_to_soc(soc_data, schematic_data)
    save_yaml(soc_file, soc_data)
    print("[OK] soc.yaml updated with board metadata")
    print()

    print("="*80)
    print("[OK] SCHEMATIC INTEGRATION COMPLETE")
    print("="*80)
    print()
    print("Summary:")
    print("- bus.yaml: Added crystal configuration")
    print("- pinmux.yaml: Added board-level pin information")
    print("- soc.yaml: Added board metadata")
    print()
    print("Next step: Validate schemas")


if __name__ == '__main__':
    main()
