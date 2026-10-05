"""GL-I05 measured experiment ledger. Offline research only, no runtime use.

Compares the frozen production baseline, the replayed frozen search, and the
GL-I05 prototype against the independent three-metric oracle over the SAME
finite seen sequence (same source / selector / seed / sampled sequence SHA).
Never claims real calibration success; real approved has no qualified draws
and negative-X is a WHAT_IF study, both stay physical=false.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import importlib.util
import tracemalloc
import argparse

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(HERE)]

from core import ground as g
from core.ground_diagnostics import (replay_frozen_search, replay_sequence,
                                     refine_hypothesis)
from core.capture_input import load_adapted, gate_selection
from evaluate_gli02_candidate import (_load_draft, _draft_region,
                                      _load_constrained_settings)

from oracle_analysis import oracle
from search_prototype import search

OUT = Path(__file__).parent
I04_PATH = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01/search_prototype.py'
spec = importlib.util.spec_from_file_location('frozen_i04_prototype', str(I04_PATH))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def _check_counts(report):
    c = report["counts"]
    assert c["qualified"] == c["unprocessed"] + c["refined_calls"]
    assert c["refined_calls"] == c["rejected"] + c["produced"]
    assert c["produced"] == c["merged_exact"] + c["retained"] + c["unstored"]
    assert c["draws_seen"] == len(report["trace"]) + c["trace_unrecorded"]
    assert c["peak_stored"] <= report["budgets"]["candidate"]


def _unique_count(witnesses):
    return len({(tuple(w["normal"]), w["offset_m"], w["support_count"])
                for w in witnesses})


def scene(kind, seed, permute=False):
    """Fit cloud + 3 holdout regions, mirrored from the GL-I04 fixture."""
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
    elif kind == "weak":
        z[:100] -= .14
    fit = np.column_stack([xy, z])
    if permute:
        fit = fit[rng.permutation(n)]
    holds = [np.column_stack([rng.uniform(-3, 3, (80, 2)), np.full(80, -1.4)])
             for _ in range(3)]
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
    for key in ("sampled_fit_count", "candidates"):
        assert baseline[key] == replay[key], (name, key)
    assert baseline.get("competition_truncated", False) == replay["competition_truncated"]
    assert baseline["degenerate_samples"] == sum(
        replay["counters"].get(key, 0) for key in ("sample_area", "sample_separation"))

    sampled, valid_rows, events = replay_sequence(points, rows, up, height, settings)
    seen = list(events)
    refined = []
    for event in seen:
        if event["stage"] == "qualified":
            item, _ = refine_hypothesis(points, sampled, valid_rows, event, up,
                                        height, settings)
            if item is not None:
                refined.append(item)
    expected = oracle(refined, settings, gaps=False)
    digest = hashlib.sha256(json.dumps(seen, sort_keys=True,
                                       allow_nan=False).encode()).hexdigest()

    unique = _unique_count(refined)
    budget = min(512, unique + 8)
    old_report = old.search(points, rows, up, height, settings, candidate_budget=budget)
    started = time.perf_counter()
    prototype = search(points, rows, up, height, settings, candidate_budget=budget)
    prototype_time = time.perf_counter() - started
    _check_counts(prototype)
    def trace_digest(report):
        raw = [dict(iteration=r['iteration'],stage=r['raw_stage'],**r['raw_hypothesis'])
               for r in report['trace']]
        return hashlib.sha256(json.dumps(raw,sort_keys=True,allow_nan=False).encode()).hexdigest()
    assert trace_digest(prototype) == digest == trace_digest(old_report)
    assert prototype['sampled_rows'] == old_report['sampled_rows'] == sampled.tolist()
    assert [event["iteration"] for event in seen] == \
           [event["iteration"] for event in prototype["trace"]]
    repeat = search(points, rows, up, height, settings, candidate_budget=budget)
    assert {k: v for k, v in repeat.items() if k not in ("elapsed_s", "stage_elapsed_s")} == \
           {k: v for k, v in prototype.items() if k not in ("elapsed_s", "stage_elapsed_s")}

    repeats = [prototype, repeat,
               search(points, rows, up, height, settings, candidate_budget=budget)]
    timings = []
    for report in repeats:
        tick = time.perf_counter()
        encoded = json.dumps(report, sort_keys=True, allow_nan=False).encode()
        timings.append(dict(report["stage_elapsed_s"], serialization=time.perf_counter()-tick,
                            search_total=report["elapsed_s"], serialized_bytes=len(encoded)))
    tracemalloc.start()
    memory_report = search(points, rows, up, height, settings, candidate_budget=budget)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert memory_report['status'] == prototype['status']

    gaps = prototype['gaps_input']
    matched = prototype["status"] == (oracle(refined, settings, gaps=gaps)["status"])
    closed = prototype["status"] in ("seen_pairwise_closed",
                                     "seen_dominant_pool_closed")
    safe = (not closed) or (not gaps and matched and expected["status"] == prototype["status"])
    return {"case": name, "seed": settings["seed"],
            "elapsed_s": {"baseline_fit": baseline_time,
                          "research_search": prototype_time,
                          "scoreboard_total": baseline_time + prototype_time},
            "baseline_status": baseline["status"], "baseline_reason": baseline.get("reason"),
            "baseline_ambiguous": baseline.get("ambiguous", False),
            "baseline_elapsed_s": baseline_time,
            "replay_counters": replay["counters"],
            "qualified_draws": sum(1 for event in seen if event["stage"] == "qualified"),
            "witness_count_raw": len(refined), "witness_count_unique": unique,
            "candidate_budget_used": budget,
            "source_sha256": hashlib.sha256(np.asarray(points).tobytes()).hexdigest(),
            "fit_rows_sha256": hashlib.sha256(np.asarray(rows).tobytes()).hexdigest(),
            "settings_sha256": hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest(),
            "up_axis": np.asarray(up).tolist(), "sensor_height_interval_m": list(height),
            "sampled_rows_sha256": hashlib.sha256(sampled.tobytes()).hexdigest(),
            "old_sequence_sha256": trace_digest(old_report),
            "prototype_sequence_sha256": trace_digest(prototype),
            "cost_repeats": timings, "peak_tracemalloc_bytes": peak,
            "memory_measurement_separate_from_timing": True,
            "old_i04": {"status": old_report['status'], 'reasons': old_report['reasons'],
                        'counts': old_report['counts'],
                        'sequence_iterations_match': [e['iteration'] for e in old_report['trace']] ==
                                                     [e['iteration'] for e in seen]},
            "rejection_attribution": {
                'actual_near_pool_competition': not expected['metrics']['NEAR']['holds'],
                'old_certificate_insufficient': 'similarity_envelope_not_closed' in old_report['reasons'],
                'processing_budget_gap': gaps},
            "sequence_sha256": digest, "sequence_length": len(seen),
            "oracle": {"status": expected["status"],
                       "witness_count": expected["witness_count"],
                       "near_pool_size": len(expected["near_pool_indices"]),
                       "metrics": {key: {"holds": value["holds"],
                                         "distinct_pair_count": len(value["distinct_pairs"])}
                                   for key, value in expected["metrics"].items()
                                   if key in ("ALL", "NEAR", "BEST_ONLY")}},
            "prototype": {"status": prototype["status"], "reasons": prototype["reasons"],
                          "counts": prototype["counts"],
                          "witnesses": prototype["witnesses"],
                          "metrics": {key: {"holds": value["holds"],
                                            "distinct_pair_count": len(value["distinct_pairs"])}
                                      for key, value in prototype["metrics"].items()
                                      if key in ("ALL", "NEAR", "BEST_ONLY")},
                          "best_support": prototype["best_support"],
                          "top_tie_count": len(prototype["top_tie_indices"]),
                          "elapsed_s": prototype_time},
            "oracle_match": matched, "closure_safe": safe}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-file', default='experiment_results_final.json')
    args = parser.parse_args()
    output_file = HERE / args.output_file
    if output_file.parent.resolve() != HERE or output_file.exists() or output_file.is_symlink():
        raise ValueError('require new ledger filename within current research root')
    result = {"kind": "gli05_experiment_ledger", "synthetic": [], "real_WHAT_IF": []}
    for kind in ("clean", "noise", "high_noise", "weak", "dual", "close"):
        for seed in (7, 19, 41):
            for permutation in (False, True):
                points, rows, regions = scene(kind, seed, permutation)
                settings = g.resolve_constrained_settings({"seed": seed,
                                                           "spatial_cell_m": .05,
                                                           "max_points_per_cell": 8})
                entry = compare("%s_seed%d_permute%s" % (kind, seed, permutation),
                                points, rows, regions, np.array([0., 0., 1.]),
                                (.5, 2.), settings)
                if kind in ("clean", "noise"):
                    assert entry["closure_safe"], entry["case"]
                if kind == "dual":
                    assert entry["prototype"]["status"] == "unresolved", entry["case"]
                assert entry["oracle_match"], entry["case"]
                result["synthetic"].append(entry)

    base = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i02_r1"
    manifest, points = load_adapted(str(base / "08_real" / "real_candidate.adapted.npz"))
    draft = _load_draft(str(base / "codex_review_01" / "work" / "filled_real_draft.json"))
    fit = _draft_region(draft["fit_region"], "FIT")
    regions = [dict(_draft_region(r, "validation"), region_id=r["region_id"])
               for r in draft["validation_regions"]]
    rows, resolved = gate_selection(points, manifest, fit, None, fit["frame_group"], regions)
    settings = _load_constrained_settings(
        str(PACKAGE / "config" / "geometry_constrained_gli03_r1.yaml"))
    for label, up in [("approved", draft["up_axis"]),
                      ("negative_X", [-draft["up_axis"][0], 0, draft["up_axis"][2]])]:
        entry = compare(label, points, rows, resolved, g._unit_vector(up, "up"),
                        draft["sensor_height_interval_m"], settings)
        entry["physical_verified"] = False
        entry["origin"] = ("approved_prior_from_human_draft" if label == "approved"
                           else "WHAT_IF_negated_up_not_physical")
        assert entry["oracle_match"], label
        result["real_WHAT_IF"].append(entry)

    result["physical_verified"] = False
    result['implementation_sha256'] = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [HERE/'search_prototype.py', HERE/'oracle_analysis.py', HERE/'experiment.py', I04_PATH,
                  PACKAGE/'core/ground.py', PACKAGE/'core/ground_diagnostics.py']}
    result['cost_comparison_boundary'] = ('Frozen baseline_fit includes native validation and '
        'research_search includes all qualified refinements and exact decision. Serialization is '
        'reported separately. These are different phases, not an end-to-end acceleration claim. '
        'tracemalloc peak is a separate run and does not include process-wide RSS.')
    result["local_runtime"] = {"python": sys.version, "numpy": np.__version__,
                               "board_run": False}
    with output_file.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps({"synthetic_cases": len(result["synthetic"]),
                      "real_cases": len(result["real_WHAT_IF"]),
                      "all_oracle_match": all(e["oracle_match"] for e in
                                              result["synthetic"] + result["real_WHAT_IF"]),
                      "all_closure_safe": all(e["closure_safe"] for e in
                                              result["synthetic"] + result["real_WHAT_IF"])}))


if __name__ == "__main__":
    main()
