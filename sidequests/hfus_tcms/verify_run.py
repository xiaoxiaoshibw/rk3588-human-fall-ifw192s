"""Verify source membership and causal scores independently of saved summaries."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from run_experiment import ROOT, HERE, load, sha, write
from tcms import support, Window, active


def lines(path):
    with gzip.open(path, 'rt', encoding='utf8') as f:
        for line in f: yield json.loads(line)


def verify(run):
    manifest = json.loads((run/'MANIFEST.json').read_text(encoding='utf8'))
    thresholds = json.loads((run/'THRESHOLDS.json').read_text(encoding='utf8'))
    checks = dict(candidate_regions=0, point_memberships=0, frame_records=0, causal_replayed_frames=0)
    for path, expected in manifest['code'].items():
        if sha(path) != expected: raise ValueError('Executed source drift')
    for sid, expected in manifest['sources'].items():
        meta, xyz, binding = load(ROOT/'data/sessions'/sid)
        if expected != binding: raise ValueError('Data drift')
        for size in manifest['grid']:
            for window in manifest['windows']:
                tag = 'v{}_w{}'.format(size, window)
                for split, (a, b) in manifest['split'][sid].items():
                    path = run/(sid+'_'+tag+'_'+split+'_metrics.jsonl.gz')
                    rows = list(lines(path))
                    if [r['fi'] for r in rows] != list(range(a, b)): raise ValueError('Frame coverage')
                    checks['frame_records'] += len(rows)
                    # Fresh prefix covers startup and first scored frames of every split.
                    state = Window(size, window)
                    for saved in rows[:2*window+2]:
                        frame = meta['frames'][saved['fi']]; start = frame['offset_points']
                        hits, _ = support(xyz[start:start+frame['count_points']], size)
                        actual, status = state.update(hits, saved['time'])
                        if actual != saved['rows'] or status != saved['status']: raise ValueError('Causal replay mismatch')
                        checks['causal_replayed_frames'] += 1
                    predicted = {(r['fi'], tuple(t['tile'])) for r in rows for t in r['rows']
                                 if split not in ('FIT', 'CAL') and active(t, thresholds[tag], 'B3')}
                    found = set()
                    path = run/(sid+'_'+tag+'_'+split+'_members.jsonl.gz')
                    # Reuse the current frame voxelization across all proposed tiles.
                    last_fi, hits = None, None
                    for candidate in lines(path):
                        fi = candidate['frame_index']; key = (fi, tuple(candidate['tile']))
                        if key in found or key not in predicted: raise ValueError('Unexpected/duplicate candidate')
                        found.add(key)
                        frame = meta['frames'][fi]; start = frame['offset_points']
                        if candidate['session_id'] != sid or candidate['frame_offset_points'] != start:
                            raise ValueError('Source identity/offset')
                        if last_fi != fi:
                            hits, _ = support(xyz[start:start+frame['count_points']], size); last_fi = fi
                        ids = np.array(candidate['source_rows'], dtype='<u4')
                        if not np.array_equal(ids, hits[tuple(candidate['tile'])][1]): raise ValueError('Source membership')
                        if hashlib.sha256(ids.tobytes()).hexdigest() != candidate['member_sha256']:
                            raise ValueError('Member hash')
                        if candidate['semantic'] != 'UNKNOWN': raise ValueError('Invented human identity')
                        checks['candidate_regions'] += 1; checks['point_memberships'] += len(ids)
                    if found != predicted: raise ValueError('Missing candidate')
        print('VERIFIED', sid, flush=True)
    write(run/'VERIFICATION.json', dict(checks=checks, state='PASS', verifier_sha256=sha(Path(__file__))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run', type=Path)
    verify(parser.parse_args().run)
