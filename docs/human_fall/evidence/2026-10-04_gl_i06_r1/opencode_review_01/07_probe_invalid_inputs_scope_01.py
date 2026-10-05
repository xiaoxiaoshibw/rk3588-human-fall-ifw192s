"""A05 invalid-input rejection, ignored-input coverage, scope/model-domain checks."""
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
    import r0_01
    from refinement_05 import validate_packet, run_variant
    from core import ground as g
    from oracle_analysis import oracle
    from r0_01 import digest

    fails = []
    pts, rows, _ = r0_01.scene("clean", 7)
    s = r0_01.settings(7)
    from core import ground_diagnostics as gd
    sampled, fit, it = gd.replay_sequence(pts, rows, np.array([0., 0., 1.]), (.5, 2.), s)
    seq = list(it)
    packet = dict(schema=1, units="m", frame="research_source", source_sha=digest(pts),
                  fit_sha=digest(fit), sampled_sha=digest(sampled), raw_sha=digest(seq),
                  settings_sha=digest(s))
    validate_packet(pts, fit, sampled, seq, s, packet)

    def reject(label, fn):
        try:
            fn()
        except (ValueError, TypeError):
            return
        fails.append(("accepted_invalid", label))

    reject("schema_bool", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, schema=True)))
    reject("schema_2", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, schema=2)))
    reject("units_cm", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, units="cm")))
    reject("frame_foreign", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, frame="foreign")))
    reject("source_changed", lambda: validate_packet(pts + 0.01, fit, sampled, seq, s, packet))
    bad = pts.copy(); bad[0, 0] = float("nan")
    reject("nan_source", lambda: validate_packet(bad, fit, sampled, seq, s, packet))
    reject("settings_changed", lambda: validate_packet(pts, fit, sampled, seq, dict(s, seed=19), packet))
    reject("zero_threshold", lambda: g.resolve_constrained_settings(dict(s, inlier_threshold_m=0.)))
    reject("nan_angle", lambda: g.resolve_constrained_settings(dict(s, max_angle_rad=float("nan"))))
    reject("zero_up", lambda: g._unit_vector([0., 0., 0.], "up"))
    reject("nan_height", lambda: g._height_interval([float("nan"), 2.]))
    reject("empty_K0", lambda: run_variant(pts, sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, 0))
    reject("bool_K", lambda: run_variant(pts, sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, True))
    reject("lo_over", lambda: run_variant(pts, sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, 1, lo_budget=6001))
    reject("non_nx3", lambda: run_variant(pts[:, :2], sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, 1))
    # oracle witness validation
    reject("witness_nonunit", lambda: oracle([dict(normal=[0., 0., 2.], offset_m=1., support_count=1)],
                                             dict(distinct_normal_deg=10., distinct_offset_m=.05, support_close_ratio=.8)))
    reject("witness_bool_support", lambda: oracle([dict(normal=[0., 0., 1.], offset_m=1., support_count=True)],
                                                  dict(distinct_normal_deg=10., distinct_offset_m=.05, support_close_ratio=.8)))
    reject("witness_nan_offset", lambda: oracle([dict(normal=[0., 0., 1.], offset_m=float("nan"), support_count=1)],
                                                dict(distinct_normal_deg=10., distinct_offset_m=.05, support_close_ratio=.8)))
    out_io = dict(fail_count=len(fails), failures=fails)
    # ignored primary inputs explicitly present with hashes
    before = json.loads((RUN / "01_before_baseline.json").read_text(encoding="utf-8"))["files"]
    ignored = ["captures/remote/cap_20261002_163621/meta.json",
               "captures/remote/cap_20261002_163621/points.bin",
               "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz"]
    ign = {}
    for rel in ignored:
        if rel not in before:
            ign[rel] = "absent_from_baseline"
            fails.append(("ignored_absent", rel))
        else:
            p = REPO / rel
            if not p.exists():
                ign[rel] = "missing_now"
                fails.append(("ignored_missing", rel))
            elif sha(p) != before[rel]["sha256"]:
                ign[rel] = "sha_mismatch"
                fails.append(("ignored_sha", rel))
            else:
                ign[rel] = "ok"
    # r0 summary real context
    summary = json.loads((HERE / "r0_summary_01.json").read_text(encoding="utf-8"))
    r0_real = dict(observed_real_frames=summary["observed_real_frames"],
                   real_use=summary["real_use"], physical_verified=summary["physical_verified"],
                   refinement_gate_triggered=summary["refinement_gate_triggered"],
                   robust_gate_triggered=summary["robust_gate_triggered"])
    # cross-K model-domain statement in ledgers
    led = json.loads((HERE / "r1_case_high_noise_7_False_K2_02.json").read_text(encoding="utf-8"))["variant"]
    dom = dict(comparison_domain=led.get("comparison_domain"),
               metric_domain=led["report"].get("metric_domain"))
    # W differs across K and full best differs
    k1 = json.loads((HERE / "r1_case_high_noise_7_False_K1_02.json").read_text(encoding="utf-8"))["variant"]
    k3 = json.loads((HERE / "r1_case_high_noise_7_False_K3_02.json").read_text(encoding="utf-8"))["variant"]
    model = dict(K1_full_best=k1["report"]["best_support"], K2_full_best=led["report"]["best_support"],
                 K3_full_best=k3["report"]["best_support"],
                 K1_W_ne_K2_W=(k1["W"] != led["W"]))
    out = dict(invalid_inputs=out_io, ignored_inputs=ign, r0_real=r0_real,
               model_domain=dom, model=model)
    (OUT / "07_probe_invalid_inputs_scope_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("invalid fails", out_io["fail_count"], out_io["failures"][:20])
    print("ignored", ign)
    print("r0_real", r0_real)
    print("model", model)


if __name__ == "__main__":
    main()
