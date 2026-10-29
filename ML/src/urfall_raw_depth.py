"""Raw UR Fall PNG16 -> causal target crop -> geometric candidate diagnostic.

PC-only Pillow decoder; fitting and voxel connectivity reuse production NumPy
helpers without changing them. Nominal pinhole coordinates are explicitly
unverified. No action/pose labels or author crops enter this input chain.
"""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import zipfile

import numpy as np
from PIL import Image

from fall_candidate_runtime import file_sha256
from fall_geometry import FallGeometryRuntime
from urfall_geometry_proxy import read_sync

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
from core.ground import fit_ground_plane
from core.lidar_candidates import spatial_components

SETTINGS = dict(stride=4, warmup_s=.3, depth_min_m=.6, depth_max_m=5.,
                ground_start_fraction=.6,
                foreground_delta_m=.10, floor_clearance_m=.08, cell_m=.08,
                minimum_component_points=40, acquire_span_m=.8,
                maximum_track_gap_s=.5, association_m=.8, ambiguity_margin_m=.15)
GROUND_SETTINGS=dict(max_points=10000,max_fit_points=5000,range_min_m=.6,range_max_m=6.,
                     min_inlier_fraction=.2,inlier_threshold_m=.03)


def load_pinhole(path):
    doc = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if (doc.get('schema') != 'urfall_pinhole_v1' or doc.get('camera') != 'cam0' or
            doc.get('status') != 'nominal_diagnostic' or doc.get('physical_verified') is not False):
        raise ValueError('Expected explicit unverified cam0 diagnostic calibration')
    for k in ('width', 'height'):
        if not isinstance(doc.get(k), int) or isinstance(doc[k], bool) or doc[k] <= 0:
            raise ValueError('Invalid image dimensions')
    for k in ('fx', 'fy', 'cx', 'cy'):
        if isinstance(doc.get(k), bool) or not isinstance(doc.get(k), (int, float)) or not math.isfinite(doc[k]):
            raise ValueError('Invalid pinhole parameter')
    if doc['fx'] <= 0 or doc['fy'] <= 0 or not 0 <= doc['cx'] < doc['width'] or not 0 <= doc['cy'] < doc['height']:
        raise ValueError('Invalid focal length or principal point')
    return doc


def decode_png(raw, scale_m, camera, stride=4):
    """Sampled grid and source pixels; zero depth is invalid, never an observation."""
    if (raw[:8] != b'\x89PNG\r\n\x1a\n' or len(raw) < 26 or
            raw[24] != 16 or raw[25] != 0):
        raise ValueError('Expected PNG16 grayscale depth')
    if not math.isfinite(scale_m) or scale_m <= 0 or not isinstance(stride, int) or isinstance(stride, bool) or stride < 1:
        raise ValueError('Invalid depth scale or stride')
    with Image.open(io.BytesIO(raw)) as check:
        check.verify()
    with Image.open(io.BytesIO(raw)) as image:
        depth = np.asarray(image)
    if depth.shape != (camera['height'], camera['width']) or depth.dtype != np.uint16:
        raise ValueError('Depth image shape/dtype differs from calibration')
    v, u = np.mgrid[0:camera['height']:stride, 0:camera['width']:stride]
    samples = depth[::stride, ::stride].astype(np.float64)*scale_m/65535.
    pixels = (v*camera['width']+u).reshape(-1).astype(np.int64)
    d = samples.reshape(-1)
    points = np.column_stack(((u.reshape(-1)-camera['cx'])*d/camera['fx'], d,
                              -(v.reshape(-1)-camera['cy'])*d/camera['fy']))
    return points, pixels, samples


def median_reference(depths):
    """Per-pixel lower median of valid past depths, preserving all-hole pixels."""
    stack = np.asarray(depths, dtype=np.float64)
    if stack.ndim != 3 or not len(stack):
        raise ValueError('Expected nonempty past depth stack')
    counts = (stack > 0).sum(axis=0)
    ordered = np.sort(np.where(stack > 0, stack, np.inf), axis=0)
    index = np.maximum(0, (counts-1)//2)
    result = np.take_along_axis(ordered, index[None], axis=0)[0]
    result[counts == 0] = 0.
    return result


class DepthTarget:
    """Measured component association, explicitly no person semantics."""
    def __init__(self, settings=None):
        self.settings = dict(SETTINGS, **(settings or {}))
        self.centre = self.last_seen = self.last_stamp = None
        self.generation = 0

    def select(self, points, pixels, heights, stamp):
        s = self.settings
        if not math.isfinite(stamp):
            raise ValueError('Invalid component timestamp')
        if self.last_stamp is not None and stamp <= self.last_stamp:
            self.centre = self.last_seen = None
        self.last_stamp = stamp
        if self.last_seen is not None and stamp-self.last_seen > s['maximum_track_gap_s']:
            self.centre = self.last_seen = None
        groups = [np.asarray(g, dtype=np.int64) for g in spatial_components(points, s['cell_m'])
                  if len(g) >= s['minimum_component_points']]
        candidates = [dict(rows=g, centre=np.median(points[g], axis=0),
                           span=float(np.ptp(heights[g]))) for g in groups]
        if self.centre is None:
            eligible = [c for c in candidates if c['span'] >= s['acquire_span_m']]
            eligible.sort(key=lambda c: (-len(c['rows']), int(pixels[c['rows']].min())))
            # Two similarly sized eligible supports are ambiguous, not one person.
            if len(eligible) > 1 and len(eligible[1]['rows']) >= .8*len(eligible[0]['rows']):
                return np.empty(0, dtype=np.int64), 'ambiguous_acquisition', len(candidates)
        else:
            eligible = [dict(c, distance=float(np.linalg.norm(c['centre']-self.centre))) for c in candidates]
            eligible = sorted((c for c in eligible if c['distance'] <= s['association_m']),
                              key=lambda c: c['distance'])
            if len(eligible) > 1 and eligible[1]['distance']-eligible[0]['distance'] < s['ambiguity_margin_m']:
                return np.empty(0, dtype=np.int64), 'ambiguous_association', len(candidates)
        if not eligible:
            return np.empty(0, dtype=np.int64), 'no_supported_component', len(candidates)
        if self.centre is None:
            self.generation += 1
        chosen = eligible[0]
        self.centre, self.last_seen = chosen['centre'], stamp
        return chosen['rows'], 'measured_component', len(candidates)


def run(archive_path, sync_path, calibration_path, out, limit=0, focal_scale=1., ground_start_fraction=.6,
        scene_reference_path=None):
    if (not math.isfinite(focal_scale) or focal_scale <= 0 or limit < 0 or
            not math.isfinite(ground_start_fraction) or not .5 <= ground_start_fraction < 1.):
        raise ValueError('Invalid diagnostic scale/limit')
    match = re.fullmatch(r'(fall|adl)-(\d{2})-cam0-d.zip', archive_path.name)
    if not match:
        raise ValueError('Expected official cam0 depth archive name')
    sequence = '%s-%s' % match.groups()
    if sync_path.name != sequence+'-data.csv':
        raise ValueError('Synchronization belongs to a different sequence')
    camera = load_pinhole(calibration_path)
    camera['fx'] *= focal_scale; camera['fy'] *= focal_scale
    times, settings = read_sync(sync_path), dict(SETTINGS)
    settings['ground_start_fraction'] = ground_start_fraction
    scale_m = 6. if match.group(1) == 'fall' else 7.
    input_hashes=dict(archive=file_sha256(archive_path),sync=file_sha256(sync_path),
                      camera=file_sha256(calibration_path))
    reference,plane,scene_reference=None,None,None
    if scene_reference_path is not None:
        from urfall_scene_reference import load_reference
        depth,plane,scene_reference=load_reference(scene_reference_path,camera,input_hashes['camera'],
            settings['stride'],sequence,input_hashes['archive'],input_hashes['sync'],min(times.values()))
        reference=depth.reshape(-1)
    out.mkdir(parents=True, exist_ok=False)
    protocol = dict(sequence=sequence, camera=camera, settings=settings, depth_scale_m=scale_m,
                    coordinate_status='nominal_diagnostic_unverified', focal_scale=focal_scale,
                    background='frozen per-pixel median of consumed warmup prefix; may contain person',
                    ground='fit only from consumed prefix lower image; candidate plane, not physical verification',
                    label_input=False, author_feature_input=False, semantic_target='UNKNOWN',
                    input_sha256=input_hashes)
    if scene_reference is not None:
        protocol.update(scene_reference=scene_reference,
                        background='explicit pre-event reference; empty-prefix metadata declared only',
                        ground='explicit frozen pre-event candidate plane; physical verification UNKNOWN')
    (out/'PROTOCOL.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    target = DepthTarget(settings)
    runtime = FallGeometryRuntime()
    prefix, prefix_points = [], []
    records, blocks, offsets, stamps, events = [], [], [0], [], []
    calibration = hashlib.sha256(json.dumps(camera, sort_keys=True).encode()).hexdigest()
    if scene_reference is not None:
        runtime=FallGeometryRuntime(plane['normal'],plane['offset_m'])
        calibration=hashlib.sha256(json.dumps(dict(camera=camera,plane=plane,
            reference_sha256=scene_reference['manifest_sha256']),sort_keys=True).encode()).hexdigest()
    with zipfile.ZipFile(archive_path) as archive, (out/'FRAMES.jsonl').open('x', encoding='utf-8') as ledger:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate depth ZIP member')
        members = []
        for name in names:
            if name.endswith('.png'):
                m = re.fullmatch(re.escape(sequence)+r'-cam0-d-(\d+)\.png', name.rsplit('/', 1)[-1])
                if not m:
                    raise ValueError('Depth member belongs to different sequence')
                members.append((int(m.group(1)), name))
        members.sort()
        if not members or len(set(f for f, _ in members)) != len(members):
            raise ValueError('Empty/ambiguous depth frames')
        for index, (frame, name) in enumerate(members[:limit or None]):
            raw = archive.read(name)
            points, pixels, depth = decode_png(raw, scale_m, camera, settings['stride'])
            stamp = times.get(frame)
            raw_valid = (points[:, 1] >= settings['depth_min_m']) & (points[:, 1] <= settings['depth_max_m'])
            selected = np.empty(0, dtype=np.int64)
            foreground = np.zeros(len(points), dtype=bool)
            status, count = 'warmup', 0
            if stamp is None:
                status = 'missing_sync_timestamp'
            elif reference is None and stamp <= settings['warmup_s']:
                prefix.append(depth)
                lower = pixels // camera['width'] >= int(camera['height']*settings['ground_start_fraction'])
                prefix_points.append(points[raw_valid & lower])
            else:
                if reference is None:
                    if not prefix:
                        raise ValueError('No consumed warmup prefix; do not fit from future frames')
                    reference = median_reference(prefix).reshape(-1)
                    floor = np.concatenate(prefix_points)
                    plane = fit_ground_plane(floor, frame='nominal_cam0', settings=GROUND_SETTINGS)
                    if plane['status'] == 'valid':
                        runtime = FallGeometryRuntime(plane['normal'], plane['offset_m'])
                        calibration = hashlib.sha256(json.dumps(dict(camera=camera, plane=plane), sort_keys=True).encode()).hexdigest()
                if plane['status'] != 'valid':
                    status = 'ground_unavailable'
                else:
                    heights = points @ np.asarray(plane['normal']) + plane['offset_m']
                    foreground = (raw_valid & (reference > 0) &
                                  (reference - depth.reshape(-1) >= settings['foreground_delta_m']) &
                                  (heights >= settings['floor_clearance_m']))
                    fg_rows = np.flatnonzero(foreground)
                    local, status, count = target.select(points[fg_rows], pixels[fg_rows], heights[fg_rows], stamp)
                    selected = fg_rows[local]
            binding=(sequence,target.generation,calibration)
            output = runtime.push(points[selected], stamp, *binding,
                                  observed=status == 'measured_component')
            if output['new_event']:
                events.append(output['new_event'])
            record = dict(frame=frame, timestamp_s=stamp, member=name,
                          member_sha256=hashlib.sha256(raw).hexdigest(), sampled_valid_pixels=int(raw_valid.sum()),
                          foreground_points=int(foreground.sum()), target_points=len(selected),
                          target_source_pixels=pixels[selected].tolist(), target_generation=target.generation,
                          component_count=count, extraction_status=status, geometry=output,binding=binding)
            ledger.write(json.dumps(record, allow_nan=False)+'\n')
            records.append(record)
            blocks.append(points[selected]); offsets.append(offsets[-1]+len(selected)); stamps.append(stamp)
    np.savez_compressed(out/'target_points.npz', points=np.concatenate(blocks),
                        frame_offsets=np.asarray(offsets, dtype=np.int64),
                        timestamps_s=np.asarray([t if t is not None else np.nan for t in stamps]))
    summary = dict(sequence=sequence, frames=len(records), target_frames=sum(r['target_points'] > 0 for r in records),
                   extraction_states={s:sum(r['extraction_status']==s for r in records)
                                      for s in sorted(set(r['extraction_status'] for r in records))},
                   geometry_states={s:sum(r['geometry']['state']==s for r in records)
                                    for s in sorted(set(r['geometry']['state'] for r in records))},
                   events=events, ground=plane, protocol=protocol,
                   source_sha256={p.name:file_sha256(p) for p in (Path(__file__),
                       Path(__file__).with_name('fall_geometry.py'),Path(__file__).with_name('urfall_scene_reference.py'),
                       ROOT/'src/human_fall_detection/core/ground.py',
                       ROOT/'src/human_fall_detection/core/lidar_candidates.py')},
                   frames_sha256=file_sha256(out/'FRAMES.jsonl'), target_cache_sha256=file_sha256(out/'target_points.npz'),
                   physical_validity='UNKNOWN', raw_person_precision_recall='UNKNOWN', IFW192S_effectiveness='UNKNOWN')
    (out/'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:summary[k] for k in ('sequence','frames','target_frames','extraction_states','geometry_states','events')}), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sync', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--focal-scale', type=float, default=1.)
    parser.add_argument('--ground-start-fraction', type=float, default=.6)
    parser.add_argument('--scene-reference',type=Path)
    args = parser.parse_args()
    run(args.archive, args.sync, args.calibration, args.output, args.limit, args.focal_scale,
        args.ground_start_fraction,args.scene_reference)
