"""Bounded ROS1 wire codec, shared by ROS and PC transport."""
import struct
from types import SimpleNamespace as NS


def parse_cloud_header(raw):
    """Lightweight ROS1 Header parser (first ~40 bytes only, zero payload copy)."""
    if len(raw) < 16 or len(raw) > 32 * 1024 * 1024:
        raise ValueError('invalid or oversized cloud header')
    seq, sec, nsec, size = struct.unpack_from('<IIII', raw, 0)
    if size > 4096 or 16 + size > len(raw):
        raise ValueError('invalid ROS string')
    frame = bytes(raw[16:16 + size]).decode('utf8')
    return NS(seq=seq, frame_id=frame, stamp=NS(secs=sec, nsecs=nsec))


def parse_cloud(raw, zero_copy=False):
    """Bounded ROS1 PointCloud2 reader; preserve the original field layout/rows."""
    if len(raw)>32*1024*1024:raise ValueError('oversized cloud')
    offset=0
    def take(fmt):
        nonlocal offset
        size=struct.calcsize(fmt)
        if offset+size>len(raw):raise ValueError('truncated cloud')
        value=struct.unpack_from(fmt,raw,offset);offset+=size;return value
    def text():
        nonlocal offset
        size,=take('<I')
        if size>4096 or offset+size>len(raw):raise ValueError('invalid ROS string')
        value=bytes(raw[offset:offset+size]).decode('utf8');offset+=size;return value
    seq,sec,nsec=take('<III');frame=text();height,width,n=take('<III')
    if n>128 or nsec>=1000000000 or not frame or width*height>262144 or not width or not height:
        raise ValueError('invalid header/dimensions')
    fields=[]
    for _ in range(n):
        name=text();start,kind,count=take('<IBI');fields.append(NS(name=name,offset=start,datatype=kind,count=count))
    big,step,stride,size=take('<?III')
    if size>32*1024*1024 or offset+size+1!=len(raw):raise ValueError('invalid cloud payload length')
    data=memoryview(raw)[offset:offset+size] if zero_copy else raw[offset:offset+size]
    offset+=size;dense,=take('<?')
    return NS(header=NS(seq=seq,frame_id=frame,stamp=NS(secs=sec,nsecs=nsec)),height=height,width=width,
              fields=fields,is_bigendian=big,point_step=step,row_step=stride,data=data,is_dense=dense)


