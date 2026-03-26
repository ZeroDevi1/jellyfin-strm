from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from jellyfin_strm.rules import RuleSet


@dataclass(slots=True)
class PlannedWrite:
    relative_path: Path
    content: str


@dataclass(slots=True)
class PlannedCopy:
    relative_path: Path
    source_path: Path


@dataclass(slots=True)
class SyncPlan:
    write_strms: list[PlannedWrite]
    copy_files: list[PlannedCopy]
    delete_paths: list[Path]
    warnings: list[str]
    source_healthy: bool


def build_sync_plan(
    source_root: Path,
    shadow_root: Path,
    strm_prefix: str,
    rules: RuleSet | None = None,
) -> SyncPlan:
    active_rules = rules or RuleSet.default()
    warnings: list[str] = []
    if not source_root.is_dir():
        return SyncPlan(
            [], [], [], [f"源目录健康检查失败：{source_root} 不存在或不可读"], False
        )

    source_entries = _count_source_entries(source_root, active_rules)
    if source_entries == 0:
        return SyncPlan(
            [],
            [],
            [],
            [f"源目录健康检查失败：{source_root} 为空或仅包含被排除目录"],
            False,
        )

    write_strms: list[PlannedWrite] = []
    copy_files: list[PlannedCopy] = []
    expected_files: set[Path] = set()

    for current_root, dirs, files in os.walk(source_root):
        dirs[:] = sorted(d for d in dirs if not active_rules.should_skip_directory(d))
        root_path = Path(current_root)
        for file_name in sorted(files):
            source_path = root_path / file_name
            relative_path = source_path.relative_to(source_root)
            if active_rules.is_video(file_name):
                target_relative = relative_path.with_suffix(".strm")
                if target_relative not in expected_files:
                    write_strms.append(
                        PlannedWrite(
                            relative_path=target_relative,
                            content=f"{strm_prefix.rstrip('/')}/{relative_path.as_posix()}",
                        )
                    )
                    expected_files.add(target_relative)
            elif active_rules.is_sidecar_file(file_name):
                if relative_path not in expected_files:
                    copy_files.append(
                        PlannedCopy(
                            relative_path=relative_path, source_path=source_path
                        )
                    )
                    expected_files.add(relative_path)

    # 影子库中现在可能会保留独立维护的 NFO/图片等元数据，不能再按“源目录缺失即删除”处理。
    # 为兼容既有数据，这里只增量写入 STRM / sidecar，不主动删除影子库已有内容。
    return SyncPlan(write_strms, copy_files, [], warnings, True)


def _count_source_entries(source_root: Path, rules: RuleSet) -> int:
    count = 0
    for current_root, dirs, files in os.walk(source_root):
        dirs[:] = [d for d in dirs if not rules.should_skip_directory(d)]
        count += len(dirs) + len(files)
    return count
