# HC-JOINT-LOCAL-01 R8 唯一验收表 v1 — 相机预览同步落盘

2026-10-15 Asia/Shanghai。依据用户直派「给联合录制加相机写盘」。本轮唯一表；改动与证据见
[README](README.md)、[回传](../../returns/HC-JOINT-LOCAL-01.md)。PASS/FAIL 为自验结果，非 Codex 验收。

| ID | 验收项 | 判据 | 结果 |
|---|---|---|---|
| CAM01 | 录制中相机逐帧落盘 | 会话目录 `camera.mjpeg` == 收到的完整 JPEG 序列；`camera_frames.jsonl` 每行 `{offset,length,recv_unix_ns}` 连续；`status.camera_frames` 与 `joint.json.camera_frames` 等于帧数 | PASS |
| CAM02 | 相机不可用不影响雷达 | 相机连不上：录制仍 `completed`，`camera.mjpeg` 为空占位，雷达 `points.bin/meta.json` 正常 | PASS |
| CAM03 | 回放路由在信任边界内 | `GET /api/camera?sid=` 只读该 sid 目录下 `camera.mjpeg`；`../meta.json`/`a/b`/空/超长 sid 一律 404，无越权读取 | PASS |
| CAM04 | 既有联合录制合同不回归 | sid 白名单、板端 stop 兜底、fetch 失败留 ready、same-origin 403 全绿 | PASS |
| CAM05 | 页面接线保持 | 联合页含 `joint-completed` 合同串且 JS 可解析；壳页/回放页既有接线不动 | PASS |
| CAM06 | 真机端到端（真板相机 → 落盘 → 页内回看） | 重打 EXE 并重启后真机跑一段 | NOT_RUN（需设备 + 重打，未授权） |
| CAM07 | 在 `human_replay` 回放页同屏显示视频 | 回放器加载 `camera.mjpeg` | NOT_RUN（本轮未改回放器，设计为联合页回看） |

边界：`camera_frames.jsonl` 为主机接收时刻，非硬件同步；回看为独立时间轴。
板端 / 驱动 / `fetch.py` / 数据格式 / 模型 / GT / `human_replay` / 旧会话与旧证据均未改。
