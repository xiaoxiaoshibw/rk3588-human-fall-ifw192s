# 九会话人体动作独立目录

动作名称是录制说明，未逐帧确认；自动候选和已有人工参照分开。骨架为源点支撑的区域估计，不是经过标定的解剖关节。

| 会话动作 | 帧数 | 有人工参照的帧 | 小ROI有候选帧 | 全场最佳簇参照覆盖 | XY对照覆盖 | 未标身份点比例 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| S1-empty-with-furniture | 304 | 0 | 0 | — | — | — | BOUND_EXISTING_REVIEWED_LABELS |
| S3-walk-x-near | 258 | 258 | 258 | 98.3% | 98.3% | 6.5% | BOUND_EXISTING_REVIEWED_LABELS |
| S3-walk-y-far | 464 | 99 | 464 | 97.6% | 97.6% | 11.0% | BOUND_EXISTING_REVIEWED_LABELS |
| S4-walk-stop-walk | 239 | 11 | 239 | 98.7% | 98.7% | 2.7% | BOUND_EXISTING_REVIEWED_LABELS |
| S5-turn-in-place | 202 | 6 | 202 | 98.9% | 98.9% | 1.6% | BOUND_EXISTING_REVIEWED_LABELS |
| S6-occlusion | 238 | 71 | 47 | 97.1% | 97.7% | 25.0% | BOUND_EXISTING_REVIEWED_LABELS |
| S7-far-5m | 251 | 12 | 113 | 97.4% | 97.4% | 12.6% | BOUND_EXISTING_REVIEWED_LABELS |
| S8-still-retention-long | 523 | 53 | 0 | 99.9% | 100.0% | 2.7% | BOUND_EXISTING_REVIEWED_LABELS |
| S9-two-person-cross | 126 | 0 | 126 | — | — | — | BLOCKED_INVALID_BINDING |

S1空场为304帧，只有HOLDOUT帧用于背景空场留帧验收；S9旧标签源绑定失败，不生成所谓纯人体参照、不计算GT分数。

若静立/远距会话在小ROI无候选但全场有人，不扩大圈线，不把区外丢失报成背景算法失败。需审核截图ROI坐标与所有旧会话是否同布局。

运动粘连诊断采用当前单帧、近背景比例、紧半径连通碎片、其他簇间距、已标家具混入和未标身份比例；未把“雷达吸引点”当已验证物理机制。
