"""非刚体内部运动与周期振荡/悬空滞留拒识（纯雷达，stdlib + NumPy）。

功能：
1. 非刚体内部运动分析：将同轨连续实测点云按相对高度切为上/中/下三段与水平四象限半区，
   扣除整体平移后计算分段残差速度与层宽形变率。r2：门限一律表示为“噪声底的倍数”，噪声底由
   静止杂物轨迹在线标定（或调参集离线值回退）；未标定前刚体罚分与非刚体加分都不产生。
2. 3–5 s 窗口周期振荡/悬空检测：统计净位移/路径比、速度方向反转次数、局部滞留半径、1D 摆动
   线性度与峰-峰摆幅。r2：振荡只作为软惩罚证据；“悬空振荡”要求整窗与地面无接触。

严格语义：本模块只输出运动学物理证据，不输出人体真值身份（semantic 恒为 UNKNOWN）。
"""

from collections import deque
import math

import numpy as np

try:  # pragma: no cover - import shim
    from .lidar_candidates import ground_plane_basis
    from .range_features import bound_ground
except ImportError:  # pragma: no cover
    from lidar_candidates import ground_plane_basis
    from range_features import bound_ground


DEFAULT_KINEMATICS_SETTINGS = {
    "window_s": 4.0,
    "max_history_frames": 128,
    "max_pair_gap_s": 0.35,
    "miss_timeout_s": 1.5,
    "reset_gap_s": 2.0,
    "min_subregion_points": 8,
    "min_matched_subregions": 3,
    "min_articulation_pairs": 3,
    # r2：噪声底标定。真实 IFW192S 上子区质心的分割/采样抖动约 0.08–0.14 m/s（静止杂物与静止
    # 真人都在这个量级），旧版绝对门限（刚体 <=0.035、非刚体 >=0.06 m/s）在真实噪声下方向相反。
    # 现改为：从“非目标、prior 不兼容、近静止”的杂物轨迹相邻帧对在线累积残差速度/层宽变化率，
    # 取分位数作为噪声底；刚体/非刚体门限均为噪声底的倍数。未标定前两类判据恒为 False
    # （非刚体加分与刚体罚分都关闭）。可选离线噪声底（必须来自调参集）作为在线样本不足时的回退。
    "calib_static_max_hspeed_mps": 0.05,
    "calib_min_samples": 20,
    "calib_min_tracks": 2,
    "calib_max_samples": 400,
    "calib_quantile": 50.0,
    "calib_min_floor_mps": 0.02,
    "offline_noise_floor_ivel_mps": None,
    "offline_noise_floor_wrate_mps": None,
    "rigid_active_speed_min_mps": 0.14,
    # 调参集（7 段旧会话）窗口中位数比值：真实移动目标 <=0.8x 噪声底的占比 0.8%（1.5x 时 9%），
    # 静止目标 0.5–0.9x；>=2.5x 且层宽 >=2.5x（或单通道 >=4x）时移动目标 34%、非目标 1.1%、静止 0%。
    "rigid_ivel_noise_mult": 0.8,
    "rigid_wrate_noise_mult": 0.8,
    "articulation_ivel_noise_mult": 2.5,
    "articulation_wrate_noise_mult": 2.5,
    "articulation_strong_ivel_noise_mult": 4.0,
    "articulation_max_internal_vel_mps": 2.50,
    # 周期往复振荡 / 悬空摆动判据（在 3 帧平滑轨迹上检查 1D 摆动线性度与峰-峰摆幅）。
    # r2：振荡只产生软惩罚（见 human_belief）；“悬空振荡”额外要求整窗与地面无接触：
    # 每帧簇最低点高度都 > ground_contact_max_m（真实站/坐/躺目标最低点 p99 约 0.23 m，
    # 拟合地面存在约 0.1–0.15 m 偏置，故取 0.30 m）。
    "osc_min_span_s": 1.0,
    "osc_min_step_m": 0.032,
    "osc_reversal_cos_max": -0.35,
    "osc_min_path_m": 0.45,
    "osc_max_straightness": 0.28,
    "osc_min_reversals": 3,
    "osc_min_reversal_rate_hz": 0.80,
    "osc_max_stay_radius_m": 0.32,
    "osc_min_p2p_m": 0.14,
    "osc_min_axis_linearity": 0.78,
    "ground_contact_max_m": 0.30,
    "hover_min_bottom_m": 0.45,
    "hover_osc_min_span_s": 0.8,
    "hover_osc_min_path_m": 0.24,
    "hover_osc_max_straightness": 0.40,
    "hover_osc_min_reversals": 2,
    "hover_osc_min_p2p_m": 0.10,
}

_OPTIONAL_FLOAT_KEYS = ("offline_noise_floor_ivel_mps", "offline_noise_floor_wrate_mps")


def resolve_kinematics_settings(settings=None):
    resolved = dict(DEFAULT_KINEMATICS_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown kinematics filter setting: " + str(key))
        resolved[key] = value
    int_keys = ("max_history_frames", "min_subregion_points", "min_matched_subregions",
                "min_articulation_pairs", "osc_min_reversals", "hover_osc_min_reversals",
                "calib_min_samples", "calib_min_tracks", "calib_max_samples")
    for key in int_keys:
        if isinstance(resolved[key], bool) or int(resolved[key]) != resolved[key] or int(resolved[key]) < 1:
            raise ValueError(key + " must be a positive integer")
        resolved[key] = int(resolved[key])
    for key in resolved:
        if key in int_keys:
            continue
        if key in _OPTIONAL_FLOAT_KEYS:
            if resolved[key] is None:
                continue
            val = float(resolved[key])
            if not np.isfinite(val) or val <= 0.0:
                raise ValueError(key + " must be None or a positive finite number")
            resolved[key] = val
            continue
        val = float(resolved[key])
        if not np.isfinite(val):
            raise ValueError(key + " must be finite")
        resolved[key] = val
    if resolved["window_s"] <= 0.0 or resolved["max_pair_gap_s"] <= 0.0:
        raise ValueError("window_s and max_pair_gap_s must be positive")
    if (resolved["offline_noise_floor_ivel_mps"] is None) != (resolved["offline_noise_floor_wrate_mps"] is None):
        raise ValueError("offline noise floors must be given together")
    if not 0.0 < resolved["calib_quantile"] < 100.0:
        raise ValueError("calib_quantile must be within (0, 100)")
    if resolved["calib_max_samples"] < resolved["calib_min_samples"]:
        raise ValueError("calib_max_samples must be >= calib_min_samples")
    if resolved["rigid_ivel_noise_mult"] >= resolved["articulation_ivel_noise_mult"]:
        raise ValueError("rigid noise multiple must be below articulation noise multiple")
    return resolved


class KinematicsNoiseCalibrator:
    """从静止杂物轨迹（或调用方声明的空场帧）在线累积子区残差速度噪声底。"""

    def __init__(self, settings):
        self.settings = settings
        self.reset()

    def reset(self):
        self._ivel = deque(maxlen=self.settings["calib_max_samples"])
        self._wrate = deque(maxlen=self.settings["calib_max_samples"])
        self._tracks = set()

    def add(self, track_id, pair):
        self._ivel.append(float(pair["internal_vel_rms_mps"]))
        self._wrate.append(float(pair["width_rate_rms_mps"]))
        self._tracks.add(track_id)

    def floor(self):
        cfg = self.settings
        online_ready = (len(self._ivel) >= cfg["calib_min_samples"]
                        and len(self._tracks) >= cfg["calib_min_tracks"])
        if online_ready:
            q = cfg["calib_quantile"]
            return {
                "calibrated": True,
                "source": "online_static_clutter",
                "ivel_floor_mps": max(cfg["calib_min_floor_mps"], float(np.percentile(self._ivel, q))),
                "wrate_floor_mps": max(cfg["calib_min_floor_mps"], float(np.percentile(self._wrate, q))),
                "samples": len(self._ivel),
                "tracks": len(self._tracks),
            }
        if cfg["offline_noise_floor_ivel_mps"] is not None:
            return {
                "calibrated": True,
                "source": "offline_tuning_set",
                "ivel_floor_mps": cfg["offline_noise_floor_ivel_mps"],
                "wrate_floor_mps": cfg["offline_noise_floor_wrate_mps"],
                "samples": len(self._ivel),
                "tracks": len(self._tracks),
            }
        return {
            "calibrated": False,
            "source": None,
            "ivel_floor_mps": None,
            "wrate_floor_mps": None,
            "samples": len(self._ivel),
            "tracks": len(self._tracks),
        }


def _extract_snapshot(xyz, basis=None, offset_m=0.0, min_subregion_points=8):
    """提取单帧点云的质心、三段/左右子区质心与分段水平宽度。"""
    if basis is not None:
        g_norm, axis_u, axis_v = basis
        u = xyz @ axis_u
        v = xyz @ axis_v
        h = xyz @ g_norm + float(offset_m)
    else:
        u = xyz[:, 0]
        v = xyz[:, 1]
        h = xyz[:, 2]

    cu = float(np.median(u))
    cv = float(np.median(v))
    ch = float(np.median(h))
    center = np.array([cu, cv, ch], dtype=np.float64)

    h_lo = float(np.percentile(h, 5.0))
    h_hi = float(np.percentile(h, 95.0))
    h_span = max(h_hi - h_lo, 1e-3)
    rel_h = (h - h_lo) / h_span

    masks = {
        "lower": rel_h < 0.35,
        "mid": (rel_h >= 0.35) & (rel_h < 0.70),
        "upper": rel_h >= 0.70,
        "u_neg": u < cu,
        "u_pos": u >= cu,
        "v_neg": v < cv,
        "v_pos": v >= cv,
    }
    sub_centers = {}
    band_widths = {}
    for name, mask in masks.items():
        if int(mask.sum()) >= min_subregion_points:
            sub_centers[name] = np.array([
                float(np.median(u[mask])),
                float(np.median(v[mask])),
                float(np.median(h[mask])),
            ], dtype=np.float64)
            if name in ("lower", "mid", "upper"):
                su = float(np.percentile(u[mask], 95.0) - np.percentile(u[mask], 5.0))
                sv = float(np.percentile(v[mask], 95.0) - np.percentile(v[mask], 5.0))
                band_widths[name] = max(su, sv)

    return {
        "center": center,
        "bottom_m": h_lo if basis is not None else None,
        "min_h_m": float(np.min(h)) if basis is not None else None,
        "top_m": h_hi if basis is not None else None,
        "sub_centers": sub_centers,
        "band_widths": band_widths,
        "has_ground": basis is not None,
    }


def _pair_articulation(prev_snap, cur_snap, dt, min_matched):
    """扣除整体平移后计算相邻两帧子区残差速度与层宽形变率。"""
    dc = cur_snap["center"] - prev_snap["center"]
    global_speed = float(np.linalg.norm(dc)) / dt
    horiz_speed = float(math.hypot(dc[0], dc[1])) / dt

    residual_speeds = []
    for name, cur_c in cur_snap["sub_centers"].items():
        prev_c = prev_snap["sub_centers"].get(name)
        if prev_c is None:
            continue
        res = (cur_c - prev_c) - dc
        residual_speeds.append(float(np.linalg.norm(res)) / dt)

    width_rates = []
    for name, cur_w in cur_snap["band_widths"].items():
        prev_w = prev_snap["band_widths"].get(name)
        if prev_w is None:
            continue
        width_rates.append(abs(cur_w - prev_w) / dt)

    upper_lower_rate = None
    if ("upper" in cur_snap["sub_centers"] and "lower" in cur_snap["sub_centers"]
            and "upper" in prev_snap["sub_centers"] and "lower" in prev_snap["sub_centers"]):
        cur_rel = cur_snap["sub_centers"]["upper"] - cur_snap["sub_centers"]["lower"]
        prev_rel = prev_snap["sub_centers"]["upper"] - prev_snap["sub_centers"]["lower"]
        upper_lower_rate = float(np.linalg.norm(cur_rel - prev_rel)) / dt

    if len(residual_speeds) < min_matched:
        return None
    res_arr = np.asarray(residual_speeds, dtype=np.float64)
    return {
        "global_speed_mps": global_speed,
        "horiz_speed_mps": horiz_speed,
        "internal_vel_rms_mps": float(np.sqrt(np.mean(res_arr * res_arr))),
        "internal_vel_std_mps": float(np.std(res_arr)),
        "width_rate_rms_mps": (float(np.sqrt(np.mean(np.square(width_rates))))
                               if width_rates else 0.0),
        "upper_lower_rate_mps": upper_lower_rate,
        "matched_subregions": len(residual_speeds),
    }


class HumanKinematicsFilter:
    """多轨迹因果非刚体运动与周期振荡分析器（r2：噪声底标定 + 相对门限）。"""

    def __init__(self, settings=None):
        self.settings = resolve_kinematics_settings(settings)
        self.calibrator = KinematicsNoiseCalibrator(self.settings)
        self._calib_key = None
        self.reset()

    def reset(self, clear_calibration=False):
        """清空轨迹历史；噪声底只在显式要求或绑定/网格/地面换代时清空。"""
        self._key = None
        self._last_stamp = None
        self._last_frame = None
        self._tracks = {}
        if clear_calibration:
            self.calibrator.reset()
            self._calib_key = None

    def _clear_all(self):
        self._tracks.clear()

    def noise_floor(self):
        return self.calibrator.floor()

    def update(self, frame, record, ground=None, stamp_s=None, frame_index=None,
               clutter_track_ids=None, empty_scene=False):
        """更新本帧所有实测轨迹的非刚体与振荡证据，返回 {track_id: evidence}。

        ``clutter_track_ids``：调用方判定的“非目标且 prior 不兼容”的杂物轨迹；其中近静止的
        相邻帧对用于在线标定噪声底。``empty_scene=True`` 表示调用方显式声明本帧为空场，
        此时全部近静止实测轨迹都可用于标定。
        """
        stamp = float(record["time_s"] if stamp_s is None else stamp_s)
        fidx = int(record["frame"] if frame_index is None else frame_index)
        if not math.isfinite(stamp):
            self.reset()
            raise ValueError("finite timestamp required for kinematics filter")

        plane = bound_ground(frame, ground) if ground is not None else None
        basis = ground_plane_basis(plane) if plane is not None else None
        offset_m = float(plane["offset_m"]) if plane is not None else 0.0
        ground_key = (None if plane is None
                      else (tuple(round(float(v), 6) for v in plane["normal"]),
                            round(offset_m, 6)))
        key = (frame.binding, frame.grid.sha256, record.get("generation"), ground_key)
        calib_key = (frame.binding, frame.grid.sha256, ground_key)
        if calib_key != self._calib_key:
            self.calibrator.reset()
            self._calib_key = calib_key
        clutter = set(clutter_track_ids or ())

        reset_reason = None
        if self._last_stamp is not None:
            if key != self._key:
                reset_reason = "context_or_ground_changed"
            elif stamp <= self._last_stamp or fidx <= self._last_frame:
                reset_reason = "nonincreasing_clock_or_frame"
            elif stamp - self._last_stamp > self.settings["reset_gap_s"]:
                reset_reason = "stream_gap"
        if reset_reason is not None:
            self._clear_all()
        self._key = key
        self._last_stamp = stamp
        self._last_frame = fidx

        # 清理超时轨迹
        timeout = self.settings["miss_timeout_s"]
        for tid in list(self._tracks.keys()):
            if stamp - self._tracks[tid]["last_stamp"] > timeout:
                del self._tracks[tid]

        cfg = self.settings
        touched = []
        for tr in record.get("tracks") or []:
            tid = tr.get("track_id")
            if tid is None:
                continue
            observed = (bool(tr.get("observed"))
                        and not bool(tr.get("position_predicted"))
                        and bool(tr.get("source_rows")))
            if not observed:
                continue

            rows = np.asarray(tr["source_rows"], dtype=np.int64)
            xyz = frame.xyz[rows].astype(np.float64)
            snap = _extract_snapshot(
                xyz, basis=basis, offset_m=offset_m,
                min_subregion_points=cfg["min_subregion_points"],
            )

            state = self._tracks.get(tid)
            if state is None:
                state = {
                    "last_stamp": stamp,
                    "last_snap": None,
                    "traj": deque(maxlen=cfg["max_history_frames"]),
                    "pairs": deque(maxlen=cfg["max_history_frames"]),
                }
                self._tracks[tid] = state

            prev_snap = state["last_snap"]
            dt = stamp - state["last_stamp"] if prev_snap is not None else None
            if prev_snap is not None and dt is not None and 0.0 < dt <= cfg["max_pair_gap_s"]:
                pair = _pair_articulation(prev_snap, snap, dt, cfg["min_matched_subregions"])
                if pair is not None:
                    pair["stamp_s"] = stamp
                    state["pairs"].append(pair)
                    if ((empty_scene or tid in clutter)
                            and pair["horiz_speed_mps"] < cfg["calib_static_max_hspeed_mps"]):
                        self.calibrator.add(tid, pair)
            elif prev_snap is not None and dt is not None and dt > cfg["max_pair_gap_s"]:
                # 跨短缺口不捏造帧间速度，但清空不连续的轨迹段，避免误算振荡。
                state["traj"].clear()
                state["pairs"].clear()

            state["last_stamp"] = stamp
            state["last_snap"] = snap
            state["traj"].append((
                stamp,
                float(snap["center"][0]),
                float(snap["center"][1]),
                float(snap["center"][2]),
                snap["bottom_m"],
                snap["min_h_m"],
            ))

            # 滑窗裁剪（3–5 s）
            win = cfg["window_s"]
            while state["traj"] and stamp - state["traj"][0][0] > win:
                state["traj"].popleft()
            while state["pairs"] and stamp - state["pairs"][0]["stamp_s"] > win:
                state["pairs"].popleft()

            touched.append(tid)

        floor = self.calibrator.floor()
        results = {}
        for tid in touched:
            results[tid] = self._summarize_track(self._tracks[tid], reset_reason, floor)
        return results

    def _summarize_track(self, state, reset_reason, floor):
        cfg = self.settings
        traj = list(state["traj"])
        pairs = list(state["pairs"])
        span_s = float(traj[-1][0] - traj[0][0]) if len(traj) >= 2 else 0.0

        # 1. 非刚体内部运动汇总（门限 = 噪声底倍数；未标定时两类判据均关闭）
        pair_count = len(pairs)
        mean_speed = float(np.mean([p["global_speed_mps"] for p in pairs])) if pair_count else 0.0
        med_int_vel = float(np.median([p["internal_vel_rms_mps"] for p in pairs])) if pair_count else None
        med_int_std = float(np.median([p["internal_vel_std_mps"] for p in pairs])) if pair_count else None
        med_w_rate = float(np.median([p["width_rate_rms_mps"] for p in pairs])) if pair_count else None

        articulation_ready = pair_count >= cfg["min_articulation_pairs"]
        calibrated = bool(floor["calibrated"])
        rigid_moving_object = False
        articulation_supported = False
        ivel_ratio = None
        wrate_ratio = None
        if calibrated and med_int_vel is not None and med_w_rate is not None:
            ivel_ratio = med_int_vel / floor["ivel_floor_mps"]
            wrate_ratio = med_w_rate / floor["wrate_floor_mps"]
        if articulation_ready and ivel_ratio is not None:
            if (mean_speed >= cfg["rigid_active_speed_min_mps"]
                    and ivel_ratio <= cfg["rigid_ivel_noise_mult"]
                    and wrate_ratio <= cfg["rigid_wrate_noise_mult"]):
                rigid_moving_object = True
            elif (ivel_ratio >= cfg["articulation_ivel_noise_mult"]
                  and med_int_vel <= cfg["articulation_max_internal_vel_mps"]
                  and (wrate_ratio >= cfg["articulation_wrate_noise_mult"]
                       or ivel_ratio >= cfg["articulation_strong_ivel_noise_mult"])):
                articulation_supported = True

        # 2. 3–5 s 窗口周期振荡与悬空滞留汇总（3 帧因果滑动平均滤除 1–2 cm 采样微抖）
        raw_uv = np.array([[p[1], p[2]] for p in traj], dtype=np.float64)
        if len(raw_uv) >= 3:
            smooth_uv = raw_uv.copy()
            smooth_uv[1:-1] = (raw_uv[:-2] + raw_uv[1:-1] + raw_uv[2:]) / 3.0
            smooth_uv[-1] = (raw_uv[-3] + raw_uv[-2] + raw_uv[-1]) / 3.0
        else:
            smooth_uv = raw_uv

        path_len = 0.0
        reversals = 0
        prev_dir = None
        for i in range(1, len(smooth_uv)):
            step = smooth_uv[i] - smooth_uv[i - 1]
            step_len = float(np.linalg.norm(step))
            path_len += step_len
            if step_len >= cfg["osc_min_step_m"]:
                cur_dir = step / step_len
                if prev_dir is not None:
                    if float(cur_dir @ prev_dir) <= cfg["osc_reversal_cos_max"]:
                        reversals += 1
                prev_dir = cur_dir

        net_disp = float(np.linalg.norm(smooth_uv[-1] - smooth_uv[0])) if len(smooth_uv) >= 2 else 0.0
        straightness = net_disp / max(path_len, 1e-6) if path_len > 1e-6 else 1.0
        centroid_uv = np.mean(smooth_uv, axis=0)
        centered_uv = smooth_uv - centroid_uv
        stay_radius = float(np.max(np.linalg.norm(centered_uv, axis=1))) if len(smooth_uv) else 0.0
        reversal_rate_hz = reversals / max(span_s, 1e-6) if span_s > 0.0 else 0.0

        # 1D 主摆动轴线性度与峰-峰摆幅（真实摆锤/窗帘/风扇高度沿单轴往复；蹲姿微抖呈各向同性噪声）
        axis_linearity = 0.0
        p2p_m = 0.0
        if len(smooth_uv) >= 4:
            cov_uv = (centered_uv.T @ centered_uv) / float(len(smooth_uv))
            if np.isfinite(cov_uv).all():
                evals, evecs = np.linalg.eigh(cov_uv)
                ev_sum = float(evals[0] + evals[1])
                if ev_sum > 1e-9:
                    axis_linearity = float(evals[1] / ev_sum)
                    proj_major = centered_uv @ evecs[:, 1]
                    p2p_m = float(proj_major.max() - proj_major.min())

        bottoms = [p[4] for p in traj if p[4] is not None]
        mean_bottom = float(np.mean(bottoms)) if bottoms else None
        min_heights = [p[5] for p in traj if p[5] is not None]
        window_min_h = float(min(min_heights)) if min_heights else None
        # r2：“与地面无接触”= 窗内每一帧簇最低点都高于 ground_contact_max_m；地面未知时不判悬空。
        no_ground_contact = bool(
            min_heights and len(min_heights) == len(traj)
            and window_min_h > cfg["ground_contact_max_m"]
        )
        hovering = bool(no_ground_contact and mean_bottom is not None
                        and mean_bottom >= cfg["hover_min_bottom_m"])

        is_oscillating = bool(
            span_s >= cfg["osc_min_span_s"]
            and path_len >= cfg["osc_min_path_m"]
            and straightness <= cfg["osc_max_straightness"]
            and reversals >= cfg["osc_min_reversals"]
            and reversal_rate_hz >= cfg["osc_min_reversal_rate_hz"]
            and stay_radius <= cfg["osc_max_stay_radius_m"]
            and p2p_m >= cfg["osc_min_p2p_m"]
            and axis_linearity >= cfg["osc_min_axis_linearity"]
        )
        is_suspended_oscillator = bool(
            hovering
            and span_s >= cfg["hover_osc_min_span_s"]
            and path_len >= cfg["hover_osc_min_path_m"]
            and straightness <= cfg["hover_osc_max_straightness"]
            and reversals >= cfg["hover_osc_min_reversals"]
            and p2p_m >= cfg["hover_osc_min_p2p_m"]
            and axis_linearity >= cfg["osc_min_axis_linearity"]
        )

        reasons = []
        if rigid_moving_object:
            reasons.append("soft_rigid_moving_object")
        if is_oscillating:
            reasons.append("soft_periodic_oscillation")
        if is_suspended_oscillator:
            reasons.append("soft_suspended_oscillator")

        return {
            "available": True,
            "reset_reason": reset_reason,
            "samples": len(traj),
            "pair_samples": pair_count,
            "window_span_s": round(span_s, 4),
            "mean_speed_mps": round(mean_speed, 4),
            "median_internal_vel_rms_mps": None if med_int_vel is None else round(med_int_vel, 4),
            "median_internal_vel_std_mps": None if med_int_std is None else round(med_int_std, 4),
            "median_width_rate_mps": None if med_w_rate is None else round(med_w_rate, 4),
            "noise_calibrated": calibrated,
            "noise_floor_source": floor["source"],
            "noise_floor_ivel_mps": (None if floor["ivel_floor_mps"] is None
                                     else round(floor["ivel_floor_mps"], 4)),
            "noise_floor_wrate_mps": (None if floor["wrate_floor_mps"] is None
                                      else round(floor["wrate_floor_mps"], 4)),
            "noise_calib_samples": int(floor["samples"]),
            "noise_calib_tracks": int(floor["tracks"]),
            "internal_vel_noise_ratio": None if ivel_ratio is None else round(ivel_ratio, 3),
            "width_rate_noise_ratio": None if wrate_ratio is None else round(wrate_ratio, 3),
            "articulation_ready": articulation_ready,
            "articulation_supported": articulation_supported,
            "rigid_moving_object": rigid_moving_object,
            "path_len_m": round(path_len, 4),
            "net_disp_m": round(net_disp, 4),
            "straightness": round(straightness, 4),
            "direction_reversals": int(reversals),
            "reversal_rate_hz": round(reversal_rate_hz, 4),
            "stay_radius_m": round(stay_radius, 4),
            "osc_p2p_m": round(p2p_m, 4),
            "osc_axis_linearity": round(axis_linearity, 4),
            "mean_bottom_m": None if mean_bottom is None else round(mean_bottom, 4),
            "window_min_height_m": None if window_min_h is None else round(window_min_h, 4),
            "no_ground_contact": no_ground_contact,
            "hovering": hovering,
            "is_oscillating": is_oscillating,
            "is_suspended_oscillator": is_suspended_oscillator,
            "rejection_reasons": reasons,
            "semantic": "UNKNOWN",
        }
