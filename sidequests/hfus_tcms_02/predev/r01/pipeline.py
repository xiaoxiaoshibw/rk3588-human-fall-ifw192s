"""V0-V2 research prototype. All numbers are fixture hypotheses, not real pass lines."""
import copy
import numpy as np
from scipy.spatial import cKDTree
from pathlib import Path
from contracts import ROOT, HERE, digest, module, production_geometry, sha, validate_members

surface_module = module('predev_surface_reuse', ROOT / 'sidequests/human_fusion_lab_next/pointset/r01/scene_change.py')
CODE_VERSION = digest({str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__), HERE/'contracts.py',
    ROOT/'sidequests/human_fusion_lab_next/pointset/r01/scene_change.py']})
DEFAULTS = dict(surface_tau_m=.08, noise_m=.012, neighbor_m=.26,
                association_m=1.25, growth_m=.5, max_extent_m=2.4,
                max_transverse_m=.8, local_change_radius_m=1.2, min_points=3, ttl_s=.7, max_gap_s=2., seed=17)
ABLATIONS = {
    'full': None, 'no_ground': 'ground', 'no_frozen': 'frozen',
    'no_continuation': 'continuation', 'no_growth': 'growth', 'no_identity': 'identity'}


def ground_candidate(points, spec):
    out = dict(geometric_valid=False, identity_confirmed=False, physical_verified=False,
               valid_range=None, coordinate_version=None, temporal_validation='NOT_RUN',
               reason=None, candidate=None, transform=None)
    required = ['up_axis', 'sensor_height_interval_m', 'fit_indices', 'fit_frame_group',
                'validation_regions', 'coordinate_version', 'reference_axis']
    missing = [k for k in required if spec.get(k) is None]
    if missing:
        out['reason'] = 'MISSING_PRIORS_OR_INDEPENDENT_VALIDATION:' + ','.join(missing)
        return out
    ground, cal = production_geometry()
    try:
        candidate = ground.fit_ground_plane_constrained(
            points, settings=spec.get('settings'), frame=spec['coordinate_version'],
            **{k: spec[k] for k in required[:5]})
        out['candidate'] = candidate
        out['reason'] = candidate.get('reason')
        if candidate['status'] != 'valid':
            return out
        # Independent row IDs alone do not make independent spatial regions.
        # Check validation footprints in the explicitly supplied up-axis basis.
        up = np.asarray(spec['up_axis'],dtype=float)
        up = up / np.linalg.norm(up)
        tangent = np.asarray(spec['reference_axis'],dtype=float)
        tangent = tangent - (tangent @ up)*up
        if np.linalg.norm(tangent) <= 1e-9:
            raise ValueError('Degenerate ground reference axis')
        tangent /= np.linalg.norm(tangent)
        basis = np.column_stack([tangent,np.cross(up,tangent)])
        xy = np.asarray(points) @ basis
        fit_xy = xy[spec['fit_indices']]
        for region in spec['validation_regions']:
            ids = ground.region_indices(np.asarray(points),region)
            q = xy[ids]
            q = q[np.isfinite(q).all(axis=1)]
            if len(q) and np.any(np.all((fit_xy >= q.min(axis=0)) & (fit_xy <= q.max(axis=0)),axis=1)):
                out['reason'] = 'VALIDATION_SPATIAL_SUPPORT_OVERLAP'
                return out
        block = cal.build_ground_derived(candidate, spec['reference_axis'],
                                        source={'kind': 'SYNTHETIC' if spec.get('synthetic') else 'EXPLICIT_FIT'})
        cal.validate_ground_derived(block)
        out.update(geometric_valid=True, coordinate_version=spec['coordinate_version'],
                   valid_range=block['valid_region_ground_local'], transform=block,
                   legacy_status=cal.ground_derived_status(block))
        # Independent evidence envelope; never mutate candidate verification flags.
        out['identity_evidence'] = spec.get('identity_evidence')
        out['physical_evidence'] = spec.get('physical_evidence')
        # First version deliberately does not certify real identity/measurement.
    except ValueError as exc:
        out['reason'] = str(exc)
    return out


def temporal_ground_check(points, qualification):
    """Held-out-time diagnostic; caller must supply separately bound source rows."""
    if not qualification['geometric_valid']:
        return {'status': 'BLOCKED', 'reason': 'NO_GEOMETRY'}
    n, d = qualification['transform']['n'], qualification['transform']['d']
    p = np.asarray(points)
    r = np.abs(p @ np.asarray(n) + d)
    return {'status': 'CONTRACT_ONLY', 'n': len(p),
            'max_residual_m': float(r.max()) if len(p) else None,
            'identity_verified': False}


class FrozenMap:
    def __init__(self, frames, authorization, config=None):
        if authorization.get('confirmed_empty') is not True or authorization.get('layout_consistent') is not True:
            raise ValueError('Explicit unattended/layout authorization required')
        if not frames:
            raise ValueError('Missing A: real M0 initialization BLOCKED')
        self.config = dict(DEFAULTS if config is None else config)
        self.authorization = copy.deepcopy(authorization)
        coordinates = {f['coordinate_version'] for f in frames}
        if len(coordinates) != 1:
            raise ValueError('Cross-coordinate mapping forbidden')
        self.coordinate = frames[0]['coordinate_version']
        points, sources = [], []
        for f in frames:
            allowed = authorization.get('segments', [])
            if not any(a['sid'] == f['sid'] and a['source_sha256'] == f['source_sha256'] and
                       a['start_fi'] <= f['fi'] <= a['end_fi'] for a in allowed):
                raise ValueError('Map frame not explicitly authorized')
            for row in np.flatnonzero(np.isfinite(f['xyz']).all(axis=1) & (np.linalg.norm(f['xyz'], axis=1) > 0)):
                points.append(f['xyz'][row])
                sources.append(dict(mapping_sid=f['sid'], mapping_fi=f['fi'], mapping_source_row=int(row),
                                    source_sha256=f['source_sha256']))
        self.xyz = np.asarray(points, dtype=float).reshape(-1, 3).copy()
        self.sources = copy.deepcopy(sources)
        cfg = dict(normal_neighbors=8, planarity_ratio=.1, surface_radius_tau=8.)
        self.surfaces = surface_module.FrozenSurfaces(self.xyz.copy(), self.config['surface_tau_m'], cfg.copy())
        self.surfaces.xyz.setflags(write=False)
        for a in [self.surfaces.centers, self.surfaces.normals, self.surfaces.radius, self.surfaces.planar]:
            a.setflags(write=False)
        self.xyz.setflags(write=False)
        self.map_id = self.fingerprint()
        self.origin = authorization.get('origin_xyz')
        self.angular_verified = authorization.get('angular_support_verified') is True
        self.return_verified = authorization.get('return_mode_verified') is True

    def fingerprint(self):
        return digest(dict(xyz=self.xyz.tolist(), sources=self.sources, coordinate=self.coordinate,
                           authorization=self.authorization, config=self.config,
                           matching_surface=dict(xyz=self.surfaces.xyz.tolist(),
                             centers=self.surfaces.centers.tolist(), normals=self.surfaces.normals.tolist(),
                             radius=self.surfaces.radius.tolist(), planar=self.surfaces.planar.tolist(),
                             config=self.surfaces.cfg)))

    def ledger(self, frame, bg, usable):
        records = []
        for i, p in enumerate(self.xyz):
            hits = np.flatnonzero(bg & (np.linalg.norm(frame['xyz'] - p, axis=1) <= self.config['surface_tau_m']))
            near = []
            # Possible relation only. V1 never certifies strong occlusion/free.
            if usable and self.origin is not None and self.angular_verified and self.return_verified:
                q = p - self.origin
                v = frame['xyz'] - self.origin
                norms = np.linalg.norm(v, axis=1)
                valid = np.isfinite(v).all(axis=1) & (norms > 0)
                cos = np.full(len(v), -1.)
                if np.linalg.norm(q) > 0:
                    cos[valid] = (v[valid] @ q) / (norms[valid] * np.linalg.norm(q))
                near = np.flatnonzero(valid & (cos > np.cos(.012)) &
                                      (norms < np.linalg.norm(q) - self.config['surface_tau_m'])).tolist()
            records.append(dict(surface_id=i, map_id=self.map_id, xyz=p.tolist(),
                                mapping_source=self.sources[i],
                                support_angular_domain='VERIFIED_LOCAL_0.012_RAD' if self.angular_verified else 'UNKNOWN',
                                visibility='visible' if len(hits) else 'occlusion_possible' if near else 'unobserved',
                                current_near_evidence_rows=near,
                                current_match_evidence_rows=hits.tolist(),
                                current_member=False))
        return records


def components(points, rows, radius):
    rows = sorted(set(int(i) for i in rows))
    if not rows:
        return []
    tree = cKDTree(points[rows])
    unseen = set(range(len(rows)))
    groups = []
    while unseen:
        todo = [min(unseen)]
        unseen.remove(todo[0])
        ids = []
        while todo:
            i = todo.pop()
            ids.append(rows[i])
            for j in tree.query_ball_point(points[rows[i]], radius):
                if j in unseen:
                    unseen.remove(j)
                    todo.append(j)
        groups.append(sorted(ids))
    return groups


class Engine:
    def __init__(self, frozen=None, ground=None, variant='full', config=None):
        if variant not in ABLATIONS:
            raise ValueError('Unknown single-factor ablation')
        self.map, self.ground = frozen, ground
        self.config = dict(DEFAULTS if config is None else config)
        self.variant = variant
        self.enabled = {k: ABLATIONS[variant] != k for k in ['ground', 'frozen', 'continuation', 'growth', 'identity']}
        self.track = None
        self.last = None
        self.next_id = 1
        self.map_usable = frozen is not None

    def step(self, frame):
        cfg, p = self.config, np.asarray(frame['xyz'])
        if p.ndim != 2 or p.shape[1] != 3 or type(frame['time_ns']) is not int:
            raise ValueError('Invalid current XYZ/time contract')
        reset = None
        if self.last:
            if (frame['sid'], frame['source_sha256'], frame['coordinate_version']) != self.last['binding']:
                reset = 'SOURCE_OR_COORDINATE_CHANGED'
            elif frame['time_ns'] <= self.last['time_ns']:
                raise ValueError('Repeated/reversed device time')
            elif (frame['time_ns'] - self.last['time_ns']) / 1e9 > cfg['max_gap_s']:
                reset = 'LONG_DEVICE_TIME_GAP'
        if self.map and self.map.coordinate != frame['coordinate_version']:
            reset = 'MAP_COORDINATE_CHANGED'
        if reset:
            self.track = None
            if reset != 'LONG_DEVICE_TIME_GAP':
                self.map_usable = False
        self.last = dict(time_ns=frame['time_ns'], fi=frame['fi'],
                         binding=copy.deepcopy((frame['sid'], frame['source_sha256'], frame['coordinate_version'])))
        finite = np.isfinite(p).all(axis=1)
        valid = finite & (np.linalg.norm(np.where(finite[:, None], p, 0.), axis=1) > 0)
        bg = np.zeros(len(p), bool)
        distance = np.full(len(p), np.inf)
        static_boundary_available = bool(self.map and self.map_usable and self.enabled['frozen'])
        if static_boundary_available:
            _, bg, distance, _ = self.map.surfaces.split(p, valid)
        height = np.full(len(p), np.nan)
        in_range = np.ones(len(p), bool)
        ground_active = bool(self.enabled['ground'] and self.ground and self.ground['geometric_valid'] and
                             self.ground['coordinate_version'] == frame['coordinate_version'])
        if ground_active:
            _, cal = production_geometry()
            transformed = cal.apply_ground_derived(p[valid], self.ground['transform'])
            height[valid] = transformed[:, 2]
            region = self.ground['valid_range']
            q = transformed
            in_range[valid] = ((q[:, 0] >= region['x_min_m']) & (q[:, 0] <= region['x_max_m']) &
                               (q[:, 1] >= region['y_min_m']) & (q[:, 1] <= region['y_max_m']))
        # Background is a label, never removed from the current valid array.
        seeds = valid & ~bg & in_range
        # Plane-compatible returns can still enter the continuation route below.
        if ground_active:
            seeds &= (height > cfg['noise_m']) & (height <= cfg['max_extent_m'])
        continuation = np.zeros(len(p), bool)
        live = self.track is not None and (frame['time_ns'] - self.track['last_measured_ns']) / 1e9 <= cfg['ttl_s']
        if live and self.enabled['continuation'] and static_boundary_available:
            t = self.track
            bounded = np.all((p >= t['min'] - cfg['growth_m']) & (p <= t['max'] + cfg['growth_m']), axis=1)
            bounded &= np.linalg.norm(p - t['center'], axis=1) <= cfg['association_m']
            # Background residual + bounded previous measured shape is evidence,
            # not a global near-ground foot/lying cut. Exact unchanged floor stays bg.
            continuation = valid & bounded & in_range & (~bg | (distance > cfg['noise_m']))
        active = seeds | continuation
        groups = components(p, np.flatnonzero(active), cfg['neighbor_m'])
        candidates, rejections = [], []
        for rows in groups:
            initial = list(rows)
            if self.enabled['growth'] and static_boundary_available:
                # A single bounded expansion; no flood across static surfaces.
                q = p[rows]
                possible = np.flatnonzero(valid & in_range & ~active & (distance > cfg['noise_m']))
                for row in possible:
                    if (np.linalg.norm(q - p[row], axis=1).min() <= cfg['neighbor_m'] and
                            np.linalg.norm(p[row] - q.mean(axis=0)) <= cfg['growth_m']):
                        rows.append(int(row))
            rows = sorted(set(rows))
            q = p[rows]
            if len(rows) < cfg['min_points'] or np.ptp(q, axis=0).max() > cfg['max_extent_m']:
                rejections.append(dict(rows=rows, reason='UNSUPPORTED_OR_EXTENT', semantic='UNKNOWN'))
                continue
            if np.sort(np.ptp(q, axis=0))[-2] > cfg['max_transverse_m']:
                rejections.append(dict(rows=rows, reason='BROAD_SURFACE_EXCEEDS_TARGET_TRANSVERSE_SUPPORT', semantic='UNKNOWN'))
                continue
            background_other = valid & bg
            if ground_active:
                background_other &= np.abs(height) > cfg['surface_tau_m']
            nearby_static = np.flatnonzero(background_other)
            contact = any(np.linalg.norm(q - p[j], axis=1).min() <= cfg['neighbor_m'] for j in nearby_static)
            cid = len(candidates)
            version = digest(dict(sid=frame['sid'], fi=frame['fi'], source=frame['source_sha256'],
                                  coordinate=frame['coordinate_version'], code=CODE_VERSION,
                                  map_id=self.map.map_id if self.map else None,
                                  ground_id=(self.ground.get('transform') or {}).get('ground_derived_id') if self.ground else None,
                                  rows=rows, config=cfg, variant=self.variant))
            candidates.append(dict(id=cid, version=version, rows=rows, seed_rows=[i for i in initial if seeds[i]],
                                   continuation_rows=[i for i in initial if continuation[i]],
                                   grown_rows=[i for i in rows if i not in initial],
                                   center=q.mean(axis=0).tolist(), min=q.min(axis=0).tolist(), max=q.max(axis=0).tolist(),
                                   quality='mixed/ambiguous' if contact or any(bg[i] for i in rows) or not static_boundary_available else 'UNVERIFIED_CANDIDATE',
                                   semantic='UNKNOWN', static_contact_rows=nearby_static.tolist() if contact else []))
        chosen = None
        if live and self.enabled['identity']:
            eligible = [c for c in candidates if np.linalg.norm(np.array(c['center']) - self.track['center']) <= cfg['association_m']]
            if len(eligible) == 1:
                chosen = eligible[0]
                self._measure(frame, chosen)
            elif len(eligible) > 1:
                # Competing objects cannot silently steal the confirmed identity.
                for c in eligible:
                    c['quality'] = 'mixed/ambiguous'
        track = self._track_record(frame, chosen)
        labels = []
        target_rows = set(track['rows'])
        for i in range(len(p)):
            label = ('INVALID_XYZ' if not finite[i] else 'ZERO_RANGE' if not valid[i] else
                     'AMBIGUOUS' if bg[i] and (continuation[i] or i in target_rows) else
                     'bg_match' if bg[i] else 'NEW_SURFACE' if self.map_usable else 'UNKNOWN_NO_M0')
            labels.append(dict(sid=frame['sid'], fi=frame['fi'], source_row=i, global_row=frame['offset'] + i,
                               xyz=[float(v) if np.isfinite(v) else None for v in p[i]], label=label,
                               background_compatible=bool(bg[i]), discovery_seed=bool(seeds[i]),
                               continuation_support=bool(continuation[i]), target_member=i in target_rows,
                               filter_reason=None if valid[i] else 'NONFINITE' if not finite[i] else 'ZERO_RANGE'))
        validate_members(frame, labels)
        self.last['candidates'] = copy.deepcopy(candidates)
        map_ledger = self.map.ledger(frame, bg, self.map_usable) if self.map else []
        conflicts = []
        if static_boundary_available and ground_active:
            block = self.ground['transform']
            map_height = self.map.xyz @ np.asarray(block['n']) + block['d']
            for s in map_ledger:
                if s['visibility'] == 'visible' or abs(map_height[s['surface_id']]) <= cfg['surface_tau_m']:
                    continue
                near = np.flatnonzero(seeds & (np.linalg.norm(p - s['xyz'], axis=1) <= cfg['local_change_radius_m']))
                if len(near):
                    conflicts.append(dict(surface_id=s['surface_id'], current_evidence_rows=near.tolist(),
                        interpretation='POSSIBLE_LOCAL_CHANGE_NEAR_UNOBSERVED_SURFACE; VISIBILITY_UNKNOWN'))
        return dict(schema='hfus-predev-frame/1', kind=frame['kind'], contract_only=True,
                    sid=frame['sid'], fi=frame['fi'], time_ns=frame['time_ns'], offset=frame['offset'],
                    source_sha256=frame['source_sha256'], coordinate_version=frame['coordinate_version'],
                    variant=self.variant, steps=self.enabled, reset=reset, current_rows=labels,
                    candidates=candidates, rejected_unknown_objects=rejections, track=track, ground=self.ground,
                    ground_active=ground_active, no_physical_ground_conclusion=True,
                    map_id=self.map.map_id if self.map else None, map_usable=self.map_usable,
                    map_ledger=map_ledger, local_map_conflicts=conflicts,
                    local_map_conflict_rows=sorted({i for c in conflicts for i in c['current_evidence_rows']}),
                    new_change_rows=np.flatnonzero(seeds).tolist(),
                    static_boundary_available=static_boundary_available,
                    effective_growth=bool(self.enabled['growth'] and static_boundary_available),
                    boundary_reason='M0_FINITE_SUPPORT' if static_boundary_available else 'DISABLED_NO_STATIC_BOUNDARY',
                    global_map_status='UNKNOWN_NO_RELIABLE_ANCHOR_AUDIT',
                    capabilities=dict(strong_free=False, strong_occlusion=False,
                                      reason='V1_HAS_NO_VERIFIED_RAY_RETURN_MODEL'),
                    accounting=dict(raw=len(p), valid=int(valid.sum()), invalid=int((~valid).sum()),
                                    ledger_rows=len(labels), measured_target=len(track['rows'])))

    def _measure(self, frame, c):
        self.track.update(last_measured_ns=frame['time_ns'], center=np.array(c['center']),
                          min=np.array(c['min']), max=np.array(c['max']), rows=c['rows'], quality=c['quality'])

    def _track_record(self, frame, c):
        if self.track is None or not self.enabled['identity']:
            return dict(state='UNCONFIRMED', identity_source=None, track_id=None, rows=[],
                        measured_count=0, prediction_age_s=None, last_measured_ns=None, center=None)
        age = (frame['time_ns'] - self.track['last_measured_ns']) / 1e9
        state = 'MEASURED' if c else 'PREDICTED' if age <= self.config['ttl_s'] else 'LOST'
        return dict(state=state, identity_source=self.track['identity_source'], track_id=self.track['id'],
                    rows=c['rows'] if c else [], measured_count=len(c['rows']) if c else 0,
                    prediction_age_s=age, last_measured_ns=self.track['last_measured_ns'],
                    center=self.track['center'].tolist() if state != 'LOST' else None,
                    quality=c['quality'] if c else 'NO_CURRENT_MEMBERS',
                    identity_claim='MANUAL_CONFIRMED_OBJECT' if c and c['quality'] != 'mixed/ambiguous' else 'AMBIGUOUS_OR_UNOBSERVED')

    def confirm(self, frame, record, request):
        if not self.enabled['identity']:
            return
        if (self.last is None or self.last['fi'] != frame['fi'] or self.last['time_ns'] != frame['time_ns'] or
                self.last['binding'] != (frame['sid'], frame['source_sha256'], frame['coordinate_version']) or
                record.get('sid') != frame['sid'] or record.get('fi') != frame['fi'] or
                record.get('source_sha256') != frame['source_sha256'] or record.get('time_ns') != frame['time_ns']):
            raise ValueError('Expired record/current frame confirmation')
        if (request.get('sid') != frame['sid'] or request.get('fi') != frame['fi'] or
                request.get('time_ns') != frame['time_ns'] or
                request.get('source_sha256') != frame['source_sha256'] or
                request.get('coordinate_version') != frame['coordinate_version'] or
                not isinstance(request.get('reviewer'), str) or not request['reviewer'].strip() or
                request.get('provenance') not in ('HUMAN_CONFIRMATION', 'SYNTHETIC_SIMULATED_CONFIRMATION')):
            raise ValueError('Wrong source/expired/unbound confirmation')
        if request['provenance'] == 'SYNTHETIC_SIMULATED_CONFIRMATION' and frame['kind'] != 'SYNTHETIC':
            raise ValueError('Simulation cannot confirm real data')
        c = next((c for c in self.last['candidates'] if c['version'] == request.get('candidate_version')), None)
        if c is None or self.track is not None:
            raise ValueError('Stale candidate or already confirmed; reset required')
        self.track = dict(id='manual-%d' % self.next_id, identity_source=copy.deepcopy(request))
        self.next_id += 1
        self._measure(frame, c)
        record['track'] = self._track_record(frame, c)
        for row in record['current_rows']:
            row['target_member'] = row['source_row'] in c['rows']
            if row['target_member'] and row['background_compatible']:
                row['label'] = 'AMBIGUOUS'
        record['accounting']['measured_target'] = len(c['rows'])
        record['confirmation'] = copy.deepcopy(request)
