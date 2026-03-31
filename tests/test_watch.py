from pathlib import Path

from jellyfin_strm.config import load_config
from jellyfin_strm.watch import (
    SnapshotStore,
    build_shadow_snapshot,
    run_watch_iteration,
    run_watch_loop,
)


def test_snapshot_store_detects_shadow_changes(tmp_path: Path) -> None:
    """测试影子目录快照能检测到目录结构变化"""
    shadow_root = tmp_path / "shadow"
    state_file = tmp_path / "state" / "watch-snapshot.json"
    shadow_root.mkdir(parents=True)

    # 创建初始目录结构
    (shadow_root / "演员A" / "番号B").mkdir(parents=True)

    store = SnapshotStore(state_file)
    snapshot = build_shadow_snapshot(shadow_root)

    assert snapshot.source_healthy is True
    assert snapshot.entry_count == 2  # 2 个目录（演员A 和 番号B）
    assert store.has_changed(snapshot) is True

    store.save(snapshot)
    assert store.has_changed(build_shadow_snapshot(shadow_root)) is False

    # 新增目录应该触发变化（新增 2 个目录：演员C 和 番号D）
    (shadow_root / "演员C" / "番号D").mkdir(parents=True)
    new_snapshot = build_shadow_snapshot(shadow_root)
    assert new_snapshot.entry_count == 4  # 总共 4 个目录
    assert store.has_changed(new_snapshot) is True


def test_shadow_snapshot_detects_strm_changes(tmp_path: Path) -> None:
    """测试影子目录快照能检测到 strm 文件变化"""
    shadow_root = tmp_path / "shadow"
    (shadow_root / "演员A" / "番号B").mkdir(parents=True)

    store = SnapshotStore(tmp_path / "state.json")
    snapshot1 = build_shadow_snapshot(shadow_root)
    store.save(snapshot1)

    # 添加 strm 文件应该触发变化
    (shadow_root / "演员A" / "番号B" / "movie.strm").write_text(
        "/path/to/video.mp4", encoding="utf-8"
    )
    snapshot2 = build_shadow_snapshot(shadow_root)
    assert store.has_changed(snapshot2) is True


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


def test_watch_iteration_skips_unchanged_shadow(
    sample_config_text: str, tmp_path: Path
) -> None:
    """测试当 shadow 目录无变化时跳过迭代"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    config = load_config(config_file)
    config.source_root.mkdir(parents=True)
    config.shadow_root.mkdir(parents=True)

    # 创建 shadow 目录结构和 strm 文件
    (config.shadow_root / "演员A" / "番号B").mkdir(parents=True)
    (config.shadow_root / "演员A" / "番号B" / "demo.strm").write_text(
        "/path", encoding="utf-8"
    )

    store = SnapshotStore(config.state_dir / "watch-snapshot.json")

    # 第一次运行，保存快照
    changed1 = run_watch_iteration(config, snapshot_store=store)
    assert changed1 is False  # 已有 strm，没有变化

    # 第二次运行，shadow 无变化，应该直接返回 False
    changed2 = run_watch_iteration(config, snapshot_store=store)
    assert changed2 is False


def test_watch_iteration_handles_missing_shadow(
    sample_config_text: str, tmp_path: Path
) -> None:
    """测试当 shadow 目录不存在时的处理"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    config = load_config(config_file)
    config.source_root.mkdir(parents=True)
    # shadow_root 故意不创建

    store = SnapshotStore(config.state_dir / "watch-snapshot.json")

    # shadow 不存在，应该视为空目录，尝试执行同步
    # 但因为没有目录结构，不会生成 strm
    changed = run_watch_iteration(config, snapshot_store=store)
    assert changed is False


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
