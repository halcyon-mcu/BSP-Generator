from pathlib import Path

from modules.build.workspace_sync import sync_generated_to_project


def _touch(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_sync_generated_to_project_removes_stale_generated_files(tmp_path: Path):
    output_dir = tmp_path / "output"
    project_dir = tmp_path / "workspace" / "ProjA"
    project_dir.mkdir(parents=True, exist_ok=True)

    _touch(output_dir / "source" / "sci_driver.c", "/* new sci */\n")
    _touch(output_dir / "include" / "sci_driver.h", "/* new sci h */\n")

    stale_generated = project_dir / "lin_driver.c"
    stale_generated.write_text("/* stale lin */\n", encoding="utf-8")
    stale_user = project_dir / "user_app.c"
    stale_user.write_text("/* keep me */\n", encoding="utf-8")

    result = sync_generated_to_project(output_dir, project_dir, clean_stale_generated_files=True)

    assert (project_dir / "sci_driver.c").exists()
    assert (project_dir / "sci_driver.h").exists()
    assert not stale_generated.exists()
    assert stale_user.exists()
    assert any("lin_driver.c" in p for p in result["removed_files"])


def test_sync_generated_to_project_removes_previously_managed_file_not_in_new_output(tmp_path: Path):
    output_a = tmp_path / "output_a"
    output_b = tmp_path / "output_b"
    project_dir = tmp_path / "workspace" / "ProjB"
    project_dir.mkdir(parents=True, exist_ok=True)

    _touch(output_a / "source" / "lin_driver.c", "/* lin */\n")
    _touch(output_a / "include" / "lin_driver.h", "/* linh */\n")
    sync_generated_to_project(output_a, project_dir, clean_stale_generated_files=False)

    assert (project_dir / "lin_driver.c").exists()

    _touch(output_b / "source" / "sci_driver.c", "/* sci */\n")
    _touch(output_b / "include" / "sci_driver.h", "/* scih */\n")
    result = sync_generated_to_project(output_b, project_dir, clean_stale_generated_files=False)

    assert not (project_dir / "lin_driver.c").exists()
    assert (project_dir / "sci_driver.c").exists()
    assert any("lin_driver.c" in p for p in result["removed_files"])

