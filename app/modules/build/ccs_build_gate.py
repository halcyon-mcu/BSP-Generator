"""
External CCS workspace compile gate.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, Optional

from .llm_rewrite import RewriteConfig, run_llm_targeted_rewrite
from .ti_diagnostics import (
    apply_deterministic_fixes,
    apply_targeted_rewrite,
    parse_ti_diagnostics,
    summarize_ti_diagnostics,
)
from .workspace_sync import resolve_workspace_layout, sync_generated_to_project


def run_ccs_build_gate(
    output_dir: Path,
    generation_profile: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
    api_contract_manifest: Optional[Dict[str, Any]] = None,
    bringup_contract: Optional[Dict[str, Any]] = None,
    run_model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    cfg = dict(generation_profile.get("build_gate", {}) or {})
    overrides = overrides or {}

    enabled = bool(cfg.get("enabled", True))
    mode = str(overrides.get("build_gate") or cfg.get("mode", "strict")).strip().lower()
    if mode == "off":
        enabled = False
    if mode not in {"strict", "advisory", "off"}:
        mode = "strict"

    fail_on_compile_error = bool(cfg.get("fail_on_compile_error", True))
    configuration = str(overrides.get("ccs_config") or cfg.get("configuration", "Debug")).strip() or "Debug"
    external_workspace_path = str(
        overrides.get("ccs_workspace") or cfg.get("external_workspace_path", "")
    ).strip()
    project_name = str(overrides.get("ccs_project") or cfg.get("project_name", "")).strip()
    max_fix_rounds = cfg.get("max_fix_rounds", 3)
    try:
        max_fix_rounds = int(max_fix_rounds)
    except (TypeError, ValueError):
        max_fix_rounds = 3
    if max_fix_rounds < 0:
        max_fix_rounds = 0
    allow_targeted = bool(cfg.get("allow_targeted_llm_rewrite", True))
    llm_cfg_raw = dict(cfg.get("llm_rewrite", {}) or {})
    llm_enabled = bool(llm_cfg_raw.get("enabled", allow_targeted))
    llm_override = str(overrides.get("build_gate_llm") or "").strip().lower()
    if llm_override == "on":
        llm_enabled = True
    elif llm_override == "off":
        llm_enabled = False
    llm_top_k = llm_cfg_raw.get("top_k_files", 2)
    if overrides.get("build_gate_llm_top_k") is not None:
        llm_top_k = overrides.get("build_gate_llm_top_k")
    try:
        llm_top_k = max(1, int(llm_top_k))
    except (TypeError, ValueError):
        llm_top_k = 2
    llm_model = str(overrides.get("build_gate_llm_model") or llm_cfg_raw.get("model", "inherit")).strip().lower() or "inherit"
    llm_apply_policy = str(llm_cfg_raw.get("apply_policy", "diff_only")).strip().lower() or "diff_only"
    llm_max_tokens = llm_cfg_raw.get("max_tokens", 6000)
    try:
        llm_max_tokens = max(1024, int(llm_max_tokens))
    except (TypeError, ValueError):
        llm_max_tokens = 6000
    llm_max_attempts = llm_cfg_raw.get("max_attempts", 1)
    try:
        llm_max_attempts = max(0, int(llm_max_attempts))
    except (TypeError, ValueError):
        llm_max_attempts = 1
    llm_include_contract = bool(llm_cfg_raw.get("include_contract_context", True))
    llm_cfg = RewriteConfig(
        enabled=llm_enabled,
        scope=str(llm_cfg_raw.get("scope", "top_files")).strip().lower() or "top_files",
        top_k_files=llm_top_k,
        apply_policy=llm_apply_policy,
        model=llm_model,
        max_tokens=llm_max_tokens,
        max_attempts=llm_max_attempts,
        include_contract_context=llm_include_contract,
    )
    clean_stale = bool(cfg.get("clean_stale_project_files", True))
    clean_build = bool(cfg.get("clean_build", True))

    report: Dict[str, Any] = {
        "mode": mode,
        "enabled": enabled,
        "configuration": configuration,
        "external_workspace_path": external_workspace_path,
        "project_name": project_name,
        "max_fix_rounds": max_fix_rounds,
        "allow_targeted_llm_rewrite": allow_targeted,
        "llm_rewrite": {
            "enabled": llm_cfg.enabled,
            "scope": llm_cfg.scope,
            "top_k_files": llm_cfg.top_k_files,
            "apply_policy": llm_cfg.apply_policy,
            "model": llm_cfg.model,
            "max_tokens": llm_cfg.max_tokens,
            "max_attempts": llm_cfg.max_attempts,
            "include_contract_context": llm_cfg.include_contract_context,
        },
        "clean_stale_project_files": clean_stale,
        "clean_build": clean_build,
        "passes": False,
        "status": "skipped",
        "rounds": [],
        "error_summary": {},
        "synced_files": 0,
        "removed_stale_files": 0,
        "sync_fingerprint": {},
        "sync_verified": False,
        "llm_rewrite_attempted": False,
        "llm_rewrite_applied": False,
        "llm_rewrite_target_files": [],
        "llm_rewrite_tokens": {"input_tokens": 0, "output_tokens": 0},
        "llm_rewrite_failure_reason": "",
        "required": mode == "strict" or fail_on_compile_error,
        "startup_contract_status": {
            "status": "not_evaluated",
            "passes": None,
            "gate_mode": "warn",
        },
        "parity_guard_status": {
            "status": "not_evaluated",
            "passes": None,
            "mode": "critical_only",
        },
        "blocking_reasons": [],
    }

    if not enabled:
        report["status"] = "disabled"
        _write_gate_report(output_dir, report)
        return report

    if not external_workspace_path or not project_name:
        report["status"] = "invalid_config"
        report["error_summary"] = {
            "errors": [
                "build_gate.enabled=true requires both external_workspace_path and project_name"
            ]
        }
        _write_gate_report(output_dir, report)
        return report

    try:
        layout = resolve_workspace_layout(
            external_workspace_path=external_workspace_path,
            project_name=project_name,
            configuration=configuration,
        )
    except Exception as exc:
        report["status"] = "workspace_not_found"
        report["error_summary"] = {"errors": [str(exc)]}
        _write_gate_report(output_dir, report)
        return report

    sync = sync_generated_to_project(
        output_dir,
        layout.project_path,
        clean_stale_generated_files=clean_stale,
    )
    pruned_refs = _prune_stale_bsp_validate_make_refs(layout.configuration_path, Path(output_dir))
    reconciled_refs = _reconcile_generated_make_refs(layout.configuration_path, Path(output_dir))
    _log(progress_callback, f"[build-gate] Synced {len(sync.get('copied_files', []))} files to CCS project")
    report["synced_files"] = len(sync.get("copied_files", []))
    report["removed_stale_files"] = len(sync.get("removed_files", []))
    report["pruned_stale_make_refs"] = int(pruned_refs)
    report["reconciled_make_refs"] = int(reconciled_refs)
    if pruned_refs > 0:
        _log(progress_callback, f"[build-gate] Pruned {pruned_refs} stale bsp_validate makefile references")
    if reconciled_refs > 0:
        _log(progress_callback, f"[build-gate] Reconciled {reconciled_refs} generated source/object makefile references")
    report["sync_fingerprint"] = dict(sync.get("fingerprint", {}) or {})
    report["sync_verified"] = bool(report["sync_fingerprint"].get("matches", False))
    if not report["sync_verified"]:
        report["status"] = "sync_fingerprint_mismatch"
        report["error_summary"] = {
            "errors": [
                "Post-sync fingerprint mismatch between generated output and workspace project files."
            ],
            "mismatch_files": report["sync_fingerprint"].get("mismatch_files", []),
        }
        _write_gate_report(output_dir, report)
        return report
    gmake_bin = _resolve_gmake_binary()

    fix_stages: list[str] = []
    if max_fix_rounds >= 1:
        fix_stages.append("deterministic")
    if max_fix_rounds >= 2:
        fix_stages.append("deterministic_targeted")

    remaining_fix_rounds = max(0, max_fix_rounds - len(fix_stages))
    if llm_cfg.enabled and llm_cfg.max_attempts > 0 and remaining_fix_rounds > 0:
        llm_rounds = min(remaining_fix_rounds, llm_cfg.max_attempts)
        fix_stages.extend(["llm_targeted"] * llm_rounds)
    total_attempts = 1 + len(fix_stages)
    all_logs: list[str] = []
    any_fix_actions = False

    for attempt in range(total_attempts):
        _log(progress_callback, f"[build-gate] Round {attempt + 1}/{total_attempts}: compile")
        return_code, log_text = _run_ccs_make(
            layout,
            gmake_bin,
            clean_first=clean_build,
            force_rebuild=clean_build,
        )
        diagnostics = parse_ti_diagnostics(log_text)
        summary = summarize_ti_diagnostics(diagnostics)

        round_entry: Dict[str, Any] = {
            "attempt": attempt,
            "return_code": return_code,
            "diagnostics": summary,
            "fix_stage": "none",
            "fix_actions": [],
            "fix_files": [],
            "log_file": f"ccs_build_log_round{attempt}.txt",
        }
        report["rounds"].append(round_entry)

        round_log_path = Path(output_dir) / round_entry["log_file"]
        round_log_path.write_text(log_text, encoding="utf-8")
        all_logs.append(f"===== ROUND {attempt} =====\n{log_text.rstrip()}\n")

        compile_ok = return_code == 0 and summary.get("errors", 0) == 0
        if not compile_ok and _is_benign_missing_bsp_validate_target(log_text, summary, Path(output_dir)):
            compile_ok = True
            round_entry["compile_note"] = "ignored_stale_bsp_validate_target"
        if compile_ok:
            report["passes"] = True
            report["status"] = "pass"
            report["error_summary"] = summary
            _log(
                progress_callback,
                f"[build-gate] Round {attempt + 1} passed (errors={summary.get('errors', 0)}, warnings={summary.get('warnings', 0)})",
            )
            break

        if attempt >= total_attempts - 1:
            report["status"] = "failed_after_max_rounds"
            report["error_summary"] = summary
            break

        stage = fix_stages[attempt] if attempt < len(fix_stages) else "none"
        round_entry["fix_stage"] = stage
        _log(progress_callback, f"[build-gate] Applying fix stage: {stage}")

        if stage == "deterministic":
            fix_result = apply_deterministic_fixes(
                Path(output_dir), diagnostics, api_contract_manifest=api_contract_manifest
            )
        elif stage == "deterministic_targeted":
            fix_result = apply_targeted_rewrite(Path(output_dir), diagnostics)
        elif stage == "llm_targeted":
            report["llm_rewrite_attempted"] = True
            fix_result = run_llm_targeted_rewrite(
                output_dir=Path(output_dir),
                diagnostics=diagnostics,
                api_contract_manifest=api_contract_manifest,
                bringup_contract=bringup_contract,
                config=llm_cfg,
                run_model_name=run_model_name or overrides.get("model"),
            )
            report["llm_rewrite_target_files"] = list(fix_result.get("target_files", []))
            report["llm_rewrite_tokens"] = dict(fix_result.get("tokens", {}) or {})
            report["llm_rewrite_failure_reason"] = str(fix_result.get("failure_reason", "") or "")

            prompt_text = str(fix_result.get("prompt_text", "") or "")
            response_text = str(fix_result.get("response_text", "") or "")
            apply_report = fix_result.get("apply_report", {}) or {}
            prompt_file = Path(output_dir) / f"llm_rewrite_prompt_round{attempt}.txt"
            response_file = Path(output_dir) / f"llm_rewrite_response_round{attempt}.txt"
            apply_file = Path(output_dir) / f"llm_rewrite_apply_report_round{attempt}.json"
            prompt_file.write_text(prompt_text, encoding="utf-8")
            response_file.write_text(response_text, encoding="utf-8")
            apply_file.write_text(json.dumps(apply_report, indent=2), encoding="utf-8")
            round_entry["llm_artifacts"] = {
                "prompt": str(prompt_file),
                "response": str(response_file),
                "apply_report": str(apply_file),
            }
            if report["llm_rewrite_target_files"]:
                _log(
                    progress_callback,
                    "[build-gate] LLM target files: "
                    + ", ".join(Path(p).name for p in report["llm_rewrite_target_files"]),
                )
            tokens = report.get("llm_rewrite_tokens", {}) or {}
            _log(
                progress_callback,
                f"[build-gate] LLM tokens: in={int(tokens.get('input_tokens', 0))}, out={int(tokens.get('output_tokens', 0))}",
            )
        else:
            fix_result = {"actions": [], "files": [], "applied": False}

        actions = list(fix_result.get("actions", []))
        files = list(fix_result.get("files", []))
        round_entry["fix_actions"] = actions
        round_entry["fix_files"] = files

        if actions:
            any_fix_actions = True
            _log(progress_callback, f"[build-gate] Applied {len(actions)} fix actions")
        if stage == "llm_targeted" and actions:
            report["llm_rewrite_applied"] = True

        if actions:
            sync = sync_generated_to_project(
                output_dir,
                layout.project_path,
                clean_stale_generated_files=clean_stale,
            )
            pruned_refs = _prune_stale_bsp_validate_make_refs(layout.configuration_path, Path(output_dir))
            reconciled_refs = _reconcile_generated_make_refs(layout.configuration_path, Path(output_dir))
            report["synced_files"] = len(sync.get("copied_files", []))
            report["removed_stale_files"] += len(sync.get("removed_files", []))
            report["pruned_stale_make_refs"] = int(report.get("pruned_stale_make_refs", 0)) + int(pruned_refs)
            report["reconciled_make_refs"] = int(report.get("reconciled_make_refs", 0)) + int(reconciled_refs)
            report["sync_fingerprint"] = dict(sync.get("fingerprint", {}) or {})
            report["sync_verified"] = bool(report["sync_fingerprint"].get("matches", False))
            _log(progress_callback, f"[build-gate] Re-synced {len(sync.get('copied_files', []))} files after fixes")
            if pruned_refs > 0:
                _log(progress_callback, f"[build-gate] Pruned {pruned_refs} stale bsp_validate makefile references")
            if reconciled_refs > 0:
                _log(progress_callback, f"[build-gate] Reconciled {reconciled_refs} generated source/object makefile references")
            if not report["sync_verified"]:
                report["status"] = "sync_fingerprint_mismatch_after_fix"
                report["error_summary"] = {
                    "errors": [
                        "Post-fix sync fingerprint mismatch between generated output and workspace project files."
                    ],
                    "mismatch_files": report["sync_fingerprint"].get("mismatch_files", []),
                }
                break

    if not report["passes"] and not any_fix_actions:
        report["status"] = "failed_no_applicable_fix"

    combined_log_path = Path(output_dir) / "ccs_build_log.txt"
    combined_log_path.write_text("\n".join(all_logs), encoding="utf-8")
    report["combined_log_file"] = str(combined_log_path)
    if report.get("llm_rewrite_attempted") and not report.get("llm_rewrite_applied"):
        _log(
            progress_callback,
            "[build-gate] LLM rewrite attempted but no edits were applied"
            + (f" ({report.get('llm_rewrite_failure_reason')})" if report.get("llm_rewrite_failure_reason") else ""),
        )
    _write_gate_report(output_dir, report)
    return report


def _log(callback: Optional[Callable[[str], None]], message: str) -> None:
    if callback:
        try:
            callback(message)
            return
        except Exception:
            pass
    print(message)


def _has_generated_bsp_validate(output_dir: Path) -> bool:
    candidates = [
        Path(output_dir) / "bsp_validate.c",
        Path(output_dir) / "source" / "bsp_validate.c",
    ]
    return any(path.exists() for path in candidates)


def _is_benign_missing_bsp_validate_target(
    log_text: str,
    summary: Dict[str, Any],
    output_dir: Path,
) -> bool:
    missing_target_re = re.compile(
        r"No rule to make target\s+['`\"]?bsp_validate\.(?:obj|d)['`\"]?",
        re.IGNORECASE,
    )
    gmake_fatal_re = re.compile(r"gmake:\s*\*\*\*", re.IGNORECASE)
    compiler_error_re = re.compile(r":\s*error\s*#", re.IGNORECASE)

    if int((summary or {}).get("errors", 0)) != 0:
        return False
    if _has_generated_bsp_validate(output_dir):
        return False
    if not missing_target_re.search(str(log_text)):
        return False

    for raw_line in str(log_text).splitlines():
        line = raw_line.strip()
        if gmake_fatal_re.search(line) and not missing_target_re.search(line):
            return False
        if compiler_error_re.search(line):
            return False
    return True


def _prune_stale_bsp_validate_make_refs(configuration_path: Path, output_dir: Path) -> int:
    """
    Remove stale bsp_validate references from CCS auto-generated makefiles
    when bsp_validate.c is not part of the generated output.
    """
    if _has_generated_bsp_validate(output_dir):
        return 0
    if not Path(configuration_path).exists():
        return 0

    touched = 0
    mk_candidates = [
        Path(configuration_path) / "subdir_vars.mk",
        Path(configuration_path) / "subdir_rules.mk",
        Path(configuration_path) / "sources.mk",
        Path(configuration_path) / "objects.mk",
        Path(configuration_path) / "makefile",
    ]
    for mk_path in mk_candidates:
        if not mk_path.exists() or not mk_path.is_file():
            continue
        text = mk_path.read_text(encoding="utf-8", errors="ignore")
        newline = _preferred_newline(text)
        if "bsp_validate" not in text.lower():
            continue
        filtered = [line for line in text.splitlines() if "bsp_validate" not in line.lower()]
        updated = newline.join(filtered).rstrip("\r\n") + newline
        if updated != text:
            mk_path.write_text(updated, encoding="utf-8", newline=newline)
            touched += 1
    return touched


def _collect_generated_c_basenames(output_dir: Path) -> list[str]:
    names: set[str] = set()
    pools = [Path(output_dir), Path(output_dir) / "source"]
    for folder in pools:
        if not folder.exists():
            continue
        for entry in folder.iterdir():
            if not entry.is_file() or entry.suffix.lower() != ".c":
                continue
            names.add(entry.stem)
    return sorted(names)


def _reconcile_generated_make_refs(configuration_path: Path, output_dir: Path) -> int:
    """
    Ensure CCS auto-generated makefiles include generated C sources/objects.
    This prevents unresolved link symbols after post-generation adds new C files
    (e.g. app_intent.c) but workspace make metadata is stale.
    """
    cfg = Path(configuration_path)
    if not cfg.exists():
        return 0

    stems = _collect_generated_c_basenames(output_dir)
    if not stems:
        return 0

    touched = 0
    subdir_vars = cfg / "subdir_vars.mk"
    if subdir_vars.exists():
        text = subdir_vars.read_text(encoding="utf-8", errors="ignore")
        newline = _preferred_newline(text)
        updated = text
        updated = _ensure_var_block_entries(
            updated,
            "C_SRCS",
            [f"../{stem}.c" for stem in stems],
        )
        updated = _ensure_var_block_entries(
            updated,
            "C_DEPS",
            [f"./{stem}.d" for stem in stems],
        )
        updated = _ensure_var_block_entries(
            updated,
            "OBJS",
            [f"./{stem}.obj" for stem in stems],
        )
        updated = _ensure_var_block_entries(
            updated,
            "C_SRCS__QUOTED",
            [f'"../{stem}.c"' for stem in stems],
        )
        updated = _ensure_var_block_entries(
            updated,
            "C_DEPS__QUOTED",
            [f'"{stem}.d"' for stem in stems],
        )
        updated = _ensure_var_block_entries(
            updated,
            "OBJS__QUOTED",
            [f'"{stem}.obj"' for stem in stems],
        )
        if updated != text:
            subdir_vars.write_text(updated, encoding="utf-8", newline=newline)
            touched += 1

    makefile = cfg / "makefile"
    if makefile.exists():
        text = makefile.read_text(encoding="utf-8", errors="ignore")
        newline = _preferred_newline(text)
        updated = _ensure_ordered_objs_entries(text, [f'"./{stem}.obj"' for stem in stems])
        if updated != text:
            makefile.write_text(updated, encoding="utf-8", newline=newline)
            touched += 1

    return touched


def _preferred_newline(text: str) -> str:
    # Keep Windows makefiles consistently CRLF when possible.
    if "\r\n" in text:
        return "\r\n"
    if "\n" in text:
        return "\n"
    if "\r" in text:
        return "\r"
    return "\n"


def _ensure_var_block_entries(text: str, var_name: str, entries: list[str]) -> str:
    newline = _preferred_newline(text)
    lines = text.splitlines()
    start = -1
    for idx, line in enumerate(lines):
        if line.strip().startswith(f"{var_name} +="):
            start = idx
            break
    if start < 0:
        return text

    end = start + 1
    while end < len(lines) and lines[end].strip() != "":
        end += 1

    existing = set()
    for idx in range(start + 1, end):
        token = lines[idx].strip().rstrip("\\").strip()
        if token:
            existing.add(token.lower())

    to_add = [entry for entry in entries if entry.strip().lower() not in existing]
    if not to_add:
        return text

    value_rows = [idx for idx in range(start + 1, end) if lines[idx].strip()]
    if value_rows:
        prior_last_idx = value_rows[-1]
        prior_last = lines[prior_last_idx].rstrip()
        if not prior_last.endswith("\\"):
            lines[prior_last_idx] = f"{prior_last} \\"

    insertion: list[str] = []
    for idx, entry in enumerate(to_add):
        token = entry.strip()
        if idx < len(to_add) - 1:
            insertion.append(f"{token} \\")
        else:
            insertion.append(token)
    lines[end:end] = insertion
    return newline.join(lines) + newline


def _ensure_ordered_objs_entries(text: str, entries: list[str]) -> str:
    newline = _preferred_newline(text)
    lines = text.splitlines()
    start = -1
    for idx, line in enumerate(lines):
        if line.strip().startswith("ORDERED_OBJS +="):
            start = idx
            break
    if start < 0:
        return text

    end = start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        if stripped.startswith("$(GEN_CMDS__FLAG)") or stripped.startswith("-lrts"):
            break
        end += 1

    existing = set()
    for idx in range(start + 1, end):
        token = lines[idx].strip().rstrip("\\").strip()
        if token:
            existing.add(token.lower())

    to_add = [entry for entry in entries if entry.strip().lower() not in existing]
    if not to_add:
        return text

    insertion = [f"{entry} \\" for entry in to_add]
    lines[end:end] = insertion
    return newline.join(lines) + newline


def gate_should_fail_run(gate_report: Dict[str, Any]) -> bool:
    if not gate_report:
        return False
    required = bool(gate_report.get("required", False))
    return required and not bool(gate_report.get("passes", False))


def _write_gate_report(output_dir: Path, report: Dict[str, Any]) -> None:
    out_path = Path(output_dir) / "compile_gate_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _resolve_gmake_binary() -> str:
    env_path = os.getenv("CCS_GMAKE")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate)

    from_path = shutil.which("gmake")
    if from_path:
        return from_path

    fallback = Path(r"C:\ti\ccs1040\ccs\utils\bin\gmake.exe")
    if fallback.exists():
        return str(fallback)
    return "gmake"


def _run_ccs_make(
    layout,
    gmake_binary: str,
    *,
    clean_first: bool = True,
    force_rebuild: bool = True,
) -> tuple[int, str]:
    working_dir = layout.configuration_path if layout.configuration_path.exists() else layout.project_path
    log_chunks: list[str] = []

    def _run_one(command: list[str], label: str) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                command,
                cwd=working_dir,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return (
                127,
                f"[error] gmake binary not found: {gmake_binary}\n"
                "Set CCS_GMAKE or install CCS gmake.",
            )

        chunk = f"[info] {label}: {' '.join(command)}\n"
        if proc.stdout:
            chunk += proc.stdout
        if proc.stderr:
            if chunk and not chunk.endswith("\n"):
                chunk += "\n"
            chunk += proc.stderr
        return proc.returncode, chunk

    if clean_first:
        clean_cmd = [gmake_binary, "-k", "clean", "-O"]
        clean_rc, clean_log = _run_one(clean_cmd, "ccs_clean")
        log_chunks.append(clean_log)
        # Clean failures are logged but do not hard-fail the gate.
        if clean_rc != 0:
            log_chunks.append(
                f"[warn] clean step returned non-zero ({clean_rc}); continuing with build.\n"
            )

    build_cmd = [gmake_binary, "-k", "-j", "16"]
    if force_rebuild:
        build_cmd.append("-B")
    build_cmd.extend(["all", "-O"])
    build_rc, build_log = _run_one(build_cmd, "ccs_build")
    log_chunks.append(build_log)
    return build_rc, "".join(log_chunks)
