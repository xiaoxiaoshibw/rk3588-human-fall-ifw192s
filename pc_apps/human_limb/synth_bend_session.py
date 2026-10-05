# -*- coding: utf-8 -*-
"""synth_bend_session.py — 合成一段「直立 5s + 弯腰 2s + 直立 5s + 弯腰 2s + 直立 5s」
会话点云， 拿来给 limb_v2 做 ground-truth 验证。

输出 meta.json + points.bin 到当前目录。
"""
import json
import numpy as np
import os

FPS = 10
N_FRAMES = 190  # 19s
H_RADAR = 0.0
N_LIDAR_PTS_PER_FRAME = 3000
N_PERSON_BASE = 300
PERSON_X = 2.0
PERSON_Y = -1.0
PERSON_STAND_H = (0.05, 1.85)    # 站立脚到头
PERSON_BEND_H = (0.05, 0.85)     # 弯腰头到小腿

rng = np.random.default_rng(7)


def person_pts(bend_deg, n=N_PERSON_BASE):
    """bend_deg: 0=stand, 90=fully bent."""
    t = bend_deg / 90.0
    z_lo = PERSON_STAND_H[0] + (PERSON_BEND_H[0] - PERSON_STAND_H[0]) * t
    z_hi = PERSON_STAND_H[1] + (PERSON_BEND_H[1] - PERSON_STAND_H[1]) * t
    z = rng.uniform(z_lo, z_hi, n)
    # x 在弯腰时往前探
    lean_x = PERSON_X + t * 0.4
    x = rng.normal(lean_x, 0.08, n)
    y = rng.normal(PERSON_Y, 0.10, n)
    return np.column_stack([x, y, z])


def environment_pts():
    """固定家具： 沙发 (1.0, 0.7, z<0.6) + 高柜 (2.8, -2.0, z 0..2.2) + 地."""
    n_sofa = rng.uniform(1.0-0.4, 1.0+0.4, 800)
    n_sofa_y = rng.uniform(0.7-0.4, 0.7+0.4, 800)
    n_sofa_z = rng.uniform(0.05, 0.62, 800)
    sofa = np.column_stack([n_sofa, n_sofa_y, n_sofa_z])
    n_cab = rng.normal(2.8, 0.1, 1200)
    n_cab_y = rng.normal(-2.0, 0.1, 1200)
    n_cab_z = rng.uniform(0.0, 2.2, 1200)
    cab = np.column_stack([n_cab, n_cab_y, n_cab_z])
    # 地面密集噪声
    n_ground = 800
    gx = rng.uniform(1.0, 4.0, n_ground)
    gy = rng.uniform(-2.0, 1.5, n_ground)
    gz = rng.normal(0.0, 0.02, n_ground)
    gnd = np.column_stack([gx, gy, gz])
    return np.vstack([sofa, cab, gnd])


def bend_schedule(fi):
    """0-49 stand, 50-69 ramp down, 70-89 hold bent, 90-109 ramp up, 110-189 stand."""
    if fi < 50:
        return 0.0
    if fi < 70:
        return 90.0 * (fi - 50) / 20.0
    if fi < 90:
        return 90.0
    if fi < 110:
        return 90.0 * (1 - (fi - 90) / 20.0)
    return 0.0


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    env = environment_pts()
    frames_meta = []
    all_rows = []
    for fi in range(N_FRAMES):
        bend = bend_schedule(fi)
        person = person_pts(bend)
        xyz = np.vstack([person, env])
        n = len(xyz)
        # 28-byte rows: x,y,z,i (f32×4) + ring (u16) + pad + timestamp (f32) + pad
        ring = np.zeros(n, dtype=np.uint16)
        pad1 = np.zeros(n, dtype=np.uint16)
        ts = np.full(n, 200000.0 + fi * 0.1, dtype=np.float32)
        pad2 = np.zeros(n, dtype=np.float32)
        intensity = rng.uniform(30, 200, n).astype(np.float32)
        buf = np.zeros((n, 28), dtype=np.uint8)
        f32cols = buf.view(np.float32).reshape(n, 7)
        f32cols[:, 0] = xyz[:, 0]
        f32cols[:, 1] = xyz[:, 1]
        f32cols[:, 2] = xyz[:, 2]
        f32cols[:, 3] = intensity
        f32cols[:, 5] = ts
        u16cols = buf.view(np.uint16).reshape(n, 14)
        u16cols[:, 8] = ring
        u16cols[:, 9] = pad1
        all_rows.append(buf)
        frames_meta.append({
            "bag_time_sec": 200000.0 + fi * 0.1,
            "count_points": n,
            "dropped_points": 0,
            "offset_points": fi * n,
            "seq": fi,
            "stamp_nanosec": 0,
            "stamp_sec": int(200000 + fi * 0.1),
            "synthetic_bend_deg": float(bend),
        })
    blobs = np.concatenate(all_rows, axis=0)
    with open(os.path.join(out_dir, "points.bin"), "wb") as fh:
        fh.write(blobs.tobytes())
    meta = {
        "format": "human_capture_session",
        "format_version": 1,
        "session_id": "synth_bend_v1",
        "total_points": int(sum(f["count_points"] for f in frames_meta)),
        "total_dropped_points": 0,
        "frames": frames_meta,
        "point_layout": {"fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
                           "stride_bytes": 28},
        "point_stride_bytes": 28,
        "duration_sec": N_FRAMES / FPS,
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    # ai_labels ground truth
    ai = {
        "session_id": "synth_bend_v1",
        "frames": {
            "range_syntax": "",
            "0-49":   {"posture": "stand", "x": 2.0, "y": -1.0, "r_xy": 0.7},
            "50-109": {"posture": "bend",  "x": 2.0, "y": -1.0, "r_xy": 0.7},
            "110-189": {"posture": "stand", "x": 2.0, "y": -1.0, "r_xy": 0.7},
        },
    }
    with open(os.path.join(out_dir, "ai_labels.json"), "w") as fh:
        json.dump(ai, fh, ensure_ascii=False)
    print("synthetic session →", out_dir)


if __name__ == "__main__":
    main(r"D:\Code\ldiar\captures\r remote\synth_bend_v1".replace(" ", ""))
