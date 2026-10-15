# HFUS-SCENE-CHANGE-01 唯一验收表 v1

状态 SUBMITTED，不报 ACCEPTED。

| ID | 条件 | 状态 |
|---|---|---|
| SC01 | SYNTHETIC 抖动/新点/退化/越界/空输入/非法输入 | PASS（自验） |
| SC02 | 1966 帧源成员/显示 XYZ/粗节点支撑 | PASS（自验） |
| SC03 | 已匹配背景因补偿晋升为新增点为 0 | PASS（当前有效域，自验） |
| SC04 | 1934 动作帧目标覆盖，32 空场留帧无目标 | PASS（几何候选，不是身份准确率） |
| SC05 | 原同页九会话/切换/跳帧/源行/历史默认 | PASS（Edge 自验） |
| SC06 | 完整人体/家具身份与污染率 | NOT_EVALUATED |
| SC07 | 物理位姿/地面/设备/泛化/独立审阅 | NOT_RUN |

数字与失败见 FINAL_REPORT.md；SOURCE_CHECK.json 和 BROWSER_CHECK.json 是本轮检查。首轮失败证据只读保留，无阈值放松换取 PASS。
