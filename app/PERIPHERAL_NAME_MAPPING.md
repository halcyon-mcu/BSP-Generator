# Peripheral Name Mapping: soc.yaml → regs.yaml

**Date**: 2026-02-24

---

## Overview

Cross-reference validation revealed 38 peripherals in soc.yaml that reference missing register definitions. Investigation shows these are **naming mismatches** - the peripherals exist in regs.yaml but with different names.

The issue: soc.yaml uses **instance-specific names** (DCAN1, DCAN2, EPWM1, EPWM2, etc.) while regs.yaml uses **generic peripheral type names** (DCAN, EPWM, etc.) since register layouts are identical across instances.

---

## Complete Mapping

| soc.yaml Name | regs.yaml Name | Type | Notes |
|---------------|----------------|------|-------|
| **I2C** | **INTER** | i2c | Inter-Integrated Circuit |
| **MIBADC1** | **ADC** | mibadc1 | MIB ADC instance 1 |
| **MIBADC2** | **ADC** | mibadc2 | MIB ADC instance 2 |
| **DCAN1** | **DCAN** | can | CAN instance 1 |
| **DCAN2** | **DCAN** | can | CAN instance 2 |
| **DCAN3** | **DCAN** | can | CAN instance 3 |
| **DCC1** | **DCC** | compare | Dual Clock Comparator 1 |
| **DCC2** | **DCC** | compare | Dual Clock Comparator 2 |
| **HTU1** | **HTU** | timer | High-End Timer Transfer Unit 1 |
| **HTU2** | **HTU** | timer | High-End Timer Transfer Unit 2 |
| **MIBSPI1** | **SPI** | spi | MIB SPI instance 1 |
| **SPI2** | **SPI** | spi | SPI instance 2 |
| **MIBSPI3** | **SPI** | spi | MIB SPI instance 3 |
| **SPI4** | **SPI** | spi | SPI instance 4 |
| **MIBSPI5** | **SPI** | spi | MIB SPI instance 5 |
| **N2HET1** | **TIMER** | timer | N2HET High-End Timer 1 |
| **N2HET2** | **TIMER** | timer | N2HET High-End Timer 2 |
| **ECAP1** | **ECAP** | ecap1 | Enhanced Capture 1 |
| **ECAP2** | **ECAP** | ecap2 | Enhanced Capture 2 |
| **ECAP3** | **ECAP** | ecap3 | Enhanced Capture 3 |
| **ECAP4** | **ECAP** | ecap4 | Enhanced Capture 4 |
| **ECAP5** | **ECAP** | ecap5 | Enhanced Capture 5 |
| **ECAP6** | **ECAP** | ecap6 | Enhanced Capture 6 |
| **EPWM1** | **EPWM** | epwm1 | Enhanced PWM 1 |
| **EPWM2** | **EPWM** | epwm2 | Enhanced PWM 2 |
| **EPWM3** | **EPWM** | epwm3 | Enhanced PWM 3 |
| **EPWM4** | **EPWM** | epwm4 | Enhanced PWM 4 |
| **EPWM5** | **EPWM** | epwm5 | Enhanced PWM 5 |
| **EPWM6** | **EPWM** | epwm6 | Enhanced PWM 6 |
| **EPWM7** | **EPWM** | epwm7 | Enhanced PWM 7 |
| **EQEP1** | **PULSE** | eqep1 | Enhanced Quadrature Encoder 1 |
| **EQEP2** | **PULSE** | eqep2 | Enhanced Quadrature Encoder 2 |
| **MDIO** | **EMACMDIO** | ethernet | Ethernet MAC Management Data I/O |
| **EMAC** | **EMACMDIO** | ethernet | Ethernet MAC (shares regs with MDIO) |
| **USB_DEVICE** | **USB** | usb | USB Device mode |
| **USB_OHCI** | **USB** | usb | USB OHCI Host mode |
| **FLASH_MODULE** | **FMC** | flash | Flash Module Controller |
| **PIN** | **IOMM** | pin | Pin multiplexing (IOMM module) |

---

## Rationale

### Why Generic Names in regs.yaml?

Peripherals like DCAN, SPI, EPWM, etc. have **identical register layouts** across all instances. The differences are only:
- Base addresses (instance 1 vs instance 2)
- Interrupt numbers
- Clock sources

Therefore, regs.yaml defines **one set of register definitions per peripheral type**, and soc.yaml instantiates multiple instances with different base addresses.

**Example: DCAN**
- regs.yaml has **DCAN** with registers (CTL, ES, etc.)
- soc.yaml has **DCAN1** @ 0xFFF7DC00, **DCAN2** @ 0xFFF7DE00, **DCAN3** @ 0xFFF7E000
- All three instances use the same register definitions from regs.yaml:DCAN

---

## Fix Strategy

Add `regs_ref` field to each peripheral in soc.yaml to explicitly map to the correct regs.yaml entry.

**Format:**
```yaml
- name: DCAN1
  regs_ref: DCAN  # ← Maps to DCAN in regs.yaml
  type: can
  base_address: '0xFFF7DC00'
```

---

## Implementation

38 peripherals need `regs_ref` added or corrected in soc.yaml:

### Group 1: ADC (2 instances)
```yaml
- name: MIBADC1
  regs_ref: ADC

- name: MIBADC2
  regs_ref: ADC
```

### Group 2: CAN (3 instances)
```yaml
- name: DCAN1
  regs_ref: DCAN

- name: DCAN2
  regs_ref: DCAN

- name: DCAN3
  regs_ref: DCAN
```

### Group 3: Clock Comparator (2 instances)
```yaml
- name: DCC1
  regs_ref: DCC

- name: DCC2
  regs_ref: DCC
```

### Group 4: Enhanced Capture (6 instances)
```yaml
- name: ECAP1
  regs_ref: ECAP
# ... ECAP2-6 similarly
```

### Group 5: Enhanced PWM (7 instances)
```yaml
- name: EPWM1
  regs_ref: EPWM
# ... EPWM2-7 similarly
```

### Group 6: Quadrature Encoder (2 instances)
```yaml
- name: EQEP1
  regs_ref: PULSE

- name: EQEP2
  regs_ref: PULSE
```

### Group 7: Ethernet (2 peripherals, shared regs)
```yaml
- name: EMAC
  regs_ref: EMACMDIO

- name: MDIO
  regs_ref: EMACMDIO
```

### Group 8: Flash
```yaml
- name: FLASH_MODULE
  regs_ref: FMC
```

### Group 9: HTU (2 instances)
```yaml
- name: HTU1
  regs_ref: HTU

- name: HTU2
  regs_ref: HTU
```

### Group 10: I2C
```yaml
- name: I2C
  regs_ref: INTER
```

### Group 11: Pin Mux
```yaml
- name: PIN
  regs_ref: IOMM
```

### Group 12: SPI (5 instances)
```yaml
- name: MIBSPI1
  regs_ref: SPI

- name: SPI2
  regs_ref: SPI

- name: MIBSPI3
  regs_ref: SPI

- name: SPI4
  regs_ref: SPI

- name: MIBSPI5
  regs_ref: SPI
```

### Group 13: Timers (2 N2HET instances)
```yaml
- name: N2HET1
  regs_ref: TIMER

- name: N2HET2
  regs_ref: TIMER
```

### Group 14: USB (2 modes, shared regs)
```yaml
- name: USB_DEVICE
  regs_ref: USB

- name: USB_OHCI
  regs_ref: USB
```

---

## Verification

After adding `regs_ref` fields, validation should pass:

```bash
$ python main.py
✓ All YAML schema validations passed
✓ Cross-reference validation passed
```

---

## Summary

- **Root cause**: Instance-specific names in soc.yaml vs generic type names in regs.yaml
- **Solution**: Add explicit `regs_ref` field to map instances to register definitions
- **Affected**: 38 peripherals across 14 groups
- **Pattern**: Multiple instances share one register definition (expected for identical hardware)

---

**Status**: Mapping identified, ready to fix soc.yaml
