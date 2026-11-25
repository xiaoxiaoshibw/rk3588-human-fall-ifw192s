"""Log-Odds 证据累积与迟滞双门限人体置信度状态机 + 统一物理评估器（纯雷达）。

融合 4 类正交物理证据：
1. `human_prior.describe_physical_v1`（10 层归一化剖面 + 三姿态兼容 + 悬空粘连/平面拒识）
2. `range_normals`（水平方位角法向熵 + 确定性单/双平面内点占比 + 粗糙度）
3. `human_kinematics_filter`（非刚体内部残差运动 vs 刚体平移 + 3–5 s 周期振荡/悬空）
4. `full_body_recovery`（核心 -> 肢体局部低阈值法向约束完整回收）

状态与语义诚实声明：
- 三态：`UNKNOWN` / `CANDIDATE_HUMAN` / `CONFIRMED_HUMAN`（高入低出迟滞双门限）。
- `CONFIRMED_HUMAN` 表示多维物理与运动学证据累积通过，**不等于独立人体真值认证**；
  输出字段始终保留 `semantic_truth='UNKNOWN'` 与完整可审计原因码。
- 所有时间/绑定/标定/地面换代或非有限时钟立即清空历史。
"""

import math
import time

import numpy as np

try:  # pragma: no cover - import shim
    from .full_body_recovery import recover_full_body
    from .human_kinematics_filter import HumanKinematicsFilter
    from .human_prior import (
        CLASS_FRAGMENT,
        CLASS_HANGING_ADHESION,
        CLASS_LYING,
        CLASS_OTHER,
        CLASS_PLANAR,
        CLASS_SITTING,
        CLASS_STANDING,
        CLASS_UNKNOWN,
        describe_physical_v1,
    )
    from .range_features import bound_ground
    from .range_normals import estimate_grid_normals
except ImportError:  # pragma: no cover
    from full_body_recovery import recover_full_body
    from human_kinematics_filter import HumanKinematicsFilter
    from human_prior import (
        CLASS_FRAGMENT,
        CLASS_HANGING_ADHESION,
        CLASS_LYING,
        CLASS_OTHER,
        CLASS_PLANAR,
        CLASS_SITTING,
        CLASS_STANDING,
        CLASS_UNKNOWN,
        describe_physical_v1,
    )
    from range_features import bound_ground
    from range_normals import estimate_grid_normals


STATE_UNKNOWN = "UNKNOWN"
STATE_CANDIDATE = "CANDIDATE_HUMAN"
STATE_CONFIRMED = "CONFIRMED_HUMAN"

DEFAULT_BELIEF_SETTINGS = {
    "log_odds_min": -6.0,
    # r2：上限由 8.0 降到 5.0，避免长时间累积后对否决/不兼容证据反应过慢。
    "log_odds_max": 5.0,
    "candidate_enter_log_odds": 1.2,
    "candidate_min_compatible_frames": 2,
    "confirm_enter_log_odds": 3.2,
    "confirm_min_compatible_frames": 5,
    "confirm_min_span_s": 0.45,
    "confirm_exit_log_odds": 1.0,
    "candidate_exit_log_odds": -0.5,
    # r2：任一硬否决帧把 Log-Odds 封顶到该值，且 CONFIRMED 立即降为 CANDIDATE。
    "veto_log_odds_cap": 1.0,
    "miss_timeout_s": 1.5,
    "reset_gap_s": 2.0,
    # 各通道单帧 Log-Odds 增量
    "delta_standing": 0.45,
    "delta_sitting_lying": 0.35,
    "delta_good_profile_bonus": 0.15,
    "delta_fragment": -1.50,
    "delta_planar": -2.20,
    "delta_hanging_adhesion": -2.50,
    "delta_not_compatible": -1.20,
    "delta_curved_strong": 0.40,
    "delta_curved_moderate": 0.15,
    "delta_normal_planar_penalty": -1.80,
    "delta_nonrigid_bonus": 0.45,
    "delta_rigid_moving_penalty": -1.00,
    # r2：振荡改为软惩罚（不触发否决）；仅“全窗无地面接触”的悬空振荡使用较重软惩罚。
    "delta_oscillation_penalty": -0.60,
    "delta_suspended_oscillation_penalty": -1.20,
    # 法向加分/罚分门限
    "curved_strong_entropy_min": 0.42,
    "curved_strong_plane_max": 0.55,
    "curved_mod_entropy_min": 0.28,
    "curved_mod_plane_max": 0.68,
    "normal_planar_single_min": 0.78,
    "normal_planar_dual_min": 0.88,
    "normal_planar_entropy_max": 0.40,
}


def resolve_belief_settings(settings=None):
    resolved = dict(DEFAULT_BELIEF_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown human belief setting: " + str(key))
        resolved[key] = value
    int_keys = ("candidate_min_compatible_frames", "confirm_min_compatible_frames")
    for key in int_keys:
        if isinstance(resolved[key], bool) or int(resolved[key]) != resolved[key] or int(resolved[key]) < 1:
            raise ValueError(key + " must be a positive integer")
        resolved[key] = int(resolved[key])
    for key in resolved:
        if key in int_keys:
            continue
        val = float(resolved[key])
        if not np.isfinite(val):
            raise ValueError(key + " must be finite")
        resolved[key] = val
    if resolved["log_odds_max"] <= resolved["log_odds_min"]:
        raise ValueError("log_odds_max must exceed log_odds_min")
    if resolved["confirm_enter_log_odds"] < resolved["confirm_exit_log_odds"]:
        raise ValueError("confirm_enter_log_odds must be >= confirm_exit_log_odds")
    if resolved["confirm_enter_log_odds"] > resolved["log_odds_max"]:
        raise ValueError("confirm_enter_log_odds must be <= log_odds_max")
    if resolved["veto_log_odds_cap"] >= resolved["confirm_enter_log_odds"]:
        raise ValueError("veto_log_odds_cap must be below confirm_enter_log_odds")
    return resolved


def _sigmoid(x):
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


class HumanBeliefTracker:
    """多轨迹 Log-Odds 证据累积与迟滞状态机。"""

    def __init__(self, settings=None):
        self.settings = resolve_belief_settings(settings)
        self.reset()

    def reset(self):
        self._key = None
        self._last_stamp = None
        self._last_frame = None
        self._tracks = {}

    def update_frame(self, context_key, stamp_s, frame_index, track_observations):
        """更新本帧全部轨迹的 Log-Odds 与三态置信状态。

        `track_observations`: `{track_id: {"observed": bool, "source_rows": list,
                                           "prior": dict|None, "kinematics": dict|None}}`
        """
        stamp = float(stamp_s)
        fidx = int(frame_index)
        if not math.isfinite(stamp):
            self.reset()
            raise ValueError("finite timestamp required for human belief tracker")

        reset_reason = None
        if self._last_stamp is not None:
            if context_key != self._key:
                reset_reason = "context_or_calibration_changed"
            elif stamp <= self._last_stamp or fidx <= self._last_frame:
                reset_reason = "nonincreasing_clock_or_frame"
            elif stamp - self._last_stamp > self.settings["reset_gap_s"]:
                reset_reason = "stream_gap"
        if reset_reason is not None:
            self._tracks.clear()
        self._key = context_key
        self._last_stamp = stamp
        self._last_frame = fidx

        cfg = self.settings
        for tid in list(self._tracks.keys()):
            if stamp - self._tracks[tid]["last_observed"] > cfg["miss_timeout_s"]:
                del self._tracks[tid]

        out = {}
        for tid, obs in sorted(track_observations.items()):
            observed = bool(obs.get("observed"))
            state = self._tracks.get(tid)
            if not observed:
                if state is not None:
                    # 缺测期间冻结 Log-Odds，绝不凭空累加正面证据。
                    out[tid] = self._export_state(
                        tid, state, observed=False, source_rows=[],
                        deltas={"geom": 0.0, "normal": 0.0, "kin": 0.0, "total": 0.0},
                        evidence_codes=["frozen_during_unobserved_frame"],
                        rejection_reasons=[], veto_active=False, reset_reason=reset_reason,
                    )
                continue

            if state is None:
                state = {
                    "log_odds": 0.0,
                    "state": STATE_UNKNOWN,
                    "first_observed": stamp,
                    "last_observed": stamp,
                    "observed_frames": 0,
                    "compatible_frames": 0,
                    "veto_frames": 0,
                }
                self._tracks[tid] = state

            prior = obs.get("prior") or {}
            kin = obs.get("kinematics") or {}
            nf = (prior.get("normal_features") or {}) if prior else {}
            prof = (prior.get("normalized_profile") or {}) if prior else {}

            d_geom = 0.0
            d_norm = 0.0
            d_kin = 0.0
            ev_codes = []
            rej_codes = []
            veto = False

            p_class = prior.get("class", CLASS_UNKNOWN)
            if p_class == CLASS_STANDING:
                d_geom += cfg["delta_standing"]
                ev_codes.append("prior_standing_compatible")
            elif p_class in (CLASS_SITTING, CLASS_LYING):
                d_geom += cfg["delta_sitting_lying"]
                ev_codes.append("prior_" + p_class)
            elif p_class == CLASS_FRAGMENT:
                d_geom += cfg["delta_fragment"]
                rej_codes.append("prior_fragment")
                veto = True
            elif p_class == CLASS_PLANAR:
                d_geom += cfg["delta_planar"]
                rej_codes.append(prior.get("reason") or "prior_planar_structure")
                veto = True
            elif p_class == CLASS_HANGING_ADHESION:
                d_geom += cfg["delta_hanging_adhesion"]
                rej_codes.append(prior.get("reason") or "prior_hanging_or_adhesion")
                veto = True
            elif p_class == CLASS_OTHER:
                d_geom += cfg["delta_not_compatible"]
                rej_codes.append(prior.get("reason") or "prior_not_compatible")
            else:
                ev_codes.append("prior_unknown_neutral")

            if prior.get("compatible") and prof:
                if prof.get("vertical_fill", 0.0) >= 0.70 and prof.get("min_third_ratio", 0.0) >= 0.10:
                    d_geom += cfg["delta_good_profile_bonus"]
                    ev_codes.append("profile_balanced_vertical_support")

            # 表面法向通道
            if nf.get("available"):
                sp = nf["single_plane_inlier_ratio"]
                dp = nf["dual_plane_inlier_ratio"]
                ent = nf["normal_azimuth_entropy"]
                s_ent = nf["normal_sphere_entropy"]
                if (sp >= cfg["normal_planar_single_min"] and ent <= cfg["normal_planar_entropy_max"]) or (
                        dp >= cfg["normal_planar_dual_min"] and ent <= cfg["normal_planar_entropy_max"]):
                    d_norm += cfg["delta_normal_planar_penalty"]
                    rej_codes.append("surface_normal_planar_penalty")
                    veto = True
                elif (max(ent, s_ent) >= cfg["curved_strong_entropy_min"]
                      and sp <= cfg["curved_strong_plane_max"]):
                    d_norm += cfg["delta_curved_strong"]
                    ev_codes.append("surface_curved_strong")
                elif (max(ent, s_ent) >= cfg["curved_mod_entropy_min"]
                      and sp <= cfg["curved_mod_plane_max"]):
                    d_norm += cfg["delta_curved_moderate"]
                    ev_codes.append("surface_curved_moderate")

            # 非刚体与周期振荡通道
            # r2：振荡/悬空振荡只做软惩罚，不触发否决；刚体/非刚体判据只在噪声底已标定时由
            # 运动学模块给出（未标定时两者恒为 False，非刚体加分自动关闭）。
            if kin.get("available"):
                if kin.get("is_suspended_oscillator"):
                    d_kin += cfg["delta_suspended_oscillation_penalty"]
                    rej_codes.append("soft_suspended_oscillator")
                elif kin.get("is_oscillating"):
                    d_kin += cfg["delta_oscillation_penalty"]
                    rej_codes.append("soft_periodic_oscillation")
                if kin.get("rigid_moving_object"):
                    # r2：调参集 qiandao 中直立移动目标仍有 9 帧落入 <=0.8x 噪声底的刚体判据，
                    # 且没有真实刚体负例可证明收益，故刚体平移只做软惩罚、不否决。
                    d_kin += cfg["delta_rigid_moving_penalty"]
                    rej_codes.append("soft_rigid_moving_object")
                elif kin.get("articulation_supported"):
                    d_kin += cfg["delta_nonrigid_bonus"]
                    ev_codes.append("nonrigid_articulation_supported")
                elif not kin.get("noise_calibrated"):
                    ev_codes.append("kinematics_uncalibrated_neutral")

            delta_total = d_geom + d_norm + d_kin
            new_lo = max(cfg["log_odds_min"], min(cfg["log_odds_max"], state["log_odds"] + delta_total))
            if veto:
                new_lo = min(new_lo, cfg["veto_log_odds_cap"])
            state["log_odds"] = new_lo
            state["last_observed"] = stamp
            state["observed_frames"] += 1
            if prior.get("compatible") and not veto:
                state["compatible_frames"] += 1
            if veto:
                state["veto_frames"] += 1

            span_s = stamp - state["first_observed"]
            cur_state = state["state"]
            if cur_state == STATE_UNKNOWN:
                if (not veto
                        and new_lo >= cfg["candidate_enter_log_odds"]
                        and state["compatible_frames"] >= cfg["candidate_min_compatible_frames"]):
                    cur_state = STATE_CANDIDATE
            if cur_state == STATE_CANDIDATE:
                if (not veto
                        and new_lo >= cfg["confirm_enter_log_odds"]
                        and state["compatible_frames"] >= cfg["confirm_min_compatible_frames"]
                        and span_s >= cfg["confirm_min_span_s"]):
                    cur_state = STATE_CONFIRMED
                elif new_lo < cfg["candidate_exit_log_odds"]:
                    cur_state = STATE_UNKNOWN
            elif cur_state == STATE_CONFIRMED:
                if new_lo < cfg["candidate_exit_log_odds"]:
                    cur_state = STATE_UNKNOWN
                elif veto or new_lo < cfg["confirm_exit_log_odds"]:
                    # r2：已确认状态遇到硬否决直接降为候选（Log-Odds 已同时封顶）。
                    cur_state = STATE_CANDIDATE
            state["state"] = cur_state

            out[tid] = self._export_state(
                tid, state, observed=True, source_rows=list(obs.get("source_rows") or []),
                deltas={
                    "geom": round(d_geom, 4),
                    "normal": round(d_norm, 4),
                    "kin": round(d_kin, 4),
                    "total": round(delta_total, 4),
                },
                evidence_codes=ev_codes,
                rejection_reasons=rej_codes,
                veto_active=veto,
                reset_reason=reset_reason,
            )

        return out

    def _export_state(self, tid, state, *, observed, source_rows, deltas,
                      evidence_codes, rejection_reasons, veto_active, reset_reason):
        lo = float(state["log_odds"])
        return {
            "track_id": tid,
            "belief_state": state["state"],
            "confirmed_physical_human": state["state"] == STATE_CONFIRMED,
            "log_odds": round(lo, 4),
            "belief_score": round(_sigmoid(lo), 4),
            "observed": observed,
            "source_rows": source_rows,
            "observed_frames": int(state["observed_frames"]),
            "compatible_frames": int(state["compatible_frames"]),
            "veto_frames": int(state["veto_frames"]),
            "veto_active": bool(veto_active),
            "deltas": deltas,
            "evidence_codes": list(evidence_codes),
            "rejection_reasons": list(rejection_reasons),
            "reset_reason": reset_reason,
            "semantic_truth": "UNKNOWN",
            "definition": "multi_evidence_physical_kinematic_belief_not_ground_truth",
        }


# r2 评估器阶段异常原因码（任何一个阶段失败都只降级本阶段输出，绝不中断原跟踪/跌倒链）。
STAGE_ERROR_CODES = {
    "normals": "normals_stage_exception",
    "prior": "prior_stage_exception",
    "kinematics": "kinematics_stage_exception",
    "belief": "belief_stage_exception",
    "recovery": "recovery_stage_exception",
}
REVISION = "physical_v1_r2"


def _error_entry(stage, exc, track_id=None):
    entry = {
        "stage": stage,
        "code": STAGE_ERROR_CODES[stage],
        "error_type": type(exc).__name__,
        "message": str(exc)[:240],
    }
    if track_id is not None:
        entry["track_id"] = track_id
    return entry


def _observed(tr):
    return (tr.get("track_id") is not None
            and bool(tr.get("observed"))
            and not bool(tr.get("position_predicted"))
            and bool(tr.get("source_rows")))


class HumanPhysicalEvaluator:
    """阶段 1 完整物理感知链协调器（法向 + 10层剖面 + 非刚体/振荡 + 局部完整回收 + Log-Odds）。

    作为显式命名变体 `human_physical_v1` 挂载在 `RangeRuntime` 或独立离线对照脚本上运行，
    绝不静默篡改原有默认跟踪器/跌倒状态机契约。r2：每个阶段独立异常保护并输出原因码；
    运动学噪声底由“非目标且 prior 不兼容”的静止杂物轨迹在线标定。
    """

    def __init__(self, *, normal_settings=None, prior_v1_settings=None,
                 kinematics_settings=None, recovery_settings=None,
                 belief_settings=None):
        self.normal_settings = normal_settings
        self.prior_v1_settings = prior_v1_settings
        self.recovery_settings = recovery_settings
        self.kinematics = HumanKinematicsFilter(kinematics_settings)
        self.belief = HumanBeliefTracker(belief_settings)

    def reset(self, clear_calibration=False):
        self.kinematics.reset(clear_calibration=clear_calibration)
        self.belief.reset()

    def _normals_rois(self, frame, observed_tracks, target_tid, target_rows):
        h, w = frame.grid.shape
        valid_cells = np.flatnonzero(frame.valid.ravel())
        row_to_cell = np.full(len(frame.xyz), -1, dtype=np.int32)
        if valid_cells.size:
            row_to_cell[frame.source_rows.ravel()[valid_cells]] = valid_cells.astype(np.int32)

        def box_for(rows, with_recovery_pad):
            arr = np.asarray(rows, dtype=np.int64)
            arr = arr[(arr >= 0) & (arr < len(frame.xyz))]
            if not arr.size:
                return None
            cells = row_to_cell[arr]
            cells = cells[cells >= 0]
            if not cells.size:
                return None
            cy = cells // w
            cx = cells % w
            y0, y1 = int(cy.min()), int(cy.max()) + 1
            x0, x1 = int(cx.min()), int(cx.max()) + 1
            if with_recovery_pad:
                pad_y = max(28, int(0.50 * (y1 - y0)) + 4)
                pad_x = max(24, int(0.50 * (x1 - x0)) + 4)
                return (max(0, y0 - pad_y), min(h, y1 + pad_y),
                        max(0, x0 - pad_x), min(w, x1 + pad_x))
            return (y0, y1, x0, x1)

        boxes = []
        target_box = box_for(target_rows, with_recovery_pad=True) if target_rows else None
        if target_box is not None:
            boxes.append(target_box)

        for tr in observed_tracks:
            if tr.get("track_id") == target_tid and target_box is not None:
                continue
            b = box_for(tr["source_rows"], with_recovery_pad=False)
            if b is None:
                continue
            if (target_box is not None
                    and b[0] >= target_box[0] and b[1] <= target_box[1]
                    and b[2] >= target_box[2] and b[3] <= target_box[3]):
                continue
            boxes.append(b)
        return boxes

    def evaluate(self, frame, record, *, background=None, ground=None, empty_scene=False):
        t0 = time.perf_counter()
        errors = []
        plane = bound_ground(frame, ground) if ground is not None else None
        max_jump = (self.normal_settings or {}).get("max_edge_jump_m", 0.25)

        observed_tracks = [tr for tr in (record.get("tracks") or []) if _observed(tr)]
        target_tid = record.get("target_track_id")
        target_rows = record.get("target_source_rows") or []

        # 1. 表面法向：仅目标带回收窗边距，其余轨迹用各自紧凑 ROI（与全图法向逐位等价，防止散落杂物撑满整图）
        grid_normals = None
        if observed_tracks or target_rows:
            try:
                roi_bboxes = self._normals_rois(frame, observed_tracks, target_tid, target_rows)
                if roi_bboxes:
                    grid_normals = estimate_grid_normals(
                        frame, max_edge_jump_m=max_jump, roi_bboxes=roi_bboxes,
                    )
            except Exception as exc:  # noqa: BLE001 - 可选遥测链必须隔离异常
                errors.append(_error_entry("normals", exc))
                grid_normals = None
        t_norm = time.perf_counter()

        # 2. 每轨迹物理先验
        priors = {}
        for tr in observed_tracks:
            tid = tr["track_id"]
            try:
                priors[tid] = describe_physical_v1(
                    frame, tr["source_rows"], plane, normals=grid_normals,
                    settings=self.prior_v1_settings,
                    normal_settings=self.normal_settings,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(_error_entry("prior", exc, track_id=tid))
        t_prior = time.perf_counter()

        # 3. 运动学：非目标且 prior 不兼容的轨迹作为噪声底标定候选（静止判定在模块内部）
        clutter_ids = sorted(
            tid for tid, pr in priors.items()
            if tid != target_tid and not pr.get("compatible")
        )
        try:
            kin_map = self.kinematics.update(
                frame, record, ground=plane,
                clutter_track_ids=clutter_ids, empty_scene=bool(empty_scene),
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(_error_entry("kinematics", exc))
            self.kinematics.reset()
            kin_map = {}
        t_kin = time.perf_counter()

        # 4. Log-Odds 置信状态
        ground_key = (None if plane is None
                      else (tuple(round(float(v), 6) for v in plane["normal"]),
                            round(float(plane["offset_m"]), 6)))
        context_key = (frame.binding, frame.grid.sha256, record.get("generation"), ground_key)
        obs_map = {}
        for tr in record.get("tracks") or []:
            tid = tr.get("track_id")
            if tid is None:
                continue
            obs_map[tid] = {
                "observed": _observed(tr),
                "source_rows": tr.get("source_rows") or [],
                "prior": priors.get(tid),
                "kinematics": kin_map.get(tid),
            }
        try:
            beliefs = self.belief.update_frame(
                context_key, record["time_s"], record["frame"], obs_map,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(_error_entry("belief", exc))
            self.belief.reset()
            beliefs = {}
        t_belief = time.perf_counter()

        # 5. 目标局部完整人体回收（仅针对本帧实测选中的目标核心，不碰其他轨迹点）
        other_rows = [
            tr.get("source_rows") or []
            for tr in (record.get("tracks") or [])
            if tr.get("track_id") != target_tid and tr.get("observed") and tr.get("source_rows")
        ]
        recovery = None
        if target_tid is not None and target_rows:
            try:
                recovery = recover_full_body(
                    frame, background, target_rows, plane,
                    grid_normals=grid_normals,
                    other_tracks_rows=other_rows,
                    settings=self.recovery_settings,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(_error_entry("recovery", exc))
                recovery = {
                    "status": "error",
                    "recovery_rejected_reason": STAGE_ERROR_CODES["recovery"],
                    "core_count": int(len(target_rows)),
                    "recovered_count": int(len(target_rows)),
                    "added_count": 0,
                    "core_rows": list(target_rows),
                    "added_rows": [],
                    "recovered_rows": list(target_rows),
                    "breakdown": None,
                    "completeness": "UNKNOWN",
                    "semantic": "UNKNOWN",
                }
        t_rec = time.perf_counter()

        confirmed_ids = sorted(
            tid for tid, b in beliefs.items()
            if b["observed"] and b["belief_state"] == STATE_CONFIRMED
        )
        candidate_ids = sorted(
            tid for tid, b in beliefs.items()
            if b["observed"] and b["belief_state"] == STATE_CANDIDATE
        )
        target_belief = beliefs.get(target_tid) if target_tid is not None else None

        timings = {
            "normals_ms": (t_norm - t0) * 1000.0,
            "prior_v1_ms": (t_prior - t_norm) * 1000.0,
            "kinematics_ms": (t_kin - t_prior) * 1000.0,
            "belief_ms": (t_belief - t_kin) * 1000.0,
            "recovery_ms": (t_rec - t_belief) * 1000.0,
            "physical_total_ms": (t_rec - t0) * 1000.0,
        }
        track_ids = sorted(set(beliefs.keys()) | set(priors.keys()) | set(kin_map.keys()))
        return {
            "variant": "human_physical_v1",
            "revision": REVISION,
            "status": "degraded" if errors else "ok",
            "error_codes": sorted({e["code"] for e in errors}),
            "errors": errors,
            "frame": record["frame"],
            "time_s": record["time_s"],
            "target_track_id": target_tid,
            "target_belief": target_belief,
            "confirmed_track_ids": confirmed_ids,
            "candidate_track_ids": candidate_ids,
            "kinematics_noise_floor": self.kinematics.noise_floor(),
            "tracks": {
                tid: {
                    "belief": beliefs.get(tid),
                    "prior": priors.get(tid),
                    "kinematics": kin_map.get(tid),
                }
                for tid in track_ids
            },
            "recovery": recovery,
            "timings": timings,
            "semantic_truth": "UNKNOWN",
        }


def evaluator_failure_output(record, exc, elapsed_ms):
    """RangeRuntime 外层保护：评估器整体异常时的最小可审计输出（原链照常返回）。"""
    return {
        "variant": "human_physical_v1",
        "revision": REVISION,
        "status": "error",
        "error_codes": ["evaluate_exception"],
        "errors": [{
            "stage": "evaluate",
            "code": "evaluate_exception",
            "error_type": type(exc).__name__,
            "message": str(exc)[:240],
        }],
        "frame": record.get("frame"),
        "time_s": record.get("time_s"),
        "target_track_id": record.get("target_track_id"),
        "target_belief": None,
        "confirmed_track_ids": [],
        "candidate_track_ids": [],
        "kinematics_noise_floor": None,
        "tracks": {},
        "recovery": None,
        "timings": {"physical_total_ms": float(elapsed_ms)},
        "semantic_truth": "UNKNOWN",
    }
