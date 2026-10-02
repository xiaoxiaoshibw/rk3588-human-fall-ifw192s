"""录制编排器：起停 record_session.py 子进程 + 看护自动停 + manifest 回写。

设计要点：
- 单实例。进程内一把锁，全局任意时刻最多一个在录会话。
- 起录制用 `--until-interrupt`；停止 = 对子进程**进程组**发 SIGINT，
  record_session 收到后自己做最后的 bag 校验 + 写 manifest + exit 130。
  若 grace 期内没退出，升级 SIGTERM→SIGKILL，状态按 failed 走。
- 看护守护线程 1s 步：超时 / 盘水位 / 子进程猝死，三类都会走到"停录"路径。
- 子进程退出后在看护里解析 manifest，写回 sessions.json 并置 extracting。
- 全程不 import rospy（core 层保持可单测）；ROS 相关在 scripts/capture_server 注入。
"""

import json
import os
import shlex
import shutil
import signal
import subprocess
import threading
import time

MAX_ELAPSED_GUARD = 60  # 时长上限的兜底边界（max_duration_sec<=0 时按此触发）


class RecordError(Exception):
    pass


class _Recording(object):
    """单次录制句柄（编排器内部）。"""

    def __init__(self, session_id, output_dir):
        self.session_id = session_id
        self.output_dir = output_dir
        self.bag_path = os.path.join(output_dir, session_id + ".bag")
        self.manifest_path = os.path.join(output_dir, session_id + ".manifest.json")
        self.proc = None
        self.started_monotonic = None
        self.stop_reason = None            # manual | duration | disk_floor | crashed
        self.stop_requested_at = None
        self.thread = None


class Recorder(object):
    """一个实例对应一个 capture_server；把状态全写在 sessions.json，进程重启不失忆。"""

    def __init__(self, store, cfg, logger=None):
        self._store = store
        self._cfg = cfg
        self._log = logger or (lambda msg: None)
        self._lock = threading.RLock()
        self._current = None              # _Recording 或 None
        self._watcher = None

    # ---------- 公开 ----------

    def is_recording(self):
        with self._lock:
            return self._current is not None

    def current_session_id(self):
        with self._lock:
            return self._current.session_id if self._current else None

    def start(self, session_id):
        """起录。返回 session_id；已在录抛 RecordError。"""
        with self._lock:
            if self._current is not None:
                raise RecordError("already_recording")
            rec = _Recording(session_id, self._cfg["staging_dir"])
            os.makedirs(rec.output_dir, exist_ok=True)
            now_iso = _iso_now()
            self._store.upsert({
                "session_id": session_id,
                "state": "recording",
                "created_iso": now_iso,
                "bag_path": rec.bag_path,
            })

            # 若 rosbag 不在 PATH（capture_server 自己不是从 source 过的 shell 起），
            # 用 bash -c 包一层 source 再 exec，子进程就能找得到 rosbag。
            setup = "/opt/ros/noetic/setup.bash"
            if os.path.exists(setup) and shutil.which("rosbag") is None:
                inner = shlex.join([self._python(), self._cfg["record_script"],
                                    "--session-id", session_id,
                                    "--until-interrupt",
                                    "--output-dir", rec.output_dir])
                if self._cfg.get("record_config"):
                    inner += " " + shlex.join(["--config", self._cfg["record_config"]])
                cmd = ["bash", "-c", "source %s && source /root/catkin_ws/devel/setup.bash 2>/dev/null; exec %s" % (setup, inner)]
            else:
                cmd = [self._python(), self._cfg["record_script"],
                       "--session-id", session_id,
                       "--until-interrupt",
                       "--output-dir", rec.output_dir]
                if self._cfg.get("record_config"):
                    cmd += ["--config", self._cfg["record_config"]]

            self._log("起录: %s" % " ".join(cmd))
            rec.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,   # 进程组独立，SIGINT 只打它不打 server
            )
            rec.started_monotonic = time.monotonic()
            rec.thread = threading.Thread(target=self._watch, args=(rec,), daemon=True)
            rec.thread.start()
            self._current = rec
            return session_id

    def stop(self, reason="manual", timeout=None):
        """停录（含自动停）。返回停止的 session_id；没在录返回 None。
        该方法只发 SIGINT，具体收尾等看护线程做了它再置 extracting。"""
        with self._lock:
            rec = self._current
            if rec is None:
                return None
            if rec.stop_reason is None:
                self._send_sigint_locked(rec)
            return rec.session_id

    # ---------- 看护 ----------

    def _watch(self, rec):
        grace = float(self._cfg.get("sigint_grace_sec", 15))
        timeout = float(self._cfg.get("sigterm_kill_sec", 5))
        escalated = False
        while True:
            time.sleep(0.5)
            with self._lock:
                if rec is not self._current:
                    return  # 已被外力接管
                elapsed = time.monotonic() - rec.started_monotonic if rec.started_monotonic else 0.0
                proc_rc = rec.proc.poll()

                # 1) 未请求停止时看硬上限/盘水位
                if rec.stop_reason is None and proc_rc is None:
                    if self._over_duration(elapsed):
                        self._send_sigint_locked(rec, reason="duration")
                    elif self._disk_low():
                        self._send_sigint_locked(rec, reason="disk_floor")

                # 2) 已请求停止：宽限后升级 SIGTERM→SIGKILL
                if rec.stop_reason is not None and proc_rc is None:
                    waited = time.monotonic() - (rec.stop_requested_at or time.monotonic())
                    if not escalated and waited > grace:
                        try:
                            _kill_pg(rec.proc, signal.SIGTERM)
                            self._log("SIGTERM (grace=%.1fs 超时)" % grace)
                        except (ProcessLookupError, PermissionError):
                            pass
                        escalated = True
                    elif escalated and waited > grace + timeout:
                        try:
                            _kill_pg(rec.proc, signal.SIGKILL)
                            self._log("SIGKILL (grace+term 超时)")
                        except (ProcessLookupError, PermissionError):
                            pass

                # 3) 子进程已退：收尾
                proc_rc = rec.proc.poll()
                if proc_rc is not None:
                    self._finalize_locked(rec, proc_rc, escalated)
                    self._current = None
                    return

    def _send_sigint_locked(self, rec, reason="manual"):
        rec.stop_reason = rec.stop_reason or reason
        rec.stop_requested_at = time.monotonic()
        try:
            _kill_pg(rec.proc, signal.SIGINT)
            self._log("SIGINT -> %s (reason=%s)" % (rec.session_id, rec.stop_reason))
        except (ProcessLookupError, PermissionError) as exc:
            self._log("SIGINT 失败 %s: %r" % (rec.session_id, exc))

    def _over_duration(self, elapsed):
        maxd = float(self._cfg.get("max_duration_sec", 0))
        if maxd <= 0:
            return elapsed >= MAX_ELAPSED_GUARD  # 兜底防御，不该到达
        return elapsed >= maxd

    def _disk_low(self):
        try:
            import shutil
            usage = shutil.disk_usage(self._cfg["staging_dir"])
            free_mb = usage.free / (1024 * 1024)
        except OSError:
            return False
        return free_mb <= float(self._cfg.get("disk_floor_mb", 0))

    # ---------- 收尾 ----------

    def _finalize_locked(self, rec, returncode, escalated):
        sid = rec.session_id
        self._log("录制收尾 sid=%s rc=%s reason=%s escalated=%s"
                  % (sid, returncode, rec.stop_reason, escalated))

        manifest = None
        if os.path.exists(rec.manifest_path):
            try:
                with open(rec.manifest_path, "r", encoding="utf-8") as fh:
                    manifest = json.load(fh)
            except (ValueError, OSError) as exc:
                self._log("manifest 解析失败: %r" % exc)

        patch = {"bag_path": rec.bag_path}
        bag_exists = os.path.exists(rec.bag_path)
        if bag_exists:
            patch["size_bytes"] = os.path.getsize(rec.bag_path)

        # 失败路径：子进程异常、被升级杀、或 manifest 没出来
        if escalated or rec.stop_reason is None or not manifest:
            reason = ("crashed_rc%d" % returncode) if rec.stop_reason is None \
                     else "escalated_%s" % ("sigterm" if escalated else "?")
            if rec.stop_reason and not manifest:
                reason += "_no_manifest"
            self._store.transition(sid, "failed", {**patch, "error": reason})
            return

        # 成功：从 manifest 抽出 HC-03 要的东西
        summary = (manifest.get("bag") or {}).get("summary") or {}
        patch.update({
            "source_bag_sha256": (manifest.get("bag") or {}).get("sha256"),
            "duration_sec": summary.get("duration_s"),
            "frame_count": _primary_topic_count(summary),
            "manifest_path": rec.manifest_path,
            "stop_reason": rec.stop_reason,
        })
        ok, err = self._store.transition(sid, "extracting", patch)
        if not ok:
            self._log("状态迁移失败 sid=%s err=%s" % (sid, err))

    # ---------- 内部 ----------

    @staticmethod
    def _python():
        # record_session.py 是 py3；跟随当前解释器
        import sys
        return sys.executable


def _iso_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _kill_pg(proc, sig):
    """给子进程组发信号。
    POSIX：killpg 打整个组（子进程 fork 的孙进程也收得到）。
    Windows：killpg / signal.SIGKILL 都不存在；
            proc.kill() = TerminateProcess（等价 POSIX SIGKILL 的粗暴路径），
            其他信号用 Popen.send_signal。"""
    if os.name == "posix":
        os.killpg(os.getpgid(proc.pid), sig)
        return
    sigkill = getattr(signal, "SIGKILL", None)
    if sigkill is not None and sig == sigkill:
        proc.kill()
        return
    # Windows send_signal 只接受 SIGTERM/CTRL_C_EVENT/CTRL_BREAK_EVENT；
    # SIGINT 不直接支持，用 SIGTERM 代替（对 python 子进程同为可捕获终止）。
    if sig == signal.SIGINT:
        sig = signal.SIGTERM
    proc.send_signal(sig)


def _primary_topic_count(summary):
    """manifest.summary.topics 里消息数最多的话题当『主话题』(=点云)"""
    topics = (summary or {}).get("topics") or {}
    if not topics:
        return None
    return max(t.get("messages", 0) for t in topics.values())
