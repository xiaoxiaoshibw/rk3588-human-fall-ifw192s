"""Read existing files only; run via docker exec python stdin, never write on board."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

target='cap_20261002_163621.bag'
roots=['/root/catkin_ws/captures_remote','/root/catkin_ws/captures']
records=[]
for root in roots:
    path=Path(root)/target
    item=dict(path=str(path),exists=path.is_file())
    if path.is_file():
        stat=path.stat()
        h=hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
        item.update(size=stat.st_size,mtime_utc=datetime.datetime.fromtimestamp(
            stat.st_mtime,datetime.timezone.utc).isoformat(),sha256=h.hexdigest())
        with path.open('rb') as handle:item['magic']=handle.read(13).decode('ascii',errors='replace')
    records.append(item)
sys.path.insert(0,'/opt/ros/noetic/lib/python3/dist-packages')
config=Path('/root/catkin_ws/src/inno_lidar_ros/config/config.yaml')
print(json.dumps(dict(kind='read_only_existing_bag_probe',targets=records,
    rosbag_module_available=importlib.util.find_spec('rosbag') is not None,
    current_config=dict(path=str(config),exists=config.is_file(),
        sha256=hashlib.sha256(config.read_bytes()).hexdigest() if config.is_file() else None,
        recording_binding='unknown; current file is not recording-time proof'))))
