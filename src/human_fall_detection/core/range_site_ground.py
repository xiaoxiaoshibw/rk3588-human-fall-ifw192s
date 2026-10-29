"""RAM-only site fitting using the existing floor selector and quality estimators.

No empty-scene declaration: whole-height XY patches reject occluding objects.
Only derived planes, headers and statistics cross the evidence boundary.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
from .ground_fit.floor_roi import detect_floor_regions_v3
from .ground_fit.floor_sheet import _discover_planes
from .ground_fit.leveling_estimators import ESTIMATORS
from .ground_fit.leveling_quality import PROFILE, compare, rotation, statistics

FIT_FRAMES = 25  # existing prepare_leveling / ablate fit count
HELD_FRAMES = PROFILE['holdout_frames']


def region_codes(points, initial, regions):
    xy = (points @ np.asarray(initial).T)[:, :2]
    codes = np.zeros(len(points), dtype=int)
    for i, (xl, xh, yl, yh) in enumerate(regions, 1):
        codes[(xy[:, 0] >= xl) & (xy[:, 0] < xh) & (xy[:, 1] >= yl) & (xy[:, 1] < yh)] = i
    return codes


def residuals(points, normal, offset):
    report = statistics(points, normal, offset)
    if len(points):
        r = np.abs(points @ normal + offset)
        report.update(median_abs_m=float(np.median(r)), max_abs_m=float(r.max()),
                      inliers=int((r <= PROFILE['inlier_threshold_m']).sum()))
    return report


def fit_site(samples, headers, binding, source):
    """One fixed attempt; held frames never select patches or fit the plane."""
    report = dict(format='live_ground_fit/1', status='unavailable', binding=binding, source=source,
        headers=headers, units='m', coordinate='RAW/' + binding['frameId'],
        formula='height_m = dot(raw_xyz_m, normal) + offset_m',
        physicalGroundTruth='UNKNOWN', settings=dict(PROFILE), rawCloudsRecorded=False,
        fitFrames=list(range(FIT_FRAMES)), heldFrames=list(range(FIT_FRAMES, FIT_FRAMES + HELD_FRAMES)))
    try:
        if len(samples) != FIT_FRAMES + HELD_FRAMES or len(headers) != len(samples):
            raise ValueError('fit requires 25 fit and 3 independent held frames')
        for a, b in zip(headers, headers[1:]):
            dt = b['sec'] + b['nsec']/1e9 - a['sec'] - a['nsec']/1e9
            if b['seq'] != a['seq'] + 1 or not 0 < dt <= .3:
                raise ValueError('fit_source_discontinuous')
        if any(h['frame_id'] != binding['frameId'] for h in headers):
            raise ValueError('fit_frame_mismatch')
        clean = []
        for p in samples:
            p = np.asarray(p, dtype=float)
            if p.ndim != 2 or p.shape[1] != 3: raise ValueError('bad fit points')
            clean.append(p[np.isfinite(p).all(1) & np.any(p != 0, 1) & (np.abs(p) <= 100).all(1)])
        report['inputCounts'] = [len(p) for p in clean]
        if any(len(p) < 120 for p in clean): raise ValueError('insufficient_scene_points')
        n, d = ESTIMATORS['ransac'](clean[0][::8])
        if n[2] < 0: n, d = -n, -d
        report['seed'] = dict(normal=n.tolist(), offset_m=float(d))
        # Same existing ablate/prepare_leveling seed plausibility gate.
        if n[2] < .8 or not .8 <= d <= 1.8: raise ValueError('seed_ground_orientation_or_height_implausible')
        initial = rotation(math.degrees(math.atan2(-n[0], n[2])), math.degrees(math.asin(float(n[1]))))
        points = np.concatenate(clean[:FIT_FRAMES])
        ids = np.concatenate([np.full(len(p), i) for i, p in enumerate(clean[:FIT_FRAMES])])
        report['discoveredPlanes'] = _discover_planes(points, initial[2])
        domain = detect_floor_regions_v3(points, ids, math.degrees(math.atan2(-n[0], n[2])),
                                         math.degrees(math.asin(float(n[1]))))
        report['domain'] = domain
        codes = region_codes(points, initial, domain['regions'])
        selected = points[codes > 0]
        held = []
        for i in range(FIT_FRAMES, len(clean)):
            hc = region_codes(clean[i], initial, domain['regions'])
            held.append(dict(ordinal=i, points=clean[i][hc > 0], regions=hc[hc > 0]))
        quality = compare(selected, codes[codes > 0], held, initial[2])
        report['quality'] = quality
        if quality['consensus'] != 'GOOD': raise ValueError('existing_quality_rejected')
        fitted = quality['estimators'][quality['recommended']]
        n, d = np.asarray(fitted['normal_source']), fitted['offset_source_m']
        report['plane'] = dict(normal=n.tolist(), offset_m=d)
        report['monitor'] = dict(initial=initial.tolist(), regions=domain['regions'])
        report['selected'] = residuals(selected, n, d)
        report['selected']['fractionOfScene'] = len(selected)/len(points)
        report['selected']['xyzSpanM'] = np.ptp(selected, axis=0).tolist()
        per_frame = []
        for i, p in enumerate(clean):
            c = region_codes(p, initial, domain['regions']); q = p[c > 0]
            entry = dict(frame=i, **residuals(q, n, d))
            if len(q) < PROFILE['min_points_per_region']: raise ValueError('per_frame_support_insufficient')
            fn, fd = ESTIMATORS['tls'](q)
            if fn @ n < 0: fn, fd = -fn, -fd
            entry.update(normal=fn.tolist(), offset_m=float(fd),
                angleDeg=math.degrees(math.acos(float(np.clip(fn @ n, -1, 1)))), offsetGapM=abs(fd-d))
            per_frame.append(entry)
        report['perFrame'] = per_frame
        if any(p['angleDeg'] > PROFILE['normal_gap_max_deg'] or p['offsetGapM'] > PROFILE['offset_gap_max_m']
               or p['status'] != 'PASS' for p in per_frame): raise ValueError('multiframe_plane_unstable')
        if n[2] <= 0 or d <= 0: raise ValueError('normal_sign_invalid')
        report.update(status='geometry_accepted', reason='existing_floor_and_quality_gates_passed',
            signCheck=dict(sensorHeightM=d, positiveDirection=n.tolist(),
                           sensorAbovePlane=True, physicalUp='UNKNOWN'))
    except (ValueError, TypeError, np.linalg.LinAlgError) as exc:
        report.update(status='unavailable', reason=str(exc))
    return report


def save_fit(report, out):
    out = Path(out).resolve()
    if any(out == p.resolve() or p.resolve() in out.parents for p in (ROOT/'data', ROOT/'captures')):
        raise ValueError('ground evidence must be outside source data')
    out.mkdir(parents=True, exist_ok=True)
    provenance = out/'GROUND_FIT.json'
    with provenance.open('x', encoding='utf8') as f: json.dump(report, f, indent=2, allow_nan=False)
    if report['status'] != 'geometry_accepted': return None
    doc = dict(format='live_site_ground/1', binding=report['binding'], plane=report['plane'],
               provenance=dict(source=str(provenance), sha256=hashlib.sha256(provenance.read_bytes()).hexdigest()))
    target = out/'SITE_GROUND.json'
    with target.open('x', encoding='utf8') as f: json.dump(doc, f, indent=2, allow_nan=False)
    return target


def monitor(points, ground):
    """Full-height frozen patches; occlusion suspends height, never refits it."""
    spec = ground['monitor']; n = np.asarray(ground['normal']); d = ground['offset_m']
    codes = region_codes(points, spec['initial'], spec['regions'])
    reports = [residuals(points[codes == i], n, d) for i in range(1, 5)]
    # Existing constrained ground requires >=3 independent validation regions.
    usable = sum(r['status'] == 'PASS' for r in reports) >= 3
    return dict(available=usable, reason='current_patch_support' if usable else 'ground_patch_support_or_residual_failed',
                regions=reports, physicalGroundTruth='UNKNOWN')


def site_ground(path, frame_id, grid_sha, site_id, identity):
    """Explicit site declaration, never reinterpret an offline session ground."""
    if not site_id:raise ValueError('live ground requires an explicit site id')
    doc=json.loads(Path(path).read_text('utf8'))
    binding=dict(siteId=site_id,frameId=frame_id,gridSha256=grid_sha)
    if doc.get('format')!='live_site_ground/1' or doc.get('binding')!=binding:
        raise ValueError('live ground site/frame/calibration mismatch; offline ground is not applicable')
    provenance=doc.get('provenance',{})
    raw=Path(provenance['source']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=provenance.get('sha256'):raise ValueError('live ground provenance changed')
    original=json.loads(raw)
    if original.get('binding')!=binding or original.get('plane')!=doc.get('plane'):
        raise ValueError('live ground plane/provenance mismatch')
    if (original.get('format')!='live_ground_fit/1' or original.get('status')!='geometry_accepted'
            or (original.get('quality') or {}).get('consensus')!='GOOD'
            or len(original.get('headers',[]))!=28 or len(original.get('perFrame',[]))!=28
            or not original.get('monitor') or not original.get('source')):
        raise ValueError('live ground requires accepted quality and continuous source evidence')
    from .range_site_ground import PROFILE
    quality=original['quality']
    if (set(quality.get('estimators',{}))!={'tls','svd','ransac'}
            or not all(e.get('valid') is True for e in quality['estimators'].values())
            or not all(p.get('status')=='PASS' for p in quality.get('pairwise',[]))
            or any(p.get('status')!='PASS' or p['angleDeg']>PROFILE['normal_gap_max_deg']
                   or p['offsetGapM']>PROFILE['offset_gap_max_m'] for p in original['perFrame'])):
        raise ValueError('live ground quality evidence rejected')
    headers=original['headers']
    if any(h['frame_id']!=frame_id for h in headers):raise ValueError('ground source frame mismatch')
    for a,b in zip(headers,headers[1:]):
        dt=b['sec']+b['nsec']/1e9-a['sec']-a['nsec']/1e9
        if b['seq']!=a['seq']+1 or not 0<dt<=.3:raise ValueError('ground source discontinuity')
    plane=doc['plane'];normal=np.asarray(plane['normal'],dtype=float);offset=float(plane['offset_m'])
    if (normal.shape!=(3,) or not np.isfinite(normal).all() or abs(np.linalg.norm(normal)-1)>1e-6
            or not np.isfinite(offset) or offset<=0 or normal[2]<=0):
        raise ValueError('invalid live ground plane')
    return dict(status='valid',frame=frame_id,normal=normal.tolist(),offset_m=offset,binding=identity,
                provenance=provenance,monitor=original['monitor'],source=original['source'],
                fitLastHeader=original['headers'][-1],siteBinding=binding,
                physical_applicability='GEOMETRY_CHECKED_PHYSICAL_GROUND_UNKNOWN')


