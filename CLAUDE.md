# CLAUDE.md

## Current HF/GL workflow

Read `docs/human_fall/WORKFLOW.md` and the current work item's acceptance table first; GL-02 uses `GL02_ACCEPTANCE.md` v1. Diagnose the whole entry/state matrix before editing, fix shared root causes, and return per-ID evidence using `RETURN_TEMPLATE.md`. The latest 2026-10-01 user authorization permits Codex to dispatch in-scope rework to OpenCode CLI `opencode-go/deepseek-v4.1-flash` and review autonomously. A single production-code writer remains required; no next milestone, deployment, or capture is authorized by historical text.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

LiDAR driver ROS workspace (InnoLight/InnoSense IFW192S LiDAR) with three packages under `src/`:

- **`inno_lidar_ros`** — the driver node. Wraps the closed-source `libinno_driver` SDK (prebuilt `.so` binaries in `third_party/inno_driver/lib/{x86_64,aarch64}`, headers in `third_party/inno_driver/inno_driver/`) and publishes `/innolidar_points` (sensor_msgs/PointCloud2), `/inno_imu`, and `/device_status`. Based on the RoboSense driver template (3-clause BSD headers).
- **`inno_lidar_msg`** — custom message package (`DeviceStatus.msg`).
- **`human_follow_calibration`** — standalone ROS1 Python package (see its README.md) that calibrates a known stationary target to JSON, then can publish read-only target presence, distance, bearing, and follow error on `/human_follow/state`. Does not publish control commands by design.
- **`human_fall_detection`** — ROS1 Python package for the human-fall detection chain (HF project): point-cloud candidate extraction → tracking → fall state machine, all read-only output. Pure algorithm code lives in `core/` (no ROS imports); `scripts/human_fall_node.py` is the ROS wrapper (bounded latest-frame queue + single worker thread). Fall events append to a local JSONL log. See `docs/human_fall/` for the plan, contracts, and per-milestone (HF-xx) records.

`webui/` holds the board-served web pages (Three.js + foxglove-bridge; static files served from the RK3588 board on port 8090 via the `slam-localization` container — `open_webui.bat` opens it from Windows). `webui/human_fall/` is the production fall-detection page; `webui/human_fall_preview/` is the synthetic/replay preview. The browser only renders and sends selection/baseline requests; the board-side backend validates and acks them.

`docs/human_fall/` is the authoritative project doc tree for the fall-detection work (master plan `README.md`, `deployment.md`, contracts, HF-xx milestone/ticket/return records). `文档/` holds vendor manuals (AISC-3830) and fall-detection literature.

`captures/` holds recorded PCAP files and board configs for offline testing.

## Build

This is a Linux ROS workspace — builds must run on Linux/aarch64 board, not Windows. Both build scripts mutate the source tree before building (package.xml swap + `COMPILE_METHOD` rewrite in both CMakeLists.txt):

```bash
# ROS1 (Noetic, catkin_make)
./tools/build_ros1.sh
source devel/setup.bash

# ROS2 (colcon)
./tools/build_ros2.sh
```

The `COMPILE_METHOD` variable in `src/inno_lidar_msg/CMakeLists.txt` and `src/inno_lidar_ros/CMakeLists.txt` toggles between `CATKIN` and `COLCON`; the scripts `sed` it. Package.xml variants (`package_ros1.xml` / `package_ros2.xml`) are copied over `package.xml` by the same scripts. If a build fails, check that these files match the intended ROS version.

`src/CMakeLists.txt` is a symlink to `/opt/ros/noetic/share/catkin/cmake/toplevel.cmake` (standard catkin workspace toplevel). It shows as broken/modified on Windows — this is expected; do not replace it with a regular file.

To rebuild a single ROS1 package: `catkin_make --pkg <package_name>`.

Run the driver (ROS1): `roslaunch inno_lidar_ros ros1_start.launch` (config path can be overridden via the `~config_path` private param).

Run the fall-detection node (ROS1): `roslaunch human_fall_detection human_fall.launch`. Deploy/start/stop on the board with `src/human_fall_detection/scripts/deploy_human_fall.sh` (must run inside the `slam-localization` container; versioned releases under `$HF_DEPLOY_BASE/releases` with symlink rollback — it never deletes releases, never broad-`pkill`s, and never touches the driver, old homepage, or network).

## Architecture (inno_lidar_ros)

Data flow: `inno_lidar_node.cpp` (main, chooses ROS1/ROS2 via the `ROS_FOUND` define) → `NodeManager` (`src/manager/`) → `SourceDriver` (`src/source/source_driver.cpp`, wraps the SDK; `msg_source` config selects live lidar vs. PCAP replay) → `PublishManager` (`src/source/publish_manager.cpp`, converts SDK frames to ROS messages and publishes).

- **Dual ROS1/ROS2**: the same sources compile under either ROS version, selected by CMake options and `#if ROS_FOUND==1/2` preprocessor branches. Keep both paths compiling when touching driver code.
- **Config**: `config/config.yaml` — `common.msg_source` (`1` = live lidar, `2` = PCAP replay, `0` = off), `lidar[].driver.*` (lidar type, ports, angle/distance crop, `pcap_file`, `pcap_repeat`, calibration folder, extrinsics) and `lidar[].ros.*` (topics, frame_id).
- **Point type**: `POINT_TYPE` in CMakeLists.txt (`XYZI` / `XYZI_TIME` / `XYZI_SOURCE`) maps to `#define POINT_TYPE_*` and custom point cloud types in `src/msg/cloud_types.hpp`.
- **Device timestamps**: the SDK header comments `imu_types.hpp` stamps as nanoseconds, but the publish side interprets them as seconds — a known unresolved contradiction. Do not "fix" the unit based on the header comment alone; invalid/out-of-range stamps become the (0,0) stamp with nanosecond carry handled (see `deviceStampToRos` in `publish_manager.cpp`).
- **Fall-detection config layering** (`src/human_fall_detection/config/`): `default.yaml` (frozen HF-01 health/manifest) and `geometry.yaml` are frozen — do not change their semantics; `human_fall.yaml` is node runtime config (topics, timeouts, output session dir); `perception.yaml` holds algorithm thresholds, one section per `core/` module.
- **Calibration CSVs** in `config/ifw192s/` (azimuth/elevation, model weights, near filter) are loaded from `calibrate_folder`; `is_device_load_calibration: true` takes them from the device instead.
- SDK logging macros (`INNO_MSG`, `INNO_ERROR`, …) come from `third_party/inno_driver/inno_driver/common/inno_log.hpp`.

## Conventions

- Driver code is C++14 (C++17 under ROS2 Humble), built with `-O3 -flto -Wall`.
- New code/comments in this repo are commonly written in Chinese; match the surrounding style.
- C++ uses PascalCase classes/methods with `m_` member prefix; Python uses `snake_case`; 4-space indent for both. No repo-wide formatter or linter is configured.
- Both calibration and fall-detection nodes are strictly read-only on the system: they never publish vehicle/robot control commands.
- Git history uses short Chinese action summaries (e.g. `优化半径滤波算法运行效率`); no enforced prefix. Keep commits focused.
- `human_follow_calibration` tests run with: `python3 -B -W error -m unittest discover -s src/human_follow_calibration/tests -v` (Python stdlib + NumPy only).
- `human_fall_detection` tests run with: `python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v` (test files map to HF milestones: `test_hf01_health.py`, `test_hf02_timebase.py`, …).
- `webui` JS tests run with node, from inside the page directory: `cd webui/human_fall && node human_fall_lib.test.js` (same for `human_fall_preview`).
- Board targets Python 3.8.10 / NumPy 1.17.4 under ROS Noetic; first-version fall code deliberately uses only stdlib + NumPy (no OpenCV/RKNN). `evaluate_sessions.py` uses stdlib JSON only.
