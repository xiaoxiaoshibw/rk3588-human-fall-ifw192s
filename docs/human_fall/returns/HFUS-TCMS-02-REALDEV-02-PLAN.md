# HFUS-TCMS-02-REALDEV-02-PLAN 回传

## 2026-10-17 r1 / Codex / 计划v2交付

- 状态SUBMITTED，未ACCEPTED；本轮仅计划。用户要求重新设计开发路线、记得配平、评估距离图+3D框定。
- 当前[唯一计划验收v1](../evidence/2026-10-17_hfus_tcms_02_replan_r1/PLAN_ACCEPTANCE_V1.md)，SHA256 69679dd272347d1e195d17d1c4ec59eae7155cea96aeee0f4662e27d85fdeeb6；[计划v2](../evidence/2026-10-17_hfus_tcms_02_replan_r1/PLAN_V2.md)。G01–G12只是拟实施条款，全部NOT_RUN，不是已开工的另一验收表。
- 策略RESEARCH（地面/距离图/提取方法）+ENGINEERING（统一坐标/回放/追溯）。实际已读ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific-toolkit-skill路径C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。
- 起始master/HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a；原故意dirty树保持。tracked/nonignored untracked完整hash基线BASELINE_*，排除data与reparse，未reset/clean/commit/push。输入源码/文档逐SHA见SOURCE_INPUTS_SHA。

## 集中诊断与实际变更

| 根因/ID | 受影响入口 | 计划中的修复/保留行为 |
|---|---|---|
| RP01/06 | r01直接RAW XYZ→server→相机，没有全链R/t | 明确完整坐标链、地图/候选/轨迹同系和实际应用门；本轮未改代码 |
| RP04/05 | 旧XY全高度ROI含家具，残差被误当纯地面失败；最大面/RAW轴门可能选错 | 距离图辅助+3D审核/排除/未知、多平面；审核地面域与全ROI诊断分开，旧失败保留 |
| RP05/06 | 候选预览、几何配平、人工身份/物理资格混淆 | 三态显示、独立验证、物理缺件不阻断离线几何工程，旧flags不翻转 |
| RP07/08 | 未闭合配平就推进人体，倾斜与关联/低姿丢点原因混在一起 | 先配平再逐级查f430–439与尾段，公平对照，不宣称旋转能自动修好身份 |

实际仅新evidence文档/规划辅助hash脚本、新回传，WORKFLOW顶部登记与REVIEW_LOG末尾追加。未写任何生产源码/参数/模型/GT/原数据，未调用工作台data导出。旧REALDEV-01封存11源码+49证据SHA一致；旧REPORT/验收/失败均保持。

## 逐条计划验收

| ID | 计划文档自验 | 证据/位置 | 实施/真实效果/设备/物理 |
|---|---|---|---|
| RP01 | PASS | §1；server.py:66/74、app.js:12/15、pipeline.py:200–205与旧AUDIT | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP02 | PASS | §3双表示/多平面和§6对照；SOURCE_REFERENCES | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP03 | PASS | §2、§3.1及§8；Source/opaque/CSR与数据写入隔离 | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP04 | PASS | §3.2、§4；DR01闭合与ground_region_review源行契约 | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP05 | PASS | §3.3、§4；DR02/DR04闭合；旧门不改、新离线身份分层 | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP06 | PASS | §4、§5；DR03闭合；所有消费对象、实际生效与可逆查询 | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP07 | PASS | §6；r01真实LOST与尾段失败保留，四分支和适用消融 | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP08 | PASS | §7 S0–S5/G01–G12、§8预算/测试/浏览器/停止条件 | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP09 | PASS | §2与SOURCE_REFERENCES；原论文/官方文档，当前数据dev-tainted | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |
| RP10 | PASS | 本文/BASELINE_*/SOURCE_INPUTS_SHA/PLAN_FINAL_SHA/回传/WORKFLOW | NOT_RUN / BLOCKED / NOT_RUN / NOT_RUN |


完整位置见[PLAN_CHECK](../evidence/2026-10-17_hfus_tcms_02_replan_r1/PLAN_CHECK.md)。文档作者反例复核DR01–04：提前FIT-only mask防VAL泄漏、跨家族冲突禁止自动推荐、有效帧必须等待配平M0就绪、artifact真实来源不得默认synthetic。v1原文保留，v2闭合；非外部审核/效果复现。

## 未闭合与限制

距离图只是现有XYZ的重组织，不能恢复不可见地面/生成独立证据；平行桌面/地板有歧义需3D源行审核。所有方法和数值门为拟实施计划，尚未新验证；当前整段dev-tainted，不宣称泛化。G01–12/设备/物理NOT_RUN，正式人体/地面身份/独立D效果BLOCKED。没有训练/HR09、模型下载、ROS/部署/采集、驱动网络或Git写。

## 复审与下一步

当前计划/来源/旧资产保护的作者自验见PLAN_CHECK、PRESERVATION_CHECK；外部OpenCode及第二人复审本轮NOT_RUN，不借上一轮意见代签。实际执行仅BASELINE_CAPTURE.py和FINALIZE_PLAN.py的hash/文档检查，无点云算法测试；源与输出SHA见PLAN_FINAL_SHA。后续由用户派发实施时，建议以本计划G01–12建立REALDEV-02唯一实施表和新r02，不自动启动。
