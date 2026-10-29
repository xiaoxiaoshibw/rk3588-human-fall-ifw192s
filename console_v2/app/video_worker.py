"""Read-only local video decoder. Latest request wins; stdout is bounded JSON/JPEG.

Indexed MJPEG uses the recorder's host-receipt times. Other containers use their
PTS and an explicit relative-start alignment; neither is hardware synchronization.
PyAV/Pillow are PC dependencies already installed in the development runtime.
"""
import base64
from bisect import bisect_left
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import threading


def jpeg_bytes(image):
    from PIL import Image
    if image.width * image.height > 16 * 1024 * 1024:
        raise ValueError('video frame exceeds 16 megapixels')
    image.thumbnail((1280, 720), Image.Resampling.BILINEAR)
    out = io.BytesIO()
    image.convert('RGB').save(out, 'JPEG', quality=82)
    data = out.getvalue()
    if len(data) > 512 * 1024:
        raise ValueError('preview JPEG exceeds limit')
    return data


class VideoReader:
    def __init__(self, filename):
        self.path = Path(filename)
        self.container = None
        self.file = None
        self.rows = []
        self.times = []
        self.decoder = None
        self.previous = None
        self.following = None
        self.last_target = None
        self.cache = None
        index = self.path.with_name(self.path.stem + '_frames.jsonl')
        try:
            if self.path.suffix.lower() in ('.mjpeg', '.mjpg') and index.is_file():
                if index.stat().st_size > 64 * 1024 * 1024:
                    raise ValueError('camera index exceeds limit')
                size = self.path.stat().st_size
                covered = 0
                with index.open(encoding='utf8') as source:
                    for line in source:
                        if len(line) > 4096:
                            raise ValueError('camera index row exceeds limit')
                        row = json.loads(line)
                        values = [row.get(k) for k in ('offset', 'length', 'recv_unix_ns')]
                        if any(type(v) is not int for v in values):
                            raise ValueError('invalid camera index fields')
                        offset, length, stamp = values
                        if offset != covered or not 0 < length <= 32 * 1024 * 1024 or offset + length > size or stamp <= 0:
                            raise ValueError('camera index outside video bytes')
                        if self.times and stamp <= self.times[-1]:
                            raise ValueError('camera timestamps must increase')
                        self.rows.append(row)
                        self.times.append(stamp)
                        covered = offset + length
                if not self.rows:
                    raise ValueError('empty camera index')
                self.file = self.path.open('rb')
                self.duration = (self.times[-1] - self.times[0]) / 1e9
                self.fps = (len(self.rows) - 1) / self.duration if self.duration > 0 else 1.
                self.mode = 'receipt_time'
            else:
                import av
                self.container = av.open(str(self.path), options={'protocol_whitelist': 'file'})
                if not self.container.streams.video:
                    raise ValueError('file has no video stream')
                self.stream = self.container.streams.video[0]
                if self.stream.codec_context.width * self.stream.codec_context.height > 16 * 1024 * 1024:
                    raise ValueError('video frame exceeds 16 megapixels')
                self.stream.thread_type = 'AUTO'
                self.start = float((self.stream.start_time or 0) * self.stream.time_base)
                self.duration = float(self.stream.duration * self.stream.time_base) if self.stream.duration is not None else (
                    self.container.duration / av.time_base if self.container.duration is not None else None)
                self.fps = float(self.stream.average_rate or 25)
                self.mode = 'relative_start'
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.container is not None:
            self.container.close()
            self.container = None
        if self.file is not None:
            self.file.close()
            self.file = None

    def sample(self, relative_s, bag_time_s=None, offset_s=0.):
        from PIL import Image
        if not all(math.isfinite(v) for v in (relative_s, offset_s)):
            raise ValueError('nonfinite video time')
        if self.rows:
            anchored = bag_time_s is not None and math.isfinite(bag_time_s)
            # Subtract integer nanoseconds before float conversion, preserving receipt precision.
            target_ns = round((bag_time_s + offset_s) * 1e9) if anchored else self.times[0] + round((relative_s + offset_s) * 1e9)
            target = (target_ns - self.times[0]) / 1e9
            at = bisect_left(self.times, target_ns)
            choices = [i for i in (at-1, at) if 0 <= i < len(self.rows)]
            index = min(choices, key=lambda i: (abs(self.times[i] - target_ns), i))
            delta = (self.times[index] - target_ns) / 1e9
            info = dict(videoTimeSec=(self.times[index] - self.times[0]) / 1e9,
                        videoFrameIndex=index, deltaMs=delta * 1000,
                        alignment='receipt_time_unverified' if anchored else 'relative_start',
                        durationSec=self.duration, fps=self.fps)
            if abs(delta) > .25:
                return None, dict(info, state='outside', reason='当前雷达时刻没有相近视频帧')
            if self.cache is None or self.cache[0] != index:
                row = self.rows[index]
                self.file.seek(row['offset'])
                data = self.file.read(row['length'])
                if len(data) != row['length'] or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
                    raise ValueError('camera frame JPEG boundary mismatch')
                with Image.open(io.BytesIO(data)) as image:
                    data = jpeg_bytes(image)
                self.cache = index, data
            return self.cache[1], dict(info, state='ready')
        target = relative_s + offset_s
        if target < 0 or self.duration is not None and target > self.duration:
            return None, dict(state='outside', reason='当前雷达时刻超出视频范围', videoTimeSec=target,
                              alignment='relative_start', durationSec=self.duration, fps=self.fps)
        if self.decoder is None or self.last_target is None or target < self.last_target - 1e-6 or target - self.last_target > .75:
            stamp = int((target + self.start) / self.stream.time_base)
            self.container.seek(stamp, backward=True, any_frame=False, stream=self.stream)
            self.decoder = iter(self.container.decode(self.stream))
            self.previous = None
            self.following = next(self.decoder, None)
        self.last_target = target

        def seconds(frame):
            if frame.pts is None:
                raise ValueError('video frame has no presentation timestamp')
            return float(frame.pts * frame.time_base) - self.start

        iterations = 0
        while self.following is not None and seconds(self.following) < target:
            self.previous = self.following
            self.following = next(self.decoder, None)
            iterations += 1
            if iterations > 2000:
                raise ValueError('video keyframe seek exceeds decode budget')
        candidates = [f for f in (self.previous, self.following) if f is not None]
        if not candidates:
            raise ValueError('video decoder returned no frames')
        frame = min(candidates, key=lambda f: abs(seconds(f) - target))
        actual = seconds(frame)
        if self.cache is None or self.cache[0] != actual:
            self.cache = actual, jpeg_bytes(frame.to_image())
        return self.cache[1], dict(state='ready', videoTimeSec=actual, videoFrameIndex=None,
                                  deltaMs=(actual-target)*1000, alignment='relative_start',
                                  durationSec=self.duration, fps=self.fps)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    condition = threading.Condition()
    inbox = {'latest': None, 'eof': False}

    def receive():
        try:
            for line in sys.stdin.buffer:
                if len(line) > 16384:
                    raise ValueError('video request exceeds limit')
                request = json.loads(line)
                with condition:
                    inbox['latest'] = request
                    condition.notify()
        finally:
            with condition:
                inbox['eof'] = True
                condition.notify()

    threading.Thread(target=receive, daemon=True).start()
    reader = None
    filename = None
    open_error = None
    try:
        while True:
            with condition:
                condition.wait_for(lambda: inbox['latest'] is not None or inbox['eof'])
                request = inbox['latest']
                inbox['latest'] = None
                if request is None:
                    break
            binding = {k: request[k] for k in ('requestId', 'sessionId', 'generation', 'mediaVersion', 'sourceFrameIndex', 'sourceTimeSec')}
            try:
                if filename != request['path']:
                    if reader is not None:
                        reader.close()
                    reader = None
                    filename = request['path']
                    open_error = None
                    try:
                        reader = VideoReader(filename)
                    except Exception as exc:
                        open_error = '%s: %s' % (type(exc).__name__, exc)
                        raise
                if reader is None:
                    raise ValueError(open_error or 'video could not be opened')
                jpeg, info = reader.sample(request['sourceTimeSec'], request.get('bagTimeSec'), request['offsetSec'])
                response = dict(binding, info=info, jpeg=base64.b64encode(jpeg).decode('ascii') if jpeg else '',
                                jpegSha256=hashlib.sha256(jpeg or b'').hexdigest())
            except Exception as exc:
                response = dict(binding, info=dict(state='error', reason='%s: %s' % (type(exc).__name__, exc)), jpeg='',
                                jpegSha256=hashlib.sha256(b'').hexdigest())
            print(json.dumps(response, ensure_ascii=False, allow_nan=False), flush=True)
    finally:
        if reader is not None:
            reader.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
