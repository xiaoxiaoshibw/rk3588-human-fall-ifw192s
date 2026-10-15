# HFUS-PARALLEL-RESEARCH-01 研究验收v1

2026-10-14，状态SUBMITTED。本表只覆盖用户本轮四线路并行研究/联网代码与架构检索；不扩大旧工单、不登记算法实现或部署完成。

| ID | 要求 | 结果与证据 |
|---|---|---|
| R01 | 读取HF/HC工作流，确认最新限制与历史区别 | PASS；RESEARCH_AND_ARCHITECTURE.md §1/2/8；旧SSE-06～08状态保留 |
| R02 | 四线路并行研究，生产源不并发写入 | PASS；背景/聚类/骨架三个只读助手+主控架构，报告§3 |
| R03 | 核查实际本地调用链，区分生产与实验聚类 | PASS；源码核查与SOURCE_BASELINE.json，报告§2 |
| R04 | 背景/异常点作者来源与代码适配检查 | PASS（研究）；报告背景补充表；真实异常原因NOT_RUN |
| R05 | 聚类/关联候选源码、依赖、许可证及边界 | PASS（研究）；报告§4，包含许可冲突/密度/身份边界 |
| R06 | 骨架/事件候选源码及因果性、模型可用性 | PASS（研究）；报告§5，LiveHPS双向与Coming Soon分别标明 |
| R07 | 给出四线路架构、写入归属、A/B/C/D公平对照 | PASS（设计）；报告§3/6/7，实施效果NOT_RUN |
| R08 | 保存检索/相关源与工作树基线，不改生产/数据 | PASS；ARXIV_RAW.xml、ARXIV_QUERY.json、GIT_STATUS_BEFORE.txt、SOURCE_BASELINE.json及SOURCE_FINAL_CHECK.json |
| R09 | 新算法实际1934帧效果/语义准确率/独立验收 | NOT_RUN；本轮研究，缺独立GT，不替代SSE-06/07 |
| R10 | 设备/物理验证/默认晋级/部署 | NOT_RUN；不替代SSE-08，不启HR-09 |

PASS均为本轮研究/设计自验，不表示算法软件验收或ACCEPTED。相关源哈希范围不是整树冻结；引用的上游可变分支须在正式引入时固定commit。下一阶段具体参数与验收门需按实际失败诊断制定，不能用本表直接宣布上线。
