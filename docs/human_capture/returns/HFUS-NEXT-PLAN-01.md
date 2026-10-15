# HFUS-NEXT-PLAN-01 回传

## 2026-10-14 R1 基于现有数据的下一阶段计划

- 用户要求：借鉴算法/架构，比较本项目效果，制定下一阶段开发计划。
- 主控只写新计划/验收/研究证据/回传；cluster_research与pose_research只读审计划，无代码writer启动。
- 状态：SUBMITTED（计划交付）；算法实现/效果NOT_RUN，不报ACCEPTED。
- 当前唯一：[计划v2](../evidence/2026-10-14_hfus_next_development_plan_r1/DEVELOPMENT_PLAN_V2.md)、[验收v2](../evidence/2026-10-14_hfus_next_development_plan_r1/ACCEPTANCE_V2.md)。v1及首次PLAN_REVISE保留；审核见PLAN_REVIEW.md，版本SHA见DELIVERY_SHA.json。
- 入口记录：HF WORKFLOW与HC README仅顶部追加本轮“仅计划”链接；HF REVIEW_LOG末尾追加计划审核结果，保留全部历史。
- 数据预检：DATA_PREFLIGHT.json，八动作1934帧+新空场272帧，18原始文件SHA/帧数/28B尺寸一致；两个背景artifact可读。旧131958原文件缺失保持BLOCKED。
- 基线：branch/HEAD见DATA_PREFLIGHT；完整git状态GIT_STATUS_BEFORE.txt；63相关tracked/untracked源SHA为SOURCE_BASELINE.json，首尾SOURCE_FINAL_CHECK.json；范围有限，不声明整树冻结。
- 技能实际使用：C:/Users/30680/.codex/skills/ponytail/SKILL.md（持续）；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md（本轮读取）。

### 集中诊断与计划变更

借鉴条件图连接为首选；鲁棒配准、弱观测关联和反射旁路分别消融。原实现生产水平网格与实验3D DBSCAN分开。A/B/B_tau区分背景和容差；C/D固定同条件图。先前46帧保留不能替代全量因果。

v1只读审核发现候选选择规则、UNKNOWN分母及单writer表述不足；v2冻结960帧调参/974帧内部比较，明确几何主指标/非退化/平手和失败后新run；固定原始U/K/X评审范围；一个工单所有算法代码由单writer串行写。另补armed期限、事件/显示分离与缺负例NOT_RUN。

### 逐项状态

N01 PASS（仅本轮实际数据预检）；N02～N07、N09～N11 NOT_RUN；N08独立身份/关节GT BLOCKED，几何评分实施NOT_RUN。PLAN_PASS若获审仅表示计划可执行，不改变这些结果。无需运行生产测试来验证文档修改；分组/链接/哈希检查见VALIDATION.json。

### 未闭合

新背景全量A/B/B_tau、条件图C/D、粗骨架/事件和独立语义验证尚未执行。无新算法准确率结论，不默认晋级、不训练/HR-09、不采集部署/设备访问、不改原数据/旧GT/模型/历史输出/生产源、不commit/push。
