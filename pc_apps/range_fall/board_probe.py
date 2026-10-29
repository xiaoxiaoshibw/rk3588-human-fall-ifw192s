"""Bounded on-board ROS transport check; stops only its own child process.

Run inside an isolated source bundle with the existing ROS environment sourced.
Does not record bags or change running services/configuration.
"""
import argparse
from collections import OrderedDict
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import numpy as np


def key(header):
    return (header.seq, header.stamp.secs, header.stamp.nsecs, header.frame_id)


def distribution(values):
    if not values:
        return dict(n=0)
    return dict(n=len(values), **{k:float(v) for k,v in
                zip(('p50','p95','p99','max'), np.percentile(values, [50,95,99,100]))})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=30)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 120:
        parser.error('seconds must be between 10 and 120')
    args.out.mkdir(parents=True, exist_ok=False)
    package = args.bundle/'src/human_fall_detection'
    sys.path.insert(0, str(package))
    from core.range_live import pointcloud_rows
    from core.range_image import ScanGrid
    import rospy
    from sensor_msgs.msg import Image, PointCloud2
    from std_msgs.msg import String
    tables = args.bundle/'tables'
    az, el = tables/'ifw192s_azimuth_192x256.csv', tables/'ifw192s_elevation_192x256.csv'
    grid = ScanGrid.from_csv(az, el)
    lock = threading.Lock()
    raw, images, states = OrderedDict(), OrderedDict(), OrderedDict()
    input_log, production_log, output_log, errors = [], [], [], []
    phase = ['before']
    message_counts = dict(raw=0, range=0, source_rows=0, valid=0, preview=0, state=0)
    prefix = '/range_image_board_probe_'+str(os.getpid())
    rospy.init_node('range_image_board_observer', anonymous=True, disable_signals=True)

    def trim(mapping, size):
        while len(mapping) > size:
            mapping.popitem(last=False)

    def on_raw(msg):
        received = time.perf_counter()
        with lock:
            raw[key(msg.header)] = msg
            trim(raw, 32)
            input_log.append(dict(phase=phase[0], received_mono_s=received,
                                  seq=msg.header.seq, sec=msg.header.stamp.secs,
                                  nsec=msg.header.stamp.nsecs, points=msg.width*msg.height))
            message_counts['raw'] += 1

    def on_image(msg, name):
        with lock:
            images.setdefault(key(msg.header), {})[name] = msg
            trim(images, 64)
            message_counts[name] += 1

    def on_state(msg):
        try:
            value = json.loads(msg.data)
            with lock:
                message_counts['state'] += 1
                source = value.get('source')
                if value.get('status') in ('ready', 'no_valid_pixels') and source:
                    identity = (source['seq'],source['stamp_sec'],source['stamp_nanosec'],source['frame_id'])
                    states[identity] = value
                    trim(states, 64)
                elif value.get('status') not in ('waiting', 'stale'):
                    errors.append(dict(kind='node_status', detail=value))
        except (ValueError, KeyError) as exc:
            errors.append(dict(kind='invalid_state', detail=str(exc)))

    def on_production(msg):
        try:
            value = json.loads(msg.data)
            with lock:
                production_log.append(dict(phase=phase[0],received_mono_s=time.perf_counter(),payload=value))
        except ValueError as exc:
            errors.append(dict(kind='production_json', detail=str(exc)))

    subscriptions = [rospy.Subscriber('/innolidar_points',PointCloud2,on_raw,queue_size=8,buff_size=2**26),
                     rospy.Subscriber('/single_target_live/state',String,on_production,queue_size=8)]
    for name in ('range','source_rows','valid','preview'):
        subscriptions.append(rospy.Subscriber(prefix+'/'+name,Image,on_image,callback_args=name,
                                              queue_size=8,buff_size=2**24))
    subscriptions.append(rospy.Subscriber(prefix+'/state',String,on_state,queue_size=32))
    child = None
    child_return = None
    started = time.perf_counter()
    deadline = started+10
    verified = 0
    seen = set()
    log = (args.out/'node.log').open('xb')
    try:
        while time.perf_counter() < deadline:
            time.sleep(.05)
        phase[0] = 'during'
        command = [sys.executable,'-u','-B','-W','error',str(package/'scripts/range_image_node.py'),
                   '--azimuth-table',str(az),'--elevation-table',str(el),'--frame-id','innolidar',
                   '--output-prefix',prefix,'--preview','__name:=range_image_board_probe_'+str(os.getpid())]
        (args.out/'COMMAND.json').write_text(json.dumps(command),encoding='utf-8')
        child = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline = time.perf_counter()+args.seconds
        while time.perf_counter() < deadline and child.poll() is None:
            with lock:
                complete = [(identity,dict(images[identity]),value,raw[identity])
                            for identity,value in list(states.items())
                            if identity not in seen and identity in raw and len(images.get(identity,{})) == 4]
            for identity,buffers,status,cloud in complete:
                seen.add(identity)
                record = dict(source=status['source'], status=status, transport=True)
                if len(seen) <= 5 or len(seen) % 30 == 0:
                    # Verification outside the measured child; bounds CPU/memory overhead.
                    frame = grid.decode(pointcloud_rows(cloud), ('independent-transport-check',))
                    actual = {}
                    for name,dtype,shape,encoding in [
                            ('range','<f4',grid.shape,'32FC1'),
                            ('source_rows','<i4',grid.shape,'32SC1'),
                            ('valid','u1',grid.shape,'mono8'),
                            ('preview','u1',grid.shape+(3,),'rgb8')]:
                        msg = buffers[name]
                        if (msg.height != shape[0] or msg.width != shape[1] or msg.encoding != encoding
                                or msg.is_bigendian or len(msg.data) != msg.step*msg.height):
                            raise AssertionError('Image layout mismatch: '+name)
                        actual[name] = np.frombuffer(msg.data,dtype=dtype).reshape(shape)
                    expected_range = frame.range_m[::-1,::-1].astype('<f4')
                    checks = dict(range=bool(np.all((actual['range'] == expected_range)
                                                    | (np.isnan(actual['range']) & np.isnan(expected_range)))),
                                  source_rows=bool(np.array_equal(actual['source_rows'],frame.source_rows[::-1,::-1])),
                                  valid=bool(np.array_equal(actual['valid'],frame.valid[::-1,::-1]*255)))
                    t = np.clip((frame.range_m[frame.valid]-.1)/7.9,0,1)
                    rgb = np.zeros(grid.shape+(3,),dtype='u1')
                    rgb[frame.valid] = np.column_stack((255*(1-t),255*(1-np.abs(2*t-1)),255*t)).astype('u1')
                    checks['preview'] = bool(np.array_equal(actual['preview'],rgb[::-1,::-1]))
                    record['pixel_checks'] = checks
                    record['output_sha256'] = {name:hashlib.sha256(msg.data).hexdigest() for name,msg in buffers.items()}
                    if not all(checks.values()):
                        errors.append(dict(kind='pixel_mismatch',source=status['source'],checks=checks))
                    verified += 1
                    if verified == 1:
                        # Only one image sample, no raw cloud/bag capture.
                        sys.path.insert(0,str(args.bundle/'pc_apps/range_fall'))
                        from depth import png
                        with (args.out/'live_preview.png').open('xb') as image:
                            image.write(png(actual['preview']))
                        (args.out/'PREVIEW_SOURCE.json').write_text(json.dumps(status),encoding='utf-8')
                output_log.append(record)
            time.sleep(.01)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGINT)
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                child.wait(timeout=5)
        child_return = child.returncode if child is not None else None
        log.close()
        phase[0] = 'after'
        end = time.perf_counter()+5
        while time.perf_counter() < end:
            time.sleep(.05)
        for sub in subscriptions:
            sub.unregister()
        rospy.signal_shutdown('bounded validation complete')
        time.sleep(.25)
        for name,records in [('INPUT.jsonl',input_log),('PRODUCTION.jsonl',production_log),('OUTPUT.jsonl',output_log)]:
            with (args.out/name).open('x',encoding='utf-8') as stream:
                for record in records:
                    stream.write(json.dumps(record,allow_nan=False)+'\n')
        def input_stats(phase_name):
            records = [r for r in input_log if r['phase'] == phase_name]
            if len(records) < 2:
                return dict(n=len(records))
            elapsed = records[-1]['received_mono_s']-records[0]['received_mono_s']
            gaps = sum(max(0,b['seq']-a['seq']-1) for a,b in zip(records,records[1:]))
            return dict(n=len(records),arrival_hz=(len(records)-1)/elapsed,seq_gaps=gaps,
                        source_delta_s=(records[-1]['sec']-records[0]['sec'])+(records[-1]['nsec']-records[0]['nsec'])/1e9)
        performance = {k:distribution([r['status'][k] for r in output_log[10:]]) for k in
                       ('adapt_ms','decode_ms','image_pack_ms','conversion_ms','queue_age_ms','local_frame_age_ms','publish_enqueue_ms')}
        summary = dict(input={p:input_stats(p) for p in ('before','during','after')},
                       complete_output_frames=len(output_log),pixel_verified_frames=verified,errors=errors,
                       message_counts=message_counts,child_returncode=child_return,
                       performance=performance,warmup_excluded_output_frames=10,
                       final_node_counters=output_log[-1]['status'] if output_log else None,
                       production_state_messages={p:sum(r['phase']==p for r in production_log) for p in ('before','during','after')},
                       grid_sha256=grid.sha256,environment=dict(python=sys.version,numpy=np.__version__),
                       latency_scope='board CPU and local ROS transport; NOT device acquisition/network/PC display',
                       human_fall_effect='UNKNOWN',own_child_stopped=child is not None and child.poll() is not None)
        with (args.out/'SUMMARY.json').open('x',encoding='utf-8') as stream:
            json.dump(summary,stream,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(summary,ensure_ascii=False))
    if not output_log or verified < 5 or errors or child_return not in (0,-signal.SIGINT):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
