"""因果W2实验：射线/运动补偿空间支撑；行号绝不作跨帧身份。"""
import math
import time

import numpy as np

from .candidate_history import ground_version
from .human_prior import CLASS_FRAGMENT, choose_single, describe, quick_screen
from .range_features import measured_features, bound_ground
from .lidar_candidates import ground_plane_basis
from .support_composition import support_cells, evaluate


# Stable inference ledger field set shared by producers and readers.
INFERENCE_KEYS = ('frame', 'time_s', 'generation', 'reset_reason', 'tracks', 'target_track_id',
    'target_source_rows', 'target_features', 'target_reason', 'association_edges', 'compositions',
    'ambiguous_component_ids', 'expired_track_ids', 'semantic', 'continuity_track_id')


SETTINGS = dict(birth_observations=3, miss_timeout_s=1.5, reset_gap_s=2.0,
                gate_m=.5, max_speed_m_s=2.5, ambiguity_margin_m=.2,
                # A standing body that lies down legitimately drops its visible
                # point count by ~3.3x; 3.0 broke association exactly at the fall
                # and rebirthed the target (measured: 1615 -> 492 points).
                max_point_ratio=4., min_support_fraction=.05, support_cell_m=.1,
                composition='existing_support_composition_defaults',
                # 单人几何相容性：默认只做影子计算（附加字段，不改变选择）；
                # 锁定策略与碎片预筛需要显式开启，便于同输入 A/B 对照。
                human_prior_enabled=True, single_person_lock=False,
                drop_fragment_candidates=False,
                # 锁定策略的去抖：单帧不相容不等于释放，新目标要连续成为最优
                # 才能替换仍在实测的旧目标（否则一次分类抖动会清空跌倒证据）。
                release_hold_s=.5, switch_hold_s=.5)


class RangeTracker:
    def __init__(self):
        self.tracks = {}
        self.generation = 0
        self.next_id = 1
        self.stamp = None
        self.frame_index = None
        self.binding = None
        self.selected = None
        self.dropped_fragments = []
        self.reject_since = None
        self.pending = None
        self.released = None

    def _candidates(self, frame, labels, components, ground=None):
        result = {}
        dropped = []
        for component in components:
            if not component['retained']:
                continue
            cid = component['component_id']
            rows = np.asarray(component['source_rows'], dtype=np.int64)
            cells = np.flatnonzero(labels.ravel() == cid)
            if not np.array_equal(np.sort(frame.source_rows.ravel()[cells]), rows):
                raise ValueError('component labels/source measurement mismatch')
            xyz = frame.xyz[rows].astype(float)
            if SETTINGS['drop_fragment_candidates'] and ground is not None:
                quick = quick_screen(xyz, ground)
                if quick['class'] == CLASS_FRAGMENT:
                    dropped.append(dict(component_id=cid, points=len(rows),
                                        reason=quick['reason']))
                    continue
            result[cid] = dict(rows=rows, xyz=xyz, center=np.median(xyz, axis=0),
                rays=set(cells.tolist()), space=support_cells(xyz), component_ids=[cid])
        self.dropped_fragments = dropped
        return result

    def _locked_choice(self, available, policy, stamp_s):
        """单人锁定选择 + 释放/切换去抖；返回 (chosen, reason)。

        ``release_hold_s``：当前目标被策略拒绝时先保留（仍实测），超过去抖
        窗口才真正释放；``switch_hold_s``：新目标必须连续这么久是最优，才
        替换仍在实测的旧目标。这样单帧分类抖动/短暂遮挡不会清空跌倒证据。
        """
        previous = self.selected
        if policy.get('ambiguous'):
            self.reject_since = self.pending = None
            return None, 'single_person_selection_ambiguous'
        held = None
        if previous is not None:
            held = next((r for r in available if r['track_id'] == previous), None)
        picked = next((r for r in available if r['track_id'] == policy['chosen_track_id']), None)
        if picked is not None:
            self.reject_since = None
            if picked['track_id'] == self.released:
                self.released = None
            if previous is not None and picked['track_id'] != previous and held is not None:
                if self.pending is None or self.pending[0] != picked['track_id']:
                    self.pending = (picked['track_id'], stamp_s)
                if stamp_s - self.pending[1] < SETTINGS['switch_hold_s']:
                    return held, 'previous_target_retained_pending_switch'
            self.pending = None
            return picked, None
        self.pending = None
        if previous is not None and held is not None:
            if self.reject_since is None:
                self.reject_since = stamp_s
            if stamp_s - self.reject_since <= SETTINGS['release_hold_s']:
                return held, 'target_held_unverified'
            self.released = previous
            return None, 'target_released_unverified'
        if policy['compatible_count'] == 0:
            return None, 'no_human_compatible_target'
        return None, 'human_compatible_target_not_stable'

    def update(self, frame, labels, components, stamp_s, frame_index, ground=None, timings=None,
               ground_binding=...):
        if not math.isfinite(stamp_s):
            self.tracks.clear()
            self.stamp = None
            self.selected = None
            self.reject_since = None
            self.pending = None
            self.released = None
            self.binding = None
            self.generation += 1
            raise ValueError('finite source header time required')
        plane=bound_ground(frame,ground)
        # RAW identity survives temporary floor occlusion. The installed plane
        # still binds the track; only this frame's height/composition uses plane.
        binding = (frame.binding, frame.grid.sha256,
                   ground_version(plane) if ground_binding is ... else ground_binding)
        reset = None
        if self.stamp is not None:
            if binding != self.binding:
                reset = 'binding_changed'
            elif stamp_s <= self.stamp or frame_index <= self.frame_index:
                reset = 'nonincreasing_clock_or_frame'
            elif stamp_s-self.stamp > SETTINGS['reset_gap_s']:
                reset = 'stream_gap'
        if reset:
            self.tracks.clear()
            self.selected = None
            self.reject_since = None
            self.pending = None
            self.released = None
            self.generation += 1
        self.binding, self.stamp, self.frame_index = binding, stamp_s, frame_index
        candidates = self._candidates(frame, labels, components, plane)
        expired = []
        for tid, track in list(self.tracks.items()):
            if stamp_s-track['last_observed'] > SETTINGS['miss_timeout_s']:
                expired.append(tid)
                del self.tracks[tid]
        edges, predictions, gates, shifted_points, plausible = {}, {}, {}, {}, {}
        for tid, track in sorted(self.tracks.items()):
            dt = stamp_s-track['last_observed']
            prediction = track['center'].copy()
            prediction[:2] += track['velocity']*dt
            predictions[tid] = prediction
            gates[tid] = SETTINGS['gate_m']+SETTINGS['max_speed_m_s']*dt
            shifted = track['prior_xyz']+(prediction-track['center'])
            shifted_points[tid] = shifted
            space = support_cells(shifted)
            eligible = []
            geometric = []
            for cid, candidate in sorted(candidates.items()):
                distance = float(np.linalg.norm(prediction-candidate['center']))
                ratio = max(len(candidate['rows']), track['points']) / min(len(candidate['rows']), track['points'])
                ray_fraction = len(candidate['rays'] & track['rays']) / max(1,len(candidate['rays']))
                spatial_fraction = len(candidate['space'] & space) / max(1,len(candidate['space']))
                if distance <= gates[tid] and ratio <= SETTINGS['max_point_ratio']:
                    geometric.append((distance,cid))
                supported_fragment = (ray_fraction >= SETTINGS['min_support_fraction']
                                      and spatial_fraction >= SETTINGS['min_support_fraction'])
                if ((distance <= gates[tid] or supported_fragment)
                        and len(candidate['rows']) <= SETTINGS['max_point_ratio']*track['points']
                        and max(ray_fraction,spatial_fraction) >= SETTINGS['min_support_fraction']):
                    eligible.append(dict(cid=cid,distance_m=distance,ray_support=ray_fraction,
                                         motion_compensated_space_support=spatial_fraction,
                                         ordinary_size_consistent=ratio <= SETTINGS['max_point_ratio'] and distance <= gates[tid]))
            edges[tid] = sorted(eligible,key=lambda e:(e['distance_m'],e['cid']))
            plausible[tid] = sorted(geometric)
        blocked_tracks, blocked_components = set(), set()
        # 射线支撑不是身份：无支撑但几何上同样合理的竞争者不能被静默排除。
        geometric_owners = {}
        for tid, items in plausible.items():
            if not items:
                continue
            geometric_owners.setdefault(items[0][1],[]).append(tid)
        for cid, tids in geometric_owners.items():
            if len(tids)>1:
                blocked_tracks.update(tids)
                blocked_components.add(cid)
        proposals, compositions = {}, []
        for tid, eligible in sorted(edges.items()):
            if tid in blocked_tracks:
                blocked_components.update(e['cid'] for e in eligible)
                continue
            if not eligible:
                if plausible[tid]:
                    blocked_tracks.add(tid)
                    blocked_components.update(cid for _,cid in plausible[tid])
                continue
            ids = [e['cid'] for e in eligible]
            if len(ids) > 1:
                competing = any(set(ids) & {e['cid'] for e in other} for t,other in edges.items() if t != tid)
                report = dict(accepted=False,reason='competing_track_support',metrics={})
                if not competing:
                    fragments = [dict(candidate_id=cid,points=candidates[cid]['xyz'],cells=candidates[cid]['space']) for cid in ids]
                    report = evaluate(shifted_points[tid], support_cells(shifted_points[tid]), fragments,
                        predicted_position=predictions[tid],gate_m=gates[tid],
                        ground_basis=ground_plane_basis(plane),
                        ground_offset_m=plane['offset_m'] if plane else None,
                        competitor_positions=[p for t,p in predictions.items() if t != tid])
                compositions.append(dict(track_id=tid,component_ids=ids,**report))
                if report['accepted']:
                    outsiders=[cid for _,cid in plausible[tid] if cid not in ids]
                    if outsiders:
                        report['accepted']=False
                        report['reason']='unbound_geometric_competitor'
                        compositions[-1].update(report)
                        blocked_tracks.add(tid)
                        blocked_components.update(ids+outsiders)
                    else:
                        proposals[tid] = ids
                    continue
                ordinary = [e for e in eligible if e['ordinary_size_consistent']]
                if len(ordinary)>1 and ordinary[1]['distance_m']-ordinary[0]['distance_m'] < SETTINGS['ambiguity_margin_m']:
                    blocked_tracks.add(tid)
                    blocked_components.update(ids)
                    continue
            items=plausible[tid]
            if (len(items)>1 and items[1][0]-items[0][0] < SETTINGS['ambiguity_margin_m']):
                blocked_tracks.add(tid)
                blocked_components.update(cid for _,cid in items)
                continue
            ordinary = [e for e in eligible if e['ordinary_size_consistent']]
            if ordinary:
                proposals[tid] = [ordinary[0]['cid']]
        # 歧义候选不能被另一轨取得，也不能新生为确定轨。
        owners = {}
        for tid, ids in proposals.items():
            for cid in ids:
                owners.setdefault(cid, []).append(tid)
        for cid,tids in owners.items():
            if len(tids)>1 or cid in blocked_components:
                blocked_tracks.update(tids)
                blocked_components.add(cid)
        while True:
            before = (len(blocked_tracks),len(blocked_components))
            for tid, ids in proposals.items():
                if tid in blocked_tracks or set(ids)&blocked_components:
                    blocked_tracks.add(tid)
                    blocked_components.update(ids)
            if before == (len(blocked_tracks),len(blocked_components)):
                break
        matches = {tid:ids for tid,ids in proposals.items()
                   if tid not in blocked_tracks and not (set(ids)&blocked_components)}
        used = {cid for ids in matches.values() for cid in ids}
        for cid in sorted(set(candidates)-used-blocked_components):
            tid = 'g%d_t%04d'%(self.generation,self.next_id)
            self.next_id += 1
            self.tracks[tid] = dict(streak=0,stable=False,velocity=np.zeros(2),last_observed=stamp_s)
            matches[tid] = [cid]
        output, feature_ms = [], 0.
        for tid,track in sorted(self.tracks.items()):
            ids = matches.get(tid)
            if ids is None:
                track['streak'] = 0
                position = predictions[tid]
                output.append(dict(track_id=tid,status='ambiguous' if tid in blocked_tracks else 'predicted',
                    observed=False,position_predicted=True,position_m=position.tolist(),
                    state_xy_vxy=[*position[:2].tolist(),*track['velocity'].tolist()],
                    source_rows=[],component_ids=[],features=None,velocity_m_s=None,
                    reason='association_ambiguous' if tid in blocked_tracks else 'no_current_measurement'))
                continue
            rows = np.sort(np.concatenate([candidates[cid]['rows'] for cid in ids]))
            xyz = frame.xyz[rows].astype(float)
            center = np.median(xyz,axis=0)
            dt = stamp_s-track['last_observed']
            velocity = (center[:2]-track['center'][:2])/dt if 'center' in track and dt>0 and track['streak']>0 else None
            track['streak'] += 1
            track['stable'] |= track['streak'] >= SETTINGS['birth_observations']
            track.update(center=center,velocity=np.zeros(2) if velocity is None else velocity,
                last_observed=stamp_s,points=len(rows),rays=set().union(*(candidates[cid]['rays'] for cid in ids)),
                prior_xyz=xyz)
            started = time.perf_counter()
            features = measured_features(frame,rows,ground)
            feature_ms += (time.perf_counter()-started)*1000
            output.append(dict(track_id=tid,status='tracked' if track['stable'] else 'tentative',
                observed=True,position_predicted=False,position_m=center.tolist(),
                state_xy_vxy=[*center[:2].tolist(),*track['velocity'].tolist()],
                source_rows=rows.tolist(),component_ids=ids,features=features,
                velocity_m_s=None if velocity is None else velocity.tolist(),
                velocity_reason='birth_or_measurement_gap' if velocity is None else None,
                selection_score=math.log1p(len(rows))/max(.5,float(np.linalg.norm(center))),semantic='unknown'))
        available = [r for r in output if r['status']=='tracked' and r['observed']]
        available.sort(key=lambda r:(-r['selection_score'],r['track_id']))
        prior_entries = []
        if SETTINGS['human_prior_enabled']:
            # 影子：给每条实测轨迹附几何相容性；只有显式开启才用它改变选择。
            for entry in output:
                if not entry['observed'] or not entry['source_rows']:
                    continue
                try:
                    prior = describe(frame, entry['source_rows'], plane)
                except ValueError:
                    continue
                entry['human_prior'] = dict(**{'class': prior['class']},
                    compatible=prior['compatible'], posture=prior['posture'],
                    reason=prior['reason'], available=prior['available'],
                    semantic='UNKNOWN')
                if entry['status'] == 'tracked':
                    prior_entries.append(dict(track_id=entry['track_id'],
                        compatible=prior['compatible'], score=entry['selection_score'],
                        point_count=len(entry['source_rows']), **{'class': prior['class']}))
        policy = choose_single(prior_entries, previous_track_id=self.selected) \
            if SETTINGS['human_prior_enabled'] else None
        chosen = next((r for r in available if r['track_id']==self.selected),None)
        reason = 'no_stable_current_measurement'
        previous = self.selected
        may_resume = (previous is not None and previous != self.released
                      and previous in self.tracks and previous not in blocked_tracks
                      and stamp_s-self.tracks[previous]['last_observed'] <= .3+1e-9)
        if previous in blocked_tracks and not available:
            chosen, reason = None, 'selected_target_ambiguous'
            may_resume = False
        elif SETTINGS['single_person_lock'] and policy is not None:
            # 单人策略 + 释放/切换去抖：单帧不相容不等于释放，新目标要连续
            # 成为最优才能替换仍在实测的旧目标，否则一次分类抖动就会清空跌倒证据。
            chosen, reason = self._locked_choice(available, policy, stamp_s)
            if policy['ambiguous']:
                may_resume = False
        elif chosen is None and may_resume and available:
            reason = 'target_temporarily_unmeasured'
        elif chosen is None and available:
            if len(available)>1 and available[1]['selection_score'] >= .9*available[0]['selection_score']:
                reason='competing_target_scores'
            else:
                chosen=available[0]
        # 短缺测只保留唯一同轨的选择偏好，不发布旧框/旧点或给缺测累计证据。
        self.selected = chosen['track_id'] if chosen else previous if may_resume else None
        continuity = self.selected if chosen is None and may_resume else None
        if timings is not None:
            timings['features_ms'] = feature_ms
        return dict(frame=frame_index,time_s=stamp_s,generation=self.generation,reset_reason=reset,
            tracks=output,target_track_id=chosen['track_id'] if chosen else None,
            continuity_track_id=continuity,target_source_rows=chosen['source_rows'] if chosen else [],
            target_features=chosen['features'] if chosen else None,target_reason=None if chosen else reason,
            single_person_policy=policy,dropped_fragments=self.dropped_fragments,
            association_edges={tid:items for tid,items in edges.items()},compositions=compositions,
            ambiguous_component_ids=sorted(blocked_components),expired_track_ids=expired,semantic='unknown')
