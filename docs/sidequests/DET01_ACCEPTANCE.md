# DET-01 v1 — PointPillars / CenterPoint 人体检测离线实验

本文件保留为历史。用户续指四个新会话并要求配平后，唯一现行表为 [v2](DET01_ACCEPTANCE_V2.md)。

授权：2026-10-07 用户要求暂停当前开发、另开分支尝试两个模型；后续指定先使用本机 CPU。Codex 是本单唯一 writer。本单为 sidequest，不启动 HR-09，不属于 HF/GL 或 W03–W09 的验收。

| ID | 要求 | 验证入口 |
|---|---|---|
| A01 | 独立分支/工作区；记录原树含未跟踪文件 SHA；保留原开发改动 | evidence baseline / Git |
| A02 | 正确解码实际 28B 和旧 16B 会话；非法布局/越界/坏数据显式失败 | test_experiment.py |
| A03 | 输入使用显式变换与强度缩放；保留数据和变换 hash；无默认猜测安装角/高度 | export manifest / tests |
| A04 | PointPillars CPU 使用可追溯的含 Pedestrian 权重；真实帧输出框/分数/耗时 | upstream hashes / predictions |
| A05 | CenterPoint 使用含 pedestrian 权重尝试 CPU；如依赖/权重不可达保留原始错误并记 BLOCKED | runtime attempt |
| A06 | 输出保持 source=model；无人工 GT 时不报精确率/召回率或识别人成功 | manifest / result review |
| A07 | 留下 CPU 体素化和旋转 NMS 的负例检查、上游示例推理检查；与上游 GPU 数值一致性未跑需显式标记 | tests / upstream sample |
| D01 | 设备、采集、部署、物理外参验证 | NOT_RUN；本单无此授权 |

本表唯一现行版本 v1。结果见 [本轮证据](evidence/2026-10-07_det01_r1/README.md)；回传见 [DET-01](returns/DET-01.md)。
