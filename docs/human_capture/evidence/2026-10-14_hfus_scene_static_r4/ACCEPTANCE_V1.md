# HFUS-SCENE-STATIC-02 唯一验收表v1

状态 SUBMITTED，不报ACCEPTED。

| ID | 条件 | 状态 |
|---|---|---|
| ST01 | 1966帧缓存XYZ/源行/变换/原帧绑定 | PASS（缓存几何自验） |
| ST02 | 活动区内补偿输入为0 | PASS（原名义ROI） |
| ST03 | 背景晋升为新增点为0、FG/背景与簇归因守恒 | PASS（当前有效域） |
| ST04 | 1934中央候选帧、32空场无候选/簇 | PASS（复用几何回归） |
| ST05 | 未分类簇无人体节点，全簇同屏与中央姿态限定 | PASS（Edge自验） |
| ST06 | 原录制18个meta/points字节验收 | BLOCKED（文件当前缺失） |
| ST07 | 新活动区外CAL独立标定 | BLOCKED（原CAL帧缺失） |
| ST08 | 完整人体/家具语义身份与准确率 | UNKNOWN/NOT_EVALUATED |
| ST09 | 物理、设备、泛化与独审 | NOT_RUN |

几何检查来自r3/GEOMETRY_CHECK.json；最终UI来自本目录BROWSER_CHECK.json。数字/原始缺失/失败与命令见FINAL_REPORT。
