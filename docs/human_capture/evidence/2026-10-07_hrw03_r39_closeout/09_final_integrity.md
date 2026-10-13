# 收尾完整性与观察到的并发变化

**PASS：264 个受保护原文件逐SHA相同**，包括本实验两会话meta/bin、绑定leveling文件、registration四文件及既有历史证据/冻结数学/验收表。PL仍精确只有三个诊断表达式的改动，包含原换行保持，SHA=af4cdea6d35c73633b12b0d230f3e91f8ba606d9e42fb2ba69bd4083b4af14e5。

**全仓并非只发生本轮授权变化。** `09_scope_check.json` 观察到另有 28 个范围外原文件变更/消失，以及 9 个范围外新增文件。这些路径从未由本轮脚本/命令写入，不能把全仓变化冒称本writer所为或冒称全仓SHA未变；也不推测操作者身份。已保留现状，没有恢复或删除。

范围外路径包含其他三份旧会话 `cap_20261002_163621` / `cap_20261002_165321` / `cap_20261002_233210` 的文件消失、新会话 `cap_20261007_154545`、Console构建/发布、PC capture/fetch、HC和WebUI文件。精确前后SHA/删除状态见 `09_final_integrity.json` / `09_scope_check.json`。本轮绑定的 `223757` 与 `203349` 未受这些变化影响，已单独重核。

新增GT格式回归6项PASS：UNKNOWN31保持未闭合；错source、artifact、seq、重复point、自动ground标签均拒绝（预期exit1）。测试夹具仅在临时目录、标记SYNTHETIC_SCHEMA_TEST_ONLY，不是人工GT，不能据此放行。

viewer初始浏览器渲染已查看，三窗点云/31点表/257变化行可见，初载无console warning/error。未生成实际人工语义标签；实体脚腿/地面仍UNKNOWN。最终状态仍REWORK_REQUIRED。
