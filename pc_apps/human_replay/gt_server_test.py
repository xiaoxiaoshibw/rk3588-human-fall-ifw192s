# -*- coding: utf-8 -*-
"""gt_server_test.py — HUMAN-GT-ANNOTATOR-R1 服务端持久化 + freeze SHA 守卫测试。

跑法：python -m unittest pc_apps.human_replay.gt_server_test -v
或：    python pc_apps/human_replay/gt_server_test.py
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gt_server as G  # noqa: E402


class AtomicStore(unittest.TestCase):
    """STEP 6 的工件：save→freeze→导出、原子写崩溃恢复、SHA 指纹稳定。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gt_test_")
        self._orig_store = G.STORE
        G.STORE = os.path.join(self.tmp, "gt_store")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        G.STORE = self._orig_store

    def _draft(self, n_objects=1):
        doc = {
            "schema_version": "gt_workbench/1",
            "session_id": "cap_20261010_175227",
            "session_sha256": {"points": "ab" * 32, "meta": "cd" * 32},
            "annotator": "tester",
            "review_status": "draft",
            "objects": {},
            "frames_objects": {},
            "frozen_versions": [],
            "history": [],
            "annotated_at": None,
        }
        for i in range(n_objects):
            oid = "obj_%d" % i
            doc["objects"][oid] = {
                "session_id": doc["session_id"], "frame_id": "cap_20261010_175227:%d" % i,
                "frame_idx": i, "timestamp": i * 0.104, "object_id": oid,
                "track_id": "P1", "class_name": "PERSON",
                "box_xy": [1.0 + i, 1.0, 2.0 + i, 2.0],
                "z_min": 0.05, "z_max": 2.3,
                "raw_point_indices": ["s", 10 + i, 20 + i],
                "point_count": 2,
                "coordinate_frame": "leveled-IFW192S",
                "leveling_transform_id": "render_person_label.R/T",
                "source": "human", "review_status": "unreviewed",
                "annotator": "tester", "schema_version": "gt_workbench/1",
            }
            doc["frames_objects"][str(i)] = [oid]
        return doc

    def test_sha256_hex_stable(self):
        s = '{"a":1}'
        h1 = G._sha256_hex(s)
        h2 = G._sha256_hex(s.encode("utf-8"))
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_atomic_write_produces_backup_and_tmp_gone(self):
        p = os.path.join(self.tmp, "d.json")
        G._atomic_write(p, b'{"v":1}')
        self.assertTrue(os.path.isfile(p))
        self.assertFalse(os.path.exists(p + ".tmp"))
        G._atomic_write(p, b'{"v":2}')
        self.assertTrue(os.path.isfile(p + ".bak"))
        with open(p + ".bak", encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '{"v":1}')
        with open(p, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), '{"v":2}')

    def test_validate_doc_rejects_model_marked_reviewed(self):
        doc = self._draft(1)
        doc["objects"]["obj_0"]["source"] = "model"
        doc["objects"]["obj_0"]["review_status"] = "reviewed"
        errs = G._validate_doc(doc)
        self.assertTrue(any("reviewed" in e and "model" in e for e in errs),
                        "model 冒充 reviewed 必须被拒: %s" % errs)

    def test_validate_doc_person_track_id_required(self):
        doc = self._draft(1)
        del doc["objects"]["obj_0"]["track_id"]
        errs = G._validate_doc(doc)
        self.assertTrue(any("track_id" in e for e in errs), errs)

    def test_validate_doc_passes_clean_doc(self):
        errs = G._validate_doc(self._draft(1))
        self.assertEqual(errs, [], errs)

    def test_validate_doc_same_frame_same_track_rejected(self):
        doc = self._draft(2)
        doc["objects"]["obj_1"]["frame_idx"] = 0     # 同帧 + 同 track
        errs = G._validate_doc(doc)
        self.assertTrue(any("同帧" in e for e in errs), errs)

    def test_freeze_produces_version_and_sha(self):
        doc = self._draft(1)
        # FIX-AUDIT-Q2: 需对象 reviewed 才能冻结
        for o in doc["objects"].values():
            o["review_status"] = "reviewed"
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)
        blob = json.dumps(doc, ensure_ascii=False).encode("utf-8")
        G._atomic_write(os.path.join(sdir, "draft.json"), blob)

        class FakeHandler:
            def __init__(self):
                self.handled = None

            def _json(self, obj, code=200):
                self.handled = (obj, code)

        h = FakeHandler()
        G._freeze(h, {"sid": doc["session_id"], "annotator": "tester"})
        payload, code = h.handled
        self.assertEqual(code, 200, payload)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["version"], "V1")
        self.assertEqual(len(payload["sha256"]), 64)
        # GT_V1.json 存在且 sha 对上
        gt_path = os.path.join(sdir, "GT_V1.json")
        self.assertTrue(os.path.isfile(gt_path))
        with open(gt_path, "rb") as fh:
            actual_sha = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(actual_sha, payload["sha256"])
        # manifest 记录
        manifest = G._read_json(os.path.join(sdir, "manifest.json"))
        self.assertEqual(manifest["versions"][0]["version"], "V1")
        # 二次冻结 → V2 递增
        G._freeze(h, {"sid": doc["session_id"], "annotator": "tester"})
        payload2, _ = h.handled
        self.assertEqual(payload2["version"], "V2")

    def test_freeze_needs_annotator_when_doc_none(self):
        doc = self._draft(1)
        doc["annotator"] = None
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)
        G._atomic_write(os.path.join(sdir, "draft.json"),
                        json.dumps(doc, ensure_ascii=False).encode("utf-8"))

        class FakeHandler:
            def _json(self, obj, code=200):
                self.handled = (obj, code)

        h = FakeHandler()
        G._freeze(h, {"sid": doc["session_id"]})     # body 无 annotator
        payload, code = h.handled
        self.assertFalse(payload["ok"])
        self.assertIn("annotator", payload["error"])

    def test_freeze_reject_invalid_schema_state(self):
        doc = self._draft(1)
        doc["objects"]["obj_0"]["raw_point_indices"] = None   # 校验应失败
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)
        G._atomic_write(os.path.join(sdir, "draft.json"),
                        json.dumps(doc, ensure_ascii=False).encode("utf-8"))

        class FakeHandler:
            def _json(self, obj, code=200):
                self.handled = (obj, code)

        h = FakeHandler()
        G._freeze(h, {"sid": doc["session_id"], "annotator": "x"})
        payload, code = h.handled
        self.assertEqual(code, 400, payload)
        self.assertFalse(payload["ok"])

    def test_sid_whitelist(self):
        self.assertTrue(G._sid_ok("cap_20261010_175227"))
        self.assertTrue(G._sid_ok("synth_bend_v1"))           # 2026-10-12 放宽：PC 生成会话可标
        self.assertTrue(G._sid_ok("cap_20261002_165321_clip_1989287-1989294"))
        self.assertFalse(G._sid_ok("../etc"))
        self.assertFalse(G._sid_ok("cap_a b"))                # 空格仍拒
        self.assertFalse(G._sid_ok("cap_x/y"))                # 斜杠仍拒
        self.assertFalse(G._sid_ok("."))                      # 隐藏/相对路径仍拒
        self.assertFalse(G._sid_ok(""))


if __name__ == "__main__":
    unittest.main()
