"""Frozen corpus runner; exclusive new outputs. Actual human GT is a separate sidecar."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from record import OUT, ROOT, sha, save
from skeleton import process, minimum_gt, SkeletonTracker, unknown, SLOTS

def read(p):
    return json.loads(Path(p).read_text('utf8'))

def freeze(args):
    files = ['input_manifest.json', 'split_manifest.json', 'prototype_params_v1.json', 'CONTRACT.md',
             'skeleton.py', 'run_offline.py', 'bind_inputs.js']
    obj = {'version': 1, 'algorithm_not_yet_run': True, 'files': {n: sha(OUT/n) for n in files},
           'python': sys.version, 'numpy': np.__version__, 'python_executable': sys.executable,
           'parameter_calibration': 'BLOCKED_GT; conservative predeclared tool defaults; no validation tuning'}
    save(OUT/args.freeze, obj)
    print('FROZEN', obj['files'])

def run(args):
    frozen = read(OUT/args.freeze)
    for n, h in frozen['files'].items():
        if sha(OUT/n) != h:
            raise ValueError('FROZEN_SHA_MISMATCH: '+n)
    manifest = read(OUT/'input_manifest.json')
    params = read(OUT/'prototype_params_v1.json')
    gt = read(args.gt) if args.gt else read(OUT/'identity_gt.json')
    if args.gt:
        subprocess.run(['node', '--max-old-space-size=8192', str(OUT/'bind_inputs.js'), 'validate', str(Path(args.gt).resolve())], check=True, cwd=str(ROOT))
    elif gt['source'] != 'unreviewed' or gt['records']:
        raise ValueError('EXPLICIT_VALIDATED_GT_ARGUMENT_REQUIRED')
    gate = minimum_gt(gt['records'], manifest['entries'])
    reviews = {r['id']: r for r in gt['records']}
    out = OUT/args.out
    if out.parent != OUT or not args.out.replace('_', '').isalnum():
        raise ValueError('NEW_OUTPUT_DIRECTORY_REQUIRED')
    out.mkdir()
    run_binding = {'input_sha256': sha(OUT/'input_manifest.json'), 'params_sha256': sha(OUT/'prototype_params_v1.json'),
                   'source_sha256': sha(OUT/'skeleton.py'), 'runner_sha256': sha(OUT/'run_offline.py'),
                   'freeze_sha256': sha(OUT/args.freeze), 'identity_gt_sha256': sha(Path(args.gt) if args.gt else OUT/'identity_gt.json')}
    trackers = {}
    durations = []
    totals = {'unique_raw_frames': 100, 'branch_rows': 120, 'reviewed_clusters': len(reviews),
              'person_clusters': sum(r['label'] == 'PERSON' for r in reviews.values()), 'valid_nodes': 0,
              'unknown_nodes': 0, 'no_cluster_branch_rows': 0, 'unreviewed_clusters': 0,
              'node_gt': {k: {'VISIBLE': 0, 'INVISIBLE': 0, 'UNCERTAIN': 0, 'UNREVIEWED': 0, 'valid': 0, 'unknown': 0, 'visible_missed': 0, 'region_reference_errors_m': []} for k in SLOTS}}
    with (out/'normalized_frames.jsonl').open('x', encoding='utf8') as nf, (out/'nodes_raw.jsonl').open('x', encoding='utf8') as rf, (out/'nodes_filtered.jsonl').open('x', encoding='utf8') as ff:
        for entry in manifest['entries']:
            if sha(OUT/entry['file']) != entry['sha256']:
                raise ValueError('FRAME_SHA_MISMATCH: '+entry['id'])
            frame = read(OUT/entry['file'])
            base = {k: frame[k] for k in ['id', 'sid', 'branch', 'ordinal', 'coordinate_id', 'split']}
            base.update({k: frame['source_frame'][k] for k in ['seq', 'stamp_sec', 'stamp_nanosec']})
            normalized, raw_records, filtered = [], [], []
            start = time.perf_counter()
            for member in frame['clusters']:
                receipt = member['receipt']
                r = reviews.get(receipt['id'])
                label = r['label'] if r else 'UNREVIEWED'
                if not r:
                    totals['unreviewed_clusters'] += 1
                norm, raw = process(member, label, r['nodes'] if r else {}, params, gate['satisfied'])
                common = {'receipt': receipt, 'identity_source': 'MANUAL_GT_FIXTURE' if r else 'UNREVIEWED',
                          'person_id': r.get('person_id') if r else None, 'reviewer': gt['reviewer'] if r else None,
                          'track_epoch': r['track_epoch'] if r else None, 'label': label, 'run_binding': run_binding}
                normalized.append({**common, 'status': 'NORMALIZED' if norm is not None else 'BLOCKED_GT' if label in ['PERSON', 'UNREVIEWED'] else 'REJECT_'+label, 'normalized': norm})
                raw_records.append({**common, 'nodes': raw})
                tracker_frame = {**base, **{k: common[k] for k in ['person_id', 'track_epoch']}}
                tk = (frame['sid'], frame['branch'], common['person_id'], common['track_epoch'])
                tracker = trackers.setdefault(tk, SkeletonTracker(params))
                filtered.append({**common, **tracker.tick(tracker_frame, raw)})
                for name, node in raw.items():
                    totals['valid_nodes' if node['valid'] else 'unknown_nodes'] += 1
                    if name in totals['node_gt']:
                        m = totals['node_gt'][name]
                        v = r['nodes'][name]['visibility'] if r else 'UNREVIEWED'
                        m[v] += 1
                        m['valid' if node['valid'] else 'unknown'] += 1
                        if v == 'VISIBLE' and not node['valid']:
                            m['visible_missed'] += 1
                        if v == 'VISIBLE' and node['valid']:
                            rows = set(r['nodes'][name]['region_rows'])
                            reference = np.median(np.array([q for row, q in zip(receipt['rows'], member['xyz']) if row in rows]), axis=0)
                            m['region_reference_errors_m'].append(float(np.linalg.norm(reference-np.array(node['xyz']))))
            durations.append(time.perf_counter()-start)
            if not frame['clusters']:
                totals['no_cluster_branch_rows'] += 1
            for handle, records in [(nf, normalized), (rf, raw_records), (ff, filtered)]:
                handle.write(json.dumps({**base, 'status': 'NO_CLUSTER' if not records else 'BLOCKED_GT' if not gate['satisfied'] else 'REVIEWED_RUN', 'records': records, 'run_binding': run_binding}, allow_nan=False)+'\n')
    save(out/'metrics.json', {'counts': totals, 'minimum_real_gt_gate': gate,
         'actual_node_effect': 'BLOCKED_GT' if not gate['satisfied'] else 'SEE_NODE_GT',
         'region_error_status': 'BLOCKED_GT' if not gt['records'] else 'REGION_ONLY_NOT_JOINT_ACCURACY',
         'jump_missing_recovery_real': 'BLOCKED_GT' if not gate['satisfied'] else 'SEE_FILTERED_RECORDS',
         'empty_control_valid_person_nodes': 0 if not reviews else 'inspect nodes_raw',
         'timing_scope': 'geometry+tracker/rejection only, excludes binding hash/raw IO; not board performance',
         'runtime_per_branch_row_s': {'median': float(np.median(durations)), 'max': max(durations)},
         'run_binding': run_binding})
    save(out/'digests.json', {n: sha(out/n) for n in ['normalized_frames.jsonl', 'nodes_raw.jsonl', 'nodes_filtered.jsonl']})
    print(json.dumps({'out': args.out, 'gate': gate, 'counts': {k:v for k,v in totals.items() if k != 'node_gt'}}))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['freeze', 'run'])
    parser.add_argument('--out', default='pass1')
    parser.add_argument('--gt')
    parser.add_argument('--freeze', default='freeze_r3.json')
    arguments = parser.parse_args()
    freeze(arguments) if arguments.action == 'freeze' else run(arguments)
