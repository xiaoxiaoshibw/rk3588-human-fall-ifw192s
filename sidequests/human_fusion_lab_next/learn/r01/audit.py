"""Read-only derived evidence; no fitting or threshold selection."""
import argparse
import copy
import sys
from pathlib import Path
import numpy as np
from contracts import ROOT, OLD, PLAN, read, sha, write, Revisions, trusted_labels, label_gate
sys.path.insert(0, str(OLD))
from next_dev import quant, node_metrics
from core import skeleton, sample_points


def probes(e):
    import torch
    spec = __import__('importlib.util', fromlist=['']).spec_from_file_location('deep_routes_probe', ROOT/'sidequests/human_fusion_lab_next/deep_routes/r01/probe.py')
    module = __import__('importlib.util', fromlist=['']).module_from_spec(spec); spec.loader.exec_module(module)
    old = ROOT/'docs/human_capture/evidence/2026-10-15_hfus_next_dev_r1'
    manifest = read(old/'RUN_MANIFEST.json'); sid = 'cap_20261013_082623'; cfg = manifest['config']
    rows = []; previous = None; selected_points = None
    for fi in [194, 195]:
        row = read(old/'runs/B'/sid/f'{fi:04d}.json')
        with np.load(old/'common'/sid/f'{fi:04d}.npz') as d: p = d['xyz'].copy()
        with np.load(old/'runs/B'/sid/f'{fi:04d}_members.npz') as d: ids = d['selected'].copy()
        sk = skeleton(p[ids], ids, cfg)
        metrics = node_metrics(sk, previous, row['body_3d'][0]['id'], row['device_time'], cfg)
        previous = dict(sk=sk, identity=row['body_3d'][0]['id'], t=row['device_time'])
        rows.append(dict(fi=fi, common_sha256=sha(old/'common'/sid/f'{fi:04d}.npz'), **metrics))
        selected_points = p[ids]
    torch.set_num_threads(2); model = module.Shadow(); weight = ROOT/'sidequests/human_fusion_lab/models/pointnet_shadow.pt'
    model.load_state_dict(torch.load(weight, map_location='cpu', weights_only=True), strict=True); model.eval()
    q = sample_points(selected_points); result = []
    for angle in [0, np.pi/2, np.pi]:
        matrix = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
        with torch.no_grad(): result.append(float(model(torch.tensor((q@matrix.T).T[None], dtype=torch.float32)).sigmoid().item()))
    write(e/'INITIAL_PROBES.json', dict(source='ORIGINAL_BOUND_OLD_B_RECOMPUTED_SKELETON_NOT_NEW_WINNER', sid=sid, rows=rows,
                                       yaw_probabilities=result, weight_sha256=sha(weight),
                                       semantic='NOT_ACCURACY; SYNTHETIC_SAME_SOURCE_YAW', axis_missing='counted on full fresh replay; not excluded'))
    print('initial counterexample', rows[-1], result, flush=True)


def summarize(e, target):
    stats = read(target/'ALL_STATS.json'); prs = read(target/'PROJECTION_STATS.json'); summaries = {}
    def aggregate(rows):
        return dict(frames=len(rows), no_candidate=sum(r['selected'] == 0 for r in rows),
                    candidate_without_axis=sum(r['selected'] > 0 and r['axis_missing'] for r in rows),
                    slot_transitions=sum(r['slot_jump_m'] is not None for r in rows), slot_jump_m=quant([r['slot_jump_m'] for r in rows]),
                    selected_total=sum(r['selected'] for r in rows), U=sum(r['U'] for r in rows),
                    CPU_stage_ms=quant([r['stage_cpu_ms'] for r in rows]), wall_stage_ms=quant([r['stage_wall_ms'] for r in rows]),
                    CPU_e2e_ms=quant([r['stage_cpu_ms']+r['shared_cpu_ms'] for r in rows]),
                    wall_e2e_ms=quant([r['stage_wall_ms']+r['shared_wall_ms'] for r in rows]),
                    peak_bytes=max((r['peak_bytes'] for r in rows), default=0))
    common = set.intersection(*[{(r['sid'], r['fi']) for r in rs if r['slot_jump_m'] is not None} for rs in stats.values()])
    for g, rs in stats.items():
        if len(rs) != 2024: raise ValueError('Incomplete full replay')
        summaries[g] = dict(all=aggregate(rs), actions=aggregate([r for r in rs if not r['sid'].startswith('cap_20261014')]),
                            by_session={s:aggregate([r for r in rs if r['sid'] == s]) for s in sorted(set(r['sid'] for r in rs))},
                            by_distance={name:aggregate([r for r in rs if r['distance_m'] is not None and lo <= r['distance_m'] < hi]) for name, lo, hi in [('0_2', 0, 2), ('2_4', 2, 4), ('4plus', 4, float('inf'))]},
                            visibility='UNKNOWN_NOT_ANNOTATED', seed_variation='NOT_RUN_NO_LEARNED_WEIGHTS',
                            common_transitions=aggregate([r for r in rs if (r['sid'], r['fi']) in common]),
                            worst20=sorted([r for r in rs if r['slot_jump_m'] is not None], key=lambda r:r['slot_jump_m'], reverse=True)[:20])
    scan = {}
    for mode in ['range', 'axial']:
        for h in [128, 256]:
            a = [r for r in prs if r['mode'] == mode and r['h'] == h]
            if len(a) != 2024: raise ValueError('Missing representation frames')
            scan[f'{mode}_{h}'] = {k:quant([r[k] for r in a]) for k in ['U', 'in_view', 'outside', 'outside_fraction', 'empty_fraction', 'collisions', 'overflow_K2', 'multi_depth_pixels', 'max_span_m']}
    write(e/(target.name.upper()+'_COMPARE_SUMMARY.json'), dict(geometry=summaries, scan=scan, common_keys=sorted(common),
          decision='NO_ELIGIBLE_MODEL; NO_END_TO_END_WINNER', semantics='BLOCKED_NO_CURRENT_HUMAN_LABELS',
          timing='PC sequential shared preprocessing+both grids+common/projection IO plus one geometry branch including member IO; JSON write excluded; not board FPS',
          source_actions='activity metadata in RUN_MANIFEST sources; not ground truth', primary_weights='NONE',
          selection='NO_TRAINING_NO_SEMANTIC_SELECTION; G0 fixed frozen B',
          equality=read(target/'G0_FROZEN_B_EQUALITY.json')))
    print(target.name, 'summary complete', flush=True)


def reproduce_compare(e):
    first = read(e/'primary/INDEX.json'); second = read(e/'reproduction/INDEX.json')
    mismatches = []; numeric = 0
    for name in first['files']:
        if not name.endswith('.npz'): continue
        with np.load(e/'primary'/name) as a, np.load(e/'reproduction'/name) as b:
            if a.files != b.files: mismatches.append(name+':schema'); continue
            for key in a.files:
                numeric += 1
                if not np.array_equal(a[key], b[key], equal_nan=True): mismatches.append(name+':'+key)
    # JSON timing intentionally differs; measured slots/rows/events/identity must match exactly.
    json_mismatch = []
    for name in first['files']:
        if not name.endswith('.json'): continue
        a = read(e/'primary'/name); b = read(e/'reproduction'/name)
        for key in ['stage_wall_ms', 'stage_cpu_ms', 'shared_wall_ms', 'shared_cpu_ms', 'peak_bytes']:
            a.pop(key, None); b.pop(key, None)
        if a != b: json_mismatch.append(name)
    write(e/'REPRODUCTION_COMPARISON.json', dict(status='PASS' if not mismatches+json_mismatch else 'FAIL',
                                               geometry_frames_per_run=8096, source_frames_per_run=2024,
                                               array_comparisons=numeric, mismatches=mismatches, json_mismatches=json_mismatch,
                                               learned_main_reproduction='BLOCKED_NO_MAIN_WEIGHTS',
                                               note='Actual current-source recomputation; no copied primary members'))
    if mismatches or json_mismatch: raise ValueError('Reproduction mismatch')


def labels(e):
    manifest = read(e/'RUN_MANIFEST.json'); tasks = read(e/'ANNOTATION_TASKS.json')
    store = Revisions(e/'labels'); rows = {}; records = {}
    index = read(e/'primary/INDEX.json')
    for task in tasks:
        if task['kind'] != 'CORE': continue
        key = task['sid'], task['fi']; name = f'common/{key[0]}/{key[1]:04d}.npz'
        path = e/'primary'/name
        if sha(path) != index['files'][name]: raise ValueError('Label audit input drift')
        with np.load(path) as d: rows[key] = np.flatnonzero(d['U'])
        records[key] = store.records(*key)
        if any(rec['source_sha256'] != manifest['sources'][key[0]]['sha256'] for rec in records[key]):
            raise ValueError('Label source drift')
    from uuid import uuid4
    report = label_gate(tasks, rows, records)
    report['revision_sha256'] = {p.name:sha(p) for p in (e/'labels').glob('*.json')}
    report['run_manifest_sha256'] = sha(e/'RUN_MANIFEST.json')
    write(e/('LABEL_AUDIT_'+uuid4().hex+'.json'), report)
    print(report['status'], 'primary', report['primary_reviewed'], 'second', report['second_reviewed'], flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['probes', 'summary', 'compare', 'labels']); p.add_argument('--evidence', type=Path, required=True); p.add_argument('--target', type=Path)
    a = p.parse_args()
    if a.phase == 'summary': summarize(a.evidence, a.target)
    elif a.phase == 'compare': reproduce_compare(a.evidence)
    elif a.phase == 'labels': labels(a.evidence)
    else: probes(a.evidence)
