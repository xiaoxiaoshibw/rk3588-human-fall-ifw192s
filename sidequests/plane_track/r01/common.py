"""PLANE-01 小飞行目标支线：会话读取与哈希共用小工具（纯 stdlib + NumPy）。

数据契约以 captures/remote/<sid>/meta.json 的 point_stride_bytes=28 为准
（human_capture_session v1：x@0,y@4,z@8,intensity@12,ring@16,u2,timestamp@20,f4）。
"""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
REMOTE = ROOT / "captures/remote"
LEVELED = ROOT / "captures/leveled"


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_session(sid, root=REMOTE):
    """Return (directory, meta) after checking the 28B contract loosely."""
    directory = Path(root) / sid
    meta = json.loads((directory / "meta.json").read_text(encoding="utf8"))
    if meta.get("format") != "human_capture_session" or meta.get("format_version") != 1:
        raise ValueError(sid + ": not a human_capture_session v1")
    stride = int(meta.get("point_stride_bytes", 0))
    if stride != 28:
        raise ValueError(sid + ": point_stride_bytes != 28 (the 16B README example does not apply)")
    if (directory / "points.bin").stat().st_size != int(meta["total_points"]) * stride:
        raise ValueError(sid + ": points.bin size mismatch")
    return directory, meta


def xyz_view(directory, meta):
    """(total_points,3) float64 strided view over points.bin (read-only)."""
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((int(meta["total_points"]), 3), dtype="<f4", buffer=raw, strides=(28, 4))
    return xyz


def intensity_view(directory, meta):
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    return np.ndarray((int(meta["total_points"]),), dtype="<f4", buffer=raw, offset=12, strides=(28,))


def frame_slice(meta, i):
    frame = meta["frames"][i]
    lo = int(frame["offset_points"])
    return lo, lo + int(frame["count_points"])
