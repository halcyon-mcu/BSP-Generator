# Archived Modules

These modules were used during **one-time** extraction and transformation phases of the BSP-Generator project. They are no longer part of the active generation pipeline but are preserved here for reference.

## Packages

| Directory | Purpose | When Used |
|-----------|---------|-----------|
| `extraction/` | PDF-to-YAML extraction from TI Technical Reference Manual | Initial data extraction phase |
| `registers/` | Register discovery and annotation from PDFs | Initial register definition phase |
| `testing/` | Prototype auto-test generation framework | Experimental (never integrated) |
| `transformation/` | YAML schema transformation from extracted to production format | Initial data transformation phase |
| `integration/` | Schematic integration into YAML configs | Board integration phase |
| `maintenance/` | Cleanup and git commit helper scripts | Ad-hoc maintenance |
| `scripts/` | One-time fix scripts (base addresses, SOC refs, JSON schemas, forensics) | Ad-hoc fixes |

## Individual Files

| File | Purpose |
|------|---------|
| `progress_tracker.py` | Superseded by `modules/utils/unified_progress.py` |
| `progress_tracker_example.py` | Example for the deprecated progress tracker |
| `fix_irq_yaml.py` | One-time IRQ YAML correction script |
| `bsp-generator.py` | Legacy entry point shim (use `main.py` instead) |
| `PROGRESS_*.md` | Documentation for the deprecated progress tracker |
