# 人体融合下一阶段计划（2026-10-11）

> **修订版 v2 · 2026-10-11 用户优先级纠偏**。本节为当前生效的优先级；下方各阶段文档（PERF-R1/R4/骨架）保留作历史与逐 ID 证据，不再作为下一步执行顺序。历史保留：`HUMAN_FUSION_PERF_R1_ACCEPTANCE.md`、`HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md`、`HR_SKELETON_OFFLINE_ACCEPTANCE.md`、`HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md`、`HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md` 均未删除。

## 当前真实状态（Fact Table，勿与李辉假设混用）

| 用户指令假设 | 真实核查结果 | 证据 |
|---|---|---|
| “Demo V2 需从零开发/尚未存在” | **已存在并可运行**：`sidequests/human_fusion_lab/demo_v2.html` + `server_v2.js @127.0.0.1:8798`，九会话切换、8 层开关、3D+俯视+侧视、同候选四模型对比、案例定位下拉、标注草稿 | `start_demo_v2.cmd`；`evidence/2026-10-11_human_fusion_demo_v2_r1/BROWSER_CHECK_02.json` 全 PASS |
| “真实浏览器截图缺失” | 已存在：9 会话 + 成功/漏检/家具误检/S9 UNKNOWN **_04 标签全部重截图**（本次重抓，确认画布样式修复后 PASS） | `evidence/2026-10-11_human_fusion_demo_v2_r1/*_F0_04.png`、`SUCCESS_NEAR_F20_04.png` 等 |
| “重复 ID / 投票膨胀未修” | **研究版已修**：`unique_tracker.js` + `v2_runtime.fixedDetector` 强制使用，全 9 会话重复 ID = 0（`validation.log`）；生产 V1 默认 tracker 仍含 21 次缺陷，**未回流** | `sidequests/human_fusion_lab/unique_tracker.js`、`results/*_unique.json` |
| “PointNet 未实现/未比较” | 已 shadow 实现：ORT 单候选 P95≈0.208 ms；58/65 未知候选分类，**未超过 RF/XGB**，未接入 V2 实时对比 | `results/POINTNET_RUNTIME.json`、`R9_FINAL_REPORT.md` P3 行 |
| “GT/S9 工具没有” | 工具链完整可用：`pc_apps/human_replay/gt_annotator.html` @:8901 支持 track_id、逐帧唯一性、SHA manifest、传播、撤销；**S9 GT 空白纯因人工未重标**，工具不缺 | `GT_ANNOTATOR_USER_GUIDE.md`、`fix_s9_f1_p2.py` 修复脚本已存在 |
| “骨架不可见/需禁止” | V2 已有「粗几何轴（非解剖关节）」开关，且**明确标 GEOMETRIC_PROXY_ONLY + NOT_ESTIMATED + UNCALIBRATED**（满足“不伪造 17 关节”原则）；真实骨架节点仍 BLOCKED 于人工 GT | `demo_v2.html` proxy checkbox；HR-SKELETON-OFFLINE R1–R3 return |
| “姿态/跌倒未实现” | **属实**：`pc_apps/human_ml/*` 仅 person/noperson 二分类；W06/W07 姿态与跌倒状态机 0 行实现 | 子代理 Q5 事实核查 |
| “Q01 完全通过” | CONDITIONALLY ACCEPTED（研究版）；geometry(post) 存在 98.7% 轨迹确认不一致 → 仅作研究对照 | `Q01_FINAL_ACCEPTANCE.md` |

## 修订后的优先级（在现有资产上增量执行）

| 新优先级 | 任务 | 现状 | 下一步（增量，不重建） |
|---|---|---|---|
| **P0 Demo 可视化** | 九会话逐人巡视野 | 已 PASS（真实浏览器 + 截图 **_04**） | **剩余唯一缺口**：把 PointNet shadow 加入 V2「同候选五模型对比」列；其余已完成不重复 |
| **P1 修复缺陷** | TRACKER 重复 ID/投票膨胀 | 研究版已修 + 证据；生产 V1 仍带缺陷 | **不自动回流**：冻结在 fusion_lab；申请修代码授权才回流，否则标 BLOCKED-AUTH |
| **P1 S9 GT** | S9 双人 GT 无效（绑定坏/f1 索引复制） | 工具与 `fix_s9_f1_p2.py` 均已就绪 | **BLOCKED-人工**：打开 annotation_guide 由用户重标，软件不自签 |
| **P2 粗骨架** | 已确认人体簇上的真实节点输出 | 标准化/拒绝/独立 Tracker 全 PASS；真人节点 0 个（336 簇 UNKNOWN） | 同依赖 **S9 + 各会话人工 PERSON GT**；不可软件推进 |
| **P3 姿态/跌倒** | 站立/坐/蹲/躺/跌倒 + 持续躺地 | **0 实现**；九会话没有任何动作真值 | 本轮新增 `POSTURE_PROTOTYPE`（纯几何 z/extent 阈值 + 状态机草案）+ 明确 **数据缺口清单**；不标召回率 |
| **P4 部署** | RK3588/NPU/RKNN/生产替换 | NOT_RUN / BLOCKED | 按用户指令**继续冻结**，直到 P0–P2 真人效果由用户确认 |

## 本轮已执行的动作（非仅规划）

1. **修复画布像素塌陷**：`demo_v2.html` `image-rendering:pixelated → auto`（高 DPI 下点云被块状放大、文本模糊）。
2. **重启本地 Demo V2**（旧实例已在 :8798 占用），`curl /api/sessions` 返回 200；启动一个 headless Chrome CDP 9223。
3. **重抓全部真实浏览器截图**：tag `_04`，10/10 UI 检查 PASS（含九会话切换、S9 UNKNOWN、家具误检、后退 seek、暂停不前进、标注草稿绑定实际帧索引）。
4. **挂载粗几何代理轴证据**：V2 中已存在、UNCALIBRATED 明示，不当作骨架成果。

## 由用户解除的关键 BLOCKED（软件不能自证）

- **S9 GT 重标**：`http://127.0.0.1:8901/gt_annotator.html?sid=cap_20261010_180751`，按 P1/P2 双人协议逐帧选点，保存→冻结→导入 V2。
- **首次真实骨架正向节点**：S9 + 1 个站立会话由人工标 3 连续帧 PERSON，解锁 SKO-04/09/14。
- **生产 tracker 回流授权**：若允许把 `unique_tracker` 逻辑回流 `pc_apps/human_replay`，需单独修代码授权；此前继续作为研究对照。

## 保留的禁止项（与 R9/Q01/用户一致）

不部署 RK3588/NPU、不生产替换、不把自动标当人工 GT、不把回顾性 holdout 当陌生人员泛化、不以测试数量代替真实效果。

---

# 历史计划归档（v1 正文，保留不动）

用户指令：“继续啊下一个阶段的开发计划制定并且执行”。按本轨道最新收口推进本地离线开发，Codex唯一writer，先完成性能闭环；未明确的轨道选择已向用户提问，可随回复调整。

## 核对R3后的当前计划

新发现 `evidence/2026-10-10_human_r3/FINAL_REPORT.md` 未登记到入口，包含现行Map优化、GT修复与v3候选。该外部报告只作事实线索，不独立授权采集/训练。本轮性能复验已12/12通过，故不重复实施M1。下述最初计划的性能修复为条件任务，当前无生产源码修改必要；GT资格以当前实际文件再审，不直接继承报告PASS。

本轮新增并执行 **HUMAN-R4-CANDIDATE-AUDIT**：空场S1、近场行走S3-near、遮挡S6全帧离线v1/v2/v3对照；开发候选点集与GT点集交叠诊断、完整GT ROI与实际簇概率对照、候选分类与融合确认分开统计。GT compact索引先按同帧有效XYZ映射回raw索引，再与engine候选raw索引匹配；无交叠/未标/资格失败均UNKNOWN。只输出观察，不凭单簇/点数区间宣布51维不可分或算法为唯一根因。

唯一验收：[HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md](HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md)。只新增human_core离线归因工具/测试和本单文档。证据 `evidence/2026-10-11_human_r4_candidate_audit_r1/`；不改生产算法、模型、GT、captures，不训练、不采集。后续先人工复核UNKNOWN/propagated来源、再冻结新数据协议；不把本轮诊断当作生产发布门。

## 阶段一：HUMAN-FUSION-PERF-R1（本轮执行）

承接R2的S3-far FUSION v1/v2 P95>50ms。先冻结全树基线及当前engine原文，针对S3-far、近场行走、空场、静止、遮挡、双人完整帧剖析，再只修复实测热点中的冗余工作。保持点序、候选点集、概率、分类、track和事件完全一致；不得通过删候选、减帧、放宽门限实现优化。每组合预热5帧，报告P50/P95/P99、heap/RSS/external。唯一验收：[HUMAN_FUSION_PERF_R1_ACCEPTANCE.md](HUMAN_FUSION_PERF_R1_ACCEPTANCE.md)。

实施路径只允许pc_apps/human_core/engine.js及本单新增离线检查/文档。生产human_replay、GT、模型、captures、历史证据只读。证据为evidence/2026-10-11_human_fusion_perf_r1，已有目录不覆盖；只读独审可交OpenCode指定Go Flash，不并行writer。

## 阶段二：GT资格恢复（后续）

只读检查S1/S9当前来源。可信冻结文件缺失或绑定错误时列出具体缺项；不得把旧快照冒充当前GT、不得自动人工确认。补齐reviewed及meta/points绑定后，重跑受阻指标。真实双人缺标帧继续UNKNOWN。

## 阶段三：候选分布诊断（后续）

对可信已标帧比较完整GT ROI与实际候选簇的51维分布、点数/截断/污染和v1/v2概率，验证运动召回回退假设。先诊断，不用test选阈值；如需新训练，另冻结划分与唯一验收。不自动替换v1。

设备/物理/采集/部署、生产推广、commit/push均不由本计划启动。当前软件自验不等于ACCEPTED。
