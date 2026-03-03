from pathlib import Path

from modules.utils.unified_progress import PassStatus, UnifiedProgressManager


def _status_for(manager: UnifiedProgressManager, short_name: str) -> PassStatus:
    for p in manager.passes:
        if p.short_name == short_name:
            return p.status
    raise AssertionError(f"Pass not found: {short_name}")


def test_optional_pass_can_be_started_and_completed(tmp_path: Path):
    manager = UnifiedProgressManager(
        passes=["Discovery", "Validation"],
        output_dir=tmp_path,
        enable_fancy=False,
        enable_color=False,
    )
    try:
        tracker = manager.start_optional_pass("Post-Gen Intent")
        assert tracker is not None
        tracker.set_total_tasks(1)
        tracker.increment_success()
        manager.complete_pass("Post-Gen Intent", success=True)
        assert _status_for(manager, "Post-Gen Intent") == PassStatus.COMPLETE
    finally:
        manager.cleanup()


def test_skip_pass_marks_status_skipped(tmp_path: Path):
    manager = UnifiedProgressManager(
        passes=["Discovery", "Validation"],
        output_dir=tmp_path,
        enable_fancy=False,
        enable_color=False,
    )
    try:
        manager.skip_pass("Docs", reason="Not requested")
        assert _status_for(manager, "Docs") == PassStatus.SKIPPED
    finally:
        manager.cleanup()

