from pathlib import Path


def test_workflow_builds_and_pushes_ghcr_on_main_push_and_dispatch() -> None:
    workflow_path = Path(".github/workflows/build-and-push-ghcr.yml")
    workflow = workflow_path.read_text(encoding="utf-8")

    assert "workflow_dispatch: {}" in workflow
    assert 'branches: ["main"]' in workflow
    assert "docker/build-push-action@v6" in workflow
    assert "ghcr.io/${{ steps.owner.outputs.owner }}/jellyfin-strm" in workflow
    assert "type=raw,value=latest" in workflow
    assert "type=sha,format=short,prefix=sha-" in workflow


def test_docker_assets_use_published_image_and_cli_entrypoint() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose_example = Path("docker-compose.nas.example.yml").read_text(encoding="utf-8")
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim" in dockerfile
    assert "uv pip install --system ." in dockerfile
    assert 'ENTRYPOINT ["jellyfin-strm"]' in dockerfile
    assert '[project.scripts]' in pyproject
    assert 'jellyfin-strm = "jellyfin_strm.cli:main"' in pyproject
    assert "ghcr.io/zerodevi1/jellyfin-strm:latest" in compose_example
    assert "strm-sync-watch:" in compose_example
    assert "watch" in compose_example
    assert "strm-sync-daily:" in compose_example
    assert "ofelia:" in compose_example
    assert "/var/run/docker.sock:/var/run/docker.sock:ro" in compose_example
    assert 'ofelia.job-exec.daily-sync.schedule: "@daily"' in compose_example
    assert 'ofelia.job-exec.daily-sync.command: "jellyfin-strm sync --config /config/config.yaml"' in compose_example
