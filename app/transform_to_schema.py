#!/usr/bin/env python3
"""
transform_to_schema.py

Transform extracted YAML files to BSP schema-compliant format.

Usage:
    python transform_to_schema.py --input yaml_in --output yaml_in_transformed
"""

import yaml
import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class SchemaTransformer:
    """Transform extracted YAMLs to BSP schema format."""

    def __init__(self, mappings_dir: Path = Path("mappings")):
        self.mappings_dir = mappings_dir
        self.periph_type_map = self.load_type_mapping()
        self.chip_metadata = self.load_chip_metadata()

    def load_type_mapping(self) -> Dict[str, str]:
        """Load peripheral name → type mapping."""
        mapping_file = self.mappings_dir / "peripheral_types.yaml"
        if not mapping_file.exists():
            print(f"[WARN] Mapping file not found: {mapping_file}")
            return {}
        with open(mapping_file) as f:
            return yaml.safe_load(f)

    def load_chip_metadata(self) -> Dict:
        """Load chip metadata (chip, vendor, cpu, etc.)."""
        metadata_file = self.mappings_dir / "chip_metadata.yaml"
        if not metadata_file.exists():
            print(f"[WARN] Metadata file not found: {metadata_file}")
            return {}
        with open(metadata_file) as f:
            return yaml.safe_load(f)

    # ========================================================================
    # SOC.YAML TRANSFORMATION
    # ========================================================================

    def transform_soc_yaml(self, extracted_soc: Dict) -> Dict:
        """Transform extracted soc.yaml to schema-compliant format."""

        output = {
            'ir_schema_version': '1.1.0',
            'chip': self.chip_metadata.get('chip', 'UNKNOWN'),
            'vendor': self.chip_metadata.get('vendor', 'UNKNOWN'),
            'family': self.chip_metadata.get('family', ''),
            'revision': self.chip_metadata.get('revision', ''),
            'soc': {
                'cpu': self.chip_metadata.get('cpu', {'cores': []}),
                'peripherals': []
            }
        }

        # Extract top-level init_sequences (if present)
        init_sequences = extracted_soc.get('init_sequences', {})

        # Transform peripherals dict → array
        peripherals = extracted_soc.get('peripherals', {})
        if not isinstance(peripherals, dict):
            print("[WARN] soc.yaml peripherals is not a dict")
            return output

        for periph_name, periph_data in peripherals.items():
            if periph_name == 'DATASHEET':
                continue  # Skip datasheet pseudo-peripheral

            peripheral_entry = {
                'name': periph_name,
                'type': self.infer_type(periph_name),
                'instance': 1,
                'regs_ref': periph_name,
                'clock_ref': self.extract_clock_ref(periph_data),
            }

            # Add IRQ references if present
            irq_refs = self.extract_irq_refs(periph_data)
            if irq_refs:
                peripheral_entry['irq_ref'] = irq_refs

            # Preserve extra data in x-ext
            x_ext = {}

            # Transform init sequence if present (check both locations)
            init_seq = periph_data.get('init_sequence', [])
            if not init_seq and isinstance(init_sequences, dict):
                # Check top-level init_sequences dict
                init_seq = init_sequences.get(periph_name, [])

            if init_seq:
                x_ext['init'] = self.transform_init_sequence(init_seq)

            # Preserve DMA references (with annotation for unknown values)
            dma_refs = periph_data.get('dma_refs', [])
            if dma_refs:
                # Annotate DMA channels that are unknown/software-configured
                annotated_dma_refs = []
                for ref in dma_refs:
                    ref_copy = ref.copy() if isinstance(ref, dict) else {}
                    channel = ref_copy.get('channel', '')

                    # Check if channel is unknown/varies
                    if channel and isinstance(channel, str):
                        channel_lower = channel.lower()
                        if 'unknown' in channel_lower:
                            ref_copy['channel'] = None
                            ref_copy['x-note'] = 'DMA channel is software-configured at runtime, not fixed in hardware'
                        elif 'varies' in channel_lower:
                            ref_copy['channel'] = None
                            ref_copy['x-note'] = 'DMA channel assignment varies based on system configuration'
                    elif channel is None or channel == 'null':
                        ref_copy['channel'] = None
                        ref_copy['x-note'] = 'DMA channel assignment not specified in TRM'

                    annotated_dma_refs.append(ref_copy)

                x_ext['dma_refs'] = annotated_dma_refs

            # Preserve features
            features = periph_data.get('features', [])
            if features:
                x_ext['features'] = features

            # Preserve base address (with annotation for null values)
            base_address = periph_data.get('base_address', '')
            if base_address is not None:  # Include even if empty/null to annotate
                if base_address == '' or base_address is None or base_address == 'null':
                    x_ext['base_address'] = None
                    x_ext['base_address_note'] = 'Base address not found in peripheral TRM chapter - check datasheet memory map'
                else:
                    x_ext['base_address'] = base_address

            # Preserve clock config details
            clock_config = periph_data.get('clock_config', {})
            if clock_config:
                x_ext['clock_config'] = clock_config

            # Preserve interrupts details
            interrupts = periph_data.get('interrupts', [])
            if interrupts:
                x_ext['interrupts'] = interrupts

            # Preserve x-source metadata
            x_source = periph_data.get('x-source', {})
            if x_source:
                x_ext['x-source'] = x_source

            # Only add x-ext if there's data
            if x_ext:
                peripheral_entry['x-ext'] = x_ext

            output['soc']['peripherals'].append(peripheral_entry)

        return output

    def infer_type(self, periph_name: str) -> str:
        """Map peripheral name to normalized type."""
        # Try exact match first
        if periph_name in self.periph_type_map:
            return self.periph_type_map[periph_name]

        # Try prefix match (e.g., SCI1 → uart)
        for prefix, ptype in self.periph_type_map.items():
            if periph_name.startswith(prefix):
                return ptype

        # Default: lowercase name
        return periph_name.lower()

    def extract_clock_ref(self, periph_data: Dict) -> str:
        """Extract clock reference from peripheral data."""
        # Check clock_config section
        clock_config = periph_data.get('clock_config', {})
        if isinstance(clock_config, dict):
            clock_source = clock_config.get('clock_source', '')
            if clock_source:
                return clock_source

        # Default to VCLK (most common peripheral clock)
        return 'VCLK'

    def extract_irq_refs(self, periph_data: Dict) -> List[str]:
        """Extract IRQ names from peripheral interrupts section."""
        interrupts = periph_data.get('interrupts', [])
        irq_names = []

        if isinstance(interrupts, list):
            for irq in interrupts:
                if isinstance(irq, dict) and 'name' in irq:
                    irq_names.append(irq['name'])

        return irq_names

    def transform_init_sequence(self, init_seq: List[Dict]) -> List[Dict]:
        """Transform init sequence to BSP format.

        Extracted format:
            - step: 1
              action: "Enable clock"
              register: "GIOGCR0"
              value: "0x00000001"

        BSP format:
            - reg: "GIO.GCR0"
              op: "set_bits"
              value: "0x00000001"
        """
        transformed = []

        for step in init_seq:
            if not isinstance(step, dict):
                continue

            reg_name = step.get('register', '')
            value = step.get('value', '0x00000000')
            action = step.get('action', '').lower()

            # Infer operation from action text
            if 'set' in action or 'enable' in action or 'write 1' in action:
                op = 'set_bits'
            elif 'clear' in action or 'disable' in action or 'write 0' in action:
                op = 'clear_bits'
            else:
                op = 'write'

            transformed.append({
                'reg': reg_name,
                'op': op,
                'value': value
            })

        return transformed

    # ========================================================================
    # REGS.YAML TRANSFORMATION
    # ========================================================================

    def transform_regs_yaml(self, extracted_regs: Dict) -> Dict:
        """Transform extracted regs.yaml to schema-compliant format."""

        output = {
            'ir_schema_version': '1.1.0',
            'peripherals': {}
        }

        peripherals = extracted_regs.get('peripherals', {})
        if not isinstance(peripherals, dict):
            print("[WARN] regs.yaml peripherals is not a dict")
            return output

        for periph_name, periph_data in peripherals.items():
            output['peripherals'][periph_name] = {
                'base_address': self.extract_base_address(periph_name, periph_data),
                'desc': periph_data.get('description', periph_data.get('desc', '')),
                'registers': {}
            }

            registers = periph_data.get('registers', {})
            if not isinstance(registers, dict):
                continue

            for reg_name, reg_data in registers.items():
                if not isinstance(reg_data, dict):
                    continue

                output['peripherals'][periph_name]['registers'][reg_name] = {
                    'offset': reg_data.get('offset', '0x00'),
                    'access': self.infer_register_access(reg_data),
                    'reset': reg_data.get('reset', '0x00000000'),
                    'desc': reg_data.get('description', reg_data.get('desc', '')),
                }

                # Transform fields dict → list (if not already a list)
                fields = reg_data.get('fields', {})
                if fields:
                    # Check if already a list (from original manual files)
                    if isinstance(fields, list):
                        output['peripherals'][periph_name]['registers'][reg_name]['fields'] = fields
                    else:
                        output['peripherals'][periph_name]['registers'][reg_name]['fields'] = \
                            self.transform_fields(fields)

        return output

    def extract_base_address(self, periph_name: str, periph_data: Dict) -> str:
        """Extract base address from various possible locations."""
        # Check direct base_address field
        if 'base_address' in periph_data:
            addr = periph_data['base_address']
            if addr and addr != 'null' and addr != 'None':
                if isinstance(addr, dict):
                    return addr.get('base', '0x00000000')
                return str(addr)

        # Check in peripheral_metadata
        metadata = periph_data.get('peripheral_metadata', {})
        if isinstance(metadata, dict) and 'base_address' in metadata:
            addr = metadata['base_address']
            if addr:
                return str(addr)

        # Default addresses for known peripherals
        known_addresses = {
            'GIO': '0xFFF7BC00',
            'SCI': '0xFFF7E400',
            'SYSTEM': '0xFFFFFF00',
            'VIM': '0xFFFFFE00',
            'RTI': '0xFFFFFC00',
            'DMA': '0xFFFFF000',
            'N2HET': '0xFFF7B800',
        }

        return known_addresses.get(periph_name, '0x00000000')

    def infer_register_access(self, reg_data: Dict) -> str:
        """Infer register access mode from description or fields."""
        # Check if already has access field
        if 'access' in reg_data:
            return reg_data['access']

        desc = reg_data.get('description', reg_data.get('desc', '')).lower()

        if 'read-only' in desc or 'read only' in desc or 'ro ' in desc:
            return 'RO'
        elif 'write-only' in desc or 'write only' in desc or 'wo ' in desc:
            return 'WO'
        elif 'status' in desc:
            return 'RO'
        elif 'control' in desc or 'config' in desc:
            return 'RW'
        else:
            # Default to RW
            return 'RW'

    def transform_fields(self, fields_dict: Dict) -> List[Dict]:
        """Transform fields dict → list with schema-compliant format.

        Extracted format:
            fields:
              FIELD_NAME:
                bits: "7:0"
                description: "..."

        BSP format:
            fields:
              - name: "FIELD_NAME"
                msb: 7
                lsb: 0
                access: RW
                desc: "..."
        """
        fields_list = []

        for field_name, field_data in fields_dict.items():
            if not isinstance(field_data, dict):
                continue

            # Skip x-source and other metadata fields
            if field_name.startswith('x-'):
                continue

            field_entry = {
                'name': field_name,
                'access': self.infer_field_access(field_data),
                'desc': field_data.get('description', field_data.get('desc', ''))
            }

            # Parse bit range
            bits_str = str(field_data.get('bits', '0'))

            if ':' in bits_str:
                # Range like "31:24" or "7:0"
                parts = bits_str.split(':')
                if len(parts) == 2:
                    try:
                        msb = int(parts[0].strip())
                        lsb = int(parts[1].strip())
                        field_entry['msb'] = msb
                        field_entry['lsb'] = lsb
                    except ValueError:
                        # Fallback to single bit 0
                        field_entry['bit'] = 0
                else:
                    field_entry['bit'] = 0
            else:
                # Single bit
                try:
                    field_entry['bit'] = int(bits_str.strip())
                except ValueError:
                    field_entry['bit'] = 0

            fields_list.append(field_entry)

        return fields_list

    def infer_field_access(self, field_data: Dict) -> str:
        """Infer field access mode from description."""
        desc = field_data.get('description', field_data.get('desc', '')).lower()

        if 'read-only' in desc or 'read only' in desc:
            return 'RO'
        elif 'write-only' in desc or 'write only' in desc:
            return 'WO'
        elif 'write 1 to clear' in desc or 'w1c' in desc:
            return 'RWC'
        elif 'read to clear' in desc or 'rtc' in desc:
            return 'RC'
        else:
            return 'RW'

    # ========================================================================
    # OTHER YAML FILES
    # ========================================================================

    def transform_irq_yaml(self, extracted_irq: Dict) -> Dict:
        """Transform irq.yaml to schema format.

        Schema expects:
            interrupt_controller: {name, type, vector_table}
            irqs: array of {name, id, peripheral_refs (optional), desc, x-ext}

        Extracted has:
            vim_channels: dict of {channel: {channel, source, peripheral, ...}}

        Extra data preserved in per-IRQ x-ext for better usability.
        """
        output = {
            'ir_schema_version': '1.1.0',
            'interrupt_controller': {
                'name': 'VIM',
                'type': 'vim',
                'vector_table': {
                    'base_address': '0xFFF82000',  # VIM RAM base for RM46
                    'entries': 128,  # VIM has 128 channels (0-127)
                    'entry_size_bytes': 4,  # Each vector table entry is 4 bytes
                    'phantom_entry': 0,  # Channel 0 is phantom (ESM high-level)
                    'valid_channels': [0, 126],  # Channels 0-126 are valid
                    'reserved_channels': [127]  # Channel 127 is reserved
                }
            },
            'irqs': []
        }

        # Transform vim_channels dict → irqs array
        vim_channels = extracted_irq.get('vim_channels', {})
        if isinstance(vim_channels, dict):
            for channel_id, channel_data in vim_channels.items():
                if not isinstance(channel_data, dict):
                    continue

                source = channel_data.get('source', 'UNKNOWN')
                peripheral = channel_data.get('peripheral', '')
                default_priority = channel_data.get('default_priority')
                x_source = channel_data.get('x-source', {})

                # Create IRQ name
                irq_name = source
                if not irq_name or irq_name == 'UNKNOWN':
                    irq_name = f"VIM_CH{channel_id}"

                # Build IRQ entry
                irq_entry = {
                    'name': irq_name,
                    'id': int(channel_id),
                    'desc': channel_data.get('description', '')
                }

                # Add peripheral_refs if peripheral is known
                if peripheral and peripheral not in ['RESERVED', 'UNKNOWN', '']:
                    irq_entry['peripheral_refs'] = [peripheral]

                # Add detailed metadata to per-IRQ x-ext
                irq_x_ext = {}
                if default_priority is not None:
                    irq_x_ext['default_priority'] = default_priority
                if x_source:
                    irq_x_ext['x-source'] = x_source

                # Add source if different from name (for traceability)
                if source != irq_name:
                    irq_x_ext['source_signal'] = source

                if irq_x_ext:
                    irq_entry['x-ext'] = irq_x_ext

                output['irqs'].append(irq_entry)

        return output

    def transform_bus_yaml(self, extracted_bus: Dict) -> Dict:
        """Transform bus.yaml to schema format.

        Schema expects:
            sources: array of {name, type, freq_hz}
            domains: array of {name, parent, divider}

        Extracted has:
            clock_domains: dict of {name: {name, source, frequency_hz, divider}}
            peripheral_clocks: dict of {peripheral: {clock_source, ...}}

        Extra data preserved in x-ext.
        """
        output = {
            'ir_schema_version': '1.1.0',
            'sources': [],
            'domains': [],
            'x-ext': {}
        }

        # Extract clock domains
        clock_domains = extracted_bus.get('clock_domains', {})
        if isinstance(clock_domains, dict):
            # Identify sources (no parent/divider)
            sources = {}
            domains_list = []
            clock_domain_details = {}

            for domain_name, domain_data in clock_domains.items():
                if not isinstance(domain_data, dict):
                    continue

                freq_hz = domain_data.get('frequency_hz', 0)
                source = domain_data.get('source', '')
                divider = domain_data.get('divider')

                # Preserve extra data for this clock domain
                clock_domain_details[domain_name] = {
                    'description': domain_data.get('description', ''),
                    'frequency_hz': freq_hz,
                    'x-source': domain_data.get('x-source', {})
                }

                if not source or source == domain_name:
                    # This is a root source
                    sources[domain_name] = {
                        'name': domain_name,
                        'type': 'pll' if 'PLL' in domain_name else 'other',
                        'freq_hz': freq_hz
                    }
                else:
                    # This is a derived domain
                    domain_entry = {
                        'name': domain_name,
                        'parent': source
                    }
                    if divider:
                        domain_entry['divider'] = divider
                    domains_list.append(domain_entry)

            output['sources'] = list(sources.values())
            output['domains'] = domains_list

            # Store extra clock domain details in x-ext
            if clock_domain_details:
                output['x-ext']['clock_domain_details'] = clock_domain_details

        # If no sources detected, add defaults
        if not output['sources']:
            output['sources'] = [
                {'name': 'OSCIN', 'type': 'external_xtal', 'freq_hz': 16000000}
            ]

        # Preserve peripheral_clocks in x-ext (with annotation for unknown values)
        peripheral_clocks = extracted_bus.get('peripheral_clocks', {})
        if isinstance(peripheral_clocks, dict) and peripheral_clocks:
            annotated_periph_clocks = {}

            for periph_name, clock_info in peripheral_clocks.items():
                if not isinstance(clock_info, dict):
                    annotated_periph_clocks[periph_name] = clock_info
                    continue

                clock_info_copy = clock_info.copy()

                # Annotate "Not specified in document" values
                for field in ['clock_enable_register', 'clock_enable_bit', 'clock_divider_register']:
                    if field in clock_info_copy:
                        value = clock_info_copy[field]
                        if isinstance(value, str) and 'not specified' in value.lower():
                            clock_info_copy[field] = None
                            if f'{field}_note' not in clock_info_copy:
                                clock_info_copy[f'{field}_note'] = 'Not documented in peripheral TRM chapter - may be in System chapter'

                # Annotate unknown prescaler registers
                if 'prescaler_register' in clock_info_copy:
                    value = clock_info_copy['prescaler_register']
                    if isinstance(value, str) and 'unknown' in value.lower():
                        clock_info_copy['prescaler_register'] = None
                        clock_info_copy['prescaler_register_note'] = 'Prescaler configuration method not specified in TRM'

                annotated_periph_clocks[periph_name] = clock_info_copy

            output['x-ext']['peripheral_clocks'] = annotated_periph_clocks

        return output

    def transform_memmap_yaml(self, extracted_memmap: Dict) -> Dict:
        """Transform memmap.yaml to schema format.

        Schema expects:
            memory: array of {name, origin, length, attrs}

        Extracted has:
            memory_regions: array of {name, base, size, type, attributes}
        """
        output = {
            'ir_schema_version': '1.1.0',
            'memory': []
        }

        # Transform memory_regions → memory
        memory_regions = extracted_memmap.get('memory_regions', [])
        if isinstance(memory_regions, list):
            for region in memory_regions:
                if not isinstance(region, dict):
                    continue

                # Map region type to attrs
                region_type = region.get('type', '').lower()
                attrs_map = {
                    'flash': 'rx',
                    'ram': 'rwx',
                    'rom': 'rx',
                    'external': 'rwx',
                    'peripheral': 'rw'
                }
                attrs = attrs_map.get(region_type, 'rwx')

                # Check if executable
                attributes = region.get('attributes', [])
                if 'executable' in attributes:
                    if 'x' not in attrs:
                        attrs += 'x'

                output['memory'].append({
                    'name': region.get('name', 'UNKNOWN'),
                    'origin': region.get('base', '0x00000000'),
                    'length': region.get('size', '0x1000'),
                    'attrs': attrs
                })

        return output

    # ========================================================================
    # MAIN TRANSFORMATION
    # ========================================================================

    def transform_all(self, input_dir: Path, output_dir: Path):
        """Transform all extracted YAMLs to schema-compliant format."""

        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print("="*80)
        print("YAML SCHEMA TRANSFORMATION")
        print("="*80)
        print(f"Input:  {input_dir}")
        print(f"Output: {output_dir}")
        print()

        # Transform soc.yaml
        if (input_dir / 'soc.yaml').exists():
            print("Transforming soc.yaml...")
            try:
                with open(input_dir / 'soc.yaml') as f:
                    extracted_soc = yaml.safe_load(f)
                transformed_soc = self.transform_soc_yaml(extracted_soc)
                with open(output_dir / 'soc.yaml', 'w') as f:
                    yaml.dump(transformed_soc, f, default_flow_style=False, sort_keys=False)
                print(f"  [OK] Wrote {output_dir / 'soc.yaml'}")
            except Exception as e:
                print(f"  [FAIL] Error: {e}")
        else:
            print("[WARN] soc.yaml not found")

        # Transform regs.yaml
        if (input_dir / 'regs.yaml').exists():
            print("Transforming regs.yaml...")
            try:
                with open(input_dir / 'regs.yaml') as f:
                    extracted_regs = yaml.safe_load(f)
                transformed_regs = self.transform_regs_yaml(extracted_regs)
                with open(output_dir / 'regs.yaml', 'w') as f:
                    yaml.dump(transformed_regs, f, default_flow_style=False, sort_keys=False)

                # Count peripherals and registers
                periph_count = len(transformed_regs.get('peripherals', {}))
                reg_count = sum(
                    len(p.get('registers', {}))
                    for p in transformed_regs.get('peripherals', {}).values()
                )
                print(f"  [OK] Wrote {output_dir / 'regs.yaml'}")
                print(f"       {periph_count} peripherals, {reg_count} registers")
            except Exception as e:
                print(f"  [FAIL] Error: {e}")
        else:
            print("[WARN] regs.yaml not found")

        # Transform irq.yaml
        if (input_dir / 'irq.yaml').exists():
            print("Transforming irq.yaml...")
            try:
                with open(input_dir / 'irq.yaml') as f:
                    extracted_irq = yaml.safe_load(f)
                transformed_irq = self.transform_irq_yaml(extracted_irq)
                with open(output_dir / 'irq.yaml', 'w') as f:
                    yaml.dump(transformed_irq, f, default_flow_style=False, sort_keys=False)
                print(f"  [OK] Wrote {output_dir / 'irq.yaml'}")
            except Exception as e:
                print(f"  [FAIL] Error: {e}")
        else:
            print("[WARN] irq.yaml not found")

        # Transform bus.yaml
        if (input_dir / 'bus.yaml').exists():
            print("Transforming bus.yaml...")
            try:
                with open(input_dir / 'bus.yaml') as f:
                    extracted_bus = yaml.safe_load(f)
                transformed_bus = self.transform_bus_yaml(extracted_bus)
                with open(output_dir / 'bus.yaml', 'w') as f:
                    yaml.dump(transformed_bus, f, default_flow_style=False, sort_keys=False)
                print(f"  [OK] Wrote {output_dir / 'bus.yaml'}")
            except Exception as e:
                print(f"  [FAIL] Error: {e}")
        else:
            print("[WARN] bus.yaml not found")

        # Transform memmap.yaml
        if (input_dir / 'memmap.yaml').exists():
            print("Transforming memmap.yaml...")
            try:
                with open(input_dir / 'memmap.yaml') as f:
                    extracted_memmap = yaml.safe_load(f)
                transformed_memmap = self.transform_memmap_yaml(extracted_memmap)
                with open(output_dir / 'memmap.yaml', 'w') as f:
                    yaml.dump(transformed_memmap, f, default_flow_style=False, sort_keys=False)
                print(f"  [OK] Wrote {output_dir / 'memmap.yaml'}")
            except Exception as e:
                print(f"  [FAIL] Error: {e}")
        else:
            print("[WARN] memmap.yaml not found")

        # Copy original pinmux.yaml (already in correct format)
        print("Copying original pinmux.yaml...")
        original_pinmux = Path('yaml_in/original/pinmux.yaml')
        if original_pinmux.exists():
            with open(original_pinmux) as f:
                pinmux_data = yaml.safe_load(f)
            with open(output_dir / 'pinmux.yaml', 'w') as f:
                yaml.dump(pinmux_data, f, default_flow_style=False, sort_keys=False)
            print(f"  [OK] Wrote {output_dir / 'pinmux.yaml'}")
        else:
            print("  [WARN] Original pinmux.yaml not found")

        print()
        print("="*80)
        print("[OK] TRANSFORMATION COMPLETE")
        print("="*80)
        print(f"Output directory: {output_dir}")
        print()
        print("Next steps:")
        print("  1. Validate against schemas: python validate_schemas.py")
        print("  2. Test with BSP generator: python main.py --yaml-dir yaml_in_transformed/")
        print("="*80)


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Transform extracted YAML files to BSP schema format"
    )
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('yaml_in'),
        help='Input directory with extracted YAMLs'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('yaml_in_transformed'),
        help='Output directory for transformed YAMLs'
    )
    parser.add_argument(
        '--mappings',
        type=Path,
        default=Path('mappings'),
        help='Directory with mapping files'
    )

    args = parser.parse_args()

    transformer = SchemaTransformer(mappings_dir=args.mappings)
    transformer.transform_all(input_dir=args.input, output_dir=args.output)


if __name__ == '__main__':
    main()
