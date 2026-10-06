# GL-S02 细粒度 ROI / v1

2026-10-05 用户授权"很好的开始修法"。只新增细粒度 ROI 选择；A 层身份与 B 层门限均不修改。writer OpenCode（opencode-go/deepseek-v4.1-flash，本会话）；外部独立复审 NOT_RUN，不自行宣布 ACCEPTED。

| ID | 可观察要求 | 覆盖/证据 | 当前结果 |
|---|---|---|---|
| A1 | 合成回归：①25cm 全脏、15cm 有 9 个干净盒且可选 4 个分散区→v3 成功（kind v3）；②密到 15cm 也无干净盒→`INSUFFICIENT_CLEAN_ROI_SUPPORT`；③散片身份失败仍 `floor_regions_invalid`；④v2 可达时 v3 逐字返回 v2；⑤v1 可达时逐字返回 v1。全部 `-W error`。 | `floor_roi_test.py` + 日志 | 实施中 |
| A2 | 223757 golden：v3 入口在真实 capture 上成功（kind v3，四区间距 ≥0.5m、独立 4、条件数 ≥0.1）；旧 v2 入口对同数据仍 `INSUFFICIENT_CLEAN_ROI_SUPPORT`（frozen 证据）。 | S02 evidence 真实数据脚本 | 实施中 |
| A3 | 223757 全流程：auto `run_job` 在本数据上 ready，三法全 valid、`recommended=tls`、全帧产物落盘；不降门。 | S02 evidence（真实 job 报告） | 实施中 |
| A4 | 三个在范围会话（203349/203135/202456）不回归：v3 入口逐字返回 v1 结果；全量回归通过。 | S02 evidence + 全套件日志 | 实施中 |
| B1 | B 层契约只增不减：细粒度门=25cm 门（厚度/法向/RMS/贴面逐字相同；每帧点数按面积折算 30→≥20，且 ≥ 下游 holdout 每区下限 20）；间距 ≥0.5m、独立 4、条件数 ≥0.1 一个不降。 | 源码审查 + 测试断言 | 实施中 |
| B2 | `floor_sheet.py` 与 `floor_detector.py` 内容 SHA 不变（v1/v2 冻结）；v3 只在 v2 报 INSUFFICIENT 时接管。 | SHA 对照 | 实施中 |
| C1 | 失败/成功语义：A 失败→`floor_regions_invalid`；双粒度不足→`INSUFFICIENT_CLEAN_ROI_SUPPORT`；成功→kind `lowest_floor_sheet_v3_fine_roi`、全高度保留、无人工参考。 | 测试 + golden | 实施中 |
| C2 | 消费者：`validation.py:floor_identified` 接受 v3 且 v1/v2 分支不变；`leveling_test`/`validation_test`/`floor_sheet_test` 全回归通过。 | 全量测试日志 | 实施中 |
| C3 | 审计：auto `code_files` 纳入 `floor_roi.py`；v3 候选含细粒度证据字段（grid、clean_boxes、min_sep、condition、selected 盒指标、sheet 摘要）。 | 源码审查 + 测试 | 实施中 |
| S01 | 流程：ponytail 已加载记录；基线 SHA；回归日志；不越界（不改 webui/captures/旧证据；不 commit/push/reset）。 | `returns/GL-S02.md` + evidence | 实施中 |
| D01 | 设备/物理/采集/部署 | 本单只离线软件 | NOT_RUN |
