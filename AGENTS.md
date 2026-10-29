# Repository Guidelines

## How we work (read first)

One project, continuous development. Read [PROJECT_WORKFLOW.md](docs/PROJECT_WORKFLOW.md) (rules), [PROJECT_STATE.md](docs/PROJECT_STATE.md) (current state) and [PROGRESS.md](docs/PROGRESS.md) (recent work) before changing anything.

- 用户说做什么就连续做完：读代码 → 改 → 测 → 记录。没有工单、验收表、回传、复审环节，也不要求人工确认 / 标注 / 复核。
- 每轮结束：跑相关测试 + 一次离线回放或端到端，把结果追加到 `docs/PROGRESS.md`，机器产物放 `docs/evidence/<date>_<topic>/`。
- 旧工单、验收表、回传、`tickets/`、`returns/`、历史 evidence 全部只读；历史流程归档在 `docs/archive/` 与 `*_HISTORY.md`。
- 红线：`data/` 与 `captures/remote|leveled|registration` junction 不删、不移、不改名；不 commit / push / reset / checkout / clean；不部署 / 采集 / 训练 / 下模型 / 改驱动网络 / 开 HR-09，除非用户明确要求。
- 唯一写入者：本会话 agent；子代理只做只读分析或独立计算。
- 语义诚实：没有 GT 的效果指标写 UNKNOWN；几何 / 软件通过不等于人体 / 物理有效。

Data root `data/` (git-ignored; `captures/remote`, `captures/leveled`, `captures/registration` are junctions pointing into it) holds the session/leveling/registration data the console and pages consume. It is data, not workspace. Deleting a session or artifact requires a sid/bytes/sha256 manifest plus explicit user confirmation first. See `data/README_数据目录说明.md`.

The tree is deliberately dirty and mixes untracked production source with a pending relocation (tracked root `build_ros*.sh` / `open_webui.bat` / `rk.txt` show deleted; untracked copies live in `tools/`; `文档/` was renamed to `文档收集（人工）/`). Baseline branch/HEAD/SHA over all files including untracked.

## Repository

Linux ROS workspace (InnoLight/InnoSense IFW192S LiDAR) plus PC/browser tooling. Five packages under `src/`:

- `inno_lidar_ros/` — C++ driver; `node/inno_lidar_node.cpp` → `src/manager/` → `src/source/` (SDK wrapper + publisher). Publishes `/innolidar_points`, `/inno_imu`, `/device_status`. `third_party/inno_driver/` holds closed-source headers and prebuilt x86_64/aarch64 `.so`.
- `inno_lidar_msg/` — `DeviceStatus.msg` only.
- `human_fall_detection/` — ROS1 Python fall detection (HF/GL). Pure algorithms in `core/` (no ROS imports); `scripts/human_fall_node.py` is the ROS wrapper. `docs/` holds the project docs and history.
- `human_capture/` — ROS1 Python capture server (HC): board REST on `:8766`, reuses `human_fall_detection/scripts/record_session.py` for bags, `core/bag2session.py` converts `.bag` → `meta.json` + `points.bin`. Format contract in `docs/human_capture/README.md` §2.
- `human_follow_calibration/` — ROS1 Python calibration + read-only monitor publishing `/human_follow/state` (detail in its `README.md`).

Elsewhere: `webui/` = board-served Three.js pages (`human_fall/` production, `human_fall_preview/` replay preview, `human_capture/` record console, `dist/webui-minimal/` external bundle); the browser only renders and sends selection/record requests. `pc_apps/` = Windows-side apps (`console/` now only the joint-recording backend `joint_capture.*` used by `console_v2` — the old web-shell Console.exe was deleted 2026-10-25, replaced by the Qt app `console_v2/`; `human_replay/` replay/trim/annotation, `human_pcl/`, `human_limb/`, `human_ml/`). `captures/` = original PCAPs/session data, treat as read-only input — its `remote/`, `leveled/`, `registration/` subdirs are junctions into the git-ignored data root `data/` (see the rule above). `tools/open_webui.bat` opens the board page and starts board-side `python3 -m http.server 8090` if it is down. `ML/` is dormant until the explicit activation phrase "开工 HR-09"; `文档收集（人工）/` holds vendor manuals/literature. `CLAUDE.md` has a fuller architecture write-up. `sidequests/` holds standalone side branches (e.g. `lidata_adapter/` synthetic-dataset adaptation, with its own README; explicitly not a main-line HF/GL/HC/HR artifact) and `tmp_gl_diag/` is scratch diagnostic output.

## Build & Run (Linux only; native Windows cannot build)

- `bash tools/build_ros1.sh` (catkin_make) / `bash tools/build_ros2.sh` (colcon), then `source devel/setup.bash` or `install/setup.bash`.
- Both scripts mutate the tree before building: copy `package_ros{1,2}.xml` over `package.xml` and `sed` `COMPILE_METHOD` to CATKIN/COLCON in `src/inno_lidar_ros/CMakeLists.txt` and `src/inno_lidar_msg/CMakeLists.txt`. Inspect these diffs before committing.
- `src/CMakeLists.txt` is the catkin toplevel symlink; on Windows it shows as broken/modified. Do not replace it with a regular file.
- Rebuild one package: `catkin_make --pkg <pkg>`. Driver deps: ROS, libpcap, yaml-cpp.
- `roslaunch inno_lidar_ros ros1_start.launch`; `roslaunch human_fall_detection human_fall.launch`.
- Board deploy/start/stop of the fall node: `src/human_fall_detection/scripts/deploy_human_fall.sh` inside the `slam-localization` container (immutable releases + symlink rollback; never deletes releases or touches the driver/network).
- `src/inno_lidar_ros/config/config.yaml` (`common.msg_source`: 0 off / 1 live lidar / 2 PCAP) and launch args hold machine-specific PCAP, calibration, and output paths.

## Tests

Fast and headless; no CI or root runner — run suites individually. `-W error` is required (warnings fail). Python suites from the repo root (`python` on Windows, `python3` on Linux):

- `python3 -B -W error -m unittest discover -s src/human_fall_detection/tests`.
- `python3 -B -W error -m unittest discover -s src/human_capture/tests`.
- `python3 -B -W error -m unittest discover -s src/human_follow_calibration/tests`.

JS/console suites, run from each directory: `node human_fall_lib.test.js` (`webui/human_fall`, `webui/human_fall_preview`), `node capture_lib.test.js` (`webui/human_capture`), `node human_replay_lib.test.js`, `node panel.test.js`, `node human_detect_lib.test.js`, and `node human_pipe_lib.test.js` (`pc_apps/human_replay`), `python joint_capture_test.py` (`pc_apps/console`, joint-recording backend only).

Board runtime is Python 3.8.10 / NumPy 1.17.4 (the Windows dev box runs 3.12) — keep board code 3.8-compatible and stdlib + NumPy only (no OpenCV/RKNN). Add regression cases for decoding, invalid data, ambiguity, and calibration changes. Driver changes need a ROS build plus live/PCAP publishing checks.

## Conventions & Gotchas

- C++14 (C++17 under ROS2 Humble), built `-O3 -flto -Wall`; PascalCase classes/methods with `m_` members; Python `snake_case`; 4-space indent; no repo-wide formatter/linter.
- New code/comments are commonly written in Chinese; git history uses short Chinese summaries (e.g. `优化半径滤波算法运行效率`).
- One source tree builds both ROS1 and ROS2 via `ROS_FOUND` (`#if ROS_FOUND==1/2`); keep both branches compiling. `POINT_TYPE` in `inno_lidar_ros/CMakeLists.txt` selects the struct in `src/msg/cloud_types.hpp`.
- `imu_types.hpp` comments device stamps as nanoseconds, but the publisher consumes them as seconds; this contradiction is unresolved — don't change the unit from the header comment (`deviceStampToRos` in `publish_manager.cpp`).
- Calibration and fall-detection nodes are strictly read-only: never publish vehicle/robot control commands.
- Fall config layering (`src/human_fall_detection/config/`): `default.yaml` + `geometry.yaml` are frozen; `geometry_constrained*.yaml` are immutable named variants (constrained scripts take `--constrained-config`); `human_fall.yaml` is node runtime (topics/timeouts/output); `human_fall_prod.yaml` is the board production config; `perception.yaml` holds per-`core/`-module thresholds. Driver, `webui/`, `captures/` and historical evidence stay read-only unless the task needs them; new variants get new files, not edits.
