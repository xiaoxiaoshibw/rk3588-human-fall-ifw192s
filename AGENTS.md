# Repository Guidelines

## Work-item workflow (read first)

Two independent milestone systems, each with its own authoritative docs. Don't cross them:

- **HF/GL** (fall detection): `docs/human_fall/WORKFLOW.md` (v2) is the entry point. Read it before any HF/GL implementation or review. Only the topmost dated entry there plus the user's explicit instruction is a current authorization; everything below is history and cannot authorize a new milestone, deployment, capture, network/driver change, or model switch.
- **HC/HR** (capture/replay/annotation): `docs/human_capture/README.md` before touching `src/human_capture/`, `webui/human_capture/`, or `pc_apps/human_replay/`.

Rules that hold in both:

- Each item has exactly one current versioned acceptance table, linked from that item's entry above. Report `PASS/FAIL/NOT_RUN/BLOCKED` against its IDs; test totals are records, not completion. Device/physics/deploy/capture conclusions default to `NOT_RUN/BLOCKED` until a current instruction explicitly authorizes them.
- One production-code writer per item. Codex may dispatch in-scope rework to OpenCode CLI `opencode-go/deepseek-v4.1-flash` and reviews read-only. Any writer must load the `ponytail` skill first and record its usage path in the return; returns without it are rejected.
- Records: evidence → `docs/<track>/evidence/<date>_<item>_r<N>/`; return → append to `docs/<track>/returns/<ID>.md` per `docs/human_fall/RETURN_TEMPLATE.md`; HF/GL reviews → `docs/human_fall/REVIEW_LOG.md`. Never overwrite older evidence or backfill past records.
- The tree is deliberately dirty and mixes untracked production source (all of `src/human_fall_detection/`, `tools/`, parts of `docs/human_capture/`) with a pending relocation (tracked root `build_ros*.sh` / `open_webui.bat` / `rk.txt` show deleted; untracked copies live in `tools/`; `文档/` was renamed to `文档收集（人工）/`). Baseline branch/HEAD/SHA over all files including untracked. Never `reset`/`checkout`/`clean`, commit, push, deploy, or capture unless explicitly asked.

## Repository

Linux ROS workspace (InnoLight/InnoSense IFW192S LiDAR) plus PC/browser tooling. Five packages under `src/`:

- `inno_lidar_ros/` — C++ driver; `node/inno_lidar_node.cpp` → `src/manager/` → `src/source/` (SDK wrapper + publisher). Publishes `/innolidar_points`, `/inno_imu`, `/device_status`. `third_party/inno_driver/` holds closed-source headers and prebuilt x86_64/aarch64 `.so`.
- `inno_lidar_msg/` — `DeviceStatus.msg` only.
- `human_fall_detection/` — ROS1 Python fall detection (HF/GL). Pure algorithms in `core/` (no ROS imports); `scripts/human_fall_node.py` is the ROS wrapper. Work is milestone-gated; `docs/human_fall/` is the authoritative doc tree.
- `human_capture/` — ROS1 Python capture server (HC): board REST on `:8766`, reuses `human_fall_detection/scripts/record_session.py` for bags, `core/bag2session.py` converts `.bag` → `meta.json` + `points.bin`. Format contract in `docs/human_capture/README.md` §2.
- `human_follow_calibration/` — ROS1 Python calibration + read-only monitor publishing `/human_follow/state` (detail in its `README.md`).

Elsewhere: `webui/` = board-served Three.js pages (`human_fall/` production, `human_fall_preview/` replay preview, `human_capture/` record console, `dist/webui-minimal/` external bundle); the browser only renders and sends selection/record requests. `pc_apps/` = Windows-side apps (`console/` packaged Console.exe + root `open_console.bat`, `human_replay/` replay/trim/annotation, `human_pcl/`, `human_limb/`, `human_ml/`). `captures/` = original PCAPs/session data, treat as read-only input. `tools/open_webui.bat` opens the board page and starts board-side `python3 -m http.server 8090` if it is down. `ML/` is dormant until the explicit activation phrase "开工 HR-09"; `文档收集（人工）/` holds vendor manuals/literature. `CLAUDE.md` has a fuller architecture write-up.

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

- `python3 -B -W error -m unittest discover -s src/human_fall_detection/tests` (files map to milestones: `test_hf*.py`, `test_gl*.py`, `test_gli*.py`).
- `python3 -B -W error -m unittest discover -s src/human_capture/tests`.
- `python3 -B -W error -m unittest discover -s src/human_follow_calibration/tests`.

JS/console suites, run from each directory: `node human_fall_lib.test.js` (`webui/human_fall`, `webui/human_fall_preview`), `node capture_lib.test.js` (`webui/human_capture`), `node human_replay_lib.test.js` and `node panel.test.js` (`pc_apps/human_replay`), `node console_html.test.js` and `python console_test.py` (`pc_apps/console`).

Board runtime is Python 3.8.10 / NumPy 1.17.4 (the Windows dev box runs 3.12) — keep board code 3.8-compatible and stdlib + NumPy only (no OpenCV/RKNN). Add regression cases for decoding, invalid data, ambiguity, and calibration changes. Driver changes need a ROS build plus live/PCAP publishing checks.

## Conventions & Gotchas

- C++14 (C++17 under ROS2 Humble), built `-O3 -flto -Wall`; PascalCase classes/methods with `m_` members; Python `snake_case`; 4-space indent; no repo-wide formatter/linter.
- New code/comments are commonly written in Chinese; git history uses short Chinese summaries (e.g. `优化半径滤波算法运行效率`).
- One source tree builds both ROS1 and ROS2 via `ROS_FOUND` (`#if ROS_FOUND==1/2`); keep both branches compiling. `POINT_TYPE` in `inno_lidar_ros/CMakeLists.txt` selects the struct in `src/msg/cloud_types.hpp`.
- `imu_types.hpp` comments device stamps as nanoseconds, but the publisher consumes them as seconds; this contradiction is unresolved — don't change the unit from the header comment (`deviceStampToRos` in `publish_manager.cpp`).
- Calibration and fall-detection nodes are strictly read-only: never publish vehicle/robot control commands.
- Fall config layering (`src/human_fall_detection/config/`): `default.yaml` + `geometry.yaml` are frozen; `geometry_constrained*.yaml` are immutable named variants (constrained scripts take `--constrained-config`); `human_fall.yaml` is node runtime (topics/timeouts/output); `human_fall_prod.yaml` is the board production config; `perception.yaml` holds per-`core/`-module thresholds. GL work treats the driver, `webui/`, `captures/`, and historical evidence as read-only unless the current item says otherwise; new variants get new files/IDs, not edits.
