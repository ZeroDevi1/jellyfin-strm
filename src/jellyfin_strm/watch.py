from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import time

from jellyfin_strm.config import SyncConfig
from jellyfin_strm.executor import SourceHealthError, SyncIOError
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
        self.state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load(self) -> dict[str, object]:
        if not self.state_file.exists():
            return {}
        return json.loads(self.state_file.read_text(encoding="utf-8"))


def build_source_snapshot(
    source_root: Path, rules: RuleSet | None = None
) -> DirectorySnapshot:
    """
    构建源目录的快照。
    递归遍历所有子目录，收集所有视频文件的状态。
    """
    active_rules = rules or RuleSet.default()
    if not source_root.is_dir():
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"源目录健康检查失败：{source_root} 不存在或不可读",
        )

    entries: list[str] = []
    try:
        # 递归遍历所有子目录中的视频文件
        for file_path in sorted(source_root.rglob("*")):
            if file_path.is_file() and active_rules.is_video(file_path.name):
                try:
                    stat = file_path.stat()
                except OSError as exc:
                    return DirectorySnapshot(
                        digest="",
                        entry_count=len(entries),
                        source_healthy=False,
                        warning=f"源目录健康检查失败：读取 {file_path} 时出错：{exc}",
                    )
                relative_path = file_path.relative_to(source_root)
                entries.append(
                    f"file:{relative_path.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}"
                )
    except OSError as exc:
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"源目录健康检查失败：无法读取目录 {source_root}：{exc}",
        )

    if not entries:
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"源目录健康检查失败：{source_root} 中没有视频文件",
        )

    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return DirectorySnapshot(
        digest=digest, entry_count=len(entries), source_healthy=True
    )


def run_watch_iteration(config: SyncConfig, snapshot_store: SnapshotStore) -> bool:
    # 检查源目录是否有变化
    snapshot = build_source_snapshot(config.source_root, RuleSet.from_config(config))
    if not snapshot.source_healthy:
        if snapshot.warning:
            print(snapshot.warning, file=sys.stderr)
        return False

    # 即使源目录没有变化，也可能需要同步（比如 shadow 中新增了没有 strm 的目录）
    # 所以每次都要执行 sync，但只在有变化时刷新 Jellyfin
    summary = execute_sync(config, dry_run=False)

    if summary.has_changes:
        print_summary(summary)
        maybe_refresh_jellyfin(config, summary.has_changes, dry_run=False)
        snapshot_store.save(snapshot)
        return True
    else:
        print("没有需要同步的内容", file=sys.stderr)
        # 仍然保存快照，记录本次检查时间
        snapshot_store.save(snapshot)
        return False


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
        # I/O 错误通常来自远端挂载抖动，记录后保留现场，等待下轮重试。
        except (SourceHealthError, SyncIOError, ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)

        iteration += 1
        if max_loops is not None and iteration >= max_loops:
            return 0
        time.sleep(interval_seconds)
