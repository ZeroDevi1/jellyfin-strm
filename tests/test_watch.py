from pathlib import Path

from jellyfin_strm.config import load_config
from jellyfin_strm.watch import SnapshotStore, build_directory_snapshot, run_watch_iteration, run_watch_loop


def test_snapshot_store_detects_changes(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    state_file = tmp_path / "state" / "watch-snapshot.json"
    source_root.mkdir(parents=True)
    (source_root / "movie.mp4").write_text("v1", encoding="utf-8")

    store = SnapshotStore(state_file)
    snapshot = build_directory_snapshot(source_root)

    assert snapshot.source_healthy is True
    assert store.has_changed(snapshot) is True

    store.save(snapshot)
    assert store.has_changed(build_directory_snapshot(source_root)) is False

    (source_root / "movie.mp4").write_text("v2", encoding="utf-8")
    assert store.has_changed(build_directory_snapshot(source_root)) is True


def test_watch_iteration_writes_snapshot_and_syncs(sample_config_text: str, tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    config = load_config(config_file)
    config.source_root.mkdir(parents=True)
    config.shadow_root.mkdir(parents=True)
    (config.source_root / "Movie").mkdir()
    (config.source_root / "Movie" / "demo.mp4").write_text("video", encoding="utf-8")
    (config.source_root / "Movie" / "demo.nfo").write_text("<movie />", encoding="utf-8")

    store = SnapshotStore(config.state_dir / "watch-snapshot.json")

    changed = run_watch_iteration(config, snapshot_store=store)

    assert changed is True
    assert (config.shadow_root / "Movie" / "demo.strm").exists()
    assert (config.state_dir / "watch-snapshot.json").exists()

    unchanged = run_watch_iteration(config, snapshot_store=store)
    assert unchanged is False


def test_watch_iteration_skips_unhealthy_source_without_overwriting_snapshot(sample_config_text: str, tmp_path: Path) -> None:
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
    assert after == before


def test_build_directory_snapshot_returns_warning_when_stat_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir(parents=True)
    broken_file = source_root / "poster.jpg"
    broken_file.write_text("image", encoding="utf-8")

    original_stat = Path.stat

    def fake_stat(self: Path, *args, **kwargs):
        if self == broken_file:
            raise OSError(5, "Input/output error")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fake_stat)

    snapshot = build_directory_snapshot(source_root)

    assert snapshot.source_healthy is False
    assert snapshot.warning is not None
    assert "poster.jpg" in snapshot.warning


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
