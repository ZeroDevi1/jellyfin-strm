from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import time

from jellyfin_strm.config import SyncConfig
from jellyfin_strm.executor import SourceHealthError, SyncIOError
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


def build_shadow_snapshot(shadow_root: Path) -> DirectorySnapshot:
    """
    构建影子目录的快照。
    递归遍历所有子目录，收集目录结构和 strm 文件状态。
    """
    if not shadow_root.exists():
        # shadow_root 不存在，视为空目录，后续会创建
        return DirectorySnapshot(
            digest=hashlib.sha256(b"").hexdigest(),
            entry_count=0,
            source_healthy=True,
        )

    if not shadow_root.is_dir():
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"影子目录检查失败：{shadow_root} 不是目录",
        )

    entries: list[str] = []
    try:
        # 递归遍历所有子目录，收集目录结构和 strm 文件
        for path in sorted(shadow_root.rglob("*")):
            try:
                stat = path.stat()
            except OSError:
                continue

            relative_path = path.relative_to(shadow_root)
            if path.is_dir():
                # 记录目录存在
                entries.append(f"dir:{relative_path.as_posix()}:{stat.st_mtime_ns}")
            elif path.is_file() and path.suffix.lower() == ".strm":
                # 记录 strm 文件
                entries.append(
                    f"strm:{relative_path.as_posix()}:{stat.st_size}:{stat.st_mtime_ns}"
                )
    except OSError as exc:
        return DirectorySnapshot(
            digest="",
            entry_count=0,
            source_healthy=False,
            warning=f"影子目录检查失败：无法读取目录 {shadow_root}：{exc}",
        )

    digest = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return DirectorySnapshot(
        digest=digest, entry_count=len(entries), source_healthy=True
    )


def run_watch_iteration(config: SyncConfig, snapshot_store: SnapshotStore) -> bool:
    # 检查影子目录是否有变化（新增/删除目录、strm 文件变化）
    snapshot = build_shadow_snapshot(config.shadow_root)
    if not snapshot.source_healthy:
        if snapshot.warning:
            print(snapshot.warning, file=sys.stderr)
        return False

    # 只有影子目录结构变化时才执行同步
    if not snapshot_store.has_changed(snapshot):
        return False

    # 执行同步：扫描 shadow 中无 strm 的目录，到 source 查找视频生成 strm
    summary = execute_sync(config, dry_run=False)

    if summary.has_changes:
        print_summary(summary)
        maybe_refresh_jellyfin(config, summary.has_changes, dry_run=False)

    # 保存快照
    snapshot_store.save(snapshot)
    return summary.has_changes


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
