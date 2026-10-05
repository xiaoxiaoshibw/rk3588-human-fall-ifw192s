"""Independent ledger audit of GL-I06 using a self-written math-only oracle.

Reads r0_case_*_01.json and r1_case_*_K*_02.json. Never imports author oracle.
"""
import itertools
import json
import math
import sys
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
OUT = RUN / "opencode_review_01"


def my_oracle(w, ratio=0.8, deg=10.0, off=0.05, gaps=False):
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
    all_holds = not allp
    near_holds = not nearp
    if gaps or not w or not near_holds:
        status = "unresolved"
    elif all_holds:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"
    return dict(best=best, near_count=len(near), top=top, allp=allp, nearp=nearp,
                bestp=bestp, status=status, all_holds=all_holds, near_holds=near_holds)


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    r0_files = sorted(HERE.glob("r0_case_*_01.json"))
    results = []
    failures = []
    for r0f in r0_files:
        name = r0f.name[len("r0_case_"):-len("_01.json")]
        r0 = load(r0f)
        s = r0["settings"]
        w0 = r0["W"]
        o0 = my_oracle(w0, s["support_close_ratio"], s["distinct_normal_deg"],
                       s["distinct_offset_m"], r0["report"]["gaps_input"])
        # A03: scalar_full published in r0 must match my independent oracle
        if o0["status"] != r0["scalar_full"]["status"]:
            failures.append(("r0_status", name, o0["status"], r0["scalar_full"]["status"]))
        # A01: native fitter vs replay already asserted in author; check K1 parity per K
        k1 = load(HERE / ("r1_case_%s_K1_02.json" % name))
        v1 = k1["variant"]
        packet = k1.get("packet") or v1.get("packet")
        # sampled/raw identity against r0
        if r0["sampled_sha"] != packet["sampled_sha"]:
            failures.append(("sampled_sha", name, r0["sampled_sha"], packet["sampled_sha"]))
        if r0["raw_sha"] != packet["raw_sha"]:
            failures.append(("raw_sha", name, r0["raw_sha"], packet["raw_sha"]))
        if r0["source_sha"] != packet["source_sha"]:
            failures.append(("source_sha", name))
        if r0["settings_sha"] != packet["settings_sha"]:
            failures.append(("settings_sha", name))
        if v1["W"] != w0:
            failures.append(("K1_W_not_equal_R0", name, len(v1["W"]), len(w0)))
        # full-domain best_support must be max over variant.W
        maxsup = max((p["support_count"] for p in v1["W"]), default=None)
        if v1["report"]["best_support"] != maxsup:
            failures.append(("best_support_not_max_W", name, v1["report"]["best_support"], maxsup))
        # my oracle on full W vs published full metrics
        of = my_oracle(v1["W"], s["support_close_ratio"], s["distinct_normal_deg"],
                       s["distinct_offset_m"], v1["report"]["gaps_input"])
        if of["status"] != v1["report"]["status"]:
            failures.append(("full_status", name, of["status"], v1["report"]["status"]))
        if of["best"] != v1["report"]["best_support"]:
            failures.append(("full_best", name, of["best"], v1["report"]["best_support"]))
        pub = v1["report"]["metrics"]
        if pub["ALL"]["holds"] != of["all_holds"]:
            failures.append(("full_ALL", name))
        if pub["NEAR"]["holds"] != of["near_holds"]:
            failures.append(("full_NEAR", name))
        # vector pair multiset equality (index pairs)
        if pub["ALL"]["distinct_pairs"] != of["allp"]:
            failures.append(("full_ALL_pairs", name, len(pub["ALL"]["distinct_pairs"]), len(of["allp"])))
        if pub["NEAR"]["distinct_pairs"] != of["nearp"]:
            failures.append(("full_NEAR_pairs", name))
        if pub["BEST_ONLY"]["distinct_pairs"] != of["bestp"]:
            failures.append(("full_BEST_pairs", name))
        # stored-subset domain consistency: apply same oracle to report witnesses
        wits = v1["report"]["witnesses"]
        ow = my_oracle(wits, s["support_close_ratio"], s["distinct_normal_deg"],
                       s["distinct_offset_m"], v1["report"]["gaps_input"])
        ssd = v1["report"].get("stored_subset_diagnostics", {})
        if ssd.get("best_support") != ow["best"]:
            failures.append(("stored_best", name, ssd.get("best_support"), ow["best"]))
        # report.witnesses is bounded exact storage subset (may differ from full)
        results.append(dict(case=name, r0_status=o0["status"], k1_status=v1["report"]["status"],
                            W_count=len(v1["W"]), witness_count=len(wits),
                            full_best=maxsup, stored_best=ssd.get("best_support"),
                            all_pairs=len(of["allp"]), near_pairs=len(of["nearp"]),
                            best_only_pairs=len(of["bestp"])))
    out = dict(results=results, failure_count=len(failures), failures=failures[:200],
               n_cases=len(r0_files),
               note="self-written math-only oracle vs published full/stored domains")
    (OUT / "02_probe_a01_a03_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("cases", len(r0_files), "failures", len(failures))
    for f in failures[:40]:
        print("FAIL", f)


if __name__ == "__main__":
    main()
