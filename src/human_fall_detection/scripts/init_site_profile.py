#!/usr/bin/env python3
"""Create an immutable site profile for one installation.

The profile is deliberately separate from the code release: a release answers
"which code", the profile answers "which place, which input, which ground /
background / display artifacts, and are they applicable". Code rollback must not
silently change the site, and a site change must not silently change the code.

Refusals (by design):

* a missing or unreadable artifact,
* an artifact whose ``kind`` is not the expected one,
* a display ground that claims ``runtime_eligible`` / ``physical_verified``,
* any attempt to mark the profile physically verified -- software format checks
  never prove a physical installation. That flag stays ``false`` and the
  unknowns stay listed until human/physical evidence exists.

Usage::

    python3 init_site_profile.py --site-id site_a --scene-id scene_1 \
        --ground ground.json --background background.json \
        --display-ground display_ground.json --out site_a.json
"""

import argparse
import hashlib
import json
import os
import sys
import time

SCHEMA_VERSION = 1


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def artifact(path, label, expected_kind):
    if not path:
        raise SystemExit('%s is required' % label)
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise SystemExit('%s not found: %s' % (label, path))
    payload = load_json(path)
    if expected_kind and payload.get('kind') != expected_kind:
        raise SystemExit('%s kind is %r, expected %r'
                         % (label, payload.get('kind'), expected_kind))
    return {'path': path, 'sha256': sha256_file(path), 'kind': payload.get('kind'),
            'bytes': os.path.getsize(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--site-id', required=True)
    parser.add_argument('--scene-id', required=True)
    parser.add_argument('--ground', required=True)
    parser.add_argument('--background', required=True)
    parser.add_argument('--display-ground', required=True)
    parser.add_argument('--calibration', default=None)
    parser.add_argument('--install-location', default='')
    parser.add_argument('--install-note', default='')
    parser.add_argument('--cloud-topic', default='/innolidar_points')
    parser.add_argument('--imu-topic', default='/inno_imu')
    parser.add_argument('--device-topic', default='/device_status')
    parser.add_argument('--frame-id', default='innolidar')
    parser.add_argument('--expected-mode', default='unknown',
                        choices=('live_lidar', 'pcap', 'unknown'))
    parser.add_argument('--work-area', default=None,
                        help='JSON object with the effective working volume; omit = unknown')
    parser.add_argument('--scene-artifact', default=None,
                        help='repository-relative artifact directory this profile is based on')
    parser.add_argument('--unknowns', action='append', default=[],
                        help='repeatable: an explicit unknown for this installation')
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)

    ground = artifact(args.ground, 'ground', 'ground_plane')
    background = artifact(args.background, 'background', None)
    display = artifact(args.display_ground, 'display_ground', 'display_ground_candidate')
    display_payload = load_json(display['path'])
    if display_payload.get('runtime_eligible') is not False:
        raise SystemExit('display ground must not be runtime_eligible')
    if display_payload.get('physical_verified') is not False:
        raise SystemExit('display ground must not claim physical_verified')
    if display_payload.get('ground_sha256') != ground['sha256']:
        raise SystemExit('display ground was built from a different ground artifact')
    geometry = {'ground': dict(ground, source=args.scene_artifact or ground['path']),
                'background': dict(background,
                                   source=args.scene_artifact or background['path']),
                'display_ground': dict(display,
                                       source=args.scene_artifact or display['path'])}
    if args.calibration:
        geometry['calibration'] = artifact(args.calibration, 'calibration', None)

    unknowns = list(args.unknowns)
    for entry in ('physical installation / leveling verification',
                  'point-level human ground truth',
                  'identity correctness rate',
                  'real fall effect'):
        if entry not in unknowns:
            unknowns.append(entry)

    profile = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'site_profile',
        'site_id': args.site_id,
        'scene_id': args.scene_id,
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'install': {'location': args.install_location, 'note': args.install_note},
        'input': {
            'cloud_topic': args.cloud_topic,
            'imu_topic': args.imu_topic,
            'device_topic': args.device_topic,
            'frame_id': args.frame_id,
            'expected_mode': args.expected_mode,
        },
        'geometry': geometry,
        'work_area': json.loads(args.work_area) if args.work_area else None,
        'applicability': {
            'scene_specific': True,
            'same_installation': None,
            'physical_verified': False,
            'runtime_eligible': False,
            'scene_artifact': args.scene_artifact,
            'unknowns': unknowns,
        },
    }
    from release_config import check_profile_data, profile_failures
    _, checks = check_profile_data(profile)
    failures = profile_failures(checks)
    if failures:
        raise SystemExit('site profile failed validation: %s'
                         % ', '.join(item['name'] for item in failures))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as handle:
        json.dump(profile, handle, sort_keys=True, indent=1, ensure_ascii=False)
        handle.write('\n')
    print(json.dumps({'out': os.path.abspath(args.out),
                      'site_id': args.site_id,
                      'ground_sha256': ground['sha256'],
                      'background_sha256': background['sha256'],
                      'display_ground_sha256': display['sha256']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
