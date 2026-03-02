# RM46 PLL TRM Findings and Generator Controls (2026-03-01)

## What Was Going Wrong (vs TRM)

1. PLL programming drifted between literal HAL-style writes and generic math without a contract-selected strategy.
2. Some outputs skipped or reordered required enable/valid sequencing around `CSDISSET/CSDISCLR` and `CSVSTAT`.
3. Frequency decode paths treated encoded PLL values inconsistently, causing wrong derived HCLK/VCLK and garbled serial output.
4. Startup checks were mostly token-based and did not enforce TRM-style field-programmed dynamic behavior.

## TRM Anchors Used

From `10_Oscillator_and_PLL.pdf`:

- Quick-start path: program `PLLCTL1/PLLCTL2(/PLLCTL3)`, enable via `CSDISCLR`, wait `CSVSTAT` valid.
- Clock source disable/enable semantics: `CSDIS/CSDISSET/CSDISCLR`.
- Slip/valid behavior and recovery: `GLBSTAT` slip flags, disable before clearing slip, then re-enable.
- Timing and lock behavior: lock/enable/disable timing requirements (`TLock`, `TEnable`).

## Generator Changes Implemented

1. Prompt now supports explicit profile modes:
   - `rm46_hal_aligned`
   - `rm46_trm_dynamic`
   - `rm46_trm_dynamic_with_hal_fallback`
2. PLL prompt now includes profile selector guidance and TRM-dynamic requirements:
   - field-composed `PLLCTL1/PLLCTL2` programming from YAML values
   - disable -> program -> enable -> valid-poll -> handoff sequence
3. HAL decode branch in prompt is now conditional on contract (`allow_hal_encoded_pllmul`), not unconditional.
4. Pass2 validator now enforces TRM-dynamic behavior when requested:
   - field-based programming checks
   - register-field extraction and divider conversion checks in `PLL_GetFrequency`
   - optional enable/disable sequencing checks
5. Startup validator now enforces TRM-dynamic startup checkpoints when requested.
6. Contract schema expanded with typed TRM behavior flags:
   - `uses_trm_field_decoding`
   - `uses_trm_enable_disable_sequence`
7. YAML contract metadata updated to carry supported PLL profiles and TRM behavior flags.
8. `bus.yaml` updated with `pll1_encoding.trm_dynamic_defaults` for machine-readable sequence expectations.

## Current Operational Guidance

1. For immediate stability, keep `pll.init_profile: rm46_hal_aligned`.
2. For dynamic migration, switch to `rm46_trm_dynamic_with_hal_fallback` first, then `rm46_trm_dynamic` once hardware is stable.
3. Keep strict validation enabled so profile-specific PLL checks fail early.

