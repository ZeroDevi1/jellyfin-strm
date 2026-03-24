from pathlib import Path

import pytest


@pytest.fixture
def sample_config_text(tmp_path: Path) -> str:
    source_root = tmp_path / "source"
    shadow_root = tmp_path / "shadow"
    state_root = tmp_path / "state"
    return f"""
source_root: {source_root.as_posix()}
shadow_root: {shadow_root.as_posix()}
strm_prefix: /mnt/115open/Secret
delete_ratio_limit: 0.25
delete_count_limit: 20
state_dir: {state_root.as_posix()}
jellyfin:
  enabled: false
  server_url: http://jellyfin:8096
  api_key: demo-key
  library_name: 115strm
""".strip()
