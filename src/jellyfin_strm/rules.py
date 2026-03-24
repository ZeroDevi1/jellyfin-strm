from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from jellyfin_strm.config import SyncConfig


@dataclass(slots=True)
class RuleSet:
    video_extensions: tuple[str, ...]
    sidecar_extensions: tuple[str, ...]
    sidecar_name_patterns: tuple[str, ...]
    preserve_directories: tuple[str, ...]
    exclude_directories: tuple[str, ...]

    @classmethod
    def default(cls) -> "RuleSet":
        from jellyfin_strm.config import (
            DEFAULT_EXCLUDE_DIRECTORIES,
            DEFAULT_PRESERVE_DIRECTORIES,
            DEFAULT_SIDECAR_EXTENSIONS,
            DEFAULT_SIDECAR_NAME_PATTERNS,
            DEFAULT_VIDEO_EXTENSIONS,
        )

        return cls(
            video_extensions=DEFAULT_VIDEO_EXTENSIONS,
            sidecar_extensions=DEFAULT_SIDECAR_EXTENSIONS,
            sidecar_name_patterns=DEFAULT_SIDECAR_NAME_PATTERNS,
            preserve_directories=tuple(item.lower() for item in DEFAULT_PRESERVE_DIRECTORIES),
            exclude_directories=tuple(item.lower() for item in DEFAULT_EXCLUDE_DIRECTORIES),
        )

    @classmethod
    def from_config(cls, config: SyncConfig) -> "RuleSet":
        return cls(
            video_extensions=config.video_extensions,
            sidecar_extensions=config.sidecar_extensions,
            sidecar_name_patterns=config.sidecar_name_patterns,
            preserve_directories=config.preserve_directories,
            exclude_directories=config.exclude_directories,
        )

    def is_video(self, file_name: str) -> bool:
        return Path(file_name).suffix.lower() in self.video_extensions

    def is_sidecar_file(self, file_name: str) -> bool:
        path = Path(file_name)
        suffix = path.suffix.lower()
        stem = path.stem.lower()
        if suffix in self.sidecar_extensions:
            return True
        return any(
            stem == pattern or stem.endswith(f"-{pattern}") or stem.endswith(f".{pattern}")
            for pattern in self.sidecar_name_patterns
        )

    def should_copy_directory(self, directory_name: str) -> bool:
        return directory_name.lower() in self.preserve_directories

    def should_skip_directory(self, directory_name: str) -> bool:
        return directory_name.lower() in self.exclude_directories
