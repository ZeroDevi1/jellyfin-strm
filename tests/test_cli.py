from pathlib import Path
from subprocess import run

from jellyfin_strm.cli import _run_sync


def test_module_help_runs() -> None:
    result = run(
        ["uv", "run", "python", "-m", "jellyfin_strm", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "sync" in result.stdout
    assert "watch" in result.stdout


def test_readme_mentions_ofelia_scheduler() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "ofelia" in readme
    assert "纯 Docker 自动调度" in readme


def test_sync_dry_run_reports_health_error(sample_config_text: str, tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    result = run(
        ["uv", "run", "python", "-m", "jellyfin_strm", "sync", "--config", str(config_file), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "源目录健康检查失败" in result.stderr


def test_run_sync_reports_io_error(sample_config_text: str, tmp_path: Path, monkeypatch, capsys) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_config_text, encoding="utf-8")

    def fake_execute_sync(*_args, **_kwargs):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr("jellyfin_strm.cli.execute_sync", fake_execute_sync)

    assert _run_sync(config_file, dry_run=False) == 2
    captured = capsys.readouterr()
    assert "Input/output error" in captured.err
