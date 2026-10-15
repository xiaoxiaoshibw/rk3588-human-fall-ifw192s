# 40 PLANE-01 证据页并入总控制台（子文件夹 + 主页面卡片）

触发：用户"所有证据统一到总控制台里面可以放个子文件夹打开用来存放html页面，还有网站就放总控台总页面"。

## 做了什么（只增不改既有卡片）

1. **子文件夹** `pc_apps/console/plane01_pages/`（19 文件 / 7.31 MB）：
   - HTML：`22_3D_TRACK_V3.html`（3D：完整形态+体形框+航线）、`20_3D_TRACK_V2.html`、`19_3D_TRACK.html`、
     `15_DEMO_FG.html`（去背景回放）、`09_DEMO_10HZ.html`（10 Hz 回放）+ `three.min.js`/`OrbitControls.js`（r127）
   - 图 8 张（30_TBD_TRACK / 26_SHAPE_ALIGNED / 25_SHAPE_SILHOUETTE / 22_UNION_MOVING / 04_BACKGROUND /
     06_TRACK_REAL / 18_DISLOCATION_EXPLAINED / 09_DEMO_SUMMARY）
   - 视频 2 个（20_PLANE_FG_TRACK_V2.mp4 推荐 / 17_PLANE_FG_TRACK.mp4）
   - `index.html`（总入口，分节列出上述内容）+ `MANIFEST.json`（每个文件对应证据源的 SHA256）
   - 由 `pc_apps/console/sync_plane01_pages.py` **幂等生成**（只读证据目录，重跑即刷新）
2. **总控制台启动服务** `console_gui.py`：新增 `_start_plane_pages_server()`
   —— 用 stdlib `http.server` 在随机空闲端口只读服务 `plane01_pages/`；`_shell_url()` 增加 `plane_port`；
   冻结版启动检查同步加 `plane_port` 与 `plane_pages_ok`（并计入 `ok`）。
3. **主页面卡片** `console.html`：新卡片 **「小目标跟踪」**（PLANE-01 · 纸飞机 3D/去背景/跟踪证据页）
   → `plane_base/index.html`；缺端口时显示"证据页面目录 plane01_pages 未随本次控制台启动"。
4. **打包** `Console.spec`：`datas` 增加 `('plane01_pages', 'plane01_pages')`。

## 测试

| 套件 | 结果 |
|---|---|
| `node console_html.test.js` | **16 passed, 0 failed**（新增「小目标跟踪入口使用本实例端口，缺端口时提示用仓库内控制台」） |
| `python -B -W error console_test.py` | **Ran 7 tests OK**（新增 `_shell_url(..., plane_port=…)` 断言） |
| 冻结版 `--check-startup` | 见下表（重建后运行，含 `plane_pages_ok`） |

## 已知边界

- 准实时 P1 页（`rt_server.py`，10 Hz 全管线）**不随控制台启动**：它是开发侧脚本（需要 evidence 目录与
  本机 Python），`index.html` 里写明了启动命令。若日后要进 EXE，需要把脚本与数据一起打包，属另一次授权。
- 页面是证据的**副本**（源仍在 `docs/sidequests/evidence/2026-10-14_plane_track_r1/`）；证据目录更新后
  重跑 `sync_plane01_pages.py` 即可刷新，不必手工拷贝。
- `data/` 未被触碰；本改动只涉及 `pc_apps/console/`（用户本次明确要求）。
