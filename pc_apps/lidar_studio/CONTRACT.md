# 雷达体态工作台（LiDAR Studio）通信与数据契约

> 适用版本：`LDSF v1`（LiDAR Studio Frame v1）+ `local_range/1` 统一状态视图 + `human_physical_v1`。  
> 语义边界：所有状态、姿态、几何骨架、置信分级与跌倒疑似均来自纯雷达几何/运动学计算；摄像头仅用于展示与人工对照，绝不进入任何算法链。

---

## 1. 二进制帧协议（LDSF v1）

后端通过 WebSocket `/ws` 以单条 Binary Message 推送一帧完整数据包（点云 + 2D 距离图 + 状态 JSON）。全部整型与浮点采用 **小端字节序（Little-Endian）**，头部及浮点段保证 4 字节对齐，浏览器端可直接以 `DataView` / `TypedArray` 零拷贝视图解码。

### 1.1 固定头部（40 Bytes，`<4sBBHIHHIIIIII`）

| 偏移 | 长度 | 类型 | 字段名 | 说明 |
|---:|---:|---|---|---|
| 0 | 4 | `char[4]` | `magic` | 固定 ASCII `"LDSF"` (`0x4C 0x44 0x53 0x46`) |
| 4 | 1 | `uint8` | `version` | 协议版本号，当前固定 `1` |
| 5 | 1 | `uint8` | `header_flags` | bit0(`0x01`): `has_intensity`；bit1(`0x02`): `has_range_mask`；bit2(`0x04`): `is_live` |
| 6 | 2 | `uint16` | `decimation` | 背景点降采样步长（`1`=全量、`2`=每 2 点取 1 点）；目标/回收/其他轨迹点 **永不降采样** |
| 8 | 4 | `uint32` | `point_count` | 本帧携带的 3D 点数 `N` |
| 12 | 2 | `uint16` | `range_height` | 距离图行数 `H`（IFW192S 为 `192`；无距离图时为 `0`） |
| 14 | 2 | `uint16` | `range_width` | 距离图列数 `W`（IFW192S 为 `256`；无距离图时为 `0`） |
| 16 | 4 | `uint32` | `xyz_len` | `xyz` 段字节数，必须等于 `N * 12` |
| 20 | 4 | `uint32` | `intensity_len` | `intensity` 段字节数，`has_intensity ? N * 4 : 0` |
| 24 | 4 | `uint32` | `range_mm_len` | `range_mm` 段字节数，必须等于 `H * W * 2` |
| 28 | 4 | `uint32` | `point_flags_len` | `point_flags` 段字节数，必须等于 `N` |
| 32 | 4 | `uint32` | `range_mask_len` | `range_mask` 段字节数，`has_range_mask ? H * W : 0` |
| 36 | 4 | `uint32` | `json_len` | 末尾 UTF-8 状态 JSON 字节数（`> 0`） |

包总字节数必须严格等于：`40 + xyz_len + intensity_len + range_mm_len + point_flags_len + range_mask_len + json_len`。

### 1.2 载荷段顺序（紧随 40 字节头部）

1. **`xyz`** (`float32[N * 3]`)：原始雷达传感器坐标系 `(x, y, z)`，单位米（m）。
2. **`intensity`** (`float32[N]`，可选)：对应每点的回波反射强度；`intensity_len == 0` 时省略。
3. **`range_mm`** (`uint16[H * W]`)：**已执行 `nativeTransform: rotate180`**（即 `frame.range_m[::-1, ::-1]`）的毫米距离矩阵，行主序（row-major）；`0` 表示无效/无测量，`1..65535` 表示毫米径向距离。
   - **显示坐标与原生网格对应**：显示像素 `(row, col)`（`0 <= row < H`, `0 <= col < W`）对应原生雷达网格 `(nativeRing = H - 1 - row, nativeCol = W - 1 - col)`；该像素坐标系与 `local_range.skeleton.nodes[*].imageXY`（`[x, y] = [col, row]`）完全一致。
   - **色标契约**：与 `src/human_fall_detection/core/range_live.py::preview_rgb` 逐公式一致，显示区间 `[0.1 m, 8.0 m]`：
     - `mm == 0` → `rgb(0, 0, 0)`
     - `t = clamp((mm / 1000.0 - 0.1) / 7.9, 0, 1)`
     - `R = floor(255 * (1 - t))`, `G = floor(255 * (1 - |2*t - 1|))`, `B = floor(255 * t)`
4. **`point_flags`** (`uint8[N]`)：每点语义掩码位：
   - `0x01` (`FLAG_TARGET_CORE`)：当前主目标核心点（`target_source_rows`）
   - `0x02` (`FLAG_RECOVERY_ADDED`)：`human_physical_v1.recovery.added_rows` 局部完整回收新增点（几何候选，非真值）
   - `0x04` (`FLAG_OTHER_TRACK`)：非主目标的其他实测轨迹点
   - `0x08` (`FLAG_FOREGROUND`)：其余前景点
   - `0x00`：背景/场景点
5. **`range_mask`** (`uint8[H * W]`，可选)：与 `range_mm` 同向（`rotate180`）的像素级掩码，复用上述 bit 位；`range_mask_len == 0` 时省略。
6. **`state_json`** (UTF-8 JSON)：严格不含 `NaN`/`Infinity`。

---

## 2. 统一状态 JSON 契约（`state_json`）

回放模式与实时模式产出同一套状态结构，顶层对齐 `src/human_fall_detection/core/range_engine.py:205-243`，并附带 `human_physical_v1`、`camera` 与 `studio` 视图元数据：

```json
{
  "schema_version": 1,
  "kind": "target_state",
  "mode": "replay",
  "session_id": "cap_20261028_houdao",
  "frame_index": 83,
  "frame_count": 169,
  "stamp_sec": 165728.510223,
  "relative_time_sec": 6.6345,
  "time_epoch": 0,
  "target_mode": "local_range_automatic",
  "track_id": "g0_t0001",
  "track_status": "locked",
  "observability": "valid",
  "bbox_observed": true,
  "position_predicted": false,
  "fall_status": "suspected",
  "acquisition": { "reason": "current_target" },
  "semantic": "unknown",
  "confirmed_enabled": false,
  "local_range": {
    "version": 1,
    "heightMedianM": 0.28,
    "measurement": {
      "topHeightM": 0.44,
      "horizontalExtentM": 1.12,
      "descentRateMps": 0.05,
      "axisVerticality": 0.21
    },
    "background": { "status": "ready", "configSha256": "...", "declaration": "offline_whole_recording_quantile" },
    "ground": {
      "available": true,
      "reason": "bound_plane_geometry_only",
      "physicalGroundTruth": "UNKNOWN",
      "displayPlane": {
        "normal": [-0.46, -0.03, 0.88],
        "offsetM": 1.36,
        "frameId": "innolidar",
        "scope": "bound_display_only"
      }
    },
    "posture": { "state": "lying_candidate", "reason": "sustained_low_horizontal_geometry", "durationSec": 1.61, "humanSemantic": "UNKNOWN", "fallEvent": false },
    "fallEvidence": { "state": "suspected", "reason_codes": ["measured_descent", "sustained_low_posture", "lying_pose_supported"], "confirmed_enabled": false, "semantic": "UNKNOWN" },
    "demoFallCandidate": { "variant": "horizontal_low_posture_v1", "level": 1, "active": true, "state": "suspected", "durationSec": 1.5, "confirmedEnabled": false, "semantic": "UNKNOWN" },
    "groundAlert": { "variant": "ground_alert_v1", "state": "suspected_ground_posture", "active": true, "confirmedEnabled": false, "semantic": "UNKNOWN" },
    "skeleton": {
      "version": "0.1.0",
      "semantic": "GEOMETRIC_REGIONS",
      "anatomicalJoints": "UNKNOWN",
      "reason": "point_supported_regions",
      "nodes": { "TOP": { "xyz": [x, y, z], "imageXY": [c, r], "supportCount": 18 } },
      "edges": [["TOP", "UPPER"], ["UPPER", "CENTER"], ["CENTER", "BASE"]]
    },
    "depth": {
      "metadata": { "format": "lidar_range_image", "version": 2, "width": 256, "height": 192, "nativeTransform": "rotate180", "validPixels": 41000, "targetPixels": 403 }
    },
    "bbox": {
      "raw": { "min": [x0, y0, z0], "max": [x1, y1, z1], "center": [cx, cy, cz] },
      "leveled": { "min": [x0, y0, z0], "max": [x1, y1, z1], "center": [cx, cy, cz] }
    }
  },
  "performance": {
    "process_ms": 18.4,
    "runtime": { "decode_ms": 1.2, "background_ms": 0.4, "tracking_ms": 2.8, "event_chain_ms": 6.1, "physical_total_ms": 11.2 }
  },
  "diagnostics": {
    "tracking": { "reason": "current_target", "tracks": [...] }
  },
  "human_physical_v1": {
    "variant": "human_physical_v1",
    "revision": "physical_v1_r2",
    "status": "ok",
    "error_codes": [],
    "target_track_id": "g0_t0001",
    "target_belief": { "belief_state": "CONFIRMED_HUMAN", "log_odds": 5.0, "belief_score": 0.9933, "veto_active": false, "evidence_codes": [...], "rejection_reasons": [...], "deltas": { "geom": 0.35, "normal": 0.4, "kin": 0.0, "total": 0.75 }, "semantic_truth": "UNKNOWN" },
    "kinematics_noise_floor": { "calibrated": false, "source": null, "ivel_floor_mps": null, "wrate_floor_mps": null },
    "recovery": { "status": "rejected", "recovery_rejected_reason": "expansion_ratio_exceeded", "core_count": 403, "added_count": 0, "recovered_count": 403, "completeness": "UNKNOWN", "semantic": "UNKNOWN" },
    "tracks": { "g0_t0001": { "belief": {...}, "prior": {...}, "kinematics": {...} } },
    "semantic_truth": "UNKNOWN"
  },
  "camera": {
    "available": true,
    "state": "ready",
    "videoFrameIndex": 68,
    "deltaMs": -12.4,
    "alignment": "receipt_time_unverified"
  }
}
```

---

## 3. HTTP REST 与 WebSocket `/ws` 控制协议

默认单端口监听 `http://127.0.0.1:8960`。

### 3.1 HTTP 端点

| 方法与路径 | 说明 |
|---|---|
| `GET /` / `GET /{asset}` | 静态页面资源（`web/`，禁止路径穿越） |
| `GET /api/sessions` | 返回可用回放会话列表：`sid`, `title`, `frames`, `duration_sec`, `has_camera`, `camera_frames`, `cached`, `cache_key` |
| `GET /api/sessions/{sid}/summary` | 返回已缓存会话摘要（`stamp_secs`, `relative_times`, `display_plane`, `timeline` 逐帧状态色带数组与轨迹摘要） |
| `GET /api/camera/{sid}/{frame}` | 返回对齐后的 `image/jpeg`；附加响应头 `X-Camera-State` (`ready`/`outside`/`unavailable`)、`X-Camera-Delta-Ms`、`X-Camera-Frame-Index`、`X-Camera-Alignment: receipt_time_unverified`。超 ±250 ms 返回 `204 No Content`，无相机会话返回 `404`。 |
| `GET /api/live/status` | 执行板端可达性探测并返回 `{reachable, ws_reachable, camera_reachable, reason, board_ws, board_camera, live_stats, camera_stats}`；不可达时不伪造数据。 |
| `GET /api/live/camera` | 多客户端扇出 `multipart/x-mixed-replace; boundary=frame`（板端仅保持一条 `:8081/stream` 上游连接；不可达返回 `503` JSON 说明）。 |

### 3.2 WebSocket `/ws` 控制指令（Client → Server, JSON）

- `{"cmd": "open", "sid": "cap_20261028_houdao", "frame": 0, "decimation": 2}`：加载或命中缓存，完成后发 `session_ready` + 第 `frame` 帧二进制包；首次计算期间持续推送 `loading` 进度消息。
- `{"cmd": "play"}` / `{"cmd": "pause"}`：按源时间戳（`stamp_secs`）开始或暂停回放。
- `{"cmd": "seek", "frame": 83}`：跳转并精确推送指定帧（同时自动暂停或重锚源时钟）。
- `{"cmd": "step", "delta": 1}`：暂停并步进 `±delta` 帧。
- `{"cmd": "rate", "rate": 1.0}`：调整回放倍速（`0.25` ~ `4.0`）。
- `{"cmd": "decimation", "decimation": 2}`：调整背景降采样步长（`1` / `2` / `3` / `4`）。
- `{"cmd": "mode", "mode": "replay" | "live", "empty_prefix_frames": null}`：切换回放或只读实时模式（切换实时会先探测板端，不可达发 `live_status` 告知 `"板端不可达"`）。
- `{"cmd": "live_probe"}`：手动刷新板端可达性探测。

### 3.3 WebSocket `/ws` 下行消息（Server → Client）

- **Text JSON**：
  - `{"type": "loading", "sid": "...", "stage": "pass1_decode" | "fit_ground" | "pass2_infer" | "cache_write", "current": 12, "total": 169, "message": "..."}`
  - `{"type": "session_ready", "sid": "...", "summary": {...}}`
  - `{"type": "playback_state", "playing": bool, "rate": float, "frame": int, "decimation": int}`
  - `{"type": "live_status", "reachable": bool, "ws_reachable": bool, "camera_reachable": bool, "status": "offline" | "connecting" | "streaming" | "error", "reason": "...", ...}`
  - `{"type": "error", "code": "...", "message": "..."}`
- **Binary**：`LDSF v1` 完整帧包（单连接独立单槽发送队列；连续播放时慢客户端自动丢弃未发旧帧，不堆积延迟；`seek`/`step`/`open` 必达）。
