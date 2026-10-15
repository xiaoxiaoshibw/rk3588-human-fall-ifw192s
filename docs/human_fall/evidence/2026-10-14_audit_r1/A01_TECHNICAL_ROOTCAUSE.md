# A01 · 独立技术根因审计（HF/GL 真人链"点死亡 97.6% / registration VALID=0"）

- 审计日期： 2026-10-14
- 审计范围： 只读；不改生产代码、测试、配置、GT、旧证据。本目录（`docs/human_fall/evidence/2026-10-14_audit_r1/`）为唯一允许写位置。

## ① 审计员身份与独立性声明

- 身份： 本聊天实例独立只读审计员（A 组），与 HF-REAL-03 / HF-REAL-04 writer 链（Codex `real_fall/r03`、`real_fall/r04`； Kimi/Claude`assistant` 助手视觉 stub）无作者关联。从未也曾向作者链传递意见。
- 模型/提供方： 我是 Claude(Kimi for Claude 路由 / kimi-k3)，无 ponytail SKILL 加载、无 writer 配置。本审计不生产任何算法代码，仅重算/复用并比对已有 JSON 证据。
- 独立性声明： 以下结论均直接引用仓库内机器可读 JSON / 源码行 / 已落盘日志。凡"数值/字段名/路径" 我全部在审计时重新打开核对；凡作者自报而机器不可复算的，我标 UNKNOWN；凡需进一步实验才可裁决的， 我标 BLOCKED。

## ② 证据清单（已实际打开/复算）

| 文件 | 用途 |
|---|---|
| `docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md` | HF-REAL 第一批闭环 writer 交付（工作表 / A×B×C 表 / artifact gate 数字） |
| 同目录 `INDEPENDENT_REVIEW.md` | 非 writer 独审意见（确认 writer 数字但拒绝 ACCEPTED） |
| 同目录 `BACKGROUND_METRICS.json` | S8 (cap_20261010_180557) 与 HF094333 的 A/B/C 三臂低位/前景/选簇点数字， 唯一来源 ground truth |
| 同目录 `ARTIFACT_STATES.json` | 4 个旧 STALE + 1 个新 REJECTED artifact 状态机 |
| 同目录 `REGISTRATION_REBUILD_RUN.json` + 同目录 `registration_094333_131958_v1/{diagnostics,registration,provenance,manifest}.json` | 新 artifact 的 source/target/correspondence/inlier/fit_p50/fit_p90/holdout_p50 直接数据 |
| 同目录 `TARGET_COUNTERFACTUAL.json` | r04 新 target vs r02 旧 target 反事实对照（删减 12965） |
| `docs/human_fall/returns/HF-REAL-03.md` | HF-REAL-03 (215540) 的 body-band 吞人量化 |
| `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/out/215540_frame_stats.json` | 215540 P 臂按带（legs/torso/shoulders/head） survived/removed 明细——HF-REAL-03 RS-E 源数据 |
| `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/out/215540_mask.json` | 同帧逐点 [x,y,z,kept]（抽查过条目数与 per_band 相符；未全量重算） |
| `sidequests/human_fusion_lab_next/real_fall/r03/probe_215540.js` | 生成 `215540_frame_stats.json` 的脚本（验证其口径为：距离 center=(2.10,-0.57) ≤0.55m 且 z∈[0.10,2.30] 的点； P 臂=在线 build_static_map 命中即删） |
| `docs/human_fall/HF_REAL_NEXT_DEVELOPMENT_PLAN_20261013.md` | 待审 HF-REAL 计划 §2 两项"假设"; §6 算法路线 |
| `pc_apps/human_replay/registration.js` 行 10–22 (`PROFILE` reg_gate_v1 bands/sanity/advanctage); 行 196–200 (load 的 gate 复核); 行 220–225 (`fusionKeys` 仅 VALID 放行) | reg_gate_v1 阈值、gate() 决策树、fusionKeys fail-closed 语义 |
| `pc_apps/human_replay/human_pipe_lib.js` 行 25–46 (PIPE 常量： `ground_keep_below_m=0.10`, `bg_occ_strong=0.85`, `bg_hit_min_pts=2`, `bg_match_radius`, `bg_voxel_xy/z`); 行 152–204 (`build_static_map` 在线、occ_strong=85% 全帧率、drop_ground 默认剔 z<0.10 的占点); 行 217–261 (`build_reference_map` 输出 voxels: occ); 行 265–270 (`reference_static_keys`, 默认 occ≥0.5); 行 277–289 (`extract_foreground` P 路径： z∈[0.10,z_max] + `_bg_match` 背景命中删); 行 313–333 (`extract_foreground_fused` HR-RET-V2 inc1： 删除 p ⇔ ref_match(p) OR (online_match(p) AND ref_supported(online_hit(p))); refkeys=null ⇒ 保守不删) | 静态背景自吸收实现、P 路径与 v2 路径删除语义、地面硬切位置 |
| `docs/human_capture/README.md`（头部前 3 行 + 行 106) | W03 R39-CLOSEOUT gate=**49.652981% < 50%** 的现行上下文口令与 R3.7 唯一验收表身份 |
| `docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/EXPERIMENT_COMPARISON.json` (大小 4.7MB, 用 Node 复算 summary 与 frames[0] 字段) | r2 单因素碎片恢复实验（baseline / point12 / point20 / component20 / low20 / axis) 的 added_count, near_background_added_count, adoption, human_precision, furniture_contamination_rate |
| `docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/FINAL_REPORT.md` + `DIAGNOSIS_BEFORE_EXPERIMENT.md` | r2 单因素实验的作者解释（fragment 概率、point12/20 near_background 增数、axis 实验净变化 0） |
| `docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1/ACCEPTANCE_V1.md`（仅摘 W03 上下文） | pointset r01 基线 |
| `sidequests/human_fusion_lab_next/pointset/r01/` 目录列表（code: actions.py, core.py, server.py, run.py, train_parts.py, …) | r01 结构核实（README 声明默认 PointPartNet 未接 GT、未训练部位模型） |
| `pc_apps/console/console_gui.py` 行 47–62 | 控制台 fall_embedded 实际加载 `pointset/r01/server.py`（与 FINAL_REPORT "console 实际 r02" 并不冲突——r02/r04 指 real_fall 线，控制台嵌入的是 pointset 线； 但 ST01 "完整入口" 未通过仍有效） |

机器复算脚本： 本审计只用 `node -e` 一次性 readFileSync + JSON.parse, 不做任何写盘。所有数值都能用同样方式单独重放。

## ③ Q1–Q5 逐条结论

### Q1: 点死亡分解（静立/低位点分别死在哪一环）

结论： **只能给最紧区间， 不是精确分解**。当前 JSON 允许拆出 5 个明确的"杀点环"(KS1–KS5), 但 97.6% 的总口径来自 215540 的 P 臂（KS2 单环）, 不是从总输入按 KS1–KS5 顺序逐级扣减。

#### 杀点环定义与直接证据

- **KS1 地面硬切 z<0.10**: `human_pipe_lib.js:281` (`extract_foreground` 工作空间裁剪 z∈[0.10, z_max]) 和 `:162` (`build_static_map` 先剔除 z<0.10 再计 occupancy)。这是**生产 P 路径入口**的第一环； 低位人体（躺/趴/腿） 绝大部分点从这里被砍掉。
  直接证据： BACKGROUND_METRICS 中 `low_z_reviewed_denominator=1163`（S8 窗口中已标低位点全集）, A 臂（P 生产） `low_z_reviewed_kept=26`(2.24%), B 臂（冻结参考） `180`(15.48%), C 臂（v2 诊断） `4`(0.34%)。
  含义： 在 S8 低位点集上， **生产 P 用 z 硬切+背景自吸收共杀 97.8%**, **v2 诊断臂 C 更差**, **B 冻结参考相对最好但仍只保 15.5%**。

- **KS2 静态背景自吸收 (P 生产主凶）**: `build_static_map` 在 64 帧内 occ_strong≥85% 的体素会被当背景。静立人在自己录制 64 帧内自然持续占同体素（HF-REAL-03 return 行 19: "occ_strong 门在 64 帧中任意持续占用体素必然被当背景；是行为性缺陷不是参数")。
  直接证据： 215540 (64 帧， 一人站立， center=(2.10,-0.57), r=0.55m, z∈[0.1,2.3]) 总区域点 = 112,903+2,774 = **115,677**; P 臂 kept=2,774, removed=112,903 ⇒ **97.6% 吞人**。这个口径就是"世纪难题"标题的来源。
  按部位（per_band): legs(-0.10..0.70) removed 31,313 / torso(0.70..1.30) removed 57,297 / shoulders(1.30..1.60) removed 18,341 / head(1.60..2.00) removed 5,952。 **躯干和腿是最大失血**（合计 88,610 = 78.5% of removed)。

- **KS3 registration 门拒绝 → v2 融合 arm 无法启用**: `ARTIFACT_STATES.json` 当前 valid=0, DEGRADED=0, STALE=4, REJECTED=1。`registration.js:220-225` `fusionKeys` 要求 `loaded.state==='VALID'`, 否则返回 null; `extract_foreground_fused` 在 refkeys=null 时保守退回 online-only 不删 (human_pipe_lib.js:311 "refkeys=null ⇒ 保守： 在线-only 不删"), 但 P 本身已吞人， 所以保守路径并不能救回人体。 ⇒ 整体 loop 停在 P 路径。

- **KS4 ROI 裁剪 / 会话布局未见人体**: HF-DATA-01 (return 行 49) 报告 S8 小 ROI 候选 **0/523 帧**, 原 polygon/REF_RT 未改； HF094333 无 reviewed GT 分母。这个环的杀点数无法从机器 JSON 单独拆（ROI 是屏幕几何示意， 不是物理过滤）。

- **KS5 所选簇丢弃 （最终"选人"步）**: runtime 段（每会话）有 rf_xyz_prob/pointnet_prob 的 selected_points vs hits; 对 S8 runtime 段 RF selected=58,593 但 hits=57,010; oracle(=最佳簇）也 57,010 ⇒ RF 选簇本身几乎达上界。S6 RF hits=20,658 vs oracle 26,739 ⇒ 差 22.7%; S6 PointNet hits=20,589。这里死点不是删（点已存在 fg), 而是"没把它归到人"。

#### 最紧区间

| 数据集 | 总点或区域分母 (D) | A=P kept | B=冻结 kept | C=v2 诊断 kept | 下界上死亡 |
|---|---:|---:|---:|---:|---|
| S8 (180557) **reviewed person** | 57,045 | 1,324 (2.3%) | 55,347 (97.0%) | 54,069 (94.8%) | **KS1+KS2 合杀 97.7%** |
| S8 (180557) **low-z reviewed** | 1,163 | 26 (2.2%) | 180 (15.5%) | **4 (0.34%)** | **KS1 地面切本身 + P 自吸 合杀 97.8%** |
| HF094333 prototype target proxy | 373,746 | 116,422 (31.1%) | 373,737 (≈100%) | 373,624 (≈100%) | **KS2 约杀 68.9%**（无 GT 分解） |
| 215540 person region probe | 115,677 | 2,774 (2.4%) | N/A (P 臂 probe 未跑冻结参考） | N/A | **KS2 单环已足杀 97.6%** |

**最紧区间（对静立/低位点）**: **KS1+KS2 联合是主凶**, 单占 ≥85% 的死亡点（S8 reviewed 97.7%, 215540 97.6%); **KS1 单独在低位点占主因**（B 冻结参考能救 KS2 但仍只保 15.5%→说明 KS1 把 84.5% 的低位点在 B 臂里也杀了）; **KS3** 不提供新删除，反而是**阻止 KS2 用 v2 救回** ; **KS4** 和 **KS5** 在 S8/S9 数据上不显著。**KS1(z<0.10) 与 KS2(build_static_map occ_strong)是可独立关掉、且当前数据就能量化的唯二源头。**

#### 缺什么才能精确

- 需要一份**逐帧逐点级**的 stage-tagged 删除 log： 对每个原始点记录"被 KS1 z 切删 / 被 KS2 static_map 删 / 被 KS4 ROI 滤掉 /被 KS5 未选簇"。当前 `extract_foreground` 只返回 `n_dropped`, 不区分删除理由(`human_pipe_lib.js:287-288`)。
- 需要对 215540 P 臂**额外跑一遍 B/C 同口径**(probe_215540.js 只跑了 P 臂）, 才能在该会话把 KS1 和 KS2 的贡献分开。
- 需要 S8 低位点(n=1,163)中， 单独增加一列 "ref-map-match" 数字 (B 臂 180/1163 已含， 但 A/C 缺这一维）, 才能知道 KS1 vs KS2 相对贡献。

### Q2: registration 全 REJECTED/STALE 第一根因

结论： **第一根因是"门本身没有给可行性证据"导致的几何 REJECT**——新 artifact (094333→131958) 是真实重算的，绑定全部通过（`binding_status=BOUND_CURRENT_INPUT_REFERENCE_CODE`), `code SHA`/`session SHA`/`leveling SHA` 全部核验， 但 reg_gate_v1 拒于 `RESIDUAL_HIGH / HOLDOUT_MISMATCH / SPARSE_CORRESPONDENCE` 三条几何原因。 **绑定已修，几何没修。**

#### 数字事实（新 artifact d5327a5f 的 diagnostics.json, 我直接打开的）

| 指标 | 实测 | reg_gate_v1 (pass / warn / reject) | 判定 |
|---|---:|---|---|
| support.n_static_source | 8,452 | ≥ 5,000 / 2,000 | pass |
| support.n_static_target | 13,330 | ≥ 5,000 | pass |
| support.n_correspondence | 3,817 | ≥ 500 / 200 | pass |
| support.inlier_ratio | 0.4516 | ≥ 0.50 / 0.30 | **warn → reject** (SPARSE_CORRESPONDENCE) |
| support.coverage_xy | 0.8007 | ≥ 0.50 | pass |
| support.max_sector_share | 0.5193 | ≤ 0.60 | pass |
| geometry.condition_number | 106.6 | ≤ 1e4 | pass |
| geometry.eig_ratio | 0.00938 | ≥ 1e-4 | pass |
| residual.fit.p50 (m) | 0.029691 | ≤ 0.020 / 0.030 | **warn** |
| residual.fit.p90 (m) | 0.105731 | ≤ 0.080 / 0.100 | **reject** (RESIDUAL_HIGH) |
| residual.holdout.p50 (m) | 0.024671 | ≤ 0.020 / 0.030 | **warn** (HOLDOUT_MISMATCH 由 fit_holdout_guard 升级为 reject) |
| residual.holdout_fit_ratio_p50 | 0.8309 | ≤ 1.50 | pass |

关键判定逻辑在 `registration.js:87-88`: `if(checks.filter(c=>c.id.startsWith('fit_')).every(c=>c.band==='pass')&&checks.some(c=>c.id.startsWith('holdout')&&c.band!=='pass'))` 会**额外补一刀 fit_holdout_guard=reject**; 但**即使不启用这条 guard**, `residual.fit.p90=0.105731 > 原 max=0.10` 独立已就是 reject。 ⇒ **第一根因是 fit_p90 单项 0.105731 超 0.10 reject 上限**, 不是 inlier_ratio (0.4516 只 warn 距 0.50 缺 0.0484), 也不是 holdout (holdout_p50 在单独比较时是 warn 0.024671 但 holdout_fit_ratio_p50=0.83 pass, 仅因 fit_ 全 pass 不成立才触发 fit_holdout_guard, 实际 fit_ 已经含 warn)。

**"重签不能修好质量门"是验证为正确的**(HF_REAL 计划 §2 论断 1): 重算出的 artifact 绑定/SHA 全部通过绑定（BOUND_CURRENT_INPUT_REFERENCE_CODE), `ARTIFACT_STAVTES` `human_qualification=BLOCKED_NO_W03_REVIEWED_GT; unrelated to geometry gate`。重签只是恢复"绑定信任", 不能解决"几何 0.105731 > 0.10"。 ⇒ 论断成立。

#### 但门本身是否合理？

这是**开放问题**, 且我的独立性要求我说 UNKNOWN:

- inlier_ratio=0.4516 与 coverage_xy=0.8007 都很高， 但 fit_p90=0.105731m （即 90 分位残差 10.6cm) 在 IFW192S 室内静态环境下**属于合理噪声水平还是真的没对准**， 当前**没有**物理真值或同步视频核验。`ifw192s-optomech-facts.md` 在 MEMORY 中提示： ROI 拟合高度≠安装高度——说明该雷达自身的光机几何会贡献与光斑尺寸同级的残差。
- reg_gate_v1 把 fit_p90 上限设在 0.10m, 是**经验值**（没有标定证据指向 8cm 或 10cm 哪个是"合理墙/柜结构残差"), 但它是**冻结 profile** (`PROFILE` freeze 在 `registration.js:39`), 打破需契约变更， 不是 writer 能私下下修的。

综上： **第一根因 = 几何 fit_p90 单项超过冻结门**。 绑定/SHA 已是 BOUND_CURRENT, 所以"重签不能救"是完全成立的。

### Q3: TARGET_COUNTERFACTUAL.json 证明了什么

只证明 r04 新 target 相对 r02 旧 target 在 9 个采样帧 (f0,4,10,18,20,47,72,109,118) 总共少了 **12,965 个点**(f10 少 144, f72 少 19, 其他帧 0)。不证明：

- 这 12965 个是家具还是人体（identity 字段明确 `UNKNOWN; old target not GT`)。
- r04 比 r02 "更准"还是"更保守"。
- 不同帧没采样的变化分布。
- 跟 registration 的三类拒绝（RESIDUAL_HIGH/HOLDOUT_MISMATCH/SPARSE_CORRESPONDENCE) 有没有因果。

**它是否暗示最小代价能过去的方向？ 否。** 该 JSON **不含**任何 toggle / 开关对照。它只在两个 target 版本间报差异。对"打开哪个开关最省事"它没有指导力。 真正的"开关"对照在 `BACKGROUND_METRICS.json` A/B/C 三臂差异（A=P vs B=冻结参考 C=v2 诊断）上—— **但那不是 TARGET_COUNTERFACTUAL.json 的内容, 是 writer 同一 FINAL REPORT 的另一份证据**。读者不要把两个 JSON 混为一谈。

在 A/B/C 臂上， S8 人保留 2.3% → 97.0% → 94.8%。如果用"B 冻结参考"作为开关， **静立吞人（KS2) 确实可解开**， 但代价（KS1 仍切, 且 unknown 48912-490193 飙升， **家具污染风险未判**） 不允许直接"打开"。所以最小代价开关的方向是有的： **B 冻结参考**, 但目前**没有身份 GT** 决定方差。

### Q4: pointset r02 单因素实验是真死路，还是缺 GT

`EXPERIMENT_COMPARISON.json` summary (我用 Node 复算过的):

| 方法 | added_count | low_added | near_bg_added | human_precision | adoption |
|---|---:|---:|---:|---|---|
| baseline | 0 | 0 | 0 | null | **BASELINE_RETAINED** |
| point12 | 434 | 0 | 108 | null | EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE |
| point20 | 4863 | 0 | 1,443 | null | EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE |
| component20 | 5917 | 0 | 1,718 | null | EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE |
| low20 | 4921 | 58 | 1,501 | null | EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE |
| axis | 0 | 0 | 0 | null | EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE |

字段 `near_background_added_count` 揭示 point20 新增 4,863 点中 **1,443 (29.7%) 在 near_background 范围**(2×tau 内）, component20 更高 1,718/5,917=29.0%, low20 也 1,501/4,921=30.5%—— 三成新增点紧贴背景残余。 writer 在 `FINAL_REPORT.md` 第 47 行明确 "拒绝新默认局部恢复", point12 对显著断片几乎无救， point20 新增 2 个轴歧义帧， low20 的 58 个低位点全在近背景。

#### 真死路 vs 缺 GT

- 显示 `EXPERIMENT_ONLY` + `BASELINE_RETAINED` 是看板口径， 并非"证明死路"; 但**实验本身已给出三个独立反例**（净轴歧义 0、近背景污染 ~30%、point12 无收益）, 在当前数据上没有可见收益信号。
- **正确表述**: "该路线没有自证收益， 且**身份 GT 缺失**导致无法复核 writer 的拒绝"。不是"已被证伪", 也不是"有希望"。
- 对"只降低静立吞人"目的： point12/20/30 **不指向恢复静立人体**(pointset r02 输入是**已经过 P 背景删除的前景**, 而静立吞人发生在 KS2 上游； 加筛下来的前景点救不回 ks2 删掉的身体）。  ⇒ **对静立吞人目标， 该实验方向是错的 lever; 它聚焦于"人不完整后怎么补碎片", 而非"为什么人根本没进簇"**。

⇒ 答复： **半死路**。缺 GT 是确定事实； 但实验指标本身已经显示 (1) 它不是修静立吞人的 lever, (2) 它牺牲了 ~30% 纯度的 near_bg 新增， (3) 这些新增没有任何精度收益证据。若目的是"解决静立吞人", 单因素碎片恢复在原理上就不对口。

### Q5: 最小修复菜单（按解锁能力/代价比排序）

以下每项都给出 (a) 修哪一环 (b) 预期翻转的 gate/验收 ID (c) 家具污染风险 (d) 最便宜的决定性实验（不写生产代码）。

#### M1 【最便宜， 最优先】 KS1 地面硬切废除 → 改为域内标记 + 由后续未知态保留

- (a) 修： `build_static_map` 的 `drop_ground` (human_pipe_lib.js:162, `:228`) 和 `extract_foreground` 的 z∈[0.10, z_max] 裁剪（`:281`)。**方法： 把 z<0.10 的点不删， 而是在一个"near_ground_unknown" 桶里单独保留**, 下游 build_static_map 计 occupancy 时可把这些点计成弱占用（例如 0.5 权重）而不是 zero weight。
- (b) 预期翻转： S8 低位 B 臂 180/1163 → 数值能冲到接近分母； 且 215540 因 p75-90 贴地点回到前景， P 吞人率可能显著改善（虽然 KS2 仍可能再次吸走）。**验收 ID = HF-BG-01 的 "low_z_reviewed_kept"**, 以及间接缓解 "C 臂低位 4/1163 FAIL"。
- (c) 家具污染风险： **高**——地面杂散、被踢动的鞋、散落小物、金属反射伪点会涌入前景。必须**同时**把 near_ground 桶的"近地未知"提交给仅诊断 UI 显示， 不能默认计入"所选人"。
- (d) 决定性实验（零生产成本）: **对 S8 low_z_reviewed_kept=1163 分母**, 用 Python or Node 一次性读 `background_frame_results.jsonl`, 把 z<0.10 的点从 deleted → kept 重新计一遍， 看 pass/warn/reject 三项分布 + 该新增点集中近背景体素的占比。这个实验只需**对已有 JSON 做域分析**, 不需跑生产函数。

#### M2 【高价比， 中等成本】 KS2 自吸收根治： 启用 B 臂冻结参考 + 在线 only 不删

- (a) 修： `extract_foreground_fused` (human_pipe_lib.js:313-333) 的 `refkeys=null` 保守路径改为真正的 v2 默认。前提是 M3 已完成（有合法 refkeys)。
- (b) 预期翻转： 把 S8 人从 2.3% → 97%, 215540 的吞人从 97.6% → 估计 <10%（需跑同 probe 才精确）。**验收 ID = HF-BG-01 "fg_person_kept"**, 以及 2026-10-13 HF-REAL-03 return 里 "静立吞人 97.6% FAIL" 记录。
- (c) 家具污染风险： **中-高**——v2 引入 unknown 点大幅保留， S8 已看到 unknown 从 48,912 (A) 涨到 490,193 (B)。与计划 §6.1 "UNKNOWN 不是必是人体"一致——须有硬负例（无人家具） 标定。
- (d) 决定性实验： 现成！ `BACKGROUND_METRICS.json` 的 A/B/C 兜底全部数字与 `RUN_LOG.md` 里已有命令。**只需要把 A/B 数据加一栏人工 intermediate 身份标注（10-20 帧）, 就能水落石出 B 臂 97.0% 里"真人 vs 家具"占比**。 HF-REAL-04 已把这列入人工队列。

#### M3 【必需前置】 registration 几何门标定（不是降门， 是补可辨识性）

- (a) 修： reg_gate_v1 `fit_p90` 的 0.08/0.10m 上限是否是 IFW192S 合理噪声， 无标定证据（见 Q2)。**方法： 不改门**, 先用一个同步的外部参照（如板端标定件、激光干涉、或者人工测量几个静态家具面） 估计 IFW 的真实墙柜残差 P90 分布。然后凭证据选 **(i) 门不变**（数据差， 重录）, **(ii) 门放宽到 P90 上限 0.15**(伪影）, 或 **(iii) 换一种几何方法（如 TLS→SVD 多假设 + 加权 RANSAC)**。
- (b) 预期翻转： 新 artifact 094333→131958 的 REJECT → 若外部参照支持"0.105731m 是该传感器合理水准", 门可调过； 若参照不支持， REJECT 是正确。无翻转保证。
- (c) 家具污染： 无（纯标定， 非删除逻辑）。
- (d) 决定性实验（便宜）: **拿 2–3 个已配平的 cap_20261010_131958 / cap_20261013_175227 无人家具会话， 计算出静态墙面体素间 P90 残差分布**, 形成一个 "IFW 静态残差 baseline" 数字。即便门维持， 这个数字也是后续所有 reg 任务的常识。这只需要**用现有 4 段空场 + Python/numpy**, 不需要动作片、不需要注册函数改动。

#### M4 【中价， 单独工单】 手工标注一批 S8 低风险代表帧 (10-20 帧）

- (a) 修： 不是代码， 是 GT。当前 S8 的 53 个对象帧是**已含传播**(FINAL_REPORT 行 45 "人工标注含传播关联"), 无法独立做身份 ground truth。
- (b) 预期翻转： M2 的家具污染率（c) 从"UNKNOWN" 变成"可测", B 臂是否 97% 真能保人 + 7.5% 是家具， 有数字回答。间接翻转 HF-BG-01 的 "COMPLETE GT" 资格。
- (c) 家具污染： 本项本身就是污染率测量。
- (d) 决定性实验： HF-REAL-04 `REVIEW_QUEUE.json` 已完成工具链（预存 PROPOSED; S8 小 ROI PHYSICAL 检查需人工）; 让一名标注员在固定窗口直接按 ANNOTATION_SCHEMA 提交。**非生产代码成本=人工时间**, 0 代码。

#### M5 【不在最小菜单， 但值得记录】 KS5 选簇/身份不是当前主凶

- (a) 修： S6 RF vs oracle 差 22.7%, S8 RF 已 99.9% 与 oracle 平。这环重要但**一旦 M1+M2 做完**, 会有更多人体点进入前景， KS5 信号会自然变大。当前不最小。

#### M6 【不在最小菜单】 ML PointPartNet/PointNet++ 线

- (a) 修： 用 PointNet++/Human3D 训练分割。HFUS-POINTSET-01 已建 PointPartNet 影子模型但没 GT。HF-REAL 计划 §7 也明确"先 freeze home-MVP, PointNet++ 是单候选"。 ⇒ 在当前无 GT 状态下继续训练 = 伪标签， HFUS-RD-01 之前已证明此路被打回（`hfus-rd01-findings.md` MEMORY)。

#### 菜单排序表（按"解锁能力 / 代价比"）

| 顺序 | 项 | 解锁能力 | 代价 | 家具风险 | 决定性实验 |
|---|---|---|---|---|---|
| **1** | **M1**(z地面硬切改 unknown 桶） | 低位 180→分母（理） | 低（纯离线义审） | 高（须另有诊断 UI) | 重算 background_frame_results.jsonl |
| **2** | **M4**(S8 人工 GT 10–20帧） | 判定 B 臂真伪 | 纯人工，0代码 | N/A | 现成 REVIEW_QUEUE |
| **3** | **M3**(reg 门标定） | 决定"0.1057m 是否这门能下" | 低-中 | 无 | 空场残差分布统计 |
| **4** | **M2**(启用 v2 默认） | 静立吞人 97.6%→<10% | 取决于 M3/M4 PASS | 中-高 | 现成 A/B/C 数字 + M4 |
| 5 | **M5**(KS5 选簇） | 次要 | 中 | 低 | 待 M1+M2 |
| 6 | **M6**(ML PointPartNet) | 高天花板 | 高 | 无法评 | BLOCKED 在 GT |

**关键依赖链**: M1 → (M4 并行） → M3 → M2 。

## ④ UNKNOWN / 不可判定项

- **IFW192S 合理残差水平**: fit_p90=0.1057m 是"这门合理 wall noise" 还是"真实未对准" 无物理真值。计划 §2 "重签不能修好质量门"已验证为成立， 但**门当前值 0.10 是否合理** = UNKNOWN。
- **B 冻结参考保留的 97% 是否都是真人**: `BACKGROUND_METRICS.runtime` 表 S8 row `known_furniture=0` 但 `unknown=1583/58593`; FINAL_REPORT 已明确"0 已标非人 **不代表** 0 家具污染"。 ⇒ UNKNOWN。
- **r04 新 target 减的 12,965 点是人是家具**: TARGET_COUNTERFACTUAL "identity: UNKNOWN"。不可判。
- **S9 原会话** SHA 断裂不可恢复， ARTIFACT_STATES 未列； 维持 BLOCKED。
- **093958** 不配平（地面稀疏）, HF-REAL-03 return 明确 DATA_BAD——**不能**用"换算法"救。
- **215540 P 臂是否可分解 KS1 vs KS2**: probe_215540.js 只跑 P 臂， 没有同口径 B 冻结参考/C v2 对照。 ⇒ 只能给 97.6% 总数， 不能精确拆成 KS1 / KS2 两个 bucket。

## ⑤ 给 B 组 / 用户一句话结论

**A 组独立审计确认： 静立/低位人点死亡的 ≥85% 由两环联合造成——KS1 地面 z<0.10 硬切 + KS2 build_static_map occ_strong=0.85 在 64 帧内自吸收； registration 现状是绑定已通但几何 fit_p90=0.1057m 超冻结门 0.10m 独立遭拒（HF 计划 §2 "重签不能修好质量门"证据核实成立）; pointset r02 单因素碎片实验不是死路、但也不是救静立的 lever（三成新增点贴背景且无 GT); 最小路径是先用离线实验重算 S8 背景日志把 z<0.10 点从"删"改记成"near_ground_unknown" + 手工给 S8 10–20 帧身份 GT, 两单都无生产代码成本即可一次性回答"v2 冻结参考保留的 97% 是人是家具"。**

—A 组 (Claude Code via kimi-k3) · 2026-10-14 只读 · 未 ACCEPTED 任何项
