"""Replay ground fitting on a captured diagnostic NPZ, with source-row images.

All plane alternatives are diagnostic: nothing is installed into a live runtime.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import numpy as np
from PIL import Image, ImageDraw

from ground_scene_probe import ROOT, write_json, safe_output
from core import range_site_ground as site
from core.ground_fit import leveling_quality as quality
from core.range_image import ScanGrid
from core.range_live import preview_rgb, pointcloud_rows
from depth import export_depth


def xyz(rows):
    return np.column_stack([rows[n] for n in ('x', 'y', 'z')]).astype(float)


def initial_rotation(report):
    n = np.asarray(report['seed']['normal'])
    return quality.rotation(math.degrees(math.atan2(-n[0], n[2])),
                            math.degrees(math.asin(float(n[1]))))


def clean_points(points):
    return points[np.isfinite(points).all(1) & np.any(points != 0, 1) & (np.abs(points) <= 100).all(1)]


def domain_arrays(samples, report):
    initial = initial_rotation(report)
    clean = [clean_points(p) for p in samples]
    points = np.concatenate(clean[:25])
    codes = site.region_codes(points, initial, report['domain']['regions'])
    held = []
    for i in range(25, 28):
        c = site.region_codes(clean[i], initial, report['domain']['regions'])
        held.append(dict(ordinal=i, points=clean[i][c > 0], regions=c[c > 0]))
    return points[codes > 0], codes[codes > 0], held


def candidate_scan(points, codes):
    """Only fit frames rank candidates; held frames never select a hypothesis."""
    rng = np.random.RandomState(20261001)
    ranked = []
    for iteration in range(861):
        ids = rng.randint(0, len(points), 3)
        sample = points[ids]
        n = np.cross(sample[1]-sample[0], sample[2]-sample[0])
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n = n/norm
        d = -float(n @ sample[0])
        residual = np.abs(points @ n + d)
        rms = [float(np.sqrt(np.mean(residual[codes == k]**2))) for k in range(1, 5)]
        feasible = quality.statistics(points, n, d)['status'] == 'PASS' and all(
            quality.statistics(points[codes == k], n, d)['status'] == 'PASS' for k in range(1, 5))
        ranked.append(dict(iteration=iteration, count=int((residual <= .05).sum()),
            median=float(np.median(residual)), region_rms=rms, fit_regions_pass=feasible,
            normal=n.tolist(), offset=d, sample_rows=ids.tolist()))
    ranked.sort(key=lambda r: (-r['count'], r['median'], r['iteration']))
    feasible = [i for i, r in enumerate(ranked) if r['fit_regions_pass']]
    return ranked, feasible


def audit_domain(samples, report):
    points, codes, held = domain_arrays(samples, report)
    base = quality.compare(points, codes, held, initial_rotation(report)[2])
    local = []
    tls = base['estimators']['tls']
    for k in range(1, 5):
        p = points[codes == k]
        n, d = quality.ESTIMATORS['tls'](p)
        if n @ np.asarray(tls['normal_source']) < 0:
            n, d = -n, -d
        local.append(dict(region=k, count=len(p), own_plane=quality.statistics(p, n, d),
            normal=n.tolist(), offset=float(d), center=p.mean(0).tolist(),
            span=np.ptp(p, axis=0).tolist(),
            normal_gap_to_global_tls_deg=float(np.degrees(np.arccos(np.clip(n @ tls['normal_source'], -1, 1))))))
    ranked, feasible = candidate_scan(points, codes)
    alternative = None
    if feasible:
        chosen = ranked[feasible[0]]
        original = quality.ESTIMATORS
        try:
            quality.ESTIMATORS = dict(original, ransac=lambda p: (np.asarray(chosen['normal']), chosen['offset']))
            alternative = quality.compare(points, codes, held, initial_rotation(report)[2])
        finally:
            quality.ESTIMATORS = original
    frozen = {}
    for name, est in report['quality']['estimators'].items():
        n, d = np.asarray(est['normal_source']), est['offset_source_m']
        frozen[name] = dict(full=quality.statistics(points,n,d),
            regions={str(k):quality.statistics(points[codes == k],n,d) for k in range(1,5)},
            holdouts=[dict(ordinal=h['ordinal'],regions={str(k):quality.statistics(
                h['points'][h['regions'] == k],n,d) for k in range(1,5)}) for h in held])
    return dict(baseline=base, local_planes=local, hypotheses=ranked, frozen_reference_planes=frozen,
        first_fit_feasible_rank=feasible[0] if feasible else None, feasible_count=len(feasible),
        fit_only_alternative=alternative, alternative_is_not_online=True)


def images(rows, headers, report, out, grid):
    palette = np.array([[255, 255, 255], [0, 255, 255], [255, 220, 0], [60, 255, 60], [255, 0, 255]], dtype='u1')
    initial = initial_rotation(report)
    records = []
    for i in (0, 13, 25, 27):
        frame = grid.decode(rows[i], ('diagnostic', i, grid.sha256))
        c = site.region_codes(xyz(rows[i]), initial, report['domain']['regions'])
        chosen = np.flatnonzero(c > 0)
        visible = np.intersect1d(chosen, frame.source_rows[frame.valid])
        descriptor = export_depth(frame, visible, out, i, headers[i]['sec']+headers[i]['nsec']/1e9,
            headers[i]['wire_sha256'], dict(session='diagnostic_capture', frame=i, gridSha256=grid.sha256))
        rgb = preview_rgb(frame)
        source = frame.source_rows[::-1, ::-1]
        valid = frame.valid[::-1, ::-1]
        mask = np.zeros(valid.shape, dtype=int)
        mask[valid] = c[source[valid]]
        marked = rgb.copy()
        marked[mask > 0] = palette[mask[mask > 0]]
        image = Image.fromarray(marked).resize((768, 576), Image.Resampling.NEAREST)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 768, 34), fill='black')
        draw.text((8, 8), 'seq %d | R1 cyan R2 yellow R3 green R4 magenta | black missing' % headers[i]['seq'], fill='white')
        image.save(out / ('regions_depth_%02d.png' % i))
        records.append(dict(frame=i, seq=headers[i]['seq'], decode_rejected={k:len(v) for k,v in frame.rejected.items()},
            valid_pixels=int(frame.valid.sum()), region_pixels={str(k):int((mask == k).sum()) for k in range(1, 5)},
            export=descriptor))
    # Side by side fit residuals on the same first-frame pixels.
    frame = grid.decode(rows[0], ('residual_diagnostic', grid.sha256))
    points = xyz(rows[0]); c = site.region_codes(points, initial, report['domain']['regions'])
    panels = []
    for name in ('tls', 'ransac'):
        est = report['quality']['estimators'][name]
        residual = points @ np.asarray(est['normal_source']) + est['offset_source_m']
        pixels = np.zeros(frame.valid.shape+(3,), dtype='u1')
        source = frame.source_rows[frame.valid]
        v = np.clip(residual[source]/.05, -1, 1)
        colors = np.column_stack((255*np.maximum(v,0), 255*(1-np.abs(v)), 255*np.maximum(-v,0))).astype('u1')
        colors[c[source] == 0] //= 5
        pixels[frame.valid] = colors
        image = Image.fromarray(pixels[::-1, ::-1]).resize((768,576), Image.Resampling.NEAREST)
        draw = ImageDraw.Draw(image);draw.rectangle((0,0,768,35),fill='black')
        draw.text((8,8), name.upper()+' signed distance: blue -5cm / green 0 / red +5cm; selected patches bright', fill='white')
        panels.append(image)
    combined = Image.new('RGB',(1536,576));combined.paste(panels[0],(0,0));combined.paste(panels[1],(768,0))
    combined.save(out/'residual_comparison.png')
    return records


def full_shadow(samples, headers, report, audit):
    rank = audit['first_fit_feasible_rank']
    if rank is None:
        return None
    chosen = audit['hypotheses'][rank]
    original = quality.ESTIMATORS
    original_compare = site.compare
    try:
        # site.ESTIMATORS retains the original seed estimator. Only the final
        # fit-domain candidate changes; all holdout and per-frame gates still run.
        quality.ESTIMATORS = dict(original, ransac=lambda p:
            (np.asarray(chosen['normal']), chosen['offset']))
        # Historical probe: evaluate the explicitly chosen raw hypothesis,
        # without replacing it with the new production candidate selector.
        site.compare = lambda p, r, h, a, **kwargs: quality.compare(p, r, h, a)
        return site.fit_site(samples, headers, report['binding'], dict(
            upstream='diagnostic_shadow_only', fit_only_candidate_rank=rank,
            original_source=report['source']))
    finally:
        quality.ESTIMATORS = original
        site.compare = original_compare


def analyze(capture, historical, out):
    out = safe_output(out)
    out.mkdir(parents=True, exist_ok=False)
    archive_path = capture/'clouds.npz'
    archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    declaration = json.loads((capture/'capture.json').read_text(encoding='utf8'))
    if declaration['archive_sha256'] != archive_hash:raise ValueError('capture archive checksum mismatch')
    with np.load(archive_path, allow_pickle=False) as archive:
        meta = json.loads(archive['metadata'].tobytes())
        rows = [archive['rows_%03d'%i].copy() for i in range(28)]
        for i,h in enumerate(meta['headers']):
            wire = archive['wire_%03d'%i].tobytes()
            if hashlib.sha256(wire).hexdigest() != h['wire_sha256']:
                raise ValueError('capture wire checksum mismatch')
            msg = NS(**{k:h[k] for k in ('width','height','point_step','row_step','is_bigendian')},
                     fields=[NS(**f) for f in h['fields']],data=wire)
            decoded = pointcloud_rows(msg)
            if any(not np.array_equal(decoded[n],rows[i][n],equal_nan=True) for n in decoded.dtype.names):
                raise ValueError('wire and archived decoded rows disagree')
    samples = [xyz(r) for r in rows]
    tables = ROOT/'src/inno_lidar_ros/config/ifw192s'
    grid = ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv',tables/'ifw192s_elevation_192x256.csv')
    report = site.fit_site(samples, meta['headers'], dict(siteId='DIAGNOSTIC_ONLY',frameId=meta['headers'][0]['frame_id'],
        gridSha256=grid.sha256),dict(upstream='captured_raw_ros',archive_sha256=archive_hash))
    write_json(out/'fresh_fit.json',report)
    old = json.loads(historical.read_text(encoding='utf8'))
    fixed = audit_domain(samples, old)
    write_json(out/'historical_domain_audit.json',fixed)
    fresh = audit_domain(samples, report) if 'quality' in report else None
    if fresh is not None:write_json(out/'fresh_domain_audit.json',fresh)
    shadow = full_shadow(samples, meta['headers'], report, fresh) if fresh is not None else None
    if shadow is not None:write_json(out/'full_shadow_site.json',shadow)
    display_report = report if 'quality' in report else old
    image_records = images(rows,meta['headers'],display_report,out,grid)
    historical_images = out/'historical_images'
    historical_images.mkdir()
    images(rows,meta['headers'],old,historical_images,grid)
    stats = []
    for i,(p,r) in enumerate(zip(samples,rows)):
        finite = np.isfinite(p).all(1)
        stats.append(dict(frame=i,seq=meta['headers'][i]['seq'],count=len(p),nonfinite=int((~finite).sum()),
            zero=int((p == 0).all(1).sum()),out_of_range=int((np.abs(p)>100).any(1).sum()),
            ring_min=int(r['ring'].min()),ring_max=int(r['ring'].max()),clean_count=len(clean_points(p))))
    write_json(out/'summary.json',dict(archive_sha256=archive_hash,grid_sha256=grid.sha256,
        historical_report_sha256=hashlib.sha256(historical.read_bytes()).hexdigest(),
        wire_to_rows_identical_frames=28,
        fresh_status=report['status'],fresh_reason=report['reason'],
        historical_domain_consensus=fixed['baseline']['consensus'],
        historical_fit_only_alternative_consensus=(fixed['fit_only_alternative'] or {}).get('consensus'),
        fresh_fit_only_alternative_consensus=((fresh or {}).get('fit_only_alternative') or {}).get('consensus'),
        full_shadow_site_status=(shadow or {}).get('status'),
        raw_stats=stats,images=image_records,scope='No live installation; RGB/extrinsics/physical GT UNKNOWN'))
    if archive_hash != hashlib.sha256(archive_path.read_bytes()).hexdigest():raise RuntimeError('input changed')
    print(json.dumps(dict(fresh=report['status'],reason=report['reason'],
        historical=fixed['baseline']['consensus'],candidate=(fixed['fit_only_alternative'] or {}).get('consensus'))))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--historical',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    analyze(a.capture,a.historical,a.out)
