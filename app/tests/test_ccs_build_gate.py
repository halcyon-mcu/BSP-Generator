from pathlib import Path

from modules.build.ccs_build_gate import gate_should_fail_run, run_ccs_build_gate


def test_build_gate_strict_missing_workspace_fails_fast(tmp_path: Path):
    profile = {
        "build_gate": {
            "enabled": True,
            "mode": "strict",
            "external_workspace_path": "",
            "project_name": "",
            "configuration": "Debug",
            "max_fix_rounds": 2,
            "allow_targeted_llm_rewrite": True,
            "fail_on_compile_error": True,
        }
    }

    result = run_ccs_build_gate(tmp_path, profile)
    assert result["passes"] is False
    assert result["status"] == "invalid_config"
    assert gate_should_fail_run(result) is True
    assert "llm_rewrite_attempted" in result
    assert "llm_rewrite_applied" in result
    assert "startup_contract_status" in result
    assert "parity_guard_status" in result
    assert "blocking_reasons" in result
    assert (tmp_path / "compile_gate_report.json").exists()


def test_build_gate_off_is_skipped(tmp_path: Path):
    profile = {"build_gate": {"enabled": True, "mode": "off"}}
    result = run_ccs_build_gate(tmp_path, profile)
    assert result["status"] == "disabled"
    assert result["passes"] is False
