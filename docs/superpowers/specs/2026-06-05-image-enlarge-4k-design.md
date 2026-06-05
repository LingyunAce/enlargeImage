# 低分辨率图片扩展到 4K — 设计文档

- **日期**: 2026-06-05
- **状态**: 设计稿(待评审)
- **作者**: brainstorming 会话产出

## 1. 目标与范围

提供 Web 端能力:用户上传低分辨率图片,服务端用 SwinIR 进行超分辨率,切片推理 + 拼接融合,输出放大后的图片。

### 1.1 使用形态

Web 应用(浏览器 → Next.js 前端 → FastAPI 后端)。无登录,保留最近 20 条历史。

### 1.2 输入输出

- **输入**: `png` / `jpg` / `jpeg` / `webp`,长边 ≤ 2000px,文件 ≤ 20MB
- **缩放**: 用户在上传时选择 `2x` / `4x` / `8x`
- **输出**: PNG 编码的长边放大后的图片(保持原图纵横比)

### 1.3 推理环境

CPU + PyTorch 真实 SwinIR 模型,启动时加载一次,所有请求复用。

### 1.4 范围外

- 用户账号体系
- 任务持久化跨进程(进程内 + SQLite 即可)
- 多 worker 集群
- 视频超分
- 客户端侧(浏览器内)推理
- 多 GPU 调度

## 2. 总体架构

```
┌─────────────────┐     HTTP/JSON      ┌──────────────────────┐
│  Next.js 前端   │ ─────────────────► │  FastAPI 后端        │
│  (App Router)   │ ◄───────────────── │  + SwinIR 推理进程   │
│                 │   1s 轮询进度      │                      │
└─────────────────┘                    │  ┌────────────────┐  │
                                       │  │ JobManager     │  │
                                       │  │  (asyncio)     │  │
                                       │  └────────────────┘  │
                                       │  ┌────────────────┐  │
                                       │  │ SwinIRRunner   │  │
                                       │  │  (torch 模型)  │  │
                                       │  └────────────────┘  │
                                       │  ┌────────────────┐  │
                                       │  │ Pipeline       │  │
                                       │  │  Tiler→Run→Blend│  │
                                       │  └────────────────┘  │
                                       │  ┌────────────────┐  │
                                       │  │ JobStore       │  │
                                       │  │  (SQLite)      │  │
                                       │  └────────────────┘  │
                                       │  ┌────────────────┐  │
                                       │  │ FileStore      │  │
                                       │  │  (本地磁盘)    │  │
                                       │  └────────────────┘  │
                                       └──────────────────────┘
```

## 3. 目录结构

```
EnlargeImage/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI 入口、路由挂载
│   │   ├── config.py            # 配置(模型路径、tile 大小、存储路径)
│   │   ├── models/
│   │   │   ├── job.py           # JobStatus 枚举、JobDTO
│   │   │   └── swinir.py        # SwinIR 网络定义(从官方实现移植)
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── tiler.py         # 切分/合并策略
│   │   │   ├── runner.py        # SwinIRRunner:加载模型、推理单块
│   │   │   ├── seam.py          # SeamBlender:重叠区域线性融合
│   │   │   └── orchestrator.py  # Pipeline:组合 tiler/runner/blender
│   │   ├── services/
│   │   │   ├── job_manager.py   # 任务状态机、并发控制
│   │   │   ├── job_store.py     # SQLite 持久化
│   │   │   └── file_store.py    # 输入/输出文件管理
│   │   └── api/
│   │       ├── jobs.py          # POST /jobs, GET /jobs, GET /jobs/{id}
│   │       └── files.py         # GET /jobs/{id}/output
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_tiler.py
│   │   ├── test_seam.py
│   │   ├── test_pipeline.py
│   │   ├── test_runner.py
│   │   ├── test_job_manager.py
│   │   ├── test_job_store.py
│   │   ├── test_api.py
│   │   └── fixtures/
│   │       ├── small.png
│   │       ├── medium.png
│   │       └── odd.png          # 513x513,非整除
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # 上传页(单页应用)
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── Uploader.tsx
│   │   ├── ProgressPanel.tsx
│   │   ├── HistoryList.tsx
│   │   └── CompareViewer.tsx
│   ├── lib/
│   │   ├── api.ts               # fetch 封装
│   │   └── types.ts             # 与后端 DTO 对齐的 TS 类型
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.js
├── storage/                     # 运行时文件(已在 .gitignore)
├── data.db                      # SQLite(已在 .gitignore)
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-06-05-image-enlarge-4k-design.md
├── .gitignore
└── README.md
```

## 4. 数据流

### 4.1 端到端时序

```
用户             前端              FastAPI              JobManager          Pipeline             SwinIRRunner        JobStore/FileStore
 │  选择文件     │                  │                      │                    │                      │                    │
 │──────────────►│                  │                      │                    │                      │                    │
 │               │ POST /jobs       │                      │                    │                      │                    │
 │               │ (multipart)      │                      │                    │                      │                    │
 │               │─────────────────►│ 解析文件             │                    │                      │                    │
 │               │                  │ 创建 job_id          │                    │                      │                    │
 │               │                  │─────────────────────►│                    │                      │                    │
 │               │                  │                      │ 写 row(status=queued) │                    │                    │
 │               │                  │───────────────────────────────────────────────────────────────────────────────────────►│
 │               │                  │ 返回 201 {id, status:queued}             │                    │                    │
 │               │◄─────────────────│                      │                    │                      │                    │
 │               │                  │                      │                    │                      │                    │
 │               │                  │ create_task          │                    │                      │                    │
 │               │                  │─────────────────────►│                    │                      │                    │
 │               │                  │                      │ update(running,    │                    │                    │
 │               │                  │                      │   stage="tiling")  │                    │                    │
 │               │                  │                      │──────────────────────────────────────────────────────►│
 │               │                  │                      │                    │                    │                    │
 │               │ GET /jobs/{id}   │                      │                    │                      │                    │
 │               │─────────────────►│ 查 row               │                    │                      │                    │
 │               │◄─────────────────│                      │                    │                      │                    │
 │               │                  │                      │                    │                      │                    │
 │               │                  │ 持续更新 stage 进度  │                    │                      │                    │
 │               │                  │                      │ callback(0.05)     │                    │                    │
 │               │                  │                      │  ──tiling────────► │                      │                    │
 │               │                  │                      │                    │ 切出 N 块            │                    │
 │               │                  │                      │                    │                      │                    │
 │               │                  │                      │ callback(0.10)     │                    │                    │
 │               │                  │                      │  ──inference─────► │                      │                    │
 │               │                  │                      │                    │ for tile in tiles:   │                    │
 │               │                  │                      │                    │   ──────────────────► │ model(tile)         │
 │               │                  │                      │                    │                      │ ── 5-30s/tile        │
 │               │                  │                      │ callback(0.10+0.85*(i/N))                  │                    │
 │               │                  │                      │                    │                      │                    │
 │               │                  │                      │ callback(0.95)     │                    │                    │
 │               │                  │                      │  ──blending──────► │                      │                    │
 │               │                  │                      │                    │ Seam 融合           │                    │
 │               │                  │                      │                    │ 写 output.png        │                    │
 │               │                  │                      │                    │────────────────────────────────────────────────►│
 │               │                  │                      │ update(done, 100%) │                    │                    │
 │               │                  │                      │──────────────────────────────────────────────────────►│
 │               │                  │                      │                    │                      │                    │
 │               │ GET /jobs/{id}   │                      │                    │                      │                    │
 │               │─────────────────►│ 查 row               │                    │                      │                    │
 │               │◄─────────────────│ status=done, output_url                │                      │                    │
 │               │                  │                      │                    │                      │                    │
 │               │ 下载 / 显示对比  │                      │                    │                      │                    │
```

### 4.2 切片 → 推理 → 拼接 的内部数据流

```
原图 (H, W, C)                          scale (2/4/8)
   │
   ▼
┌──────────────────────────────────────────────────────────┐
│ Tiler.tile(image, tile_size=192, overlap=24, scale)      │
│   返回: List[TileRequest]                                │
│     TileRequest { x, y, w, h, scale, out_w, out_h }      │
└──────────────────────────────────────────────────────────┘
   │
   ▼
for req in tiles:
   ┌──────────────────────────────────────────┐
   │ SwinIRRunner.infer(req)                  │
   │   输入 (1, C, h, w)                      │
   │   输出 (1, C, h*scale, w*scale)         │
   └──────────────────────────────────────────┘
   │
   ▼
   TileResult { x_out, y_out, w_out, h_out, pixels }
   │
   ▼
┌──────────────────────────────────────────────────────────┐
│ SeamBlender.blend(results, orig_h*scale, orig_w*scale)   │
│   用重叠区的线性 alpha 权重累积                          │
│   归一化 → 输出大图                                       │
└──────────────────────────────────────────────────────────┘
   │
   ▼
output (H*scale, W*scale, C) → 编码 PNG
```

## 5. 关键模块接口

### 5.1 `SwinIRRunner` (`backend/app/pipeline/runner.py`)

负责加载模型和单块推理。**只跟 numpy/torch 张量打交道,不接触文件**。

```python
class SwinIRRunner:
    def __init__(self, model_path: str, device: str = "cpu") -> None: ...
    def warmup(self) -> None: ...     # 用 1 张 dummy 图跑一次,避免首次请求卡顿
    @property
    def scale(self) -> int: ...       # 模型 scale(读取权重元数据得到)
    def infer(self, image: np.ndarray) -> np.ndarray: ...
        # image: (H, W, 3) uint8, RGB
        # 返回: (H*scale, W*scale, 3) uint8
```

**约束**:
- 同一个 Runner 实例在所有请求间复用(PyTorch 模型加载慢,不能每次新建)
- 用 `threading.Lock` 保护 `infer` —— 避免多线程并发推理
- `image` 进来时做 RGB 校验、归一化到 [0,1]、chw 排列
- 输出反归一化、chw→hwc、clip 到 [0,255]、uint8

### 5.2 `Tiler` (`backend/app/pipeline/tiler.py`)

**纯函数**,不依赖 torch。

```python
@dataclass(frozen=True)
class TileRequest:
    x: int            # 原图坐标系
    y: int
    w: int            # tile 大小(原图)
    h: int
    out_w: int        # = w * scale
    out_h: int        # = h * scale

class Tiler:
    def __init__(self, tile_size: int, overlap: int) -> None: ...
    def split(self, image: np.ndarray, scale: int) -> list[TileRequest]:
        # 把 (H, W, C) 切成 N 个请求
        # 算法: 在 [0, W] 上以 step = tile_size - overlap 滑窗,
        #       头尾 tile 可能 < tile_size(自动裁到实际尺寸)
    def expected_count(self, h: int, w: int) -> int:
        # 不实际切,只算块数(用于进度条 total)
```

### 5.3 `SeamBlender` (`backend/app/pipeline/seam.py`)

```python
class SeamBlender:
    def blend(
        self,
        results: list[tuple[TileRequest, np.ndarray]],  # (req, tile_pixels)
        canvas_h: int,
        canvas_w: int,
    ) -> np.ndarray:
        # 输出 (canvas_h, canvas_w, 3) uint8
```

**算法**: 累积权重图。
- 每个 tile 在自己区域内权重 = 1.0
- 在**重叠区**与邻居 tile 拼接时,用线性 alpha 渐变(进入重叠区时从 0 升到 1,出重叠区时从 1 降到 0)避免硬边
- 最终 `canvas = sum(tile * weight) / sum(weight)`,用 uint16 累加避免溢出

### 5.4 `Pipeline` (`backend/app/pipeline/orchestrator.py`)

**纯编排器**,持有 Tiler + Runner + SeamBlender,不含任何状态。

```python
@dataclass
class ProgressEvent:
    stage: Literal["tiling", "inference", "blending", "encoding"]
    current: int         # 当前块索引(0..total)
    total: int           # 总块数

class Pipeline:
    def __init__(self, runner: SwinIRRunner, tiler: Tiler, blender: SeamBlender) -> None: ...
    def run(
        self,
        image: np.ndarray,
        scale: int,
        on_progress: Callable[[ProgressEvent], None],
    ) -> np.ndarray:
        # scale 仅做断言(必须等于 runner.scale)
        # 进度事件通过 on_progress 上报
        # 返回最终大图
```

**约束**:`Pipeline` 不感知 `JobManager` —— 它是纯函数式调用,JobManager 调它并通过 callback 上报进度。

### 5.5 `JobManager` (`backend/app/services/job_manager.py`)

**有状态**,负责状态机和并发。

```python
class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"

@dataclass
class Job:
    id: str
    status: JobStatus
    stage: str | None          # 同步 ProgressEvent.stage
    progress: float            # 0..1
    scale: int
    input_path: str
    output_path: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

class JobManager:
    def __init__(self, store: JobStore, file_store: FileStore, pipeline: Pipeline) -> None: ...
    async def create(self, input_path: str, scale: int) -> Job: ...
    def get(self, job_id: str) -> Job | None: ...
    def list_recent(self, limit: int = 20) -> list[Job]: ...
    async def start(self, job: Job) -> None:
        # 用 asyncio.create_task 启动后台处理
        # 内部把同步 pipeline.run 丢到 run_in_executor
        # 通过 on_progress callback 更新 store
    async def cancel(self, job_id: str) -> bool: ...
    async def delete(self, job_id: str) -> bool:
        # 任意状态都可调:
        # - running 状态: 设取消标志(同 cancel),轮询/事件等待任务转 canceled 后再 store.delete + file_store.delete_job
        # - 其他状态: 立即 store.delete + file_store.delete_job
        # 返回是否成功删除
    def trim(self, keep: int) -> int:
        # 保留最近 keep 条,其余全部走 delete() 流程
        # 防御性:如果候选列表里夹带 running/queued 状态(理论上不会,queued 几秒内转 running),
        # 跳过这些,只删 done/failed/canceled
        # 返回实际删除的数量
    async def startup_reap_ghosts(self) -> int:
        # 启动时调用,扫表把 status=queued/running 的 row 标记为 failed (error="server_restart")
        # 返回处理数量
        # 文件保留(供排查),仅改 row 状态
```

**并发**: 一个 `asyncio.Semaphore(1)`,同一时刻只跑一个推理任务(避免 CPU 满载 OOM),其他排队的 `create` 直接 `status=queued` 入库。`queued` 任务在 `running` 转 `done`/`failed`/`canceled` 之后**自动启动下一个**,按 `created_at` 升序。

### 5.6 `JobStore` (`backend/app/services/job_store.py`)

```python
class JobStore:
    def __init__(self, db_path: str) -> None: ...   # 启动时建表
    def upsert(self, job: Job) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def list_recent(self, limit: int) -> list[Job]: ...
    def delete(self, job_id: str) -> None: ...      # 只删 row,不碰文件
    def list_ids_older_than(self, keep: int) -> list[str]: ...
        # 返回应被 trim 删除的 job_id 列表(按 created_at 升序,跳过前 keep 条)
        # 实际删除由 JobManager.trim 协调 store.delete + file_store.delete_job
    def mark_stale_as_failed(self, reason: str) -> int:
        # 把所有 status IN (queued, running) 的 row 改为 failed 并写入 reason
        # 返回受影响行数(用于启动清理幽灵任务)
```

### 5.7 `FileStore` (`backend/app/services/file_store.py`)

```python
class FileStore:
    def __init__(self, root: str) -> None: ...      # root = ./storage
    def new_job_dir(self) -> tuple[str, str]: ...   # (job_id, path)
    def path(self, job_id: str, name: str) -> str: ...
    def delete_job(self, job_id: str) -> None: ...
```

## 6. HTTP API

| 方法 | 路径 | 入参 | 出参 |
|---|---|---|---|
| POST | `/api/jobs` | multipart: file, form: scale | 201 `{id, status}` |
| GET | `/api/jobs` | query: limit=20 | `Job[]` |
| GET | `/api/jobs/{id}` | — | `Job` |
| GET | `/api/jobs/{id}/output` | — | image/png (流式) |
| DELETE | `/api/jobs/{id}` | — | 204 |
| GET | `/api/health` | — | `{ok: true}` |

`GET /api/jobs/{id}` 响应:

```json
{
  "id": "01HX...",
  "status": "running",
  "stage": "inference",
  "progress": 0.42,
  "scale": 4,
  "error": null,
  "createdAt": "2026-06-05T10:23:11Z",
  "updatedAt": "2026-06-05T10:23:48Z"
}
```

`GET /api/jobs/{id}/output`:
- `status=done` → 返回 `image/png` 流(`Content-Disposition: attachment; filename="enlarged-{id}.png"`)
- 其他状态 → `409 Conflict` + 描述

## 7. 任务与进度协议

### 7.1 状态机

```
            create()
   (new) ─────────────► QUEUED
                           │
                  acquire semaphore
                           │
                           ▼
                        RUNNING ──── 失败 ──► FAILED
                           │
                  所有 stage 完成
                           │
                           ▼
                         DONE

   *任何状态都可经 DELETE → (清理文件 + 删 row)
   *RUNNING 时收到 cancel() → 协作式取消(下个 tile 边界检查标志位)→ CANCELED
```

### 7.2 进度计算公式

进度是 **0.0 ~ 1.0** 的浮点数。前端轮询直接拿这个值,转成百分比展示。

```
总预算分配:
  tiling    : 0.00 ~ 0.05   (切完一次性推进)
  inference : 0.05 ~ 0.90   (按 (i+1)/N 线性推进)
  blending  : 0.90 ~ 0.97
  encoding  : 0.97 ~ 1.00
  done      : 1.00
```

```python
def on_progress(ev: ProgressEvent):
    if ev.stage == "tiling":
        p = 0.05
    elif ev.stage == "inference":
        p = 0.05 + 0.85 * (ev.current / ev.total)
    elif ev.stage == "blending":
        p = 0.90
    elif ev.stage == "encoding":
        p = 0.97
    job_manager.update_progress(job_id, stage=ev.stage, progress=p)
```

### 7.3 进度更新频率控制

后端不每次 callback 都写 SQLite —— 太慢。**用内存中的 `Job` 对象缓存 + 节流**:

```python
class JobManager:
    def __init__(...):
        self._cache: dict[str, Job] = {}     # 内存缓存
        self._dirty: set[str] = set()         # 待写盘
        self._flush_interval = 0.5            # 0.5s 一次

    def update_progress(self, job_id, stage, progress):
        # 更新 _cache
        # 标记 dirty
        # 不直接写 SQLite

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(self._flush_interval)
            for jid in list(self._dirty):
                self._store.upsert(self._cache[jid])
                self._dirty.discard(jid)
```

- 进度是高频读、聚合写
- 状态转换(QUEUED→RUNNING→DONE/FAILED)必须**立即同步写盘**,不延迟
- `list_recent` 和 `get` 都先查 cache,miss 再查 SQLite

### 7.4 前端轮询策略

```ts
// lib/api.ts (伪代码)
async function pollJob(id: string, signal: AbortSignal): Promise<Job> {
  while (true) {
    const job = await fetchJob(id, signal);
    if (job.status === 'done' || job.status === 'failed' || job.status === 'canceled') {
      return job;
    }
    await sleep(1000, signal);
  }
}
```

- 1000ms 间隔(简单可靠的约定)
- 页面卸载 / 切换时 `AbortController.abort()` 取消
- 失败/网络错误:重试 3 次,再失败显示 toast,保留 lastKnownJob

### 7.5 取消语义

- `DELETE /api/jobs/{id}` 在 `RUNNING` 时设 `_cancel_flags[job_id] = True`
- Pipeline 在每块推理**之后**检查标志;若置位则抛 `CanceledError`,JobManager 转 `CANCELED`,删除输出文件
- 已经 `DONE` / `FAILED` 的 `DELETE` 走清理路径

## 8. 错误处理与边界情况

### 8.1 输入校验(API 入口层)

```
文件上传
  │
  ├─ 格式不在白名单 ─────────────► 415 {"error":"unsupported_format", "got":"gif"}
  ├─ 字节数 > 20MB ──────────────► 413 {"error":"file_too_large"}
  ├─ 解码失败 / 图像损坏 ─────────► 400 {"error":"decode_failed"}
  ├─ 像素数 > 2000*2000 ─────────► 413 {"error":"image_too_large", "max_pixels":4000000}
  ├─ 通道数 != 3 (灰度 / RGBA) ──► 自动转 RGB(灰度复制三通道;RGBA 丢 alpha,白底合成)
  └─ 通过 ──────────────────────► 创建 job
```

### 8.2 运行时异常分类

| 异常源 | 类别 | 用户看到 | 后端动作 |
|---|---|---|---|
| 模型加载失败(权重缺失/版本不匹配) | `StartupError` | `/api/health` 返回 503 | 启动时单次加载,失败则 process exit(让 systemd/k8s 知道) |
| 单块推理 OOM(罕见,CPU 也会内存爆) | `InferenceOOM` | 500 `{"error":"out_of_memory","at_tile":N}` | 标记 FAILED,保留 input 供重试 |
| PIL/Pillow 编码失败 | `EncodeError` | 500 `{"error":"encode_failed"}` | 同上 |
| 取消 | `CanceledError` | 204(无 body) | 转 CANCELED |
| 未知异常 | `Exception` | 500 `{"error":"internal","trace_id":...}` | 写日志,转 FAILED,保留 trace_id 便于排查 |

**关键原则**: **永远不要把 Python traceback 透出给前端** —— 任何 unhandled 都走一个统一的 `internal_error_handler`,把异常 message 落到后端日志,前端只拿 trace_id。

### 8.3 资源耗尽场景

- **磁盘满**:写 output 前 `try: f.write(...) except OSError: → FAILED`
- **CPU 长时间没响应**(理论上不会,但保险):前端轮询 60s 内 `updatedAt` 没变 → 提示"任务卡住,是否取消"

### 8.4 进程重启

- 内存 cache 重启时丢,但 SQLite 是真相之源
- 启动时调用 `JobManager.startup_reap_ghosts()` → `JobStore.mark_stale_as_failed("server_restart")`
- 这种"幽灵任务"对外表现为"上传后立刻失败",比"永远卡 50%"好
- 已 `failed` 的 row 保留文件 7 天,便于排查;之后由 `trim()` 清理

## 9. 配置参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `tile_size` | 192 | 切片边长(像素,scale=1 时的尺寸) |
| `overlap` | 24 | 重叠边长(像素) |
| `model_dir` | `./models` | SwinIR 权重目录,内放 `SwinIR_REALSR_X2/X4/X8.pth` 中的一个或多个(见 §10) |
| `supported_input_formats` | `['png','jpg','jpeg','webp']` | 接收的文件类型 |
| `max_input_pixels` | `2000 * 2000` | 输入像素上限(避免 OOM) |
| `max_input_bytes` | `20 * 1024 * 1024` | 20MB |
| `history_keep` | `20` | 保留最近 N 条历史 |
| `flush_interval` | `0.5` | 进度节流写盘间隔(秒) |
| `semaphore_permits` | `1` | 同时刻只跑一个推理任务 |
| `max_workers` | `1` | `run_in_executor` 线程池大小(为安全起见与信号量保持一致) |

## 10. 缩放倍数与模型权重

SwinIR 官方按 scale 分别发布预训练权重(2x / 4x / 8x)。本期实现策略:

- **首选**: 维护 3 个权重文件,按用户选择的 scale 加载
  - `models/SwinIR_REALSR_X2.pth`
  - `models/SwinIR_REALSR_X4.pth`
  - `models/SwinIR_REALSR_X8.pth`
- **当前默认**: 仅下载/内置 `X4` 权重;`scale=4` 立即可用,`scale=2` 和 `scale=8` 启动时若权重缺失 → 报错 503 并提示用户下载
- **Runner 启动**: 加载**全部存在**的权重到内存字典 `{2: runner2, 4: runner4, 8: runner8}`,按需路由

## 11. 测试策略

### 11.1 单元测试

| 模块 | 测试文件 | 关键覆盖 |
|---|---|---|
| `Tiler` | `test_tiler.py` | • 完美整除(`W=512, tile=192, overlap=24` → 预期块数)<br>• 非整除(头/尾 tile 缩到剩余像素)<br>• `expected_count` 与 `split` 数量一致<br>• 边界:`W=1`、`W=tile_size`、`W=tile_size+1` |
| `SeamBlender` | `test_seam.py` | • 单 tile(无重叠)→ 像素完全保留<br>• 两 tile 重叠 → 拼接缝肉眼不可见(像素差 < 1)<br>• 4 tile 网格 → 中间接缝处无暗带<br>• 用确定性合成图(纯色+对角渐变)做 goldens |
| `SwinIRRunner` | `test_runner.py` | • 加载已知小权重 fixture<br>• 输入 `(64,64,3)` → 输出 `(64*scale, 64*scale, 3)`,dtype=uint8,值域 [0,255]<br>• 推理确定性(同输入同输出)<br>• 不真跑完整模型 —— 用一个最小 dummy checkpoint |
| `JobManager` | `test_job_manager.py` | • 状态机:queued → running → done<br>• 失败:runner 抛异常 → status=failed + error 字段<br>• 取消:running 状态下调 cancel → 下一个 tile 边界抛 `CanceledError` → status=canceled<br>• 并发:信号量 permits=1 时,两个 job 顺序执行<br>• 进度节流:50ms 内连发 100 个 progress → 实际 flush 次数 ≤ 5 |
| `JobStore` | `test_job_store.py` | • upsert/get 往返<br>• list_recent 按 created_at 降序<br>• trim(keep=2) 后只剩 2 条 + 文件删除<br>• 进程重启:startup 清理 `queued`/`running` |

### 11.2 集成测试(`test_api.py`)

用 `httpx.AsyncClient` + FastAPI TestClient,**真启动整个 app**,但 monkey-patch `SwinIRRunner` 注入一个返回固定图(deterministic,快)的假实现:

| 用例 | 步骤 | 断言 |
|---|---|---|
| 健康检查 | `GET /api/health` | 200 `{ok:true}` |
| 完整流程 | 上传 1x1 png,scale=4 → 轮询 → 下载 | 201 → 200(done) → image/png 非空 + 尺寸正确 |
| 列表 | 跑完 2 个 job → `GET /api/jobs` | 返回 2 条,按时间倒序 |
| 删除 | 跑完 → `DELETE` → 再 `GET` | 204 → 404 |
| 错误:格式 | 上传 .gif | 415 |
| 错误:超大 | 上传 > 20MB | 413 |
| 错误:跑中取消 | 上传 → 立刻 DELETE | CANCELED,无 output 文件 |
| 输出未就绪 | 上传后立刻 `GET /output` | 409 |

### 11.3 不测什么(YAGNI)

- **不测** SwinIR 模型本身的数学正确性 —— 那是论文和官方实现的责任,我们只测"调它能跑通、形状对"
- **不测**前端视觉回归 —— 本期就一个上传页,样式不写也行
- **不写**性能基准 —— CPU 上 SwinIR 慢是已知的,不在测试里卡

### 11.4 跑测命令

```bash
# 后端
cd backend
python -m pytest -x --tb=short

# 前端
cd frontend
pnpm typecheck    # tsc --noEmit
pnpm lint
```

## 12. 依赖

### 12.1 后端

- `fastapi`, `uvicorn[standard]`
- `torch`, `torchvision` (CPU 版即可)
- `numpy`, `pillow`
- `aiosqlite` (异步 SQLite 驱动)
- `python-multipart` (FastAPI 文件上传)
- 测试: `pytest`, `pytest-asyncio`, `httpx`

### 12.2 前端

- `next@14`, `react@18`, `typescript`
- 不引入 UI 组件库(原生 + CSS 即可,YAGNI)
- 工具: `eslint`, `prettier`

## 13. 部署与运行

```bash
# 后端
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
pnpm install
pnpm dev                 # 默认 :3000
```

环境变量:
- `MODEL_DIR` — SwinIR 权重目录(默认 `./models`)
- `STORAGE_DIR` — 输出文件目录(默认 `./storage`)
- `DB_PATH` — SQLite 文件路径(默认 `./data.db`)

## 14. 风险与权衡

| 风险 | 缓解 |
|---|---|
| CPU 上 SwinIR 慢(单块 5-30s) | 进度条透明;tile_size 适中,避免单图超过 100 块 |
| 大图输出 PNG 编码慢 | 用 `Pillow` 默认即可;超 50MB 输出时考虑换 JPEG |
| 信号量=1 导致排队长 | 本期不优化,文档化"同时一个任务";后续可加 worker |
| 进程重启幽灵任务 | startup 扫描清理,转 FAILED 并附 trace |
| 切缝在某些极端图上仍可见 | SeamBlender 改用 `cv2.addWeighted` 渐变叠加(留待后续优化) |
| SwinIR 官方代码版本不匹配 | 锁版本到具体 commit hash,requirements.txt 固定 |

## 15. 后续不在本期内的工作

- 用户账号与权限
- 多 worker 队列(Redis/Celery)
- 视频超分
- 浏览器内推理(ONNX Runtime Web)
- 更复杂的人脸/文字局部增强
- 图片格式转换(jpeg / webp 输出)
- 任务结果邮件通知
- 切缝质量改进
