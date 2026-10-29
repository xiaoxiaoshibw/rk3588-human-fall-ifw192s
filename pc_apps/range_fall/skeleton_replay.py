"""Add point-supported skeletons to a verified analysis, preserving its rules.

Writes a new directory; sessions and previous evidence remain read-only.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
from core.range_skeleton import estimate, project_regions, VERSION, SETTINGS
from core.range_image import ScanGrid
from core.range_contract import binding_tuple
from analysis import AnalysisStore, content_sha, sha_file


def replay(analysis, data_root, out):
    analysis, out = Path(analysis), Path(out)
    store = AnalysisStore([analysis], data_root)
    original = next(iter(store.documents.values()))
    sid = original['sessionId']
    doc = copy.deepcopy(original)
    skeleton_sha = sha_file(ROOT/'src/human_fall_detection/core/range_skeleton.py')
    out.mkdir(parents=True, exist_ok=False)
    reasons, times = Counter(), []
    meta = json.loads((Path(data_root)/sid/'meta.json').read_text('utf-8'))
    sys.path.insert(0,str(ROOT/'src/human_fall_detection/scripts'))
    from replay_range_frontend import CALIBRATION
    grid = ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv', CALIBRATION/'ifw192s_elevation_192x256.csv')
    if grid.sha256 != doc['sourceBinding']['grid_sha256']:
        raise ValueError('skeleton projection calibration mismatch')
    with (Path(data_root)/sid/'points.bin').open('rb') as stream:
        for row in doc['frames']:
            i = row['frameIndex']
            store.frame(sid, i)  # Verify source bytes and current target box.
            f = meta['frames'][i]
            stream.seek(f['offset_points']*28)
            raw = stream.read(f['count_points']*28)
            points = np.frombuffer(raw, dtype='<f4').reshape(-1, 7)[row['sourceRows'], :3]
            start = time.perf_counter()
            row['skeleton'] = estimate(points, row['sourceRows'])
            times.append((time.perf_counter()-start)*1000)
            if row['skeleton'] != estimate(points, row['sourceRows']):
                raise ValueError('nondeterministic skeleton')
            project_regions(row['skeleton'], grid.decode(raw, binding_tuple(doc['sourceBinding'])))
            reasons[row['skeleton']['reason']] += 1
            # Preserve every depth export byte; validate through the existing API.
            if 'depth' in row:
                for kind in ('preview', 'metric', 'mask', 'metadata'):
                    asset = row['depth'][kind]
                    target = out/asset['path']
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(store.asset(sid, i, kind))
    doc['skeletonAlgorithm'] = dict(id='range-region-skeleton', version=VERSION, settings=SETTINGS,
        sourceSha256=skeleton_sha,
        humanJointAccuracy='UNKNOWN', headFootIdentity='UNKNOWN', leftRightIdentity='UNKNOWN')
    if skeleton_sha != sha_file(ROOT/'src/human_fall_detection/core/range_skeleton.py'):
        raise ValueError('skeleton source changed during replay; rerun in a new directory')
    doc['contentSha256'] = content_sha({k:v for k,v in doc.items() if k != 'contentSha256'})
    AnalysisStore.validate(doc)
    (out/'analysis.json').write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False, separators=(',', ':')), 'utf-8')
    summary = dict(session=sid, frames=len(doc['frames']), reasons=dict(reasons),
        framesWithEdges=sum(bool(r['skeleton']['edges']) for r in doc['frames']),
        nodes=dict(Counter(str(len(r['skeleton']['nodes'])) for r in doc['frames'])),
        ruleStates=dict(Counter(r['state'] for r in doc['frames'])),
        ruleFieldsUnchanged=all({k:v for k,v in a.items() if k != 'skeleton'} == b
                                for a,b in zip(doc['frames'], original['frames'])),
        sourceAnalysisSha256=sha_file(analysis), analysisSha256=sha_file(out/'analysis.json'),
        skeletonMs=dict(p50=float(np.percentile(times,50)),p95=float(np.percentile(times,95))),
        humanJointAccuracy='UNKNOWN', fallAccuracy='UNKNOWN')
    (out/'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf-8')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analysis', required=True, type=Path)
    p.add_argument('--data-root', default=ROOT/'data/sessions', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(replay(a.analysis, a.data_root, a.out), ensure_ascii=False))
