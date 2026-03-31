from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def _has_strm_in_directory(dir_path: Path) -> bool:
    """检查目录中是否存在任何 .strm 文件（不递归子目录）"""
    if not dir_path.exists():
        return False
    try:
        for item in dir_path.iterdir():
            if item.is_file() and item.suffix.lower() == ".strm":
                return True
    except OSError:
        return False
    return False


def _get_subdirectories(root: Path) -> list[Path]:
    """获取根目录下的所有子目录（递归）"""
    subdirs = []
    if not root.exists():
        return subdirs
    try:
        for item in root.rglob("*"):
            if item.is_dir():
                subdirs.append(item)
    except OSError:
        pass
    return subdirs


def _find_videos_in_directory(dir_path: Path, rules: RuleSet) -> list[Path]:
    """在目录中查找所有视频文件（不递归）"""
    videos = []
    if not dir_path.exists():
        return videos
    try:
        for item in dir_path.iterdir():
            if item.is_file() and rules.is_video(item.name):
                videos.append(item)
    except OSError:
        pass
    return videos


def build_sync_plan(
    source_root: Path,
    shadow_root: Path,
    strm_prefix: str,
    rules: RuleSet | None = None,
) -> SyncPlan:
    """
    构建同步计划。

    策略：以 shadow_root 为驱动，检查哪些子目录还没有 strm 文件，
    然后到 source_root 对应路径查找视频并创建 strm。
    """
    active_rules = rules or RuleSet.default()
    warnings: list[str] = []

    if not source_root.is_dir():
        return SyncPlan(
            [], [], [], [f"源目录健康检查失败：{source_root} 不存在或不可读"], False
        )

    if not shadow_root.exists():
        # shadow_root 不存在，视为全部需要处理
        shadow_root.mkdir(parents=True, exist_ok=True)

    write_strms: list[PlannedWrite] = []

    # 获取 shadow_root 下的所有子目录（包括 shadow_root 本身）
    shadow_dirs = [shadow_root] + _get_subdirectories(shadow_root)

    for shadow_dir in shadow_dirs:
        # 检查该目录是否已有 strm 文件
        if _has_strm_in_directory(shadow_dir):
            continue

        # 计算对应的 source 目录路径
        try:
            relative_dir = shadow_dir.relative_to(shadow_root)
        except ValueError:
            continue

        source_dir = source_root / relative_dir

        # 在 source 目录中查找视频文件
        videos = _find_videos_in_directory(source_dir, active_rules)

        for video_path in sorted(videos):
            # 计算 strm 文件的相对路径
            video_relative = video_path.relative_to(source_root)
            strm_relative = video_relative.with_suffix(".strm")

            write_strms.append(
                PlannedWrite(
                    relative_path=strm_relative,
                    content=f"{strm_prefix.rstrip('/')}/{video_relative.as_posix()}",
                )
            )

    # 不再同步 sidecar 文件（png, nfo 等元数据）
    return SyncPlan(write_strms, [], [], warnings, True)
