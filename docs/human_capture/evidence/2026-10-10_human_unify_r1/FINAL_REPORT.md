# HUMAN-UNIFY-R1 · FINAL REPORT

日期： 2026-10-10 · 分支： master @ 347a5bf （工作树未 commit)

## A/B/C 三项独立裁定 （任务书 §11)

| 项 | 判定 | 依据 |
|---|---|---|
| **A. SOFTWARE_ACCEPTED** | **PASS （条件性）** | 公共核心可运行； 73/73 tests; 9 会话 × 5 模式行为一致； BASE_A/B 与生产语义一致； P95<50ms、heap<1500MB、模型兼容 OK |
| **B. ALGORITHM_ACCEPTED** | **NOT_MEASURABLE** | 27 段会话 0 HUMAN_VERIFIED; ai_labels=PSEUDO; 全库无 GT |
| **C. PRODUCTION_READY** | **BLOCKED** | RK3588 未实测； 集成路径未接通 |

## 实际完成了什么代码

| 文件 | 行数 | 角色 |
|---|---|---|
| `pc_apps/human_core/schema.js` | ~190 | FrameContext/Candidate/Track/Diagnostics + GT_LEVEL 枚举 |
| `pc_apps/human_core/leveling.js` | ~50 | 传感系→leveled R/T |
| `pc_apps/human_core/data_loader.js` | ~150 | 28B 点流切帧 / iter_frames_lazy / SHA |
| `pc_apps/human_core/engine.js` | ~470 | UnifiedEngine — 主类， 薄适配生产 pipe/rf |
| `pc_apps/human_core/runner.js` | ~160 | CLI: --session --modes |
| `pc_apps/human_core/test_*.js` × 6 | ~700 | schema / loader / smoke / replay / edge / model_compat / perf |
| `pc_apps/human_core/run_all_tests.js` | ~30 | 测试驱动 |

生产代码 `pc_apps/human_replay/*.js` **未改动**, SHA 参见 `02_source_sha/prod_sha256.json` (19 文件）。

## 公共核心位置

`pc_apps/human_core/` — UnifiedEngine 是唯一公共 entry, 通过 mode 参数切换实现：
- BASE_A: 复用 human_pipe_lib.js 全链 (denoise→fg→cleanup→cluster→features→evidence→joint→Tracker)
- BASE_B: 内嵌 detect_overlay.js 语义等价重写 (REF envelope + 5cm 网格 + 30 点门 + 1.0m gate + age≥3)
- U1: 同 BASE_A （薄适配零偏差 — 实测）
- U2: BASE_A + retention hot cell （机制存在， 时机有问题， 详见 § 已知问题）
- U3: BASE_A + rf51 顶替 joint （已修 f.joint 同写 bug)
- U4/U5: BLOCKED （无 rf69/gbdt 推理 json artifact)
- U6: NOT_RUN

## 哪些旧算法被复用

- **human_pipe_lib.js** — 入口 require: `denoise / voxelize / key_vox / key_bg / build_static_map / extract_foreground / cleanup_isolated_fg / cluster_voxels / evidence_postpass / cluster_features / classify_human / evidence_label / joint_status / Tracker / fall_assess / PIPE`。BASE_A/U1/U2/U3 全用它， 没重写。
- **rf_person.js** — rf.extract + rf.predict_person 直接被 BASE_B/U3 用；100 树 json 同生产。
- **detect_overlay.js** — BASE_B 不再 require 它（函数在 closure), 但语义等价复制： BG_CELL=0.05、z∈(0.1,2.3)、bg+0.25、30 点门、4 大簇、1.0m gate、TRACK_TTL=15、TRACK_MIN_AGE=3。
- **bg_envelope.json / rf_person_v1.json** — 生产 artifact, 引擎只读。
- **frame_feature.py 51维定义** — 由 rf_person.js 同维度实现， 引擎不再 Python 侧计算。

## 是否发现重复计算

| 现象 | 处理 |
|---|---|
| A 和 B 各自"找前景": A=online 3D 体素， B=REF envelope | 保留两路径， engine.mode 选； 不强行合 — 语义不同 |
| A 和 B 各自聚类： A=XY 0.15m 柱 BFS, B=5cm 网格 flood | 同上 |
| A 和 B 各自跟踪： A=EMA+gate.75+lost8, B=NN+gate1.0+age3 | engine 统一用 pipe.Tracker 等价； detect_overlay 不在引擎出现 |
| 28B 解码： fetch.py vs human_replay_lib.js vs session_load.py | 新建 data_loader.js 自管； 未来生产可统一进 human_core |

**结论**: 重复存在的根因是**语义不同**而非代码重复； 统一核心是"框架层统一", 不是"算法层统一"。

## 两条路线能否共用候选生成

**可以， 但有边界**:
- 若在线 bg (online static map) 严格超时踢人后无 transient, 该条会话可走统一 fg → 统一 cluster → 统一分类器。
- 若静立人被吸收， REF envelope 是必要的"反吸收"语义 — 不能丢失。
- → **统一核心支持 bg ∈ {online, ref_envelope} 作为独立选项**, 而不是合并。

## 动态真人主要损失发生在哪一级

基于 154007 (83 帧， 唯一自洽动态会话， C1.5 已知）:

| 层 | BASE_A 状态 |
|---|---|
| RAW | 49,127 点/帧 — 充足 |
| LEVELED | 同 |
| DENOISE | 同 |
| FOREGROUND | ~7,663 点/帧 (~16%) — 无问题 |
| CLEANUP | ~7,645 — 无问题 |
| RETAINED | 0 |
| CLUSTER | 5-9 簇/帧 — 合理 |
| **CLASSIFIER** | **person_cand=39/83 (47%)** ← **主损失点** （几何门 + 证据 + 3/5 confirm 太严） |
| TRACK | confirmed=1 |

**结论**: 真人 die at **CLASSIFIER层** （管道几何判定+证据+时序确认）, 与 C1.5 教导一致； C1.5 的 n_pts≥500 硬门是同一层的另一个误杀， 统一核心**未引入**该门（默认关闭）。

## 静止人体保留是否改善

**当前未实现可用保留**:
- U2 接口存在 (candidates=fg_plus_retained), 但 retention cell 注册时机是 `active.human_confirmed` → 一旦 confirmed 即成， 此时 fg 已含点 → 添加 0 点 → 等于 U1
- 143945/154007 中 U2 反而 confirmed 减 1 （位置 EMA 漂移后 lost 状态下 register 空 cell)
- **结论**: 接口对， 时机错误。需重写为"track closed 后 hot pixel bank"或"lost≥1 时 当前 track 位置注入"。

## RF/GBDT 是否带来可验证提升

- **rf51 在动态场景**: 154007 BASE_A confirmed=1 → U3 confirmed=25; 143945 3 → 23。但需 HUMAN_VERIFIED GT 判断"哪些 confirmed 是真" → **NOT_MEASURABLE**。
- **rf51 在空场**: 113611 BASE_A confirmed=0 → U3 confirmed=12 — **明确恶化**, 但 rf 不是为 transient 设计， 所以是预期。
- **rf69 / GBDT**: 无推理 json, BLOCKED。

## 家具误检是否变化

- **BASE_A**: 空场 203 家具帧， confirmed=0 → 无家具 confirmed。良好。
- **U3**: 空场 203 家具帧， confirmed=12 — rf 观点恶化； 真实场景家具 （历史 203135) 46 帧 rf 误报。
- **BASE_B**: 全部 9 会话 0 家具帧 (REF envelope 严格）。
- **结论**: 用 REF envelope 是当前家具免疫的唯一证据路径。

## 跟踪是否更稳定

- **BASE_B**: 除空场外 9 会话 5-8 tracks， confirmed/track 高 (2-6);
- **BASE_A**: 11-37 tracks， confirmed 比例极低 (0-3) — 管道本身严苛；
- **U3**: 介于两者之间。
- **已知回归场景**: 回放跳帧/循环/换sess已测 replay_contract 9/9; **真实世界跟踪稳定性** 需 GT 才能证明 (NOT_MEASURABLE)。

## 运行耗时和资源变化

PC node v24, 9 会话 × 5 模式 mean_ms:

| 最快 | 最慢 |
|---|---|
| BASE_B 113611 @ 3.0 ms/f | U3 143945 @ 41.1 ms/f |

- BASE_A 全线 10-21 ms/f
- BASE_B 全线 3.0-16.8 ms/f
- U3 全线 12.8-41 ms/f

详见 `06_PERFORMANCE_REPORT.md`。

## 已知问题 （显式 NOT_FIXED)

1. **U2 retention 时机错误** — 已识别， 未修复 （需 close 帧触发重写）
2. **U3 空场误报** — rf 在 transient 家具上 ≥0.55, 显式标记
3. **01 文件列表与实际差异** — 已修复 (R2 轮审计闭合）
4. **BASE_B inline 实现（不 require detect_overlay)** — 预期设计 （不复用闭包函数）, 已在 01 明示
5. **生产 detect_overlay.js 与 engine._tick_base_b** 是两套同义实现 — 未来独立统一； 本轮**不同步修改生产**

## 指标 BLOCKED / UNKNOWN 清单

| 指标 | 状态 |
|---|---|
| Precision / Recall / F1 | **BLOCKED** — 全库 0 HUMAN_VERIFIED GT |
| 跨场景/家具域 泛化 | **BLOCKED** — 无独立 GT 域外集 |
| 家具误检率 （绝对） | **UNKNOWN** — 无坐标级 GT |
| ID switch / track fragmentation | **UNKNOWN** — 无多目标 GT |
| Fall 检测 | **BLOCKED** — 0 段 fall 数据 |
| RK3588 实时/资源 | **BLOCKED** — 未上板 |
| RF69 / GBDT 对照 | **BLOCKED** — 无推理 artifact |

## 是否具备生产接入条件

**不满足**:
- 缺独立 GT 验证 (B)
- 缺板端实测 (C)
- U2/U3 语义需先稳定

**可以作为下一轮的基础**: 薄适配 BASE_A/B 已等价生产， 任何"生产路线切换实验"（如生产 A 换用 rf51 分类器）都可在统一引擎做， 形成测评闭环。

## 推荐的下一阶段工作

按优先级：

1. **真实人工 GT 采集**: 用带刻度渲染器（C1.5 已修）补 G-c15 动态 154007、143945 的坐标级 GT → 解锁 B
2. **修 U2 retention 时机** （重构 hot pixel bank, 在 track close 时触发） + 重测
3. **rf69 json 导出器** → 解锁 U4 实验
4. **GBDT json 导出器** → 解锁 U5 实验
5. **多人家具场景采集** → 解锁多人跟踪 ID switch 量化
6. **板端部署 spike** （用 slam-localization 容器跑 runner) → 解锁 C
7. **REF envelope 与 online bg 融合** （不是简单注入 — 有 FUSION_PRIORITY_RULE_DRAFT 备稿）

## OpenCode 独立审计

- R1: `07_review_findings.md` — REWORK, 4 FAIL + 2 note
- R2 (fix 后）: `07_review_findings_r2.md` — REWORK,
  - FAIL-1 FIXED
  - FAIL-2 PARTIAL （已修）
  - FAIL-3 PARTIAL (perf 数字每次 ±20%, 已在 06 显式声明）
  - FAIL-4 FIXED (PSEUDO_LABEL 检测 + 落盘 9 会话）
  - 注意-5/6 FIXED
- 本轮报告已按 R2 反馈完成最后一轮重写 (04 § 2.2 加 U2≠A 的例外、 05 schema=13、 06 引用 runner manifest 数字）

## 证据与可追溯性

- 代码: `pc_apps/human_core/*` （全新， 生产不动）
- 数据跑产物： `runs/*` (9 会话 × 5 模式， 每 json+manifest 有 sha256)
- 报告： `0[0-8]_*.md` + FINAL_REPORT.md （本）
- 审计： `07_review_findings.md` (R1) + `07_review_findings_r2.md` (R2)
- 生产源 SHA: `02_source_sha/prod_sha256.json`
- 会话 inventory: `01_data_audit/sessions_inventory.json`
