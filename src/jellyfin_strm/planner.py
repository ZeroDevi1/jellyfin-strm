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


def _find_nfo_files(root: Path) -> list[Path]:
    """递归查找所有 .nfo 文件"""
    nfos = []
    if not root.exists():
        return nfos
    try:
        for item in root.rglob("*.nfo"):
            if item.is_file():
                nfos.append(item)
    except OSError:
        pass
    return nfos


def _has_strm_for_nfo(nfo_path: Path) -> bool:
    """检查是否存在与 nfo 文件同名的 strm 文件"""
    strm_path = nfo_path.with_suffix(".strm")
    return strm_path.exists()


def _find_video_for_nfo(
    nfo_path: Path, source_dir: Path, rules: RuleSet
) -> Path | None:
    """
    在 source 目录中查找与 nfo 对应的视频文件。
    匹配规则：视频文件名（不含后缀）与 nfo 文件名（不含后缀）相同。
    """
    if not source_dir.exists():
        return None

    nfo_stem = nfo_path.stem.lower()

    try:
        for item in source_dir.iterdir():
            if item.is_file() and rules.is_video(item.name):
                if item.stem.lower() == nfo_stem:
                    return item
    except OSError:
        pass
    return None


def build_sync_plan(
    source_root: Path,
    shadow_root: Path,
    strm_prefix: str,
    rules: RuleSet | None = None,
) -> SyncPlan:
    """
    构建同步计划。

    策略：以 shadow 目录中的 .nfo 文件为驱动，检查每个 .nfo 是否有对应的 .strm 文件。
    如果没有对应的 .strm，就到 source 目录查找同名的视频文件并创建 .strm。

    一个文件夹内有多个视频时，会为每个缺失对应 strm 的 nfo 创建链接。
    """
    active_rules = rules or RuleSet.default()
    warnings: list[str] = []

    if not source_root.is_dir():
        return SyncPlan(
            [], [], [], [f"源目录健康检查失败：{source_root} 不存在或不可读"], False
        )

    if not shadow_root.exists():
        # shadow_root 不存在，没有 nfo 文件，无需处理
        return SyncPlan([], [], [], [], True)

    write_strms: list[PlannedWrite] = []

    # 查找所有 .nfo 文件
    nfo_files = _find_nfo_files(shadow_root)

    for nfo_path in nfo_files:
        # 检查是否已有对应的 .strm 文件
        if _has_strm_for_nfo(nfo_path):
            continue

        # 计算对应的 source 目录
        try:
            relative_dir = nfo_path.parent.relative_to(shadow_root)
        except ValueError:
            continue

        source_dir = source_root / relative_dir

        # 查找与 nfo 同名的视频文件
        video_path = _find_video_for_nfo(nfo_path, source_dir, active_rules)
        if video_path is None:
            warnings.append(f"未找到与 {nfo_path} 对应的视频文件")
            continue

        # 创建 strm 文件计划
        video_relative = video_path.relative_to(source_root)
        strm_relative = video_relative.with_suffix(".strm")

        write_strms.append(
            PlannedWrite(
                relative_path=strm_relative,
                content=f"{strm_prefix.rstrip('/')}/{video_relative.as_posix()}",
            )
        )

    return SyncPlan(write_strms, [], [], warnings, True)
