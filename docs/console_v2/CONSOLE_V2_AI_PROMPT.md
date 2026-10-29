# 新版总控制台 ConsoleV2 · C#/Qt 重构 AI 提示词（v2）

> 用法：把「主提示词」+「第 N 轮提示词」一起发给编码 AI，每轮只发一轮。
> 每轮必须交付：改动清单、命令与结果、测试与性能数字、未解风险、下一轮输入；没有实测的指标写 UNKNOWN。
> 本文件只规定“做成什么样、按什么顺序做、什么不许动”，不包含任何删除或迁移现有数据的指令。

---

## 0. 技术路线（先验证再承诺）

Qt 官方没有 C# 绑定，“Qt + C#”只有三条可落地路线：

| 路线 | 组成 | 优点 | 风险 |
|---|---|---|---|
| **A（默认）** | .NET 8 C# 领域层 + Qml.Net 承载 Qt 6 QML（Qt Quick / Quick 3D） | 真 Qt UI + C# 逻辑，一套 QML 跨平台 | Qml.Net 维护弱、Quick3D 互操作与打包需验证 |
| B（兜底） | Qt 6 C++ 薄壳（只做 QML 宿主与 3D 渲染）+ C# 服务进程（gRPC/命名管道） | UI 性能与打包最稳 | 两套语言、进程边界成本 |
| C（仅当 A/B 都失败） | Avalonia（纯 C#） | 生态最稳 | 不是 Qt，需用户书面同意 |

**硬性要求**：第 2 轮先做 spike，用真实会话跑数字。A 路线通过线：Qt 6.5+ / .NET 8 / Windows 11 上，
50 万点静态点云 ≥30 FPS、UI 线程单帧阻塞 ≤16 ms、冷启动 ≤2.5 s、可打包单文件 exe 并在无 VS 机器运行、高 DPI 正常。
不达标写 ADR 切 B，**不允许**没有数据就宣称可行。

---

## 1. 角色与目标

你是资深桌面客户端架构师兼实现者，在仓库 "D:/Code/ldiar" 内新建 **总控制台 ConsoleV2**，
替代 "pc_apps/console"（Python + pywebview + 内嵌 HTTP 服务），但**不修改、不删除**旧控制台、数据与页面。

目标（按优先级）：
1. **数据零事故**：任何情况下不删除、不移动、不改名 "data/"、"captures/"、".git/"、"ML/"、"docs/**/evidence/"。
2. **会话 API 不破坏**：现有会话 HTTP 接口原样保留（第 4 节），旧页面/脚本/板端继续可用。
3. **架构可维护**：分层 + 单向依赖 + 接口契约；单文件 ≤400 行，无 god class。
4. **可用**：会话库、点云回放、板端录制/下载、GT 标注、配平，覆盖旧控制台 P0。
5. **可验证**：每项功能有自动化测试与真实数据端到端；性能有预算与基准。
6. **可迁移**：与旧 Console 并行安装，用户确认后再切换。

v1 验收：
- 列出本地全部可读会话 → 打开任一会话 → 逐帧/连续回放 → 时间轴 seek → 相机帧（有则显示）。
- 板端：读状态 → 开始/停止录制 → 列会话 → 下载 points.bin 并 sha256 校验。
- 旧版会话页面（"pc_apps/human_replay/*.html"、"webui/human_fall"、"webui/human_capture"）指向新服务时功能不变。
- 386 帧会话冷启动到首帧 ≤2 s，1× 回放 0 丢帧，seek ≤300 ms P95。
- 测试全绿，性能基准入库；数据目录启动前后清单一致。

---

## 2. 事实基线（先读代码，不凭记忆）

必读：
1. "docs/PROJECT_STATE.md"、"docs/PROGRESS.md"
2. "docs/human_capture/README.md" §2（会话格式契约）
3. "pc_apps/console/console_gui.py"（旧控制台服务编排、入口卡片、自检）
4. "pc_apps/human_replay/human_replay_lib.py"（**会话 API 的实现基准**）
5. "pc_apps/console/joint_capture.py"（板端 REST 转发、录制、预览/相机流）
6. "pc_apps/human_replay/leveling.py"（配平三臂与 job 产物）
7. "pc_apps/human_replay/gt_server.py" + "gt_store/"（GT 存储）
8. "data/README_数据目录说明.md"（数据规矩）

### 2.1 会话数据契约（只读，不要“优化”格式）

data/sessions/<sid>/meta.json + points.bin：

~~~json
{
  "format": "human_capture_session", "format_version": 1,
  "session_id": "cap_20261018_110029",
  "created_iso": "2026-10-18T11:00:29+08:00", "duration_sec": 38.6,
  "point_file": "points.bin", "point_stride_bytes": 28,
  "point_layout": {
    "endian": "little",
    "fields": ["x","y","z","intensity","ring","timestamp"],
    "dtypes": ["<f4","<f4","<f4","<f4","<u2","<f4"],
    "pad_offsets_bytes": [18, 24], "stride_bytes": 28
  },
  "total_points": 13800000, "total_dropped_points": 0,
  "frames": [{"seq":6426183,"bag_time_sec":1791851184.46,"stamp_sec":583944,
              "stamp_nanosec":77226000,"count_points":49125,
              "offset_points":0,"dropped_points":0}],
  "sensor": {"model":"IFW192S","frame_id":"innolidar"},
  "time_domain": "device", "topics": {}, "topic_message_counts": {},
  "extraction": {}, "human_annotations": []
}
~~~

规则：
- 同时支持 stride **16**（x,y,z,intensity）与 **28**（+ring,timestamp），按 point_layout 解码，禁止写死。
- 校验：文件长度 == total_points × stride；offset_points 单调；各帧 count_points 之和 == total_points。
- 缺 meta.json（如 cap_20261017_141348）标记“不完整”，不崩溃、不改写。
- 读取用内存映射/流式，禁止把 1 GB 文件整读进托管堆；帧切片零拷贝。
- 越界/截断/NaN 显式报错并保留原始字节，不静默修补。

### 2.2 其它
- 相机：camera.mjpeg 或帧索引；无相机必须显示“无相机”，不得伪造同步。
- 配平：data/leveled/<job>/{ransac,svd,tls}/{points.bin,transform.json,quality.json,meta.json} + manifest.json、report.json。
- GT：pc_apps/human_replay/gt_store/<sid>/{draft.json,GT_V*.json,fusion_frames.json}。
- 目录联接：captures/{remote,leveled,registration} 指向 data/；解析后读写，不得删除/重建 junction。

---

## 3. 铁律（违反即失败）

1. **不删数据**：不得删除/移动/改名 data/、captures/、.git/、ML/、docs/**/evidence/ 任何内容。
   产品内“清理”只能：生成清单（path/bytes/sha256）→ 用户逐项确认 → 移入隔离区 AppData/ConsoleV2/quarantine/<时间戳>/，
   提供恢复入口；**不存在直接删除 API**。
2. **不改数据格式**：meta/points/job/GT 只读；写只发生在用户触发的导出、标注保存、录制下载。
3. **不碰 Git**：不 commit/push/reset/checkout/clean，不 git add 数据目录。
4. **不碰板端/驱动/网络设置**：只调用既有 REST。
5. **不假装**：没有 GT 的效果指标写 UNKNOWN；“软件跑通”≠“人体/物理有效”。
6. **不隐藏失败**：测试失败、性能不达标、异常日志原样上报。
7. **不覆盖旧控制台**：新程序并行安装，旧 pc_apps/console 只读参考。

---

## 4. 会话 API 兼容契约（本次重点，不可破坏）

新控制台必须**同时是这些 API 的服务端与客户端**：默认监听 127.0.0.1:8901（可配置，但默认端口保持不变，
旧页面、书签、脚本直接可用），并把同一组路由原样实现。**只许新增，不许改名/删除/改类型**。

### 4.1 本地会话 API（对齐 human_replay_lib.py）

| 方法 | 路径 | 语义 | 必须保持 |
|---|---|---|---|
| GET | /api/sessions | 本地 + 板端合并列表；?scope=local 只列本地 | 字段：sid,state,created_iso,duration_sec,size_bytes,frames,download_requested,transferred,local,bytes,name；外层 sessions,board_error,hidden{purged,missing}；按 created_iso 倒序 |
| GET | /api/manifest?sid= | 会话 manifest | 现有字段与编码 |
| GET | /api/file?sid=&name= | 只允许 meta.json / points.bin；流式 | application/octet-stream、Content-Length、分块写出；非法 sid/name → 400，缺失 → 404 |
| GET | /api/board/status | 代理板端状态 + current/current_created_iso | 原字段；板端不可达时 {"ros":"down","error":...} |
| GET | /api/sync_status | 同步进度/错误 | 原字段 |
| POST | /api/sync | 拉取会话（调用权威 fetch.py --sid，不重写逻辑） | 参数、幂等、错误结构 |
| POST | /api/board/record/start /stop | 代理板端录制 | 只转发 start/stop |
| POST | /api/board/request_download | 标记 download_requested | body {sid} |
| POST | /api/delete /api/rename /api/recover /api/load /api/save_annotations | 本机管理动作 | **仅环回可用**；非环回 403（沿用现策略） |

### 4.2 板端 API（只消费，不改）
GET /api/v1/status、GET /api/v1/record/current、GET /api/v1/sessions、GET /api/v1/sessions/{sid}、
GET /api/v1/sessions/{sid}/files/{name}、POST /api/v1/record/start|stop（带 idempotency_key）、PATCH /api/v1/sessions/{sid}。

### 4.3 相邻 API（一并保留，避免旧页面失效）
/api/leveling/*、/api/gt/*、/api/gt/exports、/api/validation/*、/api/human_detect/*；
联合录制端：/api/status、/api/preview、/api/camera?sid=、/api/start、/api/stop、/api/open-folder。

### 4.4 兼容规则
1. JSON 只做加法：新增字段允许，改名/删除/类型变化禁止；null 与缺省语义保持。
2. HTTP 语义不变：状态码、Content-Type、流式下载、路径穿越拒绝（含 ..、/、反斜杠）、sid 合法性。
3. 排序与过滤不变（created_iso 倒序、scope=local、隐藏 purged/missing 计数）。
4. 安全策略不变：非环回或 BOARD_MODE 时，破坏性 POST 一律 403 并给原因。
5. 版本化：现有无版本路由冻结；新能力加 /api/v2/*；GET /api/version 返回 {api:1, app:"ConsoleV2/x.y"}。
6. **契约测试**：以旧实现为 oracle，同一 fixture 下 JSON 逐字段比对；易变字段（端口、耗时、绝对路径、板端实时值）先规范化再比。
7. 交付 docs/console_v2/API_CONTRACT.md：路由表 + 请求/响应示例 + 错误码 + 兼容性矩阵；可选附 OpenAPI 3.1。

### 4.5 内部接口同样稳定
ISessionRepository、IPointsSource、IReplayClock、IBoardClient、IGtStore、IMutationGate 一旦发布，
只增不改；破坏性变更必须走 ADR + 主版本号。

---

## 5. 目标架构

### 5.1 分层（单向依赖）

~~~text
ConsoleV2.App (QML + ViewModel + DI 宿主 + 本地 API 服务托管)
        │
        ▼
ConsoleV2.Application (用例：OpenSession/Seek/StartRecording/Download/RunLeveling/SaveAnnotation)
        │
        ▼
ConsoleV2.Domain (纯模型/几何/规则；无 IO、无 UI、无框架)
        ▲
        │ 实现
ConsoleV2.Infrastructure (文件、二进制解码、HTTP 板端、本地 API 服务端、日志、配置、缓存)
~~~

规则：Domain 不引用其它项目；Application 只依赖接口；UI 不读文件、不发 HTTP、不解码二进制；
每个用例一个类，输入输出为 record，失败用 Result<T>/领域异常，禁止 bool 表示失败。

### 5.2 项目划分
- ConsoleV2.Domain：SessionMeta、FrameIndex、PointLayout、BoardSession、LevelingJob、Annotation、Validation
- ConsoleV2.Data：ISessionRepository、SessionRepository、PointsReader、MetaCodec、DataRoot、IntegrityChecker、Quarantine
- ConsoleV2.Replay：IReplayClock、FrameScheduler、FrameCache（LRU+预取）、CameraSync、PlaybackController
- ConsoleV2.Capture：IBoardClient、HttpBoardClient、RecordingStateMachine、SessionDownloader（sha256/续传）、SyncService
- ConsoleV2.Api：**本地兼容 HTTP 服务**（路由、序列化、鉴权策略、契约测试挂钩）
- ConsoleV2.Leveling、ConsoleV2.Annotation
- ConsoleV2.App：QML 页面 + ViewModel + ServiceCollection + 生命周期
- ConsoleV2.Tests.*：单元、契约、Golden、性能

### 5.3 关键接口

~~~csharp
public interface ISessionRepository {
    Task<IReadOnlyList<SessionSummary>> ListAsync(SessionScope scope, CancellationToken ct);
    Task<SessionHandle> OpenAsync(string sessionId, CancellationToken ct);
}
public interface IPointsSource : IAsyncDisposable {
    int FrameCount { get; }
    ReadOnlyMemory<byte> GetFrameRaw(int frameIndex);
    PointCloudView GetFrame(int frameIndex);
}
public interface IReplayClock { double PositionSec { get; } void Seek(double sec); void SetSpeed(double x); }
public interface IBoardClient {
    Task<BoardStatus> GetStatusAsync(CancellationToken ct);
    Task<RecordingState> GetRecordingAsync(CancellationToken ct);
    Task<RecordingState> StartAsync(string idempotencyKey, CancellationToken ct);
    Task<RecordingState> StopAsync(string idempotencyKey, CancellationToken ct);
    Task<IReadOnlyList<BoardSession>> ListSessionsAsync(CancellationToken ct);
    Task DownloadAsync(string sid, string destDir, IProgress<double> progress, CancellationToken ct);
}
public interface IMutationGate {
    Task<MutationPlan> PlanAsync(MutationRequest request, CancellationToken ct);
    Task ApplyAsync(MutationPlan plan, ConfirmationToken token, CancellationToken ct);
}
~~~

### 5.4 UI（QML）
左侧导航（会话库/回放/录制/配平/标注/设置），右侧内容区，底部状态栏（板端、FPS、当前会话）。
回放页：3D 视口、时间轴（帧/秒双刻度）、传输控制、帧信息、相机画中画（可选）。
耗时操作异步 + 可取消 + 进度；UI 线程不做 IO；空状态说明原因；深/浅色 + 高 DPI + 快捷键（空格、左右方向键、Home/End）。

---

## 6. 性能预算

| 项 | 预算 | 测法 |
|---|---|---|
| 冷启动到可交互 | ≤2.5 s P95 | 10 次取 P95 |
| 打开 1 GB 会话到首帧 | ≤1.0 s P95 | cap_20261017_113516 |
| 点云渲染 | ≥30 FPS @50 万点；≥60 FPS @5 万点 | 固定路径 10 s 均值 |
| UI 线程单帧阻塞 | ≤16 ms P99 | 计时打点 |
| 1× 回放 | 0 丢帧，漂移 ≤1 帧/分钟 | 386 帧会话 |
| Seek | ≤300 ms P95 | 随机 200 次 |
| 内存（780 帧） | ≤1.5 GB | 峰值工作集 |
| 下载 71 MB | ≤30 s 且 sha256 一致 | 真实板端 |

超预算必须给计时表/火焰图，不许“感觉流畅”。

---

## 7. 功能范围

**P0**：会话库（junction 解析、搜索、排序、缺失/损坏标记）；点云回放（逐帧/连续/seek/倍速/坐标域/帧详情）；
板端（状态、录制开始停止、会话列表、下载+sha256）；设置（数据根、板端地址、缓存、日志级别、测试连接）；
数据完整性（启动自检只读、损坏隔离显示、审计日志）；**本地会话 API 兼容服务**。

**P1**：GT 标注（加载/点选/框选/撤销重做/草稿/导出）；配平（列表、三臂质量、从现有会话新建 job、拒绝覆盖）；相机同步显示。

**P2**：离线评测入口（以子进程调用现有 Python，不重写算法）；外部工具页以“打开程序/本地页面”接入。

**非目标**：检测算法本身、训练、板端部署、Git 操作、自动清理磁盘、跨机同步。

---

## 8. 多轮执行流程

**R0 事实基线（只读）** → docs/console_v2/FACTS.md：入口、依赖服务、数据格式、**会话 API 全量清点**、
板端 API、GT/配平路径、已知坑（junction、缺 meta、stride 差异、evidence 依赖）。每条附文件+行号。列 5 条最大风险。

**R1 架构与 ADR** → ARCHITECTURE.md + ADR-001..006（技术路线、点云渲染、**API 兼容与版本化**、进程模型、数据安全闸门、配置/日志）。

**R2 技术验证 spike** → QML 窗口 + Quick3D 50 万点 + 真实会话 3 帧（stride 28）+ 打包 exe；
测 FPS/启动/内存/体积，写 SPIKE.md；不达标切 B 并记录数据。

**R3 数据层** → MetaCodec/PointsReader/DataRoot/IntegrityChecker；stride 16/28、缺 meta、截断、junction；
Golden 会话 3 段 + 属性测试（随机 stride/offset/路径穿越）；与 Python 参考逐值对照（容差 0）。

**R4 回放内核** → 时钟/调度/缓存/播放控制；386 帧 0 丢帧、随机 seek 200 次 P95 ≤300 ms、单测覆盖漂移与取消。

**R5 UI** → 会话库 + 回放页 + 状态栏 + 设置；MVVM；空态/错误态；UI 线程无 >16 ms 阻塞。

**R6 板端与下载** → HttpBoardClient（status/current/start/stop/sessions/files）、幂等键、超时重试、断线恢复；
SessionDownloader（进度、sha256、续传）；真实板端全流程。

**R7 本地 API 兼容服务** → 实现第 4 节全部路由；契约测试以旧实现为 oracle；旧页面（human_replay/human_fall/human_capture）
指向新端口逐页验证；错误码/流式/安全策略逐项对照；交付 API_CONTRACT.md。

**R8 GT + 配平（P1）** → 原子写、草稿、撤销；job 只读展示，新建需显式确认且拒绝覆盖。

**R9 打包与验收** → 自包含 exe、快捷方式、版本信息、日志/崩溃转储；性能基准；MIGRATION.md（并行/回退）；
逐项打勾验收，未达标写 FAIL+原因。

每轮固定输出：① 改动清单 ② 命令与结果 ③ 测试/性能数字 ④ 未解风险 ⑤ 下一轮输入。
每轮固定禁令：不删数据、不改旧控制台、不 commit、不编造指标。

---

## 9. 测试策略

- 单元：xUnit + FluentAssertions；PointsReader 用 FsCheck 属性测试。
- 契约：**会话 API Golden 测试**——同一 fixture 下新服务与旧实现 JSON 规范化后逐字段相等；
  错误路径（400/403/404、路径穿越、非法 sid）逐条覆盖。
- 兼容：把旧 webui/* 页面指向新服务，跑页面脚本（node human_replay_lib.test.js 等）与手工走查清单。
- 集成：临时目录构造会话/job/GT；禁止对真实 data/ 做写测试。
- 端到端：只读真实 data/sessions，列表→打开→回放→seek。
- UI：QML TestCase；截图对比仅辅助。
- 性能：BenchmarkDotNet + 固定数据集，阈值进 CI。
- 安全：删除/移动 API 单测证明“无确认不执行”“执行即隔离”“可恢复”。

---

## 10. 交付物

~~~text
console_v2/
  ConsoleV2.sln
  src/ConsoleV2.Domain|Data|Replay|Capture|Api|Leveling|Annotation|App/
  tests/ConsoleV2.Tests.*/
  docs/{ARCHITECTURE.md, FACTS.md, SPIKE.md, API_CONTRACT.md, PERFORMANCE.md, MIGRATION.md, ADR/*}
  README.md
~~~

只写 console_v2/ 与 docs/console_v2/；不改 pc_apps/、data/、captures/、src/、webui/。

---

## 11. 代码规范

C# 12 / .NET 8，Nullable=enable，TreatWarningsAsErrors；全链路 CancellationToken；
禁止 async void（事件处理器除外）、.Result/.Wait()、UI 线程同步 IO；
结构化日志（含 sid/帧号/耗时，不记录大数组）；配置启动校验；QML 组件 ≤200 行、不写业务分支。

---

## 12. 主提示词（整段复制）

~~~text
你在 D:/Code/ldiar 仓库内工作。任务：新建 C#/.NET 8 + Qt(QML) 的总控制台 ConsoleV2，
替代 pc_apps/console（Python+pywebview），但不修改、不删除现有数据、旧控制台、webui、src。

硬约束：
1) 只写 console_v2/ 与 docs/console_v2/；
2) 绝不删除/移动/改名 data/、captures/、.git/、ML/、docs/**/evidence/ 下任何内容；
   产品内“清理”只能“生成清单→用户确认→移入隔离区”，不得直接删；
3) 会话 HTTP API 必须原样保留：/api/sessions、/api/manifest、/api/file、/api/board/status、
   /api/sync_status、/api/sync、/api/board/record/start|stop、/api/board/request_download，
   以及 /api/leveling/*、/api/gt/*、/api/validation/*；字段只增不改，默认仍监听 127.0.0.1:8901；
   旧页面指向新服务必须照常工作；新增能力用 /api/v2；
4) 不 commit/push/reset/checkout/clean，不部署，不采集，不训练，不改驱动/网络；
5) 没实测数据的指标写 UNKNOWN；失败与不达标原样上报；
6) 旧 Console 保持可用，新程序并行安装。

工作方式：按 R0→R9 分轮交付，每轮先计划再写代码，结束输出
【改动清单 / 命令与结果 / 测试与性能数字 / 未解风险 / 下一轮输入】。

先读：docs/PROJECT_STATE.md、docs/human_capture/README.md §2、pc_apps/console/console_gui.py、
pc_apps/human_replay/human_replay_lib.py、pc_apps/console/joint_capture.py、
pc_apps/human_replay/leveling.py、data/README_数据目录说明.md。

现在执行 R0，只产出 docs/console_v2/FACTS.md、API 清点表与风险清单，不写生产代码。
~~~

---

## 13. 分轮提示词

**R0**
~~~text
执行 R0：只读调研。产出 docs/console_v2/FACTS.md：旧控制台入口/依赖服务、数据格式（meta.json 字段、
points.bin 步长 16/28、帧索引）、板端 API、GT/配平产物、已知坑（junction、缺 meta、evidence 依赖）。
另产出会话 API 清点表（方法/路径/参数/响应字段/状态码/安全策略），逐条附 human_replay_lib.py 行号。
列 5 条最大风险。不写代码、不运行会写盘的程序。
~~~

**R1**
~~~text
执行 R1：架构设计。模块图、单向依赖、关键 C# 接口签名、进程模型、配置与日志、数据安全闸门、
API 版本化与兼容策略；写 ARCHITECTURE.md 与 ADR-001..006。Domain 无 IO/UI；UI 不读文件；
所有写数据入口唯一（IMutationGate）。不写实现代码。
~~~

**R2**
~~~text
执行 R2：技术验证 spike。QML 窗口 + Quick3D 渲染 50 万点；用真实会话 cap_20261018_110029 读 3 帧按 stride 28 解码；
打包 exe 在无 VS 环境运行。测 FPS/启动/内存/体积，写 SPIKE.md。
通过线：50 万点 ≥30FPS、冷启动 ≤2.5s、高 DPI 正常。不达标写 ADR 切 B 路线，不许口头宣称可行。
~~~

**R3**
~~~text
执行 R3：数据层。实现 SessionMeta/PointsReader/DataRoot/IntegrityChecker；支持 stride 16/28、缺 meta、截断、junction；
零拷贝帧视图；异步。测试：3 个 Golden 会话 + 属性测试（随机 stride/offset/路径穿越）+ 与 Python 参考逐值对照（容差 0）。
禁止写真实 data/。
~~~

**R4**
~~~text
执行 R4：回放内核（无 UI）。ReplayClock/FrameScheduler/FrameCache/PlaybackController；播放/暂停/倍速/seek/逐帧、1× 实时、预取与取消。
验收：386 帧连续回放 0 丢帧；随机 seek 200 次 P95 ≤300ms；单测覆盖漂移、暂停恢复、缓存上限。
~~~

**R5**
~~~text
执行 R5：QML UI。会话库（搜索/排序/缺失标记）+ 回放页（3D 视口、时间轴、传输控制、帧信息、相机可选）+ 状态栏 + 设置。
MVVM；QML 不写业务逻辑；空态/错误态明确。自测：新建→打开→播放→seek→关闭；UI 线程无 >16ms 阻塞；快捷键可用。
~~~

**R6**
~~~text
执行 R6：板端与下载。HttpBoardClient（status/current/start/stop/sessions/files）、幂等键、超时重试、断线恢复；
SessionDownloader（进度、sha256、续传）。验收：真实板端 状态→开始→停止→列会话→下载；失败路径有提示与日志；不改板端配置。
~~~

**R7**
~~~text
执行 R7：本地会话 API 兼容服务。按 API_CONTRACT 实现 /api/sessions、/api/manifest、/api/file、/api/board/status、
/api/sync_status、/api/sync、/api/board/record/*、/api/board/request_download、/api/leveling/*、/api/gt/*、/api/validation/*。
默认 127.0.0.1:8901。以旧实现为 oracle 做 Golden 契约测试；旧页面指向新端口逐页验证；
非环回破坏性操作 403；错误码、流式、路径穿越拒绝逐条对齐；新增能力走 /api/v2；交付 API_CONTRACT.md。
~~~

**R8**
~~~text
执行 R8：GT 标注 + 配平（P1）。IGtStore 原子写（temp+rename）、草稿自动保存、撤销重做；
配平 job 只读展示三臂质量；新建 job 必须显式输出目录且拒绝覆盖。验收：标注保存→重开一致；报告与既有数值一致。
~~~

**R9**
~~~text
执行 R9：打包与验收。自包含 exe、快捷方式、版本信息、日志/崩溃转储；全量性能基准写 PERFORMANCE.md；
MIGRATION.md 说明与旧 Console 并行与回退；逐项打勾验收清单，未达标写 FAIL+原因。不得删除或覆盖旧控制台。
~~~

---

## 14. 验收清单（v1）

- [ ] 会话库列出全部可读会话；缺 meta/截断有标记且不崩溃
- [ ] 1 GB 会话首帧 ≤1 s；1× 回放 0 丢帧；seek ≤300 ms
- [ ] 50 万点 ≥30 FPS；UI 线程 P99 ≤16 ms
- [ ] 板端 状态/录制/列表/下载/sha256 全流程通过
- [ ] **会话 API 契约测试全绿；旧页面连新服务功能不变；默认端口 8901**
- [ ] 所有写操作经 IMutationGate 审计；无直接删除 API
- [ ] 数据目录启动前后 path/bytes/sha256 清单一致
- [ ] 单元/契约/集成/端到端全绿；性能基准存档
- [ ] README/ARCHITECTURE/ADR/SPIKE/API_CONTRACT/PERFORMANCE/MIGRATION 齐备
- [ ] 旧 Console 仍可用；新程序可卸载、可回退
