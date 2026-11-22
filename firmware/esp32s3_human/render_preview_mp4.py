"""Render side-by-side radar depth map + overlay + synced USB camera MP4 previews."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src" / "human_fall_detection"))

from core.capture_input import ROW_DTYPE  # noqa: E402
from core.range_image import ScanGrid  # noqa: E402

AZ_CSV = REPO_ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s" / "ifw192s_azimuth_192x256.csv"
EL_CSV = REPO_ROOT / "src" / "inno_lidar_ros" / "config" / "ifw192s" / "ifw192s_elevation_192x256.csv"

DEFAULT_SESSIONS = [
    "cap_20261028_houdao",
    "cap_20261028_qiandao",
    "cap_20261028_huanmandiedao",
    "cap_20261028_jixiedaiwanyao",
]

STATE_COLORS = {
    "UPRIGHT": (80, 220, 100),        # BGR green
    "FALLING": (0, 200, 255),         # BGR amber
    "FALL_SUSPECTED": (50, 50, 255),  # BGR red
    "UNKNOWN": (180, 180, 180),
}


def load_camera_index(session_dir: Path):
    idx_path = session_dir / "camera_frames.jsonl"
    mjpeg_path = session_dir / "camera.mjpeg"
    if not idx_path.exists() or not mjpeg_path.exists():
        return None, None, None
    entries = [json.loads(ln) for ln in idx_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    times = np.array([e["recv_unix_ns"] * 1e-9 for e in entries], dtype=np.float64)
    return mjpeg_path, entries, times


def read_camera_frame(mjpeg_f, entry: dict) -> np.ndarray | None:
    mjpeg_f.seek(int(entry["offset"]))
    buf = mjpeg_f.read(int(entry["length"]))
    arr = np.frombuffer(buf, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def render_depth_bgr(range_img: np.ndarray, out_w: int = 640, out_h: int = 480) -> np.ndarray:
    # range_img: (192, 256) float, NaN/<=0 for missing.
    # IFW192S ring=0 is bottom (-36.1 deg) and ring=191 is top (+36.1 deg),
    # so flip vertically for upright display.
    img_up = range_img[::-1, :]
    valid = np.isfinite(img_up) & (img_up > 0.1)
    norm = np.zeros_like(img_up, dtype=np.float32)
    # Near=hot, far=cool (0.3m .. 5.5m)
    norm[valid] = np.clip(1.0 - (img_up[valid] - 0.3) / 5.2, 0.0, 1.0)
    gray = (norm * 255.0).astype(np.uint8)
    color = cv2.applyColorMap(gray, cv2.COLORMAP_TURBO)
    color[~valid] = (12, 12, 16)
    return cv2.resize(color, (out_w, out_h), interpolation=cv2.INTER_NEAREST)


def render_session(session_name: str, grid: ScanGrid, ev_dir: Path, out_mp4: Path) -> Path:
    sdir = REPO_ROOT / "data" / "sessions" / session_name
    meta = json.loads((sdir / "meta.json").read_text(encoding="utf-8"))
    frames = meta["frames"]
    mm = np.memmap(sdir / "points.bin", dtype=ROW_DTYPE, mode="r")

    jsonl_path = ev_dir / f"{session_name}.jsonl"
    track_lines = [json.loads(ln) for ln in jsonl_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    frame_results = [m for m in track_lines if m.get("type") == "frame"]

    mjpeg_path, cam_entries, cam_times = load_camera_index(sdir)
    cam_f = mjpeg_path.open("rb") if mjpeg_path else None

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    panel_w, panel_h = 640, 480
    header_h = 60
    total_w = panel_w * 2 if cam_f else panel_w
    total_h = header_h + panel_h

    ff_cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{total_w}x{total_h}", "-r", "10",
        "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-movflags", "+faststart",
        str(out_mp4),
    ]
    proc = subprocess.Popen(ff_cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    sx = panel_w / 256.0
    sy = panel_h / 192.0

    try:
        n = min(len(frames), len(frame_results))
        t0 = float(frames[0]["bag_time_sec"])
        for i in range(n):
            fr = frames[i]
            res = frame_results[i]
            off = int(fr["offset_points"])
            cnt = int(fr["count_points"])
            rows = mm[off : off + cnt]
            decoded = grid.decode(rows, (session_name, int(fr.get("seq", i))))
            depth_img = render_depth_bgr(decoded.range_m, panel_w, panel_h)

            # Determine overall status
            locked_tracks = [t for t in res["tracks"] if t["locked"]]
            top_state = "NO_TARGET"
            top_reason = ""
            for t in locked_tracks:
                st = t["state"]
                if st == "FALL_SUSPECTED":
                    top_state = st
                    top_reason = t["reason"]
                    break
                elif st == "FALLING" and top_state != "FALL_SUSPECTED":
                    top_state = st
                elif st == "UPRIGHT" and top_state == "NO_TARGET":
                    top_state = st

            # Draw track boxes on depth image
            for t in locked_tracks:
                if not t["measured"]:
                    continue
                r0, c0, r1, c1 = t["box"]
                x0 = int(round(c0 * sx))
                x1 = int(round((c1 + 1) * sx))
                # Vertical flip: ring 191 -> y=0, ring 0 -> y=panel_h
                y0 = int(round((191 - r1) * sy))
                y1 = int(round((192 - r0) * sy))
                col = STATE_COLORS.get(t["state"], (200, 200, 200))
                thick = 3 if t["state"] == "FALL_SUSPECTED" else 2
                cv2.rectangle(depth_img, (x0, y0), (x1, y1), col, thick)

                lbl1 = f"ID{t['id']} {t['state']} H={t['height_m']:.2f}m asp={t['aspect']:.2f}"
                lbl2 = f"drop={t['drop_m']:.2f}m dv={t['pk_dv']:.2f} da={t['pk_da']:.1f} low={t['low_s']:.1f}s"
                ty = max(28, y0 - 18)
                tx = max(4, min(panel_w - 310, x0))
                cv2.rectangle(depth_img, (tx - 2, ty - 14), (tx + 305, ty + 18), (0, 0, 0), -1)
                cv2.putText(depth_img, lbl1, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.44, col, 1, cv2.LINE_AA)
                cv2.putText(depth_img, lbl2, (tx, ty + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (230, 230, 230), 1, cv2.LINE_AA)

            cv2.putText(depth_img, "LiDAR 192x256 Depth (0.3-5.5m) | ESP32-S3 C++ Core",
                        (10, panel_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (220, 220, 220), 1, cv2.LINE_AA)

            # Compose full canvas
            canvas = np.full((total_h, total_w, 3), (24, 26, 32), dtype=np.uint8)
            canvas[header_h : header_h + panel_h, 0:panel_w] = depth_img

            if cam_f is not None and cam_times is not None and cam_entries is not None:
                bt = float(fr["bag_time_sec"])
                idx_c = int(np.argmin(np.abs(cam_times - bt)))
                skew_ms = (cam_times[idx_c] - bt) * 1000.0
                cam_img = read_camera_frame(cam_f, cam_entries[idx_c])
                if cam_img is not None:
                    cam_rs = cv2.resize(cam_img, (panel_w, panel_h), interpolation=cv2.INTER_AREA)
                    cv2.putText(cam_rs, f"USB Camera (sync skew {skew_ms:+.0f} ms)",
                                (10, panel_h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (240, 240, 240), 1, cv2.LINE_AA)
                    canvas[header_h : header_h + panel_h, panel_w : panel_w * 2] = cam_rs

            # Header bar
            rel_t = float(fr["bag_time_sec"]) - t0
            hdr_txt = f"{session_name} | frame {i:03d}/{n-1} ({rel_t:5.2f}s) | 0-warmup, no ground-fit, pitch=26deg"
            cv2.putText(canvas, hdr_txt, (14, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (235, 235, 235), 1, cv2.LINE_AA)
            st_col = STATE_COLORS.get(top_state, (160, 160, 160))
            st_txt = f"STATUS: {top_state}" + (f" ({top_reason})" if top_reason else "")
            cv2.putText(canvas, st_txt, (14, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.64, st_col, 2, cv2.LINE_AA)

            proc.stdin.write(canvas.tobytes())

        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed with rc={rc}")
    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        if proc.poll() is None:
            proc.wait()
        del mm
        if cam_f is not None:
            cam_f.close()

    return out_mp4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="+", default=DEFAULT_SESSIONS)
    ap.add_argument(
        "--ev-dir",
        type=Path,
        default=REPO_ROOT / "docs" / "evidence" / "2026-11-21_esp32s3_human_kinematic",
    )
    args = ap.parse_args()

    grid = ScanGrid.from_csv(AZ_CSV, EL_CSV)
    out_dir = args.ev_dir / "videos"
    for name in args.sessions:
        mp4 = out_dir / f"{name}_preview.mp4"
        render_session(name, grid, args.ev_dir, mp4)
        print(f"OK: {mp4} ({mp4.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
