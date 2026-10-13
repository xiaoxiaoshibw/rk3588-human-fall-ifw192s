# C1 动态稳定化 — 独立复审判定

- 复审人：OpenCode `opencode-go/deepseek-v4.1-flash`（独立审计，只读，未改任何代码/证据）
- 复审对象：`docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization/`
- 依据：`C1_REVIEW_PROMPT.md`（5 审查点 + 交付格式）
- 已加载并执行 `ponytail` skill（full）；本任务为代码/证据审查，按其为"读全再断"。
- 基线核对：`label_audit/report.json` 四枚输入 SHA 与工作树逐位一致（`b2a_shadow_probe.js` `74b4a272…`、`detect_overlay.js` `585d2964…`、`rf_person_v1.json` `4c83db11…`、`bg_envelope.json` `28afdaa4…`）→ **锚点可复现 PASS**。
- 生产未落硬门：`grep HARD_GATE detect_overlay.js` 空 → v2 仍为离线候选，符合"生产零改动"。

---

## 0. 一句话结论

硬门 `n_pts≥500` **在本数据上是安全且有效的预过滤**，但其**推广性主张**（Wilson 置信、泄漏已排除、动态召回 100%）经不起拆解；六段全是静态站立、无任何动态真值。→ **C1 进入 C2 = NO**（见 §7）。

---

## 1. 统计真实性 / "过拟合于 6 段 stand"可否被驳斥 — **FAIL**

被审主张：`gate_confidence.md:1-6` 以 Wilson 95% CI **[0.993835, 0.999807]**（person 914/915 过门）证明硬门可靠、非过拟合 6 段。

裁定与反证：

- **伪重复（pseudo-replication）**：915 条 person 簇来自 **6 段、同一人、同一房间、≤2.5 m 站立**（`label_audit/report.json` `ai_labels_rows[*].person_xy_span_m` = 0.030–0.060 m）。Wilson 假设样本 iid；此处每条并非独立试验。**有效样本量是 6 段（或 6 个站位），不是 915**。按段重算 Wilson（`k=6,n=6`）下界 ≈ **0.61**，不是 0.994。→ Wilson 数字**不能**驳斥"过拟合"质疑，反而掩盖它。
- **边界人已存在**：`cluster_dataset.jsonl` person `n_pts` min=**33**、p1=**937**；furniture max=**80**、p95=60。硬门 500 已丢弃 **1 个真实 person 簇**（`gate_confidence.md:6` 自认 121622 frame87 n=33 `borderline`）。"人全都通过硬门"（`ab/summary.md:19`）与 `cluster_dataset` 不符。
- **测试域外**：person 只覆盖 ≤2.5 m；点数是距离代理，远距/遮挡/儿童未被采样。furniture 仅同房间同批柜面。→ 硬门只对"本采样域"成立。
- **可辩护部分**：500 不是学习参数，是带 457 点间距（937↔80，≈11.7×）的常数下界，物理上保守。故作为**作用域内预过滤**成立；作为**泛化保证**不成立。

## 2. 泄漏审计 / `v2b_noleak=0.3178` vs `v2b=0.2699` — **FAIL（不可结论）**

被审主张：`rf_v2/SUMMARY.md:8` "去 n_pts/max_pts → 真正的泛化力"。

裁定与反证：

- **方向相反**：去 fv[0/1/2] 后 noperson 召回由 0.2699 → 0.3178（**涨** 4.8pt；`results.json` `v2b_hard_neg` tn197/fp533、`v2b_noleak` tn232/fp498）。若 n_pts 是"泄漏捷径"，去掉应**掉**分，实际反涨 → **n_pts 是主泄漏的假设被自身数字证伪**，而非证实。
- **人召回未被撬动**：`person_recall` 两次均 1.0000 → 人也非靠 n_pts 撑起，说明 1.0 另有来源（其余 48 维含同域代理），"真泛化力"未建立。
- **slice 太粗且域混合**：只去 3/51 维；评测把**帧级 ROI pod**（约 5 万点）与**簇级**样本同一混淆矩阵（`c1_rf_v2_eval.py:104-113,131-184`），n_pts 在"帧人(大)/空帧(大)/家具簇(小)"间并不单调，指标语义含混。→ **需更多 slice**：簇级单域评测、逐特征消融、帧/簇分离测试集。
- 旁证：`rf_v2` 系列 noperson 召回普遍 **0.24–0.32**（`results.json`），重训 RF 本身仍是弱家具判别器；被采纳的是**另一个**机制（硬门），不是这些实验。

## 3. 标签完整性 / 有无 `posture!=stand` 被误标人 — **PASS（窄口径）**

- `label_audit/report.json` `ai_labels_rows[*].posture_set` 全 = `["stand"]`，`confidence_set` 全 = `["auto"]`，11 段（6 stand + 5 帽）无一 `walk/none` 混入；`c1_label_audit.py:152-202` 逻辑确实按 `posture` 计数。→ **无 walk 帧污染 person 目标**。
- 但口径外的问题（更重）：
  - 全为 **auto 标签、零人工逐帧**（`human_annotations` 全 0）；训练"人"真值仅到"站着的真人"粒度。
  - 六段 `person_xy_span_m` 0.030–0.060 m → **无一个动态帧**。"动态真人召回"（`c1_ab_metrics.py:6`）在本数据**不可测**；帽子 5 段更标 `UNKNOWN`。
  - `attribution_v2` 的 `v_airoi = 100%` 用 `ai_labels` 的 ROI 位置裁窗再判人（`c1_attribution_v2.py:106-120`），**用被评 GT 喂检测器** → 循环论证，不可作独立证据；生产拓扑 `v_p` 才是可采信项（98.1–99.1%）。

## 4. Track 闪烁 / 女近(121647) 家具 track 最高 — **FAIL（成因被误述）+ 证据悬空**

- `ab/per_session.json:51-64` 女近 v1 `furniture_tracks=18` > 男近 12 / 男中 13 / 女中 15。
- **真实成因**：该字段名不副实——`c1_ab_metrics.py:69-72` 在 track 短暂离开 `confirmed` 时即 `pop` 并封段，重现**同 id 也新建 episode**。故 18 = **重入碎片数**，非唯一 track 数。
- 原文档 `flicker_analysis.json`（`2026-10-09_b2a_shadow_r1/`）明证：女近柜位 `cabinet_profile` present 53/218、`run_len_median=1`、`n_episodes=21`（最碎）；男近 present 120/116、n_episodes 6（最稳）。→ 女近最高 = **柜面最断续**（几何/遮挡）× **指标计重入**，不是"偶发"，也不宜简单归因柜位几何。
- **悬空引用**：`ab/summary.md:20` 与 `c1_ab_metrics.py:203` 写"见 flicker_analysis.json"，但**本证据目录内无此文件**（唯一副本在 `2026-10-09_b2a_shadow_r1/`）→ 可追溯性 FAIL。

## 5. 推理耗时（无计时数据）是否 PASS 阻断 — **PASS（仅注释，不阻断）**

- 硬门是 `cl.n < 500` 的 O(1) 前置（`b2a_shadow_probe_v2.js:117-127`），**只减少** RF 调用、绝不新增调用路径 → "不劣化"可由结构证明，无需墙钟。
- 但 `ab/summary.md:20` 的 `324/(902+324)≈26%` 与 `js_p/py_p<0.05` 只是定性；`cluster_dataset.jsonl` 实测 `max|js_p−py_p| = 0.0500`（恰在阈值边界，非"<0.05"）。→ **记一条 ms/帧与搬运 float32 误差上限即可**，不影响 PASS。

---

## 6. 附加发现（prompt 未列，审计必报）

| # | 发现 | 证据锚 | 级别 |
|---|---|---|---|
| A1 | `mf_v2/` 为空目录，无产物/无 README，置于证据根 | `2026-10-09_c1_dynamic_stabilization/mf_v2/`（0 文件） | 悬置交付，需说明 |
| A2 | 全数据零动态真值；C1 名义"dynamic"无对应 GT | `label_audit/report.json` `ai_labels_rows[*].person_xy_span_m` | 结构性 |
| A3 | v2 唯一采纳机制=硬门；重训 RF-v2 召回差，两者混淆于同一 SUMMARY | `rf_v2/SUMMARY.md:3-11` vs `ab/summary.md:4-13` | 表述风险 |
| A4 | `detect_overlay.js` 工作树为 M（未提交），但 SHA 与审计锚点一致；C1 A/B 用 `workspace/` 副本，未改生产 | `git status`；`b2a_shadow_probe_v2.js:1-5` | 澄清：非 C1 引入 |
| A5 | 命中率锚点全绿（13/13） | `label_audit/report.md:1-20` | PASS |

---

## 7. 最终裁定：C1 → C2 = **NO**

**主拒绝理由（≈300 字）**：C1 的核心交付是一个离线硬门候选，但支撑其"可放行"的统计主张均不成立。其一，`gate_confidence.md` 的 Wilson CI 建立在 915 条**同人同站位逐帧**样本上，属伪重复；按段重算下界仅 ≈0.61，且硬门已丢弃 1 个真实 person 簇（n=33），却仍宣称"人全都通过"。其二，泄漏审计方向相反——去掉 n_pts 反使 noperson 召回上涨，"n_pts 是主泄漏"被自身数字证伪，单次 3 维消融且帧/簇域混合，无法定论。其三，六段 person 全部静止（xy 跨度 0.03–0.06 m），"动态真人召回 100%"是无真值的不可测主张；`v_airoi=100%` 更因用 GT-ROI 喂检测器而循环。其四，`flicker_analysis.json` 为悬空引用，`mf_v2/` 空目录。硬门本身作为保守预过滤有价值，但**带上述过度主张、无动态与跨域验证证据**，不应据此进入 C2。

**放行所需最小补件（非阻断项以外的门槛）**：
1. 硬门按**会话**（n=6）或跨站位重算 Wilson，并做留出/远距-遮挡扫描；
2. 泄漏审计改为**簇级单域** + 逐特征消融，给出多 slice；
3. 采集至少一段真实动态（walk/起落）会话作 GT；
4. 补齐/移入 `flicker_analysis.json`，处置 `mf_v2/`，`furniture_tracks` 更名 `furniture_reentry_episodes`。

**若允许降级放行**（缓支持理）：可仅将 `n_pts≥500` 作为**未经泛化验证的预过滤**并入 C2 草案，同时冻结上述四项为 C2 验收前提；但那等于承认 C1 的统计结论为空，故本裁定仍取 **NO**。
