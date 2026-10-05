"""GL-E02 contract checks. All asserted physical facts are synthetic fixtures."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.capture_input import load_adapted, prepare_npz, sha256_file, source_identity
from core.ground_evidence import (MEASUREMENTS, RUN_ROOT, prepare_packet,
                                 read_json, read_bound_json, request_id, selection_id)
from test_gli01_capture_input import write_export


def unknown():
    return dict(status="unknown", value=None, unit=None, uncertainty=None,
                frame=None, reference=None, method=None, evidence_refs=[],
                binding=None, observer=None, observed_at=None, basis=None)


class GroundEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gle02-")
        self.root = Path(self.tmp.name)
        self.outbase = self.root / RUN_ROOT
        self.outbase.mkdir(parents=True)
        self.source = self.root / "source"
        write_export(self.source, counts=(4, 4, 4, 4))
        npz = self.root / "source.npz"
        prepare_npz(str(self.source), "innolidar", "m", str(npz))
        self.manifest, self.points = load_adapted(npz)
        m = self.manifest
        bag = m["source"]["source_bag_sha256_declared"]
        chain = dict(kind="original_bag_canonical_chain_observation", schema=1,
                     source=dict(sha256_before=bag, sha256_after=bag),
                     canonical_bin_sha256=m["source"]["bin_sha256"],
                     canonical_xyz_sha256=m["points"]["sha256"],
                     frames=[dict(f, frame_id="innolidar") for f in m["frames"]])
        audit = dict(kind="original_bag_bin_npz_chain_audit", schema=1,
                     all_headers_layout_bytes_xyz_match=True,
                     source_bag_sha256_verified=bag,
                     meta_sha256=m["source"]["meta_sha256"],
                     bin_sha256=m["source"]["bin_sha256"], npz_sha256=sha256_file(npz),
                     xyz_sha256=m["points"]["sha256"])
        photo = self.root / "photo.png"
        photo.write_bytes(b"synthetic fixture photo, not a real scene")
        photo_record = dict(kind="gle02_user_scene_reference", schema=1,
                            sha256=sha256_file(photo), scene_authenticity="user_confirmed",
                            reference_view_direction="user_confirmed_correct", physical_verified=False,
                            photo_capture_time=None, photo_to_20261002_recording_binding="unknown")
        files = {"npz": dict(path=str(npz), sha256=sha256_file(npz)),
                 "photo": dict(path=str(photo), sha256=sha256_file(photo))}
        for name, obj in (("chain", chain), ("audit", audit), ("photo_record", photo_record),
                          ("code", {"fixture": "code version"}), ("survey", {"fixture": "survey"})):
            p = self.root / (name + ".json")
            p.write_text(json.dumps(obj), encoding="utf8")
            files[name] = dict(path=str(p), sha256=sha256_file(p))
        binding = dict(source_id=source_identity(m["source"]["meta_sha256"], m["source"]["bin_sha256"]),
                       bag_sha256=bag, bin_sha256=m["source"]["bin_sha256"], frame="innolidar", units="m",
                       window_bag_time_sec=[m["frames"][0]["bag_time_sec"], m["frames"][-1]["bag_time_sec"]],
                       run_id=None, config_sha256=None, run_sha256=None, sdk_sha256=None,
                       code_sha256={"code": files["code"]["sha256"]})
        self.request = dict(kind="ground_evidence_request", schema=1, request_id="",
                            units="m", files=files, run=dict(run_id=None, config_ref=None,
                            run_ref=None, sdk_ref=None, code_refs=["code"]), expected_source=binding,
                            measurements={n: unknown() for n in MEASUREMENTS}, selection=None,
                            scene_plan=[dict(region_id="front", description="continuous floor before seam",
                                             status="spatial_plan_only")])
        self.sign()
        self.counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def sign(self):
        if self.request["selection"] is not None:
            self.request["selection"]["selection_id"] = selection_id(self.request["selection"])
        self.request["request_id"] = request_id(self.request)

    def run_packet(self, sign=True, output=None):
        if sign:
            self.sign()
        self.counter += 1
        return prepare_packet(self.request, output or self.outbase / ("out_%03d" % self.counter), self.root)

    def rejects(self, sign=True, output=None):
        with self.assertRaises((ValueError, OSError, KeyError, TypeError)):
            self.run_packet(sign, output)

    def measured(self, name, value, unit, reference=None):
        self.request["measurements"][name] = dict(
            status="known", value=value, unit=unit, uncertainty=0.01,
            frame="innolidar", reference=reference, method="survey", evidence_refs=["survey"],
            binding=None, observer="synthetic observer", observed_at="2026-10-04T15:00:00+08:00",
            basis="independent synthetic fixture")

    def selections(self):
        regions = []
        for i, (gid, group) in enumerate(self.manifest["frame_groups"].items()):
            regions.append(dict(region_id="synthetic_%d" % i, frame_group=gid,
                indices=list(range(*group["rows"])), source_sha256=self.request["expected_source"]["bin_sha256"],
                spatial_description="independent scene landmark %d" % i,
                selection_method="independent_manual_source_rows",
                confirmation=dict(status="user_confirmed", person="synthetic person",
                    time="2026-10-04T15:00:00+08:00", basis="scene and raw 3D landmarks, no fitted model",
                    evidence_refs=["survey"], landmarks=["synthetic tabletop edge vs floor"])))
        self.request["selection"] = dict(selection_id="synthetic selection v1", version=1,
            binding=copy.deepcopy(self.request["expected_source"]), fit=regions[0], validation=regions[1:])

    def test_pending_positive_determinism_and_no_promotion_Q01_Q06(self):
        a = self.run_packet()
        b = self.run_packet()
        self.assertEqual(a, b)
        self.assertEqual(a["kind"], "pending_evidence_packet")
        for field in ("physical_verified", "extrinsics_verified", "candidate_eligible", "runtime_eligible"):
            self.assertIs(a[field], False)
        self.assertIn("world_up_source", a["gaps"])
        outputs = sorted(p.name for p in (self.outbase / "out_001").iterdir())
        self.assertEqual(len(outputs), 5)
        a["binding"]["frame"] = "caller changed output"
        self.assertEqual(self.run_packet()["binding"]["frame"], "innolidar")

    def test_schema_missing_units_finite_Q01(self):
        original = copy.deepcopy(self.request)
        for field, value in (("schema", True), ("schema", 2), ("kind", "calibration"),
                             ("units", "mm"), ("units", float("nan"))):
            with self.subTest(field=field, value=value):
                self.request = copy.deepcopy(original)
                self.request[field] = value
                if isinstance(value, float):
                    self.rejects(sign=False)
                else:
                    self.rejects()
        self.request = copy.deepcopy(original)
        del self.request["measurements"]["source_axes"]
        self.rejects()
        self.request = copy.deepcopy(original)
        self.request["files"]["photo"]["path"] += ".missing"
        self.rejects()

    def test_identity_mutation_new_id_existing_output_Q02(self):
        self.run_packet()
        self.rejects(output=self.outbase / "out_001")
        self.request["scene_plan"][0]["description"] = "changed by caller"
        self.rejects(sign=False)
        self.sign()
        self.run_packet(sign=False)  # New content ID, no reused old output.
        Path(self.request["files"]["photo"]["path"]).write_bytes(b"same path other content")
        self.rejects()

    def test_protected_outputs_Q02(self):
        for target in (self.root / "captures" / "bad", self.root / "src" / "bad",
                       self.root / "docs/human_fall/evidence/old_evidence/out", self.outbase):
            with self.subTest(target=str(target)):
                self.rejects(output=target)
                if target != self.outbase:
                    self.assertFalse(target.exists())

    def test_chain_and_photo_identity_E01(self):
        original = copy.deepcopy(self.request)
        cases = [("chain", lambda v: v["source"].update(sha256_after="ef" * 32)),
                 ("chain", lambda v: v["frames"][0].update(seq=1)),
                 ("audit", lambda v: v.update(npz_sha256="cd" * 32)),
                 ("photo_record", lambda v: v.update(sha256="cd" * 32))]
        for i, (name, change) in enumerate(cases):
            with self.subTest(name=name, i=i):
                self.request = copy.deepcopy(original)
                obj, _ = read_json(original["files"][name]["path"])
                change(obj)
                p = self.root / ("changed%d.json" % i)
                p.write_text(json.dumps(obj), encoding="utf8")
                self.request["files"][name] = dict(path=str(p), sha256=sha256_file(p))
                self.rejects()

    def test_wrong_binding_and_current_config_Q03(self):
        original = copy.deepcopy(self.request)
        for key, value in (("frame", "world"), ("bin_sha256", "00" * 32),
                           ("window_bag_time_sec", [0.0, 1.0]), ("run_id", "foreign"),
                           ("config_sha256", "01" * 32), ("code_sha256", {})):
            with self.subTest(key=key):
                self.request = copy.deepcopy(original)
                self.request["expected_source"][key] = value
                self.rejects()
        self.request = original
        self.measured("world_up_source", [0, 0, 1], "unit_vector", "world_up")
        # Current/9-30 log observation, without 10-2 binding, stays unknown.
        self.request["measurements"]["world_up_source"]["basis"] = "current/2026-09-30 observation only"
        self.assertIn("world_up_source", self.run_packet()["gaps"])
        self.request["measurements"]["world_up_source"]["binding"] = {"run_id": "foreign"}
        self.rejects()

    def test_window_origin_PCA_direction_units_Q04(self):
        self.measured("optical_window_height_m", 1.1, "m", "optical_window")
        packet = self.run_packet()
        self.assertIn("origin_height_m", packet["gaps"])
        self.measured("origin_definition", "synthetic SDK origin definition", "description", "point_origin")
        self.measured("origin_height_m", 1.1, "m", "optical_window")
        self.rejects()
        self.request["measurements"]["origin_height_m"]["reference"] = "point_origin"
        self.request["measurements"]["origin_height_m"]["method"] = "fit_plane_offset"
        self.rejects()
        self.request["measurements"]["origin_height_m"]["method"] = "PCA"
        self.rejects()
        self.request["measurements"]["origin_height_m"]["method"] = "survey"
        self.request["measurements"]["origin_height_m"]["unit"] = "mm"
        self.rejects()
        self.request["measurements"]["origin_height_m"]["unit"] = "m"
        self.measured("world_up_source", [0, 0, 2], "unit_vector", "world_up")
        self.rejects()
        self.request["measurements"]["world_up_source"]["value"] = [0, 0, 1]
        self.request["measurements"]["world_up_source"]["uncertainty"] = -1
        self.rejects()
        self.request["measurements"]["world_up_source"]["uncertainty"] = 0.1
        self.measured("source_axes", dict(axes=["forward", "left", "up"], from_frame="innolidar",
            to_frame="sdk_native", rotation=np.eye(3).tolist(), translation_m=[0, 0, 0], enabled=True), "m")
        self.rejects()

    def test_rows_groups_alias_duplicates_cross_group_bounds_Q05(self):
        self.selections()
        packet = self.run_packet()
        self.assertFalse(packet["physical_verified"])
        s, _ = read_json(self.outbase / "out_001/selection_draft.json")
        self.assertEqual(s["selection"]["validation"][0]["members"][0],
                         dict(pooled_row=4, source_row=0, ordinal=1, seq=1979001))
        original = copy.deepcopy(self.request)
        changes = [lambda s: s["validation"][0].update(region_id=s["fit"]["region_id"]),
                   lambda s: s["validation"][0].update(indices=[4, 4]),
                   lambda s: s["validation"][0].update(indices=[-1]),
                   lambda s: s["validation"][0].update(indices=[16]),
                   lambda s: s["validation"][0].update(indices=[True]),
                   lambda s: s["validation"][0].update(indices=[0]),
                   lambda s: s["validation"][0].update(frame_group=s["fit"]["frame_group"], indices=[0]),
                   lambda s: s["validation"][1].update(frame_group=s["validation"][0]["frame_group"], indices=[4]),
                   lambda s: s["validation"][0].update(selection_method="FIT_residual_band"),
                   lambda s: s["validation"][0]["confirmation"].update(person=None),
                   lambda s: s["validation"][0]["confirmation"].update(landmarks=[]),
                   lambda s: s.update(validation=s["validation"][:2])]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                self.request = copy.deepcopy(original)
                change(self.request["selection"])
                self.rejects()

    def test_missing_ground_identity_pending_Q05_Q06(self):
        self.selections()
        self.request["selection"]["fit"]["confirmation"]["status"] = "unknown"
        self.assertIn("manual_ground_identity", self.run_packet()["gaps"])

    def test_real_photo_no_recording_no_rows_E03_E05(self):
        self.measured("photo_capture_time", "刚刚拍摄, exact time not supplied", "statement")
        p = self.run_packet()
        self.assertIn("photo_recording_binding", p["gaps"])
        self.assertIn("independent_fit_and_three_validation_source_rows", p["gaps"])
        record, _ = read_json(self.outbase / "out_001/evidence_index.json")
        self.assertEqual(record["photo_confirmation"]["scene_authenticity"], "user_confirmed")

    def test_all_fields_present_still_unreviewed_Q06(self):
        for key in ("config_ref", "run_ref", "sdk_ref"):
            self.request["run"][key] = "survey"
        self.request["run"]["run_id"] = "synthetic run"
        b = self.request["expected_source"]
        b["run_id"] = "synthetic run"
        for key in ("config_sha256", "run_sha256", "sdk_sha256"):
            b[key] = self.request["files"]["survey"]["sha256"]
        self.measured("origin_definition", "synthetic measured origin", "description", "point_origin")
        self.measured("origin_height_m", 1.4, "m", "point_origin")
        self.measured("optical_window_height_m", 1.1, "m", "optical_window")
        self.measured("world_up_source", [0, 0, 1], "unit_vector", "world_up")
        self.measured("source_axes", dict(axes=["forward", "left", "up"], from_frame="sdk_native",
            to_frame="innolidar", rotation=np.eye(3).tolist(), translation_m=[0, 0, 0], enabled=False), "m")
        self.measured("installation_angle_deg", 0.0, "deg", "mounting_direction")
        self.measured("photo_capture_time", "synthetic time", "statement")
        self.measured("photo_recording_binding", dict(photo_sha256=self.request["files"]["photo"]["sha256"],
                      installation_unchanged=True, scene_same=True), "statement")
        for record in self.request["measurements"].values():
            record["binding"] = copy.deepcopy(b)
        self.selections()
        packet = self.run_packet()
        self.assertEqual(packet["gaps"], ["independent_physical_review_and_tolerances"])
        self.assertFalse(packet["candidate_eligible"])
        self.assertFalse(packet["physical_verified"])
        self.request["physical_verified"] = True
        self.rejects()

    def test_bad_json_nan_and_unsupported_output_fields_Q01_Q06(self):
        p = self.root / "bad.json"
        for value in ('{"v":NaN}', 'bad JSON', '{"v":Infinity}'):
            p.write_text(value, encoding="utf8")
            with self.assertRaises(ValueError):
                read_json(p)
        self.request["runtime_calibration"] = {"ground": {"status": "valid"}}
        self.rejects()

    def test_selection_same_id_different_content_and_new_id_Q02(self):
        self.selections()
        self.run_packet()
        old_id = self.request["selection"]["selection_id"]
        self.request["selection"]["fit"]["indices"] = [1, 2, 3]
        self.request["request_id"] = request_id(self.request)
        self.rejects(sign=False)
        self.sign()
        self.assertNotEqual(old_id, self.request["selection"]["selection_id"])
        self.run_packet(sign=False)

    def test_numeric_string_bool_sdk_and_negative_height_Q01_Q04(self):
        self.measured("source_axes", dict(axes=["forward", "left", "up"], from_frame="sdk_native",
            to_frame="innolidar", rotation=np.eye(3).tolist(), translation_m=[0, 0, 0], enabled=True), "m")
        record = self.request["measurements"]["source_axes"]
        for bad in (True, "1", None):
            with self.subTest(bad=bad):
                record["value"]["rotation"][0][0] = bad
                self.rejects()
        record["value"]["rotation"][0][0] = 1
        self.measured("optical_window_height_m", -1, "m", "optical_window")
        self.rejects()

    def test_parsed_snapshot_must_match_bound_file_E01_Q02(self):
        from unittest.mock import patch
        ref = self.request["files"]["chain"]
        with patch("core.ground_evidence.read_json", return_value=({"foreign": True}, "00" * 32)):
            with self.assertRaises(ValueError):
                read_bound_json(ref)


if __name__ == "__main__":
    unittest.main()
