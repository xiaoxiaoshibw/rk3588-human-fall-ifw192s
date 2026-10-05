"""GL-E01 R1 independent hand fixtures for layout, endian, padding and policy.

No project import. Builds synthetic serialized PointCloud2 records and checks
offset/datatype/endian/padding interpretations, rejects mismatched headers/alias,
and quantifies the float64->float32 timestamp loss including the theoretical
half-ULP at raw values ~183460.
"""
import hashlib
import json
import struct
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent

FIELDS = [("x", 0, "<f4"), ("y", 4, "<f4"), ("z", 8, "<f4"),
          ("intensity", 12, "<f4"), ("ring", 16, "<u2"), ("timestamp", 18, "<f8")]


def parse_record(data, n, point_step=26, fields=FIELDS):
    a = np.frombuffer(data, dtype=np.uint8).reshape(n, point_step)
    out = {}
    for name, off, dt in fields:
        width = np.dtype(dt).itemsize
        out[name] = a[:, off:off + width].copy().view(dt).reshape(-1)
    return out


def canonical_from_raw(raw_rows):
    keep = np.isfinite(raw_rows["x"]) & np.isfinite(raw_rows["y"]) & np.isfinite(raw_rows["z"])
    src = np.zeros((len(raw_rows["x"]), 26), dtype=np.uint8)
    for name, off, dt in FIELDS:
        width = np.dtype(dt).itemsize
        src[:, off:off + width] = raw_rows[name].view(np.uint8).reshape(-1, width)
    kept = src[keep]
    canon = np.zeros((len(kept), 28), dtype=np.uint8)
    canon[:, 0:18] = kept[:, 0:18]
    canon[:, 20:24] = kept[:, 18:26].view("<f8").reshape(-1).astype("<f4").view(np.uint8).reshape(-1, 4)
    return canon


def compare_frames(meta, bag, manifest):
    """Reimplementation of the frozen policy: header ints exact, bag_time round-6."""
    if not (len(meta) == len(bag) == len(manifest)):
        raise ValueError("frame_count")
    for ordinal, (m, b, a) in enumerate(zip(meta, bag, manifest)):
        if b["ordinal"] != ordinal or a["ordinal"] != ordinal:
            raise ValueError("ordinal")
        for key in ("seq", "stamp_sec", "stamp_nanosec", "offset_points",
                    "count_points", "dropped_points"):
            if not m[key] == b[key] == a[key]:
                raise ValueError(key)
        if not m["bag_time_sec"] == round(b["bag_time_sec"], 6) == a["bag_time_sec"]:
            raise ValueError("bag_time_sec")
    return True


def main():
    checks = []
    x = np.array([1.5, -2.25], dtype="<f4")
    y = np.array([3.0, 4.5], dtype="<f4")
    z = np.array([-5.0, 6.25], dtype="<f4")
    inten = np.array([7.0, 8.0], dtype="<f4")
    ring = np.array([3, 65535], dtype="<u2")
    ts = np.array([183460.002503, 183462.492189], dtype="<f8")
    data = b"".join(struct.pack("<ffffHd", x[i], y[i], z[i], inten[i], ring[i], ts[i])
                    for i in range(2))
    checks.append(dict(name="hand_serialized_len_52", value=len(data), expect=52,
                       ok=len(data) == 52))
    parsed = parse_record(data, 2)
    checks.append(dict(name="offset_datatype_roundtrip",
                       ok=bool(np.array_equal(parsed["x"], x)
                               and np.array_equal(parsed["ring"], ring)
                               and np.array_equal(parsed["timestamp"], ts))))
    # Little-endian proof: manual byte order of x=1.5 -> 00 00 c0 3f
    checks.append(dict(name="little_endian_bytes",
                       ok=list(data[0:4]) == [0x00, 0x00, 0xC0, 0x3F]))
    # Big-endian interpretation differs (refused reading would be wrong values).
    be = np.frombuffer(data[0:4], dtype=">f4")[0]
    checks.append(dict(name="big_endian_differs", ok=float(be) != 1.5, value=float(be)))
    # Wrong offset/datatype spec must not reproduce values.
    wrong = FIELDS[:1] + [("y", 0, "<f4")] + FIELDS[2:]
    wp = parse_record(data, 2, fields=wrong)
    checks.append(dict(name="wrong_offset_detected",
                       ok=not np.array_equal(wp["y"], y)))

    canon = canonical_from_raw(parsed)
    checks.append(dict(name="canonical_28_stride", ok=canon.shape == (2, 28)))
    pad = np.isin(np.arange(28), [18, 19, 24, 25, 26, 27])
    checks.append(dict(name="canonical_pads_zero", ok=bool(not canon[:, pad].any())))
    checks.append(dict(name="canonical_xyz_preserved",
                       ok=bool(np.array_equal(canon[:, 0:12].view("<f4").reshape(2, 3),
                                              np.column_stack([x, y, z])))))
    checks.append(dict(name="canonical_timestamp_is_f32",
                       ok=bool(np.array_equal(canon[:, 20:24].copy().view("<f4").reshape(-1),
                                              ts.astype("<f4")))))

    # Same count, different content -> different hash.
    a = np.array([[1.0, 2.0, 3.0]], dtype="<f4")
    b = a.copy()
    b[0, 2] += 1.0
    checks.append(dict(name="same_count_diff_content_hash",
                       ok=hashlib.sha256(a.tobytes()).hexdigest() != hashlib.sha256(b.tobytes()).hexdigest()))

    # Header/identity mismatches rejected by the frozen policy.
    base = dict(seq=1, stamp_sec=183460, stamp_nanosec=2503000, offset_points=0,
                count_points=2, dropped_points=0, bag_time_sec=1790930182.177557,
                ordinal=0)
    raw_bag = dict(base, bag_time_sec=1790930182.1775574)
    adapted = dict(base)
    ok_base = compare_frames([base], [raw_bag], [adapted])
    checks.append(dict(name="round6_policy_accepts", ok=ok_base))
    rejects = {}
    for name, field, val in [("foreign_seq", "seq", 2),
                             ("wrong_nsec", "stamp_nanosec", 2503001),
                             ("wrong_offset", "offset_points", 1),
                             ("wrong_count", "count_points", 3),
                             ("lost_point", "dropped_points", 1),
                             ("bag_time_beyond_6dp_diff", "bag_time_sec", 1790930183.177557),
                             ("ordinal_alias", "ordinal", 1)]:
        bad = dict(raw_bag, **{field: val})
        try:
            compare_frames([base], [bad], [adapted])
            rejects[name] = False
        except ValueError:
            rejects[name] = True
    checks.append(dict(name="header_alias_content_rejected", ok=all(rejects.values()),
                       detail=rejects))

    # Timestamp quantization: observed max and theoretical half-ULP.
    for v in (183460.007811, 183462.492189):
        err = abs(float(np.float64(v)) - float(np.float32(v)))
        half_ulp = float(np.spacing(np.float32(v)) / 2 if hasattr(np, "spacing")
                         else 2 ** (np.floor(np.log2(v)) - 23) / 2)
        checks.append(dict(name="timestamp_loss_counterexample", value=v,
                           numeric_error=err, half_ulp=half_ulp,
                           error_gt_0p001=err > 0.001,
                           error_le_half_ulp=err <= half_ulp * 1.0000001,
                           claimed_below_0p1us=err < 1e-7))
    header_exact = [183460, 2503000]
    checks.append(dict(name="header_ints_stay_exact",
                       ok=(base["stamp_sec"] == header_exact[0]
                           and base["stamp_nanosec"] == header_exact[1])))

    result = dict(kind="gle01_r1_independent_fixtures", schema=1, checks=checks,
                  all_pass=all(c.get("ok", c.get("error_gt_0p001", False))
                               for c in checks),
                  timestamp_units_verified=False)
    # explicitly require the counterexamples to prove loss and refute <0.1us
    assert all(c["ok"] for c in checks if "ok" in c)
    assert all((c["error_gt_0p001"] and not c["claimed_below_0p1us"])
               for c in checks if c["name"] == "timestamp_loss_counterexample")
    (OUT / "04_fixture_checks.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(checks=len(checks), all_ok=True,
                          losses=[(c["value"], c["numeric_error"])
                                  for c in checks if c["name"] == "timestamp_loss_counterexample"])))


if __name__ == "__main__":
    main()
