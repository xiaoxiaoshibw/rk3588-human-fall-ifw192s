"""Parse the ACTIVE spatial HTML payload and validate against the frozen
GL-I04 sidecar, without loading the 28MB/106MB files into chat context.
"""
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
HTML = RUN / "research_01" / "spatial_02" / "source_review.html"
I04 = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/12_real_final"


def main():
    out = {"script": "05_spatial_parse", "html": HTML.as_posix()}
    text = HTML.read_text(encoding="utf-8")
    m = re.search(r"const D=(\{.*?\});</script>", text, re.S)
    assert m, "payload marker not found"
    D = json.loads(m.group(1))

    diag = json.loads((I04 / "diagnostic.json").read_text(encoding="utf-8"))
    groups = diag["source_manifest"]["frame_groups"]
    draft = diag["approved_draft"]
    out["frame_count"] = len(D["frames"])
    out["bounds"] = list(D["bounds"].keys())
    out["stats_keys"] = len(D["stats"])
    out["record_keys"] = len(D["records"])
    out["jsonl_total_rows"] = D["jsonl_total_rows"]
    out["display_budget"] = D["display_budget"]

    # frames: seq/ordinal scalars, unique ordinals, matches diagnostic
    ords = [f["ordinal"] for f in D["frames"]]
    out["frames_ordinals_unique"] = len(set(ords)) == len(ords)
    out["frames_seq_int"] = all(type(f["seq"]) is int for f in D["frames"])
    out["frames_ordinal_int"] = all(type(f["ordinal"]) is int for f in D["frames"])
    out["frames_match_diag"] = sorted(ords) == sorted(g["ordinal"] for g in groups.values())
    out["frame_groups_match"] = all(
        groups[f["frame_group"]]["seq"] == f["seq"] for f in D["frames"])

    # bounds: four fixed boxes
    box_names = {"FIT"} | {r["region_id"] for r in draft["validation_regions"]}
    out["bounds_match_draft"] = set(out["bounds"]) == box_names

    # stats keys == 4 boxes x 89 frames
    exp_keys = {b + "\n" + f for b in box_names for f in groups}
    out["stats_keys_match"] = set(D["stats"]) == exp_keys
    out["record_keys_match_stats"] = set(D["records"]) == set(D["stats"])

    # stream the frozen sidecar and rebuild records
    expected = {k: [] for k in exp_keys}
    nlines = 0
    with (I04 / "source_indices.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            nlines += 1
            key = item["box"] + "\n" + item["frame_group"]
            xyz = item["source_xyz_m"]
            expected[key].append([item["pooled_row"], item["frame_row"], xyz])
    out["sidecar_lines"] = nlines
    out["sidecar_total_matches"] = nlines == D["jsonl_total_rows"]
    out["records_content_match"] = all(
        sorted(expected[k], key=lambda r: r[0]) ==
        sorted(D["records"][k], key=lambda r: r[0]) for k in exp_keys)
    out["records_order_match"] = all(
        expected[k] == D["records"][k] for k in exp_keys)
    out["stats_count_match"] = all(
        D["stats"][k]["count"] == len(D["records"][k]) for k in exp_keys)
    out["empty_selections"] = sum(1 for k in exp_keys if len(D["records"][k]) == 0)

    # xyz in bounds
    bad_xyz = 0
    for k in exp_keys:
        b = D["bounds"][k.split("\n")[0]]
        for r in D["records"][k]:
            if r[2] is None:
                continue
            if not all(b[a + "_min_m"] <= r[2][i] <= b[a + "_max_m"]
                       for i, a in enumerate("xyz")):
                bad_xyz += 1
    out["xyz_outside_box"] = bad_xyz

    # planes: origin trace, unit normal, physical false, approved up is prior
    planes = D["planes"]
    out["planes_count"] = len(planes)
    out["plane_names"] = list(planes)
    out["plane_origins"] = {k: v["origin"] for k, v in planes.items()}
    out["plane_norm_unit"] = all(
        abs(math.sqrt(sum(c * c for c in v["normal"])) - 1) < 1e-8 for v in planes.values())
    out["plane_physical_false"] = all(not v["physical_verified"] for v in planes.values())
    out["up_axis"] = D["up_axis"]
    out["up_axis_equals_draft_prior"] = D["up_axis"] == draft["up_axis"]
    out["approved_origin_is_prior_label"] = any(
        v["origin"] == "approved_prior_from_human_draft" for v in planes.values())
    out["recording_extrinsic"] = D["recording_extrinsic"]
    out["physical_verified"] = D["physical_verified"]

    (Path(__file__).resolve().parent / "05_spatial_parse.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("plane_origins",)}, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
