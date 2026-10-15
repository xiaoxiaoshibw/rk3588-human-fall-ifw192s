"""P3 骨架：把"形状 + 运动 + 传感器"特征汇成轨道级特征表，并按规则打分（训练留接口）。

用法：
    python -B -W error plane_classifier.py --out <evidence_dir>

说明（诚实口径）：
- 目前只有 **1 个正样本**（本段纸飞机，用户口头标注）与少量负样本（同段 3 个持续泄漏簇、
  同伴点、今天无目标段的确认轨），**不足以训练**；因此本脚本只做：
    (a) 轨道级特征表（可复算、可扩展到新数据）；
    (b) 规则打分（阈值全部有出处：25 号形状表 / 24 号文献特征族 / 30 号跟踪表）；
    (c) 训练接口（build_training_rows + logistic_fit），等新数据带标签后可直接调用。
- 负样本口径：`static_leak`（持续、慢）、`未确认`（命中不足）、`无标签`（其余）。
  不把"未确认"当负例训练，避免标签污染。
输出：31_CLASSIFY.json（特征表 + 规则分 + 说明）
"""
import argparse
import json
from pathlib import Path

import numpy as np

RULES = {
    # 名称: (区间/方向, 出处)
    "length_m": (0.15, 0.35, "25 号：纸飞机量级 0.2–0.3 m"),
    "thickness_m": (0.05, 0.15, "25 号：扁平"),
    "speed_m_s": (1.0, 8.0, "本段实测 1.34–3.07；文献：无人机/鸟典型 5–25"),
    "accel_over_g": (0.0, 0.6, "滑翔/带升力：本段 2.75/9.8=0.28；自由落体≈1.0"),
    "glide_ratio": (0.5, 8.0, "滑翔比；本段 1.29"),
}


def rule_score(features):
    """规则打分：命中区间得 1 分，权重=1；返回 (得分, 逐项判定)。"""
    hits, detail = 0.0, {}
    for name, (low, high, source) in RULES.items():
        value = features.get(name)
        ok = value is not None and low <= value <= high
        detail[name] = {"value": value, "range": [low, high], "pass": bool(ok), "source": source}
        hits += 1.0 if ok else 0.0
    return hits / len(RULES), detail


def track_features(track, shape=None, sensors=None):
    """把跟踪/形状/传感器块汇成一个特征字典（缺项写 None，不猜）。"""
    features = {
        "hits": track.get("hits"),
        "displacement_m": track.get("displacement_m"),
        "mean_speed_m_s": track.get("mean_speed_m_s"),
        "speed_m_s": track.get("mean_speed_m_s"),
        "moving": track.get("moving"),
        "confirmed": track.get("confirmed"),
    }
    if shape:
        features.update({
            "length_m": shape["flight_frame_extents_robust_m"][0] if "flight_frame_extents_robust_m" in shape
            else shape["extent_robust_m"][0],
            "width_m": (shape["flight_frame_extents_robust_m"][1] if "flight_frame_extents_robust_m" in shape
                        else shape["extent_robust_m"][1]),
            "thickness_m": (shape["flight_frame_extents_robust_m"][2] if "flight_frame_extents_robust_m" in shape
                            else shape["extent_robust_m"][2]),
            "planform_hull_area_m2": shape.get("planform_hull_area_m2",
                                               shape.get("projected_hull_area_m2")),
        })
    if sensors:
        features.update(sensors)
    return features


def logistic_fit(rows, labels, steps=400, lr=0.5, l2=0.01):
    """极简 logistic 回归（numpy）；rows 已标准化。仅有带标签数据时调用。"""
    x = np.asarray(rows, dtype=float)
    y = np.asarray(labels, dtype=float)
    w = np.zeros(x.shape[1])
    b = 0.0
    for _ in range(steps):
        z = x @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        grad_w = x.T @ (p - y) / len(y) + l2 * w
        grad_b = float(np.mean(p - y))
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--name", default="31_CLASSIFY.json")
    args = parser.parse_args()
    out = Path(args.out)
    tbd = json.loads((out / "30_TBD_TRACK.json").read_text(encoding="utf8"))
    shape = json.loads((out / "26_SHAPE_ALIGNED.json").read_text(encoding="utf8"))
    shape_core = json.loads((out / "25_SHAPE_FEATURES.json").read_text(encoding="utf8"))
    kinematics = shape_core["kinematics"]

    track_rows = tbd["kf_tracks"]["finished"]
    labeled_rows = []
    for track in track_rows:
        features = track_features(track)
        # 运动学只对纸飞机轨道（ID 4）可用；其余轨道没有独立形状/运动学证据
        if track["id"] == 4:
            features.update({
                "accel_over_g": abs(kinematics["acceleration_m_s2"]) / 9.80665,
                "glide_ratio": kinematics["glide_ratio"],
                "speed_m_s": float(np.mean(kinematics["speed_m_s"])),
                "terminal_speed_m_s": abs(shape_core["frames"][-1]["velocity_m_s"][2]),
                "length_m": shape["flight_frame_extents_robust_m"][0],
                "width_m": shape["flight_frame_extents_robust_m"][1],
                "thickness_m": shape["flight_frame_extents_robust_m"][2],
                "planform_hull_area_m2": shape["planform_hull_area_m2"],
            })
            label = "paper_plane(user_labeled)"
        elif track["moving"] and track["confirmed"]:
            label = "unlabeled_moving_confirmed"
        elif track["moving"]:
            label = "unlabeled_moving"
        else:
            label = "static_leak"
        score, detail = rule_score({k: features.get(k) for k in RULES})
        labeled_rows.append({"track_id": track["id"], "label": label, "rule_score": round(score, 3),
                             "features": features, "rules": detail})

    payload = {
        "note": ("规则打分（阈值均有出处）；训练接口 logistic_fit 已就位，"
                 "但当前 1 正样本 + 少量负样本不足以训练，未训练、未宣称准确率"),
        "rules": {k: {"range": [v[0], v[1]], "source": v[2]} for k, v in RULES.items()},
        "tracks": labeled_rows,
        "kinematics_source": kinematics,
        "trainable": False,
        "trainable_reason": "positive=1 (paper_plane), negatives=永久泄漏簇/未确认轨；需新采集与人工标签",
        "training_rows_endpoint": {
            "build": "track_features(track, shape, sensors) → dict",
            "fit": "logistic_fit(standardized_rows, labels) → (w, b)",
        },
    }
    with (out / args.name).open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps([{"id": row["track_id"], "label": row["label"], "score": row["rule_score"]}
                      for row in labeled_rows], ensure_ascii=False))


if __name__ == "__main__":
    main()
