"""LOCAL-INDOOR-LIDAR-01: source-bound R1 diagnostics, no training."""
import os
for _name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[_name] = '4'
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import numpy as np
import psutil
from scipy.spatial import cKDTree
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E = ROOT/'docs/human_capture/evidence/2026-10-15_local_indoor_lidar_phase1_r1'
OLD = ROOT/'sidequests/human_fusion_lab_next/pointset/r01'
PRIOR = ROOT/'docs/human_capture/evidence/2026-10-15_hfus_learn_dev_r2'
sys.path.insert(0, str(OLD))
from core import R, T, cluster, roi_mask
from actions import choose
from next_contract import validate_meta

REASONS = ['INVALID_OR_RANGE', 'OUTSIDE_Z', 'BACKGROUND', 'NOISE_OR_SMALL_CLUSTER', 'UNSELECTED_CLUSTER', 'SELECTED_UNKNOWN']

def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()

def write(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8') as f:
        json.dump(obj, f, ensure_ascii=False, allow_nan=False, indent=2)

def sources():
    return {str(p): sha(p) for p in list(HERE.glob('*.py')) + list(HERE.glob('*.js')) + list(HERE.glob('*.html')) + list(HERE.glob('*.bat'))}

def check_hashes(mapping):
    for p, digest in mapping.items():
        if sha(p) != digest:
            raise ValueError('CONTENT_DRIFT: '+p)

def paths(sid):
    return ROOT/'captures/remote'/sid/'meta.json', ROOT/'captures/remote'/sid/'points.bin'

def mapped(sid, expected):
    mpath, ppath = paths(sid)
    if {'meta': sha(mpath), 'points': sha(ppath)} != expected:
        raise ValueError('SOURCE_DRIFT '+sid)
    m = read(mpath); validate_meta(m, ppath.stat().st_size)
    if m['session_id'] != sid:
        raise ValueError('Session identity mismatch')
    buf = np.memmap(ppath, dtype='u1', mode='r')
    xyz = np.ndarray((m['total_points'], 3), dtype='<f4', buffer=buf, strides=(28, 4))
    intensity = np.ndarray((m['total_points'],), dtype='<f4', buffer=buf, offset=12, strides=(28,))
    return m, xyz, intensity

def transform(q, reg):
    p = q.astype('f8')@R.T+T
    if reg is not None:
        p = p@np.asarray(reg['R']).reshape(3, 3).T+reg['t']
    return p

def run_frame(q, p, tree, cfg, tau, state, stamp):
    """Instrument frozen functions, retaining every original frame-local row."""
    times = {}; start = time.process_time()
    radius = np.linalg.norm(q, axis=1)
    valid = np.isfinite(q).all(1) & np.any(q != 0, axis=1) & (radius > cfg['range_min_m']) & (radius < cfg['range_max_m'])
    dom = valid & (p[:, 2] >= cfg['z_min_m']) & (p[:, 2] <= cfg['z_max_m'])
    code = np.zeros(len(q), dtype='u1'); code[valid] = 1; code[dom] = 2
    times['preprocess'] = (time.process_time()-start)*1000; start = time.process_time()
    dist = np.full(len(q), np.inf); dist[dom] = tree.query(p[dom], workers=1)[0]
    fg = np.flatnonzero(dom & (dist > tau)); code[fg] = 3
    times['background'] = (time.process_time()-start)*1000; start = time.process_time()
    groups, _ = cluster(p[fg], cfg)
    labels = np.full(len(q), -1, dtype='i4')
    for i, g in enumerate(groups):
        labels[fg[g]] = i; code[fg[g]] = 4
    times['cluster'] = (time.process_time()-start)*1000; start = time.process_time()
    reset = ((state['t'] is not None and (stamp <= state['t'] or stamp-state['t'] > cfg['max_gap_s'])) or
             (state['seen'] is not None and stamp-state['seen'] > cfg['max_gap_s']))
    if reset:
        state['last'] = state['seen'] = None
    winner = choose(groups, p, fg, cfg, state['last'], None)
    selected = winner[1] if winner is not None else None
    if winner is not None:
        code[fg[groups[selected]]] = 5
        state['last'], state['seen'] = winner[2][:2], stamp
    state['t'] = stamp
    candidates = []
    for i, g in enumerate(groups):
        ids = fg[g]; x = p[ids]; lo, hi = np.quantile(x, [.02, .98], axis=0)
        rejected = []
        if len(g) < cfg['person_min_points']: rejected.append('POINTS_LT_PERSON_MIN')
        if roi_mask(x, cfg['roi_xy']).mean() < cfg['person_min_roi_fraction']: rejected.append('ROI_FRACTION')
        if max(hi-lo) > cfg['person_max_span_m']: rejected.append('SPAN')
        if np.quantile(x[:, 2], .9) < cfg['person_min_p90_m']: rejected.append('P90_HEIGHT')
        candidates.append(dict(id=i, count=len(ids), min=x.min(0).tolist(), max=x.max(0).tolist(),
            selected=i == selected, static_filter_reasons=rejected, semantic='UNKNOWN',
            source_row_min=int(ids.min()), source_row_max=int(ids.max()),
            member_sha256=hashlib.sha256(ids.astype('<u4').tobytes()).hexdigest()))
    times['selection'] = (time.process_time()-start)*1000
    if not np.all((code <= 5) & ((labels >= 0) == (code >= 4))):
        raise ValueError('Source row conservation')
    return code, labels, candidates, times, reset

def prepare():
    prior = read(PRIOR/'RUN_MANIFEST.json'); pre = read(PRIOR/'DATA_PREFLIGHT.json')
    approved = [x['sid'] for x in pre['checks']]
    if len(approved) != 9:
        raise ValueError('Unexpected manifest inventory')
    assets = {x['path']: x['sha256'] for x in prior['backgrounds']}
    assets.update(prior['transforms']); check_hashes(assets)
    records = {}; historical = []
    for rec in pre['checks']:
        sid = rec['sid']; m, q, intensity = mapped(sid, rec['sha256'])
        finite = np.isfinite(intensity)
        records[sid] = dict(sha256=rec['sha256'], frames=len(m['frames']), bytes=paths(sid)[1].stat().st_size,
            available=prior['split']['empty_report'] if sid == prior['split']['empty_sid'] else list(range(len(m['frames']))),
            acquisition_group='UNRESOLVED_ALL', prior_development_exposure=True,
            intensity=dict(finite=int(finite.sum()), total=len(intensity), min=float(intensity[finite].min()), max=float(intensity[finite].max())),
            layout=m['point_layout'])
        for ann in m.get('human_annotations', []):
            historical.append(dict(sid=sid, metadata=ann, status='UNVERIFIED_HISTORY_NOT_GT', reason='No current named review/source-row quality evidence'))
        print('SOURCE VERIFIED', sid, len(m['frames']), flush=True)
    manifest = dict(schema='local-indoor/1', run_id='R1_LOCAL_20261015', sources=records, cfg=prior['cfg'],
        algorithm='R1_LEGACY_NO_CLASSIFIER', cfg_id='R1_FROZEN_FROM_E0', tau=prior['old_tau'], background=prior['backgrounds'][0],
        assets=assets, R=R.tolist(), T=T.tolist(), empty_sid=prior['split']['empty_sid'], empty_split={k:v for k,v in prior['split'].items() if k.startswith('empty')},
        authorization='2026-10-15 user: 批准这九段，沿用原边界', code=sources(),
        prior_manifest_sha256=sha(PRIOR/'RUN_MANIFEST.json'), reasons=REASONS,
        coordinate='raw XYZ meters -> R/T -> frozen per-session registration; nominal, physical calibration unverified',
        models=dict(RF='NOT_RUN_CONTRACT_NOT_QUALIFIED', neural='NOT_RUN_NO_TRAINING_AUTHORIZATION'),
        split=dict(train=[], validation=[], test=[], diagnostic='ALL_AVAILABLE', trusted_groups=0, reason='Acquisition/person/scene independence unresolved; all previously development exposed'),
        limits=dict(compute_threads=4, target_rss=8*1024**3, stop_rss=12*1024**3, output_bytes=512*1024**2))
    write(E/'RUN_MANIFEST.json', manifest)
    write(E/'HISTORICAL_LABEL_AUDIT.json', dict(records=historical, trusted_human_reviews=0, policy='Do not promote metadata or AI proposals'))
    queue = []
    for sid, rec in records.items():
        if sid == manifest['empty_sid']: continue
        for index in np.linspace(0, len(rec['available'])-1, 3, dtype=int):
            fi = rec['available'][index]
            queue.append(dict(sid=sid, fi=fi, status='PENDING_REAL_HUMAN', source_sha256=rec['sha256'],
                requested_coverage=['posture', 'distance/density', 'occlusion', 'furniture_contact', 'fragmentation', 'two_people'],
                observed_coverage='UNKNOWN_UNTIL_HUMAN_REVIEW', selection='Fixed first/middle/last, no GT or semantic cherry picking'))
    write(E/'REVIEW_QUEUE.json', dict(tasks=queue, real_human_reviews=0, missing_conditions='UNKNOWN: not inferred from session names'))
    print('PREPARE COMPLETE', flush=True)

def replay(target):
    m = read(E/'RUN_MANIFEST.json'); check_hashes(m['code']); check_hashes(m['assets'])
    target.mkdir(parents=True, exist_ok=False)
    stop = threading.Event(); peak = [0]; process = psutil.Process()
    def monitor():
        while not stop.wait(.05):
            rss = process.memory_info().rss; peak[0] = max(peak[0], rss)
            if rss >= m['limits']['stop_rss']:
                os._exit(12)
    watcher = threading.Thread(target=monitor, daemon=True); watcher.start()
    with np.load(m['background']['path']) as d: tree = cKDTree(d['xyz'])
    ledger = []; signatures = []; duplicate = collections.defaultdict(list); artifacts = {}; summary = []
    try:
        with threadpool_limits(limits=4):
            for sid, source in m['sources'].items():
                meta, raw, _ = mapped(sid, source['sha256']); state = dict(last=None, seen=None, t=None)
                reg = None if sid == m['empty_sid'] else read(Path(m['cfg']['background_experiment'])/(sid+'_registration.json'))
                if reg and reg['gate']['status'] != 'PASS': raise ValueError('Registration gate')
                folder = target/sid; folder.mkdir()
                for fi in source['available']:
                    started = time.perf_counter(); cpu = time.process_time(); f = meta['frames'][fi]
                    q = raw[f['offset_points']:f['offset_points']+f['count_points']].copy()
                    p = transform(q, reg); transform_ms = (time.process_time()-cpu)*1000
                    code, labels, candidates, times, reset = run_frame(q, p, tree, m['cfg'], m['tau'], state, f['stamp_sec']+f['stamp_nanosec']*1e-9)
                    key = sid+'/'+str(fi); path = folder/(str(fi)+'.npz')
                    # Exact raw28 frame digest, not just XYZ; no raw cloud copied to outputs.
                    with paths(sid)[1].open('rb') as stream:
                        stream.seek(f['offset_points']*28); frame_sha = hashlib.sha256(stream.read(f['count_points']*28)).hexdigest()
                    duplicate[frame_sha].append(key)
                    # Only queue frames: conservative near-duplicate screen; never evidence of independence.
                    if any(t['sid'] == sid and t['fi'] == fi for t in read(E/'REVIEW_QUEUE.json')['tasks']):
                        finite = p[np.isfinite(p).all(1)]
                        cells = np.unique(np.floor(finite/.15).astype('i4'), axis=0)
                        signatures.append((key, set(map(tuple, cells.tolist()))))
                    np.savez_compressed(path, terminal=code, cluster=labels)
                    digest = sha(path); artifacts[path.relative_to(target).as_posix()] = digest
                    row = dict(sid=sid, fi=fi, run=m['run_id'], source_sha256=source['sha256'], source_frame=f, frame_bytes_sha256=frame_sha,
                        raw_count=len(q), terminal_counts=np.bincount(code, minlength=6).tolist(), candidates=candidates,
                        status='PENDING_HUMAN_REVIEW', K=0, semantic_metrics=None, reset=reset, artifact_sha256=digest,
                        cpu_ms=dict(transform_read=transform_ms, **times), wall_ms=(time.perf_counter()-started)*1000,
                        peak_rss_bytes=peak[0], exclusion='No current trusted human/point/box GT; not a success or failure',
                        selection_reason='Single causal ROI winner; unselected eligible clusters may lose by rank/association')
                    write(folder/(str(fi)+'.json'), row); artifacts[(folder/(str(fi)+'.json')).relative_to(target).as_posix()] = sha(folder/(str(fi)+'.json'))
                    ledger.append(dict(sid=sid, fi=fi, frame_bytes_sha256=frame_sha, counts=row['terminal_counts'], candidates=len(candidates),
                        selected_points=row['terminal_counts'][5], status=row['status'], cpu_ms=row['cpu_ms'], wall_ms=row['wall_ms'], exclusion=row['exclusion']))
                    if fi % 80 == 0: print('FRAME', sid, fi, 'RSS MiB', round(peak[0]/1024**2), flush=True)
                    if len(ledger) % 50 == 0:
                        total = sum(p.stat().st_size for base in [HERE, E] for p in base.rglob('*') if p.is_file())
                        if total > 500*1024**2: raise ValueError('Output budget stop before 512MiB')
                check_hashes({str(paths(sid)[0]):source['sha256']['meta'], str(paths(sid)[1]):source['sha256']['points']})
                summary.append(dict(sid=sid, frames=len(source['available'])))
                print('SESSION COMPLETE', sid, flush=True)
        near = []
        for i, (a, sa) in enumerate(signatures):
            for b, sb in signatures[:i]:
                j = len(sa & sb)/max(1, len(sa | sb))
                if j >= .8: near.append(dict(a=a, b=b, room_voxel_jaccard=j, status='PENDING_NOT_IDENTITY_OR_INDEPENDENCE'))
        write(target/'DUPLICATES.json', dict(exact=[v for v in duplicate.values() if len(v)>1], near_queue_pairs=near,
            near_scope='24 fixed queue frames, all pairs; full2024 exact raw28 hashes', split_leakage='No train/val/test; all unresolved single diagnostic group'))
        write(target/'FRAME_LEDGER.json', ledger)
        write(target/'INDEX.json', dict(manifest_sha256=sha(E/'RUN_MANIFEST.json'), artifacts=artifacts, sessions=summary, frames=len(ledger), peak_rss_bytes=peak[0]))
    finally:
        stop.set(); watcher.join()
    print('REPLAY COMPLETE', len(ledger), 'peak', peak[0], flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'replay']); parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    if args.phase == 'prepare': prepare()
    else: replay(args.target or E/'baseline_r1')
