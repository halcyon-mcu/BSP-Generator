# Board.yaml - Recommended Approach for Board-Level Configuration

**Date**: 2026-02-03
**Status**: ✅ IMPLEMENTED AND VALIDATED

---

## Executive Summary

**Recommendation**: Create a **7th YAML file (board.yaml)** as the best way to use comprehensive schematic data.

**Why**: Clean separation between MCU capabilities (from TRM) and board implementation (from schematic), enabling multi-board support and better organization.

---

## The Problem

We extracted comprehensive board-level information from the RM46 LaunchPad XL2 schematic:
- Power supply (regulators, voltages, decoupling caps)
- External crystal with load capacitors
- LEDs, buttons, sensors on specific pins
- Debug interfaces (JTAG connectors, USB)
- Reset circuits (supervisor IC, reset buttons)
- BoosterPack expansion connectors
- External component values (resistors, capacitors)

**Question**: Where does all this data belong?

### Options Considered

**Option A: Cram into existing 6 files**
- ❌ Poor fit - existing files are MCU-centric, not board-centric
- ❌ Clutters files with data that doesn't naturally belong
- ❌ Can't support multiple boards with same MCU
- ❌ Example: Where do LED connections go? Power supply specs? Reset circuit?

**Option B: Keep separate (schematic_extracted_data.yaml only)**
- ❌ Data exists but isn't integrated into BSP generation
- ❌ BSP generator wouldn't use it
- ❌ Wasted extraction effort

**Option C: Create board.yaml** ✅ **RECOMMENDED**
- ✅ Clean separation of concerns
- ✅ Natural organization
- ✅ Multi-board support
- ✅ Easy BSP generation integration

---

## Architecture: MCU Layer vs Board Layer

### Current 6 Files = MCU Layer (from TRM)

These describe **what the MCU can do**:

| File | Purpose | Source |
|------|---------|--------|
| **soc.yaml** | MCU peripherals, capabilities | TRM |
| **regs.yaml** | MCU register definitions | TRM |
| **bus.yaml** | MCU clock domains | TRM |
| **irq.yaml** | MCU interrupt controller | TRM |
| **memmap.yaml** | MCU memory layout | TRM |
| **pinmux.yaml** | MCU pin multiplexing options | TRM |

**Characteristics**:
- MCU-centric (RM46L852 specific)
- Same for any board using this MCU
- Documents hardware capabilities

### New board.yaml = Board Layer (from Schematic)

Describes **how this board is wired**:

| File | Purpose | Source |
|------|---------|--------|
| **board.yaml** | Board implementation | Schematic |

**Contents**:
- Board identification (name, revision, manufacturer)
- Power supply (regulators, voltages)
- External crystal configuration
- LEDs (which pins, colors, resistors)
- Buttons (which pins, pull resistors)
- Sensors (types, connections)
- Debug interfaces (JTAG, USB connectors)
- Reset circuits (supervisor ICs, buttons)
- Expansion connectors (BoosterPacks)
- External component values

**Characteristics**:
- Board-centric (LAUNCHXL2 specific)
- Different for each board design
- Documents board implementation

---

## Benefits of board.yaml

### 1. Clean Separation of Concerns

```
MCU Layer (TRM)              Board Layer (Schematic)
═══════════════              ═══════════════════════
What CAN be done     →       What IS implemented
Hardware capabilities →       Board-specific wiring
Portable across boards →     Board-specific

Example:
soc.yaml: "MCU has GIOB[2] pin that can be GPIO"
board.yaml: "GIOB[2] is connected to LED2 (green) with 2.2kΩ resistor"
```

### 2. Multi-Board Support

Same MCU, different boards:

```
yaml_in_transformed/
├── soc.yaml           ← RM46L852 (same for all boards)
├── regs.yaml          ← RM46L852 (same for all boards)
├── bus.yaml           ← RM46L852 (same for all boards)
├── irq.yaml           ← RM46L852 (same for all boards)
├── memmap.yaml        ← RM46L852 (same for all boards)
├── pinmux.yaml        ← RM46L852 (same for all boards)
└── board.yaml         ← LAUNCHXL2 specific

# For a custom board, just swap board.yaml:
└── board_custom.yaml  ← Custom board specific
```

**Use case**: Generate BSP for multiple board variants:
```bash
# LaunchPad XL2
python main.py --board board.yaml --out launchxl2_bsp

# Custom production board
python main.py --board board_custom.yaml --out production_bsp
```

### 3. Natural Organization

All board-level data in one place:

```yaml
board.yaml:
  board:
    name: LAUNCHXL2-TMS57012-RM46
    manufacturer: Texas Instruments

  power:
    regulators:
      - part_number: LM26420XMHX/NOPB
        channels:
          - voltage: 1.2V, current: 3.1A  # Core
          - voltage: 3.3V, current: 3.1A  # IO

  clock:
    crystal:
      frequency: 16MHz
      load_caps: 33pF

  leds:
    - LED1: NERROR (red), pin 117, 2.2kΩ, active low
    - LED2: GIOB[2] (green), pin 142, 2.2kΩ, active low
    - LED3: GIOB[1] (green), pin 133, 2.2kΩ, active low

  buttons:
    - S3: User button, pin 55, 2.2kΩ pull-up, active low
    - S4: User button, 2.2kΩ pull-up, active low

  sensors:
    - TEMT6000: Light sensor, pin 80, ADC1IN[6]

  debug:
    jtag: J1 (20-pin)
    usb: J13 (Micro-B, XDS ICDIv2)

  connectors:
    - BoosterPack Site 1: 40 pins
    - BoosterPack Site 2: 40 pins
```

### 4. Better BSP Code Generation

BSP generator can create board-specific drivers:

**board_init.c** (generated from board.yaml):
```c
// Generated from board.yaml
#include "board.h"

// From board.yaml: leds section
void board_led_init(void) {
    // LED1 (red): NERROR, pin 117, active low
    gpio_set_direction(117, GPIO_OUTPUT);
    gpio_write(117, GPIO_HIGH);  // Off (active low)

    // LED2 (green): GIOB[2], pin 142, active low, 2.2kΩ
    gpio_set_direction(142, GPIO_OUTPUT);
    gpio_write(142, GPIO_HIGH);  // Off (active low)

    // LED3 (green): GIOB[1], pin 133, active low, 2.2kΩ
    gpio_set_direction(133, GPIO_OUTPUT);
    gpio_write(133, GPIO_HIGH);  // Off (active low)
}

// From board.yaml: buttons section
void board_button_init(void) {
    // S3: User button, pin 55, 2.2kΩ pull-up, active low
    gpio_set_direction(55, GPIO_INPUT);
    gpio_set_pull(55, GPIO_PULL_UP);  // 2.2kΩ pull-up

    // S4: User button, 2.2kΩ pull-up, active low
    gpio_set_pull(GPIO_BUTTON_S4, GPIO_PULL_UP);
}

// From board.yaml: clock section
void board_clock_init(void) {
    // Crystal: 16MHz, load caps: 33pF
    clock_set_external_crystal(16000000, 33e-12);
}

// From board.yaml: power section
void board_power_init(void) {
    // Regulator: LM26420XMHX/NOPB
    // Core: 1.2V @ 3.1A, IO: 3.3V @ 3.1A
    // (Power already configured by bootloader, but info available)
}
```

**board.h** (generated from board.yaml):
```c
#ifndef BOARD_H
#define BOARD_H

// Board identification
#define BOARD_NAME "LAUNCHXL2-TMS57012-RM46"
#define BOARD_REVISION "Rev 1.0"
#define BOARD_MANUFACTURER "Texas Instruments"

// LEDs (from board.yaml)
#define LED_ERROR_PIN    117
#define LED_USER_1_PIN   142
#define LED_USER_2_PIN   133
#define LED_ACTIVE_LOW   1

// Buttons (from board.yaml)
#define BUTTON_S3_PIN    55
#define BUTTON_ACTIVE_LOW 1

// Sensors (from board.yaml)
#define LIGHT_SENSOR_ADC_CHANNEL  ADC1IN_6

// Power supply (from board.yaml)
#define VCC_VOLTAGE   1.2f
#define VCCIO_VOLTAGE 3.3f

// Clock (from board.yaml)
#define CRYSTAL_FREQ_HZ  16000000
#define CRYSTAL_LOAD_CAP 33e-12

void board_init(void);
void board_led_init(void);
void board_button_init(void);
void board_clock_init(void);

#endif
```

---

## What Goes Where

### Existing 6 Files (MCU Layer)

**soc.yaml** - MCU peripherals:
```yaml
peripherals:
  - name: GIO
    type: gpio
    instance: 1
    regs_ref: GIO
    # This says the MCU HAS a GIO peripheral
```

**regs.yaml** - MCU registers:
```yaml
GIO:
  GIOB_DIN:
    offset: '0x44'
    fields:
      - { name: "GIOB[2]", bit: 2, access: R }
    # This says GIOB[2] is bit 2 of register at offset 0x44
```

**bus.yaml** - MCU clock domains:
```yaml
clock_domains:
  - name: VCLK
    source_ref: PLL1
    # This says the MCU has a VCLK clock domain
```

### New board.yaml (Board Layer)

**board.yaml** - Board implementation:
```yaml
leds:
  - designator: LED2
    mcu_pin: 142
    gpio: GIOB[2]
    color: green
    series_resistor: 2.2kΩ
    active_state: LOW
    # This says the BOARD connects LED2 to GIOB[2] with 2.2kΩ resistor

power:
  regulators:
    - part_number: LM26420XMHX/NOPB
      channels:
        - output_voltage: 3.3
    # This says the BOARD uses LM26420 regulator for 3.3V

clock:
  crystal:
    frequency_hz: 16000000
    load_capacitors:
      - { designator: C1, value: 33pF }
    # This says the BOARD uses 16MHz crystal with 33pF load caps
```

---

## Comparison: With vs Without board.yaml

### Without board.yaml (Current State)

```
Problems:
- LED connections buried in comments or not documented
- Power supply info missing
- Crystal specs missing
- Button connections not documented
- BSP generator can't create board-specific code
- Can't support multiple boards with same MCU
```

### With board.yaml (Recommended)

```
Benefits:
✅ All board-level info organized in one file
✅ BSP generator can create board-specific drivers
✅ Easy to support multiple boards (just swap board.yaml)
✅ Clear separation: MCU capabilities vs board implementation
✅ Comprehensive documentation for hardware bring-up
✅ Crystal specs for accurate clock initialization
✅ Power supply info for validation
✅ Debug interface info for development
```

---

## Implementation Status

### ✅ Completed

1. **Schema Created**: [yaml_schemas/board.schema.yaml](yaml_schemas/board.schema.yaml)
   - Defines structure for board-level configuration
   - Covers power, clock, LEDs, buttons, sensors, debug, connectors

2. **Transformation Script**: [create_board_yaml.py](create_board_yaml.py)
   - Transforms schematic_extracted_data.yaml → board.yaml
   - Follows board.schema.yaml structure

3. **board.yaml Generated**: [yaml_in_transformed/board.yaml](yaml_in_transformed/board.yaml)
   - Complete board configuration for LAUNCHXL2
   - Includes power, clock, LEDs, buttons, sensors, debug

4. **Schema Validation**: All 7 files pass validation ✅
   ```
   [OK] soc.yaml
   [OK] regs.yaml
   [OK] irq.yaml
   [OK] bus.yaml
   [OK] memmap.yaml
   [OK] pinmux.yaml
   [OK] board.yaml  ← NEW
   ```

### 📋 Next Steps (For BSP Generator Integration)

1. **Update main.py** to read board.yaml
   ```python
   # Load all 7 YAML files
   yaml_files = {
       'soc': load_yaml('soc.yaml'),
       'regs': load_yaml('regs.yaml'),
       'irq': load_yaml('irq.yaml'),
       'bus': load_yaml('bus.yaml'),
       'memmap': load_yaml('memmap.yaml'),
       'pinmux': load_yaml('pinmux.yaml'),
       'board': load_yaml('board.yaml')  # NEW
   }
   ```

2. **Generate board-specific code**:
   - `generated_bsp/board_init.c` - Board initialization
   - `generated_bsp/board.h` - Board definitions
   - `generated_bsp/board_led.c` - LED drivers
   - `generated_bsp/board_button.c` - Button handlers

3. **Support multi-board**:
   ```bash
   python main.py --board board_launchxl2.yaml --out launchxl2_bsp
   python main.py --board board_custom.yaml --out custom_bsp
   ```

---

## Recommendation Summary

### ✅ **Use board.yaml**

**Why**:
1. **Clean separation**: MCU capabilities vs board implementation
2. **Multi-board support**: Same MCU, different boards
3. **Natural organization**: All board info in one place
4. **Better BSP generation**: Board-specific drivers
5. **Comprehensive**: Power, clock, LEDs, buttons, sensors, debug

**Where**:
- **Location**: `yaml_in_transformed/board.yaml` (alongside existing 6 files)
- **Schema**: `yaml_schemas/board.schema.yaml`
- **Source**: Generated from `schematic_extracted_data.yaml`

**What to do with schematic_extracted_data.yaml**:
- Keep as **reference documentation** (human-readable with all schematic details)
- Use as **source** for generating board.yaml
- **Don't** try to fit it into existing 6 MCU-centric files

---

## Conclusion

**board.yaml is the best approach** because it:
- Provides clean architectural separation (MCU vs board)
- Enables multi-board support
- Organizes board-level data naturally
- Enables better BSP code generation
- Maintains the integrity of existing MCU-centric files

The 7-file architecture (6 MCU + 1 board) creates a **complete source of truth** for hardware-aware BSP generation.

**Status**: ✅ **IMPLEMENTED, VALIDATED, AND READY FOR USE**

---

**Files Created**:
- [yaml_schemas/board.schema.yaml](yaml_schemas/board.schema.yaml) - Schema definition
- [create_board_yaml.py](create_board_yaml.py) - Transformation script
- [yaml_in_transformed/board.yaml](yaml_in_transformed/board.yaml) - Board configuration
- [BOARD_YAML_RECOMMENDATION.md](BOARD_YAML_RECOMMENDATION.md) - This document
