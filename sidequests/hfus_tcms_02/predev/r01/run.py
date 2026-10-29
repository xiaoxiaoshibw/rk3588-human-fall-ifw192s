"""All runs require explicit inputs and a fresh PREDEV evidence subdirectory."""
import argparse
import copy
import json
import platform
from pathlib import Path
import sys
import time
import numpy as np
import scipy
from contracts import HERE, ROOT, Source, digest, module, new_output, sha, write_new
from pipeline import ABLATIONS, DEFAULTS, Engine, FrozenMap, ground_candidate
from evaluate import evaluate
import fixtures


def environment():
    return dict(python=sys.version, executable=sys.executable, numpy=np.__version__, scipy=scipy.__version__,
                platform=platform.platform(), argv=sys.argv, seed=DEFAULTS['seed'], units='m',
                clock='integer device ns; unanchored across sessions',
                source_sha256={str(p.relative_to(ROOT)): sha(p) for p in HERE.iterdir() if p.is_file()},
                dependency_sha256={str(p.relative_to(ROOT)): sha(p) for p in [
                    ROOT / 'sidequests/human_fusion_lab_next/pointset/r01/next_contract.py',
                    ROOT / 'sidequests/human_fusion_lab_next/pointset/r01/scene_change.py',
                    ROOT / 'sidequests/hfus_tcms/tcms.py',
                    ROOT / 'sidequests/hfus_tcms/run_experiment.py',
                    ROOT / 'src/human_fall_detection/core/ground.py',
                    ROOT / 'src/human_fall_detection/core/calibration.py']})


def replay(source, frozen, ground, variant, confirmations=None, simulate=False, stop=None):
    engine = Engine(frozen, ground, variant)
    records = []
    for fi in range(len(source.frames) if stop is None else stop):
        f = source.frame(fi)
        r = engine.step(f)
        request = next((q for q in confirmations or [] if q['fi'] == fi), None)
        if simulate and fi == 1 and variant != 'no_identity':
            c = min(r['candidates'], key=lambda c: abs(c['center'][0] - 1.9))
            request = dict(sid=f['sid'], fi=fi, source_sha256=f['source_sha256'],
                           time_ns=f['time_ns'],
                           coordinate_version=f['coordinate_version'], candidate_version=c['version'],
                           reviewer='FIXTURE_SIMULATOR_NOT_A_HUMAN', provenance='SYNTHETIC_SIMULATED_CONFIRMATION')
        if request:
            engine.confirm(f, r, request)
        records.append(r)
    return records


def save_run(output, entries, records, cases, manifest, metrics):
    executed = output / 'EXECUTED_SOURCE'
    executed.mkdir(exist_ok=False)
    for p in HERE.iterdir():
        if p.is_file():
            with (executed / p.name).open('xb') as stream:
                stream.write(p.read_bytes())
    dependency_dir = output / 'DEPENDENCIES'
    dependency_dir.mkdir(exist_ok=False)
    env = environment()
    for name in env['dependency_sha256']:
        target = dependency_dir / name
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write((ROOT/name).read_bytes())
    final = []
    for e in entries:
        binding = {k:sha(Path(e['path']) / n) for k,n in [('meta','meta.json'),('points','points.bin')]}
        if binding != e['source_sha256']:
            raise ValueError('Input changed during execution')
        final.append(dict(sid=e['sid'], source_sha256=binding,
                          bytes={n:(Path(e['path']) / n).stat().st_size for n in ['meta.json','points.bin']}))
    write_new(output / 'SOURCES_FINAL.json', final)
    write_new(output / 'INPUT_MANIFEST.json', manifest)
    write_new(output / 'ENVIRONMENT.json', env)
    write_new(output / 'EVALUATION_CONTRACT_ONLY.json', metrics)
    write_new(output / 'REPLAY.json', dict(schema='hfus-predev-replay/1', entries=entries, cases=cases,
                                        records=records, real_status='BLOCKED', contract_only=True))
    index = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    index.update({str(p.relative_to(output)).replace('\\','/'):sha(p)
                  for directory in [executed,dependency_dir] for p in directory.rglob('*') if p.is_file()})
    write_new(output / 'OUTPUT_INDEX.json', index)


def synthetic(output):
    fixture = fixtures.build(output / 'inputs')
    a, b = Source(fixture['map_entry']), Source(fixture['action_entry'])
    try:
        qualification = ground_candidate(a.frame(0)['xyz'], fixture['ground_spec'])
        if not qualification['geometric_valid']:
            raise ValueError('Ground fixture failed: %s' % qualification['reason'])
        frozen = FrozenMap([a.frame(0)], fixture['authorization'])
        records, ablations = [], {}
        for variant in ABLATIONS:
            rows = replay(b, frozen, qualification, variant, simulate=True)
            records.extend(rows)
            ablations[variant] = dict(toggled_step=ABLATIONS[variant],
                                     evaluation=evaluate(rows, fixture['labels'], 'SYNTHETIC'),
                                     steps=rows[0]['steps'],
                                     source_rows_by_frame=[dict(fi=r['fi'], target=r['track']['rows'],
                                                               candidates=[c['rows'] for c in r['candidates']]) for r in rows])
        full = [r for r in records if r['variant'] == 'full']
        baseline_members = ablations['full']['source_rows_by_frame']
        for variant,row in ablations.items():
            row['source_members_differ_vs_full'] = row['source_rows_by_frame'] != baseline_members
            row['interpretation'] = ('Reference configuration; no disabled step' if variant == 'full' else
                                     'Fixture members differ; no effectiveness claim' if row['source_members_differ_vs_full']
                                     else 'No member difference in these fixtures; path switch verified by separate boundary probes; no benefit claimed')
        prefix = []
        for n in range(1, len(b.frames) + 1):
            recomputed = replay(b, frozen, qualification, 'full', simulate=True, stop=n)
            ok = digest(recomputed) == digest(full[:n])
            prefix.append(dict(prefix_frames=n, identical=ok))
        if not all(r['identical'] for r in prefix):
            raise ValueError('Causal prefix mismatch')
        write_new(output / 'PREFIX_CHECK.json', prefix)
        write_new(output / 'ABLATIONS.json', ablations)
        write_new(output / 'GROUND_SPEC.json', fixture['ground_spec'])
        write_new(output / 'LABELS_SYNTHETIC.json', fixture['labels'])
        # Separate explicit angular capability fixture; does not enable real inference.
        near = a.frame(0)['xyz'][[10,40,80]] * .6
        ve = fixtures.write_source(output/'inputs'/'synthetic_visibility', [a.frame(0)['xyz'],near])
        vs = Source(ve)
        try:
            auth = copy.deepcopy(fixture['authorization'])
            auth.update(origin_xyz=[0.,0.,0.], return_mode_verified=True, angular_support_verified=True)
            visibility_map = FrozenMap([a.frame(0)],auth)
            visibility_records = replay(vs,visibility_map,qualification,'full')
            records.extend(visibility_records)
        finally:
            vs.close()
        cases = [dict(c,sid=b.sid) for c in fixture['cases']]
        cases.append(dict(name='合成角域近回波：仅遮挡候选',fi=1,sid=ve['sid'],kind='SYNTHETIC',contract_only=True))
        save_run(output, [fixture['map_entry'], fixture['action_entry'], ve], records, cases,
                 dict(kind='SYNTHETIC', contract_only=True, fixture=fixture, config=DEFAULTS,
                      map_id=frozen.map_id, map_sha_after=frozen.fingerprint(),
                      source_observation_history='Constructed and iterated; no independent evidence',
                      synthetic_angular_authorization=auth,
                      real_A_D_results=None), ablations['full']['evaluation'])
    finally:
        a.close()
        b.close()


def reused(output):
    """Only the TCMS-01 explicit list is eligible; no directory enumeration."""
    old = ROOT / 'docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1/run_r1'
    manifest = json.loads((old / 'MANIFEST.json').read_text(encoding='utf8'))
    entries, audit, records = [], [], []
    for sid, bindings in manifest['sources'].items():
        path = Path(next(p for p in bindings if p.endswith('meta.json'))).parent
        entry = dict(sid=sid, path=str(path), source_sha256={
            'meta': bindings[str(path / 'meta.json').replace('\\', '/') ] if str(path / 'meta.json').replace('\\', '/') in bindings else next(h for p, h in bindings.items() if p.endswith('meta.json')),
            'points': next(h for p, h in bindings.items() if p.endswith('points.bin'))},
                     coordinate_version='RAW_UNVERIFIED_INSTALLATION/v1', kind='REUSED_DIAGNOSTIC',
                     role='FAILURE_REGRESSION_ONLY', development_seen=True, dev_tainted=True,
                     influences='Software source/member regression only; cannot calibrate ground/M0 from this role',
                     observation_history=['TCMS-01 already observed and iterated', 'PREDEV raw source audit'],
                     audit_scope='Full source SHA/meta; selected diagnostic f100 only')
        try:
            source = Source(entry)
        except (ValueError, OSError) as exc:
            audit.append(dict(sid=sid, status='BLOCKED', reason=str(exc)))
            continue
        try:
            stamps = [f['stamp_sec'] + f['stamp_nanosec'] / 1e9 for f in source.frames]
            audit.append(dict(sid=sid, status='PASS', kind='REUSED_DIAGNOSTIC', binding=source.binding,
                              frames=len(stamps), device_duration_s=stamps[-1] - stamps[0]))
            entries.append(entry)
            if sid == 'cap_20261013_082623':
                records.append(Engine().step(source.frame(100)))
                records[-1]['variant'] = 'full'
                # Read-only B2/B3 pure functions; no old run/verify/main.
                tcms = module('predev_tcms_baseline', ROOT / 'sidequests/hfus_tcms/tcms.py')
                state = tcms.Window(.15, 10)
                thresholds = json.loads((old / 'THRESHOLDS.json').read_text(encoding='utf8'))
                # Export raw scores; threshold shape is validated explicitly below.
                baseline = []
                for fi in range(101):
                    f = source.frame(fi)
                    hits, rejected = tcms.support(f['xyz'], .15)
                    scores, status = state.update(hits, f['time_ns'] / 1e9)
                    if fi == 100:
                        for score in scores:
                            ids = hits[tuple(score['tile'])][1].tolist()
                            baseline.append(dict(scores=score, source_rows=ids,
                                                 active={m:tcms.active(score,thresholds['v0.15_w10'],m) for m in ['B2','B3']},
                                                 sid=sid, fi=fi, offset=f['offset']))
                write_new(output / 'B2_B3_READONLY_SCORES.json', dict(
                    schema='tcms-predev-baseline/1', kind='REUSED_DIAGNOSTIC', rows=baseline,
                    thresholds_original=thresholds, score_semantics='Original B2/B3 scores; no new pass-line calibration',
                    config=dict(voxel_m=.15, window_frames=10), source_sha256=source.binding))
        finally:
            source.close()
    write_new(output / 'REUSED_SOURCE_AUDIT.json', audit)
    cases = [dict(name='旧源 f100 失败诊断；无地面/可信M0/人工确认', fi=100,
                  sid='cap_20261013_082623', kind='REUSED_DIAGNOSTIC', contract_only=True)] if records else []
    save_run(output, entries, records, cases,
             dict(kind='REUSED_DIAGNOSTIC', entries=entries, m0='BLOCKED_NO_CURRENT_UNATTENDED_AUTHORIZATION',
                  ground='BLOCKED', A_D_results=None, independent_test=False), evaluate(records, None, 'REUSED_DIAGNOSTIC'))


def explicit(output, manifest_path, confirmation_path):
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf8'))
    if any(e['kind'] == 'REAL_DEVELOPMENT' for e in manifest['entries']):
        protocol = manifest.get('real_protocol', {})
        if any(not protocol.get(k) for k in ['pass_lines','matching_rules','annotation_coverage','development_split']):
            raise ValueError('Register A-C protocol/pass-lines/matching/coverage/development split before real experiment')
        if any(not l.get('sid') or not l.get('source_sha256') for l in manifest.get('labels', [])):
            raise ValueError('Real labels require sid/source SHA')
    entries = manifest['entries']
    sources = [Source(e) for e in entries]
    try:
        by_sid = {s.sid: s for s in sources}
        if len(by_sid) != len(sources):
            raise ValueError('Duplicate session')
        confirmations = json.loads(Path(confirmation_path).read_text(encoding='utf8')) if confirmation_path else []
        auth = manifest.get('map_authorization')
        map_frames = []
        if auth:
            for segment in auth['segments']:
                s = by_sid[segment['sid']]
                map_frames.extend(s.frame(i) for i in range(segment['start_fi'], segment['end_fi'] + 1))
        frozen = FrozenMap(map_frames, auth) if map_frames else None
        ground = ground_candidate(np.concatenate([f['xyz'] for f in map_frames]), manifest.get('ground_spec', {})) if map_frames else None
        records = []
        for s in sources:
            if s.entry.get('role') == 'MAP_ONLY':
                continue
            records.extend(replay(s, frozen, ground, manifest.get('variant', 'full'),
                                  confirmations=[q for q in confirmations if q['sid'] == s.sid]))
        save_run(output, entries, records, manifest.get('cases', []), manifest,
                 evaluate(records, manifest.get('labels'), entries[0]['kind']))
    finally:
        for s in sources:
            s.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--synthetic', action='store_true')
    mode.add_argument('--reused', action='store_true')
    mode.add_argument('--manifest')
    parser.add_argument('--confirm-file')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    out = new_output(args.out)
    started = time.perf_counter()
    if args.synthetic:
        synthetic(out)
    elif args.reused:
        reused(out)
    else:
        explicit(out, args.manifest, args.confirm_file)
    print(json.dumps(dict(status='SUBMITTED_CONTRACT_ONLY', output=str(out), elapsed_s=time.perf_counter() - started)))
