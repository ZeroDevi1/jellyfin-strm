from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from jellyfin_strm.planner import SyncPlan


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
) -> ExecutionSummary:
    if not plan.source_healthy:
        raise SourceHealthError("源目录健康检查失败")

    summary = ExecutionSummary(dry_run=dry_run)
    if dry_run:
        summary.written_strms = len(plan.write_strms)
        summary.copied_files = len(plan.copy_files)
        return summary

    shadow_root.mkdir(parents=True, exist_ok=True)
    for item in plan.write_strms:
        target_path = shadow_root / item.relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            target_path.write_text(f"{item.content}\n", encoding="utf-8")
        except OSError as exc:
            raise SyncIOError(
                _build_io_error_message("写入 STRM", exc, target_path=target_path)
            ) from exc
        summary.written_strms += 1

    for item in plan.copy_files:
        target_path = shadow_root / item.relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item.source_path, target_path)
        except OSError as exc:
            raise SyncIOError(
                _build_io_error_message(
                    "复制 sidecar",
                    exc,
                    source_path=item.source_path,
                    target_path=target_path,
                )
            ) from exc
        summary.copied_files += 1

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
