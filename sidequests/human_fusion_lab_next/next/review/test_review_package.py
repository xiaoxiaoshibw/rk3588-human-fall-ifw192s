# -*- coding: utf-8 -*-
"""HFUS-D02 待审包单元测试（unittest, -B -W error discover 兼容）。

合成数据层：不依赖真实 captures 也能跑（解码/绑定/资格/导出回读/机器不升级人工）。
真实回读层（TestPackageRealReadback）：仅当磁盘上已有 review_package.jsonl 时回读其结构；
真实文件不存在时 skipTest（不伪造 PASS）。
"""
import json
import os
import sys
import unittest

_D = os.path.dirname(os.path.abspath(__file__))
if _D not in sys.path:
    sys.path.insert(0, _D)

import review_loader as L          # noqa: E402
import review_export as E          # noqa: E402
import review_schema as SC         # noqa: E402
import review_qualify as Q         # noqa: E402
import review_split as SP          # noqa: E402

REVIEW_OUT = os.path.join(_D, "review_out")
PACKAGE_JSONL = os.path.join(REVIEW_OUT, "review_package.jsonl")
PACKAGE_MANIFEST = os.path.join(REVIEW_OUT, "review_package.manifest.json")


class TestIndexBinding(unittest.TestCase):
    """索引绑定：decode 三格式 + compact→raw 映射 + 域命名."""

    def test_decode_s_r_m(self):
        self.assertEqual(L.decode_indices(["s", 3, 1, 2]), [3, 1, 2])
        self.assertEqual(L.decode_indices(["r", 10, 2, 4]), [10, 12, 14, 16])
        self.assertEqual(L.decode_indices(
            ["m", [0, 2, 3, 50, 5, 2], [7, 9]]), [0, 2, 4, 50, 55, 7, 9])

    def test_decode_rejects_bad(self):
        # [] 是合法空集合（返回 []），不属非法；只验真非法输入
        # 含 ['m'] 缺 runs/tail —— 必须 ValueError（曾被 IndexError，见复审 LOW）
        for bad in (["x", 1], ["r", 0, -1, 3], ["m", [1, 2], []], ["m"]):
            with self.assertRaises(ValueError):
                L.decode_indices(bad)
        self.assertEqual(L.decode_indices([]), [])
        self.assertEqual(L.decode_indices(None), [])

    def test_s6_bg_loss_and_no_candidate_not_eaten_by_coverage_gap(self):
        # 复审 HIGH：S6 f187/188 bg_loss、f91/128/129/130/171 no_candidate
        # 必须得到 UNKNOWN + 具体 reason，不被非穷尽 PARTIAL/coverage_gap 吃掉。
        bg = Q.qualify_record(label_source="human", sha_binding_ok=True,
                              exhaustive=False,      # S6 非穷尽（ds['exhaustive']=False）
                              has_gt_human=True, has_candidate=False, bg_loss=True)
        self.assertEqual(bg["qualification"], "UNKNOWN")
        self.assertEqual(bg["reason"], "bg_loss")
        nc = Q.qualify_record(label_source="human", sha_binding_ok=True,
                              exhaustive=False, has_gt_human=True,
                              has_candidate=False, bg_loss=False)
        self.assertEqual(nc["qualification"], "UNKNOWN")
        self.assertEqual(nc["reason"], "no_candidate")
        # has_candidate=True 时（候选未知诚实声明）才允许落 PARTIAL/coverage_gap
        na = Q.qualify_record(label_source="human", sha_binding_ok=True,
                              exhaustive=False, has_gt_human=True,
                              has_candidate=True)
        self.assertEqual(na["qualification"], "PARTIAL")
        self.assertEqual(na["reason"], "coverage_gap")

    def test_compact_maps_filter_invalid(self):
        xyz = [(1.0, 1.0, 1.0), (0.0, 0.0, 0.0), (float("nan"), 0, 0),
               (2.0, 3.0, 4.0), (0.0, 5.0, 0.0)]
        m = L.build_compact_maps(xyz)
        self.assertEqual(m["raw_of_leaf"], [0, 3, 4])
        self.assertEqual(m["n_leveled"], 3)

    def test_compact_to_raw_translation(self):
        m = L.build_compact_maps([(1.0, 1.0, 1.0), (2.0, 2.0, 2.0), (3.0, 3.0, 3.0)])
        r = L.object_member_raw_indices(["s", 0, 2, 5], m["raw_of_leaf"])
        self.assertEqual(r["raw_indices"], [0, 2])
        self.assertEqual(r["out_of_bounds"], 1)

    def test_index_domain_constants_distinct(self):
        self.assertNotEqual(SC.INDEX_DOMAIN_RAW28, SC.INDEX_DOMAIN_COMPACT)
        self.assertNotEqual(SC.INDEX_DOMAIN_COMPACT, SC.INDEX_DOMAIN_LEVELED)


class TestMachineNeverUpgradesHuman(unittest.TestCase):
    """机器永不写 reviewed / BOUND_HUMAN_REVIEWED（含硬门）."""

    def test_qualify_broken_binding(self):
        r = Q.qualify_record(label_source="human", sha_binding_ok=False,
                             exhaustive=True, has_gt_human=True, has_candidate=False)
        self.assertEqual(r["qualification"], "INVALID_BINDING")
        self.assertEqual(r["review_status"], "unreviewed")

    def test_qualify_never_reviewed_for_any_input(self):
        cases = [
            dict(label_source=s, sha_binding_ok=b, exhaustive=e,
                 has_gt_human=True, has_candidate=c)
            for s in ("human", "model", "propagated", "model_suspect")
            for b in (True, False) for e in (True, False) for c in (True, False)
        ]
        for kw in cases:
            r = Q.qualify_record(**kw)
            self.assertNotEqual(r["review_status"], "reviewed")
            self.assertNotEqual(r["qualification"], "BOUND_HUMAN_REVIEWED")

    def test_validate_no_human_auto_rejects_human_injection(self):
        with self.assertRaises(AssertionError):
            Q.validate_no_human_auto([{"review_status": "reviewed"}])
        with self.assertRaises(AssertionError):
            Q.validate_no_human_auto([{"qualification": "BOUND_HUMAN_REVIEWED"}])

    def test_make_review_item_refuses_reviewed(self):
        with self.assertRaises(ValueError):
            E.make_review_item(
                session_id="s", frame_idx=0, timestamp_s=0.0,
                raw_input_sha256={"meta": "a" * 64, "points": "b" * 64},
                index_domain=SC.INDEX_DOMAIN_COMPACT,
                member_point_raw=[0], member_point_compact=[0],
                label_source="human", review_status="reviewed",
                qualification="UNKNOWN", reason=None, class_name="person")

    def test_export_refuse_dup_and_negative_members(self):
        base = dict(session_id="s", frame_idx=0, timestamp_s=0.0,
                    raw_input_sha256={"meta": "a" * 64, "points": "b" * 64},
                    index_domain=SC.INDEX_DOMAIN_COMPACT,
                    member_point_compact=[0], label_source="human",
                    review_status="draft", qualification="UNKNOWN",
                    reason=None, class_name="person")
        with self.assertRaises(ValueError):
            E.make_review_item(member_point_raw=[1, 1], **base)
        with self.assertRaises(ValueError):
            E.make_review_item(member_point_raw=[-1], **base)


class TestExportRoundtrip(unittest.TestCase):
    """导出回读：write_package → read_package，manifest sha 对账."""

    def test_write_read_roundtrip_and_hash(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        sha = {"meta": "a" * 64, "points": "b" * 64}
        recs = [E.make_review_item(
            session_id="s", frame_idx=i, timestamp_s=float(i),
            raw_input_sha256=sha, index_domain=SC.INDEX_DOMAIN_COMPACT,
            member_point_raw=[i], member_point_compact=[i],
            label_source="human", review_status="draft",
            qualification="UNKNOWN", reason="no_candidate", class_name="person")
            for i in range(3)]
        recs.append(E.make_review_item(
            session_id="s", frame_idx=99, timestamp_s=9.0,
            raw_input_sha256=sha, index_domain=SC.INDEX_DOMAIN_COMPACT,
            member_point_raw=[9], member_point_compact=[9],
            label_source="human", review_status="draft",
            qualification="UNKNOWN", reason=None, class_name="person"))
        out = E.write_package(recs, tmp, "t", "2026-10-11T00:00:00Z")
        back = E.read_package(out["jsonl_path"])
        self.assertEqual(back["n"], 4)
        self.assertEqual(out["manifest"]["per_reason"].get("(none)"), 1)
        import hashlib
        with open(out["jsonl_path"], "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(),
                             out["manifest"]["output_jsonl_sha256"])


class TestSplitLeakage(unittest.TestCase):
    """split：同会话单 fold、跨 fold 重复必须为 0、负例分级."""

    def test_cross_fold_duplicate_detected(self):
        recs = [
            {"session_id": "A", "fold": "train", "dedup_hash": "h1", "class_name": "p"},
            {"session_id": "B", "fold": "test", "dedup_hash": "h1", "class_name": "p"},
        ]
        r = SP.cross_fold_exact_duplicate_check(recs)
        self.assertEqual(r["exact_duplicate"], 1)

    def test_clean_session_zero_duplicate(self):
        recs = [
            {"session_id": "A", "fold": "train", "dedup_hash": "h1", "class_name": "p"},
            {"session_id": "B", "fold": "test", "dedup_hash": "h2", "class_name": "p"},
        ]
        r = SP.cross_fold_exact_duplicate_check(recs)
        self.assertEqual(r["exact_duplicate"], 0)

    def test_session_stays_in_one_fold(self):
        draft = SP.build_split_draft([
            {"session_id": "S9", "n_frames": 126, "n_positive_frames": 0,
             "n_negative_candidates": 0, "eligible": False,
             "role_hint": "blocked", "reason": "broken"},
            {"session_id": "S1", "n_frames": 304, "n_positive_frames": 0,
             "n_negative_candidates": 1824, "eligible": True, "role_hint": "train"},
        ])
        self.assertIn("S9", [s["session_id"] for s in draft["folds"]["blocked"]])
        self.assertIn("S1", [s["session_id"] for s in draft["folds"]["train"]])
        # 同一会话只能出现在一个 fold
        sess_ids = [s["session_id"] for f in draft["folds"].values() for s in f]
        self.assertEqual(len(sess_ids), len(set(sess_ids)))

    def test_negative_report_model_suspect_vs_reviewed(self):
        report = SP.negative_evidence_report([
            {"candidate_id": "c1", "session_id": "s", "fold": "train",
             "label_source": "model_suspect", "review_status": "draft",
             "qualification": "UNKNOWN"},
            {"candidate_id": "c2", "session_id": "s", "fold": "test",
             "label_source": "human", "review_status": "reviewed",
             "qualification": "BOUND_HUMAN_REVIEWED"},
        ])
        self.assertEqual(len(report["model_suspect_negatives"]), 1)
        self.assertEqual(len(report["reviewed_negatives"]), 1)


@unittest.skipUnless(os.path.exists(PACKAGE_JSONL),
                     "真实 review_package.jsonl 未生成；先跑 build_review_package.py")
class TestPackageRealReadback(unittest.TestCase):
    """真实包回读（结构级，不重复跑算法）。仅校验已落盘包的结构与硬门。"""

    def test_no_auto_reviewed_in_real_package(self):
        with open(PACKAGE_JSONL, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                self.assertNotEqual(r["review_status"], "reviewed")
                self.assertNotEqual(r["qualification"], "BOUND_HUMAN_REVIEWED")
                self.assertIn(r["index_domain"],
                              (SC.INDEX_DOMAIN_COMPACT, SC.INDEX_DOMAIN_RAW28))
                for v in r["member_point_raw"]:
                    self.assertGreaterEqual(v, 0)

    def test_manifest_consistent_with_jsonl(self):
        with open(PACKAGE_MANIFEST, encoding="utf-8") as fh:
            man = json.load(fh)
        with open(PACKAGE_JSONL, encoding="utf-8") as fh:
            n = sum(1 for l in fh if l.strip())
        self.assertEqual(man["n_records"], n)
        import hashlib
        with open(PACKAGE_JSONL, "rb") as f:
            self.assertEqual(hashlib.sha256(f.read()).hexdigest(),
                             man["output_jsonl_sha256"])


if __name__ == "__main__":
    unittest.main()
