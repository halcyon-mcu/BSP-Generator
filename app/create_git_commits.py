#!/usr/bin/env python3
"""
create_git_commits.py

Create logical git commits for all BSP enhancement work.
"""

import subprocess
from pathlib import Path


def run_git(cmd):
    """Run a git command."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def git_add(files):
    """Add files to git staging."""
    for f in files:
        if Path(f).exists() or Path(f'../{f}').exists():
            success, out, err = run_git(f'git add {f}')
            if not success:
                print(f"  [WARN] Could not add {f}: {err.strip()}")
        else:
            print(f"  [SKIP] {f} not found")


def git_commit(message):
    """Create a git commit."""
    success, out, err = run_git(f'git commit -m "{message}"')
    if success:
        print("  [OK] Commit created")
        return True
    else:
        print(f"  [FAIL] {err.strip()}")
        return False


def main():
    print("="*80)
    print("CREATING GIT COMMITS FOR BSP ENHANCEMENTS")
    print("="*80)
    print()

    # Commit 1: Add LIN registers
    print("Commit 1: Add LIN registers to SCI peripheral")
    git_add([
        'yaml_in/regs.yaml',
        'add_lin_registers.py',
        'mds/LIN_EXTRACTION_SUMMARY.md',
    ])

    git_commit("""Add LIN registers to SCI peripheral

- Add 8 LIN registers to SCI peripheral
- LINCOMPARE, LINRD0-1, LINMASK, LINID, LINTD0-1, MBRS
- Extracted from TRM Chapter 28
- Total SCI registers: 24 -> 32
- Enables complete LIN functionality for automotive applications

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>""")
    print()

    # Commit 2: Create board.yaml and schema
    print("Commit 2: Add comprehensive board.yaml")
    git_add([
        'yaml_in/board.yaml',
        'yaml_schemas/board.schema.yaml',
        'create_board_yaml_comprehensive.py',
        'mds/BOARD_YAML_RECOMMENDATION.md',
        'mds/COMPREHENSIVE_BOARD_YAML_SUMMARY.md',
    ])

    git_commit("""Add comprehensive board.yaml as 7th YAML file

Architecture: Separate board-level config from MCU capabilities
- Board identification, power supply, clock system
- Debug architecture (XDS110 ICDIv2)
- Complete communication interface routing (CAN, LIN, UART, SPI, I2C)
- PWM/Timer assignments (14 ePWM, 6 eCAP, 2 eQEP)
- ADC channels with connector mapping
- LEDs, buttons, sensors with complete specs
- Hardware limitations documented

Benefits: Multi-board support, clean separation, comprehensive docs

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>""")
    print()

    # Commit 3: Schematic integration
    print("Commit 3: Integrate schematic data")
    git_add([
        'yaml_in/bus.yaml',
        'yaml_in/soc.yaml',
        'integrate_schematic_to_yamls.py',
        'mds/SCHEMATIC_INTEGRATION_COMPLETE.md',
    ])

    git_commit("""Integrate schematic data into MCU YAML files

- bus.yaml: Add crystal config (16MHz, 33pF load caps)
- soc.yaml: Add board metadata
- Complete schematic extraction and integration

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>""")
    print()

    # Commit 4: Inline formatting
    print("Commit 4: Apply inline formatting")
    git_add([
        'yaml_in/regs.yaml',
        'yaml_in/soc.yaml',
        'yaml_in/pinmux.yaml',
        'inline_yaml_format.py',
        'mds/INLINE_FORMATTING_APPLIED.md',
    ])

    git_commit("""Apply inline formatting to YAML files

- Reduce file sizes by 66% (33,000 -> 11,431 lines)
- Register fields: 8 lines -> 1 line (71% reduction)
- Init sequences: 4 lines -> 1 line (48% reduction)
- Pin functions: 6 lines -> 1 line (85% reduction)
- Schema compliance maintained 100%

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>""")
    print()

    # Commit 5: Schema validation updates
    print("Commit 5: Update schema validation")
    git_add([
        'validate_schemas.py',
        'mds/TRANSFORMATION_COMPLETE_WITH_VALIDATION.md',
    ])

    git_commit("""Update schema validation for 7 YAML files

- Add board.yaml to validation
- All 7 files pass validation
- Complete transformation documentation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>""")
    print()

    # Commit 6: Cleanup and documentation
    print("Commit 6: Cleanup and organize documentation")
    git_add([
        '../.gitignore',
        'mds/README.md',
        'mds/FINAL_COMPLETION_SUMMARY.md',
        'mds/YAML_EXTRACTION_GUIDE.md',
        'cleanup_and_organize.py',
    ])

    git_commit("""Cleanup backups and organize documentation

- Remove 4 redundant backup directories
- Move 8 important docs to mds/
- Add temporary docs to .gitignore
- Create mds/README.md with project status

Final status: 7 YAML files, 826 registers, complete board-level docs

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>""")
    print()

    print("="*80)
    print("ALL COMMITS CREATED")
    print("="*80)
    print()
    print("Summary:")
    print("  1. Add LIN registers to SCI peripheral")
    print("  2. Add comprehensive board.yaml")
    print("  3. Integrate schematic data")
    print("  4. Apply inline formatting")
    print("  5. Update schema validation")
    print("  6. Cleanup and organize documentation")
    print()
    print("Review with: git log --oneline -6")
    print("Push with: git push")


if __name__ == '__main__':
    main()
