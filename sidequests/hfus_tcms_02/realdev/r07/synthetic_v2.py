"""v2 synthetic verification: observable segments, joint angles >= 25 deg, truth used only for scoring."""
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s5core as C
import body2 as B
import chain as H

SCENARIOS = ['upright', 'bent', 'lying', 'occluded']
FRAMES = 60
TOL_ABS, TOL_REL = 0.03, 0.05
GATE_FRACTION = 0.8
GATE_CONVERGE_FRAMES = 60


def truth_of(spec):
    t = dict(spec['lengths'])
    t.update(spec['widths'])
    return t


def run(name, rng, frames=FRAMES, verbose=False):
    spec = B.scenario(name, rng)
    truth = truth_of(spec)
    cal = H.Calibrator(dict(H.SEED))
    rows, calib_frame = [], None
    for i in range(frames):
        r = np.random.default_rng(rng.integers(1 << 31))
        pts, J = B.sample(spec, r)
        placed = B.place(pts, spec['tilt'] + r.normal(0, 3.0), r)
        # body-plane projection exactly as for the real cloud
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import fit as F
        uv, _ = F.to_plane(placed)
        measured, diag = H.measure(uv)
        snap = cal.update(i, measured)
        rows.append(dict(frame=i, measured=sorted(measured), n=len(measured),
                         states={k: v['state'] for k, v in snap.items()}))
        if calib_frame is None and sum(1 for v in snap.values() if v['state'] == 'CALIBRATED') >= 0.6 * len(truth):
            calib_frame = i
        if verbose and i == 0:
            print('   f0 measured', {k: round(v, 3) for k, v in measured.items()})
            print('   f0 truth   ', {k: round(v, 3) for k, v in truth.items()})
    final = cal.snapshot()
    scored, within = {}, 0
    for k, L in truth.items():
        got = final[k]
        tol = max(TOL_ABS, TOL_REL * L)
        err = abs(got['mean'] - L) if got['n'] else None
        ok = bool(err is not None and err <= tol and got['state'] == 'CALIBRATED')
        within += int(ok)
        scored[k] = dict(true=L, estimate=got['mean'], abs_error=err, tolerance=tol, within=ok,
                         n=got['n'], state=got['state'], std=got['std'])
    return dict(scenario=name, segments=len(scored), within=within,
                within_fraction=within / len(scored), calib_frame=calib_frame,
                converged=bool(calib_frame is not None and calib_frame <= GATE_CONVERGE_FRAMES),
                per_segment=scored, frames=rows, drift_events=len(cal.log),
                calibrator_log=cal.log,
                gate_within=bool(within / len(scored) >= GATE_FRACTION),
                gate_converged=bool(calib_frame is not None and calib_frame <= GATE_CONVERGE_FRAMES))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    seeds = dict(upright=21, bent=22, lying=23, occluded=24)
    out = {}
    for name in SCENARIOS:
        rng = np.random.default_rng(seeds[name])
        out[name] = run(name, rng, verbose=(mode == 'probe'))
        r = out[name]
        print('%-9s within %2d/%2d (%.2f) calib_frame=%s drift=%d' %
              (name, r['within'], r['segments'], r['within_fraction'], r['calib_frame'], r['drift_events']))
        if mode == 'probe':
            for k, v in r['per_segment'].items():
                if not v['within']:
                    print('   miss %-12s true=%.3f est=%.3f err=%s n=%d state=%s'
                          % (k, v['true'], v['estimate'],
                             None if v['abs_error'] is None else round(v['abs_error'], 3), v['n'], v['state']))
    gate = dict(scenarios_within=sum(1 for r in out.values() if r['gate_within']),
                scenarios_converged=sum(1 for r in out.values() if r['gate_converged']),
                pass_within=sum(1 for r in out.values() if r['gate_within']) >= 4,
                pass_converged=sum(1 for r in out.values() if r['gate_converged']) >= 3)
    print(json.dumps(gate))
    if mode == 'freeze':
        C.write(C.OUT / 'SYNTHETIC_V2.json', dict(
            item=C.ITEM, version='v2', frames=FRAMES, tolerance=dict(abs_m=TOL_ABS, rel=TOL_REL),
            gate_fraction=GATE_FRACTION, converge_frames=GATE_CONVERGE_FRAMES, seeds=seeds,
            scenarios=out, gate=gate, PASS=bool(gate['pass_within'] and gate['pass_converged']),
            note='truth is used only in scoring; the extractor reads points only'))
    if mode == 'pilot':
        C.write(C.OUT / 'PILOT_V2.json', dict(item=C.ITEM, version='v2', frames=FRAMES,
                                             tolerance=dict(abs_m=TOL_ABS, rel=TOL_REL),
                                             seeds=seeds, gate=gate, scenarios=out,
                                             PASS=bool(gate['pass_within'] and gate['pass_converged'])))
