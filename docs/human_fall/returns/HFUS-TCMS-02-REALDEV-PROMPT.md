# HFUS-TCMS-02-REALDEV-PROMPT 回传

## 2026-10-17 r1 提示词制作

- 用户只要求下一步AI开发提示词，追加“前30S无人”“最后几秒躺下 其他时间在走动”“用于开发”。本轮仅原路径meta/格式/尺寸/时间/SHA预检和文档/只读复审，不查看新动作XYZ、不跑算法、不启动实施工单。
- 策略：未知真实效果/开发协议规划按RESEARCH；源预检/工程范围核查按ENGINEERING。实际已读取`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，沿用本聊天已读取`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。根Codex唯一文档writer，助手只读。
- [唯一NP01–NP05验收v1](../evidence/2026-10-17_hfus_tcms_02_realdev_prompt_r1/ACCEPTANCE_V1.md)；[提示词v1](../evidence/2026-10-17_hfus_tcms_02_realdev_prompt_r1/AI_DEVELOPMENT_PROMPT_V1.md)。未来HFUS-TCMS-02-REALDEV-01及RD01–10仅拟派发，不因本文件存在获准开工。
- BASELINE_ALL记13452非忽略tracked/untracked文件字节/SHA，排除data及junction，原status保留；branch/HEAD见基线。SOURCE_PREFLIGHT仅该显式sid，780帧/80.754363s/38298918行/28B；当前新源仅meta与points二文件。原始源不写。
- 用户说明与候选0–20/20–28/28–30秒协议另存；不是实际实验或数值通过线。真实C/D、精确躺下区间、人工点/轨迹GT、地面先验与传感器布局证据仍缺，不以提示词评审判算法/物理通过。

## 本轮信息（2026-10-17 最终v3）

- HFUS-TCMS-02-REALDEV-PROMPT / r1 / Codex唯一文档writer；策略RESEARCH协议、ENGINEERING源预检。实际ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md，科学技能见前文。
- 唯一NP验收v1：docs/human_fall/evidence/2026-10-17_hfus_tcms_02_realdev_prompt_r1/ACCEPTANCE_V1.md，SHA256 `070b9f36a5851a2fc5125874329ee5cefee2ce69d29290e5aaec71bf0ced4eef`；最终提示词SHA256 `df7909244c469e643194e81a55696e7b980d987eff570c8ded440c0ca829e057`。
- SUBMITTED，非ACCEPTED；NP逐条文档自验PASS。新算法/设备/物理NOT_RUN，人体有效性/C/D独立验证BLOCKED。
- 起始master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a，脏树保留，全部非忽略tracked/untracked基线/范围保护见BASELINE_ALL及PROTECTION_CHECK_R1。
- OpenCode实际opencode-go/deepseek-v4.1-flash、standalone/plan三轮exit0；原jsonl记录实际会话，不编造根会话ID。仅文本/契约审查，R3 PLAN_PASS。

## 集中诊断与根因覆盖

| 缺陷/ID | 根因与入口 | 文本修复位置 | 保留行为 |
|---|---|---|---|
| NP03 | 原型全量地图/records/指纹不可直接套真实规模，候选图/模式/源门容易混同 | v3 §3–5，REVISION_NOTES_V2/V3 | 旧源码/断言只读，缺件明确，严格源角色 |
| NP02/04 | 段级动作描述不能充当点GT/独立样本/实际身份确认 | v3 §1/4/5/6 | 原始源/GT不改，身份/效果单列BLOCKED |

## 实际变更

| 文件 | 本轮用途与用户原差异区分 | SHA |
|---|---|---|
| 本项新证据目录 | 源预检、v1–v3、三轮审核/修订/保护，只增新文件 | DELIVERY_SHA_FINAL |
| 本return/WORKFLOW/REVIEW_LOG | 本项当前入口及追加；历史尾/前缀保护 | FINAL_CHECK/DELIVERY_SHA_FINAL |

无源码/配置/模型/GT变更，无算法或服务启动。首次收尾读取JSON默认GBK失败发生于写入前，保留失败记录后用UTF-8重试。

## 逐条验收

| 验收ID | 层级/入口 | 状态/退出码 | 日志与源绑定 |
|---|---|---|---|
| NP01 | offline-document，显式源严格meta/尺寸/时间/SHA | PASS，0 | SOURCE_PREFLIGHT、PROTECTION_CHECK_R1 |
| NP02 | document，用户原话/候选协议/缺件 | PASS，0 | USER_FACTS_AND_CANDIDATE_PROTOCOL、v3 §1/4 |
| NP03 | document，规模/源门/因果/对照措辞 | PASS，CLI三轮0 | OPENCODE_REVIEW_R1/R2/R3、修订说明 |
| NP04 | document，范围/唯一表/分层/未来审查 | PASS，0 | v3 §2/6、DOCUMENT_CHECK_R2 |
| NP05 | offline-document，保护/审核/清单 | PASS，0 | PROTECTION_CHECK_R1、FINAL_CHECK、DELIVERY_SHA_FINAL |

本轮没有算法测试。文档检查不替代算法回归，旧PD/本NP/未来RD不混用。

## 未闭合与限制

- 精确躺下起点、地面/布局证据、人工点/轨迹GT与实际候选确认仍缺。前30s无人/开发用途已收到，不重复问。
- C/D独立数据缺失；当前不具泛化/真实跌倒/预警结论。设备/物理NOT_RUN。
- 未来用户实际派发后才登记REALDEV-01/RD；先继续不依赖缺件的工程/原始诊断，文档不自授权。

## 交给Codex独立复审

- 唯一NP表及REPORT逐ID；原始审查请求/jsonl/stderr/exit与旧版本保留，R3仅最终措辞PLAN_PASS，非独立效果或人审。
- 根因/入口审查及两版修订说明、BASELINE_ALL/保护与最终SHA清单可查。
- 当前下一步：交付v3提示词；不自动开始算法。
