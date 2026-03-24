from pathlib import Path

import pytest

from jellyfin_strm.config import load_config


def test_load_config_reads_paths_and_thresholds(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
source_root: /source
shadow_root: /shadow
strm_prefix: /mnt/115open/Secret
video_extensions: [.mp4, .mkv]
delete_ratio_limit: 0.25
delete_count_limit: 20
state_dir: /state
jellyfin:
  enabled: true
  server_url: http://jellyfin:8096
  api_key: test-key
  library_name: 115strm
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.source_root.as_posix() == "/source"
    assert config.shadow_root.as_posix() == "/shadow"
    assert config.strm_prefix == "/mnt/115open/Secret"
    assert config.video_extensions == (".mp4", ".mkv")
    assert config.delete_ratio_limit == 0.25
    assert config.delete_count_limit == 20
    assert config.state_dir.as_posix() == "/state"
    assert config.jellyfin.enabled is True


def test_load_config_reports_yaml_error(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("exclude_directories:\n  - @eaDir\n", encoding="utf-8")

    with pytest.raises(ValueError, match="解析配置失败"):
        load_config(config_file)
