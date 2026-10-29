"""PLANE-01 R3：小目标（纸飞机）逐帧实时框定核心。

纯计算（stdlib + NumPy，无 scipy 依赖），不做 I/O 副作用：

- ``ray_cells``：ring/azimuth -> 原生 192x256 射线格；同一射线跨帧可直接比较。
- ``BackgroundModel``：逐射线“在线中位数”背景。只吃历史帧；每帧只更新本帧观测到的
  射线格（增量中位数 + 方向滑动平均），O(观测格数) 而不是 O(全格)；已确认目标覆盖的
  射线冻结，静止目标不会被背景吸收。
- ``foreground_mask``：两条独立判据——① 同射线距离比背景中位数明显变近；
  ② 与“同射线背景点”的 3D 距离超过容差（能抓到贴在地面/桌面上、距离几乎不变的新物体）。
- ``cluster_points``：3D 网格并查集单链接聚类。
- ``fit_obb``：PCA 有向包围盒（中心/三轴/半长）。
- ``PlaneTracker``：最近邻 + 速度预测关联；命中数或位移决定 tentative -> confirmed。
- ``camera_boxes``：相机侧 2D 检测（时域中值背景 + 帧差 + 连通域 + 短轨迹），
  只用于在视频上画绿框，不参与 3D 结论。

诚实口径：只做“几何框定”，不声称识别“这就是纸飞机”；目标语义由用户口头给出。
"""
import warnings

import numpy as np

RINGS = 192
COLS = 256
AZ_MIN_DEG = -60.0
AZ_MAX_DEG = 60.0
AZ_STEP_DEG = (AZ_MAX_DEG - AZ_MIN_DEG) / COLS
MIN_RANGE_M = 0.10

TAU_NOVELTY_M = 0.035
TAU_REL_M_PER_M = 0.008
RANGE_DROP_M = 0.12
CLUSTER_EPS_M = 0.09
MIN_CLUSTER_POINTS = 16
MAX_CLUSTER_EXTENT_M = 0.70
MAX_RANGE_M = 8.0
MIN_INTENSITY = 0.0
ALPHA_EMA = 0.06
GATE_EMA_M = 0.08


def ray_cells(xyz, ring):
    """把一帧点映射到原生 ring×azimuth 射线格；返回 (cell, ok)。"""
    pts = np.asarray(xyz, dtype=np.float64)
    rings = np.asarray(ring).astype(np.int64)
    if pts.ndim != 2 or pts.shape[1] != 3 or rings.shape != (len(pts),):
        raise ValueError("ray_cells 需要 (N,3) 点与 (N,) ring")
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    rng = np.sqrt(x * x + y * y + z * z)
    az = np.degrees(np.arctan2(y, x))
    col = np.rint((az - AZ_MIN_DEG) / AZ_STEP_DEG).astype(np.int64)
    ok = (rng > MIN_RANGE_M) & (rings >= 0) & (rings < RINGS) & (col >= 0) & (col < COLS)
    cell = np.where(ok, rings * COLS + np.clip(col, 0, COLS - 1), -1)
    return cell, ok


def cluster_points(points, eps=CLUSTER_EPS_M, min_points=MIN_CLUSTER_POINTS):
    """3D 网格并查集单链接聚类；返回按点数降序的索引数组列表。"""
    pts = np.asarray(points, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError("cluster_points 需要 (N,3) 点")
    if len(pts) == 0:
        return []
    cells = np.floor(pts / eps).astype(np.int64)
    ucell, inv = np.unique(cells, axis=0, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    lut = {tuple(int(v) for v in c): j for j, c in enumerate(ucell.tolist())}
    parent = list(range(len(ucell)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for j, c in enumerate(ucell.tolist()):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    nb = lut.get((c[0] + dx, c[1] + dy, c[2] + dz))
                    if nb is not None:
                        ra, rb = find(j), find(nb)
                        if ra != rb:
                            parent[rb] = ra
    root = np.array([find(j) for j in range(len(ucell))], dtype=np.int64)
    comp = root[inv]
    out = []
    for label in np.unique(comp):
        sel = np.flatnonzero(comp == label)
        if len(sel) >= min_points:
            out.append(sel)
    out.sort(key=lambda idx: (-len(idx), int(idx[0])))
    return out


def fit_obb(points, pad=0.02, min_half=0.03):
    """PCA 有向包围盒：返回 center / axes(3x3 行向量) / half(3) / extent(3)。

    包围盒中心取“投影区间中点”而不是点均值：点集偏一侧（拖影尾巴）时盒子仍能贴紧。
    """
    pts = np.asarray(points, dtype=np.float64)
    if len(pts) == 0:
        raise ValueError("空点集无法拟合包围盒")
    mean = pts.mean(axis=0)
    if len(pts) < 3:
        half = np.full(3, max(min_half, pad))
        return dict(center=mean, axes=np.eye(3), half=half, extent=2 * half)
    centered = pts - mean
    cov = centered.T @ centered / max(len(pts) - 1, 1)
    vals, vecs = np.linalg.eigh(cov)
    axes = vecs[:, np.argsort(vals)[::-1]].T
    if np.linalg.det(axes) < 0:
        axes[2] = -axes[2]
    for k in range(3):
        if axes[k][int(np.argmax(np.abs(axes[k])))] < 0:
            axes[k] = -axes[k]
    proj = centered @ axes.T
    lo = proj.min(axis=0)
    hi = proj.max(axis=0)
    center = mean + ((lo + hi) / 2.0) @ axes
    half = np.maximum((hi - lo) / 2.0 + pad, min_half)
    return dict(center=center, axes=axes, half=half, extent=2 * half)


class BackgroundModel:
    """逐射线背景：用前 ``frames`` 帧做一次“背景建立”，之后冻结。

    为什么不是逐帧中位数：本段每帧 3.7 万有效点，逐格 31 帧中位数实测 245 ms/帧，
    实时性不够；而“启动窗口一次建背景”只需一次 ~30 ms，之后每帧 O(观测点)。
    本段目标在第 24 帧才出现（前 2.4 s 无目标），启动窗口不丢目标。
    真实长时场景需要周期性重估背景——本页不声称支持。

    背景点 = 该射线方向的单位向量均值 × 该射线距离中位数；中位数对“启动窗口里的
    零回波/偶发点”稳健，方向均值只需累加。
    """

    def __init__(self, rings=RINGS, cols=COLS, frames=21):
        if int(frames) < 3:
            raise ValueError("背景窗口至少 3 帧")
        self.rings, self.cols, self.frames = int(rings), int(cols), int(frames)
        size = self.rings * self.cols
        self._hist = np.full((self.frames, size), np.nan, dtype=np.float32)
        self._dir = np.zeros((size, 3), dtype=np.float64)
        self._dir_n = np.zeros(size, dtype=np.float64)
        self.range_map = np.full(size, np.nan, dtype=np.float64)
        self.points_map = np.full((size, 3), np.nan, dtype=np.float64)
        self._n = 0
        self.ready = False

    @property
    def seen(self):
        return self._n

    def observe(self, cell, ok, xyz):
        """积累一帧启动观测；窗口满后自动 finalize。"""
        if self.ready:
            return
        slot = self._n % self.frames
        self._hist[slot, :] = np.nan
        sel = np.flatnonzero(ok)
        if len(sel):
            pts = np.asarray(xyz, dtype=np.float64)[sel]
            cells = np.asarray(cell)[sel]
            rng = np.sqrt((pts * pts).sum(axis=1))
            order = np.argsort(rng, kind="stable")
            cells, rng, pts = cells[order], rng[order], pts[order]
            first = np.ones(len(cells), dtype=bool)
            first[1:] = cells[1:] != cells[:-1]
            cells, rng, pts = cells[first], rng[first], pts[first]
            self._hist[slot, cells] = rng
            np.add.at(self._dir, cells, pts / rng[:, None])
            np.add.at(self._dir_n, cells, 1.0)
        self._n += 1
        if self._n >= self.frames:
            self.finalize()

    def finalize(self):
        """计算背景距离/坐标中位数（只在启动窗口结束时算一次）。"""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(self._hist, axis=0)
        known = np.isfinite(med) & (self._dir_n > 0)
        d = np.zeros_like(self._dir)
        d[known] = self._dir[known] / self._dir_n[known][:, None]
        norm = np.sqrt((d * d).sum(axis=1))
        norm[norm == 0] = 1.0
        d = d / norm[:, None]
        self.range_map[:] = np.where(known, med, np.nan)
        self.points_map[:] = np.where(known[:, None], d * np.where(known, med, 0.0)[:, None], np.nan)
        pts = self.points_map[known]
        self._novelty = _NoveltyIndex(pts)
        self.ready = True
        return int(known.sum())

    def novel_mask(self, points, tau=TAU_NOVELTY_M):
        """背景解释不了的点（3D 上 tau 内没有背景点）。"""
        return self._novelty.novel(points, tau)


class _NoveltyIndex:
    """背景点云的 3D 近邻索引：优先 scipy KD 树，没有 scipy 时退化为体素哈希。"""

    def __init__(self, points, voxel=0.05):
        self.points = np.asarray(points, dtype=np.float64)
        self.voxel = float(voxel)
        self._tree = None
        self._keys = None
        self._base = 2048
        self._off = 1024
        try:
            from scipy.spatial import cKDTree
            self._tree = cKDTree(self.points)
        except ImportError:
            cells = np.floor(self.points / self.voxel).astype(np.int64) + self._off
            self._keys = np.unique(_pack(cells, self._base))

    @property
    def kind(self):
        return "kdtree" if self._tree is not None else "voxel"

    def novel(self, points, tau):
        pts = np.asarray(points, dtype=np.float64)
        if not len(pts):
            return np.zeros(0, dtype=bool)
        if self._tree is not None:
            dist, _ = self._tree.query(pts, k=1, distance_upper_bound=float(tau) + 1e-9)
            return ~np.isfinite(dist)
        cells = np.floor(pts / self.voxel).astype(np.int64) + self._off
        hit = np.zeros(len(pts), dtype=bool)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    q = _pack(cells + np.array([dx, dy, dz]), self._base)
                    idx = np.searchsorted(self._keys, q)
                    idx = np.clip(idx, 0, len(self._keys) - 1)
                    hit |= self._keys[idx] == q
        return ~hit


def _pack(cells, base):
    return ((cells[:, 0].astype(np.int64) * base) + cells[:, 1].astype(np.int64)) * base + cells[:, 2].astype(np.int64)


def foreground_mask(xyz, cell, ok, bg, tau=TAU_NOVELTY_M, tau_rel=TAU_REL_M_PER_M,
                    drop=RANGE_DROP_M):
    """前景 = 同射线明显变近 ∪ 3D 上背景解释不了；返回 bool 掩码。"""
    pts = np.asarray(xyz, dtype=np.float64)
    mask = np.zeros(len(pts), dtype=bool)
    sel = np.flatnonzero(ok)
    if not len(sel):
        return mask
    q = pts[sel]
    cells = np.asarray(cell)[sel]
    rng = np.sqrt((q * q).sum(axis=1))
    ref = bg.range_map[cells]
    has = np.isfinite(ref)
    closer = has & (rng < ref - drop)
    novel = bg.novel_mask(q, tau=tau)
    mask[sel] = novel | closer
    return mask


class Track:
    __slots__ = ("id", "center", "last_frame", "hits", "misses", "confirmed", "box", "speed", "path")

    def __init__(self, track_id, center, last_frame, box, path):
        self.id = track_id
        self.center = center
        self.last_frame = last_frame
        self.hits = 1
        self.misses = 0
        self.confirmed = False
        self.box = box
        self.speed = 0.0
        self.path = path


class PlaneTracker:
    """最近邻 + 速度预测关联；命中 >=4 或单帧位移 >=0.30 m 即确认。"""

    def __init__(self, gate_m=0.75, max_misses=3, confirm_hits=4, confirm_move_m=0.30):
        self.gate_m = float(gate_m)
        self.max_misses = int(max_misses)
        self.confirm_hits = int(confirm_hits)
        self.confirm_move_m = float(confirm_move_m)
        self.tracks = []
        self._next_id = 1

    def step(self, frame, dt, candidates):
        out = []
        used = set()
        for tr in sorted(self.tracks, key=lambda t: -t.hits):
            best, best_d = None, None
            for k, cand in enumerate(candidates):
                if k in used:
                    continue
                c = np.asarray(cand["center"], dtype=np.float64)
                d = float(np.linalg.norm(c - tr.center))
                if d <= self.gate_m and (best_d is None or d < best_d):
                    best, best_d = k, d
            if best is None:
                tr.misses += 1
                continue
            used.add(best)
            cand = candidates[best]
            c = np.asarray(cand["center"], dtype=np.float64)
            moved = float(np.linalg.norm(c - tr.center))
            tr.speed = moved / dt if dt > 0 else 0.0
            tr.center = c
            tr.box = cand["box"]
            tr.last_frame = frame
            tr.hits += 1
            tr.misses = 0
            tr.path.append(c.copy())
            if tr.hits >= self.confirm_hits or moved >= self.confirm_move_m:
                tr.confirmed = True
            out.append((tr, cand))
        for k, cand in enumerate(candidates):
            if k in used:
                continue
            center = np.asarray(cand["center"], dtype=np.float64)
            tr = Track(self._next_id, center, frame, cand["box"], [center.copy()])
            self._next_id += 1
            self.tracks.append(tr)
            out.append((tr, cand))
        for tr in list(self.tracks):
            if tr.misses > self.max_misses:
                self.tracks.remove(tr)
        for tr, cand in out:
            cand["track_id"] = tr.id
            cand["confirmed"] = bool(tr.confirmed)
            cand["hits"] = int(tr.hits)
        return out


def box_mask(points, box, margin=0.06):
    """点是否落在（可加 margin 的）有向包围盒内。"""
    pts = np.asarray(points, dtype=np.float64)
    if not len(pts):
        return np.zeros(0, dtype=bool)
    axes = np.asarray(box["axes"], dtype=np.float64)
    half = np.asarray(box["half"], dtype=np.float64) + margin
    proj = (pts - np.asarray(box["center"], dtype=np.float64)) @ axes.T
    return np.all(np.abs(proj) <= half, axis=1)


def detect_frame(xyz, ring, bg, tracker, frame, dt, *, tau=TAU_NOVELTY_M,
                 tau_rel=TAU_REL_M_PER_M, drop=RANGE_DROP_M, eps=CLUSTER_EPS_M,
                 min_points=MIN_CLUSTER_POINTS, max_extent=MAX_CLUSTER_EXTENT_M,
                 max_range=MAX_RANGE_M, min_intensity=MIN_INTENSITY, intensity=None):
    """逐帧检测：前景 -> 聚类 -> 过滤 -> 关联。

    背景未建立（``bg.ready`` 为 False）时只累积观测，返回 ``bootstrap=True``。
    """
    pts = np.asarray(xyz, dtype=np.float64)
    cell, ok = ray_cells(pts, ring)
    if not bg.ready:
        bg.observe(cell, ok, pts)
        return dict(frame=int(frame), bootstrap=True, foreground_points=0,
                    candidates=[], target=None)
    mask = foreground_mask(pts, cell, ok, bg, tau=tau, drop=drop)
    fg_pts = pts[mask]
    fg_int = None if intensity is None else np.asarray(intensity, dtype=np.float64)[mask]
    candidates = []
    for cluster_idx in cluster_points(fg_pts, eps=eps, min_points=min_points):
        q = fg_pts[cluster_idx]
        ext = q.max(axis=0) - q.min(axis=0)
        if float(ext.max()) > max_extent:
            continue
        if min_intensity > 0 and fg_int is not None:
            if float(np.median(fg_int[cluster_idx])) < min_intensity:
                continue
        center = q.mean(axis=0)
        rng = float(np.linalg.norm(center))
        if rng > max_range:
            continue
        box = fit_obb(q)
        candidates.append(dict(center=center, box=box, points=q, point_count=int(len(q)),
                               range=rng, extent=[float(v) for v in ext]))
    candidates.sort(key=lambda c: -c["point_count"])
    links = tracker.step(frame, dt, candidates)
    target = None
    if links:
        tr, cand = max(links, key=lambda it: (it[0].confirmed, it[0].hits, len(it[1]["points"])))
        target = dict(track_id=tr.id, confirmed=bool(tr.confirmed), hits=int(tr.hits),
                      center=[float(v) for v in cand["center"]],
                      box=dict(center=[float(v) for v in cand["box"]["center"]],
                               axes=[[float(v) for v in row] for row in cand["box"]["axes"]],
                               half=[float(v) for v in cand["box"]["half"]],
                               extent=[float(v) for v in cand["box"]["extent"]]),
                      point_count=int(cand["point_count"]), range=float(cand["range"]),
                      speed=float(tr.speed),
                      extent=[float(v) for v in cand["extent"]],
                      points=[[float(v) for v in row] for row in cand["points"]])
    return dict(frame=int(frame), bootstrap=False, foreground_points=int(mask.sum()),
                candidates=[dict(point_count=c["point_count"], center=[float(v) for v in c["center"]])
                            for c in candidates],
                target=target)


# ----------------------------------------------------------------------------- 相机 2D 侧


def _components(diff, mask, min_area, max_area, max_side, min_peak=0.0):
    """4/8 连通域（栅格 BFS）；返回按面积降序的框列表。"""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        pix = []
        while stack:
            y, x = stack.pop()
            pix.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
        if len(pix) < min_area or len(pix) > max_area:
            continue
        arr = np.array(pix)
        y1, y2 = int(arr[:, 0].min()), int(arr[:, 0].max())
        x1, x2 = int(arr[:, 1].min()), int(arr[:, 1].max())
        if (x2 - x1 + 1) > max_side or (y2 - y1 + 1) > max_side:
            continue
        peak = float(diff[arr[:, 0], arr[:, 1]].max())
        if peak < min_peak:
            continue
        out.append(dict(x0=x1, y0=y1, x1=x2, y1=y2, area=int(len(pix)), peak=peak,
                        cx=(x1 + x2) / 2.0, cy=(y1 + y2) / 2.0))
    out.sort(key=lambda b: -b["area"])
    return out


def _link_components(per_frame, link_px, min_frames=3, min_travel_px=120.0,
                     min_area_med=150.0, max_area_med=4000.0, area_weight=200.0):
    """逐帧连通域 -> 一对一贪心关联成短轨迹；只保留像“飞过去的小白点”那条。

    关联代价 = 中心位移 + area_weight*|log(面积比)|：大小差太多的连通域不会互相抢。
    """
    tracks = []
    for i, comps in enumerate(per_frame):
        pairs = []
        for ti, tr in enumerate(tracks):
            if tr["last"] < i - 2:
                continue
            last = tr["boxes"][-1]
            for ci, box in enumerate(comps):
                d = float(np.hypot(box["cx"] - last["cx"], box["cy"] - last["cy"]))
                if d > link_px:
                    continue
                ratio = max(box["area"], 1) / max(last["area"], 1)
                cost = d + area_weight * abs(float(np.log(ratio)))
                pairs.append((cost, d, ti, ci))
        pairs.sort()
        used_t, used_c = set(), set()
        for cost, d, ti, ci in pairs:
            if ti in used_t or ci in used_c:
                continue
            tr = tracks[ti]
            tr["boxes"].append(comps[ci])
            tr["frames"].append(i)
            tr["last"] = i
            used_t.add(ti)
            used_c.add(ci)
        for ci, box in enumerate(comps):
            if ci in used_c:
                continue
            tracks.append(dict(boxes=[box], frames=[i], last=i))
    assigned = [None] * len(per_frame)
    scored = []
    for tr in tracks:
        n = len(tr["boxes"])
        travel = sum(float(np.hypot(b["cx"] - a["cx"], b["cy"] - a["cy"]))
                     for a, b in zip(tr["boxes"], tr["boxes"][1:]))
        area_med = float(np.median([b["area"] for b in tr["boxes"]]))
        if n < min_frames or travel < min_travel_px:
            continue
        if area_med < min_area_med or area_med > max_area_med:
            continue
        scored.append((travel + 40.0 * n, tr))
    if scored:
        scored.sort(key=lambda it: -it[0])
        keep = scored[0][1]
        for fr, box in zip(keep["frames"], keep["boxes"]):
            assigned[fr] = box
    return assigned


def camera_boxes(frames_gray, *, tau=22.0, min_area=10, max_area=8000, max_side=220,
                 min_peak=45.0, link_px=280.0, min_frames=3, min_travel_px=100.0,
                 min_area_med=150.0, max_area_med=4000.0):
    """相机侧绿色 2D 框：时域中值背景 -> 帧差 -> 连通域 -> 短轨迹筛选。"""
    imgs = [np.asarray(g, dtype=np.float32) for g in frames_gray]
    if not imgs:
        return [], None
    bg = np.median(np.stack(imgs), axis=0)
    comps = []
    for img in imgs:
        d = np.abs(img - bg)
        comps.append(_components(d, d > tau, min_area, max_area, max_side, min_peak=min_peak))
    return _link_components(comps, link_px, min_frames=min_frames,
                            min_travel_px=min_travel_px,
                            min_area_med=min_area_med, max_area_med=max_area_med), bg