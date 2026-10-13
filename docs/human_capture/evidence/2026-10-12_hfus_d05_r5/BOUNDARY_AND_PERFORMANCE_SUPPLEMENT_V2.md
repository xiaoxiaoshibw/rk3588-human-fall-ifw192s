# R05 结束边界/性能竞争补充（追加纠正）

ENDING_BOUNDARY child4956实际exit0，15463初始baseline之后没有既有范围外SHA变化或缺失；但新增42个范围外文件，来自 sidequests/HFUS-RD-01/ 与 docs/sidequests/evidence/2026-10-12_HFUS_RD_01_r1/。本主控没有创建/修改它们，不删除或干预；作者来源不作推断。完整路径/SHA在FINAL_TREE_SHA与BOUNDARY_COMPARISON；非原子扫描，无全树冻结宣称。

11:55进程快照确认存在HFUS-RD-01 d3_classifiers与d2_cluster_ablation运行，落盘快照PID23768/32080；此前屏幕读回曾有30468但该PID未进入当前落盘快照，不把它当该快照证据，属于本轮外部工作，不停止它们。R05真实性能时间10:50:00–10:54:01；外部common/d1工具10:48–10:49落盘、D1_LAYER_SUMMARY10:51落盘，与该时间窗口重叠。目前不能证明此前性能实跑无外部评测竞争，也没有证据断定其实际CPU负载或是时差根因。

因此AUDIT_READY及brief01中的“无竞争”只能指本主控内部FULL_COMPARISON→CONTRACTS→PERFORMANCE串行，不足以宣称全机无竞争。本轮保留实际控制8/9、新版6/9 p95超50ms的FAIL结果；性能环境资格额外BLOCKED，待外部评测退出后另登记串行对拍，不能通过重跑覆盖本次FAIL。不把这当算法失败或传感器极限的解释。下一轮真实精度可以继续工程诊断，但纯性能不在外部评测竞争时运行或晋级。

浏览器V2真操作已完成且独立verify_browser_v2 exit0，26观察中23已加载三窗对齐，3加载中排除、九会话、console[]。旧cross-tab错误不进当前结论。下一轮已知反例far41偏移.411m仍满足拟议条件，f43–52十次回退必须完整实跑。
