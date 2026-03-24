from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from urllib import request


class RefreshMarkerStore:
    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file

    def should_refresh(self, library_name: str, now: int, debounce_seconds: int = 600) -> bool:
        state = self._load()
        last_refreshed = int(state.get(library_name, 0))
        return (now - last_refreshed) >= debounce_seconds

    def mark_refreshed(self, library_name: str, at: int) -> None:
        state = self._load()
        state[library_name] = at
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> dict[str, int]:
        if not self.state_file.exists():
            return {}
        return json.loads(self.state_file.read_text(encoding="utf-8"))


@dataclass(slots=True)
class JellyfinClient:
    server_url: str
    api_key: str

    def request_library_refresh(self, library_name: str) -> None:
        req = request.Request(
            url=f"{self.server_url.rstrip('/')}/Library/Refresh",
            method="POST",
            headers={
                "X-Emby-Token": self.api_key,
                "Content-Type": "application/json",
            },
            data=b"{}",
        )
        with request.urlopen(req, timeout=15):
            return
