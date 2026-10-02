"""Independent GL02 v1 entry/lifecycle checks, synthetic and ROS-free.

Execute actual wrapper functions extracted from its AST with mocked transport;
this verifies routing without claiming a ROS installation or board run.
"""
import ast
import copy
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'src/human_fall_detection'),
                str(ROOT / 'src/human_fall_detection/tests'),
                str(ROOT / 'docs/human_fall/evidence/2026-10-01_gl02_r5')]
import claude_r5_checks as r5
from core.calibration import validate_geometry_calibration
from core.node_runtime import FallNodeCore, frame_age_exceeded
from test_hf07_node import settings, standing_person


def wrapper_function(name, namespace):
    tree = ast.parse((ROOT / 'src/human_fall_detection/scripts/human_fall_node.py')
                     .read_text(encoding='utf-8-sig'))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    fn = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[fn], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(ROOT / 'src/human_fall_detection/scripts/human_fall_node.py'), 'exec'), namespace)
    return namespace[name]


class LifecycleChecks(unittest.TestCase):
    def setup_capture(self, short=False):
        sections = settings()
        # Fixture crop separates the stance from the dense plane; monitor sees
        # the unfiltered cloud. Without it both geometries form one cluster.
        sections['candidates']['height_min_m'] = 0.1
        if short:
            sections['baseline'] = {'require_seconds': 0.2, 'max_duration_s': 1.0, 'min_samples': 3}
        core = FallNodeCore('s1', settings=sections, calibration=r5.R5BoundaryChecks().artifact())
        person = standing_person(x=1., bottom=-1.2, top=0.6)
        scene = r5.scene_fixture(person)
        first = core.process(scene, 1., seq=1, stamp_secs=100, stamp_nsecs=0)
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        select = core.handle_request({'schema_version': 1, 'request_id': 'select-independent',
            'action': 'select', 'session_id': 's1', 'time_epoch': 0,
            'snapshot_id': first['snapshot']['snapshot_id'],
            'candidate_id': first['snapshot']['candidates'][0]['candidate_id'],
            'selection_version': 0}, 1.01)
        self.assertTrue(select['accepted'], select)
        request = {'schema_version': 1, 'request_id': 'capture-independent',
            'action': 'capture_baseline', 'session_id': 's1', 'time_epoch': 0,
            'selection_version': select['selection_version']}
        ack = core.handle_request(request, 1.02)
        self.assertTrue(ack['accepted'], ack)
        return core, person, scene, request, ack

    def frame(self, core, points, index):
        # 0.1 source seconds per frame, all in the same receive-clock domain.
        return core.process(points, 1. + index * 0.1, seq=index+1,
                            stamp_secs=100 + index // 10,
                            stamp_nsecs=(index % 10) * 100000000)

    def test_A10_failed_capture_replays_original_ack_under_bad_monitor(self):
        core, person, scene, request, original = self.setup_capture()
        failed = self.frame(core, person, 1)
        self.assertEqual(failed['baseline_ack']['request_id'], request['request_id'])
        replay = core.handle_request(copy.deepcopy(request), 1.11)
        expected = copy.deepcopy(original)
        expected['idempotent_replay'] = True
        self.assertEqual(replay, expected)
        self.assertEqual(core.baseline.status, 'failed')

    def test_A10_failed_capture_replays_original_ack_under_stale_cloud(self):
        core, person, scene, request, original = self.setup_capture()
        core.status_state(2.)
        replay = core.handle_request(copy.deepcopy(request), 2.01)
        expected = copy.deepcopy(original)
        expected['idempotent_replay'] = True
        self.assertEqual(replay, expected)
        self.assertEqual(core.baseline.status, 'failed')

    def test_A10_conflicting_request_keeps_conflict_under_bad_monitor(self):
        core, person, scene, request, original = self.setup_capture()
        self.frame(core, person, 1)
        conflict = copy.deepcopy(request)
        conflict['operator_confirmed'] = True
        result = core.handle_request(conflict, 1.11)
        self.assertEqual(result['reason'], 'request_id_conflict')
        self.assertFalse(result['accepted'])

    def test_A09_A10_ready_retires_on_monitor_failure_and_cannot_revive(self):
        core, person, scene, request, original = self.setup_capture(short=True)
        for i in range(1, 5):
            self.frame(core, scene, i)
        self.assertEqual(core.baseline.status, 'ready', core.baseline.snapshot())
        version = core.baseline.baseline['baseline_version']
        self.frame(core, person, 5)
        self.assertIsNone(core.baseline.baseline, 'ready eligibility survived unavailable ground')
        self.assertTrue(any(b['baseline_version'] == version for b in core.baseline.retired))
        resumed = self.frame(core, scene, 6)
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        self.assertFalse(resumed['state']['target_features'].get('baseline_applies'))
        self.assertNotEqual(core.baseline.status, 'ready')

    def test_A10_failure_recovery_requires_new_capture_samples(self):
        core, person, scene, request, original = self.setup_capture()
        self.frame(core, scene, 1)
        self.assertGreater(len(core.baseline.samples), 0)
        self.frame(core, person, 2)
        self.assertEqual(core.baseline.status, 'failed')
        old_count = len(core.baseline.samples)
        self.frame(core, scene, 3)
        self.assertEqual(core.baseline.status, 'failed')
        self.assertEqual(len(core.baseline.samples), old_count)
        new_request = dict(request, request_id='capture-after-recovery')
        new_ack = core.handle_request(new_request, 1.31)
        self.assertTrue(new_ack['accepted'], new_ack)
        self.assertEqual(core.baseline.samples, [])

    def test_A09_A10_watchdog_retires_ready_eligibility(self):
        core, person, scene, request, original = self.setup_capture(short=True)
        for i in range(1, 5):
            self.frame(core, scene, i)
        self.assertEqual(core.baseline.status, 'ready')
        version = core.baseline.baseline['baseline_version']
        state = core.status_state(2.1)
        self.assertIsNone(core.baseline.baseline)
        self.assertNotEqual(state['baseline']['status'], 'ready')
        self.assertTrue(any(b['baseline_version'] == version for b in core.baseline.retired))

    def test_A06_full_metadata_deepcopy_for_all_unchanged_entries(self):
        artifact = r5.R5BoundaryChecks().artifact()
        artifact['frames']['reference'] = 'synthetic_reference'
        artifact['transforms']['T_reference_lidar'] = {
            'status': 'unknown', 'from_frame': 'innolidar',
            'to_frame': 'synthetic_reference', 'rotation': None,
            'translation_m': None, 'units': 'm', 'note': 'unknown pose'}
        artifact['input']['extension'] = {'evidence_files': ['synthetic-only.json']}
        artifact['extension'] = {'reason': ['preserve legal optional metadata']}
        core = FallNodeCore('s1', settings=settings(), calibration=artifact)
        expected = copy.deepcopy(core.calibration)
        for entry in ['empty', 'paired', 'ground_only', 'full']:
            args = {'empty': {}, 'paired': {'ground': copy.deepcopy(core.ground),
                    'ground_derived': copy.deepcopy(core.ground_derived)},
                    'ground_only': {'ground': copy.deepcopy(core.ground)},
                    'full': {'calibration': copy.deepcopy(core.calibration)}}[entry]
            record = core.apply_ground_context(**args)
            self.assertFalse(record['changed'], entry)
            self.assertEqual(core.calibration, expected, entry)
        artifact['input']['extension']['evidence_files'].append('caller-edit')
        self.assertEqual(core.calibration, expected)
        before = copy.deepcopy(core.calibration)
        core.calibration['rotations']['R_lidar_imu']['from_frame'] = 'innolidar'
        with self.assertRaises(ValueError):
            core.apply_ground_context()
        core.calibration = before

    def test_A08_same_context_reload_keeps_recalibration_latch(self):
        core, person, scene, request, original = self.setup_capture()
        shifted = scene.copy()
        shifted[:, 2] += 0.1
        for index in range(1, 7):
            self.frame(core, shifted, index)
        self.assertEqual(core.ground_monitor_report['status'], 'recalibration_required')
        monitor = core.ground_monitor
        core.apply_ground_context()
        self.assertIs(core.ground_monitor, monitor)
        self.frame(core, scene, 7)
        self.assertEqual(core.ground_monitor_report['status'], 'recalibration_required')

    def test_A09_auxiliary_imu_degraded_keeps_capture_and_release_usable(self):
        core, person, scene, request, original = self.setup_capture()
        core.note_imu(1.03, (100, 30000000), 'imu', False)
        state = self.frame(core, scene, 1)['state']
        self.assertEqual(core.ground_monitor_report['status'], 'ok')
        self.assertEqual(core.baseline.status, 'pending')
        self.assertEqual(state['observability'], 'degraded')
        self.frame(core, person, 2)
        release = {'schema_version': 1, 'request_id': 'release-independent',
            'action': 'release', 'session_id': 's1', 'time_epoch': 0,
            'selection_version': request['selection_version']}
        ack = core.handle_request(release, 1.21)
        self.assertTrue(ack['accepted'], ack)

    def test_A10_watchdog_ack_reaches_existing_ros_ack_transport(self):
        core, person, scene, request, original = self.setup_capture()
        state = core.status_state(2.)
        self.assertIsNotNone(state.get('baseline_ack'))
        published = []
        namespace = {'performance_enabled': False, 'display_pub': None,
            'publishers': {'state': 'state', 'ack': 'ack'},
            '_publish': lambda topic, payload: published.append((topic, copy.deepcopy(payload)))}
        wrapper_function('_publish_state', namespace)(state)
        acks = [p for topic, p in published if topic == 'ack']
        self.assertEqual(len(acks), 1, 'terminal ack was published only inside state')
        self.assertEqual(acks[0]['request_id'], request['request_id'])
        self.assertFalse(acks[0]['accepted'])

    def test_A10_postcompute_stale_suppression_keeps_terminal_ack(self):
        core, person, scene, request, original = self.setup_capture()
        result = self.frame(core, person, 1)
        self.assertIsNotNone(result['baseline_ack'])
        published = []
        class Stop:
            def __init__(self):
                self.n = 0
            def is_set(self):
                self.n += 1
                return self.n > 1
        ticks = iter([1.11, 1.12, 2.0])
        namespace = {'stop': Stop(), 'publish_period': 0.1,
            'queue': types.SimpleNamespace(wait=lambda period: True, take=lambda: (1.1, types.SimpleNamespace(header=types.SimpleNamespace(seq=2, stamp=None, frame_id='innolidar'))), dropped=0),
            'time': types.SimpleNamespace(monotonic=lambda: next(ticks)),
            'core': types.SimpleNamespace(process=lambda *a, **k: result,
                    status_state=core.status_state, frame_count=core.frame_count),
            'frame_age_exceeded': frame_age_exceeded, 'cloud_stale_s': 0.6,
            'rospy': types.SimpleNamespace(logwarn_throttle=lambda *a: None, loginfo_throttle=lambda *a: None),
            'perf_holder': {}, 'performance_block': lambda *a: {},
            'xyz_from_cloud': lambda *a: person, 'stamp_pair': lambda stamp: (100, 100000000),
            'calibration_error': ValueError,
            '_publish_state': lambda state, *a: published.append(('state', copy.deepcopy(state))),
            '_publish': lambda topic, payload: published.append((topic, copy.deepcopy(payload))),
            'publishers': {'ack': 'ack', 'event': 'event', 'candidates': 'candidates'}, 'display_pub': None}
        wrapper_function('worker', namespace)()
        acks = [p for topic, p in published if topic == 'ack']
        self.assertEqual(len(acks), 1, 'postcompute suppression lost an already-issued terminal ack')
        self.assertEqual(acks[0]['request_id'], request['request_id'])
        self.assertFalse(acks[0]['accepted'])

    def test_A02_full_artifact_strict_id_and_schema_all_entries(self):
        for field, value in [('calibration_id', ''), ('calibration_id', None),
                             ('calibration_id', 1), ('schema_version', True),
                             ('schema_version', 1.0)]:
            for entry in ['validator', 'startup', 'reload']:
                with self.subTest(field=field, value=value, entry=entry):
                    artifact = r5.R5BoundaryChecks().artifact()
                    artifact[field] = value
                    core = FallNodeCore('s1', settings=settings(), calibration=r5.R5BoundaryChecks().artifact())
                    old = copy.deepcopy(core.calibration)
                    with self.assertRaises(ValueError):
                        if entry == 'validator':
                            validate_geometry_calibration(artifact)
                        elif entry == 'startup':
                            FallNodeCore('s1', settings=settings(), calibration=artifact)
                        else:
                            core.apply_ground_context(calibration=artifact)
                    self.assertEqual(core.calibration, old)


if __name__ == '__main__':
    unittest.main(verbosity=2)
