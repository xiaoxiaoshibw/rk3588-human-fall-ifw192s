# -*- coding: utf-8 -*-
"""gt_audit_fix_test.py — OpenCode 审计修复回归 (R1 → R2)。

覆盖 OpenCode OPENCODE_INDEPENDENT_REVIEW.md 抓出的具体失败模式；
每条对应 Q# 的 FAIL 案例，修后必须 PASS。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gt_server as G  # noqa: E402


def _draft(n_objects=1, source="human", review_status="unreviewed"):
    doc = {
        "schema_version": "gt_workbench/1",
        "session_id": "cap_20261010_175227",
        "session_sha256": {"points": "ab" * 32, "meta": "cd" * 32},
        "annotator": "tester", "review_status": "draft",
        "objects": {}, "frames_objects": {},
        "frozen_versions": [], "history": [], "annotated_at": None,
    }
    for i in range(n_objects):
        oid = "obj_%d" % i
        doc["objects"][oid] = {
            "session_id": doc["session_id"], "frame_id": "x:%d" % i,
            "frame_idx": i, "timestamp": i * 0.1, "object_id": oid,
            "track_id": "P1", "class_name": "PERSON",
            "box_xy": [i, 1, i + 1, 2], "z_min": 0.05, "z_max": 2.3,
            "raw_point_indices": ["s", 10 + i, 20 + i], "point_count": 2,
            "coordinate_frame": "leveled-IFW192S",
            "leveling_transform_id": "render_person_label.R/T",
            "source": source, "review_status": review_status,
            "annotator": "tester", "schema_version": "gt_workbench/1",
        }
        doc["frames_objects"][str(i)] = [oid]
    return doc


class AuditFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="gt_audit_")
        self._orig = G.STORE
        G.STORE = os.path.join(self.tmp, "gt_store")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        G.STORE = self._orig

    def test_second_save_does_not_409(self):
        doc = _draft(1)
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)

        class H:
            def _json(self, obj, code=200): self.res = (obj, code)
        h = H()
        # 保存第一遍
        G._save_draft(h, {"sid": doc["session_id"], "doc": doc, "expected_sha": None}, None)
        payload1, code1 = h.res
        self.assertTrue(payload1["ok"], payload1)
        sha1 = payload1["sha256"]
        # 再保存同一 doc, 带 returned sha → 不应 409（annotated_at 重写虽可能致 sha 变，但 409 先于 annotated_at）
        # OpenCode 残留风险：annotated_at 每秒重写导致 sha 变 — fix:守卫失败仍 200 时,
        # 用 expected_sha 指定 sha1 就应该通过(守卫读旧稿自身 sha 比较),不在乎新 blob 是不是同 sha
        G._save_draft(h, {"sid": doc["session_id"], "doc": doc, "expected_sha": sha1}, None)
        payload2, code2 = h.res
        self.assertTrue(payload2["ok"], payload2)
        self.assertEqual(code2, 200, payload2)

    def test_save_returns_sha_matching_doc_blob(self):
        doc = _draft(1)
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)

        class H:
            def _json(self, obj, code=200): self.res = (obj, code)
        h = H()
        G._save_draft(h, {"sid": doc["session_id"], "doc": doc, "expected_sha": None}, None)
        payload, _ = h.res
        draft_path = os.path.join(sdir, "draft.json")
        with open(draft_path, "rb") as fh:
            actual = G._sha256_hex(fh.read())
        self.assertEqual(payload["sha256"], actual)

    # FIX-AUDIT-Q2: freeze 拒绝 unreviewed 动物
    def test_freeze_rejects_unreviewed_objects(self):
        doc = _draft(2, review_status="unreviewed")
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "draft.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

        class H:
            def _json(self, obj, code=200): self.res = (obj, code)
        h = H()
        G._freeze(h, {"sid": doc["session_id"], "annotator": "tester"})
        payload, code = h.res
        self.assertFalse(payload["ok"])
        self.assertEqual(code, 400)
        # Windows GBK 中文 mojibake 兼容： 用 unicode invariant 片段
        self.assertIn("2", payload["error"])
        self.assertIn("n_unreviewed", payload, payload)

    def test_freeze_passes_all_reviewed(self):
        doc = _draft(2, review_status="reviewed")
        sdir = G._sid_dir(doc["session_id"])
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "draft.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

        class H:
            def _json(self, obj, code=200): self.res = (obj, code)
        h = H()
        G._freeze(h, {"sid": doc["session_id"], "annotator": "tester"})
        payload, code = h.res
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["version"], "V1")
        gt_path = os.path.join(sdir, "GT_V1.json")
        self.assertTrue(os.path.isfile(gt_path))
        # GT_V*.json 也是原子写的 (临时 .tmp 不存在)
        self.assertFalse(os.path.exists(gt_path + ".tmp"))

    # FIX-AUDIT-Q3: gt_suggest 索引映射（raw ↦ compact）
    def test_gt_suggest_index_translation(self):
        # synthesize：raw 中插入了部分全零/NaN 点，确保投影 ≠ identity
        import subprocess
        res = subprocess.run(
            ["node", "-e",
             "var G=require('./pc_apps/human_replay/gt_lib.js');"
             "var S=require('./pc_apps/human_replay/gt_suggest.js');"
             "var raw=new Float32Array([1,0,0,0, 0,0,0,0, 2,0,0,0, 0,0,0,0, 3,0,0,0, 4,0,0,0]);"
             "var sp=G.split_frame_indices(raw,4);"
             "var idx=S.raw_to_compact_frame_indices([0,2,4,5], sp.leaf_of_raw);"
             "console.log(JSON.stringify(idx));"],
            capture_output=True, text=True, cwd=os.path.normpath(
                os.path.join(os.path.dirname(__file__), "..", "..")))
        self.assertEqual(res.returncode, 0, res.stderr)
        idx = json.loads(res.stdout.strip())
        # raw idx [0,2,4,5] 中 idx=1 与 3(0/NaN) 被滤 → compact = [0,1,2,3]
        self.assertEqual(idx, [0, 1, 2, 3])

    # FIX-AUDIT-Q5: meta_sha ≠ points_sha 必须分流
    def test_get_session_returns_distinct_points_and_meta_sha(self):
        # 启动真 server 端不现实，这里直接测字段在 dictionary 上
        # 用 FakeHandler 走 read/write 流程
        meta_dir = tempfile.mkdtemp(prefix="meta_")
        try:
            sid = "cap_20261010_175227"
            os.makedirs(os.path.join(meta_dir, sid))
            meta_path = os.path.join(meta_dir, sid, "meta.json")
            bin_path = os.path.join(meta_dir, sid, "points.bin")
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump({"frames": [], "session_id": sid}, fh)
            with open(bin_path, "wb") as fh:
                fh.write(b"\x01" * 1024)

            class H:
                def __init__(self):
                    self.path = "/api/gt/session?sid=" + sid

                def _json(self, obj, code=200):
                    self.res = (obj, code)
            h = H()
            G._get_session(h, meta_dir)
            payload, _ = h.res
            self.assertTrue(payload["ok"], payload)
            self.assertIsNotNone(payload.get("points_sha"))
            self.assertIsNotNone(payload.get("meta_sha"))
            self.assertNotEqual(payload["points_sha"], payload["meta_sha"])
        finally:
            shutil.rmtree(meta_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
