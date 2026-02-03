#!/bin/bash
# create_commits.sh
# Create logical git commits for all the work done

echo "================================================================================"
echo "CREATING GIT COMMITS FOR BSP ENHANCEMENTS"
echo "================================================================================"
echo ""

# Commit 1: Add LIN registers to SCI peripheral
echo "Commit 1: Add LIN registers to SCI peripheral"
git add yaml_in_transformed/regs.yaml
git add add_lin_registers.py
git add mds/LIN_EXTRACTION_SUMMARY.md
git add yaml_out/lin_registers_requested.yaml
git commit -m "Add LIN registers to SCI peripheral

- Add 8 LIN registers to SCI peripheral (LINCOMPARE, LINRD0-1, LINMASK, LINID, LINTD0-1, MBRS)
- Extracted from TRM Chapter 28 (Serial Communication Interface with LIN)
- Total SCI registers increased from 24 to 32
- Enables complete LIN (Local Interconnect Network) functionality for automotive applications
- All registers inline formatted for readability
- Schema validation passing

Registers added:
- LINCOMPARE (0x60): Sync break and delimiter configuration
- LINRD0 (0x64): Receive buffer 0 (bytes 0-3)
- LINRD1 (0x68): Receive buffer 1 (bytes 4-7)
- LINMASK (0x6C): ID filtering masks
- LINID (0x70): Identification register
- LINTD0 (0x74): Transmit buffer 0 (bytes 0-3)
- LINTD1 (0x78): Transmit buffer 1 (bytes 4-7)
- MBRS (0x7C): Maximum baud rate prescaler

Files:
- yaml_in_transformed/regs.yaml: Updated with LIN registers
- add_lin_registers.py: Script to add LIN registers
- mds/LIN_EXTRACTION_SUMMARY.md: Detailed extraction documentation
- yaml_out/lin_registers_requested.yaml: Source LIN register definitions

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

echo "[OK] Commit 1 created"
echo ""

# Commit 2: Extract comprehensive schematic data
echo "Commit 2: Extract comprehensive board-level schematic data"
git add yaml_out/schematic_extracted_data.yaml
git add yaml_out/SCHEMATIC_ANALYSIS_SUMMARY.md
git add yaml_out/README_SCHEMATIC_EXTRACTION.md
git add app/schematic_extracted/
git commit -m "Extract comprehensive board-level data from RM46 schematic

- Extract all board-level hardware information from LAUNCHXL2-TMS57012-RM46 schematic
- Comprehensive extraction covering 15 schematic pages
- Document 100+ components with complete specifications

Extracted information:
- Power supply: LM26420 dual-buck regulator (1.2V@3.1A + 3.3V@3.1A)
- Clock system: 16MHz crystal with 33pF load capacitors
- Debug: XDS110 ICDIv2 debugger architecture (TM4C129 debug MCU)
- Communication: CAN (3x), LIN (1x), UART, SPI (4x), I2C, Ethernet signals
- PWM/Timers: 14 ePWM channels, 6 eCAP, 2 eQEP
- ADC: 24 channels with connector routing
- LEDs: 3 user + 1 error (with resistor values)
- Buttons: 2 user + 2 reset (with pull resistors)
- Sensors: TEMT6000 ambient light sensor
- Connectors: 2x BoosterPack (80 pins), JTAG (20 pins), Proto (50 pins)
- Hardware limitations: No CAN/LIN transceivers, no Ethernet PHY

Key findings:
- LIN signals routed to JTAG connector J1 (NOT USB)
- USB connector J13 is debug interface only (XDS110)
- External CAN transceivers required (not populated)
- External LIN transceiver required (not populated)
- Current monitor circuit for real-time power analysis

Files:
- yaml_out/schematic_extracted_data.yaml: Complete machine-readable board config (34KB)
- yaml_out/SCHEMATIC_ANALYSIS_SUMMARY.md: Human-readable summary
- yaml_out/README_SCHEMATIC_EXTRACTION.md: Extraction methodology
- app/schematic_extracted/: 15 high-res schematic page images + text

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

echo "[OK] Commit 2 created"
echo ""

# Commit 3: Integrate schematic data (minor updates to existing files)
echo "Commit 3: Integrate schematic data into MCU YAML files"
git add yaml_in_transformed/bus.yaml
git add yaml_in_transformed/soc.yaml
git add integrate_schematic_to_yamls.py
git commit -m "Integrate schematic data into bus.yaml and soc.yaml

Minor integration of schematic-extracted data into MCU-centric YAML files:

bus.yaml enhancements:
- Add external crystal as clock source (XTAL)
- Include crystal specifications: 16MHz, 33pF load caps
- Document OSCIN/OSCOUT/KGND pin connections

soc.yaml enhancements:
- Add board metadata section
- Board name: LAUNCHXL2-TMS57012-RM46
- Power supply: LM26420 regulator specs

pinmux.yaml enhancements:
- Add schematic provenance to 4 critical pins
- Document clock pins (OSCIN, OSCOUT, KGND)
- Light sensor connection (TEMT6000 on AD1IN[6])

Files:
- yaml_in_transformed/bus.yaml: Crystal config added
- yaml_in_transformed/soc.yaml: Board metadata added
- integrate_schematic_to_yamls.py: Integration script

Note: Most schematic data moved to board.yaml (see next commit)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

echo "[OK] Commit 3 created"
echo ""

# Commit 4: Create comprehensive board.yaml
echo "Commit 4: Add comprehensive board.yaml for board-level configuration"
git add yaml_in_transformed/board.yaml
git add yaml_schemas/board.schema.yaml
git add create_board_yaml_comprehensive.py
git add validate_schemas.py
git add mds/BOARD_YAML_RECOMMENDATION.md
git add mds/COMPREHENSIVE_BOARD_YAML_SUMMARY.md
git add mds/SCHEMATIC_INTEGRATION_COMPLETE.md
git commit -m "Add comprehensive board.yaml as 7th YAML file

Architecture decision: Create board.yaml as separate file for board-level configuration,
maintaining clean separation between MCU capabilities (TRM) and board implementation (schematic).

board.yaml contents (comprehensive):
- Board identification: LAUNCHXL2-TMS57012-RM46, Texas Instruments
- Power supply: LM26420 dual-buck with complete voltage rail details
- Clock system: 16MHz crystal with load caps and fault injection
- Debug: XDS110 ICDIv2 debugger architecture
- Communication interfaces:
  * 3x CAN (DCAN1-3) - pins, connectors, NO transceivers
  * 1x LIN - pins 131/132 to JTAG J1, NO transceiver
  * 1x UART/SCI - pins 38/39 to JTAG + BoosterPack
  * 4x SPI (MibSPI1/3/5, SPI4) - complete pin mappings
  * 1x I2C - pins 3/4 to BoosterPack
  * Ethernet MII/RMII - signals available, NO PHY chip
- PWM/Timers: 14 ePWM channels, 6 eCAP, 2 eQEP (all with pin assignments)
- ADC: 24 channels mapped to BoosterPack connectors
- LEDs: 3 with GPIO pins, colors, resistors, active states
- Buttons: 2 with pull resistors and active states
- Sensors: TEMT6000 light sensor on AD1IN[6]
- Connectors: 2x BoosterPack (80 pins), JTAG (20 pins), Proto (50 pins)
- Hardware limitations: Clearly documented (no CAN/LIN transceivers, no Ethernet PHY)
- GPIO mapping: Pin to function assignments

Benefits:
- Clean separation: MCU layer (6 files) vs Board layer (board.yaml)
- Multi-board support: Same MCU files, swap board.yaml for different boards
- Complete hardware documentation in one place
- Enables board-specific BSP code generation

Files:
- yaml_in_transformed/board.yaml: Complete board configuration (~550 lines)
- yaml_schemas/board.schema.yaml: Board YAML schema
- create_board_yaml_comprehensive.py: Generation script
- validate_schemas.py: Updated to validate board.yaml
- mds/BOARD_YAML_RECOMMENDATION.md: Architecture decision document
- mds/COMPREHENSIVE_BOARD_YAML_SUMMARY.md: Complete board.yaml documentation
- mds/SCHEMATIC_INTEGRATION_COMPLETE.md: Integration summary

Schema validation: All 7 YAML files pass validation

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

echo "[OK] Commit 4 created"
echo ""

# Commit 5: Inline formatting
echo "Commit 5: Apply inline formatting to all YAML files"
git add inline_yaml_format.py
git add mds/INLINE_FORMATTING_APPLIED.md
git commit -m "Apply inline/flow-style formatting to YAML files

Apply compact inline formatting to reduce file sizes while improving readability:

Formatting improvements:
- Register fields: 8 lines -> 1 line per field (71% reduction in regs.yaml)
- Init sequences: 4 lines -> 1 line per step (48% reduction in soc.yaml)
- Pin functions: 6 lines -> 1 line per function (85% reduction in pinmux.yaml)
- x-source metadata: 5 lines -> 1 line (where simple enough)

File size reductions:
- regs.yaml: 25,000 -> 7,268 lines (71% reduction)
- soc.yaml: 2,632 -> 1,359 lines (48% reduction)
- pinmux.yaml: 4,100 -> 609 lines (85% reduction)
- Total: ~33,000 -> 11,431 lines (66% reduction)

Benefits:
- Faster visual scanning of tabular data
- Better grep/search (single-line patterns)
- Smaller git diffs for changes
- Easier code review
- Schema compliance maintained 100%
- BSP generator compatibility preserved

Example transformation:
Before:
  - name: PARENA
    msb: 3
    lsb: 0
    access: RW
    desc: VIM parity enable

After:
  - { name: \"PARENA\", msb: 3, lsb: 0, access: RW, desc: \"VIM parity enable\" }

Files:
- inline_yaml_format.py: Formatting script
- mds/INLINE_FORMATTING_APPLIED.md: Complete documentation

All YAML files reformatted and validated successfully.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

echo "[OK] Commit 5 created"
echo ""

# Commit 6: Cleanup and documentation
echo "Commit 6: Cleanup backups and organize documentation"
git add .gitignore
git add mds/
git add mds/README.md
git add cleanup_and_organize.py
git commit -m "Cleanup backups and organize documentation

Cleanup:
- Remove 4 redundant backup directories
- Keep yaml_in_transformed_backup_pre_schematic/ (essential backup)
- Move 8 important docs to mds/ directory
- Add 21 temporary/analysis docs to .gitignore

Documentation organization (mds/):
- FINAL_COMPLETION_SUMMARY.md - Final summary of all enhancements
- TRANSFORMATION_COMPLETE_WITH_VALIDATION.md - Complete transformation with validation
- INLINE_FORMATTING_APPLIED.md - Formatting documentation
- SCHEMATIC_INTEGRATION_COMPLETE.md - Schematic integration summary
- BOARD_YAML_RECOMMENDATION.md - Board.yaml architecture decision
- COMPREHENSIVE_BOARD_YAML_SUMMARY.md - Complete board.yaml docs
- LIN_EXTRACTION_SUMMARY.md - LIN register extraction details
- YAML_EXTRACTION_GUIDE.md - User guide for YAML extraction
- README.md - Documentation index and project status

Files cleaned up:
- Removed: yaml_in/backup_* (4 directories)
- Moved: 8 docs to mds/
- Ignored: 21 temporary analysis docs

Final project status:
- 7 YAML files ready for BSP generation (soc, regs, irq, bus, memmap, pinmux, board)
- 826 registers (including 8 new LIN registers)
- Complete board-level hardware documentation
- All schemas validated
- 66% reduction in YAML line count (inline formatting)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"

echo "[OK] Commit 6 created"
echo ""

echo "================================================================================"
echo "ALL COMMITS CREATED"
echo "================================================================================"
echo ""
echo "Summary:"
echo "  1. Add LIN registers to SCI peripheral"
echo "  2. Extract comprehensive board-level schematic data"
echo "  3. Integrate schematic data into MCU YAML files"
echo "  4. Add comprehensive board.yaml for board configuration"
echo "  5. Apply inline formatting to all YAML files"
echo "  6. Cleanup backups and organize documentation"
echo ""
echo "Next: Review with 'git log' and push to remote if satisfied"
