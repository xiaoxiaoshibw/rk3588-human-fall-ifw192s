# 多行派审完整性纠正（新证据，不回写前两次）

前两次真实CLI调用/读审日志保留，指定模型确实为Go Flash，但**完整任务说明未送达**。Windows npm `opencode.cmd` 的 `%*` 将多行参数截到首行；本机session export读取actual user message后才发现。

| 调用 | 原说明字符数 | 实际user message字符数 | 完整匹配 | 当前资格 |
|---|---:|---:|---|---|
| OPENCODE_REVIEW_01 | 2112 | 191（含包装引号） | false | 宽范围真实读审参考，原READY保留；不作完整指定任务验收证据 |
| OPENCODE_REVIEW_02 | 1388 | 126 | false | 完整定点任务未送达；保留真实结果/停止记录，不充完整复审 |

首次source_check误判、retention解释误判、技能读取缺事件的原因不能唯一归因此传输问题；但已经足以要求重新完整派审。两次无工具probe为单行，无此截断，工具数均0。

修正：直接执行**同一安装** `C:/Users/30680/AppData/Roaming/npm/node_modules/opencode-ai/bin/opencode.exe`（与cmd包装器实际调用目标完全相同），不经过shell、不换模型/provider/database/auth。每次完成从session export核原提示词完整文本相等及actual provider/model；raw日志核只读工具与技能实际read。辅助脚本新增核验，若不符本次review失败，不报PASS。

第三次任务需要实际读取技能、冻结v2计划和唯一验收，既检查关键架构又逐项复核首审意见；CLI只允许read/glob/grep/list。不能用前两次READY替代第三次结果。生产/旧研究源码、GT、模型、captures、旧证据依然只读。
