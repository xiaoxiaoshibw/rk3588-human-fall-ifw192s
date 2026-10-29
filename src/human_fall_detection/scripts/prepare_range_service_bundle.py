#!/usr/bin/env python3
"""Immutable recognition-only bundle. Never deploys, activates or starts anything."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import tarfile


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    for protected in (root/'data', root/'captures'):
        if output == protected or protected in output.parents:
            raise ValueError('bundle output must be outside data/captures')
    names = [p.relative_to(root).as_posix() for p in (root/'src/human_fall_detection/core').rglob('*.py')]
    names += ['src/human_fall_detection/scripts/range_service_node.py',
              'src/human_fall_detection/scripts/sensor_health.py',
              'src/human_fall_detection/config/range_service_v1.json',
              'src/human_fall_detection/launch/range_service.launch',
              'src/human_fall_detection/setup.py', 'src/human_fall_detection/CMakeLists.txt',
              'src/human_fall_detection/package.xml']
    names += ['src/inno_lidar_ros/config/ifw192s/ifw192s_'+kind+'_192x256.csv' for kind in ('azimuth', 'elevation')]
    files = {name: (root/name).read_bytes() for name in sorted(names) if '__pycache__' not in name}
    for name, raw in files.items():
        if name.endswith('.py'):
            ast.parse(raw.decode('utf8'), filename=name, feature_version=(3, 8))
    manifest = {n: dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest()) for n, b in files.items()}
    identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    release = dict(kind='range_recognition_only', protocol='range_recognition/1', release_id=identity,
        entry='src/human_fall_detection/scripts/range_service_node.py',
        config='src/human_fall_detection/config/range_service_v1.json',
        runtime=dict(python='3.8.10', numpy='1.17.4', dependencies=['stdlib', 'numpy', 'ROS1 rospy/rosgraph/sensor_msgs/std_msgs']),
        compatibility='Python3.8 syntax checked; target runtime execution/performance must be measured separately',
        canonical_state_topic='/single_target_live/state', confirmed_enabled=False,
        background='not_declared; explicit next-50-empty-frames initialization required',
        ground='not_loaded; one asynchronous 25+3 fit supported after explicit initialization',
        excluded=['driver', 'capture', 'pages', 'PC bridge', 'Qt lifecycle', 'persisted PC RAM background'])
    files['MANIFEST.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    files['RELEASE.json'] = json.dumps(release, sort_keys=True, indent=2).encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w') as tar:
        for name, raw in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size, member.mode, member.mtime = len(raw), 0o644, 0
            tar.addfile(member, io.BytesIO(raw))
    return dict(release=release, sha256=hashlib.sha256(output.read_bytes()).hexdigest(), files=len(files), path=str(output))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.root, a.out), indent=2))
