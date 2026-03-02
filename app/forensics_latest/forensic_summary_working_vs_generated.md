# Working vs Generated Forensic Summary

Compared outputs:
- Working baseline: `output_working_with_manual_changes`
- Candidate A: `output_20260301_232357`
- Candidate B: `output_20260301_225239`

## 1) Whole-code delta
- Content differs in 30 code files (`.c/.h/.s/.cmd`) for both candidates.
- File-level manifest: `code_file_diff_summary_output_working_with_manual_changes_vs_output_20260301_232357.md`
- File-level manifest: `code_file_diff_summary_output_working_with_manual_changes_vs_output_20260301_225239.md`

## 2) Register access inventory (address-resolved)
- Working total MMIO accesses found: 112
- Candidate A total MMIO accesses found: 112
- Candidate B total MMIO accesses found: 104

Ledgers (every extracted access with resolved address):
- `register_accesses_output_working_with_manual_changes.md`
- `register_accesses_output_20260301_232357.md`
- `register_accesses_output_20260301_225239.md`

Delta tables:
- `register_access_diff_output_working_with_manual_changes_vs_output_20260301_232357.csv`
- `register_access_diff_output_working_with_manual_changes_vs_output_20260301_225239.csv`

## 3) Where MMIO behavior actually diverges
Although 30 code files changed, MMIO differences are concentrated in:
- `main.c`
- `system.c`
- `pll_driver.c`

No MMIO deltas were detected in `sci_driver.c`, `lin_driver.c`, `gio_driver.c`, `pcr_driver.c`, `iomm_driver.c`, `vim.c`.

## 4) Startup/order deltas that matter
Startup sequence reports:
- `startup_register_sequence_output_working_with_manual_changes_vs_output_20260301_232357.md`
- `startup_register_sequence_output_working_with_manual_changes_vs_output_20260301_225239.md`

High-impact differences:
- Working `system_init()` does early `SYS->CLKCNTL` writes at `0xFFFFFFD0` and `SYS->CSVSTAT` clear at `0xFFFFFF54` before `PLL_Init()`.
- Candidate A/B `system_init()` removed those early `CLKCNTL/CSVSTAT` writes and moved behavior into/after PLL logic.
- Candidate B has no post-`PLL_Init()` PENA force.
- Candidate A adds post-`PLL_Init()` `SYS->CLKCNTL |= (1<<8)` PENA force.
- Candidate A/B `PLL_Init()` was heavily refactored and reordered (disable sources, lock waits, divider-first handoff, then source switch), with many extra read-modify-write operations vs working flow.

## 5) Main runtime path changed
- Working `main.c` directly performs board test flow (manual SCI/LIN init, echo loop, debug probes).
- Candidate A/B `main.c` now delegates to `BSP_ValidateInit()` and `BSP_ValidateStep()` only.
- This is a functional behavior change, not just refactor.

## 6) Strongest no-terminal-output risk from deltas
Most critical behavioral risk visible in the generated code path:
- In Candidate A `PLL_Init()` returns early on PLL1 lock timeout before full clock-tree handoff.
- Candidate B has no fallback PENA write after `PLL_Init()`, so peripheral clocks can remain gated.
- Candidate A adds a fallback PENA write in `system_init()`, but still depends on the altered PLL/source/divider sequence.

## 7) Exact line diffs for critical files
Patch files generated:
- `diff_working_vs_232357_main.c.patch`
- `diff_working_vs_232357_system.c.patch`
- `diff_working_vs_232357_pll_driver.c.patch`
- `diff_working_vs_225239_main.c.patch`
- `diff_working_vs_225239_system.c.patch`
- `diff_working_vs_225239_pll_driver.c.patch`
