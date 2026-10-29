"""Render a self-contained bathroom-demo replay (range image + BEV + state).

Usage:
  python -B pc_apps/bathroom_demo/make_demo.py `
      --session data/sessions/cap_20261018_110029 `
      --transform docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/leveling_02/TRANSFORM.json `
      --out docs/evidence/2026-10-23_bathroom_demo

Outputs:
  frames/real/f000.png ...      per-frame composite (range image + BEV + stats)
  frames/synth/f000.png ...     controlled capsule fall
  index.html                    offline player (file:// works)
  SUMMARY.json / metrics.csv    per-frame and aggregate metrics
  contact_sheet.png             four real + four synthetic frames
"""
import argparse
import csv
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import range_pipeline as rp  # noqa: E402

W, H = 760, 440
PW, PH = 340, 272
LEFT, RIGHT, TOP = 10, 400, 32
STATE_COLORS = {
    "upright": (80, 220, 120),
    "transition": (240, 210, 80),
    "descending": (255, 150, 60),
    "fall_suspected": (255, 70, 70),
    "long_lie_suspected": (255, 40, 40),
    "low_support": (170, 170, 170),
    "low_no_descent": (200, 160, 80),
    "unknown": (150, 150, 150),
}


def _depth_rgb(rng):
    rgb = np.zeros((rp.RINGS, rp.COLS, 3), dtype=np.uint8)
    valid = np.isfinite(rng)
    t = np.clip(np.nan_to_num((rng - 0.5) / 5.5, nan=0.0), 0.0, 1.0)
    rgb[..., 0] = (255 * (1.0 - t) + 40 * t).astype(np.uint8)
    rgb[..., 1] = (90 + 40 * t).astype(np.uint8)
    rgb[..., 2] = (40 + 215 * t).astype(np.uint8)
    rgb[~valid] = 0
    return rgb


def render_frame(fr, out_path, title):
    grid = fr["grid"]
    mask = fr["mask"]
    target = fr["target"]
    state = fr["state"]
    rgb = _depth_rgb(grid.range)
    rgb[mask] = (190, 190, 190)
    if target is not None:
        rows = target.features["pixels"][:, 0]
        cols = target.features["pixels"][:, 1]
        rgb[rows, cols] = (255, 60, 60)
    panel = Image.fromarray(rgb).resize((PW, PH), Image.NEAREST)
    canvas = Image.new("RGB", (W, H), (12, 14, 18))
    draw = ImageDraw.Draw(canvas)
    draw.text((LEFT, 8), title, fill=(235, 240, 250))
    canvas.paste(panel, (LEFT, TOP))
    draw.rectangle([LEFT, TOP, LEFT + PW - 1, TOP + PH - 1], outline=(70, 78, 92))
    draw.text((LEFT + 6, TOP + 4), "range image (0.5-6 m)", fill=(245, 245, 245))

    if target is not None:
        r0, r1, c0, c1 = target.features["pixel_bbox"]
        x0 = LEFT + int(c0 / rp.COLS * PW)
        x1 = LEFT + int(c1 / rp.COLS * PW)
        y0 = TOP + int(r0 / rp.RINGS * PH)
        y1 = TOP + int(r1 / rp.RINGS * PH)
        draw.rectangle([x0, y0, x1, y1], outline=(255, 60, 60), width=2)

    # BEV: x forward 0..4 m, y -2..2 m
    bev = Image.new("RGB", (PW, PH), (8, 10, 14))
    bd = ImageDraw.Draw(bev)
    for gx in range(0, 5):
        px = int(gx / 4.0 * (PW - 1))
        bd.line([(px, 0), (px, PH - 1)], fill=(35, 40, 50))
        bd.text((px + 2, 2), "%dm" % gx, fill=(120, 130, 145))
    for gy in (-2, -1, 0, 1, 2):
        py = int((gy + 2) / 4.0 * (PH - 1))
        bd.line([(0, py), (PW - 1, py)], fill=(35, 40, 50))
    valid = grid.valid & np.isfinite(grid.range) & (grid.range < 4.0)
    ys, xs = np.nonzero(valid)
    for r, c in zip(ys.tolist(), xs.tolist()):
        x = float(grid.x[r, c])
        y = float(grid.y[r, c])
        if 0.0 <= x < 4.0 and -2.0 <= y < 2.0:
            px = int(x / 4.0 * (PW - 1))
            py = int((y + 2.0) / 4.0 * (PH - 1))
            bd.point((px, py), fill=(80, 90, 105))
    if target is not None:
        trail = target.trail[-80:]
        for j in range(1, len(trail)):
            a = (int(trail[j - 1][0] / 4.0 * (PW - 1)), int((trail[j - 1][1] + 2) / 4.0 * (PH - 1)))
            b = (int(trail[j][0] / 4.0 * (PW - 1)), int((trail[j][1] + 2) / 4.0 * (PH - 1)))
            bd.line([a, b], fill=(70, 140, 255), width=2)
        rows = target.features["pixels"][:, 0]
        cols = target.features["pixels"][:, 1]
        for r, c in zip(rows.tolist(), cols.tolist()):
            x = float(grid.x[r, c])
            y = float(grid.y[r, c])
            if 0.0 <= x < 4.0 and -2.0 <= y < 2.0:
                bd.point((int(x / 4.0 * (PW - 1)), int((y + 2.0) / 4.0 * (PH - 1))), fill=(255, 70, 70))
    bd.ellipse([PW // 2 - 4, PH // 2 - 4, PW // 2 + 4, PH // 2 + 4], fill=(0, 230, 230))
    bd.text((PW // 2 + 8, PH // 2 - 6), "sensor", fill=(0, 230, 230))
    bd.text((6, 6), "BEV: x forward / y left", fill=(180, 190, 205))
    canvas.paste(bev, (RIGHT, TOP))
    draw.rectangle([RIGHT, TOP, RIGHT + PW - 1, TOP + PH - 1], outline=(70, 78, 92))

    color = STATE_COLORS.get(state, (200, 200, 200))
    draw.text((LEFT, TOP + PH + 10), "frame %03d   t=%5.2fs   rule=" % (fr["index"], fr["stamp"]),
              fill=(210, 220, 235))
    draw.text((LEFT + 300, TOP + PH + 10), state.upper(), fill=color)
    hmm_state = fr.get("hmm_state", "unknown")
    p_lying = float(fr.get("hmm_probs", {}).get("lying", 0.0))
    draw.text((LEFT + 520, TOP + PH + 10), "HMM=%s pL=%.2f" % (hmm_state, p_lying),
              fill=(120, 180, 255))
    if target is None:
        detail = "no target (fg=%d, comps=%d)" % (int(mask.sum()), len(fr["features"]))
    else:
        f = target.features
        detail = ("track=%d pts=%d range=%.2fm h90=%.2fm span=%.2fm angle=%s"
                  % (target.id, f["count"], f["range_m"], f["height_p90"],
                     f["height_span"],
                     "NA" if f["inclination_deg"] is None else "%.0fdeg" % f["inclination_deg"]))
    draw.text((LEFT, TOP + PH + 28), detail, fill=(190, 200, 215))
    draw.text((LEFT, TOP + PH + 46),
              "front-end: range residual + depth-continuous components. rule/HMM candidates; not a confirmed alarm.",
              fill=(140, 150, 165))
    canvas.save(out_path)


def render_contact_sheet(real_frames, synth_frames, out_path):
    picks = [(real_frames, [120, 183, 300, 370], "REAL"),
             (synth_frames, [10, 30, 55, 90], "SYNTH")]
    cell_w, cell_h = 380, 220
    sheet = Image.new("RGB", (cell_w * 4, cell_h * 2 + 20), (10, 12, 16))
    d = ImageDraw.Draw(sheet)
    for row, (prefix_dir, indices, label) in enumerate(picks):
        d.text((8, row * (cell_h + 10) + 2), label, fill=(235, 240, 250))
        for col, idx in enumerate(indices):
            path = os.path.join(prefix_dir, "f%03d.png" % idx)
            if os.path.exists(path):
                img = Image.open(path).convert("RGB").resize((cell_w, cell_h))
                sheet.paste(img, (col * cell_w, row * (cell_h + 10) + 14))
    sheet.save(out_path)


def run_real(session, transform, out_dir):
    frames_dir = os.path.join(out_dir, "frames", "real")
    os.makedirs(frames_dir, exist_ok=True)
    records = []
    for fr in rp.iter_session(session, transform=transform):
        records.append(rp._record(fr))
        render_frame(fr, os.path.join(frames_dir, "f%03d.png" % fr["index"]),
                     "IFW192S bathroom demo - REAL session (no fall)")
    summary = rp.summarize(records, id_switches=records[-1]["id_switches"] if records else 0)
    return records, summary, frames_dir


def run_synth(session, transform, out_dir):
    frames_dir = os.path.join(out_dir, "frames", "synth")
    os.makedirs(frames_dir, exist_ok=True)
    settings = {"min_component": 8, "long_lie_s": 5.0, "min_track_hits": 2}
    records = []
    for fr in rp.iter_synthetic_capsule_fall(session, transform=transform, settings=settings):
        records.append(rp._record(fr))
        render_frame(fr, os.path.join(frames_dir, "f%03d.png" % fr["index"]),
                     "IFW192S bathroom demo - SYNTHETIC capsule fall (algorithm test)")
    summary = rp.summarize(records, id_switches=records[-1]["id_switches"] if records else 0)
    return records, summary, frames_dir


def write_metrics(records, path):
    fields = ["index", "stamp", "state", "n_fg", "n_comp", "n_tracks",
              "target_id", "target_count", "target_range_m", "target_height_p90",
              "target_height_span"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in records:
            t = r.get("target") or {}
            writer.writerow(dict(
                index=r["index"], stamp=r["stamp"], state=r["state"],
                n_fg=r["n_fg"], n_comp=r["n_comp"], n_tracks=r["n_tracks"],
                target_id=t.get("id"), target_count=t.get("count"),
                target_range_m=t.get("range_m"), target_height_p90=t.get("height_p90"),
                target_height_span=t.get("height_span"),
            ))


def write_html(out_dir, real, real_summary, synth, synth_summary):
    from string import Template
    with open(os.path.join(HERE, "demo_template.html"), encoding="utf-8") as fh:
        template = Template(fh.read())
    html = template.substitute(
        real_max=len(real) - 1, synth_max=len(synth) - 1,
        frames_real=real_summary.get("frames", 0), frames_synth=synth_summary.get("frames", 0),
        target_real=real_summary.get("target_frames", 0),
        target_synth=synth_summary.get("target_frames", 0),
        ratio_real="%.1f%%" % (100.0 * real_summary.get("target_ratio", 0.0)),
        ratio_synth="%.1f%%" % (100.0 * synth_summary.get("target_ratio", 0.0)),
        points_real=real_summary.get("target_points_median", "NA"),
        points_synth=synth_summary.get("target_points_median", "NA"),
        range_real=real_summary.get("target_range_median_m", "NA"),
        range_synth=synth_summary.get("target_range_median_m", "NA"),
        height_real=real_summary.get("target_height_median_m", "NA"),
        height_synth=synth_summary.get("target_height_median_m", "NA"),
        states_real=json.dumps(real_summary.get("states", {}), ensure_ascii=False),
        states_synth=json.dumps(synth_summary.get("states", {}), ensure_ascii=False),
        hmm_states_real=json.dumps(real_summary.get("hmm_states", {}), ensure_ascii=False),
        hmm_states_synth=json.dumps(synth_summary.get("hmm_states", {}), ensure_ascii=False),
        hmm_fall_real=real_summary.get("hmm_fall_frames", 0),
        hmm_long_real=real_summary.get("hmm_long_lie_frames", 0),
        hmm_fall_synth=synth_summary.get("hmm_fall_frames", 0),
        hmm_long_synth=synth_summary.get("hmm_long_lie_frames", 0),
        id_real=real_summary.get("id_switches", "NA"),
        id_synth=synth_summary.get("id_switches", "NA"),
        real_json=json.dumps(real, ensure_ascii=False),
        synth_json=json.dumps(synth, ensure_ascii=False),
    )
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--transform", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    real, real_summary, real_dir = run_real(args.session, args.transform, args.out)
    synth, synth_summary, synth_dir = run_synth(args.session, args.transform, args.out)
    write_metrics(real, os.path.join(args.out, "metrics_real.csv"))
    write_metrics(synth, os.path.join(args.out, "metrics_synth.csv"))
    write_html(args.out, real, real_summary, synth, synth_summary)
    render_contact_sheet(real_dir, synth_dir, os.path.join(args.out, "contact_sheet.png"))
    summary = dict(
        session=args.session, transform=args.transform,
        real=real_summary, synthetic_capsule=synth_summary,
        note=("Real session has no fall. Synthetic capsule is an algorithm test, "
              "not a human capture and not evidence of bathroom performance."),
    )
    with open(os.path.join(args.out, "SUMMARY.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
