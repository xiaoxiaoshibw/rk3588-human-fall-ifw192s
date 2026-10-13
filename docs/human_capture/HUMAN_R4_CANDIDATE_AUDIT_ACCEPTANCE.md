# HUMAN-R4-CANDIDATE-AUDIT 唯一验收 v1

2026-10-11，用户“下一阶段的开发计划制定并且执行”，本地离线诊断。Codex唯一writer；不训练/采集/推广。初始状态见表；实际结果写新回传。

| ID | 可观察要求 | 初始状态 |
|---|---|---|
| A01 | 全树tracked/untracked baseline及HEAD；只新增离线工具/文档；结束范围审计 | NOT_RUN |
| A02 | S1/S3-near/S6当前非e2e GT、reviewed、索引/会话meta/points/GT/manifest SHA再审；snapshot不覆盖GT | NOT_RUN |
| A03 | 三会话全帧v1/v2/v3运行，输入/模型/实现SHA守卫；未标帧UNKNOWN | NOT_RUN |
| A04 | GT compact→raw正确映射；候选与对象逐点交叠；完整GT ROI及候选概率并报，UNKNOWN不充负例 | NOT_RUN |
| A05 | 接受候选/强分类/当前确认track分开；A/B/retained来源、点数及无真人GT空场输出披露 | NOT_RUN |
| S01 | 映射、非法/越界索引、重复标注去重/歧义、未标帧检查及相关core/融合回归 | NOT_RUN |
| Q01 | Go Flash指定只读独审，先<=60秒probe；未完成不得冒充 | NOT_RUN |
| G01 | 点集差异仅证据，不声称唯一根因/泛化或模型推广 | BLOCKED |
| D01 | 设备/物理/部署/采集/生产未启动 | NOT_RUN |
