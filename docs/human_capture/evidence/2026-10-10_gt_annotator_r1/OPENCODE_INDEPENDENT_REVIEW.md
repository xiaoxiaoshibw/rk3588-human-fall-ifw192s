[0m
> plan · deepseek-v4.1-flash
[0m
[0m→ [0mSkill "ponytail"
[0m
[0m$ [0mls -la pc_apps/human_replay/ 2>/dev/null; echo "---GT files---"; ls -la pc_apps/human_replay/gt* 2>/dev/null
total 1122
drwxr-xr-x 1 30680 197609     0 Oct 10 19:38 .
drwxr-xr-x 1 30680 197609     0 Oct 10 16:18 ..
drwxr-xr-x 1 30680 197609     0 Oct  9 14:24 .pytest_cache
-rw-r--r-- 1 30680 197609  5781 Oct 10 19:37 GT_ANNOTATOR_USER_GUIDE.md
-rw-r--r-- 1 30680 197609  5665 Oct  5 20:13 LEVELING_README.md
drwxr-xr-x 1 30680 197609     0 Oct 10 19:37 __pycache__
-rw-r--r-- 1 30680 197609 21892 Oct  6 21:15 annotator.html
-rw-r--r-- 1 30680 197609  6643 Oct  9 22:05 b2a_review_probe.js
-rw-r--r-- 1 30680 197609  9244 Oct  9 17:11 b2a_shadow_flicker.js
-rw-r--r-- 1 30680 197609 13057 Oct  9 22:24 b2a_shadow_probe.js
-rw-r--r-- 1 30680 197609  4437 Oct  9 17:06 b2a_shadow_report.js
-rw-r--r-- 1 30680 197609 71829 Oct  9 13:51 bg_envelope.json
-rw-r--r-- 1 30680 197609  1101 Oct  9 22:38 config.py
-rw-r--r-- 1 30680 197609 19762 Oct  9 22:38 detect_overlay.js
-rw-r--r-- 1 30680 197609 12172 Oct  9 22:38 detect_overlay.test.js
-rw-r--r-- 1 30680 197609  3337 Oct  9 22:38 detect_ui.js
-rw-r--r-- 1 30680 197609 16631 Oct  9 22:38 fetch.py
-rw-r--r-- 1 30680 197609 13902 Oct  9 22:38 fetch_lib_test.py
-rw-r--r-- 1 30680 197609  7471 Oct  5 17:26 floor_detector.py
-rw-r--r-- 1 30680 197609  2512 Oct  5 17:40 floor_detector_test.py
-rw-r--r-- 1 30680 197609 10152 Oct  5 21:40 floor_roi.py
-rw-r--r-- 1 30680 197609  3906 Oct  5 20:58 floor_roi_test.py
-rw-r--r-- 1 30680 197609 16342 Oct  5 19:10 floor_sheet.py
-rw-r--r-- 1 30680 197609  9819 Oct  5 19:11 floor_sheet_test.py
-rw-r--r-- 1 30680 197609  4864 Oct 10 19:32 gt_annotator.html
-rw-r--r-- 1 30680 197609 36166 Oct 10 19:38 gt_annotator.js
-rw-r--r-- 1 30680 197609 21500 Oct 10 19:33 gt_lib.js
-rw-r--r-- 1 30680 197609 12660 Oct 10 19:33 gt_lib.test.js
-rw-r--r-- 1 30680 197609  8176 Oct 10 19:34 gt_roundtrip.test.js
-rw-r--r-- 1 30680 197609 18129 Oct 10 19:30 gt_server.py
-rw-r--r-- 1 30680 197609  5251 Oct 10 19:37 gt_server_e2e_test.py
-rw-r--r-- 1 30680 197609  7099 Oct 10 19:35 gt_server_test.py
drwxr-xr-x 1 30680 197609     0 Oct 10 19:39 gt_store
-rw-r--r-- 1 30680 197609  6844 Oct 10 19:35 gt_suggest.js
-rw-r--r-- 1 30680 197609  9897 Oct 10 13:36 human_detect.html
-rw-r--r-- 1 30680 197609 35146 Oct 10 13:31 human_detect.js
-rw-r--r-- 1 30680 197609  3565 Oct  6 20:05 human_detect.py
-rw-r--r-- 1 30680 197609 12901 Oct  5 18:33 human_detect_lib.js
-rw-r--r-- 1 30680 197609  9311 Oct  5 18:29 human_detect_lib.test.js
-rw-r--r-- 1 30680 197609 46377 Oct  9 22:38 human_pipe_lib.js
-rw-r--r-- 1 30680 197609 34576 Oct  9 22:38 human_pipe_lib.test.js
-rw-r--r-- 1 30680 197609 23487 Oct  9 15:30 human_replay_lib.js
-rw-r--r-- 1 30680 197609 32250 Oct 10 19:32 human_replay_lib.py
-rw-r--r-- 1 30680 197609 24059 Oct  4 20:39 human_replay_lib.test.js
-rw-r--r-- 1 30680 197609 10444 Oct 10 12:40 human_track.html
-rw-r--r-- 1 30680 197609  2309 Oct  9 14:26 human_track_static.test.js
-rw-r--r-- 1 30680 197609 13628 Oct  9 13:48 index.html
-rw-r--r-- 1 30680 197609 10670 Oct  6 21:15 leveling.html
-rw-r--r-- 1 30680 197609 24263 Oct  6 21:15 leveling.js
-rw-r--r-- 1 30680 197609 25430 Oct  5 20:57 leveling.py
-rw-r--r-- 1 30680 197609  5861 Oct  5 12:59 leveling_auto_test.py
drwxr-xr-x 1 30680 197609     0 Oct  5 12:21 leveling_estimators
-rw-r--r-- 1 30680 197609  4825 Oct  5 13:27 leveling_lib.py
-rw-r--r-- 1 30680 197609  6843 Oct  5 12:05 leveling_quality.py
-rw-r--r-- 1 30680 197609 14761 Oct  5 17:46 leveling_test.py
-rw-r--r-- 1 30680 197609   122 Oct  2 18:26 open_replay.bat
-rw-r--r-- 1 30680 197609 20445 Oct  9 22:38 panel.js
-rw-r--r-- 1 30680 197609 10655 Oct  9 22:38 panel.test.js
-rw-r--r-- 1 30680 197609 25005 Oct  8 09:59 registration.js
-rw-r--r-- 1 30680 197609 14684 Oct  8 10:06 registration.test.js
-rw-r--r-- 1 30680 197609 14109 Oct  7 13:15 registration_method.js
-rw-r--r-- 1 30680 197609 48026 Oct  9 22:38 replay.js
-rw-r--r-- 1 30680 197609 11098 Oct 10 17:39 rf_person.js
-rw-r--r-- 1 30680 197609  4494 Oct  9 16:13 rf_person.test.js
-rw-r--r-- 1 30680 197609 18946 Oct  9 16:04 rf_person_v1.json
-rw-r--r-- 1 30680 197609 15373 Oct  9 16:13 rf_test_fixture.json
-rw-r--r-- 1 30680 197609  3031 Oct 10 12:46 session_selection.js
-rw-r--r-- 1 30680 197609  5053 Oct 10 12:44 session_selection.test.js
-rw-r--r-- 1 30680 197609  2843 Oct 10 12:40 session_selection_test.py
-rw-r--r-- 1 30680 197609  9991 Oct  9 22:38 sessions_test.py
-rw-r--r-- 1 30680 197609  7176 Oct 10 18:35 test_fusion_feature_parity.js
-rw-r--r-- 1 30680 197609   464 Oct  4 19:06 trim.bat
-rw-r--r-- 1 30680 197609  5473 Oct  4 19:06 trim.js
-rw-r--r-- 1 30680 197609 15942 Oct  6 11:20 ui.css
-rw-r--r-- 1 30680 197609  1207 Oct  6 11:20 ui.js
-rw-r--r-- 1 30680 197609 11223 Oct  9 22:38 validation.html
-rw-r--r-- 1 30680 197609 12264 Oct  9 22:38 validation.py
-rw-r--r-- 1 30680 197609  6664 Oct  5 17:46 validation_test.py
drwxr-xr-x 1 30680 197609     0 Oct  4 18:49 vendor
---GT files---
-rw-r--r-- 1 30680 197609  4864 Oct 10 19:32 pc_apps/human_replay/gt_annotator.html
-rw-r--r-- 1 30680 197609 36166 Oct 10 19:38 pc_apps/human_replay/gt_annotator.js
-rw-r--r-- 1 30680 197609 21500 Oct 10 19:33 pc_apps/human_replay/gt_lib.js
-rw-r--r-- 1 30680 197609 12660 Oct 10 19:33 pc_apps/human_replay/gt_lib.test.js
-rw-r--r-- 1 30680 197609  8176 Oct 10 19:34 pc_apps/human_replay/gt_roundtrip.test.js
-rw-r--r-- 1 30680 197609 18129 Oct 10 19:30 pc_apps/human_replay/gt_server.py
-rw-r--r-- 1 30680 197609  5251 Oct 10 19:37 pc_apps/human_replay/gt_server_e2e_test.py
-rw-r--r-- 1 30680 197609  7099 Oct 10 19:35 pc_apps/human_replay/gt_server_test.py
-rw-r--r-- 1 30680 197609  6844 Oct 10 19:35 pc_apps/human_replay/gt_suggest.js

pc_apps/human_replay/gt_store:
total 13
drwxr-xr-x 1 30680 197609   0 Oct 10 19:39 .
drwxr-xr-x 1 30680 197609   0 Oct 10 19:38 ..
-rw-r--r-- 1 30680 197609 130 Oct 10 19:39 .gitignore
drwxr-xr-x 1 30680 197609   0 Oct 10 19:37 cap_20261010_180751
[0m
I'll audit this work item. Let me start by loading the required skill and exploring the files.
[0m$ [0mgit -C D:/Code/ldiar status --short 2>/dev/null | head -60; echo "---HEAD---"; git -C D:/Code/ldiar rev-parse HEAD 2>/dev/null; git -C D:/Code/ldiar branch --show-current 2>/dev/null
M docs/human_capture/README.md
 M pc_apps/console/README.txt
 M pc_apps/console/console.html
 M pc_apps/console/console_gui.py
 M pc_apps/console/console_html.test.js
 M pc_apps/console/console_test.py
 M pc_apps/console/make_release.py
 M pc_apps/human_core/data_loader.js
 M pc_apps/human_core/engine.js
 M pc_apps/human_core/leveling.js
 M pc_apps/human_core/run_all_tests.js
 M pc_apps/human_core/runner.js
 M pc_apps/human_core/schema.js
 M pc_apps/human_core/test_edge_cases.js
 M pc_apps/human_core/test_engine_smoke.js
 M pc_apps/human_core/test_perf.js
 M pc_apps/human_core/test_replay_contract.js
 M pc_apps/human_replay/config.py
 M pc_apps/human_replay/detect_overlay.js
 M pc_apps/human_replay/detect_overlay.test.js
 M pc_apps/human_replay/detect_ui.js
 M pc_apps/human_replay/fetch.py
 M pc_apps/human_replay/fetch_lib_test.py
 M pc_apps/human_replay/human_detect.html
 M pc_apps/human_replay/human_detect.js
 M pc_apps/human_replay/human_pipe_lib.js
 M pc_apps/human_replay/human_pipe_lib.test.js
 M pc_apps/human_replay/human_replay_lib.py
 M pc_apps/human_replay/human_track.html
 M pc_apps/human_replay/panel.js
 M pc_apps/human_replay/panel.test.js
 M pc_apps/human_replay/replay.js
 M pc_apps/human_replay/rf_person.js
 M pc_apps/human_replay/sessions_test.py
 M pc_apps/human_replay/validation.html
 M pc_apps/human_replay/validation.py
 M src/human_capture/config/capture.yaml
 M src/human_capture/scripts/capture_server.py
 M webui/human_capture/capture.js
 M webui/human_capture/capture_lib.js
 M webui/human_capture/capture_lib.test.js
 M webui/human_capture/index.html
?? docs/human_capture/B2A_DISPLAY_FIX_AND_SHADOW_PLAN.md
?? docs/human_capture/CAPTURE_PROTOCOL_DRAFT.md
?? docs/human_capture/CAPTURE_RUNSHEET_R1.md
?? docs/human_capture/FUSION_PRIORITY_RULE_DRAFT.md
?? docs/human_capture/HRRETV2_ACCEPTANCE.md
?? docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md
?? docs/human_capture/HR_SKELETON_OFFLINE_ACCEPTANCE.md
?? docs/human_capture/HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md
?? docs/human_capture/HUMAN_RECOGNITION_REVIEW_AND_PLAN.md
?? docs/human_capture/HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md
?? docs/human_capture/HUMAN_SKELETON_OFFLINE_PLAN.md
?? docs/human_capture/HUMAN_UNIFY_R1_ACCEPTANCE.md
?? docs/human_capture/RF_OPTIMIZATION_R1_ACCEPTANCE.md
?? docs/human_capture/SESSION_SYNC_RELEASE_ACCEPTANCE.md
?? docs/human_capture/SILENT_REGION_MEMORY_DRAFT.md
?? docs/human_capture/STILL_PERSON_RETENTION_PLAN.md
?? docs/human_capture/W03_CLOSEOUT_AND_PROTECTION_PLAN.md
?? docs/human_capture/evidence/2026-10-06_hrw03_r7/
---HEAD---
777296d707dbc0d6fe9684cad2a7500affbf3342
master
[0m
[0m$ [0mgit -C D:/Code/ldiar diff --stat pc_apps/human_replay/human_replay_lib.py; echo "===DIFF==="; git -C D:/Code/ldiar diff pc_apps/human_replay/human_replay_lib.py
pc_apps/human_replay/human_replay_lib.py | 200 +++++++++++++++++++++++++++++--
 1 file changed, 187 insertions(+), 13 deletions(-)
===DIFF===
diff --git a/pc_apps/human_replay/human_replay_lib.py b/pc_apps/human_replay/human_replay_lib.py
index e0e07e2..e766228 100644
--- a/pc_apps/human_replay/human_replay_lib.py
+++ b/pc_apps/human_replay/human_replay_lib.py
@@ -41,7 +41,12 @@ _FETCH = os.path.join(_HERE, "fetch.py")
 # 不许补 prefix/目录通配——保持「单文件 explicit」的最小攻击面（同 _serve_file 白名单精神）。
 _EXTRA_STATIC = frozenset({"human_detect_lib.js", "human_pipe_lib.js"})
 _proc_lock = threading.Lock()
-_proc = None  # 当前同步子进程
+_sync_thread = None      # 当前同步线程（替代旧 subprocess _proc）
+_sync_last_error = None  # 最近一次同步失败原因，前端轮询 /api/sync_status 看
+_sync_running_sid = None # 当前正在拉的 sid（None = 没在拉）
+_sync_last_sid = None     # 最近一次的 sid（成功/失败/短路"已在本地"都会写）
+_sync_last_result = None  # 最近一次结果：None（还在跑/未启动）/ "ok" / "failed"
+_sync_recoverable_sid = None  # 最近失败若因板端卡 transferring：允许人工「退回重试」的 sid
 
 
 def _is_ready_for_load(meta_path):
@@ -62,16 +67,21 @@ def _local_sessions(dest):
         try:
             with open(meta_p, "r", encoding="utf-8") as fh:
                 m = json.load(fh)
+            frames = m.get("frames")
+            size = os.path.getsize(os.path.join(d, "points.bin"))
+            if not isinstance(frames, list) or not frames or not size or size % 28:
+                continue  # 两页消费固定 28B/点；空帧表/空文件/未完整写入不预选。
             out[name] = {
                 "duration_sec": m.get("duration_sec"),
                 "total_points": m.get("total_points"),
                 "frames": len(m.get("frames") or []),
                 "frame_rate": m.get("frame_rate_hz_measured"),
                 "created_iso": m.get("created_iso"),
-                "bytes": os.path.getsize(os.path.join(d, "points.bin")),
+                "bytes": size,
+                "name": m.get("name"),
             }
-        except BaseException:
-            out[name] = {"error": "meta 不可读"}
+        except (OSError, ValueError, TypeError, AttributeError):
+            continue  # 元数据不可读不能当作本地可载入会话。
     return out
 
 
@@ -105,6 +115,30 @@ def _board_delete(sid, timeout=8.0):
         return json.loads(resp.read())
 
 
+def _sync_failure_note(sid):
+    """同步失败后实查板端，给面板可读的失败说明与能否人工退回。
+
+    transferring = 卡死：下载客户端中断时没人跑 fetch._fail 的自动回退。
+    干净失败（下载中断/SHA 不符）fetch 会自己退回 ready+extra.error，应显示真实错误。
+    返回 (说明文本, 是否可「退回重试」)。
+    """
+    try:
+        sess = _board_get("/api/v1/sessions/" + sid)
+    except urllib.error.HTTPError as exc:
+        if exc.code == 404:
+            return "板端无此会话（可能已被删）", False
+        return "fetch 返回 False（板端状态查询失败 %d）" % exc.code, False
+    except BaseException as exc:
+        return "fetch 返回 False（板端状态查询失败: %s）" % exc, False
+    state = sess.get("state")
+    if state == "transferring":
+        return "板端卡在传输中（上次同步中断）：点「退回重试」退回就绪后重新拉取。", True
+    err = (sess.get("extra") or {}).get("error")
+    if err:
+        return "fetch 失败：%s" % err, False
+    return "fetch 返回 False（板端状态 %s，无错误详情）" % (state or "未知"), False
+
+
 class Handler(BaseHTTPRequestHandler):
     def log_message(self, *a):
         # PyInstaller's windowed console has no stderr stream.
@@ -129,10 +163,14 @@ class Handler(BaseHTTPRequestHandler):
             return self._leveling("GET")
         if path.startswith("/api/human_detect/"):
             return self._human_detect("GET")
+        if path.startswith("/api/gt/"):
+            return self._gt("GET")
         if path == "/api/sessions":
             return self._api_sessions()
         if path == "/api/board/status":
             return self._board_status()
+        if path == "/api/sync_status":
+            return self._api_sync_status()
         if path.startswith("/api/file"):
             return self._serve_file()
         return self._serve_static(path)
@@ -213,6 +251,7 @@ class Handler(BaseHTTPRequestHandler):
                 "download_requested": bool(s.get("download_requested")),
                 "transferred": bool(s.get("transferred")),
                 "local": bool(li),
+                "name": (li or {}).get("name"),
             })
         # 本地有但板端已删的（FIFO 清过）也列上
         listed = {o["sid"] for o in out}
@@ -222,7 +261,8 @@ class Handler(BaseHTTPRequestHandler):
                             "created_iso": li.get("created_iso"),
                             "duration_sec": li.get("duration_sec"),
                             "frames": li.get("frames"),
-                            "local": True})
+                            "local": True,
+                            "name": li.get("name")})
         out.sort(key=lambda o: o.get("created_iso") or "", reverse=True)
         self._json({"sessions": out, "board_error": board_error})
 
@@ -235,13 +275,16 @@ class Handler(BaseHTTPRequestHandler):
         try:
             cur = _board_get("/api/v1/record/current")
             st["current"] = cur.get("session_id")
+            st["current_created_iso"] = cur.get("created_iso")  # 面板已录时长用
         except urllib.error.HTTPError as exc:
             if exc.code == 204:
                 st["current"] = None
             else:
                 st["current"] = None
+            st["current_created_iso"] = None
         except BaseException:
             st["current"] = None
+            st["current_created_iso"] = None
         self._json(st)
 
     def do_POST(self):  # noqa: N802
@@ -250,6 +293,8 @@ class Handler(BaseHTTPRequestHandler):
             return self._validation("POST")
         if path.startswith("/api/leveling/"):
             return self._leveling("POST")
+        if path.startswith("/api/gt/"):
+            return self._gt("POST")
         if path == "/api/board/record/start":
             return self._proxy(lambda: _board_post("/api/v1/record/start"))
         if path == "/api/board/record/stop":
@@ -262,10 +307,14 @@ class Handler(BaseHTTPRequestHandler):
             return self._proxy(lambda: _board_patch(sid, {"download_requested": True}))
         if path == "/api/sync":
             return self._api_sync()
+        if path == "/api/recover":
+            return self._api_recover()
         if path == "/api/load":
             return self._api_load()
         if path == "/api/delete":
             return self._api_delete()
+        if path == "/api/rename":
+            return self._api_rename()
         if path == "/api/save_annotations":
             return self._api_save_annotations()
         self.send_error(404)
@@ -294,6 +343,14 @@ class Handler(BaseHTTPRequestHandler):
             return self._json({"error": "人体识别工作台需要完整插件: " + str(exc)}, 503)
         return HD.handle(self, method, C.DEST_ROOT)
 
+    def _gt(self, method):
+        """HUMAN-GT-ANNOTATOR-R1 GT 工作台路由 (draft 保存 / 冻结 / 导出 / 建议)。"""
+        try:
+            import gt_server
+        except ImportError as exc:
+            return self._json({"error": "GT 工作台插件缺失: " + str(exc)}, 503)
+        return gt_server.handle(self, method, C.DEST_ROOT)
+
     def _api_delete(self):
         """删会话：scope=local|board|both。board 走 capture_server DELETE（连文件）。"""
         import shutil as _sh
@@ -330,6 +387,56 @@ class Handler(BaseHTTPRequestHandler):
                 out["local"] = "absent"
         self._json(out)
 
+    # ---------- 会话改名（本地别名，不动 sid/目录/板端） ----------
+    def _api_rename(self):
+        """写本机 <sid>/meta.json 的 name 字段；sid 是身份，改名只影响显示。
+
+        空 name = 删除该字段（恢复默认显示）。板端登记不改——要板端
+        webui 也显示名字得改 capture_server，属另一次授权。
+        """
+        body = self._body() or {}
+        sid = body.get("sid", "")
+        name = body.get("name", "")
+        if not self._SID_RE.match(sid):
+            return self._json({"ok": False, "error": "sid 非法"}, 400)
+        if not isinstance(name, str):
+            return self._json({"ok": False, "error": "name 必须是字符串"}, 400)
+        name = name.strip()
+        if len(name) > 60:
+            return self._json({"ok": False, "error": "名称最长 60 字符"}, 400)
+        if any(ord(c) < 32 for c in name):
+            return self._json({"ok": False, "error": "名称不能含控制字符"}, 400)
+
+        meta_path = os.path.join(C.DEST_ROOT, sid, "meta.json")
+        tmp_path = meta_path + ".tmp"
+        if not os.path.isfile(meta_path):
+            return self._json({"ok": False, "error": "本地无此会话（先下载再改名）"}, 404)
+        if os.path.exists(tmp_path):
+            return self._json({"ok": False, "error": "另一写者在途（.tmp 存在）"}, 409)
+        try:
+            with open(meta_path, "r", encoding="utf-8") as fh:
+                meta = json.load(fh)
+        except (OSError, ValueError) as exc:
+            return self._json({"ok": False, "error": "meta 读取失败: %s" % exc}, 500)
+        if name:
+            meta["name"] = name
+        else:
+            meta.pop("name", None)
+        try:
+            with open(tmp_path, "w", encoding="utf-8") as fh:
+                json.dump(meta, fh, ensure_ascii=False, indent=1)
+                fh.flush()
+                os.fsync(fh.fileno())
+            os.replace(tmp_path, meta_path)
+        except OSError as exc:
+            try:
+                if os.path.exists(tmp_path):
+                    os.remove(tmp_path)
+            except OSError:
+                pass
+            return self._json({"ok": False, "error": "写盘失败: %s" % exc}, 500)
+        return self._json({"ok": True, "sid": sid, "name": name})
+
     def _proxy(self, fn):
         try:
             out = fn()
@@ -354,14 +461,16 @@ class Handler(BaseHTTPRequestHandler):
 
     # ---------- 同步 ----------
     def _api_sync(self):
-        global _proc
+        global _sync_thread, _sync_last_error, _sync_running_sid, _sync_last_sid, _sync_last_result
+        global _sync_recoverable_sid
         body = self._body() or {}
         sid = body.get("sid")
         if not sid:
             return self.send_error(400, "sid 必填")
         with _proc_lock:
-            if _proc and _proc.poll() is None:
-                return self._json({"ok": False, "error": "已有同步在跑"}, 409)
+            if _sync_thread and _sync_thread.is_alive():
+                return self._json({"ok": False, "error": "已有同步在跑（%s）" % _sync_running_sid}, 409)
+            _sync_recoverable_sid = None  # 新一轮尝试开始：上一轮失败留下的「退回重试」入口作废
             # 如果板上还没 download_requested，先打标记（双保险）
             try:
                 _board_patch(sid, {"download_requested": True})
@@ -369,12 +478,77 @@ class Handler(BaseHTTPRequestHandler):
                 pass
             # 如果已转手持本地有件，不必重拉
             if _is_ready_for_load(os.path.join(C.DEST_ROOT, sid, "meta.json")):
+                _sync_last_sid = sid
+                _sync_last_result = "ok"      # 短路：已在本地——等同成功
+                _sync_last_error = None
+                _sync_running_sid = None
                 return self._json({"ok": True, "note": "已在本地"})
-            _proc = subprocess.Popen(
-                [sys.executable, "-u", _FETCH, "--sid", sid,
-                 "--dest", C.DEST_ROOT],
-                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
-        return self._json({"ok": True, "note": "拉取中，轮询 /api/sessions 等 local=true"})
+            # 新起一轮：清空上次结果
+            _sync_last_error = None
+            _sync_last_result = None
+            _sync_running_sid = sid
+            _sync_last_sid = sid
+
+            def _worker(target_sid):
+                global _sync_last_error, _sync_last_result, _sync_recoverable_sid
+                try:
+                    import fetch as F
+                    ok = F.process_session(target_sid, C.DEST_ROOT, log=lambda m: None)
+                    if ok:
+                        _sync_last_result = "ok"
+                        _sync_recoverable_sid = None
+                    else:
+                        # 实查板端再给结论：卡 transferring ≠ 有 extra.error（旧文案会误导）
+                        _sync_last_result = "failed"
+                        _sync_last_error, recoverable = _sync_failure_note(target_sid)
+                        _sync_recoverable_sid = target_sid if recoverable else None
+                except BaseException as exc:
+                    _sync_last_result = "failed"
+                    _sync_last_error = "%s: %s" % (type(exc).__name__, exc)
+                    _sync_recoverable_sid = None
+                finally:
+                    # 不在这里清 _sync_running_sid——前端一轮 /api/sync_status 看到
+                    # 线程死了再清，留给它先看到最终结果
+                    pass
+
+            _sync_thread = threading.Thread(target=_worker, args=(sid,), daemon=True)
+            _sync_thread.start()
+        return self._json({"ok": True, "note": "拉取中，轮询 /api/sync_status 等 local=true"})
+
+    def _api_sync_status(self):
+        """轮询端点：返回当前同步状态 + 最近失败原因，前端用来提前失败提示。"""
+        alive = bool(_sync_thread and _sync_thread.is_alive())
+        return self._json({
+            "running": alive,
+            "sid": _sync_running_sid if alive else None,
+            "last_sid": _sync_last_sid,
+            "last_result": _sync_last_result,   # None=未启动/在跑; "ok"=success; "failed"=error
+            "last_error": _sync_last_error,
+            "recoverable": bool(_sync_recoverable_sid),  # True=板端卡 transferring，可「退回重试」
+            "recover_sid": _sync_recoverable_sid,
+        })
+
+    def _api_recover(self):
+        """人工退回：把板端卡在 transferring 的会话置回 ready（仅面板显式触发）。
+
+        与 fetch._fail 的自动回退同一条状态机转换；区别是用于客户端进程
+        在下载中被中断、没人跑 _fail 时留下的卡死会话。
+        """
+        global _sync_recoverable_sid
+        body = self._body() or {}
+        sid = body.get("sid", "")
+        if not self._SID_RE.match(sid):
+            return self._json({"ok": False, "error": "sid 非法"}, 400)
+        try:
+            import fetch as F
+        except ImportError as exc:
+            return self._json({"ok": False, "error": "退回需要 fetch 模块: " + str(exc)}, 503)
+        ok, reason = F.recover(sid)
+        if not ok:
+            return self._json({"ok": False, "error": reason}, 409)
+        if _sync_recoverable_sid == sid:
+            _sync_recoverable_sid = None
+        return self._json({"ok": True, "sid": sid})
 
     def _api_load(self):
         def _pick():
[0m
[0m$ [0mcat D:/Code/ldiar/pc_apps/human_replay/gt_store/.gitignore; echo "===store tree==="; find D:/Code/ldiar/pc_apps/human_replay/gt_store -type f 2>/dev/null
# GT store 是运行期数据：草稿/冻结/建议缓存全都不进版本控制
# 只有 .gitignore 自身追踪
*
!.gitignore
===store tree===
D:/Code/ldiar/pc_apps/human_replay/gt_store/.gitignore
D:/Code/ldiar/pc_apps/human_replay/gt_store/cap_20261010_180751/draft.json
D:/Code/ldiar/pc_apps/human_replay/gt_store/cap_20261010_180751/fusion_frames.json
D:/Code/ldiar/pc_apps/human_replay/gt_store/cap_20261010_180751/GT_V1.json
D:/Code/ldiar/pc_apps/human_replay/gt_store/cap_20261010_180751/history.jsonl
D:/Code/ldiar/pc_apps/human_replay/gt_store/cap_20261010_180751/manifest.json
[0m
[0m$ [0mls -la "D:/Code/ldiar/" | head -50; echo "===docs gt==="; ls -la D:/Code/ldiar/docs/human_capture/ 2>/dev/null | grep -i -E "gt|annot"; echo "===parent docs==="; find D:/Code/ldiar/docs -iname "*gt*" 2>/dev/null; find D:/Code/ldiar -maxdepth 2 -iname "*ANNOTATOR*" 2>/dev/null
total 69
drwxr-xr-x 1 30680 197609    0 Oct 10 13:15 .
drwxr-xr-x 1 30680 197609    0 Oct  9 22:19 ..
drwxr-xr-x 1 30680 197609    0 Oct 10 19:31 .claude
drwxr-xr-x 1 30680 197609    0 Oct 10 19:44 .git
-rw-r--r-- 1 30680 197609 1709 Oct  6 22:04 .gitignore
drwxr-xr-x 1 30680 197609    0 Oct  5 12:54 .mirasim
drwxr-xr-x 1 30680 197609    0 Oct  6 10:57 .v2c
-rw-r--r-- 1 30680 197609 8064 Oct  6 21:15 AGENTS.md
-rw-r--r-- 1 30680 197609 7758 Oct  2 19:49 CLAUDE.md
drwxr-xr-x 1 30680 197609    0 Oct  3 23:57 ML
drwxr-xr-x 1 30680 197609    0 Oct  7 15:55 captures
drwxr-xr-x 1 30680 197609    0 Oct  2 16:02 docs
-rw-r--r-- 1 30680 197609 2760 Oct  5 15:56 fix-opencode-dns.ps1
-rw-r--r-- 1 30680 197609  217 Oct  4 19:27 open_console.bat
drwxr-xr-x 1 30680 197609    0 Oct 10 16:18 pc_apps
-rw-r--r-- 1 30680 197609 6617 Oct  8 13:46 pelican_bike.html
drwxr-xr-x 1 30680 197609    0 Oct  9 12:22 sidequests
drwxr-xr-x 1 30680 197609    0 Oct  6 21:23 src
drwxr-xr-x 1 30680 197609    0 Oct  4 14:32 tmp_gl_diag
drwxr-xr-x 1 30680 197609    0 Oct  6 22:15 tools
drwxr-xr-x 1 30680 197609    0 Oct  6 22:04 webui
drwxr-xr-x 1 30680 197609    0 Oct  6 21:36 文档收集（人工）
===docs gt===
===parent docs===
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/05_gt_schema.run.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/05_gt_schema.stderr.log
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/05_gt_schema.stdout.log
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/05_gt_schema_regression.js
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/05_gt_schema_regression.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/09_gt_pending.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/review_gt.js
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r40_research_r1/06_gt_label_format.md
D:/Code/ldiar/docs/human_capture/evidence/2026-10-07_hrw03_r40_research_r1/06_gt_tasks.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/gt_review_template.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/gt_challenge.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/gt_challenge.py
D:/Code/ldiar/docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/gt_challenge.run.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/gt_challenge.stderr.log
D:/Code/ldiar/docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/gt_challenge.stdout.log
D:/Code/ldiar/docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/gt_pending.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/GT_TASKS.md
D:/Code/ldiar/docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/identity_gt.json
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_c15_gt_validation
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_c15_gt_validation/workspace/gt_labels
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_c15_gt_validation/workspace/GT_SPEC.md
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_c15_gt_validation/workspace/render_dense_gt.py
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_gt_annotator_r1
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/GT_COVERAGE_REPORT.md
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175227/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175429/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175553/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175804/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175943/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180235/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180337/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180557/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180751/GT_v1.json.template
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_r1/02_DATA_AND_GT_AUDIT.md
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_r1/gt_verify
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_r1/gt_verify/render_with_gt_box.py
D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_human_unify_r1/gt_verify/__pycache__/render_with_gt_box.cpython-312.pyc
D:/Code/ldiar/docs/sidequests/evidence/2026-10-08_det06_fix_r1/run_gtprop.log
[0m
[0m→ [0mRead pc_apps/human_replay/gt_lib.js
[0m→ [0mRead pc_apps/human_replay/gt_server.py
[0m→ [0mRead pc_apps/human_replay/gt_annotator.js
[0m→ [0mRead pc_apps/human_replay/gt_suggest.js
[0m→ [0mRead pc_apps/human_replay/gt_lib.test.js
[0m→ [0mRead pc_apps/human_replay/gt_roundtrip.test.js
[0m→ [0mRead pc_apps/human_replay/gt_server_test.py
[0m→ [0mRead pc_apps/human_replay/gt_server_e2e_test.py
[0m
[0m$ [0mpython -c "
import json,hashlib
def h(b): return hashlib.sha256(b).hexdigest()
doc={'schema_version':'gt_workbench/1','session_id':'cap_x','objects':{'b':1,'a':2},'annotated_at':'2026'}
# what _save_draft RETURNS (stored bytes / returned sha):
returned=h(json.dumps(doc,ensure_ascii=False,separators=(',',':')).encode())
# what the guard RECOMPUTES from old on the next save:
old=json.loads(json.dumps(doc))
guard=h(json.dumps(old,sort_keys=True,ensure_ascii=False).encode())
print('returned sha (client stores):',returned)
print('guard   sha (server next):  ',guard)
print('MATCH' if returned==guard else 'MISMATCH -> spurious 409 on 2nd save')
"
returned sha (client stores): cefd4fd932bc4d564f6d6e62138cec7935d1efce17a7a6eb4a357a8d3ac76354
guard   sha (server next):   1c9e2a3c22e18db2b26245dfa2147d80cbe89ce790f426da8b7d79a570023039
MISMATCH -> spurious 409 on 2nd save
[0m
[0m→ [0mRead pc_apps/human_replay/gt_store/cap_20261010_180751/manifest.json
[0m
[0m$ [0mcd D:/Code/ldiar && ls -la --time-style=+%Y-%m-%dT%H:%M pc_apps/human_core/*.js pc_apps/human_replay/rf_person.js pc_apps/human_replay/human_replay_lib.js 2>/dev/null; echo "===git status human_core==="; git diff --stat pc_apps/human_core/ | tail -3; echo "===is human_replay_lib.js modified?==="; git status --short pc_apps/human_replay/human_replay_lib.js; echo "(empty=untouched)"; echo "===rf_person json==="; git status --short pc_apps/human_replay/rf_person_v1.json pc_apps/human_replay/rf_test_fixture.json
-rw-r--r-- 1 30680 197609  7467 2026-10-10T17:42 pc_apps/human_core/data_loader.js
-rw-r--r-- 1 30680 197609 40960 2026-10-10T18:48 pc_apps/human_core/engine.js
-rw-r--r-- 1 30680 197609  3795 2026-10-10T18:48 pc_apps/human_core/fusion.js
-rw-r--r-- 1 30680 197609  3020 2026-10-10T17:11 pc_apps/human_core/leveling.js
-rw-r--r-- 1 30680 197609  4184 2026-10-10T18:36 pc_apps/human_core/perf_profile_fusion.js
-rw-r--r-- 1 30680 197609   923 2026-10-10T17:20 pc_apps/human_core/run_all_tests.js
-rw-r--r-- 1 30680 197609  6329 2026-10-10T18:39 pc_apps/human_core/runner.js
-rw-r--r-- 1 30680 197609  9119 2026-10-10T17:14 pc_apps/human_core/schema.js
-rw-r--r-- 1 30680 197609  4714 2026-10-10T18:57 pc_apps/human_core/summarize_fusion_runs.js
-rw-r--r-- 1 30680 197609  5209 2026-10-10T17:42 pc_apps/human_core/test_baseline_parity.js
-rw-r--r-- 1 30680 197609  3831 2026-10-10T16:22 pc_apps/human_core/test_data_loader.js
-rw-r--r-- 1 30680 197609  8711 2026-10-10T17:17 pc_apps/human_core/test_edge_cases.js
-rw-r--r-- 1 30680 197609  4599 2026-10-10T17:17 pc_apps/human_core/test_engine_smoke.js
-rw-r--r-- 1 30680 197609  7417 2026-10-10T18:40 pc_apps/human_core/test_fusion_specific.js
-rw-r--r-- 1 30680 197609  4306 2026-10-10T16:34 pc_apps/human_core/test_model_compat.js
-rw-r--r-- 1 30680 197609  4132 2026-10-10T17:43 pc_apps/human_core/test_perf.js
-rw-r--r-- 1 30680 197609  3651 2026-10-10T17:17 pc_apps/human_core/test_replay_contract.js
-rw-r--r-- 1 30680 197609 10662 2026-10-10T17:42 pc_apps/human_core/test_rework.js
-rw-r--r-- 1 30680 197609  3242 2026-10-10T16:45 pc_apps/human_core/test_schema.js
-rw-r--r-- 1 30680 197609 23487 2026-10-09T15:30 pc_apps/human_replay/human_replay_lib.js
-rw-r--r-- 1 30680 197609 11098 2026-10-10T17:39 pc_apps/human_replay/rf_person.js
===git status human_core===
warning: in the working copy of 'pc_apps/human_core/data_loader.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pc_apps/human_core/engine.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pc_apps/human_core/leveling.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pc_apps/human_core/run_all_tests.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pc_apps/human_core/runner.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pc_apps/human_core/schema.js', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'pc_apps/human_core/test_replay_contract.js', LF will be replaced by CRLF the next time Git touches it
 pc_apps/human_core/test_perf.js            |  28 +-
 pc_apps/human_core/test_replay_contract.js | 202 +-----
 10 files changed, 691 insertions(+), 855 deletions(-)
===is human_replay_lib.js modified?===
(empty=untouched)
===rf_person json===
[0m
Now let me verify the suspected SHA-guard bug empirically, inspect the real store, evidence, and check file attribution.
[0m$ [0mcd D:/Code/ldiar && find docs -iname "*GT_ANNOTATOR*" -o -iname "*gt_annotator*" 2>/dev/null; echo "===evidence dir==="; find docs/human_capture/evidence/2026-10-10_gt_annotator_r1 -type f 2>/dev/null | head -40; echo "===search work order==="; grep -rl "HUMAN-GT-ANNOTATOR-R1" docs/ pc_apps/ 2>/dev/null | head
docs/human_capture/evidence/2026-10-10_gt_annotator_r1
===evidence dir===
docs/human_capture/evidence/2026-10-10_gt_annotator_r1/FINAL_REPORT.md
docs/human_capture/evidence/2026-10-10_gt_annotator_r1/OPENCODE_INDEPENDENT_REVIEW.md
docs/human_capture/evidence/2026-10-10_gt_annotator_r1/opencode_review_prompt_01.md
===search work order===
docs/human_capture/evidence/2026-10-10_gt_annotator_r1/FINAL_REPORT.md
docs/human_capture/evidence/2026-10-10_gt_annotator_r1/OPENCODE_INDEPENDENT_REVIEW.md
docs/human_capture/evidence/2026-10-10_gt_annotator_r1/opencode_review_prompt_01.md
pc_apps/human_replay/gt_annotator.html
pc_apps/human_replay/gt_annotator.js
pc_apps/human_replay/GT_ANNOTATOR_USER_GUIDE.md
pc_apps/human_replay/gt_lib.js
pc_apps/human_replay/gt_lib.test.js
pc_apps/human_replay/gt_server.py
pc_apps/human_replay/gt_server_test.py
[0m
[0m→ [0mRead docs/human_capture/evidence/2026-10-10_gt_annotator_r1/FINAL_REPORT.md
[0m→ [0mRead docs/human_capture/evidence/2026-10-10_gt_annotator_r1/OPENCODE_INDEPENDENT_REVIEW.md
[0m→ [0mRead docs/human_capture/evidence/2026-10-10_gt_annotator_r1/opencode_review_prompt_01.md
[0m→ [0mRead pc_apps/human_replay/gt_annotator.html
[0m
[0m$ [0mcd D:/Code/ldiar/pc_apps/human_replay && node gt_lib.test.js 2>&1 | tail -8; echo "=== roundtrip ==="; node gt_roundtrip.test.js 2>&1 | tail -12; echo "=== server_test ==="; python gt_server_test.py 2>&1 | tail -8
✓ 空 doc → UNKNOWN；含 model 但不 reviewed 不 → HUMAN_VERIFIED
  ✓ validate_doc: reviewed 但 source≠human 报错
  ✓ find_breaks: 出现/消失/跳帧
  ✓ doc JSON round-trip
  ✓ session_progress 覆盖工单 §5 列项
  ✓ 双人交叉各自 track 隔离：P1 消失 ≠ P2 消失

20 PASS, 0 FAIL
=== roundtrip ===
== gt_roundtrip (cap_20261010_180751 前 3 帧) ==
  ✓ S9 帧点数与 SESSION_DATASET_MANIFEST 一致
  ✓ split 产出紧凑全球 xyz
  ✓ 整段 split 与 帧分开 split 在 leveled xyz 上一致
  ✓ leveled→raw→leveled 距离 <1e-4
  ✓ ROI 选点 + encode/decode 一致
  ✓ doc JSON 保存→再载入 → 对象 map 等价
  ✓ SHA256 doc body 稳定 (同输入→同 hex)
  ✓ 两个 sid 的 doc frames_objects 相互独立

8 PASS, 0 FAIL
=== server_test ===
..........
----------------------------------------------------------------------
Ran 10 tests in 0.135s

OK
[0m
[0m$ [0mcd D:/Code/ldiar && echo "=== assignments of review_status=reviewed in annotator ==="; grep -n "reviewed" pc_apps/human_replay/gt_annotator.js; echo "=== any per-object review action? ==="; grep -n "review\|confirm\|确认\|审核\|已审" pc_apps/human_replay/gt_annotator.js | head -30; echo "=== play/pause? ==="; grep -n "play\|pause\|播放\|暂停" pc_apps/human_replay/gt_annotator.js pc_apps/human_replay/gt_annotator.html
=== assignments of review_status=reviewed in annotator ===
265:        if (o.review_status === "unreviewed") { stroke = col + "cc"; fill = col + "10"; }
293:            " [" + o.source + "/" + (o.review_status === "reviewed" ? "R" : "U") + "]", s3[0] + 4, s3[1] - 4);
360:        " · 已审 " + p.reviewed_frames +
540:    obj.review_status = "unreviewed";
607:        review_status: "unreviewed",
=== any per-object review action? ===
265:        if (o.review_status === "unreviewed") { stroke = col + "cc"; fill = col + "10"; }
293:            " [" + o.source + "/" + (o.review_status === "reviewed" ? "R" : "U") + "]", s3[0] + 4, s3[1] - 4);
360:        " · 已审 " + p.reviewed_frames +
385:            " <span style='opacity:.7'>" + o.source + "/" + o.review_status + "</span>" +
540:    obj.review_status = "unreviewed";
607:        review_status: "unreviewed",
=== play/pause? ===
pc_apps/human_replay/gt_annotator.js:356:        "<b>" + (S.doc.display_name || S.sid) + "</b>" +
pc_apps/human_replay/gt_annotator.html:10:  #wrap { display:grid; grid-template-columns: 1fr 320px; height:100vh; }
pc_apps/human_replay/gt_annotator.html:11:  #view { width:100%; height:100%; display:block; background:#0c0d10; cursor:crosshair; }
pc_apps/human_replay/gt_annotator.html:15:  .row { display:flex; gap:4px; align-items:center; margin:4px 0; flex-wrap:wrap; }
[0m
[0m$ [0mcd D:/Code/ldiar && sed -n '1,120p' pc_apps/human_replay/GT_ANNOTATOR_USER_GUIDE.md
# GT 标注工作台 USER_GUIDE — HUMAN-GT-ANNOTATOR-R1

2026-10-10。

## 0. 一键开门

```powershell
cd D:\Code\ldiar
python pc_apps\human_replay\human_replay_lib.py
# 浏览器自动弹 8901 → 自己改 URL：
#   http://127.0.0.1:8901/gt_annotator.html?sid=cap_20261010_175227
```

也可以：
- 下拉框选其它会话（默认显示 9 个新会话，S1 家具 = `cap_20261010_175227`）。
- 标注人名字段填你的 ID（例 `zhangsan`），否则默认 `annotator-1`（冻结时强制必填）。

## 1. 三步开始 S1 家具标注

1. 下拉选 `cap_20261010_175227` → 右侧进度面板出 `S1-empty-with-furniture` 标题。
2. 左手慢慢拖鼠标平移 / 滚轮缩放。看到家具黄色簇（桌子、柜子、沙发等 ~4-5 件在 10×10m 区）。
3. 标注第一件家具：
   - 按 `R` → 在家具圆团周围拖一个矩形，松手.
   - 按 `2` → 这件家具 class 变 FURNITURE（黄）.
   - (可选) 按 `T` 输入 track id (家具一般是 `F1/F2/...`，非 PERSON 不强制)。
   - 按 `K` 标关键帧（没用，家具 1 帧就够；S8/S9 人才跨帧需要）。

重复 ~5 件就 OK。

## 2. S8 坐 60 秒静立人 annotation (still recall 分母)

S8 = `cap_20261010_180557`（523 帧，单人 60 秒静立）。

1. 抽帧 - 每 25 帧标一帧（前文工单要求 static 抽稀 ≥ 25 帧 1 帧）。
2. 拖到人出现帧（从第 0 帧附近）。按 `L` 圈人形 (3-6 点多边形)。
3. 按 `1` 类变 PERSON。按 `T` 给 `P1`（单人 P1 就行）。
4. 按 `C` 复制到下一帧（源对象 source=propagated, review_status=unreviewed）。
5. 按 `→` 一帧一帧跳，对照实际形状修，按 `1` 重新 set human/reviewed。
6. 帧间批量：每 25 帧到一个采样帧，重复上一步，或在跳帧时按 `B` 看轨迹断点提示。

- 关键帧标记 K：标帧代表入/离场的标志点。工单需要 `入场帧、静止区段起止、离场帧` —— 分别在前中后找顯著变化的帧按 K。

## 3. S9 双人交叉（最难，先 S1+S8 defensively 通）

S9 = `cap_20261010_180751`（126 帧，双人交叉）。

1. **重点**：双人各自独立 `P1`、`P2`；不要因为空间"近"就把 P1 的 ROI 改成 P2。
2. 开帧快进到明显双人都可见的帧（一般 f10-f50）
3. 两人分别圈两个 ROI，一个 `P1` 一个 `P2`.
4. 轨迹交叉期：一帧一帧用 `→` 跟，交叉前后单独检查 `P1`、`P2` 身份。
   - 怀疑交叉期 ROI 混了 → 按 `B` 看断点。
   - cross 出现在两人的关键点（坐标差 <0.4m）时把 visibility 打 `partial` 或 `occluded`（右侧 obj 列表 → 点击 → 未编辑，这是 TODO）。
5. AI 预标：点上方「AI 预标」按钮（慢，3-5 分钟） → fusion_frames.json 会拉下来，帧帧渲染提建议。
   - 每个建议圆圈旁「接受/拒」按钮 → 接受会自动建对象（source=human）。
   - 接受后建议对象是 unreviewed，再按 `1`/`2`/`3`/`4` 类 + `K` 关键帧 → 与人确认一样。

> 警告：建议 source=model，永远不会自动 reviewed；GT 冻结时会被 `validate_doc` 拒绝（test_validate_doc_rejects_model_marked_reviewed 强制）。

## 4. 撤销 / 重做 / 保存 / 冻结

|用途|操作|
|---|---|
|撤销|`Ctrl+Z`（步进 50 层）|
|重做|`Ctrl+Y`|
|保存草稿|`Ctrl+S` 或左下「保存」→ 写入 `gt_store/<sid>/draft.json` + history.jsonl|
|冻结版本|左下「冻结版本」→ 服务器生成 `GT_V<n>.json` + SHA256 入 manifest|
|导出|左下「导出」→ 浏览器下载 manifest.json（GT_V<n> 在服务端）|

- 崩溃恢复：系统崩了刷新后，草稿从 `draft.json` 回读；SHA 冲突时服务器返回 409，不覆盖。
- 轨迹跨 gap 停止：同 track_id 的事件帧帧内有跳帧，GT 会自动 audit 提示（可解释）。

## 5. 标注合法性自查（军工要求）

- 冻结时候服务器执行 `gt_server._validate_doc`：错哪怕一项都 400。
- 主要规则：
  - `source` 必须是 human/model/propagated 之一。
  - `reviewed` 必须 `source=human`（不能 model 冒充）。
  - PERSON 必须 track_id；同帧内 track_id 唯一。
  - session_sha256.points 必须填（从 SESSION_DATASET_MANIFEST 拷贝）。
- 看全部 9 会话覆盖：`/api/gt/progress?sid=<sid>` 的服务器 response 给出工单要求的 track_ids 数 / person / 家具 / 冲突 / reviewed 覆盖率。

## 6. HOW TO 标注一段长时间人仍静止（S8 60 秒）

- 抽帧：每 25 帧 1 帧 → 把每个抽到的帧标 PERSON(visible)。
- 静止区段仍缺 visibility 单独标注：用 obj 右键看属性（TODO；当前 UI 未暴露），或在 doc 写 `note: "still"`。
- 离场帧 K 标关键帧。exit_frame 写进 episodes 字段（服务器端产物）——目前 UI 不直接编辑 episodes，用手动 JSON 补丁非常罕见。

## 7. 常见错误 / 修复

|症状|原因|修复|
|---|---|---|
|AI 预标慢|fusion 预跑 9 关联 + 49k 点|等待（S1 最长 ~5min）|
|建议点 0|fusion 在背景差分下没吃到人|按 `→` 换帧找下一个建议|
|接受后 track_id 出现 `P10+`|suggest_to_person_tid 全局累加|手动按 `T` 改名 → history 记 modified|
|保存返回 409|另一写者动 draft|刷新页面后重干；draft.json.sha256 冲突提示|
|冻结 400|同帧 track_id 重复|右侧 panel 点击对象改 track_id（按 `T`）|
|画面只看到建议看不到野点|z 带太窄|改 Z min/max 滑杆（默认 [0.05, 2.3]）|

## 8. 数据不污染承诺

- 不会改 `captures/remote/<sid>` 任何位置 (audit: gt_server 只写 `gt_store`)。
- 不会改生产 RF (`rf_person_v1.json`) — pre-annotation 只是计算；接受建议 = 建 GT 对象不是改模型。
- 不会改 leveling R/T (默认 `render_person_label.R/T` 是 REF_RT 同一)。
[0m
[0m$ [0mcd D:/Code/ldiar/pc_apps/human_replay/gt_store/cap_20261010_180751 && python -c "
import json
d=json.load(open('draft.json',encoding='utf-8'))
print('draft session_sha256 =', d.get('session_sha256'))
print('draft review_status =', d.get('review_status'), '| objects:', list((d.get('objects') or {}).values())[:1])
g=json.load(open('GT_V1.json',encoding='utf-8'))
print('GT_V1 session_sha256 =', g.get('session_sha256'))
print('GT_V1 review_status =', g.get('review_status'))
for oid,o in (g.get('objects') or {}).items():
    print('  obj', oid, 'source=',o.get('source'),'review=',o.get('review_status'))
"; echo "=== history ==="; cat history.jsonl
draft session_sha256 = {'points': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}
draft review_status = draft | objects: [{'session_id': 'cap_20261010_180751', 'frame_id': 'cap_20261010_180751:0', 'frame_idx': 0, 'timestamp': 0.1, 'object_id': 'obj_0', 'track_id': 'P1', 'class_name': 'PERSON', 'box_xy': [4.0, 4.0, 5.0, 5.0], 'z_min': 0.05, 'z_max': 2.3, 'raw_point_indices': ['s', 100, 200], 'point_count': 2, 'coordinate_frame': 'leveled-IFW192S', 'leveling_transform_id': 'render_person_label.R/T', 'source': 'human', 'review_status': 'unreviewed', 'annotator': 'e2e', 'schema_version': 'gt_workbench/1'}]
GT_V1 session_sha256 = {'points': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}
GT_V1 review_status = reviewed
  obj obj_0 source= human review= unreviewed
=== history ===
{"at": "2026-10-10T11:37:54Z", "n_objects": 1, "review_status": "draft"}
[0m
[0m$ [0mcd D:/Code/ldiar && echo "=== meta.json sha vs points.bin sha ==="; python -c "
import hashlib,os
for sid in ['cap_20261010_180751']:
    for f in ['meta.json','points.bin']:
        p=os.path.join('captures','remote',sid,f)
        if os.path.isfile(p):
            print(sid,f,hashlib.sha256(open(p,'rb').read()).hexdigest()[:24])
"; echo "=== engine candidate point_indices space (data_loader xyzi?) ==="; grep -n "point_indices\|xyzi\|n_points\|point_count" pc_apps/human_core/engine.js | head -30
=== meta.json sha vs points.bin sha ===
cap_20261010_180751 meta.json 60ddb3d5bc5b2cf078a66a84
cap_20261010_180751 points.bin 7d978a67336459f702c91a9e
=== engine candidate point_indices space (data_loader xyzi?) ===
40:    Object.assign(item, {in_points:in_pts||0, out_points:out_pts||0, in_candidates:in_cand||0, out_candidates:out_cand||0, elapsed_ms:performance.now()-start});
122:UnifiedEngine.prototype._level = function (xyzi, opts) {
126:    return leveling.level_frame(xyzi,contract.R,contract.T,contract.already_leveled);
128:UnifiedEngine.prototype.set_online_background = function (frames_xyzi, opts) {
132:    var clean=frames_xyzi.map(function(x){return self.pipe.denoise(self._level(x,opts));});
148:    var leveled=this._level(fc.xyzi,fc);
151:    add_layer(diag,S.LAYER.LEVELED,start,fc.n_points,fc.n_points);
189:        var c=S.make_candidate({candidate_id:"b_"+fc.frame_index+"_"+ci,point_indices:new Uint32Array(cl.members),centroid:{x:cl.cx,y:cl.cy,z:zsum/cl.n},point_count:cl.n,
206:    var clean_ids=subset_indices(leveled,indices(fc.n_points),clean);
207:    add_layer(diag,S.LAYER.DENOISE,start,fc.n_points,clean.length/4);
209:    var fg_ids=subset_indices(clean,clean_ids,fg.fg_xyzi);
211:    start=performance.now();var iso=pipe.cleanup_isolated_fg(fg.fg_xyzi);
212:    var final_ids=Array.from(subset_indices(fg.fg_xyzi,fg_ids,iso.xyzi));
214:    start=performance.now();var values=Array.from(iso.xyzi), sources=new Array(final_ids.length).fill(S.CAND_SRC.FG), seen=new Set(final_ids);
227:    var fg_final=new Float32Array(values), added=final_ids.length-iso.xyzi.length/4;
251:        var c=S.make_candidate({candidate_id:"a_"+fc.frame_index+"_"+i,point_indices:Uint32Array.from(mem,function(pp){return final_ids[pp];}),centroid:{x:f.cx,y:f.cy,z:f.cz},bbox:{min:min,max:max},point_count:mem.length,
319:    final_ids=Array.from(subset_indices(fg_pts,final_ids,iso.xyzi));
320:    var values=Array.from(iso.xyzi), sources=new Array(final_ids.length).fill(S.CAND_SRC.FG), seen=new Set(final_ids);
335:    var fg_final=new Float32Array(values), added=final_ids.length-iso.xyzi.length/4;
358:        var c=S.make_candidate({candidate_id:"a_"+fc.frame_index+"_"+i,point_indices:Uint32Array.from(mem,function(pp){return final_ids[pp];}),centroid:{x:f.cx,y:f.cy,z:f.cz},bbox:{min:min,max:max},point_count:mem.length,
377:        Array.from(c.point_indices).forEach(function(pi){
405:            centroid:{x:cl.cx,y:cl.cy,z:zsum/cl.n}, point_count:cl.n,
454:        var c=S.make_candidate({candidate_id:"b_"+fc.frame_index+"_"+bi,point_indices:Uint32Array.from(it.raw_indices),centroid:it.centroid,bbox:null,point_count:it.point_count,
523:    diag.layers.forEach(function(l){row[l.layer+"_in"]=l.in_points;row[l.layer+"_out_pts"]=l.out_points;row[l.layer+"_out_cand"]=l.out_candidates;row[l.layer+"_ms"]=+l.elapsed_ms.toFixed(2);});
[0m
[0m$ [0mcd D:/Code/ldiar && echo "=== AUTO_CANDIDATES.json exists? ==="; find docs -name "AUTO_CANDIDATES.json" 2>/dev/null | head; echo "(none = suggestions_auto always empty)"; echo; echo "=== JS validate_doc used in browser layer? ==="; grep -n "validate_doc" pc_apps/human_replay/gt_annotator.js || echo "NOT USED in gt_annotator.js"; echo; echo "=== indices() def in engine ==="; grep -n "function indices\|function subset_indices" pc_apps/human_core/engine.js; echo; echo "=== per_frame/global_split usage in gt_suggest ==="; grep -n "per_frame\|global_split\|global_lev\|global_raw_of_leaf\|frame_begins" pc_apps/human_replay/gt_suggest.js
=== AUTO_CANDIDATES.json exists? ===
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175227/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175429/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175553/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175804/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_175943/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180235/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180337/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180557/AUTO_CANDIDATES.json
docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/gt_workbench/cap_20261010_180751/AUTO_CANDIDATES.json
(none = suggestions_auto always empty)

=== JS validate_doc used in browser layer? ===
NOT USED in gt_annotator.js

=== indices() def in engine ===
22:function indices(n) { return Uint32Array.from({length:n}, function (_, i) { return i; }); }
24:function subset_indices(source, ids, subset) {

=== per_frame/global_split usage in gt_suggest ===
59:    var global_split = GT.split_frame_indices(flat, 4);       /* stride 4(xyzi) 而非 7(文件) */
60:    var global_lev = global_split.leveled_xyz;
61:    var global_raw_of_leaf = global_split.raw_of_leaf;
64:    var frame_begins = [0];
66:        /* 每帧 leaf 数量 = split 而不是 raw；frame_begins 仅供调试/审计，
68:         * per_frame split 用同一规则（过滤保序）——step 7 测试对拍这里。 */
69:        frame_begins.push(frame_begins[fi] + sess.frames[fi].n_points);
73:    var per_frame = sess.frames.map(function (f) {
98:        var sp = per_frame[fi2];
[0m
[0m$ [0mcd D:/Code/ldiar && sed -n '200,215p' pc_apps/human_core/engine.js; echo "=== indices fn body ==="; grep -n "indices=" pc_apps/human_core/engine.js | head; grep -n "function indices" pc_apps/human_core/*.js
this.pipe_ctx.tracker.tracks=diag._tracks;
    add_layer(diag,S.LAYER.TRACK,start,0,0,accepted.length,tracks.length);
    diag._candidates=cands;diag._events=[];
};
UnifiedEngine.prototype._tick_pipechain = function (fc, leveled, diag) {
    var pipe=this.pipe, start=performance.now(), clean=pipe.denoise(leveled);
    var clean_ids=subset_indices(leveled,indices(fc.n_points),clean);
    add_layer(diag,S.LAYER.DENOISE,start,fc.n_points,clean.length/4);
    start=performance.now();var fg=pipe.extract_foreground(clean,this.pipe_ctx.static_keys);
    var fg_ids=subset_indices(clean,clean_ids,fg.fg_xyzi);
    add_layer(diag,S.LAYER.FOREGROUND,start,clean.length/4,fg.n_fg);
    start=performance.now();var iso=pipe.cleanup_isolated_fg(fg.fg_xyzi);
    var final_ids=Array.from(subset_indices(fg.fg_xyzi,fg_ids,iso.xyzi));
    add_layer(diag,S.LAYER.CLEANUP,start,iso.fg_before_cleanup,iso.fg_after_cleanup);
    start=performance.now();var values=Array.from(iso.xyzi), sources=new Array(final_ids.length).fill(S.CAND_SRC.FG), seen=new Set(final_ids);
    if(this.cfg.candidates==="fg_plus_retained"){
=== indices fn body ===
pc_apps/human_core/engine.js:22:function indices(n) { return Uint32Array.from({length:n}, function (_, i) { return i; }); }
[0m
I've completed the read-only audit (ran the 3 safe suites: 20+8+10=38 PASS; the e2e suite not re-run because it writes the real `gt_store/`). Here is the full review. **Plan mode is active, so I have not written the file yet** — the report body is below and I'll save it on approval.

---

# OPENCODE_INDEPENDENT_REVIEW — HUMAN-GT-ANNOTATOR-R1

审计人: OpenCode `opencode-go/deepseek-v4.1-flash`（ponytail full，仅分析注入，无生产代码改动）
日期: 2026-10-10 · 基线 HEAD `777296d` · 工作树脏（多工单并行，见 Q6）

## 结论速览

| Q | 主题 | 判定 |
|---|---|---|
| 1 | STEP 1 页面清单覆盖 | **PARTIAL** — 无播放/暂停；无 XZ/YZ；几何修改无 UI |
| 2 | 模型建议冒充人工 GT | **PARTIAL FAIL** — 校验存在，但 reviewed 无法经 UI 产生且冻结越权标记 |
| 3 | 双人交叉强制合并 | **PASS** |
| 4 | 原子写 + SHA 守卫 | **FAIL** — SHA 守卫自相矛盾，第二次保存必 409 |
| 5 | raw/leveled/compact 契约 | **FAIL** — `gt_suggest` "compact" 实为 raw 帧内索引；sha 字段错标 |
| 6 | 未修改文件 | **PASS（有保留）** — `human_replay_lib.js`/`rf_person*.json` 未动；`human_core/*` 被并行工单改动 |
| 7 | Bug 清单 | 9 项，含 3 高危 |

---

## Q1 — STEP 1 覆盖度

已实现（有证据）：会话切换（`gt_annotator.js:785-804`）、时间轴 slider（`html:55`/`js:823`）、单帧前进后退（`js:826-827,467-468`）、XY BEV（`js:196-225`）、缩放/平移（`js:437-448,402-436`）、矩形（`js:406-413`）、多边形（`js:415-418,522-527`）、删除（`js:464`）、撤销/重做（`js:687-709`，但有 Q7-#5 缺陷）、快捷键（`js:449-475`）、track_id（`js:625-634`）、高度裁剪（`js:828-833`）、保存/恢复/导出（`js:720-766`）。

未完成 / 与 FINAL_REPORT 不符：
- **暂停/播放 完全没有**。只有单帧步进，无任何 play/pause/timer。`FINAL_REPORT.md:46` 宣称「暂停/播放/单帧 ±」✅ — **不实**。
- **XZ/YZ 侧视无**（仅 XY 俯视）。FINAL_REPORT 自认 partial，属实。
- **几何修改缺失**：只能改 class/track，不能改已画 ROI 形状；`visibility`/`note`/右键菜单无 UI（`USER_GUIDE` §6 自认 TODO）。
- **区段审核**（FINAL_REPORT #21）无实现，进度面板只读展示。

## Q2 — 模型建议冒充人工 GT

PASS 部分：`gt_lib.js:376-377` 与 `gt_server.py:365-366` 都拒绝 `reviewed && source!=human`；`gt_server_test.py:81-87` 覆盖并通过。

FAIL 部分（三条具体证据）：
1. **没有任何 UI 动作会把对象置为 `reviewed`**。`grep "reviewed" gt_annotator.js` 只有读取，写入仅 `review_status:"unreviewed"`（`js:540,607`）。`set_class`（`js:613-623`）只写 `source="human"`，不写 `reviewed`。→ 逐对象 reviewed 永不可达，`session_progress.reviewed_frames` 永远 0，`compute_gt_level` 经 UI 永远到不了 `HUMAN_VERIFIED`。`USER_GUIDE` §3「按 1 → 与人确认一样」**误导**。
2. **`accept_suggestion` 把模型对象直接改写成 `source="human"`**（`js:534-541`）。一次点击即 model→human；而 reviewed 又永不可达，二者区别坍塌。`FINAL_REPORT` #22 称「模型永远 source=model」与之矛盾。
3. **`_freeze` 无条件把文档级 `review_status` 置 `"reviewed"`**（`gt_server.py:328`），即使所有对象都还是 unreviewed。实测落盘 `GT_V1.json`：`review_status="reviewed"` 而对象 `review=unreviewed`（`gt_store/cap_20261010_180751/GT_V1.json`）。整体拔高审查等级。

附带：JS `validate_doc` 只在测试里用，浏览器路径从不调用（`grep` 证实）；服务端 `_validate_doc` 缺少 JS 有的 `point_count>0` 检查（`gt_lib.js:378` vs `gt_server.py:354-376`）。

## Q3 — 双人交叉强制合并

**PASS**。全代码无「空间最近」合并：`propagate_object` 克隆并保留 `track_id`（`gt_lib.js:260-279`）；`find_breaks` 纯按 track_id 统计（`gt_lib.js:285-306`）；`gt_lib.test.js:141-157,271-279` 通过。
残留风险（非空间合并）：`suggest_to_person_tid` 用 `_tid_map` 把引擎 label 映射到 P1/P2…（`js:550-563`），若引擎 label 在会话内复用/回卷，两个不同身份会被折叠成同一 P id；无检测。

## Q4 — 原子写 + SHA 守卫

- `_atomic_write`（tmp→fsync→replace + .bak）**正确**，`gt_server_test.py` 覆盖通过。
- `_freeze` 版本递增 / manifest **功能正确**，但：GT_V*.json 是裸 `open+write`（`gt_server.py:339-342`，非原子），且**先写文件后写 manifest**（`:336-349`）。崩溃落在两者之间 → 文件存在但 manifest 缺项 → 下次 `n` 不变、`os.path.exists(out)` 命中 → **永久 409「V1 已存在」**。并发冻结也无锁（TOCTOU 同号覆盖）。
- **SHA 守卫 `FAIL`（高危，可复现）**。客户端存的是 `_save_draft` 返回的 `sha256`＝`_sha256_hex(blob)`，其中 `blob=json.dumps(doc,separators=(",",":"))`（紧凑、非排序，`gt_server.py:283,294`）。下次保存时守卫把旧稿重新序列化为 `json.dumps(old,sort_keys=True,ensure_ascii=False)`（排序、默认分隔符，`:279`）再哈希。两种序列化必然不同：

```
python -c "... 省略"  →
returned sha (client stores): cefd4fd9…   (compact, unsorted)
guard    sha (server next):   1c9e2a3c…   (sort_keys, default sep)
→ MISMATCH → 第二次保存 spurious 409
```
后果：编辑后无法再保存（409 后 `save_sha` 不更新，之后每次保存都 409），冻结链被切断。另：`ingest_draft`/`load_session` 从不设置 `S.save_sha`（`js:35,79-86`），**加载已有 draft 后的首次保存无守卫**。测试矩阵没有「连续两次保存」用例，故漏检。

## Q5 — raw/leveled/compact 坐标契约

- 两个 stride 各自成立：`gt_annotator` 用 7（points.bin，`js:104-105`），`gt_suggest` 用 4（`data_loader` xyzi，`gt_suggest.js:59,74`）。
- **FAIL — `gt_suggest` 的 `raw_point_indices_compact` 名不副实**。引擎 `point_indices` 来自 `indices(fc.n_points)=0..n_points-1` 全量帧索引（`engine.js:22,206,251`），**未过滤零/NaN**；而 gt_lib 的 frame-compact 会剔除零/NaN（`gt_lib.js:54-62`）。`gt_suggest` 计算了 `global_split`/`per_frame` 却**从不把引擎索引经 `raw_of_leaf` 映射**（`:59-80` 的 `global_lev`/`global_raw_of_leaf`/`frame_begins`/`per_frame[fi2]` 全是死代码，grep 证实）。因此该字段若被下游消费会整体错位。当前 annotator 重建选区（`js:529-546`）才没爆，属潜伏雷。
- **FAIL — `session_sha256.points` 填的是 meta.json 的 sha，不是 points.bin 的 sha**。`init_doc_if_needed` 把 `points` 和 `meta` 都设成 `meta_sha`（`js:145`），而 `_get_session` 的 `meta_sha` 是 meta.json 的哈希（`gt_server.py:253`）。实测 meta sha `60ddb3d5…` ≠ points sha `7d978a67…`。冻结件对点云无真实绑定。

## Q6 — 未修改文件

- `pc_apps/human_replay/human_replay_lib.js`：**未改**（git status 空）。✅
- `rf_person_v1.json` / `rf_test_fixture.json`：**未改**。✅（`rf_person.js` 被改，但不在点名的 `rf_person*.json` 禁列，且属并行项。）
- `human_core/*.js`：工作树里 **10 个文件被改**（`git diff --stat`），mtime 16:22–18:57，属并行的 fusion 工单；`gt_suggest.js` 只 `require` 不写。**无法仅凭脏树证明 GT 工单没碰它们**，建议以各分支 diff 归因。
- `human_replay_lib.py`：GT 足迹＝2 行路由（GET/POST `startswith("/api/gt/")`）+ `_gt()`≈7 行（`:163-166,293-296,346-352`），与 FINAL_REPORT「+10」吻合。**其余 ~177 行（同步线程重写、`/api/rename`、session name）属另一工单**，非 GT 内容——「只改 2 行」对 GT 路由基本成立，但同文件携带了无关改动。

## Q7 — 具体 bug（含复现路径）

| # | 级别 | 位置 | 现象 | 修复 |
|---|---|---|---|---|
| 1 | 高危 | `gt_server.py:279` vs `:294` | 第二次保存必 409（Q4 复现命令） | 两处用**同一**序列化函数&同一 `sort_keys`；或返回即存 `sha256(blob)`、守卫也 `sha256(blob_bytes)` |
| 2 | 高危 | `js:534-541,613-623`；`gt_server.py:328` | reviewed 不可达 + 冻结越权标 reviewed | 加逐对象/区段「确认」动作置 `reviewed`；`_freeze` 仅当全部对象 reviewed 才置文档 reviewed，否则拒 |
| 3 | 中 | `gt_suggest.js:107-122` | compact 索引实为 raw 帧索引 | 经 `leaf_of_raw`/`raw_of_leaf` 映射后再编码；删死代码 |
| 4 | 中 | `js:145`；`gt_server.py:253` | `session_sha256.points` 非点云哈希 | 浏览器单独取 points.bin 的 sha |
| 5 | 中 | `js:613-641,341-348` | class/track/keyframe 改动不进 undo；`doc_snapshot_objects` 注释称深拷贝实为**引用**（`:345`），撤销别名污染 | in-place 编辑前 push 快照；快照改 `JSON.parse(JSON.stringify())` 深拷贝 |
| 6 | 中 | `gt_server.py:336-349` | 冻结崩溃后永久 409；无并发锁 | 先写 manifest 再落 GT 文件并加锁，或落 tmp→replace |
| 7 | 低 | `js:479` | `best=null` 漏 `var`（泄漏全局）；`S.mouse_lev` 首次未 move 前为 undefined → `pick_object_at` 出 NaN | `var best`；mousedown 时先算 `mouse_lev` |
| 8 | 低 | `gt_server.py:253,406` | `open(...).read()` 未关闭（Windows 句柄占用/ResourceWarning） | `with open(...)` |
| 9 | 低 | `gt_roundtrip.test.js:87-88` | 死 `flat3.subarray(...)` 计算后即被覆盖 | 删除 |

## 测试矩阵核验

- 实跑：`gt_lib.test.js` 20 PASS/0 FAIL；`gt_roundtrip.test.js` 8 PASS/0 FAIL；`gt_server_test.py` Ran 10 OK。合计 **38**。
- `gt_server_e2e_test.py`（5）**本次未复跑**：它写真实 `gt_store/`（非隔离），会污染证据目录；仓库内已有其产物（manifest V1 by `e2e`）。「43 全 PASS」的算术成立（20+8+10+5），但**无任何用例覆盖 Q4-#1、Q2 reviewed 工作流、Q5 索引映射** — 缺口正是三个 FAIL 所在。

---

**待确认后写入**：目标文件建议 `docs/human_capture/evidence/2026-10-10_gt_annotator_r1/OPENCODE_INDEPENDENT_REVIEW.md`（该路径现存一份本轮会话的裸日志，需覆盖）。但 AGENTS.md 规定「不覆盖旧 evidence」。请指示：
1. 覆盖该证据目录内的同名文件，还是新建 `…/OPENCODE_INDEPENDENT_REVIEW_r2.md`？
2. 或改写到 `pc_apps/human_replay/OPENCODE_INDEPENDENT_REVIEW.md`？

确认路径后我退出 plan 模式写入。
