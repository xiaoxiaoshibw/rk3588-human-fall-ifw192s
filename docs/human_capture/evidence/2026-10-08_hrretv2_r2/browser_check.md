# inc2 浏览器行为验证（human_detect · cap_20261002_223757）

- 日期：2026-10-08（Asia/Shanghai）；执行：OpenCode（本会话）。
- 环境：Windows 本机；本地只读服务 = `pc_apps/human_replay/human_replay_lib.py` 的 `ThreadingHTTPServer` @ `127.0.0.1:8901`
  （以 `python -c` 直接起，绕开 `main()` 的自动开窗；全程只读，无板端、无网络外联）；页面经 Code Mode 桌面浏览器打开。
- 页面：`/human_detect.html?sid=cap_20261002_223757`。**旗标缺省**：`human_detect.js` 以 `S.pipe` 作 ctx（无 `fusion` 字段），
  且页面无 artifact 加载路径 ⇒ 浏览器侧当前恒为 P 路径（回退语义）。
- 时序备注：首次 `wait("个静态体素")` 30s 超时（疑似等待发生在导航完成前）；紧接着的状态读取显示管线已就绪，
  未影响任何读数；此后所有读数均在就绪后采集。

## 1. 页面读数（DOM，就绪后）

| 项 | 帧 1（idx 0） | 帧 30（idx 29，seekBar=29 触发 set_idx） |
|---|---|---|
| HUD | 帧 1/165 seq=176018 t=00:00.0 点=49126 [TLS 配平] [无 ROI] | 帧 30/165 seq=176047 t=00:03.0 点=49134 [TLS 配平] [无 ROI] |
| 点链 `#pipeCounts` | 49126 → 49126 → 3913（削 45213） | 49134 → 49134 → 3930（削 45204） |
| 清理 `#pipeCleanup` | 候选 39 · veto 4 · 删 35 点 / 35 voxel · 其他z保活 6 cell · 簇 24→23 | 候选 31 · veto 3 · 删 28 点 / 28 voxel · 其他z保活 4 cell · 簇 25→25 |
| 簇 `#pipeClusters` | 5 簇 · 确认 ×2 · 候选 ×0 · 非人 ×3 | 5 簇 · 确认 ×1 · 候选 ×0 · 非人 ×4 |
| `#pipeStatus` | 静态背景 1720 个静态体素（896ms）· 每帧跑完整管线 | 同左（建模一次） |
| `#status` | 就绪 (3713ms) | 就绪 (3713ms) |
| console（两次检查） | `[]`（无错误） | `[]` |

## 2. 运行期旗标三态探针（页面内 evaluate，直接调页面已加载的 `human_pipe_lib`）

输入：`online={（2.0,0,0.5）}`，`refkeys={（1.0,0,0.5）}`，缓冲 `[2.0 / 1.0 / 2.02]`（1.0=参考命中；2.0/2.02=在线持久）。

| 调用 | n_fg | `fusion` 字段 | 结论 |
|---|---|---|---|
| `pipeline_frame(buf, 0, {static_keys})` | 1 | 无 | 缺省=关=P（在线删 2.0/2.02） |
| `pipeline_frame(buf, 1, {…, fusion:{refkeys}})` | 2 | `{n_ref_removed:1, n_online_only_kept:2, n_online_supported_removed:0}` | 开=v2（参考删 1.0；在线-only 保留） |
| `pipeline_frame(buf, 2, {…, fusion:{refkeys:null}})` | 1 | 无 | 旗标对象在但无参考 ⇒ 回 P |

另外：`typeof extract_foreground_fused === "function"` = true（页面加载的即 inc2 后代码）。

## 3. 节点复刻对账（`browser_replica_check.js`）

用**同字节输入**（`leveled_latest?sid=…` 的 R/t + `points.bin` 跨步 7 → 原位变换 → denoise → `build_static_map` → 逐帧 `pipeline_frame`）
在 node 复刻页面管线，比对上表三帧读数与静态体素数：

- **7/7 PASS**（静态体素 1720 + 帧 1/帧 30 各 3 组计数逐字符一致）；明细 `browser_replica_results.json`
  （含输入 SHA 与 transform 值）。
- 意义：浏览器缺省行为 == 节点 P 行为；页面零改动与「旗标默认关=行为不变」在真实浏览器运行时成立。

## 4. 回退语义（含非 VALID）

- 页面无 artifact 加载 ⇒ 无 `ctx.fusion` ⇒ 恒 P（结构上不可能误开）。
- 即便未来 R3.9 接线：`registration.fusionKeys` fail-closed（仅 `VALID`；`UNAVAILABLE/REJECTED/STALE/DEGRADED` → null）。
  本轮真实数据：四个现存 artifact 均因代码绑定漂移为 `STALE` → 开旗标也不启用 v2（见 `digest_results.json` 的 D3）。

## 5. 未采集项

- **截图**：浏览器工具要求桌面窗口可见，本环境不满足（两次尝试失败：`Screenshot needs a visible tab`）。
  以 DOM 读数 + 节点复刻对账替代影像证据；页面本身无异常（console 空）。
