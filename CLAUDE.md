# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. A companion `AGENTS.md` (for Codex CLI) covers the same workflow — keep the two consistent when editing either.

## How we work (read first)

One project, continuous development. Read [PROJECT_WORKFLOW.md](docs/PROJECT_WORKFLOW.md) (rules), [PROJECT_STATE.md](docs/PROJECT_STATE.md) (current state) and [PROGRESS.md](docs/PROGRESS.md) (recent work) before changing anything.

- 用户说做什么就连续做完：读代码 → 改 → 测 → 记录。没有工单、验收表、回传、复审环节，也不要求人工确认 / 标注 / 复核。
- 每轮结束：跑相关测试 + 一次离线回放或端到端，结果追加到 `docs/PROGRESS.md`，机器产物放 `docs/evidence/<date>_<topic>/`。
- 旧工单、验收表、回传、`tickets/`、`returns/`、历史 evidence 全部只读；历史流程归档在 `docs/archive/` 与 `*_HISTORY.md`。
- 红线：`data/` 与 junction 不删不移；不 commit / push / reset / checkout / clean；不部署 / 采集 / 训练 / 下模型 / 改驱动网络 / 开 HR-09，除非用户明确要求。
- 唯一写入者：本会话 agent；子代理只做只读分析或独立计算。
- 语义诚实：没有 GT 的效果指标写 UNKNOWN；几何 / 软件通过不等于人体 / 物理有效。

The tree is deliberately dirty and mixes untracked production source with pending relocations (e.g. root build scripts moved under `tools/`; `文档/` was renamed to `文档收集（人工）/`). Baseline branch/HEAD/SHA over all files including untracked.

## Repository overview

**Linux ROS workspace** (InnoLight/InnoSense IFW192S LiDAR) plus PC/browser tooling. Five packages under `src/`:

- **`inno_lidar_ros/`** — C++ driver; `node/inno_lidar_node.cpp` → `src/manager/` → `src/source/` (SDK wrapper + publisher). Wraps the closed-source `libinno_driver` SDK (prebuilt `.so` in `third_party/inno_driver/lib/{x86_64,aarch64}`, headers alongside). Based on the RoboSense driver template (3-clause BSD headers).
- **`inno_lidar_msg/`** — `DeviceStatus.msg` only.
- **`human_fall_detection/`** — ROS1 Python fall detection (HF/GL). Pure algorithms in `core/` (no ROS imports); `scripts/human_fall_node.py` is the ROS wrapper (bounded latest-frame queue + single worker thread). Fall events append to a local JSONL log. `docs/` holds the project docs and history.
- **`human_capture/`** — ROS1 Python capture server (HC): board REST on `:8766`, reuses `human_fall_detection/scripts/record_session.py` for bags, `core/bag2session.py` converts `.bag` → `meta.json` + `points.bin`. Format contract in `docs/human_capture/README.md` §2.
- **`human_follow_calibration/`** — ROS1 Python calibration + read-only monitor publishing `/human_follow/state` (detail in its `README.md`).

Elsewhere:

- **`webui/`** — board-served Three.js pages (`human_fall/` production, `human_fall_preview/` replay preview, `human_capture/` record console, `dist/webui-minimal/` external bundle). The browser only renders and sends selection/record/baseline requests; the board-side backend validates and acks them. Served from the RK3588 board on `:8090` (via the `slam-localization` container); `tools/open_webui.bat` opens it from Windows.
- **`pc_apps/`** — Windows-side apps: `console/` (only the joint-recording backend `joint_capture.*` used by `console_v2`; the old web-shell Console.exe was deleted 2026-10-25, replaced by the Qt app `console_v2/`), `human_replay/` (replay/trim/annotation, node + python), `human_core/` (unified offline engine v2, multi-mode BASE_A/BASE_B/U1–U6 — see its README; run via `runner.js`, tests via `run_all_tests.js`), `human_pcl/`, `human_limb/`, `human_ml/`.
- **`sidequests/`** — standalone side branches (e.g. `lidata_adapter/`, `human_detectors/`, `human_fusion_lab*/`), each with its own README; explicitly not main-line HF/GL/HC/HR artifacts.
- **`ML/`** — dormant reserved area (see its README); do **not** activate without the user's explicit go-ahead.
- **`docs/`** — `human_capture/` (HC/HR), `human_fall/` (HF/GL), `sidequests/`. **`captures/`** — original PCAPs/session data, treat as read-only input. **`文档收集（人工）/`** — vendor manuals (AISC-3830) and literature. **`tmp_gl_diag/`** — scratch diagnostic output.

## Build & run (Linux only; native Windows cannot build)

- `bash tools/build_ros1.sh` (catkin_make) / `bash tools/build_ros2.sh` (colcon), then `source devel/setup.bash` or `install/setup.bash`.
- Both scripts mutate the tree before building: copy `package_ros{1,2}.xml` over `package.xml` and `sed` `COMPILE_METHOD` to CATKIN/COLCON in `src/inno_lidar_ros/CMakeLists.txt` and `src/inno_lidar_msg/CMakeLists.txt`. Inspect these diffs before committing.
- `src/CMakeLists.txt` is the catkin toplevel symlink; on Windows it shows as broken/modified. Do not replace it with a regular file.
- Rebuild one package: `catkin_make --pkg <pkg>`. Driver deps: ROS, libpcap, yaml-cpp.
- `roslaunch inno_lidar_ros ros1_start.launch` (override config via `~config_path`); `roslaunch human_fall_detection human_fall.launch`.
- Board deploy/start/stop of the fall node: `src/human_fall_detection/scripts/deploy_human_fall.sh` inside the `slam-localization` container (versioned releases + symlink rollback; never deletes releases, never broad-`pkill`s, never touches the driver/network/old homepage).
- `src/inno_lidar_ros/config/config.yaml` holds machine-specific settings: `common.msg_source` (0 off / 1 live lidar / 2 PCAP replay), `lidar[].driver.*` (lidar type, ports, crop, `pcap_file`, `pcap_repeat`, calibration folder, extrinsics), `lidar[].ros.*` (topics, `frame_id`).

## Tests

Fast and headless; no CI or root runner — run suites individually. `-W error` is required (warnings fail). Python suites from the repo root (`python` on Windows, `python3` on Linux):

- `python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v`
- `python3 -B -W error -m unittest discover -s src/human_capture/tests -v`
- `python3 -B -W error -m unittest discover -s src/human_follow_calibration/tests -v`
- Run a single Python test: `python3 -B -W error -m unittest src.<pkg>.tests.<test_file>.<TestClass>.<test_method> -v` (or `cd` into the package and reference the module directly)

JS/console suites, run from each directory (file-per-suite, run by name — do not glob `*.test.js`, at least one suite is known to hang on Windows Node 24):

- `node human_fall_lib.test.js` (`webui/human_fall`, `webui/human_fall_preview`)
- `node capture_lib.test.js` (`webui/human_capture`)
- `pc_apps/human_replay/`: `node human_replay_lib.test.js`, `node panel.test.js`, `node human_detect_lib.test.js`, `node human_pipe_lib.test.js`, `node gt_*.test.js`, `node detect_overlay.test.js`, …
- `pc_apps/human_core/`: `node --max-old-space-size=2048 run_all_tests.js` (plus focused `test_*.js` / `runner.js` / perf scripts — see its README)
- `pc_apps/console/`: `python joint_capture_test.py` (joint-recording backend only; old console web shell removed 2026-10-25); `pc_apps/human_replay/` python suites e.g. `python fetch_lib_test.py`, `python floor_detector_test.py`, …

Board runtime is Python 3.8.10 / NumPy 1.17.4 (the Windows dev box runs 3.12) — keep board code 3.8-compatible and stdlib + NumPy only (no OpenCV/RKNN). `evaluate_sessions.py` uses stdlib JSON only. Add regression cases for decoding, invalid data, ambiguity, and calibration changes. Driver changes need a ROS build plus live/PCAP publishing checks.

## Architecture notes

- **Dual ROS1/ROS2**: the same driver sources compile under either ROS version, selected by CMake options and `#if ROS_FOUND==1/2` preprocessor branches. Keep both paths compiling when touching driver code.
- **Driver data flow**: `inno_lidar_node.cpp` (main; chooses ROS1/ROS2 via the `ROS_FOUND` define) → `NodeManager` → `SourceDriver` (`msg_source` selects live lidar vs. PCAP replay) → `PublishManager` (converts SDK frames to ROS messages). Publishes `/innolidar_points` (sensor_msgs/PointCloud2), `/inno_imu`, `/device_status`.
- **`POINT_TYPE`** in `inno_lidar_ros/CMakeLists.txt` (`XYZI` / `XYZI_TIME` / `XYZI_SOURCE`) maps to `#define POINT_TYPE_*` and the custom cloud types in `src/msg/cloud_types.hpp`.
- **Device timestamps**: the SDK header comments `imu_types.hpp` stamps as nanoseconds, but the publish side interprets them as seconds — a known unresolved contradiction. Do not "fix" the unit from the header comment alone; invalid/out-of-range stamps become the (0,0) stamp with nanosecond carry handled (see `deviceStampToRos` in `publish_manager.cpp`).
- **Fall config layering** (`src/human_fall_detection/config/`): `default.yaml` (frozen HF-01 health/manifest) and `geometry.yaml` are frozen — do not change their semantics; `geometry_constrained*.yaml` are immutable named variants (constrained scripts take `--constrained-config`); `human_fall.yaml` is node runtime (topics/timeouts/output); `human_fall_prod.yaml` is the board production config; `perception.yaml` holds per-`core/`-module thresholds.
- **Calibration CSVs** in `config/ifw192s/` (azimuth/elevation, model weights, near filter) are loaded from `calibrate_folder`; `is_device_load_calibration: true` takes them from the device instead. SDK logging macros (`INNO_MSG`, `INNO_ERROR`, …) come from `third_party/inno_driver/inno_driver/common/inno_log.hpp`.
- **Read-only invariant**: calibration and fall-detection nodes never publish vehicle/robot control commands. The human-detect human-IMU relationship: fall/perception identifies the person from point-cloud geometry; IMU is health-monitoring only, not a fall signal.

## Conventions & gotchas

- Driver code is C++14 (C++17 under ROS2 Humble), built with `-O3 -flto -Wall`. C++ uses PascalCase classes/methods with an `m_` member prefix; Python uses `snake_case`; 4-space indent for both. No repo-wide formatter or linter is configured.
- New code/comments in this repo are commonly written in Chinese; match the surrounding style. Git history uses short Chinese action summaries (e.g. `优化半径滤波算法运行效率`); no enforced prefix. Keep commits focused.
- Driver, `webui/`, `captures/` and historical evidence stay read-only unless the task needs them; new variants get new files, not edits.
- Dev environment: Windows host running Git Bash (Git installed under `D:\APPS\Git`) drives a remote RK3588 board (ROS Noetic, aarch64). Builds/board operations happen on the board, not on Windows.
