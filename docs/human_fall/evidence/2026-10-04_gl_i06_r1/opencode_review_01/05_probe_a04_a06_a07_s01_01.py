"""A04 gates/injection, A06 validation/freeze, A07 costs, S01 overwrite/AST."""
import ast
import hashlib
import json
import sys
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
OUT = RUN / "opencode_review_01"
REPO = RUN.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src/human_fall_detection"))
sys.path.insert(0, str(REPO / "docs/human_fall/evidence/2026-10-04_gl_i05_r2/research_01"))

import numpy as np  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    out = {}
    # ---- A04 injection (independent of author checks_05) ----
    from r0_01 import digest  # noqa
    from refinement_05 import bounded_refine, run_variant
    import r0_01
    from core import ground as g
    s = r0_01.settings(7)
    xy = np.random.RandomState(7).uniform(-3, 3, (250, 2))
    two = np.vstack([np.column_stack([xy, np.full(250, -1.4)]),
                     np.column_stack([xy, np.full(250, -1.54)])])
    ids = np.arange(500)
    a = dict(normal=[0., 0., 1.], offset_m=1.4, support_count=250, eigenvalue_ratio=1.)
    b = dict(normal=[0., 0., 1.], offset_m=1.54, support_count=250, eigenvalue_ratio=1.)
    inj_fails = []

    def injected(models):
        it = iter(models)
        return lambda *args: (next(it), "injected")

    # cycle: alternating member sets
    _, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 3,
                          dict(remaining=6000), injected([b, a, b]))
    if not (d["cycle"] and d["full_k"] and d["quality_gap"]):
        inj_fails.append(("cycle", d))
    # later height violation preserved last valid witness
    _, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 2,
                          dict(remaining=6000),
                          injected([a, dict(a, offset_m=3.0, normal=[0., 0., 1.])]))
    if not (d["violation"] == "later_round_height" and d["quality_gap"]):
        inj_fails.append(("later_height", d))
    # first round invalid: no last witness
    last, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 2,
                             dict(remaining=6000), injected([dict(a, offset_m=3.0)]))
    if not (d["violation"] == "first_round_height" and last is None):
        inj_fails.append(("first_invalid", d))
    # resource gap at k-1 remaining
    _, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 3,
                          dict(remaining=1))
    if not d["resource_gap"] or d["quality_gap"] is not True:
        inj_fails.append(("resource_gap", d))
    # real run: forced budget gap -> unresolved, no fallback closure
    cloud, rows, _ = r0_01.scene("high_noise", 7, False)
    sample, fit, itr = __import__("core.ground_diagnostics", fromlist=["replay_sequence"]).replay_sequence(
        cloud, rows, np.array([0., 0., 1.]), (.5, 2.), s)
    seq = list(itr)
    rg = run_variant(cloud, sample, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, 2, lo_budget=0)
    if rg["report"]["status"] != "unresolved" or not any(d["resource_gap"] for d in rg["details"]):
        inj_fails.append(("real_lo_gap", rg["report"]["status"]))
    # real numerical nonconvergence exists (members change) for K2/K3
    v2 = run_variant(cloud, sample, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, 2)
    if v2["refinement_counts"]["nonconverged"] == 0 or v2["report"]["status"] != "unresolved":
        inj_fails.append(("real_nonconverged", v2["refinement_counts"]))
    out["A04_injection"] = dict(fail_count=len(inj_fails), failures=inj_fails[:20],
                                real_nonconverged=v2["refinement_counts"]["nonconverged"],
                                real_W=len(v2["W"]))
    # ---- A06 development validation groups ----
    summary = json.loads((HERE / "r1_summary_02.json").read_text(encoding="utf-8"))
    vg_fails = []
    for row in summary["results"]:
        for v in row["variants"]:
            groups = [r["frame_group"] for r in v["validation"]]
            if len(groups) != 3 or len(set(groups)) != 3 or "fit" in groups:
                vg_fails.append((row["case"], groups))
            for r in v["validation"]:
                if "source_xyz_bounds" not in r:
                    vg_fails.append((row["case"], "no_bounds"))
    out["A06_validation_groups"] = dict(fail_count=len(vg_fails), failures=vg_fails[:20])
    # fixed source stability
    fs = json.loads((HERE / "fixed_source_summary_01.json").read_text(encoding="utf-8"))
    fs_fails = []
    for kind in ("clean", "low_noise", "high_noise", "wall"):
        group = [r for r in fs["results"] if r["kind"] == kind]
        if len({r["packet"]["source_sha"] for r in group}) != 1:
            fs_fails.append(("source_sha_differs", kind))
        if len({r["packet"]["seed"] for r in group}) != 3:
            fs_fails.append(("seeds", kind))
    out["A06_fixed_source"] = dict(fail_count=len(fs_fails), failures=fs_fails,
                                   stability_entries=len(fs["stability"]))
    # final holdout + freeze
    freeze = json.loads((HERE / "method_freeze_01.json").read_text(encoding="utf-8"))
    fh = json.loads((HERE / "final_holdout_summary_01.json").read_text(encoding="utf-8"))
    fh_fails = []
    if len(fh["results"]) != 30:
        fh_fails.append(("n_results", len(fh["results"])))
    if not (fh["first_exposure"] and fh["methods_frozen_before_exposure"]
            and fh["final_synthetic_not_real_physical"]):
        fh_fails.append(("flags",))
    fsha = digest(freeze)
    if fh["freeze_sha"] != fsha:
        fh_fails.append(("freeze_sha", fh["freeze_sha"], fsha))
    for name, exp in freeze["implementation_sha256"].items():
        actual = sha(HERE / name)
        if actual != exp:
            fh_fails.append(("impl_sha", name, actual, exp))
    final_files = sorted(HERE.glob("final_*_K*_01.json"))
    if len(final_files) != 90:
        fh_fails.append(("final_file_count", len(final_files)))
    for f in final_files:
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("freeze_sha") != fsha:
            fh_fails.append(("file_freeze_sha", f.name))
        if len(d["variant"]["W"]) == 0:
            fh_fails.append(("empty_W", f.name))
    out["A06_final_holdout"] = dict(fail_count=len(fh_fails), failures=fh_fails[:20],
                                    results=len(fh["results"]), final_files=len(final_files))
    # real approved zero eligible draws
    ra = json.loads((HERE / "r0_case_real_approved_01.json").read_text(encoding="utf-8"))
    rw = json.loads((HERE / "r0_case_real_historical_WHAT_IF_negative_X_01.json").read_text(encoding="utf-8"))
    out["A06_real"] = dict(real_approved_raw_counts=ra["raw_counts"],
                           real_approved_W=len(ra["W"]), real_approved_status=ra["scalar_full"]["status"],
                           whatif_raw_counts=rw["raw_counts"], whatif_W=len(rw["W"]),
                           whatif_synthetic=rw.get("synthetic"))
    # ---- A07 costs / memory ----
    cost_fails = []
    timings = {}
    for k in (1, 2, 3):
        t = json.loads((HERE / ("active_timing_K%d_01.json" % k)).read_text(encoding="utf-8"))
        timings[k] = t
        if len(t["costs"]) < 3:
            cost_fails.append(("repeat<3", k, len(t["costs"])))
        for c in t["costs"]:
            for stage in ("sampling", "raw", "LO", "refine", "decision", "serialization"):
                if stage not in c:
                    cost_fails.append(("missing_stage", k, stage))
    mem = {}
    for k in (1, 2, 3):
        m = json.loads((HERE / ("active_memory_K%d_01.json" % k)).read_text(encoding="utf-8"))
        mem[k] = m
        if "peak_working_set_bytes" not in m["after"] or "peak_private_commit_bytes" not in m["after"]:
            cost_fails.append(("mem_fields", k))
        if "separate process" not in m["after"]["method"]:
            cost_fails.append(("mem_method", k))
    out["A07"] = dict(fail_count=len(cost_fails), failures=cost_fails,
                      repeats=[len(timings[k]["costs"]) for k in (1, 2, 3)],
                      memory={k: dict(wset=mem[k]["after"]["peak_working_set_bytes"],
                                      commit=mem[k]["after"]["peak_private_commit_bytes"])
                              for k in (1, 2, 3)},
                      runtime_scope=timings[1]["runtime_scope"])
    # ---- S01 write_new overwrite refusal ----
    from r0_01 import write_new
    s01_fails = []
    existing = HERE / "check_exclusive_target_05.json"
    try:
        write_new(existing, {})
        s01_fails.append(("overwrite_allowed",))
    except ValueError:
        pass
    import tempfile
    try:
        write_new(REPO / "tmp_s01_forbidden.json", {})
        s01_fails.append(("outside_allowed",))
    except ValueError:
        pass
    # ---- Python 3.8 AST of every author script ----
    ast_fails = []
    scripts = list(RUN.rglob("*.py"))
    for p in scripts:
        try:
            ast.parse(p.read_text(encoding="utf-8"), feature_version=(3, 8))
        except SyntaxError as e:
            ast_fails.append((str(p), str(e)))
    out["S01"] = dict(fail_count=len(s01_fails) + len(ast_fails),
                      overwrite_fails=s01_fails, ast_fails=ast_fails[:20],
                      py_scripts=len(scripts))
    (OUT / "05_probe_a04_a06_a07_s01_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A04 fails", out["A04_injection"]["fail_count"],
          "| A06 vg", out["A06_validation_groups"]["fail_count"],
          "| A06 fs", out["A06_fixed_source"]["fail_count"],
          "| A06 fh", out["A06_final_holdout"]["fail_count"],
          "| A07", out["A07"]["fail_count"],
          "| S01", out["S01"]["fail_count"])
    print("real_approved:", out["A06_real"]["real_approved_raw_counts"],
          "W", out["A06_real"]["real_approved_W"], out["A06_real"]["real_approved_status"])
    print("whatif:", out["A06_real"]["whatif_raw_counts"], "W", out["A06_real"]["whatif_W"])
    for key in ("A04_injection", "A06_validation_groups", "A06_fixed_source",
                "A06_final_holdout", "A07", "S01"):
        for f in out[key]["failures"][:8]:
            print("  ", key, f)


if __name__ == "__main__":
    main()
