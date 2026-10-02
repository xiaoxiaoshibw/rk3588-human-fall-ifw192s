"""HC-02 R6/R7：FIFO 清理。"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from core.session_store import SessionStore
from core.fifo import FifoCleaner, PURGE_PRIORITY


def _mk(n=0, states=None, transferred_at=(1,)):
    tmp = tempfile.mkdtemp(prefix="hc02fifo_")
    cfg = {"staging_dir": tmp,
           "sessions_db": os.path.join(tmp, "sessions.json"),
           "fifo_keep": 2, "disk_floor_mb": 1, "fifo_interval_sec": 60}
    store = SessionStore(cfg["sessions_db"])
    cleaner = FifoCleaner(store, cfg, logger=lambda m: None)
    # 造 n 个会话，按序号增 created_iso；transferred_at 指定哪些是 transferred
    for i in range(n):
        sid = "cap_t%02d" % i
        state = "ready"
        if states and i in states:
            state = states[i]
        elif i in transferred_at:
            state = "transferred"
        created = "2026-10-02T%02d:00:00+08:00" % (i % 24)
        store.upsert({"session_id": sid, "state": state, "created_iso": created,
                      "transferred": (state == "transferred")})
        # 造物理文件，核 FIFO 会真的删
        for suf in (".bag", ".manifest.json"):
            open(os.path.join(tmp, sid + suf), "wb").close()
    return tmp, cfg, store, cleaner


class TestPickOldestByPriority(unittest.TestCase):
    def test_priority_order(self):
        sessions = [
            {"session_id": "a", "state": "ready",       "created_iso": "2026-10-02T03:00:00"},
            {"session_id": "b", "state": "failed",      "created_iso": "2026-10-02T01:00:00"},
            {"session_id": "c", "state": "transferred", "created_iso": "2026-10-02T04:00:00"},
            {"session_id": "d", "state": "transferred", "created_iso": "2026-10-02T02:00:00"},
            {"session_id": "e", "state": "recording",   "created_iso": "2026-10-02T00:00:00"},
        ]
        got = FifoCleaner._pick_oldest_by_priority(sessions)
        # transferred 优先；transferred 里 created 最老的 d
        self.assertEqual(got["session_id"], "d")


class TestFifoKeep(unittest.TestCase):
    def test_over_keep_deletes_oldest_transferred(self):
        tmp, cfg, store, cleaner = _mk(n=4, transferred_at=(0, 1, 2, 3))
        # 4 个 transferred，keep=2：应清 2 个最老 (t00, t01)
        self.assertTrue(cleaner.run_once())
        self.assertTrue(cleaner.run_once())
        self.assertFalse(cleaner.run_once())
        remaining = {s["session_id"]: s["state"] for s in store.list_sessions()}
        self.assertEqual(remaining["cap_t00"], "purged")
        self.assertEqual(remaining["cap_t01"], "purged")
        self.assertEqual(remaining["cap_t02"], "transferred")
        self.assertEqual(remaining["cap_t03"], "transferred")
        # 物理文件也删了
        self.assertFalse(os.path.exists(os.path.join(tmp, "cap_t00.bag")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "cap_t02.bag")))
        shutil.rmtree(tmp, ignore_errors=True)

    def test_active_states_never_purged(self):
        # 3 sessions keep=2: pool only has 1 ready (active excluded), <= keep, no trigger.
        # Force keep=0 to trigger; ready is purged, active must be untouched.
        tmp, cfg, store, cleaner = _mk(n=3, states={0: "ready", 1: "recording",
                                                    2: "transferring"})
        self.assertFalse(cleaner.run_once())
        cfg["fifo_keep"] = 0
        self.assertTrue(cleaner.run_once())      # purge ready
        self.assertFalse(cleaner.run_once())     # no more
        remaining = {s["session_id"]: s["state"] for s in store.list_sessions()}
        self.assertEqual(remaining["cap_t00"], "purged")
        self.assertEqual(remaining["cap_t01"], "recording")
        self.assertEqual(remaining["cap_t02"], "transferring")
        shutil.rmtree(tmp, ignore_errors=True)

    def test_exactly_at_keep_no_op(self):
        tmp, cfg, store, cleaner = _mk(n=2, transferred_at=(0, 1))
        self.assertFalse(cleaner.run_once())
        states = {s["session_id"]: s["state"] for s in store.list_sessions()}
        self.assertNotIn("purged", states.values())
        shutil.rmtree(tmp, ignore_errors=True)


class TestFifoDiskFloor(unittest.TestCase):
    def test_under_floor_overrides_keep(self):
        # keep=2，只有 2 个 transferred 也到不了"超 keep"，但盘水位低要强清。
        tmp, cfg, store, cleaner = _mk(n=2, transferred_at=(0, 1))
        with patch.object(cleaner, "_disk_low", return_value=True):
            self.assertTrue(cleaner.run_once())       # 清最老 t00
            self.assertTrue(cleaner.run_once())       # 清 t01
            self.assertFalse(cleaner.run_once())      # 无可清 → False + 告警路径
        states = {s["session_id"]: s["state"] for s in store.list_sessions()}
        self.assertEqual(states.get("cap_t00"), "purged")
        self.assertEqual(states.get("cap_t01"), "purged")
        shutil.rmtree(tmp, ignore_errors=True)

    def test_under_floor_but_only_active_sessions_do_not_purge(self):
        tmp, cfg, store, cleaner = _mk(n=3, states={0: "recording",
                                                    1: "extracting",
                                                    2: "transferring"})
        with patch.object(cleaner, "_disk_low", return_value=True):
            self.assertFalse(cleaner.run_once())   # 没可清的 = False
        states = {s["session_id"]: s["state"] for s in store.list_sessions()}
        # 全部保持原状
        self.assertEqual(states["cap_t00"], "recording")
        self.assertEqual(states["cap_t01"], "extracting")
        self.assertEqual(states["cap_t02"], "transferring")
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
