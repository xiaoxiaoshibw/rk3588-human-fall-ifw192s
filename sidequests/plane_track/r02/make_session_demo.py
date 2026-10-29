"""R2：给"任意会话"生成小目标跟踪 3D 页（PLANE-01 生成器的参数化变体）。

为什么另开一个文件：`sidequests/plane_track/r01/make_3d_demo3.py` 把 PLANE-01 的
leveled job（164522 / 131958 空场）和"运动窗口 8–17 帧"写死在 main() 里，改动它会
改掉 PLANE-01 证据里记录的源码 SHA。本文件按仓库纪律"新变体用新文件/新 ID"：
复用 r01 的 HTML 模板（`make_3d_demo3.TEMPLATE`）与 `background.py` 的去背景实现，
只把 job/空场/窗口/会话号参数化，不改 r01 任何文件。

用法：
    python -B -W error make_session_demo.py --out <会话证据目录> --sid <sid> \
        --job <target leveled job> --empty-job <空场 leveled job> --registration <registration 目录> \
        [--union-start N] [--union-end N] [--name 3D_TRACK.html]

输入：<out>/20_TRACK_V2.json（plane_fg2 产物）、<out>/31_CLASSIFY.json（plane_classifier 产物，可选）。
输出：<out>/<name> + three.min.js / OrbitControls.js（自 pc_apps/human_replay/vendor 复制）。
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

R01 = Path(__file__).resolve().parents[1] / "r01"
sys.path.insert(0, str(R01))

from make_3d_demo3 import TEMPLATE, obb, viridis      # noqa: E402  （复用同一份模板与体形框/配色实现）
from background import (apply_transform, background_keys, collect_points,   # noqa: E402
                        foreground_mask, load_points)
from common import ROOT                              # noqa: E402

CELL_M = 0.08
NEAR_M = 1.4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--sid", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--empty-job", required=True)
    parser.add_argument("--registration", required=True)
    parser.add_argument("--union-start", type=int, default=None)
    parser.add_argument("--union-end", type=int, default=None)
    parser.add_argument("--room-stride", type=int, default=12)
    parser.add_argument("--name", default="22_3D_TRACK.html")
    args = parser.parse_args()
    out = Path(args.out)
    source = json.loads((out / "20_TRACK_V2.json").read_text(encoding="utf8"))
    track = {row["frame"]: row for row in source["track"]}
    classified = {}
    if (out / "31_CLASSIFY.json").is_file():
        for row in json.loads((out / "31_CLASSIFY.json").read_text(encoding="utf8"))["tracks"]:
            classified[row["track_id"]] = row

    # 逐帧"自由空间高亮簇"（与 make_3d_demo3 同一判据：free_space 且非已知泄漏、≥8 点）
    picked = {}
    for row in source["frames"]:
        for candidate in row["candidates"]:
            if candidate.get("free_space") and not candidate.get("near_known_leak") \
                    and candidate["point_count"] >= 8:
                picked[row["frame"]] = candidate
                break

    registration = json.loads((Path(args.registration) / "registration.json").read_text(encoding="utf8"))
    assert registration["quality"]["status"] == "PASS", "registration 非 PASS，拒绝出页"
    target_frames, _tmeta = load_points(args.job, "tls")
    empty_frames, _emeta = load_points(args.empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    keys, origin, base = background_keys(collect_points(empty_registered, stride=2), CELL_M)

    detected = {row["frame"]: row for row in source["track"] if row["detected"]}
    frames_seen = sorted(row["frame"] for row in source["frames"])
    union_start = args.union_start if args.union_start is not None else min(detected or frames_seen)
    union_end = args.union_end if args.union_end is not None else max(detected or frames_seen)
    union_positions, union_colors = [], []
    for index, _stamp, xyz, _values in target_frames:
        if index < union_start or index > union_end or index not in detected:
            continue
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, CELL_M)
        center = np.asarray(detected[index]["center"])
        near = points[mask][np.linalg.norm(points[mask] - center, axis=1) <= NEAR_M]
        color = viridis((index - union_start) / max(1.0, float(union_end - union_start)))
        for point in near:
            union_positions.extend([round(float(v), 4) for v in point])
            union_colors.extend(color)

    middle = target_frames[len(target_frames) // 2][2]
    inside = np.isfinite(middle).all(axis=1) & (np.abs(middle) < 12).all(axis=1)
    room_flat = [round(float(v), 3) for v in middle[inside][::args.room_stride].reshape(-1)]

    speed_by_frame = {}
    ordered = sorted(detected)
    for i, frame in enumerate(ordered):
        candidates = []
        if i + 1 < len(ordered):
            delta = np.asarray(detected[ordered[i + 1]]["center"]) - np.asarray(detected[frame]["center"])
            dt = detected[ordered[i + 1]]["stamp_s"] - detected[frame]["stamp_s"]
            candidates.append(float(np.linalg.norm(delta) / dt) if dt > 0 else 0.0)
        if i > 0:
            delta = np.asarray(detected[frame]["center"]) - np.asarray(detected[ordered[i - 1]]["center"])
            dt = detected[frame]["stamp_s"] - detected[ordered[i - 1]]["stamp_s"]
            candidates.append(float(np.linalg.norm(delta) / dt) if dt > 0 else 0.0)
        speed_by_frame[frame] = min(candidates) if candidates else 0.0

    frames_payload = []
    for row in source["frames"]:
        frame = row["frame"]
        candidate = picked.get(frame)
        track_row = track.get(frame, {})
        entry = {"frame": frame, "t": row["stamp_s"], "points": [], "center": None, "box": None,
                 "bodybox": None, "desmear": None, "motion": None,
                 "stats": {"detected": bool(track_row.get("detected")), "point_count": None,
                           "core_point_count": None, "speed": None, "intensity": None,
                           "distance_to_empty": None}}
        if candidate is None:
            frames_payload.append(entry)
            continue
        points = np.asarray(candidate["points"], dtype=np.float64)
        box = obb(points)
        desmear = candidate.get("desmear")
        entry.update({
            "points": [round(float(v), 4) for v in points.reshape(-1)],
            "center": candidate["center"],
            "box": {"center": [round(float(v), 4) for v in box["center"]],
                    "axes": [[round(float(v), 6) for v in axis] for axis in box["axes"]],
                    "half": [round(float(v), 4) for v in box["half"]]},
            "desmear": (None if desmear is None else
                        {"along": desmear["along_track_span_m"], "step": desmear["step_m"],
                         "body_length": desmear["body_length_est_m"], "width": desmear["body_width_m"],
                         "thickness": desmear["body_thickness_m"]}),
            "motion": (None if desmear is None else
                       {"direction": desmear["motion_direction"],
                        "speed": float(speed_by_frame.get(frame, 0.0))}),
            "stats": {"detected": True, "point_count": candidate["point_count"],
                      "core_point_count": candidate["core_point_count"],
                      "speed": float(speed_by_frame.get(frame, 0.0)),
                      "intensity": candidate["intensity_median"],
                      "distance_to_empty": candidate["distance_to_empty_m"]},
        })
        if desmear is not None:
            direction = np.asarray(desmear["motion_direction"], dtype=np.float64)
            reference = np.array([0.0, 0.0, 1.0]) if abs(direction[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            perp1 = np.cross(direction, reference); perp1 /= np.linalg.norm(perp1)
            perp2 = np.cross(direction, perp1)
            length = max(desmear["body_length_est_m"], 0.02)
            entry["bodybox"] = {
                "center": [round(float(v), 4) for v in candidate["center"]],
                "axes": [[round(float(v), 6) for v in direction], [round(float(v), 6) for v in perp1],
                         [round(float(v), 6) for v in perp2]],
                "half": [round(length / 2, 4), round(desmear["body_width_m"] / 2, 4),
                         round(desmear["body_thickness_m"] / 2, 4)]}
        frames_payload.append(entry)

    # 视图中心：有目标就对着目标轨迹中点，没有就对着原点近处
    centers = [row["center"] for row in frames_payload if row["center"]]
    view = np.mean(np.asarray(centers), axis=0) if centers else np.array([2.0, 2.0, 1.0])
    # 识别表：分类器逐轨标签（31_CLASSIFY）与 KF 轨迹（30_TBD）按 id 合并，运动轨迹排前面
    tbd = json.loads((out / "30_TBD_TRACK.json").read_text(encoding="utf8"))
    kf = {row["id"]: row for row in tbd["kf_tracks"]["finished"]}
    classified_tracks = []
    for row in json.loads((out / "31_CLASSIFY.json").read_text(encoding="utf8"))["tracks"]:
        base = kf.get(row["track_id"], {})
        classified_tracks.append({
            "id": row["track_id"], "label": row["label"], "rule_score": row["rule_score"],
            "moving": base.get("moving"), "confirmed": base.get("confirmed"),
            "hits": base.get("hits"), "score": base.get("score"),
            "first_frame": base.get("first_frame"), "last_frame": base.get("last_frame"),
            "displacement_m": base.get("displacement_m"), "mean_speed_m_s": base.get("mean_speed_m_s")})
    classified_tracks.sort(key=lambda row: (not row["moving"], -(row["rule_score"] or 0.0)))
    html = (TEMPLATE
            .replace("__NMAX__", str(len(frames_payload) - 1))
            .replace("<title>PLANE-01 3D v3：完整移动形态 + 体形框</title>",
                     "<title>小目标跟踪 · %s（3D）</title>" % args.sid)
            .replace("<h3>PLANE-01 · 3D v3（完整移动形态 + 体形框 + 航线）</h3>",
                     "<h3>小目标跟踪 · %s（3D：逐帧目标点 + 体形框 + 航线）</h3>" % args.sid)
            .replace("controls.target.set(1.9, 1.2, 0.9)",
                     "controls.target.set(%.2f, %.2f, %.2f)" % tuple(view))
            .replace("camera.position.set(0.6, -2.4, 2.2)",
                     "camera.position.set(%.2f, %.2f, %.2f)"
                     % (view[0] - 1.3, view[1] - 3.0, view[2] + 1.3))
            .replace("语义 UNKNOWN。</div>",
                     "语义 UNKNOWN。<br>数据：%s（配平 job %s，去背景空场 %s 经 registration.js PASS 变换，"
                     "0.08 m 网格 ±1 格）；本页窗口 = 帧 %d–%d。</div>"
                     % (args.sid, args.job, args.empty_job, union_start, union_end))
            .replace('<div id="hud"></div>',
                     '<div id="hud"></div>\n  <div id="tracks" style="margin-top:8px;font-size:12px;'
                     'color:#b9c7d4;max-width:470px"></div>')
            .replace('`帧 ${frame.frame+1}/${frames.length}   t=${(frame.t - frames[0].t).toFixed(2)} s`',
                     '`帧 ${frame.frame}（窗口内 ${index+1}/${frames.length}）   t=${(frame.t - frames[0].t).toFixed(2)} s`')
            .replace("render(); tick();",
                     "render(); tick();\n"
                     "document.getElementById('tracks').innerHTML = "
                     "'<b>识别（规则分类 31_CLASSIFY × KF/TBD 轨迹，运动轨迹在前）</b>'\n"
                     "  + DATA.tracks.map(t => '<br>#' + t.id + (t.moving ? ' 运动' : ' 静止') + '  帧 '\n"
                     "      + t.first_frame + '–' + t.last_frame + '  位移 ' + Number(t.displacement_m).toFixed(2)\n"
                     "      + ' m  均速 ' + Number(t.mean_speed_m_s).toFixed(2) + ' m/s  KF分 ' + Number(t.score).toFixed(1)\n"
                     "      + ' → ' + t.label + '（规则分 ' + t.rule_score + '）').join('')\n"
                     "  + '<br>TBD 宣告帧: ' + (DATA.declared_frame === null ? '-' : DATA.declared_frame);")
            .replace("__DATA__", json.dumps(
                {"sid": args.sid, "frames": frames_payload, "room": room_flat,
                 "union": {"positions": union_positions, "colors": union_colors,
                           "note": "frames %d-%d, transient foreground within %.1f m of the tracked center"
                                   % (union_start, union_end, NEAR_M)},
                 "tracks": classified_tracks,
                 "declared_frame": json.loads((out / "30_TBD_TRACK.json").read_text(encoding="utf8"))
                 ["batch_tbd"]["declared_first_frame"]},
                ensure_ascii=False, separators=(",", ":"), allow_nan=False)))
    target = out / args.name
    with target.open("x", encoding="utf8") as stream:
        stream.write(html)
    for vendor in ("three.min.js", "OrbitControls.js"):
        destination = out / vendor
        if not destination.exists():
            shutil.copy2(ROOT / "pc_apps/human_replay/vendor" / vendor, destination)
    print(json.dumps({"html": str(target), "bytes": target.stat().st_size,
                      "union_points": len(union_positions) // 3, "frames": len(frames_payload),
                      "detected": len(centers)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
