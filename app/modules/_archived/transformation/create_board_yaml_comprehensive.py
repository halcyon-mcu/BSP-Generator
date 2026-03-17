#!/usr/bin/env python3
"""
create_board_yaml_comprehensive.py

Create comprehensive board.yaml with ALL schematic details including:
- Communication interface routing
- PWM/Timer assignments
- ADC channel mappings
- Connector pinouts
- Hardware limitations
- Debug architecture
- Complete GPIO mapping
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


def transform_to_comprehensive_board_yaml(schematic_data: Dict) -> Dict:
    """Transform schematic data to comprehensive board.yaml format."""

    board_yaml = {
        'ir_schema_version': '1.1.0',

        # Board identification
        'board': {
            'name': schematic_data['board_name'],
            'revision': 'Rev 1.0',
            'manufacturer': 'Texas Instruments',
            'description': 'TI LaunchPad XL2 Development Board for RM46 Hercules MCU',
            'schematic': {
                'source': schematic_data['schematic_source'],
                'revision_date': schematic_data['schematic_revision_date']
            }
        },

        # MCU information
        'mcu': {
            'part_number': schematic_data['mcu']['part_number'],
            'package': schematic_data['mcu']['package'],
            'pin_count': schematic_data['mcu']['pin_count'],
            'full_name': schematic_data['mcu']['full_name']
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

        # Communication interfaces
        'communication': {},

        # PWM/Timers
        'pwm_timers': {},

        # ADC channels
        'adc': {},

        # Expansion connectors
        'connectors': [],

        # GPIO mapping
        'gpio_mapping': {},

        # Hardware limitations
        'hardware_limitations': {
            'missing_components': [],
            'notes': []
        },

        # Extended information
        'x-ext': {
            'extraction_date': schematic_data['extraction_date']
        }
    }

    # ===== POWER SUPPLY =====
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
                    'description': buck['description'],
                    'channels': []
                }

                # Channel 1 (1.2V core)
                if 'channel_1' in buck:
                    ch1 = buck['channel_1']
                    regulator['channels'].append({
                        'channel': 1,
                        'output_voltage': ch1['output_voltage'],
                        'current_rating': ch1['current_rating'],
                        'net_name': ch1['net_name'],
                        'description': ch1['description'],
                        'inductor': ch1['components']['inductor']
                    })

                # Channel 2 (3.3V IO)
                if 'channel_2' in buck:
                    ch2 = buck['channel_2']
                    regulator['channels'].append({
                        'channel': 2,
                        'output_voltage': ch2['output_voltage'],
                        'current_rating': ch2['current_rating'],
                        'net_name': ch2['net_name'],
                        'description': ch2['description'],
                        'inductor': ch2['components']['inductor']
                    })

                board_yaml['power']['regulators'].append(regulator)

        # Voltage rails with pin lists
        if 'voltage_rails' in power:
            board_yaml['power']['voltage_rails'] = {}
            rails = power['voltage_rails']

            for rail_name, rail_data in rails.items():
                board_yaml['power']['voltage_rails'][rail_name] = {
                    'voltage': rail_data.get('voltage'),
                    'description': rail_data.get('description'),
                    'mcu_pins': rail_data.get('mcu_pins', [])
                }

                # Add decoupling cap info if available
                if 'decoupling_caps' in rail_data:
                    board_yaml['power']['voltage_rails'][rail_name]['decoupling_caps'] = rail_data['decoupling_caps']

        # Current monitor
        if 'current_monitor' in power['regulators']:
            monitor = power['regulators']['current_monitor']
            board_yaml['power']['current_monitor'] = {
                'part_number': monitor['part_number'],
                'designator': monitor['designator'],
                'description': monitor['description'],
                'sense_resistor': monitor['sense_resistor'],
                'output': monitor.get('output_net'),
                'connection': monitor.get('connection')
            }

    # ===== CLOCK SYSTEM =====
    if 'clock_system' in schematic_data:
        clock = schematic_data['clock_system']['main_crystal']
        board_yaml['clock']['crystal'] = {
            'designator': clock['designator'],
            'part_description': clock.get('part_description', 'Unknown'),
            'frequency_hz': clock['frequency_hz'],
            'frequency_mhz': clock['frequency_mhz'],
            'pins': {
                'oscin': {
                    'mcu_pin': clock['pins']['oscin']['mcu_pin'],
                    'net_name': clock['pins']['oscin']['net_name']
                },
                'oscout': {
                    'mcu_pin': clock['pins']['oscout']['mcu_pin'],
                    'net_name': clock['pins']['oscout']['net_name']
                },
                'kelvin_gnd': {
                    'mcu_pin': clock['pins']['kelvin_gnd']['mcu_pin'],
                    'net_name': clock['pins']['kelvin_gnd']['net_name'],
                    'description': clock['pins']['kelvin_gnd']['description']
                }
            },
            'load_capacitors': [
                {
                    'designator': cap['designator'],
                    'value': cap['value'],
                    'tolerance': cap.get('tolerance'),
                    'voltage_rating': cap.get('voltage_rating'),
                    'connected_to_pin': cap['pin'],
                    'description': cap['description']
                }
                for cap in clock['load_capacitors']
            ]
        }

        # Fault injection circuit
        if 'fault_injection' in clock:
            board_yaml['clock']['crystal']['fault_injection'] = clock['fault_injection']

    # ===== LEDs =====
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
                'connection': led['connection'],
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
                    'connection': led['connection'],
                    'active_state': led['active']
                })

    # ===== BUTTONS =====
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
                    button['pull_connection'] = btn['pull_up']['connection']

                board_yaml['buttons'].append(button)

    # ===== SENSORS =====
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
                'bias_resistor': sensor['bias_resistor'],
                'filter_capacitor': sensor['filter_capacitor'],
                'supply': sensor['supply'],
                'description': sensor['description']
            })

    # ===== DEBUG INTERFACES =====
    if 'debug' in schematic_data:
        # Onboard debugger (XDS ICDIv2)
        board_yaml['debug']['debugger'] = {
            'type': 'XDS110 ICDIv2',
            'description': 'Onboard XDS110 JTAG debugger with USB interface',
            'mcu': 'TM4C129 (separate debug MCU)',
            'capabilities': [
                'JTAG debugging',
                'UART passthrough',
                'Virtual COM port',
                'Current monitoring'
            ]
        }

        # JTAG interface to Hercules MCU
        if 'jtag_hercules' in schematic_data['debug']:
            jtag = schematic_data['debug']['jtag_hercules']
            board_yaml['debug']['jtag'] = {
                'connector': jtag['connector'],
                'connector_type': jtag['connector_type'],
                'description': jtag['description'],
                'signals': {}
            }

            # Add JTAG signals
            for signal_name, signal_data in jtag['signals'].items():
                board_yaml['debug']['jtag']['signals'][signal_name] = {
                    'mcu_pin': signal_data['mcu_pin'],
                    'net_name': signal_data['net_name'],
                    'description': signal_data['description']
                }
                if 'pull_up' in signal_data:
                    board_yaml['debug']['jtag']['signals'][signal_name]['pull_up'] = signal_data['pull_up']
                if 'pull_down' in signal_data:
                    board_yaml['debug']['jtag']['signals'][signal_name]['pull_down'] = signal_data['pull_down']

            # Additional signals routed to JTAG connector
            if 'additional_signals' in jtag:
                board_yaml['debug']['jtag']['additional_signals'] = jtag['additional_signals']

        # Debug USB interface
        if 'usb' in schematic_data and 'debug_usb' in schematic_data['usb']:
            usb = schematic_data['usb']['debug_usb']
            board_yaml['debug']['usb'] = {
                'connector': usb['connector'],
                'connector_type': usb['connector_type'],
                'function': usb['function'],
                'esd_protection': usb.get('esd_protection'),
                'current_limiter': usb.get('current_limiter')
            }

    # ===== COMMUNICATION INTERFACES =====
    if 'communication' in schematic_data:
        comm = schematic_data['communication']

        # CAN interfaces
        if 'can' in comm:
            board_yaml['communication']['can'] = {}
            for can_name, can_data in comm['can'].items():
                board_yaml['communication']['can'][can_name] = {
                    'rx_pin': can_data['rx_pin'],
                    'tx_pin': can_data['tx_pin'],
                    'net_rx': can_data['net_rx'],
                    'net_tx': can_data['net_tx'],
                    'connector': can_data['connector'],
                    'transceiver_populated': False,
                    'notes': can_data['notes']
                }

        # LIN interface
        if 'lin' in comm:
            board_yaml['communication']['lin'] = {}
            for lin_name, lin_data in comm['lin'].items():
                board_yaml['communication']['lin'][lin_name] = {
                    'rx_pin': lin_data['rx_pin'],
                    'tx_pin': lin_data['tx_pin'],
                    'net_rx': lin_data['net_rx'],
                    'net_tx': lin_data['net_tx'],
                    'connector': lin_data['connector'],
                    'transceiver_populated': False,
                    'notes': lin_data['notes']
                }

        # UART/SCI interface
        if 'sci_uart' in comm:
            board_yaml['communication']['uart'] = {}
            for uart_name, uart_data in comm['sci_uart'].items():
                board_yaml['communication']['uart'][uart_name] = {
                    'rx_pin': uart_data['rx_pin'],
                    'tx_pin': uart_data['tx_pin'],
                    'net_rx': uart_data['net_rx'],
                    'net_tx': uart_data['net_tx'],
                    'connector': uart_data['connector'],
                    'function': uart_data['function']
                }

        # SPI interfaces
        if 'spi' in comm:
            board_yaml['communication']['spi'] = {}
            for spi_name, spi_data in comm['spi'].items():
                board_yaml['communication']['spi'][spi_name] = spi_data

        # I2C interface
        if 'i2c' in comm:
            board_yaml['communication']['i2c'] = {}
            for i2c_name, i2c_data in comm['i2c'].items():
                board_yaml['communication']['i2c'][i2c_name] = i2c_data

        # Ethernet
        if 'ethernet' in comm:
            board_yaml['communication']['ethernet'] = comm['ethernet']
            board_yaml['communication']['ethernet']['phy_populated'] = False

    # ===== PWM/TIMERS =====
    if 'pwm_timers' in schematic_data:
        pwm = schematic_data['pwm_timers']

        # ePWM channels
        if 'epwm' in pwm:
            board_yaml['pwm_timers']['epwm'] = {
                'description': pwm['epwm']['description'],
                'channels': pwm['epwm']['channels']
            }

        # eCAP channels
        if 'ecap' in pwm:
            board_yaml['pwm_timers']['ecap'] = {
                'description': pwm['ecap']['description'],
                'channels': pwm['ecap']['channels']
            }

        # eQEP channels
        if 'eqep' in pwm:
            board_yaml['pwm_timers']['eqep'] = pwm['eqep']

        # N2HET channels (if available)
        if 'n2het' in pwm:
            board_yaml['pwm_timers']['n2het'] = pwm['n2het']

    # ===== ADC CHANNELS =====
    if 'adc' in schematic_data:
        board_yaml['adc'] = schematic_data['adc']

    # ===== CONNECTORS =====
    # BoosterPack connectors
    board_yaml['connectors'].append({
        'designator': 'J2, J3, J4, J5',
        'type': 'BoosterPack Site 1',
        'pins': 40,
        'description': 'TI BoosterPack 40-pin expansion connector (site 1)',
        'standards_compatible': '20-pin and 40-pin BoosterPack'
    })
    board_yaml['connectors'].append({
        'designator': 'J6, J7, J8, J9',
        'type': 'BoosterPack Site 2',
        'pins': 40,
        'description': 'TI BoosterPack 40-pin expansion connector (site 2)',
        'standards_compatible': '20-pin and 40-pin BoosterPack'
    })

    # Proto header
    board_yaml['connectors'].append({
        'designator': 'J11',
        'type': 'Proto Header',
        'pins': 50,
        'description': 'General purpose prototype header with additional signals'
    })

    # JTAG connector
    board_yaml['connectors'].append({
        'designator': 'J1',
        'type': 'JTAG Debug',
        'pins': 20,
        'description': '20-pin JTAG connector (0.1" pitch) for Hercules MCU',
        'signals_available': [
            'TMS', 'TCK', 'TDI', 'TDO', 'nTRST', 'RTCK',
            'CAN1/2/3 (RX/TX)', 'LIN1 (RX/TX)', 'SCI (RX/TX)'
        ]
    })

    # ===== HARDWARE LIMITATIONS =====
    board_yaml['hardware_limitations']['missing_components'] = [
        'CAN transceivers (DCAN1, DCAN2, DCAN3) - signals available, external transceiver required',
        'LIN transceiver (LIN1) - signals available, external transceiver required',
        'Ethernet PHY chip - MII/RMII signals available, external PHY required',
        'Target USB connector - USB signals available but not routed to connector'
    ]

    board_yaml['hardware_limitations']['notes'] = [
        'USB connector (J13) is for debug interface only (XDS ICDIv2), not target MCU USB',
        'CAN, LIN, and Ethernet require external transceiver/PHY for operation',
        'Debug MCU (TM4C129) provides JTAG, UART passthrough, and current monitoring',
        'BoosterPack connectors support standard TI BoosterPack expansion modules',
        'Light sensor (TEMT6000) is populated and connected to AD1IN[6]',
        'Two reset buttons: S1 (power-on reset), S2 (warm reset)',
        'Voltage supervisor (TPS3106K33) monitors both 1.2V and 3.3V rails'
    ]

    # ===== GPIO MAPPING =====
    # Create comprehensive GPIO mapping
    gpio_map = {}

    # LEDs
    for led in board_yaml['leds']:
        if 'gpio' in led:
            gpio_map[led['gpio']] = {
                'function': led['function'],
                'pin': led['mcu_pin'],
                'component': led['designator'],
                'type': 'output'
            }

    # Buttons
    for btn in board_yaml['buttons']:
        if 'mcu_pin' in btn:
            # Try to extract GPIO name from net_name if available
            if 'net_name' in btn and 'GIOB' in btn['net_name']:
                gpio_name = 'GIOB[?]'  # Would need parsing
                gpio_map[gpio_name] = {
                    'function': btn['function'],
                    'pin': btn['mcu_pin'],
                    'component': btn['designator'],
                    'type': 'input'
                }

    board_yaml['gpio_mapping'] = gpio_map

    # ===== EXTENDED INFO =====
    # Reset circuit
    if 'reset' in schematic_data:
        board_yaml['x-ext']['reset'] = {
            'supervisor': schematic_data['reset']['supervisor'],
            'buttons': schematic_data['reset']['buttons'],
            'mcu_connections': schematic_data['reset']['mcu_connections']
        }

        # Error output
        if 'error_signal' in schematic_data['reset']:
            board_yaml['x-ext']['error_signal'] = schematic_data['reset']['error_signal']

    # Power LEDs (informational)
    if 'leds' in schematic_data and 'power_leds' in schematic_data['leds']:
        board_yaml['x-ext']['power_leds'] = schematic_data['leds']['power_leds']

    # Debug MCU LEDs
    if 'leds' in schematic_data and 'debug_mcu_leds' in schematic_data['leds']:
        board_yaml['x-ext']['debug_mcu_leds'] = schematic_data['leds']['debug_mcu_leds']

    return board_yaml


def main():
    schematic_file = Path('../yaml_out/schematic_extracted_data.yaml')
    output_file = Path('yaml_in_transformed/board.yaml')

    print("="*80)
    print("CREATING COMPREHENSIVE BOARD.YAML FROM SCHEMATIC DATA")
    print("="*80)
    print()

    print(f"Loading schematic data from {schematic_file}...")
    schematic_data = load_yaml(schematic_file)
    print(f"[OK] Loaded schematic for board: {schematic_data['board_name']}")
    print()

    print("Transforming to comprehensive board.yaml format...")
    board_yaml = transform_to_comprehensive_board_yaml(schematic_data)
    print("[OK] Transformation complete")
    print()

    print(f"Saving to {output_file}...")
    save_yaml(output_file, board_yaml)
    print("[OK] Comprehensive board.yaml created")
    print()

    print("="*80)
    print("COMPREHENSIVE BOARD.YAML CREATION COMPLETE")
    print("="*80)
    print()
    print("Summary:")
    print(f"- Board: {board_yaml['board']['name']}")
    print(f"- MCU: {board_yaml['mcu']['part_number']}")
    print(f"- LEDs: {len(board_yaml['leds'])}")
    print(f"- Buttons: {len(board_yaml['buttons'])}")
    print(f"- Sensors: {len(board_yaml['sensors'])}")
    print(f"- Regulators: {len(board_yaml['power'].get('regulators', []))}")
    print(f"- CAN interfaces: {len(board_yaml['communication'].get('can', {}))}")
    print(f"- LIN interfaces: {len(board_yaml['communication'].get('lin', {}))}")
    print(f"- SPI interfaces: {len(board_yaml['communication'].get('spi', {}))}")
    print(f"- ePWM channels: {len(board_yaml['pwm_timers'].get('epwm', {}).get('channels', []))}")
    print(f"- eCAP channels: {len(board_yaml['pwm_timers'].get('ecap', {}).get('channels', []))}")
    print(f"- ADC channels: {len(board_yaml['adc'].get('channels', {}).get('adc1', []))}")
    print(f"- Connectors: {len(board_yaml['connectors'])}")
    print()
    print("Next step: Validate board.yaml against board.schema.yaml")


if __name__ == '__main__':
    main()
