"""FIFO 清理：板端 captures_remote/ 不撑爆盘。

规则（冻结决策 D6 / 票 HC-02 R6-R7）：
- 每 interval 扫一次 sessions.json。
- 数 > keep：先删 transferred=true 的最老，再删 ready/failed 的最老；
  **永不删** recording/extracting/transferring（进行中，动它会出半成品）。
- 盘余 < floor_mb：无视 keep，从上到下同优先级强清，直到回水位或无可清。
- 删除 = 删物理文件(bag/manifest/reserve) + store 状态置 purged。

设计上：每次 clean() 只删一个会话（最小步），循环由外层线程控制，
便于单测断言和随时停。
"""

import os
import threading
import time

from core.session_store import validate_session_id


def remove_session_artifacts(staging_dir, sid):
    """Remove only named artifacts, never traverse a session junction/symlink.

    An error leaves the registry intact so cleanup can be retried. Unknown
    contents prevent rmdir instead of being recursively removed.
    """
    if not validate_session_id(sid) or sid in ('.', '..'):
        raise ValueError('invalid artifact session id')
    staging = os.path.realpath(staging_dir)
    folder = os.path.join(staging, sid)
    if os.path.normcase(os.path.realpath(folder)) != os.path.normcase(folder):
        raise OSError('session directory redirects outside its named path')
    removed = []
    paths = [os.path.join(staging, sid+s) for s in
             ('.bag', '.bag.active', '.manifest.json', '.reserve')]
    paths += [os.path.join(folder, n) for n in ('points.bin', 'meta.json')]
    for path in paths:
        try:
            os.unlink(path)
            removed.append(os.path.basename(path))
        except FileNotFoundError:
            pass
    try:
        os.rmdir(folder)
        removed.append(sid+'/')
    except FileNotFoundError:
        pass
    return removed

# 状态清理优先级：小数字先清。活跃状态不出现在表里 = 永不删。
PURGE_PRIORITY = {"transferred": 0, "ready": 1, "failed": 2, "purged": 99}
ACTIVE_STATES = {"recording", "extracting", "transferring"}


class FifoCleaner(object):
    """单实例；run_once() 每次最多清一个。线程安全由 store 自己保证。"""

    def __init__(self, store, cfg, logger=None):
        self._store = store
        self._cfg = cfg
        self._log = logger or (lambda msg: None)
        self._stop_event = threading.Event()
        self._thread = None

    # ---------- 生命周期 ----------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="fifo-cleaner")
        self._thread.start()

    def stop(self, join_sec=2.0):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=join_sec)
            if self._thread.is_alive():
                raise RuntimeError('fifo_shutdown_timeout')

    # ---------- 主循环 ----------

    def _loop(self):
        interval = float(self._cfg.get("fifo_interval_sec", 30))
        while not self._stop_event.wait(interval):
            try:
                while self.run_once():
                    # run_once 返回 True 表示仍有可清，一直清到 False
                    if self._stop_event.is_set():
                        break
            except Exception as exc:  # noqa: BLE001  防御：清理坏掉不能拖死 server
                self._log("FIFO 清理异常: %r" % exc)

    def run_once(self):
        """返回 True = 刚清了一个（外层应再调）；False = 无事可做。"""
        sessions = [s for s in self._store.list_sessions()
                    if s["state"] not in ACTIVE_STATES and
                    (s['state'] != 'purged' or s.get('cleanup_pending'))]
        pending = [s for s in sessions if s.get('cleanup_pending')]
        if pending:
            return self._purge_one(self._pick_oldest_by_priority(pending))

        # 1) 盘水位强清
        if self._disk_low():
            self._log("盘余 < %s MB，强清最老可清会话"
                      % self._cfg.get("disk_floor_mb"))
            target = self._pick_oldest_by_priority(sessions)
            if target is None:
                self._log("无可清的 transferred/ready/failed，告警")
                return False
            return self._purge_one(target)

        # 2) 常规 keep 清
        keep = int(self._cfg.get("fifo_keep", 10))
        if len(sessions) <= keep:
            return False
        target = self._pick_oldest_by_priority(sessions)
        return self._purge_one(target) if target else False

    # ---------- 实现 ----------

    @staticmethod
    def _pick_oldest_by_priority(sessions):
        """优先级低→高、同优先级取最老 created_iso。"""
        pool = [s for s in sessions if s["state"] in PURGE_PRIORITY]
        if not pool:
            return None
        pool.sort(key=lambda s: (PURGE_PRIORITY[s["state"]],
                                 s.get("created_iso", "")))
        return pool[0]

    def _purge_one(self, session):
        sid = session["session_id"]
        self._log("FIFO 清 sid=%s state=%s created=%s"
                  % (sid, session["state"], session.get("created_iso")))
        try:
            ok, err, _ = self._store.cleanup(sid,
                lambda: remove_session_artifacts(self._cfg['staging_dir'], sid), 'fifo')
        except (OSError, ValueError) as exc:
            self._log('清理 %s 失败，保留登记以重试: %r' % (sid, exc))
            return False
        return ok and not err

    def _disk_low(self):
        try:
            import shutil
            usage = shutil.disk_usage(self._cfg["staging_dir"])
            free_mb = usage.free / (1024 * 1024)
        except OSError:
            return False
        return free_mb <= float(self._cfg.get("disk_floor_mb", 0))
