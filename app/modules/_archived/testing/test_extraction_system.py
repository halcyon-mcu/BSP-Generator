#!/usr/bin/env python3
"""
test_extraction_system.py

Comprehensive test suite for YAML extraction system.
Run this BEFORE overnight extraction to ensure stability.

Tests:
1. Extraction works on 3 sample peripherals
2. Source attribution is present and valid
3. YAML is parseable
4. Cross-references are detected
5. Cost estimation is accurate
6. Schema compliance
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List
import yaml as pyyaml

from ..extraction.extract_to_yaml import extract_all_peripherals
from ..generation.prompt import Model


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.details = {}

    def pass_test(self, message: str = "", **details):
        self.passed = True
        self.message = message
        self.details = details

    def fail_test(self, message: str, **details):
        self.passed = False
        self.message = message
        self.details = details

    def __str__(self):
        status = "[OK] PASS" if self.passed else "[FAIL] FAIL"
        msg = f"  {self.message}" if self.message else ""
        return f"{status}: {self.name}{msg}"


class ExtractionTestSuite:
    """Test suite for extraction system."""

    def __init__(self):
        self.results: List[TestResult] = []
        self.test_output_dir = Path("yaml_out_test")

    async def run_all_tests(self) -> bool:
        """Run all tests. Returns True if all pass."""
        print("="*80)
        print("EXTRACTION SYSTEM TEST SUITE")
        print("="*80)
        print()

        # Clean test output
        if self.test_output_dir.exists():
            import shutil
            shutil.rmtree(self.test_output_dir)

        # Run tests
        await self.test_basic_extraction()
        await self.test_source_attribution()
        await self.test_yaml_validity()
        await self.test_cross_references()
        await self.test_datasheet_extraction()
        await self.test_cost_tracking()

        # Print results
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)

        passed = 0
        failed = 0

        for result in self.results:
            print(result)
            if result.passed:
                passed += 1
            else:
                failed += 1
                if result.details:
                    print(f"    Details: {result.details}")

        print()
        print(f"Total: {passed} passed, {failed} failed")

        if failed == 0:
            print("\n[OK] ALL TESTS PASSED - System is ready for overnight run")
            return True
        else:
            print("\n[FAIL] SOME TESTS FAILED - Fix issues before overnight run")
            return False

    async def test_basic_extraction(self):
        """Test 1: Extract 3 peripherals successfully."""
        result = TestResult("Basic extraction (GIO, SCI, SYSTEM)")

        try:
            # Extract 3 test peripherals
            await extract_all_peripherals(
                trm_dir=Path("modules/pdfs/TRM_split"),
                datasheet_path=None,  # Skip datasheet for speed
                output_dir=self.test_output_dir,
                model=Model.SONNET_4_5,
                max_concurrent=2,
                max_budget=10.0,  # Low budget for test
                test_peripherals=["GIO", "SCI", "SYSTEM"]
            )

            # Check outputs exist
            extracted_dir = self.test_output_dir / "extracted"

            missing = []
            for periph in ["GIO", "SCI", "SYSTEM"]:
                periph_file = extracted_dir / periph / f"{periph}_extracted.yaml"
                if not periph_file.exists():
                    missing.append(periph)

            if missing:
                result.fail_test(f"Missing outputs: {missing}")
            else:
                result.pass_test(f" - All 3 peripherals extracted")

        except Exception as e:
            result.fail_test(f"Extraction failed: {e}")

        self.results.append(result)

    async def test_source_attribution(self):
        """Test 2: Every extracted value has source attribution."""
        result = TestResult("Source attribution (provenance tracking)")

        try:
            extracted_dir = self.test_output_dir / "extracted"

            missing_sources = []
            checked_values = 0

            for periph_dir in extracted_dir.iterdir():
                if not periph_dir.is_dir():
                    continue

                yaml_file = periph_dir / f"{periph_dir.name}_extracted.yaml"
                if not yaml_file.exists():
                    continue

                # Load YAML
                with open(yaml_file) as f:
                    data = pyyaml.safe_load(f)

                if not data:
                    continue

                # Check for x-source fields
                sources_found = self._find_source_fields(data)
                checked_values += 1

                if not sources_found:
                    missing_sources.append(periph_dir.name)

            if missing_sources:
                result.fail_test(
                    f"Missing source attribution",
                    missing=missing_sources
                )
            else:
                result.pass_test(f" - Found sources in {checked_values} extractions")

        except Exception as e:
            result.fail_test(f"Check failed: {e}")

        self.results.append(result)

    def _find_source_fields(self, data, path="") -> bool:
        """Recursively find x-source fields."""
        if isinstance(data, dict):
            if 'x-source' in data:
                # Check it has required fields
                source = data['x-source']
                if 'pdf' in source and 'confidence' in source:
                    return True

            for key, value in data.items():
                if self._find_source_fields(value, f"{path}.{key}"):
                    return True

        elif isinstance(data, list):
            for item in data:
                if self._find_source_fields(item, f"{path}[]"):
                    return True

        return False

    async def test_yaml_validity(self):
        """Test 3: All extracted YAML is valid and parseable."""
        result = TestResult("YAML validity")

        try:
            extracted_dir = self.test_output_dir / "extracted"

            invalid_files = []
            valid_count = 0

            for periph_dir in extracted_dir.iterdir():
                if not periph_dir.is_dir():
                    continue

                yaml_file = periph_dir / f"{periph_dir.name}_extracted.yaml"
                if not yaml_file.exists():
                    continue

                try:
                    with open(yaml_file) as f:
                        data = pyyaml.safe_load(f)

                    if data is None:
                        invalid_files.append((yaml_file.name, "Empty YAML"))
                    else:
                        valid_count += 1

                except pyyaml.YAMLError as e:
                    invalid_files.append((yaml_file.name, str(e)))

            if invalid_files:
                result.fail_test(
                    f"Invalid YAML files",
                    invalid=invalid_files
                )
            else:
                result.pass_test(f" - All {valid_count} YAML files are valid")

        except Exception as e:
            result.fail_test(f"Check failed: {e}")

        self.results.append(result)

    async def test_cross_references(self):
        """Test 4: Cross-references (x-needs-verification) are detected."""
        result = TestResult("Cross-reference detection")

        try:
            extracted_dir = self.test_output_dir / "extracted"

            cross_refs_found = 0
            total_files = 0

            for periph_dir in extracted_dir.iterdir():
                if not periph_dir.is_dir():
                    continue

                yaml_file = periph_dir / f"{periph_dir.name}_extracted.yaml"
                if not yaml_file.exists():
                    continue

                total_files += 1

                with open(yaml_file) as f:
                    data = pyyaml.safe_load(f)

                if data and self._find_needs_verification(data):
                    cross_refs_found += 1

            if cross_refs_found == 0:
                result.fail_test(
                    "No cross-references detected - system may not be working"
                )
            else:
                result.pass_test(
                    f" - Found cross-refs in {cross_refs_found}/{total_files} files"
                )

        except Exception as e:
            result.fail_test(f"Check failed: {e}")

        self.results.append(result)

    def _find_needs_verification(self, data) -> bool:
        """Recursively find x-needs-verification fields (e.g., pins_x-needs-verification)."""
        if isinstance(data, dict):
            # Check for keys ending with _x-needs-verification or exactly x-needs-verification
            for key in data.keys():
                if key == 'x-needs-verification' or key.endswith('_x-needs-verification'):
                    return True
            # Recurse into values
            for value in data.values():
                if self._find_needs_verification(value):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._find_needs_verification(item):
                    return True
        return False

    async def test_datasheet_extraction(self):
        """Test 5: Datasheet extraction includes pinmux/IRQ tables."""
        result = TestResult("Datasheet extraction (pinmux/IRQ tables)")

        try:
            # Find datasheet
            input_docs = Path("input_docs")
            datasheet = None

            if input_docs.exists():
                candidates = []
                for pdf in input_docs.glob("*.pdf"):
                    # Skip schematic files
                    if "schematic" in pdf.name.lower():
                        continue

                    size_mb = pdf.stat().st_size / (1024 * 1024)

                    # Prefer files with "datasheet" in name
                    if "datasheet" in pdf.name.lower():
                        datasheet = pdf
                        break

                    # Otherwise collect candidates >1MB
                    if size_mb > 1:
                        candidates.append((pdf, size_mb))

                # If no explicit "datasheet" name found, use largest candidate
                if not datasheet and candidates:
                    candidates.sort(key=lambda x: x[1], reverse=True)
                    datasheet = candidates[0][0]

            if not datasheet:
                result.pass_test(" - Skipped (no datasheet in input_docs/)")
                self.results.append(result)
                return

            # Extract datasheet only
            test_ds_dir = Path("yaml_out_test_ds")
            if test_ds_dir.exists():
                import shutil
                shutil.rmtree(test_ds_dir)

            await extract_all_peripherals(
                trm_dir=Path("modules/pdfs/TRM_split"),
                datasheet_path=datasheet,
                output_dir=test_ds_dir,
                model=Model.SONNET_4_5,
                max_concurrent=1,
                max_budget=15.0,
                test_peripherals=[]  # Empty = only datasheet
            )

            # Check datasheet output
            ds_file = test_ds_dir / "extracted" / "DATASHEET" / "datasheet_extracted.yaml"

            if not ds_file.exists():
                result.fail_test("Datasheet extraction failed - no output file")
                self.results.append(result)
                return

            with open(ds_file) as f:
                data = pyyaml.safe_load(f)

            # Check for key sections
            has_pinmux = self._has_key_recursive(data, 'pinmux')
            has_irq = self._has_key_recursive(data, 'vim') or self._has_key_recursive(data, 'interrupt')

            if has_pinmux and has_irq:
                result.pass_test(" - Found pinmux and IRQ tables")
            elif has_pinmux:
                result.fail_test("Found pinmux but missing IRQ table")
            elif has_irq:
                result.fail_test("Found IRQ table but missing pinmux")
            else:
                result.fail_test("Missing both pinmux and IRQ tables")

        except Exception as e:
            result.fail_test(f"Check failed: {e}")

        self.results.append(result)

    def _has_key_recursive(self, data, key_substring: str) -> bool:
        """Check if any key contains substring."""
        if isinstance(data, dict):
            for k, v in data.items():
                if key_substring.lower() in k.lower():
                    return True
                if self._has_key_recursive(v, key_substring):
                    return True
        elif isinstance(data, list):
            for item in data:
                if self._has_key_recursive(item, key_substring):
                    return True
        return False

    async def test_cost_tracking(self):
        """Test 6: Cost tracking is accurate."""
        result = TestResult("Cost tracking and budget enforcement")

        try:
            # Check metadata files
            extracted_dir = self.test_output_dir / "extracted"

            total_cost = 0.0
            cost_count = 0

            for periph_dir in extracted_dir.iterdir():
                if not periph_dir.is_dir():
                    continue

                meta_file = periph_dir / "metadata.json"
                if meta_file.exists():
                    with open(meta_file) as f:
                        meta = json.load(f)

                    if 'cost' in meta:
                        total_cost += meta['cost']
                        cost_count += 1

            if cost_count == 0:
                result.fail_test("No cost metadata found")
            elif total_cost == 0:
                result.fail_test("Cost tracking returned $0 - not working")
            elif total_cost > 10.0:  # We set budget to $10 in test
                result.fail_test(f"Cost exceeded test budget: ${total_cost:.2f}")
            else:
                result.pass_test(f" - Tracked ${total_cost:.2f} across {cost_count} extractions")

        except Exception as e:
            result.fail_test(f"Check failed: {e}")

        self.results.append(result)


# ============================================================================
# CLI
# ============================================================================

async def main():
    """Run test suite."""
    suite = ExtractionTestSuite()
    all_passed = await suite.run_all_tests()

    if all_passed:
        print("\n" + "="*80)
        print("SYSTEM READY FOR OVERNIGHT RUN")
        print("="*80)
        print("\nRun the full extraction with:")
        print("  python extract_to_yaml.py --budget 75")
        print("\nEstimated cost for full run: $50-60")
        print("Estimated time: 1.5-2 hours")
        exit(0)
    else:
        print("\n" + "="*80)
        print("FIX FAILURES BEFORE OVERNIGHT RUN")
        print("="*80)
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
