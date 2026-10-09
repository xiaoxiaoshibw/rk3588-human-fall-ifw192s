# -*- coding: utf-8 -*-
"""dump_rf_json.py — 把 sklearn RandomForestClassifier 导出成浏览器可用的轻量 JSON.

只包含 RandomForest 推理所需的最小集:
  - n_features: 51 (frame_feature.py 验证)
  - classes_: [0, 1]
  - trees: [ {feature, threshold, children_left, children_right, value}, ... ]
    value = tree value array (n_nodes, 1, 2), 概率树叶子才是非零

简化约束 (避免 JS 端复杂逻辑):
  - features 全部用 float32 存储
  - threshold 全部用 float32
  - children 用 int32
  - value 用 float32

输出: rf_person_v1.json (写入 PC 目录, 供 replay 服务器静态提供).
"""
import json
import os

import joblib
import numpy as np

MODEL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "ML", "models", "rf_person_v1.joblib")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "pc_apps", "human_replay", "rf_person_v1.json")


def tree_to_dict(tree):
    """sklearn.tree.Tree → JSON dict; 只保留推理必需数组."""
    state = tree.tree_
    # sklearn tree children: -1 表示叶
    cl = state.children_left.astype(np.int32).tolist()
    cr = state.children_right.astype(np.int32).tolist()
    feat = state.feature.astype(np.int32).tolist()
    thr = state.threshold.astype(np.float32).tolist()
    # value shape (n_nodes, n_outputs, n_classes) → 取第 0 个 output 的 [P(0), P(1)]
    val = state.value.astype(np.float32).reshape(state.value.shape[0], -1).tolist()
    return {"feature": feat, "threshold": thr, "children_left": cl, "children_right": cr,
            "value": val}


def main():
    clf = joblib.load(MODEL)
    if clf.n_features_in_ != 51:
        raise SystemExit("expect 51 features, got %d" % clf.n_features_in_)
    trees = [tree_to_dict(est) for est in clf.estimators_]
    json_obj = {
        "n_features": 51,
        "n_trees": len(trees),
        "classes": clf.classes_.tolist(),   # [0, 1]
        "trees": trees,
        "model_source": "rf_person_v1.joblib",
        "model_sha256_placeholder": "",
    }
    # 单元级圆角: 为防 json float->str 精度损失, 用 5 位小数舍入
    text = json.dumps(json_obj, separators=(",", ":"), allow_nan=False)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("wrote", OUT, "size:", os.path.getsize(OUT), "trees:", len(trees))

    # 就地验证: person + noperson 混合抽样, 对比 sklearn vs JSON 推理
    from frame_feature import extract_features
    from session_load import iter_session_frames, iter_none_frames, REMOTE
    import os.path as osp
    import random
    random.seed(0)
    samples = []
    for sid in ["cap_20261009_114817", "cap_20261009_121723"]:
        sd = osp.join(REMOTE, sid)
        for xyz_i, lab, name in iter_session_frames(sd, max_frames=3):
            fv = extract_features(xyz_i)
            sklearn_p = clf.predict_proba(fv.reshape(1, -1))[0, 1]
            samples.append((fv, sklearn_p, sid))
    # noperson / 空场
    sd = osp.join(REMOTE, "cap_20261009_113611")
    for xyz_i, lab, name in iter_none_frames(sd, max_frames=6):
        fv = extract_features(xyz_i)
        sklearn_p = clf.predict_proba(fv.reshape(1, -1))[0, 1]
        samples.append((fv, sklearn_p, "empty_113611"))

    # 在 Python 里用 JSON 树做 inference 对照
    def predict_json(fv):
        prob_sum = 0.0
        for t in trees:
            node = 0
            while True:
                f_i = t["feature"][node]
                if f_i == -2:  # leaf
                    break
                v = fv[f_i]
                if v <= t["threshold"][node]:
                    node = t["children_left"][node]
                else:
                    node = t["children_right"][node]
            nv = t["value"][node]
            total = sum(nv)
            prob_sum += (nv[1] / total if total > 0 else 0.0)
        return prob_sum / len(trees)

    print("predict_proba 对照 (Python sklearn vs JSON 推算):")
    ok = 0
    for fv, sklearn_p, sid in samples:
        json_p = predict_json(fv)
        diff = abs(json_p - sklearn_p)
        print("  %s sklearn=%.4f json=%.4f diff=%.6f" % (sid, sklearn_p, json_p, diff))
        if diff < 1e-3:
            ok += 1
    print("一致 %d/%d" % (ok, len(samples)))
    if ok < len(samples):
        raise SystemExit("JSON model 与 sklearn 不等价, 中止发布")


if __name__ == "__main__":
    # iter_session_frames 没有 max_frames 参数, 自己截断:
    import session_load
    orig = session_load.iter_session_frames

    def iter_session_frames_capped(session_dir, max_frames=None):
        n = 0
        for r in orig(session_dir):
            if max_frames is not None and n >= max_frames:
                return
            n += 1
            yield r

    session_load.iter_session_frames = iter_session_frames_capped
    from session_load import iter_session_frames  # rebind
    main()
