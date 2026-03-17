# RM46 Canonical Startup and PLL Sequence

This document defines the canonical ordering for RM46 bring-up. Treat this as the source of truth for sequence-sensitive startup behavior.

## 1) Canonical `system_init()` Call Order

Required call order:

1. `PCR_Init()`
2. `PCR_EnableAllPeripherals()`
3. `system_setup_flash_waitstates()` (or equivalent flash wait-state register programming)
4. `PLL_Init()`

Flash writes that must occur before `PLL_Init()`:

- `FLASH_FRDCNTL_REG` (`0xFFF87000`) write token includes `0x00000311`
- `FLASH_FBFALLBACK_REG` (`0xFFF87040`) write token includes `0x00000000`
- `FLASH_FSMWRENA_REG` (`0xFFF87288`) write tokens include `0x00000005` and `0x0000000A`
- `FLASH_EEPROMCONFIG_REG` (`0xFFF872B8`) write token includes `0x00030002`

## 2) Canonical `PLL_Init()` Ordering (Critical Checkpoints)

High-level checkpoint order:

1. Disable/set source bits (`CSDISSET`/`CSDIS` path)
2. Program `PLLCTL1`/`PLLCTL2` (and `PLLCTL3` when used)
3. Poll PLL validity/lock (`CSVSTAT` and/or lock helpers)
4. Program `CLKCNTL` dividers
5. Program `GHVSRC` source switch
6. Program `RCLKSRC`
7. Program `VCLKASRC`
8. Set peripheral enable (`PENA` via `CLKCNTL`)

Critical requirement:

- `CLKCNTL` divider programming MUST happen before `GHVSRC` source switch.
  If `GHVSRC` is switched first, VCLK can momentarily run at full HCLK and violate peripheral clock limits.

## 3) Register Address Map (SYSTEM domain)

From `reg_system.h`:

- `CSDIS`: `0xFFFFFF30`
- `CSDISSET`: `0xFFFFFF34`
- `CSDISCLR`: `0xFFFFFF38`
- `CDDIS`: `0xFFFFFF3C`
- `GHVSRC`: `0xFFFFFF48`
- `VCLKASRC`: `0xFFFFFF4C`
- `RCLKSRC`: `0xFFFFFF50`
- `CSVSTAT`: `0xFFFFFF54`
- `PLLCTL1`: `0xFFFFFF70`
- `PLLCTL2`: `0xFFFFFF74`
- `CLKCNTL`: `0xFFFFFFD0`
- `GLBSTAT`: `0xFFFFFFEC`

`SYSTEM2` domain:

- `PLLCTL3` (via `SYSREG2->PLLCTL3`): base `0xFFFFE100`

## 4) Enforcement Points

These checks are enforced in the generator pipeline:

- Contract definitions:
  - `app/yaml_in/bringup_contract.yaml`
    - `startup.required_order`
    - `pll.required_sequence`
- Prompt guidance:
  - `app/modules/generation/prompt.py` (explicit `CLKCNTL` before `GHVSRC` guidance)
- Startup validator:
  - `app/modules/validation/startup_contract_validator.py`
- Deterministic reorder fix:
  - `app/modules/build/ti_diagnostics.py`
- Baseline parity diff:
  - `app/modules/validation/register_parity_guard.py`
  - baseline configured in `generation_profile.yaml` (`parity_guard.baseline_path`)

## 5) Current Profile Gate Mode

`app/yaml_in/generation_profile.yaml` now sets:

- `startup_contract.gate_mode: fail`

Meaning runs fail if startup/parity sequencing checks fail.
