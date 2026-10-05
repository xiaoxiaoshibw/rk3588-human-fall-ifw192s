"""AGL-A 估计器契约：FrameKey / 配置 / 法向规范 / 估计记录装配。

纯 core（stdlib + NumPy；无 ROS、文件、时钟、UI）。数值约定与冻结模块一致：
来源→显示 R=Rx(roll)@Ry(pitch)（复用 joint_leveling.joint_rotation）；
全域残差复用 ground_diagnostics.residual_stats。质量评分/仲裁/时间状态机
不属于本模块（GL-B 起）。
"""
import copy
import math

import numpy as np

from ..ground_diagnostics import residual_stats
from ..ground_evidence import digest, keys, number, require, text
from ..joint_leveling import joint_rotation
from ..numeric import strict_numeric_array

SCHEMA = 1
DOMAIN_KIND = "adaptive_point_domain"
ESTIMATE_KIND = "adaptive_plane_estimate"
ESTIMATOR_IDS = ("tls", "svd", "ransac")
IMPLEMENTATION_VERSION = "agl-a-v1"
UNITS = "m"
QUALITY_STATUS_NOT_EVALUATED = "NOT_EVALUATED"
REASON_QUALITY_PENDING = "GL_QUALITY_NOT_EVALUATED"
REASON_LOW_POINT_COUNT = "GL_LOW_POINT_COUNT"
REASON_DEGENERATE = "GL_DEGENERATE_GEOMETRY"
REASON_RANSAC_INVALID = "GL_RANSAC_INVALID"
ORIENTATION_MARGIN = 1e-6
ITERATION_HARD_CAP_CEIL = 2000

FRAME_KEY_FIELDS = ("stream_instance_id", "session_id", "reference_epoch",
                    "ordinal", "seq", "source_frame", "source_stamp", "time_domain")
ESTIMATOR_CONFIG_KEYS = ("inlier_threshold_m", "min_inliers", "min_inlier_fraction",
                         "ransac_iterations", "ransac_iteration_hard_cap", "seed")
ESTIMATE_FIELDS = ("kind", "schema", "estimator_id", "implementation_version",
                   "frame_key", "domain_id", "point_sha256", "rows_sha256",
                   "weights_sha256", "config_id", "selector_id", "units",
                   "sign_anchor", "normal_source", "offset_source_m",
                   "pitch_deg", "roll_deg", "full_domain_residuals",
                   "eigenvalue_ratio", "hypothesis_count", "iterations_requested",
                   "resource_complete", "numerical_valid", "quality_status",
                   "confidence", "valid", "reject_reasons", "diagnostic_hypothesis")
FULL_DOMAIN_FIELDS = ("basis", "point_count", "finite_count", "rms_m", "p95_m",
                      "signed_median_m", "support_count", "support_fraction",
                      "threshold_m")


def _nonnegative_int(value, name):
    require(type(value) is int and value >= 0,
            name + " must be a nonnegative integer")
    return value


def validate_frame_key(frame_key):
    keys(frame_key, FRAME_KEY_FIELDS, "frame key")
    for name in ("stream_instance_id", "session_id", "source_frame", "time_domain"):
        text(frame_key[name], "frame key " + name)
    for name in ("reference_epoch", "ordinal", "seq"):
        _nonnegative_int(frame_key[name], "frame key " + name)
    number(frame_key["source_stamp"], "frame key source_stamp")
    return None


def resolve_estimator_config(config):
    """严格解析估计器配置：缺键/未知键/布尔/非有限/越界一律拒绝，不设默认值。

    门槛 profile 由 GL-F 以真实数据冻结；本函数只做结构域校验，不冒充已批准参数。
    """
    keys(config, ESTIMATOR_CONFIG_KEYS, "estimator config")
    resolved = {
        "inlier_threshold_m": number(config["inlier_threshold_m"], "inlier_threshold_m"),
        "min_inliers": _nonnegative_int(config["min_inliers"], "min_inliers"),
        "min_inlier_fraction": number(config["min_inlier_fraction"], "min_inlier_fraction"),
        "ransac_iterations": _nonnegative_int(config["ransac_iterations"], "ransac_iterations"),
        "ransac_iteration_hard_cap": _nonnegative_int(config["ransac_iteration_hard_cap"],
                                                      "ransac_iteration_hard_cap"),
        "seed": _nonnegative_int(config["seed"], "seed"),
    }
    require(resolved["inlier_threshold_m"] > 0.0, "inlier_threshold_m must be positive")
    require(resolved["min_inliers"] >= 3, "min_inliers must be at least 3")
    require(0.0 < resolved["min_inlier_fraction"] <= 1.0,
            "min_inlier_fraction must be in (0, 1]")
    require(resolved["ransac_iterations"] >= 1, "ransac_iterations must be positive")
    require(resolved["ransac_iteration_hard_cap"] <= ITERATION_HARD_CAP_CEIL,
            "ransac_iteration_hard_cap must be <= %d" % ITERATION_HARD_CAP_CEIL)
    require(resolved["ransac_iterations"] <= resolved["ransac_iteration_hard_cap"],
            "ransac_iterations exceeds ransac_iteration_hard_cap")
    return resolved


def estimator_config_id(resolved_config):
    return "agl-config:" + digest(resolved_config)


def require_domain_config(domain, resolved_config):
    require(domain["config_id"] == estimator_config_id(resolved_config),
            "point domain and estimator config are not the same config epoch")


def canonical_plane(normal, offset, up_axis):
    """归一化 n/d 并按有来源的 anchor 定符号；歧义/非法直接拒绝。

    ``n . p + d = 0``，单位法向；翻转符号时 d 同步取负。方向与 anchor 近垂直
    （|dot| < ORIENTATION_MARGIN）视为无符号依据，refuse 而不是猜。
    """
    vector = strict_numeric_array(normal, (3,), "normal")
    value = number(offset, "offset")
    anchor = strict_numeric_array(up_axis, (3,), "up_axis")
    norm = float(np.linalg.norm(vector))
    require(norm > 0.0, "normal must be nonzero")
    vector = vector / norm
    value = value / norm
    alignment = float(vector @ anchor)
    require(abs(alignment) >= ORIENTATION_MARGIN,
            "normal orientation ambiguous against anchor")
    if alignment < 0.0:
        vector, value = -vector, -value
    return [float(v) for v in vector], float(value)


def angles_from_normal(normal):
    """pitch=atan2(-nx,nz)、roll=asin(ny)，与 R=Rx(roll)@Ry(pitch) 互逆。"""
    vector = strict_numeric_array(normal, (3,), "normal")
    norm = float(np.linalg.norm(vector))
    require(norm > 0.0, "normal must be nonzero")
    vector = vector / norm
    pitch = math.degrees(math.atan2(-float(vector[0]), float(vector[2])))
    roll = math.degrees(math.asin(float(np.clip(vector[1], -1.0, 1.0))))
    return pitch, roll


def display_rotation(pitch_deg, roll_deg):
    """复用冻结的 Rx@Ry 约定（yaw/tx/ty=0 作为 gauge）。"""
    return joint_rotation(pitch_deg, roll_deg).tolist()


def _binding_fields(domain, config_id):
    return {"frame_key": copy.deepcopy(domain["frame_key"]),
            "domain_id": domain["domain_id"],
            "point_sha256": domain["point_sha256"],
            "rows_sha256": domain["rows_sha256"],
            "weights_sha256": domain["weights_sha256"],
            "config_id": config_id,
            "selector_id": domain["selector"]["selector_id"],
            "units": UNITS,
            "sign_anchor": copy.deepcopy(domain["spatial_basis"]["up_axis"])}


def _residual_block(points, normal, offset, threshold):
    stats = residual_stats(points, normal, offset, threshold)
    return {"basis": "full_domain_untruncated",
            "point_count": int(stats["count"]),
            "finite_count": int(stats["finite_count"]),
            "rms_m": stats["rms_m"], "p95_m": stats["p95_m"],
            "signed_median_m": stats["signed_median_m"],
            "support_count": int(stats["support_count"]),
            "support_fraction": stats["support_fraction"],
            "threshold_m": float(threshold)}


def assemble_estimate(estimator_id, domain, resolved_config, normal=None, offset=None,
                      invalid_reasons=None, extra=None):
    """装配 PlaneEstimate。数值有效≠质量接受：valid 恒 False（GL-B 才可置 true）。"""
    require(estimator_id in ESTIMATOR_IDS, "unknown estimator id")
    config_id = estimator_config_id(resolved_config)
    record = {"kind": ESTIMATE_KIND, "schema": SCHEMA,
              "estimator_id": estimator_id,
              "implementation_version": IMPLEMENTATION_VERSION}
    record.update(_binding_fields(domain, config_id))
    record.update({
        "normal_source": None, "offset_source_m": None,
        "pitch_deg": None, "roll_deg": None,
        "full_domain_residuals": None, "eigenvalue_ratio": None,
        "hypothesis_count": None, "iterations_requested": None,
        "resource_complete": True,
        "numerical_valid": False, "quality_status": QUALITY_STATUS_NOT_EVALUATED,
        "confidence": 0.0, "valid": False,
        "reject_reasons": [], "diagnostic_hypothesis": None})
    if normal is None or offset is None:
        require(normal is None and offset is None, "normal/offset must be given together")
        require(isinstance(invalid_reasons, list) and bool(invalid_reasons)
                and all(isinstance(reason, str) and reason for reason in invalid_reasons),
                "invalid estimate needs explicit reasons")
        record["reject_reasons"] = list(invalid_reasons)
    else:
        vector, value = canonical_plane(normal, offset, domain["spatial_basis"]["up_axis"])
        pitch, roll = angles_from_normal(vector)
        record.update({
            "normal_source": vector, "offset_source_m": value,
            "pitch_deg": pitch, "roll_deg": roll,
            "full_domain_residuals": _residual_block(
                domain["source_points"], vector, value,
                resolved_config["inlier_threshold_m"]),
            "numerical_valid": True, "reject_reasons": [REASON_QUALITY_PENDING]})
    for key, value in (extra or {}).items():
        require(key in record, "unsupported estimate field: " + str(key))
        record[key] = copy.deepcopy(value)
    return record


def validate_plane_estimate(estimate, domain=None):
    """按记录契约全量校验；给 domain 时交叉校验绑定（跨帧/域混用即拒）。"""
    keys(estimate, ESTIMATE_FIELDS, "plane estimate")
    require(estimate["kind"] == ESTIMATE_KIND, "estimate kind")
    require(type(estimate["schema"]) is int and estimate["schema"] == SCHEMA, "estimate schema")
    require(estimate["estimator_id"] in ESTIMATOR_IDS, "estimate estimator id")
    require(estimate["implementation_version"] == IMPLEMENTATION_VERSION,
            "estimate implementation version")
    validate_frame_key(estimate["frame_key"])
    for name in ("domain_id", "config_id", "selector_id"):
        text(estimate[name], name)
    require(estimate["domain_id"].startswith("agl-domain:"), "domain id namespace")
    require(estimate["config_id"].startswith("agl-config:"), "config id namespace")
    require(estimate["units"] == UNITS, "estimate units must be m")
    anchor = strict_numeric_array(estimate["sign_anchor"], (3,), "sign_anchor")
    require(abs(float(np.linalg.norm(anchor)) - 1.0) <= 1e-6,
            "sign anchor must be a unit vector")
    require(type(estimate["numerical_valid"]) is bool, "numerical_valid must be bool")
    require(type(estimate["valid"]) is bool and estimate["valid"] is False,
            "GL-A estimates are never accepted")
    require(estimate["quality_status"] == QUALITY_STATUS_NOT_EVALUATED, "quality status")
    require(estimate["confidence"] == 0.0, "GL-A confidence must be 0")
    require(type(estimate["resource_complete"]) is bool, "resource_complete must be bool")
    require(isinstance(estimate["reject_reasons"], list) and bool(estimate["reject_reasons"])
            and all(isinstance(reason, str) and reason for reason in estimate["reject_reasons"]),
            "reject reasons")
    require(estimate["hypothesis_count"] is None
            or (type(estimate["hypothesis_count"]) is int and estimate["hypothesis_count"] >= 0),
            "hypothesis_count")
    require(estimate["iterations_requested"] is None
            or (type(estimate["iterations_requested"]) is int
                and estimate["iterations_requested"] >= 1), "iterations_requested")
    require(estimate["eigenvalue_ratio"] is None
            or number(estimate["eigenvalue_ratio"], "eigenvalue_ratio") >= 0.0,
            "eigenvalue_ratio")
    require(estimate["diagnostic_hypothesis"] is None
            or isinstance(estimate["diagnostic_hypothesis"], dict),
            "diagnostic_hypothesis")
    if estimate["numerical_valid"]:
        vector = strict_numeric_array(estimate["normal_source"], (3,), "normal_source")
        require(abs(float(np.linalg.norm(vector)) - 1.0) <= 1e-9,
                "normal_source must be unit")
        number(estimate["offset_source_m"], "offset_source_m")
        number(estimate["pitch_deg"], "pitch_deg")
        number(estimate["roll_deg"], "roll_deg")
        require(estimate["reject_reasons"] == [REASON_QUALITY_PENDING],
                "numerically valid estimate can only be quality-pending")
        full = estimate["full_domain_residuals"]
        keys(full, FULL_DOMAIN_FIELDS, "full domain residuals")
        require(full["basis"] == "full_domain_untruncated", "residual basis")
        for name in ("point_count", "finite_count", "support_count"):
            require(type(full[name]) is int and full[name] >= 0,
                    "residual count " + name)
        for name in ("rms_m", "p95_m", "signed_median_m", "support_fraction", "threshold_m"):
            number(full[name], "residual " + name)
        require(full["support_count"] <= full["point_count"], "support count bound")
        require(0.0 <= full["support_fraction"] <= 1.0, "support fraction bound")
    else:
        for name in ("normal_source", "offset_source_m", "pitch_deg", "roll_deg",
                     "full_domain_residuals"):
            require(estimate[name] is None, name + " must be null for invalid numerics")
        require(REASON_QUALITY_PENDING not in estimate["reject_reasons"],
                "invalid estimate cannot claim quality pending")
    if domain is not None:
        require(estimate["domain_id"] == domain["domain_id"], "estimate/domain mismatch")
        require(estimate["point_sha256"] == domain["point_sha256"],
                "estimate point binding mismatch")
        require(estimate["rows_sha256"] == domain["rows_sha256"],
                "estimate row binding mismatch")
        require(estimate["weights_sha256"] == domain["weights_sha256"],
                "estimate weights binding mismatch")
        require(estimate["selector_id"] == domain["selector"]["selector_id"],
                "estimate selector mismatch")
        require(estimate["config_id"] == domain["config_id"], "estimate config mismatch")
        require(digest(estimate["sign_anchor"]) == digest(domain["spatial_basis"]["up_axis"]),
                "estimate sign anchor / domain basis mismatch")
        require(digest(estimate["frame_key"]) == digest(domain["frame_key"]),
                "estimate frame mismatch")
    return None
