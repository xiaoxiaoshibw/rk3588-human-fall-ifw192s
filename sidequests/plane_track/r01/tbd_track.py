"""P1：低门槛检测（≥1 点候选 / ≥2 点起轨）+ 批量 TBD（速度匹配累积）+ KF/M-N 在线跟踪。

用法：
    python -B -W error tbd_track.py --out <evidence_dir> [--registration <dir>]

设计（对应 24 号调研的方法族 2/3）：
  A) 检测层：自由空间前景点（离最近静态点 ≥0.2 m）→ 单链接 0.12 m 分簇，**≥1 点即列为候选**
     （对照：现有管线 ≥8 点成簇、生产 ≥25 点）；候选只用于统计与 TBD 种子。
  B) 批量 TBD：相邻帧候选中心两两配对生成 (p0, v) 假设，按 r=0.15 m 在全帧累积命中；
     报告最高分假设、命中帧、以及"窗口内 3/4 命中"可宣告发现的帧。
  C) 在线跟踪：6 维匀速 KF + 自适应门 + M/N 确认（8 帧内 4 次命中）+ coast 8 帧；
     起轨要求 ≥2 点（抑制 1 点噪声轨），确认后给出"运动/静止"分类（位移与平均速度）。
  D) 负对照：同一套参数跑今天无目标的帧 16–26（同一背景，唯一差别是没有纸飞机），
     报"运动型确认轨迹"数（应为 0）；另附空场自参考（前景≈0）作管线自检。
输出：30_TBD_TRACK.json + 30_TBD_TRACK.png
"""
import argparse
import json
from pathlib import Path

import numpy as np

from background import apply_transform, background_keys, collect_points, foreground_mask, load_points
from inspect_target import clusters_local
from plane_shape import robust_core

CELL_M = 0.08
LINK_M = 0.12
GRID_M = LINK_M / np.sqrt(3.0)
FREE_SPACE_MIN_M = 0.22
MIN_CLUSTER_POINTS = 1        # 候选门槛（对照 8/25）
MIN_INIT_POINTS = 3           # 起轨门槛（抑制小噪声簇）
MAX_TRACKS = 80
GATE_BASE_M = 0.5
TBD_RADIUS_M = 0.15
CONFIRM_HITS = 4
CONFIRM_WINDOW = 8
COAST_FRAMES = 8
STATIC_SPEED_M_S = 0.5
STATIC_DISPLACEMENT_M = 0.3


def frame_candidates(points, empty_points):
    """自由空间前景 → 单链接分簇（≥1 点）→ 稳健核中心/权重。"""
    candidates = []
    if not len(points):
        return candidates
    for members in clusters_local(points, GRID_M, MIN_CLUSTER_POINTS):
        group = points[members]
        center, core = robust_core(group)
        distance = float(np.linalg.norm(empty_points - center, axis=1).min()) if len(empty_points) else 99.0
        if distance < FREE_SPACE_MIN_M:
            continue
        candidates.append({"center": center, "points": int(len(group)), "core_points": int(len(core)),
                           "distance_to_empty_m": round(distance, 3),
                           "weight": float(min(len(group), 32))})
    return candidates


class Track:
    def __init__(self, track_id, center, stamp, weight, frame):
        self.id = track_id
        self.x = np.zeros(6)
        self.x[:3] = center
        self.P = np.eye(6) * np.array([0.05, 0.05, 0.05, 1.0, 1.0, 1.0]) ** 2
        self.last_stamp = stamp
        self.hits = [(frame, weight)]
        self.score = weight
        self.confirmed = False
        self.misses = 0
        self.alive = True
        self.first = (frame, np.asarray(center, dtype=float))

    def predict(self, stamp):
        dt = max(stamp - self.last_stamp, 1e-3)
        F = np.eye(6); F[:3, 3:] = np.eye(3) * dt
        q = 0.5 * dt ** 2
        Q = np.diag([0.5 * q, 0.5 * q, 0.5 * q, 0.05 * dt, 0.05 * dt, 0.05 * dt]) ** 2
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        return self.x[:3]

    def update(self, center, stamp, weight, frame):
        H = np.zeros((3, 6)); H[:, :3] = np.eye(3)
        R = np.eye(3) * 0.05 ** 2
        y = center - H @ self.x
        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ H) @ self.P
        self.last_stamp = stamp
        self.misses = 0
        self.score += weight
        self.hits.append((frame, weight))
        recent = [f for f, _ in self.hits if frame - f < CONFIRM_WINDOW]
        if len(recent) >= CONFIRM_HITS:
            self.confirmed = True
        self.last = (frame, np.asarray(center, dtype=float))

    def missed(self):
        self.misses += 1
        if self.misses > COAST_FRAMES:
            self.alive = False

    def summary(self):
        last_frame, last_position = getattr(self, "last", self.first)
        displacement = float(np.linalg.norm(last_position - self.first[1]))
        duration = max(last_frame - self.first[0], 1) * 0.103
        mean_speed = displacement / duration if duration > 0 else 0.0
        moving = bool(displacement > STATIC_DISPLACEMENT_M and mean_speed > STATIC_SPEED_M_S)
        return {"id": self.id, "confirmed": self.confirmed, "hits": len(self.hits),
                "score": round(float(self.score), 1),
                "first_frame": self.first[0], "last_frame": last_frame,
                "displacement_m": round(displacement, 3), "mean_speed_m_s": round(mean_speed, 3),
                "moving": moving, "alive": self.alive}


def run_kf(frames):
    tracks, finished, next_id = [], [], 1
    rows = []
    for index, stamp, candidates in frames:
        for track in tracks:
            track.predict(stamp)
        used = set()
        for track in tracks:
            prediction = track.x[:3]
            gate = max(GATE_BASE_M, 1.5 * float(np.linalg.norm(track.x[3:])) * 0.103 + 0.2)
            best = None
            for order, candidate in enumerate(candidates):
                if order in used:
                    continue
                distance = float(np.linalg.norm(candidate["center"] - prediction))
                if distance <= gate and (best is None or distance < best[0]):
                    best = (distance, order, candidate)
            if best is not None:
                _, order, candidate = best
                used.add(order)
                track.update(candidate["center"], stamp, candidate["weight"], index)
            else:
                track.missed()
        for order, candidate in enumerate(candidates):
            if order in used or candidate["points"] < MIN_INIT_POINTS:
                continue
            tracks.append(Track(next_id, candidate["center"], stamp, candidate["weight"], index))
            next_id += 1
        if len(tracks) > MAX_TRACKS:
            tracks.sort(key=lambda t: -t.score)
            for dropped in tracks[MAX_TRACKS:]:
                dropped.alive = False
            tracks = tracks[:MAX_TRACKS]
        alive = []
        for track in tracks:
            (alive if track.alive else finished).append(track)
        tracks = alive
        rows.append({"frame": index, "stamp_s": stamp, "candidates": len(candidates),
                     "candidate_points": sorted((c["points"] for c in candidates), reverse=True)[:6],
                     "tracks": [{"id": t.id, "confirmed": t.confirmed, "score": round(t.score, 1),
                                 "position": [round(float(v), 3) for v in t.x[:3]],
                                 "speed_m_s": round(float(np.linalg.norm(t.x[3:])), 3),
                                 "misses": t.misses, "hits": len(t.hits)} for t in tracks]})
    finished.extend(tracks)
    return rows, [t.summary() for t in finished]


def batch_tbd(frames, radius=TBD_RADIUS_M, min_speed_m_s=0.5, moving_speed_m_s=1.0, window=4):
    """速度匹配累积（TBD）。

    假设生成：相邻帧候选中心两两配对 → (p0, t0, v)，|v| ∈ [0.5, 8] m/s（滤掉静止）。
    评分：在全部帧上按 r 累积命中（线性模型）；排序用"滑窗 %d 帧内最多命中数"优先，
    避免准静态泄漏簇用全帧命中数把运动假设压下去。返回 (运动假设前 10, 静态假设数)。
    """ % (window + 1)
    stamps = {index: stamp for index, stamp, _c in frames}
    order = sorted(stamps)
    points_by_frame = {index: [c["center"] for c in candidates] for index, _s, candidates in frames}
    entries = {}
    skipped_static = 0
    for left, right in zip(order, order[1:]):
        dt = stamps[right] - stamps[left]
        if dt <= 0:
            continue
        for p in points_by_frame[left]:
            for q in points_by_frame[right]:
                velocity = (q - p) / dt
                speed = float(np.linalg.norm(velocity))
                if speed > 8.0:
                    continue
                if speed < min_speed_m_s:
                    skipped_static += 1
                    continue
                key = tuple(np.round(np.concatenate([p, velocity]), 2).tolist())
                entries.setdefault(key, {"p0": p, "t0": stamps[left], "v": velocity,
                                         "hits": [], "score": 0.0})
    for entry in entries.values():
        for index in order:
            dt = stamps[index] - entry["t0"]
            predicted = entry["p0"] + entry["v"] * dt
            best = None
            for candidate in points_by_frame[index]:
                distance = float(np.linalg.norm(candidate - predicted))
                if distance <= radius and (best is None or distance < best):
                    best = distance
            if best is not None:
                entry["hits"].append(index)
                entry["score"] += max(0.0, 1.0 - best / radius)
    for entry in entries.values():
        entry["best_window"] = 0
        entry["window_start"] = None
        hits = entry["hits"]
        for start in hits:
            in_window = [h for h in hits if start <= h < start + window + 1]
            if len(in_window) > entry["best_window"]:
                entry["best_window"] = len(in_window)
                entry["window_start"] = start
    moving = [e for e in entries.values() if float(np.linalg.norm(e["v"])) >= moving_speed_m_s]
    static_count = skipped_static + len(entries) - len(moving)
    moving.sort(key=lambda e: (-e["best_window"], -len(e["hits"]), -e["score"]))
    ranked = [{"p0": [round(float(v), 3) for v in e["p0"]], "v_m_s": [round(float(v), 3) for v in e["v"]],
               "hits": e["hits"], "n_hits": len(e["hits"]), "score": round(float(e["score"]), 2),
               "best_window": e["best_window"], "window_start": e["window_start"]}
              for e in moving[:10]]
    return ranked, static_count


def tbd_declared_frame(ranked, window=4):
    """用"滑窗内命中 ≥ 窗口×0.75"定义可宣告发现的帧（对运动假设）。"""
    for entry in ranked:
        if entry["best_window"] >= max(2, int(window * 0.75)) and entry["window_start"] is not None:
            return entry["window_start"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--registration", default="03_REGISTRATION_131958_to_164522")
    parser.add_argument("--job", default="363473a9e2e64649994dca11b2b26929")
    parser.add_argument("--empty-job", default="61cb6976b0f8479394641850d9a7c6ca")
    args = parser.parse_args()
    out = Path(args.out)
    registration = json.loads((out / args.registration / "registration.json").read_text(encoding="utf8"))
    target_frames, _tmeta = load_points(args.job, "tls")
    empty_frames, _emeta = load_points(args.empty_job, "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    empty_points = collect_points(empty_registered, stride=2)
    keys, origin, base = background_keys(empty_points, CELL_M)

    frames = []
    for index, stamp, xyz, _values in target_frames:
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, CELL_M)
        frames.append((index, stamp, frame_candidates(points[mask], empty_points)))

    rows, finished = run_kf(frames)
    moving_confirmed = [t for t in finished if t["confirmed"] and t["moving"]]
    ranked, static_hypotheses = batch_tbd(frames)
    declared = tbd_declared_frame(ranked)

    negative_rows, negative_finished = run_kf([(i, s, c) for i, s, c in frames if i >= 16])
    negative_moving = [t for t in negative_finished if t["confirmed"] and t["moving"]]

    # 空场自参考（管线自检，不是难度对照）
    empty_self = []
    for index, stamp, xyz, _values in empty_frames[:8]:
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite][::2]
        mask = foreground_mask(points, keys, origin, base, CELL_M)
        empty_self.append({"frame": index, "points": int(mask.sum()),
                           "clusters": len(frame_candidates(points[mask], empty_points))})

    payload = {
        "baseline_8point_pipeline": {"first_frame": 9, "frames_with_candidate": [9, 10, 11, 12, 13, 14, 15]},
        "low_threshold": {"min_candidate_points": MIN_CLUSTER_POINTS, "min_init_points": MIN_INIT_POINTS,
                          "candidates_per_frame": {row["frame"]: row["candidates"] for row in rows}},
        "kf_tracks": {"finished": finished,
                      "moving_confirmed": moving_confirmed,
                      "confirmed_count": sum(1 for t in finished if t["confirmed"])},
        "batch_tbd": {"radius_m": TBD_RADIUS_M, "min_seed_speed_m_s": 0.5, "moving_speed_m_s": 1.0,
                      "static_hypotheses": static_hypotheses, "top": ranked,
                      "declared_first_frame": declared,
                      "note": "窗口 4 帧内 ≥3 次命中即宣告发现；用低门槛（≥1 点）候选中心做假设"},
        "negative_controls": {
            "frames_16_26": {"moving_confirmed_tracks": negative_moving,
                             "confirmed_static_tracks": sum(1 for t in negative_finished
                                                            if t["confirmed"] and not t["moving"])},
            "empty_self_reference": empty_self},
    }
    with (out / "30_TBD_TRACK.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    render(out, rows, ranked, declared, moving_confirmed, negative_moving)
    print(json.dumps({
        "candidates_per_frame": {row["frame"]: row["candidates"] for row in rows},
        "tbd_declared_frame": declared,
        "tbd_top3": ranked[:3],
        "moving_confirmed_tracks": moving_confirmed,
        "negative_moving_confirmed": negative_moving,
    }, ensure_ascii=False))


def render(out, rows, ranked, declared, moving_confirmed, negative_moving):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    matplotlib.rcParams["axes.unicode_minus"] = False
    import matplotlib.pyplot as plt

    figure, panels = plt.subplots(1, 3, figsize=(19, 5.6))
    panels[0].bar([r["frame"] for r in rows], [r["candidates"] for r in rows], color="#4c9be8", label="≥1 点候选")
    for row in rows:
        for track in row["tracks"]:
            if track["confirmed"]:
                panels[0].plot(row["frame"], track["hits"], "r.", ms=4)
    panels[0].set_xlabel("帧"); panels[0].set_ylabel("候选数"); panels[0].grid(alpha=0.3, axis="y")
    panels[0].set_title("A 低门槛候选（红点=确认轨迹命中）")
    for order, entry in enumerate(ranked[:3]):
        panels[1].plot(entry["hits"], [order] * entry["n_hits"], "o-",
                       label="TBD#%d 命中 %d 帧 |v|=%.1f m/s" % (
                           order + 1, entry["n_hits"], float(np.linalg.norm(entry["v_m_s"]))))
    panels[1].set_yticks(range(3)); panels[1].set_xlabel("帧"); panels[1].grid(alpha=0.3)
    panels[1].legend(fontsize=9)
    panels[1].set_title("B 批量 TBD 命中帧" + ("（可宣告发现=帧 %d；基线 8 点管线=帧 9）" % declared
                                                if declared is not None else ""))
    if moving_confirmed:
        best = max(moving_confirmed, key=lambda t: t["score"])
        series = [(row["frame"], t) for row in rows for t in row["tracks"] if t["id"] == best["id"]]
        panels[2].plot([f for f, _ in series], [t["speed_m_s"] for _, t in series], "o-", label="KF 速度")
        panels[2].plot([f for f, _ in series], [t["misses"] for _, t in series], "s--", label="连续未命中")
        panels[2].legend(fontsize=9)
        panels[2].set_title("C 运动型确认轨迹 ID %d（score %.1f，命中 %d 帧）" % (
            best["id"], best["score"], best["hits"]))
    panels[2].set_xlabel("帧"); panels[2].grid(alpha=0.3)
    figure.suptitle("P1：≥%d 点候选 + TBD + KF/M-N（负对照 帧16–26 运动型确认轨迹 %d 条）" % (
        MIN_CLUSTER_POINTS, len(negative_moving)), fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, 0.93])
    figure.savefig(out / "30_TBD_TRACK.png", dpi=110)
    plt.close(figure)


if __name__ == "__main__":
    main()
