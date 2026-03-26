# jellyfin-strm

为 NAS 上的 Jellyfin 构建 115 网盘影子库的首发同步器。

工具目标：

- 只让 Jellyfin 扫描本地影子库
- 为视频文件生成 `.strm`
- 复用现有 `.nfo`、海报、背景图、字幕与资料目录
- 为兼容影子库内独立维护的元数据，不主动删除既有文件
- 可选触发一次带节流的 Jellyfin 刷新

## 目录模型

```text
源目录（CloudDrive/115 挂载，只读）
/volume2/CloudNAS/CloudDrive/115open/Secret

影子库（本地）
/volume1/Secret/115strm

Jellyfin 容器内源路径
/mnt/115open/Secret
```

示例：

```text
源文件:
/volume2/CloudNAS/CloudDrive/115open/Secret/电影A/movie.mp4

生成的影子文件:
/volume1/Secret/115strm/电影A/movie.strm
```

`.strm` 文件内容必须写成 Jellyfin 容器内可见的真实路径：

```text
/mnt/115open/Secret/电影A/movie.mp4
```

## 快速开始

1. 本地开发安装依赖

```bash
uv sync --dev
```

2. 复制示例配置并按 NAS 路径修改

```bash
cp config.example.yaml config.yaml
```

3. 先做 dry-run

```bash
uv run jellyfin-strm sync --config config.yaml --dry-run
```

4. 确认摘要无误后再执行正式同步

```bash
uv run jellyfin-strm sync --config config.yaml
```

5. 如果希望常驻监听目录变化，可以运行：

```bash
uv run jellyfin-strm watch --config config.yaml --interval 30
```

## Docker 镜像

项目会通过 GitHub Actions 在 `push main` 和手动触发时自动构建并推送：

```text
ghcr.io/zerodevi1/jellyfin-strm:latest
ghcr.io/zerodevi1/jellyfin-strm:sha-<shortsha>
```

如果你是在 NAS 上运行，优先直接拉 GHCR 镜像，而不是在 NAS 宿主机安装 Python 环境。

```bash
docker pull ghcr.io/zerodevi1/jellyfin-strm:latest
```

`docker-compose` 用法可以参考 [docker-compose.nas.example.yml](./docker-compose.nas.example.yml)。

## 运行原则

- `source_root` 指向 115 挂载根目录，只读
- `shadow_root` 指向本地影子库，可写
- `strm_prefix` 必须是 Jellyfin 容器里访问源目录的绝对路径
- 同步只增量写入 `.strm` 与源目录 sidecar，不主动删除影子库既有内容
- Jellyfin 刷新是可选能力，默认可关闭
- `watch` 每轮只做轻量目录快照比较，只有检测到变化才触发正式同步
- 源挂载异常时，`watch` 只告警，不会覆盖快照

## 调度模式

推荐同时保留两种运行方式：

- `watch`
  - 常驻轮询，默认每 30 秒检查一次目录快照
  - 检测到新增、删除、改名、海报替换等变化后立即重新执行同步
- `sync`
  - 一次执行型
  - 适合每天跑一次做兜底校准，防止长期运行时的漏检或挂载抖动

也就是说：

- 平时靠 `watch` 跟进变更
- 每天再跑一次 `sync` 做全量校准

## 纯 Docker 自动调度

如果你不想依赖 DSM 任务计划，可以直接在 `docker-compose` 里加 `ofelia`。

当前示例已经包含三类服务：

- `strm-sync-watch`
  - 常驻监听，每 30 秒轮询一次
- `strm-sync-daily`
  - 作为 `ofelia` 的执行目标容器，保持运行但不主动同步
- `ofelia`
  - 通过 Docker label 每天执行一次 `jellyfin-strm sync --config /config/config.yaml`

这里采用的是 Ofelia 官方推荐的 `job-exec` 标签方式：

- `ofelia.enabled=true`
- `ofelia.job-exec.daily-sync.schedule="@daily"`
- `ofelia.job-exec.daily-sync.command="jellyfin-strm sync --config /config/config.yaml"`

Ofelia 官方文档说明了两点：

- `job-exec` 会在一个“正在运行的容器”里执行命令
- 可以通过 `--docker-filter` 限制只读取当前 compose project 的容器标签

所以示例里 `strm-sync-daily` 会保持空转，专门供 `ofelia` 定时 `docker exec` 进去执行每日校准。

## Compose 示例

可以参考 [docker-compose.nas.example.yml](./docker-compose.nas.example.yml) 把同步器接入现有 NAS 栈。
