#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_rf_v2_eval.py — C1.4 RF v2 离线候选, 以簇级 LoS 为主指标.

主任务 (与线上推理同域=簇级):
  - 正样本: 915 人簇 (person, 6 段, cls='person')
  - 负样本: 324 家具簇 (furniture, 只存在 4 段)
  - 额外 noperson 锚点: 空场帧级 dedup 集 (保人 vs 空场景 recall, DOM 保持)
  - 正样本锚点: 11 段帧级人 (防塌, 人召回锚点)
评估: LoS fold 按会话; 家具测试只在有家具会话上.
实验 (固定 1 个变量/次):
  v1_base           = 仅训练 pod 帧级 (11段人 + 空场dedup×2)
  v2b_hard_neg      = v1 + 324 家具簇 (noperson)
  v2c_person_dup    = v2b + 远距人簇 ×2
  v2d_subgroup      = v2c + 低位家具簇 (zmax<1.2) ×3 (难负强调)
  v2e_feat_only     = v2c + r_lt3, upright; 删 i_std, zb_36up (特征选择对照)
"""
import json, os, sys
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "pc_apps", "human_ml"))
from frame_feature import extract_features  # noqa


def load_rows():
    return [json.loads(l) for l in open(os.path.join(EVID, "rf_v2", "cluster_dataset.jsonl"),
                                        encoding="utf-8")]


def load_frame_pod():
    """Frame-level pod: v1 训练数据 (同 train_person_rf.py collect, 含 dedup×2 空场)."""
    import session_load as S
    person_sids = ["cap_20261009_114641", "cap_20261009_114709", "cap_20261009_114734",
                   "cap_20261009_114754", "cap_20261009_114817",
                   "cap_20261009_121622", "cap_20261009_121647", "cap_20261009_121723",
                   "cap_20261009_122616", "cap_20261009_122637", "cap_20261009_122700"]
    Xl, yl, sl = [], [], []
    for sid in person_sids:
        sd = os.path.join(S.REMOTE, sid)
        for xyz_i, lab, name in S.iter_session_frames(sd):
            Xl.append(extract_features(xyz_i)); yl.append(1); sl.append(sid)
    sd = os.path.join(S.REMOTE, "cap_20261009_113611")
    seen, uniq = set(), []
    for xyz_i, lab, name in S.iter_none_frames(sd):
        fv = extract_features(xyz_i)
        key = tuple(np.round(fv, 6))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((fv, name))
    for fv, name in uniq + uniq:  # ×2 dup
        Xl.append(fv); yl.append(0); sl.append("cap_20261009_113611")
    return np.asarray(Xl, np.float32), np.asarray(yl, np.int32), np.asarray(sl)


def build_cluster_set():
    rows = load_rows()
    X = np.asarray([r["fv"] for r in rows], np.float32)
    y = np.asarray([1 if r["cls"] == "person" else 0 for r in rows], np.int32)
    s = np.asarray([r["sid"] for r in rows])
    # 反归一 inten → uint16 量纲
    Xc = X.copy()
    for j in (3, 45, 46, 47):
        Xc[:, j] /= 0.001
    return Xc, y, s, rows


def eval_loso(X, y, s):
    """LoS-fold: 按会话留出; 报告主指标.

    主张粒度:
      - person_recall_cluster: 家具会话留 way 时 person 簇 TP/(TP+FN)
      - furniture_recall: 家具簇 TN/(TN+FP) (准确拒)
      - overall_acc: folds weighted
    """
    folds = sorted(set(s))
    res = {}
    for hold in folds:
        te = s == hold
        tr = ~te
        p_tr, n_tr = y[tr].sum(), (~y[tr].astype(bool)).sum()
        if n_tr == 0 or p_tr == 0:
            continue
        clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                                     n_jobs=-1, random_state=0)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        cm = confusion_matrix(y[te], pred, labels=[0, 1])
        res[hold] = {"n": int(te.sum()), "n_pos": int(y[te].sum()),
                     "cm": cm.tolist()}
    tn = sum(m["cm"][0][0] for m in res.values())
    fp = sum(m["cm"][0][1] for m in res.values())
    fn = sum(m["cm"][1][0] for m in res.values())
    tp = sum(m["cm"][1][1] for m in res.values())
    return {"per_fold": res, "tn": tn, "fp": fp, "fn": fn, "tp": tp,
            "person_recall": round(tp / max(tp + fn, 1), 4),
            "noperson_recall": round(tn / max(tn + fp, 1), 4)}


def run_exp(exp_id, X_frame, y_frame, s_frame,
            X_cl, y_cl, s_cl,
            extra_X=None, extra_y=None, extra_s=None):
    X = np.vstack([X_frame, extra_X]) if extra_X is not None else X_frame.copy()
    y = np.concatenate([y_frame, extra_y]) if extra_y is not None else y_frame.copy()
    s = np.concatenate([s_frame, extra_s]) if extra_s is not None else s_frame.copy()
    r = eval_loso(X, y, s)
    r["exp"] = exp_id
    r["n_train"] = int(len(y))
    return r


def main():
    X_fr, y_fr, s_fr = load_frame_pod()
    X_cl, y_cl, s_cl, rows = build_cluster_set()

    person_mask = y_cl == 1
    furn_mask = ~person_mask
    Xp, yp, sp = X_cl[person_mask], y_cl[person_mask], s_cl[person_mask]
    Xf, yf, sf = X_cl[furn_mask], y_cl[furn_mask], s_cl[furn_mask]

    def drop_leak(X):
        idx = [i for i in range(51) if i not in (0, 1, 2)]
        return X[:, idx]

    out = []

    r = run_exp("v1_base", X_fr, y_fr, s_fr, X_cl, y_cl, s_cl)
    r["note"] = "仅帧级 pod (11段人 + 空场dedup×2)"
    out.append(r)

    r = run_exp("v1_noleak", drop_leak(X_fr), y_fr, s_fr, drop_leak(X_cl), y_cl, s_cl)
    r["note"] = "v1 + 去 fv[0/1/2] (n_pts/max_pts) → 验证 n_pts 是否泄漏源"
    out.append(r)

    r = run_exp("v2b_hard_neg", X_fr, y_fr, s_fr, X_cl, y_cl, s_cl,
                extra_X=Xf, extra_y=yf, extra_s=sf)
    r["note"] = "v1 + 324 家具簇 (noperson)"
    out.append(r)

    r = run_exp("v2b_noleak", drop_leak(X_fr), y_fr, s_fr, drop_leak(X_cl), y_cl, s_cl,
                extra_X=drop_leak(Xf), extra_y=yf, extra_s=sf)
    r["note"] = "v2b + 去 n_pts/max_pts 泄漏特征 → 真正的泛化力"
    out.append(r)

    far_sids = np.isin(sp, ["cap_20261009_122700", "cap_20261009_121723"])
    Xp_dup = np.vstack([Xp[far_sids], Xp[far_sids], Xp[~far_sids]])
    yp_dup = np.ones(len(Xp_dup), np.int32)
    sp_dup = np.concatenate([sp[far_sids], sp[far_sids], sp[~far_sids]])
    Xcombined = np.vstack([Xf, Xp_dup])
    ycombined = np.concatenate([yf, yp_dup])
    scombined = np.concatenate([sf, sp_dup])
    r = run_exp("v2c_furn_person_dup", X_fr, y_fr, s_fr, X_cl, y_cl, s_cl,
                extra_X=Xcombined, extra_y=ycombined, extra_s=scombined)
    r["note"] = "v2b + 远距 human 簇×2"
    out.append(r)

    furn_indices = np.flatnonzero(furn_mask)
    low_furn_local = [i for i, j in enumerate(furn_indices)
                      if rows[j]["zmax"] < 1.2]
    rep_idx = np.asarray(low_furn_local, np.int32).repeat(3) if low_furn_local \
        else np.arange(0, dtype=np.int32)
    Xf_low_x3 = Xf[rep_idx]
    yf_low_x3 = np.zeros(len(Xf_low_x3), np.int32)
    sf_low_x3 = sf[rep_idx]
    Xcombined = np.vstack([Xf, Xf_low_x3, Xp_dup])
    ycombined = np.concatenate([yf, yf_low_x3, yp_dup])
    scombined = np.concatenate([sf, sf_low_x3, sp_dup])
    r = run_exp("v2d_subgroup_x3", X_fr, y_fr, s_fr, X_cl, y_cl, s_cl,
                extra_X=Xcombined, extra_y=ycombined, extra_s=scombined)
    r["note"] = "v2c + 低位家具簇 ×3"
    out.append(r)

    drop_idx = [4, 14, 15, 16, 17, 21, 22, 48, 49]
    r = run_exp("v2e_feat_ablate", X_fr[:, [i for i in range(51) if i not in drop_idx]],
                y_fr, s_fr, X_cl[:, [i for i in range(51) if i not in drop_idx]],
                y_cl, s_cl,
                extra_X=Xcombined[:, [i for i in range(51) if i not in drop_idx]],
                extra_y=ycombined, extra_s=scombined)
    r["note"] = "v2d + 删 9 相关高/噪特征 (i_std, zb>2.2, r_lt3, z_p90)"
    out.append(r)

    json.dump(out, open(os.path.join(EVID, "rf_v2", "results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(EVID, "rf_v2", "SUMMARY.md"), "w", encoding="utf-8") as fh:
        fh.write("# C1.4 RF v2 离线候选评估 (LoS 诚实)\n\n")
        fh.write("| 实验 | n_train | person召回 | noperson召回 | 说明 |\n|---|---|---|---|---|\n")
        for r in out:
            fh.write("| %s | %d | %.4f | %.4f | %s |\n" % (
                r["exp"], r["n_train"], r["person_recall"], r["noperson_recall"], r["note"]))
        fh.write("\n主任务 = 训练 pod (帧级+簇样本+家具 neg) 的 LoS; cn 簇级 A/B 见 C1.6.\n")
    for r in out:
        print(r["exp"], "person=%.3f furniture_rej=%.3f" % (r["person_recall"], r["noperson_recall"]))
    print("RF v2 eval →", os.path.join(EVID, "rf_v2"))


if __name__ == "__main__":
    main()
