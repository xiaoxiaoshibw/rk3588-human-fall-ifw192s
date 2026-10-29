"""S4 run: tail and f430 root-cause decomposition, near-ground/contact layer, A/B/C/D diagnostics.

Nothing here changes a threshold or a plane. C (main with the inherited qualified boundary) runs
all 780 frames and keeps the ledger; A/B/D run only on the two registered diagnostic windows.
"""
import json
import sys
import threading
import time
from pathlib import Path
import numpy as np
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s4core as C

CONTACT = 0.10
NEAR = 0.30
WINDOWS = dict(tail=(745, 779), f430=(420, 449))


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


def band_counts(z, valid, bg, cand):
    absz = np.abs(z)
    out = {}
    for name, lo, hi in [('contact', -1.0, CONTACT), ('near_ground', CONTACT, NEAR), ('clear', NEAR, 1e9)]:
        m = valid & (absz > lo) & (absz <= hi)
        out[name] = dict(rows=int(m.sum()), bg=int((m & bg).sum()), candidate=int((m & cand).sum()),
                         free=int((m & ~bg & ~cand).sum()))
    return out


def decompose(rec, rows, valid, bg, cand, rejected):
    labels = rec['accounting']['labels']
    rej_total = sum(r['count'] for r in rejected)
    rej_by_reason = {}
    for r in rejected:
        rej_by_reason[r['reason']] = rej_by_reason.get(r['reason'], 0) + r['count']
    continuation = (rows['flags'] & 8) != 0
    seeds = (rows['flags'] & 4) != 0
    members = cand
    v, b, s, m = int(valid.sum()), int(bg.sum()), int(seeds.sum()), int(members.sum())
    ms = int((members & seeds).sum())
    mbg = int((members & bg).sum())
    rejected_rows = int((seeds & ~members).sum())
    parts = dict(valid=v, bg=b, seeds=s, continuation=int(continuation.sum()),
                 candidates=len(rec['candidates']), candidate_members=m,
                 members_from_seeds=ms, members_from_bg=mbg,
                 rejected_total=int(rej_total), rejected_rows_from_seeds=rejected_rows,
                 rejected_by_reason=rej_by_reason, labels=labels)
    # r01 defines seeds = valid & ~bg, so bg and seeds are a disjoint cover of valid rows.
    # Growth can add bg rows to a candidate, so bg and members overlap and must not be subtracted twice
    # (the first version of this function did exactly that; the old run is kept as FAILED_RUN_V1).
    parts['bg_plus_seeds_equals_valid'] = bool(b + s == v)
    parts['seeds_equals_members_plus_rejected'] = bool(s == ms + rejected_rows)
    parts['rejected_counts_match_rows'] = bool(rej_total == rejected_rows)
    parts['watertight'] = bool(parts['bg_plus_seeds_equals_valid']
                               and parts['seeds_equals_members_plus_rejected']
                               and parts['rejected_counts_match_rows'])
    parts['leftover'] = int(v - b - s)
    return parts


def main():
    protocol = C.load(C.OUT / 'PROTOCOL_V1.json')
    art = C.load(C.S3 / 'TRANSFORM/TRANSFORM_S3.json')
    m0doc = C.load(C.S3 / 'M0/M0.json')
    for rel, want in [('TRANSFORM/TRANSFORM_S3.json', C.FROZEN['transform']),
                      ('TRANSFORM/TRANSFORM_QUALIFICATION.json', C.FROZEN['qualification']),
                      ('DOMAINS/S3_DOMAINS.json', C.FROZEN['domains']),
                      ('DOMAINS/domains_s3.npz', C.FROZEN['domains_npz']),
                      ('M0/M0.json', C.FROZEN['m0'])]:
        if C.sha(C.S3 / rel) != want:
            raise SystemExit('S3 INHERITED INPUT DRIFT: ' + rel)
    if art['transform_id'] != C.FROZEN['transform_id'] or m0doc['primary']['map_id'] != C.FROZEN['m0_map_id']:
        raise SystemExit('S3 TRANSFORM/M0 ID DRIFT')
    X = C.r04_transform()
    T = X.Transform(art)
    if T.id != C.FROZEN['transform_id']:
        raise SystemExit('TRANSFORM LOAD MISMATCH')
    run = C.OUT / 'RUN'
    run.mkdir(exist_ok=False)
    (run / 'frames').mkdir()
    C.write(C.OUT / 'CONTACT_DEFINITION.json', dict(
        item=C.ITEM, plane='S3_LOCAL z=0, inherited from the S3 geometry-validated transform',
        contact_band_m=[-CONTACT, CONTACT], near_ground_band_m=[CONTACT, NEAR],
        clear_band_m=[NEAR, None], rule='interpretation label and diagnostic counter only',
        never=dict(deletes_rows=False, changes_xyz=False, changes_background_matching=False,
                   claims_physical_height=False, feeds_a_gate=False),
        variant_note='contact_aware is report-only: it adds the counters below to variant C, so DEFAULTS and the '
                     'candidate set are identical to S3 main (proved by PARAMETER_DIFF.json changed=[] and by the '
                     'candidate/member equality against S3 frames.jsonl on the shared frames)',
        added_counters=['contact/near_ground/clear row counts', 'rows in band explained by M0 (bg)',
                        'rows in band that are candidate members', 'per-frame rejected-by-reason histogram'],
        basis='no near-ground hard deletion, no height cut, no human/ground identity claim'))
    here = Path(__file__).resolve().parent
    C.write(run / 'CODE_AT_START.json', dict(
        argv=sys.argv, files={p.name: C.sha(p) for p in sorted(here.iterdir()) if p.is_file() and p.suffix in ('.py', '.js', '.html')},
        inherited=dict(transform=C.FROZEN['transform'], transform_id=C.FROZEN['transform_id'],
                       domains=C.FROZEN['domains_npz'], m0=C.FROZEN['m0_map_id'])))
    src, times = C.load_source()
    fit, val, pre = C.roles(times)
    pipe = C.r01_pipeline()
    C.write(run / 'PARAMETER_DIFF.json', dict(
        r01_defaults={k: float(v) if isinstance(v, float) else int(v) if isinstance(v, int) else v
                      for k, v in pipe.DEFAULTS.items()},
        s4_engine_config=None, note='Engine receives config=None so it copies r01 DEFAULTS verbatim',
        added_counters=['band contact/near_ground/clear row counts', 'contact rows explained by M0',
                        'per-frame rejected-by-reason histogram'],
        changed=[]))
    t0 = time.perf_counter()
    rss = Rss()
    rss.start()
    frozen = pipe.FrozenMap(run, src.binding, T.version, C.r04_map_protocol(T.version))
    engines = dict(A=pipe.Engine(frozen, 'no_frozen'), B=pipe.Engine(frozen, 'main'),
                   C=pipe.Engine(frozen, 'main'), D=pipe.Engine(frozen, 'no_growth'))
    run_version = C.digest(dict(protocol=C.sha(C.OUT / 'PROTOCOL_V1.json'), transform=T.id,
                                m0=C.FROZEN['m0_map_id']))
    for e in engines.values():
        e.run_version, e.protocol_sha = run_version, C.sha(C.OUT / 'PROTOCOL_V1.json')
    windows = {k: set(range(v[0], v[1] + 1)) for k, v in WINDOWS.items()}
    diag_frames = windows['tail'] | windows['f430']
    frames = {}
    total = dict(rows=0, valid=0, invalid=0, contact=0, near=0, contact_bg=0)
    log = open(run / 'frames.jsonl', 'x', encoding='utf8', newline='\n')
    try:
        for fi in range(len(times)):
            f = src.frame(fi)
            t = times[fi]
            local = T.points(f['xyz'], T.tag(fi, False), fi, source_validity=True)
            phase = 'MAP_BUILDING' if t < 20 else 'TEMPORAL_VALIDATION' if t < 28 else 'EMPTY_AUDIT' if t < 30 else 'ACTION'
            if t < 20:
                frozen.add(dict(f, xyz=local, coordinate_version=T.version, relative_s=t))
            elif frozen.map_id is None:
                frozen.freeze()
                frozen.bind_exact_time(src.stamps)
                if frozen.map_id != C.FROZEN['m0_map_id']:
                    raise ValueError('M0 fingerprint %s != inherited %s' % (frozen.map_id, C.FROZEN['m0_map_id']))
            qualified = fi >= 271           # inherited S3 unlock, never re-decided here
            recs = {}
            for key, e in engines.items():
                if key != 'C' and fi not in diag_frames:
                    continue
                r, rows, hits = e.step(dict(f, xyz=local, coordinate_version=T.version, relative_s=t),
                                       phase, qualified=qualified)
                _, valid = pipe.validity(f['xyz'])
                bg = (rows['flags'] & 2) != 0
                cand = rows['candidate'] >= 0
                z = local[:, 2]
                recs[key] = dict(record=r, rows=rows,
                                 decomp=decompose(r, rows, valid, bg, cand, r['rejected_unknown_objects']),
                                 bands=band_counts(z, valid, bg, cand),
                                 members=int(cand.sum()), bg=int(bg.sum()))
                if key == 'C':
                    C.save_array(run / 'frames' / ('%04d.npz' % fi), current=rows,
                                 map_hits=np.asarray(hits, dtype='i4'))
                    total['rows'] += r['accounting']['raw']
                    total['valid'] += r['accounting']['valid']
                    total['invalid'] += r['accounting']['invalid']
                    total['contact'] += recs[key]['bands']['contact']['rows']
                    total['near'] += recs[key]['bands']['near_ground']['rows']
                    total['contact_bg'] += recs[key]['bands']['contact']['bg']
                    log.write(json.dumps(dict(
                        fi=fi, t=t, transform_id=T.id, map_id=r['map_id'], phase=phase,
                        qualified=bool(r['qualified_M0']), rows=r['accounting']['raw'],
                        valid=r['accounting']['valid'], invalid=r['accounting']['invalid'],
                        labels=r['accounting']['labels'], candidates=len(r['candidates']),
                        decomp=recs[key]['decomp'], bands=recs[key]['bands'],
                        reset=r['reset']), ensure_ascii=False) + '\n')
            frames[fi] = {k: dict(candidates=len(v['record']['candidates']), members=v['members'], bg=v['bg'],
                                  decomp=v['decomp'], bands=v['bands'],
                                  rejected=[dict(count=x['count'], reason=x['reason'])
                                            for x in v['record']['rejected_unknown_objects']])
                          for k, v in recs.items()}
            if fi % 100 == 0:
                print(json.dumps(dict(fi=fi, t=round(t, 1), elapsed=round(time.perf_counter() - t0, 1),
                                      rss=rss.peak)), flush=True)
            if rss.peak > protocol['budget']['peak_rss_bytes']:
                raise MemoryError('RSS budget exceeded')
            if time.perf_counter() - t0 > protocol['budget']['full_s']:
                raise TimeoutError('wall budget exceeded')
        log.close()
        if frozen.fingerprint() != frozen.map_id:
            raise ValueError('map arrays drifted during the run')
        final = {k: C.sha(C.SOURCE / n) for k, n in [('meta', 'meta.json'), ('points', 'points.bin')]}
        if final != src.binding:
            raise ValueError('source changed during the run')

        def window_report(win):
            out = {}
            for fi in range(win[0], win[1] + 1):
                entry = frames.get(fi, {})
                row = {}
                for key, v in entry.items():
                    row[key] = dict(candidates=v['candidates'], members=v['members'], bg=v['bg'],
                                    contact=v['bands']['contact'], near_ground=v['bands']['near_ground'],
                                    rejected=v['rejected'], watertight=v['decomp']['watertight'],
                                    leftover=v['decomp']['leftover'], seeds=v['decomp']['seeds'])
                out[str(fi)] = row
            return out

        tail = window_report(WINDOWS['tail'])
        f430 = window_report(WINDOWS['f430'])
        zero_tail = [fi for fi in range(WINDOWS['tail'][0], WINDOWS['tail'][1] + 1) if frames[fi]['C']['candidates'] == 0]
        tail_reasons = {}
        for fi in zero_tail:
            v = frames[fi]['C']
            per = dict(seeds=v['decomp']['seeds'], rejected=v['rejected'], leftover=v['decomp']['leftover'],
                       contact_rows=v['bands']['contact']['rows'], contact_bg=v['bands']['contact']['bg'],
                       near_rows=v['bands']['near_ground']['rows'])
            if v['decomp']['seeds'] == 0:
                per['reason'] = 'NO_SEEDS_ALL_VALID_EXPLAINED_AS_BACKGROUND'
            elif v['rejected']:
                per['reason'] = 'GROUPS_REJECTED:' + ','.join(sorted({r['reason'] for r in v['rejected']}))
            else:
                per['reason'] = 'NO_GROUP_FORMED_OR_BELOW_EXTENT'
            tail_reasons[str(fi)] = per
        C.write(C.OUT / 'TAIL_DECOMPOSITION.json', dict(
            item=C.ITEM, window=list(WINDOWS['tail']), variant='C', frames=tail,
            zero_candidate_frames=zero_tail, zero_candidate_reasons=tail_reasons,
            contact_band_m=CONTACT, near_band_m=NEAR,
            summary=dict(frames=len(tail), zero=len(zero_tail),
                         contact_rows=int(sum(frames[fi]['C']['bands']['contact']['rows'] for fi in range(WINDOWS['tail'][0], WINDOWS['tail'][1] + 1))),
                         contact_bg=int(sum(frames[fi]['C']['bands']['contact']['bg'] for fi in range(WINDOWS['tail'][0], WINDOWS['tail'][1] + 1))),
                         all_watertight=all(frames[fi]['C']['decomp']['watertight'] for fi in range(WINDOWS['tail'][0], WINDOWS['tail'][1] + 1)))))
        C.write(C.OUT / 'F430_DECOMPOSITION.json', dict(
            item=C.ITEM, window=list(WINDOWS['f430']), variant='C', frames=f430,
            note='candidate presence only; this item has no identity and no track, so it cannot confirm or refute '
                 'the S1 LOST-at-439 event',
            summary=dict(frames=len(f430),
                         zero=[fi for fi in range(WINDOWS['f430'][0], WINDOWS['f430'][1] + 1) if frames[fi]['C']['candidates'] == 0],
                         all_watertight=all(frames[fi]['C']['decomp']['watertight'] for fi in range(WINDOWS['f430'][0], WINDOWS['f430'][1] + 1)))))
        abcd = {}
        for name, win in WINDOWS.items():
            abcd[name] = {}
            for fi in range(win[0], win[1] + 1):
                e = frames.get(fi, {})
                abcd[name][str(fi)] = {k: dict(candidates=e[k]['candidates'], members=e[k]['members'],
                                               bg=e[k]['bg'], contact=e[k]['bands']['contact']['rows'],
                                               contact_bg=e[k]['bands']['contact']['bg'])
                                       for k in sorted(e)}
        C.write(C.OUT / 'ABCD.json', dict(
            item=C.ITEM, windows={k: list(v) for k, v in WINDOWS.items()},
            definition=dict(A='no_frozen (no M0 background)', B='main with M0 but boundary disabled',
                            C='main with qualified boundary (inherited S3 unlock)', D='no_growth ablation'),
            frames=abcd,
            note='same frame, same source rows, same denominators; diagnostic counters only, no ranking and no '
                 'effectiveness metric because no labels exist'))
        C.write(run / 'EVALUATION.json', dict(
            stage='REAL_DIAGNOSTIC', effectiveness_pass=None, effectiveness_status='BLOCKED',
            reason='NO_LABELS_IS_NOT_ZERO_CONTAMINATION', point_retention=None, point_purity=None,
            known_background_mixing=None, id_switches=None, first_discovery_delay_s=None,
            maximum_measured_gap_s=None, false_track_duration_s=None, annotation_coverage=0,
            independent_result=None, development_seen=True, dev_tainted=True))
        out_bytes = sum(p.stat().st_size for p in C.OUT.rglob('*') if p.is_file())
        if out_bytes > protocol['budget']['output_bytes']:
            raise OSError('output budget exceeded')
        C.write(C.OUT / 'PERFORMANCE.json', dict(
            item=C.ITEM, seconds=time.perf_counter() - t0, peak_rss_bytes=int(rss.peak),
            output_bytes=int(out_bytes), frames_full=len(times), variant_frames=len(diag_frames),
            budget=protocol['budget'],
            within_budget=bool(time.perf_counter() - t0 <= protocol['budget']['full_s']
                               and rss.peak <= protocol['budget']['peak_rss_bytes']
                               and out_bytes <= protocol['budget']['output_bytes'])))
        C.write(C.OUT / 'SUMMARY.json', dict(
            item=C.ITEM, transform_id=T.id, map_id=frozen.map_id,
            map_matches_inherited=bool(frozen.map_id == C.FROZEN['m0_map_id']),
            totals=total, frames=len(times), diag_frames=sorted(diag_frames),
            tail_zero_frames=zero_tail, f430_zero_frames=[fi for fi in range(WINDOWS['f430'][0], WINDOWS['f430'][1] + 1)
                                                          if frames[fi]['C']['candidates'] == 0],
            watertight_all=all(frames[fi]['C']['decomp']['watertight'] for fi in range(len(times)) if fi in frames),
            state='GEOMETRY_VALIDATED_LOCAL inherited; identity NOT_CONFIRMED; human effect UNKNOWN',
            seconds=time.perf_counter() - t0, peak_rss_bytes=int(rss.peak), output_bytes=int(out_bytes)))
        rss.stop = True
        rss.join()
        print(json.dumps(dict(tail_zero=zero_tail, seconds=round(time.perf_counter() - t0, 1),
                              rss=int(rss.peak), out=int(out_bytes), tail_reasons=tail_reasons),
                        ensure_ascii=False))
    finally:
        try:
            log.close()
        except Exception:
            pass
        src.close()


if __name__ == '__main__':
    main()
