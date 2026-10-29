"""Temporal-tracking verification on synthetic bodies (truth only for scoring)."""
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s5core as C
import body2 as B
import chain as H
import track as T
import fit as F

SCENARIOS = ['upright', 'bent', 'lying', 'occluded']
FRAMES = 60
TOL_ABS, TOL_REL = 0.03, 0.05
GATE_FRACTION, GATE_FRAMES = 0.8, 60


def run(name, rng, frames=FRAMES, verbose=False):
    spec = B.scenario(name, rng)
    truth = dict(spec['lengths'])
    truth.update(spec['widths'])
    L0 = {k: H.SEED[k] for k in T.LENGTH_KEYS}
    W0 = {k: H.SEED[k] for k in T.WIDTH_KEYS}
    tr = None
    rows, calib_frame = [], None
    for i in range(frames):
        r = np.random.default_rng(rng.integers(1 << 31))
        pts, J = B.sample(spec, r)
        placed = B.place(pts, spec['tilt'] + r.normal(0, 3.0), r)
        uv, _ = F.to_plane(placed)
        if tr is None:
            theta, root, c = T.seed(uv, L0, W0, __import__('scipy.spatial', fromlist=['cKDTree']).cKDTree(uv))
            tr = T.Tracker(L0, W0, theta, root)
        rec, Jfit, snap = tr.step(uv)
        rows.append(rec)
        if calib_frame is None and sum(1 for v in snap.values() if v['state'] == 'CALIBRATED') >= 0.6 * len(truth):
            calib_frame = i
        if verbose and i == 0:
            snap0 = tr.cal.snapshot()
            print('   f0 measured', {k: round(v['mean'], 3) for k, v in snap0.items() if v['n']})
    final = tr.cal.snapshot()
    scored, within, n_calibrated = {}, 0, 0
    for k, L in truth.items():
        got = final[k]
        tol = max(TOL_ABS, TOL_REL * L)
        err = abs(got['mean'] - L) if got['n'] else None
        # accuracy is scored on the estimate with enough samples; the state machine is scored separately
        ok = bool(err is not None and err <= tol and got['n'] >= 15)
        within += int(ok)
        n_calibrated += int(got['state'] == 'CALIBRATED')
        scored[k] = dict(true=L, estimate=got['mean'], abs_error=err, tolerance=tol, within=ok,
                         n=got['n'], state=got['state'], std=got['std'])
    return dict(scenario=name, segments=len(scored), within=within,
                within_fraction=within / len(scored), calibrated=n_calibrated,
                calib_frame=calib_frame,
                converged=bool(calib_frame is not None and calib_frame <= GATE_FRAMES),
                per_segment=scored, frames=rows, drift_events=len(tr.cal.log),
                gate_within=bool(within / len(scored) >= GATE_FRACTION),
                gate_converged=bool(calib_frame is not None and calib_frame <= GATE_FRAMES))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    seeds = dict(upright=31, bent=32, lying=33, occluded=34)
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
    if mode in ('pilot', 'freeze'):
        doc = dict(item=C.ITEM, version='v4-temporal', frames=FRAMES,
                   tolerance=dict(abs_m=TOL_ABS, rel=TOL_REL), gate_fraction=GATE_FRACTION,
                   converge_frames=GATE_FRAMES, seeds=seeds, scenarios=out, gate=gate,
                   PASS=bool(gate['pass_within'] and gate['pass_converged']))
        C.write(C.OUT / ('PILOT_V4.json' if mode == 'pilot' else 'SYNTHETIC_V4.json'), doc)
