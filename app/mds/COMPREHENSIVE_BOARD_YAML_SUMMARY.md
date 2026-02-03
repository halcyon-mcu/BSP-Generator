# Comprehensive board.yaml Summary

**Date**: 2026-02-03
**Status**: ✅ COMPLETE AND VALIDATED

---

## Overview

Created a **thoroughly comprehensive board.yaml** with ALL schematic details needed for complete board-aware BSP generation.

### Key Statistics

| Category | Count | Details |
|----------|-------|---------|
| **LEDs** | 3 | Error (red) + 2 user (green) with all connection details |
| **Buttons** | 2 | User buttons with pull-up resistors |
| **Sensors** | 1 | TEMT6000 ambient light sensor |
| **Power Regulators** | 1 | LM26420 dual-buck (1.2V + 3.3V) |
| **Voltage Rails** | 6 | Complete with pin lists and decoupling caps |
| **CAN Interfaces** | 3 | DCAN1, DCAN2, DCAN3 (no transceivers) |
| **LIN Interfaces** | 1 | LIN1 routed to JTAG J1 (no transceiver) |
| **UART/SCI** | 1 | Routed to JTAG and BoosterPack |
| **SPI Interfaces** | 4 | MibSPI1, MibSPI3, MibSPI5, SPI4 |
| **I2C** | 1 | Routed to BoosterPack J2 |
| **ePWM Channels** | 14 | Complete pin mappings |
| **eCAP Channels** | 6 | Capture modules |
| **eQEP Channels** | 2 | Quadrature encoder interfaces |
| **ADC Channels** | 24 | Complete with BoosterPack routing |
| **Connectors** | 4 | 2x BoosterPack, JTAG, Proto header |

---

## What's Included - Complete Breakdown

### 1. Board Identification
```yaml
board:
  name: LAUNCHXL2-TMS57012-RM46
  revision: Rev 1.0
  manufacturer: Texas Instruments
  description: TI LaunchPad XL2 Development Board
  schematic:
    source: RM46_schematic.pdf
    revision_date: 2014-10-24
```

### 2. Power Supply - COMPLETE Details

**Regulator**:
- Part: LM26420XMHX/NOPB (dual synchronous buck)
- Switching frequency: 2.2MHz
- Channel 1: 1.2V @ 3.1A (core) with L1 = 1µH inductor
- Channel 2: 3.3V @ 3.1A (IO) with L2 = 1µH inductor

**Voltage Rails** with pin lists:
- **VCC (1.2V)**: 12 pins listed + 13 decoupling caps (10µF + 12×0.1µF)
- **VCCIO (3.3V)**: 6 pins listed + 7 decoupling caps (10µF + 6×0.1µF)
- **VCCP (3.3V)**: Peripheral voltage
- **VCCAD (3.3V)**: Analog voltage for ADC
- **VSS (GND)**: 18 ground pins listed
- **VSSAD (GND)**: Analog ground

**Current Monitor**:
- Part: INA210_DCK_6
- Sense resistor: 4.99Ω (1%)
- Output: HERCULES_ICORE to debug MCU
- Purpose: Real-time core current monitoring

### 3. Clock System - COMPLETE Details

**Crystal**:
- Frequency: 16.000 MHz (16000000 Hz)
- Part: Y1 (16.00MHz Crystal)
- Pins: OSCIN (18), OSCOUT (20), KGND (19)
- Load caps: C1 = 33pF ±5%, C2 = 33pF ±5% (50V)

**Fault Injection Circuit**:
- Jumper: JP1
- Purpose: OSC FAULT INJECT for testing
- Components: R1/R2/R3 (0Ω series), R4 (DNP)

### 4. Debug Architecture - COMPLETE Details

**Onboard Debugger**:
- Type: **XDS110 ICDIv2** (not just "XDS110")
- Debug MCU: TM4C129 (separate MCU dedicated to debugging)
- Capabilities:
  - JTAG debugging
  - UART passthrough
  - Virtual COM port
  - Real-time current monitoring

**JTAG Connector (J1)**:
- Type: 20-pin header (0.1" pitch)
- All signals with pin numbers and net names:
  - TMS (pin 108), TCK (pin 112), TDI (pin 110), TDO (pin 111)
  - nTRST (pin 109) with 10kΩ pull-up
  - RTCK (pin 113)
  - TEST (pin 34) with 2.2kΩ pull-down
- **Additional signals routed to J1**:
  - LIN RX/TX (pins 131/132)
  - CAN1/2/3 RX/TX
  - SCI RX/TX

**Debug USB (J13)**:
- Type: Micro-B USB connector
- Function: Debug interface only (NOT target MCU USB)
- ESD protection: TPD4E004_DRY_6
- Current limiter: TPS2553_DBV_6 (~500mA limit)

### 5. Communication Interfaces - COMPLETE Routing

#### CAN Interfaces (3x) - **CRITICAL: No Transceivers!**

**DCAN1**:
```yaml
rx_pin: 90, tx_pin: 89
net_rx: "DCAN1RX / CAN1RX"
net_tx: "DCAN1TX / CAN1TX"
connector: "J1 (JTAG), J11-42/43"
transceiver_populated: false
notes: "CAN transceiver not populated on board"
```

**DCAN2**: pins 129/128 → J1 (JTAG), J11-28/29
**DCAN3**: pins 12/13 → J1 (JTAG), J11-61/62

**⚠️ Important**: External CAN transceiver required for operation!

#### LIN Interface - **Answer to Your Question!**

**LIN1**:
```yaml
rx_pin: 131 (LINRX)
tx_pin: 132 (LINTX)
net_rx: "LINRX / HERCULES_LIN1_RXD"
net_tx: "LINTX / HERCULES_LIN1_TXD"
connector: "J1 (JTAG)"  ← Goes to JTAG, NOT USB!
transceiver_populated: false
notes: "LIN transceiver not populated on board"
```

**Your Question**: "LIN goes to the USB, correct?"
**Answer**: **No**, LIN goes to **JTAG connector J1** for debugging. The USB (J13) is for the XDS110 debugger (TM4C129), not for LIN.

#### UART/SCI Interface
```yaml
rx_pin: 38, tx_pin: 39
connector: "J1, J2-4/5"  ← Goes to JTAG AND BoosterPack
function: "Serial communication interface (UART)"
```

#### SPI Interfaces (4x) - Complete Pin Mappings
- **MibSPI1**: CLK(95), SIMO(93), SOMI(94), NENA(96), NCS[0-2]
- **MibSPI3**: CLK(53), SIMO(52), SOMI(51), NENA(54), NCS[0-3]
- **MibSPI5**: CLK(100), SIMO(99), SOMI(98), NENA(97), NCS[0]
- **SPI4**: CLK(25), SIMO(30), SOMI(31), NENA(23), NCS(24)

#### I2C Interface
```yaml
sda: pin 4, scl: pin 3
connector: "J2-7/8" (BoosterPack)
```

#### Ethernet - **CRITICAL: No PHY!**
```yaml
description: "Media Independent Interface signals (not populated)"
phy_populated: false
notes: "Ethernet PHY not populated on this board"
```
All MII/RMII signals available (16 pins) but **no PHY chip**.

### 6. PWM/Timer Channels - Complete Assignments

**ePWM** (14 channels):
- EPWM1A (pin 14), EPWM1B (pin 16)
- EPWM2A (pin 22), EPWM2B (pin 25)
- EPWM3A (pin 30), EPWM3B (pin 31)
- EPWM4A (pin 32), EPWM4B (pin 36)
- EPWM5A (pin 38), EPWM5B (pin 39)
- EPWM6A (pin 140), EPWM6B (pin 141)
- EPWM7A (pin 35), EPWM7B (pin 33)

**eCAP** (6 channels):
- ECAP1 (pin 41), ECAP2 (pin 51), ECAP3 (pin 52)
- ECAP4 (pin 96), ECAP5 (pin 97), ECAP6 (pin 105)

**eQEP** (2 interfaces):
- EQEP1: EQEP1A (pin 53), EQEP1B (pin 54), EQEP1I (pin 55), EQEP1S (pin 86)
- EQEP2: EQEP2A (pin 91), EQEP2B (pin 92), EQEP2I (pin 25), EQEP2S (pin 93)

### 7. ADC Channels - Complete with Routing

**24 ADC Channels** with BoosterPack connector mapping:
```yaml
AD1IN[0]: pin 60 → J2-8
AD1IN[1]: pin 71 → J6-7
AD1IN[2]: pin 73 → J6-18
# ... all 24 channels mapped
AD1IN[6]: pin 80 → Light sensor (TEMT6000)
```

**Reference voltages**:
- ADREFHI: pin 66
- ADREFLO: pin 67

### 8. Connectors - Detailed Descriptions

**BoosterPack Site 1** (J2, J3, J4, J5):
- 40 pins total
- Standards: 20-pin and 40-pin BoosterPack compatible

**BoosterPack Site 2** (J6, J7, J8, J9):
- 40 pins total
- Standards: 20-pin and 40-pin BoosterPack compatible

**Proto Header** (J11):
- 50 pins
- General purpose with additional signals

**JTAG Debug** (J1):
- 20 pins (0.1" pitch)
- Signals: JTAG + CAN + LIN + SCI

### 9. LEDs - Complete Details

**LED1** (Error):
```yaml
designator: LED1
color: RED
function: ERROR LED
mcu_pin: 117 (NERROR)
series_resistor: 2.2kΩ
active_state: LOW
```

**LED2** (User):
```yaml
designator: LED2
color: GRN
mcu_pin: 142 (GIOB[2])
series_resistor: 2.2kΩ
active_state: LOW
```

**LED3** (User):
```yaml
designator: LED3
color: GRN
mcu_pin: 133 (GIOB[1])
series_resistor: 2.2kΩ
active_state: LOW
```

### 10. Buttons - Complete Details

**S3** (User button):
```yaml
mcu_pin: 55
pull_resistor: 2.2kΩ
pull_direction: up
pull_connection: +3V3
active_state: LOW
```

**S4** (User button):
```yaml
pull_resistor: 2.2kΩ
pull_direction: up
pull_connection: +3V3
active_state: LOW
```

### 11. Sensors

**Q1** (TEMT6000 Light Sensor):
```yaml
part_number: TEMT6000
type: Ambient light sensor (phototransistor)
mcu_pin: 80
interface: analog
adc_channel: AD1IN_6
bias_resistor: { designator: R14, value: 5.76kΩ, tolerance: 1% }
filter_capacitor: { designator: C24, value: 4700pF }
supply: +3V3
```

### 12. Hardware Limitations - CRITICAL Information

**Missing Components**:
1. CAN transceivers (DCAN1/2/3) - signals available, **external transceiver required**
2. LIN transceiver (LIN1) - signals available, **external transceiver required**
3. Ethernet PHY chip - MII/RMII signals available, **external PHY required**
4. Target USB connector - USB signals available but **not routed to connector**

**Important Notes**:
- USB connector (J13) is **debug only** (XDS ICDIv2), NOT target MCU USB
- CAN, LIN, Ethernet require external hardware for operation
- Debug MCU (TM4C129) provides JTAG, UART passthrough, current monitoring
- BoosterPack connectors support standard TI modules
- Light sensor is populated and functional
- Two reset buttons: S1 (power-on), S2 (warm)
- Voltage supervisor monitors both 1.2V and 3.3V rails

### 13. Extended Information (x-ext)

**Reset Circuit**:
- Supervisor: TPS3106K33 (monitors 1.2V and 3.3V)
- Reset buttons: S1 (power-on), S2 (warm)
- MCU connections: NPORRST (pin 46), NRST (pin 116)
- Error signal: NERROR (pin 117)

**Power LEDs** (3x):
- LED4 (green): +3.3V indicator
- LED6 (green): +5V indicator
- LED9 (red): USB power indicator

**Debug MCU LEDs** (2x):
- LED7 (green): Debug status
- LED8 (green): Debug status

---

## Key Answers to Your Questions

### Q: Where do specific GPIO pins map to?

**A**: See complete GPIO mapping in board.yaml:
- **GIOB[2]** (pin 142) → LED2 (user LED, green, 2.2kΩ, active low)
- **GIOB[1]** (pin 133) → LED3 (user LED, green, 2.2kΩ, active low)
- **NERROR** (pin 117) → LED1 (error LED, red, 2.2kΩ, active low)
- Pin 55 → S3 button (2.2kΩ pull-up, active low)

### Q: Where does LIN go?

**A**: **LIN goes to JTAG connector J1**, NOT USB!
- LIN RX: pin 131 → J1 (JTAG)
- LIN TX: pin 132 → J1 (JTAG)
- Purpose: Debug and development
- **No LIN transceiver on board** - external required

### Q: USB vs Debug

**A**: USB connector (J13) is for **XDS110 ICDIv2 debugger ONLY**:
- Connected to TM4C129 debug MCU (separate MCU)
- Provides: JTAG debugging, UART passthrough, virtual COM port, current monitoring
- **NOT connected** to target MCU's USB peripheral
- Target MCU USB signals are available but not routed to a connector

### Q: XDS110 Details

**A**: Full name is **XDS110 ICDIv2**:
- Onboard debugger using TM4C129 MCU
- Capabilities: JTAG, UART, virtual COM, current monitoring
- Connects to host PC via USB (J13)
- Connects to target RM46 MCU via JTAG signals

---

## Benefits of This Comprehensive board.yaml

### 1. Complete Hardware Documentation
Everything documented in one place:
- Every component with part numbers
- Every connection with pin numbers
- Every limitation clearly stated

### 2. BSP Generator Can Create Board-Specific Drivers
```c
// Generated from board.yaml
void board_can_init(void) {
    // From communication.can section
    // DCAN1: pins 90/89, NO transceiver!
    #warning "External CAN transceiver required on DCAN1"
    gpio_set_function(90, DCAN1_RX);
    gpio_set_function(89, DCAN1_TX);
}

void board_lin_init(void) {
    // From communication.lin section
    // LIN1: pins 131/132 → J1 (JTAG), NO transceiver!
    #warning "External LIN transceiver required"
    gpio_set_function(131, LIN1_RX);
    gpio_set_function(132, LIN1_TX);
}
```

### 3. Hardware Limitations Documented
BSP can generate warnings:
```c
#if !defined(EXTERNAL_CAN_TRANSCEIVER)
#error "This board requires external CAN transceiver"
#endif

#if !defined(EXTERNAL_LIN_TRANSCEIVER)
#error "This board requires external LIN transceiver"
#endif
```

### 4. Complete Pin Routing for Debug
Developer knows exactly where each interface goes:
- CAN → J1 (JTAG) + J11 (proto)
- LIN → J1 (JTAG)
- UART → J1 (JTAG) + J2 (BoosterPack)
- I2C → J2 (BoosterPack)

---

## File Size and Organization

**Total**: ~550 lines (comprehensive but organized)

**Sections**:
- Board identification: 10 lines
- Power supply: 150 lines (complete voltage rail details)
- Clock: 30 lines
- LEDs: 30 lines
- Buttons: 20 lines
- Sensors: 15 lines
- Debug: 60 lines
- Communication: 120 lines (all interfaces)
- PWM/Timers: 40 lines
- ADC: 30 lines
- Connectors: 30 lines
- GPIO mapping: 10 lines
- Hardware limitations: 15 lines
- Extended info: 30 lines

---

## Validation Status

✅ **ALL SCHEMAS VALID**

```
Validating soc.yaml... [OK]
Validating regs.yaml... [OK]
Validating irq.yaml... [OK]
Validating bus.yaml... [OK]
Validating memmap.yaml... [OK]
Validating pinmux.yaml... [OK]
Validating board.yaml... [OK]  ← COMPREHENSIVE VERSION
```

---

## Conclusion

Created a **thoroughly comprehensive board.yaml** that includes:

✅ Complete power supply details (regulators, rails, decoupling caps, current monitor)
✅ Crystal configuration with fault injection circuit
✅ All communication interfaces with routing (CAN, LIN, UART, SPI, I2C, Ethernet)
✅ Complete PWM/timer channel assignments (ePWM, eCAP, eQEP)
✅ All ADC channels with BoosterPack routing
✅ Debug architecture details (XDS110 ICDIv2, TM4C129)
✅ Hardware limitations clearly documented
✅ Complete connector details
✅ GPIO pin to function mapping

**Key Clarifications**:
- **LIN goes to JTAG J1**, not USB
- **USB (J13) is debug only** (XDS110), not target MCU
- **No CAN/LIN transceivers** - external required
- **XDS110 ICDIv2** is the full name of the debugger

**Status**: READY FOR BSP GENERATION WITH COMPLETE BOARD AWARENESS

---

**Files**:
- Schema: [yaml_schemas/board.schema.yaml](yaml_schemas/board.schema.yaml)
- Board config: [yaml_in_transformed/board.yaml](yaml_in_transformed/board.yaml)
- Creation script: [create_board_yaml_comprehensive.py](create_board_yaml_comprehensive.py)
