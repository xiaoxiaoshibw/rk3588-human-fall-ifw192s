#!/usr/bin/env python3
"""Generate the *effective* runtime configuration for one release + site profile.

Three consumers must agree, so they are all derived from this one place:

* the node (effective YAML: bound ground/background paths + topics + run dir),
* the capture server (effective YAML: ``record_script`` inside the release),
* the page + profiler (``runtime.js`` / ``runtime.json``: topics, version).

The site profile is an immutable snapshot kept outside the code release. This
tool verifies every artifact SHA before it is used; a mismatch is a hard error,
never a silent fallback to an older scene.

Python 3.8 compatible (board 3.8.10), stdlib + PyYAML.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

SCHEMA_VERSION = 1
HF_SUFFIXES = ('candidates', 'state', 'event', 'selection_request', 'selection_ack',
               'display_points')
INPUT_SOURCE_MODES = ('live_lidar', 'pcap', 'unknown')


class ConfigError(RuntimeError):
    pass


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def load_yaml(path):
    import yaml
    with open(path, encoding='utf-8') as handle:
        return yaml.safe_load(handle) or {}


def dump_yaml(data, path):
    import yaml
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    os.makedirs(directory, exist_ok=True)
    handle = tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory,
                                         delete=False, suffix='.tmp')
    try:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, path)


def dump_json(data, path):
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    os.makedirs(directory, exist_ok=True)
    text = json.dumps(data, sort_keys=True, indent=1, ensure_ascii=False)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory,
                                     delete=False, suffix='.tmp') as handle:
        handle.write(text + '\n')
        handle.flush()
        os.fsync(handle.fileno())
        name = handle.name
    os.replace(name, path)


# --------------------------------------------------------------------------
# site profile
# --------------------------------------------------------------------------
def check_profile(profile_path):
    """Return (profile, checks). ``checks`` is a list of {name, ok, detail}."""
    return check_profile_data(load_json(profile_path))


def check_profile_data(profile):
    """Validate a new or saved profile against the node's actual geometry binding."""
    checks = []

    def check(name, ok, detail=None):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        return ok

    check('schema_version', profile.get('schema_version') == SCHEMA_VERSION,
          profile.get('schema_version'))
    check('site_id', bool(profile.get('site_id')), profile.get('site_id'))
    check('scene_id', bool(profile.get('scene_id')), profile.get('scene_id'))
    applicability = profile.get('applicability') or {}
    check('applicability_object', isinstance(applicability, dict))
    check('physical_verified_is_bool',
          isinstance(applicability.get('physical_verified'), bool),
          applicability.get('physical_verified'))
    check('runtime_eligible_is_bool',
          isinstance(applicability.get('runtime_eligible'), bool),
          applicability.get('runtime_eligible'))
    check('unknowns_listed', isinstance(applicability.get('unknowns'), list),
          len(applicability.get('unknowns') or []))
    if applicability.get('runtime_eligible') and not applicability.get('physical_verified'):
        check('runtime_eligible_requires_physical_verification', False,
              'runtime_eligible=true with physical_verified=false')
    geometry = profile.get('geometry') or {}
    artifacts, hashes = {}, {}
    keys = ('ground', 'background', 'display_ground')
    if geometry.get('calibration') is not None:
        keys += ('calibration',)
    for key in keys:
        entry = geometry.get(key)
        if entry is None:
            check('geometry_%s_present' % key, False, 'missing')
            continue
        path = entry.get('path')
        ok = bool(path) and os.path.isfile(path)
        check('geometry_%s_path' % key, ok, path)
        if not ok:
            continue
        actual = _sha256_file(path)
        hashes[key] = actual
        check('geometry_%s_sha256' % key, actual == entry.get('sha256'),
              {'expected': entry.get('sha256'), 'actual': actual})
        try:
            payload = load_json(path)
        except (OSError, ValueError) as exc:
            check('geometry_%s_json' % key, False, str(exc))
            continue
        kind = payload.get('kind') if isinstance(payload, dict) else None
        if isinstance(payload, dict):
            artifacts[key] = payload
        expected_kind = {'ground': 'ground_plane', 'background': None,
                         'display_ground': 'display_ground_candidate',
                         'calibration': 'geometry_calibration'}[key]
        if expected_kind:
            check('geometry_%s_kind' % key, kind == expected_kind, kind)
        if key == 'display_ground' and isinstance(payload, dict):
            check('display_ground_schema_version',
                  type(payload.get('schema_version')) is int
                  and payload['schema_version'] == SCHEMA_VERSION)
            check('display_ground_units', payload.get('units') == 'm')
            check('display_ground_to_frame', payload.get('to_frame') == 'ground_local')
            check('display_ground_not_runtime_eligible',
                  payload.get('runtime_eligible') is False,
                  payload.get('runtime_eligible'))
            check('display_ground_not_physically_verified',
                  payload.get('physical_verified') is False,
                  payload.get('physical_verified'))
    input_block = profile.get('input') or {}
    check('input_cloud_topic', bool(input_block.get('cloud_topic')),
          input_block.get('cloud_topic'))
    check('input_file_configured', 'expected_mode' in input_block,
          input_block.get('expected_mode'))
    required = {'ground', 'display_ground'}
    if geometry.get('calibration') is not None:
        required.add('calibration')
    if required.issubset(artifacts):
        try:
            import numpy as np
            from core.node_runtime import FallNodeCore
            from core.numeric import strict_numeric_array
            frame = input_block.get('frame_id') or 'innolidar'
            # Reuse startup binding, including explicit calibration precedence.
            core = FallNodeCore('profile-check', ground=artifacts['ground'],
                                calibration=artifacts.get('calibration'),
                                expected_frame=frame)
            display = artifacts['display_ground']
            expected_id = (core.calibration or {}).get('calibration_id')
            check('display_ground_calibration_id',
                  expected_id is not None and display.get('calibration_id') == expected_id,
                  {'expected': expected_id, 'actual': display.get('calibration_id')})
            check('display_ground_ground_sha256',
                  display.get('ground_sha256') == hashes['ground'])
            ground = core.ground or {}
            check('display_ground_source_frame',
                  display.get('source_frame') == frame == ground.get('frame')
                  == (core.calibration or {}).get('frames', {}).get('lidar'))
            rotation = strict_numeric_array(display.get('R'), (3, 3), 'display.R')
            translation = strict_numeric_array(display.get('t'), (3,), 'display.t')
            check('display_ground_transform',
                  ground.get('status') == 'valid'
                  and np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-6, rtol=0)
                  and abs(float(np.linalg.det(rotation)) - 1.0) <= 1e-6
                  and np.allclose(rotation[2], ground['normal'], atol=1e-6, rtol=0)
                  and np.allclose(translation, [0.0, 0.0, ground['offset_m']],
                                  atol=1e-6, rtol=0))
        except (TypeError, ValueError, KeyError) as exc:
            check('display_ground_runtime_binding', False, str(exc))
    return profile, checks


def profile_failures(checks):
    return [c for c in checks if not c['ok']]


# --------------------------------------------------------------------------
# node config
# --------------------------------------------------------------------------
def _require_artifact(entry, label):
    path = entry.get('path')
    if not path or not os.path.isfile(path):
        raise ConfigError('%s artifact missing: %s' % (label, path))
    actual = _sha256_file(path)
    if entry.get('sha256') and actual != entry['sha256']:
        raise ConfigError('%s SHA mismatch: expected %s actual %s'
                          % (label, entry['sha256'], actual))
    return os.path.abspath(path), actual


def build_node_config(scene_path, profile_path, run_dir=None, session_id=None):
    scene = load_yaml(scene_path)
    snapshot = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'effective_node_config',
        'generated_wall': time.time(),
        'scene_path': os.path.abspath(scene_path),
        'scene_sha256': _sha256_file(scene_path),
        'profile_path': os.path.abspath(profile_path) if profile_path else None,
        'artifacts': {},
    }
    if profile_path:
        profile, checks = check_profile(profile_path)
        failures = profile_failures(checks)
        snapshot['profile_checks'] = checks
        snapshot['profile_id'] = profile.get('site_id')
        snapshot['scene_id'] = profile.get('scene_id')
        if failures:
            raise ConfigError('site profile failed validation: %s'
                              % ', '.join(c['name'] for c in failures))
        geometry = profile['geometry']
        ground_path, ground_sha = _require_artifact(geometry['ground'], 'ground')
        background_path, background_sha = _require_artifact(
            geometry['background'], 'background')
        cfg_geometry = scene.setdefault('geometry', {})
        cfg_geometry['ground_path'] = ground_path
        cfg_geometry['background_path'] = background_path
        cfg_geometry['calibration_path'] = None
        if geometry.get('calibration'):
            calibration_path, calibration_sha = _require_artifact(
                geometry['calibration'], 'calibration')
            cfg_geometry['calibration_path'] = calibration_path
        else:
            calibration_sha = None
        snapshot['artifacts'] = {
            'ground': {'path': ground_path, 'sha256': ground_sha,
                       'source': geometry['ground'].get('source')},
            'background': {'path': background_path, 'sha256': background_sha,
                           'source': geometry['background'].get('source')},
            'display_ground': {
                'path': os.path.abspath(geometry['display_ground']['path']),
                'sha256': geometry['display_ground'].get('sha256'),
                'source': geometry['display_ground'].get('source')},
        }
        if calibration_sha:
            snapshot['artifacts']['calibration'] = {
                'path': os.path.abspath(geometry['calibration']['path']),
                'sha256': calibration_sha}
        input_block = profile.get('input') or {}
        topics = scene.setdefault('topics', {})
        for key in ('cloud', 'imu', 'device_status'):
            if input_block.get(key + '_topic'):
                topics[key] = input_block[key + '_topic']
        if input_block.get('frame_id'):
            scene.setdefault('checks', {})['expected_cloud_frame'] = \
                input_block['frame_id']
        snapshot['input'] = input_block
        snapshot['applicability'] = profile.get('applicability')
    if run_dir:
        output = scene.setdefault('output', {})
        output['session_dir'] = os.path.abspath(run_dir)
    if session_id:
        scene['session_id'] = session_id
    snapshot['config'] = scene
    snapshot['topics'] = dict(scene.get('topics') or {})
    snapshot['target_mode'] = scene.get('target_mode')
    snapshot['confirmed'] = {
        'mode_verified': False, 'allow_confirmed': False, 'confirmed_enabled': False}
    return scene, snapshot


# --------------------------------------------------------------------------
# capture config
# --------------------------------------------------------------------------
def build_capture_config(template_path, release_root, staging_dir=None,
                         sessions_db=None, port=None):
    config = load_yaml(template_path)
    # Do not write explicit `key: null` into the effective file: the capture
    # service's flat YAML reader keeps "null" as a string, which would make e.g.
    # record_config truthy. Omit unset keys instead.
    config = {key: value for key, value in config.items() if value is not None}
    release_root = os.path.abspath(release_root)
    record_script = os.path.join(release_root, 'src', 'human_fall_detection',
                                 'scripts', 'record_session.py')
    if not os.path.isfile(record_script):
        raise ConfigError('release has no record_session.py: %s' % record_script)
    config['record_script'] = record_script
    if staging_dir:
        config['staging_dir'] = os.path.abspath(staging_dir)
    if sessions_db:
        config['sessions_db'] = os.path.abspath(sessions_db)
    if port:
        config['port'] = int(port)
    for key in ('sigint_grace_sec', 'sigterm_kill_sec'):
        if key not in config:
            raise ConfigError('capture template is missing %s' % key)
    snapshot = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'effective_capture_config',
        'generated_wall': time.time(),
        'template_path': os.path.abspath(template_path),
        'template_sha256': _sha256_file(template_path),
        'release_root': release_root,
        'record_script': record_script,
        'record_script_sha256': _sha256_file(record_script),
        'staging_dir': config.get('staging_dir'),
        'sessions_db': config.get('sessions_db'),
        'grace_sec': config.get('sigint_grace_sec'),
        'kill_sec': config.get('sigterm_kill_sec'),
        'config': config,
    }
    return config, snapshot


# --------------------------------------------------------------------------
# page runtime
# --------------------------------------------------------------------------
def build_page_runtime(config, release, profile=None, source_mode='unknown'):
    topics = dict(config.get('topics') or {})
    state_topic = topics.get('state')
    if not state_topic or not state_topic.endswith('/state'):
        raise ConfigError('node config has no usable state topic: %s' % state_topic)
    prefix = state_topic[:-len('state')]
    for suffix in HF_SUFFIXES:
        expected = prefix + suffix
        if topics.get(suffix) != expected:
            raise ConfigError('topic %s=%r does not match prefix %r'
                              % (suffix, topics.get(suffix), prefix))
    cloud = topics.get('cloud')
    profile_input = (profile or {}).get('input') or {}
    if profile_input.get('cloud_topic') and cloud != profile_input['cloud_topic']:
        raise ConfigError('cloud topic %r != profile %r'
                          % (cloud, profile_input['cloud_topic']))
    geometry = (profile or {}).get('geometry') or {}
    display_ground = geometry.get('display_ground')
    runtime = {
        'schema_version': SCHEMA_VERSION,
        'release_id': release.get('release_id'),
        'page_version': release.get('page_version'),
        'scene_id': (profile or {}).get('scene_id'),
        'site_id': (profile or {}).get('site_id'),
        'scene_artifact': (profile or {}).get('applicability', {}).get('scene_artifact'),
        'prefix': prefix,
        'points': topics.get('display_points') or cloud,
        'display_points': topics.get('display_points') or cloud,
        'raw': cloud,
        'state': state_topic,
        'candidates': topics.get('candidates'),
        'event': topics.get('event'),
        'selection_request': topics.get('selection_request'),
        'selection_ack': topics.get('selection_ack'),
        'ground': 'display_ground.json' if display_ground else None,
        'source_mode': source_mode if source_mode in INPUT_SOURCE_MODES else 'unknown',
        'target_mode': config.get('target_mode'),
        'confirmed_enabled': False,
        'event_geometry_shadow': (release.get('features') or {}).get('event_geometry_shadow') is True,
        'generated_wall': time.time(),
    }
    return runtime


def write_runtime_js(runtime, path):
    body = ('/* generated by release_config.py -- do not edit */\n'
            'window.__HF_RUNTIME__ = %s;\n'
            % json.dumps(runtime, sort_keys=True, ensure_ascii=False))
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=directory,
                                     delete=False, suffix='.tmp') as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
        name = handle.name
    os.replace(name, path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_profile(args):
    profile, checks = check_profile(args.check)
    failures = profile_failures(checks)
    report = {'profile_path': os.path.abspath(args.check), 'site_id': profile.get('site_id'),
              'scene_id': profile.get('scene_id'), 'checks': checks,
              'failures': [c['name'] for c in failures]}
    if args.report:
        dump_json(report, args.report)
    print(json.dumps({'ok': not failures, 'failures': report['failures']}))
    return 0 if not failures else 4


def cmd_node(args):
    scene, snapshot = build_node_config(args.scene, args.profile, args.run_dir,
                                        args.session_id)
    dump_yaml(scene, args.out)
    snapshot['effective_path'] = os.path.abspath(args.out)
    snapshot['effective_sha256'] = _sha256_file(args.out)
    if args.snapshot:
        dump_json(snapshot, args.snapshot)
    print(json.dumps({'out': os.path.abspath(args.out),
                      'sha256': snapshot['effective_sha256'],
                      'topics': snapshot['topics']}))
    return 0


def cmd_capture(args):
    config, snapshot = build_capture_config(args.template, args.release_root,
                                            args.staging_dir, args.sessions_db,
                                            args.port)
    dump_yaml(config, args.out)
    snapshot['effective_path'] = os.path.abspath(args.out)
    snapshot['effective_sha256'] = _sha256_file(args.out)
    if args.snapshot:
        dump_json(snapshot, args.snapshot)
    print(json.dumps({'out': os.path.abspath(args.out),
                      'sha256': snapshot['effective_sha256'],
                      'record_script': snapshot['record_script']}))
    return 0


def cmd_runtime(args):
    config = load_yaml(args.config) if args.config else (load_json(args.config_json)
                                                        if args.config_json else None)
    if config is None:
        raise ConfigError('runtime needs --config or --config-json')
    release = load_json(args.release_json)
    profile = load_json(args.profile) if args.profile else None
    runtime = build_page_runtime(config, release, profile, args.source_mode)
    write_runtime_js(runtime, args.out)
    if args.json_out:
        dump_json(runtime, args.json_out)
    print(json.dumps({'out': os.path.abspath(args.out),
                      'page_version': runtime['page_version'],
                      'release_id': runtime['release_id'],
                      'state': runtime['state']}))
    return 0


def cmd_field(args):
    data = load_json(args.file)
    value = data
    for part in args.name.split('.'):
        if not isinstance(value, dict) or part not in value:
            raise ConfigError('no field %s in %s' % (args.name, args.file))
        value = value[part]
    print('' if value is None else value)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')

    profile = sub.add_parser('profile', help='validate a site profile')
    profile.add_argument('--check', required=True)
    profile.add_argument('--report')
    profile.set_defaults(func=cmd_profile)

    node = sub.add_parser('node', help='materialise the effective node config')
    node.add_argument('--scene', required=True)
    node.add_argument('--profile', default=None)
    node.add_argument('--run-dir', default=None)
    node.add_argument('--session-id', default=None)
    node.add_argument('--out', required=True)
    node.add_argument('--snapshot', default=None)
    node.set_defaults(func=cmd_node)

    capture = sub.add_parser('capture', help='materialise the effective capture config')
    capture.add_argument('--template', required=True)
    capture.add_argument('--release-root', required=True)
    capture.add_argument('--staging-dir', default=None)
    capture.add_argument('--sessions-db', default=None)
    capture.add_argument('--port', type=int, default=None)
    capture.add_argument('--out', required=True)
    capture.add_argument('--snapshot', default=None)
    capture.set_defaults(func=cmd_capture)

    runtime = sub.add_parser('runtime', help='write the page runtime.js/runtime.json')
    runtime.add_argument('--config', default=None, help='effective (or scene) YAML')
    runtime.add_argument('--config-json', default=None,
                         help='effective config snapshot JSON (uses its config block)')
    runtime.add_argument('--release-json', required=True)
    runtime.add_argument('--profile', default=None)
    runtime.add_argument('--source-mode', default='unknown',
                         choices=list(INPUT_SOURCE_MODES))
    runtime.add_argument('--out', required=True)
    runtime.add_argument('--json-out', default=None)
    runtime.set_defaults(func=cmd_runtime)

    field = sub.add_parser('field', help='print one field of a JSON snapshot')
    field.add_argument('--file', required=True)
    field.add_argument('--name', required=True)
    field.set_defaults(func=cmd_field)

    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.error('a subcommand is required')
    try:
        return args.func(args)
    except ConfigError as exc:
        parser.exit(4, 'config error: %s\n' % exc)
    except (OSError, ValueError) as exc:
        parser.exit(5, 'io error: %s\n' % exc)


if __name__ == '__main__':
    sys.exit(main())
