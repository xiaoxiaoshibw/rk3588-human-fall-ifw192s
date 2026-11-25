"""LDSF v1 二进制帧协议编解码与 JSON 安全清洗（与 web/studio_lib.js 逐字节对称）。"""

from __future__ import annotations

import json
import math
import struct
from typing import Any

import numpy as np

MAGIC = b"LDSF"
VERSION = 1

HEADER_STRUCT = struct.Struct("<4sBBHIHHIIIIII")
HEADER_SIZE = HEADER_STRUCT.size  # 40 bytes

# header_flags 位定义
HDR_HAS_INTENSITY = 0x01
HDR_HAS_RANGE_MASK = 0x02
HDR_IS_LIVE = 0x04

# point_flags / range_mask 位定义
FLAG_TARGET_CORE = 0x01
FLAG_RECOVERY_ADDED = 0x02
FLAG_OTHER_TRACK = 0x04
FLAG_FOREGROUND = 0x08


def sanitize_json(obj: Any) -> Any:
    """递归把 NaN / Inf / numpy 标量转成严格 RFC-8259 合规 JSON 值（无 NaN）。"""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        val = float(obj)
        return val if math.isfinite(val) else None
    if isinstance(obj, np.ndarray):
        return sanitize_json(obj.tolist())
    if isinstance(obj, dict):
        return {str(k): sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    return str(obj)


def pack_frame(
    xyz: np.ndarray,
    point_flags: np.ndarray,
    range_mm: np.ndarray,
    state: dict[str, Any],
    *,
    intensity: np.ndarray | None = None,
    range_mask: np.ndarray | None = None,
    decimation: int = 1,
    is_live: bool = False,
) -> bytes:
    """打包单帧 LDSF v1 二进制数据包（小端 + 4 字节对齐头）。"""
    dec = int(decimation)
    if dec < 1 or dec > 65535:
        raise ValueError(f"decimation out of range: {dec}")

    xyz_arr = np.ascontiguousarray(xyz, dtype="<f4")
    if xyz_arr.ndim != 2 or xyz_arr.shape[1] != 3:
        raise ValueError(f"xyz must have shape (N, 3), got {xyz_arr.shape}")
    n_points = int(xyz_arr.shape[0])

    flags_arr = np.ascontiguousarray(point_flags, dtype=np.uint8)
    if flags_arr.shape != (n_points,):
        raise ValueError(f"point_flags shape {flags_arr.shape} != ({n_points},)")

    intensity_bytes = b""
    hdr_flags = HDR_IS_LIVE if is_live else 0
    if intensity is not None:
        inten_arr = np.ascontiguousarray(intensity, dtype="<f4")
        if inten_arr.shape != (n_points,):
            raise ValueError(f"intensity shape {inten_arr.shape} != ({n_points},)")
        intensity_bytes = inten_arr.tobytes()
        hdr_flags |= HDR_HAS_INTENSITY

    rmm_arr = np.ascontiguousarray(range_mm, dtype="<u2")
    if rmm_arr.size == 0:
        rh, rw = 0, 0
        rmm_bytes = b""
    else:
        if rmm_arr.ndim != 2:
            raise ValueError(f"range_mm must be 2-D, got {rmm_arr.shape}")
        rh, rw = int(rmm_arr.shape[0]), int(rmm_arr.shape[1])
        if rh > 65535 or rw > 65535:
            raise ValueError("range image dimensions exceed uint16")
        rmm_bytes = rmm_arr.tobytes()

    rmask_bytes = b""
    if range_mask is not None:
        rmask_arr = np.ascontiguousarray(range_mask, dtype=np.uint8)
        if rmask_arr.shape != (rh, rw):
            raise ValueError(f"range_mask shape {rmask_arr.shape} != ({rh}, {rw})")
        if rh * rw > 0:
            rmask_bytes = rmask_arr.tobytes()
            hdr_flags |= HDR_HAS_RANGE_MASK

    clean_state = sanitize_json(state)
    json_bytes = json.dumps(
        clean_state,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")

    xyz_bytes = xyz_arr.tobytes()
    header = HEADER_STRUCT.pack(
        MAGIC,
        VERSION,
        hdr_flags,
        dec,
        n_points,
        rh,
        rw,
        len(xyz_bytes),
        len(intensity_bytes),
        len(rmm_bytes),
        len(flags_arr),
        len(rmask_bytes),
        len(json_bytes),
    )
    return b"".join(
        (header, xyz_bytes, intensity_bytes, rmm_bytes, flags_arr.tobytes(), rmask_bytes, json_bytes)
    )


def unpack_frame(packet: bytes | bytearray | memoryview) -> dict[str, Any]:
    """解包单帧 LDSF v1 二进制数据包，严格校验魔数、版本、段长与边界。"""
    mv = memoryview(packet)
    if mv.nbytes < HEADER_SIZE:
        raise ValueError(f"packet too short: {mv.nbytes} < {HEADER_SIZE}")

    (
        magic,
        version,
        hdr_flags,
        decimation,
        n_points,
        rh,
        rw,
        xyz_len,
        intensity_len,
        range_mm_len,
        point_flags_len,
        range_mask_len,
        json_len,
    ) = HEADER_STRUCT.unpack_from(mv, 0)

    if magic != MAGIC:
        raise ValueError(f"invalid magic: {magic!r}")
    if version != VERSION:
        raise ValueError(f"unsupported LDSF version: {version}")
    if decimation < 1:
        raise ValueError(f"invalid decimation: {decimation}")
    if xyz_len != n_points * 12:
        raise ValueError(f"xyz_len mismatch: {xyz_len} != {n_points * 12}")

    has_intensity = bool(hdr_flags & HDR_HAS_INTENSITY)
    expected_inten_len = n_points * 4 if has_intensity else 0
    if intensity_len != expected_inten_len:
        raise ValueError(f"intensity_len mismatch: {intensity_len} != {expected_inten_len}")

    if range_mm_len != rh * rw * 2:
        raise ValueError(f"range_mm_len mismatch: {range_mm_len} != {rh * rw * 2}")
    if point_flags_len != n_points:
        raise ValueError(f"point_flags_len mismatch: {point_flags_len} != {n_points}")

    has_range_mask = bool(hdr_flags & HDR_HAS_RANGE_MASK)
    expected_mask_len = rh * rw if has_range_mask else 0
    if range_mask_len != expected_mask_len:
        raise ValueError(f"range_mask_len mismatch: {range_mask_len} != {expected_mask_len}")
    if json_len == 0:
        raise ValueError("empty json payload")

    expected_total = (
        HEADER_SIZE
        + xyz_len
        + intensity_len
        + range_mm_len
        + point_flags_len
        + range_mask_len
        + json_len
    )
    if mv.nbytes != expected_total:
        raise ValueError(f"packet length mismatch: {mv.nbytes} != {expected_total}")

    off = HEADER_SIZE
    xyz = np.frombuffer(mv[off : off + xyz_len], dtype="<f4").reshape(n_points, 3).copy()
    off += xyz_len

    intensity = None
    if has_intensity:
        intensity = np.frombuffer(mv[off : off + intensity_len], dtype="<f4").copy()
        off += intensity_len

    if rh * rw > 0:
        range_mm = np.frombuffer(mv[off : off + range_mm_len], dtype="<u2").reshape(rh, rw).copy()
        off += range_mm_len
    else:
        range_mm = np.empty((0, 0), dtype="<u2")

    point_flags = np.frombuffer(mv[off : off + point_flags_len], dtype=np.uint8).copy()
    off += point_flags_len

    range_mask = None
    if has_range_mask:
        range_mask = np.frombuffer(mv[off : off + range_mask_len], dtype=np.uint8).reshape(rh, rw).copy()
        off += range_mask_len

    state = json.loads(bytes(mv[off : off + json_len]).decode("utf-8"))
    if not isinstance(state, dict):
        raise ValueError("state_json must decode to JSON object")

    return {
        "version": version,
        "decimation": decimation,
        "is_live": bool(hdr_flags & HDR_IS_LIVE),
        "xyz": xyz,
        "intensity": intensity,
        "range_mm": range_mm,
        "point_flags": point_flags,
        "range_mask": range_mask,
        "state": state,
    }
