"""纸飞机（运动目标）逐帧距离/方位：23_RANGE.json。

用法：
    python -B -W error range_report.py --out <evidence_dir>
雷达在显示系的位置由配平变换 t=[0,0,d] 给出（源系原点 = 雷达）；地面 z=0。
同时给出板端裁剪门 |az|<=60°、|el|<=45° 的对照（判断目标何时出视场）。
"""
import argparse
import json
from pathlib import Path

import numpy as np

AZ_LIMIT_DEG = 60.0
EL_LIMIT_DEG = 45.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    parser.add_argument("--leveling", default="02_LEVELING_cap_20261014_164522.json")
    args = parser.parse_args()
    out = Path(args.out)
    payload = json.loads((out / args.track).read_text(encoding="utf8"))
    leveling = json.loads((out / args.leveling).read_text(encoding="utf8"))
    estimator = leveling["report"]["estimators"]["tls"]
    sensor = np.array([0.0, 0.0, float(np.asarray(estimator["t"])[2])])
    rows = []
    first_stamp = None
    for row in payload["track"]:
        if not row["detected"]:
            continue
        if first_stamp is None:
            first_stamp = row["stamp_s"]
        center = np.asarray(row["center"])
        delta = center - sensor
        horizontal = float(np.linalg.norm(delta[:2]))
        rows.append({
            "frame": row["frame"],
            "t_s": round(row["stamp_s"] - first_stamp, 3),
            "center_display_m": [round(float(v), 3) for v in center],
            "slant_range_m": round(float(np.linalg.norm(delta)), 3),
            "horizontal_range_m": round(horizontal, 3),
            "height_vs_sensor_m": round(float(delta[2]), 3),
            "azimuth_deg": round(float(np.degrees(np.arctan2(delta[0], delta[1]))), 1),
            "elevation_deg": round(float(np.degrees(np.arctan2(delta[2], horizontal))), 1),
            "inside_fov_crop": bool(abs(np.degrees(np.arctan2(delta[0], delta[1]))) <= AZ_LIMIT_DEG
                                   and abs(np.degrees(np.arctan2(delta[2], horizontal))) <= EL_LIMIT_DEG),
        })
    report = {
        "object": "moving target tracked in 20_TRACK_V2.json (user: paper plane)",
        "sensor_display_m": [round(float(v), 3) for v in sensor],
        "sensor_height_above_ground_m": round(float(sensor[2]), 3),
        "frames": rows,
        "summary": {
            "first_slant_range_m": rows[0]["slant_range_m"] if rows else None,
            "last_slant_range_m": rows[-1]["slant_range_m"] if rows else None,
            "range_min_m": min(r["slant_range_m"] for r in rows) if rows else None,
            "range_max_m": max(r["slant_range_m"] for r in rows) if rows else None,
            "left_crop_azimuth_at_frame": next((r["frame"] for r in rows if not r["inside_fov_crop"]), None),
        },
        "other_object_note": "6.5 m static fixture-like object (06_TRACK_REAL.json) is a different object, not the paper plane",
    }
    with (out / "23_RANGE.json").open("x", encoding="utf8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
