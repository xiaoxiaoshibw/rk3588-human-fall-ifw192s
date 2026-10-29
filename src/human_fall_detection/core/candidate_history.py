"""Causal geometry histories, never a human classifier or an online background.

Only the previous observed frame is retained. Source rows name measurements,
not physical points across scans. Membership deltas compare occupied support
cells and retain the actual rows on each side of that comparison.
"""
import hashlib
import json
import math

import numpy as np

from core.tracking import candidate_view


def _near_cell(cell, support):
    x, y, z = cell
    return any((x+dx, y+dy, z+dz) in support
               for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1))


def ground_version(ground):
    """Bind the complete supplied plane, including its support/validity metadata."""
    if ground is None:
        return None
    encoded = json.dumps(ground, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf8')).hexdigest()


def structure_evidence(points, ground=None):
    """Measured surface/height distribution; deliberately no human score or gate."""
    p = np.asarray(points, dtype=float).reshape(-1, 3)
    if not len(p):
        return None
    centered = p - p.mean(axis=0)
    values = np.maximum(np.linalg.eigvalsh(centered.T @ centered / len(p)), 0)[::-1]
    largest = float(values[0])
    result = dict(point_count=len(p), span_source_m=np.ptp(p, axis=0).tolist(),
                  eigenvalues_m2=values.tolist(),
                  linearity=None if largest <= 1e-12 else float((values[0]-values[1])/largest),
                  planarity=None if largest <= 1e-12 else float((values[1]-values[2])/largest),
                  scattering=None if largest <= 1e-12 else float(values[2]/largest),
                  semantic='unknown', human_discrimination='UNVALIDATED', height_layers=None)
    if ground is not None and ground.get('status') == 'valid':
        normal = np.asarray(ground.get('normal'), dtype=float)
        offset = float(ground.get('offset_m'))
        if normal.shape != (3,) or not np.isfinite(normal).all() or not math.isfinite(offset):
            raise ValueError('invalid history ground')
        heights = p @ normal + offset
        # Fixed physical bins include low poses. No standing-height entry gate.
        edges = [-.3, 0., .3, .6, .9, 1.2, 1.5, 1.8, 2.1, 2.7]
        counts, _ = np.histogram(heights, edges)
        result['height_layers'] = dict(edges_m=edges, counts=counts.tolist(),
            outside_count=int(len(p)-counts.sum()))
    return result


class CandidateHistory:
    def __init__(self, max_gap_s=.3, center_gate_m=.5, cell_m=.1):
        self.max_gap_s = float(max_gap_s)
        self.center_gate_m = float(center_gate_m)
        self.cell_m = float(cell_m)
        if any(not math.isfinite(x) or x <= 0 for x in
               (self.max_gap_s, self.center_gate_m, self.cell_m)):
            raise ValueError('invalid candidate history settings')
        self._next_id = 1
        self._previous = []
        self._stamp = None
        self._binding = None
        self.ledger = []
        self.departed = []
        self.reset_reason = 'startup'

    def reset(self, reason):
        self._previous = []
        self._stamp = None
        self._binding = None
        self.ledger = []
        self.departed = []
        self.reset_reason = reason

    def _measurement(self, candidate, points, row_offset):
        session_rows = 'source_rows' in candidate
        rows = candidate.get('source_rows') if session_rows else candidate.get('evidence_indices')
        center = candidate_view(candidate)['position_m']
        p = None
        if rows is not None:
            ids = np.asarray(rows)
            if ids.ndim != 1 or (len(ids) and ids.dtype.kind not in 'iu'):
                raise ValueError('invalid source rows')
            ids = ids.astype(np.int64)
            if len(np.unique(ids)) != len(ids) or len(ids) != candidate['point_count']:
                raise ValueError('source row count/uniqueness mismatch')
            if points is not None:
                local = ids - row_offset if session_rows else ids
                if len(ids) and (local.min() < 0 or local.max() >= len(points)):
                    raise ValueError('source rows outside frame')
                p = points[local]
                if not np.isfinite(p).all():
                    raise ValueError('nonfinite support points')
                if len(p):
                    center = np.median(p, axis=0)
            rows = (ids if session_rows else ids + row_offset).tolist()
        center = np.asarray(center, dtype=float)
        if center.shape != (3,) or not np.isfinite(center).all():
            raise ValueError('invalid candidate position')
        cells = [] if p is None else [tuple(cell) for cell in
                                     np.floor(p/self.cell_m).astype(np.int64).tolist()]
        return dict(center=center, points=p, rows=rows, cells=cells, support=set(cells))

    def analyze(self, candidates, stamp, binding, *, points=None, row_offset=0,
                frame_seq=None, ground=None):
        """Measure topology against old state without committing or allocating IDs."""
        stamp = float(stamp)
        reason = None
        if not math.isfinite(stamp):
            return dict(reason='invalid_time', previous=[], current=[], invalid=[], edges=[],
                        reverse=[], stamp=stamp, binding=binding)
        if self._binding is not None and self._binding != binding:
            reason = 'binding_changed'
        elif self._stamp is not None:
            if stamp <= self._stamp:
                return dict(reason='nonincreasing_time', previous=[], current=[], invalid=[],
                            edges=[], reverse=[], stamp=stamp, binding=binding)
            if stamp-self._stamp > self.max_gap_s:
                reason = 'observation_gap'
        previous = [] if reason else self._previous
        if points is not None:
            points = np.asarray(points, dtype=float)
            if points.ndim != 2 or points.shape[1] != 3:
                raise ValueError('history points must be (N,3)')
        current = []
        invalid = []
        for c in candidates:
            try:
                m = self._measurement(c, points, row_offset)
            except (ValueError, TypeError, KeyError, OverflowError):
                invalid.append(dict(candidate_id=c.get('candidate_id'), reason='invalid_source_support'))
                continue
            m['candidate_id'] = c['candidate_id']
            current.append(m)
        edges = [[] for _ in current]
        reverse = [[] for _ in previous]
        for i, m in enumerate(current):
            for j, old in enumerate(previous):
                distance = float(np.linalg.norm(m['center']-old['center']))
                overlap = len(m['support'] & old['support'])
                fraction = overlap / max(1, min(len(m['support']), len(old['support'])))
                if fraction < .1 and distance <= self.cell_m and m['support'] and old['support']:
                    small, large = sorted((m['support'], old['support']), key=len)
                    fraction = sum(_near_cell(cell, large) for cell in small)/len(small)
                # Position-only compatibility is for legacy synthetic callers;
                # real input callers always provide measured support and rows.
                # Topology must precede the centre gate: a merged object's
                # median can move far from one of its constituent surfaces.
                if (fraction >= .1 if m['support'] and old['support'] else
                        distance <= self.center_gate_m):
                    edges[i].append((j, distance, fraction))
                    reverse[j].append(i)
        return dict(reason=reason, previous=previous, current=current,
                    invalid=invalid, edges=edges, reverse=reverse,
                    stamp=stamp, binding=binding)

    def commit(self, analysis, *, frame_seq=None, row_offset=0, ground=None):
        """Commit one analyzed frame: allocate ids, adopt support, record once.

        ``analysis`` comes from :meth:`analyze` (no side effects there). It is the
        single commit point of a frame, so a caller that replaces the candidate
        list (for example with a supported fragment composition) never advances
        the ledger twice with the same timestamp.
        """
        if analysis['reason']:
            self.reset(analysis['reason'])
        stamp = analysis['stamp']
        previous, current = analysis['previous'], analysis['current']
        edges, reverse, invalid = analysis['edges'], analysis['reverse'], analysis['invalid']
        ledger = []
        continued = set()
        for i, m in enumerate(current):
            links = edges[i]
            unique = (len(links) == 1 and len(reverse[links[0][0]]) == 1
                      and links[0][1] <= self.center_gate_m)
            old = previous[links[0][0]] if unique else None
            if old is None:
                hid = 'h%06d' % self._next_id
                self._next_id += 1
                first = stamp
                count = 1
                origin = m['center']
                path = 0.
            else:
                continued.add(links[0][0])
                hid, first, count = old['history_id'], old['first_s'], old['observed_frames']+1
                origin = old['origin']
                path = old['path_m']+links[0][1]
            conflict = len(links) > 1 or any(len(reverse[j]) > 1 for j, _, _ in links)
            status = ('unique_support' if m['support'] and old and old['support'] else
                      'position_only') if unique else ('support_conflict' if conflict else
                      'support_discontinuity' if links else 'new_observation')
            ancestors = set() if old is None else set(old['unresolved_ancestors'])
            truncated = False if old is None else old['lineage_truncated']
            if conflict and m['support']:
                for j, _, _ in links:
                    ancestors.update(previous[j]['unresolved_ancestors'] or {previous[j]['history_id']})
                    truncated |= previous[j]['lineage_truncated']
            # Bound diagnostic provenance as well as observed support memory.
            # Truncation never clears uncertainty or permits a measurement.
            truncated |= len(ancestors) > 64
            ancestors = set(sorted(ancestors)[:64])
            # A merge/split is compared against every linked predecessor, not
            # only one arbitrarily chosen "old" record.  Otherwise a merged
            # candidate would report all of its rows as newly added and hide the
            # rows that disappeared from the other predecessor.
            linked_previous = [previous[j] for j, _, _ in links]
            prior_support = set().union(*(item['support'] for item in linked_previous)) \
                if linked_previous else set()
            prior_rows_cells = [(r, cell) for item in linked_previous
                                for r, cell in zip(item['rows'] or [], item['cells'])]
            current_rows = m['rows'] or []
            added = [r for r, cell in zip(current_rows, m['cells']) if cell not in prior_support]
            removed = [r for r, cell in prior_rows_cells if cell not in m['support']]
            record = dict(history_id=hid, candidate_id=m['candidate_id'], semantic='unknown',
                first_s=first, last_s=stamp, observed_frames=count, span_s=stamp-first,
                frame_seq=frame_seq, binding=list(analysis['binding']), row_offset=row_offset,
                source_rows=m['rows'], source_stamp_s=stamp,
                row_domain='source_rows_in_session_frame',
                association=dict(status=status, previous_history_ids=[previous[j]['history_id'] for j, _, _ in links],
                    unresolved_ancestors=sorted(ancestors),
                    lineage_truncated=bool(truncated),
                    center_shift_m=None if old is None else links[0][1],
                    support_overlap=None if old is None else links[0][2]),
                temporal=dict(net_displacement_m=float(np.linalg.norm(m['center']-origin)), path_m=path,
                    motion_is_human_evidence=False),
                structure=structure_evidence(m['points'], ground) if m['points'] is not None else None,
                membership=dict(policy='retain_all_observed_candidate_rows', changed_by_history=False,
                    added_source_rows=added, added_reason='newly_observed_support_cells',
                    removed_source_rows=removed, removed_reason='previous_support_cells_not_reobserved',
                    previous_stamp_s=None if old is None else old['last_s'],
                    previous_frame_seq=None if old is None else old['frame_seq'],
                    compared_history_ids=[item['history_id'] for item in linked_previous],
                    comparison=('no_previous_history' if not linked_previous else
                                'spatial_cells_against_all_linked_previous_histories'
                                if len(linked_previous) > 1 else
                                'spatial_cells_against_previous_history_not_point_identity'),
                    unresolved_related_history_ids=[previous[j]['history_id'] for j, _, _ in links] if not unique else []))
            m.update(history_id=hid, first_s=first, last_s=stamp, observed_frames=count,
                     origin=origin, path_m=path, frame_seq=frame_seq, unresolved_ancestors=ancestors,
                     lineage_truncated=bool(truncated))
            ledger.append(record)
        self._previous = current
        self.departed = [dict(history_id=old['history_id'], source_rows=old['rows'],
            previous_frame_seq=old['frame_seq'], previous_stamp_s=old['last_s'],
            reason='split_merge_or_discontinuity_unresolved' if reverse[j] else 'no_current_support',
            current_candidate_ids=[current[i]['candidate_id'] for i in reverse[j]])
            for j, old in enumerate(previous) if j not in continued]
        self._stamp, self._binding, self.ledger = stamp, analysis['binding'], ledger
        result = self.summary()
        result['invalid'] = invalid
        return result

    def step(self, candidates, stamp, binding, *, points=None, row_offset=0,
             frame_seq=None, ground=None):
        stamp = float(stamp)
        analysis = self.analyze(candidates, stamp, binding, points=points,
            row_offset=row_offset, frame_seq=frame_seq, ground=ground)
        if analysis['reason'] in ('invalid_time', 'nonincreasing_time'):
            self.reset(analysis['reason'])
            return self.summary()
        return self.commit(analysis, frame_seq=frame_seq, row_offset=row_offset,
                           ground=ground)

    def measured_centers(self):
        """Current support medians (position-only fallback for legacy callers)."""
        return {item['history_id']: item['center'].copy() for item in self._previous}

    def measured_support(self, limit=512):
        """Bounded, order-independent actual support samples for entry diagnostics."""
        result = {}
        for item in self._previous:
            p = item['points']
            if p is not None and len(p):
                p = np.unique(p, axis=0)
                result[item['history_id']] = p[np.linspace(0, len(p)-1, min(limit, len(p))).astype(int)].copy()
        return result

    def summary(self):
        # Full row/structure ledger stays available to offline callers. The board
        # state publishes compact evidence, avoiding a second full cloud payload.
        return dict(reset_reason=self.reset_reason, cell_m=self.cell_m,
            binding=None if self._binding is None else list(self._binding), source_stamp_s=self._stamp,
            center_gate_m=self.center_gate_m, max_gap_s=self.max_gap_s, min_support_overlap=.1,
            boundary_tolerance='adjacent support cells only when center shift <= cell_m',
            departed_count=len(self.departed),
            candidates=[dict(history_id=r['history_id'], candidate_id=r['candidate_id'],
                observed_frames=r['observed_frames'], span_s=r['span_s'],
                association=r['association'], semantic='unknown',
                temporal=r['temporal'], structure=r['structure'],
                source_row_count=len(r['source_rows'] or []),
                source_rows_sha256=hashlib.sha256(json.dumps(r['source_rows'],separators=(',', ':')).encode('utf8')).hexdigest())
                for r in self.ledger], invalid=[])
