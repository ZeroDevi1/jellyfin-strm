from pathlib import Path

from jellyfin_strm.config import load_config
from jellyfin_strm.watch import (
    SnapshotStore,
    build_source_snapshot,
    run_watch_iteration,
    run_watch_loop,
)


def test_snapshot_store_detects_changes(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    state_file = tmp_path / "state" / "watch-snapshot.json"
    source_root.mkdir(parents=True)

    # 在子目录中创建视频文件
    (source_root / "演员A" / "番号B").mkdir(parents=True)
    movie_file = source_root / "演员A" / "番号B" / "movie.mp4"
    movie_file.write_text("v1", encoding="utf-8")

    store = SnapshotStore(state_file)
    snapshot = build_source_snapshot(source_root)

    assert snapshot.source_healthy is True
    assert snapshot.entry_count == 1
    assert store.has_changed(snapshot) is True

    store.save(snapshot)
    assert store.has_changed(build_source_snapshot(source_root)) is False

    # 修改文件内容并强制更新修改时间
    import time

    time.sleep(0.1)  # 确保 mtime 改变
    movie_file.write_text("v2", encoding="utf-8")
    assert store.has_changed(build_source_snapshot(source_root)) is True


def test_watch_iteration_writes_snapshot_and_syncs(
    sample_config_text: str, tmp_path: Path
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    config = load_config(config_file)
    config.source_root.mkdir(parents=True)
    config.shadow_root.mkdir(parents=True)

    # 创建 shadow 目录结构（番号B 没有 strm）
    (config.shadow_root / "演员A" / "番号B").mkdir(parents=True)

    # 在 source 对应目录创建视频
    (config.source_root / "演员A" / "番号B").mkdir(parents=True)
    (config.source_root / "演员A" / "番号B" / "demo.mp4").write_text(
        "video", encoding="utf-8"
    )

    store = SnapshotStore(config.state_dir / "watch-snapshot.json")

    changed = run_watch_iteration(config, snapshot_store=store)

    assert changed is True
    # STRM 文件应该生成在 shadow 对应目录中
    assert (config.shadow_root / "演员A" / "番号B" / "demo.strm").exists()
    assert (config.state_dir / "watch-snapshot.json").exists()


def test_watch_iteration_skips_when_shadow_has_strm(
    sample_config_text: str, tmp_path: Path
) -> None:
    """测试当 shadow 目录已有 strm 时跳过"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    config = load_config(config_file)
    config.source_root.mkdir(parents=True)
    config.shadow_root.mkdir(parents=True)

    # 创建 shadow 目录结构，番号B 已有 strm
    (config.shadow_root / "演员A" / "番号B").mkdir(parents=True)
    (config.shadow_root / "演员A" / "番号B" / "existing.strm").write_text(
        "/path", encoding="utf-8"
    )

    # source 有视频
    (config.source_root / "演员A" / "番号B").mkdir(parents=True)
    (config.source_root / "演员A" / "番号B" / "demo.mp4").write_text(
        "video", encoding="utf-8"
    )

    store = SnapshotStore(config.state_dir / "watch-snapshot.json")

    changed = run_watch_iteration(config, snapshot_store=store)

    # 由于已有 strm，不应该创建新的
    assert changed is False


def test_watch_iteration_skips_unhealthy_source_without_overwriting_snapshot(
    sample_config_text: str, tmp_path: Path
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    config = load_config(config_file)
    config.source_root.mkdir(parents=True)
    config.shadow_root.mkdir(parents=True)
    (config.source_root / "demo.mp4").write_text("video", encoding="utf-8")

    store = SnapshotStore(config.state_dir / "watch-snapshot.json")
    assert run_watch_iteration(config, snapshot_store=store) is True
    before = (config.state_dir / "watch-snapshot.json").read_text(encoding="utf-8")

    for path in sorted(config.source_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    config.source_root.rmdir()

    assert run_watch_iteration(config, snapshot_store=store) is False
    after = (config.state_dir / "watch-snapshot.json").read_text(encoding="utf-8")
    # 不健康时不应该覆盖快照
    assert after == before


def test_watch_loop_logs_io_error_and_keeps_running(
    monkeypatch,
    sample_config_text: str,
    tmp_path: Path,
    capsys,
) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")
    config = load_config(config_file)

    def fake_iteration(*_args, **_kwargs) -> bool:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr("jellyfin_strm.watch.run_watch_iteration", fake_iteration)
    monkeypatch.setattr("jellyfin_strm.watch.time.sleep", lambda _seconds: None)

    assert run_watch_loop(config, interval_seconds=0, max_loops=1) == 0
    captured = capsys.readouterr()
    assert "Input/output error" in captured.err
