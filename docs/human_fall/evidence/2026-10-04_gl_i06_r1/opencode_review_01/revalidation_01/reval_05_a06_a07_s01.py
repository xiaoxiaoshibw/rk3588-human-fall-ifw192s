"""Revalidation step 5: A06 validation/freeze, A07 costs/memory, S01 write/AST.

NEW output 05_a06_a07_s01_01.json.
"""
import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
REVAL = RUN / "opencode_review_01/revalidation_01"
REPO = RUN.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src/human_fall_detection"))
sys.path.insert(0, str(REPO / "docs/human_fall/evidence/2026-10-04_gl_i05_r2/research_01"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def mtime_utc(p):
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def main():
    import r0_01
    from r0_01 import digest
    out = {}
    # ---- A06 dev validation groups ----
    summary = json.loads((HERE / "r1_summary_02.json").read_text(encoding="utf-8"))
    vg_fail, scanned, skipped = [], 0, 0
    for row in summary["results"]:
        for v in row["variants"]:
            if not v["validation"]:
                skipped += 1
                continue
            scanned += 1
            groups = [r["frame_group"] for r in v["validation"]]
            if len(groups) != 3 or len(set(groups)) != 3 or "fit" in groups:
                vg_fail.append((row["case"], groups))
            for r in v["validation"]:
                if "source_xyz_bounds" not in r:
                    vg_fail.append((row["case"], "no_bounds"))
    # real region full-row sizes
    real_rows = {}
    for row in summary["results"]:
        if row["case"].startswith("real") and row["variants"][0]["validation"]:
            real_rows[row["case"]] = [r["stats"]["count"] for r in row["variants"][0]["validation"]]
    # region geometry
    geo_fail = []
    for kind in ("clean", "high_noise", "table"):
        pts, fit_rows, regions = r0_01.scene(kind, 7, False)
        idx = [i for r in regions for i in r["indices"]]
        if set(idx) & set(fit_rows.tolist()):
            geo_fail.append(("overlap", kind))
        if sorted(idx) != list(range(len(fit_rows), len(fit_rows) + 240)):
            geo_fail.append(("coverage", kind, len(idx)))
        for r in regions:
            if len(r["indices"]) != 80:
                geo_fail.append(("region_size", kind, len(r["indices"])))
    out["A06_validation"] = dict(scanned=scanned, skipped_empty_W=skipped,
                                 fail_count=len(vg_fail), failures=vg_fail[:40],
                                 real_region_row_counts=real_rows)
    out["A06_region_geometry"] = dict(fail_count=len(geo_fail), failures=geo_fail)
    # ---- A06 fixed source + final holdout + freeze ----
    fs = json.loads((HERE / "fixed_source_summary_01.json").read_text(encoding="utf-8"))
    fs_fail = []
    for kind in ("clean", "low_noise", "high_noise", "wall"):
        g = [r for r in fs["results"] if r["kind"] == kind]
        if len({r["packet"]["source_sha"] for r in g}) != 1 or len({r["packet"]["seed"] for r in g}) != 3:
            fs_fail.append(kind)
    freeze = json.loads((HERE / "method_freeze_01.json").read_text(encoding="utf-8"))
    fh = json.loads((HERE / "final_holdout_summary_01.json").read_text(encoding="utf-8"))
    fsha = digest(freeze)
    fh_fail = []
    if len(fh["results"]) != 30:
        fh_fail.append(("n", len(fh["results"])))
    if not (fh["first_exposure"] and fh["methods_frozen_before_exposure"]
            and fh["final_synthetic_not_real_physical"]):
        fh_fail.append(("flags",))
    if fh["freeze_sha"] != fsha:
        fh_fail.append(("freeze_sha",))
    for name, exp in freeze["implementation_sha256"].items():
        if sha(HERE / name) != exp:
            fh_fail.append(("impl_sha", name))
    final_files = sorted(HERE.glob("final_*_K*_01.json"))
    if len(final_files) != 90:
        fh_fail.append(("file_count", len(final_files)))
    for f in final_files:
        if json.loads(f.read_text(encoding="utf-8")).get("freeze_sha") != fsha:
            fh_fail.append(("file_freeze_sha", f.name))
    kinds = sorted({r["case"].rsplit("_", 1)[0][len("final_"):] for r in fh["results"]})
    seeds = sorted({int(r["case"].rsplit("_", 1)[1]) for r in fh["results"]})
    freeze_m = mtime_utc(HERE / "method_freeze_01.json")
    first_final = min(mtime_utc(p) for p in final_files)
    out["A06_fixed_source"] = dict(fail_count=len(fs_fail), failures=fs_fail)
    out["A06_final_holdout"] = dict(fail_count=len(fh_fail), failures=fh_fail[:20],
                                    results=len(fh["results"]), final_files=len(final_files),
                                    kinds=kinds, seeds=seeds,
                                    freeze_before_first_final=freeze_m <= first_final,
                                    freeze_mtime=freeze_m, first_final_mtime=first_final)
    ra = json.loads((HERE / "r0_case_real_approved_01.json").read_text(encoding="utf-8"))
    rw = json.loads((HERE / "r0_case_real_historical_WHAT_IF_negative_X_01.json").read_text(encoding="utf-8"))
    out["A06_real"] = dict(approved_raw=ra["raw_counts"], approved_W=len(ra["W"]),
                           whatif_raw=rw["raw_counts"], whatif_W=len(rw["W"]),
                           whatif_synthetic=rw.get("synthetic"))
    # ---- A07 costs/memory ----
    cost_fail, timings, mem = [], {}, {}
    for k in (1, 2, 3):
        t = json.loads((HERE / ("active_timing_K%d_01.json" % k)).read_text(encoding="utf-8"))
        timings[k] = t
        if len(t["costs"]) < 3:
            cost_fail.append(("repeat", k, len(t["costs"])))
        for c in t["costs"]:
            for stage in ("sampling", "raw", "LO", "refine", "decision", "serialization"):
                if stage not in c:
                    cost_fail.append(("stage", k, stage))
        m = json.loads((HERE / ("active_memory_K%d_01.json" % k)).read_text(encoding="utf-8"))
        mem[k] = m
        if "peak_working_set_bytes" not in m["after"] or "separate process" not in m["after"]["method"]:
            cost_fail.append(("mem", k))
    out["A07"] = dict(fail_count=len(cost_fail), failures=cost_fail,
                      repeats=[len(timings[k]["costs"]) for k in (1, 2, 3)],
                      memory={k: [mem[k]["after"]["peak_working_set_bytes"],
                                  mem[k]["after"]["peak_private_commit_bytes"]] for k in (1, 2, 3)},
                      runtime_scope=timings[1]["runtime_scope"])
    # ---- S01 write refusal + AST 3.8 ----
    from r0_01 import write_new
    s01_fail = []
    existing = HERE / "check_exclusive_target_05.json"
    try:
        write_new(existing, {})
        s01_fail.append("overwrite_allowed")
    except ValueError:
        pass
    try:
        write_new(REPO / "tmp_s01_forbidden.json", {})
        s01_fail.append("outside_allowed")
    except ValueError:
        pass
    ast_fail = []
    scripts = list(RUN.rglob("*.py"))
    for p in scripts:
        try:
            ast.parse(p.read_text(encoding="utf-8"), feature_version=(3, 8))
        except SyntaxError as e:
            ast_fail.append((str(p), str(e)))
    out["S01"] = dict(write_fail=s01_fail, ast_fail=ast_fail[:20], py_scripts=len(scripts),
                      fail_count=len(s01_fail) + len(ast_fail))
    target = REVAL / "05_a06_a07_s01_01.json"
    if target.exists():
        raise SystemExit("refuse to overwrite " + str(target))
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A06 vg", out["A06_validation"]["fail_count"], "scanned", scanned, "skipped", skipped,
          "geo", out["A06_region_geometry"]["fail_count"], "fs", out["A06_fixed_source"]["fail_count"],
          "fh", out["A06_final_holdout"]["fail_count"], "A07", out["A07"]["fail_count"],
          "S01", out["S01"]["fail_count"])
    print("real region rows", real_rows)
    print("freeze_before_first_final", out["A06_final_holdout"]["freeze_before_first_final"])


if __name__ == "__main__":
    main()
