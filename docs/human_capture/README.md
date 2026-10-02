# human_capture — 人体数据采集 / 回放 / 标注支线

> 新支线，独立于 HF/GL 工单体系。文档组织照搬 HF 的 milestone/ticket/证据习惯，
> 但本文是本方唯一计划入口。
>
> 创建：2026-10-02（Asia/Shanghai）。设计冻结：2026-10-02（用户两轮拍板后）。

## 0. 目的与边界

在板端远程控制采集 `/innolidar_points`（+IMU/设备状态）数据段，自动回传 PC，
在 PC 端 WebUI 中回放、剪辑，并用建模软件式交互对 3D 点云做**人工标注**，
标注以 `source:"human"` 写入数据产物，供下游 AI 一眼区分。

**边界（不做）：**

- 不动驱动 `inno_lidar_node`、HF 节点、8090 实时预览页、foxglove_bridge 配置（只读消费）。
- 不发布任何控制指令；全链路只读或本地文件操作。
- 不引入 MCAP（2026-10-02 用户拍板）——数据落地为自有 JSON 元数据 + 原始 float32 二进制点。
- 非目标：跨帧插值标注、旋转框（v1 仅轴对齐 yaw 预留）、自动标注模型。

## 1. 总体架构

```
            RK3588 板 (192.168.3.125)                    Windows PC (192.168.3.8)
┌─────────────────────────────────────────────┐   ┌──────────────────────────────────┐
│ 雷达 → inno_lidar_node → /innolidar_points   │   │ pc_apps/human_replay/             │
│                            │(board loopback)│   │  ├─ fetch.py      ←──轮询拉取      │
│            ┌───────────────┴───────┐        │   │  │   sessions → scp → 回报已下载   │
│            ▼                        ▼        │   │  ├─ load_session.py ← AI/Python 读 │
│   record_session.py(现成)     capture_server │   │  │      demo/校验库                │
│   (rosbag record → .bag)     :8766 REST      │   │  └─ index.html 回放/剪辑/标注     │
│            │                        │        │   │      (Three.js r127)              │
│            ▼                        │        │   │                                 │
│   bag2session.py (新, 纯 py)        │        │   │ 数据落盘:                        │
│   .bag → meta.json + points.bin    │        │   │  D:\Code\ldiar\captures\remote\   │
│            │                        │        │   │     cap_*/meta.json              │
│            ▼                        ▼        │   │     cap_*/points.bin             │
│   captures_remote/ (板端暂存) ←── sessions.json│  │                                  │
│   FIFO 留10份 / <5GB 强清                    │   │                                  │
└─────────────────────────────────────────────┘   └──────────────────────────────────┘
        ▲                                                    │
        └───────── 控制面 HTTP :8766（KB 级）─────────────────┘
                  数据面：仅下载时走 eth1，scp -l 限速 ~70Mbit
```

**控制面 vs 数据面分离**：8766 REST 只传请求和 KB 级状态；点云文件只在
下载时走 eth1 百兆（限速给实时预览留 30%）。录制过程本身零网络。

**为什么 PC 侧拉取**：PC 无 sshd，板→PC 推不动；PC 有免密到板的 key，
拉取天然成立。fetch.py 轮询 + 手动立即按钮。

## 2. 数据格式（两侧共同契约，version=1）

每个会话一个目录 `cap_YYYYMMDD_HHMMSS/`：

### meta.json

```json
{
  "format": "human_capture_session",
  "format_version": 1,
  "session_id": "cap_20261002_143012",
  "created_iso": "2026-10-02T14:30:12+08:00",
  "sensor": {"model": "IFW192S", "frame_id": "innolidar"},
  "time_domain": "device_stamp_s_unanchored",
  "duration_sec": 28.4,
  "frame_rate_hz_measured": 9.68,
  "topics": ["/innolidar_points", "/inno_imu", "/device_status"],
  "point_layout": {"fields": ["x", "y", "z", "intensity"],
                   "dtype": "<f4", "stride_points": 4},
  "point_file": "points.bin",
  "frames": [
    {"seq": 1, "stamp_sec": 12345, "stamp_nanosec": 678900000,
     "offset_points": 0, "count_points": 81234, "src_bag_time_sec": 0.0}
  ],
  "human_annotations": [
    {"id": "ann_001", "source": "human", "label": "person",
     "frame_seq": 154,
     "stamp_sec": 12360, "stamp_nanosec": 120000000,
     "box": {"center": [1.6, 0.1, 0.9], "size": [0.6, 1.1, 1.8], "yaw": 0.0},
     "created_iso": "2026-10-02T14:35:22+08:00", "tool": "human_replay/0.1",
     "frame_valid": true}
  ],
  "extraction": {"tool": "bag2session/0.1", "point_step_bytes": 16,
                 "field_map": "x,y,z,intensity@0,4,8,12",
                 "dropped_frames": 0, "source_bag_sha256": "…"}
}
```

### points.bin

原始 float32 小端连续流，行主序 `[x,y,z,i]`×N。`frames[i]` 的
`offset_points/count_points` 是**点索引**（字节偏移 = ×16）。
双端零解析：Python/`numpy.memmap`、JS/`Float32Array` 切片。

### AI 读法（pc_apps/human_replay/load_session.py 即此参考实现）

```python
import json, numpy as np
meta = json.load(open("cap_xxx/meta.json"))
pts = np.memmap("cap_xxx/points.bin", dtype="<f4")
f = meta["frames"][154]
cloud = pts[f["offset_points"]*4:(f["offset_points"]+f["count_points"])*4].reshape(-1, 4)
boxes = [a for a in meta["human_annotations"]
         if a["frame_valid"] and a["frame_seq"] == f["seq"]]
```

**契约要点**：

- `seq` 用驱动 ROS header **seq 原始值**（回放丢帧诊断）；`frame_valid=false`
  的标注（剪辑切半/戳空帧）AI 侧必须跳过。
- 时间域标 `device_stamp_s_unanchored`（雷达上电秒，跨年已知问题），
  与 HF manifest 同源声明。
- 人工标注唯一判定字段 = `source:"human"`。AI 侧过滤条件就这一个。

## 3. milestone 表

| ID | 内容 | 验收要点 |
|----|------|----------|
| **HC-01** | capture_server 骨架：:8766 REST、/healthz、/api/v1/status、sessions CRUD、sessions.json 原子写 | curl 200、JSON 契约、并发写不烂 |
| **HC-02** | 录制生命周期：**调现成 record_session.py**、超时长/低盘自动停、FIFO 留 10 已下载优先删、非干扰实测 | 启/停/双自动停/FIFO/sessions 状态机 + 共存证据 |
| **HC-03** | bag2session：.bag → meta.json+points.bin，sha256，抽帧记账 | 与 `rosbag info` 对账、meta 通过 load_session 校验 |
| **HC-04** | 板端控制页 webui/human_capture/：实时预览嵌入 + 录制控制台 + 会话列表 + 下载触发 | 浏览器全流程可点通 |
| **HR-01** | PC fetch.py：轮询 ready→限速 scp→回报 transferred；断点续传 | 板端 ready 文件自动出现在 PC captures/remote/ |
| **HR-02** | 回放器：.bin+meta 加载、Three.js 渲染、播放/逐帧/时间轴 | 打开即播，帧率与 meta 一致 |
| **HR-03** | 剪辑：区间 → 新子会话目录（同格式，points 切片不重编码） | 剪辑产物可被 load_session 正常读 |
| **HR-04** | 编辑器导航层：双相机(环绕/飞行)、四视图、网格/三轴/原点、坐标读数、参照物、标尺 | 键位表逐条过、读数对得上 |
| **HR-05** | 标注编辑：顶视画框、gizmo 移动/旋转/缩放、轴约束/捕捉、数值面板双向、撤销/复制、落盘 | 标注→存→重开→原位；AI 侧能按 seq 取框 |

## 4. 冻结设计决策（用户拍板记录，2026-10-02）

| # | 决策 | 结论 |
|---|------|------|
| D1 | PC 落盘路径 | `D:\Code\ldiar\captures\remote\` |
| D2 | 控制端鉴权 | 不要（局域网），后续加 token 属增量 |
| D3 | 板端产物格式 | ~~bag→mcap~~ 撤销 → **bag→meta.json+points.bin**（JSON 存不住点云本体，1.6GB/60s，二进制约其一半且零解析） |
| D4 | 回传方向 | PC 侧拉取（PC 无 sshd） |
| D5 | AI 消费者 | Python 脚本读 → `load_session.py` 为契约参考实现 |
| D6 | 板端回滚 | FIFO 留 10 / 盘 <5GB 强清最老，已下载优先删 |
| D7 | gizmo 键位 | Unity 式 **W/R/T** = 移动/旋转/缩放；飞行升降 **Z/C**；相机归位 **Home** |
| D8 | 左键冲突解 | 模式键 **B**（框选）/ **V**（查看），HUD 常显 |
| D9 | 标注法 | top-down 俯视正交画框 + z 自动（2%/98% 分位）+ 手动微调；旋转框/插值留 v2 |
| D10 | 音源现成复用 | **HC-02 录音机 = human_fall_detection/scripts/record_session.py**，不新造 |

## 5. 键位与交互总表（HR-04/05 的共同契约）

### 相机

| 输入 | 动作 |
|------|------|
| 模式切换 | **B** 框选 / **V** 查看（左键行为切换） |
| 查看模式 左键拖 | 环绕旋转 |
| 中键拖 / 滚轮 | 平移 / 缩放 |
| **F** | 环绕 ⇄ 飞行模式 |
| 飞行：按住右键拖 + **W A S D** + **Z/C** 升降 + Shift×5 | 自由飞行 |
| **7 / 1 / 3 / 0** | 顶视正交 / 前视 / 侧视 / 透视 |
| **Home** | 相机归位 |

### 标注操作

| 输入 | 动作 |
|------|------|
| **W / R / T** | gizmo 移动 / 旋转 / 缩放 |
| 按住 **X / Y / Z** 或 Shift+轴 | 轴约束（Shift+Z = 仅地面平移） |
| 按住 **Ctrl** | 捕捉：移 0.1m / 旋 5° / 缩 0.05m |
| **Ctrl+Z / Ctrl+C / Ctrl+V** | 撤销(20层) / 复制框 / 粘贴到当前帧 |
| **Enter / Del / Esc** | 定稿 / 删除 / 取消选择 |
| **空格 / ←→(Shift=±10)** | 播放暂停 / 步进 |
| **P** | 拾取最近点，状态栏显精确 (x,y,z,i) |

### 辅助显示开关（工具栏）

地面网格 1m（开）/ 细格 0.1m（关）/ XYZ 三轴（开）/ 雷达原点（开）/
1.8m 站立人形（可拖摆位）/ 1.8m 横放人形 / 2.1m 门框 / 两点标尺（开/关 + 数据持久化于 meta.view_state，草稿）。

## 6. 与运行系统的共存预算（HC-02 实测项）

| 资源 | 风险 | 措施 |
|------|------|------|
| 话题订阅 | 新增 rosbag 第 3 订阅者 | roscpp 慢订阅者只自身丢帧，不拖累 HF/bridge |
| CPU | 抽取转 bin 烧 1-2 核 ~30s | `nice 10` 起 bag2session；录制期 CPU 有富余 |
| 磁盘持续写 12MB/s | **最大风险**：板卡写速不达标→bag 静默缺帧 | record_session 缓冲 1GB；HC-02 实测掉帧率留证据；不达标降级录 `/dev/shm`(≤2min) |
| eth1 百兆 | 下载挤实时预览 | `scp -l ≈70Mbit` 限速，录时不传 |
| 驱动/HF/bridge | — | 全程只读，代码无触碰路径 |

## 7. 目录与产物

```
src/human_capture/                 # ROS1 包（HC-01..04，板上）
  core/__init__.py  session_store.py  recorder.py  bag2session.py
  scripts/capture_server.py  bag2session_cli.py
  config/capture.yaml
  launch/human_capture.launch
  tests/test_hc01_health.py  ...
webui/human_capture/              # 板端控制页（HC-04）
  index.html  capture.js  capture_lib.js  capture_lib.test.js
pc_apps/human_replay/            # PC 端（HR-01..05）
  fetch.py  load_session.py
  index.html  replay.js  trim.js  annotate.js  editor_*.js
  human_replay_lib.js  human_replay_lib.test.js
  vendor/three.min.js  vendor/OrbitControls.js  vendor/TransformControls.js
docs/human_capture/tickets/HC-01.md  ...      # 每单：范围、不做什么、验收表、return 模板
docs/human_capture/evidence/YYYY-MM-DD_<id>/  # 每单证据目录
```

依赖原则延续项目基线：板端 **stdlib + numpy + 系统已有的 rosbag CLI**；
PC 端 **stdlib + numpy + 浏览器 + Three.js r127**（与 human_fall_preview
同源取 r127 稳定系列，min 三件套 vendor 进仓，运行时零外网）。

## 8. 会话状态机（HC-01..04 共同养活）

`recording → extracting → ready → transferring → transferred → (FIFO) purged`
异常支：任何一步 `failed(reason)`；`deleting/purged` 仅 FIFO 清理用。
PC fetch 只对 `ready` 动手；成功后置 `transferred` 回报板端。

票/证据每个 milestone 一份，ticket 写明「不做什么」防范围漂移。
