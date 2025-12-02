# RM46 Hardware Information Reference

This document contains detailed hardware information extracted from the RM46BSP codebase.

## Table of Contents
1. [Hardware Reference Manual](#hardware-reference-manual)
2. [GPIO Implementation](#gpio-implementation)
3. [Watchdog Timer Details](#watchdog-timer-details)
4. [VIM (Vectored Interrupt Manager)](#vim-vectored-interrupt-manager)
5. [Clock Management](#clock-management)
6. [Peripheral-Specific Information](#peripheral-specific-information)
7. [Hardware Timing Requirements](#hardware-timing-requirements)
8. [Power Management](#power-management)
9. [Error Handling Mechanisms](#error-handling-mechanisms)
10. [Boot Sequence Information](#boot-sequence-information)
11. [Memory Protection and Access Control](#memory-protection-and-access-control)
12. [Errata Information](#errata-information)

## Hardware Reference Manual

### Complete Register Maps and Memory Addresses

Based on the BSP code, the TI Hercules RM46 has the following memory-mapped peripheral register addresses:

#### Core Components
- **System Control Registers:**
  - Primary System Control (systemREG1): 0xFFFFFF00
  - Secondary System Control (systemREG2): 0xFFFFE100
  - System Port (systemPORT): 0xFFFFFF04

- **Interrupt Management:**
  - VIM (Vectored Interrupt Manager): 0xFFFFFE00

- **Flash Control:**
  - Flash Controller (flashWREG): 0xFFF87000

- **Error Signaling Module (ESM):**
  - ESM Registers (esmREG): 0xFFFFF500

- **Peripheral Central Resource (PCR):**
  - PCR Registers (pcrREG): 0xFFFFE000

#### I/O and Communication Peripherals
- **GPIO Registers:**
  - GIO Base (gioREG): 0xFFF7BC00
  - GIO Port A (gioPORTA): 0xFFF7BC34
  - GIO Port B (gioPORTB): 0xFFF7BC54

- **SPI/MIBSPI Registers:**
  - MIBSPI1 (mibspiREG1): 0xFFF7F400
  - MIBSPI3 (mibspiREG3): 0xFFF7F800
  - MIBSPI5 (mibspiREG5): 0xFFF7FC00
  - MIBSPI1 Port (mibspiPORT1): 0xFFF7F418
  - MIBSPI3 Port (mibspiPORT3): 0xFFF7F818
  - MIBSPI5 Port (mibspiPORT5): 0xFFF7FC18

- **SCI (Serial Communication Interface):**
  - SCI Registers: Not explicitly defined in provided files

- **CAN (Controller Area Network):**
  - CAN1 (canREG1): 0xFFF7DC00
  - CAN2 (canREG2): 0xFFF7DE00
  - CAN3 (canREG3): 0xFFF7E000

#### Analog and Timing Peripherals
- **ADC Registers:**
  - ADC1 (adcREG1): 0xFFF7C000
  - ADC2 (adcREG2): 0xFFF7C200

- **Timer Registers:**
  - RTI (Real-Time Interrupt) (rtiREG1): 0xFFFFFC00
  - HET (High-End Timer): Registers available but addresses not explicitly defined

#### Memory Areas
- **RAM Areas:**
  - Main RAM: 0x08000000 - 0x0802FFFF (192KB)
  - ADC1 RAM (adcRAM1): 0xFF3E0000
  - ADC2 RAM (adcRAM2): 0xFF3A0000
  - MIBSPI1 RAM (mibspiRAM1): 0xFF0E0000
  - MIBSPI3 RAM (mibspiRAM3): 0xFF0C0000
  - MIBSPI5 RAM (mibspiRAM5): 0xFF0A0000
  - CAN1 RAM (canRAM1): 0xFF1E0000
  - CAN2 RAM (canRAM2): 0xFF1C0000
  - CAN3 RAM (canRAM3): 0xFF1A0000

- **Flash Memory:**
  - Flash: 0x00000000 - 0x0014FFFF (1.25MB)
  - IVT (Interrupt Vector Table): 0x00000000
  - CRC Area: 0x00000800
  - Signature: 0x00000804
  - Metadata: 0x00000808
  - Reset Handler: 0x00001000

### System Control Registers (systemREG1: 0xFFFFFF00)

The primary system control module contains the following key registers:

| Register   | Offset | Description |
|------------|--------|-------------|
| SYSPC1-10  | 0x00-0x78 | System Pin Control registers |
| SSWPLL1    | 0x24 | Software-Controlled PLL Register 1 |
| SSWPLL2    | 0x28 | Software-Controlled PLL Register 2 |
| SSWPLL3    | 0x2C | Software-Controlled PLL Register 3 |
| CSDIS      | 0x30 | Clock Source Disable Register |
| CSDISSET   | 0x34 | Clock Source Disable Set Register |
| CSDISCLR   | 0x38 | Clock Source Disable Clear Register |
| CDDIS      | 0x3C | Clock Domain Disable Register |
| CDDISSET   | 0x40 | Clock Domain Disable Set Register |
| CDDISCLR   | 0x44 | Clock Domain Disable Clear Register |
| GHVSRC     | 0x48 | GCLK, HCLK, VCLK Source Register |
| VCLKASRC   | 0x4C | VCLKA Source Register |
| RCLKSRC    | 0x50 | RTI Clock Source Register |
| CSVSTAT    | 0x54 | Clock Source Valid Status Register |
| MSTGCR     | 0x58 | Master Clock Global Control Register |
| MINITGCR   | 0x5C | Mini-Clock Global Control Register |
| MSINENA    | 0x60 | Memory Self-Init Enable Register |
| MSTFAIL    | 0x64 | Master Self-Test Fail Register |
| MSTCGSTAT  | 0x68 | Master Clock Global Status Register |
| MINISTAT   | 0x6C | Mini-Clock Status Register |
| PLLCTL1    | 0x70 | PLL Control Register 1 |
| PLLCTL2    | 0x74 | PLL Control Register 2 |
| DIEIDL     | 0x7C | Device ID Low Register |
| DIEIDH     | 0x80 | Device ID High Register |
| VRCTL      | 0x84 | Voltage Regulator Control Register |
| LPOMONCTL  | 0x88 | LPO Monitor Control Register |
| CLKTEST    | 0x8C | Clock Test Register |
| DFTCTRLREG1| 0x90 | DFT Control Register 1 |
| DFTCTRLREG2| 0x94 | DFT Control Register 2 |
| GPREG1     | 0xA0 | General Purpose Register 1 |
| BTRMSEL    | 0xA4 | Boot ROM Selection Register |
| RAMGCR     | 0xC0 | RAM Global Control Register |
| BMMCR1     | 0xC4 | Backup Memory Map Config Register 1 |
| BMMCR2     | 0xC8 | Backup Memory Map Config Register 2 |
| CPURSTCR   | 0xCC | CPU Reset Control Register |
| CLKCNTL    | 0xD0 | Clock Control Register |
| ECPCNTL    | 0xD4 | ECP Control Register |
| DEVCR1     | 0xDC | Device Control Register 1 |
| SYSECR     | 0xE0 | System Exception Control Register |
| SYSESR     | 0xE4 | System Exception Status Register |
| SYSTASR    | 0xE8 | System Technical Advisory Status Register |
| GBLSTAT    | 0xEC | Global Status Register |
| DEV        | 0xF0 | Device Identification Register |
| SSIVEC     | 0xF4 | SSI Vector Register |
| SSIF       | 0xF8 | SSI Flag Register |

### Secondary System Control Registers (systemREG2: 0xFFFFE100)

The secondary system control module contains these key registers:

| Register   | Offset | Description |
|------------|--------|-------------|
| PLLCTL3    | 0x00 | PLL Control Register 3 |
| STCCLKDIV  | 0x08 | STC Clock Divider Register |
| ECPCNTRL0  | 0x24 | ECP Control Register 0 |
| CLK2CNTL   | 0x3C | CLK2 Control Register |
| VCLKACON1  | 0x40 | VCLKA Control Register 1 |
| CLKSLIP    | 0x70 | Clock Slip Register |
| EFC_CTLEN  | 0xEC | EFC Control Enable Register |
| DIEIDL_REG0| 0xF0 | Die ID Register 0 (Low) |
| DIEIDH_REG1| 0xF4 | Die ID Register 1 (High) |
| DIEIDL_REG2| 0xF8 | Die ID Register 2 (Low) |
| DIEIDH_REG3| 0xFC | Die ID Register 3 (High) |

## GPIO Implementation

The RM46 General Purpose Input/Output (GIO) implementation consists of two ports: Port A and Port B. The GPIO module provides digital input/output functionality with configurable interrupt capabilities.

### GPIO Register Structure

#### GIO Base Registers (0xFFF7BC00)
```c
typedef volatile struct gioBase {
  uint32_t GCR0;   /* 0x0000 - Global Control Register */
  uint32_t rsvd;   /* 0x0004 - Reserved */
  uint32_t INTDET; /* 0x0008 - Interrupt Detect Register */
  uint32_t POL;    /* 0x000C - Interrupt Polarity Register */
  uint32_t ENASET; /* 0x0010 - Interrupt Enable Set Register */
  uint32_t ENACLR; /* 0x0014 - Interrupt Enable Clear Register */
  uint32_t LVLSET; /* 0x0018 - Interrupt Priority Set Register */
  uint32_t LVLCLR; /* 0x001C - Interrupt Priority Clear Register */
  uint32_t FLG;    /* 0x0020 - Interrupt Flag Register */
  uint32_t OFF1;   /* 0x0024 - Interrupt Offset 1 Register */
  uint32_t OFF2;   /* 0x0028 - Interrupt Offset 2 Register */
} gioBASE_t;
```

#### GIO Port Registers
```c
typedef volatile struct gioPort {
  uint32_t DIR;    /* 0x0000 - Direction Register */
  uint32_t DIN;    /* 0x0004 - Data Input Register */
  uint32_t DOUT;   /* 0x0008 - Data Output Register */
  uint32_t DSET;   /* 0x000C - Data Set Register */
  uint32_t DCLR;   /* 0x0010 - Data Clear Register */
  uint32_t PDR;    /* 0x0014 - Open Drain Register */
  uint32_t PULDIS; /* 0x0018 - Pull Disable Register */
  uint32_t PSL;    /* 0x001C - Pull Select Register (Up/Down) */
} gioPORT_t;
```

### Port Addressing
- GIO Port A is located at memory address 0xFFF7BC34
- GIO Port B is located at memory address 0xFFF7BC54

### Pin Configuration
Each port contains registers for configuring pin behavior:

1. **Direction Control (DIR)**:
   - Sets pin as input (0) or output (1)

2. **Input/Output Control**:
   - DIN: Reads the current state of pins
   - DOUT: Sets the output value
   - DSET: Sets specific pins high (without affecting others)
   - DCLR: Sets specific pins low (without affecting others)

3. **Pull-up/Pull-down Configuration**:
   - PULDIS: Disables the pull-up/pull-down resistors
   - PSL: Selects between pull-up (1) or pull-down (0)

4. **Open Drain Control (PDR)**:
   - Enables open-drain mode for outputs

### Interrupt Configuration
GPIO interrupts are configured using the base GIO registers:

1. **Interrupt Detection (INTDET)**:
   - Controls if interrupts trigger on edges or levels

2. **Polarity Configuration (POL)**:
   - Sets whether interrupts trigger on rising/falling edges or high/low levels

3. **Interrupt Enable/Disable**:
   - ENASET: Enables interrupts for specific pins
   - ENACLR: Disables interrupts for specific pins

4. **Priority Control**:
   - LVLSET/LVLCLR: Sets interrupt priority level

5. **Status Monitoring**:
   - FLG: Shows which interrupts are active

## Watchdog Timer Details

The RM46 implements a digital watchdog timer using the Real-Time Interrupt (RTI) module. The watchdog timer provides system protection by resetting the device if software fails to service it within a specified time window.

### Watchdog Register Structure (in RTI module at 0xFFFFFC00)

```c
typedef volatile struct rtiBase {
  // RTI control registers
  uint32_t GCTRL;        /* 0x0000 - Global Control Register */
  uint32_t TBCTRL;       /* 0x0004 - Timebase Control Register */
  uint32_t CAPCTRL;      /* 0x0008 - Capture Control Register */
  uint32_t COMPCTRL;     /* 0x000C - Compare Control Register */

  // Counter registers (array of 2 counters)
  struct {
    uint32_t FRCx;       /* Free-Running Counter */
    uint32_t UCx;        /* Up Counter */
    uint32_t CPUCx;      /* Compare Up Counter */
    uint32_t rsvd1;      /* Reserved */
    uint32_t CAFRCx;     /* Capture Free-Running Counter */
    uint32_t CAUCx;      /* Capture Up Counter */
    uint32_t rsvd2[2U];  /* Reserved */
  } CNT[2U];

  // Compare registers (array of 4 comparators)
  struct {
    uint32_t COMPx;      /* Compare Register */
    uint32_t UDCPx;      /* Update Compare Register */
  } CMP[4U];

  uint32_t TBLCOMP;      /* 0x0070 - Timebase Low Compare Register */
  uint32_t TBHCOMP;      /* 0x0074 - Timebase High Compare Register */
  uint32_t rsvd3[2U];    /* 0x0078 - Reserved */

  // Interrupt registers
  uint32_t SETINTENA;    /* 0x0080 - Set Interrupt Enable Register */
  uint32_t CLEARINTENA;  /* 0x0084 - Clear Interrupt Enable Register */
  uint32_t INTFLAG;      /* 0x0088 - Interrupt Flag Register */
  uint32_t rsvd4;        /* 0x008C - Reserved */

  // Watchdog-specific registers
  uint32_t DWDCTRL;      /* 0x0090 - Digital Watchdog Control Register */
  uint32_t DWDPRLD;      /* 0x0094 - Digital Watchdog Preload Register */
  uint32_t WDSTATUS;     /* 0x0098 - Watchdog Status Register */
  uint32_t WDKEY;        /* 0x009C - Watchdog Key Register */
  uint32_t DWDCNTR;      /* 0x00A0 - Digital Watchdog Down Counter */
  uint32_t WWDRXNCTRL;   /* 0x00A4 - Windowed Watchdog Reaction Control */
  uint32_t WWDSIZECTRL;  /* 0x00A8 - Windowed Watchdog Size Control */

  // Additional registers
  uint32_t INTCLRENABLE; /* 0x00AC - Interrupt Clear Enable Register */
  uint32_t COMP0CLR;     /* 0x00B0 - Compare 0 Clear Register */
  uint32_t COMP1CLR;     /* 0x00B4 - Compare 1 Clear Register */
  uint32_t COMP2CLR;     /* 0x00B8 - Compare 2 Clear Register */
  uint32_t COMP3CLR;     /* 0x00BC - Compare 3 Clear Register */
} rtiBASE_t;
```

### Window Size Configuration

The watchdog timer supports window size configuration, which defines the minimum time between watchdog "pets" (resets). This prevents software from servicing the watchdog too frequently.

Available window size configurations:
```c
enum {
  WD_WINSIZE_100   = 0x00000005U, /* 100% window - no minimum time between pets */
  WD_WINSIZE_50    = 0x00000050U, /* 50% window */
  WD_WINSIZE_25    = 0x00000500U, /* 25% window */
  WD_WINSIZE_12_5  = 0x00005000U, /* 12.5% window */
  WD_WINSIZE_6_25  = 0x00050000U, /* 6.25% window */
  WD_WINSIZE_3_125 = 0x0000000AU  /* 3.125% window */
};
```

With a window size of 50% on a 1ms watchdog, there must be at least 0.5ms between pets. Attempting to service the watchdog too quickly will trigger a reset.

### Watchdog Status Flags

The watchdog timer provides status flags to identify various fault conditions:

```c
typedef enum {
  WD_STATUS_DWD_ST           = 1U, /* Digital Watchdog Status */
  WD_STATUS_KEY_ST           = 2U, /* Key Sequence Status */
  WD_STATUS_START_TIME_VIOL  = 3U, /* Start Time Violation */
  WD_STATUS_END_TIME_VIOL    = 4U, /* End Time Violation */
  WD_STATUS_DWWD_ST          = 5U  /* Digital Windowed Watchdog Status */
} wdStatus_t;
```

### Initialization Sequence

The watchdog requires initialization with a specific sequence that configures the timeout period and window size, followed by enabling the watchdog and regular servicing to prevent system reset.

### Timeout Period Calculation

The timeout period is specified in seconds during initialization. The function automatically calculates the appropriate counter values based on the system clock.

If the requested timeout period would require a prescalar value greater than 4095 (the maximum 12-bit value), the system will:
1. Use the maximum prescalar value (4095)
2. Indicate the limitation
3. The watchdog will still be operational, but with a shorter timeout than requested

### Clock Source

The watchdog timer uses the RTI (Real-Time Interrupt) module's clock source, which is derived from the system clock.

## VIM (Vectored Interrupt Manager)

The Vectored Interrupt Manager (VIM) provides a central interface for managing hardware interrupts in the RM46 microcontroller.

### VIM Register Structure (0xFFFFFE00)

```c
typedef volatile struct vimBASE_s {
  uint32_t IRQINDEX;      /* 0x0000 - IRQ Index Register */
  uint32_t FIQINDEX;      /* 0x0004 - FIQ Index Register */
  uint32_t rsvd1;         /* 0x0008 - Reserved */
  uint32_t rsvd2;         /* 0x000C - Reserved */
  uint32_t FIRQPR0;       /* 0x0010 - FIQ/IRQ Priority Register 0 */
  uint32_t FIRQPR1;       /* 0x0014 - FIQ/IRQ Priority Register 1 */
  uint32_t FIRQPR2;       /* 0x0018 - FIQ/IRQ Priority Register 2 */
  uint32_t FIRQPR3;       /* 0x001C - FIQ/IRQ Priority Register 3 */
  uint32_t INTREQ0;       /* 0x0020 - Interrupt Request Register 0 */
  uint32_t INTREQ1;       /* 0x0024 - Interrupt Request Register 1 */
  uint32_t INTREQ2;       /* 0x0028 - Interrupt Request Register 2 */
  uint32_t INTREQ3;       /* 0x002C - Interrupt Request Register 3 */
  uint32_t REQMASKSET0;   /* 0x0030 - Request Mask Set Register 0 */
  uint32_t REQMASKSET1;   /* 0x0034 - Request Mask Set Register 1 */
  uint32_t REQMASKSET2;   /* 0x0038 - Request Mask Set Register 2 */
  uint32_t REQMASKSET3;   /* 0x003C - Request Mask Set Register 3 */
  uint32_t REQMASKCLR0;   /* 0x0040 - Request Mask Clear Register 0 */
  uint32_t REQMASKCLR1;   /* 0x0044 - Request Mask Clear Register 1 */
  uint32_t REQMASKCLR2;   /* 0x0048 - Request Mask Clear Register 2 */
  uint32_t REQMASKCLR3;   /* 0x004C - Request Mask Clear Register 3 */
  uint32_t WAKEMASKSET0;  /* 0x0050 - Wake-up Mask Set Register 0 */
  uint32_t WAKEMASKSET1;  /* 0x0054 - Wake-up Mask Set Register 1 */
  uint32_t WAKEMASKSET2;  /* 0x0058 - Wake-up Mask Set Register 2 */
  uint32_t WAKEMASKSET3;  /* 0x005C - Wake-up Mask Set Register 3 */
  uint32_t WAKEMASKCLR0;  /* 0x0060 - Wake-up Mask Clear Register 0 */
  uint32_t WAKEMASKCLR1;  /* 0x0064 - Wake-up Mask Clear Register 1 */
  uint32_t WAKEMASKCLR2;  /* 0x0068 - Wake-up Mask Clear Register 2 */
  uint32_t WAKEMASKCLR3;  /* 0x006C - Wake-up Mask Clear Register 3 */
  uint32_t IRQVECREG;     /* 0x0070 - IRQ Vector Register */
  uint32_t FIQVECREG;     /* 0x0074 - FIQ Vector Register */
  uint32_t CAPEVT;        /* 0x0078 - Capture Event Register */
  uint32_t rsvd3;         /* 0x007C - Reserved */
  uint32_t CHANCTRL[32U]; /* 0x0080-0x0FC - Channel Control Registers */
} vimBASE_t;
```

### VIM Register Descriptions

| Register Group | Address Range | Description |
|----------------|---------------|-------------|
| IRQINDEX       | 0xFFFFFE00   | Contains index of highest priority pending IRQ interrupt |
| FIQINDEX       | 0xFFFFFE04   | Contains index of highest priority pending FIQ interrupt |
| FIRQPR0-3      | 0xFFFFFE10-1C| Configure interrupts as FIQ (1) or IRQ (0) |
| INTREQ0-3      | 0xFFFFFE20-2C| Show which interrupts are currently active (read-only) |
| REQMASKSET0-3  | 0xFFFFFE30-3C| Enable specific interrupts (write 1 to enable) |
| REQMASKCLR0-3  | 0xFFFFFE40-4C| Disable specific interrupts (write 1 to disable) |
| WAKEMASKSET0-3 | 0xFFFFFE50-5C| Enable wake-up capability for interrupts |
| WAKEMASKCLR0-3 | 0xFFFFFE60-6C| Disable wake-up capability for interrupts |
| IRQVECREG      | 0xFFFFFE70   | Contains vector address of highest priority IRQ |
| FIQVECREG      | 0xFFFFFE74   | Contains vector address of highest priority FIQ |
| CHANCTRL[32]   | 0xFFFFFE80-FC| Individual control registers for each channel |

### Interrupt Sources

The RM46 supports up to 128 interrupt sources (channels 0-127) that can be configured as either:
- **FIQ (Fast Interrupt)**: Highest priority, minimal latency
- **IRQ (Regular Interrupt)**: Normal priority

Some key interrupt sources include:
- RTI (Real-Time Interrupt)
- ADC conversion completion
- CAN message reception/transmission
- DMA transfer completion
- GPIO edge triggers
- SPI transfer completion

### Interrupt Vector Table Structure

The VIM manages an interrupt vector table where each entry corresponds to a specific interrupt source. The vector table contains:

1. **Vector addresses**: Memory addresses of the interrupt service routines
2. **Priority levels**: Determines which interrupts take precedence
3. **Interrupt type**: IRQ (normal priority) or FIQ (fast interrupt)

### Register Functionality

1. **IRQINDEX/FIQINDEX Registers**:
   - Indicate the highest priority pending IRQ/FIQ interrupt

2. **FIRQPR Registers**:
   - Configure interrupts as either FIQ (high priority) or IRQ (normal priority)
   - Each bit controls one interrupt channel

3. **INTREQ Registers**:
   - Show which interrupts are currently active/pending
   - Read-only status registers

4. **REQMASKSET/REQMASKCLR Registers**:
   - Enable (SET) or disable (CLR) specific interrupts
   - Writing a 1 to a bit position in SET enables the interrupt
   - Writing a 1 to a bit position in CLR disables the interrupt

5. **WAKEMASKSET/WAKEMASKCLR Registers**:
   - Configure which interrupts can wake the processor from low-power modes
   - Similar operation to REQMASK registers

6. **IRQVECREG/FIQVECREG Registers**:
   - Contain the vector address of the highest priority pending IRQ/FIQ

7. **CHANCTRL Registers**:
   - Individual control registers for each interrupt channel
   - Configure interrupt-specific parameters

### Interrupt Handling Procedure

1. **Initialization**:
   - Configure interrupt vectors in the vector table
   - Set interrupt priorities
   - Configure interrupts as IRQ or FIQ
   - Enable desired interrupts

2. **When an Interrupt Occurs**:
   - CPU automatically jumps to either the IRQ or FIQ handler
   - The appropriate channel is identified and handled
   - After handling, the interrupt status is cleared

3. **Enabling/Disabling Interrupts**:
   - Specific registers control the enabling and disabling of interrupts

### Interrupt Priority Control

Interrupt priority is determined by:
1. **FIQ vs. IRQ**: FIQ interrupts always have higher priority than IRQ interrupts
2. **Channel number**: Lower channel numbers have higher priority
3. **Masking**: Masked interrupts are not serviced, regardless of priority

The VIM automatically selects the highest priority pending interrupt for service.

## Clock Management

The RM46 microcontroller features a comprehensive clock management system that provides flexible clock generation and distribution to various peripheral modules.

### Clock Sources

The primary clock sources available in the RM46 include:
- **PLL (Phase-Locked Loop)**: Generates high-frequency system clocks
- **Low-Power Oscillator (LPO)**: Low-frequency oscillator for low-power operation
- **External Clock (ECLK)**: External clock input
- **Oscillator**: Internal oscillator

### PLL Configuration Registers

The PLL configuration is managed through the System Module registers:

```c
// Primary System Control Registers (0xFFFFFF00)
struct systemBASE1_s {
  uint32_t SYSPC1;      /* 0x0000 - System Pin Control 1 Register */
  uint32_t SYSPC2;      /* 0x0004 - System Pin Control 2 Register */
  uint32_t SYSPC3;      /* 0x0008 - System Pin Control 3 Register */
  uint32_t SYSPC4;      /* 0x000C - System Pin Control 4 Register */
  uint32_t SYSPC5;      /* 0x0010 - System Pin Control 5 Register */
  uint32_t SYSPC6;      /* 0x0014 - System Pin Control 6 Register */
  uint32_t SYSPC7;      /* 0x0018 - System Pin Control 7 Register */
  uint32_t SYSPC8;      /* 0x001C - System Pin Control 8 Register */
  uint32_t SYSPC9;      /* 0x0020 - System Pin Control 9 Register */
  uint32_t SSWPLL1;     /* 0x0024 - Software Controlled PLL Register 1 */
  uint32_t SSWPLL2;     /* 0x0028 - Software Controlled PLL Register 2 */
  uint32_t SSWPLL3;     /* 0x002C - Software Controlled PLL Register 3 */
  uint32_t CSDIS;       /* 0x0030 - Clock Source Disable Register */
  uint32_t CSDISSET;    /* 0x0034 - Clock Source Disable Set Register */
  uint32_t CSDISCLR;    /* 0x0038 - Clock Source Disable Clear Register */
  uint32_t CDDIS;       /* 0x003C - Clock Domain Disable Register */
  uint32_t CDDISSET;    /* 0x0040 - Clock Domain Disable Set Register */
  uint32_t CDDISCLR;    /* 0x0044 - Clock Domain Disable Clear Register */
  uint32_t GHVSRC;      /* 0x0048 - GCLK, HCLK, VCLK Source Register */
  uint32_t VCLKASRC;    /* 0x004C - VCLKA Source Register */
  uint32_t RCLKSRC;     /* 0x0050 - RTI Clock Source Register */
  uint32_t CSVSTAT;     /* 0x0054 - Clock Source Valid Status Register */
  uint32_t MSTGCR;      /* 0x0058 - Master Clock Global Control Register */
  uint32_t MINITGCR;    /* 0x005C - Mini-Clock Global Control Register */
  uint32_t MSINENA;     /* 0x0060 - Memory Self-Init Enable Register */
  uint32_t MSTFAIL;     /* 0x0064 - Master Self-Test Fail Register */
  uint32_t MSTCGSTAT;   /* 0x0068 - Master Clock Global Status Register */
  uint32_t MINISTAT;    /* 0x006C - Mini-Clock Status Register */
  uint32_t PLLCTL1;     /* 0x0070 - PLL Control Register 1 */
  uint32_t PLLCTL2;     /* 0x0074 - PLL Control Register 2 */
  uint32_t UERFLAG;     /* 0x0078 - Uncorrectable Error Flag Register */
  uint32_t DIEIDL;      /* 0x007C - Device ID Low Register */
  uint32_t DIEIDH;      /* 0x0080 - Device ID High Register */
  uint32_t VRCTL;       /* 0x0084 - Voltage Regulator Control Register */
  uint32_t LPOMONCTL;   /* 0x0088 - LPO Monitor Control Register */
  uint32_t CLKTEST;     /* 0x008C - Clock Test Register */
  uint32_t DFTCTRLREG1; /* 0x0090 - DFT Control Register 1 */
  uint32_t DFTCTRLREG2; /* 0x0094 - DFT Control Register 2 */
  uint32_t rsvd1[2];    /* 0x0098 - Reserved */
  uint32_t GPREG1;      /* 0x00A0 - General Purpose Register 1 */
  uint32_t BTRMSEL;     /* 0x00A4 - Boot ROM Selection Register */
  uint32_t IMPFASTS;    /* 0x00A8 - Imprecise Fault Status Register */
  uint32_t IMPFTADD;    /* 0x00AC - Imprecise Fault Address Register */
  uint32_t SSIR1;       /* 0x00B0 - System Software Interrupt Request 1 */
  uint32_t SSIR2;       /* 0x00B4 - System Software Interrupt Request 2 */
  uint32_t SSIR3;       /* 0x00B8 - System Software Interrupt Request 3 */
  uint32_t SSIR4;       /* 0x00BC - System Software Interrupt Request 4 */
  uint32_t RAMGCR;      /* 0x00C0 - RAM Global Control Register */
  uint32_t BMMCR1;      /* 0x00C4 - Backup Memory Map Config Register 1 */
  uint32_t BMMCR2;      /* 0x00C8 - Backup Memory Map Config Register 2 */
  uint32_t CPURSTCR;    /* 0x00CC - CPU Reset Control Register */
  uint32_t CLKCNTL;     /* 0x00D0 - Clock Control Register */
  uint32_t ECPCNTL;     /* 0x00D4 - ECP Control Register */
  uint32_t rsvd2;       /* 0x00D8 - Reserved */
  uint32_t DEVCR1;      /* 0x00DC - Device Control Register 1 */
  uint32_t SYSECR;      /* 0x00E0 - System Exception Control Register */
  uint32_t SYSESR;      /* 0x00E4 - System Exception Status Register */
  uint32_t SYSTASR;     /* 0x00E8 - System Technical Advisory Status Register */
  uint32_t GBLSTAT;     /* 0x00EC - Global Status Register */
  uint32_t DEV;         /* 0x00F0 - Device Identification Register */
  uint32_t SSIVEC;      /* 0x00F4 - SSI Vector Register */
  uint32_t SSIF;        /* 0x00F8 - SSI Flag Register */
};

// Secondary System Control Registers (0xFFFFE100)
struct systemBASE2_s {
  uint32_t PLLCTL3;     /* 0x0000 - PLL Control Register 3 */
  uint32_t rsvd1;       /* 0x0004 - Reserved */
  uint32_t STCCLKDIV;   /* 0x0008 - STC Clock Divider Register */
  uint32_t rsvd2[6];    /* 0x000C-0x0020 - Reserved */
  uint32_t ECPCNTRL0;   /* 0x0024 - ECP Control Register 0 */
  uint32_t rsvd3[5];    /* 0x0028-0x0038 - Reserved */
  uint32_t CLK2CNTL;    /* 0x003C - CLK2 Control Register */
  uint32_t VCLKACON1;   /* 0x0040 - VCLKA Control Register 1 */
  uint32_t rsvd4[11];   /* 0x0044-0x006C - Reserved */
  uint32_t CLKSLIP;     /* 0x0070 - Clock Slip Register */
  uint32_t rsvd5[30];   /* 0x0074-0x00E8 - Reserved */
  uint32_t EFC_CTLEN;   /* 0x00EC - EFC Control Enable Register */
  uint32_t DIEIDL_REG0; /* 0x00F0 - Die ID Register 0 (Low) */
  uint32_t DIEIDH_REG1; /* 0x00F4 - Die ID Register 1 (High) */
  uint32_t DIEIDL_REG2; /* 0x00F8 - Die ID Register 2 (Low) */
  uint32_t DIEIDH_REG3; /* 0x00FC - Die ID Register 3 (High) */
};
```

### Clock Domain Control

The RM46 provides registers to control different clock domains and their sources:

```c
// Clock Control Register Bit Definitions
// CSDIS (Clock Source Disable) Register - 0x0030
#define SYS_CSDIS_CLKSR           (1U << 0U)  /* OSC clock source disable */
#define SYS_CSDIS_CLKSRL          (1U << 1U)  /* HFLPO clock source disable */
#define SYS_CSDIS_CLKSEL          (1U << 3U)  /* 32 KHz Oscillator disable */
#define SYS_CSDIS_PLLOFF          (1U << 8U)  /* PLL disable */

// CDDIS (Clock Domain Disable) Register - 0x003C
#define SYS_CDDIS_GCLK            (1U << 0U)  /* GCLK domain disable */
#define SYS_CDDIS_HCLK            (1U << 1U)  /* HCLK domain disable */
#define SYS_CDDIS_VCLK            (1U << 2U)  /* VCLK domain disable */
#define SYS_CDDIS_VCLKA           (1U << 3U)  /* VCLKA domain disable */
#define SYS_CDDIS_AVCLK1          (1U << 4U)  /* AVCLK1 domain disable */
#define SYS_CDDIS_AVCLK2          (1U << 5U)  /* AVCLK2 domain disable */
#define SYS_CDDIS_AVCLK3          (1U << 10U) /* AVCLK3 domain disable */
#define SYS_CDDIS_AVCLK4          (1U << 11U) /* AVCLK4 domain disable */

// GHVSRC (GCLK, HCLK, VCLK Source) Register - 0x0048
#define SYS_GHVSRC_GHVSRC_PLL1    (0U << 0U)  /* PLL1 is the source for all */
#define SYS_GHVSRC_HVLSRC_PLL1    (0U << 16U) /* PLL1 is the source for HCLK, VCLK */
#define SYS_GHVSRC_HVLSRC_LPO     (1U << 16U) /* LPO is the source for HCLK, VCLK */
#define SYS_GHVSRC_HVLSRC_OSC     (3U << 16U) /* OSC is the source for HCLK, VCLK */
```

#### Clock Source Control

The CSDIS register allows individual clock sources to be disabled to save power:
- OSC (Oscillator): Main system oscillator
- HFLPO (High-Frequency Low-Power Oscillator): Secondary oscillator
- LFLO (Low-Frequency Low-Power Oscillator): 32KHz oscillator
- PLL1/2: Phase-Locked Loops that provide clock multiplication

#### Clock Domain Control

The CDDIS register enables/disables individual clock domains:
- GCLK: Global Clock (200 MHz)
- HCLK: High-Speed Clock (200 MHz)
- VCLK: Peripheral Clock (100 MHz)
- VCLKA: Asynchronous Clock for peripherals
- AVCLKx: Additional asynchronous clocks for specific peripherals

#### Clock Source Selection

The GHVSRC register controls the source selection for the major clock domains:
- GCLK source: PLL1 by default
- HCLK/VCLK source: Can be configured to use PLL1, LPO, or OSC

#### Clock Validation

The CSVSTAT register provides status information about the availability and stability of clock sources:
- Bit 0: OSC clock source valid
- Bit 1: HFLPO clock source valid
- Bit 3: 32 KHz Oscillator valid
- Bit 8: PLL1 valid

### Clock Division and Selection

The system provides multiple registers for clock division and source selection:

```c
// Clock Division Register Bit Definitions
// STCCLKDIV Register (0xFFFFE108)
#define SYS_STCCLKDIV_CLKDIV_MASK     0xFFU
#define SYS_STCCLKDIV_CLKDIV(x)       ((x) & 0xFFU)  /* Divider value (1-256) */

// CLK2CNTL Register (0xFFFFE13C)
#define SYS_CLK2CNTL_CLK2EN           (1U << 0U)     /* CLK2 enable */
#define SYS_CLK2CNTL_CLK2DIV_MASK     0x1FE0U
#define SYS_CLK2CNTL_CLK2DIV(x)       (((x) << 5U) & 0x1FE0U) /* Divider value */

// VCLKACON1 Register (0xFFFFE140)
#define SYS_VCLKACON1_VCLKA1S_OSC     (0U << 0U)     /* VCLKA source: OSC */
#define SYS_VCLKACON1_VCLKA1S_PLL1    (1U << 0U)     /* VCLKA source: PLL1 */
#define SYS_VCLKACON1_VCLKA1S_LPO     (2U << 0U)     /* VCLKA source: LPO */
#define SYS_VCLKACON1_VCLKA1R_MASK    0x1F00U
#define SYS_VCLKACON1_VCLKA1R(x)      (((x) << 8U) & 0x1F00U) /* Divider value */

// CLKSLIP Register (0xFFFFE170)
#define SYS_CLKSLIP_KEY_MASK          0xFFFF0000U
#define SYS_CLKSLIP_KEY(x)            (((x) << 16U) & 0xFFFF0000U)  /* Access key */
#define SYS_CLKSLIP_CLKSR             (1U << 0U)     /* Slip OSC clock */
```

#### Clock Division Control

The system provides various clock dividers to derive slower clock frequencies from the main sources:

1. **STC Clock Divider (STCCLKDIV)**:
   - Divides the system clock for the Self-Test Controller
   - 8-bit divider: Divide by 1 to 256

2. **CLK2 Control (CLK2CNTL)**:
   - Controls the CLK2 output
   - Enables/disables CLK2
   - 8-bit divider for clock frequency adjustment

3. **VCLKA Control (VCLKACON1)**:
   - Selects the source for VCLKA (OSC, PLL1, or LPO)
   - Divides the source by a programmable factor (1-32)

4. **Clock Slip Control (CLKSLIP)**:
   - Allows adjustment of clock phase for specific peripherals
   - Protected by a key value to prevent accidental modification

### Clock Setup Functions

The BSP provides functions for setting up and configuring the clock system:

1. **PLL Setup**:
   - Initializes the PLL to generate the system clock
   - Configures PLL parameters like multiplier and divider values

2. **Clock Domain Mapping**:
   - Maps peripheral clock domains to appropriate clock sources
   - Waits for PLLs to stabilize before switching clock sources

3. **LPO Calibration**:
   - Calibrates the Low Power Oscillator to achieve precise frequency

### Clock Gating Control

The RM46 allows selective enabling/disabling of clocks to individual peripherals, which helps in power management:

- **CSDIS/CSDISSET/CSDISCLR**: Control overall clock sources
- **CDDIS/CDDISSET/CDDISCLR**: Control individual clock domains

### Clock Stability Detection

The CSVSTAT register provides status information about clock source stability and validity. This allows software to ensure that a clock is stable before switching to it as a source.

## Peripheral-Specific Information

### Multi-Buffered Serial Peripheral Interface (MibSPI)

The RM46 features a Multi-Buffered SPI interface (MibSPI) that supports high-speed serial communication.

#### MibSPI Register Structure
```c
typedef volatile struct mibspiBase {
  uint32_t  GCR0;            /* 0x0000 - Global Control Register 0 */
  uint32_t  GCR1;            /* 0x0004 - Global Control Register 1 */
  uint32_t  INT0;            /* 0x0008 - Interrupt Register */
  uint32_t  LVL;             /* 0x000C - Interrupt Level Register */
  uint32_t  FLG;             /* 0x0010 - Interrupt Flag Register */
  uint32_t  PC0;             /* 0x0014 - Pin Control Register 0 */
  uint32_t  PC1;             /* 0x0018 - Pin Control Register 1 */
  uint32_t  PC2;             /* 0x001C - Pin Control Register 2 */
  uint32_t  PC3;             /* 0x0020 - Pin Control Register 3 */
  uint32_t  PC4;             /* 0x0024 - Pin Control Register 4 */
  uint32_t  PC5;             /* 0x0028 - Pin Control Register 5 */
  uint32_t  PC6;             /* 0x002C - Pin Control Register 6 */
  uint32_t  PC7;             /* 0x0030 - Pin Control Register 7 */
  uint32_t  PC8;             /* 0x0034 - Pin Control Register 8 */
  uint32_t  DAT0;            /* 0x0038 - Data Register 0 */
  uint32_t  DAT1;            /* 0x003C - Data Register 1 */
  uint32_t  BUF;             /* 0x0040 - Buffer Register */
  uint32_t  EMU;             /* 0x0044 - Emulation Register */
  uint32_t  DELAY;           /* 0x0048 - Delay Register */
  uint32_t  DEF;             /* 0x004C - Default Chip Select Register */
  uint32_t  FMT0;            /* 0x0050 - Format Register 0 */
  uint32_t  FMT1;            /* 0x0054 - Format Register 1 */
  uint32_t  FMT2;            /* 0x0058 - Format Register 2 */
  uint32_t  FMT3;            /* 0x005C - Format Register 3 */
  uint32_t  INTVECT0;        /* 0x0060 - Interrupt Vector Register 0 */
  uint32_t  INTVECT1;        /* 0x0064 - Interrupt Vector Register 1 */
  uint32_t  SRSEL;           /* 0x0068 - Slew Rate Select Register */
  uint32_t  PMCTRL;          /* 0x006C - Parallel Mode Control Register */
  uint32_t  MIBSPIE;         /* 0x0070 - MibSPI Enable Register */
  uint32_t  TGITENST;        /* 0x0074 - Transfer Group Interrupt Enable Set Register */
  uint32_t  TGITENCR;        /* 0x0078 - Transfer Group Interrupt Enable Clear Register */
  uint32_t  TGITLVST;        /* 0x007C - Transfer Group Interrupt Level Set Register */
  uint32_t  TGITLVCR;        /* 0x0080 - Transfer Group Interrupt Level Clear Register */
  uint32_t  TGINTFLG;        /* 0x0084 - Transfer Group Interrupt Flag Register */
  uint32_t  rsvd1[2U];       /* 0x0088 - Reserved */
  uint32_t  TICKCNT;         /* 0x0090 - Tick Counter */
  uint32_t  LTGPEND;         /* 0x0090 - Last Transfer Group End Pointer Register */
  uint32_t  TGCTRL[16U];     /* 0x0098-0x00D4 - Transfer Group Control Registers */
  uint32_t  DMACTRL[8U];     /* 0x00D8-0x00F4 - DMA Control Registers */
  uint32_t  DMACOUNT[8U];    /* 0x00F8-0x0114 - DMA Count Registers */
  uint32_t  DMACNTLEN;       /* 0x0118-0x0114 - DMA Control Length Register */
  uint32_t  rsvd2;           /* 0x011C - Reserved */
  uint32_t  UERRCTRL;        /* 0x0120 - Error Control Register */
  uint32_t  UERRSTAT;        /* 0x0124 - Error Status Register */
  uint32_t  UERRADDRRX;      /* 0x0128 - Error Address Register (RX) */
  uint32_t  UERRADDRTX;      /* 0x012C - Error Address Register (TX) */
  uint32_t  RXOVRN_BUF_ADDR; /* 0x0130 - RX Overrun Buffer Address Register */
  uint32_t  IOLPKTSTCR;      /* 0x0134 - IO Loop Back Test Control Register */
  uint32_t  EXT_PRESCALE1;   /* 0x0138 - External Prescale Register 1 */
  uint32_t  EXT_PRESCALE2;   /* 0x013C - External Prescale Register 2 */
} mibspiBASE_t;
```

#### MibSPI Instances
The RM46 includes multiple MibSPI modules:
- MibSPI1: Base Address 0xFFF7F400
- MibSPI3: Base Address 0xFFF7F800
- MibSPI5: Base Address 0xFFF7FC00

#### MibSPI Data RAM
Each MibSPI module has its own dedicated RAM for TX and RX buffers:
- MibSPI1 RAM: 0xFF0E0000
- MibSPI3 RAM: 0xFF0C0000
- MibSPI5 RAM: 0xFF0A0000

The RAM structure supports up to 128 transfers:
```c
typedef volatile struct mibspiRamBase {
  struct {
    uint16_t data;
    uint16_t control;
  } tx[128];
  struct {
    uint16_t data;
    uint16_t flags;
  } rx[128];
} mibspiRAM_t;
```

### Controller Area Network (CAN)

The RM46 includes Controller Area Network (CAN) interfaces for robust communication in automotive and industrial environments.

#### CAN Register Structure
```c
typedef volatile struct canBase {
  uint32_t CTL;         /* 0x0000 - Control Register */
  uint32_t ES;          /* 0x0004 - Error Status Register */
  uint32_t EERC;        /* 0x0008 - Error Counter Register */
  uint32_t BTR;         /* 0x000C - Bit Timing Register */
  uint32_t INT;         /* 0x0010 - Interrupt Register */
  uint32_t TEST;        /* 0x0014 - Test Register */
  uint32_t rsvd1;       /* 0x0018 - Reserved */
  uint32_t PERR;        /* 0x001C - Parity Error Register */
  uint32_t rsvd2[24];   /* 0x002C-0x007C - Reserved */
  uint32_t ABOTR;       /* 0x0080 - Auto-Bus-On Time Register */
  uint32_t TXRQX;       /* 0x0084 - Transmission Request X Register */
  uint32_t TXRQx[4U];   /* 0x0088-0x0094 - Transmission Request Registers */
  uint32_t NWDATX;      /* 0x0098 - New Data X Register */
  uint32_t NWDATx[4U];  /* 0x009C-0x00A8 - New Data Registers */
  uint32_t INTPNDX;     /* 0x00AC - Interrupt Pending X Register */
  uint32_t INTPNDx[4U]; /* 0x00B0-0x00BC - Interrupt Pending Registers */
  uint32_t MSGVALX;     /* 0x00C0 - Message Valid X Register */
  uint32_t MSGVALx[4U]; /* 0x00C4-0x00D0 - Message Valid Registers */
  uint32_t rsvd3;       /* 0x00D4 - Reserved */
  uint32_t INTMUXx[4U]; /* 0x00D8-0x00E4 - Interrupt Multiplexer Registers */
  uint32_t rsvd4[6];    /* 0x00E8 - Reserved */
  // Interface registers for message objects
  uint8_t  IF1NO;       /* 0x0100 - Interface 1 Command Register: Message Number */
  uint8_t  IF1STAT;     /* 0x0100 - Interface 1 Command Register: Status */
  uint8_t  IF1CMD;      /* 0x0100 - Interface 1 Command Register: Command */
  uint8_t  rsvd9;       /* 0x0100 - Reserved */
  uint32_t IF1MSK;      /* 0x0104 - Interface 1 Mask Register */
  uint32_t IF1ARB;      /* 0x0108 - Interface 1 Arbitration Register */
  uint32_t IF1MCTL;     /* 0x010C - Interface 1 Message Control Register */
  uint8_t  IF1DATx[8U]; /* 0x0110-0x0114 - Interface 1 Data Registers */
  uint32_t rsvd5[2];    /* 0x0118 - Reserved */
  // Interface 2 registers (similar to Interface 1)
  uint8_t  IF2NO;       /* 0x0120 */
  uint8_t  IF2STAT;     /* 0x0120 */
  uint8_t  IF2CMD;      /* 0x0120 */
  uint8_t  rsvd10;      /* 0x0120 */
  uint32_t IF2MSK;      /* 0x0124 */
  uint32_t IF2ARB;      /* 0x0128 */
  uint32_t IF2MCTL;     /* 0x012C */
  uint8_t  IF2DATx[8U]; /* 0x0130-0x0134 */
  uint32_t rsvd6[2];    /* 0x0138 */
  // Interface 3 registers
  uint32_t IF3OBS;      /* 0x0140 - Interface 3 Observation Register */
  uint32_t IF3MSK;      /* 0x0144 - Interface 3 Mask Register */
  uint32_t IF3ARB;      /* 0x0148 - Interface 3 Arbitration Register */
  uint32_t IF3MCTL;     /* 0x014C - Interface 3 Message Control Register */
  uint8_t  IF3DATx[8U]; /* 0x0150-0x0154 - Interface 3 Data Registers */
  uint32_t rsvd7[2];    /* 0x0158 - Reserved */
  uint32_t IF3UEy[4U];  /* 0x0160-0x016C - Interface 3 Update Enable Registers */
  uint32_t rsvd8[28];   /* 0x0170 - Reserved */
  uint32_t TIOC;        /* 0x01E0 - TX IO Control Register */
  uint32_t RIOC;        /* 0x01E4 - RX IO Control Register */
} canBASE_t;
```

#### CAN Instances
The RM46 includes three CAN modules:
- CAN1: Base Address 0xFFF7DC00
- CAN2: Base Address 0xFFF7DE00
- CAN3: Base Address 0xFFF7E000

Each CAN module has its own message RAM:
- CAN1 RAM: 0xFF1E0000
- CAN2 RAM: 0xFF1C0000
- CAN3 RAM: 0xFF1A0000

### Analog-to-Digital Converter (ADC)

The RM46 includes two ADC modules for converting analog signals to digital values.

#### ADC Register Structure
```c
typedef volatile struct adcBase {
  uint32_t RSTCR;              /* 0x0000 - Reset Control Register */
  uint32_t OPMODECR;           /* 0x0004 - Operating Mode Control Register */
  uint32_t CLOCKCR;            /* 0x0008 - Clock Control Register */
  uint32_t CALCR;              /* 0x000C - Calibration Control Register */
  uint32_t GxMODECR[3U];       /* 0x0010,0x0014,0x0018 - Group Mode Control Registers */
  uint32_t EVSRC;              /* 0x001C - Event Source Register */
  uint32_t G1SRC;              /* 0x0020 - Group 1 Source Register */
  uint32_t G2SRC;              /* 0x0024 - Group 2 Source Register */
  uint32_t GxINTENA[3U];       /* 0x0028,0x002C,0x0030 - Group Interrupt Enable Registers */
  uint32_t GxINTFLG[3U];       /* 0x0034,0x0038,0x003C - Group Interrupt Flag Registers */
  uint32_t GxINTCR[3U];        /* 0x0040-0x0048 - Group Interrupt Control Registers */
  uint32_t EVDMACR;            /* 0x004C - Event DMA Control Register */
  uint32_t G1DMACR;            /* 0x0050 - Group 1 DMA Control Register */
  uint32_t G2DMACR;            /* 0x0054 - Group 2 DMA Control Register */
  uint32_t BNDCR;              /* 0x0058 - Buffer Boundary Control Register */
  uint32_t BNDEND;             /* 0x005C - Buffer Boundary End Register */
  uint32_t G1SRC2;             /* 0x0060 - Group 1 Extended Source Register */
  uint32_t G2SRC2;             /* 0x0064 - Group 2 Extended Source Register */
  uint32_t EVINTCR;            /* 0x0068 - Event Interrupt Control Register */
  uint32_t EVDMAINST;          /* 0x006C - Event DMA Instant Register */
  uint32_t G1DMAIST;           /* 0x0070 - Group 1 DMA Instant Register */
  uint32_t G2DMAIST;           /* 0x0074 - Group 2 DMA Instant Register */
  uint32_t PARACTL;            /* 0x0078 - Parity Control Register */
  uint32_t PARAESR;            /* 0x007C - Parity Error Status Register */
  uint32_t GPARCTL;            /* 0x0080 - G0 Parity Control Register */
  uint32_t G1PARCTL;           /* 0x0084 - G1 Parity Control Register */
  uint32_t G2PARCTL;           /* 0x0088 - G2 Parity Control Register */
  uint32_t RESADDR0;           /* 0x008C - Result Address Register 0 */
  uint32_t RESADDR1;           /* 0x0090 - Result Address Register 1 */
  uint32_t EVTDIR;             /* 0x0094 - Event Direction Register */
  uint32_t FTUCTL;             /* 0x0098 - FTU Control Register */
  uint32_t FTUSTATUS;          /* 0x009C - FTU Status Register */
  uint32_t COMPCR;             /* 0x00A0 - Compare Control Register */
  uint32_t COMPHIREF;          /* 0x00A4 - High Compare Reference Register */
  uint32_t COMPLOREF;          /* 0x00A8 - Low Compare Reference Register */
  uint32_t COMPSTATUS;         /* 0x00AC - Compare Status Register */
  uint32_t rsvd1[20];          /* 0x00B0-0x00FC - Reserved */
  struct {
    uint32_t BUF0;             /* Buffer 0 Register */
    uint32_t BUF1;             /* Buffer 1 Register */
    uint32_t BUF2;             /* Buffer 2 Register */
    uint32_t BUF3;             /* Buffer 3 Register */
    uint32_t BUF4;             /* Buffer 4 Register */
    uint32_t BUF5;             /* Buffer 5 Register */
    uint32_t BUF6;             /* Buffer 6 Register */
    uint32_t BUF7;             /* Buffer 7 Register */
    uint32_t BUF8;             /* Buffer 8 Register */
    uint32_t BUF9;             /* Buffer 9 Register */
    uint32_t BUF10;            /* Buffer 10 Register */
    uint32_t BUF11;            /* Buffer 11 Register */
    uint32_t BUF12;            /* Buffer 12 Register */
    uint32_t BUF13;            /* Buffer 13 Register */
    uint32_t BUF14;            /* Buffer 14 Register */
    uint32_t BUF15;            /* Buffer 15 Register */
  } GxBUF[3U];                 /* Group Buffer Registers */
  struct {
    uint32_t COMP0;            /* Compare 0 Register */
    uint32_t COMP1;            /* Compare 1 Register */
    uint32_t COMP2;            /* Compare 2 Register */
    uint32_t COMP3;            /* Compare 3 Register */
    uint32_t COMP4;            /* Compare 4 Register */
    uint32_t COMP5;            /* Compare 5 Register */
    uint32_t COMP6;            /* Compare 6 Register */
    uint32_t COMP7;            /* Compare 7 Register */
  } GxCOMP[3U];                /* Group Compare Registers */
  uint32_t BOUNDADDR;          /* Boundary Address Register */
  uint32_t rsvd2[13];          /* Reserved */
  struct {
    uint32_t CTL;              /* Channel Control Register */
    uint32_t OFFSET;           /* Channel Offset Register */
    uint32_t TRIPLO;           /* Channel Trip Low Register */
    uint32_t TRIPHI;           /* Channel Trip High Register */
  } RCHAN[1U];                 /* Range Checking Channel Registers */
} adcBASE_t;
```

#### ADC Control Register Bit Definitions

```c
// Reset Control Register (RSTCR) - 0x0000
#define ADC_RSTCR_ADRESET       (1U << 0U)    /* ADC Reset */
#define ADC_RSTCR_PARARESET     (1U << 1U)    /* Parity Reset */

// Operating Mode Control Register (OPMODECR) - 0x0004
#define ADC_OPMODECR_ADCEN      (1U << 0U)    /* ADC Enable */
#define ADC_OPMODECR_AREFSEL    (1U << 1U)    /* Analog Reference Select */
#define ADC_OPMODECR_ADCALCR    (1U << 2U)    /* ADC Calibration Mode */

// Clock Control Register (CLOCKCR) - 0x0008
#define ADC_CLOCKCR_CLKSEL_MASK 0x00000003U   /* Clock Select Mask */
#define ADC_CLOCKCR_CLKSEL_VCLK (0U << 0U)    /* VCLK is clock source */
#define ADC_CLOCKCR_CLKSEL_PLL1 (1U << 0U)    /* PLL1 is clock source */
```

#### ADC Instances
The RM46 includes two ADC modules:
- ADC1: Base Address 0xFFF7C000, RAM at 0xFF3E0000
- ADC2: Base Address 0xFFF7C200, RAM at 0xFF3A0000

### High-End Timer (HET)

The RM46 includes High-End Timer (HET) modules for precise timing control and pulse generation.

#### HET Register Structure
```c
typedef volatile struct hetBase {
  uint32_t GCR;        /* 0x00 - Global Control Register */
  uint32_t PFR;        /* 0x04 - Prescale Factor Register */
  uint32_t ADDR;       /* 0x08 - Current Address Register */
  uint32_t OFF1;       /* 0x0C - Interrupt Offset Register 1 */
  uint32_t OFF2;       /* 0x10 - Interrupt Offset Register 2 */
  uint32_t INTENAS;    /* 0x14 - Interrupt Enable Set Register */
  uint32_t INTENAC;    /* 0x18 - Interrupt Enable Clear Register */
  uint32_t EXC1;       /* 0x1C - Exception Control Register 1 */
  uint32_t EXC2;       /* 0x20 - Exception Control Register 2 */
  uint32_t PRY;        /* 0x24 - Interrupt Priority Register */
  uint32_t FLG;        /* 0x28 - Interrupt Flag Register */
  uint32_t AND;        /* 0x2C - AND Share Control Register */
  uint32_t rsvd1;      /* 0x30 - Reserved */
  uint32_t HRSH;       /* 0x34 - High Resolution Share Register */
  uint32_t XOR;        /* 0x38 - XOR Share Register */
  uint32_t REQENS;     /* 0x3C - Request Enable Set Register */
  uint32_t REQENC;     /* 0x40 - Request Enable Clear Register */
  uint32_t REQDS;      /* 0x44 - Request Destination Select Register */
  uint32_t DIR;        /* 0x48 - Direction Register */
  uint32_t DIN;        /* 0x4C - Data Input Register */
  uint32_t DOUT;       /* 0x50 - Data Output Register */
  uint32_t DSET;       /* 0x54 - Data Output Set Register */
  uint32_t DCLR;       /* 0x58 - Data Output Clear Register */
  uint32_t PDR;        /* 0x5C - Open Drain Register */
  uint32_t PULDIS;     /* 0x60 - Pull Disable Register */
  uint32_t PSL;        /* 0x64 - Pull Select Register */
  uint32_t PCR;        /* 0x68 - Parity Control Register */
  uint32_t PAR;        /* 0x6C - Parity Address Register */
  uint32_t PPR;        /* 0x70 - Parity Pin Register */
  uint32_t SFPRLD;     /* 0x74 - Suppression Filter Preload Register */
  uint32_t SFENA;      /* 0x78 - Suppression Filter Enable Register */
  uint32_t DISPSEL;    /* 0x7C - Debug Output Select Register */
  uint32_t HRSHCLR;    /* 0x80 - High Resolution Share Clear Register */
  uint32_t XORCLR;     /* 0x84 - XOR Share Clear Register */
  uint32_t REQSRC;     /* 0x88 - Request Source Register */
  uint32_t rsvd2[5];   /* 0x8C-0x9C - Reserved */
  uint32_t PARFLG;     /* 0xA0 - Parity Flag Register */
  uint32_t PARCTL;     /* 0xA4 - Parity Control Register */
  uint32_t ADCNOTIF;   /* 0xA8 - ADC Notification Register */
  uint32_t PCNT;       /* 0xAC - Program Counter Value Register */
  uint32_t SEMA;       /* 0xB0 - Semaphore Register */
  uint32_t rsvd3[4];   /* 0xB4-0xC0 - Reserved */
  uint32_t SCOBR;      /* 0xC4 - Scope Base Register */
  uint32_t SCOID;      /* 0xC8 - Scope Identifier Register */
  uint32_t SCOSTAT;    /* 0xCC - Scope Status Register */
  uint32_t SCOMSK;     /* 0xD0 - Scope Mask Register */
  uint32_t SCOFCN;     /* 0xD4 - Scope Function Register */
  uint32_t SCOBCN;     /* 0xD8 - Scope Buffer Control Register */
  uint32_t SCOBST;     /* 0xDC - Scope Buffer Status Register */
  uint32_t SCOGST;     /* 0xE0 - Scope Global Status Register */
  uint32_t SCOBLK;     /* 0xE4 - Scope Block Register */
  uint32_t rsvd4[6];   /* 0xE8-0xFC - Reserved */

  /* Loop Resolution Timestamp Registers */
  struct {
    uint32_t LTCP;     /* Loop Timer Compare Register */
    uint32_t LTMR;     /* Loop Timer Mode Register */
    uint32_t LTO;      /* Loop Timer Offset Register */
    uint32_t LTCR;     /* Loop Timer Control Register */
    uint32_t LTCNTO;   /* Loop Timer Counter Offset Register */
  } LTS[8];            /* 0x100-0x19C - Loop Timestamp Registers */

  /* High Resolution Timestamp Registers */
  struct {
    uint32_t LTCP;     /* Loop Timer Compare Register */
    uint32_t LTMR;     /* Loop Timer Mode Register */
    uint32_t LTO;      /* Loop Timer Offset Register */
    uint32_t LTCR;     /* Loop Timer Control Register */
  } HTS[16];           /* 0x1A0-0x29C - High Resolution Timestamp Registers */
} hetBASE_t;
```

#### HET Register Bit Definitions

```c
/* GCR (Global Control Register) - 0x00 */
#define HET_GCR_RESET            (1U << 0U)    /* Reset bit */
#define HET_GCR_STOP             (1U << 1U)    /* Stop bit */
#define HET_GCR_SUSPEND          (1U << 2U)    /* Suspend bit */
#define HET_GCR_PPCLR            (1U << 10U)   /* Program pointer clear */
#define HET_GCR_ENHPP            (1U << 15U)   /* Enable high-priority program */
#define HET_GCR_ENHPROGRAM       (1U << 16U)   /* Enable high-priority program */

/* PFR (Prescale Factor Register) - 0x04 */
#define HET_PFR_PFR_MASK         0x00FFU       /* Prescale Factor Mask */
#define HET_PFR_PFR_SHIFT        0U            /* Prescale Factor Shift */
#define HET_PFR_PFR(x)           (((x) << HET_PFR_PFR_SHIFT) & HET_PFR_PFR_MASK)
```

#### HET Instances

The RM46 includes two HET modules with control registers and RAM areas:

- HET1:
  - Registers: Base address at 0xFFF7B800
  - RAM: Base address at 0xFF460000
  - Size: 16KB (4K x 32-bit words)

- HET2:
  - Registers: Base address at 0xFFF7B900
  - RAM: Base address at 0xFF440000
  - Size: 16KB (4K x 32-bit words)

#### HET Operation

The High-End Timer is a specialized peripheral for complex timing and pulse generation:

1. **Programmable Timer**: HET executes a custom assembly-like instruction set from RAM
2. **High Resolution**: Capable of precise timing control with resolution down to one system clock cycle
3. **Autonomous Operation**: Runs independently of the CPU after configuration
4. **Flexible I/O Control**: Can handle input capture and output compare operations
5. **PWM Generation**: Supports multiple PWM channels with flexible configuration

The RM46 includes two HET modules with memory-mapped control registers and dedicated RAM areas for storing program instructions. Each HET module can be programmed to perform specialized timing tasks without CPU intervention.

## Hardware Timing Requirements

### System Clock Frequencies

The RM46 system is configured with the following clock frequencies:

| Clock Domain     | Frequency       | Description                        |
|------------------|----------------:|------------------------------------|
| OSC_FREQ         | 16,000,000 Hz   | Oscillator frequency               |
| PLL1_FREQ        | 200,000,000 Hz  | PLL1 output frequency              |
| PLL2_FREQ        | 200,000,000 Hz  | PLL2 output frequency              |
| GCLK_FREQ        | 200,000,000 Hz  | Global clock frequency             |
| HCLK_FREQ        | 200,000,000 Hz  | High-speed clock frequency         |
| RTI_FREQ         | 100,000,000 Hz  | Real-time interrupt clock frequency|
| AVCLK1_FREQ      | 100,000,000 Hz  | Asynchronous clock 1 frequency     |
| AVCLK2_FREQ      | 0 Hz            | Asynchronous clock 2 frequency     |
| AVCLK3_FREQ      | 100,000,000 Hz  | Asynchronous clock 3 frequency     |
| AVCLK4_FREQ      | 100,000,000 Hz  | Asynchronous clock 4 frequency     |
| VCLK1_FREQ       | 100,000,000 Hz  | Peripheral clock 1 frequency       |
| VCLK2_FREQ       | 100,000,000 Hz  | Peripheral clock 2 frequency       |
| VCLK3_FREQ       | 100,000,000 Hz  | Peripheral clock 3 frequency       |
| VCLK4_FREQ       | 100,000,000 Hz  | Peripheral clock 4 frequency       |
| LPO_LF_FREQ      | 0.080 Hz        | Low-power oscillator low frequency  |
| LPO_HF_FREQ      | 10,000,000 Hz   | Low-power oscillator high frequency |

### Flash Memory Timing

The flash memory controller is configured with the following timing parameters:

1. **Flash Read Mode**: Standard read mode
2. **Address Wait States**: 3 cycles
3. **Data Wait States**: 1 cycle
4. **Bank Access Time**: 1 cycle

These settings ensure proper operation at the system's operating frequency.

### Watchdog Timeout Calculations

The watchdog timer timeout is calculated using the following formula:

```
Timeout (seconds) = (Preload_Value + 1) * (1 / RTI_CLK_FREQ)
```

Where:
- Preload_Value: A 12-bit value (0-4095) stored in the DWDPRLD register
- RTI_CLK_FREQ: The frequency of the Real-Time Interrupt clock (100 MHz)

The maximum timeout period with a 12-bit counter at 100 MHz is approximately 40.96 microseconds.

### PLL Lock Time

When configuring the PLLs, the system waits for the PLLs to lock before proceeding with clock source switching. The CSVSTAT register is monitored to confirm clock validity.

### Memory Test Timing

During system startup, memory tests are performed on various RAM regions. The timing of these tests depends on the memory size and the algorithm used.

### Peripheral Initialization

After system clock configuration, peripherals are initialized with specific timing requirements:
1. Peripherals are first disabled
2. Power is provided to all peripherals
3. Peripherals are then enabled
4. Clock domains are mapped to the desired sources

This sequence ensures proper initialization and prevents issues that could occur if peripherals were enabled before their clocks were stable.

## Power Management

The RM46 microcontroller provides several power management capabilities to optimize power consumption while maintaining required functionality.

### Power Modes

The RM46 supports the following power modes:

1. **Active Mode**: Normal operating mode with full functionality
2. **Doze Mode**: Reduced power consumption with peripherals still active
3. **Snooze Mode**: Further reduced power consumption with limited peripheral activity
4. **Sleep Mode**: Lowest power consumption with most functions disabled

These modes are defined as constants in the system.h file:
```c
#define SYS_DOZE_MODE   0x000F3F02U
#define SYS_SNOOZE_MODE 0x000F3F03U
#define SYS_SLEEP_MODE  0x000FFFFFU
```

### Flash Bank Power Modes

The flash memory banks can be configured in different power modes to balance performance and power consumption:

```c
enum {
  SYS_SLEEP   = 0U,  /* Lowest power, longest wakeup time */
  SYS_STANDBY = 1U,  /* Medium power, medium wakeup time */
  SYS_ACTIVE  = 3U   /* Highest power, immediate access */
};
```

These modes are configured through the `setupFlash()` function, which sets the appropriate power mode for each flash bank:

```c
/* Setup flash bank power modes */
flashWREG->FBFALLBACK =
  0x00000000U
  | (uint32_t)((uint32_t)SYS_ACTIVE << 14U) /* BANK 7 */
  | (uint32_t)((uint32_t)SYS_ACTIVE << 2U)  /* BANK 1 */
  | (uint32_t)((uint32_t)SYS_ACTIVE << 0U); /* BANK 0 */
```

### Peripheral Power Management

The RM46 provides fine-grained control over peripheral power through the Peripheral Central Resource (PCR) module. This module allows individual peripherals to be powered down to save energy when not in use.

The PCR module includes the following registers for power management:
- PCSPWRDWNSET/PCSPWRDWNCLR: Control peripheral clock stop during power-down
- PSPWRDWNSET/PSPWRDWNCLR: Control peripheral power-down state

During system initialization, all peripherals are powered up.

### Low Power Oscillator (LPO)

The RM46 includes a Low Power Oscillator with two operating modes:
1. LPO Low Frequency: 0.080 Hz (for extreme power saving)
2. LPO High Frequency: 10 MHz (for better performance with moderate power saving)

The LPO is trimmed during system initialization to ensure accurate frequency based on either OTP values or user-defined values.

### Wakeup Sources

The Vectored Interrupt Manager (VIM) includes wake mask registers that determine which interrupts can wake the processor from low-power modes:

- WAKEMASKSET0-3: Enable specific interrupts as wake sources
- WAKEMASKCLR0-3: Disable specific interrupts as wake sources

### Clock Gating

To save power, unused clock domains can be disabled through the Clock Domain Disable register. In the default configuration, AVCLK2 is disabled to save power, while other clock domains remain active.

## Error Handling Mechanisms

The RM46 microcontroller includes comprehensive error detection and handling mechanisms to ensure reliable operation in critical applications.

### Error Signaling Module (ESM)

The Error Signaling Module (ESM) is the central hub for hardware error reporting and management. It collects error signals from various hardware modules and can trigger appropriate system responses.

#### ESM Registers
```c
typedef volatile struct esmBase {
  uint32_t EEPAPR1;     /* 0x0000 - Error Enable for ERROR Pin */
  uint32_t DEPAPR1;     /* 0x0004 - Disable Error Pin Action */
  uint32_t IESR1;       /* 0x0008 - Interrupt Enable Set Register */
  uint32_t IECR1;       /* 0x000C - Interrupt Enable Clear Register */
  uint32_t ILSR1;       /* 0x0010 - Interrupt Level Set Register */
  uint32_t ILCR1;       /* 0x0014 - Interrupt Level Clear Register */
  uint32_t SR1[3U];     /* 0x0018, 0x001C, 0x0020 - Status Registers */
  uint32_t EPSR;        /* 0x0024 - ERROR Pin Status Register */
  uint32_t IOFFHR;      /* 0x0028 - Interrupt Offset High Register */
  uint32_t IOFFLR;      /* 0x002C - Interrupt Offset Low Register */
  uint32_t LTCR;        /* 0x0030 - LTC Error Control Register */
  uint32_t LTCPR;       /* 0x0034 - LTC Error Pin Control Register */
  uint32_t EKR;         /* 0x0038 - Error Key Register */
  uint32_t SSR2;        /* 0x003C - Status Shadow Register 2 */
  uint32_t IEPSR4;      /* 0x0040 - Interrupt Enable Priority Set Register 4 */
  uint32_t IEPCR4;      /* 0x0044 - Interrupt Enable Priority Clear Register 4 */
  uint32_t IESR4;       /* 0x0048 - Interrupt Enable Set Register 4 */
  uint32_t IECR4;       /* 0x004C - Interrupt Enable Clear Register 4 */
  uint32_t ILSR4;       /* 0x0050 - Interrupt Level Set Register 4 */
  uint32_t ILCR4;       /* 0x0054 - Interrupt Level Clear Register 4 */
  uint32_t SR4;         /* 0x0058 - Status Register 4 */
} esmBASE_t;
```

The ESM is located at memory address 0xFFFFF500.

### Diagnostics Module

The BSP provides a diagnostics module that allows the software to log and track faults. This module works alongside the ESM to provide a comprehensive error handling framework.

#### Diagnostic Capabilities
- System initialization
- Status tracking and logging
- Failure and warning detection
- Status reporting

#### Failure Types
The system can detect and report various types of failures, including:

```c
typedef enum {
  BSPF_EFC_STUCK_ZERO     = ((uint32_t)1U << 0U),  /* EFC stuck at zero failure */
  BSPF_EFC_ERROR_1        = ((uint32_t)1U << 1U),  /* EFC error type 1 */
  BSPF_EFC_ERROR_2        = ((uint32_t)1U << 2U),  /* EFC error type 2 */
  BSPF_EFC_ERROR_3        = ((uint32_t)1U << 3U),  /* EFC error type 3 */
  BSPF_ECC_RAM_CPU        = ((uint32_t)1U << 4U),  /* ECC error in CPU RAM */
  BSPF_ECC_RAM_ESM        = ((uint32_t)1U << 5U),  /* ECC error in ESM RAM */
  BSPF_PBIST_CLOCK_DIS    = ((uint32_t)1U << 6U),  /* PBIST clock disabled */
  BSPF_PBIST_CPU_RAM      = ((uint32_t)1U << 7U),  /* PBIST CPU RAM test failed */
  BSPF_PBIST_PERIPH_ERROR = ((uint32_t)1U << 8U),  /* PBIST peripheral test failed */
  BSPF_PARITY_VIM         = ((uint32_t)1U << 9U),  /* Parity error in VIM RAM */
  BSPF_PARITY_DMA         = ((uint32_t)1U << 10U), /* Parity error in DMA RAM */
  BSPF_PARITY_MIBSPI1     = ((uint32_t)1U << 11U), /* Parity error in MIBSPI1 RAM */
  BSPF_PARITY_MIBSPI3     = ((uint32_t)1U << 12U), /* Parity error in MIBSPI3 RAM */
  BSPF_PARITY_MIBSPI5     = ((uint32_t)1U << 13U), /* Parity error in MIBSPI5 RAM */
  BSPF_PARITY_CAN1        = ((uint32_t)1U << 14U), /* Parity error in CAN1 RAM */
  BSPF_PARITY_CAN2        = ((uint32_t)1U << 15U), /* Parity error in CAN2 RAM */
  BSPF_PARITY_CAN3        = ((uint32_t)1U << 16U), /* Parity error in CAN3 RAM */
  BSPF_PARITY_ADC1        = ((uint32_t)1U << 17U), /* Parity error in ADC1 RAM */
  BSPF_PARITY_ADC2        = ((uint32_t)1U << 18U), /* Parity error in ADC2 RAM */
  BSPF_PARITY_HET1        = ((uint32_t)1U << 19U), /* Parity error in HET1 RAM */
  BSPF_PARITY_HET2        = ((uint32_t)1U << 20U), /* Parity error in HET2 RAM */
  BSPF_PARITY_HTU1        = ((uint32_t)1U << 21U), /* Parity error in HTU1 RAM */
  BSPF_PARITY_HTU2        = ((uint32_t)1U << 22U), /* Parity error in HTU2 RAM */
  BSPF_PARITY_RTP         = ((uint32_t)1U << 23U), /* Parity error in RTP RAM */
  BSPF_PARITY_SPI_5       = ((uint32_t)1U << 24U), /* Parity error in SPI5 */
  BSPF_PARITY_FRAY        = ((uint32_t)1U << 25U), /* Parity error in FlexRay RAM */
  BSPF_ECCRAM_SELF_TEST   = ((uint32_t)1U << 26U), /* ECC RAM self-test failed */
  BSPF_ECCRAM_ERROR       = ((uint32_t)1U << 27U), /* ECC RAM error detected */
  BSPF_FLASH_ECC_UNCORR   = ((uint32_t)1U << 28U), /* Flash ECC uncorrectable error */
  BSPF_FLASH_ECC_CORR     = ((uint32_t)1U << 29U), /* Flash ECC correctable error */
  BSPF_RAM_ECC_UNCORR     = ((uint32_t)1U << 30U), /* RAM ECC uncorrectable error */
  BSPF_RAM_ECC_CORR       = ((uint32_t)1U << 31U)  /* RAM ECC correctable error */
} bspStartupFailures_t;
```

### Memory Protection Mechanisms

#### ECC (Error-Correcting Code)

The RM46 implements ECC protection for RAM:
- Single-bit errors are automatically corrected
- Double-bit errors are detected and reported
- ECC protection functionality is verified during startup

#### Parity Checking

Parity checking is implemented for various peripheral RAM modules:
- VIM (Vectored Interrupt Manager)
- DMA (Direct Memory Access)
- ADC (Analog-to-Digital Converter)
- CAN (Controller Area Network)
- HET (High-End Timer)
- MibSPI (Multi-buffered SPI)

Parity error detection for each peripheral is verified during system startup.

### Self-Test Framework

The BSP includes a comprehensive self-test framework that executes during system startup:

#### PBIST (Programmable Built-In Self-Test)

The PBIST module tests RAM integrity using various algorithms:
- Self-check verification: Verifies the PBIST controller itself
- Memory testing: Runs tests on selected RAM regions
- Test completion: Checks if tests are complete
- Result verification: Confirms test results

#### EFC (eFuse Controller) Tests

The system tests the eFuse controller's error detection capabilities through built-in self-tests, RAM self-tests, error signaling verification, and results validation.

### Exception Handling

The system includes trap handling for CPU exceptions:
- Default exception handler: Handles unhandled exceptions
- Overridable trap handler: Can be customized by application code

### Error Recovery

For recoverable errors, the system may attempt to:
1. Correct the error (e.g., for single-bit ECC errors)
2. Report the error to the diagnostics module
3. Continue operation if possible

For critical errors, the system may:
1. Enter a safe state
2. Trigger a system reset
3. Signal the error through external pins

## Boot Sequence Information

The RM46 follows a structured boot sequence to ensure proper system initialization, hardware verification, and memory setup before application code begins execution.

### Reset Handler

The boot process begins with the reset handler in crt0.s, which performs these critical steps:

1. **CPU Mode Initialization**
   - Configures little endian data mode
   - Initializes registers for each ARM CPU mode (SVC, IRQ, FIQ, ABT, UND, SYS)
   - Sets up stack pointers for each mode

2. **FPU Initialization**
   - Enables the Floating-Point Unit
   - Initializes all FPU registers (d0-d15)

3. **Flash ECC Setup**
   - Enables Error-Correcting Code (ECC) for flash memory
   - Configures the Cortex-R4F event signaling mechanism

4. **Processor Errata Workarounds**
   - `_errata_CORTEXR4_57`: Disables out-of-order single-precision floating-point multiply-accumulate instruction completion
   - `_errata_CORTEXR4_66`: Disables out-of-order completion for divide instructions

5. **Control Transfer to C Code**
   - Calls `_sysInit()` to continue system initialization in C

### System Initialization Sequence

After the reset handler, the `_sysInit()` function in sys_startup.c continues the boot process:

1. **Clock System Setup**
   - PLL initialization: Sets up PLL clock rates
   - Peripheral clock setup: Enables clocks to peripherals and releases peripheral reset
   - LPO calibration: Initializes low-power oscillator with trim values
   - Clock domain mapping: Maps clock domains to desired sources

2. **Diagnostics Initialization**
   - Diagnostics setup: Initializes the diagnostics tracking system

3. **Flash Configuration**
   - Flash setup: Configures flash read mode, wait states, and bank power modes

4. **eFuse Controller Testing**
   - Runs eFuse controller startup checks and self-test

5. **Memory Testing and Initialization**
   - PBIST errata workaround: Applies fix for PBIST hardware issue
   - PBIST controller verification: Ensures the PBIST controller functions correctly
   - CPU RAM testing: Runs March13N algorithm on CPU RAM
   - Memory initialization: Sets up CPU RAM and associated protection
   - ECC enablement: Enables Error Correcting Code for RAM accesses
   - ECC verification: Tests the CPU ECC mechanism functionality
   - Peripheral RAM testing: Runs PBIST on peripheral RAM modules (DMA, VIM, MIBSPI, CAN, ADC, HET, etc.)
   - Parity verification: Performs parity checks on peripheral modules
   - RAM initialization: Initializes all RAM by clearing BSS and loading initialized data

6. **System Configuration**
   - Reset cause determination: Identifies the cause of the most recent reset
   - Interrupt setup: Initializes and configures the interrupt vector table

7. **Finalization**
   - Diagnostic completion: Finalizes diagnostic tracking
   - Application handoff: Transfers control to main application code for execution

### Memory Initialization

During RAM initialization, the system:
1. Clearing all BSS data to zero
2. Copying initialized data from flash to RAM
3. Setting up additional memory segments as needed

### Critical Hardware Steps

The boot sequence implements several critical hardware verification steps:
1. PLL and clock validation before switching sources
2. Comprehensive RAM testing with multiple algorithms
3. Parity and ECC verification for error detection capabilities
4. Flash controller configuration with appropriate timing
5. Peripheral module initialization with proper sequencing

## Memory Protection and Access Control

The RM46 implements several mechanisms for memory protection and access control to ensure system integrity and security.

### Memory Organization

The memory system in the RM46 is organized as follows:

```c
MEMORY
{
  flash     (RX)    : ORIGIN = 0x00000000, LENGTH = 1M + 256K  /* Flash memory: 1.25MB */
  ram       (RWX)   : ORIGIN = 0x08000000, LENGTH = 192K       /* RAM: 192KB */
}
```

Key memory regions include:
- Flash starting at 0x00000000 with 1.25MB capacity
- RAM starting at 0x08000000 with 192KB capacity
- Special flash areas:
  - Interrupt Vector Table (IVT): 0x00000000
  - CRC: 0x00000800
  - Flash signature: 0x00000804
  - Metadata: 0x00000808
  - Reset handler: 0x00001000

### Flash Bank Protection

The flash module includes protection registers that control access to flash banks:

1. **Flash Bank Protection (FBPROT) Register**:
   - Located at offset 0x0030 in the flash controller
   - Controls which flash banks can be erased or programmed
   - Each bit corresponds to a specific bank

2. **Flash Bank Select (FBSE) Register**:
   - Located at offset 0x0034 in the flash controller
   - Enables or disables access to specific flash banks

3. **Flash Bank Access Control (FBAC) Register**:
   - Located at offset 0x003C in the flash controller
   - Configures access permissions for flash banks

### Peripheral Protection

The Peripheral Central Resource (PCR) module includes registers for peripheral protection:

1. **Peripheral Memory Protection Set/Clear Registers**:
   - PMPROTSET0, PMPROTSET1: Set protection for peripheral memory regions
   - PMPROTCLR0, PMPROTCLR1: Clear protection for peripheral memory regions

2. **Peripheral Protection Set/Clear Registers**:
   - PPROTSET0-PPROTSET3: Set protection for peripherals
   - PPROTCLR0-PPROTCLR3: Clear protection for peripherals

These registers allow the system to control access to specific peripherals and their associated memory regions, preventing unauthorized or accidental modifications.

### ECC Protection for Memory

The RM46 implements Error-Correcting Code (ECC) protection for both flash and RAM:

1. **Flash ECC Protection**:
   - Enabled during boot sequence
   - Configured through FEDACCTRL1 and FEDACCTRL2 registers
   - Provides single-bit error correction and double-bit error detection

2. **RAM ECC Protection**:
   - Controlled by the CPU's ECC logic
   - Enabled during system initialization
   - Verified during startup

### Parity Protection for Peripheral RAM

Peripheral RAM modules implement parity-based protection that applies to VIM, DMA, CAN, ADC, HET, and MibSPI modules. This protection is enabled and verified during system startup.

This provides an additional layer of data integrity protection for peripheral operations.

## Errata Information

The RM46 microcontroller has several known hardware bugs (errata) that require software workarounds. The BSP implements fixes for these issues to ensure reliable system operation.

### Cortex-R4 CPU Errata

1. **CORTEX-R4#57**: Conditional VMRS APSR_Nzcv, FPSCR May Evaluate With Incorrect Flags
   - **Issue**: The CPU may evaluate conditional VMRS instructions with incorrect flags.
   - **Workaround**: Disable out-of-order single-precision floating-point multiply-accumulate instruction completion by setting bit 16 (DOOFMACS) in the Auxiliary Control Register.
   - **Implementation**: Applied during system initialization.

2. **CORTEX-R4#66**: Register Corruption During A Load-Multiple Instruction at an Exception Vector
   - **Issue**: Registers may become corrupted when a load-multiple instruction is executed at an exception vector.
   - **Workaround**: Disable out-of-order completion for divide instructions by setting bit 7 in the Auxiliary Control Register.
   - **Implementation**: Applied during system initialization.

### System Module Errata

1. **SYS#46**: Clock Source Switching Not Qualified with Clock Source Enable And Clock Source Valid
   - **Issue**: Clock switching may occur before the source clock is stable or enabled.
   - **Workaround**: Check that the clock source is turned on (CSDIS register) and valid (CSVSTAT register) before switching clock sources.
   - **Implementation**: Applied during clock configuration.

### PBIST Module Errata

1. **PBIST#4**: PBIST Algorithms May Not Execute
   - **Issue**: There is a possibility that the PBIST (Programmable Built-In Self-Test) algorithms do not execute properly.
   - **Workaround**: Initialize the PBIST and Self-Test Controller (STC) ROM sections in a specific way before running any self-tests.
   - **Implementation**: Applied before memory self-tests.

### Application of Errata Fixes

These errata workarounds are applied at different stages of the boot process:

1. CPU-related errata fixes are applied early during reset handling.
2. PBIST errata is fixed before running any memory self-tests.
3. System module errata is addressed during clock configuration.

These fixes ensure that the RM46 operates correctly despite the hardware issues. The BSP carefully sequences these workarounds to maintain system stability and reliability.