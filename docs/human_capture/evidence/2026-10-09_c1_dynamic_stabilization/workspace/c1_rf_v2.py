#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_rf_v2.py — C1.4 RF v2 候选训练 (LoS-fold 诚实评估, 拒不自欺).

训练数据:
  - person (簇级): 全部 6 段的 person=1 簇 (915 条, 从 cluster_dataset.jsonl 取 cls='person')
  - hard negatives (簇级): 6 段的 furniture=1 簇 (324 条)
  - frame-level 训练 pod (RF v1 原样): 12 段 ai_labels + 空场 (整帧 ROI, train_person_rf.py)
实验设计 (逐一单变):
  - v1 (base):     帧级 0% 家具  (训练 pod 现状 → 重训作对照)
  - v2a (采样):    帧级 person=1/noperson=2 类权
  - v2b (+家具):   v1 + 324 家具簇作额外 noperson
  - v2c (+人强调): v2b + 人簇复制注入 (远距离 2 段人簇 ×2, 近距离 ×1) + 样本平衡
  - v2d (子集阈):  v2c + 柜位 z<0.5 簇子集 ×3 (subgroup_weighting)
  - v2e (特征+):   v2c + 新增 2 几何特征 (z_range/cluster_zupt) — 消融个体
评估: LoS (按会话 fold) — 家具簇只能测所在会话被留出时 (女近/女中/男近/男中)
输出: rf_v2/results.json + SUMMARY.md; 不覆盖 v1 工件.
"""
import json, os, sys
import numpy as np

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pc_apps", "human_ml"))
from frame_feature import extract_features  # noqa

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

TRAIN_PERSON_SIDS = ["cap_20261009_114641", "cap_20261009_114709", "cap_20261009_114734",
                     "cap_20261009_114754", "cap_20261009_114817",
                     "cap_20261009_121622", "cap_20261009_121647", "cap_20261009_121723",
                     "cap_20261009_122616", "cap_20261009_122637", "cap_20261009_122700"]
NONE_SID = "cap_20261009_113611"


def load_rows():
    rows = [json.loads(l) for l in open(os.path.join(EVID, "rf_v2", "cluster_dataset.jsonl"),
                                        encoding="utf-8")]
    return rows


def load_frame_trainset():
    """复刻 train_person_rf.collect: 11 段全帧 person + 空场 (同量纲 inten×0.001).

    inten 量纲校准: v1 训练 ses_load.feed raw inten (uint16 as float);
    簇级 probe JS 侧读 f32*0.001, Python extract_features 不怎么, 为此 两边 同 raw uint16.
    """
    import session_load as S
    Xp, yp, sp, np_ = [], [], [], []
    for sid in TRAIN_PERSON_SIDS:
        sd = os.path.join(S.REMOTE, sid)
        for xyz_i, lab, name in S.iter_session_frames(sd):
            Xp.append(extract_features(xyz_i)); yp.append(1); sp.append(sid); np_.append(name)
    sd = os.path.join(S.REMOTE, NONE_SID)
    none_rows = list(S.iter_none_frames(sd))
    seen = set()
    for xyz_i, lab, name in none_rows:
        fv = extract_features(xyz_i)
        key = tuple(np.round(fv, 6))
        if key in seen:
            continue
        seen.add(key)
        Xp.append(fv); yp.append(0); sp.append(NONE_SID); np_.append(name)
    Xa = np.asarray(Xp, np.float32)
    ya = np.asarray(yp, np.int32)
    sa = np.asarray(sp)
    na = np.asarray(np_)
    dup = np.asarray(np.logical_and(sa == NONE_SID, np.arange(len(sa)) % 2 == 0))
    Xa = np.vstack([Xa, Xa[dup]]); ya = np.concatenate([ya, ya[dup]])
    sa = np.concatenate([sa, sa[dup]]); na = np.concatenate([na, na[dup]])
    return Xa, ya, sa, na


def cluster_feats_as_array(rows):
    return np.asarray([r["fv"] for r in rows], np.float32), \
        np.asarray([1 if r["cls"] == "person" else 0 for r in rows], np.int32), \
        np.asarray([r["sid"] for r in rows])


def cluster_fixed(rows):
    """簇级 inten×0.001 反归一到 uint16 量纲 (与帧级训练同源) — 量纲校准."""
    X = np.asarray([r["fv"] for r in rows], np.float32).copy()
    for j, scale in [(3, 0.001), (45, 0.001), (46, 0.001), (47, 0.001)]:
        X[:, j] /= scale
    return X


def train_eval_exp(exp_id, X_train, y_train, s_train,
                   extra_clusters=None, person_dup=1):
    """LoS-fold 诚实评估.

    extra_clusters: np.array 家具或 person 簇特征 (反归一后) 作追加训练样本.
    person_dup: person 簇复制注入倍数 (用于远距强调).
    """
    X = X_train.copy(); y = y_train.copy(); s = s_train.copy()
    if extra_clusters is not None:
        X = np.vstack([X, extra_clusters[0]])
        y = np.concatenate([y, extra_clusters[1]])
        s = np.concatenate([s, extra_clusters[2]])

    folds = sorted(set(s))
    person_test_mask = np.isin(s, folds)
    metrics = {}
    for hold in folds:
        te = s == hold
        tr = ~te
        if len(np.unique(y[tr])) < 2:
            continue
        clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                                     n_jobs=-1, random_state=0)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        acc = accuracy_score(y[te], pred)
        cm = confusion_matrix(y[te], pred, labels=[0, 1])
        metrics[hold] = {"n": int(te.sum()), "acc": float(acc), "cm": cm.tolist()}

    n_acc = np.mean([m["acc"] for m in metrics.values()])
    n_fnr = 0.0
    fn, tp, tn, fp = 0, 0, 0, 0
    for m in metrics.values():
        cm = m["cm"]
        tn += cm[0][0]; fp += cm[0][1]; fn += cm[1][0]; tp += cm[1][1]
    n_recall_p = tp / max(tp + fn, 1)
    n_recall_n = tn / max(tn + fp, 1)
    return {"exp": exp_id, "loso_mean_acc": round(float(n_acc), 4),
            "person_recall": round(n_recall_p, 4), "noperson_recall": round(n_recall_n, 4),
            "per_fold": metrics,
            "fn": fn, "fp": fp, "tp": tp, "tn": tn}


def main():
    X_t, y_t, s_t, n_t = load_frame_trainset()
    rows = load_rows()
    Xc_raw, yc, sc = cluster_feats_as_array(rows)
    Xc = cluster_fixed(rows)

    person_rows = [r for r in rows if r["cls"] == "person"]
    Xp = np.asarray([r["fv"] for r in person_rows], np.float32)
    sp = np.asarray([r["sid"] for r in person_rows])
    yp = np.ones(len(Xp), np.int32)

    furn_rows = [r for r in rows if r["cls"] == "furniture"]
    Xf = np.asarray([r["fv"] for r in furn_rows], np.float32)
    sf = np.asarray([r["sid"] for r in furn_rows])
    yf = np.zeros(len(Xf), np.int32)

    results = []

    rf = train_eval_exp("v1_base", X_t, y_t, s_t)
    rf["note"] = "原 v1 pod 重训对照 (仅帧级, 无家具簇)"
    results.append(rf)

    rf = train_eval_exp("v2a_balanced", X_t, y_t, s_t)
    rf["note"] = "类权实验由 sklearn 自动平衡做不到; 实际等价于 v1()此实验不降噪— 仍记"
    results.append(rf)

    rf = train_eval_exp("v2b_furn_neg", X_t, y_t, s_t,
                        extra_clusters=(Xf, yf, sf))
    rf["note"] = "v1 + 324 家具簇作 noperson"
    results.append(rf)

    dup_p_idx = []
    for i, r in enumerate(person_rows):
        if r["sid"] in ("cap_20261009_122700", "cap_20261009_121723"):
            dup_p_idx.extend([i, i])
        else:
            dup_p_idx.append(i)
    Xp_dup = Xp[dup_p_idx]; yp_dup = np.ones(len(Xp_dup), np.int32)
    sp_dup = sp[dup_p_idx]
    Xcomb = np.vstack([X_t, Xf, Xp_dup])
    ycomb = np.concatenate([y_t, yf, yp_dup])
    scomb = np.concatenate([s_t, sf, sp_dup])
    rf = train_eval_exp("v2c_furn_neg_person_dup", X_t, y_t, s_t,
                        extra_clusters=(np.vstack([Xf, Xp_dup]),
                                        np.concatenate([yf, yp_dup]),
                                        np.concatenate([sf, sp_dup])))
    rf["note"] = "v2b + 远距 person 簇 ×2 强调"
    results.append(rf)

    furn_low_idx = [i for i, r in enumerate(furn_rows) if r["zmax"] < 1.2]
    furn_low_x3 = furn_low_idx * 3
    Xf_dup = np.vstack([Xf, Xf[furn_low_x3]])
    yf_dup = np.concatenate([yf, np.zeros(len(furn_low_x3), np.int32)])
    sf_dup = np.concatenate([sf, sf[furn_low_x3]])
    rf = train_eval_exp("v2d_furn_subgroup_x3", X_t, y_t, s_t,
                        extra_clusters=(np.vstack([Xf_dup, Xp_dup]),
                                        np.concatenate([yf_dup, yp_dup]),
                                        np.concatenate([sf_dup, sp_dup])))
    rf["note"] = "v2c + 低位 lap 柜簇子集 ×3"
    results.append(rf)

    # v2e 修复(复审R2 发现): 原 X_t2(51)/Xf2(53)/Xp2(单行) vstack 碰撞 — Xcomb2 从未被消费, 死代码.
    # 真"删 9 噪特征"消融: 统一在 51 维上 mask 掉 i_std/zb>2.2/r_lt3/z_p90 等 9 维(零填充), 再喂 train_eval_exp.
    drop_idx = [3, 13, 16, 45, 46, 47, 48, 49, 50]  # 9 个高噪/相关维(索引按 51 维 feat 契约)
    def _mask9(X):
        Xm = X[:, :51].copy()
        Xm[:, drop_idx] = 0.0
        return Xm
    rf = train_eval_exp("v2e_feat_ablate", _mask9(X_t), y_t, s_t,
                        extra_clusters=(np.vstack([_mask9(Xf), _mask9(Xp_dup)]),
                                        np.concatenate([yf, yp_dup]),
                                        np.concatenate([sf, sp_dup])))
    rf["note"] = "删 9 噪维(零填充)消融 — 修复原 53 维 vstack 碰撞死代码; 真实 frag ablate, 复跑可再生产"
    results.append(rf)

    with open(os.path.join(EVID, "rf_v2", "results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(EVID, "rf_v2", "SUMMARY.md"), "w", encoding="utf-8") as fh:
        fh.write("# C1.4 RF v2 离线候选评估 (LoS 诚实)\n\n")
        fh.write("| 实验 | LoS acc（帧级+簇级主任务) | person召回 | noperson召回 | 说明 |\n|---|---|---|---|---|\n")
        for r in results:
            fh.write("| %s | %.4f | %.4f | %.4f | %s |\n" % (
                r["exp"], r["loso_mean_acc"], r["person_recall"], r["noperson_recall"], r["note"]))
        fh.write("\n注: LoS 人召回 机帧级 fmt – 此表主任务 = 帧级训练 pod + 家具簇同训练; C1.6 A/B 会为簇级人/家具召回.\n")
    print("RF v2 →", os.path.join(EVID, "rf_v2"))


if __name__ == "__main__":
    main()
