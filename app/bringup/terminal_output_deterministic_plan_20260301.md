# RM46 Terminal Output Deterministic Plan (Post-Patch)

## Goal
Produce first-pass generated output that compiles, flashes, and prints to terminal on RM46 LaunchXL2 without manual code edits.

## Immediate Runtime Patch Applied
Patched `output_20260301_160048` to align with known-good behavior:
- `source/system.c`
  - Restored flash waitstate register block to `0xFFF87000/0xFFF87040/0xFFF87288/0xFFF872B8`.
  - Restored SYSTEM init writes (`CLKCNTL`, `CSVSTAT`) before `PLL_Init`.
- `source/pll_driver.c`
  - Replaced generic PLL bring-up with HALCoGen-aligned sequence.
  - Added safe PLL frequency decode for HAL-encoded `PLLMUL=0xA400` and 64-bit math for baud calculations.
- `bsp_validate.c`
  - Added forced known-good IOMM pinmux helper for pins 38/39 (+ pin 133) with explicit unlock/write/lock.

## Root Causes of Drift
1. Flash waitstate addresses drifted to wrong register block.
2. PLL initialization sequence drifted from proven HAL-aligned order/values.
3. Frequency math treated HAL-encoded PLL fields as raw multipliers, corrupting derived baud.
4. Runtime path trusted abstract pinmux calls only, without board-critical fallback.

## Deterministic Generator Changes (No Hardcoding in C Output)

### 1) Encode bring-up invariants in YAML contracts
- In `yaml_in/bringup_contract.yaml` keep/extend invariants:
  - `iomm.unlock_sequence = [0x83E70B13, 0x95A4F1E0]`
  - `serial.required_pins` for pin 38/39 on `PINMMR7/8` with AF1.
  - `lin.required_registers.SCIPIO0.required_value = 0x00000006`
  - `flash.required_registers` addresses/values for waitstate block.
  - `pll.required_sequence` tokenized write/poll order.
  - `pll.frequency_decode.allow_hal_encoded_pllmul = true` (accept `0xA400` path).

### 2) Move platform ownership to source YAML
- In `yaml_in/soc.yaml`, keep SYSTEM init limited to true SYSTEM-owned registers.
- Ensure PLL-owned writes are only emitted by PLL generator path.

### 3) Pinmux schema for machine semantics
- In `yaml_in/pinmux.yaml` attach explicit field metadata:
  - `encoding: one_hot_8bit`
  - `field_width: 8`
  - `af1_bit: 1`
- This prevents enum/bit drift in generated IOMM/LIN/SCI pin setup.

### 4) PLL source-of-truth in `bus.yaml`
- Add explicit generated constants for:
  - GHVSRC source IDs
  - RCLKSRC/VCLKASRC IDs
  - accepted encoded PLL forms and expected effective HCLK/VCLK used for baud.

### 5) Prompt constraints (deterministic, contract-driven)
- Remove conflicting pinmux examples.
- Inject per-module contract block for SYSTEM/PLL/IOMM/LIN/SCI.
- Require frequency calculation to honor contract decode rules (including HAL-encoded PLL cases).

### 6) Validator hard-fail checks
- In strict mode, fail generation if missing:
  - IOMM unlock-write-lock sequence for required pins.
  - flash waitstate register block writes before PLL handoff.
  - required PLL sequence tokens.
  - accepted frequency decode path (no raw-overflow math).

### 7) Build-gate cross-check
- Compile gate must verify synced generated files (not stale project files) before build.
- Add a post-sync fingerprint check and include it in `compile_gate_report.json`.

## Acceptance Criteria
1. Fresh generation passes strict validation.
2. Compile gate builds synced generated files.
3. First flash produces terminal banner and heartbeat without manual edits.
4. No strict bring-up violations in `validation_report`.
