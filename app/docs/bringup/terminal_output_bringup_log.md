# Terminal Output Bring-Up Log (RM46)

## Context
- Goal: get deterministic terminal output over SCI/LIN (USB path) with generated BSP.
- Policy: modify generated output first to isolate root cause, then backport into pipeline.

## 2026-02-28 Changes

### 1) Initial compile/runtime unblock
- File: `app/output_20260228_133957/include/main.c`
- Changes:
  - Added explicit SCI pinmux setup (pins 38/39, plus pin 133 for LED path).
  - Enabled `PCR_EnableAllPeripherals()`.
  - Added SCI smoke test and heartbeat logic.
- Reason:
  - Establish a minimal observable runtime behavior.
- Pipeline backport target:
  - main template generation and runtime smoke test template.

### 2) HAL-aligned PLL init sequence
- File: `app/output_20260228_133957/include/pll_driver.c`
- Changes:
  - Replaced simplified PLL flow with HAL-style ordering and register writes:
    - `CSDISSET` disable PLL1/PLL2, clear `GLBSTAT`, program `PLLCTL1/2/3`,
      apply `CSDIS`, `CDDIS`, valid-source poll, `GHVSRC/RCLKSRC/VCLKASRC`,
      divider setup, and final R-divider update.
  - Added bounded polling (timeout) to prevent hard-lock during bring-up.
  - Added debug stage marker (`g_pll_debug_stage`) for debugger inspection.
- Reason:
  - Generated PLL values/order diverged from known working HAL code.
- Pipeline backport target:
  - PLL generation templates and clock-domain source mapping logic.

### 3) Frequency model fixes
- File: `app/output_20260228_133957/include/pll_driver.c`
- Changes:
  - `PLL_GetPLLFrequency()` routes PLL1 through `PLL_CalculateHCLKFrequency()`.
  - `PLL_CalculateHCLKFrequency()` handles HAL encoded `PLLMUL=0xA400`.
  - Uses 64-bit arithmetic for fallback frequency math.
- Reason:
  - Linear interpretation of `PLLMUL` produced incorrect VCLK and baud calculations.
- Pipeline backport target:
  - bus/clock semantic model and PLL frequency helper generation.

### 4) SCI + LIN runtime path validation
- File: `app/output_20260228_133957/include/main.c`
- Changes:
  - Initialized both SCI and LIN (LIN in SCI mode) at 9600.
  - Added periodic TX markers on both paths (`'A'` via SCI, `'B'` via LIN).
  - Added banner strings for both paths and dual RX echo polling.
- Reason:
  - Working HAL behavior indicates LIN path is the known USB-visible path.
- Pipeline backport target:
  - generated smoke test app and board-profile serial path defaults.

### 5) HAL register value alignment corrections
- File: `app/output_20260228_133957/include/pll_driver.c`
- Changes:
  - `CSDIS` updated from `0x88` to `0x8C` to match HAL config.
  - `RCLKSRC/VCLKASRC` updated to use HAL `SYS_VCLK` source ID `9` (not `2`).
- Reason:
  - Source ID mismatch can silently break peripheral/RTI timing domains.
- Pipeline backport target:
  - clock source enum mapping and generated register constants.

### 6) Startup data/bss copy bug fix
- File: `app/output_20260228_133957/include/entry.c`
- Changes:
  - Corrected `memcpy/memset` sizes from word-count to byte-count:
    - multiply by `sizeof(uint32_t)`.
- Reason:
  - Incorrect section init can produce unstable runtime behavior/debug artifacts.
- Pipeline backport target:
  - startup template (`entry.c`) generation.

### 7) Exception vector architecture fix (Cortex-R4)
- File: `app/output_20260228_133957/include/start.s`
- Changes:
  - Replaced Cortex-M style `.long` vector table with Cortex-R executable vector instructions.
  - Added dedicated handlers for undef/svc/prefetch/data-abort/phantom instead of routing all exceptions to `Reset_Handler`.
  - Kept IRQ/FIQ vector fetch via `LDR PC, [PC, #-0x1B0]` (VIM-style).
- Reason:
  - Previous vector table format was not ARM-R exception-vector compliant and can mask real faults as reset/recursive-looking loops.
- Pipeline backport target:
  - startup assembly template and reset/exception vector generation.

### 9) Banked stack pointer init for exception modes
- File: `app/output_20260228_133957/include/start.s`
- Changes:
  - Added reset-time initialization for FIQ/IRQ/ABT/UND/SVC stack pointers.
- Reason:
  - HAL startup initializes banked stacks via core init routine; missing this can corrupt state when abort/interrupt occurs and produce misleading recursive call stacks.
- Pipeline backport target:
  - startup assembly template (mode stack initialization logic).

### 10) Exception fault signature breadcrumbs
- File: `app/output_20260228_133957/include/start.s`
- Changes:
  - Each exception handler now writes a fault tag + LR to RAM scratch `0x0802FFF0`.
  - Tags: `1=Undef`, `2=SVC`, `3=PrefetchAbort`, `4=DataAbort`, `5=Phantom`.
- Reason:
  - CCS source/symbol mapping can misattribute low-address exception loops to unrelated C lines.
  - This provides deterministic handler identification without disassembly view.
- Pipeline backport target:
  - optional debug startup mode for generated BSPs.

### 11) Fault scratch relocation + PLL live diagnostics
- Files:
  - `app/output_20260228_133957/include/start.s`
  - `app/output_20260228_133957/include/pll_driver.c`
- Changes:
  - Moved assembly fault scratch from `0x0802FFF0` to `0x0802F000` (previous address collided with active stack region).
  - Added live PLL debug vars:
    - `g_pll_wait1_last_csdis`, `g_pll_wait1_iterations`
    - `g_pll_wait2_last_csvstat`, `g_pll_wait2_expected_mask`, `g_pll_wait2_iterations`
  - Added stage markers for timeout fallbacks:
    - `0xE1` first wait timeout fallback
    - `0xE2` second wait timeout fallback
  - Relaxed second wait criterion for bring-up to require PLL1/PLL2 valid only.
- Reason:
  - Previous diagnostics were overwritten by stack; wait gating needed visibility and reduced dependency on not-yet-initialized sources.
- Pipeline backport target:
  - optional bring-up diagnostics mode and adaptive clock-valid gating policy.

### 8) HAL source-id and CSDIS corrections
- File: `app/output_20260228_133957/include/pll_driver.c`
- Changes:
  - `CSDIS` aligned to HAL config (`0x0000008C`).
  - `RCLKSRC` and `VCLKASRC` now use HAL `SYS_VCLK` source id (`9`) rather than `2`.
- Reason:
  - Wrong source-id mapping can leave RTI/peripheral clocks invalid and create apparent startup stalls.
- Pipeline backport target:
  - clock-source enum/value mapping logic in PLL/system generation.

## Outstanding Validation Steps
- Reflash with current generated output.
- Watch `g_pll_debug_stage` and confirm progression to stage `5`.
- Verify terminal:
  - whether `'A'`, `'B'`, or both appear.
- Verify heartbeat period approximately matches expected timing.

### 12) Flash wait-state sequencing + richer abort capture
- Files:
  - `app/output_20260228_133957/include/system.c`
  - `app/output_20260228_133957/include/start.s`
- Changes:
  - Added `system_setup_flash_waitstates()` in `system.c` and call it before `PLL_Init()`.
  - Programmed HAL-equivalent flash wrapper settings before clock switch:
    - `FRDCNTL = (3 << 8) | (1 << 4) | 1`
    - `FSMWRENA = 0x5`, `EEPROMCONFIG = 0x00000002 | (3 << 16)`, `FSMWRENA = 0xA`
    - `FBFALLBACK = 0`
  - Extended abort handlers in `start.s` to capture and store:
    - DFSR, DFAR, IFSR, IFAR at scratch offsets `[+8, +12, +16, +20]`.
- Reason:
  - User-provided debug values show code reaches PLL stage 4 and then faults after clock handoff.
  - HAL configures flash wait states before clock-domain mapping; generated flow previously did not.
- Pipeline backport target:
  - `system.c` generation template must include flash timing setup before `PLL_Init`/clock source switch.
  - startup assembly template should optionally emit extended abort-register breadcrumbs in debug mode.

### 13) PCR-first startup ordering restoration
- Files:
  - `app/output_20260228_133957/include/system.c`
  - `app/output_20260228_133957/include/main.c`
- Changes:
  - Added `PCR_Init();` and `PCR_EnableAllPeripherals();` at the top of `system_init()`.
  - Removed duplicate PCR init calls from `main()` and left a note that PCR comes from reset path.
- Reason:
  - User-observed regression suspicion: peripheral/power domain setup must occur before wider register/program-clock setup in early boot.
  - Restores deterministic ordering: PCR -> flash wait-states -> PLL/clock tree -> application init.
- Pipeline backport target:
  - startup `system_init` template must emit PCR bring-up before PLL and other peripheral register programming.
  - generated `main.c` template should not duplicate PCR init when reset path already does it.

### 14) Active-clock-aware baud path + LIN pin-mode alignment + TX non-blocking loop
- Files:
  - `app/output_20260228_133957/include/pll_driver.c`
  - `app/output_20260228_133957/include/lin_driver.c`
  - `app/output_20260228_133957/include/main.c`
- Changes:
  - `PLL_GetFrequency()` now derives HCLK from live `GHVSRC` source selection instead of assuming PLL1 path.
  - `LIN_Init()` now writes HAL-equivalent `SCIPIO0` functional bits explicitly (`TX bit2`, `RX bit1`).
  - Main loop switched periodic TX to non-blocking (`IsTxReady()` gate) so failed TX readiness no longer stalls heartbeat timing.
  - Added CCS-visible debug globals in `main.c`:
    - `g_dbg_vclk_hz`, `g_dbg_ghvsrc`
    - init statuses, BRS values, FLR snapshots
    - tx-success / tx-skip counters for SCI and LIN.
- Reason:
  - If GHVSRC does not actually switch to PLL1, prior baud math could be grossly wrong (silent terminal).
  - Potential LIN functional pin-bit mismatch can suppress output on the SCILIN path.
  - Blocking send timeouts masked root cause by stretching heartbeat period.
- Pipeline backport target:
  - clock frequency helper must always reflect actual mux-selected source, not intended target only.
  - LIN/SCI pin-functional bit definitions must be validated against HAL register model.
  - include optional debug instrumentation mode for generated bring-up applications.

### 15) LIN non-blocking receive semantics fix
- File:
  - `app/output_20260228_133957/include/lin_driver.c`
- Changes:
  - `LIN_ReceiveByte()` now treats `timeout_ms == 0` as non-blocking:
    - returns timeout only when `RXRDY` is not set
    - reads data immediately when `RXRDY` is set.
- Reason:
  - Previous behavior always returned timeout for zero-timeout calls, which blocked RX echo flow even after `LIN_IsRxReady()` check.
- Pipeline backport target:
  - LIN driver template timeout semantics and unit tests for `timeout_ms == 0`.

## Backport Checklist (once runtime confirmed)
- Update generator prompts/spec constraints for:
  - HAL-accurate PLL/source sequencing.
  - SYS_VCLK source ID mapping.
  - startup section init sizing.
  - dual-path serial smoke test defaults for RM46 profile.
- Add validation rules:
  - flag non-HAL source IDs for `RCLKSRC/VCLKASRC`.
  - flag suspect `CSDIS` masks for RM46 profile.

### 16) Pipeline backport applied (prompt + validation hardening)
- Files:
  - `app/modules/generation/prompt.py`
  - `app/modules/validation/pass2_validator.py`
  - `app/modules/validation/validation_engine.py`
  - `app/tests/test_startup_and_pass2_validation.py`
- Changes:
  - Prompt now enforces:
    - `system_init` early PCR ordering (`PCR_Init` then `PCR_EnableAllPeripherals` before `PLL_Init`).
    - PLL frequency logic must be active-source aware via `GHVSRC` (not PLL1-assumed only).
    - LIN SCI-mode specifics: `SCIPIO0` TX/RX functional bits and `timeout_ms==0` non-blocking receive semantics.
  - Pass2 validator now adds hard checks for:
    - PLL driver missing `GHVSRC` awareness in `PLL_GetFrequency`.
    - LIN driver missing SCIPIO0 TX/RX functional config.
    - LIN driver missing explicit `timeout_ms==0` non-blocking path in `LIN_ReceiveByte`.
  - Validation engine now enforces `system_init` startup contract:
    - required call presence and ordering:
      `PCR_Init` -> `PCR_EnableAllPeripherals` -> `PLL_Init`.
    - warning if explicit flash wait-state setup is not detected pre-PLL.
  - Added regression tests covering:
    - valid/invalid startup ordering,
    - PLL GHVSRC check,
    - LIN non-blocking timeout semantics check.
- Verification:
  - `python -m py_compile` passed for modified modules.
  - Targeted pytest set passed (`19 passed`).
  - `python main.py --mock -y` completed end-to-end (no API calls).

### 17) Auto-generated runtime smoke harness (`bsp_validate`)
- Files:
  - `app/modules/utils/dependency_resolver.py`
  - `app/main.py`
  - `app/yaml_in/generation_profile.yaml`
  - `app/modules/yaml/yaml_utils.py`
- Changes:
  - Added profile-driven generation of:
    - `bsp_validate.h`
    - `bsp_validate.c`
  - `main.c` now switches to clean validation-mode entrypoint:
    - `BSP_ValidateInit();`
    - `while(1) { BSP_ValidateStep(); }`
  - Validation-mode auto-activates for RM46 profile with SCI/LIN/GIO coverage (or explicit `bsp_validation.enabled`).
  - `bsp_validate.c` performs deterministic UART smoke behavior:
    - initializes IOMM/VIM/GIO/SCI/LIN,
    - sends startup banners (`SCI path active (A)`, `LIN path active (B)`),
    - periodic TX heartbeats (`A` and `B`),
    - non-blocking RX echo for SCI and LIN,
    - heartbeat LED toggle.
  - RM46 defaults tuned for bring-up:
    - profile baud default set to `9600`,
    - default LED selection prioritizes `GIOB[1]` when present in `board.yaml`.
- Verification:
  - New unit tests added for validation-mode generation.
  - Targeted tests passed.
  - `python main.py --mock -y` output contains generated `main.c`, `bsp_validate.c`, `bsp_validate.h`.
