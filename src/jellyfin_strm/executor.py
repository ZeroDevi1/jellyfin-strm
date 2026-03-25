from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from jellyfin_strm.planner import SyncPlan


class DeleteThresholdError(RuntimeError):
    """删除批次超出安全阈值。"""


class SourceHealthError(RuntimeError):
    """源目录健康检查失败。"""


class SyncIOError(RuntimeError):
    """同步过程中发生文件读写错误。"""


@dataclass(slots=True)
class ExecutionSummary:
    written_strms: int = 0
    copied_files: int = 0
    deleted_paths: int = 0
    dry_run: bool = False

    @property
    def has_changes(self) -> bool:
        return (self.written_strms + self.copied_files + self.deleted_paths) > 0


def execute_plan(
    plan: SyncPlan,
    shadow_root: Path,
    dry_run: bool,
    delete_ratio_limit: float = 0.25,
    delete_count_limit: int = 20,
) -> ExecutionSummary:
    if not plan.source_healthy:
        raise SourceHealthError("源目录健康检查失败")

    _guard_delete_thresholds(
        shadow_root=shadow_root,
        delete_paths=plan.delete_paths,
        delete_ratio_limit=delete_ratio_limit,
        delete_count_limit=delete_count_limit,
    )

    summary = ExecutionSummary(dry_run=dry_run)
    if dry_run:
        summary.written_strms = len(plan.write_strms)
        summary.copied_files = len(plan.copy_files)
        summary.deleted_paths = len(plan.delete_paths)
        return summary

    shadow_root.mkdir(parents=True, exist_ok=True)
    for item in plan.write_strms:
        target_path = shadow_root / item.relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            target_path.write_text(f"{item.content}\n", encoding="utf-8")
        except OSError as exc:
            raise SyncIOError(_build_io_error_message("写入 STRM", exc, target_path=target_path)) from exc
        summary.written_strms += 1

    for item in plan.copy_files:
        target_path = shadow_root / item.relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item.source_path, target_path)
        except OSError as exc:
            raise SyncIOError(
                _build_io_error_message("复制 sidecar", exc, source_path=item.source_path, target_path=target_path)
            ) from exc
        summary.copied_files += 1

    for relative_path in plan.delete_paths:
        target_path = shadow_root / relative_path
        if not target_path.exists():
            continue
        try:
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                target_path.unlink()
        except OSError as exc:
            raise SyncIOError(_build_io_error_message("删除影子文件", exc, target_path=target_path)) from exc
        summary.deleted_paths += 1

    return summary


def _build_io_error_message(
    action: str,
    exc: OSError,
    source_path: Path | None = None,
    target_path: Path | None = None,
) -> str:
    parts = [f"{action}失败"]
    if source_path is not None:
        parts.append(f"source={source_path}")
    if target_path is not None:
        parts.append(f"target={target_path}")
    parts.append(f"error={exc}")
    return "；".join(parts)


def _guard_delete_thresholds(
    shadow_root: Path,
    delete_paths: list[Path],
    delete_ratio_limit: float,
    delete_count_limit: int,
) -> None:
    delete_count = len(delete_paths)
    if delete_count == 0:
        return
    if delete_count > delete_count_limit:
        raise DeleteThresholdError("删除数量超出安全阈值")

    existing_entries = 0
    if shadow_root.exists():
        for _ in shadow_root.rglob("*"):
            existing_entries += 1
    if existing_entries == 0:
        return

    # 先做比例保护，避免挂载异常时把整个影子库清掉。
    if delete_count / existing_entries > delete_ratio_limit:
        raise DeleteThresholdError("删除比例超出安全阈值")
