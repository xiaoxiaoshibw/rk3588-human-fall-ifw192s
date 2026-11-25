# 雷达体态工作台（LiDAR Studio）

浏览器单页控制中心，用于在回放模式与只读实时模式下同屏查看 **3D 点云（多视角/着色/几何骨架/包围盒/尾迹）**、**192×256 原生 2D 距离图**、**USB 摄像头对照画面**，以及 **体态、跌倒状态机与 `human_physical_v1` 物理一致性分析**。

## 语义与只读边界

- **100% 纯雷达识别**：摄像头画面仅用于展示与人工对照，绝不进入任何识别、体态或跌倒算法链。
- **语义诚实**：所有人体/跌倒输出均无独立人体真值（`semantic: UNKNOWN`，`confirmed_enabled: false`）；`CONFIRMED_HUMAN` 在界面固定显示为 **`多证据物理一致（非真值）`**；骨架明确标注 **`几何区域，非人体关节`**。
- **摄像头对齐**：回放模式下采用主机接收时间就近匹配（`bag_time_sec` vs `recv_unix_ns`，窗口 `±250 ms`），非硬件同步。
- **数据安全**：只读消费 `data/sessions/`，不修改 `data/`、`captures/`、`webui/`、`console_v2/` 或 `src/`；离线推理缓存仅落盘至 `pc_apps/lidar_studio/.cache/`（已加入 `.gitignore`）。实时模式只读订阅板端已有话题，板端不可达时如实显示离线状态，不造假数据。

## 一键启动（Windows）

双击或执行：

```cmd
pc_apps\lidar_studio\start_studio.cmd
```

或命令行手动启动：

```bash
python -B pc_apps/lidar_studio/server.py --host 127.0.0.1 --port 8960
```

随后在浏览器打开 <http://127.0.0.1:8960/>。

## 快捷键

| 按键 | 功能 |
|---|---|
| `Space` | 回放播放 / 暂停 |
| `←` / `→` | 上一帧 / 下一帧（自动暂停） |
| `1` – `5` | 切换 3D 视角预设（正面 / 侧面 / 俯视 / 传感器 / 立体） |

## 架构文件

- [CONTRACT.md](CONTRACT.md)：`LDSF v1` 二进制帧布局、状态字段契约与 HTTP/WS 协议
- [protocol.py](protocol.py)：二进制帧打包与解包
- [replay_source.py](replay_source.py)：会话校验、`RangeRuntime(..., human_physical_v1=True)` 推理与 `.cache/` 缓存
- [camera_hub.py](camera_hub.py)：回放相机 `±250 ms` 匹配与板端 `:8081/stream` 单连接 MJPEG 扇出
- [live_source.py](live_source.py)：板端可达性探测与只读 Foxglove WS 订阅
- [server.py](server.py)：单端口 `127.0.0.1:8960` aiohttp 服务
- [web/](web/)：零构建原生 ES 模块 + 本地副本 Three.js r128

## 测试命令

```bash
# Python 后端、契约、相机对齐与回放一致单测（要求零警告）
python -B -W error -m unittest discover -s pc_apps/lidar_studio/tests -v

# 前端纯函数单测
node pc_apps/lidar_studio/web/studio_lib.test.js
```
