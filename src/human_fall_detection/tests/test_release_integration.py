"""Release-integration regression: bundle, effective config, page binding.

These are the checks that keep a *release* honest, as opposed to the algorithm
regression suites:

* the standard bundle is complete, deterministic, and self-describing;
* it imports from an unpacked copy outside the repository, with the development
  PYTHONPATH removed, and the fall/capture ``core`` packages do not mix;
* the effective node/capture/page configuration is derived from one place and a
  bad profile or a topic mismatch fails loudly instead of degrading silently;
* the page is wired to ``runtime.js`` and shows run/version/source/region reason
  /suspected-hint state (static checks: there is no DOM here).
"""

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / 'src/human_fall_detection'
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / 'scripts'))
sys.path.insert(0, str(PKG / 'core'))

import prepare_single_target_bundle as bundler
import release_config
import verify_input_source
from core.run_record import RunRecorder


def _read_tar(path):
    files = {}
    with tarfile.open(path) as archive:
        for member in archive.getmembers():
            files[member.name] = archive.extractfile(member).read()
    return files


class BundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.tar = Path(cls.dir.name) / 'release.tar'
        cls.manifest = bundler.prepare(ROOT, cls.tar)
        cls.files = _read_tar(cls.tar)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_manifest_covers_every_file_and_checksums_match(self):
        for name, data in self.files.items():
            if name == 'MANIFEST.json':
                continue
            record = self.manifest[name]
            self.assertEqual(record['bytes'], len(data))
            self.assertEqual(record['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(set(self.manifest) | {'MANIFEST.json'}, set(self.files))

    def test_release_includes_every_runtime_component(self):
        for name in (
                'src/human_fall_detection/scripts/single_target_node.py',
                'src/human_fall_detection/scripts/human_fall_node.py',
                'src/human_fall_detection/scripts/record_session.py',
                'src/human_fall_detection/scripts/verify_input_source.py',
                'src/human_fall_detection/scripts/release_config.py',
                'src/human_fall_detection/scripts/prepare_single_target_bundle.py',
                'src/human_fall_detection/scripts/deploy_human_fall.sh',
                'src/human_fall_detection/core/run_record.py',
                'src/human_fall_detection/config/single_target_scene_20261019/'
                'declared_empty_background.json',
                'src/human_follow_calibration/scripts/calibrate_human_follow.py',
                'src/human_capture/scripts/capture_server.py',
                'src/human_capture/core/recorder.py',
                'src/human_capture/config/capture.yaml',
                'sidequests/hfus_tcms_02/realdev/current/region_runtime.py',
                'sidequests/hfus_tcms_02/realdev/r08/calibrate.py',
                'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py',
                'webui/human_fall/index.html',
                'webui/human_fall/human_fall.js',
                'webui/ui.css',
                'webui/three.min.js',
                'webui/OrbitControls.js'):
            self.assertIn(name, self.files, name)
        self.assertNotIn('webui/human_fall/human_fall_lib.test.js', self.files)
        self.assertFalse([n for n in self.files if '__pycache__' in n])

    def test_page_scripts_are_versioned_by_content(self):
        index = self.files['webui/human_fall/index.html'].decode('utf-8')
        lib = self.files['webui/human_fall/human_fall_lib.js']
        app = self.files['webui/human_fall/human_fall.js']
        lib_version = hashlib.sha256(lib).hexdigest()[:12]
        app_version = hashlib.sha256(app).hexdigest()[:12]
        self.assertIn('human_fall_lib.js?v=%s' % lib_version, index)
        self.assertIn('human_fall.js?v=%s' % app_version, index)
        release = json.loads(self.files['RELEASE.json'])
        self.assertIn('name="hf-page-version" content="%s"' % release['page_version'], index)
        self.assertIn('src="runtime.js"', index)

    def test_release_metadata_is_content_addressed_and_consistent(self):
        release = json.loads(self.files['RELEASE.json'])
        self.assertEqual(release['release_id'], release['release_id'][:16])
        self.assertEqual(len(release['release_id']), 16)
        self.assertEqual(release['file_count'], len(self.files) - 2)  # +RELEASE+MANIFEST
        self.assertFalse(release['semantic']['mode_verified'])
        self.assertFalse(release['semantic']['allow_confirmed'])
        self.assertFalse(release['semantic']['confirmed_enabled'])
        perception = self.files['src/human_fall_detection/config/'
                                'perception_single_target_v1.yaml']
        self.assertEqual(release['algorithm_config']['perception']['sha256'],
                         hashlib.sha256(perception).hexdigest())

    def test_unpacked_bundle_imports_without_repository_pythonpath(self):
        with tempfile.TemporaryDirectory() as extraction:
            with tarfile.open(self.tar) as archive:
                if hasattr(tarfile, 'data_filter'):
                    archive.extractall(extraction, filter='data')
                else:  # Python 3.8 has no extraction filters
                    archive.extractall(extraction)
            root = Path(extraction)
            env = {key: value for key, value in os.environ.items()
                   if key not in ('PYTHONPATH', 'PYTHONHOME')}
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            fall_path = os.pathsep.join([
                str(root / 'src/human_fall_detection'),
                str(root / 'src/human_fall_detection/scripts'),
                str(root / 'src/human_follow_calibration/scripts'),
                str(root / 'sidequests/hfus_tcms_02/realdev/current'),
            ])
            probe = (
                'import core, human_fall_node, region_runtime\n'
                'from core.run_record import RunRecorder\n'
                'from region_runtime import LiveRegions\n'
                'assert core.__file__.startswith(%r), core.__file__\n'
                'assert LiveRegions() is not None\n'
                'assert RunRecorder is not None\n'
                'import os\n'
                'print(os.path.dirname(core.__file__))\n' % str(root))
            done = subprocess.run([sys.executable, '-B', '-W', 'error', '-c', probe],
                                  env=dict(env, PYTHONPATH=fall_path),
                                  cwd=str(root), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
            self.assertEqual(done.returncode, 0, done.stderr.decode('utf-8', 'replace'))
            self.assertIn(str(root / 'src/human_fall_detection/core'),
                          done.stdout.decode('utf-8'))

            capture = subprocess.run(
                [sys.executable, '-B', '-c',
                 'import core; print(core.__file__)'],
                env=dict(env, PYTHONPATH=str(root / 'src/human_capture')),
                cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(capture.returncode, 0, capture.stderr.decode('utf-8', 'replace'))
            self.assertIn(str(root / 'src/human_capture/core'),
                          capture.stdout.decode('utf-8'))
            self.assertNotIn('human_fall_detection', capture.stdout.decode('utf-8'))


class EffectiveConfigTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)
        self.scene = PKG / 'config/single_target_scene_v1.yaml'

    def tearDown(self):
        self.dir.cleanup()

    def _profile(self, **overrides):
        geometry_dir = PKG / 'config/single_target_scene_20261019'
        profile = {
            'schema_version': 1,
            'kind': 'site_profile',
            'site_id': 'test_site',
            'scene_id': 'test_scene',
            'install': {'location': 'unit-test', 'note': ''},
            'input': {'cloud_topic': '/innolidar_points', 'imu_topic': '/inno_imu',
                      'device_topic': '/device_status', 'frame_id': 'innolidar',
                      'expected_mode': 'unknown'},
            'geometry': {
                'ground': {'path': str(geometry_dir / 'ground_candidate.json'),
                           'sha256': _sha256(geometry_dir / 'ground_candidate.json')},
                'background': {'path': str(geometry_dir / 'declared_empty_background.json'),
                               'sha256': _sha256(
                                   geometry_dir / 'declared_empty_background.json')},
                'display_ground': {'path': str(geometry_dir / 'display_ground.json'),
                                   'sha256': _sha256(
                                       geometry_dir / 'display_ground.json')},
            },
            'work_area': None,
            'applicability': {'scene_specific': True, 'same_installation': None,
                              'physical_verified': False, 'runtime_eligible': False,
                              'scene_artifact': 'config/single_target_scene_20261019',
                              'unknowns': ['unit test']},
        }
        profile.update(overrides)
        path = self.tmp / 'profile.json'
        path.write_text(json.dumps(profile), encoding='utf-8')
        return path

    def test_node_config_binds_profile_artifacts_and_topics(self):
        profile_path = self._profile()
        scene, snapshot = release_config.build_node_config(
            str(self.scene), str(profile_path), run_dir=str(self.tmp / 'run'))
        self.assertEqual(scene['geometry']['ground_path'],
                         str(PKG / 'config/single_target_scene_20261019/ground_candidate.json'))
        self.assertTrue(os.path.isabs(scene['geometry']['background_path']))
        self.assertEqual(scene['output']['session_dir'], str(self.tmp / 'run'))
        self.assertEqual(scene['target_mode'], 'automatic')
        self.assertEqual(snapshot['profile_id'], 'test_site')
        self.assertFalse(snapshot['confirmed']['confirmed_enabled'])
        self.assertIn('ground', snapshot['artifacts'])

    def test_profile_sha_mismatch_is_fatal(self):
        profile_path = self._profile()
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        profile['geometry']['ground']['sha256'] = '0' * 64
        profile_path.write_text(json.dumps(profile), encoding='utf-8')
        with self.assertRaises(release_config.ConfigError):
            release_config.build_node_config(str(self.scene), str(profile_path))

    def _display_profile(self, **changes):
        profile_path = self._profile()
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        display = json.loads(Path(profile['geometry']['display_ground']['path'])
                             .read_text(encoding='utf-8'))
        display.update(changes)
        display_path = self.tmp / 'display_ground.json'
        display_path.write_text(json.dumps(display), encoding='utf-8')
        profile['geometry']['display_ground'].update(
            path=str(display_path), sha256=_sha256(display_path))
        profile_path.write_text(json.dumps(profile), encoding='utf-8')
        return profile_path

    def test_profile_refuses_self_consistent_but_wrong_display_binding(self):
        cases = (
            ({'schema_version': True}, 'display_ground_schema_version'),
            ({'units': 'mm'}, 'display_ground_units'),
            ({'to_frame': 'world_local'}, 'display_ground_to_frame'),
            ({'calibration_id': 'wrong'}, 'display_ground_calibration_id'),
            ({'ground_sha256': '0' * 64}, 'display_ground_ground_sha256'),
            ({'source_frame': 'other'}, 'display_ground_source_frame'),
            ({'t': [0.0, 0.0, 99.0]}, 'display_ground_transform'),
        )
        for changes, expected in cases:
            with self.subTest(changes=changes):
                profile_path = self._display_profile(**changes)
                _, checks = release_config.check_profile(str(profile_path))
                self.assertIn(expected, [c['name'] for c in checks if not c['ok']])
                with self.assertRaises(release_config.ConfigError):
                    release_config.build_node_config(str(self.scene), str(profile_path))

    def test_display_binding_uses_explicit_calibration_when_present(self):
        from core.node_runtime import derive_ground_calibration
        profile_path = self._profile()
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        ground = release_config.load_json(profile['geometry']['ground']['path'])
        calibration = derive_ground_calibration(ground)
        calibration['calibration_id'] = 'explicit-unverified-calibration'
        calibration_path = self.tmp / 'calibration.json'
        calibration_path.write_text(json.dumps(calibration), encoding='utf-8')
        display = release_config.load_json(profile['geometry']['display_ground']['path'])
        display['calibration_id'] = calibration['calibration_id']
        display_path = self.tmp / 'display_ground.json'
        display_path.write_text(json.dumps(display), encoding='utf-8')
        profile['geometry']['calibration'] = {
            'path': str(calibration_path), 'sha256': _sha256(calibration_path)}
        profile['geometry']['display_ground'].update(
            path=str(display_path), sha256=_sha256(display_path))
        profile_path.write_text(json.dumps(profile), encoding='utf-8')
        _, checks = release_config.check_profile(str(profile_path))
        self.assertFalse(release_config.profile_failures(checks))
        scene, _ = release_config.build_node_config(str(self.scene), str(profile_path))
        self.assertEqual(scene['geometry']['calibration_path'], str(calibration_path))
        display['calibration_id'] = 'wrong'
        display_path.write_text(json.dumps(display), encoding='utf-8')
        profile['geometry']['display_ground']['sha256'] = _sha256(display_path)
        profile_path.write_text(json.dumps(profile), encoding='utf-8')
        with self.assertRaises(release_config.ConfigError):
            release_config.build_node_config(str(self.scene), str(profile_path))

    def test_profile_init_refuses_wrong_binding_before_writing(self):
        import init_site_profile
        profile_path = self._display_profile(calibration_id='wrong')
        geometry = release_config.load_json(profile_path)['geometry']
        output = self.tmp / 'new_profile.json'
        args = ['--site-id', 'new', '--scene-id', 'same',
                '--ground', geometry['ground']['path'],
                '--background', geometry['background']['path'],
                '--display-ground', geometry['display_ground']['path'],
                '--out', str(output)]
        with self.assertRaisesRegex(SystemExit, 'display_ground_calibration_id'):
            init_site_profile.main(args)
        self.assertFalse(output.exists())

    def test_runtime_eligible_without_physical_verification_is_rejected(self):
        profile_path = self._profile()
        profile = json.loads(profile_path.read_text(encoding='utf-8'))
        profile['applicability']['runtime_eligible'] = True
        profile_path.write_text(json.dumps(profile), encoding='utf-8')
        _, checks = release_config.check_profile(str(profile_path))
        names = [check['name'] for check in checks if not check['ok']]
        self.assertIn('runtime_eligible_requires_physical_verification', names)

    def test_capture_config_points_into_release(self):
        with tempfile.TemporaryDirectory() as release:
            record = Path(release) / 'src/human_fall_detection/scripts/record_session.py'
            record.parent.mkdir(parents=True)
            record.write_text('# stub\n', encoding='utf-8')
            config, snapshot = release_config.build_capture_config(
                str(ROOT / 'src/human_capture/config/capture.yaml'), release)
            self.assertEqual(config['record_script'], str(record))
            self.assertTrue(config['record_script'].startswith(release))
            self.assertEqual(snapshot['record_script_sha256'], _sha256(record))
            self.assertIn('sigint_grace_sec', config)
            with tempfile.TemporaryDirectory() as empty:
                with self.assertRaises(release_config.ConfigError):
                    release_config.build_capture_config(
                        str(ROOT / 'src/human_capture/config/capture.yaml'), empty)

    def test_page_runtime_matches_topics_and_fails_on_mismatch(self):
        profile_path = self._profile()
        scene, _ = release_config.build_node_config(str(self.scene), str(profile_path))
        release = {'release_id': 'abcdef0123456789', 'page_version': 'p' * 12}
        runtime = release_config.build_page_runtime(
            scene, release, json.loads(profile_path.read_text(encoding='utf-8')),
            source_mode='live_lidar')
        self.assertEqual(runtime['prefix'], '/single_target_live/')
        self.assertEqual(runtime['state'], '/single_target_live/state')
        self.assertEqual(runtime['points'], '/single_target_live/display_points')
        self.assertEqual(runtime['ground'], 'display_ground.json')
        self.assertEqual(runtime['source_mode'], 'live_lidar')
        out = self.tmp / 'runtime.js'
        release_config.write_runtime_js(runtime, out)
        text = out.read_text(encoding='utf-8')
        self.assertIn('window.__HF_RUNTIME__', text)
        self.assertIn('"state": "/single_target_live/state"', text)
        bad = json.loads(json.dumps(scene))
        bad['topics']['event'] = '/human_fall/event'
        with self.assertRaises(release_config.ConfigError):
            release_config.build_page_runtime(bad, release, None)


class InputSourceTest(unittest.TestCase):
    def test_missing_driver_is_unknown_not_live(self):
        evidence = verify_input_source.inspect()
        if sys.platform.startswith('win') or not os.path.isdir('/proc'):
            self.assertEqual(evidence['mode'], 'unknown')
            self.assertEqual(evidence['reason'], 'no_driver_process_found')
        else:
            self.assertIn(evidence['mode'], ('live_lidar', 'pcap', 'unknown'))

    def test_mode_decision_rules(self):
        # Conservative: live_lidar requires msg_source=1 *and* no open pcap.
        cases = [
            (1, [], 'live_lidar'),
            (2, [], 'pcap'),
            (1, [{'fd': '9'}], 'unknown'),
            (None, [], 'unknown'),
            (0, [], 'unknown'),
        ]
        for msg_source, open_pcap, expected in cases:
            self.assertEqual(verify_input_source.decide_mode(msg_source, open_pcap),
                             expected, (msg_source, open_pcap))


class PageWiringTest(unittest.TestCase):
    def test_page_shows_version_source_records_and_reasons(self):
        index = (ROOT / 'webui/human_fall/index.html').read_text(encoding='utf-8')
        script = (ROOT / 'webui/human_fall/human_fall.js').read_text(encoding='utf-8')
        for element in ('hfVer', 'hfInput', 'hfRunRec', 'hfHints'):
            self.assertIn('id="%s"' % element, index)
        self.assertIn('runtime.js', index)
        self.assertIn('HF_RUNTIME', index)
        self.assertIn('RT.prefix', script)
        self.assertIn('RT.ground', script)
        self.assertIn('notification_id', script)
        self.assertIn('hfNoticeSeq', script)
        self.assertIn('输入来源未核实', script)
        # Fixed field entry: the page connects on load (a manual 断开 still stops it).
        self.assertIn('connect();', index)
        self.assertIn('正在按页面域名连接 bridge', index)

    def test_hint_floor_prevents_replay_on_reload(self):
        # Mirrors the page rule: the first observed notification becomes a floor
        # and only larger sequence numbers are announced afterwards.
        def seq(value):
            return int(value.rsplit(':', 1)[1])

        class Page:
            def __init__(self):
                self.floor = None
                self.announced = []

            def observe(self, notification_id):
                value = seq(notification_id)
                if self.floor is None:
                    self.floor = value
                    return False
                if value > self.floor:
                    self.floor = value
                    return True
                return False

        page = Page()
        self.assertFalse(page.observe('run:suspected:1'))
        self.assertTrue(page.observe('run:suspected:2'))
        self.assertFalse(page.observe('run:suspected:2'))
        self.assertFalse(page.observe('run:suspected:1'))


class SceneProbeTest(unittest.TestCase):
    def _frame(self, **overrides):
        record = {'points': 5000, 'foreground_rows': 0, 'ground_frame_eligible': True,
                  'ground_point_fraction': 0.4, 'ground_residual_abs_p95_m': 0.01,
                  'foreground_points': 0, 'candidates': 0,
                  'largest_candidate_points': 0}
        record.update(overrides)
        return record

    def test_consistent_empty_scene(self):
        import probe_scene
        summary = probe_scene.summarize([self._frame() for _ in range(10)])
        self.assertEqual(summary['verdict'], 'CONSISTENT')
        self.assertEqual(summary['problems'], [])

    def test_ineligible_ground_and_low_support_are_flagged(self):
        import probe_scene
        frames = [self._frame(ground_frame_eligible=False,
                              ground_point_fraction=0.01) for _ in range(6)]
        summary = probe_scene.summarize(frames)
        self.assertEqual(summary['verdict'], 'REVIEW')
        self.assertIn('ground_not_eligible_for_frame', summary['problems'])
        self.assertIn('ground_support_too_low', summary['problems'])

    def test_persistent_large_foreground_object_is_flagged(self):
        import probe_scene
        frames = [self._frame(foreground_points=900,
                              largest_candidate_points=500) for _ in range(8)]
        summary = probe_scene.summarize(frames)
        self.assertIn('persistent_large_foreground_object', summary['problems'])

    def test_no_frames_is_no_data(self):
        import probe_scene
        self.assertEqual(probe_scene.summarize([])['verdict'], 'NO_DATA')


class FreezeSceneTest(unittest.TestCase):
    """The initialisation tool must reuse core fits and never self-certify."""

    def _plane_frames(self, count=14, points=None):
        """A fixed lattice on one plane: identical cells every frame."""
        import numpy as np
        x = np.linspace(1.5, 5.0, 40)
        y = np.linspace(-2.0, 2.0, 50)
        grid = np.stack(np.meshgrid(x, y), axis=-1).reshape(-1, 2)
        z = np.full(len(grid), -1.3)
        base = np.column_stack([grid, z])
        return [base.copy() for _ in range(count)]

    def _freeze(self, directory, extra_args=()):
        import freeze_scene
        frames = self._plane_frames(count=4)
        collected = [dict(points=frame, seq=i, stamp_secs=100,
                          stamp_nsecs=i * 100000000, frame_id='innolidar',
                          received_wall=1000.0 + i * 0.1)
                     for i, frame in enumerate(frames)]
        args = ['--config', str(PKG / 'config/single_target_scene_v1.yaml'),
                '--perception', str(PKG / 'config/perception_single_target_v1.yaml'),
                '--frames', str(len(frames)), '--out-dir', str(directory)]
        with mock.patch.object(freeze_scene, 'collect_live', return_value=collected), \
                mock.patch('sys.stdout', new_callable=io.StringIO):
            return freeze_scene.main(args + list(extra_args))

    def test_frozen_display_binds_to_actual_node_calibration(self):
        from core.node_runtime import FallNodeCore
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self._freeze(tmp), 0)
            ground_path = Path(tmp) / 'ground_candidate.json'
            ground = release_config.load_json(ground_path)
            display = release_config.load_json(Path(tmp) / 'display_ground.json')
            core = FallNodeCore('freeze-binding', ground=ground)
            self.assertEqual(display['calibration_id'], core.calibration['calibration_id'])
            self.assertEqual(display['ground_sha256'], _sha256(ground_path))
            self.assertFalse(display['physical_verified'])
            self.assertFalse(display['runtime_eligible'])
            # The legacy CLI option is an assertion of the actual node binding.
            self.assertEqual(self._freeze(tmp, ['--calibration-id',
                                               display['calibration_id']]), 0)

    def test_freeze_refuses_arbitrary_calibration_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SystemExit, '2'):
                self._freeze(tmp, ['--calibration-id', 'unbound-id'])
            self.assertFalse((Path(tmp) / 'ground_candidate.json').exists())

    def test_artifacts_and_display_transform(self):
        import numpy as np
        import freeze_scene
        frames = self._plane_frames()
        ground, background, attempts = freeze_scene.build_artifacts(
            frames, 'innolidar', candidate_settings={})
        self.assertTrue(ground['valid'])
        self.assertTrue(attempts)
        self.assertEqual(background['kind'], 'candidate_background')
        self.assertGreater(background['cell_count'], 0)
        display = freeze_scene.display_ground_from_plane(
            ground, 'ground-only-test', 'a' * 64, 'innolidar')
        rotation = np.asarray(display['R'], dtype=np.float64)
        normal = np.asarray(ground['normal'], dtype=np.float64)
        # R maps the ground normal to +z and is a proper rotation.
        self.assertTrue(np.allclose(rotation @ normal, [0.0, 0.0, 1.0], atol=1e-6))
        self.assertTrue(np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9))
        self.assertAlmostEqual(float(np.linalg.det(rotation)), 1.0, places=9)
        self.assertEqual(display['t'], [0.0, 0.0, ground['offset_m']])
        self.assertFalse(display['physical_verified'])
        self.assertFalse(display['runtime_eligible'])

    def test_static_guard_detects_moving_content(self):
        import numpy as np
        import freeze_scene
        frames = self._plane_frames(count=10)
        still = freeze_scene.static_check(frames, {})
        self.assertTrue(still['checked'])
        self.assertTrue(still['static'])
        moving = list(frames)
        rng = np.random.default_rng(11)
        for index in range(5, 10):
            blob = rng.uniform(-1.0, 1.0, (300, 3)) + [3.0, 0.0, -0.6 + index * 0.1]
            moving[index] = np.concatenate([moving[index], blob], axis=0)
        guard = freeze_scene.static_check(moving, {})
        self.assertFalse(guard['static'])

    def test_display_transform_matches_existing_convention(self):
        import json
        import numpy as np
        import freeze_scene
        existing = ROOT / 'src/human_fall_detection/config/single_target_scene_20261019'
        ground = json.loads((existing / 'ground_candidate.json').read_text(encoding='utf-8'))
        display = json.loads((existing / 'display_ground.json').read_text(encoding='utf-8'))
        reproduced = freeze_scene.display_ground_from_plane(
            ground, display['calibration_id'], display['ground_sha256'],
            display['source_frame'])
        # Same normal row and translation; the tangent basis may differ by yaw
        # (cosmetic for the display plane), so compare the plane orientation
        # instead of demanding a bit-identical u vector.
        self.assertTrue(np.allclose(reproduced['R'][2], display['R'][2], atol=1e-9))
        self.assertTrue(np.allclose(reproduced['t'], display['t'], atol=1e-9))
        normal = np.asarray(display['R'][2], dtype=np.float64)
        for rotation in (reproduced['R'], display['R']):
            matrix = np.asarray(rotation, dtype=np.float64)
            self.assertTrue(np.allclose(matrix @ matrix.T, np.eye(3), atol=1e-9))
            self.assertAlmostEqual(float(np.linalg.det(matrix)), 1.0, places=9)
            self.assertTrue(np.allclose(matrix @ normal, [0.0, 0.0, 1.0], atol=1e-9))
        angle = np.degrees(np.arccos(np.clip(
            float(np.dot(np.asarray(reproduced['R'][0]), np.asarray(display['R'][0]))),
            -1.0, 1.0)))
        self.assertLess(angle, 1.0)


class PageServerTest(unittest.TestCase):
    """The page server must forbid reuse of a previous release's HTML."""

    def test_no_cache_headers_on_every_response(self):
        import http.client
        import threading
        sys.path.insert(0, str(PKG / 'scripts'))
        import serve_webui
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'index.html').write_text('<html>x</html>', encoding='utf-8')
            server = serve_webui.Server(('127.0.0.1', 0), root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                connection.request('GET', '/index.html')
                response = connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertEqual(body, b'<html>x</html>')
                self.assertIn('no-cache', response.getheader('Cache-Control').lower())
                self.assertIn('must-revalidate',
                              response.getheader('Cache-Control').lower())
                # Directory traversal outside the served root is refused.
                connection.request('GET', '/../secret.txt')
                traversal = connection.getresponse()
                traversal.read()
                self.assertIn(traversal.status, (404, 400))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


class ShutdownTest(unittest.TestCase):
    def test_recorder_close_flushes_pending_performance_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'events.jsonl')
            recorder = RunRecorder(path, run_id='r', perf_interval_s=3600)
            recorder.observe({'session_id': 's', 'fall_status': 'unknown',
                              'observability': 'ok', 'baseline': {}, 'source': None,
                              'reason_codes': []},
                             {'process_s': 0.1, 'queue_dropped': 0})
            recorder.close()
            with open(path, encoding='utf-8') as handle:
                records = [json.loads(line) for line in handle if line.strip()]
            self.assertTrue(any(r['event'] == 'performance_window' for r in records))


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


if __name__ == '__main__':
    unittest.main()
