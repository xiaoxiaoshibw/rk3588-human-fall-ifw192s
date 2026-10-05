# 本次恢复检查的共享树差异

13→16 manifest观察到既有.mirasim/limb_server.log、pc_apps/human_limb/limb_lib.py、pc_apps/human_limb/run_session_limb.py变化。本轮root只运行snapshot/无工具probe/只读日志提取，14probe没有任何tool/session事件，生产writer未启动；没有对这些路径写入命令。它们为范围外共享树变化，保留、不归因、不回滚。不要把“主线源码未改”表述为“全共享树无差异”。

主线接回十SHA、冻结core/config、Windows src/CMakeLists.txt表示及HEAD需以本次最终verify为准；主线未新增constrained-config代码/newconfig/newtests，旧实现与旧回归证据继续适用。新增本次证据均本轮新文件，旧服务/诊断/复审证据没有覆盖。
