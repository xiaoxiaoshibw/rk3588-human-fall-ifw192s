"""Read-only SSH verification of active bundle, frozen assets and ROS state."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
mapping = {
    "bundle/core/node_runtime.py": "src/human_fall_detection/core/node_runtime.py",
    "bundle/scripts/human_fall_node.py": "src/human_fall_detection/scripts/human_fall_node.py",
    "bundle/scripts/profile_pipeline.py": "src/human_fall_detection/scripts/profile_pipeline.py",
    "bundle/scripts/sensor_health.py": "src/human_fall_detection/scripts/sensor_health.py",
    "bundle/scripts/record_session.py": "src/human_fall_detection/scripts/record_session.py",
    "bundle/config/default.yaml": "src/human_fall_detection/config/default.yaml",
    "bundle/config/human_fall_prod.yaml": "src/human_fall_detection/config/human_fall_prod.yaml",
    "bundle/config/perception.yaml": "src/human_fall_detection/config/perception.yaml",
    "bundle/human_follow_calibration/scripts/calibrate_human_follow.py": "src/human_follow_calibration/scripts/calibrate_human_follow.py",
    "webui/human_fall/index.html": "webui/human_fall/index.html",
    "webui/human_fall/human_fall.js": "webui/human_fall/human_fall.js",
    "webui/human_fall/human_fall_lib.js": "webui/human_fall/human_fall_lib.js",
}
expected = {key: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for key, path in mapping.items()}
remote = r'''
set -e
source /opt/ros/noetic/setup.bash
source /root/catkin_ws/hf07_verify_ws/devel/setup.bash
python3 -B - <<'PY'
import hashlib,json,os,sys,subprocess
from pathlib import Path
release=Path(os.path.realpath('/root/catkin_ws/human_fall_deploy/current'))
assert str(release).startswith('/root/catkin_ws/human_fall_deploy/releases/')
expected=json.loads(EXPECTED_JSON)
hashes={key:hashlib.sha256((release/key).read_bytes()).hexdigest() for key in expected}
for relative in ('bundle','bundle/scripts','bundle/human_follow_calibration/scripts'):
    sys.path.insert(0,str(release/relative))
import core,sensor_health
decoder,_=sensor_health._load_xyz_from_cloud()
pid=Path('/root/catkin_ws/human_fall_deploy/pids/human_fall_node.pid').read_text().strip()
cmd=Path('/proc/'+pid+'/cmdline').read_bytes().replace(bytes([0]),b' ').decode()
env=Path('/proc/'+pid+'/environ').read_bytes().split(bytes([0]))
pythonpath=next((x.split(b'=',1)[1].decode() for x in env if x.startswith(b'PYTHONPATH=')),None)
import rospy
from std_msgs.msg import String
from sensor_msgs.msg import PointCloud2
rospy.init_node('codex_hf09_readonly_check',anonymous=True,disable_signals=True)
state=json.loads(rospy.wait_for_message('/human_fall/state',String,timeout=15).data)
original_cloud=rospy.wait_for_message('/innolidar_points',PointCloud2,timeout=15)
display_cloud=rospy.wait_for_message(state['visualization']['topic'],PointCloud2,timeout=15)
manifest=subprocess.run(['sha256sum','-c','manifest.sha256'],cwd=str(release/'bundle'),capture_output=True,text=True)
report={'release':str(release),'pid':int(pid),'cmdline':cmd,'pythonpath_prefix':pythonpath.split(':')[:3] if pythonpath else None,
        'core_file':core.__file__,'health_file':sensor_health.__file__,
        'decoder_file':sys.modules[decoder.__module__].__file__ if decoder else None,
        'manifest_exit':manifest.returncode,'all_local_hashes_match':hashes==expected,'hashes':hashes,
        'driver_sha256':hashlib.sha256(Path('/root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node').read_bytes()).hexdigest(),
        'old_homepage_sha256':hashlib.sha256(Path('/root/catkin_ws/webui/index.html').read_bytes()).hexdigest(),
        'cloud_density':{'original':original_cloud.is_dense,'display':display_cloud.is_dense},
        'state':{key:state.get(key) for key in ['schema_version','kind','session_id','time_epoch','track_status','fall_status','observability','confirmed_enabled','sensor_quality','visualization','performance']}}
print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
rospy.signal_shutdown('read-only verification completed')
assert report['all_local_hashes_match'] and manifest.returncode==0
assert str(release/'bundle/core') in core.__file__
assert str(release/'bundle/scripts/human_fall_node.py') in cmd
assert report['driver_sha256']=='0286545f64e76f8435d8da20dcc55e3837eac17d1066415148a2a4c5abb6f3c4'
assert report['old_homepage_sha256']=='e68dea5121d06c6fbf2fc2e8fa8ff947c05c6a87ba4635c0511ecf5b6491af5f'
assert state['fall_status']=='unknown' and not state['confirmed_enabled']
assert display_cloud.is_dense==original_cloud.is_dense
PY
'''.replace('EXPECTED_JSON', repr(json.dumps(expected)))
result = subprocess.run(['ssh','ldiar-wel','docker exec -i slam-localization bash -s'],
                        input=remote.encode('utf-8'),capture_output=True,timeout=180)
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
print('OUTER_SSH_EXIT={}'.format(result.returncode))
raise SystemExit(result.returncode)
