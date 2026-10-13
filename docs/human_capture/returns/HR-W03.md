# HR-W03 回传（跨 session registration 生产化）

> 本文件自 R3.7 起登记。W03 早前轮次（r1–r9）的记录在 `docs/human_capture/evidence/2026-10-06_hrw03_*/`（该阶段以证据目录为记录，不回填本文件）。

## R3.7 — Cross-Session Registration Productionization Design

### 本轮信息

- 工单 / 轮次：HR-W03 R3.7（用户 2026-10-07 计划书：B 级 registration 生产化，设计阶段）。
- 执行者 / 时间：OpenCode（`opencode-go/deepseek-v4.1-flash`，本会话）；2026-10-07（Asia/Shanghai）。
- 验收基准：`docs/human_capture/W03_R3_ACCEPTANCE.md`（阶段门）；用户 2026-10-07 指令的 8 项交付。
- 执行方式：单纯文档设计轮；不跑实验、不写代码、不 commit。
- 状态：**SUBMITTED（设计交付）/ 未 ACCEPTED**；软件/设备/物理分层：设计条目自验；实现/测试/设备一律 NOT_RUN。
- 基线：branch `master`，HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`；工作树在该 HEAD 的既有未跟踪证据之外仅新增本轮目录与本文；未 commit/push/reset。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full）。

### 交付物

`docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/`：

`00_baseline_and_scope.md` / `01_coordinate_contract.md` / `02_registration_artifact_spec.md` /
`03_confidence_gate_design.md` / `04_failure_and_fallback_matrix.md` / `05_shadow_integration_plan.md` /
`06_test_matrix.md` / `07_r37_summary.md`。

### 集中诊断与根因覆盖

本轮无缺陷修复。设计针对的目标根因 = "错误/漂移的 registration 可能静默进入 foreground 或把人体吸收进背景"，覆盖点：

| 根因面 | 设计覆盖 | 落点 |
|---|---|---|
| 方向/坐标系歧义 | 单一方向冻结 + 方向字段 + 方向自检 | 01 §3；03 §2；04 §4.4 |
| artifact 漂移 | session/leveling/refmap/code 四类 SHA 绑定；失效即 STALE | 02 §4–§5；04 F8–F12 |
| 低质量解被采用 | 四族 gate + fail-closed（缺指标=REJECT）+ 盆地消解 | 03 §2–§4 |
| 重复/跨用变换 | frame 标签不变式 + 错误码 | 01 §4；04 §4.1 |
| 静默回退 | SAFE_FOREGROUND_ONLY 语义 + 显式选择（无 auto-latest） | 04 §2/§7；02 §1 |
| mtime 换 leveling 底座 | registration 绑定 job（按 transform_id 解析） | 01 §5；04 §4.3 |

### 实际变更

- 新增：本轮证据目录 8 份 Markdown；本文。
- 未变更：任何 production/测试代码、配置、数据；`captures/` 未写；R3.6/R9 digest 未重算/未覆盖。
- 只读复核：会话 meta/bin、leveling transform/report/manifest、代码文件 SHA（与 r8/r9 记录逐位一致；清单见 00 §3）。

### 逐条验收（作者自验）

| ID | 要求（用户 2026-10-07） | 结果 | 落点 |
|---|---|---|---|
| D1 | frame 契约冻结（cur→ref；参考系定义无歧义） | PASS（文档） | 01 |
| D2 | 不可变 artifact + 全绑定（session/leveling/background/算法/时间） | PASS（文档） | 02 |
| D3 | confidence gate（支撑/几何/holdout/合理性）+ 盆地不静默 | PASS（文档；阈值含推导） | 03 |
| D4 | 六状态机（仅 VALID 进生产；DEGRADED=shadow） | PASS（文档） | 04 §1 |
| D5 | fallback 明确（SAFE_FOREGROUND_ONLY） | PASS（文档） | 04 §2 |
| D6 | 重复变换防护（帧标签 + 错误码） | PASS（文档） | 01 §4；04 §4.1 |
| D7 | R3.8 shadow 方案（golden + wrong/stale/missing 故障） | PASS（文档；预注册判定门） | 05 |
| D8 | 测试矩阵 | PASS（文档；T37/T38/T39） | 06 |
| —— | 实现/测试/设备/生产接入 | NOT_RUN（本轮不授权；R3.8 起） | —— |

### 未闭合与限制

- `reg_gate_v1` 中 6 项 PROVISIONAL 常量（`n_correspondence`、`inlier_ratio`、`coverage_xy`、`max_sector_share`、`condition_number`、`eig_ratio`）须在 R3.8 实测后复核/冻结；未冻结禁止 R3.9。
- audited pair 的 gate 实测状态（VALID/DEGRADED/REJECTED）未预判；若 DEGRADED，R3.9 放行需用户裁决。
- sanity bounds 推导样本较小（D1 单 pair 四解 + D2 6 个候选 pair，场景身份沿用既有记录）；升版重导路径已写明（03 §5）。
- 设备/物理/部署/采集：NOT_RUN；不自行 ACCEPTED。

### 交给独立复审

- 现行基准与本轮变更：本文件 + [`07_r37_summary.md`](../evidence/2026-10-07_hrw03_r37_productionization/07_r37_summary.md)。
- 完整交付：上述证据目录 00–07。
- 建议复审重点：① 01 方向/canonical B 数值与 R3.6 归档一致性；② 03 阈值推导与 PROVISIONAL 清单的 fail-closed 语义；③ 04 失败矩阵是否覆盖"wrong/stale/missing + 方向 bug + 重复应用"；④ 05 判定门是否可在 R3.8 逐条执行。
- 下一步：R3.8 shadow 工单（用户授权后）。

## R3.7 复审修订 R1（2026-10-07）

### 本轮信息

- 性质：**独立复审发现项的修订**（R3.7 域内，非新里程碑）；复审发现 1–4 + 全量重导中新发现的同源项（`|t_z|` 行）一并修订。
- 执行者 / 时间：OpenCode（`opencode-go/deepseek-v4.1-flash`，本会话）；2026-10-07（Asia/Shanghai）。
- 授权与口径：用户 2026-10-07 选择修订路线 **A（全量重导：TLS-direct 平移计入观察集）**；范围为 01/03/07 文内修订 + 本记录。
- 执行方式：文档修订 + 只读复算（复算脚本在仓外 temp，仓库零写脚本）；不跑实验、不写代码、不 commit。
- 状态：R3.7 仍 **SUBMITTED / 未 ACCEPTED**；本轮为其复审修订记录。
- 基线：branch `master`，HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`；未 commit/push/reset。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full；用法 = 复用既有 TLS-direct 口径与 `_sanity_tls_direct.js`/`10_r36_registration.js` 同式公式，文内最小修订）。

### 修订内容（发现 → 处置）

| # | 复审发现 | 处置 | 落点 |
|---|---|---|---|
| 1 | `\|t\|` 行观察集口径：声称 max(D1∪D2) 但 TLS-direct 平移未计入 | 按 `t_c2r = t_ref − R_c2r·t_cur` 全量重导：`\|t\|` 0.0365→**0.0867 m**（D2 202456→203135）；limit **0.10→0.20 m** | 03 §3.2 |
| 1b | （全量重导新发现，复审报告未列）`\|t_z\|` 行同源欠计 | 同式重导：0.0099→**0.0577 m**；limit **0.05→0.15 m** | 03 §3.2 |
| 2 | “~1.1°” 例证不精确（203349 实为 0.9705°；全仓最大 202456=1.5442°） | 例证换为 202456 `a480b987/27f870c6`（≈1.54°）；“可达”两处同步为“最大 ≈1.54°” | 01 §2.2/§5；07 §4 |
| 3 | canonical B “逐位对齐”与 05 “≤1e-6 等价门”并存易误读 | 改为“≤1e-6 对账”，注明 canonical 为 10 位小数存档值、非 float64 全精度 | 01 §3.2 |
| 4 | roll 行来源 pair 对名（202456→203135 实为 2.6717°） | 改为 203135→203349（2.6799°；2.68° 数值不变） | 03 §3.2 |

### 复算协议（可复现，只读）

- 输入：`captures/leveled/<job>/tls/transform.json` + `report.json`（既有 artifact，未写）。
- D1/D2 选定 job：223757=`6bc5aabf8f0041ffa961758b4e84da94`、203349=`c9712acad48c4fb7a78cb119c08d4cdb`、202456=`a480b987d176479a89e1730f9d6b7c09`、203135=`500314ff11484be58f44b3cf11ad033f`；公式：`R_c2r = R_ref·R_curᵀ`（= `_sanity_tls_direct.js` 的 `R_directᵀ`）、`t_c2r = t_ref − R_c2r·t_cur`；euler ZYX 同 `eulerFromR`（roll=atan2(R21,R22)、pitch=asin(−R20)、yaw=atan2(R10,R00)）。
- 核对值：D1 TLS-direct euler `(−2.5818, 0.5258, −0.0271)`、θ=2.6348°；D2 六对 θ = 2.6348/2.6257/1.4240/0.0106/2.8196/2.8248；`|t|` 六对 = 0.0610/0.0608/0.0600/0.0004/0.0867/0.0867；全量 max：roll 2.6799（203135→203349）、pitch 1.4207（223757→203135）、yaw 2.3827（D1 B）、θ 3.3017（D1 C_ALT）、`|t|` 0.0867、`|t_z|` 0.0577（后两项 202456→203135）；`ceil(2×max, 0.05)` → |t| 0.20 m、|t_z| 0.15 m。
- 同会话 job roll（`transform.json` `roll_deg` 存值）：202456 {a480b987 −2.9399；27f870c6/8b3bbb66/ecdf584c −1.3957} 差 1.5442；203135 {7cb130bf −1.7339；500314ff −0.2682} 差 1.4657；203349 差 0.9705；223757 差 0.8443；本仓其余会话均单 job。
- 与独立复审复算逐值交叉核对：一致。

### 影响与边界

- 修订后复核：audited pair（canonical B）不受影响（`|t|`=0.0360 ≪ 0.20；`|t_z|`=0.0001 ≪ 0.15）；`reg_gate_v1` 其余常量未动；PROVISIONAL 清单不变。
- 未改任何 production/测试代码、配置、数据；`captures/` 未写；未 commit；R3.6/R9 digest 未重算/未覆盖。
- 本修订发生在 R3.8 任何创建/测量之前（预注册语义未被触碰）；修改点已在 01/03/07 文内以「复审修订 R1」块标注。
- 待复审：修订 diff（01/03/07 文内记录 + 本记录）；`|t_z|` 行（1b）为全量重导新增项，如复审有异议可单独回退。


## R3.8 — offline artifact + shadow（2026-10-07，最终 r3 自验）

### 本轮信息

- 本轮用户“继续推进主线”承接R3.8；后续人体识别计划已登记。
- 执行者：Codex，本聊天唯一writer，已停写。状态 **SUBMITTED / REWORK_REQUIRED，未ACCEPTED**。
- branch/HEAD：master / cfbb80c57508be1a0435fdb92260f698dc763934；原dirty tree保留，无commit/push/reset/部署/采集。
- 唯一验收：R3.7 `06_test_matrix.md` v1，SHA256 `70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18`。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full。
- 全文件（含untracked）基线及复核：本轮00_baseline.json/07_scope_result.json，4700原文件unexpected=[]；人侧Console README日期改动保留。

### 集中诊断与根因覆盖

startup/reload/同ID异内容/新目录/绑定缺失/坏版本/非法帧/SAFE矩阵见本轮00_diag.md。R1再审通过后发布新artifact。复用冻结R3.6数学，显式job/transform_id，无自动mtime顶替；session/leveling/refmap/code绑定与gate快照验证；输入失效即SAFE。

### 实际变更

新增 `pc_apps/human_replay/registration_method.js`、`registration.js`、`registration.test.js`；源码SHA见07_scope_result.json/10_final_submission.md。新四文件artifact：`captures/registration/cap_20261002_223757__to__cap_20261004_203349/`，id `ae5c8f4c021e91665c9e23cedd66730122d5f0552fd794de86a9b5f99e7a5e66`；独占创建，旧输入/产物不覆盖。新增工单/证据/人体识别计划；README维护当前链接，本回传仅追加。原生产入口/PIPE/matcher/leveling/驱动不改；临时故障副本已移除。

### 原始命令与退出

- `node .../01_r1_reaudit.js` exit0；0.20/0.15修订复核通过。
- `node pc_apps/human_replay/registration.js --source=cap_20261002_223757 --reference=cap_20261004_203349 --source-job=6bc5aabf8f0041ffa961758b4e84da94 --reference-job=c9712acad48c4fb7a78cb119c08d4cdb --outdir=captures/registration/cap_20261002_223757__to__cap_20261004_203349` exit0，02_writer.log。
- `node pc_apps/human_replay/registration.test.js` exit0；逐ID见03_unit_results_r1.json。
- `node .../04_shadow.js --run=r3` **exit1**；04_shadow_run_r3.log/04_shadow_results_r3.json/04_fault_logs_r3.txt。
- 原R3.6 `10_r36_registration.js --digest-only` exit0，原digest全等/19检查通过；旧归档未改。
- 原human_pipe_lib.test.js 35/0 exit0；human_replay_lib.test.js 45/0 exit0。
- `python -B -W error .../07_scope_check.py` exit0；09_artifact_recheck.json核manifest/当前code/B差≤1e-6。

### 逐条验收（作者自验）

| ID | 层级 | 状态 | 本轮证据 |
|---|---|---|---|
| T37-01 | synthetic | PASS | 03_unit_results_r1.json |
| T37-02 | synthetic | PASS | 03_unit_results_r1.json |
| T37-03 | synthetic | PASS | 03_unit_results_r1.json |
| T37-04 | synthetic | PASS | 03_unit_results_r1.json |
| T37-05 | synthetic | PASS | 03_unit_results_r1.json |
| T37-05b | synthetic | PASS | 03_unit_results_r1.json |
| T37-06 | synthetic | PASS | 03_unit_results_r1.json |
| T37-07 | synthetic | PASS | 03_unit_results_r1.json |
| T37-08 | synthetic | PASS | 03_unit_results_r1.json |
| T37-09 | synthetic | PASS | 03_unit_results_r1.json |
| T37-10 | synthetic | PASS | 03_unit_results_r1.json |
| T37-11 | synthetic | PASS | 03_unit_results_r1.json |
| T37-12 | synthetic | PASS | 03_unit_results_r1.json |
| T37-13 | synthetic | PASS | 03_unit_results_r1.json |
| T37-14 | synthetic | PASS | 03_unit_results_r1.json |
| T37-15 | synthetic | PASS | 03_unit_results_r1.json |
| T37-16 | synthetic | PASS | 03_unit_results_r1.json |
| T37-17 | synthetic | PASS | 03_unit_results_r1.json |
| T37-18 | synthetic | PASS | 03_unit_results_r1.json |
| T37-19 | synthetic | PASS | 03_unit_results_r1.json |
| T37-21 | synthetic | PASS | 03_unit_results_r1.json |
| T37-20 | offline | PASS | 04_shadow_results_r3.json |
| T38-02 | offline | PASS | 04_shadow_results_r3.json |
| T38-03 | offline | PASS | 04_shadow_results_r3.json |
| T38-04 | offline | PASS | 04_shadow_results_r3.json |
| T38-05 | offline | FAIL | 04_shadow_results_r3.json |
| T38-06 | offline | FAIL | 04_shadow_results_r3.json |
| T38-07 | offline | PASS | 04_shadow_results_r3.json |
| T38-08 | offline | PASS | 04_shadow_results_r3.json |
| T38-09 | offline | PASS | 04_shadow_results_r3.json |
| T38-10 | offline | PASS | 04_shadow_results_r3.json |
| T38-11 | offline | PASS | 04_shadow_results_r3.json |
| T38-12 | offline | PASS | 04_shadow_results_r3.json |
| T38-01 | offline | PASS | 05_r36_equivalence.log + 09_artifact_recheck.json |
| T39-01–08 / 设备 / 物理 / 部署 / 采集 | production/device | NOT_RUN | 本轮未授权 |

### 未闭合与限制

- gate=DEGRADED/SPARSE_CORRESPONDENCE：trimmed ratio 49.653%<50%pass门，v1不放宽，不自动开v2，不能生产消费。
- T38-05/S4 FAIL：clean人窗全带吸收31点>5，全在z<0.3；Codex此前漏计低带造成r2“0/PASS”，r3补正；旧过程证据保留。
- T38-06/S7 FAIL：原pipeline簇数组相减→NaN；新增green61行/purple70行需逐簇归因，不直接称误报。P消失126确认行包含应移除WD01，真人track/event GT不足，不能全称人体漏检。
- S1/S2/S3/S5/S6 PASS，S4/S7 FAIL；按预注册STOP，不进入R3.9。
- 背景P→S：WD01 93423→1754，WD02 159247→24508；不是人体识别率。
- r1跨盘硬链接EXDEV保留，r2改复制；r3只补cohort，pipeline/S digest未变。HP02真人BLOCKED，物理/外参未验证，dormant ML未启动。

### 交给独立复审

当前工单tickets/HR-W03-R38.md；唯一原06 v1；本轮最终集中提交 **10_final_submission.md**（覆盖08过程结论），完整输入/操作矩阵/源码SHA/真实错误与退出已保存。此为writer自验，不声称独立复审/ACCEPTED。下一步集中审计近地带loss、最小簇数统计缺陷、确认变化和支撑门定义；不擅改冻结代码、matcher、ICP或阈值。

用户人体识别计划：HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md，先W03收口→W04标准化/GT→W05粗骨架→W06姿态→W07跌倒→W08评测，仅PLAN_RECORDED。


## R39-CLOSEOUT — W03收口审计/统计返工（2026-10-07）

### 本轮信息

- 授权：用户完整粘贴的本轮任务A–F；只收口W03，禁止进入W04–W09及registration R3.9生产接入。
- 执行者：本聊天Codex唯一writer，未派工/无并行writer；本机Node v24.14.0，Python日志/清单包装使用 `-B -W error`；模型身份不另推测。
- 状态：**SUBMITTED / REWORK_REQUIRED，未ACCEPTED**；GT子问题BLOCKED，设备/物理/部署/采集NOT_RUN。
- branch/HEAD：master / cfbb80c57508be1a0435fdb92260f698dc763934；原dirty tree保留，含untracked/ignored可读文件5466项基线见 `00_baseline.json`。
- 唯一验收：R3.7 `06_test_matrix.md` v1，SHA `70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18`；不放宽或复制版本。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；复用现有PL/Three.js/OrbitControls，零新依赖。
- 本轮证据根：`docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/`。`r39_closeout`仅表示新收口轮，不是R3.9生产许可。

### 集中诊断与根因覆盖

| 缺陷/门 | 根因与消费者 | 本轮处置 | 保留行为 |
|---|---|---|---|
| BUG-R39-M01 / T38-06 | pipeline_frame簇数组相减→NaN，count字段输出数组；human_detect.js显示、R38 shadow统计均消费 | 先05_metric_reproduction复现/登记，然后三个表达式改用length | cleanup/聚类/特征/分类/Tracker/events逐位不变；严格delta==0门仍FAIL |
| T38-05/S4 | clean31损失：30注册后越过z=0.10，1reference命中；2点P本已cleanup，29属候选track1 | 原始point index与7帧逐点追踪，01/02和可标注viewer | 语义UNKNOWN31，不自动ground，不扣减既有31cohort |
| T38-06/S7 confirmation | 去背景同时改变点成员、几何/拓扑和独立Tracker票 | 257行逐点交集对应，r2纠正初次cleanup过归因，保存两侧历史 | 不称FP/FN；非静态155行真实人/物/连续性UNKNOWN |
| sparse gate | 9897raw×60%trim→5938 /11959=49.652981%，比50%差42keep | 固定R/t/支撑集诊断，07逐11959样本 | 不改ICP/matcher/PIPE/gate；旧gate仍DEGRADED |
| code binding | 最小统计修复改变PL全文件SHA，builder/code身份绑定失效 | native旧artifact STALE + SAFE=P实测；原代码/输入普通副本sandbox复现历史DEGRADED | 原artifact不重写、不静默重新绑定 |

### 实际变更

- production仅 `pc_apps/human_replay/human_pipe_lib.js` 三行诊断；SHA `af4cdea6d35c73633b12b0d230f3e91f8ba606d9e42fb2ba69bd4083b4af14e5`，diff=`05_metric_fix.diff`，起始文件副本在baseline_code。
- 新增本轮evidence工具/JSON/报告/153帧只读viewer与人工GT校验、工单 `tickets/HR-W03-R39-CLOSEOUT.md`；README和HUMAN_RECOGNITION_NEXT_STAGE_PLAN只新增当前状态/证据/下一步；本文仅追加。
- 输入meta/bin、绑定leveling、registration四文件、registration/math源码及历史证据SHA收尾见 `09_scope_check.json` / `09_input_source_sha.json`。未commit/push/reset/checkout/clean/采集/部署/改网络。
- 保留初次03诊断（由03_confirmation_attribution_r2.json supersede）与真实失败：refinement首轮257/267计数断言exit1；before/after完整shadow按安全/共同门exit1。不回写旧R38/r1/r2/r3。

### 逐条验收（作者自验）

| ID | 状态 | 当前证据 |
|---|---|---|
| T37-01 | PASS | 05_registration.stdout.log |
| T37-02 | PASS | 05_registration.stdout.log |
| T37-03 | PASS | 05_registration.stdout.log |
| T37-04 | PASS | 05_registration.stdout.log |
| T37-05 | PASS | 05_registration.stdout.log |
| T37-05b | PASS | 05_registration.stdout.log |
| T37-06 | PASS | 05_registration.stdout.log |
| T37-07 | PASS | 05_registration.stdout.log |
| T37-08 | PASS | 05_registration.stdout.log |
| T37-09 | PASS | 05_registration.stdout.log |
| T37-10 | PASS | 05_registration.stdout.log |
| T37-11 | PASS | 05_registration.stdout.log |
| T37-12 | PASS | 05_registration.stdout.log |
| T37-13 | PASS | 05_registration.stdout.log |
| T37-14 | PASS | 05_registration.stdout.log |
| T37-15 | PASS | 05_registration.stdout.log |
| T37-16 | PASS | 05_registration.stdout.log |
| T37-17 | PASS | 05_registration.stdout.log |
| T37-18 | PASS | 05_registration.stdout.log |
| T37-19 | PASS | 05_registration.stdout.log |
| T37-21 | PASS | 05_registration.stdout.log |
| T37-20 | PASS | 06_shadow_results.json |
| T38-02 | PASS | 06_shadow_results.json |
| T38-03 | PASS | 06_shadow_results.json |
| T38-04 | PASS | 06_shadow_results.json |
| T38-05 | FAIL | 06_shadow_results.json |
| T38-06 | FAIL | 06_shadow_results.json |
| T38-11 | PASS | 06_shadow_results.json |
| T38-12 | PASS | 06_shadow_results.json |
| T38-07 | PASS | 06_fault_regression.json |
| T38-08 | PASS | 06_fault_regression.json |
| T38-09 | PASS | 06_fault_regression.json |
| T38-10 | PASS | 06_fault_regression.json |
| CURRENT_ARTIFACT_STALE_SAFE | PASS | 06_fault_regression.json |
| T38-01 | PASS | 05_r36_equivalence.json |
| T39-01–08 | NOT_RUN | registration生产未授权 |
| HP02 真人弯腰 | BLOCKED | 缺真人数据，合成不替代 |
| 设备/物理/部署/采集 | NOT_RUN | 本轮未授权 |
| W04–W09 | NOT_RUN | 本轮明确禁止 |


S1/2/3/5/6 PASS；S4/7 FAIL。逐命令stdout/stderr/exit为各 `.run.json` 与同名前缀日志；完整shadow165帧且第二跑确定性通过，exit1为T38-05/06真实失败。新metric5项、新r2 attribution5项、pipe35、replay45、registration逐ID、原R3.6 19项与当前STALE/故障全帧SAFE回归均通过，不以总数替代完成。

### 未闭合与限制

- W03最终 **REWORK_REQUIRED**：31语义/候选连续性GT未闭合，原gate和共同门未过；不能进入W04。
- new green61=gain39/history20/topology2；new purple70=gain58/history1/topology11；disappeared126=WD01静态102/reference8/history6/candidate-loss6/topology4。净green -65、purple -67，不能冒称误报/漏检。
- 跨P/S候选overlap split10/merge2需真人/静态/混合GT；cleanup自身split/merge0，S128帧count delta减少，严格delta==0仍FAIL。
- WD01 93423→1754（98.1225%）、WD02 159247→24508（84.6101%）只是本机离线背景残留改善，不是人体准确率。
- 原R3.6原代码sandbox完整digest `23830edefcb28f04774e328af64abce014dfeff35df75462f8a6f68d68eb3357` 精确复现；当前源码原script19项/算法结果/CSV SHA相同；新完整digest含新PL SHA，正常变为 `5da7a60d3e23b1b718194d21049246a7820ded62468018604e5171ca1000cb8c`，旧证据未覆盖。
- 真人弯腰HP02 BLOCKED，骨架/姿态/真实跌倒性能/设备/物理均NOT_RUN或未验证。

### 交给独立复审

当前工单 `HR-W03-R39-CLOSEOUT.md`；最终集中报告 `08_final_closeout.md`；唯一验收原06 v1。31点逐表01/02、现行r2归因03/04、metric复现/回归05、完整shadow/故障06、gate07、SHA/范围09均可审查。独立复审尚NOT_RUN，不自行ACCEPTED。

下一步仅人工GT与gate支撑/契约审查：viewer `09_point_review.html`，具体point/frame/cluster/track清单 `09_gt_pending.json`；人工导出后 `review_gt.js <人工导出.json> <新结果.json>` 校验绑定/标签，复跑全链需新evidence轮，不覆盖本轮。GT也不能自动绕过未通过的gate。


### 收尾补记（只追加，保留原提交正文）

`09_final_integrity.json/md`：受保护原文件264项SHA一致、PL精确三行改动；另观测到范围外28个原文件变化/消失及9个新增，包含其他会话和Console/HC文件，均保留，不能声称全仓未变。本实验绑定输入与历史证据不受影响。GT格式回归6项PASS但仅synthetic，真人GT仍BLOCKED。


### GT 后复跑路径补充

新 evidence 目录必须与本目录同处 docs/human_capture/evidence/ 下。除工具与 baseline_code 外，还需复制本轮不可变对账锚点 01_absorbed_points.json、03_confirmation_attribution.json、03_confirmation_attribution_r2.json；不要复制旧06输出，再在新目录运行 closeout_shadow.js --phase=after 生成新的06_shadow_results.json，并用 run_record.py 新前缀保留日志。review_gt.js 另读人工文件写独占新结果，原shadow门保持。人体GT和物理验收仍未完成。


## R40 — W03人体安全收口研究与最小方案（2026-10-07）

### 本轮信息

- 授权：用户本轮A–D研究、诊断与开发方案设计；明确禁止production算法补丁与registration接入。本聊天Codex单writer，无派工。
- 状态：SUBMITTED / **REWORK_REQUIRED**，未ACCEPTED；真人GT BLOCKED，设备/物理/部署/采集NOT_RUN。未进入W04及后续阶段。
- 唯一验收表：R3.7 06_test_matrix.md v1，SHA 70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18。没有修改验收表/门/原artifact。
- branch/HEAD：master / cfbb80c57508be1a0435fdb92260f698dc763934；含untracked/ignored全树基线00_baseline.json，dirty保留。
- ponytail实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。本机Node v24.14.0，Python脚本均-B -W error，纯stdlib及既有PL/helpers。
- 新独占证据根：docs/human_capture/evidence/2026-10-07_hrw03_r40_research_r1/；集中报告07_research_and_minimal_plan.md，最小补丁设计08_bug_and_patch_design.md，GT格式06_gt_label_format.md。

### 集中诊断与根因覆盖

| 项 / 现行验收 | 根因与受影响入口 | 研究结果 | 方案/停止条件 |
|---|---|---|---|
| T38-05 / S4 | source拟合地面registration后不同于reference面，S多处extract/pipeline直接crop reference z | 两面倾斜1.770153°；31点处竖向差1.353–24.565mm；source面crop反事实翻转30点，固定图下仍2点reference命中 | GT先行；不是已证正确消地面或人体修复，不改阈值/数学；旧31cohort保留 |
| T38-06 / S7 | 固定XY网格重分箱+成员变化+独立Tracker历史 | 33帧全候选raw-index交集与旧结果一致；f151无删除Q也merge；f105/f146点保留而票变 | GT区分去粘连/真人碎裂；原strict gate仍FAIL |
| BUG-R40-I01 | leveling.py exporter保留invalid；registration.loadFrames及浏览器apply_Rt无条件变换零XYZ | source1250003/ref778477零XYZ与既有invalid_xyz_count精确相等；raw零被denoise删，配平后通过；gate源i0为虚点且normal无效 | 小guard草案核所有入口，保留索引/opaque字节；生产未改，不靠改变分母翻gate |
| BUG-R40-T01 | PL.Tracker.tick缺used集合，同帧可多簇更新一个track/votes | S f46实际复用track3两次0票；合成一帧3正簇能满足3票 | 每帧一对一used set草案，保持顺序/EMA/门；禁止本轮实施 |
| BUG-R40-T02 | votes按观测push，missing frame不老化票 | S track4 f61使用53/55/56/61观测确认；最近5帧只1正票；gap最小repro已存 | 按frame过期草案；先T01，seek生命周期另核；不改3/5或Fall |
| gate协议 | numerator确为trim后支撑，文本final iteration与fixed B重测集需澄清 | 9897raw→5938keep/11959，50%仍差42keep/70raw；50%与60%非逻辑冲突 | 双覆盖命名/独立依据建议而已；不放宽50、不发布profile、不换解/挑样本 |

### 实际变更与逐条验收

- production代码/PIPE/matcher/ICP/registration/leveling/人体几何门/确认门/Tracker/Fall **零修改**；只新增本轮evidence工具、JSON、CSV与研究报告，本文仅追加。原captures/历史evidence未覆盖。
- R39整目录293文件/1,257,292,336字节完整读入，大型JSON完整解析不直接打印；03_r2为现行归因。
- 本轮只执行新的diagnostic/assertion：baseline、full evidence read、02_research、03_followup、04_reports，实际exit0；stdout/stderr/exit/参数在同前缀run.json日志。没有重复R39 full shadow或既有test suites。
- 07_acceptance_status.json逐ID列T37-01..21含05b、T38-01..12本轮均NOT_RUN，旁列R39既有PASS/FAIL；**T38-05/06承接FAIL，不被诊断exit0取代**。T39-01..08 NOT_RUN；HP02真人BLOCKED；设备/物理/部署/采集NOT_RUN。
- 初次诊断collisions.final_votes保存可变数组引用，03跟进从不可变旧snapshot校正r2；旧输出保留，r2为当前。原R39/production没有这项工具修订。

### 未闭合与独立复审入口

- GT优先31点7帧→24非WD01消失行→12拓扑帧，去重38帧；仍须覆盖155行97帧。原viewer复用，pair单标签不足以表达P/S各簇/person_id，最小sidecar格式已交付；邻帧缺81/82/89/91/142的补充方案仅设计，NOT_RUN。
- 不称FP/FN、真人fragmentation或准确率。31语义/真实身份仍UNKNOWN；gate保持历史DEGRADED，当前STALE/SAFE结论承接R39，不重绑定。
- 先GT与I01/T01/T02审查，生产补丁另授权；高度参照/拓扑人体方案依赖GT，gate设计需独立依据。GT补齐仍不能绕严格安全/共同门或支撑gate。
- 审查集中报告07、repro/trace r2 04、逐点03、gate05、GT06、patch草案08；09_integrity.md列SHA与范围。未commit/push/reset/checkout/clean/部署/采集/网络变更。


### R40收尾补记（只追加）

06_integrity首轮exit1：393个protected文件无漂移；失败仅因校验器把以Windows文本方式保存的append.md之CRLF，与实际以二进制追加的LF相比较。原return前缀和实际追加内容正确，没有回传破坏。旧失败stdout/stderr/run/json/md保留；r2按真实追加字节复核，09_integrity_r2.md/json为当前完整性结果。

集中报告现以07_research_and_minimal_plan_r2.md为最终；研究结论、GT/production状态不变，仅补完整性校验修订及真实首轮exit1记录。观察到范围外README变化及cap_20261007_154920/下载部署证据新增，均保留，未由本轮脚本写入，不推测操作者。REWORK_REQUIRED不变。


## R41 — HTML效果对比页（2026-10-07）

- 用户授权：基于已有算法结果生成HTML效果对比。本聊天Codex唯一writer；ponytail实读 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。
- 证据：docs/human_capture/evidence/2026-10-07_hrw03_r41_comparison_r1/；入口comparison.html。复用原Three.js/OrbitControls和153帧局部viewer数据，165帧统计独立显示。新方案是已保存R39离线S，未包含R40提出的修复。
- 页面：同步双点云、播放/逐帧、8关键案例、视角/聚焦、上下文/框/差异开关、31点审计位置叠加、全序列曲线、候选/票表及GT/研究入口。颜色是算法输出，不是GT；局部点云与全帧计数明确区分。
- baseline、数据构建、JS语法、153帧数据一致性/SHA/索引守恒检查均exit0，真实stdout/stderr/exit在同前缀日志。浏览器已查看f55/f63/f151、视角/聚焦/上下文操作，控制台warn/error为空；播放按钮已触发，完整播放结束验证NOT_RUN。一次UI自动化精确label定位失败后改用DOM已确认的combobox角色，页面本身无该错误。
- production算法零修改，R39全目录及5个关键生产源码SHA核对相同；原capture/旧evidence不写，dirty保留。本文仅追加。
- 唯一验收仍R3.7 06_test_matrix.md v1；T37/T38本轮NOT_RUN（仅UI与数据检查），既有T38-05/06 FAIL/gate DEGRADED/当前STALE不变。T39/设备/物理/部署/采集NOT_RUN；真人GT BLOCKED；W03仍REWORK_REQUIRED，不进入W04。


## 2026-10-08 新五段静立/空场诊断 r1（Codex，仅诊断）

- 用户授权：承接本聊天离线诊断约定；用户交付五段本地会话并确认布置无移动、人体全程静立。状态 SUBMITTED（诊断完成），W03 REWORK_REQUIRED 与 HR-RET-V2 历史状态不变，不宣告 ACCEPTED。
- 证据/结果：evidence/2026-10-08_new_static_sessions_r1/README.md；五段配平 recommended=tls；114340/114422 配准 gate PASS（52.85/50.88%），114205/114254 WARN（49.38/49.51%，仅 SPARSE_CORRESPONDENCE）。没有生成 production artifact，新 pair loader 仍 UNAVAILABLE。
- 固定区域 V2 函数层：114340 保留 91.92%、候选281/281、确认轨道230/281；114422 保留100%、候选195/195、确认0（SOLID_UNIFORM 183帧）。区域非逐点GT；隔板旁185删除点集中家具侧边缘；5帧cleanup各1区域点，身份未核。新人体验收 BLOCKED，详见 acceptance_status.json。
- 家具窗三帧抽样：两段 PASS 的 p90 三维参考形心距离7–10cm、参考删除95–100%；WARN正Y窗p90约12–18cm。不是全桌面GT/物理验收。
- 现行唯一表与 SHA：R3.7 06_test_matrix.md v1 SHA 70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18；HRRETV2_ACCEPTANCE.md v1 SHA d5d447a10f0422b0eae4199543a8809c2c724e9046375bded3847a390d1b0f43。T37回归已跑ID均PASS，T37-20及T38/T39 NOT_RUN；原T38-05/06 FAIL不被新诊断替换；V2新数据02/03/06 BLOCKED GT；V2-07仅identity-reference离线0/0；V2-13五套回归PASS；V2-14 NOT_RUN。
- baseline master / cfbb80c57508be1a0435fdb92260f698dc763934；00_baseline.json覆盖原git tracked+untracked SHA，原始五会话SHA单独绑定；原existing文件无漂移，本文只追加。原source/captures/历史evidence只读，新增本轮evidence脚本/JSON/图/派生配平。
- ponytail实际读取路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md；Python3.12.10/NumPy1.26.4、Node24.14.0，Python均-B -W error，绘图/收尾加-X utf8。未调参数、未改算法、未重签、未开生产旗标、未设备操作、未commit/push。
- 独立复审入口：README.md、acceptance_status.json、registration_results.json、retention_results.json、region_audit.json、00_baseline.json、integrity.json及各*.run.log。下一步：审查GT/形状规则或授权PASS pair artifact生产化；不自动进入R3.9/W04。


## 2026-10-08 新会话语义冻结复核 r1（优化可行性）

- 用户询问能否进一步优化；承接离线诊断约定，只做已有S-A+参数冻结的新数据验证。状态SUBMITTED，不授权/交付新生产算法。
- 证据 evidence/2026-10-08_semantic_new_holdout_r1/README.md / results.json / probe.run.log：四段×3帧×原区域/参考保留区域 HUMAN_EVIDENCE 24/24；空场4分量×3帧0/12 HUMAN。相关区域样本、同一人、非全帧整簇、非逐点GT；举臂ARM可见但HEAD未检出。
- 优先方向：真实簇全帧语义旁路AB+空场/家具负例+按实际帧的确认审计；隔板旁边缘GT另闭合；registration协议/算法/gate改动需独立工单设计评审。
- 现行R3.7与HRRETV2唯一表不变，本轮T37/T38/T39和V2全NOT_RUN，语义H01-H08仍草案；W03 REWORK_REQUIRED不变。生产源码/captures/历史证据未改、未重签/开旗标/部署/采集/ML；本文仅追加。
- 起始 master / cfbb80c57508be1a0435fdb92260f698dc763934，完整tracked+untracked SHA见00_baseline.json；ponyail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md（同聊天），Node24.14.0 probe exit0，record_probe Python-X utf8 -B -W error；完整性见integrity.json。
