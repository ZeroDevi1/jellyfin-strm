from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from jellyfin_strm.config import SyncConfig
from jellyfin_strm.executor import DeleteThresholdError, SourceHealthError
from jellyfin_strm.rules import RuleSet
from jellyfin_strm.runtime import execute_sync, maybe_refresh_jellyfin, print_summary


@dataclass(slots=True)
class DirectorySnapshot:
    digest: str
    entry_count: int
    source_healthy: bool
    warning: str | None = None


class SnapshotStore:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file

    def has_changed(self, snapshot: DirectorySnapshot) -> bool:
        current = self._load()
        return current.get("digest") != snapshot.digest

    def save(self, snapshot: DirectorySnapshot) -> None:
        payload = {
            "digest": snapshot.digest,
            "entry_count": snapshot.entry_count,
            "saved_at": int(time.time()),
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self) -> dict[str, object]:
        if not self.state_file.exists():
            return {}
        return json.loads(self.state_file.read_text(encoding="utf-8"))


def build_directory_snapshot(source_root: Path, rules: RuleSet | None = None) -> DirectorySnapshot:
    active_rules = rules or RuleSet.default()
    if not source_root.is_dir():
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"源目录健康检查失败：{source_root} 不存在或不可读",
        )

    entries: list[str] = []
    for current_root, dirs, files in os.walk(source_root):
        dirs[:] = sorted(d for d in dirs if not active_rules.should_skip_directory(d))
        root_path = Path(current_root)
        for directory_name in dirs:
            relative_path = (root_path / directory_name).relative_to(source_root)
            entries.append(f"dir:{relative_path.as_posix()}")
        for file_name in sorted(files):
            file_path = root_path / file_name
            stat = file_path.stat()
            relative_path = file_path.relative_to(source_root)
            entries.append(
                f"file:{relative_path.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}"
            )

    if not entries:
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"源目录健康检查失败：{source_root} 为空或仅包含被排除目录",
        )

    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return DirectorySnapshot(digest=digest, entry_count=len(entries), source_healthy=True)


def run_watch_iteration(config: SyncConfig, snapshot_store: SnapshotStore) -> bool:
    snapshot = build_directory_snapshot(config.source_root, RuleSet.from_config(config))
    if not snapshot.source_healthy:
        if snapshot.warning:
            print(snapshot.warning, file=sys.stderr)
        return False

    if not snapshot_store.has_changed(snapshot):
        print("watch 未检测到目录变化，跳过同步", file=sys.stderr)
        return False

    summary = execute_sync(config, dry_run=False)
    print_summary(summary)
    maybe_refresh_jellyfin(config, summary.has_changes, dry_run=False)
    snapshot_store.save(snapshot)
    return True


def run_watch_loop(
    config: SyncConfig,
    interval_seconds: int = 30,
    max_loops: int | None = None,
) -> int:
    snapshot_store = SnapshotStore(config.state_dir / "watch-snapshot.json")
    iteration = 0
    while True:
        try:
            run_watch_iteration(config, snapshot_store=snapshot_store)
        except (DeleteThresholdError, SourceHealthError, ValueError) as exc:
            print(str(exc), file=sys.stderr)

        iteration += 1
        if max_loops is not None and iteration >= max_loops:
            return 0
        time.sleep(interval_seconds)
