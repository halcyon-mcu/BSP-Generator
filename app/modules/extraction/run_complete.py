#!/usr/bin/env python3
"""
run_complete_extraction.py

Orchestrator script: Runs all 3 passes automatically.

Pass 1: Extract from PDFs with source attribution
Pass 2: Resolve cross-document references
Pass 3: Consolidate into 6 master YAMLs

This is the main script to run overnight.
"""

import asyncio
import datetime
from pathlib import Path
import argparse

from .extract_to_yaml import extract_all_peripherals
from ..registers.resolve_cross_references import resolve_all_cross_references
from ..yaml.consolidate import YAMLConsolidator
from ..generation.prompt import Model


async def run_complete_extraction(
    trm_dir: Path,
    datasheet_path: Path,
    output_dir: Path,
    final_yaml_dir: Path,
    model: Model,
    max_concurrent: int,
    total_budget: float
):
    """
    Run complete 3-pass extraction pipeline.

    Args:
        trm_dir: TRM PDF directory
        datasheet_path: Datasheet PDF
        output_dir: Working directory (yaml_out/)
        final_yaml_dir: Final output (yaml_in/)
        model: Claude model
        max_concurrent: Parallel extractions
        total_budget: Total budget for all 3 passes
    """

    start_time = datetime.datetime.now()

    print("="*80)
    print("COMPLETE YAML EXTRACTION PIPELINE")
    print("="*80)
    print(f"Model: {model.value}")
    print(f"Total budget: ${total_budget:.2f}")
    print(f"Max concurrent: {max_concurrent}")
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Pipeline:")
    print("  Pass 1: Extract from PDFs (est. $50)")
    print("  Pass 2: Resolve cross-references (est. $5-8)")
    print("  Pass 3: Consolidate to master YAMLs (no cost)")
    print()
    input("Press ENTER to start extraction, or Ctrl+C to cancel...")
    print()

    # ========================================================================
    # PASS 1: EXTRACTION
    # ========================================================================

    print("\n" + "="*80)
    print("STARTING PASS 1: Extraction with Source Attribution")
    print("="*80)
    print()

    pass1_budget = total_budget * 0.85  # 85% of budget for Pass 1

    try:
        await extract_all_peripherals(
            trm_dir=trm_dir,
            datasheet_path=datasheet_path,
            output_dir=output_dir,
            model=model,
            max_concurrent=max_concurrent,
            max_budget=pass1_budget,
            test_peripherals=None  # All peripherals
        )
    except Exception as e:
        print(f"\n[FAIL] Pass 1 failed: {e}")
        return

    # ========================================================================
    # PASS 2: CROSS-REFERENCE RESOLUTION
    # ========================================================================

    print("\n" + "="*80)
    print("STARTING PASS 2: Cross-Reference Resolution")
    print("="*80)
    print()

    pass2_budget = total_budget * 0.15  # 15% remaining for Pass 2

    try:
        await resolve_all_cross_references(
            extracted_dir=output_dir,
            trm_dir=trm_dir,
            datasheet_path=datasheet_path,
            output_dir=output_dir,
            model=model,
            max_budget_remaining=pass2_budget
        )
    except Exception as e:
        print(f"\n[FAIL] Pass 2 failed: {e}")
        print("  (Continuing to Pass 3 with data from Pass 1)")

    # ========================================================================
    # PASS 3: CONSOLIDATION
    # ========================================================================

    print("\n" + "="*80)
    print("STARTING PASS 3: Consolidation")
    print("="*80)
    print()

    try:
        consolidator = YAMLConsolidator(
            resolved_dir=output_dir / "resolved",
            output_dir=final_yaml_dir
        )
        consolidator.consolidate_all()
    except Exception as e:
        print(f"\n[FAIL] Pass 3 failed: {e}")
        return

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================

    end_time = datetime.datetime.now()
    duration = end_time - start_time

    print("\n" + "="*80)
    print("[OK] COMPLETE EXTRACTION PIPELINE FINISHED")
    print("="*80)
    print(f"Start time:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End time:    {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration:    {duration}")
    print()
    print(f"Final output: {final_yaml_dir.absolute()}")
    print()
    print("Master YAML files created:")
    for yaml_file in ["soc.yaml", "regs.yaml", "bus.yaml", "irq.yaml", "memmap.yaml", "pinmux.yaml"]:
        file_path = final_yaml_dir / yaml_file
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print(f"  [OK] {yaml_file} ({size_kb:.1f} KB)")
        else:
            print(f"  [FAIL] {yaml_file} (NOT CREATED)")
    print()
    print("Next steps:")
    print("  1. Review yaml_in/*.yaml files")
    print("  2. Check for any TODO or x-needs-verification entries")
    print("  3. Run: python main.py (to generate BSP code)")
    print("="*80)


# ============================================================================
# CLI
# ============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Run complete 3-pass YAML extraction (overnight script)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Full extraction (all 35 peripherals + datasheet)
  python run_complete_extraction.py

  # Test run (3 peripherals only)
  python run_complete_extraction.py --test

  # Faster extraction (more parallel)
  python run_complete_extraction.py --concurrent 6

  # Use cheaper model
  python run_complete_extraction.py --model haiku4.5

Expected:
  - Time: 1.5-2 hours for full extraction
  - Cost: $50-60 (with $75 safety limit)
  - Output: 6 complete YAML files in yaml_in/
        """
    )

    parser.add_argument(
        "--trm",
        type=Path,
        default=Path("modules/pdfs/TRM_split"),
        help="TRM directory (default: modules/pdfs/TRM_split)"
    )
    parser.add_argument(
        "--datasheet",
        type=Path,
        help="Datasheet PDF (auto-detected from input_docs/ if not specified)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("yaml_out"),
        help="Working directory (default: yaml_out)"
    )
    parser.add_argument(
        "--final-output",
        type=Path,
        default=Path("yaml_in"),
        help="Final YAML directory (default: yaml_in)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Max concurrent extractions (default: 4)"
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=75.0,
        help="Total budget in USD (default: 75.00)"
    )
    parser.add_argument(
        "--model",
        choices=["haiku4.5", "sonnet4.5"],
        default="sonnet4.5",
        help="Claude model (default: sonnet4.5)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: Only extract GIO, SCI, SYSTEM (for testing)"
    )

    args = parser.parse_args()

    # Auto-detect datasheet
    if not args.datasheet:
        input_docs = Path("input_docs")
        if input_docs.exists():
            candidates = []
            for pdf in input_docs.glob("*.pdf"):
                # Skip schematic files
                if "schematic" in pdf.name.lower():
                    continue

                size_mb = pdf.stat().st_size / (1024 * 1024)

                # Prefer files with "datasheet" in name
                if "datasheet" in pdf.name.lower():
                    args.datasheet = pdf
                    print(f"Auto-detected datasheet: {pdf.name} ({size_mb:.1f} MB)\n")
                    break

                # Otherwise collect candidates >1MB (likely datasheets, not schematics)
                if size_mb > 1:
                    candidates.append((pdf, size_mb))

            # If no explicit "datasheet" name found, use largest candidate
            if not args.datasheet and candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                args.datasheet = candidates[0][0]
                print(f"Auto-detected datasheet: {args.datasheet.name} ({candidates[0][1]:.1f} MB)\n")

    if not args.datasheet:
        print("WARNING: No datasheet found in input_docs/")
        print("  Pinmux and IRQ tables will be incomplete")
        print("  Place datasheet in input_docs/ for complete extraction\n")

    model = Model.HAIKU_4_5 if args.model == "haiku4.5" else Model.SONNET_4_5

    # TEST MODE: Only extract 3 peripherals
    if args.test:
        print("="*80)
        print("TEST MODE: Only extracting GIO, SCI, SYSTEM")
        print("="*80)
        print()

        from extract_to_yaml import extract_all_peripherals

        await extract_all_peripherals(
            trm_dir=args.trm,
            datasheet_path=args.datasheet,
            output_dir=args.output,
            model=model,
            max_concurrent=2,
            max_budget=10.0,
            test_peripherals=["GIO", "SCI", "SYSTEM"]
        )

        print("\n[OK] Test extraction complete")
        print(f"Check output: {args.output / 'extracted'}")
        return

    # FULL EXTRACTION
    await run_complete_extraction(
        trm_dir=args.trm,
        datasheet_path=args.datasheet,
        output_dir=args.output,
        final_yaml_dir=args.final_output,
        model=model,
        max_concurrent=args.concurrent,
        total_budget=args.budget
    )


if __name__ == "__main__":
    asyncio.run(main())
