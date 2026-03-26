from __future__ import annotations

import argparse
from pathlib import Path
import sys

from jellyfin_strm.config import load_config
from jellyfin_strm.runtime import (
    SourceHealthError,
    SyncIOError,
    execute_sync,
    maybe_refresh_jellyfin,
    print_summary,
)
from jellyfin_strm.watch import run_watch_loop


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "sync":
        return _run_sync(Path(args.config), dry_run=args.dry_run)
    if args.command == "watch":
        return _run_watch(
            Path(args.config), interval_seconds=args.interval, max_loops=args.max_loops
        )
    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jellyfin-strm")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="同步 115 挂载源到本地影子库")
    sync_parser.add_argument("--config", required=True, help="YAML 配置文件路径")
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="只输出计划，不落盘"
    )
    watch_parser = subparsers.add_parser(
        "watch", help="常驻轮询源目录，有变化时立即同步"
    )
    watch_parser.add_argument("--config", required=True, help="YAML 配置文件路径")
    watch_parser.add_argument(
        "--interval", type=int, default=30, help="轮询间隔秒数，默认 30"
    )
    watch_parser.add_argument(
        "--max-loops", type=int, default=None, help=argparse.SUPPRESS
    )
    return parser


def _run_sync(config_path: Path, dry_run: bool) -> int:
    try:
        config = load_config(config_path)
        summary = execute_sync(config, dry_run=dry_run)
        print_summary(summary)
        maybe_refresh_jellyfin(config, summary.has_changes, dry_run)
    except (ValueError, SourceHealthError, SyncIOError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def _run_watch(config_path: Path, interval_seconds: int, max_loops: int | None) -> int:
    try:
        config = load_config(config_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_watch_loop(
        config, interval_seconds=interval_seconds, max_loops=max_loops
    )
