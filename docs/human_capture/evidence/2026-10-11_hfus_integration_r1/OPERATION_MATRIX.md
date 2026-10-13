# 本轮操作与消费者矩阵

2026-10-11；开发验收标准在派发前冻结，本文只展开覆盖，不替代验收表。

| 操作/输入 | 消费者与预期 | 验收ID | 检查入口 |
|---|---|---|---|
| 传感器NaN/Inf/零XYZ，非零T | 有效性先判；无效raw行不因配平成为有效点 | D01-01 | contracts回归及真实frame映射 |
| 重复XYZ、不同行、compact GT | raw身份保留、双向映射，不靠坐标去重 | D01-01 / D02-01 | 索引契约和待审pointset绑定 |
| 原始输入/GT/模型/import变化 | SHA拒绝或显式BLOCKED；不回填旧结果 | D01-02 / D02-01 / INTEGRATION-01 | manifest和check_assets.py |
| PA硬拒绝/PB score拒绝/无提案 | 全组件留痕；无候选GT仍FN；不同失败层分账 | D01-03/04 / D03-04 | preclassifier组件与strict ledger |
| partial/propagated/UNKNOWN GT | 已标人体召回限定资格；unmatched_unknown不计真实FP | D01-04 / D02-03/06 | evaluator负例与资格manifest |
| 当前accepted/低质union/无当前support/预测 | coverage与purity同时过门；observed/coast分开 | D01-04 / D03-05 | frame候选/track关联与匹配 |
| Float32临界特征/PointNet中心化 | 原模型冻结；输入顺序、中心化、native/ONNX一致性可审 | D01-05/06 | 隔离消费者和固定候选对拍 |
| BG-B→PA/PB/UNKNOWN参考 | 两条链真实消费；PB不再次envelope；UNKNOWN有约束 | D03-01/03 | 隔离engine和实际九会话trace |
| PIPE已确认retention/退出/seek/gap | 仅当前RAW支持重新提案；原双状态owner保持 | D03-02 / INTEGRATION-03 | frozen调用链、reset与轨迹账本 |
| S6 128/187/188/邻帧 | 逐点流向、混簇、score、关联责任，不固定单根因 | D02-02 / D03-04 | 真实失败索引及visual输出 |
| 同session/重复候选/fold/未来 | 单fold；无跨fold复用和未来输入；标签仍待审 | D02-04 | split和重复检测报告 |
| 接口冻结/升版/并行返工 | 各目录唯一writer；消费者SHA不静默变化 | INTEGRATION-02 | dispatch、freeze、owner return |
| D03工程PASS且算法FAIL | 可启D04单轴；D05受人工资格门；不掩盖失败 | INTEGRATION-04 | 第二轮决定与预注册变体 |
| D06组合/D07区域证据缺失 | 一个真实组合而非最佳指标拼接；区域资格BLOCKED | INTEGRATION-05 | 最终实际运行与待审要求 |
| OpenCode短carrier/截断/错模型/写工具 | 完整任务读取及指定模型/只读工具记录才有效 | INTEGRATION-06/07 | 原始jsonl/status/意见处理 |

设备、物理、采集、部署均未授权：NOT_RUN/BLOCKED，不能由离线检查替代。
