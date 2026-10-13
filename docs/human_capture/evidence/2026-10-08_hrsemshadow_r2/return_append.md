

## 2026-10-08T22:36:33.061879+08:00 HR-SEM-SHADOW-R2 证据可信性修复与重验（Codex）

### 本轮信息

- 单writer：本聊天Codex，PC离线；无子代理/OpenCode/改模型。用户明确允许Phase0–4最小修复和复审。
- 状态 **SUBMITTED / BLOCKED，未 ACCEPTED**；离线交付BLOCKED，生产接入仍未授权；WD02待规范裁定，SEM-05～08、10保持BLOCKED。
- 唯一表 `docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md` v1，SHA `3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd`；工单SHA `f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6`，两者未修改。
- 起始master / cfbb80c57508be1a0435fdb92260f698dc763934；dirty和6140起始路径/43,283,465,274字节基线见 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/00_baseline.json`，用户原差异全部保留。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；复用stdlib/既有Node与NumPy，不装依赖。

### 集中诊断与根因覆盖

| 缺陷 | 入口/根因 | 本轮修复/处理 | 保留行为 |
|---|---|---|---|
| SEM-12 | 外部index未绑定、SHA只字段对比、row摘要非内容摘要、显示/票据身份脱节 | 固定独立权威digest+实际raw28B/XYZ重建+receipt绑定+拒绝后清空显示；切帧清拾取row | 新R2入口；R1源码/evidence原样保留；GT真值不伪造 |
| WD02 | H.level额外历史生成源码==当前；源/产物SHA实读完整 | wd02_audit保留原断言，区分正式registration消费契约与历史leveling provenance，提交两案裁定 | BLOCKED；0处理帧，不换job、不重签、不自行放行 |
| SEM-05～08、10 | 人工全帧/实例GT与有效对抗覆盖缺口；05/08上界不足95% | 既有输入必要全帧/负例/边缘重放；逐项依赖和真实分母报告 | 门槛/算法不变，BLOCKED不自动变PASS |

### 实际变更

仅新增 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/` 中review_binding.js（authority/source/content/receipt/validate）、build_review.js、review_template.html、sem12.test.js与必要独立审核/报告/日志；copied审核工具只适配R2输出/基线名。`changes.json`记录全部源码SHA，`delivery_manifest.json`记录新交付SHA。旧finish.py、旧页面和所有R1 assets零修改。本return仅字节追加。

### 逐条验收

| ID | R2结果 | 证据/限制（均在本轮目录） |
|---|---|---|
| SEM-01 | PASS | baseline/data_r2/full_recompute/integrity |
| SEM-02 | PASS | full_recompute30 checks+24ROI; negatives12 samples |
| SEM-03 | PASS | data_r2+full_recompute full-frame/member conservation |
| SEM-04 | PASS | data_audit/recompute trivalues, invalid row disclosure |
| SEM-05 | BLOCKED | 13/244 upper bound; human identity GT absent |
| SEM-06 | BLOCKED | 269/271 proxy; GT absent; WARN |
| SEM-07 | BLOCKED | 281/281 proxy; edge185+cleanup5 identities UNKNOWN |
| SEM-08 | BLOCKED | 1/195 upper bound; HEAD0; GT absent |
| SEM-09 | PASS | 285 frames both branches zero HUMAN |
| SEM-10 | BLOCKED | WD01 GT, valid adversarial coverage, WD02 adjudication unresolved |
| SEM-11 | PASS | 1561 votes + independent actual-frame constraints; original43 collision/88 stale disclosed |
| SEM-12 | PASS | sem12_verified4 accepted/17 rejected; independent_receipts_final; real browser |
| SEM-13 | PASS | separate denominators/proxies/truth/votes and costs disclosed |
| SEM-14 | PASS | actual two-pair digests + necessary regressions38/45/23 exit0 |
| SEM-15 | PASS | final integrity old assets + return prefix |
| SEM-16 | PASS | return/ponytail/reports and authorized stopping point |

- WD02 **BLOCKED_CONTRACT_ADJUDICATION**：12派生产物+raw/report/domain SHA完整；唯一leveling.py历史代码差异，不以诊断exit0计WD02通过。
- 实际命令/exit/stdout/stderr/源码SHA：`commands.md`与同名run/log；最终SEM12 4合法+17拒绝/0失败、34切帧；PL38/0、replay45/0、registration23ID/0（T37-20未跑）。独立receipt34案例/100簇/2358删除点/183340坐标；全1561分支帧/4311簇/12019508成员坐标/9366阶段/1561票重算一致；旧可用448分支帧/2210簇/458区域，52228边缘源row和185+5对账。
- 实际浏览器：篡改拒绝、禁止保存、合法4311索引/3441成员载入、投影/拾取/合成UNKNOWN导出及校验通过，最终切帧状态正确；`browser_ui_status.json`/`browser_review.jpg`。synthetic导出不计真实GT，真实标签0。
- R2早期失败（基线名、结果独占写EEXIST）和ResourceWarning记录保留，最终干净执行为准。R1失败不覆盖。旧资产/return前缀由最终 `docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/integrity.json` + `05_integrity.md`闭合。

### 未闭合与停止点

SEM-05/08上界13/244、1/195低于95%；06/07代理高仍无成员GT。185+5、WD01 P4/WS12 HUMAN归属UNKNOWN；low_bar空输入和格栅未覆盖NOT_RUN；WD02需人工规范裁定。旧负例可信审阅入口依赖与原无效点/Tracker风险登记，不扩大本单。零候选帧外部index没有行的原有载入可用性缺口登记；嵌入空帧可看。

复审采用本writer以独立raw/NumPy逻辑与明确攻击预期核查，无第三方审阅人签署声明。硬件/物理/板端/部署/采集/网络驱动/ML/生产全部NOT_RUN/未授权，不commit/push/reset/checkout/clean、不改生产算法、不签装artifact。现在停在R2证据可复审；仅建议WD02规则裁定、可信人工GT/有效覆盖补齐，必要新算法版本另授权，不推进生产。

报告入口：[docs/human_capture/evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md](../evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md)，依次00_audit、01_sem12_fix、02_wd02_review、03_blocked_revalidation、04_regression、05_integrity及最终manifest。
