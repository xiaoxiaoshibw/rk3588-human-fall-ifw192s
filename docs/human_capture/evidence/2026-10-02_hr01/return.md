# HR-01 return

| ID | 结论 | 证据 |
|----|------|------|
| F1 过滤 | ✅ | `pc_apps/human_replay/fetch_lib_test.py::TestPick` 6 全绿（过滤 ready&&download_requested&&!transferred&&paths 齐、跳过 transferred=null/None） |
| F2 顺序 | ✅ | `TestPick.test_order_stable_oldest_first`：created_iso 升序，老会话 a_old 在前 |
| F3 速度 | ✅ | `cap_20261002_165321` (points.bin 39.9MB) 一次 fetch 全过，scp 带 `-l 70000`；跑期间 8090 human_capture 页面无卡死反馈 |
| F4 校验 | ✅ | `fetch.py::_local_verify`：`meta.stride=28`（板上真实 layout）+ sha256(frames 点区实测字节=1424701×28B) 通过，digest 前缀 `b2a706b7`；`_validate_meta` 同时显式拒绝旧 16B 契约 |
| F5 容错 | ✅ | `_fail` 分支统一清 .part + PATCH `state=ready + error=hr01:...`；`pick_sessions` 显式跳过残 transfer 状态，由 server 状态机（ready↔transferring）仲裁重入 |
| F6 回报 | ✅ | `GET /api/v1/sessions/cap_20261002_165321` → `{state:"transferred", transferred:true, error:"hr01:path repair"}`（error 字段是修补路径时留的，成功路径不写 error） |
| F7 路径 | ✅ | `pc_apps/human_replay/fetch.py::_host_path` 容器路径→宿主路径映射 + 容器内 symlink `/root/catkin_ws/captures_remote → /mnt/captures/captures_remote`（船新会话直接对得上，老会话也已修 paths） |

## 实链验证（2026-10-02 17:59）

```
[17:59:06] OK   cap_20261002_165321: meta_points=1424701 digest=b2a706b7405f5d24
```

- 本地：`D:\Code\ldiar\captures\remote\cap_20261002_165321\meta.json (6887B) + points.bin (39891628B)`，无 `.part`
- 板端：state=transferred（FIFO 可收）

## 单测输出（stdlib，Win11/Python 3.12）

```
test_filters ... ok
test_order_stable_oldest_first ... ok
test_accepts_real_board_layout ... ok
test_rejects_old_16b_layout ... ok
test_rejects_frames_beyond_bin ... ok
test_region_ignores_trailing_pad ... ok
Ran 6 tests in 0.009s — OK
```
