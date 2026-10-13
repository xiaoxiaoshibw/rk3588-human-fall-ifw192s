# -*- coding: utf-8 -*-
"""D3 分类器实验（切片版，每步独立重入）。

子命令：
  rf       — M0 基线 + M1 RF69 + M1 三组消融 → work/d3_rf.json
  xgb      — M2 XGB69 → work/d3_xgb.json
  pn       — 候选 xyz 重建并缓存 → work/d3_xyz_cache.npz
  m3       — PointNet (plain) 训练推理 → work/d3_m3.json
  m4       — PointNet++ mini-SSG        → work/d3_m4.json
  finish   — 汇总 → evidence/D3_CLASSIFIER_ABLATION.json
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

F51 = 51
F69 = 51 + 18
W = C.WORK
EVD = C.EVIDENCE


def load_rows():
    rows = [json.loads(l) for l in
            open(os.path.join(W, "d3_dataset.jsonl"), encoding="utf-8")]
    X51 = np.array([r["f51"] for r in rows], dtype=np.float32)
    X18 = np.array([r["x18"] for r in rows], dtype=np.float32)
    X69 = np.concatenate([X51, X18], axis=1)
    y = np.array([r["y"] for r in rows], dtype=np.int64)
    fold = np.array([r["fold"] for r in rows])
    sid = np.array([r["sid"] for r in rows])
    prob = np.array([r["rf_prob"] for r in rows], dtype=np.float64)
    for f in set(fold):
        sids_f = set(sid[fold == f].tolist())
        for g in set(fold):
            if f != g:
                assert not (sids_f & set(sid[fold == g].tolist()))
    return rows, X51, X18, X69, y, fold, sid, prob


def metrics(y_true, p, name):
    from sklearn.metrics import average_precision_score, \
        precision_recall_curve
    out = {"model": name, "n": int(len(y_true)), "pos": int(y_true.sum())}
    if len(np.unique(y_true)) < 2:
        out["auprc"] = None
        return out
    out["auprc"] = round(float(average_precision_score(y_true, p)), 4)
    pr, rc, t = precision_recall_curve(y_true, p)
    f1 = 2 * pr * rc / np.clip(pr + rc, 1e-9, None)
    i = int(np.nanargmax(f1))
    out["best_f1"] = round(float(f1[i]), 4)
    out["best_thr"] = round(float(t[i - 1]) if i > 0 else 0.5, 3)
    pred = (p >= 0.5).astype(int)
    tp = int((pred & (y_true == 1)).sum())
    fp = int((pred & (y_true == 0)).sum())
    fn = int(((pred == 0) & (y_true == 1)).sum())
    out["p@0.5"] = round(tp / max(tp + fp, 1), 4)
    out["r@0.5"] = round(tp / max(tp + fn, 1), 4)
    out["f1@0.5"] = round(2 * tp / max(2 * tp + fp + fn, 1), 4)
    return out


def by_fold(name, p, y, fold):
    return [{"fold": f, **metrics(y[fold == f], p[fold == f], name)}
            for f in ("train", "val", "test", "stress")
            if (fold == f).any()]


def cmd_rf():
    rows, X51, X18, X69, y, fold, sid, rf_prob = load_rows()
    tr = fold == "train"
    out = {"M0_RF51": by_fold("M0_RF51", rf_prob, y, fold)}
    from sklearn.ensemble import RandomForestClassifier
    m1 = RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                class_weight="balanced_subsample",
                                random_state=20261012).fit(X69[tr], y[tr])
    out["M1_RF69"] = by_fold("M1_RF69", m1.predict_proba(X69)[:, 1],
                             y, fold)
    out["M1_top_features"] = sorted(
        zip(["f51_%d" % i for i in range(F51)]
            + ["x18_%d" % i for i in range(18)],
            m1.feature_importances_.tolist()),
        key=lambda x: -x[1])[:15]
    for gname, cols in {
            "A1_no_intensity": [i for i in range(F69)
                                if i not in (3, 4, 45, 46, 47)],
            "A2_no_pca": [i for i in range(F69) if not 32 <= i <= 40],
            "A3_only_x18": list(range(F51, F69))}.items():
        m = RandomForestClassifier(n_estimators=200, n_jobs=-1,
                                   class_weight="balanced_subsample",
                                   random_state=20261012)
        m.fit(X69[tr][:, cols], y[tr])
        out["M1_" + gname] = {
            "n_features": len(cols),
            "folds": by_fold("M1_" + gname,
                             m.predict_proba(X69[:, cols])[:, 1],
                             y, fold)}
    json.dump(out, open(os.path.join(W, "d3_rf.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[D3-rf] done")


def cmd_xgb():
    rows, X51, X18, X69, y, fold, sid, _ = load_rows()
    tr = fold == "train"
    va = fold == "val"
    import xgboost as xgb
    ytr = y[tr]
    spw = float((ytr == 0).sum() / max((ytr == 1).sum(), 1))
    m2 = xgb.XGBClassifier(n_estimators=600, max_depth=6,
                           learning_rate=0.05, subsample=0.8,
                           colsample_bytree=0.8, scale_pos_weight=spw,
                           eval_metric="aucpr", early_stopping_rounds=40,
                           random_state=20261012, n_jobs=-1)
    va_idx = np.nonzero(va)[0]
    tr_idx = np.nonzero(tr)[0]
    m2.fit(X69[tr_idx], y[tr_idx],
           eval_set=[(X69[va_idx], y[va_idx])]
           if len(va_idx) else None, verbose=False)
    p2 = m2.predict_proba(X69)[:, 1]
    out = {"M2_XGB69": by_fold("M2_XGB69", p2, y, fold),
           "M2_best_iter": int(getattr(m2, "best_iteration", -1)),
           "M2_top_features": sorted(
               zip(["f51_%d" % i for i in range(F51)]
                   + ["x18_%d" % i for i in range(18)],
                   m2.feature_importances_.tolist()),
               key=lambda x: -x[1])[:15]}
    json.dump(out, open(os.path.join(W, "d3_xgb.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    print("[D3-xgb] done best_iter=%s" % out["M2_best_iter"])


def cmd_pn():
    """重建候选 xyz（只 P/N 行，d3 内）并缓存 npz。"""
    rows, X51, X18, X69, y, fold, sid, prob = load_rows()
    mm = {}
    frame_cache = {}
    cand_idx = {}
    for r in rows:
        cand_idx.setdefault((r["sid"], r["frame"]), {})
    for i, r in enumerate(rows):
        cand_idx[(r["sid"], r["frame"])][r["cand"]] = None
    for (sid, fi), need in cand_idx.items():
        for rec in C.iter_ledger(sid, fields=["frame_index",
                                              "candidates"]):
            if rec["frame_index"] != fi:
                continue
            for c in rec.get("candidates", []):
                if c["id"] in need:
                    need[c["id"]] = np.asarray(c["raw_indices"],
                                               dtype=np.int64)
            break
    # 物化
    X = []
    for i, r in enumerate(rows):
        key = (r["sid"], r["frame"])
        if key not in frame_cache:
            xyz, _i, m = C.read_frame_xyz(r["sid"], r["frame"],
                                          mm=mm.get(r["sid"]))
            mm[r["sid"]] = m
            frame_cache[key] = C.level(xyz).astype(np.float32)
        idx = cand_idx[key][r["cand"]]
        X.append(frame_cache[key][idx])
    # pad to max n
    nmax = max(len(x) for x in X)
    pts = np.zeros((len(X), nmax, 3), dtype=np.float32)
    cnt = np.zeros(len(X), dtype=np.int64)
    for i, x in enumerate(X):
        pts[i, :len(x)] = x
        cnt[i] = len(x)
    np.savez_compressed(os.path.join(W, "d3_xyz_cache.npz"),
                        pts=pts, cnt=cnt)
    print("[D3-pn] cache rows=%d nmax=%d" % (len(X), nmax))


def _sample(pts, n, target, seed):
    rng = np.random.default_rng(seed)
    if n >= target:
        sel = rng.choice(n, target, replace=False)
    else:
        sel = np.concatenate([np.arange(n),
                              rng.choice(n, target - n, replace=True)])
    p = pts[sel]
    return p - p.mean(0, keepdims=True)


def _torch_main(variant, tag):
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    torch.manual_seed(20261012)
    np.random.seed(20261012)
    rows, X51, X18, X69, y, fold, sid, prob = load_rows()
    z = np.load(os.path.join(W, "d3_xyz_cache.npz"))
    pts_all, cnt = z["pts"], z["cnt"]
    target = 256 if variant == "plain" else 512

    class DS(Dataset):
        def __init__(self, ids):
            self.ids = ids

        def __len__(self):
            return len(self.ids)

        def __getitem__(self, k):
            i = int(self.ids[k])
            p = _sample(pts_all[i, :cnt[i]], cnt[i], target,
                        20261012 + i)
            return torch.from_numpy(p).float(), int(y[i])

    class PNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.m = nn.Sequential(nn.Conv1d(3, 64, 1), nn.ReLU(),
                                   nn.Conv1d(64, 128, 1), nn.ReLU(),
                                   nn.Conv1d(128, 256, 1), nn.ReLU())
            self.f = nn.Sequential(nn.Linear(256, 128), nn.ReLU(),
                                   nn.Dropout(0.3), nn.Linear(128, 2))

        def forward(self, x):
            return self.f(self.m(x.transpose(1, 2)).max(-1).values)

    class PSA(nn.Module):
        def __init__(self):
            super().__init__()
            self.local = nn.Sequential(nn.Conv2d(6, 64, 1), nn.ReLU(),
                                       nn.Conv2d(64, 64, 1), nn.ReLU())
            self.glob = nn.Sequential(nn.Conv1d(64 + 3, 128, 1), nn.ReLU(),
                                      nn.Conv1d(128, 256, 1), nn.ReLU())
            self.f = nn.Sequential(nn.Linear(256, 128), nn.ReLU(),
                                   nn.Dropout(0.3), nn.Linear(128, 2))

        def forward(self, x):
            B, N, _ = x.shape
            n2 = min(64, N)                           # 中心点数（小簇，CPU）
            k = 8                                     # 邻居数
            idx = torch.randperm(N, device=x.device)[:n2]
            ctr = x[:, idx, :]                        # (B,n2,3)
            # d2[i,p,c] = ||x_p - ctr_c||^2 ; 对每个中心取 N 维最近 k 点
            d2 = ((x[:, :, None, :] - ctr[:, None, :, :]) ** 2).sum(-1)
            nn_idx = d2.topk(k, dim=1, largest=False).indices  # (B,k,n2)
            nn_idx = nn_idx.permute(0, 2, 1)          # (B,n2,k)
            bi = torch.arange(B, device=x.device).view(B, 1, 1) \
                .expand(-1, n2, k)
            neigh = x[bi, nn_idx, :]                  # (B,n2,k,3)
            rel = neigh - ctr[:, :, None, :]
            feat = torch.cat([rel, ctr[:, :, None, :]
                              .expand(-1, -1, k, -1)], -1)   # (B,n2,k,6)
            h = self.local(feat.permute(0, 3, 1, 2)).max(-1).values  # (B,64,n2)
            h = torch.cat([h, ctr.transpose(1, 2)], 1)      # (B,64+3,n2)
            return self.f(self.glob(h).max(-1).values)


    ids_tr = np.nonzero(fold == "train")[0]
    ids_va = np.nonzero(fold == "val")[0]
    net = PNet() if variant == "plain" else PSA()
    opt = torch.optim.Adam(net.parameters(), lr=1e-3)
    lossfn = nn.CrossEntropyLoss()
    dl = DataLoader(DS(ids_tr), batch_size=16, shuffle=True)
    dlv = DataLoader(DS(ids_va), batch_size=64)
    best, bstate, patience = -1.0, None, 0
    for ep in range(15):
        net.train()
        for xb, yb in dl:
            opt.zero_grad()
            lossfn(net(xb), yb).backward()
            opt.step()
        net.eval()
        corr = tot = 0
        with torch.no_grad():
            for xb, yb in dlv:
                corr += int((net(xb).argmax(-1) == yb).sum())
                tot += len(yb)
        acc = corr / max(tot, 1)
        if acc > best:
            best, bstate = acc, {k: v.clone() for k, v in
                                 net.state_dict().items()}
            patience = 0
        else:
            patience += 1
            if patience >= 5:
                break
    if bstate:
        net.load_state_dict(bstate)
    probs = np.zeros(len(rows), dtype=np.float64)
    net.eval()
    with torch.no_grad():
        alld = DataLoader(DS(np.arange(len(rows))), batch_size=64)
        off = 0
        for xb, _ in alld:
            p = torch.softmax(net(xb), -1)[:, 1].numpy()
            probs[off:off + len(p)] = p
            off += len(p)
    out = {tag: by_fold(tag, probs, y, fold),
           tag + "_meta": {"variant": variant,
                           "best_val_acc": round(float(best), 4),
                           "train_n": len(ids_tr),
                           "val_n": len(ids_va)}}
    json.dump(out, open(os.path.join(W, "d3_%s.json" % tag.lower()),
                        "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("[D3-%s] done best_val=%.4f" % (tag, best))


def cmd_finish():
    out = {"n": None, "fold_sids": {}}
    rows, X51, X18, X69, y, fold, sid, _ = load_rows()
    out["n"] = len(y)
    out["pos"] = int(y.sum())
    out["fold_sids"] = {f: sorted(set(sid[fold == f].tolist()))
                        for f in set(fold)}
    for f in ("rf", "xgb", "m3_pointnet", "m4_pointnetpp"):
        p = os.path.join(W, "d3_%s.json" % f)
        if os.path.exists(p):
            out.update(json.load(open(p, encoding="utf-8")))
    dst = os.path.join(EVD, "D3_CLASSIFIER_ABLATION.json")
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("[D3-finish] written %s" % dst)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "rf"
    if c == "rf":
        cmd_rf()
    elif c == "xgb":
        cmd_xgb()
    elif c == "pn":
        cmd_pn()
    elif c == "m3":
        _torch_main("plain", "M3_PointNet")
    elif c == "m4":
        _torch_main("ssg", "M4_PointNetPP")
    elif c == "finish":
        cmd_finish()
    else:
        print("usage: d3_classifiers.py [rf|xgb|pn|m3|m4|finish]")
