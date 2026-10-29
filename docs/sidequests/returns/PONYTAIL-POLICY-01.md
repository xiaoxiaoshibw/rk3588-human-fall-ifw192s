# PONYTAIL-POLICY-01 回传

## 2026-10-17 · r1 · Codex 单写入者

- 状态：SUBMITTED；本项为项目规范维护，不接管 HF/GL、HC/HR 算法工单。当前唯一 [验收 v1 / 审计](../evidence/2026-10-17_ponytail_policy_r1/AUDIT.md)；SHA 见 FINAL_CHECK.json。
- 本轮策略：ENGINEERING，最小文档修改；小型算法诊断子任务为 RESEARCH，复用现有 TCMS 实现，保留完整结果与 UNKNOWN。
- 实际读取 Ponytail：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；对照读取 Claude 副本 `C:/Users/30680/.claude/skills/ponytail/SKILL.md`，两者内容同 SHA。实际科学规范：`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。全局文件保持。
- 起始 branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a。工作树既有修改保留，起始 Git 状态和全部 Git 可见含未跟踪文件 SHA 在本轮 BASELINE.json / GIT_STATUS_BEFORE.txt；不是 ignored 数据快照。

根因：入口“所有 writer 读 Skill”没有规定阶段，可能将最短实现建议套到未知算法与科学验证。修复入口 AGENTS.md、CLAUDE.md 同步指向一份 [AI_DEVELOPMENT_POLICY.md](../../AI_DEVELOPMENT_POLICY.md)，保留实际路径记录和单 writer；研究完整性优先、整合先做等价验证。无生产源码/配置变更，无数据/GT/模型写入。

验收逐 ID：PP01–PP07 PASS（规范/本机自验）；PP08 新客户端会话实测 NOT_RUN；PP09 ROS/设备/物理/部署/新真实效果 NOT_RUN。工程与感知结论分列，不自行宣布工单 ACCEPTED。

实际验证：TCMS 6、跌倒页 18、采集页 33，均退出 0；小型合成反例显示平移人体候选与平移家具支撑的相同运动证据，人体召回/家具误检/IDSW 为 UNKNOWN，非真实 GT 提升。原始命令/日志及源 SHA 见同证据目录，首尾保护核对见 FINAL_CHECK.json。

限制：规范靠 AI 阅读入口按目标选择，不是新插件路由器；未启动 Claude/OpenCode 会话验证遵循程度；现有深度学习封存和全部工单授权边界保持。未做采集、训练、下载、驱动网络变更、部署、提交或推送；历史证据未改写。后续可直接在已授权开发任务按一句话策略执行，无需为策略另行审批。
