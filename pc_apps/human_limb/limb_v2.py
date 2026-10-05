# -*- coding: utf-8 -*-
"""limb_v2 — vd_limb_pose_pilot 核心公式移植， 用我们 IFW192S 1988 线 LiDAR 帧结构。

比 limb_lib.py 强在:
1. **动态点判定** 用原生 (ring, theta, r) 通道而非 xyz 网格—— 同通道 r 突变 > 5cm
   就是动态； 静止家具每秒都以相同 channel 同样距离出现， 全被滤掉
2. **EuclideanClustering** 自写 union-find, 不装 PCL—— NumPy 就够
3. **PCA 主轴** 当成 facing + long 任意
4. **conf** 抄 vd 公式: `0.25*dyn_frac + 0.25*cluster_frac + 0.30*extent_score + 0.20*(z_max<2.6)`
5. **语义状态机** Standing / Bending / None 分帧定， 不要 PCA 裸 tilt

输入： .bin frames (28 B/pt, [x y z i ring_pad_t_pad])
输出： list[SemanticEvent] per frame
   {state, keypoints{head,torso,wrist_l,wrist_r,foot_l,foot_r}, conf, person_xy, bend_deg}
"""
from collections import defaultdict
import numpy as np

BODY_KP6 = ("head", "torso_mid", "wrist_l", "wrist_r", "foot_l", "foot_r")


# ---------------------------------------------------------------------------
# 1. 通道化动态点提取  —— 跟 vd 的"帧间 xyz 距离 >0.3 不同", 我们用 channel 分辨率
# ---------------------------------------------------------------------------

def chan_key(xyz_ir):
    """每点 → (ring, theta_idx) 整数通道。xyz_ir (N,6) = [x,y,z,intensity,ring_f,timestamp_f]
    返回 (ring_arr (int16), theta_deg_arr (float32))"""
    ring = xyz_ir[:, 4].astype(np.int32)          # ring 已被 cast 成 f32, 回来取整
    theta = np.degrees(np.arctan2(xyz_ir[:, 1], xyz_ir[:, 0]))  # -180..180
    return ring, theta


def dynamic_points(xyz_ir_cur, xyz_ir_prev, ring_res=1, theta_res_deg=0.5, dr_thresh=0.05):
    """矢量： 真实"动态"必须在 r-z 平面有物理位移， 通过 r channel 距离变化超过阈值。
    不同的是， 小噪声 （雷达 per-shot ±3cm) 不该算 dynamic—— 用 dr_thresh=0.10
    并**附加 z_thresh**: 同 channel r 一致 但 z 显著抬升 → 也算 dynamic （例如沙发上的人坐起）
    """
    if xyz_ir_prev is None or len(xyz_ir_prev) < 200:
        return np.ones(len(xyz_ir_cur), dtype=bool)
    from scipy.spatial import cKDTree
    ring_c, theta_c = chan_key(xyz_ir_cur)
    ring_p, theta_p = chan_key(xyz_ir_prev)
    r_cur = np.linalg.norm(xyz_ir_cur[:, :2], axis=1)
    r_prev = np.linalg.norm(xyz_ir_prev[:, :2], axis=1)
    z_cur = xyz_ir_cur[:, 2]
    z_prev = xyz_ir_prev[:, 2]
    pt_coords = np.column_stack([ring_p.astype(float),
                                   theta_p / max(theta_res_deg, 0.1)]).astype(float)
    tree = cKDTree(pt_coords)
    cur_coords = np.column_stack([ring_c.astype(float),
                                    theta_c / max(theta_res_deg, 0.1)]).astype(float)
    idx_lists = tree.query_ball_point(cur_coords, r=2.0)
    out = np.ones(len(xyz_ir_cur), dtype=bool)
    for i, il in enumerate(idx_lists):
        if not il:
            continue
        dr = np.abs(r_prev[il] - r_cur[i])
        dz = np.abs(z_prev[il] - z_cur[i])
        # 完全不动 （即 r 跟 z 都没变 5cm) = static
        if dr.min() < dr_thresh and dz.min() < 0.08:
            out[i] = False
    return out


# ---------------------------------------------------------------------------
# 2. 欧式聚类  —— union-find, DBSCAN-like 半径聚类
# ---------------------------------------------------------------------------

def euclidean_clusters(xyz, radius=0.45, min_pts=50):
    """返回 list[ ndarray (M,3) ] 子簇。 xyz (N,3)
    v2 实现： scipy.spatial.cKDTree 查询 + union-find, 不再格子扫描"""
    from scipy.spatial import cKDTree
    N = len(xyz)
    if N < min_pts:
        return []
    tree = cKDTree(xyz)
    parent = list(range(N))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    # query pairs: cKDTree.query_pairs 直接返回所有 r<radius 的对
    pairs = tree.query_pairs(radius)
    for a, b in pairs:
        union(a, b)
    clusters_dict = defaultdict(list)
    for i in range(N):
        clusters_dict[find(i)].append(i)
    out = []
    for inds in clusters_dict.values():
        if len(inds) >= min_pts:
            out.append(xyz[inds])
    return out


# ---------------------------------------------------------------------------
# 3. PCA 主轴 + 语义状态
# ---------------------------------------------------------------------------

def pca_axes(pts):
    """返回 (centroid, axes (3,3), eigvals desc), axes 是列向量主轴"""
    c = pts.mean(axis=0)
    cov = np.cov((pts - c).T)
    w, V = np.linalg.eigh(cov)
    i = np.argsort(-w)
    return c, V[:, i], w[i]


def torso_state(pts, ground_z_fn, prev_axis=None):
    """判定语义： stand / bend / none.

    返回 (state, axis, bend_deg, centroid)
    结构：
     - bend_deg = acos(abs(axis.z)) —— 主长轴跟垂直锐角 (0..90)
     - bend_deg < 20 → stand
     - 20..45 → lean （前倾）
     - 45..90 → bend （弯腰/倒下）
     - PCA 球形 → none
    """
    if len(pts) < 50:
        return "none", None, None, None
    c, V, w = pca_axes(pts)
    if w[0] < 1e-4 or (w[0] / max(w[1], 1e-9)) < 1.5:
        return "none", None, None, None  # 球形 → 不定
    axis = V[:, 0]
    # 轴对齐： 跟 prev 保持同向， 防 PCA 翻转
    if prev_axis is not None and np.dot(prev_axis, axis) < 0:
        axis = -axis
    # 报锐角
    zen = float(np.degrees(np.arccos(np.clip(abs(axis[2]), 0, 1))))
    if zen < 20:
        state = "stand"
    elif zen < 45:
        state = "lean"
    else:
        state = "bend"
    return state, axis, zen, c


# ---------------------------------------------------------------------------
# 4. 粗 6 关键点 (沿 PCA 主轴 + 副轴两向 extrema)
# ---------------------------------------------------------------------------

def guess_6pts(pts, axis_long, axis_face, centroid):
    """沿 long_axis 头/脚 + 沿 face_axis 左右手腕 → 6 个 keypoints"""
    if len(pts) < 30:
        return {k: None for k in BODY_KP6}
    def _t(v):
        return (float(v[0]), float(v[1]), float(v[2])) if v is not None else None
    proj_l = (pts - centroid) @ axis_long
    proj_f = (pts - centroid) @ axis_face
    thr_h = np.percentile(proj_l, 95)
    thr_f_pos = np.percentile(proj_l, 5)
    head_pts = pts[proj_l >= thr_h]
    foot_pts = pts[proj_l <= thr_f_pos]
    head = head_pts.mean(axis=0) if len(head_pts) else None
    if len(foot_pts) > 5:
        fs_proj = (foot_pts - centroid) @ axis_face
        fl_pts = foot_pts[fs_proj >= np.percentile(fs_proj, 70)]
        fr_pts = foot_pts[fs_proj <= np.percentile(fs_proj, 30)]
        foot_l = fl_pts.mean(axis=0) if len(fl_pts) else None
        foot_r = fr_pts.mean(axis=0) if len(fr_pts) else None
    else:
        foot_l = foot_r = None
    mid_band = pts[(proj_l > np.percentile(proj_l, 30)) & (proj_l < np.percentile(proj_l, 70))]
    if len(mid_band) > 10:
        mb_proj = (mid_band - centroid) @ axis_face
        wl = mid_band[mb_proj >= np.percentile(mb_proj, 85)]
        wr = mid_band[mb_proj <= np.percentile(mb_proj, 15)]
        wrist_l = wl.mean(axis=0) if len(wl) else None
        wrist_r = wr.mean(axis=0) if len(wr) else None
    else:
        wrist_l = wrist_r = None
    return {
        "head": _t(head),
        "torso_mid": _t(centroid),
        "wrist_l": _t(wrist_l),
        "wrist_r": _t(wrist_r),
        "foot_l": _t(foot_l),
        "foot_r": _t(foot_r),
    }


# ---------------------------------------------------------------------------
# 5. conf 公式 (vd-style)
# ---------------------------------------------------------------------------

def compute_conf(dyn_frac, cluster_frac, height_extent, n_mid, n_high):
    """vd 公式改数： 置信度 0.0..0.9"""
    conf_base = 0.10
    c_dyn = min(0.25, dyn_frac * 0.50)
    c_cls = min(0.25, cluster_frac * 0.50)
    c_ext = min(0.30, max(0.0, height_extent - 0.4) * 0.15)
    c_geo = 0.0
    if n_mid >= 30 and n_high >= 20:
        c_geo = 0.10
    return min(0.9, conf_base + c_dyn + c_cls + c_ext + c_geo)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def detect_frame_v2(xyz_ir, prev=None, ground_z_fn=None):
    """单帧 limb 检测。

    xyz_ir: (N, 6) [x,y,z,intensity,ring,timestamp], float32
    prev: 上一帧 detect 返回
    ground_z_fn: q_xy → z0 (每帧重新拟合）

    返回 dict
    """
    out = {
        "state": "none", "keypoints": {k: None for k in BODY_KP6},
        "bend_deg": None, "conf": 0.0, "person_xy": None, "reason": None,
    }
    if len(xyz_ir) < 200:
        out["reason"] = "empty_cloud"
        return out
    # 地面 （强制平地， 同 limb_lib)
    if ground_z_fn is None:
        zs = xyz_ir[(xyz_ir[:, 2] > -1.5) & (xyz_ir[:, 2] < 1.5), 2]
        if len(zs) < 300:
            out["reason"] = "no_ground"
            return out
        counts, edges = np.histogram(zs, bins=100, range=(-1.5, 1.5))
        smooth = np.convolve(counts, np.ones(3) / 3, mode="same")
        i = int(np.argmax(smooth))
        z0 = float(0.5 * (edges[i] + edges[i+1]))
        ground_z_fn = lambda q: np.full(q.shape[0], z0)

    # 1) 动态点抠出
    dyn_mask = dynamic_points(xyz_ir, prev["xyz_ir_prev"] if prev else None,
                               dr_thresh=0.06)
    dyn_n = int(dyn_mask.sum())
    if dyn_n < 100:
        out["reason"] = "no_motion"
        return out
    dyn = xyz_ir[dyn_mask, :3]
    out["dyn_frac"] = dyn_n / float(len(xyz_ir))

    # 2) 聚类
    clusters = euclidean_clusters(dyn, radius=0.45, min_pts=50)
    if not clusters:
        out["reason"] = "no_cluster"
        return out
    # 挑最大的像人的： 用 vd 评分 mid/high 高度部分
    best = None
    ground_z0 = float(ground_z_fn(np.array([[0.0, 0.0]]))[0])
    for cl in clusters:
        zr = cl[:, 2] - ground_z0
        n_mid = int(((zr >= 0.8) & (zr < 1.4)).sum())
        n_high = int(((zr >= 1.4) & (zr < 2.2)).sum())
        z_extent = float(zr.max() - zr.min())
        score = min(n_mid, n_high) * z_extent
        if best is None or score > best[0]:
            best = (score, cl, n_mid, n_high, z_extent)
    score, cl, n_mid, n_high, z_extent = best
    person = cl
    out["person_xy"] = (float(person[:, 0].mean()), float(person[:, 1].mean()))
    centroid_xy = np.array([person[:, 0].mean(), person[:, 1].mean()])
    out["cluster_frac"] = float(len(person)) / float(dyn_n)

    # 3) PCA 状态机
    state, axis, bend_deg, centroid = torso_state(person, ground_z_fn,
                                                     prev_axis=prev.get("axis") if prev else None)
    out["state"] = state
    out["bend_deg"] = float(bend_deg) if bend_deg is not None else None
    out["axis"] = [float(v) for v in axis] if axis is not None else None
    out["torso_centroid"] = [float(v) for v in centroid] if centroid is not None else None
    out["z_extent"] = float(z_extent)
    out["dyn_frac"] = float(out["dyn_frac"])
    out["cluster_frac"] = float(out["cluster_frac"])
    out["person_xy"] = (float(person[:, 0].mean()), float(person[:, 1].mean()))

    # 4) 6 keypoints
    if state != "none" and axis is not None:
        _, V, _w = pca_axes(person)
        axis_long = V[:, 0]  # 主长轴
        axis_face = V[:, 2]  # 最小方差方向 ~ 胸侧
        out["keypoints"] = guess_6pts(person, axis_long, axis_face, centroid)
    else:
        out["keypoints"] = {k: None for k in BODY_KP6}

    # 5) conf
    out["conf"] = float(compute_conf(out.get("dyn_frac", 0),
                                      out.get("cluster_frac", 0),
                                      z_extent, n_mid, n_high))
    # 透传
    out["xyz_ir_prev"] = xyz_ir
    # out["axis"] 已在 state 部分被赋值
    return out
