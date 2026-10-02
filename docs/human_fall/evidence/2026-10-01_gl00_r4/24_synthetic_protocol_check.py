#!/usr/bin/env python3
"""GL-00 R4 self-check for the synthetic protocol definition.

Validates the protocol JSON is internally consistent and that its validation
gate is a real, failable check: a clean synthetic plane passes the numeric gate
and a shifted plane fails it. Pure NumPy; no production import. Run:
  python3 24_synthetic_protocol_check.py [path/to/24_synthetic_protocol.json]
Exit code 0 only if every check passes.
"""
import json
import math
import os
import sys

import numpy as np


def check(name, condition):
    print(("PASS " if condition else "FAIL ") + name)
    if not condition:
        raise SystemExit(1)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "24_synthetic_protocol.json")
    with open(path) as fh:
        p = json.load(fh)

    cp = p["constrained_path_parameters"]
    table = p["ransac_budget_ceil_table"]

    # 1. ceil table matches the formula
    for p_key, w_key, expect in [("p0.99", "0.20", 574), ("p0.999", "0.20", 861),
                                 ("p0.999", "0.30", 253), ("p0.999", "0.50", 52)]:
        assert table[p_key][w_key] == expect, (p_key, w_key)
    ok = True
    for p_key, pv in [("p0.99", 0.99), ("p0.999", 0.999)]:
        for w_key, wv in [(k, float(k)) for k in table[p_key]]:
            ok = ok and table[p_key][w_key] == math.ceil(
                math.log(1 - pv) / math.log(1 - wv ** 3))
    check("ceil budget table matches formula", ok)

    # 2. selected iteration count and hard cap
    check("ransac_iterations == ceil(p=.999,w=.20)",
          cp["ransac_iterations"] == math.ceil(math.log(1 - 0.999) / math.log(1 - 0.20 ** 3)))
    check("hard cap >= iterations", cp["ransac_iteration_hard_cap"] >= cp["ransac_iterations"])

    # 3. thresholds ordering and counts
    g = p["known_ground_validation_gate"]
    check("untruncated rms <= p95", g["untruncated_rms_max_m"] <= g["abs_residual_p95_max_m"])
    check("fit cap <= holdout cap", cp["fit_point_cap"] <= cp["holdout_point_cap"])
    check("at least 3 validation regions", g["independent_regions_min"] >= 3)
    check(">=20 points per region", g["points_per_region_min"] >= 20)
    check("support fraction in (0,1]", 0.0 < g["support_fraction_min"] <= 1.0)
    check("candidate cap between 1 and 3", 1 <= cp["max_candidates"] <= 3)

    # 4. gate is failable: clean plane passes, shifted plane fails
    rng = np.random.RandomState(cp["seed"])
    tilt = math.radians(25.0)
    normal = np.array([math.sin(tilt), 0.0, math.cos(tilt)])
    height = cp["sensor_height_interval_m"] if isinstance(
        cp["sensor_height_interval_m"], list) else [1.0, 1.6]
    h0 = 0.5 * (height[0] + height[1])
    sigma = 0.02
    threshold = cp["inlier_threshold_m"]

    def region(center_u, n):
        u = rng.uniform(-0.4, 0.4, n) + center_u
        v = rng.uniform(-0.4, 0.4, n)
        noise = rng.normal(0.0, sigma, n)
        pts = np.column_stack((u, v, np.zeros(n)))
        # rotate the (u,v,0) patch onto the tilted plane at distance h0
        x_axis = np.array([1.0, 0.0, 0.0])
        u_ax = x_axis - (x_axis @ normal) * normal
        u_ax /= np.linalg.norm(u_ax)
        v_ax = np.cross(normal, u_ax)
        pts = pts[:, :1] * u_ax + pts[:, 1:2] * v_ax + (-h0 * normal)
        return pts + noise[:, None] * normal

    regions = [region(c, 200) for c in (-1.0, 0.0, 1.0)]
    allpts = np.vstack(regions)
    resid = np.abs(allpts @ normal + h0)
    rms = float(np.sqrt(np.mean(resid ** 2)))
    p95 = float(np.percentile(resid, 95))
    support = float(np.mean(resid <= threshold))
    check("clean plane passes gate",
          rms <= g["untruncated_rms_max_m"] and p95 <= g["abs_residual_p95_max_m"]
          and support >= g["support_fraction_min"])

    shifted = allpts + 0.1 * normal
    resid_s = np.abs(shifted @ normal + h0)
    check("shifted plane fails gate",
          float(np.mean(resid_s <= threshold)) < g["support_fraction_min"])

    # 5. proposed degeneracy/ambiguity criteria present and sane
    d = p["degeneracy_criteria_proposed"]
    a = p["ambiguity_criteria_proposed"]
    check("degeneracy criteria present",
          d["min_sample_separation_m"] > 0 and d["min_sample_triangle_area_m2"] > 0
          and 0 < d["min_planar_eigenvalue_ratio"] < 1)
    check("ambiguity criteria present",
          0 < a["support_close_ratio"] <= 1 and a["distinct_normal_deg"] > 0)

    print("ALL_CHECKS_PASSED")


if __name__ == "__main__":
    main()
