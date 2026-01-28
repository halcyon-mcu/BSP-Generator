# BSP Generator Output - Quick Reference

## 🎯 What You've Got

✅ **5 Hardware Drivers**: GPIO, UART, Clock, Interrupt Manager, System Init  
✅ **Startup Code**: Assembly + C, handles memory init & main() call  
✅ **Linker Script**: Memory layout for FLASH (code) and RAM (data)  
✅ **Documentation**: Professional Doxygen HTML API reference  
✅ **Debug Info**: FACTS MIRROR showing all hardware values used

---

## 📁 File Locations & Purposes

| File                    | Type    | Purpose                                   |
| ----------------------- | ------- | ----------------------------------------- |
| `gio.h` / `gio.c`       | Driver  | GPIO control (pins, interrupts)           |
| `sci.h` / `sci.c`       | Driver  | Serial communication (UART)               |
| `clock.h` / `clock.c`   | Driver  | Clock configuration & frequencies         |
| `vim.h` / `vim.c`       | Driver  | Interrupt management                      |
| `system.h` / `system.c` | Init    | System hardware powerup                   |
| `entry.c`               | Startup | C reset handler (data init → main)        |
| `start.s`               | Startup | ARM assembly (vector table → stack)       |
| `linker.cmd`            | Config  | Memory layout (FLASH/RAM placement)       |
| `docs/html/`            | Docs    | Doxygen API reference (open index.html)   |
| `_artifacts/`           | Debug   | FACTS MIRROR & LLM prompts for validation |

---

## 🔍 FACTS MIRROR - What It Is

The `_artifacts/llm_preamble_*.txt` files contain all hardware constants:

```
===== FACTS MIRROR =====
GIO_BASE = 0xFFF7BC00
GIO_DIR_A_OFFSET = 0x34
GIO_DOUT_A_OFFSET = 0x3C
GIO_IRQ_A_ID = 9
... (all register addresses & offsets)
===== END FACTS MIRROR =====
```

**Purpose**: Proves which hardware values were used in code generation  
**Use**: Cross-check against RM46 datasheet for correctness

---

## ✅ Validation Checklist

After generation, verify:

- [ ] All 8 `.c` / `.h` files exist (gio, sci, clock, vim, system, entry)
- [ ] `start.s` file exists (ARM assembly)
- [ ] `linker.cmd` exists
- [ ] `docs/html/index.html` exists (Doxygen docs generated)
- [ ] `_artifacts/` has preambles (FACTS MIRROR data)
- [ ] No compilation errors when building

**Quick test**:

```bash
cd bsp_gen/output_20260127_133938
ls -la *.c *.h *.s *.cmd docs/ _artifacts/
# Should show all files without "No such file" errors
```

---

## 🚀 Use Your BSP

### **In Code Composer Studio (CCS)**:

1. Create new project (Target: RM46)
2. Drag & drop all `.c`, `.h` files into project
3. Set linker command file to `linker.cmd`
4. Create `main.c` with your application
5. Build → Download to board

### **Example main.c**:

```c
#include "gio.h"
#include "sci.h"

int main(void)
{
    // System already initialized by startup code

    // Configure GPIO pin A0 as output
    gio_set_dir(GIO_PORT_A, 0, 1);

    // Send hello over UART
    sci_send_char('H');
    sci_send_char('i');

    // Blink LED
    while(1) {
        gio_set(GIO_PORT_A, 0);      // LED on
        gio_clear(GIO_PORT_A, 0);    // LED off
    }

    return 0;
}
```

### **Build**:

```bash
# Using TI ARM CGT compiler
armcl -v4 --c11 *.c start.s -o app.elf -T linker.cmd

# Or in CCS: Right-click project → Build
```

---

## 📖 API Quick Reference

### **GPIO (gio.h)**

```c
gio_set_dir(port, pin, output);    // 0=input, 1=output
gio_set(port, pin);                 // Set HIGH
gio_clear(port, pin);               // Set LOW
gio_toggle(port, pin);              // Toggle
uint32_t val = gio_read(port, pin); // Read 0 or 1
```

### **UART (sci.h)**

```c
sci_set_baudrate(115200);    // Configure speed
sci_send_char('A');          // Send byte
uint8_t ch = sci_recv_char(); // Receive byte
```

### **Clock (clock.h)**

```c
clock_configure_pll(240, 24); // CPU to 240 MHz
clock_set_divider(domain, div); // Set divider
```

### **Interrupts (vim.h)**

```c
vim_enable_irq(irq_num);      // Enable interrupt
vim_disable_irq(irq_num);     // Disable interrupt
vim_set_priority(irq, priority); // Set priority
```

### **System (system.h)**

```c
system_init(); // Already called by startup - powers up hardware
```

---

## 🎯 Startup Sequence (What Happens at Power On)

```
1. CPU powers on
   ↓
2. Reads vector table from 0x00000000
   (Located in start.s → .intvecs section → FLASH)
   ↓
3. Jumps to Reset_Handler address
   (Assembly code in start.s)
   ↓
4. Assembly:
   - Loads stack pointer from linker symbol (end_of_stack)
   - Branches to Reset_Handler_C (C function)
   ↓
5. C code (entry.c):
   - Copies .data section from FLASH to RAM
   - Zeros .bss section
   - Calls system_init() → powers up all peripherals
   ↓
6. Calls main() → your application starts
   ↓
7. If main() returns → infinite loop (safe hang)
```

**Timeline**: ~milliseconds from power on to main()

---

## 📊 Memory Layout

```
FLASH (Code & Constants)
├─ 0x00000000: Vector table (start.s)
├─ 0x00000024: Reset_Handler code
├─ 0x00000100: main() and your code
├─ 0x....... : Constants, strings
└─ 0x0015FFFF: End of FLASH (1.5 MB total)

RAM (Variables & Stack)
├─ 0x08000000: start of .data (initialized variables)
├─ 0x08....... : .bss (uninitialized variables)
├─ 0x08020000: Heap (.sysmem)
└─ 0x0802FFFF: Stack grows down from top (192 KB total)
```

**Key**: Linker script (linker.cmd) defines these regions

---

## 🔗 Documentation

**Open this in a browser** to see detailed API reference:

```
docs/html/index.html
```

Contains:

- Module overview (GIO, SCI, Clock, VIM, System)
- Function signatures & descriptions
- Parameter documentation
- Return value documentation
- Code examples (where provided)

---

## ❓ Common Questions

### Q: What's the FACTS MIRROR?

**A**: Lists all hardware addresses/offsets used. Shows the LLM used correct values from YAML.

### Q: Can I modify the generated code?

**A**: Yes! It's your code. But if you regenerate, your changes will be overwritten.

### Q: How do I add my own functions?

**A**: Create new `.c` and `.h` files in your CCS project. Include the BSP headers you need.

### Q: What if I want to use a different peripheral?

**A**: Regenerate with that peripheral included in your input YAML.

### Q: Do I need all 5 drivers?

**A**: No, only include what you need. But the linker script must be used.

### Q: Why is start.s in assembly?

**A**: Required for ARM Cortex-R4. Handles vector table, stack pointer, CPU setup.

---

## 🚨 Troubleshooting

| Problem                                 | Cause                           | Solution                                        |
| --------------------------------------- | ------------------------------- | ----------------------------------------------- |
| Compilation error "undefined reference" | Missing .c file                 | Ensure all .c files included in project         |
| Linker error about vectors              | start.s missing or not compiled | Add start.s to build                            |
| Code doesn't start                      | Wrong linker script             | Verify linker.cmd is set as linker command file |
| UART not working                        | Wrong baud rate                 | Check sci_set_baudrate() call in main           |
| Interrupt not firing                    | Not enabled                     | Call vim_enable_irq() first                     |
| Generator output missing files          | LLM incomplete                  | Check \_artifacts/ for errors                   |

---

## 📝 Summary

You now have:

- ✅ **Verified hardware drivers** (GPIO, UART, Clock, Interrupts)
- ✅ **Complete startup code** (assembly + C)
- ✅ **Professional documentation** (Doxygen HTML)
- ✅ **Validation data** (FACTS MIRROR)

**Next step**: Import into Code Composer Studio and write your `main()` function!

---

## 📚 For More Details

- `OUTPUT_EXPECTATIONS.md` - Detailed explanation of each file
- `GENERATED_OUTPUT_GUIDE.md` - Function-by-function reference
- `VALIDATION_TESTING.md` - How to validate the generated code
- `QUICKSTART_VALIDATION.md` - Quick validation tests
