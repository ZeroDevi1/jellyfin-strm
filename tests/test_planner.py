from pathlib import Path

from jellyfin_strm.planner import build_sync_plan


def test_plan_creates_strm_for_shadow_dirs_without_strm(tmp_path: Path) -> None:
    """测试为 shadow 中没有 strm 的目录创建 strm 文件"""
    source = tmp_path / "source"
    shadow = tmp_path / "shadow"
    source.mkdir()
    shadow.mkdir()

    # 创建 shadow 目录结构
    (shadow / "演员A" / "番号B").mkdir(parents=True)
    (shadow / "演员C" / "番号D").mkdir(parents=True)

    # 番号D 目录已有 strm 文件，应该跳过
    (shadow / "演员C" / "番号D" / "existing.strm").write_text(
        "/path/to/video", encoding="utf-8"
    )

    # 创建对应的 source 目录和视频
    (source / "演员A" / "番号B").mkdir(parents=True)
    (source / "演员A" / "番号B" / "video1.mp4").write_text("video1", encoding="utf-8")

    (source / "演员C" / "番号D").mkdir(parents=True)
    (source / "演员C" / "番号D" / "video2.mp4").write_text("video2", encoding="utf-8")

    plan = build_sync_plan(
        source_root=source, shadow_root=shadow, strm_prefix="/mnt/115open/Secret"
    )

    # 只为没有 strm 的番号B 创建 strm
    assert len(plan.write_strms) == 1
    assert plan.write_strms[0].relative_path.as_posix() == "演员A/番号B/video1.strm"
    # 不再复制 sidecar 文件
    assert plan.copy_files == []
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


def test_plan_skips_existing_strm_in_subdirs(tmp_path: Path) -> None:
    """测试跳过 shadow 子目录中已有 strm 的目录"""
    source = tmp_path / "source"
    shadow = tmp_path / "shadow"
    source.mkdir()
    shadow.mkdir()

    # 创建 shadow 目录结构，番号A 已有 strm
    (shadow / "演员A" / "番号A").mkdir(parents=True)
    (shadow / "演员A" / "番号A" / "movie.strm").write_text("/path", encoding="utf-8")

    # 番号B 没有 strm
    (shadow / "演员A" / "番号B").mkdir(parents=True)

    # 对应的 source 目录都有视频
    (source / "演员A" / "番号A").mkdir(parents=True)
    (source / "演员A" / "番号A" / "video.mp4").write_text("video", encoding="utf-8")

    (source / "演员A" / "番号B").mkdir(parents=True)
    (source / "演员A" / "番号B" / "video2.mp4").write_text("video2", encoding="utf-8")

    plan = build_sync_plan(
        source_root=source,
        shadow_root=shadow,
        strm_prefix="/mnt/115open/Secret",
    )

    # 只为番号B 创建 strm
    assert len(plan.write_strms) == 1
    assert "番号B" in plan.write_strms[0].relative_path.as_posix()
    assert plan.source_healthy is True
