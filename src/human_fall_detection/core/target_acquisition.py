"""Causal automatic acquisition of one geometric target; semantics stay unknown."""
import math

import numpy as np

from core.tracking import candidate_view
from core.association import associate_tracks
from core.candidate_history import CandidateHistory, ground_version
from core.support_composition import connectivity as composition_connectivity
from core.support_composition import evaluate as evaluate_composition
from core.support_composition import resolve_settings as resolve_composition
from core.support_composition import sample_points
from core.support_composition import support_cells


DEFAULT_SETTINGS = dict(min_seconds=0.6, min_frames=5, max_gap_s=0.3,
                        continuity_m=0.5, min_points=30,
                        min_extent_m=0.1, max_extent_m=2.5,
                        min_height_span_m=0.15, max_height_m=2.7,
                        change_min_frames=5, change_min_displacement_m=0.3,
                        entry_height_min_m=0.8, entry_height_max_m=2.2,
                        entry_motion_window_s=1.2, entry_motion_min_frames=5,
                        entry_motion_min_displacement_m=0.3, entry_support_static_tolerance_m=0.1,
                        non_target_separation_m=1.5, non_target_memory_s=3.,
                        non_target_memory_radius_m=.5, recovery_gap_s=.5,
                        recovery_min_seconds=.2, recovery_min_frames=3)


class TargetAcquisition:
    def __init__(self, tracker, settings=None):
        self.tracker = tracker
        self.settings = dict(DEFAULT_SETTINGS)
        self.human_entry_gate = (settings or {}).get('human_entry_gate', True)
        self.support_history_guard = (settings or {}).get('support_history_guard', False)
        self.change_gate = (settings or {}).get('change_gate', False)
        self.history_hold_gate = (settings or {}).get('history_hold_gate', False)
        self.identity_recovery_guard = (settings or {}).get('identity_recovery_guard', True)
        if not isinstance(self.identity_recovery_guard, bool):
            raise ValueError('identity_recovery_guard must be boolean')
        if not isinstance(self.human_entry_gate, bool):
            raise ValueError('human_entry_gate must be boolean')
        if not isinstance(self.support_history_guard, bool):
            raise ValueError('support_history_guard must be boolean')
        if not isinstance(self.change_gate, bool):
            raise ValueError('change_gate must be boolean')
        if not isinstance(self.history_hold_gate, bool):
            raise ValueError('history_hold_gate must be boolean')
        for key, value in (settings or {}).items():
            if key in ('support_history_guard', 'change_gate', 'history_hold_gate', 'human_entry_gate', 'identity_recovery_guard', 'composition'):
                continue
            if key not in self.settings or not math.isfinite(float(value)) or float(value) <= 0:
                raise ValueError('invalid acquisition setting: ' + str(key))
            self.settings[key] = float(value)
        if self.settings['entry_height_min_m'] > self.settings['entry_height_max_m']:
            raise ValueError('invalid entry height range')
        frames = self.settings['entry_motion_min_frames']
        if frames != int(frames) or not 5 <= frames <= 64:
            raise ValueError('entry_motion_min_frames must be an integer in [5,64]')
        self._entry_windows = {}
        self._non_target_histories = set()
        self._non_target_memory = {}
        self._recovery = None
        self._binding = None
        self._last_time = None
        self._pending = None
        self._pending_history_id = None
        self._start = None
        self._count = 0
        self._next_id = 1
        self._last_observed = None
        self._last_history_id = None
        self._selection_basis = None
        self._locked_history_id = None
        self.composition = resolve_composition((settings or {}).get('composition'))
        self._last_target_support = None
        self._composition = None
        self._rebuild = None
        self.history = CandidateHistory(self.settings['max_gap_s'], self.settings['continuity_m'])
        self.state = dict(status='searching', reason='no_candidate', semantic='unknown')

    def _clear(self):
        self._pending = None
        self._pending_history_id = None
        self._start = None
        self._count = 0

    def reset(self, reason):
        self._clear()
        self._entry_windows = {}
        self._non_target_histories = set()
        self._non_target_memory = {}
        self._recovery = None
        self._binding = None
        self._last_time = None
        self._last_observed = None
        self._last_history_id = None
        self._selection_basis = None
        self._locked_history_id = None
        self._last_target_support = None
        self._composition = None
        self._rebuild = None
        self.history.reset(reason)
        self.tracker.release(reason)
        self.state = dict(status='searching', reason=reason, semantic='unknown')

    def quality_reason(self, candidate):
        try:
            p = np.asarray(candidate_view(candidate)['position_m'], dtype=float)
            if p.shape != (3,) or not np.isfinite(p).all():
                return 'invalid_position'
            if not candidate.get('ground_relative_available'):
                return 'ground_unavailable'
            h = candidate['height_m']
            values = [h['min'], h['max'], h['p10'], h['p90'],
                      candidate['horizontal_extent_m']['max'], candidate['point_count']]
            if not np.isfinite(values).all():
                return 'invalid_geometry'
            if candidate['point_count'] < self.settings['min_points']:
                return 'insufficient_support'
            extent = values[4]
            if not self.settings['min_extent_m'] <= extent <= self.settings['max_extent_m']:
                return 'extent_out_of_range'
            if h['max'] > self.settings['max_height_m'] or h['min'] < -0.3:
                return 'height_out_of_range'
            if h['p90'] - h['p10'] < self.settings['min_height_span_m']:
                return 'insufficient_height_span'
        except (KeyError, TypeError, ValueError):
            return 'invalid_geometry'
        return None

    def _entry_candidates(self, candidates, rejected, histories, stamp):
        """Initial acquisition only: height and recent measured movement."""
        windows = {}
        diagnostics = {}
        eligible = []
        centers = self.history.measured_centers()
        support = self.history.measured_support()
        for candidate in candidates:
            cid = candidate['candidate_id']
            if rejected[cid] is not None:
                continue
            height = candidate['height_m']['p90']
            detail = dict(height_p90_m=height, motion_frames=0,
                          motion_span_s=0., motion_displacement_m=None)
            diagnostics[cid] = detail
            if not self.settings['entry_height_min_m'] <= height <= self.settings['entry_height_max_m']:
                rejected[cid] = 'entry_height_out_of_range'
                continue
            history = histories.get(cid)
            if history is None:
                rejected[cid] = 'entry_history_unavailable'
                continue
            detail['support_ancestry_unresolved'] = bool(history['association']['unresolved_ancestors'])
            if history['association']['lineage_truncated']:
                rejected[cid] = 'entry_truncated_support_history'
                continue
            hid = history['history_id']
            samples = [sample for sample in self._entry_windows.get(hid, [])
                       if stamp-sample[0] <= self.settings['entry_motion_window_s'] + 1e-9]
            position = centers[hid]
            samples.append((stamp, position, support.get(hid)))
            samples = samples[-64:]
            windows[hid] = samples
            detail.update(history_id=hid, motion_frames=len(samples),
                          motion_span_s=stamp-samples[0][0])
            if len(samples) < self.settings['entry_motion_min_frames']:
                rejected[cid] = 'entry_motion_window'
                continue
            # Median endpoints reject a single jitter spike; path length would
            # accumulate stationary noise. Old motion expires with the window.
            positions = np.asarray([sample[1] for sample in samples])
            distance = float(np.linalg.norm(np.median(positions[-3:], axis=0)
                                            - np.median(positions[:3], axis=0)))
            detail['motion_displacement_m'] = distance
            if distance + 1e-9 < self.settings['entry_motion_min_displacement_m']:
                rejected[cid] = 'entry_motion_not_observed'
                continue
            old, current = samples[1][2], samples[-2][2]
            if old is not None and current is not None:
                delta = np.median(positions[-3:], axis=0) - np.median(positions[:3], axis=0)
                # Squared distances avoid an (N,N,3) allocation and a square
                # root for every pair; only the nearest residuals need roots.
                distances = (np.sum(old*old, axis=1)[:, None]
                    + np.sum(current*current, axis=1)[None, :]
                    - 2*np.einsum('ik,jk->ij', old, current))
                def residual(squared):
                    nearest = np.concatenate((squared.min(axis=0), squared.min(axis=1)))
                    return float(np.median(np.sqrt(np.maximum(nearest, 0.))))
                stationary = residual(distances)
                distances += 2*((old @ delta)[:, None] - (current @ delta)[None, :]) + np.dot(delta, delta)
                translated = residual(distances)
                detail.update(stationary_support_residual_m=stationary,
                              translated_support_residual_m=translated,
                              support_fit_improvement_m=stationary-translated,
                              support_sample_counts=[len(old), len(current)])
                if (stationary <= self.settings['entry_support_static_tolerance_m']
                        or translated >= stationary):
                    rejected[cid] = 'entry_motion_explained_by_visibility'
                    continue
            eligible.append(candidate)
        self._entry_windows = windows
        return eligible, diagnostics

    @staticmethod
    def _local_rows(candidate, points, row_offset):
        """Rows of one candidate inside the array the caller passed as ``points``.

        ``source_rows`` always name session rows; ``evidence_indices`` stay in the
        array domain the producer handed over. Both are mapped here explicitly so
        a non-zero ``row_offset`` and a pre-filtered selected subarray never mix
        row domains.
        """
        if 'source_rows' in candidate:
            rows = np.asarray(candidate['source_rows'])
            if rows.ndim != 1:
                raise ValueError('invalid candidate source_rows')
            rows = rows.astype(np.int64) - int(row_offset)
        else:
            rows = np.asarray(candidate.get('evidence_indices'))
            if rows.ndim != 1:
                raise ValueError('invalid candidate evidence_indices')
            rows = rows.astype(np.int64)
        if not len(rows) or len(np.unique(rows)) != len(rows):
            raise ValueError('candidate rows empty or duplicated')
        if rows.min() < 0 or rows.max() >= len(points):
            raise ValueError('candidate rows outside frame')
        return rows

    def _candidate_points(self, candidate, points, row_offset):
        rows = self._local_rows(candidate, points, row_offset)
        array = np.asarray(points, dtype=np.float64)
        if not np.isfinite(array[rows]).all():
            raise ValueError('nonfinite candidate points')
        return array[rows]

    def _remember_target_support(self, observed, points, row_offset, stamp):
        """Bounded memory of the last measured target support (cells + sample).

        Only current, actually measured target rows are stored; no prediction and
        no history-only rows.
        """
        if observed is None or points is None:
            self._last_target_support = None
            return
        try:
            actual = self._candidate_points(observed, points, row_offset)
        except (ValueError, TypeError, KeyError):
            self._last_target_support = None
            return
        settings = self.composition
        cells = support_cells(actual, settings['cell_m'], settings['max_cells'])
        sample = sample_points(actual, 768)
        self._last_target_support = dict(
            cells=cells, points=np.asarray(sample, dtype=np.float64).copy(),
            center=np.median(actual, axis=0), point_count=int(len(actual)),
            source_stamp_s=None if stamp is None else float(stamp))

    def _prospective_histories(self, analysis):
        """Evidence view of the current candidates before the single commit.

        Mirrors the committed record fields the holding gates read, without
        allocating ids or mutating the ledger.
        """
        previous = analysis['previous']
        records = {}
        for index, measurement in enumerate(analysis['current']):
            links = analysis['edges'][index]
            unique = (len(links) == 1 and len(analysis['reverse'][links[0][0]]) == 1
                      and links[0][1] <= self.history.center_gate_m)
            old = previous[links[0][0]] if unique else None
            conflict = len(links) > 1 or any(
                len(analysis['reverse'][j]) > 1 for j, _, _ in links)
            ancestors = set() if old is None else set(old['unresolved_ancestors'])
            truncated = False if old is None else old['lineage_truncated']
            if conflict and measurement['support']:
                for j, _, _ in links:
                    ancestors.update(previous[j]['unresolved_ancestors']
                                     or {previous[j]['history_id']})
                    truncated |= previous[j]['lineage_truncated']
            truncated |= len(ancestors) > 64
            records[measurement['candidate_id']] = dict(
                candidate_id=measurement['candidate_id'],
                history_id=None if old is None else old['history_id'],
                observed_frames=1 if old is None else old['observed_frames'] + 1,
                center=measurement['center'],
                association=dict(
                    previous_history_ids=[previous[j]['history_id'] for j, _, _ in links],
                    unresolved_ancestors=sorted(ancestors)[:64],
                    lineage_truncated=bool(truncated)))
        return records

    def _target_lineage(self, analysis, locked):
        """Previous histories that already belong to the locked target's lineage."""
        lineage = set() if locked is None else {locked}
        for old in analysis['previous']:
            if old['history_id'] in lineage:
                lineage |= set(old['unresolved_ancestors'] or ())
        return lineage

    def _compose_fragments(self, usable, histories, analysis, points, row_offset,
                           ground, elapsed, rebuilt_id='g0000'):
        """Try one constrained composition of the target's current fragments.

        Returns ``dict(accepted, reason, metrics, component_ids, candidate)`` or
        ``None`` when this frame offers nothing to compose. The diagnostic
        decision is always kept in ``self._composition``; no prediction becomes a
        measurement and no unmeasured candidate is added.
        """
        settings = self.composition
        support = self._last_target_support
        self._composition = None
        if (not settings['enabled'] or self._rebuild is None or support is None
                or points is None or not support['cells']):
            return None
        lineage = self._target_lineage(analysis, self._last_history_id)
        locked = self._last_history_id
        group, competitors = [], []
        for candidate in usable:
            evidence = histories.get(candidate['candidate_id'])
            links = [] if evidence is None else list(
                evidence['association']['previous_history_ids'])
            try:
                actual = self._candidate_points(candidate, points, row_offset)
            except (ValueError, TypeError, KeyError):
                continue
            if not len(actual):
                continue
            cells = support_cells(actual, settings['cell_m'], settings['max_cells'])
            overlap = len(cells & support['cells']) / max(1, len(cells))
            foreign = any(link not in lineage for link in links)
            if foreign:
                competitors.append(candidate_view(candidate)['position_m'])
                continue
            group.append(dict(candidate=candidate, points=actual, cells=cells,
                              support=overlap, links=links))
        anchors = [index for index, item in enumerate(group)
                   if item['support'] >= settings['min_fragment_support']]
        if anchors:
            # Keep anchor-connected fragments for scoring. Multiple anchored
            # components remain an unresolved proposal: evaluate_composition
            # must refuse their disconnected union, without picking one.
            graph = composition_connectivity(group, settings['max_fragment_gap_m'])
            keep = set()
            for component in graph['components']:
                if set(component) & set(anchors):
                    keep.update(component)
            dropped = [index for index in range(len(group)) if index not in keep]
            competitors.extend(candidate_view(group[index]['candidate'])['position_m']
                               for index in dropped)
            group = [group[index] for index in sorted(keep)]
        self._composition = dict(
            policy='track_guided_supported_fragment_composition',
            frame_support_cells=len(support['cells']),
            grouped=[item['candidate']['candidate_id'] for item in group],
            grouped_support=[round(item['support'], 4) for item in group],
            grouped_points=[int(item['candidate']['point_count']) for item in group],
            competitors=len(competitors), accepted=False, reason=None, metrics=None)
        if len(group) < 2:
            self._composition['reason'] = ('single_fragment' if len(group) < 2
                                           else 'too_many_fragments')
            return None
        if len(group) > settings['max_fragments']:
            self._composition['reason'] = 'too_many_fragments'
            return None
        basis = None
        if isinstance(ground, dict):
            try:
                from core.lidar_candidates import ground_frame_eligible, ground_plane_basis
            except ImportError:  # pragma: no cover
                from lidar_candidates import ground_frame_eligible, ground_plane_basis
            if ground_frame_eligible(ground, 'innolidar'):
                basis = ground_plane_basis(ground)
        predicted = self.tracker._predict(max(0.0, float(elapsed)))
        decision = evaluate_composition(
            support['points'], support['cells'],
            [dict(candidate_id=item['candidate']['candidate_id'],
                  points=item['points'], cells=item['cells']) for item in group],
            settings=settings, ground_basis=basis,
            ground_offset_m=(None if not isinstance(ground, dict)
                             else ground.get('offset_m')),
            predicted_position=predicted.tolist(),
            gate_m=self.tracker.settings['gate_m'],
            competitor_positions=competitors)
        self._composition.update(accepted=bool(decision['accepted']),
                                 reason=decision['reason'],
                                 metrics=decision['metrics'])
        if not decision['accepted']:
            return None
        rows = np.unique(np.concatenate([
            self._local_rows(item['candidate'], points, row_offset) for item in group]))
        try:
            composed = self._rebuild(rows.tolist())
        except (ValueError, TypeError, KeyError) as exc:
            self._composition.update(accepted=False, reason='rebuild_failed',
                                     error=str(exc))
            return None
        if not isinstance(composed, dict) or 'evidence_indices' not in composed:
            self._composition.update(accepted=False, reason='rebuild_incomplete')
            return None
        composed['candidate_id'] = rebuilt_id
        composed['semantic'] = 'unknown'
        composed['source_rows'] = sorted((rows + int(row_offset)).tolist())
        composed['composition'] = dict(
            policy='track_guided_supported_fragment_composition',
            component_candidate_ids=[item['candidate']['candidate_id'] for item in group],
            component_point_counts=[int(item['candidate']['point_count']) for item in group],
            component_support=[round(item['support'], 4) for item in group],
            component_history_ids=[list(item['links']) for item in group],
            union_point_count=int(len(rows)),
            metrics=decision['metrics'])
        self._composition['union_point_count'] = int(len(rows))
        self._composition['component_history_ids'] = [
            list(item['links']) for item in group]
        return dict(accepted=True, reason=decision['reason'],
                    metrics=decision['metrics'],
                    component_ids=[item['candidate']['candidate_id'] for item in group],
                    candidate=composed, rows=rows)

    def _commit_frame(self, composed, analysis, *, stamp, points, row_offset,
                      frame_seq, ground, candidates, rejected, blocked_prev):
        """Commit exactly one candidate history for this frame.

        A supported composition replaces its components before the commit, so the
        frame is never stepped twice and fragments never consume an extra
        observation. Everything else is committed as produced.
        """
        if composed is not None:
            component_ids = set(composed['component_ids'])
            effective = [c for c in candidates if c['candidate_id'] not in component_ids]
            effective.append(composed['candidate'])
            analysis_eff = self.history.analyze(
                effective, stamp, analysis['binding'], points=points,
                row_offset=row_offset, frame_seq=frame_seq, ground=ground)
            history = self.history.commit(analysis_eff, frame_seq=frame_seq,
                                          row_offset=row_offset, ground=ground)
            for cid in component_ids:
                rejected[cid] = 'composed_into_target_support'
            rejected[composed['candidate']['candidate_id']] = None
        else:
            effective = candidates
            history = self.history.commit(analysis, frame_seq=frame_seq,
                                          row_offset=row_offset, ground=ground)
        histories = {r['candidate_id']: r for r in history['candidates']}
        if self.human_entry_gate:
            # A separately observed candidate cannot become this target merely
            # because the prediction gate grows during occlusion. Propagate
            # known coexisting support through its recorded merge/split lineage.
            self._non_target_histories = {e['history_id'] for e in histories.values()
                if (e['history_id'] in blocked_prev) or blocked_prev.intersection(
                    e['association']['previous_history_ids']) or blocked_prev.intersection(
                    e['association']['unresolved_ancestors'])}
        return history, histories, effective

    def step(self, candidates, time_epoch, source_stamp_s, *, calibration_version=None,
             coordinate_version=None, receive_s=None, valid=True, points=None,
             row_offset=0, frame_seq=None, ground=None, rebuild=None):
        self._rebuild = rebuild
        binding = (self.tracker.session_id, time_epoch, calibration_version,
                   coordinate_version, ground_version(ground))
        try:
            stamp = float(source_stamp_s)
        except (TypeError, ValueError):
            stamp = float('nan')
        fault = None
        if not valid:
            fault = 'input_unavailable'
        elif not math.isfinite(stamp):
            fault = 'invalid_time'
        elif self._binding is not None and binding != self._binding:
            fault = 'binding_changed'
        elif self._last_time is not None and stamp <= self._last_time:
            fault = 'nonincreasing_time'
        self._binding = binding
        if fault:
            self.reset(fault)
            return self.tracker.snapshot(), dict(self.state), None
        gap = None if self._last_time is None else stamp - self._last_time
        self._last_time = stamp
        # Analyze first (no side effects): the frame is committed exactly once,
        # after any supported fragment composition has replaced the fragments.
        analysis = self.history.analyze(candidates, stamp, binding, points=points,
            row_offset=row_offset, frame_seq=frame_seq, ground=ground)
        if analysis['reason']:
            self.history.reset(analysis['reason'])
            analysis = self.history.analyze(candidates, stamp, binding, points=points,
                row_offset=row_offset, frame_seq=frame_seq, ground=ground)
        histories = self._prospective_histories(analysis)
        self._non_target_memory = {hid: m for hid, m in self._non_target_memory.items()
                                   if stamp <= m['until_s']}
        blocked_prev = self._non_target_histories
        blocked_now = set()
        if self.human_entry_gate:
            for cid, evidence in histories.items():
                if ((evidence['history_id'] is not None
                     and evidence['history_id'] in blocked_prev)
                        or blocked_prev.intersection(
                            evidence['association']['previous_history_ids'])
                        or blocked_prev.intersection(
                            evidence['association']['unresolved_ancestors'])):
                    blocked_now.add(cid)
        rejected = {c.get('candidate_id'): self.quality_reason(c) for c in candidates}
        for item in analysis['invalid']:
            rejected[item['candidate_id']] = item['reason']
        for cid, evidence in histories.items():
            if self.support_history_guard and evidence['association']['unresolved_ancestors']:
                rejected[cid] = 'unresolved_support_history'
        selection_basis = self._selection_basis or 'associated_geometry_not_human_classification'
        entry_evidence = {}
        holding = self.tracker.track_status in ('locked', 'occluded')
        usable = []
        recovery_pick = None
        merge = support_conflict = history_identity_conflict = known_non_target = False
        if holding:
            # Holding uses association, not the initial stance/size gates.
            self._entry_windows = {}
            usable=[];merge=False;support_conflict=False;history_identity_conflict=False;known_non_target=False
            for c in candidates:
                invalid=rejected[c.get('candidate_id')]
                if invalid in ('invalid_position','ground_unavailable','invalid_geometry','invalid_source_support'):
                    continue
                evidence = histories.get(c.get('candidate_id'))
                if self.human_entry_gate and c['candidate_id'] in blocked_now:
                    rejected[c['candidate_id']] = 'known_non_target_history'
                    known_non_target = True
                    continue
                if (self.human_entry_gate and self.identity_recovery_guard and evidence is not None
                        and evidence['history_id'] != self._last_history_id
                        and self._last_history_id not in evidence['association']['previous_history_ids']):
                    center = np.asarray(evidence['center'], dtype=float)
                    if any(np.linalg.norm(center-m['center']) <= self.settings['non_target_memory_radius_m']
                           for m in self._non_target_memory.values()):
                        rejected[c['candidate_id']] = 'known_non_target_spatial_memory'
                        known_non_target = True
                        continue
                if (self.history_hold_gate and self._locked_history_id is not None
                        and (evidence is None
                             or evidence['history_id'] != self._locked_history_id)):
                    history_identity_conflict = True
                    continue
                if (self.support_history_guard and evidence and evidence['association']['unresolved_ancestors']):
                    support_conflict = True
                    continue
                if self._last_observed is not None:
                    previous=self._last_observed
                    if (c['point_count'] > previous['point_count'] * 3
                            and c['horizontal_extent_m']['max'] > previous['horizontal_extent_m']['max'] * 2):
                        merge=True
                        continue
                usable.append(c)
            composed = None
            compose_elapsed, compose_invalid = self.tracker._elapsed(stamp, receive_s)
            if (self._last_observed is not None
                    and self._last_target_support is not None
                    and compose_invalid is None and compose_elapsed is not None
                    and 0.0 <= compose_elapsed <= self.settings['max_gap_s']):
                composed = self._compose_fragments(usable, histories, analysis, points,
                                                   row_offset, ground, compose_elapsed)
            history, histories, final_candidates = self._commit_frame(
                composed, analysis, stamp=stamp, points=points, row_offset=row_offset,
                frame_seq=frame_seq, ground=ground, candidates=candidates,
                rejected=rejected, blocked_prev=blocked_prev)
            if composed is not None:
                component_ids = set(composed['component_ids'])
                usable = [composed['candidate']] + [
                    c for c in usable if c['candidate_id'] not in component_ids]
            recovery_pick = None
            elapsed, invalid_clock = self.tracker._elapsed(stamp, receive_s)
            if (self.identity_recovery_guard and invalid_clock is None and elapsed is not None
                    and self.settings['recovery_gap_s'] < elapsed <= self.tracker.settings['lost_timeout_s']):
                trusted = []
                unbacked = []
                for c in usable:
                    e = histories.get(c['candidate_id'])
                    lineage = [] if e is None else e['association']['previous_history_ids']
                    if e is not None and (e['history_id'] == self._last_history_id
                                          or self._last_history_id in lineage):
                        trusted.append(c)
                    else:
                        unbacked.append(c)
                # Use a bounded prediction residual for unsupported recovery,
                # alongside the existing speed/ambiguity gate. Repeated geometry
                # can establish a NEW binding; it cannot prove old identity.
                predicted = self.tracker._predict(elapsed)
                matched = associate_tracks([dict(track_id='recovery', position_m=predicted.tolist())],
                    [candidate_view(c) for c in usable], elapsed, self.tracker._assoc_settings())['matches']
                pick = next((c for c in unbacked if matched and c['candidate_id']==matched[0]['candidate_id']), None)
                verifying = (pick is not None and np.linalg.norm(np.asarray(candidate_view(pick)['position_m'])-predicted) <= self.tracker.settings['gate_m'])
                if verifying:
                    e = histories[pick['candidate_id']]
                    previous = self._recovery
                    if (previous is None or previous['history_id'] != e['history_id']
                            or stamp-previous['last_s'] > self.settings['max_gap_s']):
                        previous = dict(history_id=e['history_id'], start_s=stamp, frames=0)
                    previous.update(last_s=stamp, frames=previous['frames']+1)
                    self._recovery = previous
                    if (previous['frames'] >= self.settings['recovery_min_frames']
                            and stamp-previous['start_s']+1e-9 >= self.settings['recovery_min_seconds']):
                        recovery_pick = pick
                else:
                    self._recovery = None
                for c in unbacked:
                    residual = float(np.linalg.norm(np.asarray(candidate_view(c)['position_m'])-predicted))
                    rejected[c['candidate_id']] = (
                        'recovery_residual_exceeded' if residual > self.tracker.settings['gate_m'] else
                        'recovery_verification_pending' if c is pick and verifying else
                        'recovery_candidate_competition' if len(usable) > 1 else
                        'recovery_association_rejected')
                usable = trusted
            else:
                self._recovery = None
            if recovery_pick is not None and not usable:
                state = self.tracker.select('t%04d' % self._next_id, time_epoch, candidate=recovery_pick,
                    calibration_version=calibration_version,
                    selection_version=self.tracker.selection_version+1,
                    source_stamp_s=stamp, receive_s=receive_s,
                    selection_source='verified_geometry_new_identity')
                self._next_id += 1
                self._locked_history_id = histories[recovery_pick['candidate_id']]['history_id']
                self._non_target_histories = set()
                self._non_target_memory = {}
                self._recovery = None
                rejected[recovery_pick['candidate_id']] = None
            else:
                state = self.tracker.update(usable, time_epoch, source_stamp_s=stamp,
                                            receive_s=receive_s)
            status = state['track_status']
            reason = state.get('history_reset_reason') if status in ('lost', 'ambiguous') else (
                'associated' if status == 'locked' else 'no_unique_measurement')
            if merge and status == 'occluded':reason='possible_merge_support_jump'
            if support_conflict and status == 'occluded':reason='support_split_merge_conflict'
            if history_identity_conflict and status == 'occluded':reason='history_identity_conflict'
            if known_non_target and status == 'occluded':reason='known_non_target_history'
            if self._recovery is not None and status == 'occluded':reason='recovery_verification_pending'
            if recovery_pick is not None and status == 'locked':reason='verified_geometry_new_identity'
            if status in ('lost', 'ambiguous'):
                self._locked_history_id = None
            self._clear()
        else:
            history, histories, final_candidates = self._commit_frame(
                None, analysis, stamp=stamp, points=points, row_offset=row_offset,
                frame_seq=frame_seq, ground=ground, candidates=candidates,
                rejected=rejected, blocked_prev=blocked_prev)
            if self.tracker.track_status in ('lost', 'ambiguous'):
                self.tracker.release('automatic_reacquisition')
                self._locked_history_id = None
                self._clear()
                self._entry_windows = {}
                self._non_target_histories = set()
                self._non_target_memory = {}
                self._recovery = None
            good = [c for c in candidates if rejected[c.get('candidate_id')] is None]
            change = []
            if self.human_entry_gate:
                good, entry_evidence = self._entry_candidates(good, rejected, histories, stamp)
            elif self.change_gate:
                for c in good:
                    evidence = histories.get(c.get('candidate_id'))
                    if (evidence is not None
                            and evidence['observed_frames'] >= self.settings['change_min_frames']
                            and evidence['temporal']['net_displacement_m']
                            >= self.settings['change_min_displacement_m']):
                        change.append(c)
            status, reason = 'searching', 'no_qualified_candidate'
            pick = None
            if self.human_entry_gate:
                selection_basis = 'height_and_recent_motion_not_human_classification'
                if len(good) == 1:
                    pick = good[0]
                else:
                    self._clear()
                    if len(good) > 1:
                        status, reason = 'ambiguous', 'competing_moving_candidates'
            elif self.change_gate and len(change) > 1:
                self._clear()
                status, reason = 'ambiguous', 'competing_change_candidates'
            elif self.change_gate and len(change) == 1:
                # Movement is only an acquisition cue. It never names a human
                # and never skips the quality/continuity gates.
                pick = change[0]
                selection_basis = 'causal_change_not_human_classification'
            elif len(good) == 1:
                pick = good[0]
                selection_basis = 'unique_persistent_geometry_not_human_classification'
            else:
                self._clear()
                if len(good) > 1:
                    status, reason = 'ambiguous', 'competing_candidates'
            if pick is not None:
                pick_history_id = histories[pick['candidate_id']]['history_id']
                position = np.asarray(candidate_view(pick)['position_m'], dtype=float)
                if (self._pending is None or gap is None or gap > self.settings['max_gap_s']
                        or (self.support_history_guard and self._pending_history_id != pick_history_id)
                        or (self.human_entry_gate and self._pending_history_id != pick_history_id)
                        or (self.change_gate and selection_basis.startswith('causal_change')
                            and self._pending_history_id != pick_history_id)
                        or np.linalg.norm(position - self._pending) > self.settings['continuity_m']):
                    self._clear()
                    self._start = stamp
                self._selection_basis = selection_basis
                self._pending = position
                self._pending_history_id = pick_history_id
                self._count += 1
                status, reason = 'acquiring', 'persistence_window'
                if (self._count >= self.settings['min_frames']
                        and stamp - self._start + 1e-9 >= self.settings['min_seconds']):
                    self.tracker.select('t%04d' % self._next_id, time_epoch, candidate=pick,
                                        calibration_version=calibration_version,
                                        selection_version=self.tracker.selection_version + 1,
                                        source_stamp_s=stamp, receive_s=receive_s,
                                        selection_source='automatic_acquisition')
                    self._next_id += 1
                    self._locked_history_id = pick_history_id
                    status, reason = 'locked', (
                        'unique_height_and_motion' if self.human_entry_gate else
                        'unique_causal_change' if selection_basis.startswith('causal_change')
                        else 'unique_persistent_geometry')
            state = self.tracker.snapshot()
        # Automatic loss never asks for an operator action. Next valid frame competes again.
        self.tracker.requires_reselection = False
        state['requires_reselection'] = False
        observed = None
        if state['track_status'] == 'locked' and not state['position_predicted']:
            observed = next((c for c in final_candidates
                             if c['candidate_id'] == state['candidate_id']), None)
            self._last_observed = observed
            self._last_history_id = histories[observed['candidate_id']]['history_id'] if observed else None
            self._remember_target_support(observed, points, row_offset, stamp)
            if self.human_entry_gate and observed is not None:
                centers = self.history.measured_centers()
                center = centers[self._last_history_id]
                normal = None if ground is None else np.asarray(ground.get('normal'), dtype=float)
                if normal is not None and (normal.shape != (3,) or not np.isfinite(normal).all()
                                           or np.dot(normal,normal) <= 1e-12):
                    normal = None
                for cid,evidence in histories.items():
                    if (cid == observed['candidate_id'] or evidence['observed_frames']
                            < self.settings['entry_motion_min_frames']):
                        continue
                    delta = centers[evidence['history_id']] - center
                    if normal is not None:
                        delta = delta - normal * np.dot(delta,normal) / np.dot(normal,normal)
                    # Nearby disconnected limbs are not an independently
                    # located object. Require sustained spatial separation.
                    if np.linalg.norm(delta) > self.settings['non_target_separation_m']:
                        self._non_target_histories.add(evidence['history_id'])
                        self._non_target_memory[evidence['history_id']] = dict(
                            center=centers[evidence['history_id']], until_s=stamp+self.settings['non_target_memory_s'])
                # Bounded memory; old positions expire and a new target clears it.
                self._non_target_memory = dict(sorted(self._non_target_memory.items(),
                    key=lambda item: item[1]['until_s'])[-128:])
        self.state = dict(status=status, reason=reason, semantic='unknown',
                          persistence_frames=self._count, rejected=rejected,
                          selection_basis=selection_basis,
                          change_gate=('required_recent_motion' if self.human_entry_gate else
                                       'experimental_causal_change' if self.change_gate else 'disabled'),
                          history_hold_gate=('experimental_same_history' if self.history_hold_gate
                                             else 'disabled'),
                          history_policy='experimental_guard' if self.support_history_guard else 'evidence_only',
                          candidate_history=history)
        if self._composition is not None:
            self.state['composition'] = dict(self._composition)
        if self.human_entry_gate:
            self.state['entry_gate'] = dict(enabled=True, phase='holding' if state['track_status'] in ('locked','occluded') else 'acquisition',
                height_statistic='ground_relative_p90', height_min_m=self.settings['entry_height_min_m'],
                height_max_m=self.settings['entry_height_max_m'],
                motion_window_s=self.settings['entry_motion_window_s'],
                motion_min_frames=self.settings['entry_motion_min_frames'],
                motion_min_displacement_m=self.settings['entry_motion_min_displacement_m'],
                evidence=entry_evidence)
        return state, dict(self.state), observed
