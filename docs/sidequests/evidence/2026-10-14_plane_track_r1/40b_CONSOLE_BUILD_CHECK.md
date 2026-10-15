# 40b 控制台集成：构建与检查结果（追加；不改 40 正文）

## 产物（2026-10-15 11:07 重建）

| 文件 | 大小 | SHA256（前 32） |
|---|---|---|
| `pc_apps/console/dist/Console.exe` | 193,805,996 B | `0ba4aae4fc41a864d2a870ff4a50d00d…` |
| `pc_apps/console/dist/LiDAR_Console.zip` | 151,030,081 B（33 条目，`testzip` 无错） | `a51c03a9a54286a6a1054bbba3816d44…` |
| 旧 EXE 备份 | `dist/Console.exe.bak-20261015_before_plane01`（63,068,261 B，0:32 版） | — |

源码 SHA（前 24）：`console.html` `7ec0f7cc0d45a9ae0c71f513`、`console_gui.py` `64a9ab3ab718320f3b3743e1`、
`Console.spec` `1515f847a829e97e0a443da1`、`make_release.py` `bf2a5a05723bf8f64a148fc8`、
`console_html.test.js` `a6e3389959dbdcf8a0e9fbc9`、`console_test.py` `76d2f6a0d693b629d6bfb1c1`、
`sync_plane01_pages.py` `d5f82272f8543472a2b011db`。

## 检查结果

1. **源码侧**（`import console_gui` 直接调 `_start_plane_pages_server()`）：
   页面服务起在随机端口，`/index.html`、`/22_3D_TRACK_V3.html`、`/MANIFEST.json` 全 **200**；
   `_shell_url(8901,8902,8903,real_fall_port=8904,plane_port=<p>)` 输出含 `&plane_port=<p>`。
2. **单元测试**：`node console_html.test.js` **16 passed / 0 failed**；`python -B -W error console_test.py` **7 tests OK**（exit 0）。
3. **EXE 内嵌核验**（字节搜索）：`22_3D_TRACK_V3.html` ×1、`MANIFEST.json` ×1、`plane01_pages` ×19
   （19 个页面文件全部进 TOC；文件内容在压缩包内故搜不到正文）；`sync_plane01_pages.py` 只进 ZIP 的源码副本 ✓。
4. **冻结版 `--check-startup`：未通过，但卡在既有步骤**：
   `{"ok": false, "replay_port": 8901, "fall_port": 57561, "real_fall_port": null,
     "error": "real fall replay did not start"}` —— 检查脚本在 r04 真人回放服务处 `raise`，
   **我的 plane 步骤（`plane_pages_ok`）根本没执行到**。
   根因（与本次改动无关）：数据目录迁移后 `data/sessions` 里**没有 r04 需要的 `cap_20261013_094333`
   与 `cap_20261013_131958`**，r04 的 `server.py` 在导入期校验源 SHA 失败 → 服务起不来。
   ⇒ 结论：**本机"真人倒地回放"卡片与其冻结自验当前是环境性失败**，需要把这两段会话放回
   `data/sessions`（数据动作，需用户确认）或由验收方重新界定该检查范围；本单不改弱既有检查。

## 备注

- 冻结检查的失败**不影响** PLANE-01 卡片：页面已确认内嵌 + 源码侧服务已验证；等 r04 数据恢复后重跑
  `dist\Console.exe --check-startup <新路径>.json` 应看到 `plane_pages_ok: true`。
- 本次只改了 `pc_apps/console/`（用户明确要求），未触碰 `data/`、未改其他生产源码。
