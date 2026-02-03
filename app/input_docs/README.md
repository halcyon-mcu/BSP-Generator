# Input Documentation Directory

Place your documentation files here for extraction:

## Required Files

1. **Datasheet PDF** - Full device datasheet (~200 pages)
   - Example: `RM46L852_datasheet.pdf`
   - Contains chip-level specs, pinout, electrical characteristics

2. **Schematic PDF** - Board schematic
   - Example: `my_board_schematic.pdf`
   - Contains board-specific connections and components

## Auto-Detection

The script will automatically detect PDFs in this directory:
- Files with "datasheet" or "ds" in the name → treated as datasheet
- Files with "schematic" or "sch" or "board" in the name → treated as schematic
- Larger files (>10 MB) → assumed to be datasheet
- Smaller files → assumed to be schematic

## Usage

```bash
# 1. Place your PDFs in this directory
cp /path/to/RM46L852_datasheet.pdf input_docs/
cp /path/to/board_schematic.pdf input_docs/

# 2. Run extraction (from app/ directory)
cd ..
python extract_complete_reference.py
```

## Multiple Files

If you have multiple datasheets or schematics, the script will try to auto-detect which is which. For best results:
- Name files clearly (include "datasheet" or "schematic" in filename)
- Or place only the files you want to extract

## Optional

You can run without datasheet/schematic (TRM only):
- Just don't place any files here
- The script will extract TRM peripherals only
