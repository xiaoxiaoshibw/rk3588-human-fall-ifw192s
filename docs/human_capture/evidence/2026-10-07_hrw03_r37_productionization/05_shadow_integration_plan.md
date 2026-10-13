# 05 · R3.8 Shadow Integration 方案（R3.7 冻结的计划）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 性质：**R3.8 的实施计划**（本文件不执行、不改 production）。目标：在**不改变 production 输出**的前提下，证明两件事：
  1. 正确 registration 在完整管线上的收益与安全边界（对齐 R3.6）；
  2. **错误 registration 不会静默进入**（故障用例 100% fail-closed）。
- 单一变量：只允许 registration transform / artifact 状态变化；matcher、体素语义、background tier、清理逻辑、聚类/人体/Fall 判定逐字冻结（R3.7–R3.9 禁调 matcher）。

## 1. 双分支（+1 对账分支）

```text
Branch P （production 现状口径）:
  leveled current → denoise → online:build_static_map → extract_foreground → cleanup → clusters/tracks/events

Branch S （shadow, registered）:
  leveled current → registration(artifact) → denoise → online:build_static_map（在 reference 帧重建）
                 → 背景 = reference_static_keys(ref, 0.5) ∪ online   → extract_foreground → cleanup → clusters/tracks/events

Branch A （R3.6 对账基准，只用于等价门）:
  未变换 current 对 reference map 的查询（R3.6 条件 A 口径；不做任何对齐）
```

- Branch S 的参考分支语义 = `W03_R3_ACCEPTANCE.md` §3 冻结的 `background = reference_static OR online_static`；online 模型职责不动。
- 实现形态：Node 离线 harness，复用 `pc_apps/human_replay/{human_pipe_lib.js, human_replay_lib.js}` 的**未改**函数（与 R3.6 工具同源）；浏览器 smoke 仅作可选项（§7）。
- 输出（逐帧）：`fg_prod`、`fg_registered`、各自 `n_foreground/n_dropped/fg_voxels`、`clusters_before/after`、`cleanup_split_delta`、`topology_regression`、tracks/events、以及按区域的 absorb 计数。

## 2. 输入与产物（R3.8 开测前冻结）

- 输入：R3.7 已复核的会话/leveling artifact（00 §3），加 R3.8 新生成的 `captures/registration/<src>__to__<ref>/` artifact（writer 按 02/03 实现，gate 判定随 artifact 落盘）。
- 零改动断言：所有输入（session/leveling/`human_pipe_lib.js` 等）开测前记录 SHA，收测时复核；不一致 → STOP 并查因。
- 故障用例的 artifact 一律用**拷贝到临时目录**后篡改的副本生成；**禁止**改动 `captures/registration/` 与 `captures/leveled/` 原件。

## 3. Golden cases（与 R3.6 / W03 验收规范一致的帧与窗口）

| 用例 | 精确定义（沿用既有，不重新发现） | 期望方向 |
|---|---|---|
| **WD01** | 窗口 (3.50,−0.76) r≤0.9；组 = 全 165 帧；代表帧 f2/f42/f150；问题帧段 f1–62 / f92–99 / f121–125 / f146–164 | 静态物被吸收；residual 大降（R3.6：14,966→1,875） |
| **WD02** | 远场桶 (10.75,4.25)/(10.25,−1.75)/(10.50,5.50) 各 r≤1.5（及 >8 m 全体） | residual 大降（R3.6：104,742→11,625） |
| **human f55 / f150 / f155 / f160** | 站点窗 (1.45,0.85) r≤0.6；分带 z≥1.2 / 0.8–1.2 / 0.3–0.8 | 高带（z≥1.2）不恶化；混合带如实登记 |
| **clean controls** | f63/65/80/85/90/92/95/99/123/146（人窗 r≤0.6，簇质心） | 吸收 ≈0（R3.6：全 0–1 点） |
| **safety 对照** | PROXY_FRAMES f10/f30/f55/f150/f155/f160 的 proxy 吸收 | 只对照，不作收益口径（R3.5 §2 裁决） |
| 共同门（每轮都查） | `cleanup_split_delta == 0`（全帧）；无新 green / 无新 purple；HUMAN track 不被吸回背景；人体保留率 ≥ R2.6b 水平 | `W03_R3_ACCEPTANCE.md` §2.3 |

## 4. 故障用例（必须证明"错误 registration 不会静默进入"）

| 用例 | 构造（临时副本） | 预期状态 | 预期行为 |
|---|---|---|---|
| **F1 wrong artifact** | ①把 artifact 用于非绑定会话（A→B 的 artifact 施加到 C）；②篡改拷贝中的 `reference_session` 字段并重写 manifest 使其"看起来合法" | ①`REJECTED/STALE`（绑定不符）②`REJECTED(INCONSISTENT_GATE)` 或按绑定不符处理（R3.8 实现须逐条对齐 04 §3） | SAFE：Branch S 输出与 Branch P **完全一致**（逐帧计数 + clusters/events） |
| **F2 stale SHA artifact** | 拷贝 artifact 后翻转 `registration.json` 一个字节（保持 JSON 合法）；另一变体：翻转 leveling 侧 `tls/transform.json` 拷贝副本 | `REJECTED(ARTIFACT_TAMPERED)` / `STALE(LEVELING_SHA_MISMATCH)` | 同上：不改 foreground、不应用变换、日志给具体 reason |
| **F3 missing artifact** | 不提供 artifact | `UNAVAILABLE(NO_ARTIFACT)` | 同上；并断言日志出现 `[REG] state=UNAVAILABLE` |

附加负例（低成本）：F4 重复应用（ERR_DUPLICATE_REGISTRATION）、F5 对 raw/别的 sid 应用（ERR_FRAME_MISMATCH）——运行期断言直接暴露，不吞错。

## 5. 指标与对账

1. **等价门（硬性）**：Branch A/B 的逐点/逐组输出对 R3.6 `03_results.json`（digest `23830ede…`）**逐整数复现**（桶计数、分组 stats），矩阵差 ≤1e-6（canonical vs `conditions.B`，见 01 §3.2）；r7 的 19/19 checks 全复现。
2. **收益**（vs A）：WD01/WD02 residual 相对下降 ≥50%（R3.6 实测 87.5%/88.9%）。
3. **vs P（现状口径）**：WD01 在线漏匹配问题（~101 行绿、R3.0）与 WD02 的 300 行 NON_HUMAN candidate 必须消失或显著下降；`cleanup_split_delta` 不增。
4. **人体安全**：clean controls 全帧总吸收 ≤5 点（R3.6：1）；f55 高带 vs P ≤ +1.0 pp；f155/f160 高带吸收增量逐帧登记（R3.6 A→B：+2.0 pp / +7.3 pp，均发生在站点静态块窗口，须在报告中逐点归因）；tracks/events 与 P 相比无丢失。
5. **确定性**：同输入 2 次运行 digest 一致（关键路径 5 次为可选加强）。
6. **日志**：按 04 §5 输出；故障用例必须有具体 reason。

## 6. 预注册判定门（R3.8 报告按此判定，不事后改）

```text
S1 等价门（§5.1）全部成立                     → 否则 STOP（实现/输入有偏差）
S2 WD01 residual_S ≤ 0.5 × residual_A         （且不差于 Branch P）
S3 WD02 residual_S ≤ 0.5 × residual_A         （且不差于 Branch P）
S4 人体安全：clean ≤5 点 / f55 ≤+1.0 pp / 无 track-event 丢失
S5 故障用例 F1–F5 全部 fail-closed（SAFE 输出 == Branch P）
S6 2× 确定性一致
S7 共同门（无新 green/purple 且 cleanup_split_delta == 0）成立
```

- **全部 PASS → 进入 R3.9 前置**（用户授权后实施最小生产接入）。
- 任一 FAIL → STOP；按 WORKFLOW §5 区分缺陷/新反例/新需求，禁止顺手改 matcher 或重调 registration 来"凑"通过。
- audited pair 在 gate 下若得 `DEGRADED`（WARN），S2/S3 仍可执行（shadow 允许 DEGRADED），但 **R3.9 不得消费**；是否放行需用户对 03 §6 的实测结果另行裁决。

## 7. 可选项（需工单明确才做）

- 浏览器 smoke：在 `human_detect` 页面以本地临时开关把 Branch S 可视化（不 commit、不进入默认路径）；
- 5× 确定性加强、更多会话对（需新数据/授权，不在本计划范围）。

## 8. 非目标

- 不重构 matcher；不引入新的背景模型分层；不改 `PIPE` 任何阈值；不对 reference 图做形态学；
- 不把 shadow harness 做成 production 依赖；
- 不采集/部署/commit；故障副本用后即删（仅保留哈希与日志证据）。
