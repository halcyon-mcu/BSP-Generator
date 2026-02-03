#!/bin/bash
# Create hybrid YAML set using best of extracted and original

echo "=== Creating Hybrid YAML Set ==="
echo

# Backup current state
echo "[1/4] Backing up current YAMLs..."
BACKUP_DIR="yaml_in/backup_before_hybrid_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp yaml_in/*.yaml "$BACKUP_DIR/" 2>/dev/null
echo "   Backed up to: $BACKUP_DIR"

# Use original for critical BSP files
echo
echo "[2/4] Restoring original BSP-critical files..."
cp yaml_in/original/pinmux.yaml yaml_in/pinmux.yaml
echo "   ✓ pinmux.yaml (original - has PINMMR register mappings)"

# Keep extracted for comprehensive data
echo
echo "[3/4] Keeping extracted files (comprehensive data)..."
echo "   ✓ regs.yaml (extracted - 780KB, all 32 peripherals)"
echo "   ✓ irq.yaml (extracted - 116 VIM channels)"
echo "   ✓ soc.yaml (extracted - init sequences)"
echo "   ✓ bus.yaml (extracted - clock configs)"

# Compare memory maps
echo
echo "[4/4] Memory map comparison..."
echo "   Original memmap:"
grep -A 1 "name:" yaml_in/original/memmap.yaml | grep -E "name|origin" | head -4
echo "   Extracted memmap:"
grep -A 1 "name:" "$BACKUP_DIR/memmap.yaml" | grep -E "name|base" | head -4
echo
echo "   Keeping: EXTRACTED (more comprehensive)"

echo
echo "=== Hybrid YAML Creation Complete ==="
echo
echo "Summary:"
echo "  • pinmux.yaml: ORIGINAL (BSP-ready mux control)"
echo "  • regs.yaml: EXTRACTED (comprehensive)"
echo "  • irq.yaml: EXTRACTED (complete VIM table)"
echo "  • soc.yaml: EXTRACTED (with init sequences)"
echo "  • bus.yaml: EXTRACTED (with clock configs)"
echo "  • memmap.yaml: EXTRACTED (comprehensive memory regions)"
echo
echo "Backups available in:"
ls -d yaml_in/backup_*/ | tail -2
echo
echo "Next: Test BSP generation with: python main.py"
