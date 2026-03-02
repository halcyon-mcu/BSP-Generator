from pathlib import Path

import pytest

from modules.yaml.yaml_utils import load_generation_profile


def _write_yaml(path: Path, text: str) -> Path:
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path


def test_load_generation_profile_accepts_build_gate_and_bsp_validation(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
target_board: LAUNCHXL2-TMS57012-RM46
build_gate:
  enabled: true
  mode: strict
  external_workspace_path: C:/workspace
  project_name: Blinky2
  configuration: Debug
  max_fix_rounds: 3
  allow_targeted_llm_rewrite: true
  fail_on_compile_error: true
  llm_rewrite:
    enabled: true
    scope: top_files
    top_k_files: 2
    apply_policy: hybrid
    model: inherit
    max_tokens: 6000
    max_attempts: 1
    include_contract_context: true
bsp_validation:
  enabled: true
  baud: 19200
  frame:
    data_bits: 8
    stop_bits: 2
    parity: even
  banners:
    sci: SCI ACTIVE
    lin: LIN ACTIVE
  timing:
    heartbeat_ticks: 500
    tx_period_ticks: 150
    busy_delay: 25
        """,
    )

    data = load_generation_profile(profile_path)
    assert data["build_gate"]["project_name"] == "Blinky2"
    assert data["build_gate"]["llm_rewrite"]["top_k_files"] == 2
    assert data["bsp_validation"]["baud"] == 19200
    assert data["bsp_validation"]["frame"]["stop_bits"] == 2


def test_load_generation_profile_rejects_invalid_build_gate_mode(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
build_gate:
  enabled: true
  mode: invalid
        """,
    )

    with pytest.raises(ValueError):
        load_generation_profile(profile_path)


def test_load_generation_profile_rejects_invalid_bsp_parity(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
bsp_validation:
  enabled: true
  frame:
    data_bits: 8
    stop_bits: 1
    parity: mark
        """,
    )

    with pytest.raises(ValueError):
        load_generation_profile(profile_path)


def test_load_generation_profile_rejects_invalid_build_gate_llm_model(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
build_gate:
  llm_rewrite:
    model: unknown-model
        """,
    )

    with pytest.raises(ValueError):
        load_generation_profile(profile_path)


def test_load_generation_profile_accepts_primary_serial_path(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
bsp_validation:
  enabled: true
  primary_serial_path: lin_only
  frame:
    data_bits: 8
    stop_bits: 1
    parity: none
        """,
    )

    data = load_generation_profile(profile_path)
    assert data["bsp_validation"]["primary_serial_path"] == "lin_only"


def test_load_generation_profile_rejects_invalid_primary_serial_path(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
bsp_validation:
  enabled: true
  primary_serial_path: invalid
  frame:
    data_bits: 8
    stop_bits: 1
    parity: none
        """,
    )

    with pytest.raises(ValueError):
        load_generation_profile(profile_path)


def test_load_generation_profile_accepts_bringup_mode_startup_gate_and_parity_guard(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
bringup_mode:
  default: direct_init
startup_contract:
  gate_mode: warn
parity_guard:
  mode: critical_only
  baseline_path: app/output_working_with_manual_changes
  critical_registers:
    - GHVSRC
    - CLKCNTL
        """,
    )

    data = load_generation_profile(profile_path)
    assert data["bringup_mode"]["default"] == "direct_init"
    assert data["startup_contract"]["gate_mode"] == "warn"
    assert data["parity_guard"]["mode"] == "critical_only"
    assert data["parity_guard"]["critical_registers"] == ["GHVSRC", "CLKCNTL"]


def test_load_generation_profile_rejects_invalid_startup_gate_mode(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
startup_contract:
  gate_mode: advisory
        """,
    )
    with pytest.raises(ValueError):
        load_generation_profile(profile_path)


def test_load_generation_profile_rejects_invalid_parity_guard_mode(tmp_path: Path):
    profile_path = _write_yaml(
        tmp_path / "generation_profile.yaml",
        """
parity_guard:
  mode: loose
        """,
    )
    with pytest.raises(ValueError):
        load_generation_profile(profile_path)
