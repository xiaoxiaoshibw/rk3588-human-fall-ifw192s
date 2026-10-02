"""会话元数据存取：sessions.json 的唯一读写入口。

职责：
- 维护会话登记表（SessionMeta dict 列表），按时间倒序持久化到 sessions.json。
- 状态机迁移校验（HC-01 契约：非法迁移返回 False，由 HTTP 层映射为 409）。
- 持久化原子写（tmp 文件 + fsync + os.replace），进程被 kill -9 不留半截 JSON。
- 同进程线程安全；跨进程用 fcntl 文件锁兜底（cfs 与潜在的手工修复脚本共存）。

不 import rospy，PC 端与单测可直接复用本模块。
"""

import copy
import errno
import json
import os
import tempfile
import threading

try:
    import fcntl  # POSIX；板上容器可用，Windows 单测走另一分支
except ImportError:  # pragma: no cover - windows
    fcntl = None

SCHEMA_VERSION = 1
SERVICE_VERSION = "0.1.0"

# README §8 状态机：recording → extracting → ready → transferring → transferred → purged
# 异常支：任何状态可进 failed；failed 可被重新置 extracting（人工重试抽取）。
LEGAL_TRANSITIONS = {
    "recording": {"extracting", "failed", "purged"},
    "extracting": {"ready", "failed", "purged"},
    "ready": {"transferring", "purged", "extracting"},
    "transferring": {"transferred", "failed", "ready"},  # 下载中断可退回 ready
    "transferred": {"purged"},
    "failed": {"extracting", "purged"},
    "purged": set(),  # 终态
}

SESSION_ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")

REQUIRED_FIELDS = ("session_id", "state", "created_iso")


def validate_session_id(session_id):
    """会话 id 只允许安全字符，杜绝 PATCH/文件路径拼接被注入。"""
    if not isinstance(session_id, str) or not session_id:
        return False
    return len(session_id) <= 128 and set(session_id) <= SESSION_ID_CHARS


def _now_dict():
    return {"format": "human_capture_sessions_db", "schema_version": SCHEMA_VERSION,
            "sessions": []}


class StoreError(Exception):
    """sessions.json 损坏等不可恢复错误；服务层据此拒绝启动。"""


class SessionStore(object):
    """sessions.json 的读写与状态机。一个进程一个实例；HTTP handler 全部经这里。"""

    def __init__(self, db_path):
        self._db_path = db_path
        self._lock = threading.RLock()
        self._db = self._load_or_init()

    # ---------- 持久化 ----------

    def _load_or_init(self):
        if not os.path.exists(self._db_path):
            return _now_dict()
        try:
            with open(self._db_path, "r", encoding="utf-8") as fh:
                db = json.load(fh)
        except ValueError as exc:
            raise StoreError("sessions.json 损坏(%s)：%s——拒绝启动，请人工检查 %s"
                             % (type(exc).__name__, exc, self._db_path))
        if not isinstance(db, dict) or not isinstance(db.get("sessions"), list):
            raise StoreError("sessions.json 结构非法：%s" % self._db_path)
        return db

    def _persist_locked(self):
        """调用方必须已持锁。写到同目录 tmp 再 replace，保证原子。"""
        db_dir = os.path.dirname(self._db_path) or "."
        fd, tmp = tempfile.mkstemp(prefix=".sessions.", suffix=".tmp", dir=db_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._db, fh, ensure_ascii=False, indent=1, sort_keys=True)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._db_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _with_file_lock(self, fn):
        """POSIX 下用 fcntl 给 db 文件加排他锁包住 读-改-写；无 fcntl 时退化为进程内锁。"""
        if fcntl is None:  # pragma: no cover - windows
            return fn()
        lock_path = self._db_path + ".lock"
        os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
        with open(lock_path, "a+") as lock_fh:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
            try:
                return fn()
            finally:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)

    # ---------- 查询 ----------

    def list_sessions(self):
        with self._lock:
            return copy.deepcopy(self._db["sessions"])

    def get(self, session_id):
        if not validate_session_id(session_id):
            return None
        with self._lock:
            for s in self._db["sessions"]:
                if s["session_id"] == session_id:
                    return copy.deepcopy(s)
        return None

    # ---------- 变更 ----------

    def upsert(self, meta):
        """登记或整体替换一个会话（录入器用）。meta 至少带 REQUIRED_FIELDS。"""
        missing = [k for k in REQUIRED_FIELDS if k not in meta]
        if missing:
            raise ValueError("meta 缺字段: %s" % ",".join(missing))
        if not validate_session_id(meta["session_id"]):
            raise ValueError("session_id 非法")
        if meta["state"] not in LEGAL_TRANSITIONS:
            raise ValueError("state 非法: %r" % meta["state"])

        def _op():
            with self._lock:
                self._db = self._load_or_init()  # 跨进程场景下先吸收他人写入
                for i, s in enumerate(self._db["sessions"]):
                    if s["session_id"] == meta["session_id"]:
                        self._db["sessions"][i] = copy.deepcopy(meta)
                        break
                else:
                    self._db["sessions"].append(copy.deepcopy(meta))
                # 按 created_iso 倒序；新会话永远插最前，老会话重登记不失位次大跌
                self._db["sessions"].sort(key=lambda s: s.get("created_iso", ""), reverse=True)
                self._persist_locked()

        self._with_file_lock(_op)

    def transition(self, session_id, new_state, extra=None):
        """状态机迁移。返回 (ok, reason)。extra 合并进会话（如 error、download_requested）。"""
        if not validate_session_id(session_id):
            return False, "session_id 非法"
        if new_state not in LEGAL_TRANSITIONS:
            return False, "state 非法: %r" % new_state

        result = {}

        def _op():
            with self._lock:
                self._db = self._load_or_init()
                for s in self._db["sessions"]:
                    if s["session_id"] == session_id:
                        current = s["state"]
                        if new_state not in LEGAL_TRANSITIONS.get(current, set()):
                            result["err"] = "非法迁移 %s -> %s" % (current, new_state)
                            return
                        s["state"] = new_state
                        if extra:
                            s.update(extra)
                        self._persist_locked()
                        result["ok"] = True
                        return
                result["err"] = "会话不存在"

        self._with_file_lock(_op)
        if result.get("ok"):
            return True, ""
        return False, result.get("err", "unknown")

    def delete(self, session_id):
        """删除登记（不删文件；文件本体仅 FIFO 清理删除）。"""
        if not validate_session_id(session_id):
            return False

        removed = []

        def _op():
            with self._lock:
                self._db = self._load_or_init()
                for i, s in enumerate(self._db["sessions"]):
                    if s["session_id"] == session_id:
                        removed.append(self._db["sessions"].pop(i))
                        break
                if removed:
                    self._persist_locked()

        self._with_file_lock(_op)
        return bool(removed)

    # ---------- 供 FIFO/状态接口用的聚合 ----------

    def summary_counts(self):
        with self._lock:
            recording = any(s["state"] == "recording" for s in self._db["sessions"])
            return {"sessions_total": len(self._db["sessions"]), "recording": recording}
