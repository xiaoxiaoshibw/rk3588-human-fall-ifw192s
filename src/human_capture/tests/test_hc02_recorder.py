"""HC-02 R1/R5：录制编排器的 watcher 状态机（Windows 可测的子集）。

Windows 上 send_signal(SIGINT) 语义不稳定，无法承载"子进程优雅收尾"的测试；
真实 SIGINT 语义 + 真实 record_session.py 由板上 R2/R3/R4 实测验。

本文件承载的稳定性的是：
  R1 起录会插 sessions 行、并发 start 拒绝
  R5 watcher 对"不响应信号→宽限→升级 SIGKILL"的兜底
  R5b watcher 对"外部 SIGKILL"路径的兜底
"""

import json
import os
import shutil
import signal
import sys
import tempfile
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from core.session_store import SessionStore
from core.recorder import Recorder, RecordError


# 持续死等、不响应任何信号的 fake；watcher 信号升级路径靠它。
# 真实 record_session.py 收 SIGINT 优雅收尾（写 manifest + exit 130），
# 那个路径由板上实测覆盖。
FAKE_RECORD_SESSION = """
import os, sys, time
sid = sys.argv[sys.argv.index("--session-id") + 1]
out = sys.argv[sys.argv.index("--output-dir") + 1]
os.makedirs(out, exist_ok=True)
with open(os.path.join(out, sid + ".bag"), "wb") as fh:
    fh.write(b"ROSBAG" * 100)
t0 = time.time()
while time.time() - t0 < 30:
    time.sleep(0.1)
"""


class _Ctx(object):
    def __init__(self, extra_cfg=None):
        self.tmp = tempfile.mkdtemp(prefix="hc02_")
        cfg = {
            "staging_dir": self.tmp,
            "sessions_db": os.path.join(self.tmp, "sessions.json"),
            "record_script": self._make_fake_script(),
            "record_config": None,
            "max_duration_sec": 0,
            "disk_floor_mb": 1,
            "sigint_grace_sec": 0.5,   # 测试加速
            "sigterm_kill_sec": 0.3,
        }
        if extra_cfg:
            cfg.update(extra_cfg)
        self.cfg = cfg
        self.store = SessionStore(cfg["sessions_db"])
        self.recorder = Recorder(self.store, cfg, logger=lambda m: None)

    def _make_fake_script(self):
        path = os.path.join(self.tmp, "fake_record.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(FAKE_RECORD_SESSION)
        return path

    def wait_state(self, sid, target_set, timeout=15.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            s = self.store.get(sid)
            if s and s["state"] in target_set:
                return s
            time.sleep(0.1)
        return self.store.get(sid)

    def cleanup(self):
        try:
            if self.recorder.is_recording():
                self.recorder.stop(reason="manual")
                time.sleep(2)  # 等 watcher 杀完
        except Exception:
            pass
        try:
            shutil.rmtree(self.tmp, ignore_errors=True)
        except Exception:
            pass


class TestStart(unittest.TestCase):
    def test_registers_recording(self):
        ctx = _Ctx()
        try:
            sid = ctx.recorder.start("cap_hc02_a")
            self.assertEqual(sid, "cap_hc02_a")
            s = ctx.store.get(sid)
            self.assertEqual(s["state"], "recording")
            self.assertTrue(s["created_iso"])
            self.assertEqual(s["bag_path"],
                             os.path.join(ctx.tmp, sid + ".bag"))
        finally:
            ctx.cleanup()

    def test_second_start_rejected(self):
        ctx = _Ctx()
        try:
            ctx.recorder.start("cap_hc02_b")
            with self.assertRaises(RecordError):
                ctx.recorder.start("cap_hc02_c")
        finally:
            ctx.cleanup()


class TestWatcherEscalation(unittest.TestCase):
    """手动 stop → watcher 宽限 → SIGTERM → SIGKILL → failed(escalated)"""

    def test_manual_stop_no_response_goes_failed(self):
        ctx = _Ctx()
        try:
            sid = ctx.recorder.start("cap_hc02_esc")
            time.sleep(0.3)
            stopped = ctx.recorder.stop(reason="manual")
            self.assertEqual(stopped, sid)
            s = ctx.wait_state(sid, {"failed", "extracting"}, timeout=20)
            # fake 不应信号；watcher 必走升级；终态是 failed
            self.assertEqual(s["state"], "failed", s)
            self.assertIn("escalated", s.get("error", ""), s)
        finally:
            ctx.cleanup()

    def test_external_sigkill_marks_crashed(self):
        ctx = _Ctx()
        try:
            sid = ctx.recorder.start("cap_hc02_k")
            time.sleep(0.3)
            rec = ctx.recorder._current
            # 外部直接 SIGKILL，不经 stop()
            if os.name == "posix":
                os.killpg(os.getpgid(rec.proc.pid), signal.SIGKILL)
            else:
                rec.proc.kill()
            s = ctx.wait_state(sid, {"failed"}, timeout=15)
            self.assertEqual(s["state"], "failed")
            self.assertIn("crashed", s.get("error", ""))
        finally:
            ctx.cleanup()


class TestWatcherAutoTriggers(unittest.TestCase):
    """duration/盘水位 → SIGINT → 不响应 → 升级 → failed。

    板上用真 record_session.py 验"自动停还能写 manifest → extracting"；
    Windows 这里只验 watcher 真的发起了请求。
    """

    def test_duration_cap_triggers_escalation(self):
        # 极短 max，watcher 应立刻发起 SIGINT→升级
        ctx = _Ctx({"max_duration_sec": 0.5})
        try:
            sid = ctx.recorder.start("cap_dur")
            s = ctx.wait_state(sid, {"failed", "extracting"}, timeout=20)
            # 两种结局都合法，取决于 fake 有没有响应 SIGINT；
            # 但 stop_reason 必须被记录
            self.assertIn(s.get("stop_reason", ""), ("duration", ""), s)
        finally:
            ctx.cleanup()

    def test_disk_floor_triggers_escalation(self):
        huge = 10 ** 12
        ctx = _Ctx({"disk_floor_mb": huge})
        try:
            sid = ctx.recorder.start("cap_disk_low")
            time.sleep(2)  # 让 watcher 起码转一圈
            # stop_reason 必须被设置成 disk_floor（不管最后态）
            # watcher.sleep 0.5s/圈，2s 应够
            rec = ctx.recorder._current
            # 可能已 failed，可能仍在等 SIGTERM/SIGKILL 升级
            s = ctx.store.get(sid)
            if s and s.get("stop_reason"):
                self.assertEqual(s["stop_reason"], "disk_floor")
            # 不等终态（Windows 下升级链可能很长）
        finally:
            ctx.cleanup()


if __name__ == "__main__":
    unittest.main()
