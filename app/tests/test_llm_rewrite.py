from pathlib import Path

from modules.build.llm_rewrite import _select_target_files, apply_llm_rewrite_response
from modules.build.ti_diagnostics import TiDiagnostic


def _diag(file_path: str, severity: str, message: str, line: int = 1) -> TiDiagnostic:
    return TiDiagnostic(
        file_path=file_path,
        line=line,
        severity=severity,
        code="X",
        message=message,
        raw=f"{file_path}:{line}:{severity}:{message}",
    )


def test_apply_hybrid_prefers_diff_when_valid(tmp_path: Path):
    target = tmp_path / "main.c"
    target.write_text("int x = 1;\nreturn 0;\n", encoding="utf-8")
    diff = "\n".join(
        [
            "--- a/main.c",
            "+++ b/main.c",
            "@@ -1,2 +1,2 @@",
            "-int x = 1;",
            "+int x = 2;",
            " return 0;",
            "",
        ]
    )

    result = apply_llm_rewrite_response(
        output_dir=tmp_path,
        response_text=diff,
        allowed_files=[target],
        apply_policy="hybrid",
        api_contract_manifest=None,
    )

    assert result["diff_attempted"] is True
    assert result["diff_applied"] is True
    assert str(target) in result["touched_files"]
    assert "int x = 2;" in target.read_text(encoding="utf-8")


def test_apply_hybrid_falls_back_to_full_file_blocks(tmp_path: Path):
    target = tmp_path / "main.c"
    target.write_text("int x = 1;\nreturn 0;\n", encoding="utf-8")
    payload = "\n".join(
        [
            "--- a/main.c",
            "+++ b/main.c",
            "@@ -1,1 +1,1 @@",
            "-does_not_match",
            "+still_bad",
            "===== FILE: main.c =====",
            "int x = 9;",
            "return 0;",
            "",
        ]
    )

    result = apply_llm_rewrite_response(
        output_dir=tmp_path,
        response_text=payload,
        allowed_files=[target],
        apply_policy="hybrid",
        api_contract_manifest=None,
    )

    assert result["diff_attempted"] is True
    assert result["full_file_attempted"] is True
    assert result["full_file_applied"] is True
    assert str(target) in result["touched_files"]
    assert "int x = 9;" in target.read_text(encoding="utf-8")


def test_apply_rejects_out_of_scope_file_blocks(tmp_path: Path):
    allowed = tmp_path / "main.c"
    forbidden = tmp_path / "other.c"
    allowed.write_text("int x = 1;\n", encoding="utf-8")
    forbidden.write_text("int y = 2;\n", encoding="utf-8")
    payload = "===== FILE: other.c =====\nint y = 7;\n"

    result = apply_llm_rewrite_response(
        output_dir=tmp_path,
        response_text=payload,
        allowed_files=[allowed],
        apply_policy="full_file_only",
        api_contract_manifest=None,
    )

    assert result["touched_files"] == []
    assert forbidden.read_text(encoding="utf-8") == "int y = 2;\n"


def test_target_selection_prefers_high_signal_compile_files(tmp_path: Path):
    f1 = tmp_path / "bsp_validate.c"
    f2 = tmp_path / "lin_driver.c"
    f3 = tmp_path / "note.txt"
    f1.write_text("int a;\n", encoding="utf-8")
    f2.write_text("int b;\n", encoding="utf-8")
    f3.write_text("ignore\n", encoding="utf-8")

    diagnostics = [
        _diag("../bsp_validate.c", "error", "identifier undefined"),
        _diag("../bsp_validate.c", "error", "expected ';'"),
        _diag("../lin_driver.c", "warning", "unused variable"),
        _diag("", "error", "unresolved symbols remain"),
    ]

    targets = _select_target_files(tmp_path, diagnostics, top_k=2)
    # bsp_validate.c is intentionally excluded from LLM rewrite target selection.
    assert len(targets) == 1
    assert targets[0].name == "lin_driver.c"
