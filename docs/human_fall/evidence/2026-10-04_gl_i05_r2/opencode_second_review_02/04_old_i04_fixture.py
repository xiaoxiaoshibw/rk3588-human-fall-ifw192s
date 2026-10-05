"""Cause-attribution probe: actual GL-I04 envelope prototype vs scalar/new.

Runs the *actual* frozen GL-I04 `search_prototype.py` on the same finite
sequence as the new prototype so the attribution "old certificate deficient,
not true competition" is independently reproducible. Includes the 0/4/8 deg
all-similar fixture where the fixed-anchor envelope is order-dependent.
"""
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
RES = RUN / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(RES)]

import numpy as np
from core import ground as g
from search_prototype import search_events as new_search_events

I04 = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01/search_prototype.py"
spec = importlib.util.spec_from_file_location("frozen_i04_prototype", str(I04))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

S = g.resolve_constrained_settings()


def unit(v):
    v = np.asarray(v, float)
    return (v / np.linalg.norm(v)).tolist()


def plane(offset, support, deg=0.0):
    return {"normal": unit([math.sin(math.radians(deg)), 0, math.cos(math.radians(deg))]),
            "offset_m": offset, "support_count": support}


def events(planes):
    return [dict(planes[i], iteration=i, stage="qualified") for i in range(len(planes))]


def identity_refine(event):
    return ({"normal": list(event["normal"]), "offset_m": event["offset_m"],
             "support_count": event["support_count"]}, "refined")


def scalar(ws):
    n = len(ws)
    def dist(a, b):
        dot = max(-1., min(1., sum(x * y for x, y in zip(a["normal"], b["normal"]))))
        return math.degrees(math.acos(dot)) > 10 or abs(a["offset_m"] - b["offset_m"]) > .05
    pairs = [[i, j] for i, j in itertools.combinations(range(n), 2) if dist(ws[i], ws[j])]
    s = max(w["support_count"] for w in ws)
    near = {i for i, w in enumerate(ws) if w["support_count"] >= .8 * s}
    npairs = [p for p in pairs if set(p) <= near]
    if not ws or npairs:
        return "unresolved"
    return "seen_dominant_pool_closed" if pairs else "seen_pairwise_closed"


def main():
    out = {"script": "04_old_i04_fixture", "i04_path": I04.as_posix()}
    allsim = [plane(1.0, 200, d) for d in (0.0, 4.0, 8.0)]
    rows = []
    order_dependent = False
    for perm in itertools.permutations(allsim):
        o = old.search_events(events(list(perm)), identity_refine, S)
        nw = new_search_events(events(list(perm)), identity_refine, S)
        sc = scalar(list(perm))
        rows.append({"order": [round(math.degrees(math.acos(max(-1, min(1, w["normal"][2]))))) for w in perm],
                     "old": o["status"], "old_reasons": o["reasons"],
                     "new": nw["status"], "scalar": sc})
        if o["status"] != "seen_sequence_closed_single":
            order_dependent = True
    out["all_similar_088_rows"] = rows
    out["old_order_dependent"] = order_dependent
    out["new_all_closed"] = all(r["new"] == "seen_pairwise_closed" for r in rows)
    out["scalar_all_closed"] = all(r["scalar"] == "seen_pairwise_closed" for r in rows)

    # chain 0/6/12: old and scalar should both not close
    chain = [plane(1.0, 450, -6.0), plane(1.0, 500, 0.0), plane(1.0, 450, 6.0)]
    o = old.search_events(events(chain), identity_refine, S)
    nw = new_search_events(events(chain), identity_refine, S)
    out["chain_old_status"] = o["status"]
    out["chain_new_status"] = nw["status"]
    out["chain_scalar"] = scalar(chain)

    # new prototype vs old prototype terminal agreement on random sequences
    import random
    rng = random.Random(11)
    old_vs_new = {"same": 0, "diff": 0}
    for _ in range(200):
        n = rng.randint(1, 8)
        ws = [plane(rng.choice([1.0, 1.0, 1.05, 1.2]), rng.choice([100, 200, 250, 400, 500]),
                    rng.uniform(0, 30)) for _ in range(n)]
        o = old.search_events(events(ws), identity_refine, S)
        nw = new_search_events(events(ws), identity_refine, S)
        old_close = o["status"] == "seen_sequence_closed_single"
        new_close = nw["status"] in ("seen_pairwise_closed", "seen_dominant_pool_closed")
        # both close or both not; expected mostly disagree because semantics differ
        if (o["status"] == "seen_sequence_closed_single") == new_close:
            old_vs_new["same"] += 1
        else:
            old_vs_new["diff"] += 1
    out["terminal_agreement_200_random"] = old_vs_new

    (Path(__file__).resolve().parent / "04_old_i04_fixture.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"old_order_dependent": out["old_order_dependent"],
                      "new_all_closed": out["new_all_closed"],
                      "scalar_all_closed": out["scalar_all_closed"],
                      "chain": [out["chain_old_status"], out["chain_new_status"], out["chain_scalar"]],
                      "old_vs_new_terminal_200": old_vs_new,
                      "i04_first_two": rows[:2]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
