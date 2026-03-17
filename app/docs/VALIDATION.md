# BSP Generator — Validation System Reference

This document describes the complete validation pipeline of the BSP Generator: every check
performed, why it exists, at what stage it runs, how failures are classified, and what
automatic mitigation strategies are available.

---

## Table of Contents

1. [Philosophy and Design Goals](#1-philosophy-and-design-goals)
2. [Pipeline Stages — Execution Order](#2-pipeline-stages--execution-order)
3. [Stage 0 — YAML Schema and Cross-Reference Validation](#3-stage-0--yaml-schema-and-cross-reference-validation)
4. [Stage 1 — Pass 1 Validation (Register Headers)](#4-stage-1--pass-1-validation-register-headers)
5. [Stage 2 — FACTS MIRROR Validation](#5-stage-2--facts-mirror-validation)
6. [Stage 3 — Pass 2 Validation (Driver Implementations)](#6-stage-3--pass-2-validation-driver-implementations)
7. [Stage 4 — Module Contract Check](#7-stage-4--module-contract-check)
8. [Stage 5 — Startup Contract Validation](#8-stage-5--startup-contract-validation)
9. [Stage 6 — Register Parity Guard](#9-stage-6--register-parity-guard)
10. [Stage 7 — CCS Build Gate](#10-stage-7--ccs-build-gate)
11. [Automatic Mitigation — Deterministic Fixes (ti_diagnostics.py)](#11-automatic-mitigation--deterministic-fixes)
12. [Automatic Mitigation — Contract Autofix](#12-automatic-mitigation--contract-autofix)
13. [Automatic Mitigation — LLM Rewrite](#13-automatic-mitigation--llm-rewrite)
14. [Configuration Reference](#14-configuration-reference)
15. [Failure Modes and Return Codes](#15-failure-modes-and-return-codes)
16. [Validation Report Structure](#16-validation-report-structure)
17. [The Bringup Contract](#17-the-bringup-contract)

---

## 1. Philosophy and Design Goals

The BSP Generator uses a large language model to produce C code. LLMs can hallucinate register
addresses, invent function signatures that don't match adjacent modules, omit critical
initialization steps, or write code that compiles cleanly but causes hardware faults at runtime.

The validation system exists to catch all of these failure modes at the earliest possible stage,
before they propagate forward and cause expensive or undetectable failures downstream.

### Design principles

**Fail fast, fail loudly.** Validation runs after each generation pass. A failure in Pass 1
blocks Pass 2 from starting, preventing wasted API calls and obscure downstream errors.

**Every numeric value is traceable.** The FACTS MIRROR protocol requires the LLM to explicitly
declare every constant it will use before writing any code. Post-generation, the validator
confirms each value in the code against its YAML origin. If a value was invented rather than
read from YAML, it is flagged.

**Ordering is as important as presence.** Hardware initialization sequences have strict causal
ordering requirements. Checks confirm not just that required code exists, but that it appears
in the correct order. The most critical example: CLKCNTL must be written before GHVSRC during
PLL initialization; violating this causes a 220 MHz VCLK fault on real silicon (see Section 17).

**Mitigation before escalation.** Most violations are first handled by deterministic autofix
(pure text transformation), then by targeted LLM rewrite, before the pipeline is allowed to
fail. Failing hard is the last resort.

**Configurable gates.** Different environments have different tolerances. Each major gate has
a `mode` setting: `warn` (advisory), `fail` (blocking), or `off` (disabled).

---

## 2. Pipeline Stages — Execution Order

```
python main.py
│
├── Stage 0: YAML Schema + Cross-Reference Validation       ← before any generation
│   ├── Pydantic schema validation (schemas.py)
│   └── Inter-YAML reference checks (cross_reference_validator.py)
│                                                           ABORT on critical error
│
├── Stage 1: Pass 1 Validation (Register Headers)           ← after discovery.py
│   ├── FACTS MIRROR presence + TODO check
│   ├── Base address matching vs. regs.yaml
│   └── Header guard presence
│                                                           ABORT on critical error
│
├── Stage 2: FACTS MIRROR Validation                        ← after each pass
│   ├── Constant traceability check
│   └── Value matching vs. YAML
│                                                           WARN or FAIL (configurable)
│
├── Stage 3: Pass 2 Validation (Driver Implementations)     ← after implementation.py
│   ├── API contract compliance (prototypes vs. manifest)
│   ├── Clock gating presence (PCR_EnablePeripheralClock)
│   ├── Interrupt registration (VIM_RegisterISR)
│   ├── IOMM lock/unlock discipline
│   └── PLL register sequence order
│                                          RETRY × 3 with contract autofix → FAIL
│
├── Stage 4: Module Contract Check                          ← after Pass 2
│   ├── Function signature drift (header ↔ source ↔ manifest)
│   ├── Internal call arity validation
│   ├── Cross-module dependency call validation
│   └── Struct field contract validation (LIN, SCI)
│                                          AUTO-FIX then FAIL (if unresolvable)
│
├── Stage 5: Startup Contract Validation                    ← after Pass 3 (platform gen)
│   ├── Init sequence order (PCR → IOMM → PLL → VIM)
│   ├── Flash wait-state timing (before PLL switch)
│   ├── PLL register sequence (CLKCNTL before GHVSRC)
│   ├── start.s assembly elements
│   └── VIM vector table structure
│                                          WARN or FAIL (gate_mode configurable)
│
├── Stage 6: Register Parity Guard                          ← post-generation
│   ├── Register access ledger extraction
│   └── Sequence comparison vs. known-good baseline
│                                          ADVISORY diff report (advisory by default)
│
└── Stage 7: CCS Build Gate                                 ← post-generation (optional)
    ├── Deterministic TI-specific fixes
    ├── CCS external compilation
    ├── LLM targeted rewrite on failure
    └── Re-compile (up to 4 rounds)
                                           WARN or FAIL (build_gate.mode configurable)
```

---

## 3. Stage 0 — YAML Schema and Cross-Reference Validation

**When:** Before any generation pass begins.
**Modules:** `modules/yaml/schemas.py`, `modules/validation/cross_reference_validator.py`
**Failure mode:** Abort — a broken YAML reference would cause the LLM to hallucinate values.

### 3.1 Pydantic Schema Validation (`schemas.py`)

All nine YAML files are validated against Pydantic v2 models on load.

| File | Key Rules |
|------|-----------|
| `regs.yaml` | Offsets and reset values must be `0x`-prefixed hex strings. Access types must be one of: `RW`, `RO`, `WO`, `RC`, `W1C`, `WC`, `RW1C`. Base addresses must be valid hex. Fields must be a list, not a dict. |
| `soc.yaml` | Peripheral names must be unique. Each peripheral requires `name` and `regs_ref`. `soc.cpu.cores` must be a list. |
| `irq.yaml` | IRQ names and channel numbers must each be unique. Channel numbers must be ≥ 0. |
| `pinmux.yaml` | `package_pin` must be ≥ 0. Each pin must have a non-empty `functions` list. |
| `memmap.yaml` | `start` and `size` must be valid hex strings. |
| `board.yaml` | `name` and `revision` must be non-empty strings. |
| `bringup_contract.yaml` | Baud rate must be > 0. `required_sequence` must be a list of strings. `hal_literal_hclk_hz` must be > 0 if present. |
| `generation_profile.yaml` | `modules.enabled` must be a list of strings. `contract_mode` must be `warn_only` or `auto_fix_then_fail`. |

**Why:** Schema errors mean downstream code would be generated from malformed or missing data,
producing silently wrong drivers. Catching this before any API call is made saves cost and time.

### 3.2 Cross-Reference Validation (`cross_reference_validator.py`)

Verifies that references between YAML files resolve to actual entries.

| Check | Source → Target | What Is Verified |
|-------|----------------|-----------------|
| Peripheral register block | `soc.yaml:peripheral.regs_ref` → `regs.yaml` | The named register block exists |
| Peripheral clock domain | `soc.yaml:peripheral.clock_ref` → `bus.yaml` | The named source or domain exists |
| Peripheral IRQ channels | `soc.yaml:peripheral.irq_ref[]` → `irq.yaml` | Every channel name exists |
| Serial pin numbers | `board.yaml:communication.{uart,lin}.*.{rx,tx}_pin` → `pinmux.yaml` | Package pin number has an entry |

**Why:** If `regs_ref` points to a non-existent block, the LLM receives no register data and
must invent addresses from its training memory — which produces hallucinated hex values that
look plausible but are wrong.

---

## 4. Stage 1 — Pass 1 Validation (Register Headers)

**When:** After `discovery.py` generates `reg_*.h` files and `bsp_manifest.json`.
**Module:** `modules/validation/pass1_validator.py`
**Failure mode:** Critical errors abort the run. Warnings continue.
**Return type:** `Pass1ValidationResult(is_valid, critical_errors, warnings, has_todos)`

### Check 1.1 — FACTS MIRROR TODO Detection

**Pattern searched:** Any `TODO:` text within the FACTS MIRROR block.

```
===== FACTS MIRROR =====
PLL_BASE_ADDRESS = TODO: extract from regs.yaml   ← THIS FAILS
===== END FACTS MIRROR =====
```

**Why:** A TODO in the FACTS MIRROR means the LLM could not find a value in the provided YAML
and left a placeholder instead of inventing one. This is actually a safety feature of the
prompt — but any TODO that reaches validation means there is a gap in the YAML data that must
be resolved before the header can be trusted.

**Failure result:** `has_todos = True`, critical error logged. Generation does not proceed to
Pass 2 until this is resolved.

### Check 1.2 — Base Address Matching

**Pattern:** `#define {MODULE}_BASE 0x[0-9A-Fa-f]+`

Extracts the base address from the generated header and compares it (case-insensitively) to
the `base_address` field for the corresponding block in `regs.yaml`.

**Why:** The most common hallucination failure is a base address that is close to the correct
value but off by a nibble. A mismatched base address causes every register access in the driver
to target the wrong peripheral — producing no output, no interrupt, or a hardware fault — with
no compiler error.

**Failure result:** Critical error: `Base address mismatch — YAML: 0xFFF7E400, Code: 0xFFF7E500`

### Check 1.3 — Header Guards

Verifies that each generated `.h` file contains both `#ifndef` and `#define` directives.

**Why:** Missing header guards cause multiple-inclusion compilation errors in the CCS build
gate. While the CCS gate would catch this, detecting it here provides a clearer error message
and costs no API tokens.

**Failure result:** Warning (non-blocking).

### Check 1.4 — Hardcoded Address Detection

**Pattern:** `\b0x[0-9A-Fa-f]{8}\b` (8-digit hex address literals)
**Exclusions:** `0x00000000`, `0xFFFFFFFF` (common non-address sentinels)

Flags any 8-digit hex literal appearing in register access macros outside of the FACTS MIRROR
block.

**Why:** Addresses should be derived from named `#define` macros, not inlined literals. An
inlined literal cannot be validated against YAML, cannot be refactored, and is invisible to the
parity guard. This check enforces the FACTS POLICY at the structural level.

**Failure result:** Warning listing up to 3 suspicious addresses.

---

## 5. Stage 2 — FACTS MIRROR Validation

**When:** After each generation pass, applied to all generated source files.
**Module:** `modules/validation/validation_engine.py`
**Failure mode:** Configurable — warn or fail.

### How It Works

Every LLM response for a generation pass is required to begin with a FACTS MIRROR block:

```
===== FACTS MIRROR =====
PLL_BASE_ADDRESS          = 0xFFFFFE00
PLLCTL1_OFFSET            = 0x070
CLKCNTL_VCLKR_MASK        = 0x00007800
GHVSRC_PLL1_SOURCE_ID     = 1
===== END FACTS MIRROR =====

===== FILE: include/reg_pll.h =====
...
```

The validator:
1. Parses the mirror block to extract `name → value` pairs
2. Scans all generated `.c` and `.h` files for hex literals
3. Cross-references each literal against the mirror
4. Validates each mirror value against the corresponding YAML field

### Check 2.1 — Mirror Completeness

Every hex constant appearing in the generated code must be declared in the FACTS MIRROR.
Any value in the code but absent from the mirror is flagged as untraced — the LLM used a value
without declaring its source.

### Check 2.2 — Mirror vs. YAML Agreement

Each mirror entry is validated against the YAML:
- Base addresses vs. `regs.yaml:base_address`
- Register offsets vs. `regs.yaml:registers[name].offset`
- Bit masks vs. `regs.yaml:registers[name].fields[name].mask`

Values are compared numerically (normalized from hex/decimal), not as strings.

### Cross-File Conflict Detection

When the same constant name appears in multiple generated modules with different values, the
engine classifies each conflict as acceptable or unacceptable:

- **Acceptable:** Per-instance addresses (e.g., `UART1_BASE` vs `UART2_BASE`), module-specific
  offsets that intentionally differ
- **Unacceptable:** Same peripheral constant with two different values within the same module

**Why:** Cross-file conflicts that are unacceptable mean two drivers will disagree on the
address or mask of a shared resource, producing unpredictable behavior at runtime.

---

## 6. Stage 3 — Pass 2 Validation (Driver Implementations)

**When:** After `implementation.py` generates each `*_driver.h` and `*_driver.c`.
**Module:** `modules/validation/pass2_validator.py`
**Failure mode:** Retry up to 3 rounds with contract autofix; then fail.
**Return type:** `Pass2ValidationResult(is_valid, critical_errors, warnings, has_todos)`

### Key Regex Utilities

```python
# Extract function prototypes (declarations ending with ;)
PROTOTYPE_RE = r"^\s*[A-Za-z_][\w\s\*]*?\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*;\s*$"

# Extract function definitions (with { opening brace)
DEFINITION_RE = r"^\s*[A-Za-z_][\w\s\*]*?\s+([A-Za-z_]\w*)\s*\(([^;{}]*)\)\s*\{"
```

### Check 3.1 — API Contract Compliance

Every function declared in `bsp_manifest.json` for the module must:
- Have a matching prototype in the driver header (name, return type, parameter count)
- Have a matching definition in the driver source

**Why:** If the header declares `lin_status_t LIN_Transmit(const uint8_t* data, uint32_t length)`
but the source defines `void LIN_Transmit(uint8_t data)`, any caller that includes the header
will compile correctly but link to a function with an incompatible stack frame — producing
data corruption at runtime.

**Failure result:** Critical error listing missing or mismatched functions.

### Check 3.2 — Clock Gating Presence

Verifies that each driver's `Init()` function calls `PCR_EnablePeripheralClock()` (or the
equivalent PCR enable sequence) before performing any register access.

**Why:** On the RM46, peripheral clock domains are disabled by default after reset. Accessing a
peripheral's registers before its clock is enabled produces unpredictable results — typically
a bus fault or silent reads returning 0xDEADDEAD. This cannot be caught by the compiler.

**Failure result:** Critical error if the clock enable call is absent from the init function.

### Check 3.3 — Interrupt Registration

For any peripheral whose `soc.yaml` entry includes a non-empty `irq_ref`, verifies that the
driver calls `VIM_RegisterISR()` with the correct channel number.

**Why:** Without registering the ISR in the VIM, hardware interrupts from the peripheral are
routed to the phantom handler (infinite loop) rather than the driver's handler. Polling-based
code may still work, but interrupt-driven modes will silently fail.

**Failure result:** Critical error if `VIM_RegisterISR()` is absent for an IRQ-capable peripheral.

### Check 3.4 — IOMM Lock/Unlock Discipline

Scans every function that calls `IOMM_Unlock()` and verifies that `IOMM_Lock()` is called
before every `return` path in that function. Uses brace-depth tracking to find top-level
`return` statements accurately.

**Why:** The RM46's IOMM pin-mux controller has a hardware protection register (KICK registers).
Once unlocked, the controller accepts pin-mux writes. If a function returns early (e.g., on a
parameter validation failure) without re-locking, the controller remains permanently unlocked
for the rest of the session, making all PINMMR registers vulnerable to accidental modification
by any code that happens to write to the right address range.

**Failure result:** Critical error listing functions with unlock-without-lock return paths.

### Check 3.5 — PLL Register Sequence Order

For `pll_driver.c` specifically, verifies that all required PLL initialization checkpoints
appear in the source text in the correct order.

**Checkpoint patterns (`_pll_sequence_patterns()`):**

| Checkpoint | Regex Patterns Used |
|------------|---------------------|
| disable/set source bits | `\bCSDIS(?:SET\|CLR\|)\b`, `\bSYSTEM_CSDIS(?:SET\|CLR\|)_` |
| write PLLCTL1/PLLCTL2 | `\bPLLCTL1\b`, `\bPLLCTL2\b` |
| poll CSVSTAT | `\bCSVSTAT\b`, `while\s*\([^)]*CSVSTAT`, `\bwait_for_pll(?:[12])?_lock\s*\(` |
| **write CLKCNTL** | `\bCLKCNTL\b` |
| **write GHVSRC** | `\bGHVSRC\b` |
| write RCLKSRC | `\bRCLKSRC\b` |
| write VCLKASRC | `\bVCLKASRC\b` |
| set PENA | `\bPENA\b`, `\bCLKCNTL\b[^;\n]*\|=\s*[^;\n]*PENA` |

Before pattern matching, C/C++ comments are stripped to avoid false positives in doc strings.

The critical ordering constraint: **CLKCNTL must appear before GHVSRC**. This is the
hardware-safety invariant described in Section 17.

**Failure result:** Critical error listing the out-of-order or missing checkpoints.

### Check 3.6 — TODO/FIXME Detection

Scans all generated files for `TODO`, `FIXME`, `XXX` comment markers.

**Failure result:** `has_todos = True`, warning list. Does not by itself block the run, but is
surfaced prominently in the validation report.

### Check 3.7 — Manifest Completeness

Validates the `bsp_manifest.json` entry for each module:
- `init_function` must be a non-empty string
- `functions` must be a non-empty list of objects each containing `name` and `prototype`
- `types` must be a non-empty list of objects each containing `name` and `type`

**Why:** A module entry with missing fields means `dependency_resolver.py` cannot generate a
correct `main.c` call sequence, and `contract_checker.py` has no baseline to validate against.

---

## 7. Stage 4 — Module Contract Check

**When:** After Pass 2, per module.
**Module:** `modules/contracts/contract_checker.py` and `api_contract_manifest.py`
**Failure mode:** Auto-fix (`contract_autofix.py`) then fail if unresolvable.

### 7.1 API Contract Manifest

`api_contract_manifest.py` builds a typed contract for each module by parsing the generated
headers. The manifest records for each function:
- Name, return type, parameter names and types, arity
- Capability role (e.g., `tx_buffer`, `rx_byte`, `tx_ready`)
- Compatibility wrappers that should be generated alongside the primary functions

The manifest is SHA-256 hashed in canonical JSON form, providing an immutable fingerprint
that can be used to detect drift across re-generations.

### 7.2 Contract Checks

| Check | What Is Verified |
|-------|-----------------|
| Declaration/definition coverage | Every public `MODULE_*` function in source has a header declaration, and every declaration has a definition |
| Arity consistency | Header prototype arity matches source definition arity matches manifest entry |
| Internal call arity | Module-internal calls match the definition's arity (catches "too few/too many arguments" before compile) |
| Cross-module call arity | Calls to dependency APIs match the dependency's contract arity |
| LIN `ReceiveByte` timeout | If body references `timeout_ms` but signature doesn't declare it → error |
| Struct field contract | For `bsp_validate.c`, `lin_cfg` and `sci_cfg` field assignments must match the generated `lin_config_t` / `sci_config_t` struct definitions |
| Pin config functional mode | If `lin_config_t` exposes `pin_config` with functional-mode sub-fields, they must be set to `true` — prevents silent loss of terminal output |

### 7.3 Compatibility Wrappers

For LIN and SCI modules, the contract manifest auto-generates a set of compatibility wrappers
so that application code written against a common API name continues to work regardless of what
the LLM chose to name the underlying function:

**LIN wrappers generated automatically:**
- `LIN_SendData(data, length)` → target: `tx_buffer` capability function
- `LIN_Send(data, length)` → target: `tx_buffer` capability function
- `LIN_SendByte(data)` → target: `tx_byte` capability function
- `LIN_IsTxReady()`, `LIN_GetTxStatus()` → target: `tx_ready` capability (returns bool)
- `LIN_IsRxReady()`, `LIN_GetRxStatus()` → target: `rx_ready` capability (returns bool)

Equivalent `SCI_*` wrappers are generated for the SCI module.

---

## 8. Stage 5 — Startup Contract Validation

**When:** After Pass 3 (platform file generation). Also re-evaluated after CCS build gate fixes.
**Module:** `modules/validation/startup_contract_validator.py`
**Configuration:** `startup_contract.gate_mode` — `warn` (advisory) or `fail` (blocking)

### 8.1 System.c Init Sequence Order

Checks that `system.c` calls its initialization functions in the order required by
`bringup_contract.yaml:startup.required_order`:

```
PCR_Init() < PCR_EnableAllPeripherals() < flash_waitstates < PLL_Init()
```

Positions are found using `str.find()` on the stripped source text. If a call is missing or
appears in the wrong order, an error is emitted.

**Why PCR before PLL?** The PCR (Power Control Register) manages the clock domain enables for
all peripherals. If PLL_Init() switches the HCLK source to PLL1 before PCR has enabled the
peripheral clock domains, several peripherals will be running at full PLL speed without their
clock gating being set up, which can cause undefined peripheral behavior.

**Why flash wait-states before PLL?** The RM46 flash controller requires specific read timing
wait-states for different VCLK frequencies. If PLL_Init() increases the clock speed before
flash wait-states are configured, flash reads during instruction fetch can return corrupted
data — a problem that is extremely hard to diagnose because the code appears to execute but
reads wrong values from flash.

### 8.2 PLL Required Sequence

Validates `pll_driver.c` against `bringup_contract.yaml:pll.required_sequence`.

The validator:
1. Strips all C/C++ comments from `pll_driver.c`
2. Extracts the body of the PLL initialization function using brace-depth tracking
3. For each checkpoint in `required_sequence`, finds the earliest regex match position
4. Verifies that positions appear in the required order

**Critical constraint — CLKCNTL before GHVSRC:**
Checkpoint 4 (`write CLKCNTL`) must have a lower position index than checkpoint 5
(`write GHVSRC`). See Section 17 for the full explanation of why.

**Profile-specific validation:**

| Profile | Required Tokens | Additional Checks |
|---------|----------------|-------------------|
| `rm46_hal_aligned` | `GLBSTAT`, `PLLCTL1`, `PLLCTL2`, `RCLKSRC`, `VCLKASRC`, `CLKCNTL`, `PENA` | GLBSTAT clear = `0x00000301`, HAL PLLMUL literal `0xA400` present, `uint64_t` arithmetic used |
| `rm46_trm_dynamic` | `PLLCTL1`, `PLLCTL2`, `CSDISCLR`, `GHVSRC` | Field composition style (`<<` or `SYSTEM_PLLCTL*_` macros), CSVSTAT poll present |

### 8.3 start.s Assembly Contract

Verifies that the generated ARM assembly startup file contains all required elements for the
RM46 Cortex-R4F:

| Required Element | Pattern |
|-----------------|---------|
| `.intvecs` section | `\.sect\s+"\.intvecs"` |
| Reset branch | `\bB\s+(?:Reset_Handler\|Reset_Entry)\b` |
| Undefined instruction handler | `\bB\s+Undef_Handler\b` |
| SVC handler | `\bB\s+SVC_Handler\b` |
| Prefetch abort handler | `\bB\s+Prefetch_Abort_Handler\b` |
| Data abort handler | `\bB\s+Data_Abort_Handler\b` |
| Phantom (spurious IRQ) handler | `\bB\s+Phantom_Handler\b` |
| CPSR mode read | `\bMRS\s+R0,\s*CPSR\b` |
| Mode switching | `\bMSR\s+CPSR_c\b` |
| Stack pointer setup | `\bLDR\s+SP,\s*stack_addr\b` |
| C handoff | `\bBL\s+Reset_Handler_C\b` |
| Stack address label | `^\s*stack_addr\s*:` |
| End-of-stack literal | `\.long\s+end_of_stack\b` |

**VIM vector requirement:** The RM46 routes interrupts through the Vectored Interrupt Manager.
The startup assembly must contain at least 2 instances of `LDR PC, [PC, #-0x1B0]` (the VIM
vector load pattern — one for IRQ, one for FIQ).

**Rejected patterns:**
- `^\s*\.long\s+Reset_Handler\b` — address-word vector tables (3 or more → error; the RM46
  requires executable branch instructions in the vector slots, not address words)
- `^\s*LDR\s+R\d+\s*,\s*=0x[0-9A-Fa-f]+` — GNU-style literal pool loads (TI assembler requires
  `MOVW`/`MOVT` for immediate loads)

### 8.4 Control Flow Checks

The validator uses brace-depth tracking to locate `return` statements at the top level of the
initialization function body (not inside nested conditionals). If any `return` appears before
all required checkpoints have been reached, it is flagged as a potential early-exit that
bypasses critical initialization.

---

## 9. Stage 6 — Register Parity Guard

**When:** Post-generation, after all files are written.
**Module:** `modules/validation/register_parity_guard.py`
**Configuration:** `parity_guard.mode` — `critical_only` (default), `strict`, or `off`
**Baseline:** `parity_guard.baseline_path` (default: `app/output_working_with_manual_changes/`)
**Failure mode:** Advisory diff report by default; blocking if `startup_contract.gate_mode = fail`

### 9.1 Purpose

The parity guard answers the question: **"Does the newly generated BSP write the same values
to the same critical hardware registers as the known-working reference output?"**

A BSP can pass all contract and sequence checks but still write a subtly wrong value to a
critical register — for example, computing the PLLMUL field with a rounding error, or setting
a flash wait-state count that is one cycle off. The parity guard catches this by comparing the
actual sequence of register writes against a baseline that is known to produce correct hardware
behavior (terminal output confirmed on real LAUNCHXL2 board).

### 9.2 Register Access Extraction

The guard scans every generated C source file and extracts register write expressions using
three regex patterns:

1. **Struct member writes:** `base->FIELD op= rhs;`
   - Captures: `base`, `FIELD`, operator (`=`, `|=`, `&=`, etc.), right-hand side
2. **Macro writes:** `SYMBOL op= rhs;`
3. **Pointer-macro writes:** `*SYMBOL op= rhs;`

For each access, it records:
- Source file and line number
- Register symbol (canonical name)
- Address (resolved from struct offset table)
- Operation type: `write`, `rmw_or`, `rmw_and`, `rmw_xor`, etc.
- Right-hand side value
- Domain classification (see below)

### 9.3 Domain Classification

| Domain | Registers |
|--------|-----------|
| `pll_clock` | CSDIS*, GHVSRC, RCLKSRC, VCLKASRC, CSVSTAT, PLLCTL*, CLKCNTL, GLBSTAT |
| `pinmux` | PINMMR*, KICKER* |
| `uart_lin` | SCI*, LIN*, SCIPIO0, GCR0, BRS, FORMAT |
| `pcr_power` | PSPWRDWN*, PCR* |
| `other` | all others |

### 9.4 Analysis Order

Files are analyzed in startup sequence order to produce a meaningful diff:

```
system.c → pcr_driver.c → iomm_driver.c → pll_driver.c → vim_driver.c/vim.c →
gio_driver.c → sci_driver.c → lin_driver.c → main.c
```

### 9.5 Critical Registers Tracked (22)

`CSDIS`, `CSDISSET`, `CSDISCLR`, `CDDIS`, `GHVSRC`, `RCLKSRC`, `VCLKASRC`, `CSVSTAT`,
`PLLCTL1`, `PLLCTL2`, `PLLCTL3`, `CLKCNTL`, `GLBSTAT`, `PINMMR7`, `PINMMR8`, `SCIPIO0`,
`GCR0`, `BRS`, `FORMAT`, `PSPWRDWNCLR0`–`PSPWRDWNCLR3`

### 9.6 Comparison Modes

| Mode | What Is Compared | Blocking |
|------|-----------------|---------|
| `critical_only` | Only the 22 critical registers listed above | Configurable |
| `strict` | All register accesses in all files | Configurable |
| `off` | Nothing | Never |

Comparison uses `difflib.SequenceMatcher` on tokens of the form `{canonical_symbol}:{op}`
(e.g., `CLKCNTL:write`). Differences are classified as `replace`, `delete`, or `insert`.

### 9.7 Output

The guard writes three artifacts to `output_*/forensics/`:
- `register_access_log.csv` — complete ledger of all extracted register accesses
- `forensic_trace.json` — structured JSON with full access metadata
- `parity_diff_report.md` — human-readable diff showing deviations from baseline

---

## 10. Stage 7 — CCS Build Gate

**When:** Post-generation (optional, default enabled).
**Module:** `modules/build/ccs_build_gate.py`
**Configuration:** `build_gate.enabled`, `build_gate.mode`, `build_gate.max_fix_rounds`
**Failure mode:** `strict` (any error fails), `advisory` (warnings tolerated), `off` (skip)

### 10.1 Purpose

Validates that the generated BSP compiles cleanly in the actual TI ARM compiler toolchain
(Code Composer Studio). The CCS compiler applies TI-specific rules that a general-purpose
validator cannot simulate — specific pragma requirements, register access patterns that the TI
compiler rejects, and linker symbol resolution.

### 10.2 Build Iteration Loop

```
Round 0: gmake -k -j16 all
         → parse diagnostics
         → if no errors: DONE

Round 1: apply_deterministic_fixes()   ← no LLM, pure text transform
         → re-sync to CCS workspace
         → re-compile

Round 2: apply_targeted_rewrite()      ← diagnostic-targeted, no LLM
         → re-compile

Round 3+: run_llm_targeted_rewrite()  ← LLM generates a unified diff
          → apply diff
          → re-compile
```

Maximum rounds: `build_gate.max_fix_rounds` (default: 4)

### 10.3 Diagnostic Parsing (`ti_diagnostics.py`)

The TI C compiler emits diagnostics in a format distinct from GCC/Clang:

```
"file.c", line 123: warning #12345: message text
"file.s", ERROR! at line 456: [A1234] message text
error #10050: unresolved symbol 'foo'           ← linker, no file
```

Each diagnostic is parsed into: file, line, severity, TI error code, message text.

File scoring for targeted rewrites:
- Severity: error = 100 pts, warning = 20 pts
- File type: `.c`/`.h` = +30, `.s`/`.asm` = +25, `.cmd` = +10
- Message keywords: "undefined" / "too few arguments" / "expected" = +20 each
- Linker-only (no file): −50

Top `build_gate.llm_rewrite.top_k_files` (default: 2) are selected for LLM rewrite.
`bsp_validate.c` and `main.c` are excluded from LLM rewrite (too many dependencies).

---

## 11. Automatic Mitigation — Deterministic Fixes

**Module:** `modules/build/ti_diagnostics.py`

Before any LLM is invoked, the build gate applies up to 16 deterministic text-transformation
fixes. These are ordered to apply safely in sequence.

| Fix | What It Does | Why It Is Needed |
|-----|-------------|-----------------|
| `_fix_system_flash_register_member_drift` | Replaces `SYS->FRDCNTL` with `FLASH_FRDCNTL_REG` macro | LLM sometimes accesses FLASH registers via the SYSTEM peripheral struct instead of the FLASH macro |
| `_fix_missing_flash_waitstate_helper` | Injects `system_setup_flash_waitstates()` call if invoked but not defined | LLM may call the helper without generating its definition |
| `_fix_system_init_order` | Reorders: `PCR_Init → PCR_EnableAllPeripherals → flash_waitstates → PLL_Init` | Enforces the startup contract ordering if it was violated in generated `system.c` |
| `_fix_pcr_enable_all_semantics` | Synthesizes `PCR_EnableAllPeripherals()` from individual `PSPWRDWNCLR` writes | Some generations produce direct PSPWRDWN writes instead of a helper function |
| `_fix_entry_data_bss_copy_sizes` | Fixes `.data`/`.bss` copy: multiplies count by `sizeof(uint32_t)` in size calc, not in `memcpy`/`memset` args | Common off-by-4 in startup copy loops |
| `_fix_pll_init_runtime_regressions` | (a) Fixes ODPLL encoding: `ODPLL << shift` → `(ODPLL-1) << shift`; (b) enforces CLKCNTL before GHVSRC; (c) converts CLKCNTL direct assignment to read-modify-write | Three separate PLL regressions that appear in generated code |
| `_fix_bsp_validate_gio_level_token` | Maps `GIO_LEVEL_HIGH` to the actual enum/literal from the generated header | GIO level enum name varies across generations |
| `_fix_start_reset_vector_branch` | Inserts `B Reset_Handler` in `.intvecs` section if missing | Required for RM46 reset vector; assembler may omit it |
| `_fix_start_asm_literal_loads` | Converts `LDR R0,=0x12345678` → `MOVW R0,#0x5678; MOVT R0,#0x1234` | TI assembler does not support GNU literal pool syntax |
| `_fix_vim_filename_drift` | Renames `vim.h` → `vim_driver.h` throughout | Generated code may use the old filename |
| `_fix_vim_include_name_drift` | Replaces `#include "vim.h"` with `#include "vim_driver.h"` | Same as above for include directives |
| `_fix_lin_clear_interrupt_macro_drift` | Scans `reg_lin.h` for actual `LIN_SCICLEARINT_CLR_*` macros; replaces any undefined ones with `0U` fallback | Macro names vary based on which register fields the LLM generated |
| `_fix_lin_zero_timeout_nonblocking` | Adds `if (timeout_ms == 0U) return ...;` to `wait_rx_ready()` | Prevents blocking forever on a zero-timeout receive call |
| `_fix_gio_base_alias_drift` | Adds `#define gioREG ((volatile GIO_REG_MAP_t*)GIO_BASE_ADDRESS)` if missing | LLM may use `gioREG` without generating the alias macro |
| `_fix_driver_base_alias_drift` | Normalizes base register aliases to canonical macros per module | Different generations use different alias naming conventions |
| `_apply_contract_autofixes` | Runs `contract_autofix.py` (LIN, IOMM, bsp_validate) | Applies all behavioral contract fixes described in Section 12 |

### Targeted Fix Routing

When a specific file is the primary error source, fixes are applied in a targeted order:

| Failing File | Primary Fix | Fallback Fix |
|-------------|------------|-------------|
| `start.s` | reset_vector_branch | asm_literal_loads |
| `system.c` | flash_register_member_drift | missing_flash_waitstate_helper |
| `pcr_driver.c` | driver_base_alias_drift | pcr_enable_all_semantics |
| `lin_driver.c` | lin_zero_timeout_nonblocking | lin_clear_interrupt_macro_drift |
| `gio_driver.c` | vim_include_name_drift | gio_base_alias_drift |
| `entry.c` | entry_data_bss_copy_sizes | — |
| `pll_driver.c` | pll_init_runtime_regressions | — |
| `bsp_validate.c` | bsp_validate_gio_level_token | — |

---

## 12. Automatic Mitigation — Contract Autofix

**Module:** `modules/contracts/contract_autofix.py`
**Trigger:** Contract check failure with `contract_mode = auto_fix_then_fail`
**Max rounds:** 3 (per module)

Contract autofix applies targeted behavioral corrections without invoking the LLM. It operates
on two classes of issues:

### 12.1 IOMM Pin-Mux Encoding Fixes

**Problem:** The RM46's PINMMR fields use one-hot 8-bit encoding for pin functions. The LLM
sometimes generates code with 3-bit ordinal encoding instead.

**Fixes applied:**
1. `IOMM_FUNCTION_BITS_MASK` changed from `0x07U` → `0xFFU`
2. `IOMM_BITS_PER_FUNCTION` changed from `3U` → `8U`
3. Pin function writes converted: `((uint32_t)function & mask) << shift`
   → `((1U << (uint32_t)function) & mask) << shift` (one-hot)
4. Ordinal switch assignments: `function_value = 0x03;`
   → `function_value = (1U << (uint32_t)function);`

### 12.2 LIN/SCI Capability Normalization

**RX function arity:** If the `ReceiveByte` function has arity < 2, removes the second argument
from all callsites. If arity ≥ 2, adds `0U` as timeout where missing.

**TX buffer wrapper management:** Ensures `LIN_Send`/`LIN_SendData` wrappers exist and call
the correct underlying capability function with the correct arity. Fills missing arguments
with `0U` (length) or `100U` (timeout_ms).

**Clear interrupt macro repair:** Scans `reg_lin.h` for defined `LIN_SCICLEARINT_CLR_*` macros
and replaces any undefined reference with `LIN_SCICLEARINT_CLR_BE_INT` or `0U` as fallback.

### 12.3 bsp_validate Autofix

The generated `bsp_validate.c` test harness is subject to API drift when the underlying driver
functions change names or arities across generations. The autofix:

1. **API renaming:** Maps generic capability names (`LIN_SendData`, `LIN_ReceiveByte`) to the
   actual function names discovered in the generated headers
2. **Arity normalization:** Rewrites all call sites to match the contract arity
   (fills missing args with `0U` for data, `100U` for timeout, `LIN_STATUS_OK` for status)
3. **Malformed cast repair:** Fixes artifacts like `(uint8_t, 0U)` → `(uint8_t)` left by
   previous arity-fix passes
4. **LIN config field mapping:** Renames `lin_cfg.data_length` → `lin_cfg.data_bits` if the
   generated struct uses the latter name; removes assignments to fields that don't exist in
   the generated `lin_config_t`
5. **Pin config functional mode injection:** If the generated `lin_config_t` has functional-mode
   sub-fields (`tx_functional_mode`, `rx_functional_mode`), inserts assignments setting them to
   `true` — this is critical for terminal output on the LAUNCHXL2

---

## 13. Automatic Mitigation — LLM Rewrite

**Module:** `modules/build/llm_rewrite.py`
**Trigger:** CCS build gate still failing after deterministic and targeted fixes
**Max attempts:** `build_gate.llm_rewrite.max_attempts` (default: 1 per round)
**Max rounds:** up to `build_gate.max_fix_rounds` (default: 4)
**Apply policy:** `hybrid` (tries unified diff first, falls back to full-file blocks)

### 13.1 Target File Selection

Files are scored by error severity and relevance:
- Errors score 100 pts each, warnings 20 pts each
- `.c`/`.h` files get +30 pts, `.s` files +25 pts, `.cmd` files +10 pts
- "undefined", "too few arguments", "expected" keywords each add 20 pts
- Linker-only errors (no file) subtract 50 pts

Top `top_k_files` (default: 2) are selected. `bsp_validate.c` and `main.c` are excluded.

### 13.2 Prompt Structure

The LLM rewrite prompt is carefully constrained to minimize scope:

```
[Hard constraints]
- ONLY edit files in the allowed list: [lin_driver.c, pll_driver.c]
- Do NOT create new files
- Make minimal edits focused on the compilation errors
- Do NOT alter API signatures

[Output format]
- Unified diff ONLY (--- old/file +++ new/file format)
- No full-file replacements unless diff application fails

[Compiler diagnostics]
lin_driver.c:47 [error] undefined reference to 'LIN_SCICLEARINT_CLR_BE_INT'
pll_driver.c:82 [error] too few arguments to function 'PLL_GetFrequency'

[API contract context] (if include_contract_context = true)
Module LIN:  LIN_Transmit arity=2,  LIN_ReceiveByte arity=2
Module PLL:  PLL_GetFrequency arity=1

[Bringup contract context]
serial.primary_path = LIN_SCI_MODE
lin.required_registers.SCIPIO0 = 0x00000006

[File context]
===== FILE CONTEXT: lin_driver.c =====
[full source]
===== SIBLING CONTEXT: lin_driver.h =====
[full header]
===== RELATED REGISTER HEADER: reg_lin.h =====
[register definitions]
```

### 13.3 Response Validation

Before applying the LLM's proposed diff, it is validated:
- **New `#include` directives:** All added includes must reference files that exist in the
  output directory (prevents adding includes for headers that don't exist)
- **Base register aliases:** If the diff adds a struct member access `newREG->field`, the
  base alias must either already be defined in a canonical header or be defined locally via
  `#define` in the same diff

### 13.4 Application Strategy

1. **Unified diff:** Parse `--- old/file` / `+++ new/file` / `@@ hunk @@` blocks. Apply each
   hunk with fuzzy matching (search ±120 lines from expected position, then global search).
2. **Full-file fallback:** If any hunk fails to apply, attempt to find
   `===== FILE: path =====\n[content]` blocks in the response and replace the full file.

---

## 14. Configuration Reference

All settings are in `generation_profile.yaml` or `DEFAULT_GENERATION_PROFILE` in `main.py`.

### Validation Settings

| Setting | Default | Values | Effect |
|---------|---------|--------|--------|
| `strict_validation` | `false` | bool | Promote warnings to errors for critical modules |
| `contract_mode` | `auto_fix_then_fail` | `warn_only`, `auto_fix_then_fail` | How to handle contract violations |
| `contract_lock_mode` | `strict` | `strict`, `relaxed` | `strict` = preserve canonical manifest; `relaxed` = hydrate from actual headers |

### Startup Contract Settings

| Setting | Default | Values | Effect |
|---------|---------|--------|--------|
| `startup_contract.gate_mode` | `warn` | `warn`, `fail` | `fail` blocks the run on contract violation |

### Parity Guard Settings

| Setting | Default | Values | Effect |
|---------|---------|--------|--------|
| `parity_guard.mode` | `critical_only` | `critical_only`, `strict`, `off` | Which registers are compared |
| `parity_guard.baseline_path` | `app/output_working_with_manual_changes` | path | Known-good reference output |
| `parity_guard.critical_registers` | [22 register names] | list of strings | Which registers trigger failures |

### Build Gate Settings

| Setting | Default | Values | Effect |
|---------|---------|--------|--------|
| `build_gate.enabled` | `true` | bool | Run CCS compilation |
| `build_gate.mode` | `strict` | `strict`, `advisory`, `off` | `strict` = fail on error; `advisory` = warnings ok |
| `build_gate.max_fix_rounds` | `4` | int | Max compile→fix→recompile cycles |
| `build_gate.llm_rewrite.enabled` | `true` | bool | Use LLM for compilation error fixes |
| `build_gate.llm_rewrite.top_k_files` | `2` | int | How many error files to include in LLM context |
| `build_gate.llm_rewrite.apply_policy` | `hybrid` | `hybrid`, `diff_only`, `full_file_only` | How to apply LLM response |
| `build_gate.llm_rewrite.max_tokens` | `6000` | int | Token budget for rewrite call |

---

## 15. Failure Modes and Return Codes

| Code | Trigger | Stage | Recovery |
|------|---------|-------|---------|
| `0` | Success | End of run | — |
| `1` | YAML cross-reference validation failed | Stage 0 | Fix the broken reference in the relevant YAML file |
| `2` | Startup contract or parity guard gate failed | Stage 5/6 | Fix init ordering in `soc.yaml` or `prompt.py`; check CLKCNTL/GHVSRC order |
| `3` | CCS compile gate failed (strict mode) | Stage 7 | Check `ccs_build_log.txt`; may need to adjust generation profile or run with `build_gate.mode: advisory` |
| `4` | App intent validation failed | Post-gen | Fix board component references in the intent prompt |
| `5` | Post-gen firmware generation failed | Post-gen | Fix firmware intent or generation settings |

### Per-Module Failure Behavior

Pass 2 module failures are isolated: a failed module is marked in the report but the run
continues so that other modules can complete. The final validation summary reports the
overall success rate (valid modules / total modules).

---

## 16. Validation Report Structure

Two files are written to the output directory:

**`validation_report.json`** — machine-readable structured results
**`validation_report.md`** — human-readable Markdown summary

### JSON Top-Level Keys

```json
{
  "timestamp": "20260302T211427",
  "bsp_output_dir": "/path/to/output_20260302_211427",
  "validation_summary": {
    "total_modules": 8,
    "modules_valid": 7,
    "modules_invalid": 1,
    "critical_errors": 2,
    "warnings": 5,
    "success_rate": 87.5
  },
  "peripheral_validations": {
    "PLL": {
      "module_name": "PLL",
      "facts_mirror_valid": true,
      "constants_validated": 12,
      "mismatches": 0,
      "tests_generated": false,
      "critical_errors": [],
      "warnings": []
    }
  },
  "compile_contract": { "passes": true, "checks": 8, "errors": [], "warnings": [] },
  "startup_contract": { "passes": true, "errors": [], "warnings": [], "checks": {} },
  "critical_sequence_mismatches": [
    {
      "kind": "order_mismatch",
      "baseline": { "file": "pll_driver.c", "line": 42, "canonical_symbol": "CLKCNTL", "op": "write" },
      "candidate": { "file": "pll_driver.c", "line": 51, "canonical_symbol": "CLKCNTL", "op": "write" }
    }
  ],
  "build_evidence": {
    "mode": "generator_ccs_build_gate",
    "passes": true,
    "rounds": 2,
    "llm_rewrite_attempted": true,
    "llm_rewrite_applied": true,
    "llm_rewrite_tokens": { "input_tokens": 4812, "output_tokens": 387 }
  },
  "runtime_invariants": {
    "startup_contract_gate_mode": "warn",
    "build_gate_enabled": true,
    "build_gate_mode": "strict",
    "parity_guard_mode": "critical_only",
    "parity_guard_passes": true,
    "startup_contract_passes": true
  },
  "api_contract_hash": "a3f8c2..."
}
```

---

## 17. The Bringup Contract

`app/yaml_in/bringup_contract.yaml` encodes the hardware-level safety constraints that the
generator must enforce. It is the authoritative source for the startup contract validator.

### 17.1 The CLKCNTL/GHVSRC Ordering Constraint

This is the most critical constraint in the entire project. Violating it causes a hardware
fault on real RM46 silicon with no software-visible error.

**Background:**

The RM46 has a peripheral clock (VCLK) derived from the system clock (HCLK) via a programmable
divider:

```
VCLK = HCLK / (VCLKR + 1)
VCLKR is encoded in the CLKCNTL register
VCLK maximum = 110 MHz (datasheet absolute maximum)
```

At reset, `VCLKR = 0`, so `VCLK = HCLK / 1 = HCLK`.

The PLL initialization sequence must switch the system clock source from the low-speed
oscillator (16 MHz OSCIN) to PLL1 (220 MHz HCLK) by writing the GHVSRC register.

**If CLKCNTL is written after GHVSRC:**
1. GHVSRC switches source to PLL1 → HCLK = 220 MHz
2. CLKCNTL has not yet been written → VCLKR still = 0 (reset value)
3. VCLK = HCLK / 1 = 220 MHz → **exceeds 110 MHz peripheral limit**
4. Hardware fault (typically a memory protection or CPU abort)

**Correct sequence:**
```
1. Poll CSVSTAT until PLL1 valid (bits 1 and 6 set = 0x42)
2. Write CLKCNTL with VCLKR = 1          ← VCLK = HCLK/2 when source switches
3. Write GHVSRC → PLL1                   ← HCLK = 220 MHz, VCLK = 110 MHz ✓
4. Write RCLKSRC, VCLKASRC
5. Write CLK2CNTRL, VCLKACON1
6. Set PENA
```

This constraint is enforced by:
- `pass2_validator.py:_pll_sequence_patterns()` (checks order in source text)
- `startup_contract_validator.py:_validate_pll_required_sequence()` (checks order in function body)
- `ti_diagnostics.py:_fix_pll_init_runtime_regressions()` (deterministically corrects if violated)

### 17.2 Complete Constraint Catalog

| Constraint | Register / Location | Required Value / Order | Failure Consequence |
|-----------|--------------------|-----------------------|---------------------|
| CLKCNTL before GHVSRC | `pll_driver.c` | CLKCNTL write must precede GHVSRC write | 220 MHz VCLK → hardware fault |
| SCIPIO0 functional mode | `lin_driver.c` | `0x00000006` (TX=bit2, RX=bit1) | LIN/SCI pins remain in GPIO mode; no serial output |
| No COMM_MODE bit | `lin_driver.c` | SCIGCR1 bit 0 must NOT be set | 9-bit framing (address-bit mode) → frame errors on 8N1 terminal |
| Pin 38 mux (SCIRX) | `iomm_driver.c` | PINMMR7 bit 17, AF=1 | SCIRX not connected to USB-UART; no input |
| Pin 39 mux (SCITX) | `iomm_driver.c` | PINMMR8 bit 1, AF=1 | SCITX not connected to USB-UART; no output |
| IOMM unlock before PINMMR | `iomm_driver.c` | KICK_REG0=0x83E70B13, KICK_REG1=0x95A4F1E0 | PINMMR writes are silently ignored |
| IOMM lock after PINMMR | `iomm_driver.c` | KICK_REG0=0x0 | Controller left permanently unlocked |
| Flash wait-states before PLL | `system.c` | `FLASH_FRDCNTL = 0x00000311` before PLL_Init() | Corrupted flash reads after clock speed increase |
| PCR enable before peripherals | `system.c` or `main.c` | PCR_EnableAllPeripherals() before any peripheral init | Peripheral registers inaccessible (clock domain off) |
| HCLK = 220 MHz encoding | `pll_driver.c` | HAL PLLMUL literal `0xA400`, uint64_t arithmetic | Wrong CPU frequency; all baud rates and timers miscalibrated |
| CSVSTAT poll before clock switch | `pll_driver.c` | Poll bits 1+6 (mask 0x42) before GHVSRC write | Clock switch while PLL not locked → unstable HCLK |

---

*See also:*
- *[ARCHITECTURE.md](ARCHITECTURE.md) — Full system architecture reference*
- *[STATEDIAGRAM.md](STATEDIAGRAM.md) — Runtime state diagram*
- *`app/yaml_in/bringup_contract.yaml` — Machine-readable constraint source*
- *`app/output_working_with_manual_changes/` — Parity guard baseline (known-good output)*
