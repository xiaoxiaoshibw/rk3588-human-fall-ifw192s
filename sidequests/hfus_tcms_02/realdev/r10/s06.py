"""S06 preregistered foreground experiment and auditable historical diagnostics.

Only a FrozenMap.match adapter changes numerical semantics. All source data,
prior evidence, defaults, extraction, association and calibration are read-only.
"""
import argparse
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_r1'
SK02 = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1'
OLD = SK02 / 'RUN_R4'
PLAN = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_plan_r1'
R08 = HERE.parent / 'r08'
sys.path.insert(0, str(R08))
import wire as W
W.EV = EV


def write(name, value):
    return W.write_new(EV / name, value)


def setup():
    W.EV = EV
    return W.r01_pipeline()


def read_frames(path=OLD / 'frames.jsonl'):
    with path.open(encoding='utf8') as stream:
        return [json.loads(line) for line in stream]


def foreground_override(points, valid, surface, maximum, noise):
    """Strict z envelope on the same nearest eligible surface, meters/local S3."""
    keep = np.zeros(len(points), dtype=bool)
    rows = np.flatnonzero(valid & (surface >= 0))
    s = surface[rows]
    keep[rows] = ((np.abs(points[rows, 2]) <= 0.10)
                  & (points[rows, 2] > maximum[s, 2] + noise[s, 2]))
    return keep


def envelope_class(pipe):
    class EnvelopeMap(pipe.FrozenMap):
        def match(self, points, valid):
            bg, distance, surface = super().match(points, valid)
            bg[foreground_override(points, valid, surface, self.maximum, self.noise)] = False
            return bg, distance, surface
    return EnvelopeMap


def frozen_from_evidence(pipe):
    """Reuse and fingerprint all original arrays, not a re-fit or future map."""
    doc = W.load(OLD / 'map/MAP.json')
    frozen = object.__new__(pipe.FrozenMap)
    frozen.binding = doc['source_sha256']
    frozen.coordinate = doc['coordinate']
    frozen.protocol = doc['protocol']
    frozen.build = doc['build']
    frozen.map_id = doc['map_id']
    frozen.n = doc['surfaces']
    with np.load(OLD / 'map/surfaces.npz', allow_pickle=False) as arrays:
        frozen.arrays = {key: arrays[key] for key in arrays.files}
    for key, array in frozen.arrays.items():
        setattr(frozen, key, array)
        array.setflags(write=False)
    frozen.tree = cKDTree(frozen.arrays['matching_tree_xyz'])
    if frozen.fingerprint() != W.FROZEN['m0_map_id']:
        raise ValueError('inherited M0 fingerprint mismatch')
    return frozen


def bind_inputs():
    plan = W.load(PLAN / 'INPUT_BASELINE.json')['inputs']
    seals = {}
    for key, row in plan.items():
        if 'dir' not in row:
            continue
        folder = ROOT / row['dir']
        actual = W.sha(folder / 'FINAL_SEAL.json')
        text = (folder / 'FINAL_SEAL.sha256').read_text(encoding='utf8').split()[0]
        seals[key] = dict(expected=row['seal'], actual=actual, text=text,
                          PASS=actual == text == row['seal'])
    files = W.load(SK02 / 'PROTOCOL_V3.json')['reuse_readonly']['files_sha256']
    files.update({str((R08/name).relative_to(ROOT)).replace('\\', '/'): plan['reuse'][key]
                  for name, key in [('calibrate.py', 'sk02_calibrate'), ('wire.py', 'sk02_wire')]})
    # Protocol keys are descriptive aliases; actual paths come from its records.
    reuse = {}
    for key, value in files.items():
        if isinstance(value, dict):
            path, expected = value['path'], value.get('sha256', value.get('sha'))
        else:
            path, expected = key, value
        actual = W.sha(ROOT / path)
        reuse[key] = dict(path=path, expected=expected, actual=actual, PASS=actual == expected)
    source = {key: W.sha(W.SOURCE / name) for key, name in [('meta', 'meta.json'), ('points', 'points.bin')]}
    result = dict(seals=seals, reuse=reuse, source=source,
                  source_PASS=source == plan['source'])
    result['PASS'] = all(x['PASS'] for x in seals.values()) and all(x['PASS'] for x in reuse.values()) and result['source_PASS']
    write('INPUT_CHECK.json', result)
    if not result['PASS']:
        raise ValueError('frozen input mismatch')
    return result


def candidate_stats(candidate, flags):
    ids, counts = np.unique(candidate[candidate >= 0], return_counts=True)
    valid = (flags & 1) != 0
    bg = (flags & 2) != 0
    seeds = (flags & 4) != 0
    if np.any(bg & ~valid) or np.any(seeds != (valid & ~bg)) or np.any((candidate >= 0) & ~valid):
        raise ValueError('ledger partition violated')
    return dict(candidate_rows=int((candidate >= 0).sum()),
                max_candidate_rows=int(max(counts, default=0)),
                measurable_candidate_count=int((counts >= 30).sum()),
                candidate_sizes=[dict(id=int(i), rows=int(n)) for i, n in zip(ids, counts)],
                valid_rows=int(valid.sum()), bg_rows=int(bg.sum()), seed_rows=int(seeds.sum()),
                rejected_seed_rows=int((seeds & (candidate < 0)).sum()))


def diagnose_candidates():
    """First materialize all ledger fields; only then classify empty frames."""
    setup()
    old = read_frames()
    rebuilt = []
    for record in old:
        fi = record['fi']
        with np.load(OLD / 'frames' / ('%04d.npz' % fi), allow_pickle=False) as z:
            stats = candidate_stats(z['candidate'], z['flags'])
            if len(z['flags']) != record['engine']['accounting']['raw']:
                raise ValueError('ledger denominator mismatch')
        if stats['measurable_candidate_count'] != record['engine']['candidates_used']:
            raise ValueError('candidate count mismatch')
        if stats['candidate_rows'] != record['engine']['accounting']['candidate_member_rows']:
            raise ValueError('candidate rows mismatch')
        expected = sorted(c['count'] for c in record['candidate_summaries'])
        actual = sorted(c['rows'] for c in stats['candidate_sizes'] if c['rows'] >= 30)
        if actual != expected:
            raise ValueError('candidate summaries mismatch')
        rebuilt.append(dict(fi=fi, relative_s=record['relative_s'], phase=record['phase'],
                            best_valid_nodes=record['best_valid_nodes'],
                            skeleton_available=record['skeleton_available'], **stats))
    write('CANDIDATE_FIELDS.jsonl', ''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in rebuilt))
    # Read back the materialized evidence before any classification.
    fields = read_frames(EV / 'CANDIDATE_FIELDS.jsonl')
    empties = [r for r in fields if r['phase'] == 'ACTION' and r['measurable_candidate_count'] == 0]
    if len(fields) != 780 or len(empties) != 107:
        raise ValueError('SK02 denominator drift')
    src, times = W.load_source()
    transform = W.r04_transform().Transform(W.load(W.S3 / 'TRANSFORM/TRANSFORM_S3.json'))
    pipe = W.r01_pipeline()
    frozen = frozen_from_evidence(pipe)
    engine = pipe.Engine(frozen, 'main')
    diagnostics = []
    try:
        for item in empties:
            fi = item['fi']
            f = src.frame(fi)
            local = transform.points(f['xyz'], transform.tag(fi, False), fi, source_validity=True)
            rec, ledger, _ = engine.step(dict(f, xyz=local, coordinate_version=transform.version), 'ACTION', qualified=fi >= 271)
            # Engine has no identity track. Skipping frames cannot change groups.
            with np.load(OLD / 'frames' / ('%04d.npz' % fi), allow_pickle=False) as z:
                exact = np.array_equal(ledger['candidate'], z['candidate']) and np.array_equal(ledger['flags'], z['flags'])
            if not exact:
                raise ValueError('diagnostic main differs from SK02 at %d' % fi)
            valid, bg = (ledger['flags'] & 1) != 0, (ledger['flags'] & 2) != 0
            contact = valid & (np.abs(local[:, 2]) <= .10)
            c_rows, c_bg = int(contact.sum()), int((contact & bg).sum())
            noncontact_bg = int((valid & ~contact & bg).sum())
            reasons = Counter()
            for rejected in rec['rejected_unknown_objects']:
                reasons[rejected['reason']] += rejected['count']
            if c_rows and c_bg / c_rows >= .95 and c_bg >= noncontact_bg:
                category = 'near_floor_absorption'
            elif int(bg.sum()) > item['seed_rows']:
                category = 'background_absorption_static_unknown'
            elif any(key in reasons for key in ('EXTENT_OR_REFERENCE_TRANSVERSE', 'POST_GROWTH_SCALE')):
                category = 'range_rejection'
            else:
                category = 'no_group'
            diagnostics.append(dict(**item, category=category, contact_rows=c_rows, contact_bg_rows=c_bg,
                                    noncontact_bg_rows=noncontact_bg, rejected_by_reason=dict(reasons),
                                    replay_exact=exact, static_human_cause='UNKNOWN_NO_GT'))
    finally:
        src.close()
    write('EMPTY_FRAME_CLASSIFICATION.json', dict(total=len(diagnostics), counts=dict(Counter(r['category'] for r in diagnostics)),
                                                 frames=diagnostics, note='observational suppression labels; static human identity unobservable'))
    tail = [dict(fi=r['fi'], candidates=r['engine']['candidates_used'], nodes=r['best_valid_nodes'],
                 ambiguous_candidates=r['association']['ambiguous_candidate_ids']) for r in old[745:]]
    write('PLAN_ERRATA.json', dict(
        old_plan_unchanged=True, tail=tail,
        tail_759_779=dict(no_skeleton=sum(not r['skeleton_available'] for r in old[759:]),
                         no_measurable_candidate=sum(r['engine']['candidates_used'] == 0 for r in old[759:]),
                         candidate_but_ambiguous_frames=[r['fi'] for r in old[759:] if r['engine']['candidates_used'] > 0]),
        empty_action_frames=[r['fi'] for r in empties],
        correction='candidate_summaries are populated on 383 ACTION frames; 759-763 have candidates but association ambiguity; 764-779 have no >=30-row candidate. 107 = 91 early + 16 tail, not 86 + 21.',
        acceptance_note='S06-06 tail consistency is a hypothesis check; disproved premise retained, no thresholds changed'))
    return dict(empty_frames=len(empties), counts=dict(Counter(r['category'] for r in diagnostics)))


def run_gate():
    pipe = setup()
    started = time.perf_counter()
    rss = W.Rss(); rss.start()
    src, times = W.load_source()
    transform = W.r04_transform().Transform(W.load(W.S3 / 'TRANSFORM/TRANSFORM_S3.json'))
    frozen = frozen_from_evidence(pipe)
    variant = object.__new__(envelope_class(pipe))
    variant.__dict__.update(frozen.__dict__)
    engines = dict(main=pipe.Engine(frozen, 'main'), envelope_foreground=pipe.Engine(variant, 'envelope_foreground'))
    frames = []
    try:
        for fi, t in enumerate(times):
            if not (20 <= t < 30 or 745 <= fi <= 779):
                continue
            f = src.frame(fi)
            local = transform.points(f['xyz'], transform.tag(fi, False), fi, source_validity=True)
            row = dict(fi=fi, relative_s=t, variants={})
            for name, engine in engines.items():
                phase = 'TEMPORAL_VALIDATION' if t < 28 else 'EMPTY_AUDIT' if t < 30 else 'ACTION'
                rec, ledger, _ = engine.step(dict(f, xyz=local, coordinate_version=transform.version), phase, qualified=fi >= 271)
                stats = candidate_stats(ledger['candidate'], ledger['flags'])
                stats['foreground_fraction'] = stats['seed_rows'] / stats['valid_rows']
                stats['rejected_by_reason'] = rec['rejected_unknown_objects']
                row['variants'][name] = stats
                if name == 'main':
                    with np.load(OLD / 'frames' / ('%04d.npz' % fi), allow_pickle=False) as z:
                        if not np.array_equal(ledger['candidate'], z['candidate']) or not np.array_equal(ledger['flags'], z['flags']):
                            raise ValueError('gate main differs from original')
            frames.append(row)
            if time.perf_counter() - started > 300 or rss.peak > 2147483648:
                raise RuntimeError('gate probe budget exceeded')
            if fi % 25 == 0:
                print(json.dumps(dict(gate_fi=fi, seconds=round(time.perf_counter()-started, 2))), flush=True)
    finally:
        src.close(); rss.stop = True; rss.join()
    windows = []
    for low, high in [(20, 28), (28, 30)]:
        window = [r for r in frames if low <= r['relative_s'] < high]
        medians = {name: float(np.median([r['variants'][name]['foreground_fraction'] for r in window])) for name in engines}
        delta = medians['envelope_foreground'] - medians['main']
        windows.append(dict(window_s=[low, high], frames=len(window), medians=medians, delta=delta, PASS=delta <= .02))
    tails = {}
    for low in (745, 759):
        subset = [r for r in frames if low <= r['fi'] <= 779]
        tails[str(low)] = {name: dict(frames=len(subset), with_candidate=sum(r['variants'][name]['max_candidate_rows'] >= 30 for r in subset)) for name in engines}
    tail_pass = tails['745']['envelope_foreground']['with_candidate'] >= 21
    result = dict(variant='envelope_foreground', windows=windows, tails=tails, tail_PASS=tail_pass,
                  PASS=all(r['PASS'] for r in windows) and tail_pass,
                  frames=frames, map_id=frozen.fingerprint(), parameter_diff=[],
                  seconds=time.perf_counter()-started, peak_rss_bytes=rss.peak,
                  main_replays_exact=True)
    write('A_GATE.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'frames'}), flush=True)
    return result


def diagnose_calibration():
    setup()
    old = read_frames()
    tracks = W.load(OLD / 'TRACKS.json')
    evaluation = W.load(SK02 / 'REAL_EVALUATION.json')
    primary = tracks['tracks'][tracks['primary_track']]
    by_frame = {(r['fi'], tr['track_id']): tr for r in old for tr in r['track_results']}
    events = []
    for tid, tr in tracks['tracks'].items():
        for drift in tr['calibration']['drift_events']:
            fi = drift['fi']; a, b = drift['edge']
            current = by_frame.get((fi, tid)); previous = by_frame.get((fi-1, tid))
            nodes = {} if current is None else current['nodes']
            supports = {n: nodes.get(n, {}).get('support_n') for n in (a, b)}
            jumps = {}
            if previous is not None:
                for name in (a, b):
                    now, prev = nodes[name], previous['nodes'][name]
                    if now['valid'] and prev['valid']:
                        jumps[name] = float(np.linalg.norm(np.array(now['xyz'])-np.array(prev['xyz'])))
            if not old[fi]['candidate_summaries']:
                category = 'foreground_missing'
            elif any(value is not None and value < 6 for value in supports.values()):
                category = 'support_insufficient'
            elif jumps and max(jumps.values()) > .10:
                category = 'node_jump'
            else:
                category = 'other'
            events.append(dict(track_id=tid, **drift, category=category, endpoint_support=supports,
                               endpoint_displacement_m=jumps, previous_consecutive_measurement=previous is not None,
                               posture_basis='UNKNOWN_NOT_RECORDED', cause='OBSERVATIONAL_ONLY'))
    if len(events) != 163:
        raise ValueError('drift denominator mismatch')
    categories = ['foreground_missing', 'support_insufficient', 'node_jump', 'posture_change', 'other']
    counts = {key: sum(x['category']==key for x in events) for key in categories}
    write('DRIFT_CLASSIFICATION.json', dict(total=len(events), counts=counts, events=events,
                                           remainder=[e for e in events if e['category']=='other'],
                                           posture_classification='UNKNOWN: historical basis not recorded; zero assigned is not absence of posture changes',
                                           fix=None, fix_reason='labels are observational; no verified causal intervention; do not change frozen calibration'))
    never = sorted(set(primary['calibration']['edges']) - set(evaluation['calibrated_edges']))
    support_rows = []
    for r in old:
        if r['phase'] != 'ACTION':
            continue
        for key in never:
            a,b = key.split('|'); tr = by_frame.get((r['fi'], tracks['primary_track']))
            nodes = None if tr is None else tr['nodes']
            support_rows.append(dict(fi=r['fi'], edge=key, primary_matched=tr is not None,
                                     endpoints={name: None if nodes is None else dict(valid=nodes[name]['valid'], support_n=nodes[name]['support_n'], reason=nodes[name]['reason']) for name in (a,b)},
                                     measurement=None if tr is None else next(e['measurement'] for e in tr['edges'] if e['edge']==[a,b])))
    write('UNCALIBRATED_SUPPORT.jsonl', ''.join(json.dumps(x,separators=(',',':'))+'\n' for x in support_rows))
    edges = {}
    for key, value in primary['calibration']['edges'].items():
        matched = [r for r in support_rows if r['edge']==key and r['primary_matched']]
        edges[key] = dict(ever_calibrated=value['ever_calibrated'], final_state=value['state'],
                          first_calibrated_frame=value['first_calibrated_frame'],
                          state_events=[x for x in primary['calibration']['state_events'] if '|'.join(x['edge'])==key],
                          drift_count=sum('|'.join(e['edge'])==key for e in primary['calibration']['drift_events']),
                          never_calibrated_support={} if key not in never else {
                              name: dict(observed_frames=len(matched), valid_frames=sum(r['endpoints'][name]['valid'] for r in matched),
                                         quantiles=np.quantile([r['endpoints'][name]['support_n'] for r in matched],[0,.25,.5,.75,1]).tolist()) for name in key.split('|')})
    write('EDGE_DIAGNOSIS.json', dict(primary_track=tracks['primary_track'], never_calibrated=never, edges=edges,
                                     note='Missing primary measurement is null, not zero support. Calibration variance/drift can fail despite valid supports.'))
    stable_raw = [e['best_calibration_episode']['raw_std_m'] for e in primary['calibration']['edges'].values() if e['best_calibration_episode'] is not None]
    cross = [ep['cross_window_std_m'] for e in primary['calibration']['edges'].values() if e['ever_calibrated'] for ep in e['calibration_episodes'] if ep['cross_window_std_m'] is not None]
    summary = W.load(OLD / 'FRAME_SUMMARY.json')['real_gate']
    reconciliation = dict(
        raw=dict(recomputed=max(stable_raw), recorded=summary['primary_max_stable_calibration_std_m'], formula='max edge best stable episode raw_std_m; stable episode raw std<=.02; best=min raw std', episode_count=len(stable_raw)),
        cross_window=dict(recomputed=max(cross), recorded=evaluation['max_cross_window_std_m'], formula='max cross_window_std_m over all episodes of primary ever-calibrated edges; population std of full nonoverlapping 15-sample window means', episode_count=len(cross)),
        units='m', same_run='RUN_R4', old_files_unchanged=True,
        correction='Different metrics and episode sets; do not call FRAME_SUMMARY raw std a cross-window std. Cross-window smoothness is not anatomical accuracy.')
    reconciliation['PASS'] = reconciliation['raw']['recomputed']==reconciliation['raw']['recorded'] and reconciliation['cross_window']['recomputed']==reconciliation['cross_window']['recorded']
    write('STD_RECONCILIATION.json', reconciliation)
    return dict(drifts=len(events), counts=counts, never_calibrated=never, std=reconciliation)


def run_skeleton():
    if not W.load(EV/'A_GATE.json')['PASS']:
        write('B_STATUS.json', dict(status='BLOCKED', reason='A preregistered gate failed; no B run or stability fix permitted'))
        return
    pipe_loader = W.r01_pipeline
    original_sha = W.sha
    def adapter():
        pipe = pipe_loader()
        base_engine = pipe.Engine
        pipe.FrozenMap = envelope_class(pipe)
        def engine(*args, **kwargs):
            # wire.run passes variant positionally; replace only that variant.
            values = list(args); values[1] = 'envelope_foreground'
            return base_engine(*values, **kwargs)
        pipe.Engine = engine
        return pipe
    W.EV = EV
    W.r01_pipeline = adapter
    def protocol_sha(path):
        p = Path(path)
        return original_sha(EV/'PROTOCOL_V1.json' if p==EV/'PROTOCOL_V3.json' else p)
    W.sha = protocol_sha
    try:
        result = W.run(EV/'ENVELOPE_RUN_R1')
    finally:
        W.r01_pipeline = pipe_loader; W.sha = original_sha
    write('B_STATUS.json', dict(status='SUBMITTED', adapter='import original SK02 wire.run/process_track/calibration, main engine adapter to envelope only',
                                protocol_mapping='wire PROTOCOL_V3 request -> S06 PROTOCOL_V1 hash, no historical protocol copy',
                                main=W.load(OLD/'FRAME_SUMMARY.json'), envelope=result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['inputs', 'candidates', 'gate', 'calibration', 'skeleton'])
    args = parser.parse_args()
    actions = dict(inputs=bind_inputs, candidates=diagnose_candidates, gate=run_gate,
                   calibration=diagnose_calibration, skeleton=run_skeleton)
    actions[args.action]()
