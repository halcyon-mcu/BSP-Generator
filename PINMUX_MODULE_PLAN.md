# PINMUX Module Generation Plan

## Overview
This document outlines the plan to implement automated PINMUX (pin multiplexing) module generation for the BSP Generator. The pinmux module is critical for configuring pins to their correct functional modes before peripheral use.

---

## Problem Statement

### Current Issue
Peripherals like GIO, SCI, LIN, etc. cannot function until their pins are properly multiplexed. Currently:
- ✅ Pin 142 worked for GPIO previously (likely defaulted to GPIO mode or was manually configured)
- ❌ Generated drivers don't configure pinmux automatically
- ❌ Each peripheral assumes pins are already in the correct mode
- ❌ No systematic way to ensure pin configuration

### Example: GIO on Pin 142
```yaml
# From pinmux.yaml
- package_pin: 142
  name: "N2HET1[20]"           # DEFAULT function
  board:
    net: "GIOB_2"
  functions:
    - { af: "0", signal: "N2HET1[20]", mux: { register: "PINMMR34", bit: 16 } }
    - { af: "1", signal: "EPWM6B", mux: { register: "PINMMR34", bit: 17 } }
    # Note: No explicit GPIO function listed, but may work if bits are cleared
```

---

## Architecture

### Module Structure

```
pinmux/
├── reg_pinmux.h          # IOMM register map (PINMMR0-38, KICK registers)
├── pinmux_driver.h       # Public API
├── pinmux_driver.c       # Implementation
└── pinmux_config.h       # Board-specific pin configurations
```

### Key Components

#### 1. IOMM Register Map (`reg_pinmux.h`)
```c
typedef struct {
    volatile uint32_t REVISION_REG;     /**< 0x00 */
    volatile uint32_t RESERVED0[7];     /**< 0x04-0x1C */
    volatile uint32_t ENDIAN_REG;       /**< 0x20 */
    volatile uint32_t RESERVED1[2];     /**< 0x24-0x28 */
    volatile uint32_t KICK_REG0;        /**< 0x38 - Write unlock key 1 */
    volatile uint32_t KICK_REG1;        /**< 0x3C - Write unlock key 2 */
    volatile uint32_t RESERVED2[40];    /**< 0x40-0xDC */
    volatile uint32_t ERR_RAW_STATUS_REG;   /**< 0xE0 */
    volatile uint32_t ERR_ENABLED_STATUS_REG; /**< 0xE4 */
    volatile uint32_t ERR_ENABLE_REG;   /**< 0xE8 */
    volatile uint32_t ERR_ENABLE_CLR_REG; /**< 0xEC */
    volatile uint32_t RESERVED3[4];     /**< 0xF0-0xFC */
    volatile uint32_t FAULT_ADDRESS_REG; /**< 0x100 */
    volatile uint32_t FAULT_STATUS_REG; /**< 0x104 */
    volatile uint32_t FAULT_CLEAR_REG;  /**< 0x108 */
    volatile uint32_t RESERVED4[5];     /**< 0x10C-0x11C */
    volatile uint32_t PINMMR[39];       /**< 0x120-0x1B8 - PINMMR0 to PINMMR38 */
} IOMM_REG_MAP_t;

#define IOMM_BASE_ADDR  0xFFFF1C00U
#define iommREG  ((IOMM_REG_MAP_t *)IOMM_BASE_ADDR)

/* KICK register unlock values */
#define PINMUX_KICK0_UNLOCK  0x83E70B13U
#define PINMUX_KICK1_UNLOCK  0x95A4F1E0U
#define PINMUX_KICK_LOCK     0x00000000U
```

#### 2. Pinmux Driver API (`pinmux_driver.h`)
```c
typedef enum {
    PINMUX_STATUS_OK,
    PINMUX_STATUS_ERROR,
    PINMUX_STATUS_LOCKED,
    PINMUX_STATUS_INVALID_PIN
} PINMUX_Status_t;

typedef struct {
    uint8_t package_pin;      /**< Physical pin number */
    uint8_t register_index;   /**< PINMMR register index (0-38) */
    uint8_t start_bit;        /**< Starting bit in PINMMR */
    uint8_t function_select;  /**< Function to select (0-4) */
} PINMUX_Config_t;

/* Initialize pinmux module (unlock KICK registers) */
void PINMUX_Init(void);

/* Configure a single pin */
PINMUX_Status_t PINMUX_ConfigurePin(const PINMUX_Config_t *config);

/* Lock pinmux registers (call after all configuration) */
void PINMUX_Lock(void);

/* Unlock pinmux registers */
PINMUX_Status_t PINMUX_Unlock(void);

/* Apply board-specific default configuration */
void PINMUX_ApplyBoardConfig(void);
```

#### 3. Board Configuration (`pinmux_config.h`)
Auto-generated from `pinmux.yaml` and `board.yaml`:

```c
/* Board-specific pinmux configuration */
extern const PINMUX_Config_t BOARD_PINMUX_CONFIG[];
extern const uint32_t BOARD_PINMUX_CONFIG_COUNT;

/* Quick-access configs for common peripherals */
extern const PINMUX_Config_t PINMUX_CFG_LED_GIOB2;     /* Pin 142 */
extern const PINMUX_Config_t PINMUX_CFG_LIN1_RX;       /* Pin 131 */
extern const PINMUX_Config_t PINMUX_CFG_LIN1_TX;       /* Pin 132 */
extern const PINMUX_Config_t PINMUX_CFG_SCI_RX;        /* Pin 38 */
extern const PINMUX_Config_t PINMUX_CFG_SCI_TX;        /* Pin 39 */
```

---

## Implementation Steps

### Phase 1: Register Map Generation (Agent: general-purpose)
**Input**: `regs.yaml` (IOMM section)
**Output**: `reg_pinmux.h`

**Tasks**:
1. Extract IOMM register definitions from `regs.yaml`
2. Generate register map struct with proper offsets
3. Define KICK unlock constants
4. Add PINMMR register array (0-38)

**Agent Usage**:
```python
agent = Task(
    subagent_type="general-purpose",
    description="Generate PINMUX register header",
    prompt="""
    Generate reg_pinmux.h from IOMM register definitions.
    Include KICK unlock mechanism and PINMMR array.
    Follow the volatile uint32_t member pattern.
    """
)
```

### Phase 2: Configuration Data Generation (Agent: general-purpose)
**Input**: `pinmux.yaml`, `board.yaml`
**Output**: `pinmux_config.c`, `pinmux_config.h`

**Tasks**:
1. Parse pinmux.yaml for all pin definitions
2. For each pin used on the board (from board.yaml):
   - Determine correct function (GPIO, UART, SPI, etc.)
   - Extract PINMMR register and bit information
   - Create PINMUX_Config_t entry
3. Generate arrays of configurations
4. Create named constants for commonly-used pins

**Agent Usage**:
```python
agent = Task(
    subagent_type="general-purpose",
    description="Generate PINMUX config data",
    prompt="""
    Parse pinmux.yaml and board.yaml to generate pinmux configuration.
    Create PINMUX_Config_t entries for all board-used pins.
    Generate both array and named constant access patterns.
    """
)
```

### Phase 3: Driver Implementation (Agent: general-purpose)
**Input**: API specification, register map
**Output**: `pinmux_driver.c`, `pinmux_driver.h`

**Tasks**:
1. Implement KICK unlock/lock mechanism
2. Implement pin configuration function
3. Implement batch configuration from array
4. Add safety checks and error handling

**Agent Usage**:
```python
agent = Task(
    subagent_type="general-purpose",
    description="Implement PINMUX driver",
    prompt="""
    Implement pinmux driver with KICK unlock/lock and pin configuration.
    Follow C89 style, proper error handling, and safety checks.
    Include PINMUX_Init(), PINMUX_ConfigurePin(), PINMUX_ApplyBoardConfig().
    """
)
```

### Phase 4: Integration with Existing Drivers (Agent: general-purpose)
**Input**: All generated peripheral drivers
**Output**: Updated driver init functions

**Tasks**:
For each peripheral driver (GIO, SCI, LIN, etc.):
1. Identify required pins from hardware.yaml
2. Add pinmux configuration call in XXX_Init()
3. Ensure pinmux happens BEFORE peripheral register configuration

**Example**:
```c
void GIO_Init(void)
{
    /* Configure pins for GPIO function FIRST */
    PINMUX_ConfigurePin(&PINMUX_CFG_LED_GIOB2);

    /* Then configure GIO registers */
    volatile GIO_REG_MAP_t* gio = gioREG;
    gio->GIOGCR0 = 0x00000001U;
    /* ... rest of init ... */
}
```

**Agent Usage**:
```python
agent = Task(
    subagent_type="general-purpose",
    description="Integrate PINMUX into drivers",
    prompt="""
    For each peripheral driver (GIO, SCI, LIN, etc.):
    1. Add #include "pinmux_driver.h"
    2. Add PINMUX_ConfigurePin() calls in XXX_Init()
    3. Place pinmux config BEFORE any register writes
    4. Use named configs from pinmux_config.h

    Only configure pins that are actually used by the peripheral.
    """
)
```

---

## Dependency Management

### Module Dependencies
```
PINMUX
  ├─ No dependencies (core module)
  └─ Must be initialized FIRST in init sequence

GIO
  ├─ Depends on: SYSTEM, VIM, PLL
  └─ Depends on: PINMUX (NEW)

SCI
  ├─ Depends on: PLL
  └─ Depends on: PINMUX (NEW)

LIN
  ├─ Depends on: VIM, PLL
  └─ Depends on: PINMUX (NEW)
```

### Updated Initialization Order
```c
int main(void) {
    /* Core initialization */
    system_init();
    PLL_Init();
    vim_init();

    /* PINMUX MUST come before peripherals */
    PINMUX_Init();              // NEW: Unlock and initialize
    PINMUX_ApplyBoardConfig();  // NEW: Apply board defaults

    /* Peripheral initialization (pins already muxed) */
    PCR_Init();
    SCI_Init();   // Pins already configured
    GIO_Init();   // Pins already configured
    LIN_Init();   // Pins already configured

    /* Lock pinmux after all config */
    PINMUX_Lock();  // NEW: Prevent accidental changes

    /* Application code */
    ...
}
```

---

## Data Flow

```
pinmux.yaml + board.yaml
        ↓
   [Parser Agent]
        ↓
  Pin Usage Analysis
        ↓
   [Config Generator]
        ↓
  pinmux_config.c/.h  ← Contains PINMUX_Config_t arrays
        ↓
   [Driver Generator]
        ↓
  pinmux_driver.c/.h  ← Implements configuration API
        ↓
   [Integration Agent]
        ↓
  Updated XXX_Init()  ← Calls PINMUX_ConfigurePin()
```

---

## Critical Implementation Details

### 1. KICK Register Unlock Sequence
```c
void PINMUX_Unlock(void)
{
    iommREG->KICK_REG0 = PINMUX_KICK0_UNLOCK;  /* Step 1 */
    iommREG->KICK_REG1 = PINMUX_KICK1_UNLOCK;  /* Step 2 */
}

void PINMUX_Lock(void)
{
    iommREG->KICK_REG0 = PINMUX_KICK_LOCK;
    iommREG->KICK_REG1 = PINMUX_KICK_LOCK;
}
```

### 2. Pin Configuration Pattern
```c
PINMUX_Status_t PINMUX_ConfigurePin(const PINMUX_Config_t *config)
{
    uint32_t reg_idx, bit_pos, func_sel;
    uint32_t mask, value;

    if (!config) return PINMUX_STATUS_ERROR;

    reg_idx = config->register_index;
    bit_pos = config->start_bit;
    func_sel = config->function_select;

    /* Each pin uses 5 bits for function selection (0-4 for AF0-AF4) */
    mask = 0x1FU << bit_pos;           /* 5-bit mask */
    value = (func_sel & 0x1FU) << bit_pos;

    /* Clear and set */
    iommREG->PINMMR[reg_idx] &= ~mask;
    iommREG->PINMMR[reg_idx] |= value;

    return PINMUX_STATUS_OK;
}
```

### 3. Auto-Configuration from Board Data
```c
void PINMUX_ApplyBoardConfig(void)
{
    uint32_t i;

    /* Apply all board-specific pin configurations */
    for (i = 0; i < BOARD_PINMUX_CONFIG_COUNT; i++) {
        PINMUX_ConfigurePin(&BOARD_PINMUX_CONFIG[i]);
    }
}
```

---

## Testing Strategy

### Test 1: Manual Pin Configuration
```c
/* Test manual configuration */
PINMUX_Init();

PINMUX_Config_t led_pin = {
    .package_pin = 142,
    .register_index = 34,  /* PINMMR34 */
    .start_bit = 16,
    .function_select = 0   /* Default function (check if this enables GPIO) */
};

PINMUX_ConfigurePin(&led_pin);
GIO_Init();
/* Test LED blinking */
```

### Test 2: Board Auto-Configuration
```c
/* Test automatic board configuration */
PINMUX_Init();
PINMUX_ApplyBoardConfig();  /* Configures all board pins */
GIO_Init();
SCI_Init();
/* Test all peripherals */
```

### Test 3: Lock Mechanism
```c
/* Test lock prevents changes */
PINMUX_Init();
PINMUX_ConfigurePin(&some_pin);
PINMUX_Lock();

/* This should fail or have no effect */
PINMUX_ConfigurePin(&another_pin);
```

---

## Validation Checklist

- [ ] IOMM register map matches datasheet
- [ ] KICK unlock sequence implemented correctly
- [ ] All board pins have configuration entries
- [ ] Pin configurations match pinmux.yaml exactly
- [ ] PINMUX initializes before all peripherals
- [ ] Lock mechanism prevents accidental changes
- [ ] GPIO pins work after pinmux configuration
- [ ] UART/SCI pins work after pinmux configuration
- [ ] No hard-coded magic numbers (use generated constants)

---

## Future Enhancements

1. **Runtime Pin Reconfiguration**: Allow changing pin functions at runtime
2. **Pin Conflict Detection**: Detect when multiple peripherals try to use same pin
3. **Low-Power Mode**: Support for pin power-down modes
4. **Debug Support**: Dump current pinmux state for debugging

---

## References

- RM46L852 TRM Chapter 5: I/O Multiplexing and Control Module
- `pinmux.yaml`: Pin multiplexing database
- `board.yaml`: Board-specific pin usage
- `regs.yaml`: IOMM register definitions
