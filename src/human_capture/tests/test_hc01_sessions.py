"""HC-01 验收 H3/H5：会话 CRUD + 状态机迁移 + 并发原子写（不经 HTTP，直测 store）。

H4 持久化见 test_hc01_persistence.py。
"""

import json
import os
import sys
import tempfile
import threading
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from core.session_store import (LEGAL_TRANSITIONS, SessionStore,
                                validate_session_id)


def _mkstore():
    tmp = tempfile.mkdtemp(prefix="hc01_store_")
    return SessionStore(os.path.join(tmp, "sessions.json")), tmp


def _meta(sid, state="recording", created="2026-10-02T14:30:12+08:00"):
    return {"session_id": sid, "state": state, "created_iso": created,
            "duration_sec": 0.0, "frame_count": 0}


class TestValidateId(unittest.TestCase):
    def test_accepts_normal(self):
        self.assertTrue(validate_session_id("cap_20261002_143012"))

    def test_rejects_path_traversal(self):
        for bad in ("../x", "a/b", "a b", "", None, "x" * 200, "a;b", "a=b"):
            self.assertFalse(validate_session_id(bad), repr(bad))


class TestCrud(unittest.TestCase):
    def setUp(self):
        self.store, self.tmp = _mkstore()

    def test_upsert_get_list_order(self):
        self.store.upsert(_meta("cap_002", created="2026-10-02T14:31:00+08:00"))
        self.store.upsert(_meta("cap_001", created="2026-10-02T14:30:00+08:00"))
        ids = [s["session_id"] for s in self.store.list_sessions()]
        self.assertEqual(ids, ["cap_002", "cap_001"])  # 倒序，新在前

    def test_upsert_replaces_in_place(self):
        self.store.upsert(_meta("cap_1"))
        self.store.upsert(_meta("cap_1", state="ready"))
        self.assertEqual(self.store.get("cap_1")["state"], "ready")
        self.assertEqual(len(self.store.list_sessions()), 1)

    def test_missing_required(self):
        with self.assertRaises(ValueError):
            self.store.upsert({"session_id": "x"})  # 缺 state/created_iso

    def test_bad_state(self):
        with self.assertRaises(ValueError):
            self.store.upsert(_meta("x", state="bogus"))

    def test_unknown_get(self):
        self.assertIsNone(self.store.get("cap_nope"))
        self.assertIsNone(self.store.get("../evil"))

    def test_delete(self):
        self.store.upsert(_meta("cap_1"))
        self.assertTrue(self.store.delete("cap_1"))
        self.assertIsNone(self.store.get("cap_1"))
        self.assertFalse(self.store.delete("cap_1"))  # 幂等 false


class TestStateMachine(unittest.TestCase):
    def setUp(self):
        self.store, self.tmp = _mkstore()
        self.store.upsert(_meta("cap_1"))

    def test_happy_path(self):
        for nxt in ("extracting", "ready", "transferring", "transferred", "purged"):
            ok, reason = self.store.transition("cap_1", nxt)
            self.assertTrue(ok, reason)
        self.assertEqual(self.store.get("cap_1")["state"], "purged")

    def test_illegal_jump_rejected(self):
        # recording 不能直接 ready（必须经 extracting）
        self.store.upsert(_meta("cap_2"))
        ok, reason = self.store.transition("cap_2", "ready")
        self.assertFalse(ok)
        self.assertIn("非法迁移", reason)
        self.assertEqual(self.store.get("cap_2")["state"], "recording")

    def test_terminal_purged_cannot_move(self):
        self.store.upsert(_meta("cap_3", state="purged"))
        for nxt in LEGAL_TRANSITIONS:
            ok, _ = self.store.transition("cap_3", nxt)
            self.assertFalse(ok, nxt)

    def test_failed_can_retry_extracting(self):
        self.store.upsert(_meta("cap_4", state="extracting"))
        ok, _ = self.store.transition("cap_4", "failed", {"error": "bag 截断"})
        self.assertTrue(ok)
        self.assertEqual(self.store.get("cap_4")["error"], "bag 截断")
        ok, _ = self.store.transition("cap_4", "extracting")
        self.assertTrue(ok)

    def test_transfer_interrupted_back_to_ready(self):
        self.store.upsert(_meta("cap_5", state="transferring"))
        ok, _ = self.store.transition("cap_5", "ready")
        self.assertTrue(ok)

    def test_unknown_session(self):
        ok, reason = self.store.transition("cap_ghost", "ready")
        self.assertFalse(ok)
        self.assertEqual(reason, "会话不存在")

    def test_extra_fields_merged(self):
        self.store.transition("cap_1", "failed",
                              {"error": "x", "transferred": True})
        s = self.store.get("cap_1")
        self.assertEqual(s["error"], "x")
        self.assertTrue(s["transferred"])


class TestAtomicWrite(unittest.TestCase):
    def test_concurrent_transitions_no_torn_json(self):
        store, tmp = _mkstore()
        store.upsert(_meta("cap_c", state="ready"))

        # 多线程竞争同一 session 的反向迁移：单次迁移可能因状态被抢占而合法 409，
        # 这恰是状态机要的效果。本测试只断言：迁移结果全体自洽、
        # 落盘无撕裂/混写、无异常。把"至少成功若干次"当下界防死循环式全拒。
        outcomes = {"ok": 0, "rejected": 0}
        lock = threading.Lock()
        errors = []

        def worker(tag):
            try:
                for _ in range(50):
                    ok, _ = store.transition("cap_c", "transferring",
                                             {"transferred": False})
                    if ok:
                        with lock:
                            outcomes["ok"] += 1
                        store.transition("cap_c", "ready",
                                         {"transferred": False})
                    else:
                        with lock:
                            outcomes["rejected"] += 1
            except Exception as exc:  # noqa: BLE001
                errors.append("%s: %r" % (tag, exc))

        threads = [threading.Thread(target=worker, args=("t%d" % i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertFalse(errors, errors)                    # 无 crash
        self.assertGreater(outcomes["ok"], 0)               # 至少若干次正常走完

        # 落盘必是合法 JSON，无截断
        with open(os.path.join(tmp, "sessions.json"), "r", encoding="utf-8") as fh:
            db = json.load(fh)
        self.assertEqual(len(db["sessions"]), 1)

        # 且无遗留 tmp 文件
        leftovers = [f for f in os.listdir(tmp) if f.startswith(".sessions.")]
        self.assertEqual(leftovers, [], leftovers)


if __name__ == "__main__":
    unittest.main()
