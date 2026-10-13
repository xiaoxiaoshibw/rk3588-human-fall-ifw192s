# 独审补证范围（不改原报告/验收表）

接受：补充非共线无可行四元组的全搜索实测与计数；补重复、并列、v3采用修复后v2四区的路由测试；把测试脚本自身指向candidate/frozen，以便独立重现。candidate生产源码与补丁不变。

澄清：05的32项是合并运行，包含7项选择器及所有floor suites；完整argv、PYTHONPATH、-B/-W error和退出码已在candidate_regression_05_command.json保存。06补具名verbose日志和test/candidate SHA。不能从简略stderr未列名称推断未运行这些测试。

B07资料version/help/models/effective permissions/argv/stdout/stderr/exit/session export已实际保存；模型因白名单未读到不能断言这些文件不存在。此次开放已有准确路径及baseline/guard/source绑定供补审。独审当然仍未执行SHA，完整性由作者实际复算负责，不假称双份全量SHA执行。

v3联动边界：v2原来成功时新旧完整结果保持；v2原来假拒绝的场景修复后可直接给25cm合格四区，v3按原控制流原样返回这些四区，不再进入15cm fallback，这是预期行为改变。v3自身源码/15cm purity未变不等于它在所有旧失败场景中的选择路径逐字不变。121647原v2已成功，仍原样四区并保持TLS拒绝。

原report/meta/输入SHA绑定位于01_baseline.json；session_probe在运行前实际校验，不是单靠写BLOCKED字符串。只读物理性仍UNKNOWN。旧报告保留，补审针对补充证据，不覆盖原失败判断。
