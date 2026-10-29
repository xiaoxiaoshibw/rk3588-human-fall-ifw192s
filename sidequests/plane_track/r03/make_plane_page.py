"""PLANE-01 R3 生成器：cap_20261023_215952 的“实时纸飞机绿框”对比页。

做三件事（一次跑完）：
1. 用 ``plane_live_core`` 逐帧（10 Hz，只用历史帧背景）检测纸飞机的 3D 有向包围盒，
   同时量单帧耗时；相机侧用 2D 时域中值背景 + 帧差 + 轨迹出 2D 框。
2. 导出机器证据 ``SESSION.json``（含逐帧表、阈值、SHA）与 ``detections.json``。
3. 生成自包含 HTML（内嵌 MP4 base64 + 背景点云 int16 + 逐帧检测 + 交互播放器），
   点云绿框与相机视频绿框并排、同一会话时钟实时回放。

用法：
    python -B make_plane_page.py --session <会话目录> --out <证据目录> \
        --page <输出 html> [--video-fps 10.16] [--offset 0.95] [--max-bg 16000]

本脚本在 PC 上跑（Python 3.8+ / NumPy / Pillow / ffmpeg）；不写会话数据、不部署。
"""
import argparse
import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

import plane_live_core as core

HERE = Path(__file__).resolve().parent
ROW_DTYPE = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("intensity", "<f4"),
                      ("ring", "<u2"), ("_pad1", "<u2"), ("timestamp", "<f4"), ("_pad2", "<f4")])
POINT_STRIDE = 28
CAM_W, CAM_H = 960, 540


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_session(session_dir):
    session = Path(session_dir)
    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    if meta.get("point_stride_bytes") != POINT_STRIDE:
        raise SystemExit("不支持的 point_stride_bytes: %r" % meta.get("point_stride_bytes"))
    raw = np.frombuffer((session / meta["point_file"]).read_bytes(), dtype=ROW_DTYPE)
    if len(raw) != meta["total_points"]:
        raise SystemExit("points.bin 点数 %d 与 meta.total_points %d 不一致"
                         % (len(raw), meta["total_points"]))
    cam_rows = [json.loads(line) for line in
                (session / "camera_frames.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    cam_blob = (session / "camera.mjpeg").read_bytes()
    return session, meta, raw, cam_rows, cam_blob


def frame_slice(meta, raw, index):
    fr = meta["frames"][index]
    off, n = int(fr["offset_points"]), int(fr["count_points"])
    return raw[off:off + n]


def run_radar(meta, raw, bg_window, params):
    bg = core.BackgroundModel(frames=bg_window)
    tracker = core.PlaneTracker()
    times = [float(f["bag_time_sec"]) for f in meta["frames"]]
    rows = []
    ms = []
    for i in range(len(meta["frames"])):
        payload = frame_slice(meta, raw, i)
        xyz = np.stack([payload["x"], payload["y"], payload["z"]], axis=1).astype(np.float64)
        ring = payload["ring"].astype(np.int64)
        dt = (times[i] - times[i - 1]) if i else 0.0
        tick = time.perf_counter()
        res = core.detect_frame(xyz, ring, bg, tracker, i, dt,
                                tau=params["tau_m"], drop=params["drop_m"],
                                eps=params["cluster_m"], min_points=params["min_points"],
                                max_extent=params["max_extent_m"], max_range=params["max_range_m"])
        ms.append((time.perf_counter() - tick) * 1000.0)
        target = res["target"]
        row = dict(i=i, t=round(times[i] - times[0], 4), pts=int(len(xyz)),
                   fg=int(res["foreground_points"]), nc=len(res["candidates"]),
                   st="boot" if res.get("bootstrap") else "none",
                   track=None, hits=0, range=0.0, speed=0.0, box=None, pts_xyz=[])
        if target is not None:
            row.update(st="confirmed" if target["confirmed"] else "tentative",
                       track=int(target["track_id"]), hits=int(target["hits"]),
                       range=round(float(target["range"]), 3),
                       speed=round(float(target["speed"]), 3),
                       box=dict(c=[round(v, 3) for v in target["box"]["center"]],
                                a=[[round(v, 4) for v in ax] for ax in target["box"]["axes"]],
                                h=[round(v, 3) for v in target["box"]["half"]],
                                n=int(target["point_count"])),
                       pts_xyz=[[round(v, 3) for v in p] for p in target["points"]])
        rows.append(row)
    return rows, bg, ms


def extract_camera(cam_rows, cam_blob, tmpdir):
    grays, pngs, times = [], [], []
    for i, row in enumerate(cam_rows):
        chunk = cam_blob[int(row["offset"]):int(row["offset"]) + int(row["length"])]
        if chunk[:2] != b"\xff\xd8" or chunk[-2:] != b"\xff\xd9":
            raise SystemExit("相机第 %d 帧不是完整 JPEG" % i)
        im = Image.open(io.BytesIO(chunk)).convert("RGB").resize((CAM_W, CAM_H), Image.LANCZOS)
        png = Path(tmpdir) / ("f%03d.png" % i)
        im.save(png)
        pngs.append(png)
        grays.append(np.asarray(im.convert("L"), dtype=np.uint8))
        times.append(float(row["recv_unix_ns"]) / 1e9)
    return grays, pngs, times


def estimate_offset(radar_rows, cam_boxes, cam_times, radar_t0):
    """用“起飞/落地”两个共同事件锚定时钟偏移；返回 (offset, 明细)。"""
    def first_radar(rows):
        for k, r in enumerate(rows):
            if r["box"]:
                return k
        return None

    def first_cam(boxes):
        for k, b in enumerate(boxes):
            if b:
                return k
        return None

    def first_rest(centres, tol):
        for k in range(len(centres) - 3):
            if centres[k] is None:
                continue
            if all(centres[j] is not None and
                   float(np.linalg.norm(np.asarray(centres[j]) - np.asarray(centres[k]))) <= tol
                   for j in (k + 1, k + 2, k + 3)):
                return k
        return None

    r_centres = [r["box"]["c"] if r["box"] else None for r in radar_rows]
    c_centres = [((b["x0"] + b["x1"]) / 2.0, (b["y0"] + b["y1"]) / 2.0) if b else None
                 for b in cam_boxes]
    r0, c0 = first_radar(radar_rows), first_cam(cam_boxes)
    r1, c1 = first_rest(r_centres, 0.06), first_rest(c_centres, 3.0)
    anchors = {}
    if r0 is not None and c0 is not None:
        anchors["start"] = (cam_times[c0] - radar_t0) - radar_rows[r0]["t"]
        anchors["start_detail"] = dict(radar_frame=r0, radar_t=radar_rows[r0]["t"], cam_frame=c0)
    if r1 is not None and c1 is not None:
        anchors["rest"] = (cam_times[c1] - radar_t0) - radar_rows[r1]["t"]
        anchors["rest_detail"] = dict(radar_frame=r1, radar_t=radar_rows[r1]["t"], cam_frame=c1)
    values = [v for k, v in anchors.items() if k in ("start", "rest")]
    if not values:
        raise SystemExit("相机与雷达没有共同目标事件，无法估计时钟偏移")
    offset = float(np.mean(values))
    spread = float(max(values) - min(values)) if len(values) > 1 else None
    anchors["offset_s"] = offset
    anchors["spread_s"] = spread
    return offset, anchors


def downsample(points, voxel=0.04):
    pts = np.asarray(points, dtype=np.float64)
    finite = np.isfinite(pts[:, 0])
    pts = pts[finite]
    if not len(pts):
        return pts
    cells = np.floor(pts / voxel).astype(np.int64)
    _, idx = np.unique(cells, axis=0, return_index=True)
    return pts[np.sort(idx)]


def pack_points(pts):
    q = np.clip(np.rint(np.asarray(pts, dtype=np.float64) * 1000.0), -32767, 32767).astype("<i2")
    return base64.b64encode(q.tobytes()).decode("ascii")


def encode_video(pngs, fps, out_mp4):
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("找不到 ffmpeg")
    src = pngs[0].parent / "f%03d.png"
    cmd = [exe, "-y", "-loglevel", "error", "-framerate", "%.6f" % fps,
           "-i", str(src), "-c:v", "libx264", "-preset", "slow", "-crf", "22",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)]
    subprocess.run(cmd, check=True)
    return out_mp4


def contact_sheet(radar_rows, out_png, frames=(24, 26, 28, 29, 34, 50)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(15, 8.2))
    for ax, idx in zip(axes.ravel(), frames):
        row = radar_rows[idx]
        ax.set_facecolor("#0b1119")
        if row["box"]:
            ax.scatter([p[0] for p in row["pts_xyz"]], [p[1] for p in row["pts_xyz"]],
                       s=14, c="#22ff88", zorder=3)
            c = np.asarray(row["box"]["c"])
            a = np.asarray(row["box"]["a"])
            h = np.asarray(row["box"]["h"])
            pts = []
            for i in range(8):
                sx = 1 if i & 1 else -1
                sy = 1 if i & 2 else -1
                sz = 1 if i & 4 else -1
                pts.append(c + a[0] * h[0] * sx + a[1] * h[1] * sy + a[2] * h[2] * sz)
            pts = np.asarray(pts)
            edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
                     (0, 4), (1, 5), (2, 6), (3, 7)]
            for i, j in edges:
                ax.plot([pts[i, 0], pts[j, 0]], [pts[i, 1], pts[j, 1]], color="#22ff88", lw=1.4)
            ax.set_title("frame %d · t=%.2fs · %s · %.2f m · %d pts"
                         % (idx, row["t"], row["st"], row["range"], row["box"]["n"]),
                         color="#cfe0ef", fontsize=10)
        else:
            ax.set_title("frame %d · t=%.2fs · 无目标" % (idx, row["t"]),
                         color="#8ba1b7", fontsize=10)
        ax.tick_params(colors="#6f869b", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#22323f")
        ax.set_aspect("equal")
        ax.grid(color="#1b2833", lw=0.5, alpha=0.6)
        ax.set_xlabel("x (m)", color="#6f869b", fontsize=8)
        ax.set_ylabel("y (m)", color="#6f869b", fontsize=8)
    fig.patch.set_facecolor("#0b1119")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)


def build_page(template, data, out_html):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = template.replace("__DATA_JSON__", body).replace("__TITLE__", data["session"]["title"])
    with open(out_html, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    return out_html


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--video-fps", type=float, default=None)
    ap.add_argument("--offset", type=float, default=None)
    ap.add_argument("--max-bg", type=int, default=26000)
    ap.add_argument("--bg-voxel", type=float, default=0.032)
    ap.add_argument("--bg-window", type=int, default=21,
                    help="背景建立窗口帧数（这段时间不做检测）")
    args = ap.parse_args(argv)

    session_dir, meta, raw, cam_rows, cam_blob = load_session(args.session)
    n = len(meta["frames"])
    params = dict(tau_m=core.TAU_NOVELTY_M, drop_m=core.RANGE_DROP_M,
                  cluster_m=core.CLUSTER_EPS_M, min_points=core.MIN_CLUSTER_POINTS,
                  max_extent_m=core.MAX_CLUSTER_EXTENT_M, max_range_m=core.MAX_RANGE_M,
                  bg_frames=int(args.bg_window))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    radar_rows, bg, ms = run_radar(meta, raw, args.bg_window, params)

    tmpdir = Path(tempfile.mkdtemp(prefix="plane_cam_"))
    try:
        grays, pngs, cam_times = extract_camera(cam_rows, cam_blob, tmpdir)
        boxes, _bg2 = core.camera_boxes(grays)
        cam_box_rows = [dict(t=0.0, box=None, area=0, peak=0) for _ in boxes]
        for i, b in enumerate(boxes):
            if b:
                cam_box_rows[i].update(box=[int(b["x0"]), int(b["y0"]), int(b["x1"]), int(b["y1"])],
                                       area=int(b["area"]), peak=round(float(b["peak"]), 1))

        if args.offset is not None:
            offset = float(args.offset)
            anchors = dict(offset_s=offset, source="cli")
        else:
            offset, anchors = estimate_offset(radar_rows, boxes, cam_times,
                                              float(meta["frames"][0]["bag_time_sec"]))

        # 会话时间：相机绝对时间 - 雷达首帧绝对时间 - 偏移
        radar_t0 = float(meta["frames"][0]["bag_time_sec"])
        for row, t_abs in zip(cam_box_rows, cam_times):
            row["t"] = round((t_abs - radar_t0) - offset, 4)

        # 视频：固定帧率（帧间隔中位数帧率），页面按帧号取框
        deltas = np.diff(cam_times)
        fps = args.video_fps or float(1.0 / np.median(deltas))
        mp4 = encode_video(pngs, fps, out / ("camera_%s.mp4" % meta["session_id"]))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # 背景点云（体素抽稀）
    bg_pts = downsample(bg.points_map, voxel=args.bg_voxel)
    if len(bg_pts) > args.max_bg:
        idx = np.linspace(0, len(bg_pts) - 1, args.max_bg).astype(np.int64)
        bg_pts = bg_pts[idx]

    # 目标质心作为默认视角中心
    centers = [r["box"]["c"] for r in radar_rows if r["box"]]
    focus = [round(float(v), 3) for v in np.mean(np.asarray(centers), axis=0)] if centers else [2.0, 1.2, 0.6]

    video_b64 = base64.b64encode(mp4.read_bytes()).decode("ascii")
    target_frames = [r for r in radar_rows if r["box"]]
    flight = [r for r in target_frames if r["speed"] > 0.5]
    boot_frames = sum(1 for r in radar_rows if r["st"] == "boot")
    stats = dict(detect_ms_median=round(float(np.median(ms)), 2),
                 detect_ms_p95=round(float(np.percentile(ms, 95)), 2),
                 detect_ms_max=round(float(np.max(ms)), 2),
                 target_frames=len(target_frames),
                 flight_frames=len(flight),
                 boot_frames=boot_frames,
                 none_frames=n - len(target_frames) - boot_frames,
                 confirmed_frames=sum(1 for r in target_frames if r["st"] == "confirmed"),
                 camera_box_frames=sum(1 for r in cam_box_rows if r["box"]),
                 bg_points=int(len(bg_pts)),
                 novelty_index=bg._novelty.kind,
                 bg_known_cells=int(np.isfinite(bg.range_map).sum()))

    data = dict(
        session=dict(id=meta["session_id"], title="纸飞机 · 实时绿框对比（雷达点云 × 相机视频）",
                     created_iso=meta.get("created_iso"), duration=round(float(meta["frames"][-1]["bag_time_sec"])
                                                                        - float(meta["frames"][0]["bag_time_sec"]), 4),
                     frames=n, total_points=int(meta["total_points"]),
                     camera_frames=len(cam_rows), fps=round(fps, 4), offset_s=round(offset, 4),
                     time_domain=meta.get("time_domain")),
        params=params,
        view=dict(focus=focus, dist=4.2, yaw=-2.80, pitch=0.32),
        stats=stats,
        bg=dict(count=int(len(bg_pts)), xyz_b64=pack_points(bg_pts)),
        radar=[dict(i=r["i"], t=r["t"], pts=r["pts"], fg=r["fg"], nc=r["nc"], st=r["st"],
                    track=r["track"], hits=r["hits"], range=r["range"], speed=r["speed"],
                    box=r["box"], p3=r["pts_xyz"]) for r in radar_rows],
        cam=dict(fps=round(fps, 4), start=round(cam_box_rows[0]["t"], 4),
                 frames=[dict(t=r["t"], box=r["box"], area=r["area"], peak=r["peak"])
                         for r in cam_box_rows]),
        video_uri="data:video/mp4;base64," + video_b64,
    )

    template = (HERE / "compare_template.html").read_text(encoding="utf-8")
    Path(args.page).parent.mkdir(parents=True, exist_ok=True)
    page = build_page(template, data, Path(args.page))

    # 证据（不含 base64 视频）
    evidence = {k: v for k, v in data.items() if k != "video_uri"}
    evidence["anchors"] = anchors
    evidence["inputs"] = dict(
        session_dir=str(session_dir),
        meta_sha256=sha256_file(session_dir / "meta.json"),
        points_sha256=sha256_file(session_dir / meta["point_file"]),
        camera_sha256=sha256_file(session_dir / "camera.mjpeg"),
        camera_index_sha256=sha256_file(session_dir / "camera_frames.jsonl"),
    )
    evidence["outputs"] = dict(page=str(page), page_bytes=page.stat().st_size,
                               video=str(mp4), video_bytes=mp4.stat().st_size,
                               video_fps=round(fps, 4))
    (out / "detections.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                                         encoding="utf-8", newline="\n")
    contact_sheet(radar_rows, out / "contact_sheet.png")

    print(json.dumps(dict(
        session=meta["session_id"], frames=n, camera_frames=len(cam_rows),
        offset_s=round(offset, 3), anchors=anchors,
        target_frames=len(target_frames), flight_frames=len(flight),
        camera_box_frames=stats["camera_box_frames"],
        detect_ms_median=stats["detect_ms_median"], detect_ms_p95=stats["detect_ms_p95"],
        bg_points=len(bg_pts), video_bytes=mp4.stat().st_size, page_bytes=page.stat().st_size,
    ), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()