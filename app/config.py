from pathlib import Path

# ---------------- Config ----------------
YAMLS_DIR = Path("app/yamls_in")
TARGET_FILES = [
    "drivers/gpio.h",
    "drivers/gpio.c",
    "soc/rm46_gio_regs.h",
    "board/pinmux_init.c",
    "examples/blinky/main.c",
]

FACTS_CANON = """--- FACTS CANON ---
GIO_BASE = 0xFFF7BC00
GIO_DIR_A_OFFSET = 0x0034
GIO_DIN_A_OFFSET = 0x0038
GIO_DOUT_A_OFFSET = 0x003C
GIO_DSET_A_OFFSET = 0x0040
GIO_DCLR_A_OFFSET = 0x0044
GIO_DIR_B_OFFSET = 0x0054
GIO_DIN_B_OFFSET = 0x0058
GIO_DOUT_B_OFFSET = 0x005C
GIO_DSET_B_OFFSET = 0x0060
GIO_DCLR_B_OFFSET = 0x0064
PORT_PIN_RANGE = 0..31
--- END FACTS CANON ---"""

PATTERN_SNIPS = [
    ("gpio_toggle_skeleton.c",
     """// Structure-only guidance; implement with your register macros:
// status_t bsp_gpio_toggle(uint8_t port, uint8_t pin) {
//   uint32_t mask = 1u << pin;
//   if (port == 0) {
//     uint32_t out = REG(DOUT_A);
//     (out & mask) ? REG(DCLR_A) = mask : REG(DSET_A) = mask;
//   } else {
//     uint32_t out = REG(DOUT_B);
//     (out & mask) ? REG(DCLR_B) = mask : REG(DSET_B) = mask;
//   }
//   return OK;
// }""")
]