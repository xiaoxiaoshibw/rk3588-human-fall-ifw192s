# R06 性能协议 v1（pure运行前冻结，非改验收门）

外部HFUS-RD-01评测当前未检出运行，但本主控control/guard全账仍运行，暂不启动pure。待所有本控评测/分析完成，保存实际前后进程快照，独立串行9会话native R04 fast / 新wrapped control / guard，每场每variant前5帧统一排除。原50ms p95不降低，原R05超门失败不覆盖或重新评级。

计时仍det.tick原d.total_ms，包括算法自身必要调用/分配。无trace/shadow/owner/GT/逐帧snapshot/逐帧序列化、逐帧日志/读盘/渲染；仅存数字times，完整读取会话和ref/源SHA在计时外；session完成后输出一个result。旧R05每帧计时外序列化银行等仍可能影响下一帧GC，本协议明确移除评测记录压力，全组同样处理，不冒充证明旧时差根因。

native与control算法/评分全字段已新control对R04完整parity才允许执行；native是wrapper成本诊断，control/guard才R06-06门。统一每会话顺序native→control→guard，整个进程单线程串行，不拼接最佳多轮。前后snap只能支持“未检出其他已知评测进程”，不宣称任何全机负载绝对无竞争；发现其他评测即环境BLOCKED/不晋级。

记录源码/模型/输入SHA、Node/platform、样本/quantile公式floor(n*q)/实际child exit，无Windows板端实时声明。新结果自成PERFORMANCE_PURE_V1，不替代旧R05账。若无收益或仍超门，照实FAIL，不再盲重复采样。
