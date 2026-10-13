# 独审后来源链加固提交

第一独审已完成：OPENCODE_REVIEW_01.md，指定Go Flash/default DB/plan，真实exit0，R01–R08软件PASS，S02因范围外RF并发写入BLOCKED。

之后matrix_02的外部SHA守卫又检测到RF运行中改写，终止该批（不能验收其partial outputs）。不修改/回退生产RF。在human_core范围追加最小来源链加固：

1. load_production不缓存可变工作树代码；每实例新闭包，额外把globalThis导出写入隔离对象，避免影响host消费者。
2. loader按实际读取的meta/points字节计算SHA，不再重读可能已经变化的文件冒充输入来源。
3. runner每mode开始/结束比较实现SHA及实际输入SHA，跨mode也核对同批实现；变更即报错，不能生成完整manifest。测试通过模拟hash变化验证拒绝，不写生产文件。
4. baseline parity和perf也保留起始SHA并核对结束SHA；运行期间变化不可验收。

tests_03作者自验：7suite/96项exit0（rework21项）。最终矩阵另在runs_03；最终对拍parity_04；性能在负载结束后另跑。尚未到位的文件不能预判PASS。writer再次停止，提交源码另冻submitted_source_sha_02.json。独审仅复核新加固与是否回归旧R01–R08，不改源码/记录，只stdout。

历史runs_01完整SHA对应旧依赖；parity_03跨RF变化窗口，仅作执行记录，不能作为当前来源闭合证据。保留所有失败和partial artifacts。S02原始全冻结承诺仍BLOCKED，不用新版本复验抹去范围外变化。算法/生产资格仍BLOCKED，设备/物理/采集/部署NOT_RUN。
