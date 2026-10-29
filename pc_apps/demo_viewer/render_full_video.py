"""Render all source XYZ rows alongside the offline demo alert comparison."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from demo_alert import DemoAlert
import render_video as base

WIDTH, HEIGHT = 1600, 900
POINT_DTYPE = np.dtype([('x','<f4'),('y','<f4'),('z','<f4'),('rest','V16')])


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def basis(normal):
    up = np.asarray(normal, dtype=float)
    up /= np.linalg.norm(up)
    forward = np.array([1., 0., 0.]) - up*up[0]
    forward /= np.linalg.norm(forward)
    return np.stack([forward, np.cross(up, forward), up])


def read_xyz(stream, meta_frame, rotation, offset):
    count = meta_frame['count_points']
    stream.seek(meta_frame['offset_points'] * POINT_DTYPE.itemsize)
    raw = stream.read(count * POINT_DTYPE.itemsize)
    if len(raw) != count * POINT_DTYPE.itemsize:
        raise ValueError('truncated points.bin')
    rows = np.frombuffer(raw, dtype=POINT_DTYPE)
    xyz = np.stack([rows['x'],rows['y'],rows['z']],axis=1)
    xyz = xyz[np.isfinite(xyz).all(axis=1)]
    xyz = xyz.astype(np.float64) @ rotation.T
    xyz[:,2] += offset
    return xyz, count


def full_panel(xyz, frame, center, size=(380,470)):
    w,h = size
    canvas = np.zeros((h,w,3), dtype=np.uint8)
    canvas[:] = (9,17,26)
    def coords(points):
        p = np.asarray(points,dtype=float).reshape(-1,3)
        x,y,z = p[:,0]-center[0], p[:,1]-center[1], p[:,2]
        return np.rint(np.column_stack((w/2 + (y*.75-x*.55)*51,
            h*.69 + (x*.30+y*.33-z*.85)*51))).astype(int)
    def plot(points, colour, radius):
        xy=coords(points)
        ok=(xy[:,0]>=radius)&(xy[:,0]<w-radius)&(xy[:,1]>=radius)&(xy[:,1]<h-radius)
        xy=xy[ok]
        for dx in range(-radius+1,radius):
            for dy in range(-radius+1,radius):
                canvas[xy[:,1]+dy,xy[:,0]+dx]=colour
        return int(ok.sum())
    shown=plot(xyz,(87,122,137),1)
    plot(np.asarray(frame['tg'],dtype=float).reshape(-1,3)/100.,(70,232,154),2)
    image=Image.fromarray(canvas)
    if frame['bb']:
        x0,y0,z0,x1,y1,z1=np.asarray(frame['bb'],dtype=float)/100.
        corners=coords([[x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0],
                        [x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1]])
        draw=ImageDraw.Draw(image)
        for a,b in base.EDGES:
            draw.line((tuple(corners[a]),tuple(corners[b])),fill=(94,255,170),width=2)
    return image,shown


def target_position(row):
    """Current measured target median in leveled display coordinates, metres."""
    c, z = row.get('c'), row.get('hm')
    if not row.get('tid') or not row.get('n') or not isinstance(c, list) or len(c) != 2:
        return None
    values = [c[0], c[1], z]
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in values):
        return None
    return [c[0]/100., c[1]/100., z]


def posture(row, level):
    if level == 2: return '规则确认倒地'
    if level == 1: return '疑似倒地'
    if not row.get('tid') or not row.get('n'): return '动作未知'
    state = row.get('st')
    if state != 'unknown': return base.STATES.get(state, '动作未知')
    box, hm, top = row.get('bb'), row.get('hm'), row.get('ht')
    if (isinstance(box, list) and len(box) == 6 and isinstance(hm, (int,float))
            and isinstance(top, (int,float)) and math.isfinite(hm) and math.isfinite(top)
            and hm >= .9 and top >= 1.4 and box[5]-box[2] >= 100):
        return '站立候选'
    return '动作未知'


def label_position(frame, center, panel):
    """Anchor the label near the current box in each displayed projection."""
    box=frame.get('bb')
    if not box or len(box)!=6: return None
    x0,y0,z0,x1,y1,z1=np.asarray(box,dtype=float)/100.
    if panel == 0:
        x,y,z=(x0+x1)/2-center[0],(y0+y1)/2-center[1],z1
        px=190+(y*.75-x*.55)*51
        py=470*.69+(x*.30+y*.33-z*.85)*51
    else:
        scale=380/4.2
        px=190+(((y0+y1)/2-center[1]) if panel==1 else ((x0+x1)/2-center[0]))*scale
        py=470-35-(z1+.2)*scale
    if not math.isfinite(px) or not math.isfinite(py): return None
    return max(4,min(224,int(px)-30)),max(4,min(440,int(py)-26))


def render(row, xyz, title, seq, center, camera_dir, fonts, level):
    small,label,heading=fonts
    im=Image.new('RGB',(WIDTH,HEIGHT),(7,13,20))
    d=ImageDraw.Draw(im)
    d.text((25,23),'LIDAR  /  人体动作离线回放',font=small,fill=(122,170,159))
    d.text((25,58),title,font=heading,fill=(236,244,245))
    d.text((1470,70),'%02d / 04'%seq,font=label,fill=(120,156,157))
    boxes=[(20,160),(415,160),(810,160),(1205,160)]
    for (x,y),caption in zip(boxes,['完整点云 · 3D','正面点云','侧面点云','相机画面']):
        d.rounded_rectangle((x,y-38,x+380,y+470),radius=10,fill=(15,24,34),outline=(39,57,69))
        d.text((x+13,y-31),caption,font=small,fill=(185,208,212))
    scene,shown=full_panel(xyz,row,center)
    im.paste(scene,boxes[0])
    im.paste(base.cloud_panel(row,'front',center,size=(380,470)),boxes[1])
    im.paste(base.cloud_panel(row,'side',center,size=(380,470)),boxes[2])
    pos=target_position(row)
    if row.get('tid') and row.get('n'):
        for panel in range(3):
            point=label_position(row,center,panel)
            if point is not None:
                x,y=boxes[panel][0]+point[0],boxes[panel][1]+point[1]
                label_text='人体候选 '+str(row['tid'])
                rect=d.textbbox((x,y),label_text,font=small)
                d.rounded_rectangle((rect[0]-3,rect[1]-2,rect[2]+3,rect[3]+2),radius=3,fill=(9,36,28))
                d.text((x,y),label_text,font=small,fill=(139,255,189))
    if row['cam']:
        camera=Image.open(camera_dir/('c%03d.jpg'%row['cam'][0])).convert('RGB')
        camera=ImageOps.contain(camera,(380,470),method=Image.Resampling.LANCZOS)
        im.paste(camera,(1205+(380-camera.width)//2,160+(470-camera.height)//2))
    else:
        d.text((1270,350),'相机帧不可用',font=label,fill=(130,150,160))
    alert=level > 0
    state=posture(row,level)
    d.rounded_rectangle((20,660,1585,738),radius=12,
        fill=(69,22,27) if alert else (18,31,38),outline=(170,54,65) if alert else (44,70,75))
    d.text((46,682),'状态  '+state,font=label,fill=(255,121,126) if alert else (196,224,216))
    d.text((1220,682),'倒地报警' if level == 2 else '疑似倒地报警' if alert else '未触发报警',font=label,
           fill=(255,121,126) if alert else (138,172,170))
    d.text((22,770),'离线演示 · 确认为规则判定 · 相机按接收时间配对',font=small,fill=(110,141,151))
    d.text((1455,770),'%05.1f s'%row['t'],font=small,fill=(110,141,151))
    coords=('位置：未知' if row.get('tid') and row.get('n') else '位置：未锁定') if pos is None else '人体候选  %s  ·  配平坐标 (m)   X %.2f   Y %.2f   Z %.2f' % (row['tid'],*pos)
    d.text((22,809),coords,font=small,fill=(154,211,190))
    return im,shown


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--evidence',type=Path,required=True)
    args=p.parse_args()
    args.evidence.mkdir(parents=True,exist_ok=False)
    if args.out.exists(): raise FileExistsError(args.out)
    fonts=(ImageFont.truetype(base.FONT,19),ImageFont.truetype(base.BOLD,24),ImageFont.truetype(base.BOLD,35))
    cmd=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pixel_format','rgb24',
        '-video_size',f'{WIDTH}x{HEIGHT}','-framerate',str(base.FPS),'-i','pipe:0',
        '-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(args.out)]
    manifest=[]
    with (args.evidence/'ffmpeg.log').open('wb') as log, (args.evidence/'frames.jsonl').open('w',encoding='utf8') as ledger:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        total=0
        try:
            for seq,(name,title) in enumerate(base.SESSIONS,1):
                src=base.SOURCE/('replay_'+name)
                raw=base.ROOT/'data/sessions'/('cap_20261028_'+name)
                rows=base.load_records(src/'data/frames.js')
                summary=json.loads((src/'SUMMARY.json').read_text(encoding='utf8'))
                meta=json.loads((raw/'meta.json').read_text(encoding='utf8'))
                if len(rows)!=len(meta['frames']) or sha(raw/'meta.json')!=summary['source']['meta_sha256'] or sha(raw/'points.bin')!=summary['source']['points_sha256']:
                    raise ValueError('source mismatch: '+name)
                ground=summary['ground']; rotation=basis(ground['normal'])
                center=(summary['display']['view']['tx'],summary['display']['view']['ty'])
                observer=DemoAlert(); first=None; confirmed=None; start=total
                with (raw/'points.bin').open('rb') as stream:
                    for row,count in zip(rows,base.repeats(rows)):
                        xyz,raw_count=read_xyz(stream,meta['frames'][row['i']],rotation,ground['offset_m'])
                        level=max(observer.update(row),int(row['st'] in ('suspected','confirmed')))
                        active=level > 0
                        if active and first is None: first=row['i']
                        if level == 2 and confirmed is None: confirmed=row['i']
                        image,visible=render(row,xyz,title,seq,center,src/'camera',fonts,level)
                        if row['i'] in (0,len(rows)//2,len(rows)-1) or (active and row['i']==first) or row['i']==confirmed:
                            image.save(args.evidence/(name+'_'+str(row['i'])+'.png'))
                        ledger.write(json.dumps(dict(session=name,frame=row['i'],time=row['t'],source_count=raw_count,
                            finite_count=len(xyz),visible_3d_count=visible,track=row['tid'],state=row['st'],
                            active=active,level=level,posture=posture(row,level),position_m=target_position(row),
                            camera=row['cam'],video_first_frame=total,repeats=count),ensure_ascii=False)+'\n')
                        pixels=image.tobytes()
                        for _ in range(count): proc.stdin.write(pixels)
                        total+=count
                if sha(raw/'points.bin')!=summary['source']['points_sha256']:
                    raise ValueError('source changed: '+name)
                manifest.append(dict(session=name,source_frames=len(rows),video_first_frame=start,
                    video_frames=total-start,first_alert_frame=first,first_rule_confirmation_frame=confirmed,
                    points_sha256=summary['source']['points_sha256']))
                print(name,len(rows),'first alert',first,'rule confirmation',confirmed,flush=True)
        finally:
            proc.stdin.close(); code=proc.wait()
        if code: raise RuntimeError('ffmpeg failed: %s'%code)
    (args.evidence/'MANIFEST.json').write_text(json.dumps(dict(fps=base.FPS,total_video_frames=total,
        sessions=manifest,video_sha256=sha(args.out),ground_physical_verified=False,
        alert='offline geometric comparison, rule confirmation is not verified human fall'),ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__': main()
