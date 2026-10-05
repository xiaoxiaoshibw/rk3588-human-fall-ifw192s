"""Static offline P02 quality and cross-family comparison, not AGL temporal control."""
import math
import numpy as np
from leveling_estimators import ESTIMATORS

PROFILE = {
    "profile_id": "offline_p02_workbench_v1", "schema": 1,
    "approval": "DRAFT", "scope": "offline_display_only", "runtime_enabled": False,
    "min_points_per_region": 20, "rms_max_m": .03, "p95_max_m": .05,
    "inlier_threshold_m": .05, "min_support_ratio": .8,
    "min_lambda2_lambda3": .01, "min_tangent_extent_m": .1,
    "normal_gap_max_deg": 2., "offset_gap_max_m": .03,
    "max_abs_pitch_deg": 75., "max_abs_roll_deg": 45.,
    "tls_svd_gap_max_deg": .0001, "tls_svd_offset_max_m": .000001,
    "ransac_seed": 20261001, "ransac_iterations": 861,
    "estimator_variant": "raw_no_refinement", "holdout_frames": 3,
    "physical_verified": False, "extrinsics_verified": False, "runtime_eligible": False,
}


def rotation(pitch_deg, roll_deg):
    p, r = math.radians(pitch_deg), math.radians(roll_deg)
    cp, sp, cr, sr = math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([[cp, 0., sp], [sr*sp, cr, -sr*cp], [-cr*sp, sr, cr*cp]])


def statistics(points, normal, offset):
    if not len(points):
        return {"count": 0, "rms_m": None, "p95_m": None, "support_ratio": 0., "status": "FAIL"}
    residual = np.einsum("ij,j->i", points, normal) + offset
    rms = float(np.sqrt(np.mean(residual**2)))
    p95 = float(np.percentile(np.abs(residual), 95))
    support = float(np.mean(np.abs(residual) <= PROFILE["inlier_threshold_m"]))
    ok = (len(points) >= PROFILE["min_points_per_region"] and rms <= PROFILE["rms_max_m"]
          and p95 <= PROFILE["p95_max_m"] and support >= PROFILE["min_support_ratio"])
    return {"count": len(points), "rms_m": rms, "p95_m": p95, "support_ratio": support,
            "median_signed_m": float(np.median(residual)), "status": "PASS" if ok else "FAIL"}


def compare(points, regions, holdouts, anchor):
    """Owned frozen float64 fit points; holdouts never passed to an estimator."""
    covariance = np.cov((points - points.mean(axis=0)).T)
    values, vectors = np.linalg.eigh(covariance)
    spread = (points - points.mean(axis=0)) @ vectors[:, 1:]
    ratio = float(max(0., values[1]) / max(values[2], 1e-30))
    extents = np.ptp(spread, axis=0).tolist()
    degenerate = ratio < PROFILE["min_lambda2_lambda3"] or min(extents) < PROFILE["min_tangent_extent_m"]
    results = {}
    for name, estimate in ESTIMATORS.items():
        result = {"estimator_id": name, "family": "robust" if name == "ransac" else "least_squares",
                  "valid": False, "reject_reasons": [], "normal_source": None,
                  "offset_source_m": None, "pitch_deg": None, "roll_deg": None, "R": None, "t": None}
        try:
            normal, offset = estimate(points)
            norm = float(np.linalg.norm(normal))
            if not np.isfinite(normal).all() or not math.isfinite(offset) or norm < 1e-9:
                raise ValueError("非法平面")
            normal, offset = normal/norm, offset/norm
            alignment = float(normal @ anchor)
            if abs(alignment) < .1:
                raise ValueError("方向锚点歧义")
            if alignment < 0:
                normal, offset = -normal, -offset
            pitch = math.degrees(math.atan2(-normal[0], normal[2]))
            roll = math.degrees(math.asin(float(np.clip(normal[1], -1, 1))))
            R, t = rotation(pitch, roll), [0., 0., offset]
            if not np.allclose(R[2], normal, atol=1e-10) or not np.allclose(R @ R.T, np.eye(3), atol=1e-10):
                raise ValueError("平面与旋转不一致")
            full = statistics(points, normal, offset)
            per_region = {str(i): statistics(points[regions == i], normal, offset) for i in range(1, 5)}
            held = [{"ordinal": h["ordinal"], "full": statistics(h["points"], normal, offset),
                     "regions": {str(i): statistics(h["points"][h["regions"] == i], normal, offset)
                                 for i in range(1, 5)}} for h in holdouts]
            reasons = []
            if degenerate:
                reasons.append("GL_DEGENERATE_DOMAIN")
            if abs(pitch) > PROFILE["max_abs_pitch_deg"] or abs(roll) > PROFILE["max_abs_roll_deg"] or offset <= 0:
                reasons.append("GL_IMPLAUSIBLE_POSE")
            if full["status"] != "PASS":
                reasons.append("GL_FULL_DOMAIN_QUALITY")
            if any(v["status"] != "PASS" for v in per_region.values()):
                reasons.append("GL_REGION_QUALITY")
            if any(h["full"]["status"] != "PASS" or any(s["status"] != "PASS" for s in h["regions"].values()) for h in held):
                reasons.append("GL_HOLDOUT_QUALITY")
            result.update(normal_source=normal.tolist(), offset_source_m=offset, pitch_deg=pitch, roll_deg=roll,
                          R=R.tolist(), t=t, full=full, regions=per_region, holdouts=held,
                          valid=not reasons, reject_reasons=reasons)
        except (ValueError, np.linalg.LinAlgError) as exc:
            result["reject_reasons"] = ["GL_NUMERICAL_INVALID: " + str(exc)]
        results[name] = result
    pairwise = []
    for a, b in (("tls", "svd"), ("tls", "ransac"), ("svd", "ransac")):
        ra, rb = results[a], results[b]
        angle, gap = None, None
        if ra["normal_source"] is not None and rb["normal_source"] is not None:
            angle = math.degrees(math.acos(float(np.clip(np.dot(ra["normal_source"], rb["normal_source"]), -1, 1))))
            gap = abs(ra["offset_source_m"] - rb["offset_source_m"])
        ok = angle is not None and angle <= PROFILE["normal_gap_max_deg"] and gap <= PROFILE["offset_gap_max_m"]
        pairwise.append({"a": a, "b": b, "angle_deg": angle, "offset_gap_m": gap, "status": "PASS" if ok else "FAIL"})
    ls = pairwise[0]
    numeric_ok = (ls["angle_deg"] is not None and ls["angle_deg"] <= PROFILE["tls_svd_gap_max_deg"]
                  and ls["offset_gap_m"] <= PROFILE["tls_svd_offset_max_m"])
    if not numeric_ok:
        for name in ("tls", "svd"):
            results[name]["valid"] = False
            results[name]["reject_reasons"].append("GL_TLS_SVD_NUMERIC_MISMATCH")
    good = numeric_ok and all(r["valid"] for r in results.values()) and all(p["status"] == "PASS" for p in pairwise)
    return {"estimators": results, "pairwise": pairwise, "numeric_check_ok": numeric_ok,
            "domain_geometry": {"lambda2_lambda3": ratio, "tangent_extents_m": extents},
            "consensus": "GOOD" if good else "NO_RECOMMENDATION",
            "recommended": "tls" if good else None,
            "recommendation_basis": "三方法同域有效且跨家族一致；TLS/SVD是同一LS家族" if good else "存在质量失败或方法冲突，不以TLS/SVD二票压RANSAC"}
