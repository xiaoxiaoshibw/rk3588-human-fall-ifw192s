# 下一阶段方案复核与资料记录 / 2026-10-04

本轮仅规划/查阅/只读设计复核，未启动开发CLI/probe/实验/设备或发布。当前master/cbd0be1保持；算法生产代码、配置、输入与历史结果不动。已有阶段草稿在本轮修订为v2，首代码研究单GL-I06，现场证据GL-E02并行准备但代码单writer串行。

根代理读WORKFLOW、GL-E01收口、现有geometry与GL05契约、actual constrained settings。只读子代理algorithm_plan_review沿ground.py/diagnostics/GL-I05研究代码审查，无文件写入/设备操作，不代替将来的指定OpenCode二审。

已纳入建议：研究线不等待现场；已有均衡采样/约束RANSAC/TLS/独立区域门复用；先关卡拒绝和竞争完整性shadow，确有偏差再局部优化；三个validation frame_group互异且不同FIT；轮数对照保持sampled精炼域，full FIT仅重算支持；K正常完成未稳定与总资源未处理分开；J不能改最大支持NEAR锚点；振荡/后轮越先验不得退回旧成功；开发与最终holdout隔离；条件门未触发可不采用/实验NOT_RUN且经独审确认，不额外造实现。

对只读建议中“0/4/8弱distinct”的措辞作核正：既定10°distinct门下0/4/8是**全部两两相似正例**，0/6/12才是非传递相似链。方案采用正确表述，未把助手判断当未经核对的权威。

## 联网实际读取

| 一手来源 | 本次范围 / 结论 |
|---|---|
| PCL官方SampleConsensus/PerpendicularPlane/MSAC类 | 已打开当前文档；方向约束/有界样本一致性/残差评分可借鉴，不能提供现场up或人体身份 |
| BMVC 2012 Fixing the Locally Optimized RANSAC（官方PDF，11页） | 已读摘要与方法/代价论述；采用局部优化/截断二次评分作为实验候选，不搬图像数据结论 |
| arXiv 2207.11919v2与2108.05560v2 | API返回2条（成功），raw XML与解析JSON保存；读取Patchwork++摘要及作者仓库参数说明。多区域/复杂地面备选，不装库/不套默认高度/速度 |
| 原LO与PROSAC作者PDF链接 | 本次web open返回内部错误，记录失败；已通过官方LO+全文及PCL继续查证，未声称原两篇全文复现 |

数据库只查询arXiv，endpoint见02_paper_metadata.json；官方文档/作者仓库检索另列，不伪称系统综述或多库穷尽。网上资料只支持候选机制，采用门依本项目oracle/反例/独立验证/成本。原始论文数据速度不写成本项目指标。

## 本轮产物

GROUND_LEVELING_NEXT_STAGE_PLAN.md v2；GROUND_LEVELING_ALGORITHM_DESIGN.md v1；GLI06_ACCEPTANCE.md v1/AI_PROMPT_GLI06_CODEX_R1.md；GLE02_ACCEPTANCE.md v1/AI_PROMPT_GLE02_CODEX_R1.md。全部DRAFT_READY，无活动writer、算法实验NOT_RUN，物理缺口仍BLOCKED。正文source/gate分层不变，生产接入/设备采集/部署以后逐项明确执行范围。
