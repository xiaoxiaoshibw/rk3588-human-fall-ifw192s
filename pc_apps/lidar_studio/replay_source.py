"""回放数据源与会话缓存：复用 core.RangeRuntime(..., human_physical_v1=True) 并输出统一契约。

红线与约束：
- 只读访问 data/sessions/<sid>/，绝不修改或写入 data/ 或 captures/。
- 缓存只落在 pc_apps/lidar_studio/.cache/（git-ignored）。
- 严格遵循与 human_prior_probe.py::build_inputs & run_ab_replay_r2.py 相同的输入口径。
"""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from typing import Any, Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
HF_DIR = REPO_ROOT / "src" / "human_fall_detection"
HF_SCRIPTS = HF_DIR / "scripts"
for _p in (str(HF_DIR), str(HF_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.capture_input import ROW_DTYPE, read_source_meta, sha256_file  # noqa: E402
from core.range_contract import binding_tuple, source_binding  # noqa: E402
from core.range_demo_alert import DemoAlert  # noqa: E402
from core.range_features import bound_ground  # noqa: E402
from core.range_ground_alert import GroundAlertObserver  # noqa: E402
from core.range_image import ScanGrid  # noqa: E402
from core.range_offline import QuantileBackground, SEED as OFFLINE_SEED, fit_declared_plane  # noqa: E402
from core.range_runtime import RangeRuntime  # noqa: E402
from core.range_skeleton import estimate as estimate_skeleton, project_regions  # noqa: E402

from camera_hub import ReplayCameraIndex
from protocol import (
    FLAG_FOREGROUND,
    FLAG_OTHER_TRACK,
    FLAG_RECOVERY_ADDED,
    FLAG_TARGET_CORE,
    pack_frame,
    sanitize_json,
)

CALIBRATION_DIR = REPO_ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s"
AZIMUTH_CSV = CALIBRATION_DIR / "ifw192s_azimuth_192x256.csv"
ELEVATION_CSV = CALIBRATION_DIR / "ifw192s_elevation_192x256.csv"

CACHE_FORMAT_VERSION = "lidar_studio_cache_v2"
SID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

KNOWN_TITLES = {
    "cap_20261028_houdao": "向后倒地（带相机）",
    "cap_20261028_qiandao": "向前倒地（带相机）",
    "cap_20261028_huanmandiedao": "缓慢倒地（带相机）",
    "cap_20261028_jixiedaiwanyao": "系鞋带与弯腰（带相机）",
    "cap_20261023_221125": "站立/常规对照（带相机）",
    "cap_20261015_224823": "空场景/对照（带相机）",
    "cap_20261017_113516": "长段多轨迹对照 (780帧)",
    "cap_20261018_110029": "标准回放对照 (386帧)",
}

_GRID_LOCK = threading.Lock()
_CACHED_GRID: ScanGrid | None = None
_CACHED_GRID_SHAS: tuple[str, str] | None = None


def get_shared_grid() -> tuple[ScanGrid, str, str]:
    global _CACHED_GRID, _CACHED_GRID_SHAS
    with _GRID_LOCK:
        if _CACHED_GRID is None:
            _CACHED_GRID = ScanGrid.from_csv(AZIMUTH_CSV, ELEVATION_CSV)
            _CACHED_GRID_SHAS = (sha256_file(AZIMUTH_CSV), sha256_file(ELEVATION_CSV))
        return _CACHED_GRID, _CACHED_GRID_SHAS[0], _CACHED_GRID_SHAS[1]


def assert_safe_cache_dir(cache_dir: Path, repo_root: Path = REPO_ROOT) -> Path:
    """严格保证缓存目录绝不落在 data/ 或 captures/（或其父目录）中。"""
    resolved = cache_dir.resolve()
    for protected_name in ("data", "captures"):
        protected = (repo_root / protected_name).resolve()
        if resolved == protected or protected in resolved.parents or resolved in protected.parents:
            raise ValueError(f"cache directory must never overlap protected directory: {protected}")
    return resolved


def validate_sid(sid: str, sessions_root: Path) -> Path:
    """验证会话 ID 格式并防路径穿越，返回校验后的绝对路径。"""
    if not isinstance(sid, str) or not sid or sid.startswith(".") or not SID_PATTERN.match(sid):
        raise ValueError(f"invalid session id: {sid!r}")
    root_resolved = sessions_root.resolve()
    candidate = (root_resolved / sid).resolve()
    if candidate.parent != root_resolved or not candidate.is_dir():
        raise ValueError(f"session directory not found: {sid!r}")
    return candidate


def validate_session_meta(session_dir: Path) -> tuple[dict[str, Any], str]:
    """按 replay_range_frontend 口径校验 meta.json 与 points.bin 布局（抛 ValueError 而非 SystemExit）。"""
    meta_path = session_dir / "meta.json"
    points_path = session_dir / "points.bin"
    if not meta_path.is_file():
        raise ValueError(f"missing meta.json in {session_dir.name}")
    if not points_path.is_file():
        raise ValueError(f"missing points.bin in {session_dir.name}")

    raw = meta_path.read_bytes()
    declared = json.loads(raw.decode("utf-8-sig"))
    frame_id = (declared.get("sensor") or {}).get("frame_id")
    meta = read_source_meta(raw, frame_id, "m")
    frames = meta.get("frames")
    if not isinstance(frames, list) or not frames:
        raise ValueError("empty session frame list")

    offset = 0
    previous_ns: int | None = None
    for idx, frame in enumerate(frames):
        for key in ("offset_points", "count_points", "stamp_sec", "stamp_nanosec", "dropped_points"):
            val = frame.get(key)
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise ValueError(f"frame {idx}: invalid {key}")
        if frame["offset_points"] != offset or frame["stamp_nanosec"] >= 1_000_000_000:
            raise ValueError(f"frame {idx}: invalid offset_points or stamp_nanosec")
        offset += frame["count_points"]
        stamp_ns = frame["stamp_sec"] * 1_000_000_000 + frame["stamp_nanosec"]
        if previous_ns is not None and stamp_ns <= previous_ns:
            raise ValueError(f"frame {idx}: non-increasing source header time")
        previous_ns = stamp_ns

    actual_bytes = points_path.stat().st_size
    expected_bytes = offset * ROW_DTYPE.itemsize
    if offset != meta.get("total_points") or actual_bytes != expected_bytes:
        raise ValueError(
            f"points.bin size mismatch: actual={actual_bytes}, expected={expected_bytes}"
        )
    return meta, hashlib.sha256(raw).hexdigest()


def display_basis(normal: list[float] | np.ndarray) -> np.ndarray:
    """显示坐标正交基：x=雷达前向地面投影，y=左，z=地面法向。"""
    up = np.asarray(normal, dtype=np.float64)
    up = up / np.linalg.norm(up)
    forward = np.array([1.0, 0.0, 0.0]) - up * float(up[0])
    if np.linalg.norm(forward) < 1e-6:
        forward = np.array([0.0, 1.0, 0.0]) - up * float(up[1])
    forward = forward / np.linalg.norm(forward)
    left = np.cross(up, forward)
    return np.stack([forward, left, up])


def compute_bbox(xyz: np.ndarray, basis: np.ndarray | None = None, offset_m: float = 0.0) -> dict[str, Any] | None:
    if len(xyz) == 0:
        return None
    pts = np.asarray(xyz, dtype=np.float64)
    raw_min = np.min(pts, axis=0)
    raw_max = np.max(pts, axis=0)
    raw_center = np.median(pts, axis=0)
    out: dict[str, Any] = {
        "raw": {
            "min": [round(float(v), 4) for v in raw_min],
            "max": [round(float(v), 4) for v in raw_max],
            "center": [round(float(v), 4) for v in raw_center],
        },
        "leveled": None,
    }
    if basis is not None:
        lev = pts @ basis.T
        lev[:, 2] += float(offset_m)
        l_min = np.min(lev, axis=0)
        l_max = np.max(lev, axis=0)
        l_center = np.median(lev, axis=0)
        out["leveled"] = {
            "min": [round(float(v), 4) for v in l_min],
            "max": [round(float(v), 4) for v in l_max],
            "center": [round(float(v), 4) for v in l_center],
        }
    return out


def compact_skeleton(pose: dict[str, Any]) -> dict[str, Any]:
    """保留骨架节点 xyz / imageXY / supportCount 与边，剔除大数组 sourceRows。"""
    nodes = {}
    for name, node in (pose.get("nodes") or {}).items():
        nodes[name] = {
            "xyz": [round(float(v), 4) for v in node["xyz"]],
            "imageXY": [round(float(v), 2) for v in node["imageXY"]] if "imageXY" in node else None,
            "supportCount": int(node.get("supportCount", 0)),
        }
    return {
        "version": pose.get("version"),
        "semantic": pose.get("semantic", "GEOMETRIC_REGIONS"),
        "anatomicalJoints": pose.get("anatomicalJoints", "UNKNOWN"),
        "reason": pose.get("reason"),
        "nodes": nodes,
        "edges": list(pose.get("edges") or []),
    }


def compact_physical_v1(phys: dict[str, Any]) -> dict[str, Any]:
    """保留全部可审计字段与数值，剔除重复大 row 列表以保持状态 JSON 紧凑。"""
    def _clean_belief(b: dict[str, Any] | None) -> dict[str, Any] | None:
        if b is None:
            return None
        return {k: v for k, v in b.items() if k != "source_rows"}

    tracks_out = {}
    for tid, detail in (phys.get("tracks") or {}).items():
        tracks_out[tid] = {
            "belief": _clean_belief(detail.get("belief")),
            "prior": detail.get("prior"),
            "kinematics": detail.get("kinematics"),
        }

    rec = phys.get("recovery")
    rec_out = None
    if rec is not None:
        rec_out = {
            k: v
            for k, v in rec.items()
            if k not in ("core_rows", "added_rows", "recovered_rows")
        }

    return {
        "variant": phys.get("variant"),
        "revision": phys.get("revision"),
        "status": phys.get("status"),
        "error_codes": list(phys.get("error_codes") or []),
        "errors": list(phys.get("errors") or []),
        "frame": phys.get("frame"),
        "time_s": phys.get("time_s"),
        "target_track_id": phys.get("target_track_id"),
        "target_belief": _clean_belief(phys.get("target_belief")),
        "confirmed_track_ids": list(phys.get("confirmed_track_ids") or []),
        "candidate_track_ids": list(phys.get("candidate_track_ids") or []),
        "kinematics_noise_floor": phys.get("kinematics_noise_floor"),
        "tracks": tracks_out,
        "recovery": rec_out,
        "timings": phys.get("timings"),
        "semantic_truth": phys.get("semantic_truth", "UNKNOWN"),
    }


def _rows_array(values: list[int] | np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.int32)
    if arr.ndim != 1 or arr.size == 0:
        return np.empty(0, dtype=np.int32)
    return np.unique(arr)


def build_point_flags_and_masks(
    n_raw: int,
    frame_valid: np.ndarray,
    frame_source_rows: np.ndarray,
    target_rows: np.ndarray,
    recovery_rows: np.ndarray,
    other_rows: np.ndarray,
    fg_rows: np.ndarray,
    valid_point_mask: np.ndarray,
    decimation: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """构造点集保留索引、point_flags、以及旋转 180° 后的 range_mask。"""
    row_flags = np.zeros(n_raw, dtype=np.uint8)
    if fg_rows.size:
        row_flags[fg_rows] |= FLAG_FOREGROUND
    if other_rows.size:
        row_flags[other_rows] |= FLAG_OTHER_TRACK
    if recovery_rows.size:
        row_flags[recovery_rows] |= FLAG_RECOVERY_ADDED
    if target_rows.size:
        row_flags[target_rows] |= FLAG_TARGET_CORE

    if n_raw > 0:
        safe_sr = np.maximum(frame_source_rows, 0)
        range_mask = np.where(frame_valid, row_flags[safe_sr], 0).astype(np.uint8)[::-1, ::-1]
    else:
        range_mask = np.zeros(frame_valid.shape, dtype=np.uint8)

    special_mask = valid_point_mask & (row_flags != 0)
    bg_indices = np.flatnonzero(valid_point_mask & (row_flags == 0))
    if decimation > 1 and bg_indices.size:
        bg_indices = bg_indices[::decimation]
    special_indices = np.flatnonzero(special_mask)
    keep_indices = np.sort(np.concatenate([special_indices, bg_indices]))
    return keep_indices, row_flags[keep_indices], range_mask


class ReplaySessionData:
    """单个会话的已缓存状态与逐帧二进制打包句柄。"""

    def __init__(
        self,
        sid: str,
        session_dir: Path,
        meta: dict[str, Any],
        meta_sha: str,
        points_sha: str,
        summary: dict[str, Any],
        states: list[dict[str, Any]],
        rows_npz: Path,
        grid: ScanGrid,
        identity: dict[str, Any],
    ):
        self.sid = sid
        self.session_dir = session_dir
        self.meta = meta
        self.meta_sha = meta_sha
        self.points_sha = points_sha
        self.summary = summary
        self.states = states
        self.grid = grid
        self.identity = identity
        self.binding = binding_tuple(identity)
        self.frame_count = len(meta["frames"])
        self.camera = ReplayCameraIndex(session_dir)

        with np.load(rows_npz, allow_pickle=False) as zf:
            self._rows_data = {k: zf[k].copy() for k in zf.files}

        self._points_fp = (session_dir / "points.bin").open("rb")
        self._lock = threading.Lock()
        self._pack_cache: OrderedDict[tuple[int, int], bytes] = OrderedDict()
        self._max_pack_cache = 320

    def close(self) -> None:
        with self._lock:
            if self._points_fp is not None:
                try:
                    self._points_fp.close()
                finally:
                    self._points_fp = None
            self.camera.close()
            self._pack_cache.clear()

    def _slice_rows(self, prefix: str, frame_index: int) -> np.ndarray:
        offs = self._rows_data[f"{prefix}_offsets"]
        flat = self._rows_data[f"{prefix}_flat"]
        a = int(offs[frame_index])
        b = int(offs[frame_index + 1])
        return flat[a:b]

    def get_packed_frame(self, frame_index: int, decimation: int = 2) -> bytes:
        idx = int(frame_index)
        dec = max(1, min(16, int(decimation)))
        if not (0 <= idx < self.frame_count):
            raise IndexError(f"frame index {idx} out of range [0, {self.frame_count})")

        cache_key = (idx, dec)
        with self._lock:
            cached = self._pack_cache.get(cache_key)
            if cached is not None:
                self._pack_cache.move_to_end(cache_key)
                return cached

            if self._points_fp is None:
                raise RuntimeError("session points.bin handle is closed")

            info = self.meta["frames"][idx]
            size = info["count_points"] * ROW_DTYPE.itemsize
            self._points_fp.seek(info["offset_points"] * ROW_DTYPE.itemsize)
            raw = self._points_fp.read(size)
            if len(raw) != size:
                raise ValueError(f"truncated points.bin at frame {idx}")

            packed = np.frombuffer(raw, dtype=ROW_DTYPE)
            frame = self.grid.decode(packed, self.binding)

            n_raw = len(packed)
            target_rows = self._slice_rows("target", idx)
            rec_rows = self._slice_rows("recovery", idx)
            other_rows = self._slice_rows("other", idx)
            fg_rows = self._slice_rows("fg", idx)

            xyz_all = frame.xyz
            if n_raw > 0:
                sq = np.sum(xyz_all.astype(np.float64) ** 2, axis=1)
                valid_pt = np.isfinite(xyz_all).all(axis=1) & (sq > 0.01)
            else:
                valid_pt = np.zeros(0, dtype=bool)

            keep_idx, point_flags, range_mask = build_point_flags_and_masks(
                n_raw,
                frame.valid,
                frame.source_rows,
                target_rows,
                rec_rows,
                other_rows,
                fg_rows,
                valid_pt,
                dec,
            )

            xyz_out = xyz_all[keep_idx].astype("<f4")
            inten_out = packed["intensity"][keep_idx].astype("<f4")
            inten_out = np.where(np.isfinite(inten_out), inten_out, 0.0).astype("<f4")

            with np.errstate(invalid="ignore"):
                r_mm = np.where(
                    frame.valid & np.isfinite(frame.range_m),
                    np.clip(np.rint(frame.range_m * 1000.0), 1, 65535),
                    0,
                ).astype("<u2")[::-1, ::-1]

            packet = pack_frame(
                xyz_out,
                point_flags,
                r_mm,
                self.states[idx],
                intensity=inten_out,
                range_mask=range_mask,
                decimation=dec,
                is_live=False,
            )

            self._pack_cache[cache_key] = packet
            while len(self._pack_cache) > self._max_pack_cache:
                self._pack_cache.popitem(last=False)
            return packet


class ReplayManager:
    """管理全部回放会话列表、离线算法推理与安全磁盘缓存。"""

    def __init__(
        self,
        sessions_root: Path | None = None,
        cache_dir: Path | None = None,
    ):
        self.sessions_root = (sessions_root or (REPO_ROOT / "data" / "sessions")).resolve()
        raw_cache = cache_dir or (Path(__file__).resolve().parent / ".cache")
        self.cache_dir = assert_safe_cache_dir(raw_cache)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._open_sessions: dict[str, ReplaySessionData] = {}
        self._compute_locks: dict[str, threading.Lock] = {}
        self._mgr_lock = threading.Lock()

    def close_all(self) -> None:
        with self._mgr_lock:
            for s in self._open_sessions.values():
                s.close()
            self._open_sessions.clear()

    def _compute_cache_key(self, meta_sha: str, points_sha: str, runtime_config_sha: str) -> str:
        raw = f"{CACHE_FORMAT_VERSION}:{meta_sha}:{points_sha}:{runtime_config_sha}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def _find_cached_dir(self, sid: str, meta_sha: str, points_sha: str) -> Path | None:
        prefix = f"{sid}_"
        for candidate in self.cache_dir.iterdir():
            if not candidate.is_dir() or not candidate.name.startswith(prefix):
                continue
            summary_p = candidate / "summary.json"
            states_p = candidate / "states.jsonl"
            rows_p = candidate / "rows.npz"
            if not (summary_p.is_file() and states_p.is_file() and rows_p.is_file()):
                continue
            try:
                summary = json.loads(summary_p.read_text(encoding="utf-8"))
                if (
                    summary.get("cache_format") == CACHE_FORMAT_VERSION
                    and summary.get("meta_sha256") == meta_sha
                    and summary.get("points_sha256") == points_sha
                ):
                    return candidate
            except Exception:
                continue
        return None

    def list_sessions(self) -> list[dict[str, Any]]:
        if not self.sessions_root.is_dir():
            return []
        entries: list[dict[str, Any]] = []
        for d in sorted(self.sessions_root.iterdir(), key=lambda p: p.name):
            if not d.is_dir() or d.name.startswith("."):
                continue
            meta_p = d / "meta.json"
            pts_p = d / "points.bin"
            if not meta_p.is_file() or not pts_p.is_file():
                continue
            try:
                meta = json.loads(meta_p.read_bytes().decode("utf-8-sig"))
                frames = meta.get("frames") or []
                nf = len(frames)
                if nf == 0:
                    continue
                t0 = frames[0]["stamp_sec"] + frames[0]["stamp_nanosec"] / 1e9
                t1 = frames[-1]["stamp_sec"] + frames[-1]["stamp_nanosec"] / 1e9
                cam_idx_p = d / "camera_frames.jsonl"
                cam_blob_p = d / "camera.mjpeg"
                has_cam = cam_idx_p.is_file() and cam_blob_p.is_file()
                cam_frames = 0
                if has_cam:
                    cam_frames = sum(1 for ln in cam_idx_p.read_text(encoding="utf-8").splitlines() if ln.strip())
                meta_sha = hashlib.sha256(meta_p.read_bytes()).hexdigest()
                cached = False
                for c in self.cache_dir.iterdir():
                    if not (c.is_dir() and c.name.startswith(f"{d.name}_") and (c / "summary.json").is_file()):
                        continue
                    try:
                        csum = json.loads((c / "summary.json").read_text(encoding="utf-8"))
                        if (
                            csum.get("cache_format") == CACHE_FORMAT_VERSION
                            and csum.get("meta_sha256") == meta_sha
                        ):
                            cached = True
                            break
                    except Exception:
                        continue
                entries.append(
                    {
                        "sid": d.name,
                        "title": KNOWN_TITLES.get(d.name, d.name),
                        "frames": nf,
                        "duration_sec": round(max(0.0, t1 - t0), 2),
                        "has_camera": has_cam,
                        "camera_frames": cam_frames,
                        "cached": cached,
                        "in_memory": d.name in self._open_sessions,
                    }
                )
            except Exception:
                continue
        return entries

    def _get_session_lock(self, sid: str) -> threading.Lock:
        with self._mgr_lock:
            if sid not in self._compute_locks:
                self._compute_locks[sid] = threading.Lock()
            return self._compute_locks[sid]

    def open_session(
        self,
        sid: str,
        progress_cb: Callable[[str, int, int, str], None] | None = None,
    ) -> ReplaySessionData:
        session_dir = validate_sid(sid, self.sessions_root)
        with self._mgr_lock:
            existing = self._open_sessions.get(sid)
            if existing is not None:
                return existing

        lock = self._get_session_lock(sid)
        with lock:
            with self._mgr_lock:
                existing = self._open_sessions.get(sid)
                if existing is not None:
                    return existing

            meta, meta_sha = validate_session_meta(session_dir)
            points_sha = sha256_file(session_dir / "points.bin")
            grid, az_sha, el_sha = get_shared_grid()
            identity = source_binding(session_dir, meta, meta_sha, points_sha, grid)
            identity["azimuth_sha256"] = az_sha
            identity["elevation_sha256"] = el_sha

            cached_dir = self._find_cached_dir(sid, meta_sha, points_sha)
            if cached_dir is not None:
                if progress_cb:
                    progress_cb("cache_hit", 1, 1, "命中本地推理缓存，正在载入...")
                summary = json.loads((cached_dir / "summary.json").read_text(encoding="utf-8"))
                states = [
                    json.loads(line)
                    for line in (cached_dir / "states.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                session_obj = ReplaySessionData(
                    sid,
                    session_dir,
                    meta,
                    meta_sha,
                    points_sha,
                    summary,
                    states,
                    cached_dir / "rows.npz",
                    grid,
                    identity,
                )
            else:
                session_obj = self._build_and_cache(
                    sid, session_dir, meta, meta_sha, points_sha, grid, identity, progress_cb
                )

            with self._mgr_lock:
                self._open_sessions[sid] = session_obj
            return session_obj

    def _build_and_cache(
        self,
        sid: str,
        session_dir: Path,
        meta: dict[str, Any],
        meta_sha: str,
        points_sha: str,
        grid: ScanGrid,
        identity: dict[str, Any],
        progress_cb: Callable[[str, int, int, str], None] | None,
    ) -> ReplaySessionData:
        t_start = time.perf_counter()
        binding = binding_tuple(identity)
        frames_meta = meta["frames"]
        count = len(frames_meta)
        stack = np.empty((count, grid.shape[0], grid.shape[1]), dtype=np.float32)
        observed = np.zeros(grid.shape, dtype=np.int32)

        sample_indices = {0, count // 4, count // 2, (3 * count) // 4, count - 1}
        ground_sample: list[np.ndarray] = []

        # Pass 1：全帧解码收集整段分位背景与 5 帧地面采样
        with (session_dir / "points.bin").open("rb") as stream:
            for idx, info in enumerate(frames_meta):
                size = info["count_points"] * ROW_DTYPE.itemsize
                raw = stream.read(size)
                if len(raw) != size:
                    raise ValueError(f"points.bin truncated at frame {idx}")
                frame = grid.decode(raw, binding)
                stack[idx] = frame.range_m.astype(np.float32)
                observed += frame.valid
                if idx in sample_indices:
                    rows = frame.source_rows[frame.valid]
                    with np.errstate(invalid="ignore"):
                        kept = np.isfinite(frame.range_m[frame.valid]) & (frame.range_m[frame.valid] > 0.3)
                    pts = frame.xyz[rows][kept].astype(np.float64)
                    if len(pts):
                        ground_sample.append(pts)
                if progress_cb and (idx % 10 == 0 or idx == count - 1):
                    progress_cb("pass1_decode", idx + 1, count, f"Pass 1/2 解码点云与背景采样 ({idx + 1}/{count})")

        if progress_cb:
            progress_cb("fit_ground", 0, 1, "正在构造整段分位背景并拟合离线地面...")

        ground = None
        ground_sha = None
        ground_reason = "not_loaded"
        basis = None
        offset_m = 0.0

        if len(ground_sample) >= 1:
            concat_pts = np.concatenate(ground_sample)
            if len(concat_pts) >= 100:
                try:
                    ground = fit_declared_plane(
                        concat_pts,
                        binding=identity,
                        frame=identity["coordinate"][4:],
                        seed=OFFLINE_SEED,
                    )
                    ground["source"] = {
                        "meta_sha256": meta_sha,
                        "points_sha256": points_sha,
                        "frame": ground["frame"],
                        "coordinate": identity["coordinate"],
                    }
                    ground_sha = hashlib.sha256(
                        json.dumps(ground, sort_keys=True, allow_nan=False).encode("utf-8")
                    ).hexdigest()
                    ground_reason = "bound_plane_geometry_only"
                    basis = display_basis(ground["normal"])
                    offset_m = float(ground["offset_m"])
                except ValueError as exc:
                    ground = None
                    ground_reason = f"ground_fit_failed: {exc}"
            else:
                ground_reason = "insufficient_ground_points"
        else:
            ground_reason = "insufficient_ground_samples"

        background = QuantileBackground.from_stack(
            stack, observed, binding=binding, grid_sha256=grid.sha256
        )
        del stack, ground_sample

        runtime = RangeRuntime(
            grid,
            identity,
            empty_prefix_frames=None,
            ground=ground,
            ground_sha=ground_sha,
            background=background,
            human_physical_v1=True,
        )
        demo_alert = DemoAlert(runtime.config["demo_alert"])
        ground_alert = GroundAlertObserver(runtime.config["ground_alert"])

        display_plane = None
        if ground is not None:
            display_plane = {
                "sessionId": sid,
                "normal": [float(v) for v in ground["normal"]],
                "offsetM": float(ground["offset_m"]),
                "groundSha256": ground_sha,
                "frameId": identity["coordinate"][4:],
                "scope": "bound_display_only",
            }

        base_stamp = frames_meta[0]["stamp_sec"] + frames_meta[0]["stamp_nanosec"] / 1e9
        states: list[dict[str, Any]] = []
        timeline: list[dict[str, Any]] = []
        stamp_secs: list[float] = []
        rel_times: list[float] = []

        target_list: list[np.ndarray] = []
        recovery_list: list[np.ndarray] = []
        other_list: list[np.ndarray] = []
        fg_list: list[np.ndarray] = []

        cam_index = ReplayCameraIndex(session_dir)
        try:
            with (session_dir / "points.bin").open("rb") as stream:
                for idx, info in enumerate(frames_meta):
                    size = info["count_points"] * ROW_DTYPE.itemsize
                    raw = stream.read(size)
                    if len(raw) != size:
                        raise ValueError(f"points.bin truncated at frame {idx}")
                    stamp = info["stamp_sec"] + info["stamp_nanosec"] / 1e9
                    rel_t = round(stamp - base_stamp, 4)
                    stamp_secs.append(stamp)
                    rel_times.append(rel_t)

                    result, frame, _ = runtime.update(raw, stamp, idx)
                    record = result["tracking"]
                    rule = result["rule"]
                    phys = result.get("human_physical_v1") or {}
                    features = rule["features"]
                    hb = features.get("height_m") or {}
                    rows = record["target_source_rows"]
                    height = features.get("height_median_m")
                    measured = bool(rows) and features.get("observable") and features.get("ground_relative")

                    demo_level = demo_alert.update(
                        {
                            "i": idx,
                            "t": stamp,
                            "tid": record["target_track_id"],
                            "n": len(rows) if measured else 0,
                            "hm": height if measured else None,
                            "ht": hb.get("max") if measured else None,
                            "sp": features.get("horizontal_extent_m") if measured else None,
                            "generation": record["generation"],
                            "binding": frame.binding,
                            "reset": features.get("reset_now"),
                        }
                    )
                    demo = {
                        "variant": "horizontal_low_posture_v1",
                        "level": demo_level,
                        "active": demo_level > 0,
                        "state": (
                            "unavailable"
                            if not measured
                            else "sustained"
                            if demo_level == 2
                            else "suspected"
                            if demo_level == 1
                            else "pending"
                            if demo_alert.eligible
                            else "not_matched"
                        ),
                        "durationSec": demo_alert.duration,
                        "confirmedEnabled": False,
                        "semantic": "UNKNOWN",
                    }
                    alert = ground_alert.update(
                        {
                            "frameIndex": idx,
                            "stampSec": stamp,
                            "trackId": record["target_track_id"],
                            "generation": record["generation"],
                            "measured": bool(rows),
                            "heightMedianM": height,
                            "observationGap": features.get("observation_gap"),
                        }
                    )[0]

                    try:
                        pose = project_regions(
                            estimate_skeleton(frame.xyz[rows] if rows else [], rows if rows else []),
                            frame,
                        )
                    except (ValueError, TypeError, FloatingPointError):
                        pose = project_regions(estimate_skeleton([], []), frame)

                    bbox = compute_bbox(frame.xyz[rows], basis=basis, offset_m=offset_m) if rows else None

                    # 收集行集用于压缩缓存与点云/距离图掩码
                    t_arr = _rows_array(rows)
                    rec_added = (phys.get("recovery") or {}).get("added_rows") or []
                    r_arr = _rows_array(rec_added)
                    other_raw: list[int] = []
                    for tr in record.get("tracks") or []:
                        if tr.get("track_id") != record["target_track_id"] and tr.get("observed") and tr.get("source_rows"):
                            other_raw.extend(tr["source_rows"])
                    o_arr = _rows_array(other_raw)

                    bg_res = background.foreground(frame)
                    fg_rows_raw = frame.source_rows[bg_res["mask"] & frame.valid]
                    fg_arr = _rows_array(fg_rows_raw[fg_rows_raw >= 0])

                    target_list.append(t_arr)
                    recovery_list.append(r_arr)
                    other_list.append(o_arr)
                    fg_list.append(fg_arr)

                    cam_meta = cam_index.match_meta(info.get("bag_time_sec"))
                    phys_compact = compact_physical_v1(phys) if phys else None
                    tb = phys_compact["target_belief"] if phys_compact else None

                    fall_state_val = rule["state"]["state"]
                    belief_state_val = tb["belief_state"] if tb else "NONE"

                    ground_block = {
                        "available": ground is not None,
                        "reason": ground_reason,
                        "sha256": ground_sha,
                        "physicalGroundTruth": "UNKNOWN",
                    }
                    if display_plane is not None:
                        ground_block["displayPlane"] = display_plane

                    reason = (
                        result["status"]
                        if result["status"] != "ready"
                        else (record.get("target_reason") or "current_target")
                    )

                    state_obj = {
                        "schema_version": 1,
                        "kind": "target_state",
                        "mode": "replay",
                        "session_id": sid,
                        "frame_index": idx,
                        "frame_count": count,
                        "stamp_sec": stamp,
                        "relative_time_sec": rel_t,
                        "time_epoch": record["generation"],
                        "selection_version": 0,
                        "source": {
                            "seq": info.get("seq", idx),
                            "stamp_secs": info["stamp_sec"],
                            "stamp_nsecs": info["stamp_nanosec"],
                            "frame_id": identity["coordinate"][4:],
                        },
                        "target_mode": "local_range_automatic",
                        "track_id": record["target_track_id"],
                        "track_status": "locked" if rows else "unselected",
                        "observability": "valid",
                        "bbox_observed": bool(rows),
                        "position_predicted": False,
                        "fall_status": fall_state_val,
                        "acquisition": {"reason": reason},
                        "semantic": "unknown",
                        "confirmed_enabled": False,
                        "local_range": {
                            "version": 1,
                            "heightMedianM": height,
                            "groundAlert": alert,
                            "measurement": {
                                "topHeightM": hb.get("max"),
                                "horizontalExtentM": features.get("horizontal_extent_m"),
                                "descentRateMps": features.get("descent_rate_m_s"),
                                "axisVerticality": features.get("axis_verticality"),
                            },
                            "sourceBinding": dict(identity),
                            "background": {
                                "status": result["status"],
                                "configSha256": runtime.config_sha,
                                "declaration": background.declaration,
                            },
                            "ground": ground_block,
                            "fallEvidence": rule["state"],
                            "demoFallCandidate": demo,
                            "posture": rule.get("posture"),
                            "skeleton": compact_skeleton(pose),
                            "bbox": bbox,
                            "depth": {
                                "metadata": {
                                    "format": "lidar_range_image",
                                    "version": 2,
                                    "width": grid.shape[1],
                                    "height": grid.shape[0],
                                    "nativeTransform": "rotate180",
                                    "orientation": "native_grid_rotated_180_for_view",
                                    "gridSha256": grid.sha256,
                                    "quantity": "radial_range",
                                    "units": "m",
                                    "validPixels": int(frame.valid.sum()),
                                    "targetPixels": len(rows),
                                }
                            },
                        },
                        "performance": {
                            "process_ms": result["timings"].get("event_chain_ms", 0.0)
                            + (phys.get("timings") or {}).get("physical_total_ms", 0.0),
                            "runtime": result["timings"],
                        },
                        "diagnostics": {
                            "tracking": {
                                "reason": record.get("target_reason"),
                                "continuityTrackId": record.get("continuity_track_id"),
                                "tracks": [
                                    {
                                        "track_id": t.get("track_id"),
                                        "status": t.get("status"),
                                        "component_ids": t.get("component_ids"),
                                        "selection_score": t.get("selection_score"),
                                        "reason": t.get("reason"),
                                        "point_count": len(t.get("source_rows") or []),
                                    }
                                    for t in (record.get("tracks") or [])[:32]
                                ],
                                "trackCount": len(record.get("tracks") or []),
                            }
                        },
                        "human_physical_v1": phys_compact,
                        "camera": cam_meta,
                    }
                    states.append(sanitize_json(state_obj))

                    center_raw = bbox["raw"]["center"] if bbox else None
                    center_lev = bbox["leveled"]["center"] if (bbox and bbox["leveled"]) else None
                    timeline.append(
                        {
                            "i": idx,
                            "t": rel_t,
                            "fall_state": fall_state_val,
                            "belief_state": belief_state_val,
                            "tid": record["target_track_id"],
                            "center_raw": center_raw,
                            "center_leveled": center_lev,
                        }
                    )

                    if progress_cb and (idx % 10 == 0 or idx == count - 1):
                        progress_cb(
                            "pass2_infer",
                            idx + 1,
                            count,
                            f"Pass 2/2 运行物理人体与跌倒推理 ({idx + 1}/{count})",
                        )
        finally:
            cam_index.close()

        cache_key = self._compute_cache_key(meta_sha, points_sha, runtime.config_sha)
        target_cache_dir = self.cache_dir / f"{sid}_{cache_key}"
        assert_safe_cache_dir(target_cache_dir)

        if progress_cb:
            progress_cb("cache_write", 0, 1, "正在写入离线推理缓存...")

        summary = sanitize_json(
            {
                "cache_format": CACHE_FORMAT_VERSION,
                "cache_key": cache_key,
                "sid": sid,
                "title": KNOWN_TITLES.get(sid, sid),
                "meta_sha256": meta_sha,
                "points_sha256": points_sha,
                "runtime_config_sha256": runtime.config_sha,
                "frame_count": count,
                "duration_sec": round(rel_times[-1], 3) if rel_times else 0.0,
                "has_camera": cam_index.available,
                "camera_frames": len(cam_index.rows) if cam_index.available else 0,
                "compute_s": round(time.perf_counter() - t_start, 3),
                "stamp_secs": stamp_secs,
                "relative_times": rel_times,
                "display_plane": display_plane,
                "ground_reason": ground_reason,
                "timeline": timeline,
            }
        )

        # 原子写入临时目录后再重命名
        tmp_dir = Path(tempfile.mkdtemp(prefix=f".tmp_{sid}_", dir=str(self.cache_dir)))
        try:
            (tmp_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, allow_nan=False), encoding="utf-8"
            )
            with (tmp_dir / "states.jsonl").open("w", encoding="utf-8") as sf:
                for st in states:
                    sf.write(json.dumps(st, ensure_ascii=False, allow_nan=False) + "\n")

            def _pack_csr(lst: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
                offs = np.zeros(len(lst) + 1, dtype=np.int32)
                for i, a in enumerate(lst):
                    offs[i + 1] = offs[i] + len(a)
                flat = np.concatenate(lst) if offs[-1] > 0 else np.empty(0, dtype=np.int32)
                return offs, flat

            t_offs, t_flat = _pack_csr(target_list)
            r_offs, r_flat = _pack_csr(recovery_list)
            o_offs, o_flat = _pack_csr(other_list)
            f_offs, f_flat = _pack_csr(fg_list)
            np.savez_compressed(
                tmp_dir / "rows.npz",
                target_offsets=t_offs,
                target_flat=t_flat,
                recovery_offsets=r_offs,
                recovery_flat=r_flat,
                other_offsets=o_offs,
                other_flat=o_flat,
                fg_offsets=f_offs,
                fg_flat=f_flat,
            )

            if target_cache_dir.exists():
                import shutil
                shutil.rmtree(target_cache_dir, ignore_errors=True)
            tmp_dir.rename(target_cache_dir)
        except BaseException:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise

        return ReplaySessionData(
            sid,
            session_dir,
            meta,
            meta_sha,
            points_sha,
            summary,
            states,
            target_cache_dir / "rows.npz",
            grid,
            identity,
        )
