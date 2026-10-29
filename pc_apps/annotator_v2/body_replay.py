"""Read-only two-view mapping replay; outputs new evidence, never session labels."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

import numpy as np

from server import AnalysisStore, _REPO_ROOT
from body_parts import BodyStore, map_region
from body_branches import METHOD, SETTINGS


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4*1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def replay(analyses, out, data_root):
    out = Path(out)
    out.mkdir(exist_ok=False, parents=True)
    store = AnalysisStore(analyses, data_root)
    body = BodyStore(store, out/'storage')
    summaries = []
    samples = {'cap_20261017_113516': [0, 400, 453, 550, 600, 650, 700, 750],
               'cap_20261018_110029': [0, 105, 120, 160, 200, 240, 350, 380]}
    descriptions = {'cap_20261017_113516': {0:'target_missing',400:'side_oblique_walking_appearance',453:'requested_focus_oblique_person',
        550:'frontal_or_back_appearance_identity_unknown',600:'arms_up_semantic_ambiguity',650:'oblique_appearance',
        700:'bent_low_partial_occlusion_appearance',750:'side_edge_partial_view'},
        'cap_20261018_110029': {0:'target_missing',105:'side_oblique_appearance',120:'side_oblique_appearance',
        160:'side_oblique_appearance',200:'frontal_or_back_arms_up_appearance',240:'frontal_or_back_arms_up_appearance',
        350:'frontal_or_back_arms_down_appearance',380:'side_oblique_appearance'}}
    before = {str(p): sha(p) for p in analyses}
    source_hashes = {name:sha(Path(__file__).parent/name) for name in ('body_parts.py','body_branches.py','body_replay.py')}
    for sid, doc in store.documents.items():
        ticks, stats = [], Counter()
        part_counts, unresolved = Counter(), Counter()
        with (out/(sid+'.jsonl')).open('x', encoding='utf-8') as ledger:
            for original in doc['frames']:
                start = time.perf_counter()
                index = original['frameIndex']
                c, xyz, indices = body.context(sid, index, 'candidate_'+(original['trackId'] or 'missing'))
                # Check every visible pixel against the source row, both directions.
                visible = indices[indices >= 0]
                assert len(set(visible.tolist())) == len(visible)
                assert np.isin(c['targetRows'], visible).all()
                mapped = body.suggest(c, xyz, indices)
                assert mapped == body.suggest(c, xyz, indices)
                legacy = body.suggest_legacy(c, xyz, indices)
                old_snapshot = Path(_REPO_ROOT)/'docs/evidence/2026-10-26_body_mapping/replay/storage/body_parts_v1'/sid/str(index)/(c['binding']['personId']+'.json')
                if old_snapshot.is_file():
                    old = json.loads(old_snapshot.read_text('utf-8'))['doc']
                    assert body.compute(c, xyz, indices, old) == old
                    stats['legacySavedDocumentsVerified'] += 1
                for part in mapped['parts']:
                    m = part['mapping']
                    for row, (x, y), point in zip(m['sourceRows'], m['imagePixels'], m['xyz']):
                        assert indices[y, x] == row
                        assert np.array_equal(xyz[row], point)
                    assert set(m['sourceRows']).issubset(c['targetRows'])
                    if m['sourceRows']:
                        part_counts[part['part']] += 1
                    else:
                        unresolved[part['origin']['evidence']['reason']] += 1
                chosen = [r for part in mapped['parts'] for r in part['mapping']['sourceRows']]
                assert len(chosen) == len(set(chosen))
                stats['unassignedTargetPoints'] += len(c['targetRows'])-len(chosen)
                full = map_region(indices, xyz, [0, 0, c['width'], c['height']], c['targetRows'])
                assert set(full['sourceRows']) == set(c['targetRows'])
                assert full['excludedOutsideScope'] == len(visible)-len(c['targetRows'])
                stats['frames'] += 1
                stats['validPixels'] += len(visible)
                stats['targetPixels'] += len(c['targetRows'])
                stats['mappedPartPoints'] += sum(len(p['mapping']['sourceRows']) for p in mapped['parts'])
                stats['emptyTargetFrames'] += not bool(c['targetRows'])
                stats['duplicateReturnsExcluded'] += len(c['duplicateReturnRows'])
                ticks.append((time.perf_counter()-start)*1000)
                entry = dict(frame=index, rawSha256=c['binding']['rawSha256'], targetRowsSha256=hashlib.sha256(np.asarray(c['targetRows'], dtype='<i8').tobytes()).hexdigest(),
                    trackId=original['trackId'], generation=original['generation'], state=original['state'],
                    posture=original.get('posture'), targetPoints=len(c['targetRows']),
                    parts={p['part']:len(p['mapping']['sourceRows']) for p in mapped['parts']},
                    unresolved={p['part']:p['origin']['evidence']['reason'] for p in mapped['parts'] if not p['mapping']['sourceRows']},
                    legacyParts={p['part']:len(p['mapping']['sourceRows']) for p in legacy['parts']},
                    unassignedTargetPoints=len(c['targetRows'])-len(chosen),
                    headTorso=mapped['geometry']['headTorso'], torso=mapped['geometry']['parts'].get('torso'),
                    roundtrip='PASS', geometrySemantic='UNKNOWN', durationMs=ticks[-1])
                ledger.write(json.dumps(entry, ensure_ascii=False, allow_nan=False)+'\n')
                if index in samples.get(sid, []):
                    artifact = dict(appearanceCase=descriptions[sid][index], appearanceIsGT=False,
                        semanticAccuracy='UNKNOWN', annotation=mapped,
                        duplicateReturnRows=c['duplicateReturnRows'], originalState=original['state'],
                        originalPosture=original.get('posture'), validPixelCount=len(visible))
                    artifact['legacyAnnotation'] = legacy
                    (out/('%s_%03d_mapping.json'%(sid, index))).write_text(json.dumps(artifact, ensure_ascii=False, allow_nan=False, indent=2), 'utf-8')
                    saved = body.save(c, xyz, indices, dict(doc=mapped, baseVersion=0))
                    assert saved == body.load(c, xyz, indices)
                    for key, value in [('frameIndex', index+1), ('rawSha256', '0'*64), ('orientation', 'native'), ('personId', 'wrong'), ('calibration', {})]:
                        wrong = copy.deepcopy(mapped)
                        wrong['binding'][key] = value
                        try:
                            body.compute(c, xyz, indices, wrong)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError('accepted mismatched '+key)
        summaries.append(dict(session=sid, counts=dict(stats), latencyMs=dict(p50=float(np.percentile(ticks,50)), p95=float(np.percentile(ticks,95))),
            framesWithPartCandidates=dict(part_counts), unresolvedReasons=dict(unresolved),
            targetTrackingRulesDisplayInputsUnchanged=True, sampledCases=descriptions.get(sid),
            humanPartsAccuracy='UNKNOWN', postureAccuracy='UNKNOWN'))
    assert before == {str(p):sha(p) for p in analyses}
    assert source_hashes == {name:sha(Path(__file__).parent/name) for name in source_hashes}
    summary = dict(softwareMapping='PASS', sessions=summaries, sourceAnalysisSha256=before,
        inputSessions={sid:dict(metaSha256=doc['metaSha256'], pointsSha256=doc['pointsSha256']) for sid,doc in store.documents.items()},
        provenance=METHOD, settings=SETTINGS, sourceSha256=source_hashes,
        limitation='Observed surface branch hypotheses, not anatomical joints. Arc splits are not elbows/knees. A distal turn does not prove a foot or ground contact. Appearance cases are not GT.',
        humanPartsAccuracy='UNKNOWN', postureAccuracy='UNKNOWN', fallEventAccuracy='UNKNOWN', alarmModified=False)
    (out/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2), 'utf-8')
    return summary


def http_check(base, out):
    url = base+'/api/body/cap_20261017_113516/453?person=e2e_software_probe'
    def call(method, path, payload=None):
        request = urllib.request.Request(path, data=json.dumps(payload).encode() if payload is not None else None,
            method=method, headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    status, first = call('GET', url)
    assert status == 200
    status, suggested = call('POST', url, dict(action='suggest'))
    assert status == 200 and suggested['parts']
    status, saved = call('PUT', url, dict(baseVersion=first['version'], doc=suggested))
    assert status == 200
    status, loaded = call('GET', url)
    assert status == 200 and saved['doc'] == loaded['doc'] and saved['version'] == loaded['version']
    checks = {}
    for key, value in [('frameIndex',454),('rawSha256','0'*64),('personId','other'),('orientation','native'),('calibration',{})]:
        wrong = copy.deepcopy(suggested)
        wrong['binding'][key] = value
        status, error = call('POST', url, dict(doc=wrong))
        assert status == 409
        checks[key] = error
    status, error = call('PUT', url, dict(baseVersion=first['version'], doc=suggested))
    assert status == 409
    checks['versionConflict'] = error
    # Separate person/frame storage; no carry-over on frame 454.
    status, next_frame = call('GET', url.replace('/453?', '/454?'))
    assert status == 200 and next_frame['doc'] is None
    result = dict(status='PASS', savedVersion=saved['version'], points={p['part']:len(p['mapping']['sourceRows']) for p in suggested['parts']},
        nextFrameOverlay=None, rejected=checks, semanticAccuracy='UNKNOWN')
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', type=Path, action='append', default=[])
    parser.add_argument('--data-root', type=Path, default=Path(_REPO_ROOT)/'data/sessions')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--url')
    args = parser.parse_args()
    result = http_check(args.url, args.out) if args.url else replay(args.analysis, args.out, args.data_root)
    print(json.dumps(result, ensure_ascii=False))
