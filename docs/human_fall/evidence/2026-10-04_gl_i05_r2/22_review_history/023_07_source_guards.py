"""Independent adversarial probe of source_review payload schema guards and
exclusive output. Uses safe pure fixture calls; writes nothing into author dirs.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
RES = RUN / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(RES)]

import copy
from source_review import build_payload, write_payload, _render


def base_diag():
    bounds = {a + "_" + s + "_m": v for a in "xyz"
              for s, v in [("min", -2.0), ("max", 2.0)]}
    return dict(schema=1, kind="gli04_geometry_diagnostic", frame="source", units="m",
                source_manifest=dict(schema=1, kind="capture_input_adaptation",
                                     declared=dict(frame="source", units="m"),
                                     frame_groups={"g": dict(ordinal=0, seq=123, rows=[0, 2])}),
                approved_draft=dict(up_axis=[0., 0., 1.], fit_region=dict(bounds=bounds),
                                    validation_regions=[dict(region_id="v" + str(i), bounds=bounds)
                                                        for i in (1, 2, 3)]),
                box_frame_records=[dict(box=b, frame_group="g", frame_ordinal=0, seq=123,
                                        stats=dict(count=int(b == "FIT")))
                                   for b in ("FIT", "v1", "v2", "v3")],
                experiments=[dict(label="approved",
                                  posthoc_plane=dict(normal=[0., 0., 1.], offset_m=1.,
                                                     origin="posthoc_PCA_all_approved_FIT_rows_not_physical"))])


def row():
    return dict(box="FIT", frame_group="g", pooled_row=0, frame_row=0, frame_ordinal=0,
                seq=123, source_xyz_m=[0., 0., -1.])


def rejects(fn):
    try:
        fn()
    except (ValueError, TypeError, KeyError):
        return True
    return False


def main():
    out = {"script": "07_source_guards", "checks": {}}
    d = base_diag()
    good = build_payload(d, [row()])
    out["checks"]["valid_build_ok"] = good["kind"] == "gli05_source_review" \
        and good["jsonl_total_rows"] == 1 and len(good["stats"]) == 4
    out["checks"]["empty_selection_kept"] = good["stats"]["v1\ng"]["count"] == 0
    # display budget does not change records/stats
    a = build_payload(d, [row()], 0)
    b = build_payload(d, [row()], 100)
    out["checks"]["display_budget_no_effect_on_data"] = a["records"] == b["records"] and a["stats"] == b["stats"]

    cases = {}
    cases["bad_schema"] = lambda: build_payload(dict(d, schema=2), [row()])
    cases["bad_kind"] = lambda: build_payload(dict(d, kind="x"), [row()])
    cases["bad_units"] = lambda: build_payload(dict(d, units="cm"), [row()])
    cases["frame_mismatch"] = lambda: build_payload(
        dict(d, source_manifest=dict(d["source_manifest"], declared=dict(frame="other", units="m"))), [row()])
    alias = copy.deepcopy(d)
    alias["source_manifest"]["frame_groups"]["alias"] = copy.deepcopy(d["source_manifest"]["frame_groups"]["g"])
    cases["alias_group"] = lambda: build_payload(alias, [row()])
    cases["duplicate_row"] = lambda: build_payload(d, [row(), row()])
    foreign = row(); foreign["box"] = "zzz"
    cases["foreign_box"] = lambda: build_payload(d, [foreign])
    poor = row(); poor["pooled_row"] = 5
    cases["row_outside_group"] = lambda: build_payload(d, [poor])
    bad_frame = row(); bad_frame["seq"] = 999
    cases["bad_seq"] = lambda: build_payload(d, [bad_frame])
    bad_xyz = row(); bad_xyz["source_xyz_m"] = [float("nan"), 0., 0.]
    cases["nonfinite_xyz"] = lambda: build_payload(d, [bad_xyz])
    outside = row(); outside["source_xyz_m"] = [9., 0., 0.]
    cases["xyz_outside_box"] = lambda: build_payload(d, [outside])
    missing = copy.deepcopy(d); missing["box_frame_records"].pop()
    cases["missing_stats"] = lambda: build_payload(missing, [row()])
    dupkey = copy.deepcopy(d); dupkey["box_frame_records"].append(copy.deepcopy(dupkey["box_frame_records"][0]))
    cases["duplicate_stats_key"] = lambda: build_payload(dupkey, [row()])
    cases["bad_display_budget"] = lambda: build_payload(d, [row()], 2001)
    for name, fn in cases.items():
        out["checks"]["reject_" + name] = rejects(fn)

    # exclusive output: existing dir (author's active page) and outside research_01
    out["checks"]["reject_existing_output"] = rejects(
        lambda: write_payload(good, RES / "spatial_02"))
    out["checks"]["reject_outside_root"] = rejects(
        lambda: write_payload(good, Path(__file__).resolve().parent / "fresh_output"))

    html = _render(good)
    out["checks"]["render_has_interactions"] = all(
        token in html for token in ("C.onclick", "residual(r)", "physical_verified:false",
                                    "pooled row", "显示预算不改变全统计"))
    out["checks"]["failed_wip_empty_retained"] = (
        RES / "spatial_01" / "source_review.html").stat().st_size == 0
    out["all_ok"] = all(out["checks"].values())

    (Path(__file__).resolve().parent / "07_source_guards.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"all_ok": out["all_ok"], "checks": out["checks"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
