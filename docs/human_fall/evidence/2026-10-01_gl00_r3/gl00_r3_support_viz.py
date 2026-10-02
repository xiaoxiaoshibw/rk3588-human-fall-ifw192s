#!/usr/bin/env python3
"""GL-00 R3: support-point visualization + replayable indices (read-only).

Fits the dominant plane, builds the ground-local tangent basis, and writes:
  - a local SVG with a top-down (u,v) view and a side (u,height) view of the
    ground support points, the fit zone and the (spatial) validation zone;
  - a bounded CSV of support points carrying their original (frame seq,
    in-frame point index) and ground-local coordinates for replay.
This is a diagnostic visualization for the historical/current bring-up bag, not
a verified calibration, and the zones are spatial splits of one surface, not an
independent site validation. usage:
  python3 gl00_r3_support_viz.py BAG OUT_SVG OUT_CSV OUT_JSON
"""
import json
import sys

import numpy as np
import rosbag

TOPIC = "/innolidar_points"
DT = np.dtype({"names": ["x", "y", "z"],
               "formats": ["<f4", "<f4", "<f4"],
               "offsets": [0, 4, 8], "itemsize": 26})
STRIDE = 12
ITERS = 400
THRESH = 0.05
SEED = 20261001
FIT = (1.5, 3.0, 1.0)
VAL = (3.0, 5.0, 1.0)
CAP = 8000
SVG_CAP = 6000


def fit_plane(points, rng):
    best, best_count = None, -1
    n = len(points)
    for _ in range(ITERS):
        idx = rng.randint(0, n, 3)
        a, b, c = points[idx[0]], points[idx[1]], points[idx[2]]
        normal = np.cross(b - a, c - a)
        norm = float(np.linalg.norm(normal))
        if norm < 1e-9:
            continue
        normal = normal / norm
        offset = -float(normal @ a)
        count = int(np.count_nonzero(np.abs(points @ normal + offset) <= THRESH))
        if count > best_count:
            best_count, best = count, (normal, offset)
    normal, offset = best
    inl = points[np.abs(points @ normal + offset) <= THRESH]
    c = inl.mean(axis=0)
    _, _, vt = np.linalg.svd(inl - c, full_matrices=False)
    normal = vt[-1]
    offset = -float(normal @ c)
    if normal[2] < 0:
        normal, offset = -normal, -offset
    return normal, offset


def zone_mask(u, v):
    return (u >= FIT[0]) & (u <= VAL[1]) & (np.abs(v) <= FIT[2])


def main():
    bag, out_svg, out_csv, out_json = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    pool = []
    with rosbag.Bag(bag, "r") as b:
        for _, msg, _ in b.read_messages(topics=[TOPIC]):
            a = np.frombuffer(msg.data, dtype=DT)
            xyz = np.column_stack((a["x"], a["y"], a["z"]))
            valid = xyz[np.isfinite(xyz).all(axis=1) & (np.abs(xyz).sum(axis=1) > 0)]
            if len(valid):
                pool.append(valid[::STRIDE])
    pts = np.vstack(pool)
    normal, offset = fit_plane(pts, np.random.RandomState(SEED))
    tilt = float(np.arccos(np.clip(normal[2], -1.0, 1.0)))

    x_axis = np.array([1.0, 0.0, 0.0])
    u_axis = x_axis - (x_axis @ normal) * normal
    u_axis /= np.linalg.norm(u_axis)
    v_axis = np.cross(normal, u_axis)

    h = pts @ normal + offset
    support = np.abs(h) <= THRESH
    u = pts @ u_axis
    v = pts @ v_axis
    roi = zone_mask(u, v)
    fit_sel = roi & (u <= FIT[1])
    val_sel = roi & (u >= VAL[0])
    ground = pts[support]
    gu, gv, gh = u[support], v[support], h[support]

    def to_topdown(uu, vv, umin, umax, vmin, vmax, w, hgt, pad):
        sx = (uu - umin) / max(1e-9, (umax - umin)) * (w - 2 * pad) + pad
        sy = hgt - ((vv - vmin) / max(1e-9, (vmax - vmin)) * (hgt - 2 * pad) + pad)
        return sx, sy

    uall = np.concatenate([gu, u[fit_sel], u[val_sel]])
    vall = np.concatenate([gv, v[fit_sel], v[val_sel]])
    umin, umax = float(uall.min()), float(uall.max())
    vmin, vmax = float(vall.min()), float(vall.max())
    W, H, PAD = 520, 420, 30
    circles = []
    step = max(1, len(gu) // SVG_CAP)
    for i in range(0, len(gu), step):
        sx, sy = to_topdown(gu[i], gv[i], umin, umax, vmin, vmax, W, H, PAD)
        color = "#1a73e8" if fit_sel[np.nonzero(support)[0][i]] else (
            "#e8710a" if val_sel[np.nonzero(support)[0][i]] else "#9aa0a6")
        circles.append('<circle cx="%.1f" cy="%.1f" r="1.4" fill="%s"/>' % (sx, sy, color))

    def zone_rect(spec, color, label):
        u0, u1, half = spec
        x0, y1 = to_topdown(u0, -half, umin, umax, vmin, vmax, W, H, PAD)
        x1, y0 = to_topdown(u1, half, umin, umax, vmin, vmax, W, H, PAD)
        return ('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" '
                'stroke="%s" stroke-width="2"/><text x="%.1f" y="%.1f" fill="%s" '
                'font-size="12">%s</text>' % (x0, y0, x1 - x0, y1 - y0, color,
                                              x0 + 3, y0 + 14, color, label))

    rect_fit = zone_rect(FIT, "#1a73e8", "fit zone")
    rect_val = zone_rect(VAL, "#e8710a", "spatial holdout")

    # side view (u, h)
    side = []
    sw, sh, sp = 520, 200, 30
    hmin, hmax = -0.12, 0.12
    for i in range(0, len(gu), step):
        sx = (gu[i] - umin) / max(1e-9, (umax - umin)) * (sw - 2 * sp) + sp
        sy = sh - ((gh[i] - hmin) / (hmax - hmin) * (sh - 2 * sp) + sp)
        side.append('<circle cx="%.1f" cy="%.1f" r="1.4" fill="#9aa0a6"/>' % (sx, sy))
    zero_y = sh - ((0.0 - hmin) / (hmax - hmin) * (sh - 2 * sp) + sp)

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="470">'
           '<rect width="1080" height="470" fill="white"/>'
           '<text x="30" y="20" font-size="14">GL-00 ground support (top-down u-v; '
           'unit m) tilt=%.3f rad, sensor_height~%.3f m (unverified)</text>' %
           (tilt, float(offset)) +
           '<g>' + "".join(circles) + rect_fit + rect_val + '</g>'
           '<g transform="translate(540,240)">'
           '<text x="0" y="-215" font-size="14">side view (u, height h; unit m)</text>'
           '<line x1="0" y1="%.1f" x2="520" y2="%.1f" stroke="#1a73e8" '
           'stroke-width="1"/>' % (zero_y, zero_y) +
           "".join(side) + '</g></svg>')
    with open(out_svg, "w") as fh:
        fh.write(svg)

    export = []
    with rosbag.Bag(bag, "r") as b:
        for _, msg, _ in b.read_messages(topics=[TOPIC]):
            a = np.frombuffer(msg.data, dtype=DT)
            xyz = np.column_stack((a["x"], a["y"], a["z"]))
            uu = xyz @ u_axis
            vv = xyz @ v_axis
            hh = xyz @ normal + offset
            mask = (np.abs(hh) <= THRESH) & zone_mask(uu, vv)
            for i in np.nonzero(mask)[0]:
                if len(export) >= CAP:
                    break
                export.append((int(msg.header.seq), int(i), float(xyz[i, 0]),
                               float(xyz[i, 1]), float(xyz[i, 2]),
                               float(uu[i]), float(vv[i]), float(hh[i])))
            if len(export) >= CAP:
                break
    with open(out_csv, "w") as fh:
        fh.write("frame_seq,point_index,x_m,y_m,z_m,u_m,v_m,h_m\n")
        for row in export:
            fh.write("%d,%d,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n" % row)

    summary = {
        "bag": bag, "pool_count": int(len(pts)),
        "plane_normal_up": [float(x) for x in normal], "offset_m": float(offset),
        "tilt_from_source_z_rad": tilt, "support_fraction": float(support.mean()),
        "fit_zone_points": int(fit_sel.sum()), "spatial_holdout_points": int(val_sel.sum()),
        "ground_u_range_m": [float(gu.min()), float(gu.max())],
        "ground_v_range_m": [float(gv.min()), float(gv.max())],
        "ground_height_rms_m": float(np.sqrt(np.mean(gh ** 2))),
        "export_count": len(export), "export_capped": len(export) >= CAP,
        "note": "single-surface spatial split only; NOT independent site validation",
    }
    with open(out_json, "w") as fh:
        json.dump(summary, fh, indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
