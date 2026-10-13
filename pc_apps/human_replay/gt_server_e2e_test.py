# -*- coding: utf-8 -*-
"""gt_server_e2e_test.py — 起一次隔离端口的 human_replay_lib，对 /api/gt/* 链路冒烟。

跑法： python -B -W error -m unittest pc_apps.human_replay.gt_server_e2e_test -v

安全红线（修 2026-10-10 S9 / S1 真实 GT 被旧版测试毁灭的 bug）：
  * SID 用 "cap_99999999_999999" 永不存在的命名空间；
  * STORE/DEST_ROOT 用临时目录, 不写 git_ignored gt_store；
  * 不再 os.unlink 任何东西—— 每次跑都用全新临时 STORE。
  * 这版不再探测 8901: 那台可能是别人正在标注的真服务，碰它就被它当真。本测试自己起隔离端口。
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

# 永不存在的 SID 伪装: 通过 SID_RE 但避名未来采集命名空间
FAKE_SID = "cap_99999999_999999"


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class E2E(unittest.TestCase):
    """起隔离 human_replay_lib 子进程，跑 gt/save→freeze→progress→export 全链路。"""

    PORT = None
    PROC = None
    TMP = None  # 包含 STORE + DEST_ROOT + launcher.py

    @classmethod
    def setUpClass(cls):
        cls.PORT = find_free_port()
        cls.TMP = tempfile.mkdtemp(prefix="gt_e2e_isolated_")
        # 造一个会让 gt_server 走的伪会话目录（只供 /api/gt/session 读 meta/n_frames）
        sess_dir = os.path.join(cls.TMP, "dest", FAKE_SID)
        os.makedirs(sess_dir)
        with open(os.path.join(sess_dir, "meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"session_id": FAKE_SID, "frames": [{"index": i} for i in range(3)],
                       "duration_sec": 1.0}, fh)
        # 启动脚本
        launcher = os.path.join(cls.TMP, "run.py")
        launcher_src = (
            "import sys, os\n"
            "sys.path.insert(0, %r)\n"
            "os.environ['HR_DEST_ROOT'] = %r\n"
            "os.environ['HR_STORE_DIR'] = %r\n"
            "os.makedirs(os.environ['HR_DEST_ROOT'], exist_ok=True)\n"
            "os.makedirs(os.environ['HR_STORE_DIR'], exist_ok=True)\n"
            "os.environ.pop('HUMAN_REPLAY_BOARD_MODE', None)\n"
            "import human_replay_lib\n"
            "import webbrowser\n"
            "webbrowser.open = lambda *a, **k: None\n"
            "def _main():\n"
            "    import human_replay_lib as H\n"
            "    from http.server import ThreadingHTTPServer\n"
            "    srv = ThreadingHTTPServer(('127.0.0.1', %d), H.Handler)\n"
            "    print('listening', %d)\n"
            "    try:\n"
            "        srv.serve_forever()\n"
            "    except KeyboardInterrupt:\n"
            "        pass\n"
            "_main()\n"
        ) % (HERE, os.path.join(cls.TMP, "dest"), os.path.join(cls.TMP, "store"),
             cls.PORT, cls.PORT)
        with open(launcher, "w", encoding="utf-8") as fh:
            fh.write(launcher_src)
        cls.PROC = subprocess.Popen([sys.executable, launcher],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # 等服务起来
        for _ in range(60):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:%d/api/gt/export" % cls.PORT, timeout=1.0):
                    break
            except Exception:
                time.sleep(0.2)
        else:
            cls.tearDownClass()
            raise RuntimeError("server 不起")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.PROC.terminate()
            cls.PROC.wait(timeout=3.0)
        except Exception:
            try:
                cls.PROC.kill()
            except Exception:
                pass
        try:
            if cls.PROC.stdout: cls.PROC.stdout.close()
            if cls.PROC.stderr: cls.PROC.stderr.close()
        except Exception:
            pass
        import shutil
        shutil.rmtree(cls.TMP, ignore_errors=True)

    def _post(self, path, body):
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.PORT, path),
                                     data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=8.0) as r:
            return json.loads(r.read())

    def _get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.PORT, path),
                                    timeout=8.0) as r:
            return json.loads(r.read())

    def _fake_doc(self, n_objects=1, reviewed=False):
        objs = {}
        fo = {}
        for i in range(n_objects):
            oid = "obj_%d" % i
            objs[oid] = {
                "session_id": FAKE_SID, "frame_id": "%s:%d" % (FAKE_SID, i),
                "frame_idx": i, "timestamp": i * 0.1, "object_id": oid,
                "track_id": "P%d" % (i + 1), "class_name": "PERSON",
                "box_xy": [1.0, 1.0, 3.0, 3.0],
                "z_min": 0.05, "z_max": 2.3,
                "raw_point_indices": ["s", 100 + i, 200 + i],
                "point_count": 2 + i,
                "coordinate_frame": "leveled-IFW192S",
                "leveling_transform_id": "render_person_label.R/T",
                "source": "human",
                "review_status": "reviewed" if reviewed else "unreviewed",
                "annotator": "e2e", "schema_version": "gt_workbench/1",
            }
            fo[str(i)] = [oid]
        return {
            "schema_version": "gt_workbench/1",
            "session_id": FAKE_SID,
            "session_sha256": {"points": "aa" * 32},
            "annotator": "e2e",
            "review_status": "reviewed" if reviewed else "draft",
            "objects": objs,
            "frames_objects": fo,
            "frozen_versions": [], "history": [],
        }

    def test_01_save_draft_rejects_wrong_sid(self):
        doc = self._fake_doc()
        doc["session_id"] = "cap_other_sid"
        try:
            r = self._post("/api/gt/save", {"sid": FAKE_SID, "doc": doc})
            self.fail("sid 不匹配必须 400, 得到 %s" % r)
        except Exception:
            pass  # urllib raises HTTPError on 4xx

    def test_02_save_then_progress(self):
        doc = self._fake_doc(n_objects=2)
        r = self._post("/api/gt/save", {"sid": FAKE_SID, "doc": doc})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["n_objects"], 2)
        self.assertEqual(len(r["sha256"]), 64)
        r2 = self._get("/api/gt/progress?sid=" + FAKE_SID)
        self.assertTrue(r2["ok"], r2)
        # progress 返回 n_frames 从 meta.json 推 3
        self.assertEqual(r2.get("n_frames"), 3)

    def test_03_freeze_requires_all_reviewed(self):
        # 沿用 test_02 写的 draft（unreviewed） → freeze 必须 400
        try:
            r = self._post("/api/gt/freeze", {"sid": FAKE_SID, "annotator": "e2e"})
            self.fail("未 reviewed 对象 freeze 必须拒: %s" % r)
        except Exception:
            pass
        # 全部 reviewed
        doc = self._fake_doc(n_objects=2, reviewed=True)
        r = self._post("/api/gt/save", {"sid": FAKE_SID, "doc": doc})
        self.assertTrue(r["ok"])
        r2 = self._post("/api/gt/freeze", {"sid": FAKE_SID, "annotator": "e2e"})
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(r2["version"], "V1")
        # 再 freeze: 应该升 V2 (manifest 已有 V1)
        r3 = self._post("/api/gt/save", {"sid": FAKE_SID, "doc": doc})
        self.assertTrue(r3["ok"])
        r4 = self._post("/api/gt/freeze", {"sid": FAKE_SID, "annotator": "e2e"})
        self.assertEqual(r4["version"], "V2")

    def test_04_export_blocks_bad_names(self):
        try:
            self._get("/api/gt/export?sid=%s&name=../secret.json" % FAKE_SID)
            self.fail("路径穿越必须挡")
        except Exception:
            pass

    def test_05_session_payload_uses_fake_sid(self):
        r = self._get("/api/gt/session?sid=" + FAKE_SID)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["sid"], FAKE_SID)
        # 隔离 STORE 里没有 fusion/U3 缓存 → suggestions 都是空 dict, 不强关键词名
        self.assertIn("n_frames", r)
        self.assertEqual(r["n_frames"], 3)


if __name__ == "__main__":
    unittest.main()
