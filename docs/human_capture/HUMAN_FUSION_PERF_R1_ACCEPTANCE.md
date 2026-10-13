# HUMAN-FUSION-PERF-R1 唯一验收表 v1

2026-10-11；Codex唯一writer，本地离线性能闭环。结果填写新回传，旧R2失败不回填。

| ID | 可观察要求 | 初始状态 |
|---|---|---|
| P01 | 全部tracked/untracked SHA及branch/HEAD；保存优化前engine原文；结束范围审计 | NOT_RUN |
| P02 | 完整S3-far逐层热点、前后性能；预热5帧，同机同口径，不减少帧 | NOT_RUN |
| P03 | 优化前后六指定会话全帧v1/v2候选点序/点集/概率/决策/track/事件一致，输入及代码SHA守卫 | NOT_RUN |
| P04 | 六会话FUSION两模型P95<50ms且heapUsed<1500MB；RSS/external另报，失败保留 | NOT_RUN |
| S01 | core与融合相关回归；真实命令及退出码；生产/模型/GT/数据不写入 | NOT_RUN |
| Q01 | 指定Go Flash只读独审；未完成如实NOT_RUN/BLOCKED | NOT_RUN |
| G01 | GT/模型推广资格继承BLOCKED，不以输出等价宣布精度改善 | BLOCKED |
| D01 | 设备/物理/部署/采集无本轮授权 | NOT_RUN |
