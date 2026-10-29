"""Same-frame range-region annotations. Visible representative returns only.

PC sidecar; never writes sessions, analysis, or the fall alarm pipeline.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
sys.path.insert(0, str(ROOT/'src/human_fall_detection/scripts'))
from core.range_image import ScanGrid
from core.range_contract import binding_tuple
from replay_range_frontend import CALIBRATION
from body_branches import propose, METHOD

PARTS = ['head', 'torso'] + [s+'_'+b for s in ('upper_arm', 'forearm', 'thigh', 'shin', 'foot') for b in ('1', '2')]
STATES = ('visible', 'occluded', 'invisible', 'uncertain')
ORIENTATION = 'native_grid_rotated_180_for_view'


def map_region(indices, xyz, rect, allowed):
    """Half-open display pixel rectangle -> unique visible source rows -> pixels."""
    h, w = indices.shape
    if (not isinstance(rect, list) or len(rect) != 4 or any(type(v) is not int for v in rect)
            or not 0 <= rect[0] < rect[2] <= w or not 0 <= rect[1] < rect[3] <= h):
        raise ValueError('invalid half-open display rectangle')
    # A row occurring at multiple pixels violates ownership; reject, never guess.
    valid = indices[indices >= 0]
    if len(np.unique(valid)) != len(valid) or (len(valid) and valid.max() >= len(xyz)):
        raise ValueError('source index conflict or out of bounds')
    x0, y0, x1, y1 = rect
    yy, xx = np.mgrid[y0:y1, x0:x1]
    rows = indices[y0:y1, x0:x1].ravel()
    ok = rows >= 0
    in_scope = ok & np.isin(rows, list(allowed))
    chosen = rows[in_scope]
    points = xyz[chosen]
    if not np.isfinite(points).all():
        raise ValueError('nonfinite source points')
    return dict(sourceRows=chosen.tolist(), imagePixels=np.column_stack((xx.ravel()[in_scope], yy.ravel()[in_scope])).tolist(),
                xyz=points.tolist(), invalidPixels=int((~ok).sum()), excludedOutsideScope=int((ok & ~in_scope).sum()),
                representativePoint=np.median(points, axis=0).tolist() if len(points) else None,
                pointMeaning='visible_surface_region_representative_not_anatomical_joint')


def map_pixels(indices, xyz, pixels, allowed):
    """Explicit measured pixel set, including irregular/disconnected visible support."""
    if (not isinstance(pixels, list) or len(pixels) > indices.size
            or any(type(p) is not int or not 0 <= p < indices.size for p in pixels)
            or len(set(pixels)) != len(pixels)):
        raise ValueError('invalid or duplicate selected pixels')
    valid = indices[indices >= 0]
    if len(np.unique(valid)) != len(valid) or (len(valid) and valid.max() >= len(xyz)):
        raise ValueError('source index conflict or out of bounds')
    selected = np.asarray(pixels, dtype=np.int64)
    rows = indices.ravel()[selected]
    ok = rows >= 0
    keep = ok & np.isin(rows, list(allowed))
    chosen, selected = rows[keep], selected[keep]
    points = xyz[chosen]
    if not np.isfinite(points).all():
        raise ValueError('nonfinite source points')
    return dict(sourceRows=chosen.tolist(), imagePixels=np.column_stack((selected % indices.shape[1], selected // indices.shape[1])).tolist(),
        xyz=points.tolist(), invalidPixels=int((~ok).sum()), excludedOutsideScope=int((ok & ~keep).sum()),
        representativePoint=np.median(points, axis=0).tolist() if len(points) else None,
        pointMeaning='visible_surface_region_representative_not_anatomical_joint')


def geometry(parts):
    features = {}
    usable = {}
    for part in parts:
        points = np.asarray(part['mapping']['xyz'], dtype=float).reshape(-1, 3)
        if not len(points):
            continue
        center = np.median(points, axis=0)
        axis = None
        eigenvalues = None
        reason = 'insufficient_support'
        if len(points) >= 6:
            values, vectors = np.linalg.eigh(np.cov((points-center).T))
            eigenvalues = values.tolist()
            if values[-1] > 1e-9 and values[-1] >= 1.6 * max(values[-2], 1e-9):
                vector = vectors[:, -1]
                if vector[np.argmax(np.abs(vector))] < 0:
                    vector = -vector
                axis = vector.tolist()
                reason = 'measured_unoriented_principal_axis'
            else:
                reason = 'ambiguous_principal_axis'
        usable[part['part']] = (center, axis)
        features[part['part']] = dict(representativePoint=center.tolist(), principalAxis=axis,
            eigenvalues=eigenvalues, reason=reason, source=part['origin'])
    relation = None
    if 'head' in usable and 'torso' in usable:
        delta = usable['head'][0]-usable['torso'][0]
        relation = dict(deltaSensorM=delta.tolist(), distanceM=float(np.linalg.norm(delta)))
    angles = {}
    for a, b in [('torso', 'upper_arm_1'), ('torso', 'upper_arm_2'), ('upper_arm_1', 'forearm_1'),
                 ('upper_arm_2', 'forearm_2'), ('torso', 'thigh_1'), ('torso', 'thigh_2'),
                 ('thigh_1', 'shin_1'), ('thigh_2', 'shin_2'), ('shin_1', 'foot_1'), ('shin_2', 'foot_2')]:
        if a in usable and b in usable and usable[a][1] is not None and usable[b][1] is not None:
            angles[a+':'+b] = float(np.degrees(np.arccos(np.clip(abs(np.dot(usable[a][1], usable[b][1])), 0, 1))))
    return dict(parts=features, headTorso=relation, segmentAxisAnglesDeg=angles,
        angleMeaning='unoriented_surface_axes_0_to_90_not_joint_flexion',
        standing='UNKNOWN', lying='UNKNOWN', groundHeightM=None, fallEvent='UNKNOWN',
        reason='gravity_and_ground_not_established; static_shape_is_not_a_fall_event',
        bodySemanticAccuracy='UNKNOWN', postureAccuracy='UNKNOWN', alarmChanged=False)


class BodyStore:
    def __init__(self, analysis_store, store_root, grid=None):
        self.analysis = analysis_store
        self.root = Path(store_root)/'body_parts_v1'
        self.grid = grid or ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv', CALIBRATION/'ifw192s_elevation_192x256.csv')
        self.lock = threading.RLock()
        self.cache = {}

    def context(self, sid, index, person):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', person):
            raise ValueError('invalid person identifier')
        packet = self.analysis.frame(sid, index)
        manifest, row = packet['manifest'], packet['frame']
        if self.grid.sha256 != manifest['sourceBinding']['grid_sha256']:
            raise ValueError('calibration mismatch')
        # Also validate the display orientation and exact preview bytes.
        self.analysis.asset(sid, index, 'preview')
        key = (sid, index, row['rawSha256'])
        with self.lock:
            if key not in self.cache:
                meta = json.loads((self.analysis.data_root/sid/'meta.json').read_text('utf-8'))
                fr = meta['frames'][index]
                with (self.analysis.data_root/sid/'points.bin').open('rb') as stream:
                    stream.seek(fr['offset_points']*28)
                    raw = stream.read(fr['count_points']*28)
                if hashlib.sha256(raw).hexdigest() != row['rawSha256']:
                    raise ValueError('frame changed during decode')
                decoded = self.grid.decode(raw, binding_tuple(manifest['sourceBinding']))
                self.cache = {key: decoded}  # bounded: only most recently requested frame
            decoded = self.cache[key]
        indices = decoded.source_rows[::-1, ::-1].copy()
        binding = dict(sessionId=sid, frameIndex=index, personId=person, rawSha256=row['rawSha256'],
            metaSha256=manifest['metaSha256'], pointsSha256=manifest['pointsSha256'],
            calibration=manifest['sourceBinding'], orientation=ORIENTATION,
            coordinateFrame=manifest['coordinateFrame'], units='m')
        return dict(binding=binding, width=indices.shape[1], height=indices.shape[0],
                    sourceIndices=indices.ravel().tolist(), targetRows=row['sourceRows'],
                    trackId=row['trackId'], generation=row['generation'],
                    bodyCandidates=row.get('bodyCandidates'),
                    duplicateReturnRows=decoded.rejected['duplicate_rows'].tolist()), decoded.xyz, indices

    def compute(self, context, xyz, indices, doc):
        if not isinstance(doc, dict) or doc.get('binding') != context['binding'] or doc.get('format') != 'body_parts_v1':
            raise ValueError('body annotation frame/source/person/orientation/calibration mismatch')
        scope = doc.get('scope')
        if not isinstance(scope, dict):
            raise ValueError('scope required')
        if scope.get('kind') == 'automatic_target':
            if scope != dict(kind='automatic_target', trackId=context['trackId'], generation=context['generation']):
                raise ValueError('target binding mismatch')
            allowed = context['targetRows']
            scope_reason = 'automatic_target_person_association_and_background_purity_unverified'
        elif scope.get('kind') == 'person_box':
            b = scope.get('box', {})
            keys = ('x', 'y', 'w', 'h', 'zMin', 'zMax')
            if (not scope.get('boxId') or set(b) != set(keys) or any(type(b[k]) not in (int, float) or not np.isfinite(b[k]) for k in keys)
                    or b['w'] <= 0 or b['h'] <= 0 or b['zMax'] < b['zMin']):
                raise ValueError('invalid person box scope')
            p = xyz
            allowed = np.flatnonzero((abs(p[:, 0]-b['x']) <= b['w']/2) & (abs(p[:, 1]-b['y']) <= b['h']/2)
                & (p[:, 2] >= b['zMin']) & (p[:, 2] <= b['zMax'])).tolist()
            scope_reason = 'person_box_is_a_spatial_filter_not_human_segmentation'
        else:
            raise ValueError('unknown scope')
        parts, names, used = [], set(), set()
        if not isinstance(doc.get('parts'), list) or len(doc['parts']) > len(PARTS):
            raise ValueError('invalid parts')
        for part in doc['parts']:
            name, state, origin = part.get('part'), part.get('state'), part.get('origin')
            if name not in PARTS or name in names or state not in STATES or not isinstance(origin, dict):
                raise ValueError('invalid or duplicate part')
            names.add(name)
            kind = origin.get('kind')
            if (kind not in ('human', 'automatic', 'propagated') or not isinstance(origin.get('method'), str)
                    or not isinstance(origin.get('uncertainty'), list)
                    or (kind == 'propagated' and not origin.get('fromBinding'))):
                raise ValueError('explicit provenance and uncertainty required')
            rect = part.get('rect')
            pixels = part.get('pixels')
            if rect is not None and pixels is not None:
                raise ValueError('choose rectangle or explicit pixel set, not both')
            if state in ('invisible', 'uncertain') and (rect is not None or pixels is not None):
                raise ValueError('unobserved/uncertain part must not invent support')
            mapping = map_pixels(indices, xyz, pixels, allowed) if pixels is not None else map_region(indices, xyz, rect, allowed) if rect is not None else dict(sourceRows=[], imagePixels=[], xyz=[],
                invalidPixels=0, excludedOutsideScope=0, representativePoint=None,
                pointMeaning='visible_surface_region_representative_not_anatomical_joint')
            overlap = used.intersection(mapping['sourceRows'])
            if overlap:
                raise ValueError('body part source overlap; edit regions to be disjoint')
            used.update(mapping['sourceRows'])
            reasons = [scope_reason, 'only_representative_visible_return_no_hidden_points', 'body_semantic_accuracy_UNKNOWN']
            if not mapping['sourceRows']:
                reasons.append('empty_or_unobserved_region')
            parts.append(dict(part=name, state=state, rect=rect, origin=origin, mapping=mapping, reasons=reasons))
            if pixels is not None:
                parts[-1]['pixels'] = pixels
        result = dict(format='body_parts_v1', binding=context['binding'], scope=scope, parts=parts)
        result['geometry'] = geometry(parts)
        return result

    def suggest(self, context, xyz, indices):
        cached = context.get('bodyCandidates')
        if cached is not None:
            if (cached.get('method') != METHOD or cached.get('semantic') != 'UNKNOWN'
                    or cached.get('orientation') != ORIENTATION
                    or cached.get('sourceSha256') != hashlib.sha256((ROOT/'pc_apps/annotator_v2/body_branches.py').read_bytes()).hexdigest()):
                raise ValueError('precomputed body algorithm changed; regenerate analysis')
            parts = cached['parts']
            for part in parts:
                pixels = part.get('pixels') or []
                mapped = map_pixels(indices, xyz, pixels, context['targetRows'])
                if mapped['sourceRows'] != part.get('sourceRows'):
                    raise ValueError('precomputed body pixel/source mismatch')
        else:
            parts = propose(indices, xyz, context['targetRows'])
        doc = dict(format='body_parts_v1', binding=context['binding'],
            scope=dict(kind='automatic_target', trackId=context['trackId'], generation=context['generation']),
            parts=parts)
        return self.compute(context, xyz, indices, doc)

    def suggest_legacy(self, context, xyz, indices):
        """Frozen v1 band baseline for offline comparison, not the UI default."""
        mask = np.isin(indices, context['targetRows']) & (indices >= 0)
        yy, xx = np.nonzero(mask)
        parts = []
        if len(xx) >= 30:
            x0, x1 = int(xx.min()), int(xx.max())+1
            y0, y1 = int(yy.min()), int(yy.max())+1
            split = y0+max(1, int((y1-y0)*.20))
            end = max(split+1, y0+int((y1-y0)*.62))
            if end <= y1:
                for name, rect in [('head', [x0, y0, x1, split]), ('torso', [x0, split, x1, end])]:
                    parts.append(dict(part=name, state='visible', rect=rect,
                        origin=dict(kind='automatic', method='image_extent_bands_v1', uncertainty=[
                            'hypothesis_only_not_anatomical_recognition', 'image_up_is_not_gravity',
                            'head_foot_identity_unknown', 'occlusion_background_and_nonhuman_target_possible'])))
        doc = dict(format='body_parts_v1', binding=context['binding'],
            scope=dict(kind='automatic_target', trackId=context['trackId'], generation=context['generation']), parts=parts)
        return self.compute(context, xyz, indices, doc)

    def path(self, context):
        b = context['binding']
        return self.root/b['sessionId']/str(b['frameIndex'])/(b['personId']+'.json')

    def load(self, context, xyz, indices):
        with self.lock:
            path = self.path(context)
            if not path.exists():
                return dict(version=0, doc=self.suggest(context, xyz, indices)
                            if context.get('bodyCandidates') is not None else None)
            env = json.loads(path.read_text('utf-8'))
            checked = self.compute(context, xyz, indices, env['doc'])
            if checked != env['doc']:
                raise ValueError('stored body mapping changed or tampered')
            return dict(version=env['version'], doc=checked)

    def save(self, context, xyz, indices, body):
        doc = self.compute(context, xyz, indices, body.get('doc'))
        with self.lock:
            current = self.load(context, xyz, indices)['version']
            if type(body.get('baseVersion')) is not int or body['baseVersion'] != current:
                raise ValueError('body version conflict; reload before saving')
            path = self.path(context)
            path.parent.mkdir(parents=True, exist_ok=True)
            env = dict(version=current+1, doc=doc)
            fd, temp = tempfile.mkstemp(prefix='.body-', dir=str(path.parent))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(env, stream, ensure_ascii=False, allow_nan=False)
                os.replace(temp, path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
            return env
