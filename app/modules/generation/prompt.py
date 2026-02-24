import json
import os
import sys
import threading
import time
import asyncio
import boto3
from botocore.config import Config
from langchain_aws import BedrockEmbeddings

# Configure boto3 client with increased timeout
config = Config(
    read_timeout=300,  # 5 minutes (default is 60 seconds)
    connect_timeout=10,
    retries={'max_attempts': 3}
)

# Check for custom bearer token in environment
bearer_token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK')
access_key = os.environ.get('AWS_ACCESS_KEY_ID')
secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
region = os.environ.get('AWS_REGION', 'us-east-2')

# Create boto3 client with authentication
if bearer_token:
    # Use bearer token as session token with explicit credentials
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=bearer_token,
        region_name=region,
    )
    client = session.client(
        service_name="bedrock-runtime",
        config=config,
    )
elif access_key and secret_key:
    # Use explicit credentials without session token
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=config,
    )
else:
    # Fall back to default credential chain (IAM role, ~/.aws/credentials, etc.)
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region,
        config=config,
    )

# ---------------- Prompt builders (hardened) ----------------

def build_system_prompt() -> str:

    return """You are generating minimal, portable C11 BSP files for a TI RM46 (Cortex-R4) using the TI ARM CGT toolchain in Code Composer Studio (CCS).

FACTS POLICY (strict):
- Use ONLY the numeric values from provided references (YAML fragments, FACTS CANON, etc.).
- Do NOT invent, transform, or reformat addresses/offsets/bits.
- If any required value is missing, emit a TODO in the FACTS MIRROR and STOP (do not emit files).

TYPE SAFETY POLICY (strict):
- For Pass 1 (Manifest): Declare ALL custom types (enums, structs, typedefs) in the "types" array
- For Pass 2 (Driver Code): ONLY use types that are declared in the manifest or standard C types
- Do NOT invent new types, enum values, or struct members
- If a type is needed but not in the manifest, use a standard C type (uint32_t, int, etc.) or add a TODO comment
- Violating this policy will cause compilation errors

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
- <path> may include directory prefixes (e.g., "source/foo.c" or "include/foo.h"). Use forward slashes for directory separators.
- EVERY generated file MUST end with a single trailing newline character to avoid compiler warnings.

CODING RULES:
- Public headers MUST NOT include vendor headers or vendor-specific types.
- Use ONLY values from FACTS CANON / FACTS MIRROR for base addresses, register offsets, and constant masks/values.
- For GPIO toggling, read DOUT_* (not DIN_*). Prefer DSET/DCLR for writes (avoid read-modify-write on DOUT).
- Add a short provenance comment above each register access:
  // [prov] regs.yaml:<PERIPH>.<REGISTER>
- C standard = C11. Build target = CCS for Cortex-R4 (RM46) with TI ARM CGT.
- Write ISO C90/C89-compatible code (TI compiler defaults to C89 mode):
  - ALL variable declarations MUST be at the beginning of their block, before any executable statements.
  - Do NOT use `for (int i = 0; ...)` or `for (uint32_t i = 0; ...)`:
      // WRONG:
      for (uint32_t i = 0; i < n; i++) {{ }}

      // CORRECT:
      uint32_t i;
      for (i = 0; i < n; i++) {{ }}

  - Do NOT declare variables after any executable statement:
      // WRONG:
      some_function();
      uint32_t x = 5;  // Declaration after statement!

      // CORRECT:
      uint32_t x;
      some_function();
      x = 5;

  - Static file-scope variables are automatically zero-initialized:
      // CORRECT (no explicit initialization needed):
      static MyStruct_t g_state;

      // AVOID (may cause issues with complex types):
      static MyStruct_t g_state = {{0}};

- Do NOT use C99-only features (no mixed declarations/statements, no variable-length arrays, no designated initializers where not supported).

RESERVED KEYWORD AVOIDANCE (CRITICAL for TI ARM Compiler):
- Do NOT use reserved keywords as function parameter names or local variable names.
- Prohibited keywords include:
  * 'interrupt' - causes "invalid storage class for a parameter" errors
  * 'inline', 'restrict', 'register' (as variable names)
  * Any compiler-specific keywords
- Use alternative names instead:
  * Instead of 'interrupt': use 'flags', 'int_flags', 'irq_flags', 'event', etc.
  * Instead of 'register': use 'reg_value', 'reg', 'config', etc.
- This applies to ALL function signatures in headers and implementations.

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
- The PLL module (pll_driver.c / pll_driver.h) provides clock services:

    typedef enum clock_domain_t clock_domain_t;

    int PLL_EnableClock(clock_domain_t domain);
    uint32_t PLL_GetFrequency(clock_domain_t domain);

- clock_domain_t follow the following naming convention:
  - Normalize enum names deterministically:
  CLOCKDOMAIN_<UPPERCASE_REF>
  - Replace non-alphanumeric with underscore

- Peripheral drivers MUST call PLL_EnableClock() for their required clock domain(s)
  before accessing any peripheral registers.

- Peripheral drivers MUST use PLL_GetFrequency() when computing baud rates, prescalers,
  timeouts, or other clock-derived values.

- Peripheral drivers MUST NOT:
    - Touch SYSTEM clock registers directly
      (CSDIS/CDDIS/GHVSRC/CLKCNTL/VCLKASRC/RCLKSRC/VCLKACON1 or related SET/CLR registers)
    - Touch PLL configuration registers directly
      (PLLCTL1/PLLCTL2/PLLCTL3 or related registers)
    - Call any clock configuration/modification APIs
      (PLL_Configure*, PLL_Set*, etc.)

- If clocks are used in the peripheral, "pll_driver.h" MUST be included in the generated <periph>.c file.

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

REGISTER ACCESS SEMANTICS (MANDATORY):
--------------------------------------
The 'access' field in regs.yaml specifies how to use each register. Follow these rules EXACTLY:

| Type | Read Behavior        | Write Behavior           | Usage Rules                                    |
|------|---------------------|--------------------------|------------------------------------------------|
| RW   | Get current value   | Set new value            | Normal read/write register                     |
| RO   | Get status/data     | No effect (or bus error) | NEVER generate write/set functions             |
| WO   | Undefined value     | Set value/trigger action | NEVER generate read/get functions              |
| RC   | Get flags & clear   | No effect                | Read ONCE per event, store value, don't re-read |
| W1C  | Get current flags   | Write 1 to clear bit     | Write 1 to clear, 0 = no change                |

CRITICAL RULES:

1. RC (Read-to-Clear) Registers:
   - Reading the register automatically clears the bits
   - MUST read only ONCE per event and store the value
   - DO NOT re-read or you'll lose flags
   - Example:
     ✓ CORRECT:
       uint32_t status = PERIPHERAL->STATUS_RC_REG;  // Read once
       if (status & FLAG_BIT) { /* handle */ }

     ✗ INCORRECT:
       if (PERIPHERAL->STATUS_RC_REG & FLAG_BIT) { /* handle */ }  // Clears on read
       if (PERIPHERAL->STATUS_RC_REG & OTHER_BIT) { /* handle */ } // Re-read clears again!

2. W1C (Write-1-to-Clear) Registers:
   - To clear bit N, write (1 << N)
   - Writing 0 has no effect on that bit
   - Example:
     ✓ CORRECT:
       PERIPHERAL->STATUS_W1C_REG = (1u << 3);  // Clear bit 3

     ✗ INCORRECT:
       PERIPHERAL->STATUS_W1C_REG &= ~(1u << 3);  // Does nothing (0 = no change)

3. RO (Read-Only) Registers:
   - NEVER generate Set/Write/Clear functions
   - Only generate Get/Read functions
   - Example: Status registers, ID registers, counter values

4. WO (Write-Only) Registers:
   - NEVER generate Get/Read functions
   - Only generate Set/Write functions
   - Reading returns undefined value
   - Example: Command registers, trigger registers

PERIPHERAL INIT REQUIREMENTS (UPDATED)
--------------------------------------
In <periph>_init():

1) FIRST, enable required clocks:
   - Call PLL_EnableClock() using the peripheral's clock_ref.
   - If x-ext.clock_refs exists, call PLL_EnableClock() for each entry in order.

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
- Use <stdint.h> for uint8_t, uint32_t, int32_t, etc.
- Use <stddef.h> for NULL, size_t, ptrdiff_t
- Use <stdbool.h> for bool, true, false (if needed)
- Include all dependencies needed for types used in the file
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

def build_clock_prompt(soc_yaml: str, regs_yaml: str, bus_yaml: str, manifest: dict = None):
    # Extract typedef names from manifest (Pass 1 generated headers)
    pll_typedef = "pll_reg_map_t"  # Default fallback
    system_typedef = "SYSTEM_REGS_t"  # Default fallback

    if manifest:
        api_catalog = manifest.get("api_catalog", {})
        pll_entry = api_catalog.get("PLL", {})
        system_entry = api_catalog.get("SYSTEM", {})

        if "register_typedef" in pll_entry:
            pll_typedef = pll_entry["register_typedef"]

        # Try new array format first, fall back to old single typedef
        typedefs = system_entry.get("register_typedefs", [])
        if typedefs:
            system_typedef = typedefs[0]  # Use primary typedef
        else:
            # Fallback for old manifests
            if "register_typedef" in system_entry:
                system_typedef = system_entry["register_typedef"]

    typedef_section = f"""
    REGISTER ACCESS (MANDATORY - CRITICAL FOR COMPILATION):
    -------------------------------------------------------
    You MUST use register headers generated in Pass 1 (Discovery) for all register access.

    REQUIRED INCLUDES in clock.c:
    - #include "reg_pll.h"      (for PLL registers)
    - #include "reg_system.h"   (for SYSTEM registers)

    REGISTER TYPEDEF NAMES (FROM PASS 1 - USE EXACTLY AS SHOWN):
    - PLL register struct typedef: {pll_typedef}
    - SYSTEM register struct typedef: {system_typedef}

    REQUIRED PATTERN for declaring register pointers:
    ```c
    static {pll_typedef} * const PLL = ({pll_typedef} *)0xFFFFE100u;
    static {system_typedef} * const SYS = ({system_typedef} *)0xFFFFFF00u;
    ```

    CRITICAL: You MUST use these EXACT typedef names. They come from Pass 1 generated headers.
    DO NOT guess, modify, or assume different typedef names - use these names EXACTLY.

    DO NOT use inline #define macros for register access:
    ```c
    // WRONG - Do not do this:
    #define SYSTEM_BASE 0xFFFFFF00u
    #define REG32(addr) (*(volatile uint32_t *)(addr))
    ```
    """

    return typedef_section + """
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

    1) clock_ref_t enum - COMPREHENSIVE DOMAIN SUPPORT
    - Create a public enum clock_ref_t in clock.h with one entry per unique clock reference.
    - Discover clock references from soc.yaml:
        - include soc.peripherals[*].clock_ref
        - include all entries from x-ext.clock_refs if present
    - CRITICAL: Support ALL standard RM46 clock domains, including:
        * GCLK (global clock - typically PLL output)
        * HCLK (high-speed bus clock)
        * VCLK (peripheral bus clock 1)
        * VCLK2 (peripheral bus clock 2)
        * VCLK3 (peripheral bus clock 3)
        * VCLK4 (peripheral bus clock 4)
        * RTICLK (RTI/timer clock)
        * HF_LPO (high-frequency low-power oscillator)
        * LF_LPO (low-frequency low-power oscillator)
        * OSCIN (external oscillator input)
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

    3) Frequency query function (safe) - DYNAMIC CALCULATION REQUIRED
    uint32_t clock_get_hz(clock_ref_t ref);
    - MUST return actual frequency by READING HARDWARE REGISTERS dynamically
    - For fixed sources (OSCIN, HF_LPO, LF_LPO):
        - Return the fixed frequency from bus.yaml
    - For PLL-derived clocks:
        - READ PLL registers (PLLCTL1, PLLCTL2) to extract:
          * NR (reference divider) from PLLCTL1 bits [0:5]
          * NF (feedback multiplier) from PLLCTL1 bits [8:15]
          * R (post divider) from PLLCTL2 bits [0:3]
          * OD (output divider) from PLLCTL2 bits [24:27]
        - Calculate PLL output frequency using formula from datasheet:
          PLLCLK = (OSCIN * NF) / (NR * R)  or similar
        - If register bit positions not in regs.yaml, document limitation and return 0
    - For clock domains with dividers (GCLK, HCLK, VCLK, VCLK2, VCLK3, VCLK4):
        - READ divider registers (CLKCNTL, VCLKASRC, etc.) from SYSTEM
        - Calculate: domain_freq = parent_freq / (divider + 1) or per encoding
    - For RTI clock (RTICLK):
        - READ RTICLK divider from SYSTEM registers
        - Calculate from VCLK or appropriate parent
    - MUST NEVER use hardcoded frequencies or assumptions
    - MUST NEVER guess register encodings - if unknown, return 0 with TODO comment

    CLOCK MODIFICATION API (APPLICATION-ONLY) (REQUIRED)
    ----------------------------------------------------
    Provide clock modification APIs that are intended ONLY for developer application code (main.c).
    These functions MUST NOT be called automatically by clock_enable(), clock_get_hz(), or any internal init.
    Peripheral drivers MUST NOT call them.

    REQUIRED PLL CONFIGURATION FUNCTIONS:
    You MUST provide these PLL configuration functions if PLL register encodings are available:

    1) PLL Multiplier/Divider Setters:
       int clock_set_pll_multiplier(uint8_t nf);  // Set NF (feedback multiplier)
       int clock_set_pll_ref_divider(uint8_t nr); // Set NR (reference divider)
       int clock_set_pll_post_divider(uint8_t r); // Set R (post divider)
       int clock_set_pll_output_divider(uint8_t od); // Set OD (output divider)

    2) High-Level PLL Configuration:
       int clock_configure_pll(uint32_t target_freq_hz);
       - Calculate NR, NF, R, OD to achieve target frequency
       - Validate against PLL constraints from bus.yaml
       - Apply configuration to PLL registers
       - Return error if target frequency not achievable

    REQUIRED DIVIDER CONFIGURATION FUNCTIONS:
    You MUST provide divider setters for each configurable clock domain:

    For each domain with configurable divider (GCLK, HCLK, VCLK, VCLK2, VCLK3, VCLK4, RTICLK):
       int clock_set_<domain>_divider(uint32_t divider);
       - Write divider value to appropriate SYSTEM register field
       - Return error if divider out of range or encoding unknown

    Example:
       int clock_set_vclk_divider(uint32_t divider);
       int clock_set_hclk_divider(uint32_t divider);
       int clock_set_rticlk_divider(uint32_t divider);

    IMPLEMENTATION NOTES:
    - All setter functions MUST validate inputs against bus.yaml constraints
    - MUST return error codes (0 = success, negative = error)
    - MUST NOT modify hardware if validation fails
    - If register field encodings are not in YAML, function should return -ENOTSUP with comment

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

      ===== FILE: include/clock.h =====
      ===== FILE: source/clock.c =====

    No other files may be emitted.

    CODING RULES
    ------------
    - C11, but ISO C90-compatible style
    - Declare locals at block start (no declarations inside for loops)
    - Public headers MUST NOT include vendor headers
    - Use <stdint.h> for uint8_t, uint32_t, int32_t, etc.
    - Use <stddef.h> for NULL, size_t, ptrdiff_t
    - Use <stdbool.h> for bool, true, false (if needed)
    - Include all dependencies needed for types used in the file
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
    - include <stdint.h>, "clock.h", "reg_pll.h", and "reg_system.h"
    - declare register base pointers using struct-based access (as shown in REGISTER ACCESS section)
    - implement register operations through struct member access (e.g., PLL->PLLCTL1, SYS->CSDIS)
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

  ===== FILE: include/vim.h =====
  ...

  ===== FILE: source/vim.c =====
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


def build_system_init_prompt(soc_yaml: str, regs_yaml: str, manifest: dict = None, bus_yaml: str = ""):
    # Extract typedef name from manifest (Pass 1 generated header)
    system_typedef = "SYSTEM_REGS_t"  # Default fallback
    has_system2 = False
    system2_typedef = None

    if manifest:
        api_catalog = manifest.get("api_catalog", {})
        system_entry = api_catalog.get("SYSTEM", {})

        # Try new array format first, fall back to old single typedef
        typedefs = system_entry.get("register_typedefs", [])
        if typedefs:
            system_typedef = typedefs[0]  # Use primary typedef
            # Check if there are secondary typedefs (like SYSTEM2)
            if len(typedefs) > 1:
                has_system2 = True
                system2_typedef = typedefs[1]
        else:
            # Fallback for old manifests
            if "register_typedef" in system_entry:
                system_typedef = system_entry["register_typedef"]

    typedef_section = f"""
    REGISTER ACCESS (MANDATORY - CRITICAL FOR COMPILATION):
    -------------------------------------------------------
    You MUST use register headers generated in Pass 1 (Discovery) for all register access.

    REQUIRED INCLUDES in system.c:
    - #include "reg_system.h"   (for SYSTEM registers)

    REGISTER TYPEDEF NAME (FROM PASS 1 - USE EXACTLY AS SHOWN):
    - SYSTEM register struct typedef: {system_typedef}

    REQUIRED PATTERN for declaring register pointers:
    ```c
    static {system_typedef} * const SYS = ({system_typedef} *)0xFFFFFF00u;
    ```

    CRITICAL: You MUST use this EXACT typedef name. It comes from Pass 1 generated header.
    DO NOT guess, modify, or assume a different typedef name - use this name EXACTLY.
"""

    if has_system2:
        typedef_section += f"""
    NOTE: This header contains TWO register structures:
    - {system_typedef} at 0xFFFFFF00 (primary SYSTEM registers)
    - {system2_typedef} at 0xFFFFE100 (secondary SYSTEM2 registers)

    For system initialization, you MUST use {system_typedef} for the primary SYSTEM registers.
    Do NOT use {system2_typedef} unless accessing SYSTEM2-specific registers at 0xFFFFE100.
"""

    typedef_section += """
    DO NOT use inline #define macros for register access:
    ```c
    // WRONG - Do not do this:
    #define SYSTEM_BASE 0xFFFFFF00u
    #define REG32(addr) (*(volatile uint32_t *)(addr))
    ```
    """

    return typedef_section + """
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
    the clock domain naming used by the PLL module (clock_domain_t values), e.g.:
      x-ext.base_clock_refs: ["HCLK", "VCLK", "HF_LPO", "LF_LPO"]
    If x-ext.base_clock_refs is absent, do not enable any clocks implicitly in system_init.

  - clock_domain_t follow the following naming convention:
      - Normalize enum names deterministically:
      CLOCKDOMAIN_<UPPERCASE_REF>
      - Replace non-alphanumeric with underscore

- regs.yaml:
  - peripherals.<name>.base_address is the base address as a hex string.
  - peripherals.<name>.registers.<reg_name>.offset is the offset as a hex string.

CLOCK MODULE INTEGRATION (MANDATORY)
------------------------------------
- The PLL module (pll_driver.c / pll_driver.h) provides clock services:

    typedef enum clock_domain_t clock_domain_t;
    int PLL_EnableClock(clock_domain_t domain);

- system.c MUST include "pll_driver.h" to call PLL_EnableClock().

- system_init() MUST perform ONLY the following clock-related work:
  1) Enable base clocks listed in SYSTEM.x-ext.base_clock_refs by calling PLL_EnableClock(domain).
  2) MUST NOT configure/modify clock dividers, PLLs, or muxes here.
  3) MUST NOT call any clock configuration/modification APIs
     (PLL_Configure*, PLL_Set*, etc.).
     Those are APPLICATION-ONLY and must be called by developer code in main.c if desired.

- Peripheral drivers will call PLL_EnableClock() for their own clock_ref(s). system_init
  should only ensure minimal base clocks are enabled.

SYSTEM MODULE SCOPE (MANDATORY CONSTRAINTS)
-------------------------------------------
system.c owns chip bring-up ONLY. It MUST NOT touch PLL configuration registers.

FORBIDDEN in system.c (these belong exclusively to pll_driver.c):
  - SYS->PLLCTL1, SYS->PLLCTL2, SYS->PLLCTL3  — PLL multiplier/divider config
  - SYS->CSDIS, SYS->CSDISSET, SYS->CSDISCLR  — clock source disable/enable
  - SYS->CDDIS, SYS->CDDISSET, SYS->CDDISCLR  — clock domain disable/enable
  - SYS->GHVSRC                                 — GCLK/HCLK/VCLK source mux
  - SYS->CLKCNTL (VCLKR, VCLK2R divider fields) — domain frequency dividers

If SYSTEM.x-ext.init contains any of the above register names, SKIP those entries with a comment:
    /* Skipped: PLLCTL1/CSDIS/GHVSRC/etc. are owned by pll_driver.c */

PERMITTED in system.c:
  - SYS->CLKCNTL CLKENA bit (oscillator enable) — only if in x-ext.init
  - PCR power-down clear registers (PCR.PSPWRDWNCLR*)
  - SYS->MINITGCR, SYS->MSIENA — memory init trigger if in x-ext.init
  - Any other SYSTEM register NOT in the forbidden list above

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

NOTE: PLL_EnableClock() calls do not require mirroring numeric constants here, since those are handled
inside the PLL module.

Requirements:

1) system.h
-----------
- Provide an include guard.
- Include <stdint.h>.
- Declare the following functions (all of these are REQUIRED):
    void     system_init(void);
    uint32_t system_get_reset_cause(void);   /* Returns SYS->SYSESR reset status register value */
    void     system_soft_reset(void);        /* Writes SYS->SYSECR to trigger a software reset */
    uint32_t system_get_device_id(void);     /* Returns SYS->DEVID device identification value */
    void     system_clear_status_flags(void); /* Clears SYS->SYSESR by writing it back to itself */

2) system.c
-----------
- Include <stdint.h>, "system.h", "reg_system.h", and "pll_driver.h".
- Include "reg_pcr.h" if PCR register access is needed for x-ext.init operations.

- Declare register base pointers using struct-based access (as shown in REGISTER ACCESS section):
    static {system_typedef} * const SYS = ({system_typedef} *)0xFFFFFF00u;
    static PCR_REGS_t * const PCR = (PCR_REGS_t *)0xFFFFE000u;  /* if needed */

- For SYSTEM.x-ext.init operations:
    - Parse each "reg" field to determine peripheral (SYSTEM or PCR) and register name
    - Access registers through the struct pointer, e.g.:
        SYS->CLKCNTL |= value;    /* for set_bits */
        SYS->CLKCNTL &= ~value;   /* for clear_bits */
        SYS->CLKCNTL = value;     /* for write */
        PCR->PSPWRDWNCLR0 = value; /* for PCR registers */

- You MUST use the EXACT register member names from the Pass 1 generated headers.
- The base addresses MUST come from regs.yaml.

- Implement void system_init(void) that performs, in this exact order:
  1) Apply SYSTEM.x-ext.init register operations in order using struct member access as shown above.
     (Skip any forbidden PLL-owned registers per SYSTEM MODULE SCOPE constraints above.)
  2) Call PLL_Init() to configure the PLL and activate the complete clock tree.
     This is MANDATORY — entry.c calls system_init() and then main(); it does NOT call PLL_Init()
     separately. Without this call the device runs unconfigured on OSCIN only.
  3) Enable additional base clocks (optional):
     - If SYSTEM.x-ext.base_clock_refs exists, call PLL_EnableClock() for each listed ref, in order.
     - If absent, skip this step (PLL_Init() already enables the core domains).

- The effective behavior MUST match exactly:
  - The provided SYSTEM.x-ext.init list (minus forbidden PLL registers)
  - A call to PLL_Init() after the register operations
  - The provided SYSTEM.x-ext.base_clock_refs list (if present, called after PLL_Init)

- You MAY add a comment such as:
    /* Clock configuration (PLL/dividers/mux) is application-owned; see PLL_Configure* APIs in pll_driver.h (do not call here). */

- Also implement the following utility functions (use register member names from reg_system.h):
    uint32_t system_get_reset_cause(void)  { return SYS->SYSESR; }
    void     system_soft_reset(void)       { SYS->SYSECR = 0x8000u; }  /* bit 15 = SW reset */
    uint32_t system_get_device_id(void)    { return SYS->DEVID; }
    void     system_clear_status_flags(void) { SYS->SYSESR = SYS->SYSESR; }  /* write-1-to-clear */
  CRITICAL: Look up the exact register member names from reg_system.h (provided in regs.yaml input).
  Use ONLY member names that exist in the register struct. If a register is not present, add a TODO.

3) Assumptions:
---------------
- The linker script and assembly startup (Reset_Handler, stack pointer setup) are handled elsewhere in start.s and linker.cmd.
- Reset_Handler_C (in entry.c) will call system_init() before main().

OUTPUT CONTRACT
---------------
After the FACTS MIRROR, output exactly:
  ===== FILE: include/system.h =====
  ===== FILE: source/system.c =====

No other files may be emitted.

Here is soc.yaml (relevant slice):

%s

Here is regs.yaml (relevant slice):

%s

Here is bus.yaml (clock topology - sources, domains, and SYSTEM clock numbering):

%s

Now, output FACTS MIRROR, then system.h followed by system.c, obeying the global HARD OUTPUT CONTRACT.


    """ % (soc_yaml, regs_yaml, bus_yaml if bus_yaml else "(not provided)")

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
   - Note: linker.cmd goes to the root directory, not source/ or include/.

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
- A single FILE block for source/entry.c, nothing else (besides the FACTS MIRROR required by the system prompt).


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

    ===== FILE: source/start.s =====
    <assembly here>

- Use only TI assembler directives (.sect, .align, .long, .global, .ref) and ARM instructions (LDR, BL, B).
- Do NOT emit any C code or additional files.
- The file must end with a trailing newline to avoid compiler warnings.

Now generate start.s that satisfies all requirements above.

    """

def build_manifest_prompt(module_name: str, soc_slice: str) -> str:
    """
    Constructs the prompt for "Pass 1A" - API Manifest Discovery.
    Focuses solely on architectural metadata (JSON).
    """
    # Special instructions for PLL module (provides clock services)
    pll_extra = ""
    if module_name.upper() == "PLL":
        pll_extra = """

SPECIAL REQUIREMENTS FOR PLL MODULE:
------------------------------------
The PLL module provides BOTH PLL configuration AND clock services for the system.
You MUST include these clock-related functions in addition to PLL functions:

Required Clock API Functions:
1. PLL_GetFrequency(clock_domain_t domain) - Returns frequency in Hz for a clock domain
2. PLL_EnableClock(clock_domain_t domain) - Enables a clock domain
3. PLL_ConfigureClock(...) - Optional: Configure PLL/dividers (for application use only)

CRITICAL - Clock Domain Enum:
You MUST define a "clock_domain_t" enum in the "types" section.

CLOCK DOMAIN ENUM NAMING RULE (MANDATORY):
- Transform each clock_ref string to: CLOCKDOMAIN_<UPPERCASE_REF>
- Replace non-alphanumeric characters with underscores
- Examples:
  * "VCLK"   → CLOCKDOMAIN_VCLK
  * "HF_LPO" → CLOCKDOMAIN_HF_LPO
  * "VCLK2"  → CLOCKDOMAIN_VCLK2
  * "RTICLK" → CLOCKDOMAIN_RTICLK
  * "GCLK"   → CLOCKDOMAIN_GCLK
  * "HCLK"   → CLOCKDOMAIN_HCLK

CLOCK DOMAIN DISCOVERY (MANDATORY):
Step 1: Collect ALL clock domain names from these sources:
  a) x-ext.all_clock_domains array (if present in soc slice)
  b) soc.peripherals[*].clock_ref values (scan all peripherals)
  c) soc.peripherals[*].x-ext.clock_refs arrays (if present)
  d) bus.yaml domains[*].name (if bus topology provided)
  e) bus.yaml sources[*].name (if bus topology provided)

Step 2: Normalize and deduplicate:
  - Convert each name to: CLOCKDOMAIN_<UPPERCASE_NAME>
  - Replace non-alphanumeric characters with underscores
  - Merge duplicates (same normalized name = same enum value)
  - Examples:
    * "VCLK" → CLOCKDOMAIN_VCLK
    * "vclk" → CLOCKDOMAIN_VCLK (merge with above)
    * "VCLK2" → CLOCKDOMAIN_VCLK2

Step 3: Sort and assign values:
  - Sort enum names lexicographically (for stability)
  - Assign consecutive values starting from 0
  - Add CLOCKDOMAIN_MAX as final sentinel value

CRITICAL: The enum MUST be complete - include ALL discovered domains. Missing domains will cause runtime errors in peripheral drivers.

REQUIRED enum format in the "types" array:
{{
  "name": "clock_domain_t",
  "type": "enum",
  "values": [/* Populate from x-ext.all_clock_domains - do NOT use hardcoded list */],
  "description": "Clock domain identifiers for all system clock domains"
}}

The PLL module is THE clock service provider for the entire system.
All peripherals will call PLL_GetFrequency() and PLL_EnableClock() for clock management.
"""

    # IOMM-specific requirements
    iomm_extra = ""
    if module_name.upper() == "IOMM":
        iomm_extra = """

SPECIAL REQUIREMENTS FOR IOMM MODULE:
--------------------------------------
The IOMM module provides pin multiplexing services for the entire system.

NON-LINEAR PIN MAPPING (CRITICAL):
-----------------------------------
The PINMMR register-to-pin mapping is NON-LINEAR and MUST NOT be computed dynamically.

FORBIDDEN PATTERN (causes incorrect pin configuration):
```c
// WRONG - This assumes linear mapping which is INCORRECT
uint32_t reg_index = pin_number / 4;
uint32_t bit_offset = (pin_number % 4) * 8;
```

REQUIRED APPROACH - Pre-computed Lookup Table:
1. Define a lookup table structure:
   typedef struct {
       uint8_t pin_number;
       volatile uint32_t* pinmmr_reg;
       uint8_t bit_offset;
   } pin_mapping_t;

2. Initialize lookup table in IOMM_Init() using pinmux.yaml data:
   static const pin_mapping_t g_pin_map[] = {
       {1,  &IOMMREG->PINMMR0, 0},
       {2,  &IOMMREG->PINMMR0, 8},
       {5,  &IOMMREG->PINMMR1, 0},
       // ... complete mapping from pinmux.yaml
       // Extract from pinmux.yaml: package_pin -> mux.register/bit
   };

3. Implement O(1) lookup function:
   static int get_pin_mapping(uint8_t pin, volatile uint32_t** reg, uint8_t* bit) {
       for (size_t i = 0; i < sizeof(g_pin_map)/sizeof(g_pin_map[0]); i++) {
           if (g_pin_map[i].pin_number == pin) {
               *reg = g_pin_map[i].pinmmr_reg;
               *bit = g_pin_map[i].bit_offset;
               return 0;  // Success
           }
       }
       return -1;  // Pin not found
   }

4. Use lookup in IOMM_ConfigurePin() or IOMM_EnablePins():
   volatile uint32_t* reg;
   uint8_t bit;
   if (get_pin_mapping(pin_num, &reg, &bit) == 0) {
       *reg |= (alternate_function << bit);
   }

WHY PRE-COMPUTATION IS MANDATORY:
- Pin-to-register mapping is hardware-specific and non-linear
- Different chips have different mappings
- Computing at runtime wastes CPU cycles and increases token usage
- Pre-computed tables are faster and more maintainable
"""

    return f"""
You are a Senior Embedded Systems Architect.
Analyze the hardware description for the "{module_name}" module and define its software interface.

INPUT CONTEXT:
1. Module Name: "{module_name}"
2. SOC Description (YAML):
{soc_slice}
{pll_extra}
{iomm_extra}
TASK:
Define the public interface (functions, types, and structs) this module will expose.

CRITICAL TYPE REQUIREMENTS:
- You MUST declare ALL custom types that will be used in the "types" array
- This includes: enums, structs, typedefs, function pointer types
- Every type used in function prototypes MUST be defined in the "types" section
- Standard C types (uint8_t, uint32_t, bool, etc.) do NOT need to be declared
- Register types from reg_{module_name.lower()}.h do NOT need to be declared
- Example: If a function takes "my_config_t*", you MUST define "my_config_t" in types
- Example: If a function returns "status_code_t", you MUST define "status_code_t" in types

DEPENDENCY DETECTION (CRITICAL):
----------------------------------
You MUST analyze the peripheral's functionality and declare ALL required dependencies.

CLOCK DEPENDENCY (MANDATORY RULE):
- If the peripheral uses ANY clock-derived values, it MUST declare "PLL" in dependencies
- Clock-derived values include:
  * Baud rates (UART/SCI)
  * Timeouts (timers, watchdogs)
  * Prescalers (ADC, PWM, timers)
  * Sampling rates (ADC)
  * Bit timing (CAN, I2C)
  * Any calculation based on peripheral clock frequency

Examples:
- UART/SCI: Uses VCLK for baud rate + pins for TX/RX → MUST include ["IOMM", "PLL"] in dependencies
- Timers/RTI: Use RTICLK or VCLK → MUST include "PLL" in dependencies
- CAN: Uses VCLK for bit timing + pins → MUST include ["IOMM", "PLL"] in dependencies
- ADC: Uses clock for conversion timing → MUST include "PLL" in dependencies
- SPI: Uses VCLK + pins for SCLK/MOSI/MISO/CS → MUST include ["IOMM", "PLL"] in dependencies
- I2C: Uses clock + pins for SDA/SCL → MUST include ["IOMM", "PLL"] in dependencies
- PWM: Uses clock + pins for PWM outputs → MUST include ["IOMM", "PLL"] in dependencies
- LIN: Uses VCLK + pins → MUST include ["IOMM", "PLL", "VIM"] in dependencies
- GIO/GPIO: Uses pins for digital I/O → MUST include ["IOMM"] in dependencies

CLOCK SERVICE API USAGE (MANDATORY - READ CAREFULLY):
------------------------------------------------------
Peripheral drivers that depend on PLL MUST use the clock service API correctly:

✓ REQUIRED USAGE:
1. Include the PLL driver header:
   #include "pll_driver.h"

2. Call PLL_EnableClock() in your init function:
   - Enable the peripheral's clock_ref domain
   - If x-ext.clock_refs exists, enable each domain in order
   Example:
   int SCI_Init(const sci_config_t* config) {{
       // Enable peripheral clock FIRST
       PLL_EnableClock(CLOCKDOMAIN_VCLK);

       // Then configure peripheral registers
       ...
   }}

3. Call PLL_GetFrequency() when computing timing parameters:
   - Baud rate calculations
   - Timeout/prescaler calculations
   - Any frequency-dependent parameter
   Example:
   uint32_t vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);
   uint32_t baud_div = (vclk_hz / (16 * baud_rate)) - 1;

✗ FORBIDDEN (causes system conflicts):
- DO NOT access SYSTEM clock registers directly (CSDIS, CDDIS, CLKCNTL, VCLKASRC, etc.)
- DO NOT access PLL registers (PLLCTL1/2/3) directly
- DO NOT configure clocks/dividers in peripheral drivers
- DO NOT implement your own clock enable/disable logic

EXCEPTION: Only the PLL and SYSTEM modules may access clock hardware registers.

IOMM DEPENDENCY (MANDATORY):
- Peripherals using external pins MUST include "IOMM" in dependencies
- This ensures pins are multiplexed to correct functions BEFORE peripheral registers are configured
- I/O peripherals requiring IOMM: SCI, LIN, GIO, SPI, I2C, CAN, PWM, EPWM, ECAP, EQEP, N2HET
- IOMM module is core infrastructure that initializes very early (after PCR, before peripherals)

OTHER DEPENDENCIES:
- VIM: If the peripheral has interrupts (check soc.yaml for irq_ref)
- PCR: If the peripheral requires power domain control

INTERFACE DESIGN:
- Naming Convention: {module_name.upper()}_FunctionName
- Init Function: {module_name.upper()}_Init (required)
- Dependencies: List in the "dependencies" array (e.g., ["PLL", "VIM", "PCR"])

OUTPUT FORMAT (CRITICAL - READ CAREFULLY):
Your response MUST be ONLY a valid JSON object. Follow these rules strictly:
1. NO explanatory text before or after the JSON
2. NO markdown code blocks (no ```json```)
3. Use DOUBLE QUOTES for all strings (NOT single quotes)
4. NO trailing commas after the last item in arrays or objects
5. NO comments in the JSON (// or /* */)
6. Start your response with {{ and end with }}

Return exactly this structure:
{{
    "module_name": "{module_name}",
    "driver_header_file": "{module_name.lower()}_driver.h",
    "reg_header_file": "reg_{module_name.lower()}.h",
    "init_function": "{module_name.upper()}_Init",
    "types": [
        {{
            "name": "status_t",
            "type": "enum",
            "values": ["STATUS_OK", "STATUS_ERROR", "STATUS_BUSY"],
            "description": "Return status codes"
        }},
        {{
            "name": "config_t",
            "type": "struct",
            "members": [
                {{"name": "mode", "type": "uint32_t"}},
                {{"name": "flags", "type": "uint16_t"}}
            ],
            "description": "Configuration structure"
        }},
        {{
            "name": "callback_t",
            "type": "typedef",
            "definition": "void (*callback_t)(void)",
            "description": "Callback function pointer type"
        }}
    ],
    "functions": [
        {{
            "name": "Init",
            "prototype": "void {module_name.upper()}_Init(void);",
            "description": "Initialize the module"
        }},
        {{
            "name": "Configure",
            "prototype": "status_t {module_name.upper()}_Configure(const config_t* cfg);",
            "description": "Configure the module"
        }}
    ],
    "dependencies": ["PLL", "PCR"]
}}

IMPORTANT:
- The "types" array is MANDATORY. Every custom type used in function prototypes must be listed here.
- The "dependencies" array is MANDATORY. Follow the DEPENDENCY DETECTION rules above to determine required dependencies.
"""

def build_reg_header_prompt(module_name: str, soc_slice: str, regs_slice: str) -> str:
    """
    Constructs the prompt for "Pass 1B" - Register Header Generation.
    Focuses solely on C Code generation.
    """
    return f"""
You are an Expert Embedded C Developer.
Generate the Register Map Header file for the "{module_name}" peripheral.

INPUT CONTEXT:
1. Module Name: "{module_name}"
2. Register Definition (YAML):
{regs_slice}

TASK:
Generate the C header file defining the register map struct.
- Filename: reg_{module_name.lower()}.h
- Use "typedef struct" for the register map (NOT "typedef volatile struct").
- CRITICAL: Each register member MUST be declared as "volatile uint32_t" (not plain "uint32_t").
- The volatile keyword MUST be on each member, NOT on the struct typedef itself.
- This is essential for preventing compiler optimization of hardware register access.
- Example:
    typedef struct {{
        volatile uint32_t REG_NAME;    /**< Register description */
        volatile uint32_t RESERVED0;   /**< Reserved */
    }} PERIPHERAL_REG_MAP_t;
- Use uint32_t for all register widths (unless specified otherwise).
- Define bit-masks as macros (e.g., #define {module_name.upper()}_BIT_NAME ...).
- Do NOT use bit-fields.
- Do NOT include base address pointers (those go in the driver).
- Wrap the output in a C code block (```c ... ```).

MULTIPLE BASE ADDRESS HANDLING:
- If the YAML input contains registers for TWO peripherals with DIFFERENT base_address values
  (e.g. "system" at 0xFFFFFF00 AND "system2" at 0xFFFFE100), you MUST generate TWO separate
  typedef struct definitions with volatile members, one per base address.
- Name each typedef using the peripheral name in SCREAMING_SNAKE with _REG_MAP_t suffix:
    system  → SYSTEM_REG_MAP_t   (base 0xFFFFFF00)
    system2 → SYSTEM2_REG_MAP_t  (base 0xFFFFE100)
- Generate macros for each struct using its own prefix (SYSTEM_ vs SYSTEM2_).
- Both typedefs go in the same header file (reg_{module_name.lower()}.h).

OUTPUT:
Return the C code content inside markdown code blocks.
"""

def build_pass2_driver_h_prompt(module_name: str, manifest_json: str, reg_header_content: str) -> str:
    """
    Constructs the prompt for "Pass 2A" - Driver Header Generation.
    Uses the Registry Manifest to strict define the API.
    """
    return f"""
You are an Expert Embedded C Developer.
Generate the Public Driver Header file for the "{module_name}" peripheral.

INPUT CONTEXT:
1. Module Name: "{module_name}"
2. API Manifest (JSON Source of Truth):
{manifest_json}
3. Register Header Definitions (Reference):
{reg_header_content}

TASK:
Generate the C header file (`{module_name.lower()}_driver.h`) that exposes the public interface.

INCLUDE REQUIREMENTS:
- Include the register header: `#include "reg_{module_name.lower()}.h"`
- **CRITICAL:** Do NOT redefine the register struct. It is already in the included register header.

TYPE DEFINITION REQUIREMENTS (CRITICAL):
- Define ALL types listed in the Manifest "types" section IN THE EXACT ORDER they appear
- For each type in the manifest:
  * If type="enum": Define a C enum with the exact name and values from manifest
  * If type="struct": Define a C struct with the exact name and members from manifest
  * If type="typedef": Define a C typedef with the exact definition from manifest
- **ABSOLUTE RULE:** Do NOT define any types that are NOT in the Manifest "types" section
- **ABSOLUTE RULE:** Do NOT add extra enum values, struct members, or types beyond what the manifest specifies
- Standard C types (uint8_t, uint32_t, bool, etc.) and register types do NOT need definition

FUNCTION PROTOTYPE REQUIREMENTS:
- Define function prototypes EXACTLY as listed in the Manifest "functions" section
- Do NOT add, remove, or modify function signatures
- Do NOT add extra functions not in the manifest

ORDERING:
- Ensure strict dependency order: Types MUST be defined BEFORE functions that use them
- Use include guards (e.g., `{module_name.upper()}_DRIVER_H`)
- Do NOT implement functions here
- Wrap output in a C code block

CLOCK FREQUENCY CONSTANTS IN HEADERS - FORBIDDEN:
-------------------------------------------------
- Do NOT define clock frequency constants (#define *_FREQUENCY, *_HZ, *_CLOCK)
- Do NOT define prescaler constants based on assumed clock values
- Do NOT use magic numbers for clock-related calculations
- Header may declare configuration functions (e.g., SetBaudRate, SetPrescaler)
- Implementation (.c file) MUST query clock frequency dynamically at runtime

If user needs to configure frequency-dependent features:
- Provide function that takes desired value (e.g., SetBaudRate(uint32_t baud))
- Implementation queries actual clock and calculates register values

OUTPUT:
Return ONLY the C code content.
"""

def build_pass2_driver_c_prompt(module_name: str, manifest_json: str, reg_header_content: str, soc_slice: str = "", bus_slice: str = "", pinmux_yaml: str = "", manifest: dict = None) -> str:
    """
    Constructs the prompt for "Pass 2B" - Driver Implementation Generation.
    Uses the Registry Manifest + Register Header + Hardware Info + Bus Info + Pin Mux Info (optional).
    """
    # PLL-specific implementation requirements
    pll_section = ""
    if module_name.upper() == "PLL":
        # Extract the SYSTEM register typedef name from the manifest so the LLM uses
        # the exact name generated by Pass 1 rather than guessing.
        system_typedef = "SYSTEM_REG_MAP_t"  # safe fallback
        system2_typedef = None
        has_system2 = False

        if manifest:
            api_catalog = manifest.get("api_catalog") or {}
            system_entry = api_catalog.get("SYSTEM") or {}

            # Try new array format first
            typedefs = system_entry.get("register_typedefs", [])
            if typedefs:
                system_typedef = typedefs[0]  # Primary
                if len(typedefs) > 1:
                    system2_typedef = typedefs[1]  # Secondary
                    has_system2 = True
            else:
                # Fallback to old format
                td = system_entry.get("register_typedef")
                if td:
                    system_typedef = td

        pll_section = f"""
PLL MODULE SPECIAL REQUIREMENTS (MANDATORY):
--------------------------------------------

HARD RULE — MACRO VERIFICATION (ENFORCED):
Before writing ANY code, scan INPUT CONTEXT 3 (register headers) line by line.
INPUT CONTEXT 3 contains reg_pll.h followed by reg_system.h.
Create a mental list of every #define visible there.
You MUST ONLY use macro names that appear verbatim in that list.
If you want to use a macro that is NOT in that list, you MUST NOT use it.
Instead, either use the closest named macro that IS present, or derive the
value from a MASK/SHIFT pair that IS present.

This is the central clock service module. You MUST implement ALL functions completely.
NO STUB FUNCTIONS. NO TODO COMMENTS in switch cases. Every case in every switch MUST be handled.

ENUM NAMING RULE (CRITICAL):
- All clock domain enum values use: CLOCKDOMAIN_<UPPERCASE_REF>
- Example: VCLK → CLOCKDOMAIN_VCLK, HF_LPO → CLOCKDOMAIN_HF_LPO
- Use the EXACT values from the clock_domain_t enum in the manifest
- Every enum value MUST have a corresponding case in PLL_EnableClock() and PLL_GetFrequency()

REQUIRED INCLUDES in pll_driver.c:
- #include "pll_driver.h"
- #include "reg_system.h" (contains PLLCTL1/2, CSDIS/CDDIS/CLR/SET, CLKCNTL, GHVSRC, CSVSTAT)
- Do NOT include a separate reg_pll.h if PLL registers are already in reg_system.h

REGISTER ACCESS (MANDATORY):
- The EXACT typedef name for the PRIMARY SYSTEM register struct is: {system_typedef}
- Declare register pointer to the SYSTEM base (0xFFFFFF00):
    static {system_typedef} * const SYSREG = ({system_typedef} *)0xFFFFFF00u;
"""

        if has_system2:
            pll_section += f"""
- The header ALSO contains {system2_typedef} for secondary registers at 0xFFFFE100:
    static {system2_typedef} * const SYSREG2 = ({system2_typedef} *)0xFFFFE100u;
- Use SYSREG2 for: PLLCTL3, CLK2CNTRL, VCLKACON1, CLKSLIP, STCCLKDIV
- Use SYSREG for: PLLCTL1, PLLCTL2, CLKCNTL, CSDIS, CDDIS, GHVSRC
"""
        else:
            pll_section += """
- If reg_system.h contains SYSTEM2_REG_MAP_t (check INPUT CONTEXT 3), also declare:
    static SYSTEM2_REG_MAP_t * const SYSREG2 = (SYSTEM2_REG_MAP_t *)0xFFFFE100u;
- Use SYSREG2->PLLCTL3 for PLL2 configuration
- Use SYSREG2->CLK2CNTRL for VCLK3R (bits[3:0]) and VCLK4R (bits[11:8]) dividers
- Use SYSREG2->VCLKACON1 for VCLKA3 and VCLKA4 source and divider configuration
"""

        pll_section += """
- Use EXACT member names from reg_system.h (e.g. SYSREG->PLLCTL1, SYSREG->CSDISCLR, SYSREG->CLKCNTL)
- NEVER use undefined symbols. Every constant you use MUST exist in reg_system.h or your FACTS MIRROR.

CSDIS/CDDIS REGISTER USAGE (CRITICAL):
- CSDIS controls clock SOURCES (oscillator, PLL1, LF_LPO, HF_LPO, etc.)
- CDDIS controls clock DOMAINS (GCLK, HCLK, VCLK, VCLK2, etc.)
- Both registers use active-HIGH disable semantics: bit=1 means disabled, bit=0 means enabled.
- To ENABLE: write the bit to the CLR register (CSDISCLR or CDDISCLR). Do NOT read-modify-write CSDIS.
- CSDISCLR macros in reg_system.h: SYSTEM_CSDISCLR_CLRCLKSR0OFF (OSCIN/bit0), SYSTEM_CSDISCLR_CLRCLKSR1OFF (PLL1/bit1), SYSTEM_CSDISCLR_CLRCLKSR4OFF (LF_LPO/bit4), SYSTEM_CSDISCLR_CLRCLKSR5OFF (HF_LPO/bit5), SYSTEM_CSDISCLR_CLRCLKSR6OFF (PLL2/bit6)
- CDDISCLR macros in reg_system.h: SYSTEM_CDDISCLR_CLRGCLKOFF (GCLK/bit0), SYSTEM_CDDISCLR_CLRHCLKOFF (HCLK/bit1), SYSTEM_CDDISCLR_CLRVCLKPOFF (VCLK/bit2), SYSTEM_CDDISCLR_CLRVCLK2OFF (VCLK2/bit3), SYSTEM_CDDISCLR_CLRVCLKA1OFF (VCLKA1/bit4), SYSTEM_CDDISCLR_CLRRTI1CLKOFF (RTICLK/bit6), SYSTEM_CDDISCLR_CLRVCLK3OFF (VCLK3/bit8), SYSTEM_CDDISCLR_CLRVCLK4OFF (VCLK4/bit9), SYSTEM_CDDISCLR_CLRVCLKA3OFF (VCLKA3/bit10), SYSTEM_CDDISCLR_CLRVCLKA4OFF (VCLKA4/bit11)

REQUIRED FUNCTION: PLL_Init(void)
This function owns the COMPLETE clock tree activation. Perform in this exact order:
1. Enable OSCIN: SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR0OFF;
2. Configure PLL1 multipliers using the values in INPUT CONTEXT 5 (bus.yaml slice) under
   sources → PLL1 → x-ext → default_config. Extract nr, nf, r, odpll values from there.
   FACTS MIRROR REQUIRED: mirror these exact values before writing any code.
   Do NOT hardcode numeric divider values — read them from the bus slice.
   - Write PLLCTL1: set REFCLKDIV (NR-1 in bits 16-21), PLLMUL (NF in bits 0-15), PLLDIV (R in bits 24-28)
   - Write PLLCTL2: set ODPLL (bits 9-11), clear FMENA (bit 31) for non-modulating
3. Enable PLL1 source: SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF;
4. Wait for PLL1 lock: poll SYSREG->CSVSTAT bit 1 (SYSTEM_CSVSTAT_CLKSR1V) with bounded iteration counter
5. Switch GHVSRC to PLL1 source using the source_number for PLL1 from
   x-ext.peripheral_clocks.SYSTEM.clock_sources in bus slice (source_number=1 → GHVSRC=1).
   Mirror the source_number in FACTS MIRROR.
6. Set VCLK divider: write CLKCNTL with VCLKR=1 (divide-by-2) and VCLK2R=1 (divide-by-2) in bits 16-19 and 24-27
7. Enable core domains: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF | SYSTEM_CDDISCLR_CLRHCLKOFF | SYSTEM_CDDISCLR_CLRVCLKPOFF | SYSTEM_CDDISCLR_CLRVCLK2OFF;
8. Enable peripheral enable: set SYSTEM_CLKCNTL_PENA bit in SYSREG->CLKCNTL

REQUIRED FUNCTION: PLL_EnableClock(clock_domain_t domain)
Must have a case for EVERY enum value in clock_domain_t. Handle as follows:
- CLOCKDOMAIN_OSCIN / CLOCKDOMAIN_EXTCLKIN1 / CLOCKDOMAIN_EXTCLKIN2: already enabled; return PLL_STATUS_OK
- CLOCKDOMAIN_PLL1: SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR1OFF; break;
- CLOCKDOMAIN_PLL2: SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR6OFF; break;
- CLOCKDOMAIN_HF_LPO: SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR5OFF; break;
- CLOCKDOMAIN_LF_LPO: SYSREG->CSDISCLR = SYSTEM_CSDISCLR_CLRCLKSR4OFF; break;
- CLOCKDOMAIN_GCLK: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRGCLKOFF; break;
- CLOCKDOMAIN_HCLK: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRHCLKOFF; break;
- CLOCKDOMAIN_VCLK: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKPOFF; break;
- CLOCKDOMAIN_VCLK2: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK2OFF; break;
- CLOCKDOMAIN_VCLK3: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK3OFF; break;
- CLOCKDOMAIN_VCLK4: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLK4OFF; break;
- CLOCKDOMAIN_VCLKA1: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA1OFF; break;
- CLOCKDOMAIN_VCLKA3: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA3OFF; break;
- CLOCKDOMAIN_VCLKA4: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRVCLKA4OFF; break;
- CLOCKDOMAIN_RTICLK: SYSREG->CDDISCLR = SYSTEM_CDDISCLR_CLRRTI1CLKOFF; break;
- default: return PLL_STATUS_INVALID_PARAM;
Must be idempotent. Must NEVER disable clocks.

REQUIRED FUNCTION: PLL_GetFrequency(clock_domain_t domain)
Must handle EVERY enum value. Calculate DYNAMICALLY from hardware registers.

PLL FREQUENCY CALCULATION (MANDATORY):
--------------------------------------
The RM46 PLLs use this formula:

f_pll = (f_osc × NF) / (NR × R)
f_hclk = f_pll / ODPLL

Where (from hardware registers):
- f_osc: Oscillator input frequency (OSCIN_HZ from bus.yaml, typically 16 MHz)
- NF: Feedback multiplier (from PLLCTL1 register)
- NR: Pre-divider (from PLLCTL1 register, stored as NR-1)
- R: Output divider (from PLLCTL1 register, stored as power of 2)
- ODPLL: Final output divider (from PLLCTL2 register, stored as ODPLL-1)

REGISTER EXTRACTION (Step by step):
1. Read registers:
   uint32_t pllctl1 = SYSREG->PLLCTL1;
   uint32_t pllctl2 = SYSREG->PLLCTL2;

2. Extract bit fields:
   uint32_t nf_raw = (pllctl1 & SYSTEM_PLLCTL1_PLLMUL_MASK) >> SYSTEM_PLLCTL1_PLLMUL_SHIFT;
   uint32_t nr_raw = (pllctl1 & SYSTEM_PLLCTL1_REFCLKDIV_MASK) >> SYSTEM_PLLCTL1_REFCLKDIV_SHIFT;
   uint32_t plldiv_raw = (pllctl1 & SYSTEM_PLLCTL1_PLLDIV_MASK) >> SYSTEM_PLLCTL1_PLLDIV_SHIFT;
   uint32_t odpll_raw = (pllctl2 & SYSTEM_PLLCTL2_ODPLL_MASK) >> SYSTEM_PLLCTL2_ODPLL_SHIFT;

3. Convert to actual values:
   uint32_t NF = nf_raw;           // Multiplier value (use as-is)
   uint32_t NR = nr_raw + 1;       // Pre-divider (register stores NR-1)
   uint32_t R = 1u << plldiv_raw;  // Output divider (2^PLLDIV)
   uint32_t ODPLL = odpll_raw + 1; // Final divider (register stores ODPLL-1)

4. Calculate PLL frequency:
   uint32_t f_pll = (OSCIN_HZ * NF) / (NR * R);
   uint32_t f_hclk = f_pll / ODPLL;

WORKED EXAMPLE (from bus.yaml typical configuration):
- OSCIN_HZ = 16,000,000 Hz (16 MHz)
- NF = 120 (multiplier)
- NR = 6 (pre-divider, stored as 5 in register)
- R = 2 (output divider, stored as 1 in register since 2^1=2)
- ODPLL = 2 (final divider, stored as 1 in register)

Calculation:
f_pll = (16 MHz × 120) / (6 × 2) = 1,920 MHz / 12 = 160 MHz
f_hclk = 160 MHz / 2 = 80 MHz

VERIFICATION:
Use bus.yaml default_config values to verify your formula produces the expected frequency.
If bus.yaml shows: nr=5, nf=120, r=1, odpll=1, then:
- Actual values: NR=6 (5+1), NF=120, R=2 (2^1), ODPLL=2 (1+1)
- Expected result: 160 MHz PLL, 80 MHz HCLK

5. Domain-specific calculations:
Cases per domain:
- CLOCKDOMAIN_GCLK / CLOCKDOMAIN_HCLK / CLOCKDOMAIN_PLL1: return hclk_hz
- CLOCKDOMAIN_VCLK: vclkr = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLKR_MASK) >> SYSTEM_CLKCNTL_VCLKR_SHIFT; return hclk_hz / (vclkr + 1u)
- CLOCKDOMAIN_VCLK2: vclk2r = (SYSREG->CLKCNTL & SYSTEM_CLKCNTL_VCLK2R_MASK) >> SYSTEM_CLKCNTL_VCLK2R_SHIFT; return hclk_hz / (vclk2r + 1u)
- CLOCKDOMAIN_VCLK3: if VCLKACON1 is in reg_system.h, read VCLK3R field (bits 0-3); else return hclk_hz / 2u
- CLOCKDOMAIN_VCLK4: if VCLKACON1 is in reg_system.h, read VCLK4R field (bits 8-11); else return hclk_hz / 2u
- CLOCKDOMAIN_RTICLK / CLOCKDOMAIN_VCLKA1 / CLOCKDOMAIN_VCLKA3 / CLOCKDOMAIN_VCLKA4: return same as VCLK
- CLOCKDOMAIN_OSCIN: return OSCIN_HZ (16000000U)
- CLOCKDOMAIN_HF_LPO: return HF_LPO_HZ (9600000U)
- CLOCKDOMAIN_LF_LPO: return LF_LPO_HZ (85000U)
- CLOCKDOMAIN_PLL2: return hclk_hz  (secondary PLL, treat as same frequency)
- default: return 0u
OSCIN_HZ, HF_LPO_HZ, LF_LPO_HZ MUST be in the FACTS MIRROR (pulled from bus.yaml).

REQUIRED FUNCTION: PLL_ConfigureClock(const pll_divider_config_t* divider_config)
- Read divider_config->domain and divider_config->divider
- For VCLK: validate divider in [0,15]; write VCLKR field of CLKCNTL
- For VCLK2: validate; write VCLK2R field of CLKCNTL
- For VCLK3/VCLK4: write VCLKACON1 if register exists in reg_system.h
- Return PLL_STATUS_OK on success, PLL_STATUS_INVALID_PARAM if out of range or unknown domain

FORBIDDEN:
- Do NOT hardcode PLLCLK or any PLL-derived frequency as a #define constant
- Do NOT stub any function or leave any switch case as TODO
- Do NOT reference undefined symbols (every macro you use must exist in reg_system.h)
"""

    UNIVERSAL_CLOCK_RULES = """
CLOCK FREQUENCY HANDLING - MANDATORY FOR ALL PERIPHERAL DRIVERS:
================================================================
Never hardcode clock frequencies. Always call available API functions to establish clock frequencies.

This applies to ANY calculation involving:
- Baud rates (UART, SCI, CAN, I2C)
- Prescalers (ADC, PWM, Timers)
- Timeouts (Watchdog, RTI)
- Dividers (SPI clocks, PWM frequency)

ABSOLUTELY FORBIDDEN:
```c
// ❌ NEVER do this:
#define VCLK_FREQUENCY 110000000U
#define SCI_CLOCK_HZ 110000000U
#define PRESCALER_VALUE 5  // hardcoded for specific frequency
uint32_t freq = 110000000; // magic number
prescaler = (110000000 / baud) - 1;  // hardcoded calculation
```

ALWAYS REQUIRED:
```c
// ✅ ALWAYS do this:
#include "pll_driver.h"
uint32_t clk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);  // Query at runtime
uint32_t prescaler = (clk_hz / (16 * baud)) - 1;       // Use queried value
```

WHY THIS MATTERS:
- Clock frequencies are board-specific and configurable
- PLL settings vary by application
- Runtime clock changes must be supported
- Hardcoded values WILL cause wrong baud rates and timing failures

If manifest shows "PLL" in dependencies, these APIs are guaranteed available:
- PLL_GetFrequency(clock_domain_t domain) → Returns Hz for specified domain
- PLL_EnableClock(clock_domain_t domain) → Enables clock before peripheral access

Use the clock_domain_t enum value matching your peripheral's clock_ref from the manifest.

VALIDATION: After writing code, scan for patterns like:
- "#define.*FREQUENCY", "#define.*HZ", "#define.*CLOCK"
- Numeric literals > 1000000 in calculations
If found, replace with PLL_GetFrequency() calls.
"""

    return f"""
You are an Expert Embedded C Developer.
Generate the Driver Implementation file for the "{module_name}" peripheral.
{pll_section}
{UNIVERSAL_CLOCK_RULES}

INPUT CONTEXT:
1. Module Name: "{module_name}"
2. API Manifest (JSON Source of Truth):
{manifest_json}
3. Register Header Definitions (Reference):
{reg_header_content}
4. Hardware Details (YAML):
{soc_slice}
5. Bus/Clock Details (YAML):
{bus_slice}
6. Pin Multiplexing Data (YAML):
{pinmux_yaml if pinmux_yaml else "Not provided - peripheral does not use external pins"}

TASK:
Generate the C source file (`{module_name.lower()}_driver.c`) implementing the driver.

INCLUDE REQUIREMENTS:
- Include the driver header: `#include "{module_name.lower()}_driver.h"`
- **CRITICAL:** Do NOT redefine any types. All types are defined in the driver header.
- **CRITICAL:** Do NOT redefine the register struct. It is already defined in `reg_{module_name.lower()}.h`.

REGISTER ACCESS REQUIREMENTS:
- **CRITICAL:** Look at INPUT CONTEXT 3 to find the exact typedef name (e.g., `sciBASE_t` or `SYSTEM_RegMap_t`)
- **CRITICAL:** Use the EXACT member names from Context 3 (e.g., `GCR0`, `FLR`)
- Base Address: Use the specific memory address from the YAML (e.g. `sciREG1`)
- Instance Definition:
  - Create the base pointer definition casting the address to the Struct Type found in Context 3
  - Example: `#define {module_name.lower()}REG ((volatile <STRUCT_TYPE_FROM_CTX3> *)0xFFF7E500U)`

CLOCK SERVICE INTEGRATION (MANDATORY):
--------------------------------------
**CRITICAL:** If the manifest (INPUT CONTEXT 2) lists "PLL" in dependencies, you MUST follow these rules:

1. INCLUDE REQUIREMENT:
   - Add `#include "pll_driver.h"` to the .c file

2. FORBIDDEN PATTERNS (will cause validation errors):
   - Do NOT hardcode frequency values:
     ```c
     // WRONG - Do NOT do this:
     #define SCI_VCLK_FREQUENCY 110000000U
     #define VCLK_HZ 110000000U
     ```
   - Do NOT use magic numbers for frequency calculations
   - Do NOT assume any specific clock frequency

3. REQUIRED PATTERN - Clock Enable in Init Function:
   The {module_name.upper()}_Init() function MUST enable the peripheral's clock FIRST:
   ```c
   void {module_name.upper()}_Init(void) {{
       // STEP 1: Enable peripheral clock (MANDATORY - must be first)
       PLL_EnableClock(CLOCKDOMAIN_<CLOCK_REF>);

       // STEP 2: Then configure peripheral registers
       ...
   }}
   ```
   - Look at INPUT CONTEXT 4 (soc.yaml) to find the peripheral's clock_ref
   - Convert clock_ref to enum name: CLOCKDOMAIN_<UPPERCASE_REF>
   - Call PLL_EnableClock() BEFORE accessing ANY peripheral registers

4. REQUIRED PATTERN - Baud Rate / Timing Calculations:
   For peripherals with baud rates, timeouts, or prescalers, you MUST use PLL_GetFrequency():
   ```c
   // CORRECT - For UART/SCI baud rate:
   uint32_t vclk_hz = PLL_GetFrequency(CLOCKDOMAIN_VCLK);
   uint32_t prescaler = (vclk_hz / (16 * baud_rate)) - 1;

   // CORRECT - For Timer period:
   uint32_t clock_hz = PLL_GetFrequency(CLOCKDOMAIN_RTICLK);
   uint32_t ticks = (clock_hz * timeout_ms) / 1000;
   ```

5. VALIDATION CHECKS:
   Your generated code will be validated for:
   - Presence of `#include "pll_driver.h"` when PLL is in dependencies
   - NO hardcoded `#define *_FREQUENCY` or `#define *_HZ` macros
   - Calls to PLL_EnableClock() in init function
   - Calls to PLL_GetFrequency() for baud/timing calculations

IOMM PIN MULTIPLEXING INTEGRATION (MANDATORY FOR I/O PERIPHERALS):
-------------------------------------------------------------------
**CRITICAL:** If the manifest (INPUT CONTEXT 2) lists "IOMM" in dependencies, the peripheral uses external pins that require multiplexing.

**IMPORTANT:** Peripheral drivers MUST NOT directly access IOMM/PINMMR registers. Instead, they must use the IOMM driver API.

1. INCLUDE REQUIREMENT:
   - Add `#include "iomm_driver.h"` to the .c file

2. PIN CONFIGURATION APPROACH:
   **DO NOT directly configure pins in the peripheral Init() function.**

   Instead, document required pins in a comment and assume they are pre-configured:
   ```c
   void {module_name.upper()}_Init(void) {{
       // STEP 1: Enable peripheral clock (MANDATORY - must be first)
       PLL_EnableClock(CLOCKDOMAIN_<CLOCK_REF>);

       /* Pin Configuration Requirements (must be done before calling this function):
        * The following pins must be configured via IOMM_ConfigurePin() or main.c:
        * - <SIGNAL_NAME>: PINMMRx bit y (e.g., SCIRX: PINMMR7 bit 17)
        * - <SIGNAL_NAME>: PINMMRx bit y (e.g., SCITX: PINMMR8 bit 1)
        *
        * Example configuration in main.c:
        *   IOMM_Unlock();
        *   // Set PINMMR7 bit 17 for SCIRX
        *   // Set PINMMR8 bit 1 for SCITX
        *   IOMM_Lock();
        */

       // STEP 2: Configure peripheral registers
       ...
   }}
   ```

3. EXTRACTING PIN REQUIREMENTS FROM PINMUX.YAML (INPUT CONTEXT 6):
   - Find your peripheral's signal names in pinmux.yaml
   - Look for entries where functions[].signal matches your peripheral (e.g., "SCIRX", "SCITX", "LINRX", "LINTX")
   - The mux.register and mux.bit tell you which PINMMR register and bit control each signal
   - Document these requirements in comments as shown above
   - Example from pinmux.yaml:
     ```yaml
     - package_pin: 39
       functions:
         - {{ af: "1", signal: "SCIRX", mux: {{ register: "PINMMR7", bit: 17 }} }}
     ```
     This means: SCIRX requires PINMMR7 bit 17 to be set

4. MULTIPLE INSTANCES:
   - If your peripheral has multiple instances (e.g., LIN1, LIN2, SCI1, SCI2):
     * Check INPUT CONTEXT 4 (soc.yaml) for the instance number
     * Search pinmux.yaml for signals with instance suffixes
     * Document only the pins for YOUR specific instance
   - If instance information is unavailable, document the default/first pin set found

5. WHY THIS APPROACH:
   - Pin multiplexing is typically done once at system startup in main.c or board init
   - Multiple peripherals may share IOMM configuration responsibility
   - The IOMM driver provides proper lock/unlock management
   - Peripheral drivers should focus on peripheral-specific configuration only

FUNCTION IMPLEMENTATION REQUIREMENTS:
- Implement EVERY function listed in the Manifest "functions" section
- Do NOT add extra functions not in the manifest
- Init Function: Must perform initialization steps described in the Manifest/YAML
- Dependencies:
  * If Manifest lists "PLL" dependency, MUST follow CLOCK SERVICE INTEGRATION rules above
  * If Manifest lists "PCR" dependency, assume `PCR_EnablePeripheral(id)` is available
  * If Manifest lists "VIM" dependency, assume VIM APIs are available for interrupt management

**ABSOLUTE TYPE SAFETY RULES (CRITICAL - VIOLATIONS WILL CAUSE COMPILATION ERRORS):**
1. **Enum Usage:**
   - ONLY use enum values that are explicitly listed in INPUT CONTEXT 2 (Manifest "types" section)
   - Check the manifest types array for the COMPLETE list of valid enum values
   - Do NOT invent, add, or guess enum values
   - Example: If manifest defines enum clock_domain_t with values [CLOCKDOMAIN_VCLK, CLOCKDOMAIN_VCLK2],
     you can ONLY use those two values. Do NOT use CLOCKDOMAIN_VCLK3, VCLK4, etc.

2. **Struct Usage:**
   - ONLY use structs that are defined in the manifest "types" section
   - Do NOT create anonymous structs or new struct types
   - ONLY access struct members that are listed in the manifest type definition

3. **Type References:**
   - Before using ANY custom type (enum, struct, typedef), verify it exists in INPUT CONTEXT 2
   - If you need a type that's not in the manifest, use a built-in C type (uint32_t, int, etc.)
   - If functionality is impossible without a missing type, add a TODO comment and use a workaround

4. **Constants:**
   - If you need a constant value that's not an enum, use `#define` or literal values
   - Do NOT create enum values to represent constants

Wrap output in a C code block.

OUTPUT:
Return ONLY the C code content.
"""

from enum import Enum

class Model(Enum):
    HAIKU_3_0 = "haiku3.0"
    HAIKU_4_5 = "haiku4.5"
    SONNET_3_5 = "sonnet3.5"
    SONNET_4_5 = "sonnet4.5"
    OPUS_4_5 = "opus4.5"
    OPUS_4_6 = "opus4.6"

    def get_model_id(self):
        model_ids = {
            "haiku3.0": "us.anthropic.claude-3-haiku-20240307-v1:0",
            "sonnet3.5": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
            "haiku4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "sonnet4.5": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "opus4.5": "us.anthropic.claude-opus-4-5-20250201-v1:0",
            "opus4.6": "us.anthropic.claude-opus-4-6-20250514-v1:0",
        }

        return model_ids[self.value]

    def get_pricing(self):
        """
        Returns (input_cost_per_million, output_cost_per_million) in USD.
        AWS Bedrock pricing as of February 2025.
        Source: https://aws.amazon.com/bedrock/pricing/
        """
        pricing = {
            # Claude 3 models (older generation)
            "haiku3.0": (0.25, 1.25),      # Claude 3 Haiku

            # Claude 3.5 models
            "sonnet3.5": (3.0, 15.0),      # Claude 3.5 Sonnet

            # Claude 4.5 models
            "haiku4.5": (1.0, 5.0),        # Claude 4.5 Haiku
            "sonnet4.5": (3.0, 15.0),      # Claude 4.5 Sonnet
            "opus4.5": (5.0, 25.0),        # Claude 4.5 Opus

            # Claude 4.6 models
            "opus4.6": (5.0, 25.0),        # Claude 4.6 Opus
        }

        return pricing[self.value]

    def get_display_name(self):
        """Returns a human-readable model name."""
        names = {
            "haiku3.0": "Claude 3 Haiku",
            "sonnet3.5": "Claude 3.5 Sonnet",
            "haiku4.5": "Claude 4.5 Haiku",
            "sonnet4.5": "Claude 4.5 Sonnet",
            "opus4.5": "Claude 4.5 Opus",
            "opus4.6": "Claude 4.6 Opus",
        }

        return names[self.value]


from typing import TypedDict, Literal


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class _CostTracker:
    """Thread-safe cost tracker for API usage with model-specific pricing."""
    def __init__(self):
        self.lock = threading.Lock()
        # Track usage per model: {model_value: {"input": X, "output": Y}}
        self.usage_by_model = {}

    def add_usage(self, model: Model, input_tokens: int, output_tokens: int):
        """Add token usage for a specific model."""
        with self.lock:
            model_key = model.value
            if model_key not in self.usage_by_model:
                self.usage_by_model[model_key] = {"input": 0, "output": 0}

            self.usage_by_model[model_key]["input"] += input_tokens
            self.usage_by_model[model_key]["output"] += output_tokens

    def get_cost(self) -> float:
        """Calculate total cost in USD across all models."""
        with self.lock:
            total_cost = 0.0
            for model_key, usage in self.usage_by_model.items():
                model = Model(model_key)
                input_price, output_price = model.get_pricing()
                input_cost = (usage["input"] / 1_000_000) * input_price
                output_cost = (usage["output"] / 1_000_000) * output_price
                total_cost += input_cost + output_cost
            return total_cost

    def get_stats(self) -> dict:
        """Get usage statistics with per-model breakdown."""
        with self.lock:
            total_input = sum(u["input"] for u in self.usage_by_model.values())
            total_output = sum(u["output"] for u in self.usage_by_model.values())

            # Calculate per-model breakdown
            models_breakdown = []
            total_cost = 0.0
            for model_key, usage in self.usage_by_model.items():
                model = Model(model_key)
                input_price, output_price = model.get_pricing()
                input_cost = (usage["input"] / 1_000_000) * input_price
                output_cost = (usage["output"] / 1_000_000) * output_price
                model_cost = input_cost + output_cost
                total_cost += model_cost

                models_breakdown.append({
                    "model_name": model.get_display_name(),
                    "input_tokens": usage["input"],
                    "output_tokens": usage["output"],
                    "total_tokens": usage["input"] + usage["output"],
                    "cost_usd": model_cost
                })

            return {
                "input_tokens": total_input,
                "output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "cost_usd": total_cost,  # Calculate inline instead of calling get_cost() to avoid deadlock
                "models": models_breakdown
            }

    def reset(self):
        """Reset all counters."""
        with self.lock:
            self.usage_by_model = {}


class _ProgressTracker:
    """
    Thread-safe progress tracker for concurrent generation tasks.

    .. deprecated:: 2.0
        This class is deprecated and kept only for backward compatibility.
        Use :class:`~modules.utils.unified_progress.UnifiedProgressManager` instead,
        which provides hierarchical progress tracking with global and per-pass views.

    The old _ProgressTracker provides basic spinner functionality but lacks:
    - Hierarchical progress display (global + per-pass)
    - Per-module progress tracking
    - ETA calculation
    - Success/failure counters
    - Comprehensive logging

    For new code, use UnifiedProgressManager from modules.utils.unified_progress.
    """
    def __init__(self):
        self.total_tasks = 0
        self.completed_tasks = 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

    def set_total(self, total: int):
        with self.lock:
            self.total_tasks = total
            self.completed_tasks = 0  # Reset counter for new batch
    
    def increment(self):
        with self.lock:
            self.completed_tasks += 1
            return self.completed_tasks, self.total_tasks
    
    def start_spinner(self):
        spinner_thread = threading.Thread(target=self._show_progress)
        spinner_thread.daemon = True
        spinner_thread.start()
        return spinner_thread
    
    def stop_spinner(self):
        self.stop_event.set()
    
    def _show_progress(self):
        """Display overall progress while tasks are running."""
        spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        start_time = time.time()
        
        while not self.stop_event.is_set():
            with self.lock:
                completed = self.completed_tasks
                total = self.total_tasks
            
            elapsed = int(time.time() - start_time)
            minutes, seconds = divmod(elapsed, 60)
            spinner = spinner_chars[idx % len(spinner_chars)]
            
            progress_str = f'{spinner} Generating: {completed}/{total} tasks completed ({minutes:02d}:{seconds:02d})'
            sys.stdout.write(f'\r{progress_str:<70}')
            sys.stdout.flush()
            idx += 1
            time.sleep(0.1)
        
        # Final clear
        sys.stdout.write('\r' + ' ' * 70 + '\r')
        sys.stdout.flush()


# Global trackers
_progress = _ProgressTracker()
_cost_tracker = _CostTracker()

# Semaphore to limit concurrent API calls (Bedrock has rate limits)
# Will be created in invoke_model on first call
_model_semaphore = None


async def invoke_model(model: Model, max_tokens: int, messages: list[Message]) -> str:
    """
    Invoke the Bedrock model with concurrency limiting.
    Allows up to N concurrent model invocations to avoid rate limiting.

    Set BSP_MOCK_MODE=1 environment variable to use mock responses for testing.
    """
    global _model_semaphore
    if _model_semaphore is None:
        # Start with 15 concurrent requests - good balance for most accounts
        # If you see ThrottlingException, reduce this number
        # If you have increased quotas, you can raise it to 30-50
        _model_semaphore = asyncio.Semaphore(15)

    # Check for mock mode (for testing without API calls)
    import os
    if os.getenv("BSP_MOCK_MODE", "").lower() in ("1", "true", "yes"):
        from modules.utils.mock_api import mock_invoke_model
        async with _model_semaphore:
            response = await mock_invoke_model(model, max_tokens, messages)

            # Track mock usage for cost estimation
            try:
                from modules.utils.utils import extract_usage_from_bedrock_response
                usage = extract_usage_from_bedrock_response(response)
                _cost_tracker.add_usage(model, usage["input_tokens"], usage["output_tokens"])
            except Exception:
                pass

            # Mark progress
            _progress.increment()

            return response

    # Token limit protection: Claude models have 200K total context limit (input + output)
    # Dynamically calculate available output tokens based on actual input size
    MODEL_CONTEXT_LIMIT = 200000
    SAFETY_MARGIN = 5000  # Buffer for tokenizer estimation error

    # Estimate input token count (rough: ~4 chars per token)
    total_input_chars = sum(len(msg["content"]) for msg in messages)
    estimated_input_tokens = total_input_chars // 4

    # Calculate maximum available output tokens
    available_output = MODEL_CONTEXT_LIMIT - estimated_input_tokens - SAFETY_MARGIN

    # Adjust max_tokens if it exceeds available space
    if max_tokens > available_output:
        if available_output < 4096:
            # Input is extremely large, use minimum viable output
            print(f"[warn] Input very large (~{estimated_input_tokens} tokens). "
                  f"Only {available_output} tokens available for output. Using minimum 4096.")
            max_tokens = 4096
        else:
            print(f"[info] Requested {max_tokens} output tokens, but only {available_output} available "
                  f"(estimated input: ~{estimated_input_tokens} tokens). Adjusting output to {available_output}.")
            max_tokens = available_output

    async with _model_semaphore:
        body = {
            "max_tokens": max_tokens,
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
        }

        try:
            # Run the blocking API call in a thread pool executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model(
                    modelId=model.get_model_id(),
                    body=json.dumps(body)
                )
            )

            # Read the body once to avoid stream exhaustion
            # The body is a StreamingBody that can only be read once
            body_bytes = response['body'].read()
            response['body'] = body_bytes  # Replace StreamingBody with bytes

            # Extract and track usage for cost estimation
            try:
                from modules.utils.utils import extract_usage_from_bedrock_response
                usage = extract_usage_from_bedrock_response(response)
                _cost_tracker.add_usage(model, usage["input_tokens"], usage["output_tokens"])
            except Exception:
                pass  # Don't fail if usage tracking fails

            return response
        finally:
            # Mark this task as completed for progress tracking
            _progress.increment()


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

