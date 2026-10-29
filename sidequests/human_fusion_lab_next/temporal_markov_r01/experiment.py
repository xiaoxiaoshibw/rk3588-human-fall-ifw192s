"""Read immutable E0 candidates; recompute features/RF; run fixed offline A/B."""
import argparse
import copy
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
import numpy as np
from temporal import Track, HMM, HSMM, geometry, sequence, POSTURES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT/'docs/human_capture/evidence/2026-10-15_hfus_learn_dev_r2'
EVIDENCE = ROOT/'docs/human_capture/evidence/2026-10-15_hfus_markov_r01'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write(p, value):
    with Path(p).open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def stats(v):
    return None if not v else dict(mean=float(np.mean(v)), p50=float(np.quantile(v, .5)), p95=float(np.quantile(v, .95)), max=float(max(v)))


def summarize(rows, outputs):
    result = {}
    for name in ['baseline', 'ema', 'vote', 'hysteresis', 'mc', 'presence', 'posture', 'offline_viterbi', 'event']:
        values = []
        for o in outputs:
            v = o[name]
            values.append(int(np.argmax(v)) if isinstance(v, list) else v)
        switches = eligible = 0
        previous = {}
        for value, b in zip(values, outputs):
            key = b['sid'], b['track_id']
            prior = previous.get(key)
            if prior is not None and value is not None and not b['reset']:
                eligible += 1; switches += value != prior
            previous[key] = value
        result[name] = dict(switches=int(switches), eligible_transitions=eligible,
                            unknown_frames=sum(v is None or v in ['UNKNOWN'] or (name in ['mc', 'presence'] and v == 2) or (name == 'posture' and v == 5) for v in values),
                            positive_frames=sum(v is True or (name in ['mc', 'presence'] and v == 0) for v in values))
    result['candidates'] = sum(o['candidate'] for o in outputs)
    result['missing'] = sum(o['missing'] for o in outputs)
    result['weak'] = sum(r['feature'] is not None and (r['feature']['count'] < 100 or r['feature']['tilt_deg'] is None) for r in rows)
    result['semantic_metrics'] = 'BLOCKED_NO_REVIEWED_HUMAN_POSTURE_EVENT_GT'
    return result


def extract(out):
    old = read(OLD/'RUN_MANIFEST.json'); index = read(OLD/'primary/INDEX.json')['files']
    bindings = {}; sources = {}; sessions = []; allrows = []
    def bound(p):
        relative = p.relative_to(OLD/'primary').as_posix()
        digest = sha(p)
        if digest != index[relative]:
            raise ValueError('E0 member drift: '+relative)
        bindings[str(p.relative_to(ROOT)).replace('\\', '/')] = digest
    rfproc = subprocess.Popen(['node', str(HERE/'rf_batch.js')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf8')
    try:
        for sid, source in old['sources'].items():
            folder = ROOT/'captures/remote'/sid
            meta = read(folder/'meta.json'); binfile = folder/'points.bin'
            hashes = dict(meta=sha(folder/'meta.json'), points=sha(binfile))
            if hashes != source['sha256'] or meta['point_stride_bytes'] != 28 or binfile.stat().st_size != meta['total_points']*28:
                raise ValueError('Source binding/layout changed '+sid)
            times = [f['stamp_sec']+f['stamp_nanosec']*1e-9 for f in meta['frames']]
            if np.any(np.diff(times) <= 0):
                raise ValueError('Nonmonotonic source')
            end = 0
            for f in meta['frames']:
                if f['offset_points'] != end or f['count_points'] < 0:
                    raise ValueError('Frame boundary')
                end += f['count_points']
            if end != meta['total_points']:
                raise ValueError('Point count')
            raw = np.memmap(binfile, dtype='u1', mode='r')
            intensity = np.ndarray((end,), dtype='<f4', buffer=raw, offset=12, strides=(28,))
            files = sorted((OLD/'primary/runs/G0'/sid).glob('*.json'))
            last_id = 'NO_TRACK'; sessionrows = []
            for path in files:
                bound(path); row = read(path); fi = row['fi']
                member = path.with_suffix('.npz'); common = OLD/'primary/common'/sid/member.name
                bound(member); bound(common)
                with np.load(member) as data:
                    mask = data['selected'].copy(); clusters = data['cluster'].copy()
                if not np.isin(mask, [0, 1]).all():
                    raise ValueError('Nonbinary membership')
                mask = mask.astype(bool)
                with np.load(common) as data:
                    xyz = data['corrected'][mask].copy()
                    if len(mask) != len(data['corrected']) or mask.dtype != bool:
                        raise ValueError('Invalid membership')
                ids = np.flatnonzero(mask)
                if len(ids) != row['selected'] or row['source'] != hashes or row['time'] != times[fi]:
                    raise ValueError('Frame binding')
                it = intensity[meta['frames'][fi]['offset_points']+ids]
                if not np.isfinite(it).all():
                    raise ValueError('Nonfinite intensity, do not replace with zero')
                points = np.column_stack((xyz, it))
                rfproc.stdin.write(json.dumps(dict(points=points.tolist()), allow_nan=False)+'\n'); rfproc.stdin.flush()
                rf = json.loads(rfproc.stdout.readline())
                if row['identity'] is not None:
                    last_id = row['identity']
                feature = geometry(xyz)
                record = dict(sid=sid, fi=fi, time=times[fi], track_id=last_id, candidate_id=row['identity'],
                              source_frame=meta['frames'][fi], source_sha256=hashes,
                              selected_indices_sha256=hashlib.sha256(ids.astype('<u4').tobytes()).hexdigest(),
                              source_count=len(mask), selected_count=len(ids), cluster_count=row['clusters'],
                              candidate_valid=bool(len(ids)), association_confidence=None, completeness=None,
                              feature=feature, rf=rf['rf'], rf_ms=rf['ms'],
                              points=xyz[np.linspace(0, len(xyz)-1, min(len(xyz), 900), dtype=int)].tolist() if len(xyz) else [])
                sessionrows.append(record)
            sdir = out/sid; sdir.mkdir(); write(sdir/'features.json', sessionrows)
            sources[sid] = dict(sha256=hashes, frames=len(sessionrows), total_source_frames=len(times),
                                dt_s=stats(np.diff(times).tolist()), measured_hz=1/float(np.median(np.diff(times))),
                                source_annotations=len(meta.get('human_annotations', [])), stride=28)
            sessions.append(dict(sid=sid, frames=len(sessionrows), first=sessionrows[0]['fi'],
                                 empty=sid.startswith('cap_20261014'), role=old['split'].get('classification', 'PREVIOUS_DEVELOPMENT_EXPOSED')))
            allrows.extend(sessionrows)
            print(sid, len(sessionrows), 'features, observed', sum(x['feature'] is not None for x in sessionrows), flush=True)
    finally:
        rfproc.stdin.close(); rfproc.wait(timeout=15)
        rfproc.stdout.close()
        if rfproc.returncode:
            raise RuntimeError('RF child failed')
    write(out/'catalog.json', sessions)
    labelpaths = list((OLD/'labels').glob('*.json'))
    write(out/'INPUT_MANIFEST.json', dict(sources=sources, bindings=bindings, previous_manifest_sha256=sha(OLD/'RUN_MANIFEST.json'),
                                         previous_index_sha256=sha(OLD/'primary/INDEX.json'), current_label_files={str(p):sha(p) for p in labelpaths},
                                         labels=read(OLD/'LABEL_MANIFEST.json'), training='NOT_RUN_FIXED_RULE_PARAMETERS',
                                         split=old['split'], candidate_chain='E0 immutable G0, no re-association',
                                         python=platform.python_version(), numpy=np.__version__,
                                         source_fields='XYZ float32@0/4/8, intensity float32@12, stride28; remaining bytes uninterpreted'))
    return allrows


def run(out, features_from=None):
    cfg = read(HERE/'config.json')
    write(out/'FROZEN_CONFIG.json', cfg)
    if features_from is None:
        rows = extract(out)
    else:
        # Explicit reuse of exact frozen feature bytes, never a claim of fresh extraction.
        manifest = read(features_from/'INPUT_MANIFEST.json')
        reused = {}
        for n in ['catalog.json','INPUT_MANIFEST.json']:
            (out/n).write_bytes((features_from/n).read_bytes())
            reused[n] = sha(features_from/n)
        rows = []
        for s in read(out/'catalog.json'):
            p = features_from/s['sid']/'features.json'
            (out/s['sid']).mkdir()
            (out/s['sid']/'features.json').write_bytes(p.read_bytes())
            reused[s['sid']+'/features.json'] = sha(p)
            rows.extend(read(p))
        write(out/'FEATURE_REUSE.json', dict(source=str(features_from), sha256=reused, note='R2 features reused byte-for-byte; temporal predictions freshly recomputed'))
    results = {}; outputs = []
    for s in read(out/'catalog.json'):
        rs = [r for r in rows if r['sid'] == s['sid']]
        start = time.perf_counter(); os = sequence(rs, cfg); wall = time.perf_counter()-start
        write(out/s['sid']/'predictions.json', os)
        results[s['sid']] = dict(summary=summarize(rs, os), batch_wall_ms=wall*1000, duration_s=rs[-1]['time']-rs[0]['time'])
        outputs.extend(os)
    sensitivity = []
    # Predeclared sweep; no winner selection and no labels consumed.
    for tau in [.15, .3, .6]:
        c = copy.deepcopy(cfg); c['ema_tau_s'] = tau
        sensitivity.append(dict(ema_tau_s=tau, summary=summarize(rows, sequence(rows, c))))
    timings = {k:[] for k in ['combined_online', 'hmm_forward', 'hsmm', 'mc_kernel', 'viterbi_batch_per_frame']}
    tracks={}
    for r in rows:
        key=r['sid'],r['track_id']
        if key not in tracks:tracks[key]=Track(cfg)
        start = time.perf_counter_ns(); tracks[key].update(r['time'], r['feature'], r['rf']); timings['combined_online'].append((time.perf_counter_ns()-start)/1e6)
    # Separate independent kernel benchmarks on actual fixed emissions; no feature/IO cost included.
    h = HMM(cfg['posture']['initial'], cfg['posture']['matrix']); hs = HSMM(cfg['event']); last = None; last_key=None
    for o in outputs:
        key=o['sid'],o['track_id']
        if last is not None and (key!=last_key or o['time'] <= last or o['time']-last > cfg['reset_gap_s']):
            h = HMM(cfg['posture']['initial'], cfg['posture']['matrix']); hs = HSMM(cfg['event']); last = None
        dt = None if last is None else o['time']-last
        st = time.perf_counter_ns(); h.update(o['emission'], dt); timings['hmm_forward'].append((time.perf_counter_ns()-st)/1e6)
        st = time.perf_counter_ns(); hs.update(o['event_emission'], o['time']); timings['hsmm'].append((time.perf_counter_ns()-st)/1e6)
        from temporal import transition, normalize
        st=time.perf_counter_ns(); normalize(np.array([.3,.3,.4]) @ transition(np.asarray(cfg['presence_matrix']),dt or .1)*np.array([.05,.9,.05]));timings['mc_kernel'].append((time.perf_counter_ns()-st)/1e6)
        last = o['time'];last_key=key
    for s in read(out/'catalog.json'):
        os=[o for o in outputs if o['sid']==s['sid']]
        st=time.perf_counter_ns();h.viterbi([o['emission'] for o in os],[o['time'] for o in os]);timings['viterbi_batch_per_frame'].append((time.perf_counter_ns()-st)/1e6/len(os))
    write(out/'RESULTS.json', dict(by_session=results, aggregate=summarize(rows, outputs), sensitivity=sensitivity,
                                  timing_ms={k:stats(v) for k,v in timings.items()}, rf_ms=stats([r['rf_ms'] for r in rows]),
                                  response_latency='UNKNOWN_NO_HUMAN_ONSET_GT', semantics='BLOCKED',
                                  benchmark='PC single-thread call wall time; RF includes feature extraction; temporal excludes preprocessing/IO. Individual HMM/HSMM kernels use same recorded emissions. Viterbi batch time divided by frames is throughput, not online latency. MC kernel is fixed-vector workload. Simple filter individual timings NOT_RUN; combined includes all filters.'))
    print('complete', len(rows), summarize(rows, outputs), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, default=EVIDENCE/'run_r1')
    parser.add_argument('--features-from',type=Path)
    args = parser.parse_args(); args.out.mkdir(parents=True, exist_ok=False); run(args.out,args.features_from)
