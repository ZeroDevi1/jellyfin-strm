from __future__ import annotations

from pathlib import Path
import sys
import time

from jellyfin_strm.config import SyncConfig
from jellyfin_strm.executor import (
    ExecutionSummary,
    SourceHealthError,
    SyncIOError,
    execute_plan,
)
from jellyfin_strm.jellyfin import JellyfinClient, RefreshMarkerStore
from jellyfin_strm.planner import build_sync_plan
from jellyfin_strm.rules import RuleSet


def execute_sync(config: SyncConfig, dry_run: bool) -> ExecutionSummary:
    plan = build_sync_plan(
        source_root=config.source_root,
        shadow_root=config.shadow_root,
        strm_prefix=config.strm_prefix,
        rules=RuleSet.from_config(config),
    )
    emit_warnings(plan.warnings)
    summary = execute_plan(
        plan=plan,
        shadow_root=config.shadow_root,
        dry_run=dry_run,
    )
    return summary


def emit_warnings(warnings: list[str]) -> None:
    for message in warnings:
        print(message, file=sys.stderr)


def print_summary(summary: ExecutionSummary) -> None:
    print(
        (
            f"dry_run={summary.dry_run} "
            f"written_strms={summary.written_strms} "
            f"copied_files={summary.copied_files} "
            f"deleted_paths={summary.deleted_paths}"
        ),
        file=sys.stdout,
    )


def maybe_refresh_jellyfin(
    config: SyncConfig, has_changes: bool, dry_run: bool
) -> None:
    if dry_run or not has_changes or not config.jellyfin.enabled:
        return

    state_file = config.state_dir / "jellyfin-refresh-state.json"
    marker_store = RefreshMarkerStore(state_file)
    now = int(time.time())
    if not marker_store.should_refresh(
        config.jellyfin.library_name,
        now=now,
        debounce_seconds=config.jellyfin.debounce_seconds,
    ):
        print("Jellyfin 刷新仍在节流窗口内，已跳过", file=sys.stderr)
        return

    if not config.jellyfin.server_url or not config.jellyfin.api_key:
        print(
            "Jellyfin 已启用，但 server_url 或 api_key 未配置，已跳过刷新",
            file=sys.stderr,
        )
        return

    client = JellyfinClient(
        server_url=config.jellyfin.server_url,
        api_key=config.jellyfin.api_key,
    )
    client.request_library_refresh(config.jellyfin.library_name)
    marker_store.mark_refreshed(config.jellyfin.library_name, at=now)
    print(f"已请求 Jellyfin 刷新库：{config.jellyfin.library_name}", file=sys.stderr)


__all__ = [
    "ExecutionSummary",
    "SourceHealthError",
    "SyncIOError",
    "emit_warnings",
    "execute_sync",
    "maybe_refresh_jellyfin",
    "print_summary",
]
