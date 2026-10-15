# 2026-10-15 HC-JOINT-LOCAL-01 R8 相机预览同步落盘（camera.mjpeg + 逐帧索引）

**工单/轮次**：HC-JOINT-LOCAL-01 / R8（承接 R7，R7 为并行工作流的目录名修复）
**执行者**：OpenCode CLI `opencode-go/deepseek-v4.1-flash`（用户直派 writer）
**时间**：2026-10-15 14:35–15:00 Asia/Shanghai
**状态**：SUBMITTED，未 ACCEPTED，独审 NOT_RUN

## 触发

用户连问「这些数据都看不了吗 → 视频看不了 → 视频文件帮我拉下来啊」。只读核对后确认：

- `data/sessions/` 下三个联合会话（`joint_cap_20261015_111738 / 142227 / 142730`）**只有雷达**（`meta.json` + `points.bin`），
  `camera.mjpeg` 恒 **0 字节占位**；全 `data/` 树只有这三个 `camera.mjpeg`，全是 0B。
- 板端相机服务 `http://192.168.31.58:8081` 实测只有三个路由：`/stream`（实时 multipart MJPEG）、
  `/snapshot`（单帧 JPEG）、`/status`（JSON）；`/files`、`/list`、`/recordings`、`/record` 等一律 **404**。
  **没有录像、没有历史、没有任何可下载文件**，所以「那两次录制的视频」不是拉取失败，而是**从未被保存**。
- 现行设计（R4 起，`2026-10-14_hc_joint_local_r4` 之后）为错峰模式：相机**仅预览不写盘**，
  板端 HC 只录雷达 bag。因此该时段相机画面随预览结束即消失。

用户据此选择「**给联合录制加相机写盘**」，本轮实现之。

## 根因

`Recorder._camera_preview_only` 只把最新一帧留在内存供 `/api/preview`，从不落盘；
`_run` 组装会话目录时只写一个空 `camera.mjpeg` 占位（历史注释「以便回放器将此会话当 video-only 段」），
文件本身没有任何消费者。板端仅提供实时流，无缓存/录像层。→ 相机数据在链路两处都不落盘。

## 实际变更（PC 侧 4 文件，零新依赖）

| 文件 | 改动 |
|---|---|
| `pc_apps/console/joint_capture.py` | `_camera_preview_only(url, mj_path, frames_path)`：录制中把预览帧逐条 `ab` 追加进会话 `camera.mjpeg`，并把 `{offset,length,recv_unix_ns}` 写入 `camera_frames.jsonl`（跨断流重连续写同一文件）；`_run` 在 `board.start()` 后即建会话目录（沿用 R7 的 `out_dir = root / sid`）并起相机线程，停板后 `stop_event.set()` + `preview.join(10)` 先关文件再继续组装；`joint.json` 增 `camera_frames`；新增 `GET /api/camera?sid=` 流式回放该会话录像（sid 白名单 `[A-Za-z0-9_-]{1,100}`，越权/无文件→404）。相机未上线时仍写空占位，行为与旧版一致 |
| `pc_apps/console/joint_capture.html` | 顶部/保存内容文案改为「相机实时预览并同步录像」；新增「相机录制回看」面板（按 JPEG SOI/EOI 切帧，▶播放 / 拖动 / 逐帧）与 `/api/camera` 拉取；预览提示与计数文案同步 |
| `pc_apps/console/README.txt` | 入口说明与保存内容改为含 `camera.mjpeg` / `camera_frames.jsonl`，并注明可在联合页回看 |
| `pc_apps/console/joint_capture_test.py` | 新增 2 用例：相机在线→帧整套落盘（camera.mjpeg 字节 = 帧序列，jsonl 逐帧 offset/length，status/joint.json 计数）；`/api/camera` 只出本会话录像、越权 sid 一律 404 |

未动：板端 / 驱动 / `fetch.py` 校验与状态机 / 数据格式 / 模型 / GT / `human_replay` / 旧会话与旧证据。
`camera_frames.jsonl` 的时刻是**主机接收时刻**，与雷达设备时系**未做硬件同步**，仅作帧索引。

## 逐条验收

| 验收ID | 检查 | 方式 | 结果 |
|---|---|---|---|
| CAM01 相机帧落盘 | 录制后会话目录 `camera.mjpeg` = 收到的 JPEG 序列，`camera_frames.jsonl` 逐帧 offset/length；计数正确 | `joint_capture_test.py::test_camera_preview_is_written_to_session` | **PASS** |
| CAM02 相机离线不破坏雷达 | 相机一直失败：录制仍 completed，`camera.mjpeg` 0B 占位 | `joint_capture_test.py::test_camera_preview_failure_still_allows_board_record_and_marked_gaps` | **PASS** |
| CAM03 回放路由边界 | `/api/camera?sid=` 只出本会话录像；`../meta.json`、`a/b`、空、超长 sid → 404 | `joint_capture_test.py::test_camera_route_serves_saved_video_and_rejects_unsafe_sid` | **PASS** |
| CAM04 原有合同不回归 | sid 白名单拒写、板端 stop、fetch 失败留 ready、same-origin 403 | `joint_capture_test.py` 余下 7 用例 | **PASS** |
| CAM05 页面/壳页 | 联合页 JS 语法与内嵌合同串（`joint-completed`）仍在 | `node console_html.test.js` + 本地 `new Function` 语法检查 | **PASS** |
| CAM06 真机端到端（真板相机 + 真录制回看） | — | — | **NOT_RUN**（需重打 EXE + 重启总控制台，且涉设备） |
| CAM07 回放面板内嵌显示 | 在 `human_replay` 会话回放里同屏看视频 | — | **NOT_RUN**（本轮回看在联合录制页；回放器未改） |

回归命令/退出码与日志见 `TEST_EXIT_CODES.txt`、`TESTS_*.log`；源码 SHA 见 `FILE_SHAS.json`。

## 未闭合与限制

- **EXE 未由本轮重打**：R7 并行工作流在 14:50/14:57 两次重打 `Console.exe`，因 `joint_capture.py/html` 早于其打包，
  本改动已被带入其冻结产物。生效须以 R7 终版 exe 为准并**重启总控制台**；R7 的 `FILE_SHAS.json`(14:44)/`TESTS_*.log`(14:43)
  早于本改动，已过期，需重生成。
- 回看面板只对**当前/最近一次**联合会话生效（联合页无会话列表选择器）；历史会话与自定义目录未接入。
- 相机与雷达时间基准不同（`BOARD_MASTER_CLOCK_pc_camera_host_receipt`），回看为**独立时间轴**，不做跨模态同步声明。
- `human_replay` 会话回放页未加视频面板（`_serve_file` 白名单仍只 `meta.json/points.bin`），本轮不改。
- 板端 / 设备 / 物理 / 独立复审 NOT_RUN；未 commit / push / 部署 / 采集。

## 并行写入如实记录

本轮编辑期间另一路工作流（R7）持续写同一批文件（14:38–14:57，含 14:50/14:57 两次 PyInstaller 重打）。
R7 的 `README.md` 亦记录了本流 14:38:46 / 14:40:29 的两次写入。本改动落在 R7 之后，R7 改动（`out_dir = root / sid`、
sid 守卫、测试断言）保留未动；两改动互不冲突。

技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full 强度）：复用既有 `jpeg_frames`
解析器与预览线程，只加「落盘 + 一条只读回放路由 + 一个页面播放器」，未引入任何新依赖或新进程。
