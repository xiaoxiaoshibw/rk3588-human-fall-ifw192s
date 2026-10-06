"""AGL-C 三估计器一致性仲裁（纯 core；只给 candidate，不提交 transform）。

GOOD/DEGRADED/BAD + pairwise 角/offset/pitch/roll + 家族/支持簇 + 选择/score cap。
TLS/SVD 同属 LS 家族：不用相关多数压制 RANSAC；非传递链不强行合并；不平均三
平面、不改输入/阈值；输出 update_candidate_allowed，实际应用/时序归 GL-D。
"""
import copy
import math
from itertools import combinations

import numpy as np

from ..ground_evidence import digest, keys, number, require, text
from .contracts import SCHEMA, UNITS, canonical_plane, validate_plane_estimate
from .quality import validate_quality_report
from .selection import validate_point_domain

CONSENSUS_KIND = "adaptive_consensus_report"
CONSENSUS_SCHEMA = 1
CONSENSUS_CONFIG_PREFIX = "agl-consensus-config:"
ESTIMATOR_ORDER = ("tls", "svd", "ransac")
FAMILIES = {"tls": "ls", "svd": "ls", "ransac": "robust"}
STATUSES = ("GOOD", "DEGRADED", "BAD")

REASON_NUMERIC = "GL_NUMERICAL_DISAGREEMENT"
REASON_NO_CONSENSUS = "GL_NO_CONSENSUS"
REASON_ROBUST_DIVERGENCE = "GL_ROBUST_DIVERGENCE"
REASON_LOW_CONFIDENCE = "GL_LOW_CONFIDENCE"
REASON_NORMAL_INVALID = "GL_NORMAL_INVALID"

CONSENSUS_CONFIG_KEYS = ("good_angle_deg", "degraded_angle_deg",
                         "good_offset_m", "degraded_offset_m",
                         "tls_svd_numeric_angle_deg", "tls_svd_numeric_offset_m",
                         "degraded_confidence_cap", "min_good_confidence",
                         "min_degraded_confidence", "degraded_updates_enabled",
                         "ls_only_updates_enabled")
PAIR_FIELDS = ("a", "b", "level", "angle_deg", "offset_gap_m",
               "pitch_gap_deg", "roll_gap_deg", "reason")
REPORT_FIELDS = ("kind", "schema", "report_id", "frame_key", "domain_id", "config_id",
                 "consensus_config_id", "units", "members", "pairwise", "status",
                 "supporting_estimators", "supporting_families", "numeric_check_ok",
                 "selected_estimator", "confidence", "confidence_cap",
                 "update_candidate_allowed", "reason_codes")


def _strict_bool(value, name):
    require(type(value) is bool, name + " must be bool")
    return value


def resolve_consensus_config(config):
    """严格解析仲裁配置：缺键/未知键/布尔/非有限/关系错一律拒绝，不设默认值。"""
    keys(config, CONSENSUS_CONFIG_KEYS, "consensus config")
    resolved = {
        "good_angle_deg": number(config["good_angle_deg"], "good_angle_deg"),
        "degraded_angle_deg": number(config["degraded_angle_deg"], "degraded_angle_deg"),
        "good_offset_m": number(config["good_offset_m"], "good_offset_m"),
        "degraded_offset_m": number(config["degraded_offset_m"], "degraded_offset_m"),
        "tls_svd_numeric_angle_deg": number(config["tls_svd_numeric_angle_deg"],
                                            "tls_svd_numeric_angle_deg"),
        "tls_svd_numeric_offset_m": number(config["tls_svd_numeric_offset_m"],
                                           "tls_svd_numeric_offset_m"),
        "degraded_confidence_cap": number(config["degraded_confidence_cap"],
                                          "degraded_confidence_cap"),
        "min_good_confidence": number(config["min_good_confidence"], "min_good_confidence"),
        "min_degraded_confidence": number(config["min_degraded_confidence"],
                                          "min_degraded_confidence"),
        "degraded_updates_enabled": _strict_bool(config["degraded_updates_enabled"],
                                                 "degraded_updates_enabled"),
        "ls_only_updates_enabled": _strict_bool(config["ls_only_updates_enabled"],
                                                "ls_only_updates_enabled"),
    }
    require(0.0 < resolved["good_angle_deg"] < resolved["degraded_angle_deg"],
            "angle thresholds must satisfy 0 < good < degraded")
    require(0.0 < resolved["good_offset_m"] < resolved["degraded_offset_m"],
            "offset thresholds must satisfy 0 < good < degraded")
    require(0.0 < resolved["tls_svd_numeric_angle_deg"] <= resolved["good_angle_deg"],
            "numeric angle tolerance out of range")
    require(0.0 < resolved["tls_svd_numeric_offset_m"] <= resolved["good_offset_m"],
            "numeric offset tolerance out of range")
    require(0.0 < resolved["min_degraded_confidence"] <= resolved["degraded_confidence_cap"]
            < resolved["min_good_confidence"] <= 1.0,
            "confidence thresholds must satisfy min_degraded <= cap < min_good <= 1")
    return resolved


def consensus_config_id(resolved_config):
    return CONSENSUS_CONFIG_PREFIX + digest(resolved_config)


def quality_summary(report):
    """B 报告 → C 成员质量摘要（含原因与来源 ID，供追溯）。"""
    validate_quality_report(report)
    return {"valid": bool(report["valid"]),
            "confidence": float(report["confidence_geo"]),
            "reasons": list(report["reject_reasons"]),
            "quality_report_id": report["report_id"]}


def _member(estimate, domain, summary):
    validate_plane_estimate(estimate, domain)
    require(isinstance(summary, dict)
            and {"valid", "confidence", "reasons"} <= set(summary)
            and set(summary) <= {"valid", "confidence", "reasons", "quality_report_id"},
            "quality summary has missing/unsupported keys")
    _strict_bool(summary["valid"], "quality valid")
    confidence = number(summary["confidence"], "quality confidence")
    require(0.0 <= confidence <= 1.0, "quality confidence out of range")
    require(isinstance(summary["reasons"], list)
            and all(isinstance(item, str) and item for item in summary["reasons"]),
            "quality reasons must be text codes")
    record = {"numerical_valid": bool(estimate["numerical_valid"]),
              "quality_valid": bool(summary["valid"]),
              "confidence": confidence if summary["valid"] else 0.0,
              "reasons": list(summary["reasons"]),
              "estimate_digest": digest(estimate)}
    if "quality_report_id" in summary:
        text(summary["quality_report_id"], "quality_report_id")
        record["quality_report_id"] = summary["quality_report_id"]
    return record


def _plane_of(member, estimate, anchor, reasons):
    if not member["numerical_valid"]:
        return None
    try:
        vector, offset = canonical_plane(estimate["normal_source"],
                                         estimate["offset_source_m"], anchor)
    except ValueError:
        member["numerical_valid"] = False
        if REASON_NORMAL_INVALID not in reasons:
            reasons.append(REASON_NORMAL_INVALID)
        return None
    normal = np.asarray(vector, dtype=np.float64)
    pitch = math.degrees(math.atan2(-float(normal[0]), float(normal[2])))
    roll = math.degrees(math.asin(float(np.clip(normal[1], -1.0, 1.0))))
    return {"normal": normal, "offset": float(offset), "pitch": pitch, "roll": roll}


def _pair_level(angle_deg, offset_gap_m, resolved):
    if angle_deg <= resolved["good_angle_deg"] \
            and offset_gap_m <= resolved["good_offset_m"]:
        return "GOOD"
    if angle_deg <= resolved["degraded_angle_deg"] \
            and offset_gap_m <= resolved["degraded_offset_m"]:
        return "DEGRADED"
    return "CONFLICT"


def _maximal_cliques(nodes, consistent):
    cliques = []
    for size in (3, 2):
        for combo in combinations(nodes, size):
            if all(consistent(pair) for pair in combinations(combo, 2)):
                cliques.append(combo)
    return [combo for combo in cliques
            if not any(set(combo) < set(other) for other in cliques)]


def build_consensus(estimates, domain, quality, config):
    """对同一 domain 的三估计器结果与质量摘要做一致性仲裁（深拷贝输出）。"""
    resolved = resolve_consensus_config(config)
    validate_point_domain(domain)
    keys(estimates, ESTIMATOR_ORDER, "estimates")
    keys(quality, ESTIMATOR_ORDER, "quality")
    anchor = domain["spatial_basis"]["up_axis"]
    reasons = []
    members = {}
    planes = {}
    for name in ESTIMATOR_ORDER:
        estimate = estimates[name]
        require(estimate["estimator_id"] == name, "estimator id / slot mismatch")
        member = _member(estimate, domain, quality[name])
        members[name] = member
        planes[name] = _plane_of(member, estimate, anchor, reasons)
        for reason in member["reasons"]:
            if not member["quality_valid"] and reason not in reasons:
                reasons.append(reason)
    pairwise = []
    levels = {}
    for first, second in combinations(ESTIMATOR_ORDER, 2):
        if planes[first] is None or planes[second] is None:
            pairwise.append({"a": first, "b": second, "level": "UNAVAILABLE",
                             "angle_deg": None, "offset_gap_m": None,
                             "pitch_gap_deg": None, "roll_gap_deg": None,
                             "reason": "member plane unavailable"})
            levels[(first, second)] = "UNAVAILABLE"
            continue
        dot = float(np.clip(np.dot(planes[first]["normal"], planes[second]["normal"]),
                            -1.0, 1.0))
        angle = math.degrees(math.acos(dot))
        offset_gap = abs(planes[first]["offset"] - planes[second]["offset"])
        pitch_gap = abs(planes[first]["pitch"] - planes[second]["pitch"])
        roll_gap = abs(planes[first]["roll"] - planes[second]["roll"])
        level = _pair_level(angle, offset_gap, resolved)
        pairwise.append({"a": first, "b": second, "level": level, "angle_deg": angle,
                         "offset_gap_m": offset_gap, "pitch_gap_deg": pitch_gap,
                         "roll_gap_deg": roll_gap, "reason": None})
        levels[(first, second)] = level
    numeric_check_ok = False
    if planes["tls"] is not None and planes["svd"] is not None:
        numeric_check_ok = (levels[("tls", "svd")] == "GOOD") and (
            abs(planes["tls"]["offset"] - planes["svd"]["offset"])
            <= resolved["tls_svd_numeric_offset_m"]) and (
            math.degrees(math.acos(float(np.clip(
                np.dot(planes["tls"]["normal"], planes["svd"]["normal"]),
                -1.0, 1.0)))) <= resolved["tls_svd_numeric_angle_deg"])
        if not numeric_check_ok and REASON_NUMERIC not in reasons:
            reasons.append(REASON_NUMERIC)
    elif REASON_NUMERIC not in reasons:
        reasons.append(REASON_NUMERIC)
    active = [name for name in ESTIMATOR_ORDER
              if members[name]["quality_valid"] and members[name]["numerical_valid"]
              and planes[name] is not None]

    def consistent(pair):
        return levels[pair] in ("GOOD", "DEGRADED")

    candidates = [combo for combo in _maximal_cliques(active, consistent)
                  if len(combo) >= 2]
    supporting = []
    status = "BAD"
    if numeric_check_ok and set(active) == set(ESTIMATOR_ORDER) and all(
            levels[pair] == "GOOD" for pair in combinations(ESTIMATOR_ORDER, 2)):
        status = "GOOD"
        supporting = list(ESTIMATOR_ORDER)
    elif len(candidates) == 1:
        status = "DEGRADED"
        supporting = list(candidates[0])
    else:
        if candidates and REASON_NO_CONSENSUS not in reasons:
            reasons.append(REASON_NO_CONSENSUS)
        elif not candidates and REASON_NO_CONSENSUS not in reasons:
            reasons.append(REASON_NO_CONSENSUS)
    if supporting:
        member_confidences = [members[name]["confidence"] for name in supporting]
        min_confidence = min(member_confidences)
    else:
        min_confidence = 0.0
    if status == "GOOD" and min_confidence < resolved["min_good_confidence"]:
        status = "DEGRADED"
        if REASON_LOW_CONFIDENCE not in reasons:
            reasons.append(REASON_LOW_CONFIDENCE)
    if status == "DEGRADED" and min_confidence < resolved["min_degraded_confidence"]:
        status = "BAD"
        supporting = []
        if REASON_LOW_CONFIDENCE not in reasons:
            reasons.append(REASON_LOW_CONFIDENCE)
        if REASON_NO_CONSENSUS not in reasons:
            reasons.append(REASON_NO_CONSENSUS)
    if status == "DEGRADED" and "ransac" not in supporting \
            and members["ransac"]["numerical_valid"] \
            and REASON_ROBUST_DIVERGENCE not in reasons:
        reasons.append(REASON_ROBUST_DIVERGENCE)
    families = sorted(set(FAMILIES[name] for name in supporting))
    cross_family = len(families) > 1
    if status == "GOOD":
        selected = "tls"
        cap = 1.0
        update_allowed = True
    elif status == "DEGRADED":
        ranked = sorted(supporting,
                        key=lambda name: (-members[name]["confidence"],
                                          ESTIMATOR_ORDER.index(name)))
        selected = ranked[0] if ranked else None
        cap = resolved["degraded_confidence_cap"]
        update_allowed = (resolved["degraded_updates_enabled"] if cross_family
                          else resolved["ls_only_updates_enabled"])
    else:
        selected = None
        cap = 0.0
        update_allowed = False
    confidence = min(min_confidence, cap) if status != "BAD" else 0.0
    report = {"kind": CONSENSUS_KIND, "schema": CONSENSUS_SCHEMA,
              "frame_key": copy.deepcopy(domain["frame_key"]),
              "domain_id": domain["domain_id"], "config_id": domain["config_id"],
              "consensus_config_id": consensus_config_id(resolved), "units": UNITS,
              "members": members, "pairwise": pairwise, "status": status,
              "supporting_estimators": supporting,
              "supporting_families": families, "numeric_check_ok": bool(numeric_check_ok),
              "selected_estimator": selected, "confidence": float(confidence),
              "confidence_cap": float(cap),
              "update_candidate_allowed": bool(update_allowed),
              "reason_codes": list(reasons)}
    report["report_id"] = "agl-consensus:" + digest(report)
    return report


def validate_consensus_report(report, domain=None):
    keys(report, REPORT_FIELDS, "consensus report")
    require(report["kind"] == CONSENSUS_KIND and type(report["schema"]) is int
            and report["schema"] == CONSENSUS_SCHEMA, "consensus kind/schema")
    require(report["units"] == UNITS, "consensus units")
    require(report["status"] in STATUSES, "consensus status")
    text(report["report_id"], "report_id")
    require(report["report_id"].startswith("agl-consensus:"), "report id namespace")
    require(report["report_id"] == "agl-consensus:" + digest(
        {k: v for k, v in report.items() if k != "report_id"}), "report ID/content mismatch")
    require(type(report["numeric_check_ok"]) is bool, "numeric_check_ok")
    require(type(report["update_candidate_allowed"]) is bool, "update flag")
    require(isinstance(report["supporting_estimators"], list)
            and all(name in ESTIMATOR_ORDER for name in report["supporting_estimators"]),
            "supporting estimators")
    require(report["selected_estimator"] is None
            or report["selected_estimator"] in ESTIMATOR_ORDER, "selected estimator")
    confidence = number(report["confidence"], "confidence")
    require(0.0 <= confidence <= 1.0, "confidence out of range")
    require(report["status"] == "BAD" or bool(report["supporting_estimators"]),
            "non-BAD needs support")
    require(report["status"] != "BAD" or confidence == 0.0, "BAD confidence must be 0")
    if domain is not None:
        require(report["domain_id"] == domain["domain_id"], "report/domain mismatch")
        require(digest(report["frame_key"]) == digest(domain["frame_key"]),
                "report frame mismatch")
    return None
