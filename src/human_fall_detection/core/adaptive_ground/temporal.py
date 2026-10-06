"""AGL-D 时间滤波（纯 core）：validated cohort → sliding median → EMA → 限速。

显式时间（dt 来自受审同流 source stamps，不猜 FPS）；本模块不做状态机/接受
事务（在 controller），不改输入；offset 与角度同门控、分通道限速。
"""
import math

import numpy as np

from ..ground_evidence import digest, keys, number, require, text
from .contracts import display_rotation

TEMPORAL_CONFIG_KEYS = (
    "window_size", "ema_alpha", "degraded_ema_alpha", "acquire_frames",
    "recover_frames", "min_cohort_duration_s", "max_pitch_deg", "max_roll_deg",
    "max_delta_pitch_per_frame", "max_delta_roll_per_frame", "max_angle_step_deg",
    "max_delta_angle_per_second", "max_angle_rate_deg_s", "raw_jump_reject_deg",
    "pending_rebase_max_deg", "offset_policy", "max_offset_step_m",
    "max_offset_rate_m_s", "raw_offset_jump_reject_m", "max_frame_gap_s",
    "max_hold_age_s")
OFFSET_POLICIES = ("gated_observed", "frozen_observed")
TEMPORAL_CONFIG_PREFIX = "agl-temporal-config:"
CANDIDATE_FIELDS = ("pitch_deg", "roll_deg", "offset_m")


def _positive(value, name):
    result = number(value, name)
    require(result > 0.0, name + " must be positive")
    return result


def _alpha(value, name):
    result = number(value, name)
    require(0.0 < result <= 1.0, name + " must be in (0, 1]")
    return result


def resolve_temporal_config(config):
    """严格解析时间配置：缺键/未知键/布尔/非有限/关系错一律拒绝，不设默认值。"""
    keys(config, TEMPORAL_CONFIG_KEYS, "temporal config")
    resolved = {
        "window_size": config["window_size"],
        "ema_alpha": _alpha(config["ema_alpha"], "ema_alpha"),
        "degraded_ema_alpha": _alpha(config["degraded_ema_alpha"], "degraded_ema_alpha"),
        "acquire_frames": config["acquire_frames"],
        "recover_frames": config["recover_frames"],
        "min_cohort_duration_s": _positive(config["min_cohort_duration_s"],
                                           "min_cohort_duration_s"),
        "max_pitch_deg": _positive(config["max_pitch_deg"], "max_pitch_deg"),
        "max_roll_deg": _positive(config["max_roll_deg"], "max_roll_deg"),
        "max_delta_pitch_per_frame": _positive(config["max_delta_pitch_per_frame"],
                                               "max_delta_pitch_per_frame"),
        "max_delta_roll_per_frame": _positive(config["max_delta_roll_per_frame"],
                                              "max_delta_roll_per_frame"),
        "max_angle_step_deg": _positive(config["max_angle_step_deg"],
                                        "max_angle_step_deg"),
        "max_delta_angle_per_second": _positive(config["max_delta_angle_per_second"],
                                                "max_delta_angle_per_second"),
        "max_angle_rate_deg_s": _positive(config["max_angle_rate_deg_s"],
                                          "max_angle_rate_deg_s"),
        "raw_jump_reject_deg": _positive(config["raw_jump_reject_deg"],
                                         "raw_jump_reject_deg"),
        "pending_rebase_max_deg": _positive(config["pending_rebase_max_deg"],
                                            "pending_rebase_max_deg"),
        "offset_policy": config["offset_policy"],
        "max_offset_step_m": _positive(config["max_offset_step_m"], "max_offset_step_m"),
        "max_offset_rate_m_s": _positive(config["max_offset_rate_m_s"],
                                         "max_offset_rate_m_s"),
        "raw_offset_jump_reject_m": _positive(config["raw_offset_jump_reject_m"],
                                              "raw_offset_jump_reject_m"),
        "max_frame_gap_s": _positive(config["max_frame_gap_s"], "max_frame_gap_s"),
        "max_hold_age_s": _positive(config["max_hold_age_s"], "max_hold_age_s"),
    }
    for name in ("window_size", "acquire_frames", "recover_frames"):
        value = resolved[name]
        require(type(value) is int, name + " must be an integer (bool rejected)")
    require(resolved["window_size"] >= 3 and resolved["window_size"] % 2 == 1,
            "window_size must be odd and >= 3")
    require(resolved["acquire_frames"] >= resolved["window_size"],
            "acquire_frames must be >= window_size")
    require(resolved["recover_frames"] >= resolved["window_size"],
            "recover_frames must be >= window_size")
    require(resolved["offset_policy"] in OFFSET_POLICIES, "unsupported offset_policy")
    require(resolved["pending_rebase_max_deg"] < resolved["raw_jump_reject_deg"],
            "pending_rebase_max_deg must be below raw_jump_reject_deg")
    require(abs(resolved["max_delta_angle_per_second"]
                - resolved["max_angle_rate_deg_s"]) <= 1e-12,
            "max_delta_angle_per_second / max_angle_rate_deg_s alias mismatch")
    require(resolved["max_offset_step_m"] <= resolved["raw_offset_jump_reject_m"],
            "max_offset_step_m must be <= raw_offset_jump_reject_m")
    require(0.0 < resolved["max_pitch_deg"] <= 90.0
            and 0.0 < resolved["max_roll_deg"] <= 90.0,
            "max_pitch/max_roll must be within (0, 90]")
    return resolved


def temporal_config_id(resolved_config):
    return TEMPORAL_CONFIG_PREFIX + digest(resolved_config)


def validate_candidate(candidate, name="candidate"):
    keys(candidate, CANDIDATE_FIELDS, name)
    return {"pitch_deg": number(candidate["pitch_deg"], name + ".pitch_deg"),
            "roll_deg": number(candidate["roll_deg"], name + ".roll_deg"),
            "offset_m": number(candidate["offset_m"], name + ".offset_m")}


def plane_normal(pitch_deg, roll_deg):
    return np.asarray(display_rotation(pitch_deg, roll_deg), dtype=np.float64)[2]


def angle_between_deg(first, second):
    left = plane_normal(first["pitch_deg"], first["roll_deg"])
    right = plane_normal(second["pitch_deg"], second["roll_deg"])
    return math.degrees(math.acos(float(np.clip(float(left @ right), -1.0, 1.0))))


def sliding_median(cohort):
    require(isinstance(cohort, list) and bool(cohort), "cohort must be non-empty")
    return {"pitch_deg": float(np.median([item["pitch_deg"] for item in cohort])),
            "roll_deg": float(np.median([item["roll_deg"] for item in cohort])),
            "offset_m": float(np.median([item["offset_m"] for item in cohort]))}


def ema_step(previous, target, alpha):
    return {"pitch_deg": alpha * target["pitch_deg"] + (1.0 - alpha) * previous["pitch_deg"],
            "roll_deg": alpha * target["roll_deg"] + (1.0 - alpha) * previous["roll_deg"],
            "offset_m": alpha * target["offset_m"] + (1.0 - alpha) * previous["offset_m"]}


def _axis_clamp(delta, limit):
    return max(-limit, min(limit, delta))


def limit_step(previous, target, dt_s, resolved):
    """向量/逐轴/组合角三层限速；返回（已限速 proposal, 是否被限制）。"""
    require(dt_s is not None and math.isfinite(dt_s) and dt_s > 0.0,
            "limit_step needs a positive finite dt")
    dp_request = target["pitch_deg"] - previous["pitch_deg"]
    dr_request = target["roll_deg"] - previous["roll_deg"]
    dp = _axis_clamp(dp_request, resolved["max_delta_pitch_per_frame"])
    dr = _axis_clamp(dr_request, resolved["max_delta_roll_per_frame"])
    allowed = min(resolved["max_angle_step_deg"],
                  resolved["max_delta_angle_per_second"] * dt_s,
                  resolved["max_angle_rate_deg_s"] * dt_s)
    limited = abs(dp - dp_request) > 0.0 or abs(dr - dr_request) > 0.0
    factor = 1.0
    trial = {"pitch_deg": previous["pitch_deg"] + dp, "roll_deg": previous["roll_deg"] + dr}
    combined = angle_between_deg(previous, trial)
    if combined > allowed:
        factor = allowed / combined
        for _ in range(6):
            trial = {"pitch_deg": previous["pitch_deg"] + dp * factor,
                     "roll_deg": previous["roll_deg"] + dr * factor}
            combined = angle_between_deg(previous, trial)
            if combined <= allowed + 1e-12:
                break
            factor *= allowed / combined
        limited = True
    return {"proposal": {"pitch_deg": trial["pitch_deg"], "roll_deg": trial["roll_deg"]},
            "limited": limited, "allowed_angle_step_deg": allowed,
            "combined_angle_deg": combined}


def limit_offset(previous_m, target_m, dt_s, resolved):
    require(dt_s is not None and math.isfinite(dt_s) and dt_s > 0.0,
            "limit_offset needs a positive finite dt")
    allowed = min(resolved["max_offset_step_m"], resolved["max_offset_rate_m_s"] * dt_s)
    delta = target_m - previous_m
    limited = abs(delta) > allowed
    value = previous_m + _axis_clamp(delta, allowed)
    return {"value": float(value), "limited": bool(limited),
            "allowed_offset_step_m": float(allowed)}
