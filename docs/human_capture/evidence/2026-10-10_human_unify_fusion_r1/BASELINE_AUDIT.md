# BASELINE_AUDIT — HUMAN-UNIFY-FUSION-R1 STEP 0

2026-10-10 (Asia/Shanghai)。本文件逐文件核实工单 §1 列出的既有证据与代码，全部真实读取，非按名猜测。
基线 SHA 见 `source_baseline_sha.txt`，git HEAD 见 `git_head.txt`。

## 1. 既有验收状态（真实来源）

| 来源 | 结论 |
|---|---|
| [R2 CLOSEOUT](../2026-10-10_human_unify_rework_r2/CLOSEOUT.md) | SUBMITTED：R01–R08 修复+独审 PASS；96 项功能回归 PASS；9 旧会话 1,196 帧 A/B 对拍 PASS；**性能 FAIL**（perf_02 exit1 dynamic U3 P95=71.49ms；perf_03 exit1 dynamic BASE_B P95=53.33ms / U3=42.62ms；门限 P95<50ms + heapUsed<1500MB，未放宽）；S02 全树冻结 BLOCKED（范围外 RF 被外部改写，记录在 EXTERNAL_DEPENDENCY_CHANGE.md，不回退）；D01 NOT_RUN。整体 **未 ACCEPTED**。 |
| [RF-OPTIMIZATION-R1 21_CLOSEOUT](../2026-10-10_rf_optimization_r1/21_CLOSEOUT.md) | 离线研究 SUBMITTED，独审无当前软件 FAIL；**识别可用性 BLOCKED**，R3/R4 NOT_RUN。同房间 6 静态会话弱标签折间统计：RF-v2(51 维) P=.8772/R=.9989/FP=128；RF-v3(69 维) 同值；HistGBDT(69 维) P=.9870/FP=12。明确注明「折间描述统计，不是生产阈值成绩」「0 人工 GT 签核，人工复核 JSON label/signature 留空」。 |
| [HUMAN_UNIFY_R1_ACCEPTANCE v1](../../HUMAN_UNIFY_R1_ACCEPTANCE.md) | R2 轮唯一验收表，逐 ID PASS/FAIL/NOT_RUN/BLOCKED 语义沿用。 |

**旧 9 会话 1,196 帧**（runs_03 对拍）= cap_20261004_203135、cap_20261004_203349、cap_20261007_143945、cap_20261007_154007、cap_20261009_113611、cap_20261009_114641、cap_20261009_114709、cap_20261009_114817、cap_20261009_121622。
**新 9 会话**（本工单表格，2026-10-10 录制）= cap_20261010_175227 / 175429 / 175553 / 175804 / 175943 / 180235 / 180337 / 180557 / 180751，meta.json `display_name` 与工单 S1–S9 名称、帧数逐一相符（见 F0 manifest）。两批无任何 SID 重叠。

## 2. 当前真实架构与模块调用关系

```
runner.js ── data_loader.js (28B/点 meta/points.bin 契约, eager+lazy)
        └─ engine.js UnifiedEngine(cfg.mode)
             ├─ schema.js        : FrameContext/Candidate/Track/Diagnostics + GT_LEVEL 四态
             ├─ leveling.js      : R/T 契约解析 (REF_RT / IDENTITY / meta.leveling / 显式)
             └─ 生产模块经 vm.compileFunction 每实例独立闭包加载 (pc_apps/human_replay/, 只读):
                  ├─ human_pipe_lib.js  : denoise/build_static_map/extract_foreground/
                  │    cleanup_isolated_fg/voxelize/cluster_voxels/cluster_features/
                  │    classify_human/evidence_postpass/joint_status/Tracker (A 链)
                  ├─ detect_overlay.js  : grid_key/find_clusters/associate/_dbg_state (B 链, 原样复用)
                  └─ rf_person.js       : 51 维 extract + rf_person_v1.json predict_person
```

模式语义（engine.js DEFAULT_CFG + 分支）：
- **BASE_A** = A 链 (PIPE 簇特征 + classify_human 几何门 + joint_status + Tracker)，online 背景。
- **BASE_B** = 原生产 B（固定配置，ref bg_envelope + find_clusters + rf51 0.55 + associate），配置被 _validate_mode_cfg 锁死。
- **U1** = A 链原样；**U2** = A + 保留 bank（仅独立 FG 确认建立/刷新，retained/merged 确认不续命，180s/30 帧过期）；**U3** = U2 但分类器换 rf51（几何特征照算但 decision 由 RF 概率阈 0.55 决定）；**U6** = U3 + track_lost_max=30；**U4/U5** 显式 BLOCKED（无 artifact）。

GT 契约：schema.GT_LEVEL 四态（HUMAN_VERIFIED / HUMAN_UNVERIFIED / PSEUDO_LABEL / UNKNOWN）；`ai_labels.json` 一律 PSEUDO_LABEL。`report().prf` 恒 `BLOCKED:measurable=false`。

保留 bank 规则（engine.js:183-234）：bank 条目仅由「active+human_confirmed 且本帧有 FG 源 CONFIRMED_HUMAN 候选」刷新（confirmations 需连续帧）；retained/merged 源候选不刷新；超时 180s 或 30 帧即删。

## 3. RF 特征契约（fv[37..39] 历史固化顺序）

51 维定义 `frame_feature.py` FEAT_NAMES。关键段：
- fv[32..34] = 特征值降序；fv[35]=ev0/ev1；fv[36]=ev1/ev2；fv[40]=ev0/ev2；fv[50]=ev0+ev1+ev2。
- **fv[37..39] 历史行为**：Python `np.sort(w)[::-1]` 后接 `np.argsort(-w_sorted)`，`argsort` 作用在**已降序**数组上恒得 [0,1,2]，`V=V[:,idx]` 为恒等 → 实际取的是 **eigh 原始升序（最小/中/最大特征值）对应特征向量列的 z 分量** |V[2,0..2]|。这不是「主轴 z 分量」的语义注释（header 与 [37..39] 的真实索引互相矛盾），但 `rf_person_v1.json` (SHA 4c83db11…) 就是在此固化顺序下训练的。
- rf_person.js:143-156 **显式复刻**：ev 按 desc、az 按 asc 排序输出，注释声明「JS 必须复刻，不是修 Python 排序链 bug」。
- 结论：**fv[37..39] 属于『训练时已有的历史特征契约』，任何修正必须版本化为新 fv 布局 + 新模型；不得改动 frame_feature.py / rf_person.js 的既有行为**（否则 v1 模型输入语义静默变化）。
- 其余维度（fv[0..36, 41..49]）python/JS 语义一致；协方差两端均用 N 分母（np.cov 偏差已在 RFO-R1 审计记录为已知差异项，见 01_AUDIT.md）。JS PCA 用幂迭代+收缩（闭式 3×3 数值不稳，seed 反例见 rf_person.js:88-91 注释）。
- 既有对拍：rf_person.test.js（合成点 + rf_test_fixture.json person/noperson 概率断言）+ RFO-R1「1239 源候选全向量重现」+ B2a 接件「joblib→json 12/12 推理对齐」。**缺**：真实簇逐维误差数值表 + 叶节点路径级对拍 + 边界矩阵（本工单 F1 任务 C）。

## 4. 已通过测试与未解决阻断项

已通过（R2 + RFO-R1）：96 项功能回归（7 suite）、9 旧会话 5 模式对拍（runs_03，SHA 守卫完整）、生产 JS 6 suite 回归、OpenCode 两轮真实独审（exit0）。
未解决阻断项：
1. **性能 FAIL**：dynamic BASE_B P95 53.33ms / dynamic U3 P95 71.49ms（perf_03/perf_02），门限 50ms，未放宽、未定位到模块级根因。
2. **fv[37..39] 语义/文档矛盾**——只能以兼容契约冻结；新 fv 版本化才可改。
3. **0 段人工 GT**：9 新会话无任何标注；人工复核队列（RFO-R1 manual_review_cases.json）label/signature 全空。
4. **RF 模型资格 BLOCKED**：RF-v2/v3/HistGBDT 只有弱标签折间统计，无跨场景人工 GT 证据；不得直接替换 v1。
5. **S02 全树冻结 BLOCKED**：工作树存在外部改写（含本轮开始前 git_status 已显示的大量 M 文件），本工单不主张全树冻结，以逐文件 SHA 守卫替代。

## 5. 本工单不触碰的边界

- 不回退/覆盖 R2、RFO-R1 或任何外部 agent 的修改；pc_apps/human_replay 生产文件只读（除新模型 v2 产物另名落盘）。
- 不自动 commit/push/部署/采集；不替换生产 WebUI 主入口。
- 新会话目录 `captures/remote/cap_20261010_*` 原始数据只读（F0 只生成 manifest 与 GT 工作台，不写会话目录）。
