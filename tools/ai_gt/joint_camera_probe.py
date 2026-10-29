"""Inspect recorded RGB on the existing RK3588 NPU, with no board-side files.

Reception-time pairing is only a diagnostic. Unknown clock offset, capture
latency and missing extrinsics forbid turning these boxes into LiDAR labels.
"""
import argparse
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shlex
import subprocess

import numpy as np
from PIL import Image, ImageDraw

from membership_probe import ROOT, sha, write


REMOTE = r'''
import base64,hashlib,json,sys,time
import cv2
import numpy as np
from rknnlite.api import RKNNLite
model='/home/wel/yolov8n_v2.rknn'
request=json.load(sys.stdin)
engine=RKNNLite()
results=[]
try:
    assert engine.load_rknn(model)==0
    assert engine.init_runtime()==0
    for item in request:
        img=cv2.imdecode(np.frombuffer(base64.b64decode(item['jpeg']),np.uint8),cv2.IMREAD_COLOR)
        if img is None:raise ValueError('invalid JPEG')
        h,w=img.shape[:2];r=min(640/w,640/h)
        nw,nh=int(round(w*r)),int(round(h*r));dx,dy=(640-nw)//2,(640-nh)//2
        canvas=np.full((640,640,3),114,np.uint8)
        canvas[dy:dy+nh,dx:dx+nw]=cv2.resize(img,(nw,nh))
        inp=np.expand_dims(canvas[:,:,::-1].astype(np.float32)/255.,0)
        start=time.perf_counter();out=engine.inference(inputs=[inp]);elapsed=time.perf_counter()-start
        if len(out)!=1 or list(out[0].shape)!=[1,84,8400]:raise ValueError('unexpected model layout')
        pred=out[0][0].T;scores=pred[:,4:].max(1);cls=pred[:,4:].argmax(1)
        keep=(scores>=.25)&(cls==0);p=pred[keep];scores=scores[keep]
        boxes=np.column_stack((p[:,0]-p[:,2]/2,p[:,1]-p[:,3]/2,p[:,2],p[:,3]))
        selected=cv2.dnn.NMSBoxes(boxes.tolist(),scores.tolist(),.25,.45)
        detections=[]
        for i in np.asarray(selected,dtype=int).reshape(-1):
            x,y,bw,bh=boxes[i]
            box=[max(0.,(x-dx)/r),max(0.,(y-dy)/r),min(float(w),(x+bw-dx)/r),min(float(h),(y+bh-dy)/r)]
            detections.append(dict(class_id=0,label='person',confidence=float(scores[i]),xyxy=box))
        results.append(dict(key=item['key'],width=w,height=h,inference_s=elapsed,people=detections))
    with open(model,'rb') as f:model_sha=hashlib.sha256(f.read()).hexdigest()
    print('PROBE_JSON='+json.dumps(dict(model=model,model_sha256=model_sha,results=results,
        numpy=np.__version__,opencv=cv2.__version__)))
finally:engine.release()
'''


def nearest_camera(camera, stamp):
    if not np.isfinite(stamp):
        raise ValueError('finite bag time required')
    times = np.asarray([row['recv_unix_ns'] / 1e9 for row in camera])
    if not len(times) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError('strictly increasing finite camera reception times required')
    index = int(np.argmin(np.abs(times - stamp)))
    return index, float(times[index] - stamp)


def recorded_frames(session, indices):
    session = Path(session)
    meta = json.loads((session / 'meta.json').read_text(encoding='utf8'))
    camera = [json.loads(line) for line in (session / 'camera_frames.jsonl').read_text(encoding='utf8').splitlines()]
    result, jpeg = [], []
    with (session / 'camera.mjpeg').open('rb') as stream:
        size = (session / 'camera.mjpeg').stat().st_size
        for fi in indices:
            if type(fi) is not int or not 0 <= fi < len(meta['frames']):
                raise ValueError('frame index outside source')
            index, dt = nearest_camera(camera, meta['frames'][fi]['bag_time_sec'])
            row = camera[index]
            if row['offset'] < 0 or row['length'] < 1 or row['offset'] + row['length'] > size:
                raise ValueError('camera byte range outside source')
            stream.seek(row['offset']); data = stream.read(row['length'])
            if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
                raise ValueError('camera range is not a complete JPEG')
            key = '{}:{}'.format(meta['session_id'], fi)
            jpeg.append(dict(key=key, jpeg=base64.b64encode(data).decode('ascii')))
            result.append(dict(key=key, lidar_frame=fi, camera_index=index,
                reception_minus_bag_s=dt, jpeg_sha256=hashlib.sha256(data).hexdigest()))
    binding = {name: sha(session / name) for name in
               ['meta.json', 'points.bin', 'joint.json', 'camera_frames.jsonl', 'camera.mjpeg']}
    return result, jpeg, binding


def main(sessions, out, host=None):
    out = Path(out).resolve()
    if (ROOT / 'docs/evidence').resolve() not in out.parents or any(
            p.is_symlink() or p.is_junction() for p in [out, *out.parents] if p.exists()):
        raise ValueError('fresh ordinary evidence subdirectory required')
    out.mkdir(parents=True, exist_ok=False)
    rows, images, bindings = [], [], {}
    for session in sessions:
        meta = json.loads((session / 'meta.json').read_text(encoding='utf8'))
        indices = sorted(set(np.linspace(0, len(meta['frames']) - 1, 8).astype(int).tolist()))
        pairs, request, binding = recorded_frames(session, indices)
        rows.extend(pairs);images.extend(request);bindings[session.name] = binding
    inference = None
    if host:
        remote = '/home/wel/yolo-env/bin/python -B -c ' + shlex.quote(REMOTE)
        proc = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', host, remote],
                              input=json.dumps(images), text=True, encoding='utf8',
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        write(out / 'REMOTE_EXECUTION.json', dict(exit_code=proc.returncode,
            stdout=proc.stdout, stderr=proc.stderr, remote_script_sha256=hashlib.sha256(REMOTE.encode()).hexdigest()))
        if proc.returncode:
            raise RuntimeError('existing NPU inference failed; see REMOTE_EXECUTION.json')
        lines = [line for line in proc.stdout.splitlines() if line.startswith('PROBE_JSON=')]
        if len(lines) != 1:
            raise RuntimeError('no unique structured NPU response')
        inference = json.loads(lines[0].split('=', 1)[1])
    lookup = {} if inference is None else {row['key']: row for row in inference['results']}
    montage = Image.new('RGB', (4 * 480, ((len(images) + 3) // 4) * 295), 'white')
    draw = ImageDraw.Draw(montage)
    for i, (row, item) in enumerate(zip(rows, images)):
        img = Image.open(BytesIO(base64.b64decode(item['jpeg']))).convert('RGB')
        scale = 480 / img.width
        img.thumbnail((480, 260))
        x, y = (i % 4) * 480, (i // 4) * 295
        montage.paste(img, (x, y + 30))
        draw.text((x + 5, y + 2), row['key'], fill='black')
        draw.text((x + 5, y + 16), 'reception-bag = {:.3f}s; capture skew UNKNOWN'.format(row['reception_minus_bag_s']), fill='black')
        for detection in lookup.get(row['key'], {}).get('people', []):
            a,b,c,d = detection['xyxy']
            draw.rectangle((x+a*scale,y+30+b*scale,x+c*scale,y+30+d*scale), outline='red', width=2)
    montage.save(out / 'CAMERA.png')
    write(out / 'CAMERA.json', dict(inputs=bindings, pairs=rows, inference=inference,
        source_script_sha256=sha(__file__), pair_basis='nearest reception time vs bag wall time',
        clock_offset_s=None, capture_skew_s=None, lidar_camera_extrinsics=None,
        point_membership='UNKNOWN; RGB boxes are not LiDAR labels'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sessions', type=Path, nargs='+', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--host', help='Existing SSH alias; run installed NPU model in memory')
    args = parser.parse_args()
    main(args.sessions, args.out, args.host)
