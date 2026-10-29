"""Independent delivery consistency checks; writes only new S06 evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import psutil
import s06 as S

EV = S.EV


def measured_diagnostics():
    results = []
    for action in ('candidates', 'calibration'):
        out = EV / ('MEASURED_' + action.upper())
        out.mkdir(exist_ok=False)
        code = ("import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
                "import s06 as S; S.EV=Path(sys.argv[2]); S.W.EV=S.EV; "
                + ('S.diagnose_candidates()' if action=='candidates' else 'S.diagnose_calibration()'))
        command = [sys.executable, '-B', '-W', 'error', '-c', code, str(S.HERE), str(out)]
        start = time.perf_counter(); peak = 0
        with (out/'COMMAND.log').open('xb') as log:
            proc = subprocess.Popen(command, cwd=S.ROOT, stdout=log, stderr=subprocess.STDOUT)
            monitor = psutil.Process(proc.pid)
            while proc.poll() is None:
                try: peak = max(peak, monitor.memory_info().rss)
                except psutil.NoSuchProcess: pass
                if peak > 2147483648 or time.perf_counter()-start > 300:
                    proc.kill(); proc.wait(); raise RuntimeError('diagnostic budget exceeded')
                time.sleep(.05)
        results.append(dict(action=action, command=command, exit_code=proc.returncode,
                            seconds=time.perf_counter()-start, peak_rss_bytes=peak,
                            output=str(out.relative_to(S.ROOT))))
        if proc.returncode != 0: raise RuntimeError('diagnostic process failed: '+action)
    S.write('MEASURED_DIAGNOSTICS.json', results)


def verify():
    old = S.read_frames()
    new = S.read_frames(EV/'ENVELOPE_RUN_R1/frames.jsonl')
    assert len(old)==len(new)==780
    gate = S.W.load(EV/'A_GATE.json')
    gates = {x['fi']: x['variants']['envelope_foreground'] for x in gate['frames']}
    stats = {}; ambiguous_measurements = []
    for name, records, directory in [('main',old,S.OLD), ('envelope_foreground',new,EV/'ENVELOPE_RUN_R1')]:
        action=[]; tail=[]; frame_rows=0; errors=[]
        for fi, r in enumerate(records):
            assert r['fi']==fi and r['coordinate_version']==old[fi]['coordinate_version']
            assert set(['matches','ambiguous_track_ids','ambiguous_candidate_ids','unmatched_track_ids','unmatched_candidate_ids']) <= set(r['association'])
            with np.load(directory/'frames'/('%04d.npz'%fi),allow_pickle=False) as arrays:
                measured=S.candidate_stats(arrays['candidate'],arrays['flags'])
                assert measured['measurable_candidate_count']==r['engine']['candidates_used']
                assert measured['candidate_rows']==r['engine']['accounting']['candidate_member_rows']
                assert len(arrays['flags'])==r['engine']['accounting']['raw']
                frame_rows+=len(arrays['flags'])
                if name=='envelope_foreground' and fi in gates:
                    for key in ('max_candidate_rows','candidate_rows','valid_rows','seed_rows'):
                        assert measured[key]==gates[fi][key], (fi,key)
            best=0
            for tr in r['track_results']:
                assert tr['track_id'] not in r['association']['ambiguous_track_ids']
                if tr['candidate_id'] in r['association']['ambiguous_candidate_ids']:
                    ambiguous_measurements.append(dict(variant=name, fi=fi, track_id=tr['track_id'],
                                                       candidate_id=tr['candidate_id'],association=r['association']))
                raw_valid=sum(n['valid'] for n in tr['nodes'].values())
                assert raw_valid==tr['valid_nodes']
                for n in tr['nodes'].values():
                    if n['valid']: assert n['xyz'] is not None and n['support_n']>=6
                for e in tr['edges']:
                    a,b=e['edge']; na,nb=tr['nodes'][a],tr['nodes'][b]
                    if na['valid'] and nb['valid']:
                        expected=float(np.linalg.norm(np.asarray(na['xyz'])-np.asarray(nb['xyz'])))
                        assert abs(e['measurement']-expected)<1e-12
                    else: assert e['measurement'] is None
                best=max(best,raw_valid)
            assert best==r['best_valid_nodes']
            assert r['skeleton_available']==(best>0)
            if measured['measurable_candidate_count']==0: assert not r['track_results'] and best==0
            if r['phase']=='ACTION': action.append(r)
            if fi>=745: tail.append(r)
        assert frame_rows==38298918
        candidates=sum(r['engine']['candidates_used']>0 for r in action)
        six=sum(r['best_valid_nodes']>=6 for r in action)
        tracks=S.W.load(directory/'TRACKS.json')
        primary=tracks['tracks'][tracks['primary_track']]
        states={}
        for tr in tracks['tracks'].values():
            for e in tr['calibration']['edges'].values(): states[e['state']]=states.get(e['state'],0)+1
        stats[name]=dict(action_frames=len(action),candidate_frames=candidates,six_node_frames=six,
                        candidate_fraction=six/candidates,all_action_fraction=six/len(action),
                        tail_frames=len(tail),tail_six_node_frames=sum(r['best_valid_nodes']>=6 for r in tail),
                        tail_any_node_frames=sum(r['best_valid_nodes']>0 for r in tail),
                        final21_any_node_frames=sum(r['best_valid_nodes']>0 for r in records[759:]),
                        tracks=len(tracks['tracks']),primary_track=tracks['primary_track'],
                        primary_ever_calibrated_edges=primary['calibrated_edge_count'],
                        total_ever_calibrated_edge_tracks=sum(t['calibrated_edge_count'] for t in tracks['tracks'].values()),
                        drift_events=sum(len(t['calibration']['drift_events']) for t in tracks['tracks'].values()),
                        current_edge_state_counts=states,
                        association_ambiguous_frames=sum(bool(r['association']['ambiguous_track_ids']) for r in action),
                        rows=frame_rows)
    fields=S.read_frames(EV/'CANDIDATE_FIELDS.jsonl')
    assert sum(r['phase']=='ACTION' and r['measurable_candidate_count']==0 for r in fields)==107
    classification=S.W.load(EV/'EMPTY_FRAME_CLASSIFICATION.json')
    assert sum(classification['counts'].values())==len(classification['frames'])==107
    drifts=S.W.load(EV/'DRIFT_CLASSIFICATION.json')
    assert sum(drifts['counts'].values())==len(drifts['events'])==163
    assert S.W.load(EV/'STD_RECONCILIATION.json')['PASS']
    # Verify actual population stds from retained episode means, not only stored maxima.
    tracks=S.W.load(S.OLD/'TRACKS.json')
    for tr in tracks['tracks'].values():
        for e in tr['calibration']['edges'].values():
            for ep in e['calibration_episodes']:
                if ep['cross_window_std_m'] is not None:
                    assert abs(float(np.std(ep['window_means']))-ep['cross_window_std_m'])<1e-12
    frozen=S.frozen_from_evidence(S.setup())
    assert frozen.fingerprint()==S.W.FROZEN['m0_map_id']
    assert S.W.sha(S.W.SOURCE/'meta.json')==S.W.FROZEN['meta']
    assert S.W.sha(S.W.SOURCE/'points.bin')==S.W.FROZEN['points']
    S.write('COMPARISON.json', dict(variants=stats,retention_gate_PASS=gate['PASS'],
                                   inherited_node_gate=dict(main=stats['main']['candidate_fraction']>=.8,envelope=stats['envelope_foreground']['candidate_fraction']>=.8),
                                   adopted=False,reason='foreground retention passed its narrow gate; full skeleton coverage/calibration regressed; no selection or gate change',
                                   point_semantics='point-supported regions, all anatomy/identity/effectiveness UNKNOWN'))
    S.write('ASSOCIATION_CONTRACT_FINDING.json',dict(
        counts={name:sum(x['variant']==name for x in ambiguous_measurements) for name in stats},
        records=ambiguous_measurements,status='FAIL_INHERITED_AMBIGUOUS_CANDIDATE_MEASURED',
        root_cause='associate_tracks adds candidates from ambiguous-track pairs to ambiguous_candidate_ids, but its final matches filter only checks track id; wire trusts matches.',
        scope='Frozen association unchanged under S06 plan; no repair or gate change. Not a new claim that historical SK02 is accepted.'))
    S.write('DELIVERY_VERIFICATION.json',dict(PASS=not ambiguous_measurements,frames_checked=1560,raw_node_edge_checks=True,
                                             gate_vs_full_run_exact_frames=len(gates),ledgers_conserved=True,
                                             no_ambiguous_track_measurements=True,
                                             no_ambiguous_candidate_measurements=not ambiguous_measurements,no_display_fill=True,
                                             map_id=frozen.fingerprint(),source_hashes_unchanged=True,
                                             cross_window_formula_recomputed=True))
    # Enrich the two never-calibrated edges with the actual failed state predicates.
    never=S.W.load(EV/'EDGE_DIAGNOSIS.json')['never_calibrated']; primary=tracks['primary_track']
    edge_detail={}
    for key in never:
        snapshots=[e for r in old for tr in r['track_results'] if tr['track_id']==primary for e in tr['edges'] if '|'.join(e['edge'])==key]
        edge_detail[key]=dict(measurement_frames=sum(e['measurement'] is not None for e in snapshots),
                             n_ge_15_frames=sum(e['n']>=15 for e in snapshots),max_samples=max(e['n'] for e in snapshots),
                             enough_n_but_rel_std_fail=sum(e['n']>=15 and e['relative_std'] is not None and e['relative_std']>.05 for e in snapshots),
                             enough_n_but_abs_std_fail=sum(e['n']>=15 and e['sigma'] is not None and e['sigma']>.02 for e in snapshots),
                             max_n_and_stability_pass_frames=sum(e['n']>=15 and e['relative_std'] is not None and e['relative_std']<=.05 and e['sigma']<=.02 for e in snapshots))
    S.write('EDGE_FAILURE_PREDICATES.json',dict(primary_track=primary,edges=edge_detail,interpretation='actual frozen calibration predicates, no intervention or anatomical cause inference'))
    print(json.dumps(stats,ensure_ascii=False))


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='measure': measured_diagnostics()
    else: verify()
