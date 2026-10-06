"""AGL-E source→adaptive-display 变换与只读离线应用（纯 core，无 ROS/写盘）。

R=Rx(roll)@Ry(pitch)、t=[0,0,observed_tz]；yaw/tx/ty=0 gauge；physical 1.14 是
独立只读测量（不是拟合目标）；candidate 不直接应用；HOLD 可保留最近已接受数值
但 fresh/eligible_for_geometry 分开；不冒充旧 geometry_calibration kind；写盘/CLI/
WebUI 属后续单。
"""
import copy
import hashlib
import math

import numpy as np

from ..ground_evidence import digest, keys, number, require, text
from ..numeric import strict_numeric_array
from .contracts import display_rotation, validate_frame_key

TRANSFORM_KIND = "adaptive_display_transform"
TRANSFORM_SCHEMA = 1
TO_FRAME = "ground_adaptive_display"
PHYSICAL_HEIGHT_M = 1.14
OFFLINE_KIND = "adaptive_offline_result"
FRAME_REPORT_KIND = "adaptive_frame_report"
TRANSFORM_FIELDS = ("kind", "schema", "transform_id", "from_frame", "to_frame", "units",
                    "rotation", "translation_m", "accepted_pitch_deg", "accepted_roll_deg",
                    "observed_tz_m", "frame_key", "domain_id", "config_id",
                    "controller_epoch", "accept_revision", "mode", "physical_height_m",
                    "physical_verified", "extrinsics_verified", "runtime_eligible",
                    "measurement_reference")
MEASUREMENT_FIELDS = ("physical_height_m", "note")


def build_display_transform(pitch_deg, roll_deg, offset_m, frame_key, domain_id,
                            config_id, controller_epoch=0, accept_revision=None):
    """由已接受(accepted)平面的角度与观测 tz 构建显示变换（numeric 记录，非物理）。"""
    validate_frame_key(frame_key)
    text(domain_id, "domain_id")
    text(config_id, "config_id")
    pitch = number(pitch_deg, "pitch_deg")
    roll = number(roll_deg, "roll_deg")
    offset = number(offset_m, "offset_m")
    require(0.0 < offset <= 50.0, "observed tz out of numeric domain (0, 50]")
    require(type(controller_epoch) is int and controller_epoch >= 0,
            "controller_epoch must be a nonnegative integer")
    if accept_revision is not None:
        require(type(accept_revision) is int and accept_revision >= 0,
                "accept_revision must be a nonnegative integer")
    rotation = np.asarray(display_rotation(pitch, roll), dtype=np.float64)
    transform = {
        "kind": TRANSFORM_KIND, "schema": TRANSFORM_SCHEMA,
        "from_frame": frame_key["source_frame"], "to_frame": TO_FRAME, "units": "m",
        "rotation": [[float(v) for v in row] for row in rotation],
        "translation_m": [0.0, 0.0, offset],
        "accepted_pitch_deg": pitch, "accepted_roll_deg": roll,
        "observed_tz_m": offset, "frame_key": copy.deepcopy(frame_key),
        "domain_id": domain_id, "config_id": config_id,
        "controller_epoch": controller_epoch, "accept_revision": accept_revision,
        "mode": "display_only", "physical_height_m": PHYSICAL_HEIGHT_M,
        "physical_verified": False, "extrinsics_verified": False,
        "runtime_eligible": False,
        "measurement_reference": {"physical_height_m": PHYSICAL_HEIGHT_M,
                                  "note": "independent laser-user measurement; read-only; "
                                          "never a fit target"}}
    transform["transform_id"] = "agl-transform:" + digest(
        {k: v for k, v in transform.items() if k != "transform_id"})
    validate_display_transform(transform)
    return transform


def validate_display_transform(transform):
    keys(transform, TRANSFORM_FIELDS, "display transform")
    require(transform["kind"] == TRANSFORM_KIND
            and type(transform["schema"]) is int and transform["schema"] == TRANSFORM_SCHEMA,
            "transform kind/schema")
    text(transform["from_frame"], "from_frame")
    require(transform["to_frame"] == TO_FRAME and transform["to_frame"] != transform["from_frame"],
            "transform to_frame")
    require(transform["units"] == "m", "transform units must be m")
    validate_frame_key(transform["frame_key"])
    text(transform["domain_id"], "domain_id")
    text(transform["config_id"], "config_id")
    rotation = strict_numeric_array(transform["rotation"], (3, 3), "rotation")
    require(np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-12, rtol=0),
            "rotation must be orthonormal")
    require(abs(float(np.linalg.det(rotation)) - 1.0) <= 1e-12, "rotation must be proper (+1)")
    require(abs(float(rotation[0, 1])) <= 1e-15, "yaw gauge must be zero")
    translation = strict_numeric_array(transform["translation_m"], (3,), "translation_m")
    require(translation[0] == 0.0 and translation[1] == 0.0, "tx/ty gauge must be zero")
    require(translation[2] > 0.0, "observed tz must be positive")
    normal = rotation[2]
    require(float(np.linalg.norm(rotation @ normal - np.array([0.0, 0.0, 1.0]))) <= 1e-12,
            "R @ n must equal up")
    number(transform["accepted_pitch_deg"], "accepted_pitch_deg")
    number(transform["accepted_roll_deg"], "accepted_roll_deg")
    require(number(transform["observed_tz_m"], "observed_tz_m") == float(translation[2]),
            "observed tz / translation mismatch")
    require(transform["mode"] == "display_only", "transform mode")
    require(transform["physical_height_m"] == PHYSICAL_HEIGHT_M,
            "physical height record mismatch")
    require(transform["physical_verified"] is False
            and transform["extrinsics_verified"] is False
            and transform["runtime_eligible"] is False, "qualification promotion forbidden")
    reference = transform["measurement_reference"]
    keys(reference, MEASUREMENT_FIELDS, "measurement_reference")
    require(reference["physical_height_m"] == PHYSICAL_HEIGHT_M
            and isinstance(reference["note"], str) and reference["note"], "reference record")
    require(transform["transform_id"] == "agl-transform:" + digest(
        {k: v for k, v in transform.items() if k != "transform_id"}),
        "transform ID/content mismatch")
    return None


def _valid_mask(array):
    """有效行 = 有限且非全零；全零行是采集链路的无效占位符，不参与映射。"""
    return np.all(np.isfinite(array), axis=1) & np.any(array != 0.0, axis=1)


def apply_display_transform(points, transform):
    """只读应用：输入不变；无效行（非有限或全零）原样保留并计数。"""
    validate_display_transform(transform)
    array = np.asarray(points, dtype=np.float64)
    require(array.ndim == 2 and array.shape[1] == 3, "points must be (N,3)")
    rotation = np.asarray(transform["rotation"], dtype=np.float64)
    translation = np.asarray(transform["translation_m"], dtype=np.float64)
    finite = _valid_mask(array)
    output = array.copy()
    if bool(finite.any()):
        output[finite] = array[finite] @ rotation.T + translation
    invalid_count = int((~finite).sum())
    return {"points": output, "point_count": int(len(array)),
            "invalid_row_count": invalid_count,
            "valid_row_count": int(len(array) - invalid_count)}


def signed_residuals(points, transform):
    validate_display_transform(transform)
    array = np.asarray(points, dtype=np.float64)
    require(array.ndim == 2 and array.shape[1] == 3, "points must be (N,3)")
    normal = np.asarray(transform["rotation"], dtype=np.float64)[2]
    offset = float(transform["observed_tz_m"])
    finite = _valid_mask(array)
    values = np.full(len(array), np.nan, dtype=np.float64)
    if bool(finite.any()):
        values[finite] = array[finite] @ normal + offset
    return values


def invert_display_transform(transform):
    validate_display_transform(transform)
    rotation = np.asarray(transform["rotation"], dtype=np.float64)
    translation = np.asarray(transform["translation_m"], dtype=np.float64)
    return {"rotation": rotation.T.tolist(),
            "translation_m": (-rotation.T @ translation).tolist()}


def display_sample(points, budget):
    """确定性显示抽样（仅展示；不参与 fit/验收，也不修改输入）。"""
    require(type(budget) is int and budget >= 0, "budget must be a nonnegative integer")
    array = np.asarray(points, dtype=np.float64)
    require(array.ndim == 2 and array.shape[1] == 3, "points must be (N,3)")
    if budget == 0:
        return array[:0].copy()
    stride = int(math.ceil(len(array) / budget)) if len(array) else 1
    return array[::stride].copy()


def run_offline(points, source_indices, frame_key, decision, transform,
                historical_failures=None):
    """只读离线结果：mapped/资格/来源绑定；无 accepted 不补 identity、不写文件。"""
    validate_frame_key(frame_key)
    require(isinstance(decision, dict), "decision must be an object")
    rows = source_indices
    require(isinstance(rows, np.ndarray) and rows.dtype == np.int64
            and rows.ndim == 1 and len(rows) == len(points),
            "source_indices must be int64 (N,)")
    invalid = int((~_valid_mask(np.asarray(points, dtype=np.float64))).sum())
    result = {"kind": OFFLINE_KIND, "schema": 1, "units": "m",
              "frame_key": copy.deepcopy(frame_key),
              "state": decision.get("state"),
              "applied": bool(decision.get("applied", False)),
              "fresh": bool(decision.get("fresh", False)),
              "eligible_for_geometry": bool(decision.get("eligible_for_geometry", False)),
              "accept_revision": decision.get("accept_revision"),
              "point_count": int(len(points)), "invalid_row_count": invalid,
              "source_rows": rows.tolist(),
              "historical_leave_one_out_failures": copy.deepcopy(historical_failures)}
    if transform is None:
        result["mode"] = "reference_only"
        result["transform"] = None
        result["mapped_points"] = None
        result["result_id"] = "agl-offline:" + digest(
            {k: v for k, v in result.items() if k != "result_id"})
        return result
    validate_display_transform(transform)
    require(digest(transform["frame_key"]) == digest(frame_key),
            "transform / output frame mismatch")
    applied = apply_display_transform(points, transform)
    result["mode"] = "accepted" if result["applied"] else "hold_numeric"
    result["transform"] = copy.deepcopy(transform)
    result["mapped_points"] = applied["points"]
    result["mapped_sha256"] = "sha256:" + hashlib.sha256(
        applied["points"].tobytes()).hexdigest()
    result["valid_row_count"] = applied["valid_row_count"]
    result["result_id"] = "agl-offline:" + digest(
        {k: v for k, v in result.items() if k not in ("result_id", "mapped_points")})
    return result


def build_frame_report(rows, historical_failures=None):
    """逐帧 raw/filtered/accepted 与 pose spread；历史 FAIL 仅引用、不重算。"""
    require(isinstance(rows, list) and bool(rows), "frame rows required")
    resolved = []
    for row in rows:
        keys(row, ("frame_key", "raw", "filtered", "accepted", "rms_m", "p95_m"),
             "frame row")
        validate_frame_key(row["frame_key"])
        entry = {"frame_key": copy.deepcopy(row["frame_key"]),
                 "raw": strict_numeric_array(
                     [row["raw"]["pitch_deg"], row["raw"]["roll_deg"], row["raw"]["offset_m"]],
                     (3,), "raw"),
                 "filtered": strict_numeric_array(
                     [row["filtered"]["pitch_deg"], row["filtered"]["roll_deg"],
                      row["filtered"]["offset_m"]], (3,), "filtered"),
                 "accepted": strict_numeric_array(
                     [row["accepted"]["pitch_deg"], row["accepted"]["roll_deg"],
                      row["accepted"]["offset_m"]], (3,), "accepted"),
                 "rms_m": number(row["rms_m"], "rms_m"),
                 "p95_m": number(row["p95_m"], "p95_m")}
        resolved.append(entry)
    accepted = np.array([entry["accepted"] for entry in resolved])
    report = {"kind": FRAME_REPORT_KIND, "schema": 1, "units": "m",
              "per_frame": [{"frame_key": entry["frame_key"],
                             "raw_pitch_deg": float(entry["raw"][0]),
                             "raw_roll_deg": float(entry["raw"][1]),
                             "raw_offset_m": float(entry["raw"][2]),
                             "filtered_pitch_deg": float(entry["filtered"][0]),
                             "filtered_roll_deg": float(entry["filtered"][1]),
                             "filtered_offset_m": float(entry["filtered"][2]),
                             "accepted_pitch_deg": float(entry["accepted"][0]),
                             "accepted_roll_deg": float(entry["accepted"][1]),
                             "accepted_offset_m": float(entry["accepted"][2]),
                             "rms_m": entry["rms_m"], "p95_m": entry["p95_m"]}
                            for entry in resolved],
              "pose_spread": {"pitch_std_deg": float(np.std(accepted[:, 0])),
                              "roll_std_deg": float(np.std(accepted[:, 1])),
                              "offset_std_m": float(np.std(accepted[:, 2]))},
              "historical_leave_one_out_failures": copy.deepcopy(historical_failures),
              "historical_note": "citation only; not recomputed; not to be greened by filtering"}
    report["report_id"] = "agl-frame-report:" + digest(
        {k: v for k, v in report.items() if k != "report_id"})
    return report
