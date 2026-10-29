# HFUS-TCMS-02-REALDEV-02-S07F 回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-TCMS-02-REALDEV-02-S07F / r1 / OpenCode 本会话（用户本聊天派发"新修复项：OUTER_A 双支撑群"；声明模型 opencode-go/deepseek-v4.1-flash，未独立审计）/ 2026-10-18。
- 当前唯一验收：[ACCEPTANCE_V1.md](../evidence/2026-10-18_hfus_tcms_02_s07f_r1/ACCEPTANCE_V1.md)，SHA 2fd7fc1936e856afb12b17ac459f851581f5ef128289503d4de37bfe33aef6e4。
- 策略：区域支撑修复 RESEARCH；契约/复现/封存 ENGINEERING。ponytail 实际路径：`C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md`（OpenCode skill 工具加载，full）；Scientific Toolkit 本会话未读取（记为未核）。
- 执行方式：Windows Python 3.12 离线；复用 S07 会话与冻结前景账本（不重算前景）；命令/环境/源码 SHA/退出/耗时见各 *_RUN.json 与 FROZEN_BINDINGS.json。
- 状态：SUBMITTED，非 ACCEPTED。修复专项 PASS；冻结门 8/10（2 项遗留失败与修复范围无关，如实保留）→ NO_PROMOTION；独立执行 NOT_RUN；关节精度/人体效果 BLOCKED；纯度/召回 UNKNOWN。
- 起始 branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；注册时全树 size/mtime 基线 BASELINE_SCAN.json，封存复扫对照 SCOPE_CHECK.json。
- 输入两段 meta/points SHA 见 INPUTS.json；S07 证据 159/159 MANIFEST 复核一致（FROZEN_BINDINGS.json）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| S07-06 OUTER_A 900mm 跳变 | OUTER 掩码带 [0.33,0.88) 同时纳入两组纵向分离支撑（下带 frac .33-.44 与上带 .72-.88，案例帧最大间隙 0.41-0.86m），r0 组内中位数随成员数在群间切换 | r12 regions2 → 原样支撑门 → r08 CalibrationLayer 边测量 → summarize/conclude2 | r12/regions2.py 唯一语义变化：eligible 带 [0.33,0.88)→[0.52,0.88)（与 UPPER 同带），分位数域随之 | 旧 r11 与 S07 证据冻结；0.8m 门/几何阈值/参数/契约未动；失败与首轮日志保留 |

调用者核查：变体仅接受本会话 RAW ROI 契约（拒绝旧数据）；其余 12 节点代码路径逐字节未变（合成测试断言逐值相等）。

## 实际变更

| 文件组 | 用途 | 与用户既有差异的区分 | 提交源码SHA |
|---|---|---|---|
| r12/regions2.py | 唯一变体提取器 | 新目录；与 r11 差异 4 处（band 一处语义 + docstring/import/等价 asarray），见 REGIONS2_DIFF.txt | FINAL_SEAL.source |
| r12 其余 16 个 .py | 机制/登记/候选/评估/核验/测试/图/报告/勘误/审核/封存工具 | 仅本轮隔离代码 | FINAL_SEAL.source |
| 证据目录 2026-10-18_hfus_tcms_02_s07f_r1/ | 全部证据与记录 | 新增 | MANIFEST.json |
| WORKFLOW/REVIEW_LOG/本回传 | 流程记录 | 前置/追加，历史原字节保留 | DOCUMENT_APPEND.json |

## 逐条验收

| 验收ID | 类别 | 状态 | 证据与说明 | 入口 |
|---|---|---|---|---|
| SS01 | 交付 | PASS | 注册→输入/绑定/基线冻结；S07 证据 159/159 MANIFEST 复核；首轮基线扫描唯一排他写 | REGISTRATION/INPUTS/FROZEN_BINDINGS/BASELINE_SCAN |
| SS02 | 工程 | PASS | 唯一语义变化一处（band）；diff 4 处全披露；合成边界 5 测试 R3 通过；0.8m 门未动 | REGIONS2_DIFF.txt、TEST_REGIONS2_R3.log |
| SS03 | 机制 | PASS | 掩码复刻 3406 次比对 0 不一致；双群几何与规则对比（R0/R1/R4/R5/RB）；唯一变体选择依据 | MECHANISM_SUPPORT_RULES_R3 / MECHANISM_DUAL_POP_R3 |
| SS04 | 研究证据 | PASS | 两组 386 帧、逐帧账本/支撑源行、标定复用、连通性 150/151、缺测 6 帧逐帧原因 | FG/RAW_NEW2_*、VERIFY2.json |
| SS05 | 冻结门复评 | FAIL | 十项原样复评：8/10（残余共同节点回归、6 边失败，未软化）；NO_PROMOTION | EFFECT_GATE2.json |
| SS06 | 修复专项 | PASS | 85.0mm ≤100；145/151 ≥136；缺测 6 ≤10 列明；跨缺测 ≤52.6mm；不得以缺测换稳定 | EFFECT_GATE2.json、VERIFY2.json、VERIFY2_DELTA_ARGMAX.json |
| SS07 | 交付+独审 | PASS | MANIFEST/FINAL_SEAL/范围核验；OpenCode 只读审核 1 轮无阻断、模型经 session export 复核；独立执行 NOT_RUN | OPENCODE_REVIEW(.md/_STATUS/_EXPORT)、REVIEW_DISPOSITION.json |

回归与保留失败：MECHANISM 首轮 exit1（rejected 帧无 partitions）→ R2/R3 exit0；TEST_REGIONS2 两轮失败（import 路径、合成构造）→ R3 5/5 通过；REPORT 三轮失败 → R4 通过；均原样保留。

## 未闭合与限制

- 冻结门残余两项不在本修复范围：共同节点回归（TOP_REGION 57.1/41.1、UPPER_A 76.8/63.9、LOWER_A 37.5/23.6、END_A 32.0/21.6 对比冻结基线 RAW_OLD）与持续标定 6 边（仍 5 条 ≥75）；继续须用户另行派发新项。
- OUTER_A 缺测 6 帧（197,210,212,226,323,324，掩码均 5 点）；跨缺测步长 ≤52.6mm；不得解读为等支持精度比较、纯雷达噪声或关节精度。
- REGION_PROTOCOL_V2 分离度字段含 B 侧混入 → REGION_PROTOCOL_V2_ERRATA.json（不改登记文件；勘误文本笔误以字段为准，见处置）；regions2 另有 1 处等价 np.asarray 文本差异（diff 披露）。
- 静态审核无 shell 不能重算 SHA；封存自检与后续复算补齐；独立执行仍 NOT_RUN。
- 设备/物理/部署/采集/训练/模型下载/HR09 NOT_RUN；无 Git 写。

## 交给独立复审

- 现行验收表与本轮变更记录：ACCEPTANCE_V1.md + 本回传 + AUTHOR_REPORT.md。
- 根因诊断/完整入口检查证据：MECHANISM_SUPPORT_RULES_R3 / MECHANISM_DUAL_POP_R3 / VERIFY2 / REGIONS2_DIFF.txt。
- 源码差异与 SHA 证据：FINAL_SEAL.json（source）、EXECUTED_SOURCE、FROZEN_BINDINGS.json。
- 原始日志索引：各 *_RUN.json/*.log；OPENCODE_REVIEW* 与 REVIEW_DISPOSITION.json。
- 当前工单下一步：等独立复审与用户派发；不自动启动下一单或推广。

## 2026-10-18 S07F 开发、自验及OpenCode只读审核交付

- HFUS-TCMS-02-REALDEV-02-S07F，OpenCode 本会话唯一 writer，SUBMITTED，非 ACCEPTED。RESEARCH+ENGINEERING。
- 唯一语义变化：OUTER_A/B 支撑带 [0.33,0.88)→[0.52,0.88)（与 UPPER 同带）；OUTER_A 保持段 900.0→85.0mm、151→145 有效（缺测 6 帧逐帧列明、跨缺测 ≤52.6mm、连通 150/151）；冻结门 6/10→8/10，仍 2 项失败（共同节点回归、6 边）→ NO_PROMOTION。
- OpenCode opencode-go/deepseek-v4.1-flash（session export 复核），exit 0，338.4s，仅 read/glob/grep，无阻断问题；非阻断 6 项处置见 REVIEW_DISPOSITION.json；独立执行 NOT_RUN。
- 逐 ID：{"SS01": "PASS", "SS02": "PASS", "SS03": "PASS", "SS04": "PASS", "SS05": "FAIL", "SS06": "PASS", "SS07": "PASS"}。边界：REUSED_DEVELOPMENT 非独立测试；区域非解剖关节；人体/关节 BLOCKED；纯度/召回 UNKNOWN。
- 可复现与证据索引见 HANDOFF.md；范围 SCOPE_CHECK.json；快照 EXECUTED_SOURCE；MANIFEST/FINAL_SEAL；历史文档追加/前置原字节保留。
