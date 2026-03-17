# BSP Generator — Architecture Reference

**Target Hardware:** LAUNCHXL2-TMS57012-RM46 (TI Hercules RM46L852, Cortex-R4F @ 220 MHz)
**Generator Host:** Python 3.12+ · AWS Bedrock (Claude API)
**Entry Point:** `app/main.py`
**Scope:** Complete pipeline — YAML hardware descriptions → LLM generation → validated C BSP → (optional) firmware from user prompt

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Repository Structure](#2-repository-structure)
3. [YAML Input System](#3-yaml-input-system)
4. [Invocation and Terminal Input Parsing](#4-invocation-and-terminal-input-parsing)
5. [Core Generation Pipeline](#5-core-generation-pipeline)
6. [Prompt Engineering](#6-prompt-engineering)
7. [AWS Bedrock API Integration](#7-aws-bedrock-api-integration)
8. [Output File Writing and Code Normalization](#8-output-file-writing-and-code-normalization)
9. [Dependency Resolution](#9-dependency-resolution)
10. [Validation Pipeline](#10-validation-pipeline)
11. [Firmware Generation from User Prompt](#11-firmware-generation-from-user-prompt)
12. [Progress Tracking and UX](#12-progress-tracking-and-ux)
13. [Output Directory Structure](#13-output-directory-structure)
14. [Critical Hardware Constraints](#14-critical-hardware-constraints)

---

## 1. Executive Summary

The BSP Generator reads nine YAML hardware-description files that together describe the TI RM46
Hercules microcontroller and the LAUNCHXL2-TMS57012-RM46 LaunchPad board. It orchestrates three
sequential LLM generation passes via AWS Bedrock (Claude), then writes a complete, compilable C
Board Support Package into a timestamped output directory.

The complete output includes:
- Register struct/enum typedefs for every peripheral (`reg_*.h`)
- HAL driver headers and implementations (`*_driver.h` / `*_driver.c`)
- ARM Cortex-R4 startup assembly (`start.s`)
- Reset vector entry point (`entry.c`)
- TI linker script (`linker.cmd`)
- Vectored interrupt manager (`vim_driver.c`)
- Topologically-ordered initialization entry point (`main.c`)

After the BSP is generated, an optional fourth stage invites the user to describe a firmware task
in natural language (e.g., "blink LED2 when S3 is pressed and echo the event to the terminal").
The generator validates the described intent against the available board components and then
invokes the LLM a final time to produce application-layer firmware that calls into the BSP.

> **Important:** The generation pipeline makes many Claude API calls and can take several minutes.
> Never run it automatically. Always prompt the user to invoke `python main.py` manually.

---

## 2. Repository Structure

```
BSP-Generator/
├── app/
│   ├── main.py                          # Entry point + full orchestration (4 651 lines)
│   ├── yaml_in/                         # YAML hardware description inputs (see Section 3)
│   │   ├── soc.yaml
│   │   ├── regs.yaml
│   │   ├── irq.yaml
│   │   ├── memmap.yaml
│   │   ├── bus.yaml
│   │   ├── pinmux.yaml
│   │   ├── board.yaml
│   │   ├── bringup_contract.yaml
│   │   └── generation_profile.yaml
│   ├── modules/
│   │   ├── generation/
│   │   │   ├── discovery.py             # Pass 1: register header + manifest generation
│   │   │   ├── implementation.py        # Pass 2: driver .h/.c generation
│   │   │   ├── prompt.py                # Prompt builders + Bedrock API calls + cost tracking
│   │   │   └── pin_config_builder.py    # IOMM/pin configuration helpers
│   │   ├── yaml/
│   │   │   └── yaml_utils.py            # YAML loading, Pydantic schema validation, slicing
│   │   ├── utils/
│   │   │   ├── user.py                  # Interactive peripheral selection menu
│   │   │   ├── file_io.py               # File splitting (===== FILE: =====), safe writes
│   │   │   ├── unified_progress.py      # Hierarchical ANSI progress display
│   │   │   └── dependency_resolver.py   # Dependency graph + topological sort + main.c gen
│   │   ├── validation/
│   │   │   ├── pass1_validator.py        # Pass 1 output: reg headers, FACTS MIRROR
│   │   │   ├── pass2_validator.py        # Pass 2 output: API contracts, PLL sequence order
│   │   │   ├── startup_contract_validator.py  # Init sequence safety (CLKCNTL-before-GHVSRC)
│   │   │   ├── cross_reference_validator.py   # Inter-YAML ref consistency
│   │   │   ├── register_parity_guard.py       # Register trace vs. known-good baseline
│   │   │   ├── validation_engine.py     # FACTS MIRROR constant comparison
│   │   │   └── validation_integration.py     # Validation orchestration layer
│   │   ├── contracts/
│   │   │   ├── contract_checker.py      # Contract compliance evaluation
│   │   │   ├── contract_autofix.py      # LLM-based auto-repair for violations
│   │   │   └── api_contract_manifest.py # API/contract catalog management
│   │   ├── build/
│   │   │   ├── ccs_build_gate.py        # External CCS compilation gate
│   │   │   ├── llm_rewrite.py           # LLM-based compilation error fix (up to 4 rounds)
│   │   │   └── ti_diagnostics.py        # TI-specific deterministic register corrections
│   │   ├── intent/
│   │   │   ├── board_capabilities.py    # Board component → BSP API mapping
│   │   │   └── post_generation_prompt.py  # Firmware generation from user intent
│   │   └── regeneration/
│   │       ├── token_strategy.py        # Adaptive token allocation (historical data)
│   │       └── retry_wrapper.py         # Generation retry wrapper
│   ├── tests/                           # pytest suite
│   └── output_*/                        # Timestamped output directories (one per run)
└── README.md
```

---

## 3. YAML Input System

All nine files in `app/yaml_in/` are the authoritative source of truth for the project. Every
register address, bit mask, pin assignment, clock divider, and initialization sequence in the
generated C code is ultimately derived from these files. The generation pipeline never invents
numeric values — it extracts them from YAML and embeds them verbatim via the FACTS MIRROR
mechanism (see Section 6.2).

### 3.1 File Reference

| File | Size | Role |
|------|------|------|
| `soc.yaml` | 70 KB | Peripheral catalog: type, instance, `regs_ref`, `clock_ref`, `irq_ref`, `x-ext.init` sequences |
| `regs.yaml` | 407 KB | Register blocks: base addresses, offsets, bit fields, access types (RW / RO / WO / RC / W1C) |
| `irq.yaml` | 24 KB | VIM interrupt channel assignments and IRQ source mappings |
| `memmap.yaml` | ~1 KB | Memory map: FLASH origin/length, RAM origin/length (used in linker script) |
| `bus.yaml` | 26 KB | Clock tree: PLL1/PLL2 config, domain hierarchy (GCLK / HCLK / VCLK), divider fields, source IDs |
| `pinmux.yaml` | 28 KB | 144-pin IOMM multiplex table: `package_pin`, alternate functions, PINMMR register + bit position |
| `board.yaml` | 23 KB | Board-level capabilities: LEDs, buttons, connectors, power regulators, voltage rails |
| `bringup_contract.yaml` | 2.1 KB | Safety contracts: required PLL register sequence, pin config requirements, flash wait states |
| `generation_profile.yaml` | 2.1 KB | User-tunable generation settings: enabled modules, model, validation strictness, build gate |

### 3.2 soc.yaml — Peripheral Definitions

Each peripheral entry in `soc.yaml` carries:

```yaml
- name: LIN
  type: serial
  instance: LIN1
  regs_ref: LIN_REGS          # → key in regs.yaml
  clock_ref: VCLK              # → domain name in bus.yaml
  irq_ref: [LIN0_LEVEL0]      # → entries in irq.yaml
  x-ext:
    init:
      - op: write
        reg: SCIGCR0
        value: "0x00000001"   # Take LIN out of reset
      - op: write
        reg: SCIGCR1
        value: "0x03000000"   # TX enable, RX enable (SCI mode)
      - op: write
        reg: SCIPIO0
        value: "0x00000006"   # TX=bit2, RX=bit1 → functional (not GPIO) mode
```

The `x-ext.init` sequences are extracted and used both to drive the generated
driver code and to validate it against the bringup contract.

### 3.3 bus.yaml — Clock Topology

Defines the complete clock tree from the 16 MHz external crystal through PLL1/PLL2 to all
peripheral clock domains:

```
OSCIN (16 MHz xtal)
  └─ PLL1 (NF=120, NR=6, ODPLL=2 → HCLK = 220 MHz)
       ├─ GCLK  = HCLK  = 220 MHz  (CPU)
       ├─ HCLK  = HCLK  = 220 MHz  (AHB bus)
       └─ VCLK  = HCLK / (VCLKR+1)  = 110 MHz max  (peripheral bus)
```

The `x-ext.source_ids` field provides the numeric values for GHVSRC, RCLKSRC, and VCLKASRC
registers, which the PLL driver must write in the correct order (see Section 14).

### 3.4 bringup_contract.yaml — Safety Contracts

This file encodes hardware initialization constraints that, if violated, cause faults at runtime
on real silicon:

- **PLL sequence order**: CLKCNTL must be written before GHVSRC (see Section 14)
- **Serial pin config**: Pins 38 (SCIRX) and 39 (SCITX) must be muxed to IOMM functional mode
- **SCIPIO0 value**: Must be `0x00000006` for LIN/SCI operational mode
- **IOMM unlock sequence**: Two magic writes to KICK_REG0/KICK_REG1 must bracket all pin-mux ops
- **Flash wait states**: Must be configured before any PLL speed change
- **Startup order**: `PCR_Init → PCR_EnableAllPeripherals → flash_waitstates → PLL_Init`

The `startup_contract_validator.py` and `pass2_validator.py` parse this file and enforce all
constraints against the generated code before it is accepted.

### 3.5 generation_profile.yaml — Run Configuration

Controls the behavior of a specific generation run:

```yaml
target_board: LAUNCHXL2-TMS57012-RM46
modules:
  enabled: [SCI, GIO, LIN, PLL, IOMM, PCR, SYSTEM, VIM]
sci:
  default_baud: 9600
contract_mode: auto_fix_then_fail    # auto-repair violations, then fail if unresolvable
parity_guard:
  mode: critical_only
  baseline_path: app/output_working_with_manual_changes
  critical_registers: [CSDIS, GHVSRC, CLKCNTL, SCIPIO0, PINMMR7, PINMMR8, ...]  # 22 regs
build_gate:
  enabled: true
  mode: strict
  llm_rewrite:
    enabled: true
    top_k_files: 2
app_intent:
  enabled: true
  intent_refs_mode: proven_only
  generate_firmware_pass: true
  post_gen_max_tokens: 8000
```

The in-code default (`DEFAULT_GENERATION_PROFILE` at `main.py:193`) is used when no YAML profile
is present. A loaded profile shallow-merges over the defaults, section by section.

---

## 4. Invocation and Terminal Input Parsing

### 4.1 CLI Arguments

```
python main.py [OPTIONS]
```

| Argument | Default | Purpose |
|----------|---------|---------|
| `--out PATH` | auto-timestamped | Output directory for all generated files |
| `--model MODEL` | `haiku4.5` | Claude model: `haiku4.5`, `sonnet4.5`, `opus4.6` |
| `--yamlpath PATH` | `yaml_in` | Directory containing the 9 YAML config files |
| `--max-tokens N` | adaptive | Token budget per generation pass |
| `--targets LIST` | `all` | Components to generate: `all`, `startup`, `entry`, `system`, `clock`, `linker`, `vim`, `peripherals` |
| `--modules LIST` | (from profile or menu) | Specific peripherals: `SCI LIN GIO` etc. |
| `--yes` | false | Skip cost confirmation prompt |
| `--menu` | false | Force open interactive action menu |
| `--validate-only` | false | Run validation only on an existing output dir (no generation) |
| `--action ACTION` | (menu) | High-level action: `generate`, `validate`, `postgen_prompt`, `postgen_generate`, `compile_only`, `docs_only`, `reflash` |
| `--profile PATH` | auto-detected | Path to generation profile YAML |
| `--no-profile` | false | Ignore any profile file; use in-code defaults |
| `--post-gen-prompt` | false | After BSP generation, pause for app intent input |
| `--post-gen-generate` | false | After intent input, invoke firmware generation pass |

### 4.2 Interactive Action Menu

When invoked with no arguments (or `--menu`), the generator presents:

```
BSP Generator — Action Menu
  1. Full BSP generation
  2. Validate existing output
  3. Post-gen prompt only
  4. Post-gen prompt + firmware generation
  5. Compile gate only (re-run CCS build)
  6. Docs only (Doxygen)
  7. Reflash existing output to board
```

The selected option sets `args.action` internally and may prompt for an existing output directory
(options 2, 5, 6, 7).

### 4.3 Peripheral Selection — 3-Strategy Hierarchy

Once YAML is loaded and the generation profile is resolved, the set of peripherals to generate
is determined by the following priority order:

```
Priority 1: --modules CLI flag
            e.g.  --modules SCI LIN GIO
            → Immediately accepted; no confirmation prompt

Priority 2: generation_profile.yaml → modules.enabled
            User is asked: "Use modules from loaded profile? [Y/n]:"
            → Accepted on Y; falls through to Priority 3 on N

Priority 3: Interactive menu
            Displays table: Index | Name | Type | Instance | Clock Ref
            Accepts:   "a" or "all"  → all peripherals
                       "1,3,5"       → by index
                       "GIO,MIBSPI1" → by name
                       "1,GIO"       → mixed
            Shows confirmation with metadata; must confirm before proceeding
```

**Note:** SCI is handled by a separate code path (baud rate, SCIPIO0 config). PCR and SYSTEM are
CORE modules — always included regardless of user selection and never shown in the menu.

### 4.4 Cost Estimation Gate

Before generation begins, the user is shown:

```
Model:             Claude Haiku 4.5
Modules:           8
Estimated tokens:  ~42,000
Estimated cost:    ~$0.03 USD

Proceed with generation? [Y/n]:
```

Skipped automatically with `--yes`. Token estimates come from `token_strategy.py`, which
maintains a history of actual token usage for each module×model combination and projects forward.

---

## 5. Core Generation Pipeline

### 5.1 Module Categories

The generator partitions all modules into two categories:

```
CORE_MODULES  (always included, cannot be deselected)
  SYSTEM  — base system registers (PCR, flash wait states)
  PCR     — power/clock enable gating for all peripherals
  IOMM    — I/O multiplexing controller (must run before any peripheral using pins)
  PLL     — phase-locked loop clock management (must run before any peripheral using VCLK)
  VIM     — vectored interrupt manager

USER_MODULES  (selected by user at runtime)
  LIN, SCI, GIO, CAN, I2C, SPI, ADC, DMA, MibSPI, N2HET, etc.
```

### 5.2 Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  YAML Inputs (9 files)                                               │
│  soc · regs · irq · memmap · bus · pinmux · board · contracts       │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  load + cross-validate
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PASS 1 — DISCOVERY          discovery.py                           │
│  Modules: CORE + USER                                                │
│  Input:   soc.yaml + regs.yaml slices                               │
│  Output:  reg_*.h (register typedefs)                               │
│           bsp_manifest.json (API catalog)                            │
│  Validates: Pass1Validator (FACTS MIRROR, base addresses)           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  bsp_manifest.json
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PASS 2 — IMPLEMENTATION     implementation.py                      │
│  Modules: PLL + IOMM + PCR + USER (up to 15 concurrent)            │
│  Input:   manifest + reg_*.h + YAML slices + dependency headers     │
│  Output:  *_driver.h  *_driver.c                                    │
│  Validates: Pass2Validator (contracts, PLL sequence order)          │
│  Retries:  up to 3 rounds with ContractAutoFix                      │
└──────────────────────────────┬───────────────────────────────────────┘
                               │  driver headers + implementations
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  PASS 3 — PLATFORM FILES     (parallel generation)                  │
│  system.c/h  entry.c  start.s  vim_driver.c/h  linker.cmd          │
│  main.c  (topologically sorted by dependency_resolver.py)           │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  POST-GENERATION (optional)                                          │
│  StartupContractValidation → ParityGuard → CCS BuildGate            │
│  → BoardCapabilityManifest → AppIntentPrompt → FirmwareGeneration   │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 Pass 1 — Discovery

**Entry point:** `modules/generation/discovery.py` → `run_discovery_pass()`

For each module in `CORE + USER`:

1. **Slice YAML** — `yaml_utils.py:make_regs_slice_for_refs()` extracts only the register blocks
   that belong to this peripheral from the 407 KB `regs.yaml`
2. **Build prompt** — `prompt.py:build_discovery_prompt()` wraps the slice in the system prompt
   and instructs the LLM to generate:
   - Register struct typedefs (e.g., `pll_reg_map_t`)
   - Bit-field enums and masks
   - A JSON manifest entry declaring the module's exported types and functions
3. **Invoke model** — Bedrock API call; response contains `===== FILE: =====` delimited outputs
4. **Extract files** — `file_io.py:split_and_write_files()` parses response and writes `reg_*.h`
5. **Validate** — `pass1_validator.py` checks base addresses, header guards, FACTS MIRROR
6. **Update manifest** — accumulates per-module entries into `bsp_manifest.json`

**Output of Pass 1:**
- `include/reg_pll.h`, `include/reg_sci.h`, `include/reg_gio.h`, ... (one per module)
- `bsp_manifest.json` — API catalog referenced throughout Pass 2 and Pass 3

### 5.4 Pass 2 — Implementation

**Entry point:** `modules/generation/implementation.py` → `run_implementation_pass()`

For each module in `PLL + IOMM + PCR + USER` (run concurrently, semaphore = 15):

#### Sub-phase 2A — Driver Header

1. **Build prompt** — `prompt.py:build_pass2_driver_h_prompt()`
   - Includes Pass 1 manifest entries for this module (typedef names must match exactly)
   - Includes `soc.yaml` peripheral slice (clock_ref, irq_ref)
2. **Invoke model** → `*_driver.h`

#### Sub-phase 2B — Driver Source

1. **Build dependency context** — collects function signatures from all drivers that this module
   depends on (e.g., LIN driver needs `PLL_EnableClock()`, `VIM_RegisterISR()`)
2. **Build prompt** — `prompt.py:build_pass2_driver_c_prompt()`
   - Includes `regs.yaml` slice, `soc.yaml` init sequences, `irq.yaml` entries
   - Injects dependency headers as context
   - FACTS MIRROR requirement: all hex constants must appear in the mirror block before code
3. **Invoke model** → `*_driver.c`
4. **Postprocess** — `_postprocess_generated_code()` fixes include paths, IOMM one-hot encoding,
   unlock/lock discipline, PCR compat helpers
5. **Validate** — `pass2_validator.py` checks API contracts and PLL register sequence order
6. **Auto-fix loop** — if validation fails and `contract_mode = auto_fix_then_fail`:
   - `contract_autofix.py` constructs a targeted fix prompt
   - Re-generates the offending file only
   - Re-validates (up to 3 rounds total)

### 5.5 Pass 3 — Platform Files

Six files are generated in parallel, each with its own prompt:

| File | Prompt function | Key inputs |
|------|----------------|-----------|
| `system.c/h` | `build_system_init_prompt()` | `bus.yaml` (top-level domains only), PCR register block |
| `entry.c` | `build_entry_prompt()` | CPU model from `soc.yaml`, stack sizes |
| `start.s` | `build_startup_prompt()` | CPU model, FPU/MPU/TCM flags from `soc.yaml` |
| `vim_driver.c/h` | `build_vim_prompt()` | `irq.yaml` full channel table |
| `linker.cmd` | `build_linker_prompt()` | `memmap.yaml` regions |
| `main.c` | `dependency_resolver.py` (deterministic, no LLM) | `bsp_manifest.json` dependency graph |

`main.c` is the only file not generated by the LLM — it is produced deterministically by
`dependency_resolver.py` after a topological sort of the dependency graph (see Section 9).

---

## 6. Prompt Engineering

### 6.1 System Prompt (Global Rules)

All generation calls share a common system prompt (`build_system_prompt()` in `prompt.py`) that
establishes absolute rules for all generated code:

- **Language:** C11 standard, ISO C89-compatible (no VLAs, no C99 designated initializers)
- **Documentation:** Doxygen-style comments required on all exported functions
- **FACTS POLICY:** All numeric literals (addresses, masks, dividers, frequencies) must come
  verbatim from the provided YAML data. Inventing values is forbidden.
- **Register access:** Only the access type declared in YAML is permitted (RW / RO / WO / RC / W1C)
- **Output format:** Files are delimited by `===== FILE: <relative/path> =====` markers.
  The FACTS MIRROR block must appear before the first FILE marker.

### 6.2 FACTS MIRROR Protocol

Before generating any code, the LLM is required to emit a FACTS MIRROR block that explicitly
lists every numeric constant it will use, cross-referenced to the YAML source:

```
===== FACTS MIRROR =====
PLL_BASE_ADDRESS          = 0xFFFFFE00    # regs.yaml: PLL_REGS.base_address
PLLCTL1_OFFSET            = 0x070         # regs.yaml: PLL_REGS.PLLCTL1.offset
CLKCNTL_VCLKR_MASK        = 0x00007800    # regs.yaml: SYSTEM_REGS.CLKCNTL.VCLKR.mask
GHVSRC_PLL1_SOURCE_ID     = 1             # bus.yaml: x-ext.source_ids.ghvsrc_pll1_source_id
===== END FACTS MIRROR =====
```

Post-generation, `validation_engine.py` parses the FACTS MIRROR and the generated C code,
comparing all hex literals to ensure traceability. Any constant found in the code but absent
from the mirror, or any mirror value that does not match the YAML source, is flagged as a
validation error.

### 6.3 Pass-Specific Prompts

| Function | Pass | Output |
|----------|------|--------|
| `build_discovery_prompt()` | 1 | `reg_*.h` + manifest JSON |
| `build_pass2_driver_h_prompt()` | 2A | `*_driver.h` (must reuse Pass 1 typedef names exactly) |
| `build_pass2_driver_c_prompt()` | 2B | `*_driver.c` (includes dependency context) |
| `build_clock_prompt()` | 2 | `clock.c/h` with `PLL_EnableClock()`, `PLL_GetFrequency()` |
| `build_system_init_prompt()` | 3 | `system.c/h` (PCR control, CLKENA bit) |
| `build_vim_prompt()` | 3 | `vim_driver.c/h` (ISR registration, vector table) |
| `build_entry_prompt()` | 3 | `entry.c` (reset handler, FPU init) |
| `build_startup_prompt()` | 3 | `start.s` (stack init, TCM, MPU, FPU) |
| `build_linker_prompt()` | 3 | `linker.cmd` (MEMORY/SECTIONS from memmap.yaml) |

### 6.4 Dependency Context Injection (Pass 2B)

Each driver's source-generation prompt includes the function signatures of all drivers it
depends on. This prevents the LLM from guessing API shapes:

```c
// Injected context for LIN driver:
// From pll_driver.h:
void PLL_EnableClock(clock_domain_t domain);
uint32_t PLL_GetFrequency(clock_domain_t domain);

// From vim_driver.h:
void VIM_RegisterISR(uint32_t channel, void (*isr)(void), vim_priority_t priority);
void VIM_EnableChannel(uint32_t channel);
```

---

## 7. AWS Bedrock API Integration

### 7.1 Client Configuration

```python
# modules/generation/prompt.py
client = boto3.client("bedrock-runtime", region_name="us-east-1")
# Read timeout: 300s (5 minutes)
# Retry policy: max 3 attempts (boto3 default)
# Auth: AWS_BEARER_TOKEN_BEDROCK environment variable
```

### 7.2 Invocation

```python
async def invoke_model(model: Model, max_tokens: int, messages: list[Message]) -> str
```

- **Concurrency:** `asyncio.Semaphore(15)` limits simultaneous in-flight requests
- **Token budget:** `available = min(max_tokens, 200_000 - input_token_count - 5_000)`
  (5 K safety margin to avoid context overflow errors)
- **Adaptive sizing:** `token_strategy.py` uses a rolling history of actual token usage per
  module×model to dynamically right-size `max_tokens` for each call
- **Minimum floor:** 4096 tokens guaranteed even when context is large

### 7.3 Response Processing

The Bedrock API returns a `StreamingBody`. The generator reads it exactly once (stream
exhaustion protection), decodes the JSON, and calls `extract_usage_from_bedrock_response()`
to record input/output token counts for cost tracking.

### 7.4 Cost Tracking

`_CostTracker` in `prompt.py` maintains thread-safe per-model token counters and computes
real-time USD cost estimates using current Bedrock pricing tables. Costs are displayed live
in the progress UI throughout generation.

---

## 8. Output File Writing and Code Normalization

### 8.1 File Splitting (`file_io.py`)

The LLM response for each pass is a single text block containing multiple files separated by
named markers. `split_and_write_files()` uses the regex:

```python
r'^===== FILE: (.+) =====\s*$'
```

to split the response into individual files. Each file path is validated for safety
(no absolute paths, no `..` traversal, no symlink tricks) before writing.

The preamble before the first FILE marker (containing the FACTS MIRROR) is saved to
`_artifacts/llm_preamble_<timestamp>.txt` for audit.

### 8.2 Code Postprocessing (`implementation.py`)

After the LLM response is split, `_postprocess_generated_code()` applies deterministic fixes:

- **Missing includes:** Injects `#include` directives for any referenced headers not present
- **IOMM one-hot encoding:** Ensures pin function values use one-hot 8-bit encoding as specified
  in `pinmux.yaml`
- **IOMM lock discipline:** Every pin-mux write sequence must be bracketed by `IOMM_Unlock()`
  and `IOMM_Lock()` calls; missing locks are injected
- **PCR compatibility:** Adds `PCR_EnableAllPeripherals()` helper where needed
- **Flash register normalization:** Normalizes `system.c` FLASH register access to the pattern
  expected by the startup contract validator

### 8.3 Generation Metadata

Every generated file is prepended with a metadata comment:

```c
/* BSP-GEN-META: created_at=2026-03-02T21:14:27; output_folder=output_20260302_211427; output_tag=v1.2 */
```

This allows tracing any file back to the exact generation run that produced it.

---

## 9. Dependency Resolution

`modules/utils/dependency_resolver.py` provides deterministic, LLM-free generation of `main.c`.

### 9.1 Graph Construction

`build_dependency_graph(manifest, soc_data, selected_modules)`:

- Nodes are created for every module (CORE + USER)
- Edges are extracted from the `dependencies` field in each module's `bsp_manifest.json` entry
- CORE modules (SYSTEM, PCR, IOMM, PLL, VIM) are always present as root-reachable nodes

### 9.2 Topological Sort

`topological_sort(graph)` uses Kahn's algorithm:
- Detects and reports circular dependencies before they cause issues
- Returns a deterministic `InitOrder` with the canonical init sequence

**Canonical order for default module set:**

```
SYSTEM → PCR → IOMM → PLL → VIM → SCI → GIO → LIN
```

### 9.3 main.c Generation

`generate_main_c(order, manifest, profile)` writes `main.c` with:
- `#include` directives in topological order
- A single `BSP_Init()` function that calls each module's `<MODULE>_Init()` in sequence
- Optional modules (SCI, GIO, etc.) enabled/disabled based on the generation profile
- CORE modules (SYSTEM, PCR, IOMM, PLL, VIM) always enabled

---

## 10. Validation Pipeline

The validation pipeline runs at multiple checkpoints. Failures at earlier stages prevent wasted
API calls on downstream passes. Each stage has a distinct *purpose* — what category of defect
it is designed to catch.

### 10.1 Stage Summary

| Stage | When | Guarding Against | Failure Mode |
|-------|------|-----------------|--------------|
| YAML cross-ref | Before generation | Missing or invalid inter-YAML references | Abort |
| Pass 1 gate | After Discovery | Address hallucinations, incomplete register typedefs | Abort on critical |
| FACTS MIRROR | After each pass | Numeric constants that don't trace back to YAML | Warn or fail |
| Pass 2 gate | After Implementation | API drift, missing clock/interrupt wiring, wrong PLL register order | Retry × 3 → autofix → fail |
| Startup contract | After Pass 3 | Wrong init sequence order — can cause hardware fault at power-on | Warn or fail (gate_mode) |
| Parity guard | Post-generation | Register value drift vs. known-good baseline across re-generations | Advisory diff |
| Contract check | Post-generation | Any remaining contract violations after all passes | Autofix → fail |
| CCS build gate | Post-generation | Code that fails to compile in the actual TI toolchain | LLM rewrite → fail |

### 10.2 YAML Cross-Reference Validation (`cross_reference_validator.py`)

**What it guards against:** Generating code that references a register block, clock domain, or
IRQ channel that does not exist in the YAML inputs. This would cause the LLM to hallucinate
values for the missing data.

Checks performed:
- Every `regs_ref` in `soc.yaml` resolves to a block in `regs.yaml`
- Every `clock_ref` resolves to a source or domain in `bus.yaml`
- Every entry in `irq_ref[]` resolves to a channel in `irq.yaml`
- Pin function names in `soc.yaml` match alternate function entries in `pinmux.yaml`

### 10.3 Pass 1 Validation (`pass1_validator.py`)

**What it guards against:** Register headers that contain invented addresses or are structurally
broken in ways that would silently corrupt Pass 2 output.

Checks performed:
- FACTS MIRROR block is present and contains no `TODO` placeholders (a TODO means the LLM
  could not extract a value from the YAML and guessed instead)
- All peripheral base addresses in the generated struct match the `base_address` field in `regs.yaml`
- Standard C header guards (`#ifndef PERIPH_H` / `#define PERIPH_H` / `#endif`) are present
- No bare hex literals appear in register access macros outside of the FACTS MIRROR block

### 10.4 FACTS MIRROR Validation (`validation_engine.py`)

**What it guards against:** Constants in the generated C code that do not match the YAML source
of truth, meaning the LLM invented or misread a value.

Checks performed:
- Parses the FACTS MIRROR preamble to extract all declared constant → value pairs
- Scans generated C source for all hex literals
- Cross-references each literal against the mirror; flags any value present in code but absent
  from the mirror, or any mirror value that doesn't match the YAML

### 10.5 Pass 2 Validation (`pass2_validator.py`)

**What it guards against:** Driver implementations that are structurally correct C but
functionally wrong — API shape mismatch, missing peripheral wiring, or a dangerous clock
register sequence.

Checks performed:
- All exported function prototypes match the shapes declared in `bsp_manifest.json` (name,
  return type, parameter count) — prevents API incompatibility across drivers
- `PCR_EnablePeripheralClock()` is called in each driver's `Init()` function — ensures the
  peripheral clock domain is enabled before any register is touched
- For peripherals with an `irq_ref`, `VIM_RegisterISR()` is called — ensures interrupt routing
  is configured before the peripheral can fire an IRQ
- `IOMM_Lock()` is present before every `return` path in functions that called `IOMM_Unlock()`
  — prevents the pin-mux controller being left unlocked after an early return
- **PLL register sequence order** (`_pll_sequence_patterns()`): for `pll_driver.c`, verifies
  that CLKCNTL appears before GHVSRC in the source text. This is the single most safety-critical
  check in the entire pipeline (see Section 14.1 for why this matters)

### 10.6 Startup Contract Validation (`startup_contract_validator.py`)

**What it guards against:** An init sequence that will cause a hardware fault at power-on, or
that initializes peripherals before their dependencies are ready.

Checks performed against `bringup_contract.yaml:startup.required_order`:
- `PCR_Init()` is called before any peripheral driver init (clock gating must be set up first)
- `IOMM` configuration precedes any peripheral that uses physical pins
- `PLL_Init()` is called, and within it the PLL required_sequence is present and ordered:
  - CSDIS (disable clock sources) → PLLCTL1/PLLCTL2 (configure PLL) → poll CSVSTAT (wait for
    lock) → **CLKCNTL** (set VCLKR divider) → GHVSRC (switch source to PLL1) → RCLKSRC → PENA
- No `return` statement appears before the critical init steps complete
- C/C++ comments are stripped before matching to avoid false positives in doc strings

Configurable via `startup_contract.gate_mode`:
- `warn` — logs violation, continues generation
- `fail` — halts the run immediately

### 10.7 Register Parity Guard (`register_parity_guard.py`)

**What it guards against:** Subtle register-value drift between generation runs — where the
generator produces syntactically valid and contract-passing code, but the actual values written
to critical hardware registers differ from a known-working reference.

How it works:
- Builds a complete register access ledger from the generated C source: for each write, records
  file, line number, register symbol, address, and value
- Compares against the ledger from `app/output_working_with_manual_changes/` (the reference
  output confirmed to produce terminal output on real hardware)
- Tracks 22 critical registers: CSDIS, GHVSRC, CLKCNTL, SCIPIO0, PINMMR7, PINMMR8, PLLCTL1,
  PLLCTL2, CSVSTAT, RCLKSRC, VCLKASRC, CLK2CNTRL, and others
- Analysis order follows the startup sequence: `system.c → pcr_driver.c → iomm_driver.c →
  pll_driver.c → vim.c → gio_driver.c → sci_driver.c → lin_driver.c → main.c`
- Outputs a diff report to `validation_report.md`; does not block the run (advisory only)

### 10.8 Contract Auto-Fix (`contract_autofix.py`)

**What it guards against:** Contract violations that the initial generation produced but that
are deterministically fixable without a full re-generation.

When `contract_mode = auto_fix_then_fail` (default) and a violation is detected:

1. Violation is categorized: wrong register value, missing required write, wrong ordering
2. A targeted LLM prompt is built embedding: the contract requirement, the exact offending
   code, and the correct expected pattern
3. Only the single violating file is regenerated — not the entire pass
4. The file is re-validated; the cycle repeats up to 3 times
5. If unresolved after 3 rounds, the run fails with the specific violation message

### 10.9 CCS Build Gate (`ccs_build_gate.py`)

**What it guards against:** Generated code that is logically correct but fails to compile in
the actual TI ARM compiler toolchain (type errors, missing symbols, TI-specific pragma issues).

Steps:
1. `ti_diagnostics.py` applies deterministic pre-corrections for known TI toolchain quirks
   (e.g., specific FLASH register access patterns that the TI compiler rejects)
2. CCS is invoked on the full BSP source tree; compiler output is parsed
3. If errors are found, `llm_rewrite.py` constructs a fix prompt from the compiler error text
   and regenerates only the files referenced in the errors
4. Up to 4 compile → rewrite cycles before the gate fails

Modes (`build_gate.mode`):
- `strict` — any compiler error fails the gate
- `advisory` — warnings are tolerated; only errors fail
- `off` — skip compilation entirely

---

## 11. Firmware Generation from User Prompt

This is the capstone feature that demonstrates the full end-to-end value of the generator:
from hardware YAML description all the way to compiled, flashable application firmware.

### 11.1 Activation

The firmware generation stage is reached via any of:

| Path | How |
|------|-----|
| Interactive menu | Option 4: "Post-gen prompt + firmware generation" |
| CLI flag | `--post-gen-generate` |
| CLI flag | `--post-gen-prompt` (intent capture only, no generation) |
| Profile | `app_intent.enabled: true` + `generate_firmware_pass: true` |
| Action | `--action postgen_generate` |

### 11.2 Board Capability Manifest

Generated automatically at the end of Pass 3. Maps board-level components (user-facing names)
to concrete BSP driver API calls:

```json
{
  "LED2": {
    "driver": "gio_driver",
    "init_function": "GIO_Init",
    "set_function": "GIO_SetPin",
    "clear_function": "GIO_ClearPin",
    "port": "GIO_PORT_B",
    "pin": 1
  },
  "S3": {
    "driver": "gio_driver",
    "read_function": "GIO_ReadPin",
    "port": "GIO_PORT_B",
    "pin": 2,
    "active_low": true
  },
  "SCI_TERMINAL": {
    "driver": "sci_driver",
    "write_function": "SCI_WriteByte",
    "read_function": "SCI_ReadByte",
    "baud": 9600
  }
}
```

Written to `board_capability_manifest.json` and `board_capabilities.h`. This manifest is the
vocabulary that constrains the user intent prompt.

### 11.3 App Intent Prompt (Interactive)

```
═══════════════════════════════════════════════════════════
 BSP Generation Complete — Firmware Intent
═══════════════════════════════════════════════════════════
 Available components:
   LED2, LED3, S3, SCI_TERMINAL, GIO_PORTB_PIN4, LIN1

 Enter firmware intent:
 (e.g., "blink LED2 at 1 Hz and print S3 press count to terminal")
> _
```

Input is validated by `board_capabilities.py`:
- `proven_only` mode (default): only components with a confirmed generated driver are allowed
- Referenced component names are resolved against the board capability manifest
- Unknown references are rejected with a list of valid names

### 11.4 Firmware Generation Pass

Implemented in `modules/intent/post_generation_prompt.py`:

1. **System prompt:** Full BSP driver headers (`*_driver.h`) are embedded as context, giving the
   LLM complete knowledge of all available API functions and types
2. **User prompt:** Validated intent string + board capability manifest + firmware constraints:
   - Use polling or ISR (consistent with BSP driver model)
   - No heap allocation (`malloc`/`free` forbidden)
   - Interrupt-safe patterns for shared state
3. **Invocation:** Single LLM call with `post_gen_max_tokens` budget (default: 8000)
4. **Output:** `firmware_main.c` and any helper files, written to the output directory
5. **Optional compile gate:** If `build_gate.enabled`, the firmware files are compiled together
   with the BSP; LLM rewrite applies on failure (up to 4 rounds)

### 11.5 End-to-End Data Flow

```
app/yaml_in/*.yaml          (9 hardware description files)
        │
        ▼ load + validate
YAML data structures
        │
        ▼ Pass 1 (Discovery)
reg_*.h + bsp_manifest.json
        │
        ▼ Pass 2 (Implementation)
*_driver.h + *_driver.c
        │
        ▼ Pass 3 (Platform)
system.c  entry.c  start.s  vim.c  linker.cmd  main.c
        │
        ▼ Post-gen validation + parity guard + CCS build
Validated BSP
        │
        ▼ Board capability manifest
board_capability_manifest.json + board_capabilities.h
        │
        ▼ User types: "blink LED2 and print S3 presses to terminal"
Intent validated against manifest
        │
        ▼ Firmware generation pass (LLM + BSP headers as context)
firmware_main.c
        │
        ▼ CCS compile gate + LLM rewrite (up to 4 rounds)
Compiled binary → flash to board
```

---

## 12. Progress Tracking and UX

`UnifiedProgressManager` (`modules/utils/unified_progress.py`) provides a hierarchical display
that runs throughout the entire generation process.

### 12.1 Tracked Passes

| Pass | Label | Description |
|------|-------|-------------|
| 1 | Discovery | Register header + manifest generation |
| 2 | Implementation | Driver header + source generation |
| 3 | Platform | system, entry, startup, VIM, linker, main |
| 4 | Validation | Startup contract + parity guard |
| 5 | Post-Gen Intent | Board capability manifest + user prompt |
| 6 | Post-Gen Firmware | Firmware generation from intent |
| 7 | Post-Gen Compile | CCS build gate for firmware |
| 8 | Docs | Doxygen HTML generation |

### 12.2 Display Modes

| Mode | Trigger | Description |
|------|---------|-------------|
| `fancy` | default (TTY detected) | Unicode box drawing, ANSI colors, 10 FPS spinner |
| `simple` | `--simple` flag | Plain text progress lines, no ANSI |
| `quiet` | `--quiet` flag | Errors only |

Per-pass display includes: task count (success/failure), ETA, elapsed time, token spend (K),
and running USD cost.

---

## 13. Output Directory Structure

Each generation run creates a new timestamped directory. Nothing is overwritten or deleted.

```
output_20260302_211427/
├── include/
│   ├── reg_pll.h              Pass 1: PLL register struct typedefs
│   ├── reg_sci.h              Pass 1: SCI register struct typedefs
│   ├── reg_gio.h              Pass 1: GIO register struct typedefs
│   ├── reg_lin.h              Pass 1: LIN register struct typedefs
│   ├── reg_iomm.h             Pass 1: IOMM register struct typedefs
│   ├── reg_pcr.h              Pass 1: PCR register struct typedefs
│   ├── reg_system.h           Pass 1: SYSTEM register struct typedefs
│   ├── reg_vim.h              Pass 1: VIM register struct typedefs
│   ├── pll_driver.h           Pass 2: PLL driver API
│   ├── sci_driver.h           Pass 2: SCI driver API
│   ├── gio_driver.h           Pass 2: GIO driver API
│   ├── lin_driver.h           Pass 2: LIN driver API
│   ├── iomm_driver.h          Pass 2: IOMM driver API
│   ├── pcr_driver.h           Pass 2: PCR driver API
│   ├── system.h               Pass 3: system init API
│   ├── vim.h                  Pass 3: VIM driver API
│   └── board_capabilities.h   Post-gen: board component map
├── source/
│   ├── pll_driver.c           Pass 2: PLL implementation
│   ├── sci_driver.c           Pass 2: SCI implementation
│   ├── gio_driver.c           Pass 2: GIO implementation
│   ├── lin_driver.c           Pass 2: LIN implementation
│   ├── iomm_driver.c          Pass 2: IOMM implementation
│   ├── pcr_driver.c           Pass 2: PCR implementation
│   ├── system.c               Pass 3: system init
│   ├── vim.c                  Pass 3: interrupt vector table
│   ├── entry.c                Pass 3: reset vector entry point
│   ├── start.s                Pass 3: ARM Cortex-R4 startup assembly
│   ├── main.c                 Pass 3: topologically-ordered BSP init
│   └── firmware_main.c        Post-gen: application firmware (if generated)
├── linker.cmd                 Pass 3: TI linker script
├── bsp_manifest.json          Pass 1 output: complete API catalog
├── api_contract_manifest.json Contract definitions
├── board_capability_manifest.json  Post-gen: board component registry
├── validation_report.json     Structured validation results
├── validation_report.md       Human-readable validation summary
├── generation_log_20260302_211427.txt  Full generation log
└── _artifacts/
    ├── llm_raw_pll_20260302_211427.txt        Raw LLM response for PLL
    ├── llm_preamble_pll_20260302_211427.txt   FACTS MIRROR block for PLL
    ├── pll_driver_system_prompt.txt           System prompt used for PLL
    ├── pll_driver_user_prompt.txt             User prompt used for PLL
    └── ...                                    (similar per module per pass)
```

---

## 14. Critical Hardware Constraints

### 14.1 The CLKCNTL-Before-GHVSRC Rule

This is the most safety-critical constraint in the entire project. Violating it causes a hardware
fault on real RM46 silicon.

**Background:**

The RM46's system clock is derived from PLL1 via a chain of dividers:

```
PLL1 → HCLK = 220 MHz
VCLK = HCLK / (VCLKR + 1)       VCLKR field in CLKCNTL register
VCLK maximum = 110 MHz           (RM46 datasheet limit)
```

At reset, `VCLKR = 0`, so `VCLK = HCLK / 1 = HCLK`.

The PLL initialization sequence must switch the system clock source (GHVSRC register) from the
low-speed oscillator to PLL1. If CLKCNTL is not written first to set `VCLKR = 1`, then the
moment GHVSRC switches to PLL1, `VCLK = 220 MHz`, which exceeds the 110 MHz peripheral limit
and causes a system fault.

**Required order (enforced by `bringup_contract.yaml`):**

```
1. Poll CSVSTAT until PLL1 valid (bits 1 and 6 both set → 0x42)
2. Write CLKCNTL with VCLKR = 1        ← pre-divide BEFORE switching source
3. Write GHVSRC → source = PLL1        ← now VCLK = 220 MHz / 2 = 110 MHz ✓
4. Write RCLKSRC, VCLKASRC
5. Write CLK2CNTRL, VCLKACON1
6. Set PENA
```

**Validation enforcement:**

Both `pass2_validator.py:_pll_sequence_patterns()` and `startup_contract_validator.py` verify
this order using regex pattern matching on the generated `pll_driver.c` source. The generation
pipeline will not accept output where GHVSRC appears before CLKCNTL.

### 14.2 IOMM Unlock/Lock Discipline

All writes to PINMMR registers (pin multiplexing) must be bracketed:

```c
IOMM_Unlock();          // Write magic values to KICK_REG0 and KICK_REG1
// ... PINMMR writes ...
IOMM_Lock();            // Write 0x0 to KICK_REG0
```

The postprocessor and `pass2_validator.py` enforce that every code path that calls
`IOMM_Unlock()` also calls `IOMM_Lock()` before returning.

### 14.3 SCIPIO0 Functional Mode

For the LIN/SCI peripheral to operate (not as GPIO), pin bits 1 (RX) and 2 (TX) must be set
in `SCIPIO0`:

```c
linREG->SCIPIO0 = 0x00000006U;   // bit2=TX functional, bit1=RX functional
```

Setting `COMM_MODE` (bit 0 of SCIGCR1) to 1 switches the framing to 9-bit (address-bit mode),
which is incompatible with standard 8N1 terminals. The generation prompt explicitly prohibits
this: `NEVER write gcr1_value |= LIN_SCIGCR1_COMM_MODE`.

---

*Generated by BSP Generator v1.x — See [STATEDIAGRAM.md](STATEDIAGRAM.md) for the runtime state diagram.*
