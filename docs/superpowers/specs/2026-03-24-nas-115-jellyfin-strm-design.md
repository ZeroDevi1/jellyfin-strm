# NAS 115 Jellyfin STRM 部署设计

## 背景

当前影音服务器运行在远程 NAS 上，核心组件包括 Jellyfin、MDC 与 MetaTube。现有本地媒体库路径为 `/volume1/Secret/media`，另有 115 网盘通过 CloudDrive 挂载到 `/volume2/CloudNAS/CloudDrive/115open/Secret`。目标是在尽量不触发 115 风控的前提下，将网盘中的媒体以 STRM 形式接入 Jellyfin，同时最大化复用已经整理好的 `.nfo`、海报图、背景图与附属资料目录。

用户的核心偏好为“元数据直用优先”：不希望为了 STRM 接入而重新全量刮削，希望扫描阶段只读取本地小文件，而不是让 Jellyfin 直接遍历 115 挂载目录。

## 目标

- Jellyfin 继续保留本地真实媒体库 `/volume1/Secret/media`
- 新增 115 影子媒体库 `/volume1/Secret/115strm`
- 115 挂载源 `/volume2/CloudNAS/CloudDrive/115open/Secret` 不直接加入 Jellyfin
- 在 `/volume1/Secret/115strm` 中保留与源目录一致的树形结构
- 视频实体不复制，只生成对应 `.strm`
- 现有 `.nfo`、封面图、背景图、字幕和资料目录按原名原层级复制到影子库
- 降低扫库阶段对 115 挂载的直接访问频率

## 非目标

- 当前阶段不优先建设基于 115 开放平台 OAuth 的完整直链/302 播放体系
- 当前阶段不替换 Jellyfin、MDC、MetaTube 的既有职责
- 当前阶段不做与本任务无关的库结构重构

## 现状与约束

### 现有目录

- 本地真实媒体库：`/volume1/Secret/media`
- 115 挂载源：`/volume2/CloudNAS/CloudDrive/115open/Secret`
- 新增影子库：`/volume1/Secret/115strm`

### 元数据形态

源目录中可能同时存在以下内容：

- 视频文件，如 `zzz.mp4`
- 同目录同名的 `.nfo`
- `poster.jpg`、`fanart.jpg`、`thumb.jpg`
- 同名图片，如 `zzz-poster.jpg`
- 字幕文件，如 `.srt`、`.ass`
- 资料目录，如 `behind the scenes`、`extrafanart`、`extrathumbs`

这些内容都应尽量原样保留到影子库中，避免破坏现有刮削成果和 Jellyfin 的 sidecar 识别规则。

## 方案对比

### 方案 A：Auto_Symlink 维护本地影子库（推荐）

做法：以 115 挂载目录作为只读源，由 Auto_Symlink 监控或扫描源目录，在 `/volume1/Secret/115strm` 中生成 `.strm`，并复制 `.nfo`、图片、字幕及附属资料目录。

优点：

- 与“元数据直用优先”目标完全一致
- 与现有 CloudDrive 挂载模式契合，部署成本低
- 工具本身明确支持生成 `strm/软链接`、复制更新元数据、清理无效文件
- Jellyfin 扫描时只读取本地影子库，显著降低直接访问 115 的概率

缺点：

- 仍依赖挂载目录作为事实来源
- 若挂载通知能力有限，可能需要定时扫描补偿

### 方案 B：qmediasync 作为主同步器

做法：使用 qmediasync 直接基于 115 开放平台能力生成 STRM、处理元数据与后续播放联动。

优点：

- 后续扩展到直链、302、联动刷新时能力更强
- 更适合未来逐步摆脱对本地挂载路径的依赖

缺点：

- 需要 115 开放平台账号、OAuth 或其他授权配套
- 首次接入复杂度高于当前需求
- 在“我已有成熟 sidecar 元数据，只想先稳定接入 Jellyfin”这个目标上，不如方案 A 直接

### 方案 C：Jellyfin 直接扫描 115 挂载目录

做法：将 `/volume2/CloudNAS/CloudDrive/115open/Secret` 直接加入 Jellyfin 媒体库。

优点：

- 部署最简单

缺点：

- 扫库、探测媒体信息、抽帧时更容易直接触发 115 访问
- 与“降低风控”和“元数据直用优先”目标冲突
- 排障与性能控制最差

## 推荐方案

采用“两阶段路线”：

1. 第一阶段使用 Auto_Symlink 构建本地影子库 `/volume1/Secret/115strm`
2. Jellyfin 只扫描影子库，而不直接扫描 115 挂载源
3. MDC 与 MetaTube 继续承担补刮削职责，仅在影子库缺失元数据时介入
4. 若后续需要更强的 115 直链/302 播放能力，再评估将 `.strm` 生成端升级为 qmediasync

一句话定义该方案：`115strm` 是 115 媒体目录的本地影子库，保留原目录树与全部元数据，只把视频实体替换成 `.strm`。

### 第一阶段播放链路定稿

第一阶段明确采用“文件路径型 STRM”，而不是 HTTP/302 型 STRM。

- `Jellyfin` 容器内必须额外只读挂载 115 源目录
- 建议挂载为：`/volume2/CloudNAS/CloudDrive/115open/Secret:/mnt/115open/Secret:ro`
- 影子库中的 `.strm` 文件内容写入对应的容器内绝对路径

示例：

源文件：

```text
/volume2/CloudNAS/CloudDrive/115open/Secret/xxx/yyy/zzz.mp4
```

Jellyfin 容器内可见路径：

```text
/mnt/115open/Secret/xxx/yyy/zzz.mp4
```

则目标 `.strm` 内容必须固定写为：

```text
/mnt/115open/Secret/xxx/yyy/zzz.mp4
```

这样可以保证：

- 扫描阶段只读取 `/volume1/Secret/115strm` 中的本地小文件
- 播放阶段 Jellyfin 能在容器内解析 `.strm` 指向的真实视频路径
- 不把 115 源目录直接加入媒体库，但仍保留播放时的只读访问能力

## 逻辑架构

```text
115 挂载源（只读）
/volume2/CloudNAS/CloudDrive/115open/Secret
            |
            v
 Auto_Symlink 同步/监控
 - 生成 .strm
 - 复制 sidecar 元数据
 - 复制附属资料目录
 - 清理失效内容
            |
            v
本地影子库
/volume1/Secret/115strm
            |
            v
Jellyfin 扫描与播放入口

本地真实媒体
/volume1/Secret/media
            |
            v
Jellyfin 现有本地库
```

## 目录与命名规则

### 目录分层

- `/volume1/Secret/media`：本地真实媒体，继续保留给 Jellyfin
- `/volume2/CloudNAS/CloudDrive/115open/Secret`：115 挂载源，只作为同步输入
- `/volume1/Secret/115strm`：115 影子媒体库，作为 Jellyfin 新增库目录

### 影子库同步规则

对于源文件：

```text
/volume2/CloudNAS/CloudDrive/115open/Secret/xxx/yyy/zzz.mp4
/volume2/CloudNAS/CloudDrive/115open/Secret/xxx/yyy/zzz.nfo
/volume2/CloudNAS/CloudDrive/115open/Secret/xxx/yyy/poster.jpg
/volume2/CloudNAS/CloudDrive/115open/Secret/xxx/yyy/extrafanart/*
```

目标影子库应变为：

```text
/volume1/Secret/115strm/xxx/yyy/zzz.strm
/volume1/Secret/115strm/xxx/yyy/zzz.nfo
/volume1/Secret/115strm/xxx/yyy/poster.jpg
/volume1/Secret/115strm/xxx/yyy/extrafanart/*
```

规则如下：

- 视频文件不复制实体，只生成同名 `.strm`
- `.strm` 与 `.nfo` 必须同名同目录
- 目录结构必须与源目录一致
- 所有 sidecar 元数据和资料目录按原名原路径复制
- 删除源文件或源目录时，影子库对应内容也应被清理

### 与现有本地库的冲突处理

- 首发阶段要求本地真实媒体库 `/volume1/Secret/media` 与 115 影子库 `/volume1/Secret/115strm` 尽量避免纳入同一影片的双份来源
- 如果同一影片同时存在于本地库与 115 影子库，优先保留本地真实媒体作为正式纳管来源，115 影子库中的对应目录应通过排除规则跳过生成或在同步后清理
- 推荐按媒体类型拆分 Jellyfin 库，例如 `本地电影`、`本地剧集`、`115电影`、`115剧集`，避免不同来源混入同一个库后产生错误合并或错误识别
- 若过渡期内必须允许重复条目存在，应接受库级重复展示，不以“自动合并”为验收目标
- 首发实现应预留一个排除清单机制，例如 `exclude.txt` 或工具自身的 ignore 规则，用于屏蔽已在本地库存在的目录

## 服务职责划分

### Jellyfin

- 扫描 `/volume1/Secret/media`
- 新增扫描 `/volume1/Secret/115strm`
- 不扫描 `/volume2/CloudNAS/CloudDrive/115open/Secret`
- 优先读取本地 sidecar 元数据
- 额外挂载 `/volume2/CloudNAS/CloudDrive/115open/Secret:/mnt/115open/Secret:ro` 以满足 `.strm` 播放
- 尽量避免激进的自动媒体分析任务

### Auto_Symlink

- 读取 115 挂载源目录
- 在影子库生成 `.strm`
- 复制 `.nfo`、图片、字幕与资料目录
- 维护增量更新与失效清理
- 若原生能力不能完整覆盖资料目录或特殊 sidecar 文件，必须由旁路同步脚本补齐，且该旁路属于第一阶段范围

### MDC / MetaTube

- 保持现有刮削链路
- 仅在影子库缺失元数据时补充写入
- 不作为当前阶段 STRM 生成的主方案

### qmediasync

- 当前阶段不作为主流程工具
- 作为后续增强方案，适用于 115 开放平台直链/302 播放需求

## Compose 调整原则

### Jellyfin

Jellyfin 容器应保持对以下目录的挂载访问：

- `./jellyfin/config:/config`
- `./jellyfin/cache:/cache`
- `/volume1/Secret:/mnt/Secret`
- `/volume2/CloudNAS/CloudDrive/115open/Secret:/mnt/115open/Secret:ro`

同时，Jellyfin 媒体库中新增一个指向 `/mnt/Secret/115strm` 的库路径，现有 `/mnt/Secret/media` 继续保留。

### 新增 Auto_Symlink 服务

Auto_Symlink 服务需要满足：

- 容器内能读取 `/volume2/CloudNAS/CloudDrive/115open/Secret`
- 容器内能写入 `/volume1/Secret/115strm`
- 使用绝对路径映射，避免生成无效链接或错误路径
- 如果依赖 CloudDrive 的挂载传播能力，需要按文档处理 `rslave` 或 shared mount 设置
- `.strm` 的目标路径生成规则必须与 Jellyfin 容器内的 `/mnt/115open/Secret` 保持一致

## 首发实现边界

### Auto_Symlink 与旁路同步脚本的职责边界

- Auto_Symlink 负责主流程：扫描 115 挂载源、识别视频实体、生成 `.strm`、处理基础增删改事件
- 旁路同步脚本负责补齐非视频实体：`.nfo`、图片、字幕、资料目录，以及 Auto_Symlink 无法完整覆盖的特殊 sidecar
- 两者共享同一套源路径与目标路径映射规则，均以“源相对路径 -> 影子库相对路径”为唯一主键，保证幂等
- 首发推荐执行顺序固定为：`Auto_Symlink` 先完成 `.strm` 更新，再由旁路同步脚本补齐 sidecar 和资料目录，最后再触发 Jellyfin 刷新
- 若 Auto_Symlink 已原生复制某些 sidecar，旁路脚本仍允许再次覆盖写入；覆盖视为幂等行为，不应造成重复文件或异常失败

### 旁路同步脚本的输入输出与失败策略

- 输入：115 源根目录、影子库根目录、视频后缀清单、sidecar 白名单、目录黑名单、排除清单
- 输出：新增/更新/删除摘要日志、异常日志、待刷新标记
- 同步脚本必须先执行源根目录健康检查；当源根目录不可读、空挂载、文件数异常骤减时，只允许告警并退出，不允许删除影子库内容
- 删除动作必须在健康检查通过后才允许执行，并受“删除比例阈值”保护
- 同步脚本失败时，不回滚已成功生成的 `.strm`，而是记录失败项并在下一轮重试；避免因为局部失败影响整个影子库可用性

## 同步矩阵

### 视频文件

- 匹配视频后缀时，不复制实体文件
- 在影子库生成同名 `.strm`
- `.strm` 内容固定为 Jellyfin 容器内可见的绝对路径，例如 `/mnt/115open/Secret/.../zzz.mp4`

### 必须复制的 sidecar 文件

- `.nfo`
- `poster.*`
- `fanart.*`
- `thumb.*`
- `clearlogo.*`
- `logo.*`
- `banner.*`
- 同名图片，如 `zzz-poster.*`、`zzz-fanart.*`
- 字幕文件，如 `.srt`、`.ass`、`.ssa`、`.sub`、`.idx`、`.sup`
- 其他与视频同目录、且属于元数据展示用途的小文件

### 必须递归复制的资料目录

- `behind the scenes`
- `extrafanart`
- `extrathumbs`
- `featurettes`
- `deleted scenes`
- `trailers`

### 未知目录处理

- 默认策略为保守保留：对于视频目录下除视频实体外的非临时目录，默认递归复制到影子库
- 仅排除明显无关或缓存目录，例如转码缓存、下载中间目录、系统隐藏临时目录
- 若 Auto_Symlink 无法直接支持该策略，则由旁路同步脚本负责“复制所有非视频实体内容”

### 未知目录复制细则

- 白名单优先复制：`extrafanart`、`extrathumbs`、`behind the scenes`、`featurettes`、`deleted scenes`、`trailers`
- 黑名单默认排除：`.@__thumb`、`.DS_Store`、`Thumbs.db`、`@eaDir`、`$RECYCLE.BIN`、`System Volume Information`、下载缓存目录、转码缓存目录、BT/下载客户端临时目录
- 未命中白名单、也未命中黑名单的未知目录，若目录内文件主要为图片、字幕、文本、NFO 等小文件，则允许复制
- 未知目录若包含压缩包、磁盘镜像、大体积样片、下载残片或单目录总体积超过预设阈值（首发建议 200 MB），则不自动复制，只记录告警等待人工确认
- 阈值与黑白名单应作为配置项，而不是写死在脚本中

## Jellyfin 刷新机制

### 首发推荐机制

- 小范围验证阶段：每次同步后由人工在 Jellyfin 中仅刷新 `115strm` 对应库，确认目录映射、元数据和播放链路正确
- 稳定运行阶段：由旁路同步脚本在成功完成一次同步批次后，通过 Jellyfin API 触发一次 `115strm` 库刷新
- 刷新触发必须带防抖/节流；首发建议同一库 10 分钟内最多触发 1 次，避免连续小变更造成高频重扫
- 若 NAS 环境暂时不方便接 Jellyfin API，则退化为低频计划刷新 `115strm` 库；该退化模式只作为临时措施，不作为满足 10 分钟可见性的推荐实现

### 刷新与验收时限的对应关系

- 小目录增量变化：同步批次完成后 5 分钟内写入待刷新标记，10 分钟内完成一次库刷新
- 单个条目的元数据替换：旁路同步脚本完成覆盖写入后，依靠同一轮刷新机制在 10 分钟内可见
- 删除同步：删除动作完成后必须在同一轮或下一轮节流窗口内触发库刷新，确保 15 分钟内完成条目清理展示

### 覆盖与时间戳策略

- 同名文件默认覆盖更新
- 新文件新增，缺失文件删除
- 若工具支持，优先保留源文件修改时间，便于排障与审计
- 若工具不支持保留时间戳，不阻塞首发，但必须保证内容一致

## 数据流

### 入库流

1. 新文件出现在 `/volume2/CloudNAS/CloudDrive/115open/Secret`
2. Auto_Symlink 发现变化
3. 为视频生成 `.strm`
4. Auto_Symlink 与旁路同步脚本共同完成 `.nfo`、海报、背景图、字幕和资料目录同步到 `/volume1/Secret/115strm`
5. Jellyfin 扫描 `/volume1/Secret/115strm`
6. Jellyfin 基于本地 sidecar 元数据完成识别与展示

### 删除流

1. 源目录中的视频或资料被删除
2. Auto_Symlink 清理影子库中的对应 `.strm` 与 sidecar 内容
3. Jellyfin 在后续扫描中移除或更新对应条目

### 更新与重命名流

1. 源目录中的视频改名、目录改名或 sidecar 文件被替换
2. Auto_Symlink 或旁路同步脚本根据新路径重建影子库对应结构
3. 旧 `.strm`、旧海报、旧字幕和失效目录被清理
4. Jellyfin 对 `115strm` 库执行一次受节流保护的库刷新，避免长期残留旧条目

以下更新场景必须被视为首发范围：

- 视频文件改名
- 目录改名
- `.nfo` 内容更新
- 海报或背景图替换
- 字幕新增、删除、替换
- `behind the scenes`、`extrafanart` 等资料目录的局部变化

### 补刮削流

1. 某条目缺失 `.nfo` 或图片
2. MDC / MetaTube 对该条目补刮削
3. 补充产物写入影子库
4. Jellyfin 刷新后使用新的 sidecar 数据

## 错误处理与风险控制

### 风控与访问控制

- 严禁让 Jellyfin 直接扫描 115 挂载源
- 首次导入时先小范围验证若干目录，再逐步扩展
- 对 `115strm` 新建库禁用或限制以下能力：自动章节图、预览图、首次深度媒体分析、激进实时监控
- 首次建库采用手动小批量刷新，验证通过后再启用计划刷新
- 计划刷新应优先由同步工具通知或低频定时触发，避免高频全库重扫

### Jellyfin 最小配置清单

- `115strm` 应单独建库，不与现有本地库共用同一个库定义
- 优先启用本地元数据读取能力，包括 `.nfo`、本地图片、字幕 sidecar
- 关闭或限制实时文件系统监控，改用手动刷新或低频计划刷新
- 关闭自动章节图、预览缩略图、激进的媒体分析任务，避免 Jellyfin 为生成附加数据而主动深度探测 `.strm` 指向源文件
- 首发阶段不以自动提取在线元数据为主，缺失项优先交给 MDC / MetaTube 补齐后再刷新

### 同步异常

- 如果 Auto_Symlink 漏检变化，应增加定时全量校正任务
- 如果某些特殊资料目录未被默认复制，需要在工具配置中显式补充包含规则
- `.strm` 内容必须固定指向 Jellyfin 容器内可见路径 `/mnt/115open/Secret/...`

### 挂载异常保护

- 同步前必须检查 115 源根目录是否可访问，且不是空挂载状态
- 增加最小文件数或最小目录数阈值；若源目录数量异常骤降，则拒绝执行批量清理
- 增加删除比例阈值；当单次计划删除比例超过阈值时，仅告警、不执行删除
- CloudDrive 未就绪、目录为空、读取失败时，只允许记录日志与告警，不允许清空影子库
- 如工具支持，增加人工确认开关或 dry-run 模式用于首次大规模删除前审查

### 安全

- Compose 中出现的明文口令应迁移到 `.env` 或 NAS 机密管理方式
- 当前暴露过的 `MDC_PASSWORD` 应立即轮换

## 验证与测试计划

### 小范围验证

- 选取 1 到 2 个电影目录同步到 `/volume1/Secret/115strm`
- 确认生成 `.strm`
- 检查 `.strm` 文件内容是否为 `/mnt/115open/Secret/...` 容器内绝对路径
- 确认 `.nfo`、`poster.jpg`、`fanart.jpg`、字幕与 `extrafanart` 等目录被复制
- 进入 Jellyfin 容器确认 `.strm` 指向的真实视频路径可访问
- 在 Jellyfin 中验证展示信息与图片是否正确
- 实测播放是否能从 `.strm` 正常拉起

### 扩大量验证

- 选取包含多层目录、中文路径、特殊资料目录的样本
- 验证增量更新、删除同步与重扫库结果
- 观察 115 挂载侧是否仍出现异常高频读取
- 模拟挂载失效或空目录返回，确认不会触发影子库大规模误删

### 最终验收标准

- Jellyfin 只扫描本地影子库，不直接扫描 115 挂载源
- 现有 sidecar 元数据能够被复用，不需要全量重刮削
- `behind the scenes`、`extrafanart` 等资料目录被按原名原层级保留
- `.strm` 内容与 Jellyfin 容器内只读挂载路径一致，并可实际播放
- 挂载失效、空目录或异常骤减时不会触发全库误删
- 新增、删除、修正条目后，影子库与 Jellyfin 展示状态能在可接受时间内同步

### 可接受时间阈值

- 小目录增量变化：5 分钟内完成同步并可手动刷新识别
- 单个条目的元数据替换：10 分钟内在 Jellyfin 中可见
- 删除同步：15 分钟内完成影子库清理，且不发生误删
- 手动刷新仅用于小范围验证阶段；进入稳定运行后，应以 API 触发或低频计划刷新满足上述时限

## 后续演进

- 当需要 115 直链/302 播放、更多联动刷新能力时，评估引入 qmediasync
- 若 Auto_Symlink 在某些资料目录、字幕或命名规则上存在短板，可补充自定义同步脚本作为旁路增强
- 若未来希望统一管理本地媒体与 115 影子媒体，可再设计上层媒体目录编排方案，但不纳入当前阶段
