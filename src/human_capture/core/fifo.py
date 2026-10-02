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

    # ---------- 主循环 ----------

    def _loop(self):
        interval = float(self._cfg.get("fifo_interval_sec", 30))
        while not self._stop_event.wait(interval):
            try:
                while self.run_once():
                    # run_once 返回 True 表示仍有可清，一直清到 False
                    continue
            except Exception as exc:  # noqa: BLE001  防御：清理坏掉不能拖死 server
                self._log("FIFO 清理异常: %r" % exc)

    def run_once(self):
        """返回 True = 刚清了一个（外层应再调）；False = 无事可做。"""
        sessions = [s for s in self._store.list_sessions()
                    if s["state"] not in ACTIVE_STATES and s["state"] != "purged"]

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
        for suffix in (".bag", ".manifest.json", ".reserve"):
            path = os.path.join(self._cfg["staging_dir"], sid + suffix)
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError as exc:
                self._log("删 %s 失败: %r" % (path, exc))
        ok, err = self._store.transition(sid, "purged",
                                         {"purged_reason": "fifo"})
        return ok and not err

    def _disk_low(self):
        try:
            import shutil
            usage = shutil.disk_usage(self._cfg["staging_dir"])
            free_mb = usage.free / (1024 * 1024)
        except OSError:
            return False
        return free_mb <= float(self._cfg.get("disk_floor_mb", 0))
