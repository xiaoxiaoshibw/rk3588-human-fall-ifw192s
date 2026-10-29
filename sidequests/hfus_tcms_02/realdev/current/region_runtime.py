"""Shared per-observation orchestration of the existing region/calibration code."""
import numpy as np

from project_dependencies import CalibrationLayer, SK, measurements
from project_regions import estimate


class RegionRuntime:
    def __init__(self, session_id, partition=True, region_contract='target_ground_v1',
                 diagnostic_limit=None):
        self.session_id = session_id
        self.partition = partition
        self.contract = region_contract
        self.limit = diagnostic_limit
        self.binding = None
        self.previous = None
        self.last = None
        self.cal = CalibrationLayer(SK.EDGES)

    def feed(self, points, rows, fi, binding, observed, ground_up):
        reset = not observed or binding != self.binding
        if reset:
            self.previous = self.last = None
            self.cal = CalibrationLayer(SK.EDGES)
        self.binding = binding
        prior = self.previous if self.last is not None and fi == self.last + 1 else None
        sk, _ = estimate(points, rows, coordinate_version='RAW/innolidar',
            session_id=self.session_id, previous_lateral=prior,
            partition_branch=self.partition, region_contract=self.contract, ground_up=ground_up)
        if sk['basis_lateral'] is None:
            if self.previous is not None:
                self.cal = CalibrationLayer(SK.EDGES)
                reset = True
            self.previous = self.last = None
        else:
            self.previous = np.array(sk['basis_lateral'])
            self.last = fi
        cf = self.cal.update(fi, measurements(sk))
        # Gates consume the original 20-sample window. Only optional live audit
        # retention is bounded; offline callers retain the complete diagnostics.
        if self.limit is not None:
            self.cal.frames[:] = self.cal.frames[-1:]
            self.cal.events[:] = self.cal.events[-self.limit:]
            self.cal.drifts[:] = self.cal.drifts[-self.limit:]
            for cal in self.cal.calibrators.values():
                cal.episodes[:] = cal.episodes[-16:]
                cal.post_calibration_values[:] = cal.post_calibration_values[-self.limit:]
                if cal.open_episode is not None:
                    cal.open_episode['values'][:] = cal.open_episode['values'][-self.limit:]
        return sk, cf, reset


class LiveRegions:
    """Transport adapter: consumes the production core's single actual target."""
    def __init__(self):
        self.runtime = None
        self.sequence = 0
        self.latest = None

    def process(self, points, result):
        state = result['state']
        session = state['session_id']
        if self.runtime is None or self.runtime.session_id != session:
            self.runtime = RegionRuntime(session, diagnostic_limit=300)
        self.sequence += 1
        rows = list(state.get('target_source_rows') or [])
        observed = (state['track_status'] == 'locked' and not state['position_predicted']
                    and state['observability'] != 'invalid' and bool(rows))
        if not observed:
            rows = []
        raw = np.asarray(points, dtype=float).reshape(-1, 3) if points is not None else np.empty((0, 3))
        ids = np.asarray(rows, dtype=np.int64)
        if len(ids) and (ids.min() < 0 or ids.max() >= len(raw) or len(set(rows)) != len(rows)):
            raise ValueError('live region rows outside current source')
        binding = (session, state['time_epoch'], state['action_generation'],
                   state['calibration']['calibration_id'])
        normal = (state.get('ground') or {}).get('normal')
        if normal is None:
            # Unavailable ground never reaches the ground-dependent estimator.
            self.latest = None
            self.runtime = None
            return
        sk, cf, reset = self.runtime.feed(raw[ids], rows, self.sequence, binding, observed, normal)
        self.latest = dict(kind='target_regions', schema_version=1, source=state['source'],
            session_id=session, time_epoch=state['time_epoch'],
            action_generation=state['action_generation'], calibration_id=binding[-1],
            coordinate='source', coordinate_alias='RAW/innolidar', source_frame=state['frame_id'],
            target_source_rows=rows, observed=observed, nodes=sk['nodes'], edges=sk.get('edges', []),
            reason=sk['reason'], diagnostics=sk.get('diagnostics'), calibration=cf,
            reset=reset, diagnostic_window_observations=300, semantic='UNKNOWN')

    def state(self, payload):
        state = dict(payload)
        if state.get('observability') == 'invalid':
            self.runtime = self.latest = None
        r = self.latest
        eligible = (r is not None and r['observed'] and state.get('observability') != 'invalid'
                    and state.get('track_status') == 'locked' and not state.get('position_predicted')
                    and state.get('source') == r['source'] and state['session_id'] == r['session_id']
                    and state['time_epoch'] == r['time_epoch']
                    and state['action_generation'] == r['action_generation']
                    and state['calibration']['calibration_id'] == r['calibration_id']
                    and state['frame_id'] == r['source_frame']
                    and state.get('target_source_rows') == r['target_source_rows'])
        state['regions'] = r if eligible else dict(kind='target_regions', schema_version=1,
            observed=False, nodes={}, edges=[], reason='NO_CURRENT_MEASURED_TARGET', semantic='UNKNOWN')
        return state
