"""逐帧运行时；无ROS、无拟合、默认不读未来帧。

唯一的非因果例外：构造时显式安装的离线整段背景（``background=``，必须
``non_causal=True``+声明+绑定匹配，见 ``core/range_offline.py``）。在线链只
用空场前缀，两者的检测/跟踪/特征/状态机是同一份代码。
"""
import hashlib
import json
import time

import numpy as np

from .baseline import StanceBaselineCollector, resolve_settings as resolve_baseline_settings, DEFAULT_SETTINGS as BASELINE_SETTINGS
from .features import FeatureExtractor, DEFAULT_SETTINGS as FEATURE_SETTINGS
from .fall_state import FallStateMachine, DEFAULT_SETTINGS as FALL_SETTINGS
from .lidar_candidates import rebuild_candidate
from .range_background import RayBackground
from .range_components import label_components
from .range_contract import binding_tuple
from .range_denoise import denoise
from .range_features import bound_ground
from .range_posture import PostureObserver, SETTINGS as POSTURE_SETTINGS
from .range_tracker import INFERENCE_KEYS, RangeTracker, SETTINGS
from .human_prior import DEFAULT_SETTINGS as HUMAN_PRIOR_SETTINGS
from .candidate_history import ground_version
from .range_ground_alert import SETTINGS as ALERT_SETTINGS
from .range_demo_alert import SETTINGS as DEMO_ALERT_SETTINGS


class SettingsDriftError(ValueError):
    pass


def serial(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


class RangeRuntime:
    def __init__(self, grid, identity, *, empty_prefix_frames, ground=None, ground_sha=None,
                 detailed=True, background=None):
        self.grid, self.identity = grid, dict(identity)
        self.binding = binding_tuple(identity)
        self.background_non_causal = background is not None
        if background is not None:
            # 只有显式声明非因果的离线输入模型能替换空场前缀；两者不能同时给。
            if empty_prefix_frames is not None:
                raise ValueError('installed background replaces the empty prefix; pass one or the other')
            if (getattr(background, 'non_causal', None) is not True
                    or not getattr(background, 'declaration', None)):
                raise ValueError('installed background must be an explicit non-causal offline model')
            if (getattr(background, 'binding', None), getattr(background, 'grid_sha256', None)) != (self.binding, grid.sha256):
                raise ValueError('installed background binding mismatch')
        elif type(empty_prefix_frames) is not int or empty_prefix_frames < 1:
            raise ValueError('explicit positive empty prefix required')
        self.ground, self.ground_sha = ground, ground_sha
        self.detailed = bool(detailed)
        self.prefix_size = 0 if background is not None else empty_prefix_frames
        self.prefix, self.background = [], background
        self.background_disabled = False
        self.last_time = None
        self.last_frame_index = None
        self.tracker = RangeTracker()
        self.features = FeatureExtractor(identity['session'])
        self.state = FallStateMachine(identity['session'], dict(mode_verified=False, allow_confirmed=False))
        self.posture = PostureObserver()
        self.baseline_collector = StanceBaselineCollector(identity['session'])
        self.config = dict(frontend='range_v1', empty_prefix_frames=empty_prefix_frames,
            tracker=dict(SETTINGS), ground_sha256=ground_sha, background_update=False,
            min_neighbours=2, min_component_points=15, merge=False,
            fall=dict(self.state.settings), posture=dict(POSTURE_SETTINGS),
            human_prior=dict(HUMAN_PRIOR_SETTINGS),
            baseline=dict(mode='automatic_stance', settings=resolve_baseline_settings(None)),
            feature_defaults=dict(FEATURE_SETTINGS), fall_defaults=dict(FALL_SETTINGS),
            ground_alert=dict(ALERT_SETTINGS), demo_alert=dict(DEMO_ALERT_SETTINGS))
        if background is not None:
            self.config.update(background_source=background.declaration, background_non_causal=True)
        self.config_sha = hashlib.sha256(serial(self.config).encode()).hexdigest()

    def rules(self, frame, record, costs, ground=...):
        if self.features.session_id != self.identity['session']:
            self.features = FeatureExtractor(self.identity['session'])
            self.state = FallStateMachine(self.identity['session'],dict(mode_verified=False,allow_confirmed=False))
            self.posture = PostureObserver()
            self.baseline_collector = StanceBaselineCollector(self.identity['session'])
        rows = record['target_source_rows']
        plane = bound_ground(frame, self.ground if ground is ... else ground)
        start = time.perf_counter()
        candidate = None
        if rows:
            xyz = frame.xyz[rows].astype(float)
            candidate = rebuild_candidate(xyz, np.arange(len(rows)), ground=plane,
                frame_id=plane['frame'] if plane else 'unbound')
        costs['rule_geometry_ms'] = (time.perf_counter()-start)*1000
        track_id = record['target_track_id'] or record.get('continuity_track_id')
        observation = dict(session_id=self.identity['session'],
            track_id=track_id,
            time_epoch=record['generation'], action_generation=record['generation'],
            selection_version=record['generation'], calibration_version=self.ground_sha or 'ground_unavailable',
            source_stamp_s=record['time_s'],
            # 'held' is a measured gap of the same target, not a released target;
            # the fall machine keeps the episode across it.
            track_status=('locked' if rows else 'held' if track_id else
                          'ambiguous' if record.get('target_reason') in
                          ('selected_target_ambiguous', 'single_person_selection_ambiguous') else 'unselected'),
            position_predicted=False, candidate=candidate,
            ground_relative_available=plane is not None)
        start = time.perf_counter()
        if plane is None:
            # A ready ground-relative baseline is a measurement too: settle it the
            # moment the ground context fails, exactly like the live ROS node.
            if self.baseline_collector.status in ('pending', 'ready'):
                self.baseline_collector.invalidate('ground_monitor_unavailable')
            snapshot = self.baseline_collector.snapshot()
        else:
            track = dict(track_id=track_id, time_epoch=record['generation'],
                selection_version=record['generation'], action_generation=record['generation'],
                calibration_version=observation['calibration_version'],
                track_status=observation['track_status'], position_predicted=False)
            snapshot = self.baseline_collector.feed_automatic(candidate, track, record['time_s'])
        baseline = snapshot['baseline']
        costs['baseline_ms'] = (time.perf_counter()-start)*1000
        start = time.perf_counter()
        features = self.features.update(observation, baseline=baseline)
        costs['temporal_features_ms'] = (time.perf_counter()-start)*1000
        start = time.perf_counter()
        posture = self.posture.update(features, record, frame.binding)
        state = self.state.update(features, observation, baseline=baseline, posture=posture)
        costs['rules_ms'] = (time.perf_counter()-start)*1000
        if state['confirmed_enabled'] or state['new_event'] is not None:
            raise ValueError('confirmed/event forbidden in offline runtime')
        return dict(frame=record['frame'], time_s=record['time_s'], track_id=record['target_track_id'],
            source_rows=list(rows), input_inference_sha256=record['inference_sha256'],
            features=features, state=state, posture=posture, baseline=snapshot, semantic='UNKNOWN')

    def update(self, packed, stamp_s, frame_index, *, identity=None, grid=None, ground_validator=None):
        """只消费当前packed；背景只能由连续、显式声明的起始前缀建立。"""
        for name, current, saved in (
                ('tracker', SETTINGS, self.config['tracker']),
                ('human prior', HUMAN_PRIOR_SETTINGS, self.config['human_prior']),
                ('posture', POSTURE_SETTINGS, self.config['posture']),
                ('baseline', BASELINE_SETTINGS, self.config['baseline']['settings']),
                ('feature', FEATURE_SETTINGS, self.config['feature_defaults']),
                ('fall', FALL_SETTINGS, self.config['fall_defaults']),
                ('ground alert', ALERT_SETTINGS, self.config['ground_alert']),
                ('demo alert', DEMO_ALERT_SETTINGS, self.config['demo_alert'])):
            if current != saved:
                raise SettingsDriftError(name + ' settings changed; create a new runtime')
        started = time.perf_counter()
        if not np.isfinite(stamp_s):
            self.background, self.prefix, self.last_time = None, [], None
            self.background_disabled = True
            self.features = FeatureExtractor(self.identity['session'])
            self.state = FallStateMachine(self.identity['session'], dict(mode_verified=False,allow_confirmed=False))
            self.posture = PostureObserver()
            self.tracker.update(None, None, None, stamp_s, frame_index)
        costs = {}
        skipped = max(0,frame_index-self.last_frame_index-1) if self.last_frame_index is not None else 0
        if skipped:
            # 队列覆盖是显式缺测；沿用现有观测缺口机制，不伪造中间帧。
            self.features._note_gap()
        self.last_frame_index = frame_index
        identity = self.identity if identity is None else dict(identity)
        grid = self.grid if grid is None else grid
        binding = binding_tuple(identity)
        changed = binding != self.binding or grid.sha256 != self.grid.sha256
        discontinuity = self.last_time is not None and (stamp_s <= self.last_time or stamp_s-self.last_time > SETTINGS['reset_gap_s'])
        if changed or (discontinuity and not self.background_non_causal):
            # 不把换来源后的任意帧冒称空场；重新构建须创建新的显式会话。
            # 已声明绑定的离线整段背景不因时间跳变被当成“空场重学”。
            self.background, self.prefix = None, []
            self.background_disabled = True
        self.grid, self.identity, self.binding = grid, identity, binding
        self.last_time = stamp_s
        frame = grid.decode(packed, binding, timings=costs if self.detailed else None)
        decoded = time.perf_counter()
        # 同帧地面质量门复用唯一decode；无回调时保持已有回放/生产语义。
        effective_ground = self.ground if ground_validator is None else ground_validator(frame,self.ground)
        monitored = time.perf_counter()
        costs['ground_monitor_ms'] = (monitored-decoded)*1000
        if self.background_disabled:
            mask = np.zeros(grid.shape, dtype=bool)
            status = 'background_requires_explicit_rebind'
        elif self.background is None:
            if frame_index != len(self.prefix):
                self.background_disabled = True
                self.prefix.clear()
            else:
                self.prefix.append(frame)
            mask = np.zeros(grid.shape, dtype=bool)
            status = 'background_requires_explicit_rebind' if self.background_disabled else 'prefix_warmup'
        else:
            result = self.background.foreground(frame)
            mask, status = result['mask'], result['status']
            with np.errstate(invalid='ignore'):
                mask &= (frame.range_m >= .1) & (frame.range_m <= 8)
        background_done = time.perf_counter()
        cleaned = denoise(frame, mask)
        denoised = time.perf_counter()
        labels, components = label_components(frame, cleaned['mask'], timings=costs if self.detailed else None)
        costs.setdefault('source_lift_ms', 0.)
        front_done = time.perf_counter()
        detail = {}
        record = self.tracker.update(frame, labels, components, stamp_s, frame_index,
            ground=effective_ground, timings=detail,
            ground_binding=ground_version(bound_ground(frame,self.ground)))
        tracked = time.perf_counter()
        record['inference_sha256'] = hashlib.sha256(serial(
            {k: record[k] for k in INFERENCE_KEYS if k in record}).encode()).hexdigest()
        costs['inference_binding_json_ms'] = (time.perf_counter()-tracked)*1000
        rule = self.rules(frame, record, costs, ground=effective_ground)
        ruled = time.perf_counter()
        init_start = time.perf_counter()
        if not self.background_disabled and self.prefix_size and len(self.prefix) == self.prefix_size:
            self.background = RayBackground(self.prefix, empty_prefix_declared=True,
                min_observations=min(10, self.prefix_size))
            self.prefix.clear()
        costs.update(decode_ms=(decoded-started)*1000, background_ms=(background_done-monitored)*1000,
            denoise_ms=(denoised-background_done)*1000, components_ms=(front_done-denoised)*1000,
            frontend_ms=(front_done-started)*1000, tracking_ms=(tracked-front_done)*1000,
            features_ms=detail['features_ms'], algorithm_ms=(tracked-started)*1000,
            event_chain_ms=(ruled-started)*1000, background_init_ms=(time.perf_counter()-init_start)*1000)
        return dict(tracking=record, rule=rule, status=status, source_binding=identity,
            config_sha256=self.config_sha, skipped_input_frames=skipped, timings=costs), frame, components
