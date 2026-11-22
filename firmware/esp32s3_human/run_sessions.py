"""Offline replay runner for ESP32-S3 C++ background-free kinematic human tracker.

Decodes IFW192S sessions via the repository's ScanGrid (no empty-room warmup,
no offline ground plane fitting; only nominal mount pitch/roll or gravity vector),
pipes binary frames to human_host.exe, and writes reproducible machine evidence.
"""

import argparse
from collections import Counter
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "human_fall_detection"))

from core.capture_input import ROW_DTYPE  # noqa: E402
from core.range_image import ScanGrid  # noqa: E402

DEFAULT_SESSIONS = [
    "cap_20261028_houdao",
    "cap_20261028_qiandao",
    "cap_20261028_huanmandiedao",
    "cap_20261028_jixiedaiwanyao",
    "cap_20261018_110029",
    "cap_20261023_221125",
]

# Fixed development windows in zero-based, inclusive LiDAR frames. Four action windows
# use approximate camera receipt times. 110029 uses tracker telemetry alone.
DEVELOPMENT_WINDOWS = {
    "cap_20261028_houdao": {"tracking": (22, 168), "low": (71, 104), "rise": (120, 153)},
    "cap_20261028_qiandao": {"tracking": (99, 240), "low": (150, 173), "rise": (197, 218)},
    "cap_20261028_huanmandiedao": {"tracking": (21, 221), "low": (100, 163), "rise": (186, 207)},
    "cap_20261028_jixiedaiwanyao": {"tracking": (31, 260), "tie_and_rise": (65, 115),
                                   "squat_and_rise": (164, 190), "bend_and_rise": (190, 239)},
    "cap_20261018_110029": {"tracking": (108, 370), "pause": (177, 300), "walk_again": (301, 370)},
    "cap_20261023_221125": {"tracking": (15, 116), "low": (60, 92), "rise": (100, 108)},
}
CONTROL_SESSIONS = {"cap_20261028_jixiedaiwanyao", "bird_archive"}

AZ_CSV = REPO_ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s" / "ifw192s_azimuth_192x256.csv"
EL_CSV = REPO_ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s" / "ifw192s_elevation_192x256.csv"
DEFAULT_HOST_EXE = Path(__file__).resolve().parent / "build" / "human_host.exe"

CELL_DTYPE = np.dtype([
    ("cell", "<u2"),
    ("reserved", "<u2"),
    ("x", "<f4"),
    ("y", "<f4"),
    ("z", "<f4"),
])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def measure_continuity(frames: list, session: str) -> dict:
    observed = [(frame["frame"], [tr for tr in frame["tracks"] if tr["locked"] and tr["measured"]])
                for frame in frames]
    first_height = {}
    locks = Counter()
    for _, tracks in observed:
        for tr in tracks:
            locks[tr["id"]] += 1
            first_height.setdefault(tr["id"], tr["height_m"])
    main_id = min(locks, key=lambda track_id: (-locks[track_id], track_id)) if locks else None
    windows = DEVELOPMENT_WINDOWS.get(session, {})
    intervals = {}
    for name, (lo, hi) in windows.items():
        window = [(frame, tracks) for frame, tracks in observed if lo <= frame <= hi]
        if len(window) != hi - lo + 1:
            raise ValueError(f"{session}: incomplete fixed interval {name}")
        primary = None
        switches = 0
        gap = max_gap = 0
        for _, tracks in window:
            if not tracks:
                gap += 1
                max_gap = max(max_gap, gap)
                continue
            gap = 0
            track_ids = {tr["id"] for tr in tracks}
            if primary not in track_ids:
                switches += primary is not None
                primary = max(tracks, key=lambda tr: (tr["pts"], -tr["id"]))["id"]
        main_frames = sum(any(tr["id"] == main_id for tr in tracks) for _, tracks in window)
        intervals[name] = {
            "frames": [lo, hi], "locked_frames": sum(bool(tracks) for _, tracks in window),
            "main_id_frames": main_frames, "main_id_coverage": round(main_frames / len(window), 4),
            "primary_id_switches": switches, "max_no_lock_frames": max_gap,
        }
    main_alert = next((frame for frame, tracks in observed if any(
        tr["id"] == main_id and tr["state"] == "FALL_SUSPECTED" for tr in tracks)), None)
    rise = windows.get("rise")
    recovery = next((frame for frame, tracks in observed if main_alert < frame and rise[0] <= frame <= rise[1]
                     and any(tr["id"] == main_id and tr["state"] == "UPRIGHT" and
                             tr["height_m"] >= 1.02 and tr["drop_m"] <= 0.35 for tr in tracks)),
                    None) if rise and main_alert is not None else None
    low_ids = {track_id for track_id, height in first_height.items() if height < 0.90}
    return {
        "main_id": main_id, "first_lock_heights_m": first_height, "measured_lock_ids": sorted(locks),
        "measured_locked_frames": sum(bool(tracks) for _, tracks in observed),
        "main_first_suspected_frame": main_alert, "main_upright_in_rise_window": recovery,
        "suspected_frames": sum(any(tr["state"] == "FALL_SUSPECTED" for tr in tracks) for _, tracks in observed),
        "low_entry_lock_frames": sum(any(tr["id"] in low_ids for tr in tracks) for _, tracks in observed),
        "control_lock_frames": sum(bool(tracks) for _, tracks in observed) if session == "bird_archive" else None,
        "control_suspected_frames": sum(any(tr["state"] == "FALL_SUSPECTED" for tr in tracks)
                                        for _, tracks in observed) if session in CONTROL_SESSIONS else None,
        "intervals": intervals,
    }


def replay_frames(path: Path) -> list:
    with path.open(encoding="utf-8") as stream:
        next(stream)  # Initial host configuration, not a frame.
        return [json.loads(line) for line in stream]


def run_one_session(
    session_dir: Path,
    grid: ScanGrid,
    host_exe: Path,
    pitch_deg: float,
    roll_deg: float,
    out_jsonl: Path,
) -> dict:
    meta_path = session_dir / "meta.json"
    pts_path = session_dir / "points.bin"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frames = meta["frames"]
    mm = np.memmap(pts_path, dtype=ROW_DTYPE, mode="r")

    cmd = [
        str(host_exe),
        "--pitch-deg",
        f"{pitch_deg:.3f}",
        "--roll-deg",
        f"{roll_deg:.3f}",
    ]
    prev_t = None
    chunks = []
    try:
        for idx, fr in enumerate(frames):
            off = int(fr["offset_points"])
            cnt = int(fr["count_points"])
            seq = int(fr.get("seq", idx))
            t_s = float(fr["stamp_sec"]) + float(fr["stamp_nanosec"]) * 1e-9
            dt = 0.104 if prev_t is None else t_s - prev_t
            prev_t = t_s

            rows = mm[off : off + cnt]
            decoded = grid.decode(rows, (session_dir.name, seq))
            src_rows = decoded.source_rows.ravel()
            valid_cells = np.flatnonzero(src_rows >= 0)
            valid_src = src_rows[valid_cells]

            rec = np.empty(len(valid_cells), dtype=CELL_DTYPE)
            rec["cell"] = valid_cells.astype("<u2")
            rec["reserved"] = 0
            rec["x"] = rows["x"][valid_src].astype("<f4")
            rec["y"] = rows["y"][valid_src].astype("<f4")
            rec["z"] = rows["z"][valid_src].astype("<f4")

            chunks.append(struct.pack("<IfI", seq, float(dt), len(valid_cells)))
            if len(valid_cells) > 0:
                chunks.append(rec.tobytes())

        chunks.append(struct.pack("<IfI", 0, 0.0, 0xFFFFFFFF))
    finally:
        del mm

    res = subprocess.run(
        cmd,
        input=b"".join(chunks),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"human_host failed (rc={res.returncode}): {res.stderr.decode('utf-8', errors='replace')}"
        )
    raw_out = res.stdout.decode("utf-8")

    lines = [ln for ln in raw_out.splitlines() if ln.strip()]
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    init_msg = json.loads(lines[0])
    frame_msgs = [json.loads(ln) for ln in lines[1:]]

    step_us = [m["step_us"] for m in frame_msgs]
    locked_frames = 0
    first_locked_frame = None
    falling_frames = 0
    first_falling_frame = None
    suspected_frames = 0
    first_suspected_frame = None
    suspected_reasons = set()
    max_pk_dv = 0.0
    max_pk_da = 0.0
    max_pk_ba = 0.0
    max_drop = 0.0
    locked_ids = set()

    for m in frame_msgs:
        fidx = m["frame"]
        has_locked = False
        has_falling = False
        has_suspected = False
        for tr in m["tracks"]:
            if tr["locked"] and tr["measured"]:
                has_locked = True
                locked_ids.add(tr["id"])
                if tr["pk_dv"] > max_pk_dv:
                    max_pk_dv = tr["pk_dv"]
                if tr["pk_da"] > max_pk_da:
                    max_pk_da = tr["pk_da"]
                if tr["pk_ba"] > max_pk_ba:
                    max_pk_ba = tr["pk_ba"]
                if tr["drop_m"] > max_drop:
                    max_drop = tr["drop_m"]
                if tr["state"] == "FALLING":
                    has_falling = True
                elif tr["state"] == "FALL_SUSPECTED":
                    has_suspected = True
                    suspected_reasons.add(tr["reason"])
        if has_locked:
            locked_frames += 1
            if first_locked_frame is None:
                first_locked_frame = fidx
        if has_falling:
            falling_frames += 1
            if first_falling_frame is None:
                first_falling_frame = fidx
        if has_suspected:
            suspected_frames += 1
            if first_suspected_frame is None:
                first_suspected_frame = fidx

    return {
        "session": session_dir.name,
        "frames": len(frame_msgs),
        "meta_sha256": sha256_file(meta_path),
        "points_sha256": sha256_file(pts_path),
        "pitch_deg": pitch_deg,
        "roll_deg": roll_deg,
        "workspace_bytes": init_msg["workspace_bytes"],
        "tracker_object_bytes": init_msg["tracker_object_bytes"],
        "locked_frames": locked_frames,
        "first_locked_frame": first_locked_frame,
        "unique_locked_ids": sorted(locked_ids),
        "continuity": measure_continuity(frame_msgs, session_dir.name),
        "falling_frames": falling_frames,
        "first_falling_frame": first_falling_frame,
        "fall_suspected_frames": suspected_frames,
        "first_fall_suspected_frame": first_suspected_frame,
        "fall_suspected_reasons": sorted(suspected_reasons),
        "max_peak_down_vel_mps": round(max_pk_dv, 3),
        "max_peak_down_acc_mps2": round(max_pk_da, 3),
        "max_peak_brake_acc_mps2": round(max_pk_ba, 3),
        "max_drop_top_m": round(max_drop, 3),
        "step_ms_p50": round(float(np.percentile(step_us, 50)) / 1000.0, 3),
        "step_ms_p95": round(float(np.percentile(step_us, 95)) / 1000.0, 3),
        "step_ms_max": round(float(max(step_us)) / 1000.0, 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", default=DEFAULT_SESSIONS)
    ap.add_argument("--host-exe", type=Path, default=DEFAULT_HOST_EXE)
    ap.add_argument("--pitch-deg", type=float, default=26.0)
    ap.add_argument("--roll-deg", type=float, default=0.0)
    ap.add_argument("--compare-dir", type=Path, help="Baseline host replay directory for the same sessions")
    ap.add_argument("--bird-jsonl", type=Path, help="Optional host ledger for the bird archive")
    ap.add_argument("--baseline-bird-jsonl", type=Path, help="Optional paired baseline bird ledger")
    ap.add_argument(
        "--out-dir",
        type=Path,
        required=True,
    )
    args = ap.parse_args()

    grid = ScanGrid.from_csv(AZ_CSV, EL_CSV)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for name in args.sessions:
        sdir = REPO_ROOT / "data" / "sessions" / name
        if not sdir.exists():
            raise FileNotFoundError(f"missing session: {sdir}")
        out_jsonl = args.out_dir / f"{name}.jsonl"
        summary = run_one_session(
            sdir, grid, args.host_exe, args.pitch_deg, args.roll_deg, out_jsonl
        )
        results.append(summary)
        print(
            f"{name:28s} frames={summary['frames']:3d} "
            f"locked={summary['locked_frames']:3d}(f{summary['first_locked_frame']}) "
            f"ids={len(summary['unique_locked_ids'])} "
            f"fall={summary['fall_suspected_frames']:3d}(f{summary['first_fall_suspected_frame']}) "
            f"reasons={summary['fall_suspected_reasons']} "
            f"dv={summary['max_peak_down_vel_mps']:.2f} "
            f"da={summary['max_peak_down_acc_mps2']:.2f} "
            f"drop={summary['max_drop_top_m']:.2f} "
            f"p95={summary['step_ms_p95']:.2f}ms"
        )

    src_dir = Path(__file__).resolve().parent
    report = {
        "note": "No empty-room warmup, no ground plane fitting; nominal gravity_up from pitch/roll only. No human/fall GT; accuracy/recall UNKNOWN.",
        "host_exe_sha256": sha256_file(args.host_exe),
        "source_sha256_note": "Hashes describe the current working tree. An explicit --host-exe may have been built from another revision.",
        "source_sha256": {
            "human_tracker.hpp": sha256_file(src_dir / "human_tracker.hpp"),
            "human_tracker.cpp": sha256_file(src_dir / "human_tracker.cpp"),
            "host_replay.cpp": sha256_file(src_dir / "host_replay.cpp"),
            "run_sessions.py": sha256_file(Path(__file__).resolve()),
        },
        "grid_sha256": grid.sha256,
        "sessions": results,
    }
    if args.compare_dir:
        baseline = json.loads((args.compare_dir / "SUMMARY.json").read_text(encoding="utf-8"))
        baseline_sessions = {entry["session"]: entry for entry in baseline["sessions"]}
        if baseline["grid_sha256"] != grid.sha256:
            raise ValueError("baseline scan grid differs")
        report["baseline_host_exe_sha256"] = baseline["host_exe_sha256"]
        for entry in results:
            session = entry["session"]
            for key in ("meta_sha256", "points_sha256", "pitch_deg", "roll_deg"):
                if entry[key] != baseline_sessions[session][key]:
                    raise ValueError(f"baseline {key} differs for {session}")
            entry["baseline_continuity"] = measure_continuity(
                replay_frames(args.compare_dir / f"{session}.jsonl"), session)
            before = entry["baseline_continuity"]
            after = entry["continuity"]
            print(f"{session:28s} measured {before['measured_locked_frames']:3d} -> "
                  f"{after['measured_locked_frames']:3d}; IDs {before['measured_lock_ids']} -> "
                  f"{after['measured_lock_ids']}; main recovery f{after['main_upright_in_rise_window']}")
    for key, path in (("bird_archive", args.bird_jsonl), ("baseline_bird_archive", args.baseline_bird_jsonl)):
        if path:
            report[key] = measure_continuity(replay_frames(path), "bird_archive")
            report[key]["ledger_sha256"] = sha256_file(path)
            print(f"{key:28s} locks={report[key]['measured_locked_frames']} alerts={report[key]['suspected_frames']}")
    (args.out_dir / "SUMMARY.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
