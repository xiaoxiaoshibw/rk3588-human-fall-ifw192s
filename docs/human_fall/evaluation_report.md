# HF-08 固定规则评测报告（R1）

- 状态：**SUBMITTED**，待 Codex 复审；不代表本工单 ACCEPTED。
- 数据版本：`hf08-r1`；评测器 schema：1。
- 当前真实跌倒性能结论：**不可计算 / 待人工标注**。授权板上有 4 个 HF-01/02 传感器 bag manifest，但不含 `/human_fall/state` 或 `/human_fall/event`，label path/hash 均为 null；板上工作区未发现 `events.jsonl`。不确认其中是否有人、身份或动作。4 段均只入待人工核实清单，真实 TP/FP/FN、precision、recall、false alarms/hour 全部 `null`，不可把 synthetic 表格当成真实表现。
- 数据目录和缺项登记：[dataset_manifest.json](dataset_manifest.json)。只登记匿名目标别名，不含原始人体点云，也不建立跨 session 身份库。

## 固定计算规则

- 所有 onset、预测、负例区间与观测区间都必须处于同一个显式 `event_time_domain`；每 session 同时写 `prediction_time_domain` 与 `labels_time_domain`，不一致即拒绝。当前契约域为 `device_stamp_s_unanchored`。事件延迟是 `prediction.time_s - label.start_s` 的有符号差值，不是主机、网页或端到端延迟。
- Synthetic fixture 必须标记 `labels_status=known_synthetic`；它只验证规则数值。offline/device 的性能指标必须为 `human_reviewed`，无标签必须为 `pending`；工具拒绝把 synthetic 标签作为真实性能标签。
- 一对一事件匹配容差固定为 **±1.0 s（含边界）**，按 session、`time_epoch` 和**人工复核的目标别名**绑定。预测目标通过 `event_target_bindings` 逐事件填写；不从 track ID 推断身份。冲突时使用最大匹配数的确定性增广路径算法，重复预测只能匹配一个真值，其余计 FP。
- `precision=TP/(TP+FP)`、`recall=TP/(TP+FN)`。分母为零时返回 `null`。无人工标签始终 `pending_annotation`、指标 `null`；显式空标签但无已标注负例时间为 `no_data`，也不视为通过。
- 批次聚合按 `dataset_kind + split_role` 分开；其中任一 session 标签待定，该组聚合性能指标整体置 `null`，避免只汇总已标注 session 形成偏差。
- false alarms/hour 只使用**人工确认负例区间**内未匹配预测数，并以每个 epoch 内合并重叠后的负例秒数为分母；epoch 之间分别合并再相加。负例时长为零时返回 `null`。正事件区间与负例区间重叠会被拒绝。
- latency p50/p95 使用已匹配有符号延迟的线性插值分位数；输出延迟样本可人工核算。身份切换只由人工复核的 `(target_id, track_id, time_epoch, time_s)` 序列逐目标/epoch 计算。有效观测时长为 `observability=valid` 区间并集；同时返回区间总并集和有效比例，无区间资料返回 `null`。
- 数据分割角色随每个 session 保存。相同 `split_group` 不允许跨角色；该组必须代表同一连续采集/人员日期的所有片段，工具不靠相邻帧自行推断分割独立性。盲测失败必须保留，不能更改标签或移除困难片段。
- offline/device session 还必须附预测源码、冻结参数、派生预测数据和人工标签的 artifact path + SHA256；缺 hash 会拒绝计算。输出保存输入 JSON SHA256、评测器源码 SHA256、固定参数和 split roles。脚本只用 Python 标准库，不接触 ROS、网页或原始点云。

## Synthetic 手算例（仅验证数值/规则）

输入：[hf08_synthetic_events.json](../../src/human_fall_detection/tests/hf08_synthetic_events.json)。2 个真值 onset（10.0、10.8 s），4 个预测，目标绑定均指向匿名 `person-a`，负例区间 20–30 s；容差 ±1.0 s。匹配 `truth-1↔pred-near-2`（+0.1 s）、`truth-2↔pred-near-1`（−0.1 s），early 与 negative 两条未匹配：

| 项 | 结果 | 手算说明 |
|---|---:|---|
| TP / FP / FN | 2 / 2 / 0 | 每条 truth 最多配一条 prediction |
| Precision / recall | 0.5 / 1.0 | 2/4；2/2（仅此 synthetic fixture） |
| Negative FP / negative seconds / FP per hour | 1 / 10 / 360 | 1 ÷ (10/3600) |
| Signed delay samples; p50 / p95 | −0.1, +0.1 s; 0 / 0.09 s | 2 样本，线性插值 |
| Adjudicated track switches | 1 | `t0001 → t0002` |
| Valid observation / observation window | 5 / 8 s = 0.625 | 区间并集，valid 5 s、总计 8 s |

以上只有固定事件表的程序计算结果，不是从 LiDAR 点云回放，也不是人体性能、盲测或板端测量。原 JSON 报告与两次重复输出位于 [HF08 evidence](evidence/2026-10-01_autonomous_hf08_r1/)；两次输出 SHA256 均为 `c61d121a46ee2460f9f2e8820f7f86b6f93d2c1e43fbb745353fa416cc18299c`。

## 复跑

从仓库根目录运行（Python 3.12.10 / Windows 本地纯函数环境）：

```powershell
python -B -W error -m unittest src.human_fall_detection.tests.test_hf08_evaluate_sessions -v
python -B src/human_fall_detection/scripts/evaluate_sessions.py `
  --input src/human_fall_detection/tests/hf08_synthetic_events.json `
  --output docs/human_fall/evidence/2026-10-01_autonomous_hf08_r1/synthetic_report.json
```

批量真实数据使用同一 schema，把经审查的派生事件 JSONL 用每个 session 的 `predicted_events_path` 引用（支持 HF-07 `start_source_s`，并校验该 JSONL 与 `artifacts.prediction_data.sha256` 一致），人工标签保存在 versioned input；输出文件名另指定。输入数据至少要有 session/epoch、时间域、数据类型、`split_role`/`split_group`、人工事件标签、逐事件人工目标绑定、负例区间和预测源码/冻结参数/派生数据 SHA256。缺失的标签/区间必须用 `null` 表示未提供，不能用空数组代替。一个人/日期/连续采集组的相邻片段不得拆到不同角色。

## 真实运行、网页和待办

- **本地 synthetic evaluator：实测**，固定输入两次产生相同 JSON SHA256 `c61d121a46ee2460f9f2e8820f7f86b6f93d2c1e43fbb745353fa416cc18299c`。细节见 `synthetic_report_run1.json`、`synthetic_report_run2.json`。
- **既有回归：实测**，`human_fall_detection/tests` 185 项通过；`human_follow_calibration/tests` 2 项通过。纯本地 Windows Python 3.12.10，不是 RK3588 ROS/device 评测。
- **板端/离线真实跌倒评测：NOT_RUN / BLOCKED（缺 HF state/event 输出与标签）**。只读板端清单显示 `hf01_verify`、`hf01_sigint_r2`、`hf01_sigint_r2b`、`hf02_timebase_20260930` 四段健康/时间基准采集，按 `dataset_manifest.json` 保留各自 bag/manifest SHA256、帧数与长度；无 bag 被复制、打开或回放。先人工核实是否有人及动作/匿名目标，再补派生 event JSON、冻结配置/源码哈希、负例小时和 split roles 后评测。
- **网页第 3 轮修复后复测：本次 NOT_RUN，由并行 Codex 实际复测负责**。此前记录的浏览器选择/解除/基线流程仅说明先前版本实际链路；本报告不替代修复后刷新、框对齐、断流/重连和事件对应证据。已有合成 ROS 选择回执探针 `evidence/2026-10-01_autonomous_hf07_11_r1/09_wire_probe.txt` 是协议链证据，不是本次网页视觉或真人验证。
- **独立盲测、点云回放延迟和设备观测时长：NOT_RUN**。未提供冻结参数对应的实际样本、负例标注及授权板上输出；synthetic 无法代替这些数据。

## 开发期失败记录

首轮评测器检查曾捕获 pending 标签无预测时误报 `no_data`；已修为始终 `pending_annotation`。另一次断言把两个 epoch 的相交负例区间误算为 20 s；按规则每 epoch 内并集再跨 epoch 相加应为 25 s，已更正人工期望值。保留摘要见 `evidence/2026-10-01_autonomous_hf08_r1/hf08_development_failures.md`；最终所有测试通过。
