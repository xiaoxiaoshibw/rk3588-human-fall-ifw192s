# HF-REAL-01 回传（追加记录）

## 2026-10-13 / R1 / Codex唯一writer / SUBMITTED

用户明确真人新会话“需要先配平再去背景，然后再分析，先借助你的视觉”，承接首版追踪倒地识别。唯一验收 [v1](../evidence/2026-10-13_hf_real_01_r1/ACCEPTANCE_V1.md)，[完整报告](../evidence/2026-10-13_hf_real_01_r1/FINAL_REPORT.md)，回放 http://127.0.0.1:8929/ 。

RF01/03/04/05/06/07作者自验PASS（各限定见报告）；RF02 094333 PASS、093958 FAIL不接入；RF08独立审核NOT_RUN、真人精度/泛化BLOCKED、设备/物理/部署NOT_RUN。未ACCEPTED。

源sidequests/human_fusion_lab_next/real_fall/r01；基线master/026e06303f60ed1bbe4ddc4d037836db68da6d27，全树19201 SHA非原子；SOURCE_AND_END_BOUNDARY已核已有载入依赖和两输入无SHA变化，记录非全树二次冻结。没有Git写、采集、部署、GT/模型或原始数据修改。

核心链：已有自动floor v3/同域三法→前10帧排除视觉人体区启动参考→已有前景删除→视觉种子因果3D组件关联→原HF06未开启确认状态+明确未验证prototype告警。154/154初始化后候选关联，不能冒充身份正确率；f72/7.460271s一次prototype事件，起身恢复。背景非已确认空场，残留家具公开；不使用视觉倒地时间或未来帧生成事件。

2审计tests、全493579前景源行独立核验、HF06 20tests -B -W error、JS语法/3.8AST均exit0；实际headless Edge WebGL四记录/四非法400、play/pause/seek/模式/视角/告警/恢复通过。CUA缺路径与首轮favicon404失败保留，browser_r2后续通过。实际检查/源码SHA/未跑项见完整报告；未外派独审。

ponytail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md。下一步同位置空场确认后新版本重做背景，并补独立困难负例与身份/动作人工参照；本首版不替代HFUS-D05未收口状态。
