from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".ts", ".m2ts", ".mov")
DEFAULT_SIDECAR_EXTENSIONS = (
    ".nfo",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".srt",
    ".ass",
    ".ssa",
    ".sub",
    ".idx",
    ".sup",
    ".txt",
)
DEFAULT_SIDECAR_NAME_PATTERNS = (
    "poster",
    "fanart",
    "thumb",
    "clearlogo",
    "logo",
    "banner",
    "landscape",
    "disc",
    "keyart",
)
DEFAULT_PRESERVE_DIRECTORIES = (
    "behind the scenes",
    "extrafanart",
    "extrathumbs",
    "featurettes",
    "deleted scenes",
    "trailers",
)
DEFAULT_EXCLUDE_DIRECTORIES = (
    ".mount-health",
    ".@__thumb",
    "@eaDir",
    "$RECYCLE.BIN",
    "System Volume Information",
    ".DS_Store",
    "Thumbs.db",
)


@dataclass(slots=True)
class JellyfinConfig:
    enabled: bool = False
    server_url: str | None = None
    api_key: str | None = None
    library_name: str = "115strm"
    debounce_seconds: int = 600


@dataclass(slots=True)
class SyncConfig:
    source_root: Path
    shadow_root: Path
    strm_prefix: str
    state_dir: Path
    video_extensions: tuple[str, ...] = DEFAULT_VIDEO_EXTENSIONS
    sidecar_extensions: tuple[str, ...] = DEFAULT_SIDECAR_EXTENSIONS
    sidecar_name_patterns: tuple[str, ...] = DEFAULT_SIDECAR_NAME_PATTERNS
    preserve_directories: tuple[str, ...] = DEFAULT_PRESERVE_DIRECTORIES
    exclude_directories: tuple[str, ...] = DEFAULT_EXCLUDE_DIRECTORIES
    delete_ratio_limit: float = 0.25
    delete_count_limit: int = 20
    jellyfin: JellyfinConfig = field(default_factory=JellyfinConfig)


def load_config(config_path: Path) -> SyncConfig:
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ValueError(f"读取配置失败：{exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"解析配置失败：{exc}") from exc
    source_root = Path(_require(raw, "source_root"))
    shadow_root = Path(_require(raw, "shadow_root"))
    strm_prefix = str(_require(raw, "strm_prefix")).rstrip("/")
    state_dir = Path(raw.get("state_dir") or shadow_root / ".jellyfin-strm-state")
    jellyfin_raw = raw.get("jellyfin") or {}

    return SyncConfig(
        source_root=source_root,
        shadow_root=shadow_root,
        strm_prefix=strm_prefix,
        state_dir=state_dir,
        video_extensions=_normalize_suffixes(raw.get("video_extensions"), DEFAULT_VIDEO_EXTENSIONS),
        sidecar_extensions=_normalize_suffixes(raw.get("sidecar_extensions"), DEFAULT_SIDECAR_EXTENSIONS),
        sidecar_name_patterns=_normalize_names(raw.get("sidecar_name_patterns"), DEFAULT_SIDECAR_NAME_PATTERNS),
        preserve_directories=_normalize_names(raw.get("preserve_directories"), DEFAULT_PRESERVE_DIRECTORIES),
        exclude_directories=_normalize_names(raw.get("exclude_directories"), DEFAULT_EXCLUDE_DIRECTORIES),
        delete_ratio_limit=float(raw.get("delete_ratio_limit", 0.25)),
        delete_count_limit=int(raw.get("delete_count_limit", 20)),
        jellyfin=JellyfinConfig(
            enabled=bool(jellyfin_raw.get("enabled", False)),
            server_url=jellyfin_raw.get("server_url"),
            api_key=jellyfin_raw.get("api_key"),
            library_name=str(jellyfin_raw.get("library_name", "115strm")),
            debounce_seconds=int(jellyfin_raw.get("debounce_seconds", 600)),
        ),
    )


def _require(raw: dict[str, Any], key: str) -> Any:
    if key not in raw or raw[key] in (None, ""):
        raise ValueError(f"配置缺少必填字段: {key}")
    return raw[key]


def _normalize_suffixes(value: Any, defaults: tuple[str, ...]) -> tuple[str, ...]:
    items = value or defaults
    return tuple(_normalize_suffix(item) for item in items)


def _normalize_names(value: Any, defaults: tuple[str, ...]) -> tuple[str, ...]:
    items = value or defaults
    return tuple(str(item).lower() for item in items)


def _normalize_suffix(value: Any) -> str:
    text = str(value).lower()
    return text if text.startswith(".") else f".{text}"
