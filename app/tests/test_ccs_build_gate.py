from pathlib import Path

from modules.build.ccs_build_gate import (
    _ensure_ordered_objs_entries,
    _ensure_var_block_entries,
    _is_benign_missing_bsp_validate_target,
    _prune_stale_bsp_validate_make_refs,
    _reconcile_generated_make_refs,
    gate_should_fail_run,
    run_ccs_build_gate,
)


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


def test_benign_bsp_validate_make_error_is_detected(tmp_path: Path):
    log_text = "\n".join(
        [
            "gmake: *** No rule to make target `bsp_validate.obj', needed by 'all'.",
            "gmake: Target 'all' not remade because of errors.",
            "../main.c, line 10: warning #112-D: statement is unreachable",
        ]
    )
    summary = {"errors": 0, "warnings": 1}
    assert _is_benign_missing_bsp_validate_target(log_text, summary, tmp_path) is True


def test_benign_bsp_validate_make_error_not_ignored_when_file_exists(tmp_path: Path):
    (tmp_path / "bsp_validate.c").write_text("/* present */\n", encoding="utf-8")
    log_text = "gmake: *** No rule to make target 'bsp_validate.obj', needed by 'all'."
    summary = {"errors": 0, "warnings": 0}
    assert _is_benign_missing_bsp_validate_target(log_text, summary, tmp_path) is False


def test_benign_bsp_validate_make_error_not_ignored_when_other_fatal_gmake_exists(tmp_path: Path):
    log_text = "\n".join(
        [
            "gmake: *** No rule to make target 'bsp_validate.obj', needed by 'all'.",
            "gmake: *** [lin_driver.obj] Error 1",
            "gmake: Target 'all' not remade because of errors.",
        ]
    )
    summary = {"errors": 0, "warnings": 0}
    assert _is_benign_missing_bsp_validate_target(log_text, summary, tmp_path) is False


def test_prune_stale_bsp_validate_make_refs(tmp_path: Path):
    cfg = tmp_path / "Debug"
    cfg.mkdir(parents=True, exist_ok=True)
    subdir_vars = cfg / "subdir_vars.mk"
    subdir_vars.write_text(
        "\n".join(
            [
                "C_SRCS += \\",
                "../entry.c \\",
                "../bsp_validate.c \\",
                "../main.c",
                "",
                "OBJS += \\",
                "./entry.obj \\",
                "./bsp_validate.obj \\",
                "./main.obj",
                "",
            ]
        ),
        encoding="utf-8",
    )
    touched = _prune_stale_bsp_validate_make_refs(cfg, tmp_path)
    assert touched >= 1
    updated = subdir_vars.read_text(encoding="utf-8")
    assert "bsp_validate.c" not in updated
    assert "bsp_validate.obj" not in updated


def test_ensure_var_block_entries_inserts_missing_items_once():
    text = "\n".join(
        [
            "C_SRCS += \\",
            "../entry.c \\",
            "",
        ]
    )
    updated = _ensure_var_block_entries(text, "C_SRCS", ["../entry.c", "../app_intent.c"])
    assert "../app_intent.c" in updated
    updated2 = _ensure_var_block_entries(updated, "C_SRCS", ["../app_intent.c"])
    assert updated2.count("../app_intent.c") == 1


def test_ensure_var_block_entries_preserves_crlf_and_terminates_last_entry():
    text = "\r\n".join(
        [
            "C_SRCS += \\",
            "../entry.c",
            "",
        ]
    ) + "\r\n"
    updated = _ensure_var_block_entries(text, "C_SRCS", ["../app_intent.c"])
    assert "\r\n" in updated
    assert "../entry.c \\\r\n../app_intent.c\r\n\r\n" in updated


def test_ensure_ordered_objs_entries_inserts_before_gen_cmds():
    text = "\n".join(
        [
            "ORDERED_OBJS += \\",
            "\"./entry.obj\" \\",
            "$(GEN_CMDS__FLAG) \\",
            "-lrtsv7R4_T_le_v3D16_eabi.lib \\",
            "",
        ]
    )
    updated = _ensure_ordered_objs_entries(text, ['"./app_intent.obj"'])
    assert '"./app_intent.obj" \\' in updated
    assert updated.index('"./app_intent.obj" \\') < updated.index("$(GEN_CMDS__FLAG) \\")


def test_reconcile_generated_make_refs_adds_app_intent_entries(tmp_path: Path):
    out_dir = tmp_path / "out"
    (out_dir / "source").mkdir(parents=True, exist_ok=True)
    (out_dir / "source" / "entry.c").write_text("int x;\n", encoding="utf-8")
    (out_dir / "source" / "app_intent.c").write_text("int y;\n", encoding="utf-8")

    cfg = tmp_path / "Debug"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "subdir_vars.mk").write_text(
        "\n".join(
            [
                "C_SRCS += \\",
                "../entry.c \\",
                "",
                "C_DEPS += \\",
                "./entry.d \\",
                "",
                "OBJS += \\",
                "./entry.obj \\",
                "",
                "C_SRCS__QUOTED += \\",
                "\"../entry.c\" \\",
                "",
                "C_DEPS__QUOTED += \\",
                "\"entry.d\" \\",
                "",
                "OBJS__QUOTED += \\",
                "\"entry.obj\" \\",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (cfg / "makefile").write_text(
        "\n".join(
            [
                "ORDERED_OBJS += \\",
                "\"./entry.obj\" \\",
                "$(GEN_CMDS__FLAG) \\",
                "-lrtsv7R4_T_le_v3D16_eabi.lib \\",
                "",
            ]
        ),
        encoding="utf-8",
    )

    touched = _reconcile_generated_make_refs(cfg, out_dir)
    assert touched >= 1
    subdir_vars = (cfg / "subdir_vars.mk").read_text(encoding="utf-8")
    makefile = (cfg / "makefile").read_text(encoding="utf-8")
    assert "../app_intent.c" in subdir_vars
    assert "./app_intent.obj" in subdir_vars
    assert '"./app_intent.obj" \\' in makefile
