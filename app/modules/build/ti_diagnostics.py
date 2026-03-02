"""
TI diagnostic parsing and deterministic fix routing for CCS build logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..contracts.contract_autofix import autofix_bsp_validate, autofix_module_contract
from ..utils.file_io import normalize_generated_text


@dataclass(frozen=True)
class TiDiagnostic:
    file_path: str
    line: int
    severity: str
    code: str
    message: str
    raw: str


_TI_C_DIAG_RE = re.compile(
    r'^"(?P<file>[^"]+)",\s*line\s*(?P<line>\d+):\s*'
    r'(?P<severity>warning|error)\s*'
    r'(?P<code>#?[A-Za-z0-9_-]+)?'
    r':?\s*(?P<message>.*)$',
    re.IGNORECASE,
)
_TI_ASM_DIAG_RE = re.compile(
    r'^"(?P<file>[^"]+)",\s*ERROR!\s+at line\s*(?P<line>\d+):\s*'
    r'\[(?P<code>[A-Za-z0-9_-]+)\]\s*(?P<message>.*)$',
    re.IGNORECASE,
)
_TI_LINK_RE = re.compile(
    r'(?P<severity>error|warning)\s*#(?P<code>[A-Za-z0-9_-]+):\s*(?P<message>.*)',
    re.IGNORECASE,
)


def parse_ti_diagnostics(log_text: str) -> List[TiDiagnostic]:
    diagnostics: List[TiDiagnostic] = []
    for raw_line in (log_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        c_match = _TI_C_DIAG_RE.match(line)
        if c_match:
            diagnostics.append(
                TiDiagnostic(
                    file_path=c_match.group("file"),
                    line=int(c_match.group("line")),
                    severity=c_match.group("severity").lower(),
                    code=(c_match.group("code") or "").lstrip("#"),
                    message=c_match.group("message").strip(),
                    raw=raw_line,
                )
            )
            continue

        asm_match = _TI_ASM_DIAG_RE.match(line)
        if asm_match:
            diagnostics.append(
                TiDiagnostic(
                    file_path=asm_match.group("file"),
                    line=int(asm_match.group("line")),
                    severity="error",
                    code=asm_match.group("code"),
                    message=asm_match.group("message").strip(),
                    raw=raw_line,
                )
            )
            continue

        link_match = _TI_LINK_RE.search(line)
        if link_match:
            diagnostics.append(
                TiDiagnostic(
                    file_path="",
                    line=0,
                    severity=link_match.group("severity").lower(),
                    code=link_match.group("code"),
                    message=link_match.group("message").strip(),
                    raw=raw_line,
                )
            )
    return diagnostics


def summarize_ti_diagnostics(diagnostics: Sequence[TiDiagnostic]) -> Dict[str, Any]:
    errors = [d for d in diagnostics if d.severity == "error"]
    warnings = [d for d in diagnostics if d.severity == "warning"]
    by_file: Dict[str, int] = {}
    for diag in diagnostics:
        key = Path(diag.file_path).name if diag.file_path else "<linker>"
        by_file[key] = by_file.get(key, 0) + 1
    return {
        "total": len(diagnostics),
        "errors": len(errors),
        "warnings": len(warnings),
        "by_file": dict(sorted(by_file.items(), key=lambda item: item[0])),
    }


def apply_deterministic_fixes(
    output_dir: Path,
    diagnostics: Sequence[TiDiagnostic],
    api_contract_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    actions: List[str] = []
    changed_files: List[str] = []

    for result in (
        _fix_system_flash_register_member_drift(output_dir),
        _fix_missing_flash_waitstate_helper(output_dir),
        _fix_system_init_order(output_dir),
        _fix_pcr_enable_all_semantics(output_dir),
        _fix_entry_data_bss_copy_sizes(output_dir),
        _fix_pll_init_runtime_regressions(output_dir),
        _fix_bsp_validate_gio_level_token(output_dir),
        _fix_start_reset_vector_branch(output_dir),
        _fix_start_asm_literal_loads(output_dir),
        _fix_lin_clear_interrupt_macro_drift(output_dir),
        _fix_gio_base_alias_drift(output_dir),
        _apply_contract_autofixes(output_dir, diagnostics, api_contract_manifest),
    ):
        if not result:
            continue
        actions.extend(result.get("actions", []))
        changed_files.extend(result.get("files", []))

    return {
        "actions": actions,
        "files": sorted(set(changed_files)),
        "applied": len(actions) > 0,
    }


def apply_targeted_rewrite(
    output_dir: Path,
    diagnostics: Sequence[TiDiagnostic],
) -> Dict[str, Any]:
    if not diagnostics:
        return {"actions": [], "files": [], "applied": False}

    priority = [Path(d.file_path).name.lower() for d in diagnostics if d.file_path]
    top = priority[0] if priority else ""
    if top == "start.s":
        result = _fix_start_reset_vector_branch(output_dir)
        if result.get("applied"):
            return result
        return _fix_start_asm_literal_loads(output_dir)
    if top == "system.c":
        result = _fix_system_flash_register_member_drift(output_dir)
        if result.get("applied"):
            return result
        return _fix_missing_flash_waitstate_helper(output_dir)
    if top == "pcr_driver.c":
        return _fix_pcr_enable_all_semantics(output_dir)
    if top == "lin_driver.c":
        return _fix_lin_clear_interrupt_macro_drift(output_dir)
    if top == "gio_driver.c":
        return _fix_gio_base_alias_drift(output_dir)
    if top == "entry.c":
        return _fix_entry_data_bss_copy_sizes(output_dir)
    if top == "pll_driver.c":
        return _fix_pll_init_runtime_regressions(output_dir)
    if top == "bsp_validate.c":
        return _fix_bsp_validate_gio_level_token(output_dir)
    return {"actions": [], "files": [], "applied": False}


def _candidate_paths(output_dir: Path, filename: str) -> List[Path]:
    return [
        output_dir / filename,
        output_dir / "include" / filename,
        output_dir / "source" / filename,
    ]


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    return next((p for p in paths if p.exists()), None)


def _write_normalized(path: Path, text: str) -> None:
    path.write_text(normalize_generated_text(text, path), encoding="utf-8")


def _fix_missing_flash_waitstate_helper(output_dir: Path) -> Dict[str, Any]:
    system_c = _first_existing(_candidate_paths(output_dir, "system.c"))
    if not system_c:
        return {"actions": [], "files": [], "applied": False}

    content = system_c.read_text(encoding="utf-8", errors="ignore")
    call_present = "system_setup_flash_waitstates();" in content
    helper_present = re.search(r"\b(?:static\s+)?void\s+system_setup_flash_waitstates\s*\(", content) is not None
    if not call_present or helper_present:
        return {"actions": [], "files": [], "applied": False}

    helper_snippet = (
        "static void system_setup_flash_waitstates(void)\n"
        "{\n"
        "    /* RM46 HAL-aligned flash/EEPROM wait-state setup before PLL handoff. */\n"
        "    FLASH_FRDCNTL_REG = 0x00000311u;\n"
        "    FLASH_FSMWRENA_REG = 0x00000005u;\n"
        "    FLASH_EEPROMCONFIG_REG = 0x00030002u;\n"
        "    FLASH_FSMWRENA_REG = 0x0000000Au;\n"
        "    FLASH_FBFALLBACK_REG = 0x00000000u;\n"
        "}\n\n"
    )

    updated = content
    if '#include "reg_system.h"' not in updated:
        include_block = re.search(r"^(?:\s*#include[^\n]*\n)+", updated, re.MULTILINE)
        if include_block:
            idx = include_block.end()
            updated = updated[:idx] + '#include "reg_system.h"\n' + updated[idx:]
        else:
            updated = '#include "reg_system.h"\n' + updated

    macro_block = (
        "#define FLASH_FRDCNTL_REG      (*(volatile uint32_t *)0xFFF87000u)\n"
        "#define FLASH_FSMWRENA_REG     (*(volatile uint32_t *)0xFFF87288u)\n"
        "#define FLASH_EEPROMCONFIG_REG (*(volatile uint32_t *)0xFFF872B8u)\n"
        "#define FLASH_FBFALLBACK_REG   (*(volatile uint32_t *)0xFFF87040u)\n"
    )
    for macro_line in macro_block.splitlines():
        if macro_line and macro_line not in updated:
            include_block = re.search(r"^(?:\s*#include[^\n]*\n)+", updated, re.MULTILINE)
            if include_block:
                idx = include_block.end()
                updated = updated[:idx] + macro_line + "\n" + updated[idx:]
            else:
                updated = macro_line + "\n" + updated

    init_match = re.search(r"^\s*void\s+system_init\s*\(", updated, re.MULTILINE)
    if init_match:
        updated = updated[: init_match.start()] + helper_snippet + updated[init_match.start() :]
    else:
        updated = updated + ("\n" if not updated.endswith("\n") else "") + helper_snippet

    _write_normalized(system_c, updated)
    return {
        "actions": ["Injected missing system_setup_flash_waitstates() helper in system.c"],
        "files": [str(system_c)],
        "applied": True,
    }


def _fix_system_flash_register_member_drift(output_dir: Path) -> Dict[str, Any]:
    """
    Fix SYSTEM struct-member drift for flash wait-state programming.

    Converts invalid member accesses such as SYS->FRDCNTL into explicit MMIO
    register macros so CCS build does not depend on reg_system.h exposing these
    flash-controller registers.
    """
    system_c = _first_existing(_candidate_paths(output_dir, "system.c"))
    if not system_c:
        return {"actions": [], "files": [], "applied": False}

    text = system_c.read_text(encoding="utf-8", errors="ignore")
    updated = text
    replacements = {
        "FRDCNTL": "FLASH_FRDCNTL_REG",
        "FSMWRENA": "FLASH_FSMWRENA_REG",
        "EEPROMCONFIG": "FLASH_EEPROMCONFIG_REG",
        "FBFALLBACK": "FLASH_FBFALLBACK_REG",
        "FLASH_FRDCNTL": "FLASH_FRDCNTL_REG",
    }
    aliases = ("SYS", "systemREG1", "sysREG", "SYSTEMREG1")
    for member, macro in replacements.items():
        for alias in aliases:
            updated = re.sub(rf"\b{alias}\s*->\s*{member}\b", macro, updated)

    if updated == text:
        return {"actions": [], "files": [], "applied": False}

    macro_block = (
        "#define FLASH_FRDCNTL_REG      (*(volatile uint32_t *)0xFFF87000u)\n"
        "#define FLASH_FSMWRENA_REG     (*(volatile uint32_t *)0xFFF87288u)\n"
        "#define FLASH_EEPROMCONFIG_REG (*(volatile uint32_t *)0xFFF872B8u)\n"
        "#define FLASH_FBFALLBACK_REG   (*(volatile uint32_t *)0xFFF87040u)\n"
    )
    for macro_line in macro_block.splitlines():
        if macro_line and macro_line not in updated:
            include_block = re.search(r"^(?:\s*#include[^\n]*\n)+", updated, re.MULTILINE)
            if include_block:
                idx = include_block.end()
                updated = updated[:idx] + macro_line + "\n" + updated[idx:]
            else:
                updated = macro_line + "\n" + updated

    _write_normalized(system_c, updated)
    return {
        "actions": ["SYSTEM: Replaced invalid flash register struct members with MMIO flash macros"],
        "files": [str(system_c)],
        "applied": True,
    }


def _fix_pcr_enable_all_semantics(output_dir: Path) -> Dict[str, Any]:
    pcr_c = _first_existing(_candidate_paths(output_dir, "pcr_driver.c"))
    pcr_h = _first_existing(_candidate_paths(output_dir, "pcr_driver.h"))
    if not pcr_c:
        return {"actions": [], "files": [], "applied": False}

    source = pcr_c.read_text(encoding="utf-8", errors="ignore")
    clear_regs = sorted(set(re.findall(r"\bPSPWRDWNCLR(\d+)\b", source)))
    if not clear_regs:
        return {"actions": [], "files": [], "applied": False}

    register_lines = [f"    pcrREG->PSPWRDWNCLR{idx} = 0xFFFFFFFFU;" for idx in clear_regs]
    replacement = (
        "void PCR_EnableAllPeripherals(void)\n"
        "{\n"
        "    /* Enable all PCR-controlled domains by clearing powerdown bits. */\n"
        + "\n".join(register_lines)
        + "\n}\n"
    )

    fn_re = re.compile(
        r"void\s+PCR_EnableAllPeripherals\s*\(\s*void\s*\)\s*\{[\s\S]*?\n\}",
        re.MULTILINE,
    )
    if fn_re.search(source):
        updated = fn_re.sub(replacement.rstrip("\n"), source, count=1)
    else:
        updated = source + ("\n" if not source.endswith("\n") else "") + replacement

    if updated == source:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(pcr_c, updated)
    touched = [str(pcr_c)]
    actions = ["Normalized PCR_EnableAllPeripherals() to clear PSPWRDWNCLR registers"]

    if pcr_h:
        header = pcr_h.read_text(encoding="utf-8", errors="ignore")
        if "void PCR_EnableAllPeripherals(void);" not in header:
            marker = "#endif /* PCR_DRIVER_H */"
            decl = (
                "\n"
                "void PCR_EnableAllPeripherals(void);\n"
                "\n"
            )
            if marker in header:
                header = header.replace(marker, decl + marker)
            else:
                header = header + ("\n" if not header.endswith("\n") else "") + decl
            _write_normalized(pcr_h, header)
            touched.append(str(pcr_h))
            actions.append("Added PCR_EnableAllPeripherals() declaration to pcr_driver.h")

    return {"actions": actions, "files": touched, "applied": True}


def _fix_entry_data_bss_copy_sizes(output_dir: Path) -> Dict[str, Any]:
    entry_c = _first_existing(_candidate_paths(output_dir, "entry.c"))
    if not entry_c:
        return {"actions": [], "files": [], "applied": False}

    text = entry_c.read_text(encoding="utf-8", errors="ignore")
    updated = text
    actions: List[str] = []

    data_pat = re.compile(
        r"(\bdata_size\s*=\s*\(size_t\)\s*\(&end_of_data\s*-\s*&start_of_data\))\s*;"
    )
    bss_pat = re.compile(
        r"(\bbss_size\s*=\s*\(size_t\)\s*\(&end_of_bss\s*-\s*&start_of_bss\))\s*;"
    )

    updated, data_n = data_pat.subn(r"\1 * sizeof(uint32_t);", updated)
    if data_n > 0:
        actions.append("ENTRY: Restored byte scaling for .data initialization size")

    updated, bss_n = bss_pat.subn(r"\1 * sizeof(uint32_t);", updated)
    if bss_n > 0:
        actions.append("ENTRY: Restored byte scaling for .bss zero-init size")

    # If byte scaling is already present in data_size/bss_size, ensure memcpy/memset
    # use the computed byte counts directly (avoid double scaling).
    memcpy_double_pat = re.compile(
        r"memcpy\s*\(\s*&start_of_data\s*,\s*&start_of_data_in_flash\s*,\s*"
        r"data_size\s*\*\s*sizeof\s*\(\s*uint32_t\s*\)\s*\)\s*;"
    )
    memset_double_pat = re.compile(
        r"memset\s*\(\s*&start_of_bss\s*,\s*0\s*,\s*"
        r"bss_size\s*\*\s*sizeof\s*\(\s*uint32_t\s*\)\s*\)\s*;"
    )

    updated, memcpy_n = memcpy_double_pat.subn(
        "memcpy(&start_of_data, &start_of_data_in_flash, data_size);",
        updated,
    )
    if memcpy_n > 0:
        actions.append("ENTRY: Removed double scaling from memcpy .data size argument")

    updated, memset_n = memset_double_pat.subn(
        "memset(&start_of_bss, 0, bss_size);",
        updated,
    )
    if memset_n > 0:
        actions.append("ENTRY: Removed double scaling from memset .bss size argument")

    if updated == text:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(entry_c, updated)
    return {"actions": actions, "files": [str(entry_c)], "applied": True}


def _fix_pll_init_runtime_regressions(output_dir: Path) -> Dict[str, Any]:
    pll_c = _first_existing(_candidate_paths(output_dir, "pll_driver.c"))
    if not pll_c:
        return {"actions": [], "files": [], "applied": False}

    text = pll_c.read_text(encoding="utf-8", errors="ignore")
    updated = text
    actions: List[str] = []

    # Fix ODPLL encoding drift in PLL_Init default path:
    # register expects (ODPLL - 1), but some generations write ODPLL directly.
    odpll_pat = re.compile(
        r"\(\(\s*([A-Za-z_]\w*ODPLL\w*)\s*<<\s*SYSTEM_PLLCTL2_ODPLL_SHIFT\s*\)\s*&\s*SYSTEM_PLLCTL2_ODPLL_MASK\s*\)"
    )

    def _odpll_repl(match: re.Match[str]) -> str:
        symbol = match.group(1)
        return f"((({symbol} - 1u) << SYSTEM_PLLCTL2_ODPLL_SHIFT) & SYSTEM_PLLCTL2_ODPLL_MASK)"

    # Only rewrite simple no-subtraction form (avoid touching already-correct expressions).
    if re.search(r"\bPLL_Init\s*\(", updated):
        pre = updated
        updated = odpll_pat.sub(_odpll_repl, updated)
        if updated != pre:
            actions.append("PLL: Normalized default ODPLL register encoding to (ODPLL-1)")

    # Preserve existing CLKCNTL bits when programming VCLK dividers in PLL_Init.
    clkcntl_assign_pat = re.compile(
        r"SYSREG->CLKCNTL\s*=\s*\(\(\s*1[uU]\s*<<\s*SYSTEM_CLKCNTL_VCLKR_SHIFT\s*\)\s*&\s*SYSTEM_CLKCNTL_VCLKR_MASK\s*\)\s*"
        r"\|\s*\(\(\s*1[uU]\s*<<\s*SYSTEM_CLKCNTL_VCLK2R_SHIFT\s*\)\s*&\s*SYSTEM_CLKCNTL_VCLK2R_MASK\s*\)\s*;"
    )
    clkcntl_rmw_block = (
        "clkcntl_value = SYSREG->CLKCNTL;\n"
        "    clkcntl_value &= ~(SYSTEM_CLKCNTL_VCLKR_MASK | SYSTEM_CLKCNTL_VCLK2R_MASK);\n"
        "    clkcntl_value |= ((1u << SYSTEM_CLKCNTL_VCLKR_SHIFT) & SYSTEM_CLKCNTL_VCLKR_MASK);\n"
        "    clkcntl_value |= ((1u << SYSTEM_CLKCNTL_VCLK2R_SHIFT) & SYSTEM_CLKCNTL_VCLK2R_MASK);\n"
        "    SYSREG->CLKCNTL = clkcntl_value;"
    )
    updated, rmw_n = clkcntl_assign_pat.subn(clkcntl_rmw_block, updated)
    if rmw_n > 0:
        if "uint32_t clkcntl_value;" not in updated:
            updated = re.sub(
                r"(uint32_t\s+pllctl2_value\s*;)",
                r"\1\n    uint32_t clkcntl_value;",
                updated,
                count=1,
            )
        actions.append("PLL: Replaced CLKCNTL overwrite with read-modify-write divider update")

    # Enforce bring-up contract ordering: CLKCNTL divider programming before GHVSRC source switch.
    updated, order_fix_applied = _ensure_pll_clkcntl_before_ghvsrc(updated)
    if order_fix_applied:
        actions.append("PLL: Reordered PLL_Init writes so CLKCNTL precedes GHVSRC")

    if updated == text:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(pll_c, updated)
    return {"actions": actions, "files": [str(pll_c)], "applied": True}


def _ensure_pll_clkcntl_before_ghvsrc(source: str) -> tuple[str, bool]:
    fn = re.search(r"\bvoid\s+PLL_Init\s*\(\s*void\s*\)\s*\{", source)
    if not fn:
        fn = re.search(r"\bvoid\s+PLL_Init\s*\(\s*\)\s*\{", source)
    if not fn:
        return source, False

    open_brace = fn.end() - 1
    idx = open_brace + 1
    depth = 1
    while idx < len(source) and depth > 0:
        ch = source[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        idx += 1
    if depth != 0:
        return source, False

    body = source[open_brace + 1 : idx - 1]
    lines = body.splitlines()
    ghv_idx = -1
    clk_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if ghv_idx < 0 and "GHVSRC" in stripped and "->GHVSRC" in stripped and "=" in stripped:
            ghv_idx = i
        if clk_idx < 0 and "CLKCNTL" in stripped and "->CLKCNTL" in stripped and "=" in stripped:
            clk_idx = i

    if ghv_idx < 0 or clk_idx < 0 or clk_idx < ghv_idx:
        return source, False

    clk_line = lines.pop(clk_idx)
    if clk_idx < ghv_idx:
        ghv_idx -= 1
    lines.insert(ghv_idx, clk_line)
    new_body = "\n".join(lines)
    updated = source[: open_brace + 1] + new_body + source[idx - 1 :]
    return updated, True


def _fix_system_init_order(output_dir: Path) -> Dict[str, Any]:
    system_c = _first_existing(_candidate_paths(output_dir, "system.c"))
    if not system_c:
        return {"actions": [], "files": [], "applied": False}

    text = system_c.read_text(encoding="utf-8", errors="ignore")
    fn = re.search(r"\bvoid\s+system_init\s*\(\s*void\s*\)\s*\{", text)
    if not fn:
        fn = re.search(r"\bvoid\s+system_init\s*\(\s*\)\s*\{", text)
    if not fn:
        return {"actions": [], "files": [], "applied": False}

    open_brace = fn.end() - 1
    idx = open_brace + 1
    depth = 1
    while idx < len(text) and depth > 0:
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        idx += 1
    if depth != 0:
        return {"actions": [], "files": [], "applied": False}

    body = text[open_brace + 1 : idx - 1]
    call_patterns = {
        "PCR_Init": re.compile(r"^\s*PCR_Init\s*\(\s*\)\s*;\s*$", re.MULTILINE),
        "PCR_EnableAllPeripherals": re.compile(r"^\s*PCR_EnableAllPeripherals\s*\(\s*\)\s*;\s*$", re.MULTILINE),
        "flash_waitstates": re.compile(r"^\s*system_setup_flash_waitstates\s*\(\s*\)\s*;\s*$", re.MULTILINE),
        "PLL_Init": re.compile(r"^\s*PLL_Init\s*\(\s*\)\s*;\s*$", re.MULTILINE),
    }

    calls: Dict[str, str] = {}
    for key, pat in call_patterns.items():
        m = pat.search(body)
        if m:
            calls[key] = m.group(0)

    required = ["PCR_Init", "PCR_EnableAllPeripherals", "PLL_Init"]
    if not all(k in calls for k in required):
        return {"actions": [], "files": [], "applied": False}

    order = ["PCR_Init", "PCR_EnableAllPeripherals"]
    if "flash_waitstates" in calls:
        order.append("flash_waitstates")
    order.append("PLL_Init")

    current_positions = {k: body.find(calls[k]) for k in order}
    already_ordered = all(
        current_positions[order[i]] < current_positions[order[i + 1]]
        for i in range(len(order) - 1)
    )
    if already_ordered:
        return {"actions": [], "files": [], "applied": False}

    cleaned_body = body
    for key in order:
        cleaned_body = call_patterns[key].sub("", cleaned_body, count=1)
    cleaned_body_lines = [ln for ln in cleaned_body.splitlines() if ln.strip() or ln == ""]
    cleaned_body = "\n".join(cleaned_body_lines).lstrip("\n")

    indent = "    "
    new_call_block = "\n".join(f"{indent}{calls[k].strip()}" for k in order) + "\n"
    if cleaned_body and not cleaned_body.startswith("\n"):
        new_body = new_call_block + "\n" + cleaned_body
    else:
        new_body = new_call_block + cleaned_body

    updated = text[: open_brace + 1] + "\n" + new_body.rstrip() + "\n" + text[idx - 1 :]
    _write_normalized(system_c, updated)
    return {
        "actions": ["Reordered system_init() bring-up calls to PCR_Init -> PCR_EnableAllPeripherals -> flash_waitstates -> PLL_Init"],
        "files": [str(system_c)],
        "applied": True,
    }


def _fix_start_reset_vector_branch(output_dir: Path) -> Dict[str, Any]:
    start_s = _first_existing(_candidate_paths(output_dir, "start.s"))
    if not start_s:
        return {"actions": [], "files": [], "applied": False}

    text = start_s.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"\bB\s+(?:Reset_Handler|Reset_Entry)\b", text):
        return {"actions": [], "files": [], "applied": False}

    lines = text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if re.search(r"^\s*\.long\s+end_of_stack\b", line):
            lines.insert(i + 1, "        B       Reset_Handler")
            changed = True
            break

    if not changed:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(start_s, "\n".join(lines) + "\n")
    return {
        "actions": ["Inserted missing reset vector branch in start.s (.intvecs)"],
        "files": [str(start_s)],
        "applied": True,
    }


def _fix_start_asm_literal_loads(output_dir: Path) -> Dict[str, Any]:
    start_s = _first_existing(_candidate_paths(output_dir, "start.s"))
    if not start_s:
        return {"actions": [], "files": [], "applied": False}

    lines = start_s.read_text(encoding="utf-8", errors="ignore").splitlines()
    changed = False
    out_lines: List[str] = []
    ldr_re = re.compile(r"^(\s*)LDR\s+(R\d+),\s*=0x([0-9A-Fa-f]{1,8})\s*$")
    for line in lines:
        match = ldr_re.match(line)
        if not match:
            out_lines.append(line)
            continue
        indent, reg, value_hex = match.groups()
        value = int(value_hex, 16)
        low = value & 0xFFFF
        high = (value >> 16) & 0xFFFF
        out_lines.append(f"{indent}MOVW    {reg}, #0x{low:04X}")
        out_lines.append(f"{indent}MOVT    {reg}, #0x{high:04X}")
        changed = True

    if not changed:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(start_s, "\n".join(out_lines) + "\n")
    return {
        "actions": ["Converted TI-unsupported LDR literal forms in start.s to MOVW/MOVT"],
        "files": [str(start_s)],
        "applied": True,
    }


def _fix_lin_clear_interrupt_macro_drift(output_dir: Path) -> Dict[str, Any]:
    lin_c = _first_existing(_candidate_paths(output_dir, "lin_driver.c"))
    reg_lin_h = _first_existing(_candidate_paths(output_dir, "reg_lin.h"))
    if not lin_c or not reg_lin_h:
        return {"actions": [], "files": [], "applied": False}

    source = lin_c.read_text(encoding="utf-8", errors="ignore")
    reg_text = reg_lin_h.read_text(encoding="utf-8", errors="ignore")
    defined_macros = {
        m
        for m in re.findall(r"^\s*#define\s+([A-Za-z_]\w*)\b", reg_text, flags=re.MULTILINE)
    }
    clear_macros = sorted(set(re.findall(r"\bLIN_SCICLEARINT_CLR_[A-Z0-9_]+\b", source)))
    fallback = "LIN_SCICLEARINT_CLR_BE_INT" if "LIN_SCICLEARINT_CLR_BE_INT" in defined_macros else "0U"

    updated = source
    replaced = 0
    for macro in clear_macros:
        if macro in defined_macros:
            continue
        updated, n = re.subn(rf"\b{re.escape(macro)}\b", fallback, updated)
        replaced += n

    if replaced == 0:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(lin_c, updated)
    return {
        "actions": [f"Replaced {replaced} undefined LIN_SCICLEARINT clear macros with {fallback}"],
        "files": [str(lin_c)],
        "applied": True,
    }


def _fix_gio_base_alias_drift(output_dir: Path) -> Dict[str, Any]:
    gio_c = _first_existing(_candidate_paths(output_dir, "gio_driver.c"))
    if not gio_c:
        return {"actions": [], "files": [], "applied": False}

    source = gio_c.read_text(encoding="utf-8", errors="ignore")
    uses_gioreg = re.search(r"\bgioREG\s*->", source) is not None
    has_alias = re.search(r"^\s*#define\s+gioREG\b", source, flags=re.MULTILINE) is not None
    if (not uses_gioreg) or has_alias:
        return {"actions": [], "files": [], "applied": False}

    alias_block = (
        "#ifndef gioREG\n"
        "#define gioREG ((volatile GIO_REG_MAP_t *)GIO_BASE_ADDRESS)\n"
        "#endif\n"
    )

    include_block = re.search(r"^(?:\s*#include[^\n]*\n)+", source, flags=re.MULTILINE)
    if include_block:
        insert_at = include_block.end()
        updated = source[:insert_at] + "\n" + alias_block + source[insert_at:]
    else:
        updated = alias_block + "\n" + source

    _write_normalized(gio_c, updated)
    return {
        "actions": ["Inserted gioREG base alias using GIO_BASE_ADDRESS in gio_driver.c"],
        "files": [str(gio_c)],
        "applied": True,
    }


def _fix_bsp_validate_gio_level_token(output_dir: Path) -> Dict[str, Any]:
    bsp_validate_c = _first_existing(_candidate_paths(output_dir, "bsp_validate.c"))
    gio_header = _first_existing(_candidate_paths(output_dir, "gio_driver.h"))
    if not bsp_validate_c or not gio_header:
        return {"actions": [], "files": [], "applied": False}

    src = bsp_validate_c.read_text(encoding="utf-8", errors="ignore")
    if "GIO_LEVEL_HIGH" not in src:
        return {"actions": [], "files": [], "applied": False}

    gio_text = gio_header.read_text(encoding="utf-8", errors="ignore")

    replacement = None
    if re.search(r"\bGIO_LEVEL_HIGH\b", gio_text):
        replacement = "GIO_LEVEL_HIGH"
    elif re.search(r"\bGIO_LEVEL_SET\b", gio_text):
        replacement = "GIO_LEVEL_SET"
    elif re.search(r"\bGIO_WritePin\s*\([^)]*bool\s+\w+\s*\)", gio_text):
        replacement = "true"
    else:
        replacement = "1U"

    updated, n = re.subn(r"\bGIO_LEVEL_HIGH\b", replacement, src)
    if n == 0:
        return {"actions": [], "files": [], "applied": False}

    _write_normalized(bsp_validate_c, updated)
    return {
        "actions": [f"Normalized bsp_validate GIO level token: GIO_LEVEL_HIGH -> {replacement}"],
        "files": [str(bsp_validate_c)],
        "applied": True,
    }


def _apply_contract_autofixes(
    output_dir: Path,
    diagnostics: Sequence[TiDiagnostic],
    api_contract_manifest: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not api_contract_manifest:
        return {"actions": [], "files": [], "applied": False}

    actions: List[str] = []
    files: List[str] = []

    bsp_validate_c = _first_existing(_candidate_paths(output_dir, "bsp_validate.c"))
    if bsp_validate_c:
        result = autofix_bsp_validate(bsp_validate_c, api_contract_manifest)
        for action in result.get("actions", []):
            actions.append(f"BSP_VALIDATE: {action}")
        if result.get("actions"):
            files.append(str(bsp_validate_c))

    module_names = {
        Path(diag.file_path).name.replace("_driver.c", "").replace("_driver.h", "").upper()
        for diag in diagnostics
        if diag.file_path
    }
    for module in sorted(module_names):
        if module not in {"LIN", "IOMM"}:
            continue
        header = _first_existing(_candidate_paths(output_dir, f"{module.lower()}_driver.h"))
        source = _first_existing(_candidate_paths(output_dir, f"{module.lower()}_driver.c"))
        if not header or not source:
            continue
        result = autofix_module_contract(module, header, source, api_contract_manifest)
        for action in result.get("actions", []):
            actions.append(f"{module}: {action}")
        if result.get("actions"):
            files.extend([str(header), str(source)])

    return {"actions": actions, "files": sorted(set(files)), "applied": len(actions) > 0}
