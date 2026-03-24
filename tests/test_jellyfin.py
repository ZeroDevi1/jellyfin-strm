from pathlib import Path

from jellyfin_strm.jellyfin import RefreshMarkerStore


def test_refresh_marker_debounces_calls(tmp_path: Path) -> None:
    store = RefreshMarkerStore(tmp_path / "refresh-state.json")

    assert store.should_refresh("115strm", now=1_000) is True
    store.mark_refreshed("115strm", at=1_000)
    assert store.should_refresh("115strm", now=1_100, debounce_seconds=600) is False
    assert store.should_refresh("115strm", now=1_700, debounce_seconds=600) is True
