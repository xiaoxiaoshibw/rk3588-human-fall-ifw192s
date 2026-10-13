"""HF-REAL-03 cam-hot：从板上 MJPEG /stream 提取首帧和中段一帧保存 JPEG。
ponytail：一次工具，输出按帧命名，不建 helper。"""
import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'out'
OUT.mkdir(parents=True, exist_ok=True)
URL = 'http://192.168.31.58:8081/stream'


def grab(idx_want=(0, 200)):
    req = urllib.request.Request(URL, headers={'User-Agent': 'curl/8'})
    buf = b''; frames = []
    with urllib.request.urlopen(req, timeout=20) as r:
        while len(frames) <= max(idx_want):
            chunk = r.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                s = buf.find(b'\xff\xd8\xff')
                if s < 0:
                    break
                e = buf.find(b'\xff\xd8\xff', s + 3)
                if e < 0:
                    buf = buf[s:]
                    break
                frames.append(buf[s:e])
                buf = buf[e:]
    saved = []
    for i in idx_want:
        if i < len(frames):
            p = OUT / f'CAM_F{i:04d}.jpg'
            p.write_bytes(frames[i])
            saved.append((i, len(frames[i]), str(p)))
    return saved, len(frames)


if __name__ == '__main__':
    saved, total = grab()
    print(json.dumps({'total_frames_seen': total, 'saved': saved}, ensure_ascii=False))
