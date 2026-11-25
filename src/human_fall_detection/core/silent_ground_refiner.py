"""开机即用重力方向配平 + 后台无感地面精修（纯雷达 + 可选静止 IMU，stdlib + NumPy）。

设计目标：
1. 第 0 帧立刻可用：优先使用雷达 `/inno_imu` 静止重力均值，无 IMU 时退回标称安装角
   (pitch_deg / roll_deg)，立即给出单位重力向上向量 `gravity_up` 与初始 `displayPlane`，
   不需要 50 帧空场声明或阻塞式 25+3 帧拟合。
2. 后台无感精修地面零点 `offset_m` 与法向 `normal`：
   - 通道 A（静态底面静默拟合）：从非前景静态点中按 `gravity_up` 找最低显著水平峰，
     做确定性 RANSAC + TLS 精修，并施加倾斜一致门、空间跨度门与“平面下方静态点占比 < 3%”
     防桌面/床面劫持门；多帧一致后离散原子提交，收敛后遇遮挡冻结保持，绝不打断跟踪或清空历史。
   - 通道 B（直立人脚底高度兜底与交叉校验）：累计已锁直立目标的 `h_p02`，地面被杂物挡死无法
     拟合平面时可提供 `foot_anchored` 零点，平面已收敛时提供 `footConsistent` 物理交叉校验。
3. 语义诚实：
   - 所有输出明确标明 `physicalGroundTruth='UNKNOWN'`、`imuExtrinsicsVerified=False`；
   - 阶段显式区分 `gravity_only` / `foot_anchored` / `refined_plane`，不把标称角或几何拟合伪装成真值。
"""

import hashlib
import json
import math
import threading

import numpy as np

try:  # pragma: no cover - import shim
    from .range_contract import binding_tuple
except ImportError:  # pragma: no cover
    from range_contract import binding_tuple


STAGE_GRAVITY_ONLY = "gravity_only"
STAGE_FOOT_ANCHORED = "foot_anchored"
STAGE_REFINED_PLANE = "refined_plane"

DEFAULT_GRAVITY_SETTINGS = {
    "mount_pitch_deg": 26.0,
    "mount_roll_deg": 0.0,
    "imu_axis_signs": (1.0, 1.0, 1.0),
    "imu_norm_min_m_s2": 8.5,
    "imu_norm_max_m_s2": 11.0,
    "imu_max_gyro_rad_s": 0.15,
    "imu_min_up_z": 0.30,
    "imu_min_samples": 10,
    "imu_ema_alpha_init": 0.10,
    "imu_ema_alpha_steady": 0.01,
    "imu_commit_angle_deg": 1.5,
}

DEFAULT_REFINER_SETTINGS = {
    "check_interval_converging": 5,
    "check_interval_steady": 25,
    "min_range_m": 0.50,
    "max_range_m": 7.50,
    "max_sample_points": 2000,
    "hist_bin_m": 0.03,
    "band_half_width_m": 0.12,
    "min_sensor_height_m": 0.45,
    "max_sensor_height_m": 3.50,
    "min_band_points": 160,
    "min_inliers": 200,
    "inlier_threshold_m": 0.035,
    "max_rms_m": 0.025,
    "max_p95_m": 0.045,
    "min_span_major_m": 0.80,
    "min_span_minor_m": 0.45,
    "below_plane_margin_m": 0.15,
    "max_below_fraction": 0.03,
    "max_tilt_diff_nominal_deg": 12.0,
    "max_tilt_diff_imu_deg": 8.0,
    "ransac_iters": 48,
    "consensus_window": 3,
    "consensus_angle_deg": 1.5,
    "consensus_offset_m": 0.03,
    "shift_angle_deg": 2.5,
    "shift_offset_m": 0.04,
    "shift_confirm_count": 5,
    "foot_min_samples": 10,
    "foot_min_travel_m": 0.20,
    "foot_fallback_min_samples": 20,
    "foot_max_history": 80,
    "foot_consistency_tol_m": 0.18,
    "nominal_display_offset_m": 0.0,
}


def gravity_up_from_pitch_roll(pitch_deg, roll_deg):
    """按雷达系 (X前, Y左, Z上; pitch向下为正) 构造世界向上单位向量。"""
    p = math.radians(float(pitch_deg))
    r = math.radians(float(roll_deg))
    cp = math.cos(p)
    vec = np.array([-math.sin(p), -cp * math.sin(r), cp * math.cos(r)], dtype=np.float64)
    norm = float(np.linalg.norm(vec))
    if not math.isfinite(norm) or norm < 1e-9:
        return np.array([0.0, 0.0, 1.0], dtype=np.float64)
    return vec / norm


def _unit_vec(v):
    arr = np.asarray(v, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(arr))
    if not np.isfinite(arr).all() or not math.isfinite(norm) or norm < 1e-9:
        raise ValueError("vector must be finite and non-zero")
    return arr / norm


def _angle_deg(a, b):
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    return math.degrees(math.acos(dot))


def horizontal_basis(up):
    """构造与 up 正交的水平基 (u_axis, v_axis, up)。"""
    g = _unit_vec(up)
    ref = np.array([1.0, 0.0, 0.0], dtype=np.float64) if abs(float(g[0])) < 0.8 else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    v_axis = _unit_vec(np.cross(g, ref))
    u_axis = _unit_vec(np.cross(v_axis, g))
    return u_axis, v_axis, g


def _plane_sha(normal, offset_m, stage, source):
    payload = {
        "normal": [round(float(x), 6) for x in normal],
        "offset_m": None if offset_m is None else round(float(offset_m), 6),
        "stage": str(stage),
        "source": str(source),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def resolve_gravity_settings(settings=None):
    resolved = dict(DEFAULT_GRAVITY_SETTINGS)
    for k, v in (settings or {}).items():
        if k not in resolved:
            raise ValueError("unknown gravity setting: " + str(k))
        resolved[k] = v
    resolved["mount_pitch_deg"] = float(resolved["mount_pitch_deg"])
    resolved["mount_roll_deg"] = float(resolved["mount_roll_deg"])
    if not (-85.0 <= resolved["mount_pitch_deg"] <= 85.0 and -85.0 <= resolved["mount_roll_deg"] <= 85.0):
        raise ValueError("mount pitch/roll must be within [-85, 85] deg")
    signs = tuple(float(x) for x in resolved["imu_axis_signs"])
    if len(signs) != 3 or any(s not in (-1.0, 1.0) for s in signs):
        raise ValueError("imu_axis_signs must be a 3-tuple of +1/-1")
    resolved["imu_axis_signs"] = signs
    for key in ("imu_norm_min_m_s2", "imu_norm_max_m_s2", "imu_max_gyro_rad_s",
                "imu_min_up_z", "imu_ema_alpha_init", "imu_ema_alpha_steady", "imu_commit_angle_deg"):
        val = float(resolved[key])
        if not math.isfinite(val) or val < 0.0:
            raise ValueError(key + " must be finite non-negative")
        resolved[key] = val
    if resolved["imu_norm_max_m_s2"] <= resolved["imu_norm_min_m_s2"]:
        raise ValueError("imu_norm_max_m_s2 must exceed imu_norm_min_m_s2")
    if isinstance(resolved["imu_min_samples"], bool) or int(resolved["imu_min_samples"]) < 1:
        raise ValueError("imu_min_samples must be positive integer")
    resolved["imu_min_samples"] = int(resolved["imu_min_samples"])
    return resolved


def resolve_refiner_settings(settings=None):
    resolved = dict(DEFAULT_REFINER_SETTINGS)
    for k, v in (settings or {}).items():
        if k not in resolved:
            raise ValueError("unknown refiner setting: " + str(k))
        resolved[k] = v
    int_keys = (
        "check_interval_converging", "check_interval_steady", "max_sample_points",
        "min_band_points", "min_inliers", "ransac_iters", "consensus_window",
        "shift_confirm_count", "foot_min_samples", "foot_fallback_min_samples",
        "foot_max_history",
    )
    for key in int_keys:
        val = resolved[key]
        if isinstance(val, bool) or int(val) != val or int(val) < 1:
            raise ValueError(key + " must be a positive integer")
        resolved[key] = int(val)
    for key in resolved:
        if key in int_keys:
            continue
        val = float(resolved[key])
        if not math.isfinite(val):
            raise ValueError(key + " must be finite")
        resolved[key] = val
    if resolved["max_range_m"] <= resolved["min_range_m"]:
        raise ValueError("max_range_m must exceed min_range_m")
    if resolved["max_sensor_height_m"] <= resolved["min_sensor_height_m"]:
        raise ValueError("max_sensor_height_m must exceed min_sensor_height_m")
    return resolved


class GravityUpEstimator:
    """线程安全的重力向上方向估计器：第 0 帧即由标称角就绪，收到静止 IMU 后离散平滑切入。"""

    def __init__(self, settings=None):
        self.settings = resolve_gravity_settings(settings)
        self._lock = threading.Lock()
        self._nominal_up = gravity_up_from_pitch_roll(
            self.settings["mount_pitch_deg"], self.settings["mount_roll_deg"]
        )
        self._committed_up = self._nominal_up.copy()
        self._source = "nominal_mount"
        self._revision = 0
        self._imu_ema = None
        self._imu_samples = 0
        self._imu_rejected = 0
        self._imu_last_stamp = None

    def reset(self):
        with self._lock:
            self._committed_up = self._nominal_up.copy()
            self._source = "nominal_mount"
            self._revision += 1
            self._imu_ema = None
            self._imu_samples = 0
            self._imu_rejected = 0
            self._imu_last_stamp = None

    def feed_imu(self, ax, ay, az, gx=0.0, gy=0.0, gz=0.0, stamp_s=None):
        """喂入单帧三轴加速度/角速度（m/s^2, rad/s）；仅静止样本参与重力方向估计。"""
        cfg = self.settings
        vals = (ax, ay, az, gx, gy, gz)
        try:
            fvals = [float(v) for v in vals]
        except (TypeError, ValueError):
            with self._lock:
                self._imu_rejected += 1
            return False
        if not all(math.isfinite(v) for v in fvals):
            with self._lock:
                self._imu_rejected += 1
            return False
        sx, sy, sz = cfg["imu_axis_signs"]
        acc = np.array([fvals[0] * sx, fvals[1] * sy, fvals[2] * sz], dtype=np.float64)
        gyro = np.array([fvals[3], fvals[4], fvals[5]], dtype=np.float64)
        acc_norm = float(np.linalg.norm(acc))
        gyro_norm = float(np.linalg.norm(gyro))
        if not (cfg["imu_norm_min_m_s2"] <= acc_norm <= cfg["imu_norm_max_m_s2"]):
            with self._lock:
                self._imu_rejected += 1
            return False
        if gyro_norm > cfg["imu_max_gyro_rad_s"]:
            with self._lock:
                self._imu_rejected += 1
            return False
        unit_up = acc / acc_norm
        if float(unit_up[2]) < cfg["imu_min_up_z"]:
            with self._lock:
                self._imu_rejected += 1
            return False

        with self._lock:
            self._imu_samples += 1
            if stamp_s is not None and math.isfinite(float(stamp_s)):
                self._imu_last_stamp = float(stamp_s)
            if self._imu_ema is None:
                self._imu_ema = unit_up.copy()
            else:
                alpha = (cfg["imu_ema_alpha_init"]
                         if self._imu_samples <= cfg["imu_min_samples"] * 3
                         else cfg["imu_ema_alpha_steady"])
                blended = (1.0 - alpha) * self._imu_ema + alpha * unit_up
                bn = float(np.linalg.norm(blended))
                if bn > 1e-9:
                    self._imu_ema = blended / bn

            if self._imu_samples >= cfg["imu_min_samples"]:
                if self._source != "imu_static_gravity":
                    self._committed_up = self._imu_ema.copy()
                    self._source = "imu_static_gravity"
                    self._revision += 1
                elif _angle_deg(self._committed_up, self._imu_ema) >= cfg["imu_commit_angle_deg"]:
                    self._committed_up = self._imu_ema.copy()
                    self._revision += 1
        return True

    def snapshot(self):
        with self._lock:
            return {
                "up": self._committed_up.copy(),
                "source": self._source,
                "revision": int(self._revision),
                "imu_samples": int(self._imu_samples),
                "imu_rejected": int(self._imu_rejected),
                "imu_last_stamp_s": self._imu_last_stamp,
                "imu_extrinsics_verified": False,
                "mount_pitch_deg": self.settings["mount_pitch_deg"],
                "mount_roll_deg": self.settings["mount_roll_deg"],
            }


def fit_low_plane_candidate(static_xyz, gravity_up, settings, max_tilt_deg):
    """从静态非前景点云中基于 gravity_up 搜索最低显著水平面（确定性 RANSAC + TLS）。

    返回 dict（含 normal, offset_m, inliers, rms_m, p95_m, span_major_m, span_minor_m,
    below_fraction, tilt_diff_deg）或 (None, reason_str)。
    """
    pts = np.asarray(static_xyz, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < settings["min_band_points"]:
        return None, "insufficient_static_points"

    g_up = _unit_vec(gravity_up)
    r = np.linalg.norm(pts, axis=1)
    keep = np.isfinite(pts).all(axis=1) & (r >= settings["min_range_m"]) & (r <= settings["max_range_m"])
    pts = pts[keep]
    if len(pts) < settings["min_band_points"]:
        return None, "insufficient_range_filtered_points"

    # 均匀确定性子采样，控制单次耗时在 ~1–3 ms
    max_n = settings["max_sample_points"]
    if len(pts) > max_n:
        stride = max(1, len(pts) // max_n)
        pts = pts[::stride][:max_n]

    h_g = pts @ g_up
    # 地板位于传感器下方：h_g = -sensor_height_m ∈ [-max_sensor_height_m, -min_sensor_height_m]
    h_lo = -settings["max_sensor_height_m"]
    h_hi = -settings["min_sensor_height_m"]
    in_domain = (h_g >= h_lo) & (h_g <= h_hi)
    if int(in_domain.sum()) < settings["min_band_points"]:
        return None, "no_points_in_sensor_height_domain"

    h_dom = h_g[in_domain]
    pts_dom = pts[in_domain]
    bin_m = settings["hist_bin_m"]
    h_min = float(h_dom.min())
    h_max = float(h_dom.max())
    n_bins = max(1, int(math.ceil((h_max - h_min) / bin_m)) + 1)
    idx = np.clip(((h_dom - h_min) / bin_m).astype(np.int64), 0, n_bins - 1)
    counts = np.bincount(idx, minlength=n_bins)

    # 3-bin 平滑（9 cm 带宽）找最低显著峰，避免桌面/台面高处峰抢占地板
    if n_bins >= 3:
        smooth = np.convolve(counts.astype(np.float64), np.array([1.0, 1.0, 1.0]), mode="same")
    else:
        smooth = counts.astype(np.float64)

    u_ax, v_ax, _ = horizontal_basis(g_up)
    min_peak_pts = max(40, settings["min_band_points"] // 3)

    # 按高度从低到高扫描局部峰（或超过阈值的最低带），第一个满足水平跨度与下方净空门的即为地板
    candidate_bins = []
    for b in range(n_bins):
        if smooth[b] < min_peak_pts:
            continue
        left_ok = (b == 0) or (smooth[b] >= smooth[b - 1])
        right_ok = (b == n_bins - 1) or (smooth[b] >= smooth[b + 1])
        if left_ok and right_ok:
            candidate_bins.append(b)
    if not candidate_bins:
        # 兜底：取最低 30% 中最高峰
        low_limit = max(1, int(math.ceil(n_bins * 0.4)))
        candidate_bins = [int(np.argmax(smooth[:low_limit]))]

    last_reason = "no_valid_floor_peak"
    tol = settings["inlier_threshold_m"]
    band_half = settings["band_half_width_m"]
    rng = np.random.RandomState(20261125)

    for peak_b in candidate_bins[:16]:
        h_peak = h_min + (peak_b + 0.5) * bin_m
        band_mask = np.abs(h_dom - h_peak) <= band_half
        band_pts = pts_dom[band_mask]
        if len(band_pts) < settings["min_band_points"]:
            last_reason = "floor_band_too_sparse"
            continue

        # 确定性 RANSAC（固定 3 点采样 + 倾斜门预筛）
        m = len(band_pts)
        best_inliers = None
        best_count = 0
        cos_min = math.cos(math.radians(max_tilt_deg))
        for _ in range(settings["ransac_iters"]):
            tri = rng.randint(0, m, size=3)
            p0, p1, p2 = band_pts[tri[0]], band_pts[tri[1]], band_pts[tri[2]]
            n = np.cross(p1 - p0, p2 - p0)
            nn = float(np.linalg.norm(n))
            if nn < 1e-6:
                continue
            n = n / nn
            if float(np.dot(n, g_up)) < 0.0:
                n = -n
            if float(np.dot(n, g_up)) < cos_min:
                continue
            d = -float(np.dot(n, p0))
            inliers = np.abs(band_pts @ n + d) <= tol
            cnt = int(inliers.sum())
            if cnt > best_count:
                best_count = cnt
                best_inliers = inliers

        # 额外加入 gravity_up 初始假设作为候选，防止小斜率下随机漏检
        d0 = -float(np.median(band_pts @ g_up))
        inl0 = np.abs(band_pts @ g_up + d0) <= tol
        if int(inl0.sum()) > best_count:
            best_count = int(inl0.sum())
            best_inliers = inl0

        if best_inliers is None or best_count < settings["min_inliers"]:
            last_reason = "insufficient_plane_inliers"
            continue

        # TLS / SVD 精修
        inlier_pts = band_pts[best_inliers]
        center = inlier_pts.mean(axis=0)
        centered = inlier_pts - center
        _, _, vt = np.linalg.svd(centered, full_matrices=False)
        n_fit = vt[-1]
        if float(np.dot(n_fit, g_up)) < 0.0:
            n_fit = -n_fit
        n_fit = _unit_vec(n_fit)
        d_fit = -float(np.dot(n_fit, center))

        # 用精修平面重算全静态点集中的内点（带 ±tol）
        all_signed = pts @ n_fit + d_fit
        inlier_all = np.abs(all_signed) <= tol
        inlier_count = int(inlier_all.sum())
        if inlier_count < settings["min_inliers"]:
            last_reason = "insufficient_tls_inliers"
            continue

        if not (settings["min_sensor_height_m"] <= d_fit <= settings["max_sensor_height_m"]):
            last_reason = "sensor_height_out_of_domain"
            continue

        tilt_diff = _angle_deg(n_fit, g_up)
        if tilt_diff > max_tilt_deg:
            last_reason = "tilt_exceeds_gravity_gate"
            continue

        # 再次 TLS 精修（使用所有地板内点）
        final_pts = pts[inlier_all]
        center = final_pts.mean(axis=0)
        _, _, vt = np.linalg.svd(final_pts - center, full_matrices=False)
        n_fit = vt[-1]
        if float(np.dot(n_fit, g_up)) < 0.0:
            n_fit = -n_fit
        n_fit = _unit_vec(n_fit)
        d_fit = -float(np.dot(n_fit, center))
        tilt_diff = _angle_deg(n_fit, g_up)
        if tilt_diff > max_tilt_deg or not (settings["min_sensor_height_m"] <= d_fit <= settings["max_sensor_height_m"]):
            last_reason = "refined_plane_gate_failed"
            continue

        res = np.abs(final_pts @ n_fit + d_fit)
        rms = float(np.sqrt(np.mean(res * res)))
        p95 = float(np.percentile(res, 95.0))
        if rms > settings["max_rms_m"] or p95 > settings["max_p95_m"]:
            last_reason = "plane_residual_too_high"
            continue

        # 2D 水平支撑跨度检查（防窄桌沿/栏杆）
        u_f, v_f, _ = horizontal_basis(n_fit)
        uv = np.column_stack((final_pts @ u_f, final_pts @ v_f))
        uv_c = uv - uv.mean(axis=0)
        cov = (uv_c.T @ uv_c) / max(1, len(uv_c))
        eigvals, eigvecs = np.linalg.eigh(cov)
        proj_minor = uv_c @ eigvecs[:, 0]
        proj_major = uv_c @ eigvecs[:, 1]
        span_minor = float(np.percentile(proj_minor, 95.0) - np.percentile(proj_minor, 5.0))
        span_major = float(np.percentile(proj_major, 95.0) - np.percentile(proj_major, 5.0))
        if span_major < settings["min_span_major_m"] or span_minor < settings["min_span_minor_m"]:
            last_reason = "insufficient_horizontal_support"
            continue

        # 关键防桌面劫持门：静态点中显著低于该平面的比例必须极小
        below_frac = float((pts @ n_fit + d_fit < -settings["below_plane_margin_m"]).mean())
        if below_frac > settings["max_below_fraction"]:
            last_reason = "elevated_surface_rejected_below_points"
            continue

        return {
            "normal": n_fit,
            "offset_m": float(d_fit),
            "inliers": inlier_count,
            "rms_m": rms,
            "p95_m": p95,
            "span_major_m": span_major,
            "span_minor_m": span_minor,
            "below_fraction": below_frac,
            "tilt_diff_deg": tilt_diff,
        }, None

    return None, last_reason


class SilentGroundRefiner:
    """后台无感地面精修器：从第 0 帧即提供重力配平，后台渐进收敛地面零点与法向。"""

    def __init__(self, gravity_estimator=None, settings=None, frame_id="innolidar"):
        self.gravity = gravity_estimator if gravity_estimator is not None else GravityUpEstimator()
        self.settings = resolve_refiner_settings(settings)
        self.frame_id = str(frame_id)

        self._stage = STAGE_GRAVITY_ONLY
        self._normal = self.gravity.snapshot()["up"]
        self._offset_m = None
        self._source = "nominal_mount"
        self._quality = None
        self._revision = 0
        self._sha = _plane_sha(self._normal, self._offset_m, self._stage, self._source)
        self._last_gravity_rev = self.gravity.snapshot()["revision"]

        self._frames_seen = 0
        self._checks_run = 0
        self._last_check_reason = "awaiting_first_check"
        self._consensus_buf = []
        self._shift_buf = []

        # 直立人脚底高度缓冲 [(foot_h, u, v), ...]
        self._foot_samples = []
        self._foot_offset_m = None
        self._foot_consistent = None
        self._foot_residual_m = None

    def reset(self):
        snap = self.gravity.snapshot()
        self._stage = STAGE_GRAVITY_ONLY
        self._normal = snap["up"]
        self._offset_m = None
        self._source = snap["source"]
        self._quality = None
        self._revision += 1
        self._sha = _plane_sha(self._normal, self._offset_m, self._stage, self._source)
        self._last_gravity_rev = snap["revision"]
        self._frames_seen = 0
        self._checks_run = 0
        self._last_check_reason = "reset"
        self._consensus_buf.clear()
        self._shift_buf.clear()
        self._foot_samples.clear()
        self._foot_offset_m = None
        self._foot_consistent = None
        self._foot_residual_m = None

    def _commit(self, stage, normal, offset_m, source, quality=None):
        self._stage = stage
        self._normal = _unit_vec(normal)
        self._offset_m = None if offset_m is None else float(offset_m)
        self._source = str(source)
        if quality is not None:
            self._quality = dict(quality)
        self._revision += 1
        self._sha = _plane_sha(self._normal, self._offset_m, self._stage, self._source)
        self._update_foot_consistency()

    def _update_foot_consistency(self):
        if self._offset_m is None or self._foot_offset_m is None:
            self._foot_consistent = None
            self._foot_residual_m = None
            return
        # foot_offset_m ≈ -median(foot_h), plane height at feet ≈ offset_m - foot_offset_m
        res = float(self._offset_m - self._foot_offset_m)
        self._foot_residual_m = res
        self._foot_consistent = abs(res) <= self.settings["foot_consistency_tol_m"]

    def observe_upright_foot(self, foot_h_along_up, horiz_u, horiz_v):
        """喂入已锁定直立人的脚底高度（沿当前 normal 投影，未加 offset_m）。"""
        if not all(math.isfinite(float(v)) for v in (foot_h_along_up, horiz_u, horiz_v)):
            return False
        est_offset = -float(foot_h_along_up)
        cfg = self.settings
        if not (cfg["min_sensor_height_m"] <= est_offset <= cfg["max_sensor_height_m"]):
            return False
        self._foot_samples.append((est_offset, float(horiz_u), float(horiz_v)))
        if len(self._foot_samples) > cfg["foot_max_history"]:
            self._foot_samples = self._foot_samples[-cfg["foot_max_history"]:]

        n = len(self._foot_samples)
        if n < cfg["foot_min_samples"]:
            return False
        us = [s[1] for s in self._foot_samples]
        vs = [s[2] for s in self._foot_samples]
        travel = math.hypot(max(us) - min(us), max(vs) - min(vs))
        if travel < cfg["foot_min_travel_m"] and n < cfg["foot_fallback_min_samples"]:
            return False

        med_offset = float(np.median([s[0] for s in self._foot_samples]))
        self._foot_offset_m = med_offset
        self._update_foot_consistency()

        if self._stage == STAGE_GRAVITY_ONLY:
            snap = self.gravity.snapshot()
            self._commit(
                STAGE_FOOT_ANCHORED,
                snap["up"],
                med_offset,
                "foot_anchored_" + snap["source"],
                quality={"foot_samples": n, "foot_travel_m": round(travel, 3)},
            )
            return True
        elif self._stage == STAGE_FOOT_ANCHORED:
            if abs(med_offset - float(self._offset_m)) >= cfg["shift_offset_m"]:
                snap = self.gravity.snapshot()
                self._commit(
                    STAGE_FOOT_ANCHORED,
                    snap["up"],
                    med_offset,
                    "foot_anchored_" + snap["source"],
                    quality={"foot_samples": n, "foot_travel_m": round(travel, 3)},
                )
                return True
        return False

    def is_check_due(self):
        """判断下一次 observe_frame 是否需要静态点云抽样拟合（便于调用方跳过非检查帧点云提取）。"""
        next_idx = self._frames_seen + 1
        interval = (self.settings["check_interval_steady"]
                    if self._stage == STAGE_REFINED_PLANE
                    else self.settings["check_interval_converging"])
        return (next_idx == 1) or (next_idx % interval == 0)

    def observe_frame(self, static_xyz, force_check=False):
        """每帧轻量调用：同步重力更新，按周期执行无感静态底面精修。"""
        self._frames_seen += 1
        snap = self.gravity.snapshot()
        if snap["revision"] != self._last_gravity_rev:
            self._last_gravity_rev = snap["revision"]
            if self._stage == STAGE_GRAVITY_ONLY:
                self._commit(STAGE_GRAVITY_ONLY, snap["up"], None, snap["source"])
            elif self._stage == STAGE_FOOT_ANCHORED:
                self._commit(STAGE_FOOT_ANCHORED, snap["up"], self._offset_m, "foot_anchored_" + snap["source"])

        cfg = self.settings
        interval = (cfg["check_interval_steady"]
                    if self._stage == STAGE_REFINED_PLANE
                    else cfg["check_interval_converging"])
        due = force_check or (self._frames_seen == 1) or (self._frames_seen % interval == 0)
        if not due or static_xyz is None or len(static_xyz) == 0:
            return False

        self._checks_run += 1
        max_tilt = (cfg["max_tilt_diff_imu_deg"]
                    if snap["source"] == "imu_static_gravity"
                    else cfg["max_tilt_diff_nominal_deg"])
        cand, reason = fit_low_plane_candidate(static_xyz, snap["up"], cfg, max_tilt)
        if cand is None:
            self._last_check_reason = reason
            return False

        self._last_check_reason = "candidate_accepted"
        if self._stage != STAGE_REFINED_PLANE:
            return self._accumulate_consensus(cand)
        return self._monitor_steady_shift(cand)

    def _accumulate_consensus(self, cand):
        cfg = self.settings
        if self._consensus_buf:
            ref = self._consensus_buf[-1]
            ang = _angle_deg(ref["normal"], cand["normal"])
            off = abs(ref["offset_m"] - cand["offset_m"])
            if ang > cfg["consensus_angle_deg"] or off > cfg["consensus_offset_m"]:
                self._consensus_buf = [cand]
                self._last_check_reason = "consensus_reset_inconsistent"
                return False
        self._consensus_buf.append(cand)
        if len(self._consensus_buf) < cfg["consensus_window"]:
            self._last_check_reason = "converging_%d_of_%d" % (len(self._consensus_buf), cfg["consensus_window"])
            return False

        normals = np.stack([c["normal"] for c in self._consensus_buf], axis=0)
        mean_n = _unit_vec(normals.mean(axis=0))
        med_off = float(np.median([c["offset_m"] for c in self._consensus_buf]))
        quality = {
            "inliers": int(np.median([c["inliers"] for c in self._consensus_buf])),
            "rms_m": round(float(np.median([c["rms_m"] for c in self._consensus_buf])), 5),
            "p95_m": round(float(np.median([c["p95_m"] for c in self._consensus_buf])), 5),
            "span_major_m": round(float(np.median([c["span_major_m"] for c in self._consensus_buf])), 3),
            "span_minor_m": round(float(np.median([c["span_minor_m"] for c in self._consensus_buf])), 3),
            "below_fraction": round(float(np.median([c["below_fraction"] for c in self._consensus_buf])), 4),
            "tilt_diff_deg": round(float(np.median([c["tilt_diff_deg"] for c in self._consensus_buf])), 3),
            "consensus_count": len(self._consensus_buf),
        }
        self._consensus_buf.clear()
        self._shift_buf.clear()
        self._last_check_reason = "refined_plane_converged"
        self._commit(STAGE_REFINED_PLANE, mean_n, med_off, "silent_plane_ransac_tls", quality=quality)
        return True

    def _monitor_steady_shift(self, cand):
        cfg = self.settings
        ang = _angle_deg(self._normal, cand["normal"])
        off = abs(float(self._offset_m) - cand["offset_m"])
        if ang <= cfg["shift_angle_deg"] and off <= cfg["shift_offset_m"]:
            self._shift_buf.clear()
            self._last_check_reason = "steady_consistent"
            return False

        if self._shift_buf:
            ref = self._shift_buf[-1]
            if (_angle_deg(ref["normal"], cand["normal"]) > cfg["consensus_angle_deg"]
                    or abs(ref["offset_m"] - cand["offset_m"]) > cfg["consensus_offset_m"]):
                self._shift_buf = [cand]
                self._last_check_reason = "shift_candidate_reset"
                return False
        self._shift_buf.append(cand)
        if len(self._shift_buf) < cfg["shift_confirm_count"]:
            self._last_check_reason = "shift_pending_%d_of_%d" % (len(self._shift_buf), cfg["shift_confirm_count"])
            return False

        normals = np.stack([c["normal"] for c in self._shift_buf], axis=0)
        mean_n = _unit_vec(normals.mean(axis=0))
        med_off = float(np.median([c["offset_m"] for c in self._shift_buf]))
        quality = {
            "inliers": int(np.median([c["inliers"] for c in self._shift_buf])),
            "rms_m": round(float(np.median([c["rms_m"] for c in self._shift_buf])), 5),
            "p95_m": round(float(np.median([c["p95_m"] for c in self._shift_buf])), 5),
            "span_major_m": round(float(np.median([c["span_major_m"] for c in self._shift_buf])), 3),
            "span_minor_m": round(float(np.median([c["span_minor_m"] for c in self._shift_buf])), 3),
            "below_fraction": round(float(np.median([c["below_fraction"] for c in self._shift_buf])), 4),
            "tilt_diff_deg": round(float(np.median([c["tilt_diff_deg"] for c in self._shift_buf])), 3),
            "releveling_detected": True,
        }
        self._shift_buf.clear()
        self._last_check_reason = "refined_plane_releveled"
        self._commit(STAGE_REFINED_PLANE, mean_n, med_off, "silent_plane_ransac_tls", quality=quality)
        return True

    @property
    def stage(self):
        return self._stage

    @property
    def normal(self):
        return self._normal.copy()

    @property
    def offset_m(self):
        return self._offset_m

    @property
    def has_offset(self):
        return self._offset_m is not None

    @property
    def sha256(self):
        return self._sha

    @property
    def revision(self):
        return self._revision

    def bound_plane(self, frame_or_identity):
        """当已获得地面零点（refined_plane / foot_anchored）时，返回与 core.range_features.bound_ground 兼容的平面字典。"""
        if self._offset_m is None:
            return None
        if hasattr(frame_or_identity, "binding"):
            raw_b = frame_or_identity.binding
            if isinstance(raw_b, tuple) and len(raw_b) == 1 and isinstance(raw_b[0], str):
                binding = json.loads(raw_b[0])
            else:
                raise ValueError("unsupported frame.binding format")
        else:
            binding = dict(frame_or_identity)
        coord = str(binding.get("coordinate", ""))
        frame_name = coord.split("/", 1)[1] if "/" in coord else self.frame_id
        return {
            "status": "valid",
            "frame": frame_name,
            "binding": binding,
            "normal": [float(v) for v in self._normal],
            "offset_m": float(self._offset_m),
            "source": "silent_ground_refiner",
            "refinement_stage": self._stage,
            "refinement_source": self._source,
            "physicalGroundTruth": "UNKNOWN",
        }

    def status_dict(self, session_id):
        """生成与 RangeEngine / LiDAR Studio 契约兼容的 ground 状态对象（含第 0 帧即用的 displayPlane）。"""
        gsnap = self.gravity.snapshot()
        disp_offset = (
            float(self._offset_m)
            if self._offset_m is not None
            else float(self.settings["nominal_display_offset_m"])
        )
        available = self._offset_m is not None
        if self._stage == STAGE_REFINED_PLANE:
            reason = "silent_refined_plane"
        elif self._stage == STAGE_FOOT_ANCHORED:
            reason = "silent_foot_anchored"
        else:
            reason = "gravity_only_refining"
        return {
            "available": available,
            "reason": reason,
            "refinementStage": self._stage,
            "refinementSource": self._source,
            "gravitySource": gsnap["source"],
            "imuSamples": gsnap["imu_samples"],
            "imuExtrinsicsVerified": False,
            "offsetAvailable": available,
            "revision": self._revision,
            "sha256": self._sha,
            "checksRun": self._checks_run,
            "lastCheckReason": self._last_check_reason,
            "quality": dict(self._quality) if self._quality is not None else None,
            "footSamples": len(self._foot_samples),
            "footConsistent": self._foot_consistent,
            "footResidualM": None if self._foot_residual_m is None else round(self._foot_residual_m, 4),
            "physicalGroundTruth": "UNKNOWN",
            "displayPlane": {
                "sessionId": session_id,
                "normal": [round(float(v), 6) for v in self._normal],
                "offsetM": round(disp_offset, 6),
                "groundSha256": self._sha,
                "frameId": self.frame_id,
                "scope": "silent_refined_plane" if self._stage == STAGE_REFINED_PLANE else (
                    "silent_foot_anchored" if self._stage == STAGE_FOOT_ANCHORED else "gravity_only_display"
                ),
                "offsetAvailable": available,
            },
        }
