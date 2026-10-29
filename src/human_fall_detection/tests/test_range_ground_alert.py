"""ground_alert_v1 单元测试：持续低姿态报警的判定与边界。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from core import range_ground_alert as alert                      # noqa: E402

DT = 0.1037


def frames(heights, start=0, dt=DT, measured=None, track='g0_t0001'):
    out = []
    for offset, height in enumerate(heights):
        index = start + offset
        out.append(dict(frameIndex=index, stampSec=index * dt,
                        measured=True if measured is None else measured[offset],
                        trackId=track, heightMedianM=height))
    return out


class IntervalTest(unittest.TestCase):
    def test_ambiguous_gap_is_identified_and_cannot_pause(self):
        observer = alert.GroundAlertGapCandidate()
        observer.update(dict(frameIndex=0, stampSec=0., measured=True, trackId='a',
                             heightMedianM=.4, groundAvailable=True))
        result = observer.update(dict(frameIndex=1, stampSec=.1, measured=False,
            trackId=None, continuityTrackId='a', uniquePredictedTrack=True,
            groundAvailable=True, ambiguous=True))
        self.assertEqual(result['reason'], 'target_ambiguous')
        self.assertFalse(result['active'])
        self.assertEqual(result['durationSec'], 0.)

    def test_causal_trigger_and_prefix_invariance(self):
        rows=frames([.5]*34)
        observer=alert.GroundAlertObserver()
        values=[observer.update(r)[0] for r in rows]
        self.assertFalse(any(v['active'] for v in values[:15]))
        self.assertTrue(values[15]['active'])
        self.assertEqual(values[15]['triggerFrame'],15)
        self.assertEqual(alert.scan(rows)['intervals'][0]['triggerFrame'],15)
        shorter=alert.GroundAlertObserver()
        self.assertEqual(values[:16],[shorter.update(r)[0] for r in rows[:16]])

    def test_gaps_rewind_invalid_time_and_generation_do_not_join(self):
        for patch in (dict(frameIndex=20),dict(stampSec=10.),dict(stampSec=.2),
                      dict(stampSec=float('nan')),dict(observationGap=True),dict(generation=1)):
            rows=frames([.5]*16)
            rows[8].update(patch)
            self.assertEqual(alert.scan(rows)['intervals'],[],patch)

    def test_too_short_is_rejected_and_counted(self):
        # 15 帧低姿态：源时间差 14 × 0.1037 = 1.4518 s < 1.5 s
        result = alert.scan(frames([0.5] * 15))
        self.assertEqual(result['intervals'], [])
        self.assertEqual(len(result['rejected']), 1)
        self.assertEqual(result['rejected'][0]['frames'], 15)
        self.assertAlmostEqual(result['rejected'][0]['durationS'], 14 * DT, places=6)

    def test_sixteen_frames_fires(self):
        result = alert.scan(frames([0.5] * 16))
        self.assertEqual(len(result['intervals']), 1)
        interval = result['intervals'][0]
        self.assertEqual((interval['startFrame'], interval['endFrame']), (0, 15))
        self.assertEqual(interval['frames'], 16)
        self.assertAlmostEqual(interval['durationS'], 15 * DT, places=6)
        self.assertEqual(interval['state'], 'suspected_ground_posture')
        self.assertFalse(interval['confirmed'])
        self.assertFalse(interval['confirmedEnabled'])
        self.assertEqual(interval['semantic'], 'UNKNOWN')
        self.assertEqual(interval['variant'], 'ground_alert_v1')

    def test_threshold_is_inclusive(self):
        # 高度正好等于 0.7 m 仍算低姿态（与 fall_state 的 <= 一致）
        result = alert.scan(frames([0.7] * 16))
        self.assertEqual(len(result['intervals']), 1)
        # 0.7001 m 则不是
        self.assertEqual(alert.scan(frames([0.7001] * 16))['intervals'], [])

    def test_upright_frame_splits_episodes(self):
        heights = [0.5] * 16 + [1.2] + [0.5] * 16
        result = alert.scan(frames(heights))
        self.assertEqual(len(result['intervals']), 2)
        self.assertEqual(result['uprightFrames'], 1)

    def test_missing_measurement_splits_episodes(self):
        heights = [0.5] * 16 + [0.5] + [0.5] * 16
        measured = [True] * 16 + [False] + [True] * 16
        result = alert.scan(frames(heights, measured=measured))
        self.assertEqual(len(result['intervals']), 2)
        self.assertEqual(result['unavailableFrames'], 1)

    def test_track_change_splits_episodes(self):
        first = frames([0.5] * 16, start=0)
        second = frames([0.5] * 16, start=16, track='g0_t0002')
        result = alert.scan(first + second)
        # 两段各自达标：第二段从 16 起算 15 帧差
        self.assertEqual(len(result['intervals']), 2)
        self.assertEqual(result['intervals'][1]['trackId'], 'g0_t0002')

    def test_none_height_is_unavailable(self):
        heights = [0.5] * 8 + [None] + [0.5] * 8
        result = alert.scan(frames(heights))
        self.assertEqual(result['lowFrames'], 16)
        self.assertEqual(result['unavailableFrames'], 1)
        self.assertEqual(result['intervals'], [])

    def test_no_ground_means_no_interval(self):
        result = alert.scan(frames([None] * 40))
        self.assertEqual(result['intervals'], [])
        self.assertEqual(result['unavailableFrames'], 40)

    def test_split_episode_is_reported_as_rejected(self):
        # 缺口把 31 帧低姿态切成两个 15 帧段：各 14 × 0.1037 = 1.4518 s → 都不达标
        heights = [0.5] * 31
        measured = [True] * 15 + [False] + [True] * 15
        result = alert.scan(frames(heights, measured=measured))
        self.assertEqual(result['intervals'], [])
        self.assertEqual([iv['frames'] for iv in result['rejected']], [15, 15])

    def test_trailing_episode_is_flushed(self):
        result = alert.scan(frames([0.5] * 20))
        self.assertEqual(len(result['intervals']), 1)
        self.assertEqual(result['intervals'][0]['endFrame'], 19)

    def test_settings_override_is_honoured(self):
        result = alert.scan(frames([0.5] * 16), settings=dict(low_height_m=0.4))
        self.assertEqual(result['intervals'], [])
        self.assertEqual(result['uprightFrames'], 16)

    def test_classify_states(self):
        self.assertEqual(alert.classify(dict(measured=True, trackId='t', heightMedianM=0.3))[0],
                         'low')
        self.assertEqual(alert.classify(dict(measured=True, trackId='t', heightMedianM=1.4))[0],
                         'upright')
        self.assertEqual(alert.classify(dict(measured=False, trackId=None, heightMedianM=0.3))[0],
                         'unavailable')
        self.assertEqual(alert.classify(dict(measured=True, trackId=None, heightMedianM=0.3))[0],
                         'unavailable')

    def test_settings_are_frozen_values(self):
        # 必须与规则层引用同一组既有值，不得出现新数字
        from core.fall_state import DEFAULT_SETTINGS
        self.assertIs(alert.SETTINGS['low_height_m'], DEFAULT_SETTINGS['low_height_m'])
        self.assertIs(alert.SETTINGS['min_duration_s'], DEFAULT_SETTINGS['low_min_duration_s'])


if __name__ == '__main__':
    unittest.main()
