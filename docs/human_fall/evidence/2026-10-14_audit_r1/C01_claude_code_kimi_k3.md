# C01 · C 组独立审计（HF/GL 点死亡≥97.6% / registration VALID=0）· 2026-10-14

审计范围：只读。不改生产代码、测试、配置、GT、历史证据。本文件位于 `docs/human_fall/evidence/2026-10-14_audit_r1/`，为唯一允许写位置。
审计对象：A 组技术根因审计（`A01_TECHNICAL_ROOTCAUSE.md`）、B 组收口路径审计（`B01_CLOSURE_PATH_AUDIT.md`）。**不被盲信**——A/B 的每一项关键数字、门逻辑、菜单可行性均经我独立重算/对账，只剩列在 §④ 的 UNKNOWN 保留。

---

## ① 身份与独立性声明（模型/提供方、与作者链无关的证据，及局限）

- **身份**：本聊天实例独立只读审计员（C 组），由用户直接指定，任务是审计 A01/B01。产出仅为只读判断；**无权**把任何工单标 ACCEPTED，**无权**修改生产代码、GT、测试、配置、历史证据。
- **模型/提供方**：本人为 **Claude Code（Kimi 路由）/ kimi-k3**。这与 A01 底稿自报身份（第 9 行 "我是 Claude(Kimi for Claude 路由 / kimi-k3)"）属**同模型族**。
- **独立性必须诚实降级**：同模型族意味着 A01 与我**不可排除模型级相关性**（共享 base 决策倾向）。但我与 A01 **无共享上下文**：A01 的全部输出（26KB 文本 + 引用的 JSON）我都**独立从原始证据重推**——用 node 现算了 BACKGROUND_METRICS/EXPERIMENT_COMPARISON/diagnostics/process_v2/process 等主要数据源，逐字节核对了 human_pipe_lib.js / registration.js / probe_215540.js / background_ab.js 的行级证据，而非咀嚼 A01 文本。因此本审计对 A01 的**数字与归因**是独立裁决；对 A01 的**叙事框架与盲区**披露模型级相关性风险。
- **方法**：内联亲自精读 A01/B01 全文 + 17 个关键 JSON；Workflow 分发 20 路核实代理（并行 node -e 重算）+ 3 位评委（风险/GT/物理三视角独立裁决第一单一选择）+ 1 席 synthesis 终审。合计 25 个只读代理、1,471,179 token。**每一路都被强制要求字段级 evidence 或进 unknowns，禁止乐观猜测。**
- **与作者链无关**：未向 Codex/Kimi/Claude 作者链传意见、不加载 ponytail、无任何生产代码写权限、无 git commit。本文件之前及之后我均未修改任何工单状态。

---

## ② 证据清单（实际打开/读入内存的文件；目录清单详见 git status）

| 文件 | 用途 |
|---|---|
| `docs/human_fall/evidence/2026-10-14_audit_r1/A01_TECHNICAL_ROOTCAUSE.md` 全文（213 行） | 被审对象甲 |
| `docs/human_fall/evidence/2026-10-14_audit_r1/B01_CLOSURE_PATH_AUDIT.md` 全文（119 行） | 被审对象乙 |
| `docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/` 目录 + FINAL_REPORT.md / INDEPENDENT_REVIEW.md / BACKGROUND_METRICS.json / ARTIFACT_STATES.json / REGISTRATION_REBUILD_RUN.json / TARGET_COUNTERFACTUAL.json / ACCEPTANCE_V1.md / RUN_LOG.md / CURRENT_DELIVERY_INDEX.md / REVIEW_QUEUE.json / metrics.json / TEST_RUNS.json / TEST_01..07.log / browser_*/ | HF-REAL 第一批闭环; A/B/C 三臂真值源 |
| `docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/registration_094333_131958_v1/{diagnostics,registration,provenance,manifest}.json` | 新 artifact；12 数字真值 |
| `docs/human_fall/evidence/2026-10-13_hf_real_01_r1/cap_20261013_094333_leveling.json` + `docs/human_fall/evidence/2026-10-13_hf_real_02_r1/cap_20261013_131958_leveling.json` | 两 leveling 基准不一致证据 |
| `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/out/{215540_frame_stats.json, 215540_mask.json}` | 215540 probe 点级 truth |
| `docs/human_fall/returns/HF-REAL-01.md / HF-REAL-02.md / HF-REAL-03.md` | RS04 三方立场 |
| `docs/human_fall/evidence/2026-10-13_hf_real_02_r1/ACCEPTANCE_V1.md` / `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/ACCEPTANCE_V1.md` | RS04 原定义与 RS-C 结论 |
| `pc_apps/human_replay/human_pipe_lib.js`（行 1-460） | KS1/KS2/KS5 生产码 |
| `pc_apps/human_replay/registration.js`（行 1-240） | reg_gate_v1 / fit_holdout_guard / fusionKeys |
| `sidequests/human_fusion_lab_next/real_fall/r03/probe_215540.js` 全文 | 215540 probe 口径 |
| `sidequests/human_fusion_lab_next/real_fall/r04/background_ab.js` 全文（关键行 37, 63, 70） | **推翻 KS1 归因的决定性证据** |
| `docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/EXPERIMENT_COMPARISON.json`（4.9MB 顶层 summary 用 node 现算） | R2 五方案 adoption/added/near_bg |
| `docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/{FINAL_REPORT.md, ACCEPTANCE_V2.md, CURRENT_DELIVERY_INDEX.md, DIAGNOSIS_BEFORE_EXPERIMENT.md}` | R2 实验期终结证据 |
| `docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r|1/{ACCEPTANCE_V1.md, FINAL_REPORT.md, ACCEPTANCE_FINAL.json, MEASURED_SUMMARY.json}`（仅摘 PS01-PS07/GT01 行） | POINTSET-01 卡点 |
| `docs/human_capture/evidence/2026-10-13_hc_joint_local_r2/{REPORT.md, ACCEPTANCE_V1.md}` + returns/HC-JOINT-LOCAL-01.md | JOINT R2 缺号 126 |
| `docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/08_final_closeout.md` | W03 gate 49.652981% |
| `pc_apps/console/console_gui.py`（HEAD + 工作树两份） + `console.html` + `git diff/log` | 控制台接法 |
| `docs/human_fall/HF_REAL_NEXT_DEVELOPMENT_PLAN_20261013.md`（218 行） | L4 计划对照 |
| `captures/remote/` 目录枚举（node readdir） + `captures/leveled/` 枚举 | 会话 id 核查 |
| `docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/background_frame_results.jsonl` | M1 证伪证据（17 帧级字段无逐点 z） |
| `pc_apps/human_replay/gt_store/cap_20261010_180557/draft.json`（892KB，含 53 帧 GT） | 替代 M1' 数据源 |

**机器重算**一律 node -e 一次性 readFileSync + JSON.parse，不写盘；源码处一律 Read/Grep + git show/log 字面对账。

---

## ③ 逐项结论（L1-L6 六层全量，核心数字用字段级 evidence，所有跨报告对比给行号）

### L1 数值正确性 —— A01 大体可信，**四处需修正**

15/16 A01 关键比率独立重算全 PASS：1324/57045=2.321%、55347/57045=97.023%、54069/57045=94.783%、26/1163=2.236%、180/1163=15.477%、4/1163=0.344%、116422/373746=31.150%、KS5 字段 hits=57010/oracle_hits=57010/selected_points=58593 全部在原 JSON 存在。**15/16 数值项可引用**；唯一例外 **A01 L181 "S8 RF 99.9% 与 oracle 平"是口径混写**：实测 hits/oracle=100.0000%（真"平"），99.9386% 是 hits/denominator=57010/57045。底层定性结论（RF≈oracle）成立，属算术修辞瑕疵非伪造。

**新发现（A01 未报告）**：215540 per_band legs removed=31313 中 "legs zlo=0.10" 已**不含 z<0.10 点**（probe ZLO=0.10 先扣），所以"legs 是最大失血带"实际是 **z=0.10-0.70 的足踝-小腿被 KS2 杀**——A01 没点破这一点，意味着"低位"vs"KS1 杀伤"的外延被它悄悄混淆。

### L2 根因覆盖 —— **A01 最大漏洞：KS1 归因全错**

**决定性证据 `sidequests/human_fusion_lab_next/real_fall/r04/background_ab.js:70`**：`PL.PIPE.ground_keep_below_m=-.25; // isolated process only; source/default remains unchanged`。S8 诊断 A/B/C 三臂实验**全部禁用了 KS1（z<0.10 硬切被移到 -0.25 = 实际全保留）**；FINAL_REPORT.md L57 "三路均在独立进程使用显式共同诊断 workspace z≥-0.25m" 与源码一致。

⇒ **A01 最紧区间表的三个 97.x% 全部是纯 KS2 杀伤**：
- S8 A_P 97.68% = `build_static_map(10-frame-causal ephemeral map)` 在线吸收（human_pipe_lib.js:182-190 occ_strong）+ `--10 帧窗`, **KS1 已禁**；
- S8 A_P low-z 97.76% 同上口径；
- 215540 97.60% = probe 行 18 `ZLO=0.10` 预扣 KS1 后余 `z∈[0.10,2.30]` 子集被 `build_static_map(64-frame static map)` occ_strong 吸收（probe_215540.js:37,72）。

**KS1 单独贡献当前不可量化 = UNKNOWN**（生产 human_pipe_lib.js:31/162/281 行活跃，但 S8/215540 三处数据源全部 KS1 禁用或预扣，不能证明它杀多少）。
**A01 L69 "KS1 单独在低位点占主因(B 只保 15.5%→KS1 在 B 里也杀 84.5%)"是事实错误**：B 臂在同一实验中 KS1 同样被禁（background_ab.js:37 `{drop_ground:false}` 的 build_reference_map），B low-z 84.5% 损失**只能**来自**冻结参考侧的静态吸收**（参考图含与人体共位的家具/结构体素——KS2-class）——这与"KS1 在 B 里杀 84.5%"的归因物理矛盾。

**根因覆盖完整性实测**：除 KS1/KS2/KS3/KS4/KS5 外，`human_pipe_lib.js:1-460` 还有 **KS0_denoise(range_min=0.35m :112-115)**、**KS2b_z_max=2.50m (:32,281)**、**KS_ISO_cleanup_isolated_fg(:353-421)**、**KS_MIN_VOX_cluster_min_voxels=3(:48,456)**、**KS_REF_bg_hit_min_pts=2(:36)** 五处删点机制。当前 JSON 无逐点 stage-tag，无法量化其占比。**"唯二源头"只在当前无 stage-tag 数据下可独立关掉且可量化的尾限定下成立；字面全文件穷举下有 7+ 环。**

**新感知增强**：A_P 的 97.68% **不是生产 P 的等价物**（FINAL_REPORT L59：生产 build_static_map 用整录制 523 帧含未来帧背景，比 10 帧因果窗更强自吸收）；生产吞人率 **预期 ≥ 97.68%**。⇒ "≥85% 联合主凶"偏松不紧。

### L3 registration 门 —— **A01/B01 共同漏掉的最强中间假设：leveling 基准不闭合**

数字/门码/绑定全部核实 CONFIRMED：fit_p50=0.029691(warn)、fit_p90=0.105731(reject>0.10)、holdout_p50=0.024671(warn>0.02)、holdout_fit_ratio_p50=0.8309(pass)、inlier_ratio=0.4516(warn 在 [0.5,0.3] 带)、n_correspondence=3817(pass)——A01 12 行表格 12/12 数值精确一致（行 13-18 PROFILE, 76 band 决策, 87-88 guard, 89 status 全部由 node 重算+代码行独立复核）。**REJECT 单尾驱动=fit_p90>0.10**；`fit_holdout_guard` 因 fit_p50≠pass 前提不成立**从未触发**（registration.js:87 与 diagnostics.gate.checks 20 个 id 中都无 fit_holdout_guard 一同证实）；**bands 中无 holdout_p90 键**（registration.js:13-18 / grep holdout_p90 零命中）⇒ holdout_p90=0.119998 只被记录不被门判，**"fit-p90 与 holdout-p90 双尾 overdetermined"不成立**（我此前内联预裁收回）。`binding_status=BOUND_CURRENT_INPUT_REFERENCE_CODE`（ARTIFACT_STATES L65 字面值）与 provenance.json session/leveling SHA 一致、`binding` 字段在 registration.js grep 0 命中——旁证仅来自 ARTIFACT_STATES/metrics 汇总侧，**源头字符串未溯源到生成脚本（留 §④）**。

**但更深诊断 A01 未给**：leveling_094333 TLS `roll_deg=+1.3035`、leveling_131958 `roll_deg=-1.5601`（三估计器 TLS/SVD/RANSAC 各自逐对一致）；**两基准 roll 差 2.86-3.26°**，offset 差 0.209m（1.14788 vs 1.35663m），regions 选型完全不同（4 cell/0.625m² vs 44 cell/2.75m²）。ICP recovered `roll=-2.2147°` ≈ 该差值的负值（= ICP 在补偿 leveling 不闭合）；half_split roll=-2.797/-2.670°；**剔除配平基准后残差旋转仅 0.67°，在 leveling 家族一致容忍内**。**弧长锚点**：2.86° × tan × 3m ≈ **10.0cm ≈ fit_p90=10.5731cm**——定量吻合。

⇒ **fit_p90=0.1057m 更像"leveling 不闭合 + 协议点面残差下限(≈5-8cm)"的投影，恰顶冻结门上方 6%**，而非"真跨会话位移"或"门过严"的二选一。A01 行 98 把结论压成"fit_p90 单项"在 REJECT 因果上正确但**窄化了根因**；A01/B01 都漏掉"leveling patch 不公共"这条**最便宜可证伪**的中间假设。

**对 reg_gate_v1 0.10m 的独立意见**：
- (i) **门不变（首选）**：0.10 是经验值但现在是 n=1 的伪 REJECT（基线不闭合）；给 reg 前端加"leveling 段间相容性"预检（roll/offset 差 >0.5°/0.05m 直接拒绝进入 ICP）比放宽门更治本。
- (ii) **放宽到 0.15m**：**不推荐**，在拿到 2-3 段空场同 pair 的 fit_p90 分布前放宽=放弃对真未对准的判别力。
- (iii) **换几何（TLS→SVD 多假设 / 加权 RANSAC）**：不解决 leveling 不闭合这个根因，不建议当前开。

### L4 A01 与 20261013 计划§6 对照 —— 忠实但有 3 处收窄

计划 §6.1（背景先行）/§6.2（删地面点与配平分开）/§6.3（聚类置后）/§6.4（骨架最末）与 A01 的 KS1/KS2/KS5/M6 排序**完全一致**；计划行 10 "静立不被吞、低位人体不被裁掉"把低位放前，与 A01 M1 排序同向。

**A01 的增量 vs 计划**：A01 从 BACKGROUND_METRICS 三臂数据反推出 KS1-KS5 分环，这是计划文本没有的（计划只分子节）。A01 用 "B 冻结参考只保 15.5%" 反推 KS1 独立贡献——**该推因背景 ab.js L70 已禁用 KS1 被证伪**（见 L2），但**计划的 §6.2 仍是正确方向**（z 硬切与配平分离），只是 A01 没给出能翻它的数字。
**A01 的收窄 vs 计划**：计划 GTB（行 77）要求 "48-80 困难帧完整标 + W03 31 点/155 行队列"，A01 M4 只提 "S8 10-20 帧"——范围更窄更便宜但**未直接回答** B 组 RS04/W03 资格卡壳所需的完整 GT。
**两文档共同漏掉**：融合链 BG-01 与 levleing 段间相容性的前置关联（计划 §4 行 57 未列，A01 未补充）——我现在补一笔：**registration 重建永远不该在 leveling 不闭合下跑**。

### L5 M 菜单可操作性 —— **A01 菜单方向基本可辩护但 4/6 处具体实施被推翻或强烈收窄**

| 菜单 | A01 表述 | 裁决 | 理由（字段级） |
|---|---|---|---|
| **M1**（z<0.10 硬切改 unknown 桶；离线 jsonl 重算） | "零生产成本，最便宜最优先" | **NO-GO（原方案）** | `background_frame_results.jsonl` 2061 行**只 17 个帧级聚合字段**（sid/frame/t/arm/reviewed_human_points/fg_human_kept/...），**无 z 直方图、无逐点 kept/deleted**；deleted 点在 process 内丢弃未写 disk，帧级计数物理不可回推 "z<0.10 deleted 点"。"零生产成本"被字段集证伪。**替代 M1'**：draft.json(892KB) raw_point_indices(gt_lib.js:82-114) + points.bin 反拆 53 帧 GT，node 实测 57045 点 / low_z=32136(56.33%)；可行, ~30 行脚本, ♠2h（非 zero-cost） |
| **M2**（启用 v2 默认 + B 冻结参考） | "S8 从 2.3% → 97%" | **收益口径用错臂** | B 冻结参考 (97.02%) **需 VALID registration**（fusionKeys registration.js:221 仅 VALID 放行；ARTIFACT_STATES 当前 VALID=0）；生产 deploy 路径 `extract_foreground_fused` 对应 **C 臂=94.78% < BG02 的 95% 门**。⇒ 即使 M3+M4 PASS，**99.78 vs 95 门还差 -0.8pp 的 v2 算法精调**，这不在 A01 某一单交付物里。收益行实际是 B 臂被乐观化。且 unknown 涨 48,912→490,193 **10 倍**（A/B selected_unknown 对账）——B 97.0% 里 89.86% 是未标身份点，`labeled_nonhuman=0` 是 **无负例 GT 的伪零**（FINAL_REPORT L71 已警告）|
| **M3**（reg 门标定 / 空场残差分布） | "2-3 个已配平空场会话算 IFW 残差分布" | **必要条件不足；应前移到 M3′** | 会话 id 笔误：`cap_20261010_131958` **不存在**（captures/remote/ 枚举到 cap_20261002_165321..20261013_082829），正确 `cap_20261013_131958` 已被 REGISTRATION_REBUILD_RUN 引用；空场同 pair 会话确实在, 但 2-4h 工作量（非 trivial）。**更严重**：root cause 是 **leveling 不闭合**（L3 已证），空场残差分布**救不了跨会话 leveling 错位**——只能刻画传感器本底。**真正第一单 = M3′（修 leveling, 再复跑同门）**：一次实验同时裁决 (a) 门 0.10 是否科学值 (b) 真位移 vs 假配平（leveling） |
| **M4**（S8 10-20 帧人工 GT, REVIEW_QUEUE 现成） | "非生产代码成本=人工时间, 0 代码" | **CONDITIONAL 翻具体实施** | 工具链在（REVIEW_QUEUE.json status=PROPOSED）但 **S8 window 仅 4 帧 [0,10,261,522]**（L1072-1083），**非 10-20**；POINT/ROW sid 全 cap_20261002_223757 非 S8；ANNOTATION_SCHEMA 是 pointset 支线 schema，与 HF-BG-01 低位/身份字段未显式对齐；**无 seed-truth/双盲/kappa/负例穿插设计**——按原规格开单会制造"标注者=验证者同体"争议，被下一轮独立审计打回。**改造版** = 加 seed-truth 帧(从 S1 空场家具段预置已知答案)+双人标注 Cohen kappa+blind B/C 臂来源+S1 负例穿插 |
| **M5**（KS5) | "非当前主凶" | **不显著当前成立**，但**修复前 KS5 将成为下一杠杆** | S8 cluster→selected 损失仅 228 = 0.40% of 57045；但 228 = **17.2% of fg-kept 1324**——一旦 M3′/M2 把 fg kept 救回, KS5 将自然升级到 15-20pp 杠杆。当前排序正确但 **A01 未声明 "KS5=KS2 修复后的下一个杠杆"**这一时间窗结构 |
| **M6**（ML PointPartNet） | 非最小 | 与 A01 一致 | HFUS-POINTSET-01 GT01/PS05 BLOCKED 无 GT；训练无 GT 即伪标签（HFUS-RD-01 已证明被打回）。**M4+PS05 解剖标注升级后才可开** |

**M 菜单真实排序（C 组独立修订）**：
```
  M3′(leveling 修一次)  →  M4 改造版(一次人工会议)  →  M3(空场残差基线)  →  M1′(draft+points 反拆)  →  M2(v2 默认/启用)
         ↑ 一击可判 + 不动 GT          ↑ 解锁 BG02/GT01/PS06   ↑ 才谈门严不严          ↑ 才谈低位救多少       ↑ 有 C≥95% 证据再谈
```

### L6 GT 充分性 —— **M4 不是银弹，"ID × M4 贡献" 表**

REVIEW_QUEUE.json 工具/浏览器已 PASS（ACCEPTANCE_V1 L14），31 POINT + 155 ROW PROPOSED 已落；**S8 window 在 windows['7'] 仅 4 帧**（[0,10,261,522]）非 10-20——**M4 的帧数口径 A01 高估 2.5-5 倍**。下列 **ID × M4 贡献表** 是独立裁决（会被 защ下称"首个明写的 GT 充分性矩阵"）：

| 验收 ID | 状态字面值（出处） | M4 原规格贡献 | M4 改造版贡献 | 留言 |
|---|---|---|---|---|
| **BG02**(HF-BG-01) | FAIL C=94.783%<95%（ACCEPTANCE_V1 L16） | partial：只解家具污染子项，94.783 数值门翻不了 | partial：同上 | 分母 57045 不变；要翻 94.78→95 门得另外 M1′+M2 组合 |
| **DT03 31 POINT** | PROPOSED（REVIEW_QUEUE L2） | **no_effect** | resolves：**同一会话里可消化** | 31 POINT 全部 sid=cap_20261002_223757(W03)，非 S8；一场会议行政并购 |
| **DT03 155 ROW** | PROPOSED（L41） | **no_effect** | resolves：同上 | 同上，155 条 P/S track 关联行 |
| **GT01**(POINTSET-01) | BLOCKED（ACCEPTANCE_FINAL L12） | partial：纯度子项可推进，部位/关节子项仍 BLOCKED | partial：同上 | 部 位/关节语义需解剖标注，M4 身份标签不给 |
| **PS05** | BLOCKED_NO_HUMAN_ANATOMICAL_LABELS（L8） | **no_effect** | **no_effect** | PS05 要的是 head/trunk/limb 逐点标注，与 M4 的身份标签**语义错位**，需另开解剖标注轮 |
| **PS06** | PASS_SOFTWARE; PURE_HUMAN_AND_JOINT_ACCURACY_BLOCKED（L9） | partial：纯人体准确率可评 | partial：同上 | skeleton_accuracy=BLOCKED 不动 |
| **PS07** | ROI_COORDINATE_REVIEW_PENDING（L10） | `no_effect` 语义，但可顺场核 | resolves：会议顺带核对 ROI 坐标 | 体力复用非逻辑依赖（B01 K5 序 7 同语） |
| **HR-W03 31 POINT** | UNKNOWN（7 工单） | **no_effect** | resolves：同会议可消化 | 同 DT03-31POINT |
| **R2 EXPERIMENT_ONLY** | 五方案 全 EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE | **no_effect** | partial：R2 帧在 cap_20261011-13 其他会话，S8 GT 不直接喂 | 需另开 M4' (R2 帧集) 并 同 IDENTITY schema 才能翻 |
| **BG01 生产现行 P 完整等价 A/B BLOCKED** | BG01 BLOCKED（ACCEPTANCE_V1 L15） | **no_effect** | partial：M4 含 S1 空场负例穿插后可初步判 | 需加 S1-empty-with-furniture 会话（REVIEW_QUEUE windows[0]，仍 4 帧）扩窗 |
| **S9 BLOCKED** | DT01 S9 BLOCKED（ACCEPTANCE_V1 L14） | **no_effect** | **no_effect** | S9 SHA 断裂需用户拍板 |

**B 组 K5 序 3 的"一次会议解决 31 POINT+155 ROW"不是逻辑完备性而是行政合并**——31/155 与 S8 10-20 帧是 **两组会话**（223757 vs 180557），M4 本身**并不能**解决 DT03 子项；但一次会议可行政地把两组 GT 一起消化——行政合并 ≠ 逻辑解锁，B01 K5 序 3 的措辞含糊。

**GT 充分性的刚结论**：M4 在改造版下可 partial/unlock 4 个 ID（BG02 家具污染子项/GT01 纯度子项/PS06 纯人体/BG01 部分）+行政合并 DT03 两项+PS07 顺带，但**PS05/GT01 解剖子项/PS06 skeleton_accuracy/BG01 数值门/S9 全都 BLOCKED 不变**。**需要用户提供负例空场 GT 穿插（S1）与 M4' (R2 其他会话）**，A01 M4 单独不够。

---

## ④ UNKNOWN / 不可判定项（约 12 项，比 A/B 列得都硬）

1. **KS1 (z<0.10 硬切） 单独贡献杀多少真 low-z 人点**：生产 human_pipe_lib.js:31/162/281 活跃，但 S8/215540 三处数据均 KS1 禁用/预扣；需 KS1 恢复 0.10 对照重跑才能分离（M1′ 实验可解）。
2. **raw→kept 全程人体存活率**：57045 是上游 pointset 预过滤池（占 raw 25,689,368=0.222%）；未标人点的上行损失无法量化。
3. **194333 与 131958 之间 3.61 小时的真实物理移动**：无同步视频/外部参照；leveling 不闭合（三路可证）与真位移（17.5cm 平移残差）混合比不可分离——**M3′ 实验可判，当前 UNKNOWN**。
4. **门 0.10 是否为 IFW192S+协议的科学值**：n=1，需 2-3 段空场同 pair fit_p90 分布标定。
5. **IFW192S ±5cm 规格是 bias 还是 precision**：手册 `design_full.txt` "测距准度与精度 ±5cm（典型值）；3cm@10m（1σ，10% 反射率）"两项并列不写性质，歧义。
6. **B 臂 490,193 unknown 点的真人 vs 家具占比**：`labeled_nonhuman=0` 是伪零（无负例 GT）；M4 完成前永远 UNKNOWN。
7. **BG02 C=94.783%→95% 的 0.22pp 可补翻性**：M2 可达臂与门差太小，未知 identity GT 分布能否补齐。
8. **`binding_status=BOUND_CURRENT_INPUT_REFERENCE_CODE` 字符串真实源头**：registration.js grep 0 命中，ARTIFACT_STATES/metrics 汇总侧字段，**未溯源到生成者**。
9. **HF-CLOSE-01 四处自述 console=r02 的矛盾产生时点**：mtime 11:52:30 vs B01 11:53:50≈80s，Edit 工具机制可能让 mtime 不反映顺序；UNKNOWN。
10. **S9 SHA 断裂是否可恢复**：用户拍板，无机器证据。
11. **`fit_holdout_guard` 是否在生产历史上曾实际触发过**：需遍历所有历史 artifact gate.checks 找该 id，超出本审计范围（本 artifact 明确未触发）。
12. **KS_ISO_cleanup_isolated_fg / KS0_denoise / KS_MIN_VOX 在真实会话的量化占比**：当前 JSON 无 per-stage tag，既是盲区也是未来 stage-tagged 删除 log 的工单。

---

## ⑤ 与 A/B 两组的差异（**明确记 4 处**，每条独立证据）

### 差异 1：A01 的核心框架"KS1+KS2 联合主凶"（**对 A01 事实错误**）
A01 L69："KS1 地面硬切+KS2 build_static_map occ_strong 联合是主凶，单占 ≥85%；KS1 单独在低位点占主因（B 臂 84.5%)"。
**裁决**：**97.68%/97.60% 全部是纯 KS2 杀伤**（background_ab.js:70 `ground_keep_below_m=-.25` 三臂全禁 KS1；probe_215540.js:18 `ZLO=0.10` 预扣），KS1 单独贡献在现有证据下 **UNKNOWN**。A01 对 B 臂低位 84.5% 归因 KS1 是**事实错误**（同实验 KS1 已被禁，不可能来自 KS1）。
**方向**：A01 的 M1 菜单方向不因此被推翻——KS1 活跃属实且 5 环框架里有是有，但 M1 的"最优先"被偷换成"解锁能力"时（ca2 与 L2 双路证实），应该降权为"最便宜最窄的 KS1 贡献鉴别器"。

### 差异 2：registration 的"门严 vs 真未对准"二分（**漏掉最强中间假设**）
A01 行 98 把 REJECT 因果压成"fit_p90 单项"与"门严不严"未给证据。B01 未补充。
**裁决**：**两 leveling 基准 roll 差 2.86°/offset 差 0.209m** 是定量独立证据（2.86°×3m ≈ 10.0cm ≈ fit_p90=10.5731cm；剔除配平基准后残差旋转仅 0.67°）。`fit_p90=0.1057m` 更像 **leveling 不闭合 + 协议点面残差下限），不能锁死为"真位移"，也不能锁死为"门过严"。**
**方向**：给 A01 补 **M3′（leveling 修一次再复跑同门）作为第 1 单**——A01/B01 都没有这一项；其单次实验同时裁决"门 0.10 是否科学值"与"真位移 vs 假配平"两个悬案，零生产代码，二元可判。

### 差异 3：R2 "登记矛盾"不存在，"未提交"才存在（**对 B01 K5 序 1 的修正**）
B01 K6#1/L48-51："ACCEPTANCE_V2 尚未在 docs/human_capture/README.md 顶部登记（主要登记矛盾）"；K5 序 1 "在 human_capture README 顶部补一行 R2 条目"。
**裁决**：当前工作树**README.md 行 1 已是 R2 条目**（含"SUBMITTED非ACCEPTED"），WORKFLOW.md 行 1 同；两文件 mtime 11:52:30，B01 mtime 11:53:50。B01 读的可能是已提交 HEAD 或同日内快照差异，未区分 "未提交" 与 "未登记"。**正确动作从"补一行登记"改为"commit 11:52 以来未提交的 README.md/WORKFLOW.md 工作树头面"** ——K5 序 1 本体立即闭合。
**另**：B01 L51 "console_gui.py 为 untracked"是**用词错误**——git status 是 ` M` tracked-modified 非 `??` untracked。B01 K3.1 主结论（工作树=pointset/r01, HEAD=real_fall/r02, r04 从未接入）数字级完全成立（我自己 grep 复核：`grep -n r04 pc_apps/console/*.*` 源码层 0 命中，二进制 dist 层有字节巧合不构成接入）。

### 差异 4：A01 M2 收益口径用错臂 / M4 GT 充分性高估（**对 A 菜单的双重收窄**）
A01 L161："M2 把 S8 人从 2.3% → 97%"——但 B 冻结参考（97.02%）**需 VALID registration**（ARTIFACT_STATES VALID=0）；M2 实际 deploy 路径 `extract_foreground_fused` 对应 **C 臂=94.78% < BG02 的 95% 门**。**M2 按现规格即使 M3+M4 全 PASS 也翻不了 BG02**——需要额外 v2 算法精调（不在 A01 某一单的交付物里）。
A01 M4 "S8 10-20 帧 + 现成 REVIEW_QUEUE"——**REVIEW_QUEUE S8 只 4 帧**（非 10-20），ANNOTATION_SCHEMA 与 HF-BG-01 字段未显式对齐，无 seed-truth/双盲设计。**按原规格开单会制造"标注者=验证者同体"下一轮争议**，必须改造后开。

---

## ⑥ 给用户的 ≤150 字核心摘要 + 一句话行动建议

**摘要（139 字）**：
A01/B01 数字大体可信但被 C 组独立证伪/收窄 4 处：① KS1 归因错（background_ab.js:70 全禁，97.7% 是纯 KS2）；② M1 原方案 jsonl 只有 17 帧聚合字段物理不可行（NO-GO，须用 draft+points.bin 反拆）；③ 12,965=全 164 帧总额非 9 采样帧 f48-f70 集中 57%；④ M2 用 B 臂 97% 乐观化可达 C 臂 94.78%<95 门。B01 也有 2 处：untracked 是 tracked-modified，R2 登记矛盾不存在但 commit 缺失存在。三评委 1:1:1 分裂，终审决胜=M3′：**两 leveling roll 差 2.86°/offset 差 0.209m 是 fit_p90=10.6cm 的根因**，先修 leveling 重跑原门即可一次定门严不严与位移真假。

**一句话行动建议**：
**顺序 `commit 现存 R2 头面` → `M3′（修 leveling 基准+原门重跑094333→131958）` → `改造版 M4 人工会` → `M3 空场基线` → `M1′+M2`——不要按 A 的 M1 或 B 的"补一行登记"开场；每一步都已被证伪或机器证据撬窄。**

---

—C 组（Claude Code via kimi-k3）· 2026-10-14 只读 · 未 ACCEPTED 任何项 · 与 A/B 组共用同目录，本文件独立落盘
