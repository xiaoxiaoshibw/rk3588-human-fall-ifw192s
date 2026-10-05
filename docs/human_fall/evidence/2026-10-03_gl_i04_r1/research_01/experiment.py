"""Finite-sequence oracle, adversarial fixtures and measured experiment ledger."""
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[5]
PACKAGE = ROOT / "src/human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(Path(__file__).parent)]
from core import ground as g
from core.ground_diagnostics import replay_frozen_search, replay_sequence, refine_hypothesis
from core.capture_input import load_adapted, gate_selection
from evaluate_gli02_candidate import _load_draft, _draft_region, _load_constrained_settings
from search_prototype import search, search_events

OUT = Path(__file__).parent


def oracle(items, settings):
    """Unbounded only in evidence; complete SAME finite sequence, not physics."""
    distinct = []
    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            b = items[j]
            angle = np.degrees(np.arccos(np.clip(np.dot(a["normal"], b["normal"]), -1, 1)))
            if angle > settings["distinct_normal_deg"] or abs(a["offset_m"] - b["offset_m"]) > settings["distinct_offset_m"]:
                distinct.append([i, j])
    return {"status": "seen_sequence_closed_single" if items and not distinct else "unresolved",
            "refined_count": len(items), "distinct_pair_count": len(distinct),
            "scope": "same seen hypotheses only"}


def check_counts(report):
    c = report["counts"]
    assert c["qualified"] == c["refined"] + c["unprocessed"]
    assert c["refined"] == c["rejected"] + c["retained"] + c["merged_exact"] + c["merged_certified"] + c["unstored"]
    assert c["draws_seen"] == len(report["trace"]) + c["trace_unrecorded"]
    assert c["peak_retained"] <= report["budgets"]["candidate"]


def events_from_planes(planes):
    return [dict(plane, iteration=i, stage="qualified") for i, plane in enumerate(planes)]


def semantic_cases():
    s = g.resolve_constrained_settings()
    plane = lambda d, count=200: {"normal": [0., 0., 1.], "offset_m": d, "support_count": count}
    cases = {"clean": [plane(1.)], "duplicate": [plane(1.)] * 40,
             "close_distinct": [plane(1.), plane(1.07)],
             "late": [plane(1.)] * 40 + [plane(1.14)],
             "distinct_low_support": [plane(1., 500), plane(1.2, 100)],
             "chain": [plane(1.), plane(1.04), plane(1.08)]}
    cases["angular_chain"] = [dict(plane(1.), normal=[float(np.sin(np.radians(angle))), 0.,
                                                       float(np.cos(np.radians(angle)))]) for angle in (0, 6, 12)]
    ledger = []
    for name, planes in cases.items():
        variants = list(itertools.permutations(planes)) if "chain" in name else [planes, list(reversed(planes))]
        for order, ordered in enumerate(variants):
            events = events_from_planes(ordered)
            report = search_events(events, lambda e: (dict(e), "fixture_refined"), s)
            expected = oracle(ordered, s)
            assert report["status"] == expected["status"], (name, report["reasons"])
            check_counts(report)
            ledger.append({"case": name, "order": order, "oracle": expected, "prototype": report})
    # Explicitly disprove moving representative merge on the same chain.
    a, b, c = cases["chain"]
    assert abs(a["offset_m"] - b["offset_m"]) <= .05
    assert abs(b["offset_m"] - c["offset_m"]) <= .05
    assert abs(a["offset_m"] - c["offset_m"]) > .05
    for key, value in [("candidate_budget", 0), ("candidate_budget", 1), ("refine_budget", 0),
                       ("refine_budget", 1), ("trace_budget", 0), ("trace_budget", 1),
                       ("iteration_budget", 0), ("iteration_budget", 1)]:
        events = events_from_planes(cases["late"])
        report = search_events(events, lambda e: (dict(e), "fixture_refined"), s, **{key: value})
        assert report["status"] == "unresolved", (key, value)
        check_counts(report)
        ledger.append({"case": "budget", "setting": {key: value}, "prototype": report,
                       "oracle_same_sequence": oracle(cases["late"], s)})
    rejected = search_events(events_from_planes([plane(1.)]), lambda e: (None, "refine_degenerate"), s)
    assert rejected["status"] == "unresolved" and rejected["counts"]["rejected"] == 1
    assert search_events([], lambda e: (dict(e), "fixture_refined"), s)["status"] == "unresolved"
    for key in ("candidate_budget", "refine_budget", "trace_budget", "iteration_budget"):
        for value in (-1, True, 1.5, 2001):
            try:
                search_events([], lambda e: (None, "reject"), s, **{key: value})
            except ValueError:
                pass
            else:
                raise AssertionError("invalid budget accepted")
    return ledger


def scene(kind, seed, permute=False):
    rng = np.random.RandomState(seed)
    n = 500
    xy = rng.uniform(-3, 3, (n, 2))
    z = np.full(n, -1.4)
    if kind == "noise":
        z += rng.normal(0, .008, n)
    elif kind == "high_noise":
        z += rng.normal(0, .035, n)
    elif kind == "dual":
        z[n // 2:] -= .14
    elif kind == "close":
        z[n // 2:] -= .08
    fit = np.column_stack([xy, z])
    if permute:
        fit = fit[rng.permutation(n)]
    holds = [np.column_stack([rng.uniform(-3, 3, (80, 2)), np.full(80, -1.4)]) for _ in range(3)]
    points = np.vstack([fit] + holds)
    regions = [{"region_id": "v%d" % i, "frame_group": "hold%d" % i,
                "indices": list(range(n + 80 * i, n + 80 * (i + 1)))} for i in range(3)]
    return points, np.arange(n), regions


def compare(name, points, rows, regions, up, height, settings):
    started = time.perf_counter()
    baseline = g.fit_ground_plane_constrained(points, settings, "fixture", up, height,
                                               rows, "fit", regions)
    baseline_time = time.perf_counter() - started
    replay = replay_frozen_search(points, rows, up, height, settings)
    for key in ("sampled_fit_count", "raw_candidates", "candidates"):
        assert baseline[key] == replay[key], (name, key)
    assert baseline.get("competition_truncated", False) == replay["competition_truncated"]
    assert baseline["degenerate_samples"] == sum(replay["counters"].get(key, 0) for key in ("sample_area", "sample_separation"))
    prototype = search(points, rows, up, height, settings)
    check_counts(prototype)
    sampled, valid_rows, events = replay_sequence(points, rows, up, height, settings)
    seen, refined = list(events), []
    for event in seen:
        if event["stage"] == "qualified":
            item, _ = refine_hypothesis(points, sampled, valid_rows, event, up, height, settings)
            if item is not None:
                refined.append(item)
    expected = oracle(refined, settings)
    if prototype["status"] == "seen_sequence_closed_single":
        assert expected["status"] == prototype["status"], name
    if not any("budget" in reason or "unprocessed" in reason or "envelope" in reason for reason in prototype["reasons"]):
        assert expected["status"] == prototype["status"], name
    assert [event["iteration"] for event in seen] == [event["iteration"] for event in prototype["trace"]]
    digest = hashlib.sha256(json.dumps(seen, sort_keys=True, allow_nan=False).encode()).hexdigest()
    repeat = search(points, rows, up, height, settings)
    assert {k: v for k, v in repeat.items() if k != "elapsed_s"} == {k: v for k, v in prototype.items() if k != "elapsed_s"}
    return {"case": name, "seed": settings["seed"], "baseline": baseline,
            "baseline_elapsed_s": baseline_time, "replay_counters": replay["counters"],
            "sequence_sha256": digest, "sequence_length": len(seen),
            "oracle": expected, "prototype": prototype,
            "finite_sequence_parity": True}


def main():
    result = {"semantic": semantic_cases(), "synthetic": [], "real_WHAT_IF": []}
    for kind in ("clean", "noise", "high_noise", "dual", "close"):
        for seed in (7, 19, 41):
            for permutation in (False, True):
                points, rows, regions = scene(kind, seed, permutation)
                settings = g.resolve_constrained_settings({"seed": seed, "spatial_cell_m": .05,
                                                          "max_points_per_cell": 8})
                entry = compare("%s_seed%d_permute%s" % (kind, seed, permutation), points, rows,
                                regions, np.array([0., 0., 1.]), (.5, 2.), settings)
                if kind in ("clean", "noise"):
                    assert entry["prototype"]["status"] == "seen_sequence_closed_single", entry["case"]
                if kind == "dual":
                    assert entry["prototype"]["status"] == "unresolved", entry["case"]
                result["synthetic"].append(entry)
    base = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i02_r1"
    manifest, points = load_adapted(str(base / "08_real/real_candidate.adapted.npz"))
    draft = _load_draft(str(base / "codex_review_01/work/filled_real_draft.json"))
    fit = _draft_region(draft["fit_region"], "FIT")
    regions = [dict(_draft_region(r, "validation"), region_id=r["region_id"]) for r in draft["validation_regions"]]
    rows, resolved = gate_selection(points, manifest, fit, None, fit["frame_group"], regions)
    settings = _load_constrained_settings(str(PACKAGE / "config/geometry_constrained_gli03_r1.yaml"))
    for label, up in [("approved", draft["up_axis"]),
                       ("negative_X", [-draft["up_axis"][0], 0, draft["up_axis"][2]])]:
        result["real_WHAT_IF"].append(compare(label, points, rows, resolved,
            g._unit_vector(up, "up"), draft["sensor_height_interval_m"], settings))
    result["physical_verified"] = False
    result["local_runtime"] = {"python": sys.version, "numpy": np.__version__, "board_run": False}
    with (OUT / "experiment_results_final.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"synthetic_cases": len(result["synthetic"]), "semantic_cases": len(result["semantic"]),
                      "real_cases": len(result["real_WHAT_IF"]), "safety_checks": "PASS"}))


if __name__ == "__main__":
    main()
