import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from sync_audit import CONVENTION, alignment_audit, audit, timing


def alignment():
    return dict(schema='sync_alignment_v1', convention=CONVENTION,
                lidar_clock='meta.frames[].bag_time_sec (bag receipt)',
                video_clock='video presentation seconds from file start',
                adopted_offset_s=10.0, adoption_source='fit anchor motion-1',
                uncertainty_s=0.1, uncertainty_source='frame bracketing on both streams',
                anchors=[dict(id='a', physical_event_id='motion-1', role='fit',
                              lidar_s=11.0, video_s=1.0, lidar_source='frame 1', video_source='frame 10'),
                         dict(id='b', physical_event_id='motion-2', role='check',
                              lidar_s=12.05, video_s=2.0, lidar_source='frame 2', video_source='frame 20'),
                         dict(id='c', physical_event_id='motion-3', role='check',
                              lidar_s=14.15, video_s=4.0, lidar_source='frame 4', video_source='frame 40')])


class SyncAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.session = self.root / 'session'
        self.session.mkdir()
        self.write(self.session / 'meta.json', dict(session_id='synthetic', frames=[
            dict(bag_time_sec=11., stamp_sec=1, stamp_nanosec=0),
            dict(bag_time_sec=12., stamp_sec=2, stamp_nanosec=0)]))
        self.write(self.session / 'joint.json', dict(state='completed'))
        (self.session / 'points.bin').write_bytes(b'synthetic-not-real-points')
        (self.session / 'camera.mjpeg').write_bytes(b'\xff\xd8\xff\xd9' * 2)
        (self.session / 'camera_frames.jsonl').write_text(
            '\n'.join(json.dumps(dict(offset=i * 4, length=4, recv_unix_ns=i * 10**9))
                      for i in range(2)), encoding='utf8')
        self.align_path = self.root / 'alignment.json'
        self.write(self.align_path, alignment())

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding='utf8')

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', '-W', 'error',
                               str(Path(__file__).with_name('sync_audit.py')),
                               '--session', str(self.session), *map(str, args)],
                              capture_output=True, text=True)

    def test_no_anchors_does_not_infer_sync_from_receipt_times(self):
        result = audit(self.session)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIsNone(result['alignment']['adopted_offset_s'])
        self.assertEqual(result['quality']['physical_sync_error_s'], 'UNKNOWN')
        self.assertEqual(result['quality']['camera_byte_errors'], [])

    def test_sign_raw_residual_and_independent_drift(self):
        result = alignment_audit(alignment())
        self.assertEqual(result['status'], 'RECORDED')
        self.assertEqual(result['automatic_offset_s'], 10.)
        self.assertAlmostEqual(result['residuals'][1]['residual_s'], .05)
        self.assertAlmostEqual(result['max_abs_check_residual_s'], .15)
        self.assertAlmostEqual(result['drift_s_per_s'], .05)
        self.assertTrue(result['check_residual_exceeds_declared_uncertainty'])
        self.assertEqual(result['residuals'][1]['raw_lidar_s'], 12.05)
        self.assertEqual(result['residuals'][1]['lidar_source'], 'frame 2')
        self.assertEqual(result['residuals'][1]['physical_event_id'], 'motion-2')
        self.assertEqual(result['uncertainty_source'], alignment()['uncertainty_source'])

    def test_suggested_offset_is_never_implicitly_adopted(self):
        doc = alignment()
        doc['adopted_offset_s'] = None
        result = alignment_audit(doc)
        self.assertEqual(result['automatic_offset_s'], 10.)
        self.assertIsNone(result['adopted_offset_s'])
        self.assertIsNone(result['residuals'][0]['residual_s'])
        self.assertEqual(result['status'], 'UNKNOWN')

    def test_fit_anchor_is_not_independent_check(self):
        doc = alignment()
        doc['anchors'][1]['physical_event_id'] = 'motion-1'
        with self.assertRaisesRegex(ValueError, 'independent'):
            alignment_audit(doc)
        doc = alignment()
        doc['anchors'][1].update(lidar_s=11., video_s=1.)
        with self.assertRaisesRegex(ValueError, 'independent'):
            alignment_audit(doc)
        doc = alignment()
        doc['anchors'] = doc['anchors'][:1]
        self.assertEqual(alignment_audit(doc)['status'], 'UNKNOWN')

    def test_bad_evidence_rejected(self):
        for key, value in [('convention', 'reverse'), ('uncertainty_s', -1),
                           ('adopted_offset_s', float('nan')), ('uncertainty_s', True),
                           ('uncertainty_source', ''), ('lidar_clock', 'UNKNOWN')]:
            doc = alignment()
            doc[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                alignment_audit(doc)

    def test_clock_errors_keep_original_order_and_denominator(self):
        result = timing([1., 1., 0., None, float('nan'), 5., 6.])
        self.assertEqual((result['n'], result['invalid'], result['duplicates'], result['regressions']),
                         (7, 2, 1, 1))
        self.assertEqual(result['median_positive_interval_s'], 1.)
        self.assertEqual(result['dropped_frames'], 'UNKNOWN')

    def test_every_source_and_alignment_change_invalidates_previous(self):
        previous = audit(self.session, self.align_path)
        old = self.root / 'previous.json'
        self.write(old, previous)
        self.assertEqual(audit(self.session, self.align_path, old)['previous_audit']['status'], 'UNCHANGED')
        for name in ('meta.json', 'points.bin', 'joint.json', 'camera_frames.jsonl', 'camera.mjpeg'):
            path = self.session / name
            original = path.read_bytes()
            path.write_bytes(original + (b' ' if name.endswith(('.json', '.jsonl')) else b'x'))
            with self.subTest(name=name):
                result = audit(self.session, self.align_path, old)
                self.assertEqual(result['status'], 'STALE')
                self.assertEqual(result['previous_audit']['changed'], [name])
            path.write_bytes(original)
        doc = alignment()
        doc['adopted_offset_s'] = 9.
        self.write(self.align_path, doc)
        self.assertEqual(audit(self.session, self.align_path, old)['previous_audit']['changed'], ['alignment'])

    def test_missing_input_preserved_as_incomplete(self):
        (self.session / 'points.bin').unlink()
        result = audit(self.session)
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['missing_files'], ['points.bin'])

    def test_camera_corruption_and_unindexed_bytes_reported(self):
        (self.session / 'camera.mjpeg').write_bytes(b'bad!\xff\xd8\xff\xd9tail')
        quality = audit(self.session)['quality']
        self.assertEqual(quality['camera_byte_errors'], [dict(index=0, reason='invalid_jpeg_envelope')])
        self.assertEqual(quality['camera_trailing_unindexed_bytes'], 4)

    def test_cli_is_exclusive_read_only_and_deterministic(self):
        before = {p.name: p.read_bytes() for p in self.session.iterdir()}
        out = self.root / 'out.json'
        self.assertEqual(self.cli('--out', out).returncode, 0)
        original = out.read_bytes()
        self.assertNotEqual(self.cli('--out', out).returncode, 0)
        self.assertEqual(out.read_bytes(), original)
        self.assertNotEqual(self.cli('--out', self.session / 'new.json').returncode, 0)
        second = self.root / 'second.json'
        self.assertEqual(self.cli('--out', second).returncode, 0)
        self.assertEqual(out.read_bytes(), second.read_bytes())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.session.iterdir()})

    def test_input_change_during_audit_discards_result(self):
        from sync_audit import session_quality
        def changing(*args):
            result = session_quality(*args)
            (self.session / 'points.bin').write_bytes(b'changed')
            return result
        with mock.patch('sync_audit.session_quality', side_effect=changing):
            with self.assertRaisesRegex(ValueError, 'input changed'):
                audit(self.session)


if __name__ == '__main__':
    unittest.main()
