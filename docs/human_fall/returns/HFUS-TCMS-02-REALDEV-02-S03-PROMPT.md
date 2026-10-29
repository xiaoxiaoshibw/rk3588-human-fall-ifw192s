# HFUS-TCMS-02-REALDEV-02-S03-PROMPT

## 本轮信息

- 工单/轮次/执行者/时间：HFUS-TCMS-02-REALDEV-02-S03-PROMPT / r1 / 本会话唯一文档 writer / 2026-10-17 20:56–21:05。
- 唯一验收：docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_prompt_r1/PROMPT_ACCEPTANCE_V1.md，SHA `fe7ae5047937129e75ebfb2b055cc81c3fa760fb17ad4b805644bdc3792da00e`。
- 执行方式/模型：只写提示词与文档，未运行 S3 代码、未处理数据；模型按环境声明为 deepseek-flash，未切换。
- 状态：**SUBMITTED（仅提示词），非实施、非 ACCEPTED**；S3 实施、外部审查、正式独审均 NOT_RUN。
- 起始 branch/HEAD：master / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；无 Git 写。
- 实际 ponytail 路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。

## 提示词内容

[AI_DEVELOPMENT_PROMPT_V1.md](D:/Code/ldiar/docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_prompt_r1/AI_DEVELOPMENT_PROMPT_V1.md) 是给“没有本聊天上下文”的实现 AI 的自包含提示词，包含：

- 先读清单、策略（ENGINEERING+RESEARCH）、唯一 writer 与模型记录；
- S3 范围与排除项；
- 源/S2 封存/C3D_03/对照/历史 R/t 的 SHA 与冻结值；
- T0–T8 强制顺序：登记 → transform artifact → 新域冻结 → FIT-only M0 → 原阈值重跑 → 验证/271 因果 → 对象同系 → 真实浏览器 → 封存回传；
- G05/G06/G07/G10/G11/G12 建议验收、预算、失败包、防作弊、停止条件；
- 明确“S2 VAL 已曝光、不得当新证据”“不重拟合/不平均/不调门”“不把预览写成验证”“不做 S4”。

## 实际变更（仅文档）

| 文件 | 用途 |
|---|---|
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_prompt_r1/AI_DEVELOPMENT_PROMPT_V1.md | S3 开发提示词 |
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_prompt_r1/PROMPT_ACCEPTANCE_V1.md | PR01–PR08 提示词验收 |
| docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_prompt_r1/PROMPT_CHECK.md | 提示词自检 |
| docs/human_fall/WORKFLOW.md | 顶部追加本提示词条目，原文内容保留 |
| docs/human_fall/REVIEW_LOG.md | 末尾追加自检记录 |
| docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S03-PROMPT.md | 本回传 |

未改源码、配置、模型、GT、data、旧证据/门；追加用二进制 LF，未重演 S2 的换行归一化问题。

## 逐条提示词验收

| ID | 文档自验 | 说明 |
|---|---|---|
| PR01 | PASS | 自包含读入/技能/策略/记录 |
| PR02 | PASS | 输入 SHA/候选冻结/曝光披露 |
| PR03 | PASS | 变换/M0/容差/异常停止 |
| PR04 | PASS | 新域/门/271/失败包 |
| PR05 | PASS | 对象同系/缺失字段/版本 |
| PR06 | PASS | 真实浏览器/点选/NOT_RUN |
| PR07 | PASS | 测试/预算/封存/回传/独审 |
| PR08 | PASS | 防作弊/失败处理 |

S3 实施：全部 NOT_RUN。

## 未闭合与限制

- 提示词不是实施；S3 的 transform、M0、重跑、验证、浏览器、封存均未做。
- 提示词要求新域仍是先验条件选择，且 S2 VAL 已曝光；S3 只能做应用链复核，不称独立验证。
- 3cm 门接近噪声、M0 表示变化、271 前缀失败等风险已写入提示词。
- 地面身份/物理高度/独立 D/人体效果/设备仍 BLOCKED/NOT_RUN。

## 交给 Codex 独立复审

- 提示词/验收/自检：AI_DEVELOPMENT_PROMPT_V1、PROMPT_ACCEPTANCE_V1、PROMPT_CHECK。
- 计划依据：S3_PLAN_V1、PLAN_ACCEPTANCE_V1、INPUT_BASELINE.json。
- 用户实际派发 S3 后，接收 AI 按提示词建立 S3 唯一验收并实施；未派发前不建源码、不跑数据。
