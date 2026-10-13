"""HUMAN-R3-CONTINUOUS STEP 3-4: frozen GT -> offline candidate v3; never replace v1/v2.

R3 关键差异（相对 R2 v2):
1. 用 R3 新核验的 9 会话 GT (S1 V1 d4b5cacb5656 / S9 V2 285c11026b57)
2. 移除 S9 (双人 f=1 propagated P2,样本稀疏不应作主要 train 源）
3. **分层过/欠采样处理 point_count 重叠**——让模型学形态学特征而不是 n
4. 主负源 S1 家具 (PC 中位 1915) vs 近场正例 (PC 中位 1105) 在 [700, 2500] 区间均衡化,
   强制模型学形态学

仍然:
- 51 维契约冻结 (frame_feature.FEAT_DIM/FEAT_NAMES 不动)
- THRESHOLD = 0.55 (不修改,不通过调阈值造假)
- 按会话隔离 split (不随机打散)
- 模型保存为 rf_person_v3.json, 独立 artifact, v1/v2 不动

跑法:
    python -X utf8 pc_apps/human_ml/train_person_rf_v3.py --out <全新空目录>
"""
import argparse
import json
import pathlib
import sys

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.utils import resample

from dump_rf_json import tree_to_dict
from frame_feature import FEAT_DIM, FEAT_NAMES
from frozen_gt import REPO, SIDS, audit_session, export_samples, read_json, sha, write_json

# 会话级 split (同 R2 v2): train 4 会话 + val 1 + test 2 + stress 1 + blocked S9
SPLITS = {"train": ["cap_20261010_175227", "cap_20261010_175429",
                    "cap_20261010_175804", "cap_20261010_175943"],
          "val": ["cap_20261010_175553"],
          "test": ["cap_20261010_180337", "cap_20261010_180557"],
          "stress": ["cap_20261010_180235"],
          "blocked": ["cap_20261010_180751"]}  # S9 双人独立评估,不入训练

THRESHOLD = 0.55


def stratified_oversample(X, y, point_counts, target_pos_neg_gap_ratio=1.0, seed=42):
    """在 point_count 维度上让正负分布尽量对齐。
    简单策略: 按 point_count 把样本分桶 (log 桶),每桶内若 |pos-neg| > 比率,小类 oversample.
    """
    rng = np.random.RandomState(seed)
    pc = np.asarray(point_counts)
    # log2 桶
    buckets = np.clip((np.log2(np.maximum(pc, 1)).astype(int) - 5), 0, 12)
    X_out, y_out, pc_out = [X], [y], [pc]
    audit = []
    for b in np.unique(buckets):
        pos_idx = np.where((buckets == b) & (y == 1))[0]
        neg_idx = np.where((buckets == b) & (y == 0))[0]
        if len(pos_idx) == 0 and len(neg_idx) == 0:
            continue
        target_max = max(len(pos_idx), len(neg_idx))
        # 只 oversample 小类,不下采样
        for cls_idx, cls_y in [(pos_idx, 1), (neg_idx, 0)]:
            if len(cls_idx) == 0: continue
            if len(cls_idx) < target_max * 0.5:
                # 需要 oversample 到 target_max * 0.5
                need = int(target_max * 0.5) - len(cls_idx)
                if need > 0:
                    pick = rng.choice(cls_idx, size=need, replace=True)
                    X_out.append(X[pick]); y_out.append(y[pick]); pc_out.append(pc[pick])
                    audit.append({"bucket": int(b), "cls": int(cls_y), "added": int(need),
                                  "before": int(len(cls_idx)), "target": int(target_max)})
    return (np.vstack(X_out), np.concatenate(y_out), np.concatenate(pc_out),
            {"buckets": int(len(np.unique(buckets))), "oversample_actions": audit})


def predict_json(model, X):
    prob = np.zeros(len(X))
    for tree in model["trees"]:
        for i, fv in enumerate(X):
            node = 0
            while tree["feature"][node] >= 0:
                feature = tree["feature"][node]
                node = tree["children_left" if fv[feature] <= tree["threshold"][node] else "children_right"][node]
            v = tree["value"][node]
            prob[i] += v[1] / sum(v) if sum(v) else 0
    return prob / len(model["trees"])


def metrics(y, p):
    hit = p >= THRESHOLD
    tp, fp = int(((y == 1) & hit).sum()), int(((y == 0) & hit).sum())
    fn, tn = int(((y == 1) & ~hit).sum()), int(((y == 0) & ~hit).sum())
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall": tp / (tp + fn) if tp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-stratify", action="store_true", help="关 R3 分层 (等于 R2 风格)")
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("--out 必须空")
    out.mkdir(parents=True, exist_ok=True)

    # R3 关键改动: 从当前 GT_STORE 读 (而不是 R2 跑的版本)
    store = REPO / "pc_apps" / "human_replay" / "gt_store"
    capture = REPO / "captures" / "remote"

    sessions = []
    docs = {}
    metas = {}
    for sid in SIDS:
        record, doc, meta = audit_session(sid, store, capture)
        sessions.append(record)
        docs[sid] = doc
        metas[sid] = meta
        print(f"[audit] {sid} v={record.get('version')} sha16={record.get('gt_sha256','')[:16]} eligible={record.get('eligible')}")
        if not record.get("eligible"):
            print(f"  issues: {record.get('issues')}")

    # 导出样本
    all_samples = []
    for record in sessions:
        sid = record["sid"]
        if sid in SPLITS["blocked"]:
            print(f"[skip] {sid} blocked")
            continue
        doc = docs[sid]
        meta = metas[sid]
        samples, info = export_samples(record, doc, meta, capture)
        print(f"[export] {sid}: {info['samples']} 样本, dup_removed={info['duplicates_removed']}")
        all_samples.extend(samples)

    # 统计
    from collections import Counter
    print("\n=== 总样本分布 ===")
    print(f"total: {len(all_samples)}")
    print(f"class: {dict(Counter(s['class_name'] for s in all_samples))}")
    print(f"label: {dict(Counter(s['label'] for s in all_samples))}")
    # 按会话
    by_sid = Counter(s["session_id"] for s in all_samples)
    print("by_sid:")
    for sid, c in by_sid.most_common():
        print(f"  {sid}: {c}")

    # 划分
    split_data = {}
    for split_name, sid_list in SPLITS.items():
        if split_name == "blocked": continue
        subset = [s for s in all_samples if s["session_id"] in sid_list]
        split_data[split_name] = subset
        pos = sum(1 for s in subset if s["label"] == 1)
        neg = sum(1 for s in subset if s["label"] == 0)
        print(f"[split] {split_name}: {len(subset)} (pos={pos} neg={neg})")

    # =========== 训练 ===========
    train = split_data["train"]
    X_train = np.array([s["fv"] for s in train], dtype=np.float32)
    y_train = np.array([s["label"] for s in train], dtype=np.int64)
    pc_train = np.array([s["point_count"] for s in train], dtype=np.int64)
    print(f"\ntrain raw: X={X_train.shape} y_pos={int((y_train==1).sum())} y_neg={int((y_train==0).sum())}")
    print(f"train point_count: pos p50={int(np.median(pc_train[y_train==1]))} neg p50={int(np.median(pc_train[y_train==0]))}")

    oversample_audit = {"enabled": not args.no_stratify}
    if not args.no_stratify:
        X_train, y_train, pc_train, audit_info = stratified_oversample(X_train, y_train, pc_train)
        oversample_audit.update(audit_info)
        print(f"train stratified: X={X_train.shape} pos={int((y_train==1).sum())} neg={int((y_train==0).sum())}")
        print(f"oversample actions: {len(audit_info['oversample_actions'])}")

    clf = RandomForestClassifier(n_estimators=200, max_depth=15, min_samples_leaf=2,
                                  n_jobs=-1, random_state=42, class_weight="balanced")
    clf.fit(X_train, y_train)

    # 转 JSON
    model_json = {"version": "rf_person_v3",
                  "n_features": FEAT_DIM,      /* 契约 key, rf_person.js:22 要它=51 */
                  "feature_dim": FEAT_DIM, "feature_names": FEAT_NAMES,
                  "threshold": THRESHOLD,
                  "n_estimators": 200, "max_depth": 15,
                  "class_weight": "balanced",
                  "preprocessing": "stratified_bucket_oversample" if not args.no_stratify else "none",
                  "oversample_audit": oversample_audit,
                  "trees": [tree_to_dict(t) for t in clf.estimators_]}
    model_path = out / "rf_person_v3.json"
    write_json(model_path, model_json)
    model_sha = sha(model_path)
    print(f"\n[model] rf_person_v3.json sha16={model_sha[:16]}")

    # =========== 评估 ===========
    metrics_per_split = {}
    for split_name, subset in split_data.items():
        if not subset: continue
        X = np.array([s["fv"] for s in subset], dtype=np.float32)
        y = np.array([s["label"] for s in subset], dtype=np.int64)
        p = predict_json(model_json, X)
        m = metrics(y, p)
        metrics_per_split[split_name] = m
        print(f"[eval] {split_name}: recall={m['recall']:.3f} precision={m['precision']:.3f} tp={m['tp']} fp={m['fp']} fn={m['fn']}")

    # 保存
    write_json(out / "TRAIN_REPORT.json", {
        "split_counts": {k: {"samples": len(v), "pos": sum(1 for s in v if s["label"]==1),
                              "neg": sum(1 for s in v if s["label"]==0)}
                          for k, v in split_data.items()},
        "metrics": metrics_per_split,
        "model_sha16": model_sha[:16],
        "oversample_audit": oversample_audit,
        "splits_def": SPLITS,
        "threshold": THRESHOLD,
    })
    print(f"\n[out] {out}")


if __name__ == "__main__":
    main()
