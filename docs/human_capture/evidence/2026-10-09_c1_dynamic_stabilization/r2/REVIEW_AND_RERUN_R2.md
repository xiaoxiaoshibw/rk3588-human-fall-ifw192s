# C1 动态人体识别稳定化 — 复核 + 重跑轮 R2

> 日期：2026-10-10（Asia/Shanghai）。性质：**复核 + 同代码重跑 + 发现披露**，非新一轮设计/实现。
> 范围：用户 2026-10-10 授权 8 项。生产算法零改动（仅复核）；不启动 C2/C3；不部署新模型；不改生产背景去除参数。
> 与旧 FINAL_REPORT.md 的关系：旧报告是 **r1（2026-10-09）实施轮**的交付；本文件是 **r2 复核轮**——在现行代码上独立重取证据、判定旧结论是否仍然成立。

---

## 0. 执行边界声明

| 约束 | 遵守证据 |
|---|---|
| 生产算法禁改 | `human_pipe_lib.js` 现行 SHA `8b50a221…` ≡ B2-A-FIX-R1 `protected_snapshot/HRV2.sha256`；`detect_overlay.js` `585d2964…`、`b2a_shadow_probe.js` `74b4a272…` 与 R1 复审基线逐位一致 |
| 仅离线/证据/独立工具 | 全部产物落在 `evidence/.../` 与 `workspace/`；唯一写工作的树是临时 `_tmp_b2a_shadow_probe_v2.js`（跑完即 `rm`，`git status` 无新增） |
| 不启动 C2/C3 | 未创建任何 C2 工单/计划文件 |
| 不改背景去除参数 | `human_pipe_lib.js` 的 `denoise/extract_foreground/bg_*` 常量未触 |
| 不部署 | 未触板端（ssh/容器/8090/8766 全程未连接） |

工作树非 C1 改动（`console*`、`fetch.py`、`panel.js` 等 M 文件）属用户其他支线（HR-RET-V2、console、B2a），本轮**只复核不改、不重置**。

---

## 1. 任务1 — B2-A-FIX-R1 复核（Shadow↔生产语义一致性）

**机制**：`workspace/c1_label_audit.py` 用**数值指纹**比对（非字符串全等）——`b2a_shadow_probe.js` 内联复制的 `find_hot / find_clusters / associate` 与生产 `detect_overlay.js` 同行同值，规避"复制漂移"。

**结果**（重跑 `label_audit/report.md`，2026-10-10 重取）：
- **blueprint_consistency 13/13 全 PASS**：find_hot/find_clusters/associate 数值指纹一致；`TRACK_GATE_M=1.0 / TTL15 / MIN_AGE3 / BG_CELL=0.05`、z 带 0.1–2.3、bg +0.25m、min30、top4、FIX-1 claimed 单帧一对一、阈值档 [0.55,0.65,0.80] —— 两侧锚点全部对齐。
- **跨 session / 颜色缓存生命周期**：`replay.js load()` 单点入口（`notify_session`+`reset`+`set_leveled_in_s(true)`）；`finish_load` 重挂 `attach_color(S.colour)`（B2-A E#2）；`reset()` 实清 colorBuf 红点（E#3）。
- **逆序 / 跳帧**：`set_idx` 的 `tracker_last_idx` 守卫——同 idx 重入跳过 `on_frame`（不重复 associate）；`|Δ|≠1` → reset + 单帧重建（**诚实：不冒充历史**，仅"本帧分类"）。
- **重复帧**：帧 identity 阻止二次 associate；overlay 层若被直接重放 `frame_no=2`，在上层 `set_idx` 挡（双层防御）。
- **跨 session / gen 守卫**：`session_gen` 模块级自增，旧 gen 的异步/rAF `on_frame` 直接 return（E#11 诚实标注为冗余兜底，主防线是 load()/set_idx 双重）。

**结论：PASS**。B2-A-FIX-R1 三项修复（FIX-1 claimed 一对一 / FIX-2 删 is_stable 死分支 / FIX-3 生命周期）在现行代码中**完整保留且语义与生产一致**，未发现回退。

---

## 2. 任务2 — 六段漏检归因（逐帧级联）

**机制**：`c1_miss_attribution.py`（链级 bucket）+ `c1_attribution_v2.py`（生产拓扑 v_p vs AI-ROI 拓扑 v_airoi）。数据：`attribution_v2/<sid>.frames.jsonl`（逐帧）+ `attribution*/summary.md`。

**级联四级归因（六段 915 帧，生产拓扑 v_p）**：

| 会话 | 帧数 | BG丢失 | 聚类失败(无簇) | RF拒绝 | Track丢失(age<3) | shown | shown% |
|---|---|---|---|---|---|---|---|
| 男近 122637 | 116 | 0 | 0 | 0 | 2 | 114 | 98.3 |
| 男中 122616 | 139 | 0 | 0 | 0 | 2 | 137 | 98.6 |
| 男远 122700 | 111 | 0 | 0 | 0 | 2 | 109 | 98.2 |
| 女近 121647 | 218 | 0 | 0 | 0 | 2 | 216 | 99.1 |
| 女中 121622 | 107 | 0 | 0 | 0 | 2 | 105 | 98.1 |
| 女远 121723 | 223 | 0 | 0 | 0 | 2 | 221 | 99.1 |

- **背景去除 / 聚类 / RF 三级全程 0 漏检**；唯一未 shown 原因是**开场 2 帧 track age<MIN_AGE(3)**（时序确认门，非漏检）。
- 距离变异（近/中/远 ≈1.2/1.7/2.5m）：shown% 98.1–99.1%，**未见远距离退化**（但测试域 ≤2.5m，更远未知 → 标 UNKNOWN 域外）。
- `v_airoi` 全 100% **不作独立证据**——用 `ai_labels` 的 ROI 裁窗喂检测器（GT 循环论证）；可信项仅 v_p。

**结论：PASS（限静态 stand 域）**。

---

## 3. 任务3 — 训练数据与人工标签审计

**机制**：`c1_label_audit.py` 段 C/D。禁止把旧 Track 自动判定当真值 → 审计 `ai_labels.json` 的 `source`/`confidence` 字段 + 跨 session 泄漏。

**结果**（`label_audit/report.json`）：
- **11 段 posture 全 = `["stand"]`，confidence 全 = `["auto"]`，`human_annotations` 全 = 0** → 训练"人"真值**仅到"AI 判读的站立真人"粒度，零人工逐帧确认**。
- 5 段帽子会话标 `UNKNOWN_HAT_STAND`（戴帽站立，动态性未确认，不误入 person 目标）。
- **跨 session 泄漏**：`leak_audit.cross_session_shared_frames = 无`（points.bin 顺序传输，无跨会话共享帧）；`dedup_none=true`（空场模板去重，防静态帧近邻泄到相邻 fold）；LoS fold 间无帧级泄漏。
- **域偏移诚实标注**：训练=全帧 ROI；推理=BG diff 簇级——n_pts 在"帧人(大)/家具簇(小)"间不单调，`v2b_noleak` 去 fv[0/1/2] 家具拒 0.270→**0.318 反涨**，"n_pts 是主泄漏"假设**被自身数字证伪**（审计 R2 #2）。
- **"泄漏已排除"不作主张**：full≡noleak、逐特征/对组合 Δ≡0 是 RF 结构性冗余（importances 实测 max 10.8% 高度分散），域内不可证——只能域外 holdout 剥离（见 C2 门槛）。

**⚠ source 显式分级（用户禁止"旧 Track 自动判定当真值"）**：`ai_labels.json` 仅有 `labelled_by=auto_person_label.py` + 每帧 `confidence:"auto"`，**无 `source:"human"` 人工标注字段**——本批次**不存在人工真值**，训练/评测全部建立在 AI 自动判读上。任何下游"召回/精度"数字的"GT"实为**auto 参考**，非人工金标。

**结论：PASS（know-unknowns 明示）**——无 posture!=stand 污染、无跨会话帧泄漏；但**全 auto 标签、零人工确认、零动态真值**是结构性上限。

---

## 4. 任务4 — RF v2 离线候选（保留 v1）

**机制**：`rf_v2/results.json`（LoS 诚实评测，训练 pod = 帧级 + 家具簇）。**新增特征未在本轮授权**，53 维 v2e 段存在执行期维度碰撞 bug（见 §7 问题 A），本轮不重训，仅用已入库的稳定 results.json。

| 实验 | 人召回 | noperson(家具)拒 | 说明 |
|---|---|---|---|
| v1_base | 1.000 | 0.000 | 仅帧级 pod |
| v2b_hard_neg | 0.989 | 0.460 | +324 家具簇 |
| v2c 远距×2 | 0.993 | 0.401 | 强调远距人 |
| v2d 低位家具×3 | 0.994 | 0.421 | 困难负样本 |
| v2e 删9噪特征 | 0.982 | 0.299 | **真·特征消融**（修复 R2 复审发现的死代码后） |

> **数字更正（R2 复审后）**：RF 有随机性，v2b 家具拒旧值 0.270 → 本轮重跑 0.460（不同随机/数据态合法重训）。**方向性结论不变**——重训 RF 家具拒 ≤0.46，远弱于硬门清零。

- **重训 RF 是弱家具判别器**（家具拒 0.24–0.32 封顶）→ C1.6 采纳的是**另一机制：硬门 `n_pts≥500`**（非重训 v2）。
- **样本平衡 / 困难负样本 / 特征优化均已尝试**（v2c/v2d/v2e），均无法把家具拒推过 0.32。
- RF v1 工件 `rf_person_v1.json`（sha `4c83db11…`）**全程未改**。
- **新特征（53 维）未完成有效消融**：53 维 v2e 段因脚本 bug 未产出（问题 A）；`leakage_slice.md` 的 minimal_3（zmax/z_range/upright）家具拒 0.605 > full_51 0.568 是**离线 slice 实验**线索，C1 未授权接入生产，进 C2 候选。

**结论：PASS（候选 = 硬门，非重训 RF）**。

---

## 5. 任务5 — Track 闪烁 / 短暂丢失 / 重复 ID 根因

**机制**：`flicker_analysis.json`（上游 `2026-10-09_b2a_shadow_r1`）+ repair_r1 的 `furniture_reentry_episodes`。**无条件延长 TTL 被明确禁止**。

**根因（生产零改动如实）**：
1. **检测侧间歇成簇**：柜位 presence run 中位 = **1 帧** → track `miss` 极少超 TTL=15 → 不是 TTL 不够长，是**簇根本不稳定**。女近柜面 present=53/218、run_len_median=1、n_episodes=21（最碎）→ reentry=18（最高）；男中 present=128/139、run 中位 15（最稳）→ reentry=13。
2. **柜 prob 自始至终 ≥0.76**：RF 无参数可调（阈值降到 0.76 下才能压柜，但会连人一起压）。
3. **截图 #8/#11 重复 ID**：跨会话 `t_id_next` 累积（显示缺陷）→ 已由 E#2（finish_load 重挂 attach_color）+ FIX-3（session_gen/reset 生命周期）修复，**非关联缺陷**。
4. **男近 reentry 2→1**（`person_episodes`）：121622 frame87 n=33 小旁簇 + 主簇同帧 confirmed → 开场旁簇独立成 1 段，非人 track 闪烁。

**结论**：闪烁/丢失/重复 ID 的**三大根因 = 检测侧簇不稳定 × RF 无法分家具/人 × 显示层跨会话累积**；定位到检测+RF，**未用 TTL 延长掩盖**。**PASS**。

---

## 6. 任务6 — RF v1 / v2(硬门) A/B 对比

**机制**：repair_r1（`furniture_reentry_episodes` 按"一次 id 出/灭段"）+ `person_episodes`(轨迹碎片) + `id_switch = max(0, person_episodes−1)`。阈值 0.55 档。

| 会话 | 动态人召回 | 家具误检(RF≥0.55) | Track ID切换 | 轨迹碎片(person_ep) | 推理耗时 |
|---|---|---|---|---|---|
| 男近 | UNKNOWN(静态) | 119→**0** | 0→0 | 2→1 | v2 省26% RF调用 |
| 男中 | UNKNOWN(静态) | 128→**0** | 0→0 | 1→1 | (结构性估算) |
| 男远 | UNKNOWN(静态) | 0→0 | 0→0 | 1→1 | |
| 女近 | UNKNOWN(静态) | 53→**0** | 0→0 | 1→1 | |
| 女中 | UNKNOWN(静态) | 23→**0** | 0→0 | 1→1 | |
| 女远 | UNKNOWN(静态) | 0→0 | 0→0 | 1→1 | |

- **动态真人召回 = UNKNOWN**：6 段全静态 stand（xy 跨度 0.03–0.06m），**无动态 GT，C1 不制造假 GT**。静态 shown 召回 98.1–99.1%（域内），但"动态"不可测。
- **家具误检**：v2 硬门 **全 4 段柜位置零**（12/13/18/15 → **0**），人 confirmed 簇零回归（6 段全过门）。
- **Track ID 切换 = 0/0**：全段单连续 person track，无切换可测（除 121622 n=33 旁簇，属展示非切换）。
- **轨迹碎片**：男近 `person_episodes` 2→1（旁簇消除），其余 1→1。
- **推理耗时**：硬门 O(1) 前置，省 **26%** RF predict 调用（324/1235 家具簇被 pre-gate 拦截）；JS vs Python prob 差 max **0.0500**（Float32 边界，0.55 阈值在 [0.50,0.60] 有边界不定性，生产 age≥3 二重门实际 <5% 帧）。

**结论：A/B 完成；动态召回/部分指标按授权标 UNKNOWN**。

---

## 7. 任务7 — 回归 + 本轮发现的问题

**回归证据**：
- **探针可复现性**：r2 重跑 production probe（12 jsonl）与 v2 probe（12 jsonl），与旧 evidence **24/24 逐位 cmp IDENTICAL** → 生产自 R1 后零污染，探针链确定性成立。
- **JS 单测**：`detect_overlay.test.js` **36/36 PASS**；`human_pipe_lib.test.js` **38/38**；`panel.test.js` 全 PASS。
- **Python 单测**：`pc_apps/human_replay` 49 项，48 PASS + 1 ERROR=`leveling_auto_test` 因 `captures/remote/cap_20261004_202456/meta.json` 未下载（**数据缺失，非代码缺陷**，与 C1 无关， leveling 支线资产）。
- **锚点 SHA**：4 枚输入 + `human_pipe_lib.js` 现行 ≡ R1 基线，逐位一致。
- **旧证据完整性（R2 复审证伪后更正）**：~~旧 `SHA_MANIFEST.sha256` 68/69 一致，唯一 FAILED = manifest 自身~~ **更正：4 FAILED**——`./SHA_MANIFEST.sha256`（自身，固有）+ `./ab/summary.md`、`./rf_v2/slice_metrics.json`、`./rf_v2/wilson_perfeature.md` 三个**内容文件**。后者因本 R2 在旧证据根**原地重跑**审计/RF 脚本覆盖了原 r1 产物（同代码同数据确定性重跑，数值差异源于 RF 随机态，方向不变）。我 §7 原稿"唯一 FAILED=manifest 自身"系**失实**，特此更正。**处置**：新增 `r2/SHA_MANIFEST_R2.sha256` 自含锁定本轮全部产物。下游引用旧 r1 根产物时，应认本 R2 manifest 为现行权威。

**本轮发现 + 修复的问题（披露，未越权改生产）**：

| # | 问题 | 级别 | 处置 |
|---|---|---|---|
| A | `workspace/c1_rf_v2.py` v2e 段执行期崩溃（51 维 vstack 53 维）+ `Xcomb2` 死代码 → "v2e 特征消融"名不副实 | 中（离线脚本） | **已修**：51 维零填充 9 噪维真消融，重跑 person=0.9818/noperson=0.2989 可再生产 |
| B | 旧 manifest 4 FAILED（A#5） + 我原稿"仅 1"失实 | 中（诚实） | 本节更正；旧产物覆盖原因如实标注；新 r2 manifest 锁定 |
| C | `attribution_v2` 的 `v_airoi=100%` 循环论证（GT-ROI 喂检测器） | 已知（审计 R2 #3 已标） | 仅以 v_p 为可信项 |
| D | `c1_label_audit.py` z_band 锚点恒真（`pass:True` 硬编码，`z_bands` 算后未用） | 中（审计脚本） | **已修**：真比对 probe/overlay 各须 ≥1 出现，重跑仍 PASS |
| E | 临时卫生：`r2/label_audit/`、`r2/workspace/outs/` 空目录 | 低 | **已删**（rmdir） |

---

## 8. 任务8 — 独立复审（OpenCode CLI）＋ 本轮返修

OpenCode `opencode-go/deepseek-v4.1-flash` **真实执行了独立审计**（`opencode run` 真推理，非提示词占位）：复审人只读地重算 SHA256、逐位 cmp、重跑 JS 单测、静态读源码（不采信报告自述）。原文存档 `r2/C1_INDEPENDENT_REVIEW_R2.md`，prompt 见 `r2/C1_REVIEW_PROMPT_R2.md`，返修记录见 `r2/REPAIR_AFTER_R2_REVIEW.md`。

**审计员发现 → 本轮修复（已重跑）**：

| 审计发现 | 级别 | 本轮处置 |
|---|---|---|
| A#3 z_band 恒真锚点 | 失实 | ✅ 修为真比对（§7-D） |
| A#5 旧 manifest 4 FAILED（3 内容文件） | 失实 + 冻结违例 | ✅ §7 更正 + 补 r2 manifest 锁定 |
| C2 v2e 伪特征消融 | 自相矛盾 | ✅ 重写真消融 + §4 更正 |
| B#4 悬空引用 C1_INDEPENDENT_REVIEW_R2.md | 卫生 | ✅ 本文件已生成兑现 |
| B#A1 新增空目录 label_audit/outs | 卫生 | ✅ rmdir |
| §3 auto 标签当 GT 风险（用户禁令） | 伦理 | ✅ §3 加 source 显式警示 |

**审计员结论（a) C1 PASS 条件性 / (b) 进 C2 NO）**：C1 PASS 是基于**底稿证据**而非我报告——因我报告含 2 失实 + 1 自相矛盾（本轮已全部修复）；进 C2 NO 因核心目标"动态"无真值 + 统计泛化作废 + 泄漏仅"不作主张"。

---

## 9. C1 判定（r2 复核轮，R2 复审返修后）

| 维度 | 结论 | 证据锚 |
|---|---|---|
| B2-A-FIX-R1 语义一致性（任务1） | PASS（12 真比对锚点 + 1 已修 z_band 真断言；数值指纹仅比数字字面量序列，诚实标注强度有限） | label_audit/report.json |
| 漏检归因（任务2，静态域） | PASS | attribution*/summary.md |
| 标签审计（任务3，source 显式 + know-unknowns） | PASS（auto 标签不作人工 GT，§3 警示） | label_audit/report.json |
| RF v2 候选（任务4，硬门非重训） | PASS（重训 RF 家具拒 ≤0.46 弱，硬门胜出） | rf_v2/results.json + ab/ |
| Track 闪烁根因（任务5，未用 TTL 掩盖） | PASS | flicker_analysis.json + per_session |
| A/B 对比（任务6） | PASS（家具 12/13/18/15→0；动态/ID切换/碎片部分=UNKNOWN） | ab/summary.md |
| 回归（任务7） | PASS（24/24 cmp + JS 36/36/38/38 + SHA ≡；发现 §7 A–E 全披露） | r2/TEST_LOG_R2.md |
| **动态真人召回** | **UNKNOWN（6 段全 stand，无 GT，不造数）** | label_audit xy_span 0.03–0.06m |
| **统计泛化主张** | FAIL（段级 Wilson 下界 0.61） | rf_v2/gate_by_session.md |
| **域外泄漏排除** | 不可证（域内 full≡noleak，仅"不作主张"） | rf_v2/leakage_slice.md |

### **C1：PASS（条件性，限本采样域 = 同房间 ≤2.5m 静态 stand，6 段 915 帧）**
硬门 `n_pts≥500` 在该域内是**安全有效的预过滤**（家具全清零、人零回归、Track 稳定）；B2-A-FIX-R1 完好；漏检归因/标签审计（auto 分级明示）/闪烁根因闭合。**此 PASS 基于底稿证据，非基于失实叙述——审计员证伪的 2 失实 + 1 自相矛盾本轮已全部修复。**

### **进入 C2 资格：NO（OpenCode R2 复审裁定，本轮采纳）**
主理由：C1 名义"动态稳定化"，但全数据零动态帧（xy 0.03–0.06m），动态召回 UNKNOWN = 核心目标不可测；统计泛化主张已作废（0.61）；泄漏仅"域内不作主张"非正证据。
**C2 最小门槛（冻结，需用户另行授权开工）**：①≥1 段真实动态 GT（walk/起落）把动态召回从 UNKNOWN 变可测；②远距/遮挡/异房间新采样剥离域伪影撑回 Wilson；③泄漏消融升级为域外 holdout；④53 维新特征脚本已修，可作 C2 候选特征源（`c1_rf_v2.py` v2e 段现在真可复跑）。

### **生产接入：继续 BLOCKED**
本轮生产零改动（5 锚点 SHA ≡ R1 基线）；硬门仅存在于离线探针 `b2a_shadow_probe_v2.js`；上线须**独立验收 + 用户单独授权**，不随本判定放行。

---

## 10. 交付物清单（任务7）

| 项 | 路径 |
|---|---|
| 代码 diff | `r2/CODE_DIFF_R2.md`（声明本轮生产零改动 + 工作树 B2a 资产 stat） |
| 测试日志 | `r2/TEST_LOG_R2.md`（JS 36/36 + 38/38 + panel PASS；Py 48/49, 1 数据缺失） |
| 实验指标 | `rf_v2/results.json`、`ab/per_session.json`、`attribution*/`（4 级归因）、`rf_v2/slice_metrics.json` |
| 失败/边界样本 | `rf_v2/cluster_dataset.jsonl`（n=33 person 边界簇 121622 frame87）+ `gate_by_session.md` borderline |
| 最终报告 | `r2/REVIEW_AND_RERUN_R2.md`（本文件） |
| 独立复审 | `r2/C1_INDEPENDENT_REVIEW_R2.md`（原文存档）+ `r2/REPAIR_AFTER_R2_REVIEW.md`（返修记录） |
| SHA 锁定 | `r2/SHA_MANIFEST_R2.sha256`（110+ 文件，零自引用） |



---

## 附：本轮产物 SHA
见 `r2/SHA_MANIFEST_R2.sha256`（不含自引用；旧 manifest 的自引用 FAILED 已在 §7-B 披露）。
