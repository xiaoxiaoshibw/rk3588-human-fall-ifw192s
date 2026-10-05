"""A02 count identities, A03/A05 full-W max + false-closure across all K, J/coverage."""
import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
OUT = RUN / "opencode_review_01"
REPO = RUN.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src/human_fall_detection"))

import numpy as np  # noqa: E402


def my_oracle(w, ratio, deg, off, gaps):
    n = len(w)
    if n:
        sup = [p["support_count"] for p in w]
        best = max(sup)
        near = [i for i in range(n) if sup[i] >= ratio * best]
        top = [i for i in range(n) if sup[i] == best]
    else:
        best, near, top = None, [], []
    near_s, top_s = set(near), set(top)

    def distinct(i, j):
        dot = sum(a * b for a, b in zip(w[i]["normal"], w[j]["normal"]))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        return ang > deg or abs(w[i]["offset_m"] - w[j]["offset_m"]) > off

    allp, nearp, bestp = [], [], []
    for i, j in itertools.combinations(range(n), 2):
        if distinct(i, j):
            allp.append([i, j])
            if i in near_s and j in near_s:
                nearp.append([i, j])
                if i in top_s or j in top_s:
                    bestp.append([i, j])
    if gaps or not w or nearp:
        status = "unresolved"
    elif not allp:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"
    return dict(status=status, best=best, allp=allp, nearp=nearp)


def main():
    summary = json.loads((HERE / "r1_summary_02.json").read_text(encoding="utf-8"))
    fails = []
    count_records = []
    for row in summary["results"]:
        for k, v in zip((1, 2, 3), row["variants"]):
            c = v["I05_counts"]
            # A02 identities
            if c["qualified"] != c["refined_calls"] + c["unprocessed"]:
                fails.append(("qualified_identity", row["case"], k))
            if c["produced"] != c["retained"] + c["merged_exact"] + c["unstored"]:
                fails.append(("produced_identity", row["case"], k))
            if c["refined_calls"] != c["produced"] + c["rejected"]:
                fails.append(("refined_identity", row["case"], k))
            count_records.append(dict(case=row["case"], k=k, **c))
    # full-W oracle / max / no-false-closure across every K ledger
    ledger_fails = []
    checked = 0
    W_by_case = {}
    for f in sorted(HERE.glob("r1_case_*_K*_02.json")):
        name = f.name[len("r1_case_"):]
        case = name.split("_K")[0]
        k = int(name.split("_K")[1].split("_")[0])
        item = json.loads(f.read_text(encoding="utf-8"))
        v = item["variant"]
        setting = json.loads((HERE / ("r0_case_%s_01.json" % case)).read_text(encoding="utf-8"))["settings"]
        ratio = setting["support_close_ratio"]
        deg = setting["distinct_normal_deg"]
        off = setting["distinct_offset_m"]
        gaps = v["report"]["gaps_input"]
        w = v["W"]
        best_w = max((p["support_count"] for p in w), default=None)
        if v["report"]["best_support"] != best_w:
            ledger_fails.append(("best_not_max", case, k, v["report"]["best_support"], best_w))
        o = my_oracle(w, ratio, deg, off, gaps)
        if o["status"] != v["report"]["status"]:
            ledger_fails.append(("status", case, k, o["status"], v["report"]["status"]))
        if o["best"] != v["report"]["best_support"]:
            ledger_fails.append(("best", case, k))
        if v["report"]["metrics"]["ALL"]["holds"] != (not o["allp"]):
            ledger_fails.append(("ALL", case, k))
        if v["report"]["metrics"]["NEAR"]["holds"] != (not o["nearp"]):
            ledger_fails.append(("NEAR", case, k))
        if v["report"]["metrics"]["ALL"]["distinct_pairs"] != o["allp"]:
            ledger_fails.append(("ALL_pairs", case, k))
        if v["report"]["metrics"]["NEAR"]["distinct_pairs"] != o["nearp"]:
            ledger_fails.append(("NEAR_pairs", case, k))
        # false closure: closed status must mean NEAR holds (no distinct competitor)
        if v["report"]["status"] != "unresolved" and o["nearp"]:
            ledger_fails.append(("false_closure", case, k))
        # gaps must force unresolved
        if gaps and v["report"]["status"] != "unresolved":
            ledger_fails.append(("gap_not_unresolved", case, k))
        # stored-subset domain distinct from full when budget truncated
        ssd = v["report"].get("stored_subset_diagnostics", {})
        wits = v["report"]["witnesses"]
        ow = my_oracle(wits, ratio, deg, off, gaps)
        if ssd.get("best_support") != ow["best"]:
            ledger_fails.append(("stored_best", case, k))
        # W changes with K: capture a local content hash per case
        W_by_case.setdefault(case, {})[k] = hashlib.sha256(
            json.dumps(w, sort_keys=True).encode()).hexdigest()
        checked += 1
    # cross-K W domain change
    wdiff = {case: d for case, d in W_by_case.items()
             if len(set(x for x in d.values() if x)) > 1}
    # J / coverage independent recompute on one witness
    import r0_01
    from r0_01 import quality, scene
    jcase = "high_noise_7_False"
    item = json.loads((HERE / ("r1_case_%s_K1_02.json" % jcase)).read_text(encoding="utf-8"))
    setting = json.loads((HERE / ("r0_case_%s_01.json" % jcase)).read_text(encoding="utf-8"))["settings"]
    kind, seed, perm = jcase.rsplit("_", 2)
    cloud, rows, regions = scene(kind, int(seed), perm == "True")
    j_fail = []
    cq = item["variant"]["candidate_quality"]
    for i, p in enumerate(item["variant"]["W"]):
        recomputed = quality(cloud, rows, p, setting)
        got = cq[i]
        for key in ("J_m2", "occupied_xy_cells", "supported_xy_cells", "source_xy_cell_coverage"):
            if abs(float(got[key]) - float(recomputed[key])) > 1e-12:
                j_fail.append((jcase, i, key, got[key], recomputed[key]))
        if int(got["rms_m"] is None) != int(recomputed["rms_m"] is None):
            j_fail.append((jcase, i, "rms_none_mismatch"))
    out = dict(a02_fail_count=len(fails), a02_failures=fails[:50],
               ledger_checked=checked, ledger_fail_count=len(ledger_fails),
               ledger_failures=ledger_fails[:80],
               cases_with_W_change_by_K=len(wdiff), total_cases=len(W_by_case),
               J_recompute_fail_count=len(j_fail), J_recompute_failures=j_fail[:20],
               count_records_summary=dict(
                   max_draws_seen=max(r["draws_seen"] for r in count_records),
                   max_qualified=max(r["qualified"] for r in count_records),
                   total_records=len(count_records)))
    (OUT / "04_probe_a02_a03_a05_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A02 fails", len(fails), "| ledger checked", checked, "fails", len(ledger_fails),
          "| W-changes-by-K", len(wdiff), "/", len(W_by_case), "| J fails", len(j_fail))
    for x in ledger_fails[:30]:
        print("LFAIL", x)
    for x in j_fail[:10]:
        print("JFAIL", x)


if __name__ == "__main__":
    main()
