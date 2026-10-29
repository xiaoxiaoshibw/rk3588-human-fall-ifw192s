"""同一实测目标的几何姿态状态机；不是人体分类器或跌倒事件。

输入只有已算好的时序特征块（``core.features``）：地面系顶部高度、竖直跨度、
水平跨度、PCA 垂直度、点数与可观测性。输出是**几何姿态**：

``unknown`` / ``standing`` / ``sitting`` / ``transitioning`` /
``vertical_surface`` / ``lying_pending`` / ``lying_candidate``

语义边界：

* 姿态来自"这一次实测的点云表面"，不是人体身份、不是跌倒真值；
  ``humanSemantic`` 恒为 ``UNKNOWN``，``fallEvent`` 恒为 ``False``。
* ``lying_candidate`` 只表示"持续 min_duration_s 的贴地水平几何"；主动躺卧、
  坐在地上、被家具挡住的低姿态都可能得到同一几何（已在 fall_state 的
  limitations 里报告，不在这里隐藏）。
* 短暂不可评估（缺地面/轴退化/预测帧/跳帧）不会伪造姿态转移：驻留计时清零。
* 站/坐/躺之间需要 ``dwell_s`` 的连续证据才切换，期间输出 ``transitioning``；
  这是姿态层的迟滞，不是跌倒判据。
"""
import math

from .fall_state import DEFAULT_SETTINGS

SETTINGS = dict(
    max_top_m=DEFAULT_SETTINGS['lying_max_top_m'],
    min_extent_m=DEFAULT_SETTINGS['lying_min_extent_m'],
    min_duration_s=DEFAULT_SETTINGS['low_min_duration_s'],
    max_verticality=.5, min_points=15, max_gap_s=.3,
    # 站立/坐姿的几何门；与 human_prior 的相容集合保持同一量纲（竖直跨度用
    # p90-p10，水平跨度用候选的 horizontal_extent_m）。
    standing_top_min_m=1.05, standing_span_min_m=.60, standing_verticality_min_m=.80,
    standing_bottom_max_m=1.00,
    sitting_top_min_m=.55, sitting_span_min_m=.35, sitting_horizontal_max_m=1.10,
    sitting_bottom_max_m=.70,
    dwell_s=.20,
)

STATES = ('unknown', 'standing', 'sitting', 'transitioning', 'vertical_surface',
          'lying_pending', 'lying_candidate')
LYING_STATES = ('lying_pending', 'lying_candidate')


def resolve_settings(settings=None):
    resolved = dict(SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError('unknown posture setting: ' + str(key))
        resolved[key] = value
    for key in resolved:
        resolved[key] = float(resolved[key])
        if not math.isfinite(resolved[key]) or resolved[key] < 0.0:
            raise ValueError(key + ' must be a finite non-negative number')
    if resolved['min_points'] < 1:
        raise ValueError('min_points must be positive')
    return resolved


def _instant(features, settings):
    """单帧几何姿态；不可评估返回 None。"""
    height_block = features.get('height_m') or {}
    top = height_block.get('max')
    p10, p90 = height_block.get('p10'), height_block.get('p90')
    bottom = height_block.get('min')
    extent = features.get('horizontal_extent_m')
    axis = features.get('axis_verticality')
    values = (top, extent, axis)
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        return None
    span = None
    if isinstance(p10, (int, float)) and isinstance(p90, (int, float)) \
            and math.isfinite(p10) and math.isfinite(p90):
        span = float(p90) - float(p10)
    if 0 <= top <= settings['max_top_m'] and extent >= settings['min_extent_m'] \
            and 0 <= axis <= settings['max_verticality']:
        return 'lying'
    if top >= settings['standing_top_min_m'] and span is not None \
            and span >= settings['standing_span_min_m'] \
            and axis >= settings['standing_verticality_min_m'] \
            and (bottom is None or bottom <= settings['standing_bottom_max_m']):
        return 'standing'
    if settings['sitting_top_min_m'] <= top < settings['standing_top_min_m'] \
            and span is not None and span >= settings['sitting_span_min_m'] \
            and extent <= settings['sitting_horizontal_max_m'] \
            and (bottom is None or bottom <= settings['sitting_bottom_max_m']):
        return 'sitting'
    if axis >= .8:
        return 'vertical_surface'
    return 'unknown'


class PostureObserver:
    def __init__(self, settings=None):
        self.settings = resolve_settings(settings)
        self.key = self.last_frame = self.last_time = None
        self.since = None
        self.current = None
        self.current_since = None
        self.pending = None

    def _restart(self):
        self.since = None
        self.current = None
        self.current_since = None
        self.pending = None

    def update(self, features, record, binding):
        key = (tuple(binding), record['generation'], record['target_track_id'])
        index, now = record['frame'], record['time_s']
        valid_time = isinstance(now, (float, int)) and math.isfinite(now)
        continuous = (key == self.key and self.last_frame is not None
                      and index == self.last_frame + 1 and valid_time
                      and self.last_time is not None
                      and 0 < now-self.last_time <= self.settings['max_gap_s']+1e-9
                      and not features.get('observation_gap') and not features.get('reset_now'))
        if not continuous:
            self._restart()
        self.key, self.last_frame = key, index
        self.last_time = now if valid_time else None
        result = dict(state='unknown', reason='measurement_or_ground_unavailable',
                      durationSec=0., stable=None, humanSemantic='UNKNOWN', fallEvent=False)
        top = (features.get('height_m') or {}).get('max')
        extent, axis = features.get('horizontal_extent_m'), features.get('axis_verticality')
        valid = (valid_time and features.get('observable') and features.get('ground_relative')
                 and record['target_track_id'] is not None and bool(record['target_source_rows'])
                 and not features.get('axis_ambiguous', True)
                 and (features.get('point_count') or 0) >= self.settings['min_points']
                 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in (top, extent, axis)))
        if not valid:
            self._restart()
            return result
        instant = _instant(features, self.settings)
        if instant is None:
            self._restart()
            result['reason'] = 'posture_not_evaluable'
            return result
        if instant == 'lying':
            if self.since is None:
                self.since = now
            duration = now-self.since
            candidate = duration+1e-9 >= self.settings['min_duration_s']
            result.update(state='lying_candidate' if candidate else 'lying_pending',
                          reason='sustained_low_horizontal_geometry' if candidate
                          else 'lying_duration_pending',
                          durationSec=duration, stable='lying')
            self.current, self.current_since, self.pending = 'lying', self.since, None
            return result
        self.since = None
        if instant == 'unknown':
            self._restart()
            result.update(reason='posture_not_evaluable')
            return result
        if self.current is None:
            self.current, self.current_since, self.pending = instant, now, None
            result.update(state=instant, reason='posture_'+instant, stable=instant)
            return result
        if instant == self.current:
            self.pending = None
            result.update(state=instant, reason='sustained_'+instant, stable=instant)
            return result
        if self.pending is None or self.pending[0] != instant:
            self.pending = (instant, now)
        if now-self.pending[1]+1e-9 >= self.settings['dwell_s']:
            self.current, self.current_since, self.pending = instant, now, None
            result.update(state=instant, reason='posture_transition', stable=instant)
            return result
        result.update(state='transitioning', reason='posture_transition_pending',
                      stable=self.current)
        return result