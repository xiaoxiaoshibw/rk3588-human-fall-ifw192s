# DET-01 唯一现行验收表 v2

2026-10-07 用户续指：只用 cap_20261007_215540、215607、215623、215643 四个静止会话，须先配平。沿用 v1 的模型试跑范围；四会话全帧替代早期 203349 抽帧。v1 保留历史。

| ID | 要求 | 验证入口 |
|---|---|---|
| A01 | 独立分支/工作区；原树所有 Git 源文件含未跟踪 SHA；保留原开发差异 | 00_baseline.json / final preservation |
| A02 | 正确解码实际 28B/旧 16B；非法布局/越界/坏数据拒绝 | test_experiment.py |
| A03 | 四会话各自做离线配平，沿用既有地面检测/质量/留帧门；绑定源 SHA；模型输入强度、Z 偏移明确记录 | batch_static.py / leveling reports |
| A04 | PointPillars 可追溯行人权重、本机 CPU、四会话所有帧输出 | four predictions / summary |
| A05 | CenterPoint 含 pedestrian 权重配置的 CPU 尝试；依赖/权重不可达公开 BLOCKED | CenterPoint attempt / runtime log |
| A06 | source=model，不写人标真值；无 GT 不报精确率/召回率；静止会话不走背景扣除 | predictions / report |
| A07 | 体素化/NMS 负例、上游示例检查；GPU 逐值等价未跑独列 | tests / KITTI trial |
| D01 | 设备、采集、部署、物理外参验证 | NOT_RUN；无本单授权 |

入口：[实验 README](../../sidequests/human_detectors/README.md)；[证据](evidence/2026-10-07_det01_r1/README.md)；[回传](returns/DET-01.md)。
