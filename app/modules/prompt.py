import json
import os
import sys
import threading
import time
import boto3
from botocore.config import Config
from langchain_aws import BedrockEmbeddings

# Configure boto3 client with increased timeout
config = Config(
    read_timeout=300,  # 5 minutes (default is 60 seconds)
    connect_timeout=10,
    retries={'max_attempts': 3}
)

client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-2",
    config=config,
)

# ---------------- Prompt builders (hardened) ----------------

def build_system_prompt() -> str:

    return """You are generating minimal, portable C11 BSP files for a TI RM46 (Cortex-R4) using the TI ARM CGT toolchain in Code Composer Studio (CCS).

FACTS POLICY (strict):
- Use ONLY the numeric values from provided references (YAML fragments, FACTS CANON, etc.).
- Do NOT invent, transform, or reformat addresses/offsets/bits.
- If any required value is missing, emit a TODO in the FACTS MIRROR and STOP (do not emit files).

VERIFICATION STEP (required):
- Emit EXACTLY this header block BEFORE any files:
===== FACTS MIRROR =====
<key> = <hex or int>
...
===== END FACTS MIRROR =====
- Do NOT place any Doxygen or other comments inside the FACTS MIRROR block. It must contain only the key/value lines described above.

HARD OUTPUT CONTRACT:
- After the FACTS MIRROR, emit ONLY specified files, with these separators:
- Each file MUST be delimited by a line of the form:
===== FILE: <path> =====
- The FIRST line of the entire response MUST be:
===== FILE: <path> =====
  (This is enforced by our post-processor. If you need to include the mirror first, then output the mirror and immediately re-emit the first separator as the next line.)
- No prose, explanations, or extra text outside the FACTS MIRROR block and the file blocks.
- <path> must consist only of the file name, no folder directories or special characters. File organization is handled by our post-processor.
- EVERY generated file MUST end with a single trailing newline character to avoid compiler warnings.

CODING RULES:
- Public headers MUST NOT include vendor headers or vendor-specific types.
- Use ONLY values from FACTS CANON / FACTS MIRROR for base addresses, register offsets, and constant masks/values.
- For GPIO toggling, read DOUT_* (not DIN_*). Prefer DSET/DCLR for writes (avoid read-modify-write on DOUT).
- Add a short provenance comment above each register access:
  // [prov] regs.yaml:<PERIPH>.<REGISTER>
- C standard = C11. Build target = CCS for Cortex-R4 (RM46) with TI ARM CGT.
- Write ISO C90-compatible code:
  - Declare all local variables at the start of a block, before any statements.
  - Do NOT use `for (int i = 0; ...)`; instead:
      int i;
      for (i = 0; i < n; ++i)
- Do NOT use C99-only features (no mixed declarations/statements, no variable-length arrays, etc.).

DOCUMENTATION / DOXYGEN RULES (required):
- All generated C header (.h) and source (.c) files MUST use Doxygen-style comments for public APIs and types.
- Do NOT emit any Doxygen comments in the FACTS MIRROR block.

File-level documentation:
- At the very top of every header file intended for consumption by user code (public headers), emit a Doxygen file block of the form:
  /**
   * @file <filename.h>
   * @brief <one-line summary of this module>
   */
- For modules that define a logical BSP component (e.g. system, clocks, gpio, uart, spi), define exactly one Doxygen group per module in a public header:
  /**
   * @defgroup BSP_<MODULE> <Human-readable module name>
   * @brief <Short description of what this BSP module provides.>
   * @{
   */
  ... public declarations ...
  /** @} */ /* end of BSP_<MODULE> */
- All public functions, types, and macros belonging to a module MUST be associated with the appropriate group using @ingroup BSP_<MODULE>.

Function documentation:
- Immediately before every function that can be called by user code (public API), emit a Doxygen comment block with:
  - @brief: a concise one-line summary.
  - A longer description paragraph when nontrivial behavior or ordering requirements exist.
  - One @param entry for each parameter, in order, describing its purpose and expected units/range.
  - An @return entry for non-void functions describing the meaning of the return value and error codes.
  - @return may be omitted for void functions.
  - @ingroup BSP_<MODULE> to associate it with its module group.
  - Use @note and/or @warning when there are important constraints (e.g. “must be called after BSP_SystemInit()”, “not IRQ-safe”, “blocking until transfer completes”).
- For interrupt handlers or weak hook functions, document the expected usage pattern (e.g. “User may override this weak symbol to handle <IRQ>.”).

Type and struct documentation:
- For every typedef, struct, union, or enum that appears in a public header:
  - Precede it with a Doxygen block containing at least @brief and @ingroup BSP_<MODULE>.
  - For structs and unions, document each member either using trailing Doxygen comments of the form:
      type member; /**< description of member */
    or via @var entries in the main block when appropriate.
- For enums, briefly describe the enum as a whole and ensure each enumerator has either a trailing /**< description */ or is explained in the surrounding text.

Macro and constant documentation:
- For any macro or constant intended for user code (e.g. configuration values, bit masks, helper macros), provide a Doxygen description:
  #define BSP_<MODULE>_FOO  (0x01u) /**< Short description of what this macro controls. */
- Avoid undocumented public macros; if a macro is not meant for public use, keep it in a source file or mark it with a brief comment indicating it is internal.

Examples (when appropriate):
- Where helpful and not overly long, include short @code ... @endcode examples in the documentation of key init or usage functions, showing the typical call sequence (e.g. system init, clock init, GPIO init, then use).

ASSEMBLY / LINKER NOTES:
- For startup assembly (start.s) you MUST use TI ARM CGT assembler syntax:
  - Use directives like `.sect`, `.align`, `.global`, `.ref`, `.long`.
  - Use `;` for comments (not `/* */`).
  - Use a literal-pool style load for linker symbols, e.g.:
      LDR   SP, stack_addr
    ...
  stack_addr:
      .long end_of_stack
- For linker scripts, emit a TI-compatible linker command file named `linker.cmd` using MEMORY and SECTIONS blocks:
  - The syntax is compatible with standard GNU ld-style MEMORY/SECTIONS, which TI’s linker also accepts.
"""



def build_user_prompt(soc_yaml: str, regs_yaml: str, irq_yaml: str = None) -> str:
    return """
    You are generating portable C11 BSP driver files for a SINGLE TI RM46 (Cortex-R4) peripheral.

You MUST obey the global FACTS POLICY, HARD OUTPUT CONTRACT, and CODING RULES from the system prompt.

TASK OVERVIEW
-------------
Generate exactly TWO files for one peripheral:
1) <periph>.h  - public header
2) <periph>.c  - implementation

The peripheral is described by:
- A single peripheral entry from soc.yaml
- The corresponding register block from regs.yaml
- (Optional) the referenced interrupt entries from irq.yaml (only if soc.irq_ref is non-empty)

You must:
- Mirror ALL numeric constants you use (addresses, offsets, masks, bit values) in the FACTS MIRROR first.
- Use ONLY those mirrored constants in the C code.
- Implement a peripheral-specific init function that performs ALL required LOCAL initialization
  (for example, for GIO/GPIO: set GCR0).
- Assume global/system-level init (PCR PS power-up, system clocks, CLKCNTL, PLL configuration,
  VIM vector table init, CPU IRQ enable, etc.) is handled in separate system/clock code and MUST NOT be duplicated here.
- Ensure BOTH generated files end with a single trailing newline.

SYSTEM / CLOCK / INTERRUPT ASSUMPTIONS
-------------------------------------
- RM46 does NOT use an NVIC. Interrupts are managed by the VIM interrupt controller.
- VIM driver code is generated separately (system-level) and provides this API:

    int vim_register_isr(uint32_t channel_id, void (*isr)(void));
    int vim_enable_channel(uint32_t channel_id);
    int vim_disable_channel(uint32_t channel_id);

- Peripheral drivers MUST NOT initialize the VIM vector table or globally enable CPU IRQs.
- Peripheral drivers MAY register their ISR(s) and enable/disable their VIM channels using the VIM API ABOVE,
  but ONLY if irq.yaml IDs are provided.

CLOCK SERVICE ASSUMPTIONS (MANDATORY)
------------------------------------
- A shared clock service module (clock.c / clock.h) is generated separately and provides:

    typedef enum clock_ref_t clock_ref_t;

    int clock_enable(clock_ref_t ref);
    uint32_t clock_get_hz(clock_ref_t ref);

- clock_ref_t follow the following naming convention.
  - Normalize enum names deterministically:
  CLOCKREF_<UPPERCASE_REF>
  - Replace non-alphanumeric with underscore

- Peripheral drivers MUST call clock_enable() for their required clock reference(s)
  before accessing any peripheral registers.

- Peripheral drivers MUST use clock_get_hz() when computing baud rates, prescalers,
  timeouts, or other clock-derived values.

- Peripheral drivers MUST NOT:
    - Touch SYSTEM clock registers directly
      (CSDIS/CDDIS/GHVSRC/CLKCNTL/VCLKASRC/RCLKSRC/VCLKACON1 or related SET/CLR registers)
    - Call any clock configuration/modification APIs
      (clock_configure*, clock_set_*, clock_configure_profile, etc.)

- If clocks are used in the peripheral, "clock.h" MUST be included in the generated <periph>.c file.

INPUT SHAPES
------------
You are given up to three YAML fragments:

1) soc.yaml fragment (only this peripheral):

  soc.peripherals[*]:
    - name: string
    - type: string          # gpio|uart|spi|i2c|adc|timer|can|...
    - instance: integer
    - regs_ref: string
    - irq_ref: [string...]
    - clock_ref: string
    - x-ext: object

For this task, interpret the following clock metadata:
- soc.peripherals[*].clock_ref
- OPTIONAL: soc.peripherals[*].x-ext.clock_refs: [string...] (if present, multiple required clocks)

2) regs.yaml fragment (only this peripheral):

  peripherals:
    <regs_ref>:
      base_address: "0x........"
      desc: "..."
      registers:
        <REGISTER_NAME>:
          offset: "0x...."
          access: RW|R|W|RO|WO|RC
          reset:  "0x........"
          desc:   "..."

3) irq.yaml fragment (optional):

  irqs:
    - name: string
      id: integer
      peripheral_refs: [string...]
      desc: string

If soc.irq_ref is non-empty but irq.yaml is NOT provided:
- You MUST NOT invent interrupt IDs.
- ISR helpers must accept uint32_t channel_id OR return an error.

FACTS MIRROR REQUIREMENTS
-------------------------
Before emitting any files, you MUST populate the FACTS MIRROR with every numeric constant you will use,
pulled directly from YAML.

You MUST NOT invent numeric values.

If required numeric data is missing for any register access:
- Add TODO entries to the FACTS MIRROR
- STOP after the FACTS MIRROR (do NOT emit files)

This STRICTLY includes specific bits in registers. Do not invent these.

PERIPHERAL INIT REQUIREMENTS (UPDATED)
--------------------------------------
In <periph>_init():

1) FIRST, enable required clocks:
   - Call clock_enable() using the peripheral’s clock_ref.
   - If x-ext.clock_refs exists, call clock_enable() for each entry in order.

2) THEN, perform peripheral-local register initialization:
   - Apply x-ext.init register operations in order.
   - Do NOT perform any system-level or clock-tree configuration.

DRIVER FUNCTION DISCOVERY (REQUIRED)
-----------------------------------
You MUST derive the public API from the register map, not from a fixed template.

- Inspect ALL register names/descriptions and classify them into roles:
  - configuration / control
  - data I/O
  - status / flags / errors
  - interrupt enable / disable / status
  - timers / counters
  - DMA / triggers / events
  - test / diagnostic / loopback / DFT

- For each role with meaningful registers, design 1–3 thin wrapper functions.
- Prefer MORE small wrappers over large ones.
- If semantics are unclear, MAY omit but MUST document omission in comments.

BLOCKING / POLL-WAIT REQUIREMENTS (MANDATORY)
---------------------------------------------
If the peripheral exposes ANY registers that:
- indicate readiness / availability / completion (status, flags, busy bits), AND
- support data movement or state transitions,

then you MUST implement at least ONE blocking (poll-wait) API that:

1) Polls on one or more hardware status bits
2) Includes a bounded timeout (cycle counter or iteration count)
3) Returns success/failure (or bytes transferred)
4) NEVER spins forever

You MUST:
- Implement a reusable internal wait helper (static function)
- Use only register bits discovered from regs.yaml
- Document which status bits are polled and why

Interrupt-driven or DMA APIs MAY also be provided, but do NOT replace blocking APIs.

INTERRUPT SUPPORT REQUIREMENTS (WHEN irq_ref IS PRESENT)
--------------------------------------------------------
If soc.peripherals[*].irq_ref is non-empty:

- Add ISR registration helpers.
- Do NOT initialize vector tables or enable global IRQs.

At minimum, provide:
  typedef void (*<periph>_isr_t)(void);
  int <periph>_register_isr(uint32_t channel_id, <periph>_isr_t isr);
  int <periph>_enable_irq(uint32_t channel_id);
  int <periph>_disable_irq(uint32_t channel_id);

Use vim_* APIs exclusively.

INTERNAL TEST / LOOPBACK / DFT SUPPORT (MANDATORY WHEN PRESENT)
--------------------------------------------------------------
If regs.yaml contains registers whose name or description indicates:
- loopback
- test
- diagnostic
- DFT
- self-test
- internal routing

then you MUST:
1) Expose a public configuration API to enable/disable that functionality
2) Implement at least ONE helper function demonstrating its use
3) Prefer a self-test that exercises data-path registers using the blocking APIs

If no such registers exist, do nothing.

OUTPUT CONTRACT (PERIPHERAL-SPECIFIC)
-------------------------------------
After the FACTS MIRROR, emit exactly TWO files:

  ===== FILE: <periph>.h =====
  ===== FILE: <periph>.c =====

Where:
- <periph> is soc.peripherals[*].name lowercased
- No other files may be emitted

Add provenance comments above each register access:
  // [prov] regs.yaml:<PERIPH>.<REGISTER>

CODING RULES
------------
- C11, but ISO C90-compatible style
- Declare locals at block start
- Public headers MUST NOT include vendor headers
- Use <stdint.h>
- Use ONLY FACTS MIRROR constants
- You may define:
    #define REG32(addr) (*(volatile uint32_t *)(addr))
- Each file must end with a trailing newline

DRIVER DESIGN REQUIREMENTS
--------------------------
Header (<periph>.h):
- include guard
- declare: void <periph>_init(void);
- expose derived low-level APIs
- expose blocking APIs when required
- expose test/loopback APIs when present
- declare ISR helpers when irq_ref present

Source (<periph>.c):
- include <stdint.h> and "<periph>.h"
- define base + offsets macros from FACTS MIRROR
- implement init as:
    - clock_enable() calls
    - x-ext.init register writes
- clear/read flags as required
- implement all declared functions
- each function must touch hardware OR VIM API

IF REQUIRED DATA IS MISSING
---------------------------
If YAML lacks required numeric data:
- Populate FACTS MIRROR with TODOs
- STOP after the FACTS MIRROR
- Do NOT emit FILE blocks

INPUTS
------
soc.yaml fragment:
%s

regs.yaml fragment:
%s

(optional) irq.yaml fragment:
%s


 """ % (soc_yaml, regs_yaml, "" if irq_yaml is None else irq_yaml)

def build_clock_prompt(soc_yaml: str, regs_yaml: str, bus_yaml: str):
    return """
    You are generating portable C11 BSP CLOCK SERVICE files for TI Hercules RM46 (Cortex-R4).

    You MUST obey the global FACTS POLICY, HARD OUTPUT CONTRACT, and CODING RULES from the system prompt.

    TASK OVERVIEW
    -------------
    Generate exactly TWO files for the shared clock service module:
    1) clock.h  - public header
    2) clock.c  - implementation

    This module is NOT a single peripheral driver. It is a shared service used by all peripheral drivers.

    You will be given:
    - A slice of soc.yaml listing peripherals (for discovering which clock_ref values exist).
    - A slice of bus.yaml describing clock sources, domains, gates, constraints, and known frequencies/dividers.
    - A slice of regs.yaml describing the SYSTEM and PCR register blocks used to control clocks.

    You must:
    - Mirror ALL numeric constants you use (addresses, offsets, masks, bit values, frequencies, divider defaults/encodings) in the FACTS MIRROR first.
    - Use ONLY those mirrored constants in the C code.
    - Implement a stable, minimal clock API that peripheral drivers can call to enable and query clocks.
    - Provide OPTIONAL clock modification APIs intended ONLY for application code (main.c), and ensure they are NEVER called from peripheral init code.
    - Ensure BOTH generated files end with a single trailing newline.

    SYSTEM / PERIPHERAL ASSUMPTIONS
    -------------------------------
    - Peripheral drivers are generated separately and MUST NOT touch SYSTEM clock control registers directly
      (CSDIS/CDDIS/GHVSRC/CLKCNTL/VCLKASRC/RCLKSRC/VCLKACON1 and related SET/CLR registers).
    - Peripheral drivers MAY call ONLY these safe clock APIs:
        int clock_enable(clock_ref_t ref);
        uint32_t clock_get_hz(clock_ref_t ref);

    - Peripheral drivers MUST NOT call any clock configuration/modification API (clock_configure*, clock_set_*).
    - Clock configuration/modification APIs are intended ONLY for developer application code
      (e.g., main.c or an application-specific board_init()).

    INPUT SHAPES
    ------------
    You are given up to THREE YAML fragments:

    1) soc.yaml fragment (multiple peripherals):
      soc.peripherals[*]:
        - name: string
        - type: string
        - instance: integer
        - regs_ref: string
        - irq_ref: [string...]
        - clock_ref: string
        - x-ext: object

    For clock discovery, interpret:
    - soc.peripherals[*].clock_ref
    - OPTIONAL: soc.peripherals[*].x-ext.clock_refs: [string...] (if present), representing multiple required clock refs.

    2) bus.yaml fragment (clock topology):
    - sources:
        - name, type, freq_hz, x-ext (may include default_enabled, gate bit, etc.)
    - domains:
        - name, parent, divider
        - x-ext may include:
            clock_domain_id, source_sel_reg, cddis_bit
            divider_reg, divider_field, divider_range, default_divider
            and any divider/source encoding details if provided
    - gates:
        - entries describing SYSTEM.CSDIS and SYSTEM.CDDIS gating bits (active-high disables)
        - optional local divider disables in VCLKACON1
        - optional PCR PS enable policy metadata (do not duplicate PCR PS enabling here unless explicitly required by the clock API)
    - constraints:
        - rules that must be respected (document; enforce only if required numeric encodings exist)

    3) regs.yaml fragment (SYSTEM + PCR):
      peripherals:
        SYSTEM:
          base_address: "0x........"
          registers:
            <REGISTER_NAME>: { offset: "0x....", ... }
        PCR:
          base_address: "0x........"
          registers:
            <REGISTER_NAME>: { offset: "0x....", ... }

    IMPORTANT: regs.yaml may or may not include field encodings (bit positions / masks) for divider/mux fields.
    - If a register bit/field encoding is required for a write and is NOT present, you MUST NOT guess.

    FACTS MIRROR REQUIREMENTS
    -------------------------
    Before emitting any files, you MUST populate the FACTS MIRROR with every numeric constant you will use, pulled directly from YAML.

    You MUST NOT invent numeric values.

    This STRICTLY includes:
    - Base addresses and register offsets
    - Bit masks/bit positions for gate enables/disables (CSDIS/CDDIS and any SET/CLR)
    - Any mux selection encodings you write
    - Any divider field encodings you write
    - Fixed source frequencies (OSCIN, HF_LPO, LF_LPO, etc.)
    - Default_divider values used for frequency computation

    If required numeric data is missing for any register access you plan to perform:
    - Add TODO entries to the FACTS MIRROR
    - STOP after the FACTS MIRROR (do NOT emit files)

    You MAY choose to omit functionality that would require unknown encodings
    (e.g., omit divider programming), and still emit files, as long as you do not touch
    unknown fields and you document the limitation.

    CLOCK API REQUIREMENTS (REQUIRED)
    --------------------------------
    You MUST implement the following:

    1) clock_ref_t enum
    - Create a public enum clock_ref_t in clock.h with one entry per unique clock reference.
    - Discover clock references from soc.yaml:
        - include soc.peripherals[*].clock_ref
        - include all entries from x-ext.clock_refs if present
    - Normalize enum names deterministically:
        CLOCKREF_<UPPERCASE_REF>
        - Replace non-alphanumeric with underscore
    - Enum integer values must be explicit and stable:
        - Sort enum names lexicographically and assign values 0..N-1 in that order.

    2) Enable function (safe)
    int clock_enable(clock_ref_t ref);
    - MUST be idempotent.
    - MUST NEVER disable clocks.
    - MUST only perform enabling actions needed for the referenced clock:
        - clear disable bits for required clock SOURCES (SYSTEM.CSDIS disable bits)
        - clear disable bits for required clock DOMAINS (SYSTEM.CDDIS disable bits)
    - MUST NOT modify dividers/muxes/PLL settings as part of enabling unless bus.yaml explicitly
      identifies them as required enable steps AND provides numeric encodings.
    - Add provenance comment above each register access:
        // [prov] regs.yaml:SYSTEM.<REGISTER>
        // [prov] regs.yaml:PCR.<REGISTER> (only if used)

    3) Frequency query function (safe)
    uint32_t clock_get_hz(clock_ref_t ref);
    - MUST return best-known frequency derived ONLY from YAML facts:
        - If frequency is a fixed source -> return it
        - If derived from parent/divider:
            - If divider value is known (default_divider or explicitly configured value tracked by this module) -> compute
            - If divider encoding is unknown and no default_divider -> return 0 and document
        - If PLL parameters are unknown -> return 0 unless bus.yaml provides a concrete freq_hz for that PLL output
    - MUST NEVER guess.

    CLOCK MODIFICATION API (APPLICATION-ONLY) (REQUIRED IF POSSIBLE)
    ---------------------------------------------------------------
    Provide clock modification APIs that are intended ONLY for developer application code (main.c).
    These functions MUST NOT be called automatically by clock_enable(), clock_get_hz(), or any internal init.
    Peripheral drivers MUST NOT call them.

    Required shape (choose ONE strategy):

    Strategy A (preferred): single config entry point
    - In clock.h:
        typedef struct clock_config_t { ... } clock_config_t;
        int clock_configure(const clock_config_t *cfg);
    - clock_config_t must represent OPTIONAL per-ref settings (e.g., divider selections) and default to "no change".
    - clock_configure() MUST validate inputs and return error without touching hardware if encodings are missing.

    OR

    Strategy B: explicit divider setters
    - In clock.h:
        int clock_set_divider(clock_ref_t ref, uint32_t divider);
    - Implement only for refs that have divider_reg/divider_field encodings present in YAML.
    - For unsupported refs, return error.
    - MUST NOT guess divider field encodings.

    In all cases:
    - Put a prominent comment in clock.h:
      "APPLICATION-ONLY: Do not call from peripheral drivers."
    - Do not call configuration APIs from within clock.c.

    DRIVER FUNCTION DISCOVERY (CLOCK-SPECIFIC) (REQUIRED)
    -----------------------------------------------------
    You MUST derive additional helper functions from bus.yaml content (not a fixed template), such as:
    - per-ref inline wrappers (optional):
        static inline int clock_enable_vclk(void) { return clock_enable(CLOCKREF_VCLK); }
        static inline uint32_t clock_get_vclk_hz(void) { return clock_get_hz(CLOCKREF_VCLK); }

    - If bus.yaml indicates multiple domains/sources are required for a ref, encode that relationship in clock_enable().

    OUTPUT CONTRACT
    ---------------
    After the FACTS MIRROR, emit exactly TWO files:

      ===== FILE: clock.h =====
      ===== FILE: clock.c =====

    No other files may be emitted.

    CODING RULES
    ------------
    - C11, but ISO C90-compatible style
    - Declare locals at block start (no declarations inside for loops)
    - Public headers MUST NOT include vendor headers
    - Use <stdint.h>
    - Use ONLY FACTS MIRROR constants
    - You may define:
        #define REG32(addr) (*(volatile uint32_t *)(addr))
    - Each file must end with a trailing newline

    IMPLEMENTATION REQUIREMENTS
    ---------------------------
    clock.h:
    - include guard
    - declare clock_ref_t enum with explicit values
    - declare required APIs:
        int clock_enable(clock_ref_t ref);
        uint32_t clock_get_hz(clock_ref_t ref);
    - declare application-only config API (Strategy A or B) if possible
    - optional: inline wrappers for common refs

    clock.c:
    - include <stdint.h> and "clock.h"
    - define base + offsets macros from FACTS MIRROR
    - implement register operations with volatile accesses
    - implement clock_enable() and clock_get_hz() as switch(ref) dispatchers
    - implement application-only config API without calling it internally
    - add provenance comments above each register access

    IF REQUIRED DATA IS MISSING
    ---------------------------
    If YAML lacks required numeric data for any register bit/field access you plan to perform:
    - Populate FACTS MIRROR with TODOs
    - STOP after FACTS MIRROR
    - Do NOT emit FILE blocks

    INPUTS
    ------
    soc.yaml fragment:
    %s

    bus.yaml fragment:
    %s

    regs.yaml fragment (SYSTEM + PCR slices):
    %s

    """ % (soc_yaml, bus_yaml, regs_yaml)

def build_vim_prompt(soc_yaml, regs_yaml, irq_yaml):
    
    return """
    You are generating the SYSTEM-LEVEL VIM (Vectored Interrupt Manager) interrupt controller driver for TI RM46 (Cortex-R4).

You MUST obey the global FACTS POLICY, HARD OUTPUT CONTRACT, and CODING RULES from the system prompt.

TASK OVERVIEW
-------------
Generate exactly TWO files:
1) vim.h
2) vim.c

The VIM driver is system-level and MUST:
- Initialize the VIM interrupt vector table in VIM RAM (vectored mode support)
- Provide APIs to register ISRs and enable/disable channels
- Never depend on vendor headers
- Use only constants from YAML inputs (mirrored in FACTS MIRROR)

It MUST NOT:
- Initialize other peripherals (PCR/SYSTEM clocks etc.)
- Implement peripheral-specific ISRs
- Assume an RTOS

INPUT SHAPES
------------
You are given these YAML fragments:

1) soc.yaml fragment containing ONLY the VIM peripheral entry (and optional x-ext metadata):
  soc.peripherals[*]:
    - name: "VIM"
    - type: "vim"
    - regs_ref: "VIM"
    - x-ext: may include:
        vector_table:
          base_address: "0xFFF82000"
          entries: 128
          entry_size_bytes: 4
          phantom_entry: 0
          reserved_channels: [127]

2) regs.yaml fragment containing VIM register blocks:
  peripherals:
    VIM:
      base_address: "0xFFFFFE00"
      registers: { IRQINDEX, FIQINDEX, FIRQPR0..3, REQENASET0..3, REQENACLR0..3, ... CHANCTRL0..31, ... }
    (optional) VIM_PARITY:
      base_address: "0xFFFFFD00"
      registers: { PARCTL, PARFLG, ADDERR, FBPARERR }

3) irq.yaml fragment containing ALL interrupt request assignments for this SoC:
  irqs:
    - name: string
      id: integer    # VIM channel number 0..126
      peripheral_refs: [...]
      desc: string

VIM VECTOR TABLE FACTS
----------------------
- VIM vector table is in RAM at a fixed base address provided in soc.yaml x-ext.vector_table (or otherwise provided explicitly).
- The table is 128 entries x 32-bit.
- Entry 0 is phantom.
- Channel N uses entry (N + 1).
- Channel 127 is reserved/invalid.

FACTS MIRROR REQUIREMENTS
-------------------------
Before emitting any files, you MUST populate the FACTS MIRROR with every numeric constant you will use, pulled directly from YAML:

- VIM base address
- VIM_PARITY base address (if you use it)
- Offsets for every VIM register you access
- Vector table base address
- Entry count (e.g., 128)
- Reserved channel numbers (e.g., 127)
- Any masks/values used for register writes (must come from YAML; do NOT invent)

If required numeric values are not provided, add TODOs and STOP after the FACTS MIRROR.

REQUIRED PUBLIC API (vim.h)
---------------------------
You MUST implement these public APIs:

- typedef void (*vim_isr_t)(void);

- void vim_init(void);
  Initializes the VIM for vectored interrupts:
  - (optional) enables parity before vector table init, ONLY if VIM_PARITY.PARCTL is provided in regs.yaml
  - initializes ALL vector table entries to a default handler
  - does NOT enable any specific interrupt channel by default

- int vim_register_isr(uint32_t channel_id, vim_isr_t isr);
  Stores the ISR address into the vector table entry for channel_id.
  Must reject invalid channel_id (>= entries-1 OR reserved channels).

- int vim_enable_channel(uint32_t channel_id);
  Enables the channel in REQENASET registers.

- int vim_disable_channel(uint32_t channel_id);
  Disables the channel in REQENACLR registers.

OPTIONAL (if register map supports it):
- int vim_set_fiq(uint32_t channel_id, int enable_fiq);
  Uses FIRQPR registers to route a channel to FIQ instead of IRQ.

DEFAULT ISR BEHAVIOR
--------------------
You MUST implement a static default handler:
- void vim_default_isr(void);
The vector table is initialized to this handler.

IMPLEMENTATION REQUIREMENTS (vim.c)
-----------------------------------
- Use REG32 macro for register access.
- Use only FACTS MIRROR constants for addresses/offsets.
- Vector table writes are memory writes:
    VIM_VECTOR_BASE + 4*(channel_id + 1)

- Do NOT use dynamic allocation.
- C90 style variable declarations.

PROVENANCE COMMENTS
-------------------
- For each register access, include:
  // [prov] regs.yaml:VIM.<REGISTER>
- For vector table memory writes, include:
  // [prov] soc.yaml:VIM.x-ext.vector_table (base/entries)

OUTPUT CONTRACT
---------------
After the FACTS MIRROR, emit exactly TWO files:

  ===== FILE: vim.h =====
  ...

  ===== FILE: vim.c =====
  ...

Do NOT emit any other files.

INPUTS
------
soc.yaml fragment for VIM:
%s

regs.yaml fragment for VIM:
%s

irq.yaml fragment (full list):
%s

    """ % (soc_yaml, regs_yaml, irq_yaml)


def build_system_init_prompt(soc_yaml: str, regs_yaml: str):
    return """
    You are generating low-level embedded C startup code for a TI Hercules RM46-like MCU.

You MUST obey the global FACTS POLICY, HARD OUTPUT CONTRACT, and CODING RULES from the system prompt.

You will be given:
- A slice of soc.yaml describing SYSTEM and PCR peripherals.
- A slice of regs.yaml describing the SYSTEM and PCR register blocks.

The YAML follows this schema:

- soc.yaml:
  - soc.peripherals is an array of peripherals.
  - Each peripheral has:
      name: string, e.g. "SYSTEM", "PCR"
      regs_ref: string key that matches peripherals.<name> in regs.yaml
      clock_ref: string (you do not need to use it in this task)
      x-ext: optional object for extra metadata

  - For SYSTEM, x-ext.init is a list of initialization operations.
    Each op has:
      reg: "<PERIPHERAL>.<REGISTER>", e.g. "PCR.PSPWRDWNCLR0"
      op:  "set_bits", "clear_bits", or "write"
      value: 32-bit hex string like "0xFFFFFFFF"

  - For SYSTEM, OPTIONAL x-ext.base_clock_refs is a list of clock references to enable
    at boot as "base clocks" (minimal safe bring-up). Each entry is a string matching
    the clock_ref naming used by the clock module (clock_ref_t values), e.g.:
      x-ext.base_clock_refs: ["HCLK", "VCLK", "HF_LPO", "LF_LPO"]
    If x-ext.base_clock_refs is absent, do not enable any clocks implicitly in system_init.

  - clock_ref_t follow the following naming convention.
      - Normalize enum names deterministically:
      CLOCKREF_<UPPERCASE_REF>
      - Replace non-alphanumeric with underscore

- regs.yaml:
  - peripherals.<name>.base_address is the base address as a hex string.
  - peripherals.<name>.registers.<reg_name>.offset is the offset as a hex string.

CLOCK MODULE INTEGRATION (MANDATORY)
------------------------------------
- A shared clock service module (clock.c / clock.h) is generated separately and provides:

    typedef enum clock_ref_t clock_ref_t;
    int clock_enable(clock_ref_t ref);

- system.c MUST include "clock.h" to call clock_enable().

- system_init() MUST perform ONLY the following clock-related work:
  1) Enable base clocks listed in SYSTEM.x-ext.base_clock_refs by calling clock_enable(ref).
  2) MUST NOT configure/modify clock dividers, PLLs, or muxes here.
  3) MUST NOT call any clock configuration/modification APIs
     (clock_configure*, clock_set_*, clock_configure_profile, etc.).
     Those are APPLICATION-ONLY and must be called by developer code in main.c if desired.

- Peripheral drivers will call clock_enable() for their own clock_ref(s). system_init
  should only ensure minimal base clocks are enabled.

Your task:
- Generate two files: system.h and system.c.
- These files must be self-contained and ISO C90 compatible:
  - Do NOT declare variables inside for loops.
  - Declare all local variables at the top of a block, before any statements.
- Ensure BOTH generated files end with a trailing newline.

FACTS MIRROR REQUIREMENTS (MANDATORY)
-------------------------------------
Before emitting any files, you MUST populate a FACTS MIRROR with every numeric constant you will use,
pulled directly from YAML:
- Base addresses
- Register offsets
- Values written from SYSTEM.x-ext.init

You MUST NOT invent numeric values.

If required numeric data is missing for any register access:
- Add TODO entries to the FACTS MIRROR
- STOP after the FACTS MIRROR (do NOT emit files)

NOTE: clock_enable() calls do not require mirroring numeric constants here, since those are handled
inside the clock module.

Requirements:

1) system.h
-----------
- Provide an include guard.
- Declare:
    void system_init(void);
- Keep the API minimal.

2) system.c
-----------
- Include <stdint.h>, "system.h", and "clock.h".
- Define macros for SYSTEM and PCR base addresses and register offsets using the YAML data, for example:
    #define SYSTEM_BASE 0xFFFFFF00u
    #define SYSTEM_CLKCNTL_OFFSET 0x00D0u
    #define PCR_BASE 0xFFFFE000u
    #define PCR_PSPWRDWNCLR0_OFFSET 0x00A0u
- Use the exact names and values taken from regs.yaml.
- You may define:
    #define REG32(addr) (*(volatile uint32_t *)(addr))

- Implement a static helper to perform a register operation:
    #define OP_SET_BITS   1
    #define OP_CLEAR_BITS 2
    #define OP_WRITE      3

    static void reg_write_op(uint32_t base, uint32_t offset, uint32_t value, int op)
    {
        volatile uint32_t *reg;

        reg = (volatile uint32_t *)(base + offset);

        if (op == OP_SET_BITS) {
            *reg |= value;
        } else if (op == OP_CLEAR_BITS) {
            *reg &= ~value;
        } else if (op == OP_WRITE) {
            *reg = value;
        }
    }

- Implement void system_init(void) that performs, in this exact order:
  1) Apply SYSTEM.x-ext.init register operations in order via reg_write_op(...).
  2) Enable base clocks:
     - If SYSTEM.x-ext.base_clock_refs exists, call clock_enable() for each listed ref, in order.
     - If absent, do nothing (do NOT enable clocks implicitly).

- The effective behavior MUST match exactly:
  - The provided SYSTEM.x-ext.init list
  - The provided SYSTEM.x-ext.base_clock_refs list (if present)

- You MAY add a comment such as:
    /* Clock configuration (PLL/dividers/mux) is application-owned; see clock_configure* APIs in clock.h (do not call here). */

3) Assumptions:
---------------
- The linker script and assembly startup (Reset_Handler, stack pointer setup) are handled elsewhere in start.s and linker.cmd.
- Reset_Handler_C (in entry.c) will call system_init() before main().

OUTPUT CONTRACT
---------------
After the FACTS MIRROR, output exactly:
  ===== FILE: system.h =====
  ===== FILE: system.c =====

No other files may be emitted.

Here is soc.yaml (relevant slice):

%s

Here is regs.yaml (relevant slice):

%s

Now, output FACTS MIRROR, then system.h followed by system.c, obeying the global HARD OUTPUT CONTRACT.


    """ % (soc_yaml, regs_yaml)

def build_linker_prompt(memmap_yaml: str):
    return """You are generating a TI ARM CGT linker command file (linker.cmd) for an ARM-based TI Hercules RM46-like MCU, built with the TI ARM CGT linker (armcl) from Code Composer Studio (CCS).

GLOBAL RULES (from system prompt)
---------------------------------
- Use ONLY numeric values taken directly from MEMMAP.yaml.
- You MAY form simple arithmetic expressions like <origin> + <length> using those exact literals, but you MUST NOT hand-compute new hex literals.
- Do NOT use GNU ld-only constructs (for example: ENTRY(), KEEP(), ORIGIN(), LENGTH(), LOADADDR()).
- The output file must be valid TI linker command file syntax.
- The generated linker.cmd file MUST end with a trailing newline.

GOAL
----
Generate a single TI-compatible linker command file named linker.cmd that:

1) Defines FLASH and RAM memory regions from MEMMAP.yaml.
2) Places:
   - The interrupt vector table (.intvecs) in FLASH at the beginning of the image.
   - Code (.text) and read-only data (.const, .cinit, .pinit) in FLASH.
   - Initialized data (.data) in RAM, with load image in FLASH.
   - Zero-initialized data (.bss plus COMMON symbols) in RAM.
   - Heap (.sysmem) and stack (.stack) in RAM.
3) Defines the linker symbols used by entry.c and start.s:
   - start_of_data_in_flash
   - start_of_data, end_of_data
   - start_of_bss, end_of_bss
   - end_of_stack
4) Uses TI ARM CGT linker syntax, not GNU ld.

MEMMAP.yaml SHAPE
-----------------
You are given a slice of MEMMAP.yaml with this structure:

ir_schema_version: "1.1.0"
memory:
  - name:   "FLASH"
    origin: "0x00000000"
    length: "0x00150000"
    attrs:  "rx"
  - name:   "RAM"
    origin: "0x08000000"
    length: "0x00030000"
    attrs:  "rwx"
link:
  vector_table: "0x00000000"   # informational, you do not have to use it
startup:
  reset_handler: "0x00001000"  # informational, you do not have to use it

For this task:
- memory is an ARRAY of regions.
- Use the region whose name is "FLASH" for code.
- Use the region whose name is "RAM" for data/stack/heap.
- Use origin and length exactly as given (hex strings or size strings).
- You do NOT need to use link.vector_table or startup.reset_handler; they are just for context.

TI LINKER SYNTAX REQUIREMENTS
-----------------------------
1) MEMORY block:
   - Use TI-style attributes in parentheses: RX and RWX (UPPERCASE).
   - Example shape:

     MEMORY
     {
         FLASH (RX)  : origin = <FLASH.origin>, length = <FLASH.length>
         RAM   (RWX) : origin = <RAM.origin>,   length = <RAM.length>
     }

   - <FLASH.origin> and <FLASH.length> must be copied directly or used inside simple expressions; do NOT recalc them into new hex values.
   - <RAM.origin> and <RAM.length> must likewise come from MEMMAP.yaml.

2) Entry point:
   - You MUST force the entry point to Reset_Handler using a TI linker option line in the command file.
   - Emit exactly one of the following (prefer the first form):
       --entry_point=Reset_Handler
     or:
       -e Reset_Handler
   - This entry-point directive must appear near the top of the command file, before the MEMORY block.
   - Do NOT use GNU’s ENTRY() directive.

3) Required absolute symbols:
   - Define an absolute symbol for top-of-stack based on the RAM region:

       end_of_stack = <RAM.origin> + <RAM.length>;

     where both operands come directly from MEMMAP.yaml (you may write the sum as an expression, do NOT replace it with a single computed literal).

   - For .data and .bss, use TI’s section operator syntax to define:

       LOAD_START(start_of_data_in_flash)
       RUN_START(start_of_data)
       RUN_END(end_of_data)

       RUN_START(start_of_bss)
       RUN_END(end_of_bss)

     These operators must be attached to the .data and .bss section declarations as shown below.

4) SECTIONS layout (TI style, aligned with HALCoGen conventions):
   - Use a SECTIONS block with the following intent:

     SECTIONS
     {
         /* Vector table at start of FLASH */
         .intvecs :
         {
             . = ALIGN(4);
             /* Do NOT use *(.intvecs) here; TI linker automatically
                aggregates this section by name. */
         } > FLASH

         /* Code in FLASH */
         .text :
         {
             . = ALIGN(4);
             /* No wildcard collectors; TI linker will place .text here. */
         } > FLASH

         /* Read-only data in FLASH */
         .const :
         {
             . = ALIGN(4);
             /* No *(.const*); TI linker will place .const here. */
         } > FLASH

         .cinit :
         {
             . = ALIGN(4);
             /* IMPORTANT: do not try to collect *(.cinit*); .cinit is a
                special TI runtime section and the linker manages it. */
         } > FLASH

         .pinit :
         {
             . = ALIGN(4);
             /* No *(.pinit*); TI linker will place .pinit here. */
         } > FLASH

         /* Initialized data: FLASH load, RAM run */
         .data :
         {
             . = ALIGN(4);
             /* Leave body empty; linker will place .data here. */
         } load = FLASH, run = RAM,
           LOAD_START(start_of_data_in_flash),
           RUN_START(start_of_data),
           RUN_END(end_of_data)

         /* Zero-init data in RAM */
         .bss :
         {
             . = ALIGN(4);
             /* Do not use *(.bss*) or *(COMMON); TI linker collects them. */
         } > RAM,
           RUN_START(start_of_bss),
           RUN_END(end_of_bss)

         /* Stack: size is driven by --stack_size option */
         .stack :
         {
             __stack_start = .;
             /* Optional: you may set end_of_stack = .; here instead of
                using the absolute symbol expression, but do not use
                ORIGIN() or LENGTH(). */
         } > RAM

         /* Heap (.sysmem): size is driven by --heap_size */
         .sysmem :
         {
             __sysmem_start = .;
         } > RAM
     }


   - You MUST:
     - Place .intvecs in FLASH and ensure it comes before code.
     - Place .text, .const, .cinit, .pinit into FLASH.
     - Place .data in RAM with load = FLASH, run = RAM, and attach
       LOAD_START/RUN_START/RUN_END for the data symbols.
     - Place .bss in RAM (including COMMON symbols) with RUN_START/RUN_END
       for the bss symbols.
     - Provide .stack and .sysmem sections in RAM.
     - DO NOT use wildcard collectors like *(.intvecs), *(.text*), *(.const*),
       *(.cinit*), *(.pinit*), *(.bss*), or *(COMMON) inside the section bodies.
     - Simply defining the section name (e.g., .text : { } > FLASH) is enough;
       the TI linker automatically places contributions for that section.
     - For .cinit in particular, do NOT attempt to collect *(.cinit*); the TI
       linker treats .cinit specially and will ignore such specifiers with a
       warning.

5) GNU ld constructs to AVOID:
   - Do NOT use:
     - ENTRY(...)
     - KEEP(...)
     - ORIGIN(...)
     - LENGTH(...)
     - LOADADDR(...)
   - Rely on:
     - MEMORY, origin, length
     - load =, run = on sections
     - LOAD_START(), RUN_START(), RUN_END() section operators
     - Plain symbol assignments like:
         end_of_stack = 0x08000000 + 0x00030000;

6) File output contract:
   - You MUST produce exactly one FILE block named:

       ===== FILE: linker.cmd =====

     followed by the complete TI linker command file contents.
   - The command file MUST end with a trailing newline.
   - No additional files or prose are allowed outside the FACTS MIRROR and this FILE block.

INPUT
-----
Here is MEMMAP.yaml (relevant slice):

%s

OUTPUT
------
- A single FILE block for linker.cmd using TI ARM CGT linker syntax and TI-style section names (.intvecs, .text, .const, .cinit, .pinit, .data, .bss, .sysmem, .stack), obeying all rules above.
""" % (memmap_yaml)


def build_entry_prompt():
    return """
    You are generating the C reset handler for a TI Hercules RM46-like MCU.

Goal:
- Generate a C file entry.c that defines Reset_Handler_C().
- Reset_Handler_C must:
  1. Initialize the .data section in RAM by copying from flash.
  2. Zero the .bss section.
  3. Call system_init() to bring up clocks/peripherals.
  4. Call main().
  5. End in an infinite loop if main() returns.

You are targeting the TI/CCS ARM toolchain, which defaults to ISO C90/C89. Therefore:

- All code MUST be ISO C90 compatible:
  - Do NOT use `for (int i = 0; …)`; instead declare loop counters before the loop:
      int i;
      for (i = 0; i < n; ++i) { ... }
  - Do NOT mix declarations and statements; declare all variables at the top of a block.
  - Do NOT use C99-only features.
- Ensure entry.c ends with a trailing newline character.

Behavioral reference (do NOT copy verbatim, but match functionality):

  // Higher level Reset Handler
  // This exists to avoid any more assembly code than needed.

  #include "util.h"
  #include <stddef.h>
  #include <stdint.h>

  // Linker defined addresses
  extern uint32_t start_of_data;
  extern uint32_t end_of_data;

  extern uint32_t start_of_data_in_flash;

  extern uint32_t end_of_stack;

  extern uint32_t start_of_bss;
  extern uint32_t end_of_bss;

  // User defined entrypoint
  extern int main();

  void Reset_Handler_C() {
      size_t data_size = (size_t)(&end_of_data - &start_of_data);
      memcpy(&start_of_data, &start_of_data_in_flash, data_size);

      size_t bss_size = (size_t)(&end_of_bss - &start_of_bss);
      memset(&start_of_bss, 0, bss_size);

      main();

      while (1) {
          // Ensure we don't go into UB
      }
  }

Requirements for your generated entry.c:
----------------------------------------
- Include headers:
  - <stdint.h> and <stddef.h> for integer and size types.
  - <string.h> OR a project-specific "util.h" that provides memcpy and memset.
- Declare these linker symbols as extern (they are defined in the linker script):
  - extern uint32_t start_of_data;
  - extern uint32_t end_of_data;
  - extern uint32_t start_of_data_in_flash;
  - extern uint32_t start_of_bss;
  - extern uint32_t end_of_bss;
  - You may also declare extern uint32_t end_of_stack; if desired (for debugging), but you do not need to use it.

- Declare:
  - extern void system_init(void);
  - extern int main(void);

- Implement void Reset_Handler_C(void) that:
  1. Computes the size (in bytes) of .data using start_of_data and end_of_data.
  2. Calls memcpy to copy initialized data from flash:
      - Destination: &start_of_data
      - Source:      &start_of_data_in_flash
      - Size:        data_size
  3. Computes the size of .bss using start_of_bss and end_of_bss.
  4. Calls memset to zero the entire .bss region.
  5. Calls system_init();
  6. Calls main();
  7. If main() returns, enters an infinite loop (for (;;){}) to avoid undefined behavior.

- All local variables must be declared at the top of Reset_Handler_C before any statements.

Output:
- A single FILE block for entry.c, nothing else (besides the FACTS MIRROR required by the system prompt).


    """

def build_start_asm_prompt():
    return f"""
    You are generating ARM assembly startup code for a TI Hercules RM46-like MCU, using the TI ARM CGT assembler (armcl) from Code Composer Studio (CCS).

GOAL
----
Generate a minimal start.s file that:

- Defines an interrupt vector table section called .intvecs.
- Places the initial stack pointer and Reset_Handler in .intvecs in the first two entries.
- Provides minimal placeholder vectors for other exceptions (they may all branch to Reset_Handler).
- Defines a Reset_Handler label in a .text section.
- In Reset_Handler:
  - Loads the address end_of_stack (a linker-defined symbol) into SP.
  - Branches with link to Reset_Handler_C (a C function implemented elsewhere).
  - If Reset_Handler_C returns, loops forever.

ASSEMBLER / SYNTAX REQUIREMENTS
-------------------------------
- You MUST use TI ARM CGT assembler syntax, not GNU.
- DO NOT use:
  - .syntax
  - .cpu
  - .section
  - .word
- INSTEAD, use:
  - .sect   for sections
  - .align  for alignment
  - .long   for 32-bit constants
  - .global for global symbols
  - .ref    for referenced external symbols
- All labels should end with ':' and be placed at the start of a line.

VECTOR TABLE LAYOUT
-------------------
- The vector table must be emitted in a section named ".intvecs":

    .sect   ".intvecs"
    .align  4

- The first entries should be (in order):

    0x00: initial SP value (symbol end_of_stack)
    0x04: Reset vector (address of Reset_Handler)
    0x08: Undefined instruction vector
    0x0C: Supervisor call (SVC) vector
    0x10: Prefetch abort vector
    0x14: Data abort vector
    0x18: Reserved word
    0x1C: IRQ vector
    0x20: FIQ vector

- For this minimal BSP, ALL exception vectors except the initial SP may simply point to Reset_Handler (or a single error handler label that loops forever).

- Example shape (do NOT copy verbatim, but match the structure):

    .sect   ".intvecs"
    .align  4

    .long   end_of_stack      ; initial stack pointer
    .long   Reset_Handler     ; reset
    .long   Reset_Handler     ; undef
    .long   Reset_Handler     ; svc
    .long   Reset_Handler     ; prefetch abort
    .long   Reset_Handler     ; data abort
    .long   0                 ; reserved
    .long   Reset_Handler     ; irq
    .long   Reset_Handler     ; fiq

CODE SECTION AND RESET HANDLER
------------------------------
- After the vector table, define a .text section for the actual Reset_Handler code:

    .sect   ".text"
    .align  4

- You MUST declare:

    .global  Reset_Handler
    .ref     Reset_Handler_C
    .ref     end_of_stack

- Implement Reset_Handler:

  - Use an address label to load end_of_stack into SP using TI assembler syntax.
    One safe pattern is:

        Reset_Handler:
            LDR   SP, stack_addr
            BL    Reset_Handler_C

        Reset_Loop:
            B     Reset_Loop

        stack_addr:
            .long end_of_stack

    This avoids GNU-style "LDR SP, =symbol" syntax and uses only TI-supported directives.

- Reset_Handler_C is a C function defined in entry.c and must be declared .ref so the linker can resolve it.
- end_of_stack is a symbol defined in the linker command file and must be declared .ref as well.

OUTPUT CONTRACT
---------------
- You MUST produce exactly one FILE block:

    ===== FILE: start.s =====
    <assembly here>

- Use only TI assembler directives (.sect, .align, .long, .global, .ref) and ARM instructions (LDR, BL, B).
- Do NOT emit any C code or additional files.
- The file must end with a trailing newline to avoid compiler warnings.

Now generate start.s that satisfies all requirements above.

    """

from enum import Enum

class Model(Enum):
    HAIKU_3_0 = "haiku3.0"
    HAIKU_4_5 = "haiku4.5"
    SONNET_3_5 = "sonnet3.5"
    SONNET_4_5 = "sonnet4.5"

    def get_model_id(self):
        model_ids = {
            "haiku3.0": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "sonnet3.5": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "haiku4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        }

        return model_ids[self.value]


from typing import TypedDict, Literal


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


async def invoke_model(model: Model, max_tokens: int, messages: list[Message]) -> str:
    body = {
        "max_tokens": max_tokens,
        "anthropic_version": "bedrock-2023-05-31",
        "messages": messages,
    }

    # Start progress indicator
    stop_spinner = threading.Event()
    spinner_thread = threading.Thread(target=_show_progress, args=(stop_spinner,))
    spinner_thread.daemon = True
    spinner_thread.start()

    try:
        response = client.invoke_model(modelId=model.get_model_id(), body=json.dumps(body))
        return response
    finally:
        # Stop the spinner
        stop_spinner.set()
        spinner_thread.join(timeout=1)
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * 50 + '\r')
        sys.stdout.flush()


def _show_progress(stop_event):
    """Display a simple progress indicator while waiting for API response."""
    spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    idx = 0
    start_time = time.time()
    
    while not stop_event.is_set():
        elapsed = int(time.time() - start_time)
        minutes, seconds = divmod(elapsed, 60)
        spinner = spinner_chars[idx % len(spinner_chars)]
        sys.stdout.write(f'\r{spinner} Waiting for response... ({minutes:02d}:{seconds:02d})')
        sys.stdout.flush()
        idx += 1
        time.sleep(0.1)

