"""地面相对"持续低姿态"报警旁路（命名变体 ground_alert_v1）。

只回答一个问题：目标是否**持续处于地面高度**。它用于"先能报出来"的最小可用
报警，允许把倒地 / 坐地 / 蹲伏都算作同一件事。

它不是跌倒识别：
  * 不含下降速度门（`descending_min_rate_m_s` / `descending_min_drop_m`）；
  * 不含躺倒几何门（`lying_min_extent_m` / `lying_max_top_m`）；
  * 不产生 confirmed（`confirmed_enabled` 恒为 False），输出只是"疑似"；
  * 不改生产默认、不改冻结配置、不写 analysis。

两个阈值原样引用 `core.fall_state.DEFAULT_SETTINGS` 里的既有值，本模块没有新增
任何数值：
  low_height_m        0.7   规则层同一个"低"的米制高度
  low_min_duration_s  1.5   规则层同一个持续时间门

持续时间语义与 `FallStateMachine` 一致：从首个低姿态帧起算，逐帧取源时间差；
中间任何一帧"没有可信实测"就结束当前段，不做跨段拼接。
"""
import math

from .fall_state import DEFAULT_SETTINGS
from .range_posture import SETTINGS as POSTURE_SETTINGS

VARIANT = 'ground_alert_v1'

SETTINGS = dict(
    low_height_m=DEFAULT_SETTINGS['low_height_m'],
    min_duration_s=DEFAULT_SETTINGS['low_min_duration_s'],
)

REASON_CODES = ('sustained_low_posture', 'no_descent_required', 'no_lying_support_required')

LIMITATIONS = (
    'not_fall_detection: sustained low posture only',
    'squat_or_sitting_also_alarms',
    'no_human_ground_truth',
    'output_is_suspected_only',
)

SEMANTIC = 'UNKNOWN'

_STATE_LOW = 'low'
_STATE_UPRIGHT = 'upright'
_STATE_UNAVAILABLE = 'unavailable'


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def classify(record, settings=None):
    """逐帧三分类：low / upright / unavailable（不可信实测一律 unavailable）。"""
    resolved = dict(SETTINGS)
    if settings:
        resolved.update(settings)
    height = _finite(record.get('heightMedianM'))
    usable = (bool(record.get('measured'))
              and record.get('trackId') is not None
              and height is not None)
    if not usable:
        return _STATE_UNAVAILABLE, height
    return (_STATE_LOW if height <= resolved['low_height_m'] else _STATE_UPRIGHT), height


def _frame_of(record):
    index = record.get('frameIndex')
    return record.get('frame') if index is None else index


class GroundAlertObserver:
    """Causal source-time observer. A low segment starts before an alert fires."""
    def __init__(self, settings=None):
        self.settings = dict(SETTINGS)
        if settings:
            self.settings.update(settings)
        self.previous = self.current = None

    def update(self, record):
        state, height = classify(record, self.settings)
        frame, stamp = _frame_of(record), _finite(record.get('stampSec'))
        key = (record.get('trackId'), record.get('generation'), record.get('binding'))
        valid = type(frame) is int and stamp is not None
        continuous = (self.previous is not None and valid
            and frame == self.previous[0]+1 and key == self.previous[2]
            and 0 < stamp-self.previous[1] <= POSTURE_SETTINGS['max_gap_s']+1e-9
            and not record.get('observationGap') and not record.get('resetNow'))
        closed = None
        if self.current is not None and (not continuous or state != _STATE_LOW or not valid):
            closed, self.current = self.current, None
        if not valid:
            state = _STATE_UNAVAILABLE
        if state == _STATE_LOW:
            if self.current is None:
                self.current = dict(startFrame=frame, endFrame=frame, startSec=stamp, endSec=stamp,
                    trackId=record['trackId'], generation=record.get('generation'),
                    minHeightM=height, frames=1, triggerFrame=None, triggerSec=None)
            else:
                self.current.update(endFrame=frame, endSec=stamp, frames=self.current['frames']+1,
                    minHeightM=min(height, self.current['minHeightM']))
            if (_duration(self.current)+1e-9 >= self.settings['min_duration_s']
                    and self.current['triggerFrame'] is None):
                self.current.update(triggerFrame=frame, triggerSec=stamp)
        self.previous = (frame, stamp, key) if valid else None
        active = self.current is not None and self.current['triggerFrame'] is not None
        status = 'suspected_ground_posture' if active else 'low_pending' if self.current else state
        return dict(variant=VARIANT, state=status, active=active, heightMedianM=height,
            durationSec=_duration(self.current) if self.current else 0.,
            startFrame=self.current['startFrame'] if self.current else None,
            triggerFrame=self.current['triggerFrame'] if self.current else None,
            reason='sustained_low_posture' if active else 'duration_pending' if self.current
                else 'measurement_or_ground_unavailable' if state == _STATE_UNAVAILABLE else 'above_low_height',
            confirmedEnabled=False, semantic=SEMANTIC), closed, state


class GroundAlertGapCandidate:
    """ground_alert_gap_v2 comparison only: pause a unique same-track short hole.

    Missing intervals contribute zero duration and never emit an active alert.
    IDs are never bridged. Competition, ground failure or >0.3 source s resets.
    """
    def __init__(self):
        self.key = self.previous = self.last_measured = None
        self.duration = 0.
        self.paused = False

    def update(self, record):
        frame, stamp = _frame_of(record), _finite(record.get('stampSec'))
        key = (record.get('trackId') or record.get('continuityTrackId'),
               record.get('generation'), record.get('binding'))
        valid = type(frame) is int and stamp is not None
        continuous = (valid and self.previous is not None and frame == self.previous[0]+1
            and 0 < stamp-self.previous[1] <= POSTURE_SETTINGS['max_gap_s']+1e-9
            and key == self.key and key[0] is not None and not record.get('ambiguous')
            and not record.get('resetNow'))
        state, height = classify(record)
        may_pause = (state == _STATE_UNAVAILABLE and record.get('uniquePredictedTrack') is True
            and record.get('groundAvailable') is True and continuous and self.last_measured is not None
            and stamp-self.last_measured <= POSTURE_SETTINGS['max_gap_s']+1e-9)
        if state == _STATE_LOW:
            if not continuous or self.last_measured is None or stamp-self.last_measured > POSTURE_SETTINGS['max_gap_s']+1e-9:
                self.duration = 0.
            elif not self.paused:
                self.duration += stamp-self.previous[1]
            self.last_measured = stamp
            self.paused = False
        elif may_pause:
            self.paused = True
        else:
            self.duration = 0.; self.last_measured = None; self.paused = False
        self.key = key
        self.previous = (frame, stamp) if valid else None
        active = state == _STATE_LOW and self.duration+1e-9 >= SETTINGS['min_duration_s']
        return dict(variant='ground_alert_gap_v2',state='suspected_ground_posture' if active else
            'low_pending' if state == _STATE_LOW else state,active=active,heightMedianM=height,
            durationSec=self.duration,reason='short_unique_track_hole_paused' if may_pause else
            'sustained_low_posture' if active else 'observed_duration_pending' if state == _STATE_LOW else
            'target_ambiguous' if state == _STATE_UNAVAILABLE and record.get('ambiguous') else
            'measurement_or_ground_unavailable' if state == _STATE_UNAVAILABLE else 'above_low_height',
            confirmedEnabled=False,semantic=SEMANTIC,comparisonOnly=True)


def scan(records, settings=None):
    """扫描逐帧记录，返回 dict(intervals, rejected, lowFrames, unavailableFrames)。

    `records` 只需 frameIndex/frame、stampSec、measured、trackId、heightMedianM。
    段只有达到 `min_duration_s` 才进入 intervals；未达标的段记在 rejected，
    便于回答"差多少秒"。
    """
    resolved = dict(SETTINGS)
    if settings:
        resolved.update(settings)
    intervals, rejected = [], []
    observer = GroundAlertObserver(resolved)
    counts = {_STATE_LOW: 0, _STATE_UPRIGHT: 0, _STATE_UNAVAILABLE: 0}
    for record in records:
        _, closed, state = observer.update(record)
        counts[state] += 1
        if closed is not None:
            (intervals if closed['triggerFrame'] is not None else rejected).append(closed)
    if observer.current is not None:
        current = observer.current
        (intervals if current['triggerFrame'] is not None else rejected).append(current)
    return dict(intervals=[_finalize(iv, resolved) for iv in intervals],
                rejected=[_finalize(iv, resolved) for iv in rejected],
                lowFrames=counts[_STATE_LOW],
                uprightFrames=counts[_STATE_UPRIGHT],
                unavailableFrames=counts[_STATE_UNAVAILABLE])


def _duration(interval):
    start, end = interval.get('startSec'), interval.get('endSec')
    if start is None or end is None:
        return 0.
    return float(end) - float(start)


def _finalize(interval, settings):
    duration = _duration(interval)
    return dict(
        variant=VARIANT,
        startFrame=interval['startFrame'], endFrame=interval['endFrame'],
        startSourceS=None if interval.get('startSec') is None else float(interval['startSec']),
        endSourceS=None if interval.get('endSec') is None else float(interval['endSec']),
        durationS=round(duration, 6),
        frames=interval['frames'],
        trackId=interval.get('trackId'),
        generation=interval.get('generation'),
        triggerFrame=interval.get('triggerFrame'), triggerSourceS=interval.get('triggerSec'),
        minHeightMedianM=None if interval.get('minHeightM') is None else round(interval['minHeightM'], 6),
        lowHeightM=settings['low_height_m'],
        minDurationS=settings['min_duration_s'],
        reasonCodes=list(REASON_CODES),
        state='suspected_ground_posture',
        confirmed=False,
        confirmedEnabled=False,
        semantic=SEMANTIC,
        limitations=list(LIMITATIONS),
    )


def intervals(records, settings=None):
    """只要达标的报警区间（`scan` 的 intervals 部分）。"""
    return scan(records, settings)['intervals']
