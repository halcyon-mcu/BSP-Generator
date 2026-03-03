import builtins
import json
import sys
from pathlib import Path

from main import (
    _build_build_evidence_from_gate_result,
    _load_profile_data,
    _prompt_for_ccs_workspace_project,
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
