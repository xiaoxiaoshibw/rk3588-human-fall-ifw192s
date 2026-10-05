"""AGL-B 单估计器质量与可信度（纯 core；只评估，不给 FINAL 资格）。

QualityReport = 全域/逐区未裁尾残差（RMS/P95/MAD/max/support）+ 谱退化 +
切平面 coverage + normal 合理性 + 7 分项 score + hard gates。``confidence_geo``
是启发式指数（score_kind=heuristic_quality_v1），不是正确概率；任一 hard gate
失败即 valid=false、confidence=0（平均分不能救回）。不实现 consensus（C）、
时间/状态机（D）、transform/应用（E）。
"""
import copy
import math

import numpy as np

from ..ground import _tangent_basis
from ..ground_diagnostics import residual_stats
from ..ground_evidence import digest, keys, number, require, text
from ..numeric import strict_numeric_array
from .contracts import (SCHEMA, UNITS, estimator_config_id, resolve_estimator_config,
                        validate_plane_estimate)
from .selection import validate_point_domain

QUALITY_KIND = "adaptive_quality_report"
QUALITY_SCHEMA = 1
SCORE_KIND = "heuristic_quality_v1"
QUALITY_CONFIG_PREFIX = "agl-quality-config:"

REASON_UPSTREAM = "GL_UPSTREAM_INVALID"
REASON_LOW_POINTS = "GL_LOW_POINT_COUNT"
REASON_HIGH_RESIDUAL = "GL_HIGH_RESIDUAL"
REASON_LOW_SUPPORT = "GL_LOW_SUPPORT"
REASON_LOW_COVERAGE = "GL_LOW_SPATIAL_COVERAGE"
REASON_DEGENERATE = "GL_DEGENERATE_GEOMETRY"
REASON_NORMAL = "GL_NORMAL_INVALID"
REASON_FEW_REGIONS = "GL_LOW_SUPPORTED_REGIONS"
REASON_REGION_FAILED = "GL_REQUIRED_REGION_FAILED"
REASON_REGION_MISSING = "GL_REQUIRED_REGION_MISSING"

QUALITY_CONFIG_KEYS = (
    "min_points", "min_supported_regions", "region_min_points", "required_region_codes",
    "max_rms_m", "max_p95_m", "min_support_ratio",
    "min_lambda2_lambda3", "soft_full_lambda2_lambda3",
    "min_occupied_cells", "soft_full_occupied_cells", "coverage_cell_m",
    "min_tangent_extents_m", "max_single_cell_share",
    "max_normal_tilt_deg", "soft_good_normal_tilt_deg",
    "soft_good_rms_m", "soft_good_p95_m", "soft_full_support_ratio", "soft_full_points",
    "score_weights")
REPORT_FIELDS = ("kind", "schema", "report_id", "estimator_id", "estimate_digest",
                 "frame_key", "domain_id", "config_id", "quality_config_id", "units",
                 "threshold_m", "score_kind", "upstream_numerical_valid", "full",
                 "regions", "spectral", "coverage", "normal", "score_components",
                 "hard_gate_results", "confidence_geo", "valid", "reject_reasons")
STATS_FIELDS = ("point_count", "rms_m", "p95_m", "mad_m", "max_abs_m",
                "support_count", "support_fraction")

_GATE_REASONS = {"full_min_points": REASON_LOW_POINTS,
                 "full_rms_max": REASON_HIGH_RESIDUAL,
                 "full_p95_max": REASON_HIGH_RESIDUAL,
                 "full_support_min": REASON_LOW_SUPPORT,
                 "region_min_points": REASON_LOW_POINTS,
                 "region_rms_max": REASON_HIGH_RESIDUAL,
                 "region_p95_max": REASON_HIGH_RESIDUAL,
                 "region_support_min": REASON_LOW_SUPPORT,
                 "min_supported_regions": REASON_FEW_REGIONS,
                 "required_region_present": REASON_REGION_MISSING,
                 "spectral_lambda2_lambda3_min": REASON_DEGENERATE,
                 "coverage_min_cells": REASON_LOW_COVERAGE,
                 "tangent_extent_min": REASON_LOW_COVERAGE,
                 "single_cell_share_max": REASON_LOW_COVERAGE,
                 "normal_tilt_max": REASON_NORMAL}


def _strict_int(value, name):
    require(type(value) is int, name + " must be an integer (bool rejected)")
    return value


def resolve_quality_config(config):
    """严格解析质量配置：缺键/未知键/布尔/非有限/关系错一律拒绝，不设默认值。"""
    keys(config, QUALITY_CONFIG_KEYS, "quality config")
    resolved = {
        "min_points": _strict_int(config["min_points"], "min_points"),
        "min_supported_regions": _strict_int(config["min_supported_regions"],
                                             "min_supported_regions"),
        "region_min_points": _strict_int(config["region_min_points"], "region_min_points"),
        "max_rms_m": number(config["max_rms_m"], "max_rms_m"),
        "max_p95_m": number(config["max_p95_m"], "max_p95_m"),
        "min_support_ratio": number(config["min_support_ratio"], "min_support_ratio"),
        "min_lambda2_lambda3": number(config["min_lambda2_lambda3"], "min_lambda2_lambda3"),
        "soft_full_lambda2_lambda3": number(config["soft_full_lambda2_lambda3"],
                                            "soft_full_lambda2_lambda3"),
        "min_occupied_cells": _strict_int(config["min_occupied_cells"], "min_occupied_cells"),
        "soft_full_occupied_cells": _strict_int(config["soft_full_occupied_cells"],
                                                "soft_full_occupied_cells"),
        "coverage_cell_m": number(config["coverage_cell_m"], "coverage_cell_m"),
        "min_tangent_extents_m": number(config["min_tangent_extents_m"],
                                        "min_tangent_extents_m"),
        "max_single_cell_share": number(config["max_single_cell_share"],
                                        "max_single_cell_share"),
        "max_normal_tilt_deg": number(config["max_normal_tilt_deg"], "max_normal_tilt_deg"),
        "soft_good_normal_tilt_deg": number(config["soft_good_normal_tilt_deg"],
                                            "soft_good_normal_tilt_deg"),
        "soft_good_rms_m": number(config["soft_good_rms_m"], "soft_good_rms_m"),
        "soft_good_p95_m": number(config["soft_good_p95_m"], "soft_good_p95_m"),
        "soft_full_support_ratio": number(config["soft_full_support_ratio"],
                                          "soft_full_support_ratio"),
        "soft_full_points": _strict_int(config["soft_full_points"], "soft_full_points"),
    }
    codes = config["required_region_codes"]
    require(isinstance(codes, list), "required_region_codes must be a list")
    clean_codes = []
    for code in codes:
        item = _strict_int(code, "required region code")
        require(item not in clean_codes, "duplicate required region code")
        clean_codes.append(item)
    resolved["required_region_codes"] = clean_codes
    weights = config["score_weights"]
    require(isinstance(weights, list) and len(weights) == 7,
            "score_weights must have 7 entries")
    clean_weights = [number(value, "score weight") for value in weights]
    require(all(value >= 0.0 for value in clean_weights), "score weights must be >= 0")
    require(abs(sum(clean_weights) - 1.0) <= 1e-9, "score weights must sum to 1")
    resolved["score_weights"] = clean_weights
    require(resolved["min_points"] >= 3, "min_points must be at least 3")
    require(resolved["region_min_points"] >= 3, "region_min_points must be at least 3")
    require(resolved["min_supported_regions"] >= 1,
            "min_supported_regions must be positive")
    require(0.0 < resolved["max_rms_m"] and 0.0 < resolved["max_p95_m"],
            "residual limits must be positive")
    require(0.0 <= resolved["min_support_ratio"] < resolved["soft_full_support_ratio"] <= 1.0,
            "support ratio ordering violated")
    require(0.0 <= resolved["min_lambda2_lambda3"] < resolved["soft_full_lambda2_lambda3"],
            "lambda ratio ordering violated")
    require(0.0 < resolved["coverage_cell_m"], "coverage_cell_m must be positive")
    require(0 < resolved["min_occupied_cells"] < resolved["soft_full_occupied_cells"],
            "occupied cell ordering violated")
    require(0.0 < resolved["min_tangent_extents_m"], "min_tangent_extents_m must be positive")
    require(0.0 < resolved["max_single_cell_share"] <= 1.0,
            "max_single_cell_share must be in (0, 1]")
    require(0.0 <= resolved["soft_good_normal_tilt_deg"] < resolved["max_normal_tilt_deg"] <= 90.0,
            "normal tilt ordering violated")
    require(0.0 < resolved["soft_good_rms_m"] < resolved["max_rms_m"],
            "soft_good_rms_m ordering violated")
    require(0.0 < resolved["soft_good_p95_m"] < resolved["max_p95_m"],
            "soft_good_p95_m ordering violated")
    require(resolved["min_points"] < resolved["soft_full_points"],
            "point count ordering violated")
    return resolved


def quality_config_id(resolved_config):
    return QUALITY_CONFIG_PREFIX + digest(resolved_config)


def _stats(signed, threshold):
    absd = np.abs(signed)
    count = int(len(signed))
    support_count = int(np.count_nonzero(absd <= threshold))
    median = float(np.median(signed))
    return {"point_count": count,
            "rms_m": float(np.sqrt(np.mean(np.square(signed)))),
            "p95_m": float(np.percentile(absd, 95.0)),
            "mad_m": float(np.median(np.abs(signed - median))),
            "max_abs_m": float(absd.max()),
            "support_count": support_count,
            "support_fraction": float(support_count / count)}


def _spectral(points, weights):
    total = float(weights.sum())
    center = (weights[:, None] * points).sum(axis=0) / total
    centered = points - center
    covariance = (centered * weights[:, None]).T @ centered / total
    values = np.linalg.eigvalsh(covariance)
    first, second, third = (float(value) for value in values)
    return {"lambda1_m2": first, "lambda2_m2": second, "lambda3_m2": third,
            "lambda2_lambda3": (second / third) if third > 0.0 else 0.0,
            "lambda1_lambda2": (first / second) if second > 0.0 else 0.0,
            "weighting": "domain_weights"}


def _coverage(points, anchor, cell_m):
    first, second = _tangent_basis(np.asarray(anchor, dtype=np.float64))
    axis_u = points @ first
    axis_v = points @ second
    cells = np.column_stack([np.floor(axis_u / cell_m), np.floor(axis_v / cell_m)])
    _, counts = np.unique(cells.astype(np.int64), axis=0, return_counts=True)
    return {"cell_m": float(cell_m), "occupied_cells": int(len(counts)),
            "single_cell_share": float(counts.max() / len(points)),
            "tangent_extents_m": [float(axis_u.max() - axis_u.min()),
                                  float(axis_v.max() - axis_v.min())]}


def _lower_better(value, reject, soft_good):
    return min(max((reject - value) / (reject - soft_good), 0.0), 1.0)


def _higher_better(value, hard_min, soft_full):
    return min(max((value - hard_min) / (soft_full - hard_min), 0.0), 1.0)


def _region_reasons(gate_results):
    reasons = []
    for gate in gate_results:
        if not gate["passed"]:
            reason = _GATE_REASONS[gate["gate"]]
            if reason not in reasons:
                reasons.append(reason)
    return reasons


def evaluate_quality(estimate, domain, estimator_config, quality_config):
    """对单个 A 阶段估计做质量评估；返回新的 QualityReport（深拷贝、JSON 安全）。"""
    resolved = resolve_quality_config(quality_config)
    resolved_estimator = resolve_estimator_config(estimator_config)
    validate_point_domain(domain)
    validate_plane_estimate(estimate, domain)
    require(estimator_config_id(resolved_estimator) == domain["config_id"],
            "estimator config / domain config mismatch")
    threshold = float(resolved_estimator["inlier_threshold_m"])
    report = {"kind": QUALITY_KIND, "schema": QUALITY_SCHEMA,
              "estimator_id": estimate["estimator_id"],
              "estimate_digest": digest(estimate),
              "frame_key": copy.deepcopy(estimate["frame_key"]),
              "domain_id": domain["domain_id"], "config_id": domain["config_id"],
              "quality_config_id": quality_config_id(resolved),
              "units": UNITS, "threshold_m": threshold, "score_kind": SCORE_KIND,
              "upstream_numerical_valid": bool(estimate["numerical_valid"]),
              "full": None, "regions": [], "spectral": None, "coverage": None,
              "normal": None, "score_components": None, "hard_gate_results": [],
              "confidence_geo": 0.0, "valid": False, "reject_reasons": []}
    if not estimate["numerical_valid"]:
        report["hard_gate_results"] = [{"gate": "upstream_numerics", "scope": "upstream",
                                        "region_code": None, "passed": False,
                                        "value": None, "limit": None}]
        report["reject_reasons"] = [REASON_UPSTREAM] + list(estimate["reject_reasons"])
        report["report_id"] = "agl-quality:" + digest(report)
        return report
    points = domain["source_points"]
    weights = domain["weights"]
    codes = domain["region_codes"]
    normal = np.asarray(estimate["normal_source"], dtype=np.float64)
    offset = float(estimate["offset_source_m"])
    anchor = domain["spatial_basis"]["up_axis"]
    signed = points @ normal + offset
    full = _stats(signed, threshold)
    required = set(resolved["required_region_codes"])
    gates = []

    def gate(name, scope, value, limit, passed, region=None):
        gates.append({"gate": name, "scope": scope, "region_code": region,
                      "passed": bool(passed),
                      "value": None if value is None else float(value),
                      "limit": None if limit is None else float(limit)})

    gate("full_min_points", "full", full["point_count"], resolved["min_points"],
         full["point_count"] >= resolved["min_points"])
    gate("full_rms_max", "full", full["rms_m"], resolved["max_rms_m"],
         full["rms_m"] <= resolved["max_rms_m"])
    gate("full_p95_max", "full", full["p95_m"], resolved["max_p95_m"],
         full["p95_m"] <= resolved["max_p95_m"])
    gate("full_support_min", "full", full["support_fraction"], resolved["min_support_ratio"],
         full["support_fraction"] >= resolved["min_support_ratio"])
    present = sorted(set(int(code) for code in np.unique(codes)))
    region_records = []
    supported_regions = 0
    for code in present:
        mask = codes == code
        stats = _stats(signed[mask], threshold)
        required_flag = code in required
        region_gates = [
            ("region_min_points", stats["point_count"], resolved["region_min_points"],
             stats["point_count"] >= resolved["region_min_points"]),
            ("region_rms_max", stats["rms_m"], resolved["max_rms_m"],
             stats["rms_m"] <= resolved["max_rms_m"]),
            ("region_p95_max", stats["p95_m"], resolved["max_p95_m"],
             stats["p95_m"] <= resolved["max_p95_m"]),
            ("region_support_min", stats["support_fraction"], resolved["min_support_ratio"],
             stats["support_fraction"] >= resolved["min_support_ratio"])]
        if all(item[3] for item in region_gates):
            supported_regions += 1
        if required_flag:
            for name, value, limit, passed in region_gates:
                gate(name, "region", value, limit, passed, region=code)
        region_reasons = _region_reasons(
            [{"gate": name, "passed": passed}
             for name, _, _, passed in region_gates])
        if required_flag and region_reasons and REASON_REGION_FAILED not in region_reasons:
            region_reasons.insert(0, REASON_REGION_FAILED)
        region_records.append({"region_code": code, **stats, "required": required_flag,
                               "passed": all(item[3] for item in region_gates),
                               "reject_reasons": region_reasons})
    missing = sorted(required - set(present))
    for code in missing:
        region_records.append({"region_code": code, "point_count": 0, "rms_m": None,
                               "p95_m": None, "mad_m": None, "max_abs_m": None,
                               "support_count": 0, "support_fraction": None,
                               "required": True, "passed": False,
                               "reject_reasons": [REASON_REGION_MISSING]})
    for code in missing:
        gate("required_region_present", "region", None, None, False, region=code)
    gate("min_supported_regions", "global", supported_regions,
         resolved["min_supported_regions"],
         supported_regions >= resolved["min_supported_regions"])
    spectral = _spectral(points, weights)
    gate("spectral_lambda2_lambda3_min", "global", spectral["lambda2_lambda3"],
         resolved["min_lambda2_lambda3"],
         spectral["lambda2_lambda3"] >= resolved["min_lambda2_lambda3"])
    coverage = _coverage(points, anchor, resolved["coverage_cell_m"])
    gate("coverage_min_cells", "global", coverage["occupied_cells"],
         resolved["min_occupied_cells"],
         coverage["occupied_cells"] >= resolved["min_occupied_cells"])
    gate("tangent_extent_min", "global", min(coverage["tangent_extents_m"]),
         resolved["min_tangent_extents_m"],
         min(coverage["tangent_extents_m"]) >= resolved["min_tangent_extents_m"])
    gate("single_cell_share_max", "global", coverage["single_cell_share"],
         resolved["max_single_cell_share"],
         coverage["single_cell_share"] <= resolved["max_single_cell_share"])
    tilt = math.degrees(math.acos(float(np.clip(np.dot(normal, anchor), -1.0, 1.0))))
    gate("normal_tilt_max", "global", tilt, resolved["max_normal_tilt_deg"],
         tilt <= resolved["max_normal_tilt_deg"])
    components = {
        "q_rms": _lower_better(full["rms_m"], resolved["max_rms_m"],
                               resolved["soft_good_rms_m"]),
        "q_p95": _lower_better(full["p95_m"], resolved["max_p95_m"],
                               resolved["soft_good_p95_m"]),
        "q_support": _higher_better(full["support_fraction"], resolved["min_support_ratio"],
                                    resolved["soft_full_support_ratio"]),
        "q_count": _higher_better(full["point_count"], resolved["min_points"],
                                  resolved["soft_full_points"]),
        "q_coverage": _higher_better(coverage["occupied_cells"],
                                     resolved["min_occupied_cells"],
                                     resolved["soft_full_occupied_cells"]),
        "q_condition": _higher_better(spectral["lambda2_lambda3"],
                                      resolved["min_lambda2_lambda3"],
                                      resolved["soft_full_lambda2_lambda3"]),
        "q_normal": _lower_better(tilt, resolved["max_normal_tilt_deg"],
                                  resolved["soft_good_normal_tilt_deg"])}
    raw_score = float(sum(weight * components[key] for weight, key in
                          zip(resolved["score_weights"],
                              ("q_rms", "q_p95", "q_support", "q_count", "q_coverage",
                               "q_condition", "q_normal"))))
    hard_ok = all(item["passed"] for item in gates)
    reasons = []
    for item in gates:
        if not item["passed"]:
            reason = _GATE_REASONS[item["gate"]]
            if reason not in reasons:
                reasons.append(reason)
    if missing and REASON_REGION_MISSING not in reasons:
        reasons.append(REASON_REGION_MISSING)
    if any(record["required"] and not record["passed"]
           and record["region_code"] in present for record in region_records) \
            and REASON_REGION_FAILED not in reasons:
        reasons.append(REASON_REGION_FAILED)
    report.update({
        "full": full, "regions": region_records, "spectral": spectral,
        "coverage": {**coverage,
                     "basis_provenance": domain["spatial_basis"]["provenance"],
                     "basis_version": domain["spatial_basis"]["version"]},
        "normal": {"tilt_deg": tilt, "anchor": list(anchor)},
        "score_components": {**components, "weights": list(resolved["score_weights"]),
                             "raw_score": raw_score},
        "hard_gate_results": gates,
        "confidence_geo": raw_score if hard_ok else 0.0,
        "valid": bool(hard_ok), "reject_reasons": reasons})
    report["report_id"] = "agl-quality:" + digest(report)
    return report


def validate_quality_report(report, domain=None, estimate=None):
    keys(report, REPORT_FIELDS, "quality report")
    require(report["kind"] == QUALITY_KIND and type(report["schema"]) is int
            and report["schema"] == QUALITY_SCHEMA, "quality report kind/schema")
    require(report["score_kind"] == SCORE_KIND, "quality score kind")
    require(report["units"] == UNITS, "quality report units")
    for name in ("report_id", "domain_id", "config_id", "quality_config_id",
                 "estimate_digest"):
        text(report[name], name)
    require(report["report_id"].startswith("agl-quality:"), "report id namespace")
    require(report["domain_id"].startswith("agl-domain:"), "report domain namespace")
    require(report["config_id"].startswith("agl-config:"), "report config namespace")
    require(report["quality_config_id"].startswith(QUALITY_CONFIG_PREFIX),
            "quality config namespace")
    require(report["report_id"] == "agl-quality:" + digest(
        {k: v for k, v in report.items() if k != "report_id"}), "report ID/content mismatch")
    require(type(report["valid"]) is bool, "quality valid must be bool")
    confidence = number(report["confidence_geo"], "confidence_geo")
    require(0.0 <= confidence <= 1.0, "confidence_geo out of range")
    require(type(report["upstream_numerical_valid"]) is bool, "upstream flag")
    require(report["valid"] is True or confidence == 0.0,
            "invalid report must have zero confidence")
    require(report["valid"] is True or bool(report["reject_reasons"]),
            "invalid report needs reasons")
    if domain is not None:
        require(report["domain_id"] == domain["domain_id"], "report/domain mismatch")
        require(digest(report["frame_key"]) == digest(domain["frame_key"]),
                "report frame mismatch")
    if estimate is not None:
        require(report["estimate_digest"] == digest(estimate), "report/estimate mismatch")
    return None
