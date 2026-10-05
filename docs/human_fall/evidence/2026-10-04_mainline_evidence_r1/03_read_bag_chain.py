"""Independent read-only original ROS bag -> canonical 28-byte row evidence.

Does not import/run the project's extractor, create files, or access ROS topics.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

sys.path.insert(0,'/opt/ros/noetic/lib/python3/dist-packages')
import rosbag

PATH=Path('/root/catkin_ws/captures_remote/cap_20261002_163621.bag')
EXPECTED='bbbc0c00122c68c9c71cd6a799e4ee977f839cc4904d733f9660998df0ebd378'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

before=sha(PATH)
if before!=EXPECTED:raise ValueError('bag hash mismatch; do not verify foreign input')
started=time.monotonic()
canonical_dtype=np.dtype({'names':['x','y','z','intensity','ring','timestamp'],
    'formats':['<f4','<f4','<f4','<f4','<u2','<f4'],
    'offsets':[0,4,8,12,16,20],'itemsize':28})
fields_expected=[('x',0,7,1),('y',4,7,1),('z',8,7,1),('intensity',12,7,1),
                 ('ring',16,4,1),('timestamp',18,8,1)]
raw_dtype=np.dtype({'names':['x','y','z','intensity','ring','timestamp'],
    'formats':['<f4','<f4','<f4','<f4','<u2','<f8'],
    'offsets':[0,4,8,12,16,18],'itemsize':26})
frames=[];offset=0;bin_hash=hashlib.sha256();xyz_hash=hashlib.sha256()
time_loss_max=0.;timestamp_range=[None,None]
layouts=set()
with rosbag.Bag(str(PATH),'r') as bag:
    info=bag.get_type_and_topic_info()
    topics={name:dict(type=value.msg_type,count=value.message_count)
            for name,value in info.topics.items()}
    point_topics=[name for name,value in topics.items() if value['type']=='sensor_msgs/PointCloud2']
    if point_topics!=['/innolidar_points']:
        raise ValueError('ambiguous/foreign PointCloud2 topic set')
    for topic,msg,t in bag.read_messages(topics=point_topics):
        actual=[(f.name,f.offset,f.datatype,f.count) for f in msg.fields]
        if actual!=fields_expected or msg.point_step!=26 or msg.is_bigendian:
            raise ValueError('unsupported/mismatched source layout')
        if msg.row_step!=msg.width*msg.point_step or len(msg.data)!=msg.height*msg.row_step:
            raise ValueError('row padding/data length mismatch')
        n=msg.width*msg.height
        raw=np.frombuffer(msg.data,dtype=raw_dtype,count=n)
        xyz=np.column_stack([raw[name] for name in ('x','y','z')]).astype('<f4',copy=False)
        finite=np.all(np.isfinite(xyz),axis=1)
        selected=raw[finite]
        canon=np.zeros(len(selected),dtype=canonical_dtype)
        for name in canonical_dtype.names:canon[name]=selected[name]
        blob=canon.tobytes()
        canonical_xyz=xyz[finite].tobytes()
        bin_hash.update(blob);xyz_hash.update(canonical_xyz)
        ts=selected['timestamp'];good=np.isfinite(ts)
        if np.any(good):
            low=float(ts[good].min());high=float(ts[good].max())
            timestamp_range[0]=low if timestamp_range[0] is None else min(low,timestamp_range[0])
            timestamp_range[1]=high if timestamp_range[1] is None else max(high,timestamp_range[1])
            time_loss_max=max(time_loss_max,float(np.abs(ts[good]-canon['timestamp'][good].astype(np.float64)).max()))
        frames.append(dict(ordinal=len(frames),seq=int(msg.header.seq),
            stamp_sec=int(msg.header.stamp.secs),stamp_nanosec=int(msg.header.stamp.nsecs),
            frame_id=msg.header.frame_id,offset_points=offset,count_points=len(selected),
            dropped_points=n-len(selected),bag_time_sec=t.to_sec(),
            width=int(msg.width),height=int(msg.height),row_step=int(msg.row_step),
            raw_xyz_sha256=hashlib.sha256(canonical_xyz).hexdigest(),
            canonical_frame_sha256=hashlib.sha256(blob).hexdigest()))
        offset+=len(selected)
after=sha(PATH)
if after!=before:raise ValueError('original bag changed while reading')
print(json.dumps(dict(kind='original_bag_canonical_chain_observation',schema=1,
    source=dict(path=str(PATH),sha256_before=before,sha256_after=after,size=PATH.stat().st_size),
    original_layout=dict(fields=fields_expected,point_step=26,is_bigendian=False,
        row_padding_bytes=0,xyz_original_float32=True),
    canonical_layout=dict(stride=28,offsets=[0,4,8,12,16,20],padding_offsets=[18,24],
        timestamp_conversion='float64@18 -> float32@20; lossy, no unit or clock claim'),
    canonical_bin_sha256=bin_hash.hexdigest(),canonical_xyz_sha256=xyz_hash.hexdigest(),
    topics=topics,frames=frames,total_points=offset,total_dropped_points=sum(f['dropped_points'] for f in frames),
    source_timestamp_raw_range=timestamp_range,max_timestamp_numeric_conversion_error=time_loss_max,
    timestamp_units_verified=False,physical_verified=False,recording_config_binding='unknown',
    elapsed_s=time.monotonic()-started,python=sys.version,numpy=np.__version__),allow_nan=False))
