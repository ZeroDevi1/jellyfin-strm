from pathlib import Path

from jellyfin_strm.planner import build_sync_plan


def test_plan_creates_strm_and_sidecars(tmp_path: Path) -> None:
    source = tmp_path / "source"
    shadow = tmp_path / "shadow"
    (source / "A/B/extrafanart").mkdir(parents=True)
    shadow.mkdir()
    (source / "A/B/movie.mp4").write_text("video", encoding="utf-8")
    (source / "A/B/movie.nfo").write_text("<movie />", encoding="utf-8")
    (source / "A/B/poster.jpg").write_bytes(b"poster")
    (source / "A/B/extrafanart/shot1.jpg").write_bytes(b"fanart")

    plan = build_sync_plan(
        source_root=source, shadow_root=shadow, strm_prefix="/mnt/115open/Secret"
    )

    assert [item.relative_path.as_posix() for item in plan.write_strms] == [
        "A/B/movie.strm"
    ]
    assert {item.relative_path.as_posix() for item in plan.copy_files} == {
        "A/B/movie.nfo",
        "A/B/poster.jpg",
        "A/B/extrafanart/shot1.jpg",
    }
    assert plan.source_healthy is True


def test_plan_marks_unhealthy_source(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow"
    shadow.mkdir()

    plan = build_sync_plan(
        source_root=tmp_path / "missing",
        shadow_root=shadow,
        strm_prefix="/mnt/115open/Secret",
    )

    assert plan.source_healthy is False
    assert "源目录健康检查失败" in plan.warnings[0]


def test_plan_keeps_existing_shadow_files_when_source_missing_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    shadow = tmp_path / "shadow"
    (source / "Movie").mkdir(parents=True)
    shadow.mkdir()
    (source / "Movie" / "movie.mp4").write_text("video", encoding="utf-8")
    (shadow / "Movie").mkdir(parents=True)
    (shadow / "Movie" / "movie.nfo").write_text("<movie />", encoding="utf-8")

    plan = build_sync_plan(
        source_root=source,
        shadow_root=shadow,
        strm_prefix="/mnt/115open/Secret",
    )

    assert plan.delete_paths == []
