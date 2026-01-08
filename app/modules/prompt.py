import json
import os
import boto3
from langchain_aws import BedrockEmbeddings

client = boto3.client(
    service_name="bedrock-runtime",
    region_name="us-east-2",
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



def build_user_prompt(soc_yaml: str, regs_yaml: str) -> str:
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

You must:
- Mirror ALL numeric constants you use (addresses, offsets, masks, bit values) in the FACTS MIRROR first.
- Use ONLY those mirrored constants in the C code.
- Implement a peripheral-specific init function that performs ALL required LOCAL initialization (for example, for GIO/GPIO: set GCR0).
- Assume global/system-level init (CLKCNTL, PCR, etc.) is handled in a separate system.c/system_init() and MUST NOT be duplicated here.
- Ensure BOTH generated files end with a single trailing newline.

INPUT SHAPES
------------
You are given two YAML fragments:

1) soc.yaml fragment (only this peripheral):

Conceptual schema:

  soc.peripherals[*]:
    - name: string          # e.g., "GIO"
    - type: string          # normalized type: gpio|uart|spi|i2c|adc|timer|can|...
    - instance: integer     # 1..N
    - regs_ref: string      # key into regs.yaml: peripherals.<regs_ref>
    - irq_ref: [string...]  # (optional) keys into irq.yaml
    - clock_ref: string     # domain/gate name from bus.yaml
    - x-ext: object         # extension for codegen metadata

For this task, the ONLY x-ext field you must interpret is:

  x-ext.init:
    - A list of register operations that must be applied in the peripheral's init function.
    - Each entry has:
        reg:   "<REGS_REF>.<REGISTER>"   # e.g., "GIO.GCR0"
        op:    "set_bits" | "clear_bits" | "write"
        value: "0x........"              # hex string

2) regs.yaml fragment (only this peripheral):

Conceptual schema:

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

FACTS MIRROR REQUIREMENTS
-------------------------
Before emitting any files, you MUST populate the FACTS MIRROR with every numeric constant you will use, pulled directly from the YAML:

- Base address of this peripheral (peripherals.<regs_ref>.base_address)
- Offsets of every register you reference
- Any masks/values from x-ext.init[*].value

Naming in the FACTS MIRROR is up to you, but should be clear and stable, for example:

  GIO_BASE = 0xFFF7BC00
  GIO_GCR0_OFFSET = 0x0000
  GIO_GCR0_INIT_MASK = 0x00000001

You MUST NOT invent numeric values; if something is needed but not provided, put a TODO entry in the mirror and STOP (do not emit files), as per the system prompt.

When choosing which constants to mirror, you MUST:
- First inspect the FULL register list under peripherals.<regs_ref>.registers.
- Decide which registers will be used by your driver API based on their names and descriptions.
- Mirror all numeric values required to implement that API (base + offsets + masks/values from x-ext.init and from any obvious bitfields you need).

DRIVER FUNCTION DISCOVERY (REQUIRED)
------------------------------------
You MUST derive the public API from the register map, not from a fixed template.

For this peripheral:

- Inspect ALL register names and descriptions and classify them into roles, for example:
  - configuration / mode / control (e.g., GCR, CTRL, FORMAT)
  - data input/output (e.g., DAT, TX, RX, BUF, DOUT, DIN)
  - status / error / flags (e.g., STAT, FLG, ERR)
  - interrupt enable/disable and status (e.g., INTENA, INTENASET, INTENACLR, LVL, LVLSET, LVLCLR, INTFLG)
  - timer/counter/compare/capture (e.g., CNT, CMP, PERIOD)
  - DMA / trigger / event control (if present)
- For each role with clearly meaningful registers, design 1–3 thin wrapper functions that:
  - Perform obvious operations such as:
    * configure / set mode
    * enable / disable a feature or channel
    * start / stop a peripheral or timer
    * set / get a value (data, period, baud, etc.)
    * clear status or interrupt flags
    * query status / error conditions
  - Hide raw bit-manipulation behind named functions where reasonable.
- Prefer including MORE small, simple wrapper functions rather than too few. Do NOT leave obviously useful registers without any API coverage, unless the semantics are unclear.
- If a register appears to have unclear or highly specialized semantics from its name/desc, you MAY omit it from the API and briefly note this in a comment in the C file.

You MUST also use soc.peripherals[*].type to shape the API:
- type: "uart" → include send/receive, status, and configuration helpers appropriate to the registers.
- type: "spi" or "mibspi" → include transfer/config helpers (mode, frame size, chip-select, etc.) appropriate to the registers.
- type: "i2c" → include start/stop, address, read/write, and status/flag helpers as supported by the registers.
- type: "timer" → include configure/start/stop, set period, read counter, and interrupt/flag helpers as supported.
- type: "adc" → include channel/configuration, start conversion, read result, status/flag helpers as supported.
- type: "can" → include init/config, transmit, receive, and status/flag helpers as supported.
If the type is not recognized, design a generic but reasonably complete low-level API around the available control/data/status/interrupt registers.

OUTPUT CONTRACT (PERIPHERAL-SPECIFIC)
-------------------------------------
After the FACTS MIRROR (and respecting the global HARD OUTPUT CONTRACT), you MUST emit exactly TWO files:

  ===== FILE: <periph>.h =====
  ...header content...

  ===== FILE: <periph>.c =====
  ...source content...

Where:
- <periph> SHOULD be derived from soc.peripherals[*].name, lowercased:
  - name: "GIO"     → files: "gio.h" and "gio.c"
  - name: "MIBSPI1" → files: "mibspi1.h" and "mibspi1.c"
- Do NOT emit any other files.
- Add provenance comments above each register access in the C file:
  // [prov] regs.yaml:<PERIPH>.<REGISTER>

CODING RULES (REMINDERS)
------------------------
These reinforce the system prompt for this specific task:

- C standard = C11, but code must be ISO C90-compatible in style:
  - Declare all local variables at the start of a block.
  - Do NOT use: for (int i = 0; ...).
    Instead:
      int i;
      for (i = 0; i < n; ++i) { ... }
- Public headers MUST NOT include vendor headers or vendor-specific types.
- Use only standard integer types (`uint32_t`, etc.) from <stdint.h>.
- Use ONLY values listed in the FACTS MIRROR for:
  - Base addresses
  - Register offsets
  - Masks/values for writes
- For register access in the C file, you may use a macro like:
    #define REG32(addr) (*(volatile uint32_t *)(addr))
  and then REG32(BASE + OFFSET) inside functions.
- Ensure each generated file ends with a trailing newline.

DRIVER DESIGN REQUIREMENTS
--------------------------
Header file (<periph>.h):

- Provide a standard include guard.
- Include <stdint.h> if needed.
- Declare at least:
    void <lowercase_name>_init(void);
  For example, for "GIO" → void gio_init(void);

- You MUST design a reasonably complete, low-level but ergonomic API surface based ONLY on registers present in regs.yaml:
  - Use the DRIVER FUNCTION DISCOVERY rules above.
  - Every clearly meaningful control/data/status/interrupt feature should have at least one public function that exercises it.
  - Keep functions thin (mostly one or a few register accesses), but cover the full obvious feature set of the peripheral.

For GPIO-like peripherals (type "gpio" or name "GIO") you MUST:
- Expose port as an argument rather than generating separate functions for each port.
- For example, you MUST at least provide:
    void gio_set_dir(uint32_t port, uint32_t pin, uint32_t output);
    void gio_set(uint32_t port, uint32_t pin);
    void gio_clear(uint32_t port, uint32_t pin);
    void gio_toggle(uint32_t port, uint32_t pin);
    uint32_t gio_read(uint32_t port, uint32_t pin);
  where port is an integer or enum mapping to Port A/B/etc.
- Internally, map (port, pin) to the correct DIR/DSET/DCLR/DOUT/DIN registers using the offsets from regs.yaml and the FACTS MIRROR.
- DO NOT create separate public APIs like gio_set_a() and gio_set_b(); always route through a port parameter.
- In addition to the basic pin-level APIs above, if the register map exposes features such as:
    - pull-up / pull-down enable/disable,
    - open-drain control,
    - input qualification / debounce,
    - polarity / inversion,
    - interrupt enable/disable, level, and flags,
  you MUST add corresponding configuration/status helpers that wrap those registers.

Source file (<periph>.c):

- Include:
    #include <stdint.h>
    #include "<periph>.h"

- Define macros for:
  - Base address, using FACTS MIRROR value:
      #define GIO_BASE 0xFFF7BC00u
  - Register offsets for any registers you touch:
      #define GIO_GCR0_OFFSET 0x0000u
      #define GIO_DIR_A_OFFSET 0x0034u
      ...

- Optionally define convenience macros/helpers:
    #define REG32(addr) (*(volatile uint32_t *)(addr))

- Implement:
    void <lowercase_name>_init(void);
    // plus ALL public API functions declared in the header.

The init function MUST:
- Apply all operations from soc.x-ext.init[], in order.
  For each entry:
  - reg: "<REGS_REF>.<REGISTER>"
  - op: "set_bits"  → REG32(BASE + OFFSET) |= VALUE;
  - op: "clear_bits"→ REG32(BASE + OFFSET) &= ~VALUE;
  - op: "write"     → REG32(BASE + OFFSET)  = VALUE;
- Use only the base address and offsets from regs.yaml (reflected via FACTS MIRROR).
- Emit a provenance comment on each access, for example:
    // [prov] regs.yaml:GIO.GCR0
    REG32(GIO_BASE + GIO_GCR0_OFFSET) |= GIO_GCR0_INIT_MASK;

- Do NOT perform:
  - SYSTEM-level initialization (CLKCNTL, PCR, etc.).
  - Stack setup, data/bss init, or vector table work.
  Those are handled by other files (start.s, entry.c, system.c).

- You MUST implement all declared public functions, and each function MUST touch at least one hardware register (read or write) using FACTS MIRROR constants.
- When selecting which registers to use, consider the entire register block; err on the side of using all clearly purposeful (non-reserved) registers in at least one helper, unless their semantics are unclear.

IF REQUIRED DATA IS MISSING
---------------------------
If the YAML does not contain enough information to:
- Determine the peripheral's base address, or
- Determine the offsets and masks for x-ext.init registers

then:
- Add TODO entries to the FACTS MIRROR describing what is missing.
- STOP after the FACTS MIRROR (do NOT emit any FILE blocks), as per the global FACTS POLICY.

INPUTS
------
Below are the concrete YAML fragments for this call.

soc.yaml fragment for this peripheral:
%s

regs.yaml fragment for this peripheral:
%s
    """ % (soc_yaml, regs_yaml)


def build_system_init_prompt(soc_yaml: str, regs_yaml: str):
    return """
    You are generating low-level embedded C startup code for a TI Hercules RM46-like MCU.

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

- regs.yaml:
  - peripherals.<name>.base_address is the base address as a hex string.
  - peripherals.<name>.registers.<reg_name>.offset is the offset as a hex string.

Your task:
- Generate two files: system.h and system.c.
- These files must be self-contained and ISO C90 compatible:
  - Do NOT declare variables inside for loops.
  - Declare all local variables at the top of a block, before any statements.
- Ensure BOTH generated files end with a trailing newline.

Requirements:

1) system.h
-----------
- Provide an include guard.
- Declare:
    void system_init(void);
- Optionally, you may declare helper functions as static inline if needed, but keep the API minimal.

2) system.c
-----------
- Include <stdint.h> and "system.h".
- Define macros for SYSTEM and PCR base addresses and register offsets using the YAML data, for example:
    #define SYSTEM_BASE 0xFFFFFF00u
    #define SYSTEM_CLKCNTL_OFFSET 0x00D0u
    #define PCR_BASE 0xFFFFE000u
    #define PCR_PSPWRDWNCLR0_OFFSET 0x00A0u
- Use the exact names and values taken from regs.yaml.
- You may define a helper macro:
    #define REG32(addr) (*(volatile uint32_t *)(addr))

- Implement a static helper to perform a register operation, for example:
    #define OP_SET_BITS  1
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

- Implement void system_init(void) that:
  - Conceptually iterates over SYSTEM.x-ext.init in order.
  - For each entry, hardcode the mapping from the "reg" string to:
      - A base address (SYSTEM_BASE or PCR_BASE)
      - A register offset macro (e.g. SYSTEM_CLKCNTL_OFFSET, PCR_PSPWRDWNCLR0_OFFSET)
      - An operation kind (set_bits, clear_bits, write)
      - A value constant (from YAML)
  - Emit direct calls to reg_write_op(...) with the correct base, offset, value, and op kind.

- The effective behavior should match:
  - PCR.PSPWRDWNCLR0/1/2/3 |= 0xFFFFFFFF  (power up all peripheral quadrants)
  - SYSTEM.CLKCNTL |= 0x00000100         (enable the global peripheral enable bit)

- You may also add a placeholder function such as:
    static void system_configure_clocks(void) { /* TODO */ }
  and call it from system_init(), but keep it empty.

3) Assumptions:
---------------
- The linker script and assembly startup (Reset_Handler, stack pointer setup) are handled elsewhere in start.s and linker.cmd.
- Reset_Handler_C (in entry.c) will call system_init() before main().

Here is soc.yaml (relevant slice):

%s

Here is regs.yaml (relevant slice):

%s

Now, output system.h followed by system.c, obeying the global HARD OUTPUT CONTRACT.
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

    response = client.invoke_model(modelId=model.get_model_id(), body=json.dumps(body))
    return response
