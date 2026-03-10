import builtins
import asyncio
import json
import sys
from argparse import Namespace
from pathlib import Path

from main import (
    _discover_recent_output_dirs,
    _build_build_evidence_from_gate_result,
    _colorize_prefixed_log_message,
    _derive_validation_status,
    _load_profile_data,
    _prompt_for_ccs_workspace_project,
    _run_api_preflight_check,
    _resolve_action_from_args,
    _resolve_output_dir_from_index,
    _should_open_auto_menu,
    _run_reflash_action,
    _sync_validation_report_build_evidence,
    _should_use_profile_module_selection,
)


def _write_profile(path: Path, target_board: str = "LAUNCHXL2-TMS57012-RM46") -> Path:
    path.write_text(f"target_board: {target_board}\n", encoding="utf-8")
    return path


def test_prompt_for_ccs_workspace_project_non_interactive_returns_seed_values(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    ws, proj = _prompt_for_ccs_workspace_project("C:/ws", "Proj", context_label="test")
    assert ws == "C:/ws"
    assert proj == "Proj"


def test_prompt_for_ccs_workspace_project_interactive_collects_values(monkeypatch, tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "MyProject").mkdir(parents=True, exist_ok=True)

    answers = iter([str(workspace), "MyProject"])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))

    ws, proj = _prompt_for_ccs_workspace_project("", "", context_label="test")
    assert ws == str(workspace)
    assert proj == "MyProject"


def test_prompt_for_ccs_workspace_project_allows_skip(monkeypatch):
    answers = iter([""])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))

    ws, proj = _prompt_for_ccs_workspace_project("", "", context_label="test")
    assert ws == ""
    assert proj == ""


def test_load_profile_data_skips_all_loading_when_no_profile_flag_set(tmp_path: Path):
    explicit = _write_profile(tmp_path / "explicit.yaml", target_board="EXPLICIT")
    _write_profile(tmp_path / "generation_profile.yaml", target_board="DEFAULT")

    data, loaded_path = _load_profile_data(
        args_profile=str(explicit),
        no_profile=True,
        yaml_root=tmp_path,
    )
    assert data is None
    assert loaded_path is None


def test_load_profile_data_prefers_explicit_profile_path(tmp_path: Path):
    explicit = _write_profile(tmp_path / "explicit.yaml", target_board="EXPLICIT")
    _write_profile(tmp_path / "generation_profile.yaml", target_board="DEFAULT")

    data, loaded_path = _load_profile_data(
        args_profile=str(explicit),
        no_profile=False,
        yaml_root=tmp_path,
    )
    assert loaded_path == explicit
    assert data["target_board"] == "EXPLICIT"


def test_load_profile_data_uses_default_generation_profile_yaml(tmp_path: Path):
    default_profile = _write_profile(tmp_path / "generation_profile.yaml", target_board="DEFAULT")

    data, loaded_path = _load_profile_data(
        args_profile=None,
        no_profile=False,
        yaml_root=tmp_path,
    )
    assert loaded_path == default_profile
    assert data["target_board"] == "DEFAULT"


def test_load_profile_data_returns_none_when_no_profile_available(tmp_path: Path):
    data, loaded_path = _load_profile_data(
        args_profile=None,
        no_profile=False,
        yaml_root=tmp_path,
    )
    assert data is None
    assert loaded_path is None


def test_should_use_profile_module_selection_requires_loaded_profile_path(tmp_path: Path):
    loaded_profile = tmp_path / "generation_profile.yaml"
    assert (
        _should_use_profile_module_selection(
            loaded_profile_path=loaded_profile,
            no_profile=False,
            profile_enabled_modules=["SCI", "GIO"],
        )
        is True
    )
    assert (
        _should_use_profile_module_selection(
            loaded_profile_path=None,
            no_profile=False,
            profile_enabled_modules=["SCI", "GIO"],
        )
        is False
    )
    assert (
        _should_use_profile_module_selection(
            loaded_profile_path=loaded_profile,
            no_profile=True,
            profile_enabled_modules=["SCI", "GIO"],
        )
        is False
    )


def test_build_build_evidence_from_gate_result_maps_expected_fields():
    gate_result = {
        "required": True,
        "status": "pass",
        "passes": True,
        "rounds": [{"attempt": 0}],
        "error_summary": {"errors": 0, "warnings": 2},
        "configuration": "Debug",
        "external_workspace_path": "C:/ws",
        "project_name": "Proj",
        "llm_rewrite_attempted": False,
        "llm_rewrite_applied": False,
        "llm_rewrite_target_files": [],
        "llm_rewrite_tokens": {"input_tokens": 0, "output_tokens": 0},
        "llm_rewrite_failure_reason": "",
    }
    evidence = _build_build_evidence_from_gate_result(gate_result)
    assert evidence["status"] == "pass"
    assert evidence["passes"] is True
    assert evidence["rounds"] == 1
    assert evidence["project_name"] == "Proj"


def test_sync_validation_report_build_evidence_rewrites_json_and_markdown(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_json = out_dir / "validation_report.json"
    report_md = out_dir / "validation_report.md"
    report_json.write_text(
        json.dumps(
            {
                "timestamp": "20260302_000000",
                "bsp_output_dir": "output_test",
                "validation_summary": {
                    "total_modules": 1,
                    "modules_valid": 1,
                    "modules_invalid": 0,
                    "critical_errors": 0,
                    "warnings": 0,
                    "success_rate": 100.0,
                },
                "peripheral_validations": {
                    "SCI": {
                        "module_name": "SCI",
                        "facts_mirror_valid": True,
                        "constants_validated": 0,
                        "mismatches": 0,
                        "tests_generated": False,
                        "critical_errors": [],
                        "warnings": [],
                    }
                },
                "compile_contract": {"passes": True, "checks": 0, "errors": [], "warnings": []},
                "startup_contract": {"passes": True, "errors": [], "warnings": []},
                "runtime_invariants": {"build_gate_passes": False, "parity_guard_passes": True},
                "build_evidence": {"status": "failed_after_max_rounds", "passes": False},
                "critical_sequence_mismatches": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report_md.write_text("# stale\n", encoding="utf-8")

    gate_result = {
        "required": True,
        "status": "pass",
        "passes": True,
        "rounds": [{"attempt": 0}],
        "error_summary": {"errors": 0, "warnings": 1},
        "configuration": "Debug",
        "external_workspace_path": "C:/ws",
        "project_name": "Proj",
        "llm_rewrite_attempted": False,
        "llm_rewrite_applied": False,
        "llm_rewrite_target_files": [],
        "llm_rewrite_tokens": {"input_tokens": 0, "output_tokens": 0},
        "llm_rewrite_failure_reason": "",
    }
    synced = _sync_validation_report_build_evidence(
        out_dir,
        gate_result,
        strict_validation_enabled=False,
    )
    assert synced is True

    updated_json = json.loads(report_json.read_text(encoding="utf-8"))
    assert updated_json["build_evidence"]["status"] == "pass"
    assert updated_json["build_evidence"]["passes"] is True
    assert updated_json["runtime_invariants"]["build_gate_passes"] is True

    updated_md = report_md.read_text(encoding="utf-8")
    assert "## Build Evidence" in updated_md
    assert "- **status:** pass" in updated_md


def test_should_open_auto_menu_only_for_bare_interactive_launch():
    assert _should_open_auto_menu([], stdin_tty=True, stdout_tty=True, explicit_menu=False) is True
    assert _should_open_auto_menu(["--no-profile"], stdin_tty=True, stdout_tty=True, explicit_menu=False) is False
    assert _should_open_auto_menu([], stdin_tty=False, stdout_tty=True, explicit_menu=False) is False
    assert _should_open_auto_menu(["--anything"], stdin_tty=False, stdout_tty=False, explicit_menu=True) is True


def test_resolve_action_from_args_prefers_explicit_action():
    args = Namespace(action="docs_only", validate_only=True, post_gen_generate=True, post_gen_prompt=True)
    assert _resolve_action_from_args(args) == "docs_only"


def test_resolve_action_from_args_maps_validate_modes():
    args = Namespace(action=None, validate_only=True, post_gen_generate=True, post_gen_prompt=True)
    assert _resolve_action_from_args(args) == "postgen_generate"
    args = Namespace(action=None, validate_only=True, post_gen_generate=False, post_gen_prompt=True)
    assert _resolve_action_from_args(args) == "postgen_prompt"
    args = Namespace(action=None, validate_only=True, post_gen_generate=False, post_gen_prompt=False)
    assert _resolve_action_from_args(args) == "validate"
    args = Namespace(action=None, validate_only=False, post_gen_generate=False, post_gen_prompt=False)
    assert _resolve_action_from_args(args) == "generate"


def test_discover_recent_output_dirs_scans_root_and_app(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    out_old = tmp_path / "output_20260301_010101"
    out_new = tmp_path / "app" / "output_20260302_020202"
    out_old.mkdir(parents=True, exist_ok=True)
    out_new.mkdir(parents=True, exist_ok=True)

    outputs = _discover_recent_output_dirs(limit=10)
    assert len(outputs) == 2
    assert outputs[0].name == "output_20260302_020202"
    assert outputs[1].name == "output_20260301_010101"


def test_resolve_output_dir_from_index_uses_recent_order(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "output_20260301_000000").mkdir(parents=True, exist_ok=True)
    (tmp_path / "output_20260303_000000").mkdir(parents=True, exist_ok=True)

    first = _resolve_output_dir_from_index(1, limit=10)
    second = _resolve_output_dir_from_index(2, limit=10)
    missing = _resolve_output_dir_from_index(3, limit=10)

    assert first is not None and first.name == "output_20260303_000000"
    assert second is not None and second.name == "output_20260301_000000"
    assert missing is None


def test_run_reflash_action_requires_flash_enabled(tmp_path: Path):
    out_dir = tmp_path / "output_20260302_000000"
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_root = tmp_path / "yaml_in"
    yaml_root.mkdir(parents=True, exist_ok=True)
    profile_path = yaml_root / "generation_profile.yaml"
    profile_path.write_text(
        """
flash:
  enabled: false
  command_template: "flash_tool --out {output_dir}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    args = Namespace(
        output_dir=str(out_dir),
        output_index=None,
        yamlpath=str(yaml_root),
        no_profile=False,
        profile=str(profile_path),
        ccs_workspace=None,
        ccs_project=None,
        ccs_config=None,
    )
    rc = asyncio.run(_run_reflash_action(args))
    assert rc == 2


def test_run_reflash_action_rejects_unknown_template_placeholder(tmp_path: Path):
    out_dir = tmp_path / "output_20260302_000000"
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_root = tmp_path / "yaml_in"
    yaml_root.mkdir(parents=True, exist_ok=True)
    profile_path = yaml_root / "generation_profile.yaml"
    profile_path.write_text(
        """
flash:
  enabled: true
  command_template: "flash_tool --bad {unknown_placeholder}"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    args = Namespace(
        output_dir=str(out_dir),
        output_index=None,
        yamlpath=str(yaml_root),
        no_profile=False,
        profile=str(profile_path),
        ccs_workspace=None,
        ccs_project=None,
        ccs_config=None,
    )
    rc = asyncio.run(_run_reflash_action(args))
    assert rc == 2


def test_derive_validation_status_fail_when_build_evidence_fails():
    status = _derive_validation_status(
        {
            "build_evidence": {"passes": False},
            "validation_summary": {"critical_errors": 0, "warnings": 0},
        }
    )
    assert status == "FAIL"


def test_derive_validation_status_warn_on_non_blocking_critical_errors():
    status = _derive_validation_status(
        {
            "build_evidence": {"passes": True},
            "compile_contract": {"passes": True},
            "startup_contract": {"passes": True},
            "runtime_invariants": {
                "startup_contract_gate_mode": "warn",
                "parity_guard_mode": "critical_only",
                "parity_guard_passes": False,
            },
            "validation_summary": {"critical_errors": 1, "warnings": 10},
        }
    )
    assert status == "WARN"


def test_derive_validation_status_pass_when_clean():
    status = _derive_validation_status(
        {
            "build_evidence": {"passes": True},
            "compile_contract": {"passes": True},
            "startup_contract": {"passes": True},
            "runtime_invariants": {
                "startup_contract_gate_mode": "warn",
                "parity_guard_mode": "critical_only",
                "parity_guard_passes": True,
            },
            "validation_summary": {"critical_errors": 0, "warnings": 0},
        }
    )
    assert status == "PASS"


def test_run_api_preflight_check_passes_with_nonempty_response(monkeypatch):
    import main

    monkeypatch.setattr(main, "invoke_model_sync", lambda model, max_tokens, messages: {"ok": True})
    monkeypatch.setattr(main, "extract_text_from_bedrock_response", lambda response: "OK")
    rc = _run_api_preflight_check(model_name="sonnet4.5", max_tokens=32, mock_mode=False)
    assert rc == 0


def test_run_api_preflight_check_fails_on_empty_response(monkeypatch):
    import main

    monkeypatch.setattr(main, "invoke_model_sync", lambda model, max_tokens, messages: {"ok": True})
    monkeypatch.setattr(main, "extract_text_from_bedrock_response", lambda response: "")
    rc = _run_api_preflight_check(model_name="sonnet4.5", max_tokens=32, mock_mode=False)
    assert rc == 2


def test_colorize_prefixed_log_message_colors_warn_error_ok():
    warn = _colorize_prefixed_log_message("[warn] caution")
    err = _colorize_prefixed_log_message("[error] boom")
    ok = _colorize_prefixed_log_message("[ok] good")
    assert "\033[" in warn and warn.endswith("\033[0m")
    assert "\033[" in err and err.endswith("\033[0m")
    assert "\033[" in ok and ok.endswith("\033[0m")


def test_colorize_prefixed_log_message_leaves_unprefixed_text_unchanged():
    msg = "plain line"
    assert _colorize_prefixed_log_message(msg) == msg
