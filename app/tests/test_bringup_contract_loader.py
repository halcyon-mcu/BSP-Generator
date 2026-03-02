from pathlib import Path

import pytest

from modules.yaml.yaml_utils import load_bringup_contract, load_generation_profile


def test_load_bringup_contract_valid(tmp_path: Path):
    contract = tmp_path / "bringup_contract.yaml"
    contract.write_text(
        """
serial:
  primary_path: LIN_SCI_MODE
  primary_tx_only: LIN
  baud_default: 9600
  required_pins:
    - pin: 38
      register: PINMMR7
      bit: 17
      af: 1
lin:
  required_registers:
    SCIPIO0:
      required_value: "0x00000006"
iomm:
  unlock_sequence: ["0x83E70B13", "0x95A4F1E0"]
pll:
  required_sequence: [CSDISSET, CSVSTAT, GHVSRC]
startup:
  required_order: [PCR_Init, PCR_EnableAllPeripherals, flash_waitstates, PLL_Init]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    data = load_bringup_contract(contract)
    assert data["serial"]["primary_path"] == "LIN_SCI_MODE"
    assert data["serial"]["primary_tx_only"] == "LIN"
    assert data["lin"]["required_registers"]["SCIPIO0"]["required_value"] == "0x00000006"


def test_load_generation_profile_with_bringup_options(tmp_path: Path):
    profile = tmp_path / "generation_profile.yaml"
    profile.write_text(
        """
target_board: LAUNCHXL2-TMS57012-RM46
bringup:
  mode: strict
  contract_file: app/yaml_in/bringup_contract.yaml
  fail_on_contract_mismatch: true
  emit_debug_probes: false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    data = load_generation_profile(profile)
    assert data["bringup"]["mode"] == "strict"
    assert data["bringup"]["fail_on_contract_mismatch"] is True


def test_load_generation_profile_rejects_invalid_bringup_mode(tmp_path: Path):
    profile = tmp_path / "generation_profile.yaml"
    profile.write_text(
        """
target_board: LAUNCHXL2-TMS57012-RM46
bringup:
  mode: invalid_mode
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_generation_profile(profile)
