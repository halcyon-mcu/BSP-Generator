# Hardware Deployment & Validation Guide

**Testing Generated BSP Code on TI RM46 Cortex-R4 Board with Code Composer Studio**

This guide provides step-by-step instructions to deploy and validate the BSP-Generator output on actual hardware using TI Code Composer Studio (CCS) and the JTAG debugger.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Creating a CCS Project](#creating-a-ccs-project)
4. [Importing Generated Code](#importing-generated-code)
5. [Configuring the Project](#configuring-the-project)
6. [Building the Project](#building-the-project)
7. [Connecting the Debugger](#connecting-the-debugger)
8. [Flashing the Board](#flashing-the-board)
9. [Running Tests](#running-tests)
10. [Validation Checklist](#validation-checklist)

---

## Prerequisites

### Hardware Requirements

- **TI RM46 Evaluation Board** (or compatible RM46L852-based target)
- **XDS110 JTAG Debugger** (or compatible TI debugger)
- **USB Cable** for JTAG connection (Type-A to Micro-B or appropriate connector)
- **Power Supply** for the board (typically 3.3V or 5V)

### Software Requirements

- **TI Code Composer Studio** 12.0+ (CCS)
  - Download from: https://www.ti.com/tool/download/CCSTUDIO
  - ~1.2 GB disk space required
  - Supports Windows, Linux, Mac
- **TI ARM CGT Compiler** (included with CCS)
  - Version 20.x or later
  - Automatically installed with CCS

- **TI HalCoGen** (optional, for peripheral configuration)
  - Download from: https://www.ti.com/tool/HALCOGEN
  - Only needed if modifying hardware configuration

### Software Installation Steps

#### 1. Install Code Composer Studio

```bash
# Windows
# Download CCSTUDIO-12.0.0-windows-installer.exe from TI website
# Run installer and follow setup wizard
# Install to default location: C:\ti\ccs\ccs12.0.0

# Linux/Mac
# Download appropriate package and follow TI documentation
```

#### 2. Install RM46 Device Support

When CCS first launches:

1. Open **Help** → **Install CCS Components**
2. Search for "RM46"
3. Install: **RM46L852 Device Support Pack**
4. Restart CCS

#### 3. Configure JTAG Debugger

Connect your XDS110 debugger:

1. Plug JTAG cable into board (JTAG header)
2. Connect XDS110 via USB to your computer
3. Install XDS110 drivers (usually automatic on Windows)

Verify debugger detection:

1. In CCS, go to **Tools** → **Debugger** → **List Connected Debuggers**
2. You should see your XDS110 listed

---

## Environment Setup

### 1. Prepare the Generated BSP

From your BSP generation output:

```bash
cd bsp_gen/output_20260210_130852/

# Verify all files are present
ls *.c *.h *.cmd *.s
# Should show:
# - start.s (ARM startup)
# - entry.c (C reset handler)
# - system.c/h (system init)
# - linker.cmd (linker script)
# - clock.c/h, gio.c/h, sci.c/h, vim.c/h (drivers)
```

### 2. Create Project Directory Structure

```bash
# Create a clean project folder for CCS
mkdir RM46_BSP_Project
cd RM46_BSP_Project

# Create subdirectories
mkdir src inc doc

# Copy generated files
cp ../bsp_gen/output_20260210_130852/*.c src/
cp ../bsp_gen/output_20260210_130852/*.h inc/
cp ../bsp_gen/output_20260210_130852/*.cmd .
cp ../bsp_gen/output_20260210_130852/*.s src/
```

---

## Creating a CCS Project

### Step 1: Launch Code Composer Studio

```bash
# Windows
C:\ti\ccs\ccs12.0.0\eclipse\ccstudio.exe

# Linux/Mac
/opt/ti/ccs/ccs12.0.0/eclipse/ccstudio  # or wherever installed
```

### Step 2: Create New Project

1. **File** → **New** → **CCS Project**
2. **Project name:** `RM46_BSP_Test`
3. **Project type:** Select **CCS C/C++ Project**
4. **Device variant:**
   - Search for: `RM46L852`
   - Select: **RM46L852 Cortex-R4**
5. **Target Configuration:**
   - Select: **User Specified**
   - Or use existing config if available
6. **Runtime Support Library:**
   - Select: **TI ARM Compiler** (default)
7. **Compiler version:** (default is fine)
8. **Project template:**
   - Select: **Empty Project**
   - **Uncheck** "Include device specific files"
9. Click **Finish**

### Step 3: Configure Project Settings

Right-click project → **Properties**:

#### Build Settings

1. **Build** → **ARM Compiler** → **Include Options**
   - Add: `${PROJECT_ROOT}/inc` (for header files)

2. **Build** → **ARM Compiler** → **Advanced Options** → **Dialect**
   - Set: **C90 or later** (or C99)

3. **Build** → **Linker** → **File Search Path**
   - Add: `${PROJECT_ROOT}`

4. **Build** → **Linker** → **Input** → **Linker Command File**
   - Specify: `linker.cmd` (relative path)

#### Debug Settings

1. **Run** → **Debug**
   - **Debug probe:** Select your debugger (XDS110)
   - **Device:** RM46L852
   - **Connection:** Default (or specific if multiple debuggers)

---

## Importing Generated Code

### Step 1: Add Source Files

1. Right-click **RM46_BSP_Test** project → **New** → **Folder**
   - Name: `src`

2. Right-click **src** folder → **Import**
   - **General** → **File System**
   - Select source directory: `bsp_gen/output_20260210_130852/`
   - Select files:
     - `start.s`
     - `entry.c`
     - `system.c`
     - `clock.c`
     - `gio.c`
     - `sci.c`
     - `vim.c`
   - Click **Finish**

### Step 2: Add Header Files

1. Right-click project → **New** → **Folder**
   - Name: `inc`

2. Right-click **inc** folder → **Import**
   - Select all `.h` files from output directory
   - Click **Finish**

### Step 3: Add Linker Script

1. Right-click project → **Import**
   - **General** → **File System**
   - Select: `linker.cmd`
   - Click **Finish**

### Step 4: Verify Project Structure

Your CCS project should now look like:

```
RM46_BSP_Test/
├── inc/
│   ├── clock.h
│   ├── gio.h
│   ├── sci.h
│   ├── system.h
│   └── vim.h
├── src/
│   ├── start.s        (set as "Root")
│   ├── entry.c
│   ├── system.c
│   ├── clock.c
│   ├── gio.c
│   ├── sci.c
│   └── vim.c
├── linker.cmd
└── .project (hidden)
```

---

## Configuring the Project

### Step 1: Create Main Program

Create a simple test program:

1. Right-click **src** → **New** → **Source File**
2. Name: `main.c`
3. Add content:

```c
/**
 * @file main.c
 * @brief BSP Test Program - Validates generated drivers on RM46
 */

#include <stdint.h>
#include "system.h"
#include "clock.h"
#include "gio.h"

/* LED GPIO configuration for RM46 EVB */
#define LED_PORT   0
#define LED_PIN    0

/**
 * @brief Simple delay function
 */
void delay_ms(uint32_t ms) {
    volatile uint32_t count = ms * 1000;
    while (count--) {
        __asm("NOP");
    }
}

/**
 * @brief Main application entry point
 */
int main(void) {
    /* Initialize system (clock, peripherals) */
    system_init();

    /* Initialize clock module */
    clock_init();

    /* Initialize GPIO */
    gio_init();

    /* Configure LED pin as output */
    gio_set_direction(LED_PORT, LED_PIN, 0);  /* 0 = output */

    /* Blink LED 5 times to verify GPIO works */
    for (int i = 0; i < 5; i++) {
        gio_set_pin(LED_PORT, LED_PIN);      /* LED on */
        delay_ms(500);

        gio_clear_pin(LED_PORT, LED_PIN);    /* LED off */
        delay_ms(500);
    }

    /* All tests passed - loop forever */
    while (1) {
        gio_set_pin(LED_PORT, LED_PIN);
        delay_ms(100);
        gio_clear_pin(LED_PORT, LED_PIN);
        delay_ms(100);
    }

    return 0;
}
```

### Step 2: Mark start.s as Root Linker File

Right-click **src/start.s** → **Mark as Root File**

This tells the linker to use start.s as the entry point.

### Step 3: Enable Semihosting (Optional)

For debug output:

1. **Project** → **Properties**
2. **Build** → **ARM Compiler** → **Advanced Options** → **Runtime Options**
3. Check **Enable semihosting**

---

## Building the Project

### Step 1: Build Configuration

1. **Project** → **Build Configurations** → **Manage...**
2. Ensure **Debug** configuration is selected

### Step 2: Build Project

**Project** → **Build Project** (or Ctrl+B)

**Expected output in Console:**

```
Building target: RM46_BSP_Test.out

Invoking: ARM Compiler
...
"C:\ti\ccs\tools\compiler\arm_20.2.0.LTS\bin\armcl" ...

Linking...
"C:\ti\ccs\tools\compiler\arm_20.2.0.LTS\bin\armlnk" linker.cmd ...

Build complete.

RM46_BSP_Test.out
   text    data     bss     dec     hex filename
  12345   1024    4096   17465   441f9 RM46_BSP_Test.out
```

### Step 3: Verify Build

Check that these files were created:

- `Debug/RM46_BSP_Test.out` - Executable ELF file
- `Debug/RM46_BSP_Test.hex` - Hex file (if configured)

---

## Connecting the Debugger

### Step 1: Physical Connection

1. Connect XDS110 JTAG probe to computer via USB
2. Connect JTAG cable to RM46 board's JTAG header
3. Power on the RM46 board
4. Verify LED indicators on XDS110 (should show power)

### Step 2: Configure Debug Session

1. **Run** → **Debug Configurations**
2. Create **New** → **GDB Hardware Debugging**
   - **Name:** `RM46_Debug`
   - **C/C++ Application:** `Debug/RM46_BSP_Test.out`
   - **GDB command:** (leave default)
   - **Debugger Tab:**
     - **GDB Debugger:** `arm-none-eabi-gdb`
     - **Initialization commands:**
       ```
       target remote localhost:55000
       monitor reset
       monitor halt
       load
       ```
3. Click **Debug**

### Step 3: Debug Perspective

CCS switches to Debug perspective showing:

- Registers
- Variables
- Disassembly
- Call Stack

---

## Flashing the Board

### Method 1: Flash via Debugger (Recommended)

1. In **Debug** perspective
2. **Run** → **Resume** (or press F8)
   - This loads code to flash and starts execution
3. LED should blink 5 times
4. Then blink continuously (success indicator)

### Method 2: Flash Standalone with Uniflash

1. Download **TI Uniflash** from: https://www.ti.com/tool/UNIFLASH
2. Open Uniflash
3. **Select Tool:** XDS110
4. **Select Device:** RM46L852
5. **Load Image:** Select `Debug/RM46_BSP_Test.hex`
6. Click **Flash**
7. Wait for completion message

### Method 3: Use CCS Flash Programmer

1. **Tools** → **Flash Programmer**
2. **Select Device:** RM46L852
3. **Specify Flash Data File:** `Debug/RM46_BSP_Test.hex`
4. Click **Start Flash**

---

## Running Tests

### Test 1: LED Blink Test (GPIO Validation)

**Expected Behavior:**

1. After flashing, LED blinks 5 times quickly
2. Then blinks continuously slowly (indefinite)

**What this validates:**

- ✅ Clock initialization working
- ✅ GPIO driver functions correctly
- ✅ System initialization complete
- ✅ No hard faults or exceptions

### Test 2: Serial Output Test (SCI Validation)

Add serial output to main.c:

```c
#include "sci.h"

void sci_print(const char *str) {
    while (*str) {
        sci_transmit_byte(*str++);
    }
}

int main(void) {
    system_init();
    clock_init();
    gio_init();
    sci_init();

    sci_print("BSP-Generator Test Started\n");
    sci_print("System Clock: OK\n");
    sci_print("GPIO Driver: OK\n");
    sci_print("UART Driver: OK\n");

    // ... rest of code
}
```

**To verify UART output:**

1. Connect USB-to-UART adapter to SCI pins on board
2. Open serial terminal: 115200 baud, 8N1
3. Should see debug messages

### Test 3: Interrupt Validation (VIM)

Create interrupt test (advanced):

```c
#include "vim.h"

void button_isr(void) {
    gio_clear_pin(LED_PORT, LED_PIN);  /* Turn LED off on interrupt */
}

int main(void) {
    system_init();
    vim_init();

    /* Register button interrupt handler */
    vim_register_handler(BUTTON_INTERRUPT, button_isr);

    /* Enable global interrupts */
    vim_enable_interrupts();

    // ... rest of code
}
```

---

## Validation Checklist

Use this checklist to validate that the generated BSP is working correctly:

### Initialization & Startup

- [ ] Project builds with no errors or warnings
- [ ] Hex/ELF file generates correctly (~30-50 KB typical)
- [ ] Debugger connects to board successfully
- [ ] Code loads without memory protection errors

### Clock & System

- [ ] System initializes without hard faults
- [ ] Clock rates are stable (measure with oscilloscope if available)
- [ ] No watchdog resets occurring

### GPIO Functionality

- [ ] LED blinks as expected
- [ ] Pin voltage levels correct (3.3V for high, 0V for low)
- [ ] Multiple GPIO operations work (set, clear, toggle)
- [ ] No GPIO conflicts or cross-talk

### UART/Serial (if implemented)

- [ ] Serial output appears in terminal
- [ ] Baud rate is correct
- [ ] No data corruption or framing errors
- [ ] Loopback test successful (if enabled)

### Interrupts (if implemented)

- [ ] External interrupts trigger correctly
- [ ] ISR handlers execute
- [ ] No unexpected interrupts occurring
- [ ] Interrupt priorities work as expected

### Register Access

- [ ] All generated register macros work
- [ ] No undefined register access
- [ ] Memory-mapped I/O accesses are atomic
- [ ] No write-back errors

### Performance

- [ ] Code execution is fast (no unexpected delays)
- [ ] No memory leaks
- [ ] Stack depth is reasonable
- [ ] CPU utilization matches expectations

---

## Advanced: Using HalCoGen for Additional Configuration

If you need to modify hardware configuration:

### Step 1: Open HalCoGen

```bash
# Windows
C:\ti\Hercules\HalCoGen\halcogen.exe

# Load your RM46 device
```

### Step 2: Configure Peripherals

1. **Peripherals** tab
2. Enable additional modules (if needed):
   - Add second SCI instance
   - Configure ADC
   - Setup timers
   - Configure PWM

### Step 3: Generate Updated Code

1. **Generate Code** button
2. Choose output directory
3. HalCoGen generates `sys_*.c/h` files

### Step 4: Integrate with CCS

Replace the old system files with HalCoGen-generated ones in your CCS project

---

## Troubleshooting

### Problem: "Device not recognized"

**Solution:**

```bash
# Check XDS110 is detected
# Windows: Device Manager should show "XDS110"
# Linux: lsusb | grep -i texas
# If not found, reinstall drivers from TI website
```

### Problem: "Failed to connect to target"

**Solution:**

1. Verify JTAG cable connections (check both ends)
2. Power cycle board and debugger
3. Check CCS → Window → Show View → Debugger → Debug View
4. Try: **Window** → **Show View** → **Other** → **Debug** → **Debug View**

### Problem: "Linker error: undefined reference"

**Solution:**

1. Ensure all `.c` files are in project (not just headers)
2. Verify **linker.cmd** is set as linker command file
3. Check include paths: **Project** → **Properties** → **Paths and Symbols**
4. Rebuild project (clean + build)

### Problem: "Program halts at breakpoint but doesn't resume"

**Solution:**

1. Right-click process → **Resume** (or F8)
2. Check for infinite loops or blocking calls
3. If stuck in startup code, debug start.s line-by-line

### Problem: "Flash fails with 'Write Error'"

**Solution:**

1. Verify board is powered properly
2. Check JTAG cable connection
3. Try erasing flash first: **Tools** → **Flash Programmer** → **Erase All**
4. Retry flash operation

### Problem: "LED doesn't blink"

**Solution:**

1. Verify LED connections on board
2. Check GPIO pin configuration (output mode, not input)
3. Measure voltage at LED pin with multimeter
4. Try different GPIO pins
5. Check system clock is initialized (scope measurement)

---

## Next Steps

Once hardware validation is complete:

1. **Review generated code** - Check API documentation in `docs/html/index.html`
2. **Run unit tests** - Execute compiled test suite on PC
3. **Create your application** - Build on top of generated drivers
4. **Integrate with real-time OS** - Add FreeRTOS or Zephyr if needed
5. **Enable production features** - Configure error handling, watchdog, etc.

---

## References

- [TI RM46 Reference Manual](https://www.ti.com/product/RM46L852)
- [TI Code Composer Studio Getting Started](https://software-dl.ti.com/ccs/esd/documents/CCS_Getting_Started_Guide.pdf)
- [ARM JTAG Debugger Guide](https://developer.arm.com/documentation/dui0060/)
- [Cortex-R4 Technical Reference Manual](https://developer.arm.com/documentation/ddi0436/)

---

## Support

For issues related to:

- **BSP-Generator:** Check [README.md](./README.md) and project documentation
- **CCS:** Consult TI support forum or CCS help system
- **RM46 Hardware:** See TI RM46L852 datasheet and reference design
- **Debugger:** Check XDS110 user guide on TI website
