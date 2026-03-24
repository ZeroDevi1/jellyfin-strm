# 115 STRM 首发同步器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可在 NAS 上运行的 Python CLI，同步 115 挂载源到 Jellyfin 本地影子库，生成 `.strm`、复制 sidecar 元数据与资料目录，并在安全前提下清理失效内容与触发 Jellyfin 刷新。

**Architecture:** 采用 `src/` 布局的 Python 项目。核心拆成配置加载、文件分类规则、同步规划、执行引擎与 Jellyfin 刷新客户端五个单元；CLI 只负责参数解析、调用用例与输出日志，确保后续可以单独测试规划与执行逻辑。

**Tech Stack:** Python 3.13、uv、pytest、PyYAML、标准库 `pathlib`/`hashlib`/`shutil`/`json`。

---

## 文件结构

- Create: `pyproject.toml`
- Create: `README.md`
- Create: `config.example.yaml`
- Create: `src/jellyfin_strm/__init__.py`
- Create: `src/jellyfin_strm/__main__.py`
- Create: `src/jellyfin_strm/cli.py`
- Create: `src/jellyfin_strm/config.py`
- Create: `src/jellyfin_strm/rules.py`
- Create: `src/jellyfin_strm/planner.py`
- Create: `src/jellyfin_strm/executor.py`
- Create: `src/jellyfin_strm/jellyfin.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`
- Create: `tests/test_rules.py`
- Create: `tests/test_planner.py`
- Create: `tests/test_executor.py`
- Create: `tests/test_cli.py`

### 责任划分

- `config.py`：解析 YAML 配置，校验源目录、影子库目录、`.strm` 前缀路径、删除阈值、Jellyfin 刷新配置。
- `rules.py`：定义视频后缀、sidecar 白名单、目录白名单/黑名单，以及“是否复制/是否跳过/是否需要告警”的判定。
- `planner.py`：扫描源目录与影子库，生成“创建 `.strm` / 复制文件 / 复制目录 / 删除失效项 / 产生告警”的计划对象。
- `executor.py`：执行计划，支持 `--dry-run`、健康检查、删除比例熔断、状态摘要输出。
- `jellyfin.py`：封装 Jellyfin 刷新请求与节流标记文件。
- `cli.py`：提供 `sync` 命令，组合配置、规划、执行、刷新。

### Task 1: 启动 Python 工程骨架

**Files:**
- Create: `pyproject.toml`
- Create: `src/jellyfin_strm/__init__.py`
- Create: `src/jellyfin_strm/__main__.py`
- Create: `README.md`

- [ ] **Step 1: 写一个最小 CLI 测试，证明包尚未可执行**

```python
from subprocess import run


def test_module_help_runs():
    result = run(["uv", "run", "python", "-m", "jellyfin_strm", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "sync" in result.stdout
```

- [ ] **Step 2: 先运行测试，确认当前失败**

Run: `uv run pytest tests/test_cli.py::test_module_help_runs -v`
Expected: FAIL，因为包和入口文件还不存在。

- [ ] **Step 3: 添加项目骨架与最小入口**

```toml
[project]
name = "jellyfin-strm"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["PyYAML>=6.0.2"]

[project.scripts]
jellyfin-strm = "jellyfin_strm.cli:main"

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```python
# src/jellyfin_strm/__main__.py
from jellyfin_strm.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 实现最小 `sync` 帮助输出并再次跑测试**

Run: `uv run pytest tests/test_cli.py::test_module_help_runs -v`
Expected: PASS。

- [ ] **Step 5: 提交骨架**

```bash
git add pyproject.toml README.md src/jellyfin_strm/__init__.py src/jellyfin_strm/__main__.py src/jellyfin_strm/cli.py tests/test_cli.py
git commit -m "feat(cli): 初始化 STRM 同步器骨架"
```

### Task 2: 配置模型与 YAML 加载

**Files:**
- Create: `config.example.yaml`
- Create: `src/jellyfin_strm/config.py`
- Create: `tests/test_config.py`
- Modify: `src/jellyfin_strm/cli.py`

- [ ] **Step 1: 编写失败测试，锁定配置字段与默认值**

```python
from pathlib import Path

from jellyfin_strm.config import load_config


def test_load_config_reads_paths_and_thresholds(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
source_root: /source
shadow_root: /shadow
strm_prefix: /mnt/115open/Secret
video_extensions: [.mp4, .mkv]
delete_ratio_limit: 0.25
delete_count_limit: 20
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
    assert config.delete_ratio_limit == 0.25
    assert config.jellyfin.enabled is True
```

- [ ] **Step 2: 运行配置测试，确认失败**

Run: `uv run pytest tests/test_config.py::test_load_config_reads_paths_and_thresholds -v`
Expected: FAIL，因为 `load_config` 未实现。

- [ ] **Step 3: 实现配置 dataclass 与加载校验**

```python
@dataclass(slots=True)
class JellyfinConfig:
    enabled: bool = False
    server_url: str | None = None
    api_key: str | None = None
    library_name: str | None = None
    debounce_seconds: int = 600


@dataclass(slots=True)
class SyncConfig:
    source_root: Path
    shadow_root: Path
    strm_prefix: str
    video_extensions: tuple[str, ...]
    sidecar_extensions: tuple[str, ...]
    sidecar_name_patterns: tuple[str, ...]
    preserve_directories: tuple[str, ...]
    exclude_directories: tuple[str, ...]
    delete_ratio_limit: float
    delete_count_limit: int
    jellyfin: JellyfinConfig
```

- [ ] **Step 4: 补充 `config.example.yaml` 并跑完整配置测试**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS。

- [ ] **Step 5: 提交配置能力**

```bash
git add config.example.yaml src/jellyfin_strm/config.py src/jellyfin_strm/cli.py tests/test_config.py
git commit -m "feat(config): 添加同步配置加载与校验"
```

### Task 3: 文件分类规则与同步规划器

**Files:**
- Create: `src/jellyfin_strm/rules.py`
- Create: `src/jellyfin_strm/planner.py`
- Create: `tests/test_rules.py`
- Create: `tests/test_planner.py`

- [ ] **Step 1: 写失败测试，锁定视频、sidecar、目录判定规则**

```python
from jellyfin_strm.rules import RuleSet


def test_rules_identify_known_sidecars():
    rules = RuleSet.default()
    assert rules.is_video("movie.mp4") is True
    assert rules.is_sidecar_file("movie.nfo") is True
    assert rules.is_sidecar_file("poster.jpg") is True
    assert rules.should_copy_directory("extrafanart") is True
    assert rules.should_skip_directory("@eaDir") is True
```

```python
from pathlib import Path

from jellyfin_strm.planner import build_sync_plan


def test_plan_creates_strm_and_sidecars(tmp_path: Path):
    source = tmp_path / "source"
    shadow = tmp_path / "shadow"
    (source / "A/B").mkdir(parents=True)
    (shadow).mkdir()
    (source / "A/B/movie.mp4").write_text("video", encoding="utf-8")
    (source / "A/B/movie.nfo").write_text("<movie />", encoding="utf-8")
    (source / "A/B/poster.jpg").write_bytes(b"poster")

    plan = build_sync_plan(source_root=source, shadow_root=shadow, strm_prefix="/mnt/115open/Secret")

    assert [item.relative_path.as_posix() for item in plan.write_strms] == ["A/B/movie.strm"]
    assert {item.relative_path.as_posix() for item in plan.copy_files} == {"A/B/movie.nfo", "A/B/poster.jpg"}
```

- [ ] **Step 2: 运行规则和规划测试，确认失败**

Run: `uv run pytest tests/test_rules.py tests/test_planner.py -v`
Expected: FAIL，因为规则集和规划器尚未实现。

- [ ] **Step 3: 实现 `RuleSet` 与计划对象**

```python
@dataclass(slots=True)
class PlannedWrite:
    relative_path: Path
    content: str


@dataclass(slots=True)
class PlannedCopy:
    relative_path: Path
    source_path: Path


@dataclass(slots=True)
class SyncPlan:
    write_strms: list[PlannedWrite]
    copy_files: list[PlannedCopy]
    copy_directories: list[PlannedCopy]
    delete_paths: list[Path]
    warnings: list[str]
```

- [ ] **Step 4: 补测试覆盖删除候选、未知目录告警、重复路径幂等后再次运行**

Run: `uv run pytest tests/test_rules.py tests/test_planner.py -v`
Expected: PASS。

- [ ] **Step 5: 提交规划逻辑**

```bash
git add src/jellyfin_strm/rules.py src/jellyfin_strm/planner.py tests/test_rules.py tests/test_planner.py
git commit -m "feat(sync): 添加文件分类规则与同步规划器"
```

### Task 4: 执行引擎、安全保护与 CLI 主流程

**Files:**
- Create: `src/jellyfin_strm/executor.py`
- Modify: `src/jellyfin_strm/cli.py`
- Create: `tests/conftest.py`
- Create: `tests/test_executor.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试，锁定 dry-run、健康检查和删除熔断**

```python
from pathlib import Path

from jellyfin_strm.executor import execute_plan
from jellyfin_strm.planner import SyncPlan, PlannedCopy, PlannedWrite


def test_execute_plan_writes_strm_and_copies_sidecars(tmp_path: Path):
    source_file = tmp_path / "source/movie.nfo"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("<movie />", encoding="utf-8")
    shadow_root = tmp_path / "shadow"
    shadow_root.mkdir()

    plan = SyncPlan(
        write_strms=[PlannedWrite(Path("movie.strm"), "/mnt/115open/Secret/movie.mp4")],
        copy_files=[PlannedCopy(Path("movie.nfo"), source_file)],
        copy_directories=[],
        delete_paths=[],
        warnings=[],
    )

    summary = execute_plan(plan=plan, shadow_root=shadow_root, dry_run=False)

    assert (shadow_root / "movie.strm").read_text(encoding="utf-8") == "/mnt/115open/Secret/movie.mp4\n"
    assert (shadow_root / "movie.nfo").read_text(encoding="utf-8") == "<movie />"
    assert summary.written_strms == 1
```

```python
import pytest

from jellyfin_strm.executor import DeleteThresholdError


def test_execute_plan_blocks_large_delete_batch(tmp_path):
    with pytest.raises(DeleteThresholdError):
        ...
```

- [ ] **Step 2: 运行执行器测试，确认失败**

Run: `uv run pytest tests/test_executor.py -v`
Expected: FAIL，因为执行器与异常类型尚未实现。

- [ ] **Step 3: 实现执行器与 CLI `sync` 命令**

```python
def execute_plan(plan: SyncPlan, shadow_root: Path, dry_run: bool, delete_ratio_limit: float = 0.25, delete_count_limit: int = 20) -> ExecutionSummary:
    if plan.source_unhealthy:
        raise SourceHealthError("source root is unavailable")
    if len(plan.delete_paths) > delete_count_limit:
        raise DeleteThresholdError("delete count exceeds limit")
    ...
```

```python
parser = argparse.ArgumentParser(prog="jellyfin-strm")
subparsers = parser.add_subparsers(dest="command", required=True)
sync_parser = subparsers.add_parser("sync")
sync_parser.add_argument("--config", required=True)
sync_parser.add_argument("--dry-run", action="store_true")
```

- [ ] **Step 4: 运行 CLI 与执行器测试**

Run: `uv run pytest tests/test_executor.py tests/test_cli.py -v`
Expected: PASS。

- [ ] **Step 5: 提交执行主流程**

```bash
git add src/jellyfin_strm/executor.py src/jellyfin_strm/cli.py tests/conftest.py tests/test_executor.py tests/test_cli.py
git commit -m "feat(cli): 实现同步执行与安全保护"
```

### Task 5: Jellyfin 刷新、端到端验证与文档

**Files:**
- Create: `src/jellyfin_strm/jellyfin.py`
- Modify: `src/jellyfin_strm/cli.py`
- Modify: `README.md`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: 写失败测试，锁定刷新节流行为**

```python
from pathlib import Path

from jellyfin_strm.jellyfin import RefreshMarkerStore


def test_refresh_marker_debounces_calls(tmp_path: Path):
    store = RefreshMarkerStore(tmp_path / "refresh-state.json")
    assert store.should_refresh("115strm", now=1_000) is True
    store.mark_refreshed("115strm", at=1_000)
    assert store.should_refresh("115strm", now=1_100, debounce_seconds=600) is False
```

- [ ] **Step 2: 运行 Jellyfin 相关测试，确认失败**

Run: `uv run pytest tests/test_cli.py::test_refresh_marker_debounces_calls -v`
Expected: FAIL，因为刷新模块尚未实现。

- [ ] **Step 3: 实现刷新标记与可选 HTTP 刷新客户端，并补充 README**

```python
class RefreshMarkerStore:
    def should_refresh(self, library_name: str, now: int, debounce_seconds: int = 600) -> bool:
        ...


class JellyfinClient:
    def request_library_refresh(self, library_name: str) -> None:
        ...
```

- [ ] **Step 4: 跑完整测试与一次 dry-run 端到端命令**

Run: `uv run pytest -v`
Expected: PASS。

Run: `uv run python -m jellyfin_strm sync --config config.example.yaml --dry-run`
Expected: 成功输出计划摘要；若示例路径不存在，应以明确的健康检查错误退出，而不是 traceback。

- [ ] **Step 5: 提交首发版本**

```bash
git add README.md src/jellyfin_strm/jellyfin.py src/jellyfin_strm/cli.py tests/test_cli.py
git commit -m "feat(jellyfin): 添加刷新节流与端到端说明"
```

## 最终验收检查

- [ ] `uv run pytest -v`
- [ ] `uv run python -m jellyfin_strm --help`
- [ ] `uv run python -m jellyfin_strm sync --config config.example.yaml --dry-run`
- [ ] 人工核对 README 是否明确说明：`.strm` 路径写容器内路径、侧重影子库、删除阈值保护、Jellyfin 刷新为可选能力
- [ ] 人工核对 `config.example.yaml` 是否覆盖 source/shadow/strm_prefix/Jellyfin/deletion thresholds/ignore 规则

## 追加任务：混合调度模式

### Task 6: 常驻 watch 与定时兜底调度

**Files:**
- Create: `src/jellyfin_strm/watch.py`
- Modify: `src/jellyfin_strm/cli.py`
- Modify: `README.md`
- Modify: `docker-compose.nas.example.yml`
- Modify: `tests/test_cli.py`
- Create: `tests/test_watch.py`
- Modify: `tests/test_packaging.py`

- [ ] **Step 1: 写失败测试，锁定 watch 命令与目录快照行为**

```python
def test_module_help_runs():
    result = run(["uv", "run", "python", "-m", "jellyfin_strm", "--help"], capture_output=True, text=True)
    assert "sync" in result.stdout
    assert "watch" in result.stdout
```

```python
def test_watch_iteration_writes_snapshot_and_syncs(tmp_path: Path):
    ...
```

- [ ] **Step 2: 运行 watch 相关测试，确认失败**

Run: `uv run pytest tests/test_cli.py tests/test_watch.py tests/test_packaging.py -v`
Expected: FAIL，因为 watch 命令与快照模块尚未实现。

- [ ] **Step 3: 实现 watch 模块与 CLI 命令**

```python
def run_watch_loop(config: SyncConfig, interval_seconds: int = 30) -> int:
    ...
```

```python
class SnapshotStore:
    def has_changed(self, snapshot: DirectorySnapshot) -> bool:
        ...
```

- [ ] **Step 4: 更新 README 与 compose，补 daily + watch 双服务**

Run: `uv run pytest tests/test_cli.py tests/test_watch.py tests/test_packaging.py -v`
Expected: PASS。

- [ ] **Step 5: 跑完整测试与帮助命令**

Run: `uv run pytest -v`
Expected: PASS。

Run: `uv run python -m jellyfin_strm --help`
Expected: `watch` 与 `sync` 都存在。
