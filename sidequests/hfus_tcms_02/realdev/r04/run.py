"""T4/T5: replay the unchanged r01 application chain in S3_LOCAL and validate the new domains.

M0 is rebuilt from FIT rows only and fingerprinted against the frozen T3 artifact. Ground gates
come from the frozen S3 domains; the causal unlock takes effect from fi 271 and only if the
[28,30) prefix audit also passes, exactly as registered before the run.
"""
import json
import sys
import threading
import time
from pathlib import Path
import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C
import transform as X
import build_m0

GATE = dict(min_points=20, rms_m=0.03, p95_abs_m=0.05, support_m=0.05, support_rate=0.8, spread_min_m=0.1)
PATCH_NAMES = ['S3V_H', 'S3V_I', 'S3V_J']


class Rss(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.peak = 0
        self.stop = False

    def run(self):
        p = psutil.Process()
        while not self.stop:
            self.peak = max(self.peak, p.memory_info().rss)
            time.sleep(0.05)


def domain_rows(dom):
    """Frozen domain rows per patch and frame; global rows minus the frame offset."""
    z = np.load(C.OUT / 'DOMAINS/domains_s3.npz')
    out = {}
    for name in PATCH_NAMES:
        out[name] = {}
        for role in ('val', 'prefix'):
            rows = z['%s_%s_rows' % (name, role)]
            fis = z['%s_%s_fi' % (name, role)]
            table = {}
            for fi in np.unique(fis):
                table[int(fi)] = rows[fis == fi]
            out[name][role] = table
    return out


def local_rows(table, fi, offset):
    g = table.get(fi)
    return None if g is None else (g - offset)


def patch_frame_stats(res):
    """One frame, one patch: the registered per-frame gate."""
    n = len(res)
    if n < GATE['min_points']:
        return dict(count=int(n), PASS=False, reason='BELOW_MIN_POINTS')
    rms = float(np.sqrt(np.mean(res ** 2)))
    p95 = float(np.percentile(np.abs(res), 95))
    support = float(np.mean(np.abs(res) <= GATE['support_m']))
    ok = bool(rms <= GATE['rms_m'] and p95 <= GATE['p95_abs_m'] and support >= GATE['support_rate'])
    return dict(count=int(n), rms_m=rms, p95_abs_m=p95, support_rate=support,
                median_signed_m=float(np.median(res)), PASS=ok,
                reason=None if ok else 'RMS_P95_OR_SUPPORT_GATE')


def pooled_patch_stats(res, pts):
    n = len(res)
    if n < GATE['min_points']:
        return dict(count=int(n), PASS=False, reason='BELOW_MIN_POINTS')
    rms = float(np.sqrt(np.mean(res ** 2)))
    p95 = float(np.percentile(np.abs(res), 95))
    support = float(np.mean(np.abs(res) <= GATE['support_m']))
    su = float(np.percentile(pts[:, 0], 95) - np.percentile(pts[:, 0], 5))
    sv = float(np.percentile(pts[:, 1], 95) - np.percentile(pts[:, 1], 5))
    spread = max(su, sv)
    ok = bool(rms <= GATE['rms_m'] and p95 <= GATE['p95_abs_m'] and support >= GATE['support_rate']
              and spread >= GATE['spread_min_m'])
    return dict(count=int(n), rms_m=rms, p95_abs_m=p95, support_rate=support, spread_u_m=su, spread_v_m=sv,
                spread_max_m=spread, median_signed_m=float(np.median(res)), PASS=ok,
                reason=None if ok else 'RMS_P95_SUPPORT_OR_SPREAD_GATE')


def prefix_audit(src, times, T, dom_rows, pre, patch_names=PATCH_NAMES):
    """Evaluate the [28,30) prefix stability before the unlock takes effect at fi 271."""
    per = {}
    for fi in pre:
        f = src.frame(fi)
        local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
        z = local[:, 2]
        entry = {}
        for name in patch_names:
            rows = local_rows(dom_rows[name]['prefix'], fi, f['offset'])
            entry[name] = dict(count=0, PASS=False, reason='NO_ROWS') if rows is None or not len(rows) \
                else patch_frame_stats(z[rows])
        per[str(fi)] = entry
    passed = sum(all(v['PASS'] for v in e.values()) for e in per.values())
    return dict(frames=len(per), all_patch_pass_frames=int(passed), per_frame=per,
                required='19/19', PASS=bool(len(per) == 19 and passed == 19))


def online_state(fi, available_after, qualified):
    if fi <= 192:
        return 'RAW'
    if fi <= available_after:
        return 'CANDIDATE_PLANE_PREVIEW'
    return 'GEOMETRY_VALIDATED_LOCAL' if qualified else 'CANDIDATE_PLANE_PREVIEW'


if __name__ == '__main__':
    t0 = time.perf_counter()
    rss = Rss()
    rss.start()
    protocol = C.load(C.OUT / 'PROTOCOL_V2.json')
    dom = C.load(C.OUT / 'DOMAINS/S3_DOMAINS.json')
    m0doc = C.load(C.OUT / 'M0/M0.json')
    if C.sha(C.OUT / 'DOMAINS/domains_s3.npz') != dom['domains_sha']:
        raise SystemExit('DOMAIN ARRAY DRIFT')
    T = X.Transform(C.load(C.OUT / 'TRANSFORM/TRANSFORM_S3.json'))
    if dom['transform_id'] != T.id or m0doc['transform_id'] != T.id:
        raise SystemExit('TRANSFORM/DOMAIN/M0 MISMATCH')
    run = C.OUT / 'RUN'
    run.mkdir(exist_ok=False)
    (run / 'frames').mkdir()
    here = Path(__file__).resolve().parent
    C.write(run / 'CODE_AT_START.json', dict(
        argv=sys.argv, protocol_sha=C.sha(C.OUT / 'PROTOCOL_V2.json'),
        files={p.name: C.sha(p) for p in sorted(here.iterdir()) if p.is_file() and p.suffix in ('.py', '.js', '.html')}))
    src, times = C.load_source()
    fit, val, pre = C.roles(times)
    pipe = C.r01_pipeline()
    dest = run / 'primary_map'
    dest.mkdir()
    frozen = pipe.FrozenMap(dest, src.binding, T.version, build_m0.r01_map_protocol(
        protocol['m0']['primary']['tau_m'], protocol['m0']['primary']['voxel_m'],
        protocol['m0']['primary']['max_surfaces']))
    frozen.protocol['coordinate'] = T.version
    engine = pipe.Engine(None, 'main', C.sha(run / 'CODE_AT_START.json'),
                         run_version=C.digest(dict(protocol=C.sha(C.OUT / 'PROTOCOL_V2.json'),
                                                   domains=dom['domains_sha'], transform=T.id,
                                                   m0=m0doc['primary']['map_id'])),
                         protocol_sha=C.sha(C.OUT / 'PROTOCOL_V2.json'))
    dom_rows = domain_rows(dom)
    available_after = m0doc['available_after_fi']
    val_frames = {name: {} for name in PATCH_NAMES}
    pooled = {name: ([], []) for name in PATCH_NAMES}
    frame_log = open(run / 'frames.jsonl', 'x', encoding='utf8', newline='\n')
    totals = dict(rows=0, valid=0, invalid=0, candidates=0, member_rows=0, track_rows=0, bg=0)
    labels_total = np.zeros(6, dtype='i8')
    resets = {}
    qualification = None
    prefix = None
    qualification_done = False
    try:
        for fi in range(len(times)):
            f = src.frame(fi)
            t = times[fi]
            local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
            phase = 'MAP_BUILDING' if t < 20 else 'TEMPORAL_VALIDATION' if t < 28 else 'EMPTY_AUDIT' if t < 30 else 'ACTION'
            if t < 20:
                _, valid = pipe.validity(f['xyz'])
                frozen.add(build_m0.frame(local, f, T, fi, times))
            elif frozen.map_id is None:
                frozen.freeze()
                frozen.bind_exact_time(src.stamps)
                if frozen.map_id != m0doc['primary']['map_id']:
                    raise ValueError('Rebuilt M0 fingerprint %s != frozen %s'
                                     % (frozen.map_id, m0doc['primary']['map_id']))
                engine.map = frozen
            # ground gates are decided at the end of the [20,28) window, before fi 271
            if fi == val[-1] + 1 and not qualification_done:
                spatial = {}
                for name in PATCH_NAMES:
                    res = np.concatenate(pooled[name][0]) if pooled[name][0] else np.empty(0)
                    pts = np.concatenate(pooled[name][1]) if pooled[name][1] else np.empty((0, 2))
                    spatial[name] = pooled_patch_stats(res, pts) if len(res) else dict(count=0, PASS=False,
                                                                                      reason='NO_ROWS')
                frames_all_pass = sum(all(val_frames[name][fi]['PASS'] for name in PATCH_NAMES)
                                      for fi in val_frames[PATCH_NAMES[0]])
                frame_pass = {fi: all(val_frames[name][fi]['PASS'] for name in PATCH_NAMES)
                              for fi in val_frames[PATCH_NAMES[0]]}
                temporal_pass = frames_all_pass / len(val)
                prefix = prefix_audit(src, times, T, dom_rows, pre)
                spatial_pass = sum(v['PASS'] for v in spatial.values())
                m0_ok = bool(frozen.map_id == m0doc['primary']['map_id']
                             and len(frozen.tree_ids) == m0doc['primary']['eligible_surfaces'])
                qualified = bool(spatial_pass >= 2 and temporal_pass >= 0.95 and prefix['PASS'] and m0_ok)
                qualification = dict(
                    available_after_fi=available_after, first_effective_fi=available_after + 1,
                    spatial_patches=spatial, spatial_pass_patches=int(spatial_pass),
                    spatial_required=2, temporal_frames=len(val), temporal_all_pass_frames=int(frames_all_pass),
                    temporal_frame_pass=frame_pass,
                    temporal_pass_fraction=float(temporal_pass), temporal_required=0.95,
                    temporal_PASS=bool(temporal_pass >= 0.95), prefix=prefix, m0_rebuild_ok=m0_ok,
                    transform_math_ok=True, qualified_M0=qualified,
                    ground=dict(geometric_validated_local=qualified, identity_confirmed=False,
                                physical_verified=False, runtime_eligible=False,
                                reason='LOCAL_GEOMETRY_ONLY; NO_GROUND_IDENTITY; NO_PHYSICAL_HEIGHT'))
                qualification_done = True
            qualified = bool(qualification and qualification['qualified_M0'] and fi > available_after)
            r, rows, hits = engine.step(dict(f, xyz=local, coordinate_version=T.version,
                                            relative_s=t), phase, qualified=qualified)
            if r['reset']:
                resets[str(fi)] = r['reset']
            # per-frame domain statistics over the frozen patches
            z = local[:, 2]
            if fi in val:
                for name in PATCH_NAMES:
                    rows_d = local_rows(dom_rows[name]['val'], fi, f['offset'])
                    if rows_d is None or not len(rows_d):
                        val_frames[name][str(fi)] = dict(count=0, PASS=False, reason='NO_ROWS')
                        continue
                    st = patch_frame_stats(z[rows_d])
                    val_frames[name][str(fi)] = st
                    pooled[name][0].append(z[rows_d])
                    pooled[name][1].append(local[rows_d][:, :2])
            acct = r['accounting']
            if acct['ledger_rows'] != acct['raw']:
                raise ValueError('ledger rows != raw rows at fi %d' % fi)
            rec = dict(fi=fi, relative_s=t, time_ns=f['time_ns'], offset=f['offset'],
                       transform_id=T.id, coordinate_version=T.version,
                       map_id=r['map_id'], variant=r['variant'], phase=phase, reset=r['reset'],
                       qualified=bool(r['qualified_M0']), candidate_map_exists=r['candidate_map_exists'],
                       rows=acct['raw'], valid=acct['valid'], invalid=acct['invalid'],
                       labels=acct['labels'], candidates=len(r['candidates']),
                       candidate_rows=acct['candidate_member_rows'], measured_target=acct['measured_target'],
                       track=dict(state=r['track']['state'], center=r['track']['center'],
                                  rows=len(r['track']['rows']), measured_count=r['track']['measured_count']),
                       map_hits=int(len(hits)),
                       online_state=online_state(fi, available_after, bool(r['qualified_M0'])),
                       offline_preview='S3_LOCAL_PREVIEW',
                       m0_exists=bool(frozen.map_id), ground=r['ground'],
                       rejected=len(r['rejected_unknown_objects']))
            frame_log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            C.save_array(run / 'frames' / ('%04d.npz' % fi), current=rows,
                         map_hits=np.asarray(hits, dtype='i4'))
            totals['rows'] += acct['raw']
            totals['valid'] += acct['valid']
            totals['invalid'] += acct['invalid']
            totals['candidates'] += len(r['candidates'])
            totals['member_rows'] += acct['candidate_member_rows']
            totals['track_rows'] += len(r['track']['rows'])
            totals['bg'] += acct['labels']['bg_match']
            labels_total += np.array([acct['labels'][k] for k in pipe.LABELS], dtype='i8')
            if fi % 50 == 0:
                print(json.dumps(dict(fi=fi, t=round(t, 2), surfaces=frozen.n,
                                      elapsed=round(time.perf_counter() - t0, 1), rss=rss.peak)), flush=True)
            if rss.peak > protocol['budget']['peak_rss_bytes']:
                raise MemoryError('Pre-registered RSS budget exceeded')
            if time.perf_counter() - t0 > protocol['budget']['full_s']:
                raise TimeoutError('Pre-registered wall budget exceeded')
        frame_log.close()
        if frozen.fingerprint() != frozen.map_id:
            raise ValueError('Frozen map arrays drifted during the run')
        final_binding = {k: C.sha(C.SOURCE / n) for k, n in [('meta', 'meta.json'), ('points', 'points.bin')]}
        if final_binding != src.binding:
            raise ValueError('Source changed during the run')
        out_bytes = sum(p.stat().st_size for p in C.OUT.rglob('*') if p.is_file())
        if out_bytes > protocol['budget']['output_bytes']:
            raise OSError('Output budget exceeded')
        conservation = dict(rows=int(totals['rows']), valid=int(totals['valid']), invalid=int(totals['invalid']),
                            rows_expected=38298918, valid_expected=29049839, invalid_expected=9249079,
                            labels=dict(zip(pipe.LABELS, [int(x) for x in labels_total])),
                            resets=resets, PASS=bool(totals['rows'] == 38298918 and totals['valid'] == 29049839
                                                     and totals['invalid'] == 9249079))
        C.write(run / 'FRAME_CONSERVATION.json', conservation)
        verification = dict(
            item=C.ITEM, transform_id=T.id, coordinate_version=T.version, domains_sha=dom['domains_sha'],
            protocol_sha=C.sha(C.OUT / 'PROTOCOL_V2.json'), gates=GATE,
            spatial=qualification['spatial_patches'], spatial_pass_patches=qualification['spatial_pass_patches'],
            spatial_required=2, temporal=dict(frames=qualification['temporal_frames'],
                                              all_pass_frames=qualification['temporal_all_pass_frames'],
                                              fraction=qualification['temporal_pass_fraction'],
                                              required=0.95, PASS=qualification['temporal_PASS'],
                                              frame_pass=qualification['temporal_frame_pass'],
                                              per_frame={k: {n: v for n, v in val_frames[k].items()}
                                                         for k in PATCH_NAMES}),
            prefix=prefix, m0_rebuild_ok=qualification['m0_rebuild_ok'],
            qualified_M0=qualification['qualified_M0'],
            state_from_271=('GEOMETRY_VALIDATED_LOCAL' if qualification['qualified_M0']
                            else 'CANDIDATE_PLANE_PREVIEW'),
            ground=qualification['ground'],
            identity='NOT_CONFIRMED', physical='NOT_RUN', independent_D='BLOCKED',
            noise_reference={}, note='noise reference is reported only; it never moves a gate')
        for name in PATCH_NAMES:
            med = [v['median_signed_m'] for v in val_frames[name].values() if 'median_signed_m' in v]
            verification['noise_reference'][name] = dict(
                frames=len(med), cross_frame_median_std_m=float(np.std(med)) if med else None,
                cross_frame_median_span_m=float(max(med) - min(med)) if med else None)
        C.write(run / 'VERIFICATION.json', verification)
        C.write(run / 'EVALUATION.json', dict(
            stage='REAL_DIAGNOSTIC', effectiveness_pass=None, effectiveness_status='BLOCKED',
            reason='NO_LABELS_IS_NOT_ZERO_CONTAMINATION', point_retention=None, point_purity=None,
            known_background_mixing=None, id_switches=None, first_discovery_delay_s=None,
            maximum_measured_gap_s=None, false_track_duration_s=None, annotation_coverage=0,
            independent_result=None, development_seen=True, dev_tainted=True))
        C.write(run / 'SUMMARY.json', dict(
            item=C.ITEM, frames=len(times), transform_id=T.id, coordinate_version=T.version,
            domain_patches=[(p['id'], p['rect_uv'], p['purity']) for p in dom['patches']],
            totals=totals, conservation=conservation['PASS'],
            surfaces=frozen.n, eligible_surfaces=int(frozen.eligible.sum()), map_id=frozen.map_id,
            map_id_matches_frozen=bool(frozen.map_id == m0doc['primary']['map_id']),
            qualification=dict(qualified_M0=qualification['qualified_M0'],
                               spatial_pass=qualification['spatial_pass_patches'],
                               temporal=qualification['temporal_pass_fraction'],
                               prefix_pass=prefix['PASS'],
                               state_from_271=verification['state_from_271']),
            seconds=time.perf_counter() - t0, peak_rss_bytes=int(rss.peak), output_bytes=int(out_bytes),
            budget=protocol['budget'], all_rows_processed=True,
            raw_xyz_invalid_rows='kept at original values; only valid XYZ transformed',
            algorithm='r01 Engine/thresholds unchanged; variant main; M0 r01 semantics',
            development_seen=True, dev_tainted=True))
        C.write(C.OUT / 'PERFORMANCE.json', dict(
            item=C.ITEM, full_wall_seconds=time.perf_counter() - t0, peak_rss_bytes=int(rss.peak),
            output_bytes=int(out_bytes), m0_build_seconds=m0doc['primary']['seconds'],
            budget=protocol['budget'], frames=len(times),
            within_budget=bool(time.perf_counter() - t0 <= protocol['budget']['full_s']
                               and rss.peak <= protocol['budget']['peak_rss_bytes']
                               and out_bytes <= protocol['budget']['output_bytes'])))
        rss.stop = True
        rss.join()
        print(json.dumps(dict(qualified=qualification['qualified_M0'],
                              spatial=qualification['spatial_pass_patches'],
                              temporal=qualification['temporal_pass_fraction'],
                              prefix_pass=prefix['PASS'],
                              seconds=round(time.perf_counter() - t0, 1), rss=int(rss.peak),
                              out_bytes=int(out_bytes)), ensure_ascii=False))
    finally:
        try:
            frame_log.close()
        except Exception:
            pass
        src.close()
