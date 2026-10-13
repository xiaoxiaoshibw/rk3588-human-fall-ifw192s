# -*- coding: utf-8 -*-
"""HFUS-RD-02 工作四：分类器公平对比（阻断 RD-01 的会话泄漏）。

RD-01 的失败模式（工作一已证）：train 负例 100% 来自 S1、正例 100% 来自
S3-near → "会话A的物 vs 会话B的人"，val 全正无判别。

本实验重划分（seed=20261012，帧级）：
  train_pos  S3-near 偶数帧 259→ 实际 (frames 0,2,4…) 的正例行
  train_neg  S1 偶数帧候选    (~184)
  test_pos   S3-near 奇数帧 + S3-far 全部（会话级 OOS）
  test_neg   S1 奇数帧候选    (~202)
  → 测试负例与训练负例来自**不同帧**，正/负例各自同会话但异帧；
  → S3-far 是整会话 OOS 正例（从未参与任何训练）。

模型（全部用同 69 维特征，除非注明）：
  M0_RF51      冻结生产分数（ledger rf_prob，out-of-sample by construction）
  M1_RF69      RF 200 树
  M2_XGB69     XGBoost hist
  M3_ABL_x18   仅 18 维扩展特征（消融）
  M4_ABL_51    仅 51 维（消融）
  M5_PN        轻量 PointNet（复用 RD-01 PNet 结构，1024 点重采样）

指标：tests 上的 AUPRC / P@thr / R@thr / F1@thr，阈值取 train 上的
best-F1 阈值（不在测试上调阈值）。分 n 桶（<100/100-999/1000+）报。

诚实约束：测试负例仅 S1 家具（单一场景）→ 结果标注 "neg=S1-only"，
不外推其它场景；S3-far 正例是唯一真 OOS 会话。
输出 work/w4_fair.json + evidence/W4_MODEL_COMPARE.json。
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np

_RD1 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "HFUS-RD-01", "tools")
sys.path.insert(0, os.path.abspath(_RD1))

WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "work")
EVID = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "..", "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
D3 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "HFUS-RD-01", "work", "d3_dataset.jsonl")
XYZ = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "HFUS-RD-01", "work", "d3_xyz_cache.npz")
os.makedirs(WORK, exist_ok=True)
SEED = 20261012
F51 = 51
F69 = 69


def load():
    with open(D3, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f]
    X69 = np.array([r["f51"] + r["x18"] for r in rows], dtype=np.float32)
    y = np.array([r["y"] for r in rows], dtype=np.int64)
    sid = np.array([r["sid"][-6:] for r in rows])
    fr = np.array([r["frame"] for r in rows])
    prob = np.array([r["rf_prob"] for r in rows], dtype=np.float64)
    n = np.array([r["n"] for r in rows])
    # 划分：S1(175227) 负例帧奇偶；S3-near(175429) 正例帧奇偶
    tr = ((sid == "175227") & (fr % 2 == 0)) | \
         ((sid == "175429") & (fr % 2 == 0))
    te = ((sid == "175227") & (fr % 2 == 1)) | \
         ((sid == "175429") & (fr % 2 == 1)) | (sid == "175553")
    return rows, X69, y, sid, fr, prob, n, tr, te


def m_metrics(y_true, p, thr, name, mask=None):
    from sklearn.metrics import average_precision_score
    if mask is not None:
        y_true, p = y_true[mask], p[mask]
    out = {"model": name, "n": int(len(y_true)), "pos": int(y_true.sum()),
           "neg": int(len(y_true) - y_true.sum())}
    if len(np.unique(y_true)) < 2:
        out["auprc"] = None
        return out
    out["auprc"] = round(float(average_precision_score(y_true, p)), 4)
    pred = (p >= thr).astype(int)
    tp = int((pred & (y_true == 1)).sum())
    fp = int((pred & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    out["thr"] = round(float(thr), 4)
    out["precision"] = round(tp / max(tp + fp, 1), 4)
    out["recall"] = round(tp / max(tp + fn, 1), 4)
    out["f1"] = round(2 * tp / max(2 * tp + fp + fn, 1), 4)
    out["fp_at_thr"] = fp
    return out


def best_thr_train(y, p):
    from sklearn.metrics import precision_recall_curve
    if len(np.unique(y)) < 2:
        return 0.5
    pr, rc, t = precision_recall_curve(y, p)
    f1 = 2 * pr * rc / np.clip(pr + rc, 1e-9, None)
    i = int(np.nanargmax(f1))
    return float(t[i - 1]) if i > 0 and len(t) else 0.5


def train_models(X69, y, tr):
    from sklearn.ensemble import RandomForestClassifier
    res = {}
    rf = RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                class_weight="balanced_subsample",
                                random_state=SEED).fit(X69[tr], y[tr])
    res["M1_RF69"] = rf.predict_proba(X69)[:, 1]
    res["_M1_thr"] = best_thr_train(y[tr], res["M1_RF69"][tr])
    try:
        import xgboost as xgb
        spw = float((y[tr] == 0).sum() / max((y[tr] == 1).sum(), 1))
        xg = xgb.XGBClassifier(n_estimators=400, max_depth=5,
                               learning_rate=0.06, subsample=0.85,
                               colsample_bytree=0.8, scale_pos_weight=spw,
                               eval_metric="logloss",
                               random_state=SEED, n_jobs=-1)
        xg.fit(X69[tr], y[tr], verbose=False)
        res["M2_XGB69"] = xg.predict_proba(X69)[:, 1]
        res["_M2_thr"] = best_thr_train(y[tr], res["M2_XGB69"][tr])
    except ImportError:
        pass
    # 消融
    rf18 = RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                  class_weight="balanced_subsample",
                                  random_state=SEED)
    rf18.fit(X69[tr][:, F51:], y[tr])
    res["M3_ABL_x18only"] = rf18.predict_proba(X69[:, F51:])[:, 1]
    res["_M3_thr"] = best_thr_train(y[tr], res["M3_ABL_x18only"][tr])
    rf51 = RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                  class_weight="balanced_subsample",
                                  random_state=SEED)
    rf51.fit(X69[tr][:, :F51], y[tr])
    res["M4_ABL_51only"] = rf51.predict_proba(X69[:, :F51])[:, 1]
    res["_M4_thr"] = best_thr_train(y[tr], res["M4_ABL_51only"][tr])
    return res


def train_pointnet(rows, y, tr, te):
    """轻量 PointNet：1024 点重采样 + 复用 RD-01 PNet 结构。"""
    import torch
    import torch.nn as nn
    z = np.load(XYZ)
    pts_all, cnt = z["pts"], z["cnt"]
    N = 512

    def sample(i, rng):
        c = int(cnt[i])
        if c == 0:
            return np.zeros((N, 3), dtype=np.float32)
        idx = rng.choice(c, N, replace=c < N)
        return pts_all[i, idx].astype(np.float32)

    torch.manual_seed(SEED)
    tr_idx = np.nonzero(tr)[0]
    te_idx = np.nonzero(te)[0]
    # 归一化：候选质心置零 + 尺度归一（防会话位置泄漏）
    norm = {}
    for i in np.concatenate([tr_idx, te_idx]):
        rng = np.random.RandomState(SEED + int(i))
        p = sample(int(i), rng)
        p = p - p.mean(axis=0)
        s = max(np.abs(p).max(), 1e-3)
        norm[int(i)] = p / s

    class PNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.c1 = nn.Conv1d(3, 64, 1)
            self.c2 = nn.Conv1d(64, 128, 1)
            self.c3 = nn.Conv1d(128, 256, 1)
            self.fc1 = nn.Linear(256, 128)
            self.fc2 = nn.Linear(128, 1)
            self.bn1 = nn.BatchNorm1d(64)
            self.bn2 = nn.BatchNorm1d(128)
            self.bn3 = nn.BatchNorm1d(256)

        def forward(self, x):
            x = torch.relu(self.bn1(self.c1(x)))
            x = torch.relu(self.bn2(self.c2(x)))
            x = torch.relu(self.bn3(self.c3(x)))
            x = x.max(dim=2)[0]
            return self.fc2(torch.relu(self.fc1(x))).squeeze(1)

    net = PNet()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lossf = nn.BCEWithLogitsLoss()
    Xtr = torch.tensor(np.stack([norm[int(i)] for i in tr_idx]).transpose(0, 2, 1))
    ytr = torch.tensor(y[tr_idx], dtype=torch.float32)
    ntr = len(tr_idx)
    bs = 32
    for ep in range(25):
        perm = torch.randperm(ntr)
        net.train()
        for b0 in range(0, ntr, bs):
            bidx = perm[b0:b0 + bs]
            opt.zero_grad()
            out = net(Xtr[bidx])
            l = lossf(out, ytr[bidx])
            l.backward()
            opt.step()
    net.eval()
    p = np.zeros(len(rows), dtype=np.float64)
    with torch.no_grad():
        for b0 in range(0, len(te_idx), 64):
            b = te_idx[b0:b0 + 64]
            Xb = torch.tensor(np.stack([norm[int(i)] for i in b]).transpose(0, 2, 1))
            p[b] = torch.sigmoid(net(Xb)).numpy()
    # train 分数（阈值用）
    with torch.no_grad():
        ptr = np.zeros(ntr)
        for b0 in range(0, ntr, 64):
            b = tr_idx[b0:b0 + 64]
            Xb = Xtr[b0:b0 + 64]
            ptr[b0:b0 + len(b)] = torch.sigmoid(net(Xb)).numpy()
    return p, ptr, float(best_thr_train(y[tr_idx], ptr))


def main():
    rows, X69, y, sid, fr, prob, n, tr, te = load()
    print("[w4] train n=%d (pos=%d neg=%d) | test n=%d (pos=%d neg=%d)"
          % (tr.sum(), int(y[tr].sum()), int((y[tr] == 0).sum()),
             te.sum(), int(y[te].sum()), int((y[te] == 0).sum())))
    res = train_models(X69, y, tr)
    # M0 冻结分数
    thr0 = best_thr_train(y[tr], prob[tr])
    out = {"split": {
        "train": "S1 偶数帧(neg) + S3-near 偶数帧(pos)",
        "test": "S1 奇数帧(neg) + S3-near 奇数帧(pos) + S3-far 全会话(pos)",
        "n_train": int(tr.sum()), "n_test": int(te.sum()),
        "train_pos": int(y[tr].sum()), "train_neg": int((y[tr] == 0).sum()),
        "test_pos": int(y[te].sum()), "test_neg": int((y[te] == 0).sum()),
        "leak_note": ("测试负例与训练负例来自不同帧（奇偶拆分）；S3-far "
                      "整会话从未参与训练 = 真 OOS。负例仍全部是 S1 家具 → "
                      "结果仅对 'S1家具场景' 的负例有效，不外推。")}}
    out["models"] = {}
    out["models"]["M0_RF51_FROZEN"] = m_metrics(y[te], prob[te], thr0,
                                                "M0_RF51_FROZEN")
    for name in ["M1_RF69", "M2_XGB69", "M3_ABL_x18only", "M4_ABL_51only"]:
        if name not in res:
            continue
        out["models"][name] = m_metrics(y[te], res[name][te],
                                        res["_" + name.split("_")[0] + "_thr"]
                                        if ("_" + name.split("_")[0] + "_thr")
                                        in res else 0.5, name)
    # 分 n 桶
    out["by_bucket"] = {}
    for name, pcol, thrk in [("M0_RF51_FROZEN", prob, None),
                             ("M1_RF69", res.get("M1_RF69"), "_M1_thr"),
                             ("M2_XGB69", res.get("M2_XGB69"), "_M2_thr")]:
        if pcol is None:
            continue
        thr = thr0 if thrk is None else res[thrk]
        rows_b = {}
        for bname, lo, hi in [("lt100", 0, 99), ("mid_100_999", 100, 999),
                              ("ge1000", 1000, 10 ** 9)]:
            mk = te & (n >= lo) & (n <= hi)
            if mk.sum():
                rows_b[bname] = m_metrics(y, pcol, thr, name, mask=mk)
        out["by_bucket"][name] = rows_b
    # PointNet
    try:
        pn, pntr, thr5 = train_pointnet(rows, y, tr, te)
        out["models"]["M5_PointNet"] = m_metrics(y, pn, thr5, "M5_PointNet",
                                                 mask=te)
        out["models"]["M5_PointNet"]["train_auprc_note"] = "见 split 说明"
        out["_m5_thr"] = thr5
    except Exception as e:  # noqa: BLE001
        out["models"]["M5_PointNet"] = {"status": "ERROR", "err": str(e)[:200]}
    # 概率校准检查：用同时含正负的 test 集算 Brier + 校准曲线
    cal = {}
    for name, pcol, thrk in [("M0_RF51_FROZEN", prob, None),
                             ("M1_RF69", res.get("M1_RF69"), "_M1_thr"),
                             ("M2_XGB69", res.get("M2_XGB69"), "_M2_thr")]:
        if pcol is None:
            continue
        yt, pt = y[te], pcol[te]
        cal[name] = {
            "brier": round(float(np.mean((pt - yt) ** 2)), 4),
            "mean_pred": round(float(pt.mean()), 4),
            "base_rate": round(float(yt.mean()), 4),
            "hist": [[round(float(b), 2),
                      int(((pt >= b) & (pt < b + 0.1)).sum()),
                      round(float(yt[(pt >= b) & (pt < b + 0.1)].mean()), 3)
                      if ((pt >= b) & (pt < b + 0.1)).sum() else None]
                     for b in np.arange(0, 1.0, 0.1)]}
    out["calibration_on_test"] = cal
    out["calibration_note"] = ("测试集同时含正负 → Brier/校准曲线在此有效；"
                               "这是 RD-01 未做到的（其 val 全正）。")
    with open(os.path.join(WORK, "w4_fair.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(EVID, "W4_MODEL_COMPARE.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("[w4] done → W4_MODEL_COMPARE.json")
    for k, v in out["models"].items():
        print("   %-18s AUPRC=%s P=%s R=%s F1=%s" %
              (k, v.get("auprc"), v.get("precision"), v.get("recall"),
               v.get("f1")))


if __name__ == "__main__":
    main()
