from pathlib import Path

from modules.utils.facts_parser import compare_values, normalize_value
from modules.validation.validation_engine import _validate_code_against_yaml


def test_compare_values_accepts_casted_pointer_literal():
    assert compare_values("((volatile LIN_REG_MAP_t *)0xFFF7E400U)", "0xFFF7E400")


def test_compare_values_accepts_parenthesized_arithmetic_literal():
    assert compare_values("((uint32_t)(0xFFF7E400U + 0x0U))", "0xFFF7E400")


def test_compare_values_rejects_nonconstant_identifier_expression():
    assert not compare_values("(foo + 0x10U)", "0x10")


def test_normalize_value_reports_canonical_hex_for_casted_pointer_literal():
    assert normalize_value("((volatile LIN_REG_MAP_t *)0xFFF7E400U)") == "0xfff7e400"


def test_validate_code_against_yaml_accepts_casted_base_define(tmp_path: Path):
    lin_c = tmp_path / "lin_driver.c"
    lin_c.write_text(
        "#define LIN_BASE ((volatile LIN_REG_MAP_t *)0xFFF7E400U)\n",
        encoding="utf-8",
    )

    soc_data = {
        "peripherals": [
            {"name": "LIN", "regs_ref": "LIN"},
        ]
    }
    regs_data = {
        "peripherals": {
            "LIN": {
                "base_address": "0xFFF7E400",
                "registers": {},
            }
        }
    }

    result = _validate_code_against_yaml(
        written_files=[lin_c],
        soc_data=soc_data,
        regs_data=regs_data,
        module_name="LIN",
    )

    assert result.is_valid is True
    assert not result.errors
