# HFUS-TCMS-02-REALDEV-02-S03-PLAN

## 本轮信息

- 工单/轮次/执行者/时间：HFUS-TCMS-02-REALDEV-02-S03-PLAN / r1 / 本会话唯一文档 writer / 2026-10-17 20:47–20:55。
- 唯一验收：docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/PLAN_ACCEPTANCE_V1.md，SHA `4f421409dafc0b9a58d109a2d835bb8c8b7880210e0ee7039b0a721ddaa3489c`。
- 执行方式/模型：仅文档规划，未运行 S3 代码或数据；模型按环境声明为 deepseek-flash，未切换。
- 状态：**SUBMITTED（仅计划），非实施、非 ACCEPTED**；S3 实施、外部审查、正式独审均 NOT_RUN。
- 起始 branch/HEAD：master / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；未做 Git 写。
- 实际 ponytail 路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。

## 集中诊断与计划依据

| 来源 | 结论 | 对 S3 的约束 |
|---|---|---|
| S2 报告/封存 | C3D_03 4/4 FIT + 3/3 VAL，VAL RMS 0.8–2.6cm；DIMG_01 3/3；旧 TLS 1/3 | S3 固定 C3D_03 主候选，不重拟合、不平均 |
| S2 限制 | 审核片先验条件选择、VAL 已曝光、非独立真值 | S3 另选新域，并承认仍非独立；不把相容当验证 |
| PLAN_V2 §4–§5 | 新地面与 M0 全部就绪才解锁；271 最早可能帧 | S3 因果解锁 271，前缀失败即降级 |
| S2 距离图 | 洞 92.8% 是表示稀疏 | S3 不把洞当遮挡/无地面 |

## 实际变更（仅文档）

| 文件 | 用途 |
|---|---|
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/S3_PLAN_V1.md | S3 计划正文（范围、候选冻结、变换、M0、因果、验证、页面、预算、风险） |
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/PLAN_ACCEPTANCE_V1.md | P01–P10 计划验收 |
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/PLAN_CHECK.md | 计划自检 |
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_plan_r1/INPUT_BASELINE.json | S2 验收/协议/报告/封存/候选/域/历史 R/t/源 SHA |
| docs/human_fall/WORKFLOW.md | 顶部追加本计划条目，原文内容保留 |
| docs/human_fall/REVIEW_LOG.md | 末尾追加计划自检记录 |
| docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S03-PLAN.md | 本回传 |

未改源码、配置、模型、GT、data、旧证据/门；S2 封存为时点封存，本轮追加只改变 WORKFLOW/REVIEW 的当前 SHA，不改变 S2 交付内容与 S2 封存时的结论。

文档 SHA：

| 文件 | SHA256 |
|---|---|
| S3_PLAN_V1.md | `e2effa724633771460b4e1ca921fd35bf9a1d81e1241d39ed4f2fd3300c17931` |
| PLAN_ACCEPTANCE_V1.md | `4f421409dafc0b9a58d109a2d835bb8c8b7880210e0ee7039b0a721ddaa3489c` |
| PLAN_CHECK.md | `5d7fd54be46778accdff07c975e8139e6a711fdfa0e1213564e416db29aa97be` |
| INPUT_BASELINE.json | `ababa22ffae58a8d098004a7c364792f299b2aa71021ede35f052305b5e75361` |

## 逐条计划验收

| ID | 文档自验 | 说明 |
|---|---|---|
| P01 | PASS | §3/§15 范围与排除项 |
| P02 | PASS | §4 候选冻结与暴露披露 |
| P03 | PASS | §5 基底/R/t/退化/版本 |
| P04 | PASS | §6/§7 FIT-only M0 与 271 解锁 |
| P05 | PASS | §8 对象同系/缺失字段 |
| P06 | PASS | §9 新域/门/失败包 |
| P07 | PASS | §10 三态/页面/反查 |
| P08 | PASS | §12 测试/预算 |
| P09 | PASS | §13/§14 交付/失败/独审 |
| P10 | PASS | §13/§15 停止条件/非目标 |

S3 实施：全部 NOT_RUN。

## 未闭合与限制

- S3 尚未实施：transform artifact、M0 重建、应用链重跑、新域验证、浏览器、封存均 NOT_RUN。
- S3 新域仍是先验条件选择；S2 VAL 已曝光，S3 不能声称独立验证。
- 3cm 门接近观测噪声的风险已列入；若失败只报告，不事后放宽。
- 地面身份/物理高度/独立D/人体效果/设备仍 BLOCKED/NOT_RUN。
- 正式独立复审 NOT_RUN；本轮只交计划，不自动进入实施。

## 交给 Codex 独立复审

- 计划/验收/自检：S3_PLAN_V1、PLAN_ACCEPTANCE_V1、PLAN_CHECK。
- 输入基线：INPUT_BASELINE.json（含 S2 封存 SHA `740342ec…e1d`）。
- 下一步：用户实际派发 S3 后，按本计划建立 S3 唯一验收并实施；未派发前不建源码、不跑数据。
