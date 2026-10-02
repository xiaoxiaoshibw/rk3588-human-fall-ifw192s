# Repository Guidelines

## Current work-item workflow

For HF/GL work, read `docs/human_fall/WORKFLOW.md` before implementation or review. Use the work item's versioned acceptance table; GL-02 uses `docs/human_fall/GL02_ACCEPTANCE.md`. The user's latest 2026-10-01 authorization permits Codex to dispatch in-scope rework directly to OpenCode CLI `opencode-go/deepseek-v4.1-flash`, follow progress, and independently review the shared workspace without manual forwarding. Preserve one production-code writer, check all supported entries and state transitions, and report against acceptance IDs rather than test totals. Historical instructions do not authorize new milestones, deployment, or capture.

Linux ROS workspace (InnoLight/InnoSense IFW192S LiDAR) plus the RK3588 human-fall stack. Four packages under `src/`:

- `inno_lidar_ros/` — C++ driver; `node/inno_lidar_node.cpp` → `src/manager/` → `src/source/` (SDK wrapper + publisher). Publishes `/innolidar_points`, `/inno_imu`, `/device_status`. `third_party/inno_driver/` holds closed-source headers and prebuilt x86_64/aarch64 `.so`.
- `inno_lidar_msg/` — `DeviceStatus.msg` only.
- `human_follow_calibration/` — ROS1 Python calibration + read-only monitor publishing `/human_follow/state` (detail in its `README.md`).
- `human_fall_detection/` — ROS1 Python fall detection. Pure algorithms in `core/` (no ROS imports); `scripts/human_fall_node.py` is the ROS wrapper. Work is milestone-gated (HF-xx); `docs/human_fall/` is the authoritative doc tree, and `config/default.yaml` + `geometry.yaml` are frozen.

`webui/` holds board-served Three.js pages (`human_fall/` production, `human_fall_preview/` replay preview); the browser only renders and sends selection requests. `open_webui.bat` opens the board page and starts the board-side `python3 -m http.server 8090` if it is down. `文档/` holds vendor manuals/literature. `CLAUDE.md` has a fuller architecture write-up.

## Build & Run (Linux only; native Windows cannot build)

- `bash build_ros1.sh` (catkin_make) / `bash build_ros2.sh` (colcon), then `source devel/setup.bash` or `install/setup.bash`.
- Both scripts mutate the tree before building: copy `package_ros{1,2}.xml` over `package.xml` and `sed` `COMPILE_METHOD` to CATKIN/COLCON in `src/inno_lidar_ros/CMakeLists.txt` and `src/inno_lidar_msg/CMakeLists.txt`. Inspect these diffs before committing.
- `src/CMakeLists.txt` is the catkin toplevel symlink; on Windows it shows as broken/modified. Do not replace it with a regular file.
- Rebuild one package: `catkin_make --pkg <pkg>`. Driver deps: ROS, libpcap, yaml-cpp.
- `roslaunch inno_lidar_ros ros1_start.launch`; `roslaunch human_fall_detection human_fall.launch`.
- Board deploy/start/stop of the fall node: `src/human_fall_detection/scripts/deploy_human_fall.sh` inside the `slam-localization` container (immutable releases + symlink rollback; never deletes releases or touches the driver/network).
- `config/config.yaml` (`common.msg_source`: 0 off / 1 live lidar / 2 PCAP) and launch args hold machine-specific PCAP, calibration, and output paths.

## Tests

The pure suites run without ROS/board and are fast (verified on Windows with `python`/`node`):

- `python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v` (211 tests; files map to milestones, e.g. `test_hf01_health.py`).
- `python3 -B -W error -m unittest discover -s src/human_follow_calibration/tests -v` (2 tests).
- `cd webui/human_fall && node human_fall_lib.test.js` (18 checks; same pattern for `human_fall_preview`).

Board target is Python 3.8.10 / NumPy 1.17.4; first-version fall code deliberately uses only stdlib + NumPy (no OpenCV/RKNN). Add regression cases for decoding, invalid data, ambiguity, and calibration changes. Driver changes need a ROS build plus live/PCAP publishing checks.

## Conventions & Gotchas

- C++14 (C++17 under ROS2 Humble), built `-O3 -flto -Wall`; PascalCase classes/methods with `m_` members; Python `snake_case`; 4-space indent; no repo-wide formatter/linter.
- New code/comments are commonly written in Chinese; git history uses short Chinese summaries (e.g. `优化半径滤波算法运行效率`).
- One source tree builds both ROS1 and ROS2 via `ROS_FOUND` (`#if ROS_FOUND==1/2`); keep both branches compiling. `POINT_TYPE` in `inno_lidar_ros/CMakeLists.txt` selects the struct in `src/msg/cloud_types.hpp`.
- `imu_types.hpp` comments device stamps as nanoseconds, but the publisher consumes them as seconds; this contradiction is unresolved — don't change the unit from the header comment (`deviceStampToRos` in `publish_manager.cpp`).
- Calibration and fall-detection nodes are strictly read-only: never publish vehicle/robot control commands.
- Fall config layering: `default.yaml`/`geometry.yaml` frozen; `human_fall.yaml` runtime (topics/timeouts/output); `perception.yaml` thresholds per `core/` module.
