#!/usr/bin/env python3
"""
annotate_unknown_values.py

Post-process transformed YAML files to properly annotate unknown/unclear values
with structured metadata explaining WHY they are unknown.

Usage:
    python annotate_unknown_values.py --yaml-dir yaml_in_transformed
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List
import re


class UnknownValueAnnotator:
    """Annotate unknown values with structured metadata."""

    # Patterns to detect unknown values
    UNKNOWN_PATTERNS = [
        r'(?i)^unknown$',
        r'(?i)not specified',
        r'(?i)not.*document',
        r'(?i)varies$',
    ]

    # Reasons for unknown values
    REASONS = {
        'dma_channel': {
            'reason': 'software_configured',
            'explanation': 'DMA channel assignment is configured by software at runtime, not fixed in hardware'
        },
        'base_address_null': {
            'reason': 'not_in_trm',
            'explanation': 'Base address not explicitly stated in TRM, may be in datasheet'
        },
        'clock_enable_register': {
            'reason': 'not_documented',
            'explanation': 'Clock enable register not specified in peripheral chapter'
        },
        'register_not_specified': {
            'reason': 'not_documented',
            'explanation': 'Register name not found in source documentation'
        },
        'field_varies': {
            'reason': 'context_dependent',
            'explanation': 'Value varies based on configuration or operating mode'
        }
    }

    def __init__(self, yaml_dir: Path):
        self.yaml_dir = Path(yaml_dir)

    def is_unknown_value(self, value: Any) -> bool:
        """Check if a value represents an unknown/unclear value."""
        if value is None:
            return True
        if not isinstance(value, str):
            return False
        for pattern in self.UNKNOWN_PATTERNS:
            if re.match(pattern, value):
                return True
        return False

    def annotate_dma_refs(self, dma_refs: List[Dict]) -> List[Dict]:
        """Annotate DMA references with unknown channel explanations."""
        annotated = []
        for ref in dma_refs:
            ref_copy = ref.copy()
            if self.is_unknown_value(ref_copy.get('channel')):
                reason = self.REASONS['dma_channel']
                ref_copy['channel'] = None  # Standardize to None
                ref_copy['x-unknown'] = {
                    'field': 'channel',
                    'reason': reason['reason'],
                    'explanation': reason['explanation'],
                    'note': 'Assign DMA channel during peripheral initialization'
                }
            annotated.append(ref_copy)
        return annotated

    def annotate_peripheral(self, periph: Dict) -> Dict:
        """Annotate a peripheral's unknown values."""
        periph_copy = periph.copy()

        # Handle x-ext field
        if 'x-ext' in periph_copy:
            x_ext = periph_copy['x-ext']

            # Annotate DMA refs
            if 'dma_refs' in x_ext and isinstance(x_ext['dma_refs'], list):
                x_ext['dma_refs'] = self.annotate_dma_refs(x_ext['dma_refs'])

            # Annotate base address
            if 'base_address' in x_ext and x_ext['base_address'] is None:
                reason = self.REASONS['base_address_null']
                x_ext['base_address'] = {
                    'value': None,
                    'x-unknown': {
                        'field': 'base_address',
                        'reason': reason['reason'],
                        'explanation': reason['explanation'],
                        'note': 'Check datasheet memory map section'
                    }
                }

            # Annotate clock config unknowns
            if 'clock_config' in x_ext:
                clock_config = x_ext['clock_config']
                for key, value in list(clock_config.items()):
                    if self.is_unknown_value(value):
                        reason = self.REASONS['clock_enable_register']
                        clock_config[key] = {
                            'value': None,
                            'x-unknown': {
                                'field': key,
                                'reason': reason['reason'],
                                'explanation': reason['explanation']
                            }
                        }

        return periph_copy

    def annotate_soc_yaml(self, soc_data: Dict) -> Dict:
        """Annotate soc.yaml unknown values."""
        output = soc_data.copy()

        if 'soc' in output and 'peripherals' in output['soc']:
            peripherals = output['soc']['peripherals']
            for i, periph in enumerate(peripherals):
                peripherals[i] = self.annotate_peripheral(periph)

        return output

    def annotate_bus_yaml(self, bus_data: Dict) -> Dict:
        """Annotate bus.yaml unknown values."""
        output = bus_data.copy()

        if 'x-ext' in output and 'peripheral_clocks' in output['x-ext']:
            periph_clocks = output['x-ext']['peripheral_clocks']

            for periph_name, clock_info in periph_clocks.items():
                if not isinstance(clock_info, dict):
                    continue

                # Annotate unknown clock enable registers
                for field in ['clock_enable_register', 'clock_enable_bit']:
                    if field in clock_info and self.is_unknown_value(clock_info[field]):
                        reason = self.REASONS['clock_enable_register']
                        clock_info[field] = {
                            'value': None,
                            'x-unknown': {
                                'field': field,
                                'reason': reason['reason'],
                                'explanation': reason['explanation']
                            }
                        }

        return output

    def annotate_file(self, filename: str):
        """Annotate unknown values in a specific file."""
        filepath = self.yaml_dir / filename

        if not filepath.exists():
            print(f"[SKIP] {filename} not found")
            return

        # Load YAML
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Annotate based on file type
        if filename == 'soc.yaml':
            annotated = self.annotate_soc_yaml(data)
        elif filename == 'bus.yaml':
            annotated = self.annotate_bus_yaml(data)
        else:
            # Other files don't need annotation for now
            print(f"[SKIP] {filename} - no unknown value patterns defined")
            return

        # Write annotated YAML
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(annotated, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"[OK] Annotated {filename}")

    def annotate_all(self):
        """Annotate all YAML files in the directory."""
        print("="*80)
        print("ANNOTATING UNKNOWN VALUES")
        print("="*80)
        print(f"YAML dir: {self.yaml_dir}")
        print()

        files = ['soc.yaml', 'bus.yaml', 'irq.yaml', 'regs.yaml', 'memmap.yaml', 'pinmux.yaml']

        for filename in files:
            self.annotate_file(filename)

        print()
        print("="*80)
        print("[OK] ANNOTATION COMPLETE")
        print("="*80)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Annotate unknown values in transformed YAML files"
    )
    parser.add_argument(
        '--yaml-dir',
        type=Path,
        default=Path('yaml_in_transformed'),
        help='Directory containing YAML files to annotate'
    )

    args = parser.parse_args()

    annotator = UnknownValueAnnotator(args.yaml_dir)
    annotator.annotate_all()


if __name__ == '__main__':
    main()
