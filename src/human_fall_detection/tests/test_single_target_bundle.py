import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
PKG = ROOT / 'src/human_fall_detection'
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(PKG / 'scripts'))
from human_fall_node import load_yaml, load_ground_context, build_core
from prepare_single_target_bundle import prepare
from single_target_node import configure_paths


class SingleTargetBundle(unittest.TestCase):
    def test_legacy_production_waits_but_named_scene_has_bound_artifacts(self):
        config = PKG / 'config'
        legacy = load_yaml(config / 'human_fall_prod.yaml')
        self.assertEqual(load_ground_context(legacy['geometry'], str(config)), (None, None, None))
        named = load_yaml(config / 'single_target_scene_v1.yaml')
        ground, calibration, background = load_ground_context(named['geometry'], str(config))
        self.assertIsNotNone(ground)
        self.assertIsNotNone(background)
        self.assertEqual(named['target_mode'], 'automatic')
        with tempfile.TemporaryDirectory() as tmp:
            core = build_core(named, load_yaml(config / 'perception_single_target_v1.yaml'),
                              session_id='bundle_test', config_dir=str(config), event_path=None)
            self.assertTrue(core._ground_valid())
        configure_paths(ROOT)
        from region_runtime import LiveRegions
        self.assertIsNotNone(LiveRegions())

    def test_bundle_is_deterministic_and_complete_without_tmp_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp)/'a.tar', Path(tmp)/'b.tar'
            prepare(ROOT, first)
            prepare(ROOT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as archive:
                manifest = json.load(archive.extractfile('MANIFEST.json'))
                for name, record in manifest.items():
                    self.assertEqual(hashlib.sha256(archive.extractfile(name).read()).hexdigest(), record['sha256'])
                self.assertIn('src/human_fall_detection/config/single_target_scene_20261019/declared_empty_background.json', manifest)
                self.assertIn('sidequests/hfus_tcms_02/realdev/current/region_runtime.py', manifest)

    def test_driver_default_is_replay_not_live(self):
        config = load_yaml(ROOT / 'src/inno_lidar_ros/config/config.yaml')
        self.assertEqual(config['common']['msg_source'], 2)
        self.assertTrue(config['lidar'][0]['driver']['pcap_repeat'])
