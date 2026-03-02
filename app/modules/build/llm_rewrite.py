"""
Bounded LLM-based compile repair for CCS build gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..contracts.contract_checker import check_generated_module_contract
from ..generation.prompt import Model, invoke_model_sync
from ..utils.file_io import normalize_generated_text
from ..utils.utils import extract_text_from_bedrock_response, extract_usage_from_bedrock_response
from .ti_diagnostics import TiDiagnostic


@dataclass(frozen=True)
class RewriteConfig:
    enabled: bool = True
    scope: str = "top_files"
    top_k_files: int = 2
    apply_policy: str = "hybrid"  # hybrid | diff_only | full_file_only
    model: str = "inherit"  # inherit | <Model.value>
    max_tokens: int = 6000
    max_attempts: int = 1
    include_contract_context: bool = True


_ALLOWED_EXTS = {".c", ".h", ".s", ".asm", ".cmd"}
_BRINGUP_MODULES = {"LIN", "SCI", "IOMM", "PLL", "SYSTEM", "PCR", "VIM"}
_REWRITE_EXCLUDED_BASENAMES = {"bsp_validate.c", "main.c"}


def run_llm_targeted_rewrite(
    output_dir: Path,
    diagnostics: Sequence[TiDiagnostic],
    *,
    api_contract_manifest: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
    config: Optional[RewriteConfig] = None,
    run_model_name: Optional[str] = None,
) -> Dict[str, Any]:
    cfg = config or RewriteConfig()
    output_dir = Path(output_dir).resolve()

    result: Dict[str, Any] = {
        "applied": False,
        "actions": [],
        "files": [],
        "target_files": [],
        "prompt_text": "",
        "response_text": "",
        "apply_report": {},
        "tokens": {"input_tokens": 0, "output_tokens": 0},
        "failure_reason": "",
    }

    if not cfg.enabled:
        result["failure_reason"] = "llm_rewrite_disabled"
        return result

    target_files = _select_target_files(output_dir, diagnostics, top_k=max(1, cfg.top_k_files))
    if not target_files:
        result["failure_reason"] = "no_target_files"
        return result
    result["target_files"] = [str(p) for p in target_files]

    prompt = _build_rewrite_prompt(
        output_dir=output_dir,
        target_files=target_files,
        diagnostics=diagnostics,
        api_contract_manifest=api_contract_manifest,
        bringup_contract=bringup_contract,
        include_contract_context=cfg.include_contract_context,
    )
    result["prompt_text"] = prompt

    try:
        model = _resolve_model(cfg.model, run_model_name)
    except Exception as exc:
        result["failure_reason"] = f"invalid_model: {exc}"
        return result

    try:
        response = invoke_model_sync(
            model=model,
            max_tokens=max(1024, int(cfg.max_tokens)),
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = extract_text_from_bedrock_response(response)
        usage = extract_usage_from_bedrock_response(response)
    except Exception as exc:
        result["failure_reason"] = f"llm_invoke_failed: {exc}"
        return result

    result["response_text"] = response_text
    result["tokens"] = usage

    apply_report = apply_llm_rewrite_response(
        output_dir=output_dir,
        response_text=response_text,
        allowed_files=target_files,
        apply_policy=cfg.apply_policy,
        api_contract_manifest=api_contract_manifest,
    )
    result["apply_report"] = apply_report

    touched = [Path(p) for p in apply_report.get("touched_files", [])]
    if touched:
        result["applied"] = True
        result["files"] = [str(p) for p in touched]
        result["actions"] = [
            f"LLM_TARGETED: Updated {p.relative_to(output_dir).as_posix()}" for p in touched
        ]
    else:
        result["failure_reason"] = apply_report.get("failure_reason", "no_edits_applied")

    return result


def _resolve_model(config_model: str, run_model_name: Optional[str]) -> Model:
    selected = (config_model or "inherit").strip().lower()
    if selected == "inherit":
        selected = (run_model_name or "sonnet4.5").strip().lower()
    try:
        return Model(selected)
    except Exception as exc:
        raise ValueError(f"unsupported model '{selected}'") from exc


def _candidate_paths(output_dir: Path, filename: str) -> List[Path]:
    return [
        output_dir / filename,
        output_dir / "include" / filename,
        output_dir / "source" / filename,
    ]


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    return next((p for p in paths if p.exists()), None)


def _resolve_diag_file(output_dir: Path, file_path: str) -> Optional[Path]:
    if not file_path:
        return None
    base = Path(file_path).name
    if not base:
        return None
    candidate = _first_existing(_candidate_paths(output_dir, base))
    if not candidate:
        return None
    if candidate.suffix.lower() not in _ALLOWED_EXTS:
        return None
    return candidate.resolve()


def _diag_score(diag: TiDiagnostic, resolved_path: Path) -> int:
    score = 0
    if diag.severity == "error":
        score += 100
    elif diag.severity == "warning":
        score += 20

    ext = resolved_path.suffix.lower()
    if ext in {".c", ".h"}:
        score += 30
    elif ext in {".s", ".asm"}:
        score += 25
    elif ext == ".cmd":
        score += 10

    # Linker-level unresolved symbols with no concrete file get deprioritized.
    if not diag.file_path:
        score -= 50

    msg = (diag.message or "").lower()
    if "undefined" in msg or "too few arguments" in msg or "expected" in msg:
        score += 20
    return score


def _select_target_files(output_dir: Path, diagnostics: Sequence[TiDiagnostic], top_k: int) -> List[Path]:
    ranked: Dict[Path, Dict[str, int]] = {}
    for diag in diagnostics:
        resolved = _resolve_diag_file(output_dir, diag.file_path)
        if not resolved:
            continue
        if resolved.name.lower() in _REWRITE_EXCLUDED_BASENAMES:
            continue
        node = ranked.setdefault(resolved, {"score": 0, "count": 0, "errors": 0})
        node["score"] += _diag_score(diag, resolved)
        node["count"] += 1
        if diag.severity == "error":
            node["errors"] += 1

    sorted_paths = sorted(
        ranked.items(),
        key=lambda item: (
            -item[1]["score"],
            -item[1]["errors"],
            -item[1]["count"],
            item[0].name.lower(),
        ),
    )
    return [p for p, _ in sorted_paths[: max(1, int(top_k))]]


def _module_for_file(path: Path) -> Optional[str]:
    stem = path.stem.lower()
    direct_map = {
        "system": "SYSTEM",
        "vim": "VIM",
        "bsp_validate": "BSP_VALIDATE",
        "entry": "ENTRY",
        "start": "STARTUP",
    }
    if stem in direct_map:
        return direct_map[stem]
    if stem.endswith("_driver"):
        return stem[:-7].upper()
    if stem.startswith("reg_"):
        return stem[4:].upper()
    return None


def _get_sibling_file(path: Path, output_dir: Path) -> Optional[Path]:
    ext = path.suffix.lower()
    if ext not in {".c", ".h"}:
        return None
    sibling_name = f"{path.stem}{'.h' if ext == '.c' else '.c'}"
    return _first_existing(_candidate_paths(output_dir, sibling_name))


def _build_rewrite_prompt(
    *,
    output_dir: Path,
    target_files: Sequence[Path],
    diagnostics: Sequence[TiDiagnostic],
    api_contract_manifest: Optional[Dict[str, Any]],
    bringup_contract: Optional[Dict[str, Any]],
    include_contract_context: bool,
) -> str:
    rel_targets = [p.relative_to(output_dir).as_posix() for p in target_files]
    lines: List[str] = []
    lines.append("You are fixing CCS compile failures in generated embedded C code.")
    lines.append("")
    lines.append("HARD CONSTRAINTS:")
    lines.append("- Edit ONLY the allowed files listed below.")
    lines.append("- Do NOT create new files.")
    lines.append("- Keep edits minimal and compilation-focused.")
    lines.append("- Preserve API contracts; do not change public signatures unless required by diagnostics and still contract-compatible.")
    lines.append("")
    lines.append("ALLOWED FILES:")
    for rel in rel_targets:
        lines.append(f"- {rel}")
    lines.append("")
    lines.append("OUTPUT FORMAT:")
    lines.append("Unified diff ONLY with ---/+++ and @@ hunks for only allowed files.")
    lines.append("Do NOT emit full-file blocks.")
    lines.append("Return ONLY the diff, no prose.")
    lines.append("")
    lines.append("DIAGNOSTICS:")
    for diag in diagnostics:
        resolved = _resolve_diag_file(output_dir, diag.file_path)
        if resolved and resolved in target_files:
            rel = resolved.relative_to(output_dir).as_posix()
            lines.append(f"- {rel}:{diag.line} [{diag.severity}] {diag.message}")

    if include_contract_context and api_contract_manifest:
        modules = api_contract_manifest.get("modules", {}) if isinstance(api_contract_manifest, dict) else {}
        lines.append("")
        lines.append("API CONTRACT CONTEXT:")
        for path in target_files:
            mod = _module_for_file(path)
            if not mod or mod in {"BSP_VALIDATE", "ENTRY", "STARTUP"}:
                continue
            mod_data = modules.get(mod)
            if mod_data:
                lines.append(f"- Module {mod}:")
                for fname, sig in (mod_data.get("functions", {}) or {}).items():
                    arity = sig.get("arity")
                    lines.append(f"  - {fname} arity={arity}")

    if include_contract_context and bringup_contract:
        lines.append("")
        lines.append("BRINGUP CONTRACT CONTEXT:")
        serial = (bringup_contract.get("serial") or {}) if isinstance(bringup_contract, dict) else {}
        if serial:
            lines.append(f"- serial.primary_path={serial.get('primary_path')}")
            lines.append(f"- serial.baud_default={serial.get('baud_default')}")
        required_regs = (
            ((bringup_contract.get("lin") or {}).get("required_registers") or {})
            if isinstance(bringup_contract, dict)
            else {}
        )
        if required_regs:
            lines.append(f"- lin.required_registers={required_regs}")

    for path in target_files:
        rel = path.relative_to(output_dir).as_posix()
        lines.append("")
        lines.append(f"===== FILE CONTEXT: {rel} =====")
        lines.append(path.read_text(encoding="utf-8", errors="ignore"))
        sibling = _get_sibling_file(path, output_dir)
        if sibling:
            sibling_rel = sibling.relative_to(output_dir).as_posix()
            lines.append("")
            lines.append(f"===== SIBLING CONTEXT: {sibling_rel} =====")
            lines.append(sibling.read_text(encoding="utf-8", errors="ignore"))

    return "\n".join(lines).strip() + "\n"


def apply_llm_rewrite_response(
    *,
    output_dir: Path,
    response_text: str,
    allowed_files: Sequence[Path],
    apply_policy: str,
    api_contract_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    output_dir = output_dir.resolve()
    allowed = {p.resolve() for p in allowed_files}
    policy = (apply_policy or "diff_only").strip().lower()
    report: Dict[str, Any] = {
        "mode": policy,
        "diff_attempted": False,
        "diff_applied": False,
        "full_file_attempted": False,
        "full_file_applied": False,
        "touched_files": [],
        "errors": [],
        "warnings": [],
        "failure_reason": "",
    }

    if policy not in {"hybrid", "diff_only", "full_file_only"}:
        policy = "diff_only"

    touched: List[Path] = []
    if policy in {"hybrid", "diff_only"}:
        report["diff_attempted"] = True
        diff_result = _try_apply_unified_diff(response_text, output_dir, allowed)
        report["errors"].extend(diff_result.get("errors", []))
        if diff_result.get("applied"):
            report["diff_applied"] = True
            touched = [Path(p) for p in diff_result.get("touched_files", [])]

    if not touched and policy in {"hybrid", "full_file_only"}:
        report["full_file_attempted"] = True
        ff_result = _try_apply_full_file_blocks(response_text, output_dir, allowed)
        report["errors"].extend(ff_result.get("errors", []))
        if ff_result.get("applied"):
            report["full_file_applied"] = True
            touched = [Path(p) for p in ff_result.get("touched_files", [])]

    if touched:
        sanity = _quick_signature_sanity(output_dir, touched, api_contract_manifest)
        if sanity.get("errors"):
            report["warnings"].extend(sanity["errors"])
        report["touched_files"] = [str(p) for p in touched]
        return report

    report["failure_reason"] = "no_applicable_edit_payload"
    return report


def _allowed_resolved_path(candidate: str, output_dir: Path, allowed: set[Path]) -> Optional[Path]:
    normalized = candidate.strip().replace("\\", "/")
    normalized = normalized.replace("a/", "", 1) if normalized.startswith("a/") else normalized
    normalized = normalized.replace("b/", "", 1) if normalized.startswith("b/") else normalized
    if normalized.startswith("../") or normalized.startswith("/"):
        return None
    path = (output_dir / normalized).resolve()
    if path not in allowed:
        # Try basename resolution for compiler-style paths.
        base = Path(normalized).name
        for allowed_path in allowed:
            if allowed_path.name == base:
                return allowed_path
        return None
    return path


def _parse_hunk_header(header: str) -> Optional[Tuple[int, int, int, int]]:
    match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header.strip())
    if not match:
        return None
    old_start = int(match.group(1))
    old_count = int(match.group(2) or "1")
    new_start = int(match.group(3))
    new_count = int(match.group(4) or "1")
    return old_start, old_count, new_start, new_count


def _apply_hunks_to_lines(original: List[str], hunks: List[Tuple[str, List[str]]]) -> Tuple[Optional[List[str]], List[str]]:
    errors: List[str] = []
    current = list(original)
    offset = 0

    for header, hunk_lines in hunks:
        parsed = _parse_hunk_header(header)
        if not parsed:
            errors.append(f"invalid_hunk_header: {header}")
            return None, errors
        old_start, _, _, _ = parsed
        expected_idx = old_start - 1 + offset
        idx = expected_idx
        if idx < 0:
            errors.append(f"invalid_hunk_start: {header}")
            return None, errors

        # Fuzzy matching: if hunk doesn't match at stated line, search nearby
        # and then globally. This handles small context drift in model diffs.
        if not _hunk_matches_at(current, hunk_lines, idx):
            found_idx = _find_hunk_match_index(current, hunk_lines, idx)
            if found_idx is None:
                errors.append(f"hunk_not_found_near_expected_start: {header}")
                return None, errors
            idx = found_idx
            offset += (idx - expected_idx)

        for raw in hunk_lines:
            if raw.startswith("\\ No newline at end of file"):
                continue
            if not raw:
                prefix = " "
                text = ""
            else:
                prefix = raw[0]
                text = raw[1:] if len(raw) > 1 else ""

            if prefix == " ":
                if idx >= len(current) or current[idx] != text:
                    got = "<eof>" if idx >= len(current) else current[idx]
                    errors.append(f"context_mismatch expected='{text}' got='{got}'")
                    return None, errors
                idx += 1
            elif prefix == "-":
                if idx >= len(current) or current[idx] != text:
                    got = "<eof>" if idx >= len(current) else current[idx]
                    errors.append(f"delete_mismatch expected='{text}' got='{got}'")
                    return None, errors
                del current[idx]
                offset -= 1
            elif prefix == "+":
                current.insert(idx, text)
                idx += 1
                offset += 1
            else:
                errors.append(f"unsupported_hunk_line_prefix: {prefix}")
                return None, errors

    return current, errors


def _try_apply_unified_diff(response_text: str, output_dir: Path, allowed: set[Path]) -> Dict[str, Any]:
    lines = _strip_markdown_fences(response_text).splitlines()
    errors: List[str] = []
    touched: List[Path] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.startswith("--- "):
            i += 1
            continue
        if i + 1 >= len(lines) or not lines[i + 1].startswith("+++ "):
            errors.append("malformed_diff_missing_plus_header")
            return {"applied": False, "errors": errors, "touched_files": []}

        old_label = lines[i][4:].strip()
        new_label = lines[i + 1][4:].strip()
        target_path = _allowed_resolved_path(new_label, output_dir, allowed) or _allowed_resolved_path(
            old_label, output_dir, allowed
        )
        if not target_path:
            errors.append(f"diff_target_out_of_scope: {new_label}")
            return {"applied": False, "errors": errors, "touched_files": []}
        if not target_path.exists():
            errors.append(f"diff_target_missing: {target_path}")
            return {"applied": False, "errors": errors, "touched_files": []}
        if target_path.suffix.lower() not in _ALLOWED_EXTS:
            errors.append(f"diff_target_invalid_extension: {target_path}")
            return {"applied": False, "errors": errors, "touched_files": []}

        i += 2
        hunks: List[Tuple[str, List[str]]] = []
        while i < len(lines):
            if lines[i].startswith("--- "):
                break
            if not lines[i].startswith("@@ "):
                i += 1
                continue
            header = lines[i]
            i += 1
            hunk_lines: List[str] = []
            while i < len(lines):
                if lines[i].startswith("@@ ") or lines[i].startswith("--- "):
                    break
                hunk_lines.append(lines[i])
                i += 1
            hunks.append((header, hunk_lines))

        if not hunks:
            errors.append(f"no_hunks_for_target: {target_path.name}")
            return {"applied": False, "errors": errors, "touched_files": []}

        original_lines = target_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        patched_lines, patch_errors = _apply_hunks_to_lines(original_lines, hunks)
        if patch_errors:
            return {"applied": False, "errors": patch_errors, "touched_files": []}
        if patched_lines is None:
            return {"applied": False, "errors": ["patch_application_failed"], "touched_files": []}

        new_text = "\n".join(patched_lines) + "\n"
        if not new_text.strip():
            errors.append(f"empty_file_after_patch: {target_path.name}")
            return {"applied": False, "errors": errors, "touched_files": []}
        target_path.write_text(normalize_generated_text(new_text, target_path), encoding="utf-8")
        touched.append(target_path)

    return {"applied": len(touched) > 0, "errors": errors, "touched_files": [str(p) for p in touched]}


def _strip_markdown_fences(text: str) -> str:
    lines = text.splitlines()
    out: List[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        out.append(line)
    return "\n".join(out)


def _hunk_matches_at(lines: List[str], hunk_lines: List[str], start_idx: int) -> bool:
    if start_idx < 0:
        return False
    idx = start_idx
    for raw in hunk_lines:
        if raw.startswith("\\ No newline at end of file"):
            continue
        if not raw:
            prefix = " "
            text = ""
        else:
            prefix = raw[0]
            text = raw[1:] if len(raw) > 1 else ""

        if prefix in {" ", "-"}:
            if idx >= len(lines) or lines[idx] != text:
                return False
            idx += 1
        elif prefix == "+":
            continue
        else:
            return False
    return True


def _find_hunk_match_index(lines: List[str], hunk_lines: List[str], expected_idx: int) -> Optional[int]:
    # Try expected location first.
    if _hunk_matches_at(lines, hunk_lines, expected_idx):
        return expected_idx

    # Local search around expected location.
    radius = 120
    for delta in range(1, radius + 1):
        left = expected_idx - delta
        right = expected_idx + delta
        if left >= 0 and _hunk_matches_at(lines, hunk_lines, left):
            return left
        if right <= len(lines) and _hunk_matches_at(lines, hunk_lines, right):
            return right

    # Global search fallback.
    for idx in range(0, len(lines) + 1):
        if _hunk_matches_at(lines, hunk_lines, idx):
            return idx
    return None


_FILE_BLOCK_RE = re.compile(
    r"^===== FILE:\s*(?P<path>.+?)\s*=====\s*$",
    re.MULTILINE,
)


def _try_apply_full_file_blocks(response_text: str, output_dir: Path, allowed: set[Path]) -> Dict[str, Any]:
    matches = list(_FILE_BLOCK_RE.finditer(response_text))
    if not matches:
        return {"applied": False, "errors": ["no_file_blocks_found"], "touched_files": []}

    touched: List[Path] = []
    errors: List[str] = []
    for idx, match in enumerate(matches):
        rel_path = match.group("path").strip()
        content_start = match.end()
        content_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(response_text)
        new_content = response_text[content_start:content_end]
        if new_content.startswith("\n"):
            new_content = new_content[1:]

        target = _allowed_resolved_path(rel_path, output_dir, allowed)
        if not target:
            errors.append(f"file_block_out_of_scope: {rel_path}")
            continue
        if not target.exists():
            errors.append(f"file_block_target_missing: {rel_path}")
            continue
        if target.suffix.lower() not in _ALLOWED_EXTS:
            errors.append(f"file_block_invalid_extension: {rel_path}")
            continue
        if not new_content.strip():
            errors.append(f"file_block_empty_content: {rel_path}")
            continue

        if not new_content.endswith("\n"):
            new_content += "\n"
        target.write_text(normalize_generated_text(new_content, target), encoding="utf-8")
        touched.append(target)

    return {"applied": len(touched) > 0, "errors": errors, "touched_files": [str(p) for p in touched]}


def _quick_signature_sanity(
    output_dir: Path,
    touched_files: Sequence[Path],
    api_contract_manifest: Optional[Dict[str, Any]],
) -> Dict[str, List[str]]:
    if not api_contract_manifest:
        return {"errors": []}

    touched_names = {p.name for p in touched_files}
    errors: List[str] = []
    checked_modules: set[str] = set()

    for name in touched_names:
        module = _module_for_file(Path(name))
        if not module or module in {"BSP_VALIDATE", "ENTRY", "STARTUP"}:
            continue
        if module in checked_modules:
            continue
        checked_modules.add(module)
        if module not in (api_contract_manifest.get("modules") or {}):
            continue

        lower = module.lower()
        header_path = _first_existing(_candidate_paths(output_dir, f"{lower}_driver.h"))
        source_path = _first_existing(_candidate_paths(output_dir, f"{lower}_driver.c"))
        if not header_path or not source_path:
            # SYSTEM/VIM have non *_driver naming.
            if module == "SYSTEM":
                header_path = _first_existing(_candidate_paths(output_dir, "system.h"))
                source_path = _first_existing(_candidate_paths(output_dir, "system.c"))
            elif module == "VIM":
                header_path = _first_existing(_candidate_paths(output_dir, "vim.h"))
                source_path = _first_existing(_candidate_paths(output_dir, "vim.c"))
        if not header_path or not source_path:
            continue

        contract_result = check_generated_module_contract(
            module,
            header_path,
            source_path,
            api_contract_manifest,
        )
        if not contract_result.get("passed", True):
            errors.extend(contract_result.get("errors", [])[:3])

    return {"errors": errors}
