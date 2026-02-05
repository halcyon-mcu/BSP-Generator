#!/usr/bin/env python3
"""
create_board_yaml.py

Transform schematic_extracted_data.yaml into board.yaml following board.schema.yaml
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_yaml(filepath: Path) -> Dict:
    """Load YAML file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(filepath: Path, data: Dict):
    """Save YAML file with nice formatting."""
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                 allow_unicode=True, width=120)


def transform_to_board_yaml(schematic_data: Dict) -> Dict:
    """Transform schematic data to board.yaml format."""

    board_yaml = {
        'ir_schema_version': '1.1.0',

        # Board identification
        'board': {
            'name': schematic_data['board_name'],
            'revision': 'Rev 1.0',  # Could be extracted if in schematic
            'manufacturer': 'Texas Instruments',
            'schematic': {
                'source': schematic_data['schematic_source'],
                'revision_date': schematic_data['schematic_revision_date']
            }
        },

        # MCU information
        'mcu': {
            'part_number': schematic_data['mcu']['part_number'],
            'package': schematic_data['mcu']['package'],
            'pin_count': schematic_data['mcu']['pin_count']
        },

        # Power supply
        'power': {},

        # Clock system
        'clock': {},

        # LEDs
        'leds': [],

        # Buttons
        'buttons': [],

        # Sensors
        'sensors': [],

        # Debug interfaces
        'debug': {},

        # Expansion connectors
        'connectors': [],

        # Extended information
        'x-ext': {
            'extraction_date': schematic_data['extraction_date']
        }
    }

    # Power supply details
    if 'power_supply' in schematic_data:
        power = schematic_data['power_supply']

        # Regulators
        if 'regulators' in power:
            board_yaml['power']['regulators'] = []

            # Main dual buck regulator
            if 'main_dual_buck' in power['regulators']:
                buck = power['regulators']['main_dual_buck']
                regulator = {
                    'designator': buck.get('designator', 'U5'),
                    'part_number': buck['part_number'],
                    'type': 'buck',
                    'switching_frequency': buck.get('switching_frequency'),
                    'channels': []
                }

                # Channel 1 (1.2V)
                if 'channel_1' in buck:
                    ch1 = buck['channel_1']
                    regulator['channels'].append({
                        'channel': 1,
                        'output_voltage': ch1['output_voltage'],
                        'current_rating': ch1['current_rating'],
                        'net_name': ch1['net_name'],
                        'description': ch1['description']
                    })

                # Channel 2 (3.3V)
                if 'channel_2' in buck:
                    ch2 = buck['channel_2']
                    regulator['channels'].append({
                        'channel': 2,
                        'output_voltage': ch2['output_voltage'],
                        'current_rating': ch2['current_rating'],
                        'net_name': ch2['net_name'],
                        'description': ch2['description']
                    })

                board_yaml['power']['regulators'].append(regulator)

        # Voltage rails
        if 'voltage_rails' in power:
            board_yaml['power']['voltage_rails'] = {}
            rails = power['voltage_rails']

            for rail_name, rail_data in rails.items():
                board_yaml['power']['voltage_rails'][rail_name] = {
                    'voltage': rail_data.get('voltage'),
                    'description': rail_data.get('description'),
                    'mcu_pins': rail_data.get('mcu_pins', [])
                }

    # Clock system
    if 'clock_system' in schematic_data:
        clock = schematic_data['clock_system']['main_crystal']
        board_yaml['clock']['crystal'] = {
            'designator': clock['designator'],
            'part_number': clock.get('part_description', 'Unknown'),
            'frequency_hz': clock['frequency_hz'],
            'frequency_mhz': clock['frequency_mhz'],
            'pins': {
                'oscin': clock['pins']['oscin']['mcu_pin'],
                'oscout': clock['pins']['oscout']['mcu_pin'],
                'kelvin_gnd': clock['pins']['kelvin_gnd']['mcu_pin']
            },
            'load_capacitors': [
                {
                    'designator': cap['designator'],
                    'value': cap['value'],
                    'tolerance': cap.get('tolerance'),
                    'connected_to_pin': cap['pin']
                }
                for cap in clock['load_capacitors']
            ]
        }

    # LEDs
    if 'leds' in schematic_data:
        # Error LED
        if 'error_led' in schematic_data['leds']:
            led = schematic_data['leds']['error_led']
            board_yaml['leds'].append({
                'designator': led['designator'],
                'function': led['function'],
                'color': led['color'],
                'mcu_pin': led['mcu_pin'],
                'net_name': led['net_name'],
                'series_resistor': led['series_resistor']['value'],
                'active_state': led['active'],
                'description': led.get('description')
            })

        # User LEDs
        if 'user_leds' in schematic_data['leds']:
            for led in schematic_data['leds']['user_leds']:
                board_yaml['leds'].append({
                    'designator': led['designator'],
                    'function': led['function'],
                    'color': led['color'],
                    'mcu_pin': led['mcu_pin'],
                    'gpio': led['gpio'],
                    'net_name': led['net_name'],
                    'series_resistor': led['series_resistor']['value'],
                    'active_state': led['active']
                })

        # Power LEDs (for reference)
        if 'power_leds' in schematic_data['leds']:
            board_yaml['x-ext']['power_leds'] = [
                {
                    'designator': led['designator'],
                    'function': led['function'],
                    'color': led['color'],
                    'series_resistor': led['series_resistor']['value']
                }
                for led in schematic_data['leds']['power_leds']
            ]

    # Buttons
    if 'buttons' in schematic_data:
        if 'user_buttons' in schematic_data['buttons']:
            for btn in schematic_data['buttons']['user_buttons']:
                button = {
                    'designator': btn['designator'],
                    'function': btn['function'],
                    'type': btn['type'],
                    'active_state': btn['active']
                }

                if 'mcu_pin' in btn:
                    button['mcu_pin'] = btn['mcu_pin']

                if 'net_name' in btn:
                    button['net_name'] = btn['net_name']

                if 'pull_up' in btn:
                    button['pull_resistor'] = btn['pull_up']['value']
                    button['pull_direction'] = 'up'

                board_yaml['buttons'].append(button)

    # Sensors
    if 'sensors' in schematic_data:
        if 'light_sensor' in schematic_data['sensors']:
            sensor = schematic_data['sensors']['light_sensor']
            board_yaml['sensors'].append({
                'designator': sensor['designator'],
                'part_number': sensor['part_number'],
                'type': sensor['type'],
                'mcu_pin': sensor['mcu_pin'],
                'interface': 'analog',
                'adc_channel': sensor['output_pin'],
                'bias_resistor': sensor['bias_resistor']['value'],
                'filter_capacitor': sensor['filter_capacitor']['value'],
                'description': sensor['description']
            })

    # Debug interfaces
    if 'debug' in schematic_data:
        if 'jtag_hercules' in schematic_data['debug']:
            jtag = schematic_data['debug']['jtag_hercules']
            board_yaml['debug']['jtag'] = {
                'connector': jtag['connector'],
                'connector_type': jtag['connector_type'],
                'description': jtag['description'],
                'signals': {}
            }

            # Add key JTAG signals
            for signal_name, signal_data in jtag['signals'].items():
                board_yaml['debug']['jtag']['signals'][signal_name] = {
                    'mcu_pin': signal_data['mcu_pin'],
                    'net_name': signal_data['net_name']
                }

                if 'pull_up' in signal_data:
                    board_yaml['debug']['jtag']['signals'][signal_name]['pull_up'] = signal_data['pull_up']['value']
                if 'pull_down' in signal_data:
                    board_yaml['debug']['jtag']['signals'][signal_name]['pull_down'] = signal_data['pull_down']['value']

    if 'usb' in schematic_data and 'debug_usb' in schematic_data['usb']:
        usb = schematic_data['usb']['debug_usb']
        board_yaml['debug']['usb'] = {
            'connector': usb['connector'],
            'connector_type': usb['connector_type'],
            'function': usb['function']
        }

    # Expansion connectors (BoosterPack)
    # For now, just add high-level info
    board_yaml['connectors'].append({
        'type': 'BoosterPack Site 1',
        'pins': 40,
        'description': 'TI BoosterPack expansion connector site 1'
    })
    board_yaml['connectors'].append({
        'type': 'BoosterPack Site 2',
        'pins': 40,
        'description': 'TI BoosterPack expansion connector site 2'
    })
    board_yaml['connectors'].append({
        'type': 'Proto Header',
        'pins': 50,
        'description': 'General purpose prototype header'
    })

    # Add reset circuit info to x-ext
    if 'reset' in schematic_data:
        board_yaml['x-ext']['reset'] = {
            'supervisor': schematic_data['reset']['supervisor'],
            'buttons': schematic_data['reset']['buttons']
        }

    # Add ADC channels to x-ext
    if 'adc' in schematic_data:
        board_yaml['x-ext']['adc_channels'] = schematic_data['adc']['channels']

    return board_yaml


def main():
    schematic_file = Path('../yaml_out/schematic_extracted_data.yaml')
    output_file = Path('yaml_in_transformed/board.yaml')

    print("="*80)
    print("CREATING BOARD.YAML FROM SCHEMATIC DATA")
    print("="*80)
    print()

    print(f"Loading schematic data from {schematic_file}...")
    schematic_data = load_yaml(schematic_file)
    print(f"[OK] Loaded schematic for board: {schematic_data['board_name']}")
    print()

    print("Transforming to board.yaml format...")
    board_yaml = transform_to_board_yaml(schematic_data)
    print("[OK] Transformation complete")
    print()

    print(f"Saving to {output_file}...")
    save_yaml(output_file, board_yaml)
    print("[OK] board.yaml created")
    print()

    print("="*80)
    print("BOARD.YAML CREATION COMPLETE")
    print("="*80)
    print()
    print("Summary:")
    print(f"- Board: {board_yaml['board']['name']}")
    print(f"- MCU: {board_yaml['mcu']['part_number']}")
    print(f"- LEDs: {len(board_yaml['leds'])}")
    print(f"- Buttons: {len(board_yaml['buttons'])}")
    print(f"- Sensors: {len(board_yaml['sensors'])}")
    print(f"- Regulators: {len(board_yaml['power'].get('regulators', []))}")
    print()
    print("Next step: Validate board.yaml against board.schema.yaml")


if __name__ == '__main__':
    main()
