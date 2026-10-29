"""Read-only wiring: source -> S3 transform -> r01 candidates -> r04 estimate
-> new persistent calibration layer -> per-frame evidence.

No extractor or association code is copied or modified here.  The only new
algorithmic layer is calibrate.py.
"""
import hashlib
import importlib.util
import json
import math
import sys
import threading
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1'
SOURCE = ROOT / 'data/sessions/cap_20261017_113516'
R01 = ROOT / 'sidequests/hfus_tcms_02/realdev/r01'
R04 = ROOT / 'sidequests/hfus_tcms_02/realdev/r04'
R04S = ROOT / 'sidequests/human_fusion_lab_next/real_fall/r04'
S3 = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1'
ASSOCIATION = ROOT / 'src/human_fall_detection/core/association.py'
RAW = 'RAW/innolidar'
FROZEN = dict(
    meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
    points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1',
    rows=38298918, frames=780,
    transform='8699429bcc9b85e8b9cf10a3252b8082a09174f60f7eb550cd4cc9f65bbce3de',
    transform_id='f0533fd84b9c7e1f0ec22bfcf3f7f433fb071fa73327ca9c9c881cc4aef4ab8d',
    m0='9bb0f1115919445deb259757e1dcaacfdb8fa72337c3008353d5a699df3d1c41',
    m0_map_id='56fa2141c00aebda8a9854d258be3e0c8ee44fc6f9a7d20e7704e110c1aa9553',
    domains='8cdceb00c0b33338ed180b711fc7157bba2a74db0c026b7f8fb00bbff22d4c81',
    domains_npz='ffae5211f275a1f4d7da1a69a2ab42cef154ee82f268a628568bc068e17d5899',
)
FIT_END_S, ACTION_START_S = 20.0, 30.0
TTL_S = 1.0
MIN_CANDIDATE_ROWS = 30


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(16 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def guarded(path):
    p = Path(path).absolute()
    if not p.resolve().is_relative_to(EV.resolve()) or p.resolve() == EV.resolve():
        raise ValueError('Output must be under this item evidence root')
    if any(q.is_symlink() or q.is_junction() for q in [p, *p.parents] if q.exists()):
        raise ValueError('Output reparse/link path forbidden')
    return p


def write_new(path, value):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
    return p


def save_array(path, **arrays):
    p = guarded(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('xb') as f:
        np.savez_compressed(f, **arrays)
    return p


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load_source():
    contracts = module('skeleton02_r01_contracts', R01 / 'contracts.py')
    entry = dict(kind='REAL_DEVELOPMENT', role='B', independent_test=False,
                 path=str(SOURCE), sid='cap_20261017_113516',
                 coordinate_version=RAW,
                 source_sha256=dict(meta=FROZEN['meta'], points=FROZEN['points']))
    src = contracts.Source(entry)
    if len(src.frames) != FROZEN['frames'] or sum(f['count_points'] for f in src.frames) != FROZEN['rows']:
        raise ValueError('Source denominator drift')
    return src, list(src.times)


def r01_pipeline():
    if str(R01) not in sys.path:
        sys.path.insert(0, str(R01))
    m = module('skeleton02_r01_pipeline', R01 / 'pipeline.py')
    m.save_array, m.write_new = save_array, write_new
    return m


def r04_transform():
    sys.path.insert(0, str(R04))
    try:
        return module('skeleton02_r04_transform', R04 / 'transform.py')
    finally:
        sys.path.remove(str(R04))


def r04_build_m0():
    sys.path.insert(0, str(R04))
    try:
        return module('skeleton02_r04_build_m0', R04 / 'build_m0.py')
    finally:
        sys.path.remove(str(R04))


def r04_skeleton():
    assert str(R04S) in sys.path
    return module('skeleton02_r04_skeleton', R04S / 'skeleton.py')


def association_module():
    return module('skeleton02_association', ASSOCIATION)


def valid_nodes(skeleton):
    return sum(1 for node in skeleton['nodes'].values() if node.get('valid'))


def skeleton_measurements(skeleton, edges):
    out = {}
    for a, b in edges:
        na, nb = skeleton['nodes'][a], skeleton['nodes'][b]
        if na.get('valid') and nb.get('valid'):
            pa = np.asarray(na['xyz'], dtype=float)
            pb = np.asarray(nb['xyz'], dtype=float)
            if np.all(np.isfinite(pa)) and np.all(np.isfinite(pb)):
                out[(a, b)] = float(np.linalg.norm(pa - pb))
    return out


def node_record(node):
    xyz = node.get('xyz')
    display = node.get('display_xyz')
    return dict(valid=bool(node.get('valid')),
                xyz=None if xyz is None else [float(x) for x in xyz],
                display_xyz=None if display is None else [float(x) for x in display],
                display_predicted=bool(node.get('display_predicted', False)),
                display_opacity=float(node.get('display_opacity', 0.0)),
                support_n=int(node.get('support_n', 0)),
                reason=node.get('reason'))


class Rss(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.peak = 0
        self.stop = False

    def run(self):
        try:
            import psutil
            proc = psutil.Process()
            while not self.stop:
                self.peak = max(self.peak, proc.memory_info().rss)
                time.sleep(0.05)
        except Exception:
            self.peak = 0


def make_new_track(track_id, candidate, t, frame_index, edges):
    from calibrate import CalibrationLayer
    return dict(
        id=track_id, state='SEEDED', identity='UNKNOWN', center=np.asarray(candidate['position_m'], dtype=float),
        size_m=float(candidate['size_m']), last_t=t, last_fi=frame_index,
        first_t=t, first_fi=frame_index, matched_frames=0, skeleton_frames=0,
        total_valid_nodes=0, last_axis=None, last_lateral=None, axis_measured_t=None,
        display_history={}, edge_reference={}, calibration=CalibrationLayer(edges),
        events=[dict(fi=frame_index, old='NONE', new='SEEDED', reason='NEW_UNMATCHED_CANDIDATE')],
    )


def run(outroot):
    out = guarded(outroot)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'frames').mkdir()
    before_hashes = {
        'r04_skeleton': sha(R04S / 'skeleton.py'),
        'r04_paths': sha(R04S / 'paths.py'),
        'old_skeleton': sha(ROOT / 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py'),
        'old_params': sha(ROOT / 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/prototype_params_v1.json'),
        'association': sha(ASSOCIATION),
        'r01_contracts': sha(R01 / 'contracts.py'),
        'r01_pipeline': sha(R01 / 'pipeline.py'),
        'r04_transform': sha(R04 / 'transform.py'),
        'r04_build_m0': sha(R04 / 'build_m0.py'),
    }
    for rel, want in [
        ('TRANSFORM/TRANSFORM_S3.json', FROZEN['transform']),
        ('M0/M0.json', FROZEN['m0']),
        ('DOMAINS/S3_DOMAINS.json', FROZEN['domains']),
        ('DOMAINS/domains_s3.npz', FROZEN['domains_npz']),
    ]:
        if sha(S3 / rel) != want:
            raise ValueError('Inherited input drift: ' + rel)
    protocol_sha = sha(EV / 'PROTOCOL_V3.json')
    t0 = time.perf_counter()
    rss = Rss()
    rss.start()
    src, times = load_source()
    if len(times) != FROZEN['frames']:
        raise ValueError('Frame count drift')
    X = r04_transform()
    Build = r04_build_m0()
    T = X.Transform(load(S3 / 'TRANSFORM/TRANSFORM_S3.json'))
    if T.id != FROZEN['transform_id']:
        raise ValueError('Transform id drift')
    sys.path.insert(0, str(R04S))
    import paths  # noqa: F401
    SK = r04_skeleton()
    A = association_module()
    pipe = r01_pipeline()
    if len(SK.SLOTS) != 13 or len(SK.EDGES) != 12:
        raise ValueError('r04 region contract drift')
    map_protocol = Build.r01_map_protocol(0.08, 0.05, 750000)
    map_protocol['coordinate'] = T.version
    frozen = pipe.FrozenMap(out, src.binding, T.version, map_protocol)
    run_version = digest(dict(protocol=protocol_sha, transform=T.id,
                              m0=FROZEN['m0_map_id']))
    engine = pipe.Engine(frozen, 'main', sha(HERE / 'wire.py'), run_version=run_version,
                         protocol_sha=protocol_sha)
    code_at_start = dict(
        item='HFUS-HUMAN-SKELETON-02', protocol_sha=protocol_sha,
        files={p.name: sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.suffix in ('.py', '.js', '.html')},
        read_only_before=before_hashes, transform_id=T.id, m0_map_id=FROZEN['m0_map_id'])
    write_new(out / 'CODE_AT_START.json', code_at_start)
    write_new(out / 'RUN_META.json', dict(
        item='HFUS-HUMAN-SKELETON-02', protocol_sha=protocol_sha,
        source=dict(sid='cap_20261017_113516', meta_sha256=FROZEN['meta'],
                    points_sha256=FROZEN['points'], frames=FROZEN['frames'], rows=FROZEN['rows']),
        transform_id=T.id, coordinate_version=T.version, m0_map_id=FROZEN['m0_map_id'],
        action_start_s=ACTION_START_S, ttl_s=TTL_S, min_candidate_rows=MIN_CANDIDATE_ROWS,
        identity_claims=dict(human='UNKNOWN', anatomy='UNKNOWN', left_right='UNKNOWN', physical_height='UNKNOWN')))
    tracks = {}
    active = []
    track_seq = 0
    previous_frame_t = None
    all_assoc = []
    action_total = 0
    action_with_candidates = 0
    action_with_skeleton = 0
    action_with_six_nodes = 0
    frame_log = open(out / 'frames.jsonl', 'x', encoding='utf8', newline='\n')
    totals = dict(rows=0, valid=0, invalid=0, candidates=0, skeleton_frames=0,
                  valid_node_frames=0, valid_node_six_frames=0)
    try:
        for fi in range(FROZEN['frames']):
            f = src.frame(fi)
            t = times[fi]
            local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
            phase = ('MAP_BUILDING' if t < 20.0 else
                     'TEMPORAL_VALIDATION' if t < 28.0 else
                     'EMPTY_AUDIT' if t < 30.0 else 'ACTION')
            if t < FIT_END_S:
                frozen.add(dict(f, xyz=local, coordinate_version=T.version, relative_s=t))
            elif frozen.map_id is None:
                frozen.freeze()
                frozen.bind_exact_time(src.stamps)
                if frozen.map_id != FROZEN['m0_map_id']:
                    raise ValueError('Rebuilt M0 fingerprint mismatch')
            qualified = fi >= 271
            record, row_labels, hits = engine.step(
                dict(f, xyz=local, coordinate_version=T.version, relative_s=t),
                phase, qualified=qualified)
            frame_index = fi
            candidates = []
            for c in record['candidates']:
                if c['count'] < MIN_CANDIDATE_ROWS:
                    continue
                size = max(max(c['max'][i] - c['min'][i] for i in range(3)), 1e-6)
                candidates.append(dict(candidate_id='c%d' % c['id'], engine_id=int(c['id']),
                                       position_m=[float(x) for x in c['center']],
                                       size_m=float(size), count=int(c['count']),
                                       rows=list(c['rows'])))
            candidates_by_id = {c['candidate_id']: c for c in candidates}
            active = [tr for tr in active if t - tr['last_t'] <= TTL_S]
            association_tracks = [dict(track_id=tr['id'], position_m=tr['center'].tolist(),
                                       size_m=float(tr['size_m'])) for tr in active]
            dt_s = 0.0 if previous_frame_t is None else max(0.0, t - previous_frame_t)
            assoc = A.associate_tracks(association_tracks, candidates, dt_s=dt_s,
                                       settings=dict(gate_m=0.8, ambiguity_margin_m=0.2,
                                                     max_speed_m_s=2.5, max_size_ratio=3.0))
            assoc_record = dict(
                matches=assoc['matches'],
                ambiguous_track_ids=assoc['ambiguous_track_ids'],
                ambiguous_candidate_ids=assoc['ambiguous_candidate_ids'],
                unmatched_track_ids=assoc['unmatched_track_ids'],
                unmatched_candidate_ids=assoc['unmatched_candidate_ids'],
                gate_m=assoc['gate_m'], settings=assoc['settings'])
            match_by_track = {m['track_id']: candidates_by_id[m['candidate_id']]
                              for m in assoc['matches'] if m['candidate_id'] in candidates_by_id}
            ambiguous_tracks = set(assoc['ambiguous_track_ids'])
            matched_tracks = set(match_by_track)
            track_results = []
            for tr in list(active):
                if tr['id'] not in matched_tracks:
                    new_state = 'AMBIGUOUS' if tr['id'] in ambiguous_tracks else 'UNMATCHED'
                    if new_state != tr['state']:
                        tr['events'].append(dict(fi=fi, old=tr['state'], new=new_state,
                                                 reason='ASSOCIATION_' + new_state))
                    tr['state'] = new_state
                    if t - tr['last_t'] > TTL_S:
                        tr['state'] = 'LOST'
                        tr['events'].append(dict(fi=fi, old=new_state, new='LOST',
                                                 reason='TTL_EXPIRED'))
                        active.remove(tr)
                    continue
                cand = match_by_track[tr['id']]
                if tr['state'] != 'MATCHED':
                    tr['events'].append(dict(fi=fi, old=tr['state'], new='MATCHED',
                                             reason='ASSOCIATION_MATCH'))
                tr['state'] = 'MATCHED'
                tr['center'] = np.asarray(cand['position_m'], dtype=float)
                tr['size_m'] = float(cand['size_m'])
                tracks[tr['id']] = tr
                track_results.append(process_track(tr, cand, fi, t, f, local, SK, dt_s, track_results_only=False))
                tr['last_t'] = t
                tr['last_fi'] = fi
                tr['matched_frames'] += 1
            # Explicitly seed unmatched candidates as new UNKNOWN tracks; never pick a nearest match.
            ambiguous_candidates = set(assoc['ambiguous_candidate_ids'])
            for cid in assoc['unmatched_candidate_ids']:
                if cid in ambiguous_candidates or cid not in candidates_by_id:
                    continue
                cand = candidates_by_id[cid]
                track_seq += 1
                track_id = 'U%04d' % track_seq
                tr = make_new_track(track_id, cand, t, fi, SK.EDGES)
                tracks[track_id] = tr
                active.append(tr)
                result = process_track(tr, cand, fi, t, f, local, SK, dt_s, track_results_only=False)
                result['association_event'] = 'SEEDED_FROM_UNMATCHED_CANDIDATE'
                track_results.append(result)
                tr['last_t'] = t
                tr['last_fi'] = fi
            best_nodes = max([tr['valid_nodes'] for tr in track_results], default=0)
            totals['rows'] += record['accounting']['raw']
            totals['valid'] += record['accounting']['valid']
            totals['invalid'] += record['accounting']['invalid']
            totals['candidates'] += len(candidates)
            if track_results:
                totals['skeleton_frames'] += 1
            if best_nodes > 0:
                totals['valid_node_frames'] += 1
            if best_nodes >= 6:
                totals['valid_node_six_frames'] += 1
            if phase == 'ACTION':
                action_total += 1
                if candidates:
                    action_with_candidates += 1
                if track_results:
                    action_with_skeleton += 1
                if best_nodes >= 6:
                    action_with_six_nodes += 1
            frame_record = dict(
                schema='hfus-human-skeleton-calibration-frame/1', fi=fi, relative_s=float(t),
                time_ns=int(f['time_ns']), phase=phase, qualified=bool(qualified),
                source_sha256=dict(meta=FROZEN['meta'], points=FROZEN['points']),
                transform_id=T.id, coordinate_version=T.version, map_id=record.get('map_id'),
                engine=dict(candidates_total=len(record['candidates']), candidates_used=len(candidates),
                            accounting=record['accounting'], reset=record.get('reset')),
                association=assoc_record,
                candidate_summaries=[dict(candidate_id=c['candidate_id'], engine_id=c['engine_id'],
                                          count=c['count'], center=c['position_m'], size_m=c['size_m'])
                                     for c in candidates],
                track_results=track_results, best_valid_nodes=int(best_nodes),
                skeleton_available=bool(best_nodes > 0),
                semantic=dict(anatomy='UNKNOWN', left_right='UNKNOWN',
                              physical_height='UNKNOWN', human_identity='UNKNOWN'))
            frame_log.write(json.dumps(frame_record, ensure_ascii=False, allow_nan=False,
                                       separators=(',', ':')) + '\n')
            save_array(out / 'frames' / ('%04d.npz' % fi),
                       candidate=row_labels['candidate'].astype('i4'),
                       label=row_labels['label'], flags=row_labels['flags'],
                       map_hits=np.asarray(hits, dtype='i4'))
            previous_frame_t = t
            if fi % 50 == 0:
                print(json.dumps(dict(fi=fi, t=round(t, 2), surfaces=frozen.n,
                                      elapsed=round(time.perf_counter() - t0, 1),
                                      rss=int(rss.peak))), flush=True)
            if rss.peak > 2147483648:
                raise MemoryError('RSS budget exceeded')
            if time.perf_counter() - t0 > 2400:
                raise TimeoutError('wall budget exceeded')
    finally:
        frame_log.close()
        src.close()
        rss.stop = True
    if frozen.fingerprint() != frozen.map_id:
        raise ValueError('Map arrays drifted during run')
    if sha(SOURCE / 'meta.json') != FROZEN['meta'] or sha(SOURCE / 'points.bin') != FROZEN['points']:
        raise ValueError('Source changed during run')
    after_hashes = {k: sha(ROOT / rel) for k, rel in [
        ('r04_skeleton', 'sidequests/human_fusion_lab_next/real_fall/r04/skeleton.py'),
        ('r04_paths', 'sidequests/human_fusion_lab_next/real_fall/r04/paths.py'),
        ('old_skeleton', 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py'),
        ('old_params', 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/prototype_params_v1.json'),
        ('association', 'src/human_fall_detection/core/association.py'),
        ('r01_contracts', 'sidequests/hfus_tcms_02/realdev/r01/contracts.py'),
        ('r01_pipeline', 'sidequests/hfus_tcms_02/realdev/r01/pipeline.py'),
        ('r04_transform', 'sidequests/hfus_tcms_02/realdev/r04/transform.py'),
        ('r04_build_m0', 'sidequests/hfus_tcms_02/realdev/r04/build_m0.py'),
    ]}
    read_only_unchanged = bool(before_hashes == after_hashes)
    track_summaries = {}
    for tid, tr in sorted(tracks.items()):
        summary = tr['calibration'].summary()
        calibrated = [k for k, v in summary['edges'].items() if v['ever_calibrated']]
        post_stds = [v['post_calibration_std'] for k, v in summary['edges'].items()
                     if k in calibrated and v['post_calibration_std'] is not None]
        stable_edges = {}
        for k, v in summary['edges'].items():
            best = v.get('best_calibration_episode')
            if best is not None:
                stable_edges[k] = best
        current_calibrated = [k for k, v in summary['edges'].items()
                              if v['state'] == 'CALIBRATED']
        track_summaries[tid] = dict(
            track_id=tid, identity='UNKNOWN', first_fi=tr['first_fi'], last_fi=tr['last_fi'],
            matched_frames=tr['matched_frames'], skeleton_frames=tr['skeleton_frames'],
            total_valid_nodes=tr['total_valid_nodes'],
            calibrated_edges=calibrated, calibrated_edge_count=len(calibrated),
            current_calibrated_edges=current_calibrated,
            stable_calibrated_edges=stable_edges,
            stable_calibrated_edge_count=len(stable_edges),
            max_stable_calibration_std_m=(
                max(v['raw_std_m'] for v in stable_edges.values()) if stable_edges else None),
            max_post_calibration_std_m=(max(post_stds) if post_stds else None),
            calibration=summary, events=tr['events'])
    primary_tid = None
    if track_summaries:
        primary_tid = sorted(track_summaries, key=lambda k: (
            track_summaries[k]['stable_calibrated_edge_count'],
            track_summaries[k]['calibrated_edge_count'],
            track_summaries[k]['skeleton_frames'],
            track_summaries[k]['total_valid_nodes'],
            -int(k[1:])))[-1]
    primary = track_summaries.get(primary_tid)
    real_gate = dict(
        action_frames=action_total,
        action_frames_with_candidates=action_with_candidates,
        action_frames_with_skeleton=action_with_skeleton,
        action_frames_with_six_valid_nodes=action_with_six_nodes,
        all_action_six_fraction=action_with_six_nodes / action_total if action_total else 0.0,
        candidate_action_six_fraction=(action_with_six_nodes / action_with_candidates
                                       if action_with_candidates else 0.0),
        minimum_candidate_denominator=0.8,
        primary_track=primary_tid,
        primary_calibrated_edges=(0 if primary is None else primary['calibrated_edge_count']),
        primary_stable_calibrated_edges=(0 if primary is None
                                         else primary['stable_calibrated_edge_count']),
        primary_max_stable_calibration_std_m=(None if primary is None
                                              else primary['max_stable_calibration_std_m']),
        primary_current_calibrated_edges=([] if primary is None
                                          else primary['current_calibrated_edges']),
        calibrated_edges_stable=bool(primary is not None
                                     and primary['stable_calibrated_edge_count'] >= 6
                                     and primary['max_stable_calibration_std_m'] is not None
                                     and primary['max_stable_calibration_std_m'] <= 0.02),
    )
    real_gate['candidate_coverage_PASS'] = bool(
        real_gate['candidate_action_six_fraction'] >= 0.8)
    real_gate['calibration_PASS'] = bool(real_gate['calibrated_edges_stable'])
    write_new(out / 'TRACKS.json', dict(item='HFUS-HUMAN-SKELETON-02',
                                        primary_track=primary_tid, tracks=track_summaries))
    write_new(out / 'CALIBRATION.json', dict(
        item='HFUS-HUMAN-SKELETON-02', primary_track=primary_tid,
        primary=(None if primary is None else primary['calibration']),
        gate=real_gate,
        semantic=dict(anatomy='UNKNOWN', left_right='UNKNOWN',
                      physical_height='UNKNOWN', human_identity='UNKNOWN')))
    write_new(out / 'FRAME_SUMMARY.json', dict(
        item='HFUS-HUMAN-SKELETON-02', totals=totals, real_gate=real_gate,
        frame_count=FROZEN['frames'], rows_expected=FROZEN['rows'],
        rows_conserved=bool(totals['rows'] == FROZEN['rows']),
        read_only_before=before_hashes, read_only_after=after_hashes,
        read_only_unchanged=read_only_unchanged,
        transform_id=T.id, map_id=frozen.map_id,
        identity=dict(human='UNKNOWN', anatomy='UNKNOWN', left_right='UNKNOWN',
                      physical_height='UNKNOWN')))
    write_new(out / 'PERFORMANCE.json', dict(
        item='HFUS-HUMAN-SKELETON-02', seconds=time.perf_counter() - t0,
        peak_rss_bytes=int(rss.peak),
        output_bytes=int(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())),
        limits=dict(seconds=2400, peak_rss_bytes=2147483648, output_bytes=3221225472),
        read_only_unchanged=read_only_unchanged,
        PASS=bool(read_only_unchanged and rss.peak <= 2147483648
                  and time.perf_counter() - t0 <= 2400)))
    return dict(real_gate=real_gate, totals=totals, primary_track=primary_tid,
                read_only_unchanged=read_only_unchanged,
                seconds=time.perf_counter() - t0)


def process_track(tr, cand, fi, t, frame, local, SK, dt_s, track_results_only=False):
    rows = np.asarray(cand['rows'], dtype=int)
    points = local[rows]
    source_rows = (frame['offset'] + rows).tolist()
    dt_track = 0.0 if tr.get('last_t') is None else max(0.0, t - tr['last_t'])
    reference_age = (0.0 if tr.get('axis_measured_t') is None
                     else max(0.0, t - tr['axis_measured_t']))
    skeleton, axis = SK.estimate(
        points, source_rows, tr.get('last_axis'), tr.get('last_lateral'),
        dt=dt_track, reference_age=reference_age)
    if axis is not None:
        tr['last_axis'] = axis
        tr['last_lateral'] = skeleton.get('basis_lateral')
        if not skeleton.get('axis_prior_reference'):
            tr['axis_measured_t'] = t
    SK.stabilize_display(skeleton, t, tr['display_history'], tr['edge_reference'])
    measurements = skeleton_measurements(skeleton, SK.EDGES)
    cal_frame = tr['calibration'].update(fi, measurements)
    nv = valid_nodes(skeleton)
    tr['skeleton_frames'] += 1
    tr['total_valid_nodes'] += nv
    edge_records = []
    for a, b in SK.EDGES:
        key = '%s|%s' % (a, b)
        cal = cal_frame['edges'][key]
        edge_records.append(dict(
            edge=[a, b], measurement=measurements.get((a, b)),
            state=cal['state'], mean=cal['mean'], sigma=cal['sigma'],
            relative_std=cal['relative_std'], n=cal['n']))
    return dict(
        track_id=tr['id'], track_state=tr['state'], identity='UNKNOWN',
        candidate_id=cand['candidate_id'], candidate_engine_id=cand['engine_id'],
        candidate_rows=int(len(rows)), valid_nodes=int(nv),
        edge_count=int(len(skeleton.get('edges', []))),
        measurements=len(measurements), reason=skeleton.get('reason'),
        nodes={name: node_record(node) for name, node in skeleton['nodes'].items()},
        edges=edge_records,
        display_edges=[list(e) for e in skeleton.get('display_edges', [])],
        unstable_connections=[list(e) for e in skeleton.get('unstable_connections', [])],
        calibration=dict(frame=cal_frame['frame'], state_events=tr['calibration'].events[-4:],
                         drift_events=tr['calibration'].drifts[-4:]),
        semantic='POINT_SUPPORTED_REGIONS_ONLY; DISPLAY_IS_NOT_EVIDENCE')


if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else EV / 'RUN'
    print(json.dumps(run(target), ensure_ascii=False, allow_nan=False))
