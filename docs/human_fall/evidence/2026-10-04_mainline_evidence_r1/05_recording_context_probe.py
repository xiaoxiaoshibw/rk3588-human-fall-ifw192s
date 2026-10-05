"""Read bounded existing config/log locations; no automatic recording-time binding."""
import datetime
import hashlib
import json
from pathlib import Path

files=[Path('/root/catkin_ws/src/inno_lidar_ros/config/config.yaml'),
       Path('/tmp/lidar.log'),Path('/var/log/inno_lidar.log')]
records=[]
for path in files:
    item=dict(path=str(path),exists=path.is_file(),recording_binding='unknown')
    if path.is_file():
        h=hashlib.sha256();snippets=[];following=0
        with path.open('rb') as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
        with path.open('r',encoding='utf8',errors='replace') as handle:
            for index,line in enumerate(handle):
                if 'Transform Parameters' in line or 'extrinsic:' in line:
                    following=12
                if following and len(snippets)<120:
                    snippets.append(dict(line=index+1,text=line.rstrip()));following-=1
        stat=path.stat()
        item.update(sha256=h.hexdigest(),size=stat.st_size,
            mtime_utc=datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
            extracted_transform_blocks=snippets,
            reason='mtime/current or retained log block alone lacks original recording process/config SHA binding')
    records.append(item)
config_dir=Path('/root/catkin_ws/src/inno_lidar_ros/config')
archives=[dict(name=p.name,size=p.stat().st_size) for p in config_dir.glob('config.yaml*') if p.is_file()]
print(json.dumps(dict(kind='bounded_recording_context_observation',files=records,
    config_archive_names=archives,from_to_measured=False,ground_region_identity=False,
    recording_config_binding='unknown',physical_verified=False),allow_nan=False))
