# BG-B UNKNOWN接入约束预登记

2026-10-11，D03首轮真实全链运行前，C提出、主控确认实现选择。

原V3 groupB 对无容差体素匹配的点全部输出keep；其原因不证明射线FREE。本轮不虚构FREE，采用下面独立可审的背景输入策略，固定候选门、XGB69、PIPE-retention与Unique：

1. 参考仍为原空场，每4帧、occ≥0.5、原体素和匹配半径。
2. 有背景匹配点为OCCUPIED删除；无匹配或低支持为UNKNOWN。
3. UNKNOWN只有邻近冻结参考已观测XY柱支持（半径0.4m，复用现有retention空间尺度）才进入原z、cleanup、proposal、分类门。无邻域支持的UNKNOWN不进入proposal；全参考缺失BLOCKED。
4. 裸B mask输出、覆盖约束删除、入链前景、retention回补、质量拒绝各自分账。retention仍只能用本帧RAW点且重新经过候选门；不能把补回计成背景FREE。

这是背景表示＋覆盖约束的研究变体，不能把收益唯一归因容差或宣称与V3裸B语义完全相同。半径未按GT调优，GT只用于事后评价。其物理射线可见性/跨场景合理性UNKNOWN。工程接通与算法目标分别判定，允许FAIL并保留损失/家具反例。A corrected-input控制和C变体都遵守相同传感器域valid索引契约。
