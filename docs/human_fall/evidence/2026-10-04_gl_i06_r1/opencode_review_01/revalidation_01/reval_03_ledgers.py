"""Revalidation step 3: independent math-only oracle over every published ledger.

Rechecks A01 (source/sampled/raw/settings identity + K1==R0 W), A03/A05
(full-W and stored-subset domains, best=max(W), gap->unresolved, no false
closure) for 62 R0 + 186 K + 90 final ledgers. NEW output 03_ledgers_01.json.
"""
import itertools
import json
import math
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
REVAL = RUN / "opencode_review_01/revalidation_01"
RATIO, DEG, OFF = 0.8, 10.0, 0.05


def my_oracle(w, gaps):
    n = len(w)
    if n:
        sup = [p["support_count"] for p in w]
        best = max(sup)
        near = [i for i in range(n) if sup[i] >= RATIO * best]
    else:
        best, near = None, []
    near_s = set(near)

    def distinct(i, j):
        dot = sum(a * b for a, b in zip(w[i]["normal"], w[j]["normal"]))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        return ang > DEG or abs(w[i]["offset_m"] - w[j]["offset_m"]) > OFF

    allp, nearp = [], []
    for i, j in itertools.combinations(range(n), 2):
        if distinct(i, j):
            allp.append([i, j])
            if i in near_s and j in near_s:
                nearp.append([i, j])
    if gaps or not w or nearp:
        status = "unresolved"
    elif not allp:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"
    return dict(status=status, best=best, allp=allp, nearp=nearp)


def check_variant(tag, v, fails):
    # settings gates are constant across all variants (distinct 10 / .05 / .8)
    w = v["W"]
    rep = v["report"]
    gaps = rep["gaps_input"]
    best = max((p["support_count"] for p in w), default=None)
    if rep["best_support"] != best:
        fails.append(("best_not_max", tag, rep["best_support"], best))
    o = my_oracle(w, gaps)
    if o["status"] != rep["status"]:
        fails.append(("status", tag, o["status"], rep["status"]))
    if o["best"] != rep["best_support"]:
        fails.append(("best", tag))
    if rep["metrics"]["ALL"]["holds"] != (not o["allp"]):
        fails.append(("ALL", tag))
    if rep["metrics"]["NEAR"]["holds"] != (not o["nearp"]):
        fails.append(("NEAR", tag))
    if rep["metrics"]["ALL"]["distinct_pairs"] != o["allp"]:
        fails.append(("ALL_pairs", tag))
    if rep["metrics"]["NEAR"]["distinct_pairs"] != o["nearp"]:
        fails.append(("NEAR_pairs", tag))
    if gaps and rep["status"] != "unresolved":
        fails.append(("gap_not_unresolved", tag))
    if rep["status"] != "unresolved" and o["nearp"]:
        fails.append(("false_closure", tag))
    ssd = rep.get("stored_subset_diagnostics")
    if ssd is not None:
        ow = my_oracle(rep["witnesses"], gaps)
        if ssd.get("best_support") != ow["best"]:
            fails.append(("stored_best", tag))
    return o, best


def main():
    fails = []
    n_r0 = n_k = n_final = 0
    # R0 cases: full scalar_full status vs my oracle on R0 W
    for f in sorted(HERE.glob("r0_case_*_01.json")):
        name = f.name[len("r0_case_"):-len("_01.json")]
        r0 = json.loads(f.read_text(encoding="utf-8"))
        o = my_oracle(r0["W"], r0["report"]["gaps_input"])
        if o["status"] != r0["scalar_full"]["status"]:
            fails.append(("r0_status", name, o["status"], r0["scalar_full"]["status"]))
        # A01 identity across K ledgers
        for k in (1, 2, 3):
            led = json.loads((HERE / ("r1_case_%s_K%d_02.json" % (name, k))).read_text(encoding="utf-8"))
            pkt = led["packet"]
            if (r0["source_sha"] != pkt["source_sha"] or r0["sampled_sha"] != pkt["sampled_sha"]
                    or r0["raw_sha"] != pkt["raw_sha"] or r0["settings_sha"] != pkt["settings_sha"]):
                fails.append(("identity", name, k))
            if k == 1 and led["variant"]["W"] != r0["W"]:
                fails.append(("K1_ne_R0", name))
        n_r0 += 1
    # K ledgers full/stored domain
    for f in sorted(HERE.glob("r1_case_*_K*_02.json")):
        name = f.name[len("r1_case_"):]
        v = json.loads(f.read_text(encoding="utf-8"))["variant"]
        check_variant(name, v, fails)
        n_k += 1
    # final holdout ledgers
    for f in sorted(HERE.glob("final_*_K*_01.json")):
        v = json.loads(f.read_text(encoding="utf-8"))["variant"]
        check_variant(f.name, v, fails)
        n_final += 1
    target = REVAL / "03_ledgers_01.json"
    if target.exists():
        raise SystemExit("refuse to overwrite " + str(target))
    out = {"n_r0": n_r0, "n_k": n_k, "n_final": n_final,
           "fail_count": len(fails), "failures": fails[:200],
           "note": "self-written math-only oracle; gates 10deg/0.05m/0.8 constant"}
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("r0", n_r0, "k", n_k, "final", n_final, "failures", len(fails))
    for x in fails[:30]:
        print("FAIL", x)


if __name__ == "__main__":
    main()
