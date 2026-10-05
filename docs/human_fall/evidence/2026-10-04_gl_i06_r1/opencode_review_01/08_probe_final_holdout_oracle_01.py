"""Independent full-W oracle over all 90 final-holdout ledgers (synthetic)."""
import itertools
import json
import math
from pathlib import Path

HERE = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1/research_01")
OUT = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1/opencode_review_01")


def my_oracle(w, ratio, deg, off, gaps):
    n = len(w)
    if n:
        sup = [p["support_count"] for p in w]
        best = max(sup)
        near = [i for i in range(n) if sup[i] >= ratio * best]
    else:
        best, near = None, []
    near_s = set(near)

    def distinct(i, j):
        dot = sum(a * b for a, b in zip(w[i]["normal"], w[j]["normal"]))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        return ang > deg or abs(w[i]["offset_m"] - w[j]["offset_m"]) > off

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


def main():
    fails = []
    checked = 0
    closed = 0
    for f in sorted(HERE.glob("final_*_K*_01.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        v = d["variant"]
        # settings are seed-dependent only in the RANSAC seed; distinct gates constant
        ratio, deg, off = 0.8, 10.0, 0.05
        w = v["W"]
        gaps = v["report"]["gaps_input"]
        best_w = max((p["support_count"] for p in w), default=None)
        o = my_oracle(w, ratio, deg, off, gaps)
        if v["report"]["best_support"] != best_w:
            fails.append(("best_not_max", f.name, v["report"]["best_support"], best_w))
        if o["status"] != v["report"]["status"]:
            fails.append(("status", f.name, o["status"], v["report"]["status"]))
        if v["report"]["metrics"]["ALL"]["holds"] != (not o["allp"]):
            fails.append(("ALL", f.name))
        if v["report"]["metrics"]["NEAR"]["holds"] != (not o["nearp"]):
            fails.append(("NEAR", f.name))
        if v["report"]["metrics"]["NEAR"]["distinct_pairs"] != o["nearp"]:
            fails.append(("NEAR_pairs", f.name))
        if v["report"]["status"] != "unresolved":
            closed += 1
        checked += 1
    # summary cross-check
    fh = json.loads((HERE / "final_holdout_summary_01.json").read_text(encoding="utf-8"))
    sum_fails = []
    if len(fh["results"]) != 30:
        sum_fails.append("results")
    out = dict(checked=checked, closed=closed, fail_count=len(fails),
               failures=fails[:50], summary_fail_count=len(sum_fails))
    (OUT / "08_probe_final_holdout_oracle_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("final ledgers checked", checked, "closed", closed, "fails", len(fails))
    for x in fails[:20]:
        print("FAIL", x)


if __name__ == "__main__":
    main()
