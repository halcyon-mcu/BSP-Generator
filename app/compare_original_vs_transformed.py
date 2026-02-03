#!/usr/bin/env python3
"""
compare_original_vs_transformed.py

Compare original manually-created YAMLs with AI-extracted transformed YAMLs
to validate extraction accuracy.

Usage:
    python compare_original_vs_transformed.py
"""

import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict


class YAMLComparator:
    """Compare original vs transformed YAML files."""

    def __init__(self, original_dir: Path, transformed_dir: Path):
        self.original_dir = original_dir
        self.transformed_dir = transformed_dir
        self.results = {
            'matches': [],
            'mismatches': [],
            'missing_in_transformed': [],
            'extra_in_transformed': [],
            'statistics': {}
        }

    def load_yaml(self, filepath: Path) -> Dict:
        """Load YAML file safely."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[ERROR] Failed to load {filepath}: {e}")
            return {}

    def compare_soc_yaml(self) -> Dict:
        """Compare soc.yaml files."""
        print("\n" + "="*80)
        print("COMPARING SOC.YAML")
        print("="*80)

        original = self.load_yaml(self.original_dir / 'soc.yaml')
        transformed = self.load_yaml(self.transformed_dir / 'soc.yaml')

        results = {
            'peripherals_compared': 0,
            'matches': [],
            'mismatches': [],
            'missing': [],
            'extra': []
        }

        # Get peripheral dictionaries
        orig_peripherals = original.get('soc', {}).get('peripherals', [])
        trans_peripherals = transformed.get('soc', {}).get('peripherals', [])

        # Convert lists to dicts keyed by name
        orig_dict = {p['name']: p for p in orig_peripherals if isinstance(p, dict)}
        trans_dict = {p['name']: p for p in trans_peripherals if isinstance(p, dict)}

        print(f"\nOriginal peripherals: {len(orig_dict)}")
        print(f"Transformed peripherals: {len(trans_dict)}")

        # Compare common peripherals
        common_peripherals = set(orig_dict.keys()) & set(trans_dict.keys())
        print(f"Common peripherals: {len(common_peripherals)}")

        for periph_name in sorted(common_peripherals):
            results['peripherals_compared'] += 1
            orig_periph = orig_dict[periph_name]
            trans_periph = trans_dict[periph_name]

            # Compare key fields
            fields_to_compare = ['type', 'instance', 'base_address', 'regs_ref', 'clock_ref']

            for field in fields_to_compare:
                orig_val = orig_periph.get(field)
                trans_val = trans_periph.get(field)

                if orig_val == trans_val:
                    results['matches'].append({
                        'peripheral': periph_name,
                        'field': field,
                        'value': orig_val
                    })
                elif orig_val is not None:  # Only mismatch if original has a value
                    results['mismatches'].append({
                        'peripheral': periph_name,
                        'field': field,
                        'original': orig_val,
                        'transformed': trans_val
                    })

        # Check for missing peripherals
        missing = set(orig_dict.keys()) - set(trans_dict.keys())
        for periph_name in missing:
            results['missing'].append(periph_name)

        # Check for extra peripherals
        extra = set(trans_dict.keys()) - set(orig_dict.keys())
        for periph_name in extra:
            results['extra'].append(periph_name)

        return results

    def compare_regs_yaml(self) -> Dict:
        """Compare regs.yaml files."""
        print("\n" + "="*80)
        print("COMPARING REGS.YAML")
        print("="*80)

        original = self.load_yaml(self.original_dir / 'regs.yaml')
        transformed = self.load_yaml(self.transformed_dir / 'regs.yaml')

        results = {
            'peripherals_compared': 0,
            'registers_compared': 0,
            'matches': [],
            'mismatches': [],
            'missing_peripherals': [],
            'missing_registers': []
        }

        orig_peripherals = original.get('peripherals', {})
        trans_peripherals = transformed.get('peripherals', {})

        print(f"\nOriginal peripherals: {len(orig_peripherals)}")
        print(f"Transformed peripherals: {len(trans_peripherals)}")

        # Compare common peripherals
        common_peripherals = set(orig_peripherals.keys()) & set(trans_peripherals.keys())
        print(f"Common peripherals: {len(common_peripherals)}")

        for periph_name in sorted(common_peripherals):
            results['peripherals_compared'] += 1
            orig_regs = orig_peripherals[periph_name].get('registers', {})
            trans_regs = trans_peripherals[periph_name].get('registers', {})

            # Registers are already dicts keyed by name
            orig_regs_dict = orig_regs if isinstance(orig_regs, dict) else {}
            trans_regs_dict = trans_regs if isinstance(trans_regs, dict) else {}

            # Compare common registers
            common_regs = set(orig_regs_dict.keys()) & set(trans_regs_dict.keys())

            for reg_name in common_regs:
                results['registers_compared'] += 1
                orig_reg = orig_regs_dict[reg_name]
                trans_reg = trans_regs_dict[reg_name]

                # Compare offset
                orig_offset = orig_reg.get('offset', orig_reg.get('addr'))
                trans_offset = trans_reg.get('offset', trans_reg.get('addr'))

                if orig_offset == trans_offset:
                    results['matches'].append({
                        'peripheral': periph_name,
                        'register': reg_name,
                        'field': 'offset',
                        'value': orig_offset
                    })
                else:
                    results['mismatches'].append({
                        'peripheral': periph_name,
                        'register': reg_name,
                        'field': 'offset',
                        'original': orig_offset,
                        'transformed': trans_offset
                    })

            # Check for missing registers
            missing_regs = set(orig_regs_dict.keys()) - set(trans_regs_dict.keys())
            for reg_name in missing_regs:
                results['missing_registers'].append({
                    'peripheral': periph_name,
                    'register': reg_name
                })

        # Check for missing peripherals
        missing_periph = set(orig_peripherals.keys()) - set(trans_peripherals.keys())
        for periph_name in missing_periph:
            results['missing_peripherals'].append(periph_name)

        return results

    def compare_bus_yaml(self) -> Dict:
        """Compare bus.yaml files."""
        print("\n" + "="*80)
        print("COMPARING BUS.YAML")
        print("="*80)

        original = self.load_yaml(self.original_dir / 'bus.yaml')
        transformed = self.load_yaml(self.transformed_dir / 'bus.yaml')

        results = {
            'sources_compared': 0,
            'domains_compared': 0,
            'matches': [],
            'mismatches': []
        }

        # Compare clock sources
        orig_sources = original.get('sources', [])
        trans_sources = transformed.get('sources', [])

        orig_sources_dict = {s['name']: s for s in orig_sources if isinstance(s, dict)}
        trans_sources_dict = {s['name']: s for s in trans_sources if isinstance(s, dict)}

        common_sources = set(orig_sources_dict.keys()) & set(trans_sources_dict.keys())

        for source_name in common_sources:
            results['sources_compared'] += 1
            orig_source = orig_sources_dict[source_name]
            trans_source = trans_sources_dict[source_name]

            # Compare type and frequency
            for field in ['type', 'freq_hz']:
                orig_val = orig_source.get(field)
                trans_val = trans_source.get(field)

                if orig_val == trans_val:
                    results['matches'].append({
                        'source': source_name,
                        'field': field,
                        'value': orig_val
                    })
                elif orig_val is not None:
                    results['mismatches'].append({
                        'source': source_name,
                        'field': field,
                        'original': orig_val,
                        'transformed': trans_val
                    })

        # Compare clock domains
        orig_domains = original.get('domains', [])
        trans_domains = transformed.get('domains', [])

        orig_domains_dict = {d['name']: d for d in orig_domains if isinstance(d, dict)}
        trans_domains_dict = {d['name']: d for d in trans_domains if isinstance(d, dict)}

        common_domains = set(orig_domains_dict.keys()) & set(trans_domains_dict.keys())

        for domain_name in common_domains:
            results['domains_compared'] += 1
            orig_domain = orig_domains_dict[domain_name]
            trans_domain = trans_domains_dict[domain_name]

            # Compare parent and divider
            for field in ['parent', 'divider', 'multiplier']:
                orig_val = orig_domain.get(field)
                trans_val = trans_domain.get(field)

                if orig_val == trans_val:
                    results['matches'].append({
                        'domain': domain_name,
                        'field': field,
                        'value': orig_val
                    })
                elif orig_val is not None:
                    results['mismatches'].append({
                        'domain': domain_name,
                        'field': field,
                        'original': orig_val,
                        'transformed': trans_val
                    })

        return results

    def compare_irq_yaml(self) -> Dict:
        """Compare irq.yaml files."""
        print("\n" + "="*80)
        print("COMPARING IRQ.YAML")
        print("="*80)

        original = self.load_yaml(self.original_dir / 'irq.yaml')
        transformed = self.load_yaml(self.transformed_dir / 'irq.yaml')

        results = {
            'irqs_compared': 0,
            'matches': [],
            'mismatches': []
        }

        orig_irqs = original.get('irqs', [])
        trans_irqs = transformed.get('irqs', [])

        # Convert to dicts keyed by name
        orig_irqs_dict = {irq['name']: irq for irq in orig_irqs if isinstance(irq, dict)}
        trans_irqs_dict = {irq['name']: irq for irq in trans_irqs if isinstance(irq, dict)}

        common_irqs = set(orig_irqs_dict.keys()) & set(trans_irqs_dict.keys())

        print(f"\nOriginal IRQs: {len(orig_irqs_dict)}")
        print(f"Transformed IRQs: {len(trans_irqs_dict)}")
        print(f"Common IRQs: {len(common_irqs)}")

        for irq_name in common_irqs:
            results['irqs_compared'] += 1
            orig_irq = orig_irqs_dict[irq_name]
            trans_irq = trans_irqs_dict[irq_name]

            # Compare ID
            orig_id = orig_irq.get('id')
            trans_id = trans_irq.get('id')

            if orig_id == trans_id:
                results['matches'].append({
                    'irq': irq_name,
                    'field': 'id',
                    'value': orig_id
                })
            else:
                results['mismatches'].append({
                    'irq': irq_name,
                    'field': 'id',
                    'original': orig_id,
                    'transformed': trans_id
                })

        return results

    def generate_report(self, soc_results: Dict, regs_results: Dict,
                       bus_results: Dict, irq_results: Dict) -> str:
        """Generate markdown report."""

        lines = []
        lines.append("# Extraction Accuracy Report - Original vs Transformed")
        lines.append("")
        lines.append(f"**Date**: 2026-02-03")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")

        # Calculate overall statistics
        total_matches = (len(soc_results['matches']) + len(regs_results['matches']) +
                        len(bus_results['matches']) + len(irq_results['matches']))
        total_mismatches = (len(soc_results['mismatches']) + len(regs_results['mismatches']) +
                           len(bus_results['mismatches']) + len(irq_results['mismatches']))
        total_comparisons = total_matches + total_mismatches

        if total_comparisons > 0:
            accuracy = (total_matches / total_comparisons) * 100
        else:
            accuracy = 0.0

        lines.append(f"**Overall Extraction Accuracy**: {accuracy:.2f}%")
        lines.append("")
        lines.append(f"- ✅ **Matches**: {total_matches}")
        lines.append(f"- ⚠️ **Mismatches**: {total_mismatches}")
        lines.append(f"- 📊 **Total Comparisons**: {total_comparisons}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # SOC.YAML Results
        lines.append("## SOC.YAML Comparison")
        lines.append("")
        lines.append(f"**Peripherals Compared**: {soc_results['peripherals_compared']}")
        lines.append(f"**Matches**: {len(soc_results['matches'])}")
        lines.append(f"**Mismatches**: {len(soc_results['mismatches'])}")
        lines.append("")

        if soc_results['mismatches']:
            lines.append("### Mismatches")
            lines.append("")
            lines.append("| Peripheral | Field | Original | Transformed |")
            lines.append("|------------|-------|----------|-------------|")
            for mismatch in soc_results['mismatches'][:20]:  # Limit to 20
                lines.append(f"| {mismatch['peripheral']} | {mismatch['field']} | "
                           f"`{mismatch['original']}` | `{mismatch['transformed']}` |")
            lines.append("")

        if soc_results['missing']:
            lines.append("### Missing in Transformed")
            lines.append("")
            lines.append(f"Peripherals: {', '.join(sorted(soc_results['missing']))}")
            lines.append("")

        if soc_results['extra']:
            lines.append("### Extra in Transformed (New Peripherals)")
            lines.append("")
            lines.append(f"Peripherals: {', '.join(sorted(soc_results['extra']))}")
            lines.append("")

        lines.append("---")
        lines.append("")

        # REGS.YAML Results
        lines.append("## REGS.YAML Comparison")
        lines.append("")
        lines.append(f"**Peripherals Compared**: {regs_results['peripherals_compared']}")
        lines.append(f"**Registers Compared**: {regs_results['registers_compared']}")
        lines.append(f"**Matches**: {len(regs_results['matches'])}")
        lines.append(f"**Mismatches**: {len(regs_results['mismatches'])}")
        lines.append("")

        if regs_results['mismatches']:
            lines.append("### Register Offset Mismatches")
            lines.append("")
            lines.append("| Peripheral | Register | Original Offset | Transformed Offset |")
            lines.append("|------------|----------|----------------|-------------------|")
            for mismatch in regs_results['mismatches'][:30]:  # Limit to 30
                lines.append(f"| {mismatch['peripheral']} | {mismatch['register']} | "
                           f"`{mismatch['original']}` | `{mismatch['transformed']}` |")
            lines.append("")

        if regs_results['missing_registers']:
            lines.append("### Missing Registers in Transformed")
            lines.append("")
            missing_by_periph = defaultdict(list)
            for item in regs_results['missing_registers']:
                missing_by_periph[item['peripheral']].append(item['register'])

            for periph, regs in sorted(missing_by_periph.items()):
                lines.append(f"**{periph}**: {', '.join(sorted(regs))}")
            lines.append("")

        lines.append("---")
        lines.append("")

        # BUS.YAML Results
        lines.append("## BUS.YAML Comparison")
        lines.append("")
        lines.append(f"**Clock Sources Compared**: {bus_results['sources_compared']}")
        lines.append(f"**Clock Domains Compared**: {bus_results['domains_compared']}")
        lines.append(f"**Matches**: {len(bus_results['matches'])}")
        lines.append(f"**Mismatches**: {len(bus_results['mismatches'])}")
        lines.append("")

        if bus_results['mismatches']:
            lines.append("### Mismatches")
            lines.append("")
            lines.append("| Item | Field | Original | Transformed |")
            lines.append("|------|-------|----------|-------------|")
            for mismatch in bus_results['mismatches']:
                item = mismatch.get('source') or mismatch.get('domain')
                lines.append(f"| {item} | {mismatch['field']} | "
                           f"`{mismatch['original']}` | `{mismatch['transformed']}` |")
            lines.append("")

        lines.append("---")
        lines.append("")

        # IRQ.YAML Results
        lines.append("## IRQ.YAML Comparison")
        lines.append("")
        lines.append(f"**IRQs Compared**: {irq_results['irqs_compared']}")
        lines.append(f"**Matches**: {len(irq_results['matches'])}")
        lines.append(f"**Mismatches**: {len(irq_results['mismatches'])}")
        lines.append("")

        if irq_results['mismatches']:
            lines.append("### IRQ ID Mismatches")
            lines.append("")
            lines.append("| IRQ Name | Original ID | Transformed ID |")
            lines.append("|----------|-------------|----------------|")
            for mismatch in irq_results['mismatches']:
                lines.append(f"| {mismatch['irq']} | `{mismatch['original']}` | `{mismatch['transformed']}` |")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Accuracy Summary
        lines.append("## Accuracy Summary by File")
        lines.append("")
        lines.append("| File | Matches | Mismatches | Accuracy |")
        lines.append("|------|---------|------------|----------|")

        for file_name, results in [
            ('soc.yaml', soc_results),
            ('regs.yaml', regs_results),
            ('bus.yaml', bus_results),
            ('irq.yaml', irq_results)
        ]:
            matches = len(results['matches'])
            mismatches = len(results['mismatches'])
            total = matches + mismatches
            acc = (matches / total * 100) if total > 0 else 0.0
            lines.append(f"| {file_name} | {matches} | {mismatches} | {acc:.2f}% |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Conclusion
        lines.append("## Conclusion")
        lines.append("")

        if accuracy >= 95:
            lines.append(f"✅ **EXCELLENT** - Extraction accuracy of {accuracy:.2f}% demonstrates high-quality AI extraction.")
        elif accuracy >= 90:
            lines.append(f"✅ **GOOD** - Extraction accuracy of {accuracy:.2f}% is acceptable with minor corrections needed.")
        elif accuracy >= 80:
            lines.append(f"⚠️ **FAIR** - Extraction accuracy of {accuracy:.2f}% requires review and corrections.")
        else:
            lines.append(f"❌ **POOR** - Extraction accuracy of {accuracy:.2f}% indicates significant issues.")

        lines.append("")
        lines.append("**Key Findings**:")
        lines.append("")
        lines.append(f"- Compared {soc_results['peripherals_compared']} peripherals across soc.yaml")
        lines.append(f"- Compared {regs_results['registers_compared']} registers across {regs_results['peripherals_compared']} peripherals")
        lines.append(f"- Compared {bus_results['sources_compared']} clock sources and {bus_results['domains_compared']} clock domains")
        lines.append(f"- Compared {irq_results['irqs_compared']} interrupt definitions")
        lines.append("")

        if total_mismatches > 0:
            lines.append("**Recommended Actions**:")
            lines.append("")
            lines.append("1. Review mismatches listed above")
            lines.append("2. Verify against source PDFs")
            lines.append("3. Update extraction prompts if patterns are found")
            lines.append("4. Apply manual corrections to transformed YAMLs")

        return '\n'.join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare original vs transformed YAML files"
    )
    parser.add_argument(
        '--original-dir',
        type=Path,
        default=Path('yaml_in/original'),
        help='Directory containing original YAML files'
    )
    parser.add_argument(
        '--transformed-dir',
        type=Path,
        default=Path('yaml_in_transformed'),
        help='Directory containing transformed YAML files'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('EXTRACTION_ACCURACY_REPORT.md'),
        help='Output report file'
    )

    args = parser.parse_args()

    print("="*80)
    print("EXTRACTION ACCURACY COMPARISON")
    print("="*80)
    print(f"Original: {args.original_dir}")
    print(f"Transformed: {args.transformed_dir}")
    print(f"Output: {args.output}")

    comparator = YAMLComparator(args.original_dir, args.transformed_dir)

    # Run comparisons
    soc_results = comparator.compare_soc_yaml()
    regs_results = comparator.compare_regs_yaml()
    bus_results = comparator.compare_bus_yaml()
    irq_results = comparator.compare_irq_yaml()

    # Generate report
    print("\n" + "="*80)
    print("GENERATING REPORT")
    print("="*80)

    report = comparator.generate_report(soc_results, regs_results, bus_results, irq_results)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n[OK] Report saved to {args.output}")

    # Print summary
    total_matches = (len(soc_results['matches']) + len(regs_results['matches']) +
                    len(bus_results['matches']) + len(irq_results['matches']))
    total_mismatches = (len(soc_results['mismatches']) + len(regs_results['mismatches']) +
                       len(bus_results['mismatches']) + len(irq_results['mismatches']))
    total_comparisons = total_matches + total_mismatches

    if total_comparisons > 0:
        accuracy = (total_matches / total_comparisons) * 100
        print(f"\n[RESULT] Overall Extraction Accuracy: {accuracy:.2f}%")
        print(f"         Matches: {total_matches}")
        print(f"         Mismatches: {total_mismatches}")

    print("\n" + "="*80)
    print("[OK] COMPARISON COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
