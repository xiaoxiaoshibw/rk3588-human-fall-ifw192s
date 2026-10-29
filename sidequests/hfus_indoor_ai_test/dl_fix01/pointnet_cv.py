"""HFUS-DL-OPT-01：PointNet 训练协议三缺陷修复（合成自验版）。

对应 HFUS-INDOOR-TRAIN-AI01 R2 只读审查发现 2（T06/T07 FAIL）：
  1. 旧实现折循环前只建一次模型/Adam，后 3 折验证已见训练
     → 本实现每折新建模型与优化器（carry_state=True 仅作旧缺陷对照，默认关）。
  2. 旧实现按全量 25782/49≈526 设 pos_weight，而训练实际只用 6000 采样子集（49 正/5951 负≈121）
     → 本实现 pos_weight_from() 取各训练折实际采样分布（全正 + 负采样后 n/p）。
  3. 旧实现后 3 折不是有效 OOF
     → 本实现每条折外预测只来自训练成员不含该折的模型，1:1 覆盖、不丢样，并留成员重叠计数。

真实输入（ML/data 三 ZIP、候选/标签账本、原训练器）在本机缺失，真实训练与真实效果 BLOCKED；
本文件只做协议实现与合成自验，不复刻旧训练器、不冒充真实效果。
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import torch
import torch.nn as nn


class TinyPointNet(nn.Module):
    """共享 MLP + max pool 的极小 PointNet（盒系 xyz 输入），无 T-Net。"""

    def __init__(self, hidden: int = 32, seed: int = 43):
        super().__init__()
        torch.manual_seed(seed)
        self.mlp = nn.Sequential(
            nn.Linear(3, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU()
        )
        self.head = nn.Linear(hidden, 1)

    def forward(self, points: torch.Tensor) -> torch.Tensor:  # (B, N, 3) -> (B,)
        feat = self.mlp(points)
        return self.head(feat.max(dim=1).values).squeeze(-1)


def init_model(hidden: int = 32, seed: int = 43) -> TinyPointNet:
    return TinyPointNet(hidden=hidden, seed=seed)


def state_hash(model: nn.Module) -> str:
    h = hashlib.sha256()
    for tensor in model.state_dict().values():
        h.update(tensor.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def sample_subset(y: np.ndarray, cap: int = 6000, seed: int = 43) -> np.ndarray:
    """原 6000 子集规则：全部正例 + 负例随机抽样补足 cap。返回传入数组的局部下标。"""
    y = np.asarray(y)
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    if len(pos) == 0:
        raise ValueError("训练折采样后无正例，无法设定 pos_weight")
    room = max(cap - len(pos), 0)
    if len(neg) > room:
        neg = np.random.RandomState(seed).choice(neg, size=room, replace=False)
    return np.sort(np.concatenate([pos, neg]))


def pos_weight_from(y_sampled: np.ndarray) -> float:
    """缺陷 2 修复点：权重取实际采样分布 n/p，而非全量比例。"""
    y_sampled = np.asarray(y_sampled)
    pos = int((y_sampled == 1).sum())
    neg = int((y_sampled == 0).sum())
    if pos == 0:
        raise ValueError("采样分布中无正例")
    return neg / pos


def _fit(model: TinyPointNet, optimizer: torch.optim.Optimizer, points: np.ndarray,
         y: np.ndarray, steps: int, lr: float, pos_weight: float) -> None:
    x = torch.from_numpy(np.ascontiguousarray(points, dtype=np.float32))
    t = torch.from_numpy(np.ascontiguousarray(y, dtype=np.float32))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([float(pos_weight)], dtype=torch.float32))
    model.train()
    for _ in range(steps):
        optimizer.zero_grad()
        loss = loss_fn(model(x), t)
        loss.backward()
        optimizer.step()


def _predict(model: TinyPointNet, points: np.ndarray) -> np.ndarray:
    model.eval()
    with torch.no_grad():
        logits = model(torch.from_numpy(np.ascontiguousarray(points, dtype=np.float32)))
        return torch.sigmoid(logits).cpu().numpy().astype(np.float64)


def run_cv(points: np.ndarray, y: np.ndarray, val_folds, *, steps: int = 300,
           lr: float = 1e-2, hidden: int = 32, seed: int = 43, cap: int = 6000,
           carry_state: bool = False) -> dict:
    """组折 OOF 训练。val_folds 为各折验证集下标（须互斥）。

    carry_state=True 复现旧缺陷（模型/Adam 跨折延续），仅用于对照，禁止当正式结果。
    返回 {'oof': (S,), 'folds': [...], 'carry_state': bool}。
    """
    y = np.asarray(y)
    n = len(y)
    oof = np.full(n, np.nan, dtype=np.float64)
    model = optimizer = None
    model_seen = np.zeros(n, dtype=int)  # 当前模型累计训练过的样本（模型重建即清零）
    fold_records = []
    for k, val in enumerate(val_folds):
        val = np.asarray(val, dtype=int)
        train = np.setdiff1d(np.arange(n), val)
        sub = train[sample_subset(y[train], cap=cap, seed=seed + k)]
        weight = pos_weight_from(y[sub])
        reused = model is not None and carry_state
        if not reused:
            model = init_model(hidden=hidden, seed=seed)  # 缺陷 1 修复点：每折全新
            optimizer = torch.optim.Adam(model.parameters(), lr=lr)
            model_seen[:] = 0
        prev_seen = int((model_seen[val] > 0).sum())  # 当前模型此前是否已见折 k 验证样本（污染计数）
        init_hash = state_hash(model)
        _fit(model, optimizer, points[sub], y[sub], steps, lr, weight)
        oof[val] = _predict(model, points[val])
        model_seen[sub] += 1
        fold_records.append({
            "fold": k, "n_train": int(len(train)), "n_sampled": int(len(sub)),
            "pos_weight": weight, "model_reused": bool(reused),
            "init_hash": init_hash, "final_hash": state_hash(model),
            "prev_seen_in_val": prev_seen,
        })
    if np.isnan(oof).any():
        raise ValueError("折划分未覆盖全部样本，OOF 不完整")
    return {"oof": oof, "folds": fold_records, "carry_state": bool(carry_state)}


def oof_metrics(y: np.ndarray, scores: np.ndarray, thr: float = 0.5) -> dict:
    y = np.asarray(y)
    pred = (np.asarray(scores) >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
    }


def synthetic_clouds(n_pos: int, n_neg: int, *, points_per: int = 64, seed: int = 7):
    """合成点云：正例 x∈[1,2]，负例 x∈[-2,-1]（可分）；不模拟真实传感器。"""
    rng = np.random.RandomState(seed)
    pos = rng.uniform(1.0, 2.0, size=(n_pos, points_per, 3)).astype(np.float32)
    neg = rng.uniform(-2.0, -1.0, size=(n_neg, points_per, 3)).astype(np.float32)
    x = np.concatenate([pos, neg])
    yy = np.concatenate([np.ones(n_pos, dtype=int), np.zeros(n_neg, dtype=int)])
    perm = rng.permutation(len(yy))
    return x[perm], yy[perm]


def _folds(n: int, k: int = 4):
    return [np.arange(i, n, k) for i in range(k)]


def main() -> None:
    report = {}
    x, yy = synthetic_clouds(40, 200, seed=7)
    fixed = run_cv(x, yy, _folds(len(yy)), steps=300, lr=2e-2)
    report["separable_fixed"] = {
        "n": int(len(yy)), "oof": oof_metrics(yy, fixed["oof"]),
        "pos_weight_by_fold": [round(f["pos_weight"], 4) for f in fixed["folds"]],
        "prev_seen_in_val": [f["prev_seen_in_val"] for f in fixed["folds"]],
        "global_ratio_not_used": round(float((yy == 0).sum()) / float((yy == 1).sum()), 4),
    }
    x2, y2 = synthetic_clouds(32, 96, seed=11)
    y2 = np.random.RandomState(11).permutation(y2)  # 随机标签：无真实可分性
    leaky = run_cv(x2, y2, _folds(len(y2)), steps=400, lr=2e-2, carry_state=True)
    clean = run_cv(x2, y2, _folds(len(y2)), steps=400, lr=2e-2)
    report["random_label_contamination"] = {
        "n": int(len(y2)),
        "leaky_carry_state": {
            "oof": oof_metrics(y2, leaky["oof"]),
            "prev_seen_in_val": [f["prev_seen_in_val"] for f in leaky["folds"]],
        },
        "fixed": {
            "oof": oof_metrics(y2, clean["oof"]),
            "prev_seen_in_val": [f["prev_seen_in_val"] for f in clean["folds"]],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
