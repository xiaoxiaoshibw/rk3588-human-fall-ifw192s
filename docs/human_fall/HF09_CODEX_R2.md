# HF09最终独立复审返工

30分钟原测量与历史证据保留，不需因部署脚本修复重录30分钟。5项独立watchdog已PASS。

1. 当前release只存config/page及human_fall_node.release.py（未使用），start实际启动外部hf07_verify_ws/devel wrapper，core仍从可变工作树导入。rollback只回滚页面/参数，无法恢复代码。请release保存完整所需Python源码及冻结依赖的同哈希副本，start/profile均从当前release的不可变bundle加载（PYTHONPATH优先该bundle，ROS消息依赖可仍用已存在devel环境）。校验实际core.__file__/node路径来自release。legacy无bundle版本明确拒绝代码回滚，不能默默运行最新core。
2. PID校验仅human_fall_node.py名字子串不够，应核对记录的精确node路径和config release路径，防复用PID误停其他节点；拒绝停机不能||true后仍启动第二个同名node。release先检查current/web链接合法，再切指针，失败不能留下半部署。用两个完整已审同代码版本实际start→rollback→start验证路径/PID/页面/原driver不变；版本保留，无删目录。起/停/回滚失败保留非零退出码。
3. 独立脚本evidence/review_hf09_profile_codex.py当前schema bool、坏frame_key、negative/bool latency三方法失败。strict整数header/epoch/version，非法返回None不抛异常；坏performance时间不计样本/有效输出，duration有限正保留。补回归，不改独立断言。
4. Windows203、板202项差异请说明并同步当前源码/测试后跑同一树。不要用文字总结当原始测试日志；本地/板回归、SHA和外层退出码均存真实stdout/stderr。deployment.md与HF09追加第2轮。
5. 正式网页hfPred在track已锁但没有有效position时不能仍绿显“实测”，应显示无有效观测。preview与正式JS同样小修；其余已审UI守卫保留。Codex已打开正式真实页面，将在新版本后连接复测截图；无需你做浏览器。

测量事实：9.647/8.718Hz，p95约146ms，队列4122是启动累计，不是30分钟区间增量。第一行2461→末行4122（10s后到末约1661），全窗口初始计数未记，不能反推精确完整区间丢帧。仅如实分析已有10s序列CPU/RSS/temp分布/内存趋势，不宣称实时门槛已通过。以后collector可记开始baseline/区间增量，不伪改历史日志。

只改上述部署/测量边界，不改候选算法/阈值；默认ground未知/confirmed false、原首页/driver/原bags保持。完成SUBMITTED后退出供Codex最终复审。
