"""Read-only indexed-MJPEG/MP4 sync and real Qt video-window integration."""
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
import av

from video_worker import VideoReader
import test_integration as fixtures

EPOCH = 1700000000


def make_video_session(directory):
    directory.mkdir(parents=True)
    rows = []
    with (directory / 'camera.mjpeg').open('wb') as video:
        for i in range(100):
            out = io.BytesIO()
            Image.new('RGB', (48, 32), ((i * 13) % 256, 35, 175)).save(out, 'JPEG', quality=90)
            jpeg = out.getvalue()
            rows.append(dict(offset=video.tell(), length=len(jpeg), recv_unix_ns=(EPOCH * 10**9 + i * 100000000)))
            video.write(jpeg)
    (directory / 'camera_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf8')
    with av.open(str(directory / 'clip.mp4'), 'w') as container:
        stream = container.add_stream('mpeg4', rate=10)
        stream.width, stream.height, stream.pix_fmt = 48, 32, 'yuv420p'
        for i in range(100):
            frame = av.VideoFrame.from_image(Image.new('RGB', (48, 32), ((i * 13) % 256, 35, 175)))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    raw = struct.pack('<ffffId', 2., 0., .5, 10., 1, 1.)
    (directory / 'points.bin').write_bytes(raw * 80)
    meta = dict(point_file='points.bin', point_layout=dict(stride_bytes=28), total_points=80,
                frames=[dict(offset_points=i, count_points=1, stamp_sec=1+i//10,
                             stamp_nanosec=(i % 10) * 100000000, bag_time_sec=EPOCH+i/10)
                        for i in range(80)])
    (directory / 'meta.json').write_text(json.dumps(meta), encoding='utf8')


class TestVideoDecoder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session = Path(self.temp.name) / 'video_session'
        make_video_session(self.session)

    def test_receipt_clock_offset_reverse_seek_and_missing_coverage(self):
        reader = VideoReader(self.session / 'camera.mjpeg')
        self.addCleanup(reader.close)
        for relative, offset, expected in [(0., 0., 0), (.53, 0., 5), (.53, .2, 7), (.2, 0., 2)]:
            jpeg, info = reader.sample(relative, EPOCH+relative, offset)
            self.assertEqual(info['videoFrameIndex'], expected)
            self.assertEqual(info['alignment'], 'receipt_time_unverified')
            with Image.open(io.BytesIO(jpeg)) as image:
                self.assertLessEqual(abs(image.getpixel((24, 16))[0] - expected*13), 5)
        jpeg, info = reader.sample(0, EPOCH+60)
        self.assertIsNone(jpeg)
        self.assertEqual(info['state'], 'outside')

    def test_mp4_pts_seek_then_reverse_without_reusing_future_frame(self):
        reader = VideoReader(self.session / 'clip.mp4')
        self.addCleanup(reader.close)
        for target, expected in [(0., 0.), (3.53, 3.5), (.23, .2), (5.1, 5.1)]:
            jpeg, info = reader.sample(target)
            self.assertAlmostEqual(info['videoTimeSec'], expected, places=5)
            self.assertEqual(info['alignment'], 'relative_start')
            with Image.open(io.BytesIO(jpeg)) as image:
                self.assertLessEqual(abs(image.getpixel((24, 16))[0] - (round(expected*10)*13)%256), 6)

    def test_bad_index_bounds_and_nonmonotonic_clock_rejected(self):
        index = self.session / 'camera_frames.jsonl'
        rows = [json.loads(row) for row in index.read_text(encoding='utf8').splitlines()]
        for kind in ('bounds', 'clock'):
            copy = [dict(row) for row in rows]
            if kind == 'bounds':
                copy[0]['length'] = 999999999
            else:
                copy[1]['recv_unix_ns'] = copy[0]['recv_unix_ns']
            index.write_text(''.join(json.dumps(row)+'\n' for row in copy), encoding='utf8')
            with self.assertRaises(ValueError):
                VideoReader(self.session / 'camera.mjpeg')

    def test_worker_latest_request_wins_and_source_is_unchanged(self):
        source = self.session / 'clip.mp4'
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        requests = [dict(requestId=i, sessionId='video_session', generation=i, mediaVersion=0,
                         sourceFrameIndex=i, sourceTimeSec=.23, bagTimeSec=None, offsetSec=0., path=str(source))
                    for i in range(500)]
        done = subprocess.run([sys.executable, '-B', '-W', 'error', str(Path(__file__).with_name('video_worker.py'))],
                              input=''.join(json.dumps(row)+'\n' for row in requests), text=True,
                              capture_output=True, timeout=20, encoding='utf8')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stderr, '')
        responses = [json.loads(line) for line in done.stdout.splitlines()]
        self.assertEqual(responses[-1]['requestId'], 499)
        self.assertEqual(responses[-1]['info']['state'], 'ready')
        self.assertLess(len(responses), 100)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)


class TestVideoWindow(unittest.TestCase):
    setUp = fixtures.TestApp.setUp

    def test_auto_window_play_pause_seek_offset_mp4_speed_close_reopen(self):
        session = self.out / 'sessions' / 'video_session'
        make_video_session(session)
        empty = session.parent / 'no_video_session'
        empty.mkdir()
        for name in ('meta.json', 'points.bin'):
            (empty / name).write_bytes((session / name).read_bytes())
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in session.iterdir()}
        args = [str(fixtures.SDK), str(fixtures.DLL), '--session', str(session), '--host', str(fixtures.HOST),
                '--report', str(self.out / 'run.json'), '--python', sys.executable,
                '--video-report', str(self.out / 'video.json')]
        done = subprocess.run(args, cwd=fixtures.ROOT, capture_output=True, timeout=30)
        (self.out / 'stdout.txt').write_bytes(done.stdout)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))
        report = json.loads((self.out / 'video.json').read_text(encoding='utf8'))
        self.assertEqual(report['status'], 'PASS', report)
        cases = {row['case']: row for row in report['checks']}
        self.assertIn('ordinary_mp4_follows_replay', cases)
        self.assertIn('no_video_session_clears_old_image', cases)
        seek = cases['video_follows_seek']
        self.assertEqual(seek['video']['videoFrameIndex'], 55)
        self.assertLessEqual(abs(seek['rgb'][0] - (55*13)%256), 5)
        for p in session.iterdir():
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), before[p.name])
        service = json.loads((self.out / 'run.json').read_text(encoding='utf8'))
        self.assertEqual(service['jointMutationRequests'], 0)
        self.assertEqual(service['sessionDeletes'], 0)
        self.assertTrue(any(row['eventType'] == 'videoFrame' for row in service['log']))
        if (self.out / 'video.stderr').exists():
            self.assertEqual((self.out / 'video.stderr').read_text(encoding='utf8'), '')

    def test_delete_private_session_closes_active_video_reader(self):
        session = self.out / 'sessions' / 'video_session'
        make_video_session(session)
        fallback = session.parent / 'no_video_session'
        fallback.mkdir()
        for name in ('meta.json', 'points.bin'):
            (fallback / name).write_bytes((session / name).read_bytes())
        args = [str(fixtures.SDK), str(fixtures.DLL), '--session', str(session), '--host', str(fixtures.HOST),
                '--report', str(self.out / 'run.json'), '--python', sys.executable,
                '--smoke-delete', 'video_session,probe,0']
        done = subprocess.run(args, cwd=fixtures.ROOT, capture_output=True, timeout=25)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))
        report = json.loads((self.out / 'run.json').read_text(encoding='utf8'))
        events = [row['eventType'] for row in report['log']]
        self.assertIn('videoFrame', events, 'Reader was not active before the private delete')
        self.assertIn('sessionDeleted', events)
        self.assertFalse(session.exists())
        self.assertTrue((fallback / 'points.bin').is_file())
        self.assertEqual(report['jointMutationRequests'], 0)


if __name__ == '__main__':
    unittest.main()
