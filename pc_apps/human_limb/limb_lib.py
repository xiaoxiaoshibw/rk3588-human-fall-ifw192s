# -*- coding: utf-8 -*-
"""human_limb limb_lib — 单帧四肢/躯干关键点识别（纯 NumPy）

输入：单帧 xyz 点云 (N,3) float32（雷达系：x 前、y 左、z 上，单位米）
输出（字典）：
  detected   — 是否找到人体
  reason     — 未检测原因（便于开发者诊断）
  keypoints  — 17 个关键点 dict（name → (x,y,z) 或 None）
  bones      — list of (name_a, name_b)，对应前后骨架
  torso_tilt_deg — 躯干与地面法线夹角（弯腰角度）
  person_track   — 人的水平轨迹/pose 量化（用于连续帧的 bend 检测）

算法骨架（最简版）：
  1. 粗去地：平面 z = a*x + b*y + c 用 RANSAC 拟合地面（只考虑近处 z<0.5 的点），
     把「离地 < 5 cm」的点丢掉
  2. 离地 ROI：点投影到 xy，按 0.3 m 网格算密度峰，取半径 1.2 m 内高密度区域为人
  3. 人体 bbox: 取靠近峰的点，z>ground+0.05, z<ground+2.2
  4. 主躯干 PCA：取 z 在 ground+[0.4, 1.6] 的点做 PCA，第一主成分即躯干方向，
     跟地面法线夹角即 bend 角
  5. 四肢提取（根据 torso-tilt 分两个分支）：
     bend<20：直立。把点分成上躯干(z>1.2)/下躯干(z<0.8)，各在 xy 上找两侧 extrema
     bend>=20：弯曲。人更可能水平摆动，按 PCA 主轴把点分成前臂/后臂
  6. 跳过：单帧返回，不做跟踪（HR-07 v1 简化）
"""
from collections import defaultdict
import numpy as np

BODY_KP_ORDER = (
    "head", "neck", "shoulder_l", "shoulder_r", "elbow_l", "elbow_r",
    "wrist_l", "wrist_r", "spine_mid", "hip_l", "hip_r",
    "knee_l", "knee_r", "ankle_l", "ankle_r",
)

# 骨架连接 —— 没匹配到的 limb 不会出现
BONES = [
    ("head", "neck"),
    ("neck", "shoulder_l"), ("neck", "shoulder_r"),
    ("shoulder_l", "elbow_l"), ("shoulder_r", "elbow_r"),
    ("elbow_l", "wrist_l"), ("elbow_r", "wrist_r"),
    ("neck", "spine_mid"),
    ("spine_mid", "hip_l"), ("spine_mid", "hip_r"),
    ("hip_l", "knee_l"), ("hip_r", "knee_r"),
    ("knee_l", "ankle_l"), ("knee_r", "ankle_r"),
]


# ---------------------------------------------------------------------------
# 粗略地面拟合：RANSAC
# ---------------------------------------------------------------------------

def fit_ground_ransac(xyz, n_iter=60, dist_thr=0.06, seed_min_pts=300,
                       n_max_tilt_deg=10.0):
    """RANSAC 拟合地面，但**强制假设雷达本身已水平安装**——
    地面法线预设为 (0,0,1)，只用 RANSAC 求高度 z0。等价于在室内 z 直方图找最强峰。

    这样就不可能被斜墙/家具骗成"45° 地面"。

    返回 (n, c)，n 为 (0,0,1)，c 是某地面点（z=z0，xy 任意取原点）。
    """
    if xyz.shape[0] < seed_min_pts:
        return None, None
    # 只信近处（如果雷达向外看，地面 z 大致 < 1m）+ 高度直方图
    rng = np.random.default_rng(0)
    near = xyz[(xyz[:, 2] < 1.5) & (xyz[:, 2] > -1.5)]
    if len(near) < seed_min_pts // 4:
        return None, None
    # 直方图 + 局部平滑： 选择累计最高 0.05m 窗所在 z
    counts, edges = np.histogram(near[:, 2], bins=100, range=(-1.5, 1.5))
    # 平滑 (3-bin boxcar)
    from numpy import convolve, ones
    smooth = convolve(counts, ones(3) / 3, mode="same")
    peak_i = int(np.argmax(smooth))
    z0 = float(0.5 * (edges[peak_i] + edges[peak_i + 1]))
    # 验证： |z - z0| < 0.05 的点应该够多
    enough = int((np.abs(xyz[:, 2] - z0) < 0.05).sum())
    if enough < seed_min_pts:
        return None, None
    return np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, z0])


def ground_height_lut_const_z(z0):
    """平地 z=z0 模型： ground_z(x,y) = z0 常数。"""
    return lambda q_xy: np.full(q_xy.shape[0], z0)


def ground_height_lut(xyz, n, c, cell=0.5, roi_r=12.0):
    """把低于 n·(p-c)=0 平面 < 5cm 的点丢掉，返回 lut 函数 z_ground(x,y) 查表高度（粗）
    — v1 用全局平面就够，不做二次拟合"""
    return lambda q_xy: c[2] + n[0] * (q_xy[..., 0] - c[0]) + n[1] * (q_xy[..., 1] - c[1])


# ---------------------------------------------------------------------------
# 人形 ROI 提取：xy 网格密度峰 + 圆柱抠点
# ---------------------------------------------------------------------------

def _person_score_at(xyz, ground_z_fn, cx, cy, radius=0.55):
    """评估 (cx, cy) 半径 radius 圆柱里的点有多像「直立人柱」。

    评分： min(low, mid, high) 点数 × max(low, mid, high)
        — 三段(null/躯干/上肢)都有点才算人形。
    返回 (score, mask) — mask 是 xyz 里落在圆柱内的点索引。
    """
    d2 = (xyz[:, 0] - cx) ** 2 + (xyz[:, 1] - cy) ** 2
    mask = d2 < radius * radius
    if mask.sum() < 30:
        return 0, mask
    zr = xyz[mask, 2] - ground_z_fn(xyz[mask, :2])
    inb = (zr > 0.05) & (zr < 2.3)
    if inb.sum() < 30:
        return 0, mask
    z_in = zr[inb]
    low = ((z_in > 0.2) & (z_in < 0.8)).sum()
    mid = ((z_in >= 0.8) & (z_in < 1.4)).sum()
    high = ((z_in >= 1.4) & (z_in < 2.2)).sum()
    score = int(min(low, mid, high)) * int(max(low, mid, high))
    return score, mask


def find_person_roi(xyz, ground_z_fn, cell=0.3, hh_min=0.5, hh_max=2.2, radius=0.7,
                    lock_xy=None, lock_radius=2.5):
    """选人形 ROI： 在 lock 圆内扫所有 0.3m 网格点， 用人形评分挑最高峰。

    lock_radius 默认 2.5m——允许人在 lock 周围 2.5m 内走动。
    每帧独立全局选， 不做硬绑定（防锁死柜）。
    """
    """从地面滤后点里**找单一峰**，只取峰周围 radius 内的点。

    v3 思路： 不再用 N 格几何中心（会跨物体）。
    - lock_xy 提供时： 在 lock 圆内找最密单格，锁到那一格
    - 否则： 全局最密单格
    - ROI 是「峰中心 + radius 圆」，目标是一团而不是一片
    """
    if xyz.shape[0] < 200:
        return None, "too_few_points", None
    # 扫候选圆心： 0.3 m 网格或 lock 周围
    if lock_xy is not None:
        # 在 lock ±lock_radius 内扫
        x_lo, x_hi = lock_xy[0] - lock_radius, lock_xy[0] + lock_radius
        y_lo, y_hi = lock_xy[1] - lock_radius, lock_xy[1] + lock_radius
    else:
        x_lo = max(0.5, float(np.percentile(xyz[:, 0], 1)))
        x_hi = min(8.0, float(np.percentile(xyz[:, 0], 99)))
        y_lo = max(-4.0, float(np.percentile(xyz[:, 1], 1)))
        y_hi = min(4.0, float(np.percentile(xyz[:, 1], 99)))
    best = None
    step = cell
    cy = y_lo
    while cy <= y_hi:
        cx = x_lo
        while cx <= x_hi:
            score, mask = _person_score_at(xyz, ground_z_fn, cx, cy, radius=0.55)
            if score > 0 and (best is None or score > best[0]):
                best = (score, cx, cy, mask)
            cx += step
        cy += step
    if best is None or best[0] < 1000:
        return None, "no_person_peak", None
    _, cx, cy, mask = best
    idx = np.nonzero(mask)[0]
    return idx, None, (float(cx), float(cy))


# ---------------------------------------------------------------------------
# 躯干 PCA + bend 角
# ---------------------------------------------------------------------------

def torso_pca(pts, ground_z_fn):
    """对身体带 [0.4, 1.6] m 做 PCA。

    返回 (centroid, axis, bend_deg)；若 PCA 形状接近球形（最大/次大特征值比 < 1.8），
    说明躯干没有清晰方向，返回 None（这点会被上层当「不可信」处理，不再返回乱轴）。
    """
    if len(pts) < 30:
        return None, None, None
    h = pts[:, 2] - ground_z_fn(pts[:, :2])
    inb = (h > 0.4) & (h < 1.6)
    if inb.sum() < 20:
        return None, None, None
    t = pts[inb]
    hub = t[:, :2].mean(axis=0)
    d2 = ((t[:, :2] - hub) ** 2).sum(axis=1)
    core = t[d2 < 0.3 * 0.3]
    if len(core) < 20:
        core = t
    t = core
    c = t.mean(axis=0)
    cov = np.cov((t - c).T)
    w, V = np.linalg.eigh(cov)
    if w[-1] < 1e-4 or w[-2] < 1e-6 or w[-1] / max(w[-2], 1e-9) < 1.8:
        return None, None, None  # 球形 → 方向不可信
    axis = V[:, -1]
    # PCA 主轴有 ± 号歧义（同一条直线），不要强行翻 +Z。
    # tilt 报"轴向量与垂直的锐角"， 0..90 度区间， 永远 ge 0
    zenith = float(np.degrees(np.arccos(np.clip(abs(axis[2]), 0, 1))))
    return c, axis, zenith


# ---------------------------------------------------------------------------
# 四肢投票器（extrema）
# ---------------------------------------------------------------------------

def _extrema_in_band(pts_xy_hz, hz_range, n_best=2):
    """从带内点 xy 找「两两最远」的 extrema 点。返回 [(x, y, z_top)] 长度 0..2"""
    h = pts_xy_hz[:, 2]
    inb = (h >= hz_range[0]) & (h < hz_range[1])
    if inb.sum() < 10:
        return []
    p = pts_xy_hz[inb]
    if len(p) > 4000:
        # 下采样，留表现好的
        dq = p[:, 0] * 1.2345 + p[:, 1] * 5.4321
        thr = np.percentile(dq, 200 * 100.0 / len(p))
        p = p[dq <= thr]
    if len(p) < 10:
        return []
    xy = p[:, :2]
    # 取前 20 个「离质心最远」的点
    centre = xy.mean(axis=0)
    d = np.linalg.norm(xy - centre, axis=1)
    far = np.argsort(-d)[: max(20, len(p) // 5)]
    cands = p[far]
    # 让两两距离最大的两点 = extremum pair
    dist2 = ((cands[:, None, :2] - cands[None, :, :2]) ** 2).sum(-1)
    i, j = np.unravel_index(np.argmax(dist2), dist2.shape)
    out = []
    for k in (i, j):
        pt = cands[k]
        out.append((float(pt[0]), float(pt[1]), float(pt[2])))
    # 去重
    if len(out) == 2 and (out[0][0]-out[1][0])**2 + (out[0][1]-out[1][1])**2 < 0.04:
        out = out[: 1]
    return out


def _pick_lr(two_pts, centroid_xy):
    """把两个候选点上左右标签（相对人体朝向决定的「左右」）。
    v1: 简单用 y 值正负当 LR（雷达前向为 +x，+y=left）"""
    if not two_pts:
        return None, None
    if len(two_pts) == 1:
        # 根据 y 决定是左还是右
        return (two_pts[0], None) if two_pts[0][1] > centroid_xy[1] else (None, two_pts[0])
    a, b = two_pts
    return (a, b) if a[1] >= b[1] else (b, a)


# ---------------------------------------------------------------------------
# 时序滤波 / 跟踪
# ---------------------------------------------------------------------------

class LimbTracker:
    """跨帧 EMA 平滑 + 弯腰事件提取。
    alpha: EMA 参数 (0..1)。越小越平，越大越灵敏。0.6 ≈ 时间常数 ~1.5 帧 ≈ 0.15 s。
    """

    STATIC_FRAMES = 12   # N 帧质心漂移 < 0.08 m → 判定锁定静态对象， 重置

    def __init__(self, alpha=0.3, lock_seed=None):
        self.alpha = alpha
        self.ema_tilt = None
        self.ema_centroid = None
        self.ema_axis = None
        self.roi_xy = lock_seed  # 初始 ROI (x, y)
        self.lock_seed = lock_seed  # 用户 pin 的固定 ROI（ 不会被覆盖）
        self.last_kp = {}
        self.bend_history = []
        self._static_log = []

    def _check_static(self, frame_i, centroid):
        """判断质心是否长时间不动（锁定家具）"""
        if centroid is None:
            return False
        self._static_log.append((frame_i, (float(centroid[0]), float(centroid[1]))))
        if len(self._static_log) > self.STATIC_FRAMES:
            self._static_log.pop(0)
        if len(self._static_log) < self.STATIC_FRAMES:
            return False
        c0 = self._static_log[0][1]
        for _, c in self._static_log[1:]:
            d = ((c[0] - c0[0]) ** 2 + (c[1] - c0[1]) ** 2) ** 0.5
            if d > 0.08:
                return False
        return True  # 全部都在 0.08 m 内 → 静止

    def reset(self):
        """清锁——给 detect_frame 一个 None prev， 强制重新全局搜。
        但**不清 lock_seed**（用户 pin 不允许被覆盖）。"""
        self.roi_xy = self.lock_seed   # 清锁后回到 seed (如果有)
        self._static_log = []

    def _ema(self, prev, cur, alpha=None):
        a = self.alpha if alpha is None else alpha
        if prev is None:
            return cur
        return (1 - a) * prev + a * cur

    def smooth(self, raw):
        """输入 detect_frame 原始输出，返回 smoothed 输出"""
        out = {
            "detected": raw["detected"], "reason": raw["reason"],
            "keypoints": None, "bones": raw.get("bones", BONES),
            "torso_tilt_deg": None, "torso_tilt_raw_deg": raw.get("torso_tilt_deg"),
            "torso_axis": None, "torso_centroid": None,
            "roi_xy": None,
        }
        if not raw["detected"]:
            # 丢了：不清历史， 让 ROI 吸收一下跨帧空窗
            out["torso_tilt_deg"] = self.ema_tilt
            out["torso_axis"] = (None if self.ema_axis is None
                                  else [float(v) for v in self.ema_axis])
            out["torso_centroid"] = (None if self.ema_centroid is None
                                      else [float(v) for v in self.ema_centroid])
            out["keypoints"] = self.last_kp
            out["roi_xy"] = self.roi_xy
            return out

        # EMA 更新
        raw_tilt = float(raw["torso_tilt_deg"])
        raw_axis = np.asarray(raw["torso_axis"], dtype=float)
        raw_centroid = np.asarray(raw["torso_centroid"], dtype=float)

        self.ema_tilt = self._ema(self.ema_tilt, raw_tilt)
        # axis 符号对齐 + 突变保护：
        # prev 与 cur 反号 → 翻转 cur
        # prev + cur 太接近 0 向量（几乎 180° 差别）→ 直接接受 cur（是真快速弯腰），不做 EMA
        if self.ema_axis is not None:
            dot = float(np.dot(self.ema_axis, raw_axis))
            if dot < 0:
                raw_axis = -raw_axis
            mixed = (1 - self.alpha) * self.ema_axis + self.alpha * raw_axis
            if np.linalg.norm(mixed) < 0.2:
                self.ema_axis = raw_axis
            else:
                self.ema_axis = mixed / np.linalg.norm(mixed)
        else:
            self.ema_axis = raw_axis / max(np.linalg.norm(raw_axis), 1e-9)
        self.ema_centroid = self._ema(self.ema_centroid, raw_centroid)

        # keypoints 只保留 torso + limb 的都不平滑 (四肢噪声大， 但物理上必须看到才行)
        # 为了 UI 稳定， wrist/ankle 用 0.5 alpha, torso 用 0.25
        smoothed_kp = {}
        for name, v in raw["keypoints"].items():
            if v is None:
                smoothed_kp[name] = self.last_kp.get(name)
                continue
            cur = np.asarray(v, dtype=float)
            prev_v = self.last_kp.get(name)
            if prev_v is None:
                smoothed_kp[name] = tuple(cur.tolist())
            else:
                alpha = 0.25 if "spine" in name or name in ("head", "neck", "hip_l", "hip_r") else 0.5
                sv = (1 - alpha) * np.asarray(prev_v, dtype=float) + alpha * cur
                smoothed_kp[name] = tuple(sv.tolist())
        self.last_kp = smoothed_kp

        # 从平滑后 axis 重算 tilt —— 不区分 ±，取与垂直的锐角（0..90°）
        z = abs(float(self.ema_axis[2])) if self.ema_axis is not None else 0.0
        smoothed_tilt = float(np.degrees(np.arccos(np.clip(z, 0, 1))))

        out["torso_tilt_deg"] = smoothed_tilt
        out["torso_axis"] = [float(v) for v in self.ema_axis]
        out["torso_centroid"] = [float(v) for v in self.ema_centroid]
        out["keypoints"] = smoothed_kp
        # lock_seed 是用户显式 pin 的， 永远不被覆盖；
        # 否则用 raw 给出的 ROI_xy（跨帧自适应）
        if self.lock_seed is not None:
            self.roi_xy = self.lock_seed
        else:
            self.roi_xy = raw.get("roi_xy") or self.roi_xy
        out["roi_xy"] = self.roi_xy
        self.bend_history.append(smoothed_tilt)
        return out


# ---------------------------------------------------------------------------
# 单帧主入口
# ---------------------------------------------------------------------------

def _bg_subtract(xyz_cur, xyz_prev, ground_z_fn, diff_thresh=0.30):
    """背景差分： 把 xyz_prev 的点删掉（它们在 xyz_cur 跟前差异 < diff_thresh 范围），
    只留「新出现/移动过」的点。

    实现： xyz_prev 用 0.3m xy 网格 + 0.3m z 网格 hash；xyz_cur 每个点查 prev 是否有近邻。
    返回布尔 mask (xyz_cur.shape[0],) True=动态点。
    """
    if xyz_prev is None or len(xyz_prev) < 200:
        return np.ones(len(xyz_cur), dtype=bool)
    key = lambda a, s: (
        (a[:, 0] / s).astype(np.int32),
        (a[:, 1] / s).astype(np.int32),
        (a[:, 2] / s).astype(np.int32),
    )
    cell = diff_thresh
    kp = key(xyz_prev, cell)
    prev_set = set(zip(kp[0], kp[1], kp[2]))
    kc = key(xyz_cur, cell)
    out = np.ones(len(xyz_cur), dtype=bool)
    for i in range(len(xyz_cur)):
        c = (kc[0][i], kc[1][i], kc[2][i])
        # 查 27 个相邻 cell
        found = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if (c[0]+dx, c[1]+dy, c[2]+dz) in prev_set:
                        found = True; break
                if found: break
            if found: break
        out[i] = not found  # 静态 → False （滤掉）
    return out


def detect_frame(xyz, prev=None):
    """单帧四肢检测主入口。

    xyz: (N,3) float32 点云。
    prev: 上一帧 detect 返回的 dict（用于：
        - roi_xy 跟踪 lock
        - 全身点云 prev_xyz 做背景差分）
    """
    out = {
        "detected": False, "reason": None,
        "keypoints": {k: None for k in BODY_KP_ORDER},
        "bones": BONES, "torso_tilt_deg": None,
        "torso_axis": None, "torso_centroid": None,
        "roi_xy": None,
        "xyz": xyz,   # 透传， 下一帧做 bg_subtract 用
    }
    if xyz is None or xyz.shape[0] < 200:
        out["reason"] = "empty_cloud"
        return out

    g_n, g_c = fit_ground_ransac(xyz)
    if g_n is None:
        out["reason"] = "no_ground"
        return out
    # 强制平地 z0 模式
    z0 = float(g_c[2])
    ground_z_fn = ground_height_lut_const_z(z0)

    # lock： 上一帧 roi 或用户 pin / ai_label hint（ 硬， 直接当圆心）
    lock = None
    lock_radius = 0.7
    if prev and prev.get("roi_xy"):
        lock = prev["roi_xy"]
    if isinstance(prev, dict) and prev.get("roi_r"):
        lock_radius = float(prev["roi_r"])
    if lock is not None:
        # 硬约束： 直接用 lock 当圆心抓圆柱内点
        d2 = (xyz[:, 0] - lock[0]) ** 2 + (xyz[:, 1] - lock[1]) ** 2
        sel = d2 < lock_radius * lock_radius
        h = xyz[:, 2] - ground_z_fn(xyz[:, :2])
        sel &= (h > 0.05) & (h < 2.3)
        if sel.sum() < 30:
            out["reason"] = "hard_lock_no_points"
            return out
        roi_idx = np.nonzero(sel)[0]
        roi_xy = lock
    else:
        roi_idx, err, roi_xy = find_person_roi(xyz, ground_z_fn, lock_xy=None)
        if roi_idx is None or len(roi_idx) < 30:
            out["reason"] = err or "roi_too_small"
            return out
    out["roi_xy"] = (float(roi_xy[0]), float(roi_xy[1]))
    person = xyz[roi_idx]
    gound_z = ground_z_fn(person[:, :2])
    h = person[:, 2] - gound_z  # 离地高度

    # 形状检验： 人形 ROI 高度 spread < 2.0m（弯腰 <1.2m，站立 <2.0m）；
    if len(person) < 30:
        out["reason"] = "roi_too_few_points"
        return out

    centroid, axis, bend_deg = torso_pca(person, ground_z_fn)
    if centroid is None:
        out["reason"] = "no_torso_pca"
        return out
    out["detected"] = True
    out["torso_tilt_deg"] = bend_deg
    out["torso_axis"] = [float(v) for v in axis]
    out["torso_centroid"] = [float(v) for v in centroid]

    # 躯干关键点（基于 torso PCA + 身高量）
    h_max = float(np.percentile(h, 99))
    h_min = float(np.percentile(h, 1))
    gound_at_origin = float(ground_z_fn(np.array([[0.0, 0.0]]))[0])
    spine_bot = centroid - axis * (h_max / 2.0)  # 大致骨盆处
    spine_top = centroid + axis * (h_max / 2.0)  # 大致颈部
    kps = out["keypoints"]
    kps["spine_mid"] = (float(centroid[0]), float(centroid[1]), float(centroid[2]))
    kps["neck"] = (float(spine_top[0]), float(spine_top[1]), float(spine_top[2]))
    kps["head"] = (float(spine_top[0]), float(spine_top[1]),
                    float(spine_top[2]) + 0.15)
    kps["hip_l"] = (float(spine_bot[0]), float(spine_bot[1]) + 0.10,
                     float(spine_bot[2]))
    kps["hip_r"] = (float(spine_bot[0]), float(spine_bot[1]) - 0.10,
                     float(spine_bot[2]))

    # 四肢
    body = np.column_stack([person[:, 0], person[:, 1], h])  # (x, y, height_above_ground)
    if bend_deg < 25:
        # 直立 —— 四肢在两侧
        arm_band = _extrema_in_band(body, (0.95, 1.55), n_best=2)
        leg_band = _extrema_in_band(body, (0.10, 0.55), n_best=2)
        wrist_l, wrist_r = _pick_lr(arm_band, centroid[:2])
        ankle_l, ankle_r = _pick_lr(leg_band, centroid[:2])
    else:
        # 弯腰： arms 在前向（PCA 主轴方向），腿在后向
        # 沿 axis 在 xy 上分解
        axis_xy = np.array([axis[0], axis[1], 0.0])
        norm = np.linalg.norm(axis_xy)
        if norm < 1e-3:
            axis_xy = np.array([1.0, 0.0, 0.0])
        else:
            axis_xy = axis_xy / norm
        # 投影点：relative to centroid.xy
        rel_xy = person[:, :2] - centroid[:2]
        proj = rel_xy @ axis_xy[:2]
        # 前 25%（沿 axis）是 head/arms，后 25%（反方向）是 legs
        far = np.percentile(proj, 90)
        near = np.percentile(proj, 10)
        arm_band = _extrema_in_band(
            body[(proj > far) & (h > 0.1)], (0.0, 1.6), n_best=2)
        leg_band = _extrema_in_band(
            body[(proj < near) & (h > 0.05)], (0.0, 0.6), n_best=2)
        wrist_l, wrist_r = _pick_lr(arm_band, centroid[:2])
        ankle_l, ankle_r = _pick_lr(leg_band, centroid[:2])

    # 填 wrist / elbow / shoulder / knee / ankle
    def fill_arm(w):
        if w is None or kps["neck"] is None:
            return
        w = np.array(w, dtype=float)
        shoulder = np.array(kps["neck"], dtype=float) + np.array([0, 0, -0.15])
        if abs(w[1] - kps["neck"][1]) > 0:
            # 把 shoulder 推到对应一侧
            shoulder[1] = kps["neck"][1] + (0.20 if w[1] > kps["neck"][1] else -0.20)
        elbow = shoulder + (w - shoulder) * 0.5
        # 保证顺序
        if w[1] > kps["neck"][1]:
            kps["shoulder_l"] = tuple(shoulder.tolist())
            kps["elbow_l"] = tuple(elbow.tolist())
            kps["wrist_l"] = tuple(w.tolist())
        else:
            kps["shoulder_r"] = tuple(shoulder.tolist())
            kps["elbow_r"] = tuple(elbow.tolist())
            kps["wrist_r"] = tuple(w.tolist())

    def fill_leg(a):
        if a is None:
            return
        a = np.array(a, dtype=float)
        hip = np.array([0, 0, kps["spine_mid"][2] - 0.30]) if kps["spine_mid"] else None
        if hip is None:
            return
        src = kps["hip_l"] if a[1] > kps["spine_mid"][1] else kps["hip_r"]
        hip = np.array(src, dtype=float) if src else None
        if hip is None:
            return
        knee = hip + (a - hip) * 0.5
        if a[1] > kps["spine_mid"][1]:
            kps["knee_l"] = tuple(knee.tolist())
            kps["ankle_l"] = tuple(a.tolist())
        else:
            kps["knee_r"] = tuple(knee.tolist())
            kps["ankle_r"] = tuple(a.tolist())

    fill_arm(wrist_l)
    fill_arm(wrist_r)
    fill_leg(ankle_l)
    fill_leg(ankle_r)
    return out
