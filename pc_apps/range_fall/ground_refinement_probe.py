"""Compare a shadow RANSAC refinement on frozen offline site-fit domains.

Experimental only: never changes the production estimator or accepts live ground.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
from core.capture_input import ROW_DTYPE, sha256_file
from core import range_site_ground as site
from core.ground_fit import leveling_quality as quality


def compare_session(session):
    session = Path(session)
    identity = {name: sha256_file(session / name) for name in ('meta.json', 'points.bin')}
    meta = json.loads((session / 'meta.json').read_text(encoding='utf8'))
    frames = meta['frames'][:site.FIT_FRAMES + site.HELD_FRAMES]
    samples, headers = [], []
    with (session / 'points.bin').open('rb') as stream:
        for f in frames:
            stream.seek(f['offset_points'] * ROW_DTYPE.itemsize)
            raw = stream.read(f['count_points'] * ROW_DTYPE.itemsize)
            if len(raw) != f['count_points'] * ROW_DTYPE.itemsize:
                raise ValueError('truncated source frame')
            rows = np.frombuffer(raw, dtype=ROW_DTYPE)
            samples.append(np.column_stack((rows['x'], rows['y'], rows['z'])))
            headers.append(dict(seq=f['seq'], sec=f['stamp_sec'], nsec=f['stamp_nanosec'],
                                frame_id=meta['sensor']['frame_id']))
    original_compare, original_estimators = site.compare, quality.ESTIMATORS
    original_ransac, tls = original_estimators['ransac'], original_estimators['tls']
    observed = {}
    def refined(points):
        normal, offset = original_ransac(points)
        distance = np.abs(np.einsum('ij,j->i', points, normal) + offset)
        inliers = points[distance <= quality.PROFILE['inlier_threshold_m']]
        observed['inlier_count'] = int(len(inliers))
        observed['inlier_fraction'] = float(len(inliers) / len(points))
        if len(inliers) < 3:
            raise ValueError('refinement has too few inliers')
        return tls(inliers)
    def shadow_compare(points, regions, held, anchor, **kwargs):
        # This probe compares the historical raw estimator, even when fit_site
        # now opts into the production fit-region selection variant.
        observed['baseline'] = quality.compare(points, regions, held, anchor)
        try:
            quality.ESTIMATORS = dict(original_estimators, ransac=refined)
            candidate = quality.compare(points, regions, held, anchor)
        finally:
            quality.ESTIMATORS = original_estimators
        observed['candidate'] = candidate
        return candidate
    started = time.perf_counter()
    try:
        site.compare = shadow_compare
        report = site.fit_site(samples, headers,
            dict(siteId='OFFLINE_EXPERIMENT', frameId=meta['sensor']['frame_id'], gridSha256='UNBOUND'),
            dict(upstream='offline_existing_session', identity=identity))
    finally:
        site.compare = original_compare
        quality.ESTIMATORS = original_estimators
    if identity != {name: sha256_file(session / name) for name in identity}:
        raise RuntimeError('input changed during experiment')
    return dict(session=session.name, input_sha256=identity, fit=report, comparison=observed,
                elapsed_s=time.perf_counter()-started,
                scope='Retrospective 25+3 frames; empty scene not established; experimental only; no physical GT.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,action='append',required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    out=args.out.resolve()
    for protected in (ROOT/'data', ROOT/'captures'):
        protected=protected.resolve()
        if out == protected or protected in out.parents:
            raise ValueError('output must be outside data and captures')
    out.mkdir(parents=True,exist_ok=False)
    for session in args.session:
        result=compare_session(session)
        with (out/(session.name+'.json')).open('x',encoding='utf8') as f:
            json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
        c=result['comparison']; print(session.name, 'baseline',c.get('baseline',{}).get('consensus'),
            'candidate',c.get('candidate',{}).get('consensus'),'full',result['fit']['status'],
            'reason',result['fit'].get('reason'),'inliers',c.get('inlier_fraction'),flush=True)


if __name__=='__main__':main()
