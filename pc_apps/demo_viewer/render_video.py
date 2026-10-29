"""Render the four recorded sessions as one offline, three-panel video."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'docs/evidence/2026-10-28_demo_four_sessions'
SESSIONS = [('houdao', '向后倒地'), ('qiandao', '向前倒地'),
            ('huanmandiedao', '缓慢倒地'), ('jixiedaiwanyao', '系鞋带与弯腰')]
WIDTH, HEIGHT, FPS = 1440, 810, 20
FONT = 'C:/Windows/Fonts/msyh.ttc'
BOLD = 'C:/Windows/Fonts/msyhbd.ttc'
STATES = {'unknown': '动作未知', 'upright': '直立', 'descending': '下降中',
          'low_posture_unclassified': '低位 · 未分类', 'suspected': '跌倒嫌疑',
          'confirmed': '确认跌倒', 'recovering': '恢复中'}
EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
         (0, 4), (1, 5), (2, 6), (3, 7)]


def load_records(path):
    content = path.read_text(encoding='utf-8')
    if not content.startswith('window.FRAMES=') or not content.rstrip().endswith(';'):
        raise ValueError('invalid frames.js')
    rows = json.loads(content[len('window.FRAMES='):].strip()[:-1])
    if any(row['i'] != i or (i and row['t'] <= rows[i-1]['t']) for i, row in enumerate(rows)):
        raise ValueError('source frames must be ordered with increasing time')
    return rows


def repeats(rows):
    # Keep every source frame, with a constant-rate output approximating source time.
    result = []
    elapsed = 0
    for i, row in enumerate(rows):
        end = rows[i+1]['t'] if i+1 < len(rows) else row['t'] + (row['t'] - rows[i-1]['t'] if i else .1)
        target = round(end * FPS)
        count = max(1, target - elapsed)
        result.append(count)
        elapsed += count
    return result


def cloud_panel(frame, view, center, size=(450, 470)):
    w, h = size
    pixels = np.zeros((h, w, 3), dtype=np.uint8)
    pixels[:] = (9, 17, 26)
    horizontal = 1 if view == 'front' else 0
    span = 4.2
    scale = w / span
    x_center = center[horizontal]
    def project(points):
        p = np.asarray(points, dtype=float).reshape(-1, 3) / 100.0
        return np.column_stack((w/2 + (p[:, horizontal]-x_center)*scale,
                                h-35 - (p[:, 2]+.2)*scale))
    for values, color, radius in ((frame['bg'], (73, 100, 118), 1),
                                   (frame['tg'], (70, 232, 154), 2)):
        xy = project(values).astype(int)
        inside = (xy[:, 0] >= radius) & (xy[:, 0] < w-radius) & (xy[:, 1] >= radius) & (xy[:, 1] < h-radius)
        xy = xy[inside]
        for dx in range(-radius+1, radius):
            for dy in range(-radius+1, radius):
                pixels[xy[:, 1]+dy, xy[:, 0]+dx] = color
    img = Image.fromarray(pixels)
    draw = ImageDraw.Draw(img)
    floor_y = h-35-int(.2*scale)
    draw.line((0, floor_y, w, floor_y), fill=(37, 63, 73), width=1)
    if frame['bb']:
        x0,y0,z0,x1,y1,z1=frame['bb']
        p=project([[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],
                   [x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]])
        for a,b in EDGES:
            draw.line((tuple(p[a]),tuple(p[b])),fill=(94,255,170),width=2)
    return img


def render(frame, title, seq, center, camera_dir, fonts):
    small, label, heading = fonts
    im = Image.new('RGB', (WIDTH, HEIGHT), (7, 13, 20))
    d = ImageDraw.Draw(im)
    d.text((32, 22), 'LIDAR  /  人体动作离线回放', font=small, fill=(122, 170, 159))
    d.text((32, 55), title, font=heading, fill=(236, 244, 245))
    d.text((1290, 67), '%02d / 04' % seq, font=label, fill=(120, 156, 157))
    boxes = [(25, 152), (495, 152), (965, 152)]
    for (x,y), caption in zip(boxes, ['正面点云', '侧面点云', '相机画面']):
        d.rounded_rectangle((x, y-38, x+450, y+470), radius=10, fill=(15,24,34), outline=(39,57,69), width=1)
        d.text((x+15,y-31),caption,font=small,fill=(185,208,212))
    im.paste(cloud_panel(frame, 'front', center), boxes[0])
    im.paste(cloud_panel(frame, 'side', center), boxes[1])
    if frame['cam']:
        camera_path = camera_dir / ('c%03d.jpg' % frame['cam'][0])
        camera = Image.open(camera_path).convert('RGB')
        camera = ImageOps.contain(camera, (450,470), method=Image.Resampling.LANCZOS)
        im.paste(camera, (965+(450-camera.width)//2, 152+(470-camera.height)//2))
    else:
        d.text((1090, 350), '相机帧不可用', font=label, fill=(130,150,160))
    state = STATES.get(frame['st'], '动作未知')
    hot = frame['st'] in ('suspected', 'confirmed')
    d.rounded_rectangle((25, 651, 1415, 725), radius=12,
                        fill=(69,22,27) if hot else (18,31,38),
                        outline=(170,54,65) if hot else (44,70,75), width=1)
    d.text((48, 672), '状态  ' + state, font=label, fill=(255,121,126) if hot else (196,224,216))
    d.text((1020, 672), '跌倒嫌疑' if hot else '未触发报警', font=label,
           fill=(255,121,126) if hot else (138,172,170))
    d.text((25, 755), '目标为点云几何候选  ·  相机按接收时间配对  ·  地面未验证', font=small, fill=(110,141,151))
    d.text((1288, 755), '%05.1f s' % frame['t'], font=small, fill=(110,141,151))
    return im


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise FileExistsError(args.out)
    fonts = (ImageFont.truetype(FONT, 19), ImageFont.truetype(BOLD, 24), ImageFont.truetype(BOLD, 35))
    manifest = []
    cmd = ['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24',
           '-video_size',f'{WIDTH}x{HEIGHT}','-framerate',str(FPS),'-i','pipe:0',
           '-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
           '-movflags','+faststart',str(args.out)]
    with (args.evidence/'ffmpeg.log').open('wb') as log:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
        total = 0
        try:
            for seq, (name, title) in enumerate(SESSIONS, 1):
                src = SOURCE / ('replay_' + name)
                rows = load_records(src/'data/frames.js')
                summary = json.loads((src/'SUMMARY.json').read_text(encoding='utf-8'))
                if len(rows) != summary['source']['frames']:
                    raise ValueError('incomplete source ' + name)
                center = (summary['display']['view']['tx'], summary['display']['view']['ty'])
                counts = repeats(rows)
                start = total
                for i, (row, n) in enumerate(zip(rows, counts)):
                    image = render(row, title, seq, center, src/'camera', fonts)
                    if i in (0, len(rows)//2, len(rows)-1):
                        image.save(args.evidence / (name + '_' + str(i) + '.png'))
                    data = image.tobytes()
                    for _ in range(n):
                        process.stdin.write(data)
                    total += n
                manifest.append(dict(session=name, source_frames=len(rows), first_video_frame=start,
                                     video_frames=total-start, first_source_time=rows[0]['t'],
                                     last_source_time=rows[-1]['t'], repeats=counts,
                                     frames_sha256=hashlib.sha256((src/'data/frames.js').read_bytes()).hexdigest(),
                                     states={s:sum(row['st']==s for row in rows) for s in sorted(set(r['st'] for r in rows))}))
                print(name, len(rows), total-start, flush=True)
        finally:
            process.stdin.close()
            code = process.wait()
        if code:
            raise RuntimeError('ffmpeg failed: %s' % code)
    (args.evidence/'MANIFEST.json').write_text(json.dumps(dict(fps=FPS, width=WIDTH, height=HEIGHT,
        total_video_frames=total, sessions=manifest, video_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest()),
        ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
