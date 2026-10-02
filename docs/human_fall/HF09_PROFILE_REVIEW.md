# HF09测量器上线前必须闭合

Codex已独立复跑watchdog5/5通过。当前profile_pipeline.py仍有实质测量问题，先修再启动30分钟，以免需要重测。

- 当前latency是独立observer的cloud回调到candidate回调之差，不是实际节点queue/decode/compute耗时；两订阅调度不同甚至输出先到输入。请节点在已审JSON state加入可选performance诊断（node monotonic receive/start/finish、frame_count、queue_dropped、有效输入标志、配置模式），不改算法/冻结health。observer以节点自身时间差算处理p50/p95、queue与receive→finish；此值不含网络/浏览器或publish序列化。若保留observer差值另列真实名称，绝不冒称处理延迟。
- raw seq独自配对在重启/重复seq时会跨帧；使用source seq/sec/nsec和session/epoch，候选/状态去重。坏JSON/未知版本/重复输出不能计有效输出。有效几何处理和ground未验收/fall unknown分别记。
- input_count-output_count不等于实际节点丢帧，可能启动窗口错位/重复输出甚至负数。实际node队列覆盖计数用LatestFrameQueue.dropped；observer观测缺口另名，不把seq跳变跨重启误计巨大丢帧。明确接收/处理计数以及首末窗口。
- duration/window须为有限正值，latency样本内存须有明确上限；CPU读/温度缺失标null，不用NO_OUTPUT当性能通过。在板上30分钟只记录统计。
- 补数值/重复seq不同stamp/未知schema/非法窗口/掉帧计数等有效测试，不只grep。profile和正式node同时以同一已审源码运行，保留版本/config哈希和备份。

启动时合成清理脚本要同时核对验证配置(hf07_verify.yaml)或记录的确切PID，不能仅匹配同一hf07_verify_ws二进制路径，后续正式node可能复用该安装路径。正式节点PID文件需cmdline验证再kill，不泛pkill。

性能门槛和真人标签未冻结，报告只是测量交付。所有旧回归/独立边界保留；修复后继续原HF09，尽早持续30分钟，完成其他文档/回放后回传退出。
