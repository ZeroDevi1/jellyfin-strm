from pathlib import Path

import pytest

from jellyfin_strm.executor import DeleteThresholdError, execute_plan
from jellyfin_strm.planner import PlannedCopy, PlannedWrite, SyncPlan


def test_execute_plan_writes_strm_and_copies_sidecars(tmp_path: Path) -> None:
    source_file = tmp_path / "source/movie.nfo"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("<movie />", encoding="utf-8")
    shadow_root = tmp_path / "shadow"
    shadow_root.mkdir()

    plan = SyncPlan(
        write_strms=[PlannedWrite(Path("movie.strm"), "/mnt/115open/Secret/movie.mp4")],
        copy_files=[PlannedCopy(Path("movie.nfo"), source_file)],
        delete_paths=[],
        warnings=[],
        source_healthy=True,
    )

    summary = execute_plan(plan=plan, shadow_root=shadow_root, dry_run=False)

    assert (shadow_root / "movie.strm").read_text(encoding="utf-8") == "/mnt/115open/Secret/movie.mp4\n"
    assert (shadow_root / "movie.nfo").read_text(encoding="utf-8") == "<movie />"
    assert summary.written_strms == 1
    assert summary.copied_files == 1


def test_execute_plan_blocks_large_delete_batch(tmp_path: Path) -> None:
    shadow_root = tmp_path / "shadow"
    shadow_root.mkdir()
    (shadow_root / "stale-1.strm").write_text("1", encoding="utf-8")
    (shadow_root / "stale-2.strm").write_text("2", encoding="utf-8")
    (shadow_root / "stale-3.strm").write_text("3", encoding="utf-8")

    plan = SyncPlan(
        write_strms=[],
        copy_files=[],
        delete_paths=[Path("stale-1.strm"), Path("stale-2.strm"), Path("stale-3.strm")],
        warnings=[],
        source_healthy=True,
    )

    with pytest.raises(DeleteThresholdError):
        execute_plan(
            plan=plan,
            shadow_root=shadow_root,
            dry_run=False,
            delete_ratio_limit=0.5,
            delete_count_limit=2,
        )


def test_execute_plan_reports_copy_source_on_io_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_file = tmp_path / "source" / "movie.nfo"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("<movie />", encoding="utf-8")
    shadow_root = tmp_path / "shadow"
    shadow_root.mkdir()

    plan = SyncPlan(
        write_strms=[],
        copy_files=[PlannedCopy(Path("movie.nfo"), source_file)],
        delete_paths=[],
        warnings=[],
        source_healthy=True,
    )

    def fake_copy2(_source: Path, _target: Path) -> None:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr("jellyfin_strm.executor.shutil.copy2", fake_copy2)

    with pytest.raises(RuntimeError, match="movie.nfo"):
        execute_plan(plan=plan, shadow_root=shadow_root, dry_run=False)
