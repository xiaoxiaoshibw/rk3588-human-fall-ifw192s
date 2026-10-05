"""AGL-A PointDomain：公共几何预筛、来源绑定与所有权快照。

结构性预筛只丢弃全零行（输入必须已有限），全高度、不按残差；ROI/range/cap
重选不在估计器内发生，只以 selector 显式绑定。``domain_id`` 内容寻址：
任何"同 ID 不同内容"在 validate/消费前拒绝，不修复、不回写。
"""
import copy
import hashlib

import numpy as np

from ..ground_evidence import digest, keys, number, require, text
from ..numeric import strict_numeric_array
from .contracts import DOMAIN_KIND, SCHEMA, UNITS, validate_frame_key

PREFILTER_POLICY = "finite_nonzero_full_height_v1"
DOMAIN_FIELDS = ("kind", "schema", "frame_key", "selector", "config_id", "units",
                 "point_count", "source_points", "source_indices", "weights",
                 "region_codes", "point_sha256", "rows_sha256", "weights_sha256",
                 "region_codes_sha256", "prefilter", "spatial_basis",
                 "source_provenance", "domain_id")
PREFILTER_FIELDS = ("policy", "input_row_count", "kept_row_count",
                    "dropped_zero_count", "height_or_residual_trim")
SPATIAL_BASIS_FIELDS = ("up_axis", "provenance", "version")


def _sha256(array):
    return hashlib.sha256(array.tobytes()).hexdigest()


def _integer_array(values, length, name):
    if values is None:
        return None
    if isinstance(values, np.ndarray):
        require(values.ndim == 1, name + " must be one-dimensional")
        items = values
    elif isinstance(values, (list, tuple)):
        items = values
    else:
        raise ValueError(name + " must be an integer sequence")
    require(len(items) == length, name + " length mismatch")
    out = np.empty(length, dtype=np.int64)
    for index, item in enumerate(items):
        if isinstance(item, (bool, np.bool_)) or not isinstance(item, (int, np.integer)):
            raise ValueError(name + " must be integers (bool rejected)")
        out[index] = int(item)
    return out


def _validate_spatial_basis(basis):
    keys(basis, SPATIAL_BASIS_FIELDS, "spatial basis")
    up = strict_numeric_array(basis["up_axis"], (3,), "up_axis")
    require(abs(float(np.linalg.norm(up)) - 1.0) <= 1e-6,
            "up_axis must be a unit vector")
    text(basis["provenance"], "spatial basis provenance")
    require(type(basis["version"]) is int and basis["version"] >= 1,
            "spatial basis version")
    return [float(v) for v in up]


def _domain_binding(record):
    return {"kind": record["kind"], "schema": record["schema"],
            "frame_key": record["frame_key"], "selector": record["selector"],
            "config_id": record["config_id"], "units": record["units"],
            "point_count": record["point_count"],
            "point_sha256": record["point_sha256"],
            "rows_sha256": record["rows_sha256"],
            "weights_sha256": record["weights_sha256"],
            "region_codes_sha256": record["region_codes_sha256"],
            "prefilter": record["prefilter"], "spatial_basis": record["spatial_basis"],
            "source_provenance": record["source_provenance"]}


def build_point_domain(points, frame_key, selector, config_id, source_provenance,
                       spatial_basis, source_indices=None, weights=None,
                       region_codes=None):
    """由调用者拥有的 source 数组构建不可变 PointDomain（深拷贝、内容寻址）。

    ``points`` 必须是有限的 (N,3) 数值序列/数组（bool/string/NaN/Inf 拒）；
    预筛只丢全零行并记录计数；``source_indices`` 默认 0..N-1 且必须严格递增唯一。
    """
    validate_frame_key(frame_key)
    keys(selector, ("selector_id", "version"), "selector")
    text(selector["selector_id"], "selector_id")
    require(type(selector["version"]) is int and selector["version"] >= 1,
            "selector version must be a positive integer")
    text(config_id, "config_id")
    require(config_id.startswith("agl-config:"),
            "config_id must be an agl-config: identity")
    text(source_provenance, "source_provenance")
    basis = copy.deepcopy(spatial_basis)
    basis["up_axis"] = _validate_spatial_basis(basis)
    if isinstance(points, np.ndarray):
        require(points.ndim == 2 and points.shape[1] == 3,
                "points must be an (N,3) array")
        row_count = int(points.shape[0])
    else:
        require(isinstance(points, (list, tuple)),
                "points must be an (N,3) sequence or array")
        row_count = len(points)
    array = strict_numeric_array(points, (row_count, 3), "points")
    indices = _integer_array(source_indices, row_count, "source_indices")
    if indices is None:
        indices = np.arange(row_count, dtype=np.int64)
    require(bool(np.all(indices >= 0)), "source_indices must be nonnegative")
    require(bool(np.all(np.diff(indices) > 0)),
            "source_indices must be strictly increasing")
    weights_array = (strict_numeric_array(weights, (row_count,), "weights")
                     if weights is not None else np.ones(row_count, dtype=np.float64))
    require(bool(np.all(weights_array > 0.0)), "weights must be positive")
    codes = _integer_array(region_codes, row_count, "region_codes")
    if codes is None:
        codes = np.full(row_count, -1, dtype=np.int64)
    keep = np.any(array != 0.0, axis=1)
    kept = np.ascontiguousarray(array[keep], dtype=np.float64)
    require(len(kept) >= 1, "point domain has no usable nonzero points")
    kept_indices = np.ascontiguousarray(indices[keep], dtype=np.int64)
    kept_weights = np.ascontiguousarray(weights_array[keep], dtype=np.float64)
    kept_codes = np.ascontiguousarray(codes[keep], dtype=np.int64)
    record = {"kind": DOMAIN_KIND, "schema": SCHEMA,
              "frame_key": copy.deepcopy(frame_key),
              "selector": copy.deepcopy(selector), "config_id": config_id,
              "units": UNITS, "point_count": int(len(kept)),
              "source_points": kept, "source_indices": kept_indices,
              "weights": kept_weights, "region_codes": kept_codes,
              "point_sha256": _sha256(kept), "rows_sha256": _sha256(kept_indices),
              "weights_sha256": _sha256(kept_weights),
              "region_codes_sha256": _sha256(kept_codes),
              "prefilter": {"policy": PREFILTER_POLICY,
                            "input_row_count": int(row_count),
                            "kept_row_count": int(len(kept)),
                            "dropped_zero_count": int(row_count - len(kept)),
                            "height_or_residual_trim": False},
              "spatial_basis": basis, "source_provenance": source_provenance}
    record["domain_id"] = "agl-domain:" + digest(_domain_binding(record))
    return record


def validate_point_domain(domain):
    """消费前重核结构与内容寻址；"同 ID 不同内容"即拒，不分修复阶段。"""
    keys(domain, DOMAIN_FIELDS, "point domain")
    require(domain["kind"] == DOMAIN_KIND, "domain kind")
    require(type(domain["schema"]) is int and domain["schema"] == SCHEMA, "domain schema")
    validate_frame_key(domain["frame_key"])
    keys(domain["selector"], ("selector_id", "version"), "selector")
    text(domain["selector"]["selector_id"], "selector_id")
    require(type(domain["selector"]["version"]) is int
            and domain["selector"]["version"] >= 1, "selector version")
    text(domain["config_id"], "config_id")
    require(domain["config_id"].startswith("agl-config:"), "config_id namespace")
    text(domain["source_provenance"], "source_provenance")
    require(domain["units"] == UNITS, "domain units must be m")
    _validate_spatial_basis(domain["spatial_basis"])
    points = domain["source_points"]
    indices = domain["source_indices"]
    weights = domain["weights"]
    codes = domain["region_codes"]
    require(type(domain["point_count"]) is int and domain["point_count"] >= 1,
            "domain point_count")
    count = int(domain["point_count"])
    require(isinstance(points, np.ndarray) and points.dtype == np.float64
            and points.ndim == 2 and points.shape[1] == 3,
            "domain source_points must be float64 (N,3)")
    require(len(points) == count, "domain point_count mismatch")
    require(bool(np.all(np.isfinite(points))), "domain points must be finite")
    require(bool(np.all(np.any(points != 0.0, axis=1))),
            "domain contains all-zero rows")
    require(isinstance(indices, np.ndarray) and indices.dtype == np.int64
            and indices.ndim == 1 and len(indices) == count, "domain source_indices")
    require(bool(np.all(indices >= 0))
            and (count < 2 or bool(np.all(np.diff(indices) > 0))),
            "domain source_indices not strictly increasing")
    require(isinstance(weights, np.ndarray) and weights.dtype == np.float64
            and weights.ndim == 1 and len(weights) == count, "domain weights")
    require(bool(np.all(np.isfinite(weights))) and bool(np.all(weights > 0.0)),
            "domain weights must be positive finite")
    require(isinstance(codes, np.ndarray) and codes.dtype == np.int64
            and codes.ndim == 1 and len(codes) == count, "domain region_codes")
    pre = domain["prefilter"]
    keys(pre, PREFILTER_FIELDS, "prefilter")
    require(pre["policy"] == PREFILTER_POLICY and pre["height_or_residual_trim"] is False,
            "prefilter policy")
    require(type(pre["input_row_count"]) is int
            and type(pre["kept_row_count"]) is int
            and type(pre["dropped_zero_count"]) is int, "prefilter counts")
    require(pre["kept_row_count"] == count
            and pre["input_row_count"] - pre["kept_row_count"] == pre["dropped_zero_count"],
            "prefilter counts mismatch")
    require(_sha256(points) == domain["point_sha256"],
            "point content changed (same ID different content)")
    require(_sha256(indices) == domain["rows_sha256"], "row identity changed")
    require(_sha256(weights) == domain["weights_sha256"], "weights changed")
    require(_sha256(codes) == domain["region_codes_sha256"], "region codes changed")
    require(domain["domain_id"] == "agl-domain:" + digest(_domain_binding(domain)),
            "domain ID/content mismatch")
    return None


def point_domain_reference(domain):
    """JSON 安全摘要：只含身份/哈希/计数，供解耦的展示或导出层消费。"""
    validate_point_domain(domain)
    return {"kind": domain["kind"], "schema": domain["schema"],
            "domain_id": domain["domain_id"],
            "frame_key": copy.deepcopy(domain["frame_key"]),
            "selector": copy.deepcopy(domain["selector"]),
            "config_id": domain["config_id"], "units": domain["units"],
            "point_count": domain["point_count"],
            "point_sha256": domain["point_sha256"],
            "rows_sha256": domain["rows_sha256"],
            "weights_sha256": domain["weights_sha256"],
            "region_codes_sha256": domain["region_codes_sha256"],
            "spatial_basis": copy.deepcopy(domain["spatial_basis"]),
            "prefilter": copy.deepcopy(domain["prefilter"]),
            "source_provenance": domain["source_provenance"]}
