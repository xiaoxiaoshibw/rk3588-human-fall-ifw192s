"""GL-P01 R1 concentrated tests: additive ``coordinate.ground`` R/t projection.

Covers the producer whitelist/binding/isolation and the real pipeline
Python ``build_snapshot`` -> ``project_snapshot_for_ros`` -> ``dumps_strict`` ->
the existing preview parser (``webui/human_fall_preview/human_fall_lib.js``).

Software/synthetic only. It is not a human-fall or physical-ground acceptance.
"""

import copy
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parents[1]
TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR / "scripts"))
sys.path.insert(0, str(TEST_DIR))

from core.calibration import build_ground_derived  # noqa: E402
from core.lidar_candidates import validate_snapshot  # noqa: E402
from core.node_runtime import (FallNodeCore,  # noqa: E402
                               project_snapshot_for_ros)
from sensor_health import dumps_strict  # noqa: E402

from test_gl02_ground_frame import flat_ground, trusted_block  # noqa: E402
from test_gl03_candidates_geometry import (  # noqa: E402
    blob, calibration_with, snapshot, tilted_ground)

FROM_FRAME = "innolidar"
CONSUMER = TEST_DIR / "glp01_consumer.js"
IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _tilted_ground():
    return tilted_ground(offset=1.4, normal=(0.2, 0.0, 0.9797958971132712))


def _tilted_block(ground):
    region = {"available": True, "x_min_m": -2.0, "x_max_m": 2.0,
              "y_min_m": -2.0, "y_max_m": 2.0, "z_min_m": -0.05,
              "z_max_m": 0.05, "point_count": 400, "trusted": True,
              "evidence": "synthetic known floor", "source": "synthetic_fixture"}
    return build_ground_derived(ground, [1.0, 0.0, 0.0],
                                valid_region_ground_local=region)


def _tuple_block(block, rotation=False, translation=False):
    """The same validated content with R and/or t carried as tuples."""
    item = copy.deepcopy(block)
    if rotation:
        item["R"] = tuple(tuple(row) for row in item["R"])
    if translation:
        item["t"] = tuple(item["t"])
    return item


def _settings():
    return {"candidates": {"min_cluster_points": 20,
                           "preferred_cluster_points": 30,
                           "height_min_m": 0.1},
            "tracking": {"occlusion_timeout_s": 1.5, "lost_timeout_s": 3.0},
            "fall": {"mode_verified": False, "allow_confirmed": False}}


def _preview_parse(snapshot_json, expect="ready"):
    """Run the real preview parser via node over the projected wire bytes."""
    node = shutil.which("node")
    if node is None:
        raise unittest.SkipTest("node runtime required for the preview check")
    envelope = '{"snapshot":' + snapshot_json + ',"expect":"' + expect + '"}'
    return subprocess.run([node, str(CONSUMER)], input=envelope,
                          capture_output=True, text=True, encoding="utf-8")


class CoordinateGroundProjectionTest(unittest.TestCase):
    """P01/P02/P04/P05: whitelist R/t binding, null paths and support fields."""

    def test_valid_derived_projects_exact_rt_and_binding(self):
        ground = flat_ground()
        block = trusted_block()
        artifact = calibration_with(ground, block)
        snap = snapshot(blob(), calibration=artifact, ground=ground)
        cg = snap["coordinate"]["ground"]
        self.assertIsInstance(cg, dict)
        self.assertEqual(cg["kind"], "coordinate_ground")
        self.assertEqual(cg["schema_version"], 1)
        self.assertEqual(cg["from_frame"], FROM_FRAME)
        self.assertEqual(cg["to_frame"], "ground_local")
        self.assertEqual(cg["units"], "m")
        self.assertEqual(cg["calibration_id"], artifact["calibration_id"])
        self.assertEqual(cg["geometry_schema_version"], artifact["schema_version"])
        self.assertEqual(cg["geometry_schema_version"], 1)
        self.assertEqual(cg["ground_derived_id"], block["ground_derived_id"])
        self.assertEqual(cg["ground_derived_id"],
                         snap["coordinate"]["ground_derived_id"])
        self.assertEqual(cg["R"], block["R"])
        self.assertEqual(cg["t"], block["t"])
        validate_snapshot(snap)

    def test_tilted_ground_keeps_nonidentity_rt(self):
        ground = _tilted_ground()
        block = _tilted_block(ground)
        artifact = calibration_with(ground, block)
        snap = snapshot(blob(), calibration=artifact, ground=ground)
        cg = snap["coordinate"]["ground"]
        self.assertEqual(cg["R"], block["R"])
        self.assertEqual(cg["t"], block["t"])
        self.assertNotEqual(cg["R"], IDENTITY)
        validate_snapshot(snap)

    def test_no_derived_leaves_coordinate_ground_null(self):
        ground = flat_ground()
        artifact = calibration_with(ground, None)
        snap = snapshot(blob(), calibration=artifact, ground=ground)
        self.assertIsNone(snap["coordinate"]["ground"])
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])

    def test_artifact_only_ground_none_stays_unqualified(self):
        artifact = calibration_with(flat_ground(), trusted_block())
        snap = snapshot(blob(), calibration=artifact)
        self.assertIsNone(snap["ground"])
        self.assertEqual(snap["calibration"]["ground_status"], "unknown")
        self.assertIsNotNone(snap["coordinate"]["ground"])

    def test_foreign_frame_projection_is_null(self):
        ground = flat_ground()
        artifact = calibration_with(ground, trusted_block())
        snap = snapshot(blob(), calibration=artifact, ground=ground,
                        frame_id="other_lidar")
        self.assertIsNone(snap["coordinate"]["ground"])
        self.assertIsNone(snap["coordinate"]["ground_derived_id"])

    def test_projection_is_isolated_from_artifact_and_other_snapshots(self):
        ground = flat_ground()
        block = trusted_block()
        artifact = calibration_with(ground, block)
        snap1 = snapshot(blob(), calibration=artifact, ground=ground)
        original = copy.deepcopy(snap1["coordinate"]["ground"])
        snap1["coordinate"]["ground"]["R"][0][0] += 1.0
        snap1["coordinate"]["ground"]["t"][0] += 1.0
        self.assertEqual(artifact["ground_derived"]["R"], original["R"])
        self.assertEqual(artifact["ground_derived"]["t"], original["t"])
        snap2 = snapshot(blob(), calibration=artifact, ground=ground)
        self.assertEqual(snap2["coordinate"]["ground"], original)

    def test_support_fields_only_on_existing_ground_summary(self):
        ground = flat_ground()
        artifact = calibration_with(ground, trusted_block())
        snap = snapshot(blob(), calibration=artifact, ground=ground)
        summary = snap["ground"]
        self.assertIsInstance(summary, dict)
        self.assertIsNone(summary["support_polygon"])
        self.assertIsNone(summary["support_polyline"])
        self.assertTrue(summary["support_reason"])
        self.assertNotIn("support", snap)


class PythonToPreviewPipelineTest(unittest.TestCase):
    """P03/P06: production snapshot reaches the real preview parser."""

    def test_production_snapshot_reaches_preview_js_parser(self):
        ground = flat_ground()
        block = trusted_block()
        artifact = calibration_with(ground, block)
        snap = snapshot(blob(), calibration=artifact, ground=ground)
        self.assertTrue(snap["candidates"])
        self.assertIn("evidence_indices", snap["candidates"][0])

        projected = project_snapshot_for_ros(snap)
        self.assertNotIn("evidence_indices", projected["candidates"][0])
        self.assertIn("evidence_indices", snap["candidates"][0])
        self.assertEqual(projected["coordinate"]["ground"],
                         snap["coordinate"]["ground"])

        payload = dumps_strict(projected)
        node = shutil.which("node")
        self.assertIsNotNone(node, "node runtime required for the preview check")
        result = subprocess.run([node, str(CONSUMER)], input=payload,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GLP01_CONSUMER_OK", result.stdout)
        parsed = json.loads(
            result.stdout.split("GLP01_CONSUMER_OK", 1)[1].strip())
        self.assertEqual(parsed["parse_status"], "ready")
        self.assertEqual(parsed["support_status"], "unavailable")
        self.assertEqual(parsed["ground_R"], block["R"])
        self.assertEqual(parsed["ground_t"], block["t"])
        self.assertEqual(parsed["ground_derived_id"], block["ground_derived_id"])


class TupleContainerProjectionTest(unittest.TestCase):
    """R2: legal tuple R/t containers (accepted by the shared validator) must
    project exactly like the list form, through the pure producer and the actual
    FallNodeCore -> ROS projection -> strict JSON -> preview parser chain."""

    COMBOS = ((False, False), (True, False), (False, True), (True, True))

    def test_pure_producer_projects_tuple_containers(self):
        ground = flat_ground()
        base = trusted_block()
        expected = snapshot(blob(),
                            calibration=calibration_with(ground, base),
                            ground=ground)["coordinate"]["ground"]
        for rotation, translation in self.COMBOS:
            with self.subTest(rotation_tuple=rotation, translation_tuple=translation):
                block = _tuple_block(base, rotation=rotation,
                                     translation=translation)
                artifact = calibration_with(ground, block)
                snap = snapshot(blob(), calibration=artifact, ground=ground)
                cg = snap["coordinate"]["ground"]
                self.assertIsInstance(cg, dict)
                self.assertEqual(cg["R"], expected["R"])
                self.assertEqual(cg["t"], expected["t"])
                self.assertEqual(cg["ground_derived_id"],
                                 base["ground_derived_id"])
                validate_snapshot(snap)

    def test_actual_nodecore_tuple_containers_to_preview_js(self):
        ground = flat_ground()
        base = trusted_block()
        for rotation, translation in self.COMBOS:
            with self.subTest(rotation_tuple=rotation, translation_tuple=translation):
                block = _tuple_block(base, rotation=rotation,
                                     translation=translation)
                artifact = calibration_with(ground, block)
                core = FallNodeCore("s1", _settings(), expected_frame=FROM_FRAME,
                                    ground=ground, calibration=artifact)
                result = core.process(blob(), 1.0, seq=1, stamp_secs=100,
                                      stamp_nsecs=0, frame_id=FROM_FRAME, now=1.0)
                snap = result["snapshot"]
                cg = snap["coordinate"]["ground"]
                self.assertIsInstance(cg, dict)
                self.assertEqual(cg["R"], base["R"])
                self.assertEqual(cg["t"], base["t"])
                payload = dumps_strict(project_snapshot_for_ros(snap))
                done = _preview_parse(payload, expect="ready")
                self.assertEqual(done.returncode, 0, done.stderr)
                parsed = json.loads(
                    done.stdout.split("GLP01_CONSUMER_OK", 1)[1].strip())
                self.assertEqual(parsed["parse_status"], "ready")
                self.assertEqual(parsed["support_status"], "unavailable")
                self.assertEqual(parsed["ground_R"], base["R"])
                self.assertEqual(parsed["ground_t"], base["t"])
                self.assertEqual(parsed["ground_derived_id"],
                                 base["ground_derived_id"])

    def test_preview_js_reports_unqualified_and_unavailable(self):
        # artifact-only (validated derived, unknown ground_status): unqualified
        snap = snapshot(blob(),
                        calibration=calibration_with(flat_ground(),
                                                     trusted_block()))
        done = _preview_parse(dumps_strict(project_snapshot_for_ros(snap)),
                              expect="unqualified")
        self.assertEqual(done.returncode, 0, done.stderr)
        # no embedded derived block: unavailable
        ground = flat_ground()
        snap = snapshot(blob(), calibration=calibration_with(ground, None),
                        ground=ground)
        done = _preview_parse(dumps_strict(project_snapshot_for_ros(snap)),
                              expect="unavailable")
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
