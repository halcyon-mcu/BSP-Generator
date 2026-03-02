"""
Register access parity guard and forensic trace generation.

This module builds deterministic register access ledgers from generated C code,
compares critical startup sequences against a known-good baseline, and emits
artifacts that can be used to pinpoint order/access drift.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


_STARTUP_FILE_ORDER = [
    "system.c",
    "pcr_driver.c",
    "iomm_driver.c",
    "pll_driver.c",
    "vim.c",
    "gio_driver.c",
    "sci_driver.c",
    "lin_driver.c",
    "main.c",
]

_KNOWN_CRITICAL_DEFAULTS = [
    "CSDIS",
    "CSDISSET",
    "CSDISCLR",
    "CDDIS",
    "GHVSRC",
    "RCLKSRC",
    "VCLKASRC",
    "CSVSTAT",
    "PLLCTL1",
    "PLLCTL2",
    "PLLCTL3",
    "CLKCNTL",
    "GLBSTAT",
    "PINMMR7",
    "PINMMR8",
    "SCIPIO0",
    "GCR0",
    "BRS",
    "FORMAT",
    "PSPWRDWNCLR0",
    "PSPWRDWNCLR1",
    "PSPWRDWNCLR2",
    "PSPWRDWNCLR3",
]


@dataclass(frozen=True)
class RegisterAccess:
    order_index: int
    file: str
    line: int
    expression: str
    symbol: str
    canonical_symbol: str
    address: Optional[str]
    op: str
    value: str
    domain: str


def default_critical_registers() -> List[str]:
    return list(_KNOWN_CRITICAL_DEFAULTS)


def run_parity_guard(
    output_dir: Path,
    baseline_dir: Optional[Path],
    *,
    mode: str = "critical_only",
    critical_registers: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    out_dir = Path(output_dir)
    baseline = Path(baseline_dir) if baseline_dir else None
    norm_mode = (mode or "critical_only").strip().lower()
    if norm_mode not in {"critical_only", "strict", "off"}:
        norm_mode = "critical_only"

    result: Dict[str, Any] = {
        "enabled": norm_mode != "off",
        "mode": norm_mode,
        "passes": True,
        "baseline_dir": str(baseline) if baseline else None,
        "critical_registers": list(critical_registers or default_critical_registers()),
        "access_counts": {},
        "critical_sequence_mismatches": [],
        "warnings": [],
        "errors": [],
        "artifacts": {},
    }

    if norm_mode == "off":
        result["warnings"].append("parity_guard.mode=off")
        return result

    if baseline is None or not baseline.exists():
        result["passes"] = False
        result["errors"].append("parity guard baseline directory missing or not provided")
        return result

    artifact_dir = out_dir / "forensics"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    candidate_accesses = collect_register_accesses(out_dir)
    baseline_accesses = collect_register_accesses(baseline)

    result["access_counts"] = {
        "candidate": len(candidate_accesses),
        "baseline": len(baseline_accesses),
    }

    candidate_csv = artifact_dir / "register_accesses_candidate.csv"
    baseline_csv = artifact_dir / "register_accesses_baseline.csv"
    _write_access_csv(candidate_accesses, candidate_csv)
    _write_access_csv(baseline_accesses, baseline_csv)
    candidate_md = artifact_dir / "register_accesses_candidate.md"
    baseline_md = artifact_dir / "register_accesses_baseline.md"
    _write_access_markdown(candidate_accesses, candidate_md, title="Register Access Ledger (Candidate)")
    _write_access_markdown(baseline_accesses, baseline_md, title="Register Access Ledger (Baseline)")

    critical_set = {
        str(item).strip().upper()
        for item in (critical_registers or default_critical_registers())
        if str(item).strip()
    }

    sequence_cmp = compare_register_sequences(
        baseline_accesses,
        candidate_accesses,
        mode=norm_mode,
        critical_registers=critical_set,
    )
    result["passes"] = bool(sequence_cmp.get("passes", False))
    result["critical_sequence_mismatches"] = list(sequence_cmp.get("mismatches", []))
    result["summary"] = dict(sequence_cmp.get("summary", {}))

    diff_json = artifact_dir / "critical_sequence_diff.json"
    diff_md = artifact_dir / "critical_sequence_diff.md"
    diff_json.write_text(json.dumps(sequence_cmp, indent=2), encoding="utf-8")
    _write_diff_markdown(sequence_cmp, diff_md)

    result["artifacts"] = {
        "candidate_csv": str(candidate_csv),
        "baseline_csv": str(baseline_csv),
        "candidate_md": str(candidate_md),
        "baseline_md": str(baseline_md),
        "critical_diff_json": str(diff_json),
        "critical_diff_md": str(diff_md),
    }

    if not result["passes"] and not result["critical_sequence_mismatches"]:
        result["warnings"].append("parity guard reported mismatch without detailed entries")

    return result


def collect_register_accesses(output_dir: Path) -> List[RegisterAccess]:
    root = Path(output_dir)
    reg_struct_offsets = _load_register_struct_offsets(root)

    files: List[Path] = []
    for base_name in _STARTUP_FILE_ORDER:
        found = _first_existing(_candidate_paths(root, base_name))
        if found:
            files.append(found)

    seen = {str(p.resolve()) for p in files}
    for ext in ("*.c",):
        for path in sorted((root / "source").glob(ext)) if (root / "source").exists() else []:
            resolved = str(path.resolve())
            if resolved not in seen:
                files.append(path)
                seen.add(resolved)
        for path in sorted((root / "include").glob(ext)) if (root / "include").exists() else []:
            resolved = str(path.resolve())
            if resolved not in seen:
                files.append(path)
                seen.add(resolved)
        for path in sorted(root.glob(ext)):
            resolved = str(path.resolve())
            if resolved not in seen:
                files.append(path)
                seen.add(resolved)

    accesses: List[RegisterAccess] = []
    order = 0
    for path in files:
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        var_types, var_bases = _extract_pointer_aliases(content)
        macro_addresses = _extract_macro_addresses(content)
        for lineno, raw_line in enumerate(content.splitlines(), start=1):
            line = _strip_inline_comment(raw_line)
            if not line.strip():
                continue

            # Structured register member writes: SYSREG->GHVSRC = ...
            for m in re.finditer(
                r"\b(?P<base>[A-Za-z_]\w*)\s*->\s*(?P<field>[A-Za-z_]\w*)\s*"
                r"(?P<op>\|=|&=|\^=|<<=|>>=|\+=|-=|\*=|/=|%=|=)\s*(?P<rhs>[^;]+);",
                line,
            ):
                base_var = m.group("base")
                field = m.group("field")
                op = m.group("op")
                rhs = m.group("rhs").strip()
                reg_type = var_types.get(base_var)
                base_addr = var_bases.get(base_var)
                abs_addr = _resolve_struct_field_address(reg_type, base_addr, field, reg_struct_offsets)
                canonical = _canonical_symbol(field, abs_addr)
                accesses.append(
                    RegisterAccess(
                        order_index=order,
                        file=path.name,
                        line=lineno,
                        expression=m.group(0).strip(),
                        symbol=f"{base_var}->{field}",
                        canonical_symbol=canonical,
                        address=_format_address(abs_addr),
                        op=_normalize_op(op),
                        value=rhs,
                        domain=_classify_domain(canonical),
                    )
                )
                order += 1

            # Macro writes: FLASH_FRDCNTL_REG = ...
            for m in re.finditer(
                r"\b(?P<sym>[A-Za-z_]\w*)\b\s*(?P<op>\|=|&=|\^=|<<=|>>=|\+=|-=|\*=|/=|%=|=)\s*(?P<rhs>[^;]+);",
                line,
            ):
                sym = m.group("sym")
                if sym not in macro_addresses:
                    continue
                op = m.group("op")
                rhs = m.group("rhs").strip()
                abs_addr = macro_addresses[sym]
                canonical = _canonical_symbol(sym, abs_addr)
                accesses.append(
                    RegisterAccess(
                        order_index=order,
                        file=path.name,
                        line=lineno,
                        expression=m.group(0).strip(),
                        symbol=sym,
                        canonical_symbol=canonical,
                        address=_format_address(abs_addr),
                        op=_normalize_op(op),
                        value=rhs,
                        domain=_classify_domain(canonical),
                    )
                )
                order += 1

            # Pointer-macro writes: *FLASH_FRDCNTL_REG = ...
            for m in re.finditer(
                r"\*\s*(?P<sym>[A-Za-z_]\w*)\s*(?P<op>\|=|&=|\^=|<<=|>>=|\+=|-=|\*=|/=|%=|=)\s*(?P<rhs>[^;]+);",
                line,
            ):
                sym = m.group("sym")
                if sym not in macro_addresses:
                    continue
                op = m.group("op")
                rhs = m.group("rhs").strip()
                abs_addr = macro_addresses[sym]
                canonical = _canonical_symbol(sym, abs_addr)
                accesses.append(
                    RegisterAccess(
                        order_index=order,
                        file=path.name,
                        line=lineno,
                        expression=m.group(0).strip(),
                        symbol=f"*{sym}",
                        canonical_symbol=canonical,
                        address=_format_address(abs_addr),
                        op=_normalize_op(op),
                        value=rhs,
                        domain=_classify_domain(canonical),
                    )
                )
                order += 1

    return accesses


def compare_register_sequences(
    baseline: Sequence[RegisterAccess],
    candidate: Sequence[RegisterAccess],
    *,
    mode: str,
    critical_registers: Optional[set[str]] = None,
) -> Dict[str, Any]:
    critical_set = {s.upper() for s in (critical_registers or set())}

    if mode == "critical_only":
        base_seq = [a for a in baseline if _is_critical_access(a, critical_set)]
        cand_seq = [a for a in candidate if _is_critical_access(a, critical_set)]
    else:
        base_seq = list(baseline)
        cand_seq = list(candidate)

    base_tokens = [f"{a.canonical_symbol}:{a.op}" for a in base_seq]
    cand_tokens = [f"{a.canonical_symbol}:{a.op}" for a in cand_seq]

    matcher = SequenceMatcher(a=base_tokens, b=cand_tokens, autojunk=False)
    mismatches: List[Dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        max_len = max(i2 - i1, j2 - j1)
        for k in range(max_len):
            b_item = base_seq[i1 + k] if (i1 + k) < i2 else None
            c_item = cand_seq[j1 + k] if (j1 + k) < j2 else None
            mismatches.append(
                {
                    "kind": tag,
                    "baseline_index": b_item.order_index if b_item else None,
                    "candidate_index": c_item.order_index if c_item else None,
                    "baseline": asdict(b_item) if b_item else None,
                    "candidate": asdict(c_item) if c_item else None,
                }
            )

    passes = len(mismatches) == 0
    summary = {
        "baseline_sequence_len": len(base_seq),
        "candidate_sequence_len": len(cand_seq),
        "mismatch_count": len(mismatches),
    }

    return {
        "passes": passes,
        "summary": summary,
        "mismatches": mismatches,
    }


def _candidate_paths(output_dir: Path, filename: str) -> List[Path]:
    return [
        output_dir / filename,
        output_dir / "include" / filename,
        output_dir / "source" / filename,
    ]


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    return next((p for p in paths if p.exists()), None)


def _strip_inline_comment(line: str) -> str:
    return re.sub(r"//.*$", "", line)


def _parse_hex(value: str) -> Optional[int]:
    try:
        return int(value, 16)
    except Exception:
        return None


def _format_address(value: Optional[int]) -> Optional[str]:
    if value is None:
        return None
    return f"0x{value:08X}"


def _load_register_struct_offsets(output_dir: Path) -> Dict[str, Dict[str, int]]:
    headers: List[Path] = []
    for root in [output_dir / "include", output_dir / "source", output_dir]:
        if not root.exists():
            continue
        headers.extend(sorted(root.glob("reg_*.h")))

    all_offsets: Dict[str, Dict[str, int]] = {}
    for hdr in headers:
        text = hdr.read_text(encoding="utf-8", errors="ignore")
        # typedef struct { ... } TYPE;
        for block in re.finditer(
            r"typedef\s+struct\s*\{(?P<body>[\s\S]*?)\}\s*(?P<type>[A-Za-z_]\w*)\s*;",
            text,
        ):
            body = block.group("body")
            type_name = block.group("type")
            offsets: Dict[str, int] = {}
            for line in body.splitlines():
                m = re.search(
                    r"volatile\s+uint32_t\s+(?P<field>[A-Za-z_]\w*)(?:\[[^\]]+\])?\s*;\s*/\*\*<\s*(?P<off>0x[0-9A-Fa-f]+)",
                    line,
                )
                if not m:
                    continue
                off = _parse_hex(m.group("off"))
                if off is None:
                    continue
                offsets[m.group("field")] = off
            if offsets:
                all_offsets[type_name] = offsets
    return all_offsets


def _extract_pointer_aliases(content: str) -> Tuple[Dict[str, str], Dict[str, int]]:
    var_types: Dict[str, str] = {}
    var_bases: Dict[str, int] = {}

    decl_re = re.compile(
        r"(?:static\s+)?(?P<type>[A-Za-z_]\w*)\s*\*\s*(?:const\s+)?(?P<var>[A-Za-z_]\w*)\s*=\s*"
        r"\(\s*(?P<cast>[A-Za-z_]\w*)\s*\*\s*\)\s*(?P<addr>0x[0-9A-Fa-f]+)[uU]?\s*;"
    )
    for m in decl_re.finditer(content):
        var = m.group("var")
        typ = m.group("type")
        addr = _parse_hex(m.group("addr"))
        if addr is None:
            continue
        var_types[var] = typ
        var_bases[var] = addr

    macro_re = re.compile(
        r"#define\s+(?P<var>[A-Za-z_]\w*)\s+\(\(\s*(?P<type>[A-Za-z_]\w*)\s*\*\s*\)\s*(?P<addr>0x[0-9A-Fa-f]+)[uU]?\s*\)"
    )
    for m in macro_re.finditer(content):
        var = m.group("var")
        typ = m.group("type")
        addr = _parse_hex(m.group("addr"))
        if addr is None:
            continue
        var_types[var] = typ
        var_bases[var] = addr

    return var_types, var_bases


def _extract_macro_addresses(content: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    ptr_macro_re = re.compile(
        r"#define\s+(?P<name>[A-Za-z_]\w*)\s+\(\*\s*\(?\s*\(\s*volatile\s+uint32_t\s*\*\s*\)\s*(?P<addr>0x[0-9A-Fa-f]+)[uU]?\s*\)?\s*\)"
    )
    for m in ptr_macro_re.finditer(content):
        addr = _parse_hex(m.group("addr"))
        if addr is not None:
            result[m.group("name")] = addr

    addr_ptr_re = re.compile(
        r"#define\s+(?P<name>[A-Za-z_]\w*)\s+\(\(\s*volatile\s+uint32_t\s*\*\s*\)\s*(?P<addr>0x[0-9A-Fa-f]+)[uU]?\s*\)"
    )
    for m in addr_ptr_re.finditer(content):
        addr = _parse_hex(m.group("addr"))
        if addr is not None:
            result[m.group("name")] = addr
    return result


def _resolve_struct_field_address(
    reg_type: Optional[str],
    base_addr: Optional[int],
    field: str,
    offsets: Dict[str, Dict[str, int]],
) -> Optional[int]:
    if not reg_type or base_addr is None:
        return None
    fields = offsets.get(reg_type, {})
    off = fields.get(field)
    if off is None:
        return None
    return base_addr + off


def _normalize_op(op: str) -> str:
    mapping = {
        "=": "write",
        "|=": "rmw_or",
        "&=": "rmw_and",
        "^=": "rmw_xor",
        "+=": "rmw_add",
        "-=": "rmw_sub",
        "*=": "rmw_mul",
        "/=": "rmw_div",
        "%=": "rmw_mod",
        "<<=": "rmw_lshift",
        ">>=": "rmw_rshift",
    }
    return mapping.get(op, op)


def _canonical_symbol(symbol: str, address: Optional[int]) -> str:
    raw = symbol.strip().upper()
    raw = raw.replace("*", "")
    raw = re.sub(r"_REG$", "", raw)
    raw = re.sub(r"_REGISTER$", "", raw)

    # Address-based alias unification for flash register macros.
    if address is not None:
        addr_map = {
            0xFFF87000: "FLASH_FRDCNTL",
            0xFFF87040: "FLASH_FBFALLBACK",
            0xFFF87288: "FLASH_FSMWRENA",
            0xFFF872B8: "FLASH_EEPROMCONFIG",
        }
        mapped = addr_map.get(address)
        if mapped:
            return mapped
    return raw


def _classify_domain(canonical_symbol: str) -> str:
    sym = canonical_symbol.upper()
    if sym.startswith("PINMMR") or sym.startswith("KICKER"):
        return "pinmux"
    if sym in {
        "CSDIS",
        "CSDISSET",
        "CSDISCLR",
        "CDDIS",
        "GHVSRC",
        "RCLKSRC",
        "VCLKASRC",
        "CSVSTAT",
        "PLLCTL1",
        "PLLCTL2",
        "PLLCTL3",
        "CLKCNTL",
        "GLBSTAT",
    }:
        return "pll_clock"
    if sym.startswith("SCI") or sym.startswith("LIN") or sym in {"SCIPIO0", "GCR0", "BRS", "FORMAT"}:
        return "uart_lin"
    if sym.startswith("PSPWRDWN") or sym.startswith("PCR"):
        return "pcr_power"
    return "other"


def _is_critical_access(access: RegisterAccess, critical_set: set[str]) -> bool:
    if access.canonical_symbol.upper() in critical_set:
        return True
    return access.domain in {"pll_clock", "pinmux", "uart_lin", "pcr_power"} and not critical_set


def _write_access_csv(accesses: Sequence[RegisterAccess], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "order_index",
                "file",
                "line",
                "symbol",
                "canonical_symbol",
                "address",
                "op",
                "value",
                "domain",
                "expression",
            ],
        )
        writer.writeheader()
        for access in accesses:
            writer.writerow(asdict(access))


def _write_access_markdown(accesses: Sequence[RegisterAccess], path: Path, *, title: str) -> None:
    lines: List[str] = [f"# {title}", "", f"Total accesses: {len(accesses)}", ""]
    lines.append("| # | File | Line | Symbol | Canonical | Address | Op | Value | Domain |")
    lines.append("|---:|------|-----:|--------|-----------|---------|----|-------|--------|")
    for access in accesses:
        value = access.value.replace("|", "\\|")
        lines.append(
            "| "
            f"{access.order_index} | {access.file} | {access.line} | "
            f"{access.symbol} | {access.canonical_symbol} | {access.address or ''} | "
            f"{access.op} | {value} | {access.domain} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_diff_markdown(diff: Dict[str, Any], path: Path) -> None:
    summary = diff.get("summary", {}) if isinstance(diff, dict) else {}
    mismatches = diff.get("mismatches", []) if isinstance(diff, dict) else []
    lines = ["# Critical Register Sequence Diff", ""]
    lines.append(f"- Passes: {bool(diff.get('passes', False))}")
    lines.append(f"- Baseline sequence length: {summary.get('baseline_sequence_len', 0)}")
    lines.append(f"- Candidate sequence length: {summary.get('candidate_sequence_len', 0)}")
    lines.append(f"- Mismatch count: {summary.get('mismatch_count', 0)}")
    lines.append("")
    lines.append("## Mismatches")
    lines.append("")
    if not mismatches:
        lines.append("No mismatches.")
    else:
        lines.append("| Kind | Baseline | Candidate |")
        lines.append("|------|----------|-----------|")
        for item in mismatches[:300]:
            baseline = item.get("baseline") or {}
            candidate = item.get("candidate") or {}
            btxt = ""
            ctxt = ""
            if baseline:
                btxt = (
                    f"{baseline.get('file')}:{baseline.get('line')} "
                    f"{baseline.get('canonical_symbol')} {baseline.get('op')}"
                )
            if candidate:
                ctxt = (
                    f"{candidate.get('file')}:{candidate.get('line')} "
                    f"{candidate.get('canonical_symbol')} {candidate.get('op')}"
                )
            lines.append(f"| {item.get('kind')} | {btxt} | {ctxt} |")
        if len(mismatches) > 300:
            lines.append("")
            lines.append(f"... truncated {len(mismatches) - 300} additional mismatch rows")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
