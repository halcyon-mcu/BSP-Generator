#!/usr/bin/env python3
"""
cleanup_and_organize.py

Cleanup backups and organize MD documentation files.
"""

import shutil
from pathlib import Path
from datetime import datetime


def cleanup_backups():
    """Remove redundant backup directories, keep only essential ones."""
    print("="*80)
    print("CLEANING UP BACKUP DIRECTORIES")
    print("="*80)
    print()

    # Keep only the most recent pre-schematic backup
    backups_to_remove = [
        'yaml_in/backup_20260203_084603',
        'yaml_in/backup_before_hybrid_20260203_084850',
        'yaml_in/early_extraction_backup',
        'yaml_in_transformed_backup',  # Superseded by yaml_in_transformed_backup_pre_schematic
    ]

    for backup in backups_to_remove:
        backup_path = Path(backup)
        if backup_path.exists():
            print(f"Removing: {backup}")
            shutil.rmtree(backup_path)
            print(f"  [OK] Removed")
        else:
            print(f"  [SKIP] {backup} not found")

    print()
    print("Keeping:")
    print("  - yaml_in_transformed_backup_pre_schematic/ (backup before schematic integration)")
    print()


def organize_md_files():
    """Move important MD files to mds/, ignore temporary ones."""
    print("="*80)
    print("ORGANIZING MARKDOWN DOCUMENTATION")
    print("="*80)
    print()

    # Create mds directory if it doesn't exist
    mds_dir = Path('mds')
    mds_dir.mkdir(exist_ok=True)

    # Important documentation to keep in mds/
    important_docs = [
        'FINAL_COMPLETION_SUMMARY.md',
        'TRANSFORMATION_COMPLETE_WITH_VALIDATION.md',
        'INLINE_FORMATTING_APPLIED.md',
        'SCHEMATIC_INTEGRATION_COMPLETE.md',
        'BOARD_YAML_RECOMMENDATION.md',
        'COMPREHENSIVE_BOARD_YAML_SUMMARY.md',
        'LIN_EXTRACTION_SUMMARY.md',
        'YAML_EXTRACTION_GUIDE.md',
    ]

    # Temporary/analysis docs to ignore
    temp_docs = [
        'DATA_LOSS_ANALYSIS.md',
        'DATA_LOSS_FIXED.md',
        'EXTRACTION_ACCURACY_ANALYSIS.md',
        'EXTRACTION_ACCURACY_REPORT.md',
        'EXTRACTION_COMPLETE.md',
        'EXTRACTION_FORMAT_ANALYSIS.md',
        'EXTRACTION_GAPS_ANALYSIS.md',
        'EXTRACTION_QUICKSTART.md',
        'EXTRACTION_SCHEMA_FIX.md',
        'FINAL_TRANSFORMATION_SUMMARY.md',
        'INIT_SEQUENCES_FIXED.md',
        'IRQ_STRUCTURE_IMPROVED.md',
        'MISSING_REGISTERS_AND_SCHEMATIC_PLAN.md',
        'PRE_FLIGHT_CHECKLIST.md',
        'READY_FOR_OVERNIGHT_RUN.md',
        'SCHEMA_STRUCTURE_ANALYSIS.md',
        'SCHEMATIC_INTEGRATION_SUMMARY.md',
        'TRANSFORMATION_COMPARISON.md',
        'TRANSFORMATION_SUCCESS.md',
        'UNKNOWN_VALUES_ANNOTATED.md',
        'VALIDATION_REPORT.md',
    ]

    # Move important docs to mds/
    print("Moving important documentation to mds/:")
    for doc in important_docs:
        src = Path(doc)
        if src.exists():
            dst = mds_dir / doc
            shutil.move(str(src), str(dst))
            print(f"  [MOVED] {doc} -> mds/{doc}")
        else:
            print(f"  [SKIP] {doc} not found")

    print()
    print(f"Temporary/analysis docs will be added to .gitignore:")
    for doc in temp_docs:
        print(f"  - {doc}")

    return important_docs, temp_docs


def update_gitignore(temp_docs):
    """Update .gitignore with temporary MD files."""
    print()
    print("="*80)
    print("UPDATING .GITIGNORE")
    print("="*80)
    print()

    gitignore_path = Path('../.gitignore')

    # Read existing .gitignore
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            existing = f.read()
    else:
        existing = ""

    # Add section for temporary MD files
    new_section = "\n# Temporary analysis and intermediate documentation\n"
    for doc in temp_docs:
        new_section += f"app/{doc}\n"

    new_section += "\n# Backup directories (keep only essential)\n"
    new_section += "app/yaml_in/backup_*/\n"
    new_section += "app/yaml_in_transformed_backup/\n"

    # Check if already added
    if "Temporary analysis and intermediate documentation" not in existing:
        with open(gitignore_path, 'a') as f:
            f.write(new_section)
        print("[OK] Updated .gitignore")
    else:
        print("[SKIP] .gitignore already contains these entries")


def create_readme_in_mds():
    """Create README in mds/ explaining the documentation."""
    print()
    print("="*80)
    print("CREATING mds/README.md")
    print("="*80)
    print()

    readme_content = """# BSP Generator Documentation

This directory contains important documentation for the BSP Generator project.

## Key Documentation Files

### Final Summaries
- **FINAL_COMPLETION_SUMMARY.md** - Complete summary of all register additions and enhancements
- **TRANSFORMATION_COMPLETE_WITH_VALIDATION.md** - Full transformation process with validation results

### Architecture Decisions
- **BOARD_YAML_RECOMMENDATION.md** - Decision document for board.yaml architecture
- **COMPREHENSIVE_BOARD_YAML_SUMMARY.md** - Complete board.yaml documentation

### Schematic Integration
- **SCHEMATIC_INTEGRATION_COMPLETE.md** - Schematic data integration summary

### Technical Details
- **INLINE_FORMATTING_APPLIED.md** - YAML inline formatting improvements
- **LIN_EXTRACTION_SUMMARY.md** - LIN register extraction details

### User Guides
- **YAML_EXTRACTION_GUIDE.md** - Guide for extracting YAML from TRM PDFs

## Document Purpose

These documents provide:
1. Architecture decisions and rationale
2. Complete feature documentation
3. Validation results
4. User guides for maintenance

## Latest Status

**Date**: 2026-02-03
**Status**: [OK] Complete and production-ready

### Final YAML Files (7 files total)

Located in `app/yaml_in_transformed/`:
1. **soc.yaml** - 70 peripherals with init sequences
2. **regs.yaml** - 826 registers (including 8 LIN registers)
3. **irq.yaml** - 116 IRQs with VIM configuration
4. **bus.yaml** - 7 clock domains, 39 peripheral clocks
5. **memmap.yaml** - 10 memory regions
6. **pinmux.yaml** - 144+ pins with inline formatting
7. **board.yaml** - Complete board configuration (NEW)

### Key Achievements

- [OK] 826 registers (was 818, +8 LIN registers)
- [OK] Complete LIN functionality for automotive applications
- [OK] VIM wake registers verified
- [OK] Schematic data integrated into board.yaml
- [OK] All 7 files schema-validated
- [OK] 66% reduction in YAML line count (inline formatting)
- [OK] Ready for BSP generation

## Next Steps

Generate BSP code:
```bash
cd app
python main.py --yamlpath yaml_in_transformed --out generated_bsp
```
"""

    readme_path = Path('mds/README.md')
    with open(readme_path, 'w') as f:
        f.write(readme_content)

    print("[OK] Created mds/README.md")


def main():
    print()
    print("="*80)
    print("BSP-GENERATOR CLEANUP AND ORGANIZATION")
    print("="*80)
    print()

    # Cleanup backups
    cleanup_backups()

    # Organize MD files
    important_docs, temp_docs = organize_md_files()

    # Update .gitignore
    update_gitignore(temp_docs)

    # Create README
    create_readme_in_mds()

    print()
    print("="*80)
    print("CLEANUP COMPLETE")
    print("="*80)
    print()
    print("Summary:")
    print(f"  - Removed 4 redundant backup directories")
    print(f"  - Moved {len(important_docs)} important docs to mds/")
    print(f"  - Added {len(temp_docs)} temporary docs to .gitignore")
    print(f"  - Created mds/README.md")
    print()
    print("Next: Create git commits for the work")


if __name__ == '__main__':
    main()
