# -*- coding: utf-8 -*-
"""frame_feature.py — 把一帧 (N,4) 点云压成定长 feature vector.

刻意用 NumPy 而不是 PointNet, 理由：
1. 训练 RF 必须定长
2. 特征代表「形状 + 分布」, 神经网络会自己学, 但 RF 要我们喂它
3. 所有特征都是 permutation-invariant (对点的顺序不敏感) — 公平对待任何采集顺序

Feature vector (50 dim), 分块:
  [0..4]    基础： n_pts, min_pts, max_pts, mean_intensity, std_intensity
  [5..13]   位置分布： x/y/z 的 (10, 50, 90) 分位
  [14..22]  高度带： z < 0.3 / 0.3..0.6 / 0.6..0.9 / 0.9..1.2 / 1.2..1.5 / 1.5..1.8 / 1.8..2.2 / 2.2..2.6 / >2.6 比例
  [23..31]  形心+协差： 3 vec mean + 6 upper-tri cov
  [32..40]  PCA: eigvals (desc) + eigvals_ratio + PCA 主轴三向量 dot 单位 z 的 cos
  [41..50]  形状： 径向 (xy) spread, 高度 range, z_tilt_score, 直立度 (bonding), intensity 10/50/90 分位 + PCA eigenvalue 第二第三 ratio
"""
import numpy as np

FEAT_DIM = 51
FEAT_NAMES = [
    "n_pts", "min_pts", "max_pts", "i_mean", "i_std",
    "x_p10", "x_p50", "x_p90", "y_p10", "y_p50", "y_p90",
    "z_p10", "z_p50", "z_p90",
    "zb_03", "zb_036", "zb_069", "zb_0912", "zb_1215",
    "zb_1518", "zb_1822", "zb_2226", "zb_26up",
    "cx", "cy", "cz", "cov_xx", "cov_xy", "cov_xz",
    "cov_yy", "cov_yz", "cov_zz",
    "pca_ev0", "pca_ev1", "pca_ev2", "pca_r01", "pca_r12",
    "pca_axis0_z", "pca_axis1_z", "pca_axis2_z",
    "r_xy_spread", "z_range", "z_tilt_log",
    "upright_score", "i_p10", "i_p50", "i_p90",
    "pca_r02", "pca_shape_spread",
    "n_pts_ratio_near", "z_max",
]
assert len(FEAT_NAMES) == FEAT_DIM


def extract_features(xyz_i):
    """xyz_i: (N,4) [x, y, z, intensity] → (FEAT_DIM,) float32"""
    out = np.zeros(FEAT_DIM, dtype=np.float32)
    n = len(xyz_i)
    if n < 10:
        return out
    xyz = xyz_i[:, :3]
    i_v = xyz_i[:, 3]

    # ---- [0..4] 基础 ----
    out[0] = float(n)
    out[1] = 10.0
    out[2] = float(max(n, 2000))
    out[3] = float(i_v.mean()) if n else 0.0
    out[4] = float(i_v.std()) if n else 0.0

    # ---- [5..13] 位置分位 ----
    p = [10, 50, 90]
    x_p = np.percentile(xyz[:, 0], p)
    y_p = np.percentile(xyz[:, 1], p)
    z_p = np.percentile(xyz[:, 2], p)
    out[5:8] = x_p
    out[8:11] = y_p
    out[11:14] = z_p

    # ---- [14..22] 高度带 ----
    z = xyz[:, 2]
    bins = [(-1, 0.3), (0.3, 0.6), (0.6, 0.9), (0.9, 1.2),
              (1.2, 1.5), (1.5, 1.8), (1.8, 2.2), (2.2, 2.6),
              (2.6, 1e9)]
    for k, (lo, hi) in enumerate(bins):
        out[14 + k] = float(((z >= lo) & (z < hi)).mean())

    # ---- [23..31] 形心 + cov (6 元） ----
    c = xyz.mean(axis=0)
    out[23:26] = c
    cov = np.cov((xyz - c).T) if n > 3 else np.zeros((3, 3))
    out[26] = float(cov[0, 0])
    out[27] = float(cov[0, 1])
    out[28] = float(cov[0, 2])
    out[29] = float(cov[1, 1])
    out[30] = float(cov[1, 2])
    out[31] = float(cov[2, 2])

    # ---- [32..40] PCA ----
    try:
        w, V = np.linalg.eigh(cov)
        w = np.sort(w)[:: -1]  # desc
        # 取 PCA 主轴跟 (0,0,1) 的夹角绝对值
        idx = np.argsort(-w)
        V = V[:, idx]
        ev = np.sort(w)[:: -1]
        out[32] = float(ev[0])
        out[33] = float(ev[1])
        out[34] = float(ev[2])
        out[35] = float(ev[0] / max(ev[1], 1e-9))
        out[36] = float(ev[1] / max(ev[2], 1e-9))
        out[37] = float(abs(V[2, 0]))
        out[38] = float(abs(V[2, 1]))
        out[39] = float(abs(V[2, 2]))
        out[40] = float(ev[0] / max(ev[2], 1e-9))
    except np.linalg.LinAlgError:
        pass

    # ---- [41..50] 形状 ----
    out[41] = float(np.std(np.sqrt(xyz[:, 0] ** 2 + xyz[:, 1] ** 2)))
    out[42] = float(z_p[2] - z_p[0])  # z range p90-p10
    if out[42] > 0.01:
        out[43] = float(np.log10(abs(out[42])))
    # 直立度： z 高 (1.2+) 点数 / z 中 (0.4..1.2) 点数
    up = float(((z > 1.2) & (z < 2.2)).sum())
    mid = float(((z >= 0.4) & (z < 1.2)).sum())
    if mid > 0:
        out[44] = float(up / max(mid, 1))
    # 强度分位
    i_p = np.percentile(i_v, p)
    out[45] = float(i_p[0])
    out[46] = float(i_p[1])
    out[47] = float(i_p[2])
    # 比例： 距雷达 < 3m / 总
    r = np.linalg.norm(xyz[:, :2], axis=1)
    out[48] = float((r < 3.0).mean())
    out[49] = float(z_p[2])
    # PCA 主轴扩散度
    out[50] = float(ev[0] + ev[1] + ev[2])
    return out


# 给 RF 用： X_train (M, FEAT_DIM) 大矩阵的快速构建入口
def build_matrix(gen, max_frames=None):
    """gen 是 iter (xyz_i, label, path). 返回 (X, y, names)"""
    X = []
    y = []
    names = []
    for k, (xyz_i, lab, path) in enumerate(gen):
        if max_frames is not None and k >= max_frames:
            break
        X.append(extract_features(xyz_i))
        y.append(lab)
        names.append(path)
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int32), names
