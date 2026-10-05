"""Independently confirm the page's selected-plane residual formula against the
frozen GL-I04 sidecar stored `signed_residual_m` (FIT PCA plane).

The page JS computes residual = sum(xyz_i * normal_i) + offset_m. If that is
the frozen convention, then recomputing it with the FIT-PCA plane must equal
every sidecar `signed_residual_m` for that plane.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
I04 = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final"


def main():
    diag = json.loads((I04 / "diagnostic.json").read_text(encoding="utf-8"))
    exp = [e for e in diag["experiments"] if e["label"] == "WHAT_IF_FIT_PCA_normal"][0]
    n = exp["posthoc_plane"]["normal"]
    off = exp["posthoc_plane"]["offset_m"]
    n_match = off_match = 0
    n_lines = 0
    max_abs = 0.0
    with (I04 / "source_indices.jsonl").open(encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            xyz = r["source_xyz_m"]
            stored = r["signed_residual_m"]
            if xyz is None or stored is None:
                continue
            n_lines += 1
            calc = sum(a * b for a, b in zip(xyz, n)) + off
            d = abs(calc - stored)
            max_abs = max(max_abs, d)
            if d < 1e-9:
                n_match += 1
            else:
                off_match += 1
    out = {"script": "05b_spatial_residual", "lines_checked": n_lines,
           "exact_matches": n_match, "mismatches": off_match,
           "max_abs_diff": max_abs,
           "plane": "WHAT_IF_FIT_PCA_normal",
           "convention_confirmed": off_match == 0 and n_lines > 0}
    (Path(__file__).resolve().parent / "05b_spatial_residual.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
