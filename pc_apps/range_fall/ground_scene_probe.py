"""Bounded diagnostic capture: USB JPEGs and 28 ROS clouds, no service changes.

The NPZ preserves wire bytes and decoded rows. RGB reception times are not
hardware synchronization or camera/LiDAR extrinsics. No online ground is set.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.request

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
sys.path.insert(0, str(ROOT / 'pc_apps/console'))
from joint_capture import jpeg_frames


REMOTE = r'''
import hashlib,io,json,sys,threading,time
import numpy as np
import rospy
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import String
sys.path.insert(0,sys.argv[1]+'/src/human_fall_detection')
from core.range_live import pointcloud_rows
rospy.init_node('ground_scene_diagnostic',anonymous=True,disable_signals=True)
frames=[];states=[];lock=threading.Lock();ready=threading.Event();target=int(sys.argv[2])
def cloud(msg):
    with lock:
        if len(frames)>=target:return
        h=msg.header
        if frames and h.seq!=frames[-1][0].header.seq+1:frames[:]=[]
        frames.append((msg,time.time_ns()))
        if len(frames)==target:ready.set()
def state(msg):
    with lock:
        states.append(dict(received_unix_ns=time.time_ns(),payload=json.loads(msg.data)))
        if len(states)>5:del states[0]
subs=[rospy.Subscriber('/innolidar_points',PointCloud2,cloud,queue_size=32,buff_size=2**26),
      rospy.Subscriber('/single_target_live/state',String,state,queue_size=2)]
ok=ready.wait(max(20,target/8+10))
for sub in subs:sub.unregister()
with lock:captured=list(frames);status=list(states)
rospy.signal_shutdown('bounded diagnostic done')
if not ok:raise RuntimeError('requested consecutive clouds not received')
arrays={};headers=[]
for i,(msg,received) in enumerate(captured):
    arrays['rows_%03d'%i]=pointcloud_rows(msg)
    arrays['wire_%03d'%i]=np.frombuffer(msg.data,dtype=np.uint8)
    h=msg.header
    headers.append(dict(seq=h.seq,sec=h.stamp.secs,nsec=h.stamp.nsecs,frame_id=h.frame_id,
        received_unix_ns=received,width=msg.width,height=msg.height,point_step=msg.point_step,
        row_step=msg.row_step,is_bigendian=msg.is_bigendian,
        fields=[dict(name=f.name,offset=f.offset,datatype=f.datatype,count=f.count) for f in msg.fields],
        wire_sha256=hashlib.sha256(msg.data).hexdigest()))
arrays['metadata']=np.frombuffer(json.dumps(dict(headers=headers,states=status,release=sys.argv[1],
    capture_clock='board time.time_ns reception; device clock offset UNKNOWN')).encode(),dtype=np.uint8)
buffer=io.BytesIO();np.savez_compressed(buffer,**arrays)
sys.stdout.buffer.write(buffer.getvalue());sys.stdout.buffer.flush()
'''


def write_json(path, value):
    with Path(path).open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)


def safe_output(out):
    out = Path(out).resolve()
    for protected in (ROOT / 'data', ROOT / 'captures'):
        protected = protected.resolve()
        if out == protected or protected in out.parents:
            raise ValueError('diagnostic output must be outside data and captures')
    return out


def capture_camera(url, out):
    images = []
    start = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            for jpeg in jpeg_frames(response):
                now = time.monotonic()
                if not images or now - images[-1]['received_mono_s'] >= .7:
                    name = 'usb_%02d.jpg' % len(images)
                    (out / name).write_bytes(jpeg)
                    images.append(dict(file=name, received_mono_s=now,
                        received_unix_ns=time.time_ns(), sha256=hashlib.sha256(jpeg).hexdigest()))
                if len(images) >= 8 or now-start > 12:
                    break
        return dict(images=images, clock='PC reception; hardware sync/extrinsics UNKNOWN')
    except (OSError, ValueError) as exc:
        return dict(images=images, error=str(exc))


def capture(host, release, out, camera_url, frames=28):
    out = safe_output(out)
    if not 28 <= frames <= 128:
        raise ValueError('diagnostic frame count must be between 28 and 128')
    out.mkdir(parents=True, exist_ok=False)
    command = "docker exec -i slam-localization bash -c " + shlex.quote(
        '. /opt/ros/noetic/setup.bash; . /root/catkin_ws/devel/setup.bash; python3 -B -W error - '
        + shlex.quote(release) + ' ' + str(frames))
    with ThreadPoolExecutor(max_workers=1) as pool:
        camera = pool.submit(capture_camera, camera_url, out)
        result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', host, command],
            input=REMOTE.encode(), capture_output=True, timeout=90)
        (out / 'remote_stderr.log').write_bytes(result.stderr)
        write_json(out / 'camera.json', camera.result())
    if result.returncode:
        raise RuntimeError('ROS capture failed; see remote_stderr.log')
    # Validate before giving the bytes the successful capture filename.
    with np.load(BytesIO(result.stdout), allow_pickle=False) as archive:
        metadata = json.loads(archive['metadata'].tobytes())
        for i, header in enumerate(metadata['headers']):
            if hashlib.sha256(archive['wire_%03d' % i].tobytes()).hexdigest() != header['wire_sha256']:
                raise ValueError('wire checksum mismatch')
    (out / 'clouds.npz').write_bytes(result.stdout)
    write_json(out / 'capture.json', dict(**metadata,
        archive_sha256=hashlib.sha256(result.stdout).hexdigest(),
        source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        no_services_changed=True, physical_ground_truth='UNKNOWN'))
    print(json.dumps(dict(frames=len(metadata['headers']), bytes=len(result.stdout), out=str(out))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='ldiar-wel')
    parser.add_argument('--release', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--camera-url', default='http://192.168.31.58:8081/stream')
    parser.add_argument('--frames', type=int, default=28)
    args = parser.parse_args()
    capture(args.host, args.release, args.out, args.camera_url, args.frames)


if __name__ == '__main__':
    main()
