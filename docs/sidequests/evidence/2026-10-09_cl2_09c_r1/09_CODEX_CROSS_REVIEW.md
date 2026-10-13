# CL2-09C Codex 交叉裁决

2026-10-09 Asia/Shanghai。Codex裁定：逻辑FAIL=无。状态仍 SUBMITTED / STOPPED，不宣称已获生产接入许可。OpenCode 原话见 08_OPENCODE_REVIEW.md，未修改其报告。

## 独审事实与结论边界

实际 CLI1.18.35 / opencode-go/deepseek-v4.1-flash / session ses_edf09e4a0ffe2L1WVp04Yusuw5；raw 进程 exit0，完整 export exit0，actual assistant model 单一且 last_finish=stop，结束 AUDIT_COMPLETE。有效 agent 只有 read，其他工具 false，逐文件 Git-project-relative/absolute 白名单；目录 read 被拒绝，未扩大为全树权限。

审计员读取了基线/候选/patch/测试/基准/会话和作者分析，C03/C04 给出部分最小间距上界、原序并列及首对共线剪枝等价证明。没有逻辑 FAIL。其“全定义域证明”应以本函数实际契约为界：由 _clean_cells 生成的有效整数格坐标，物理工作范围受 ±100m 限制；没有把非法 NaN/Inf 直接拼装的 clean keys 当作新增受支持 API，也不把抽样差分当板端证明。

OpenCode 未执行数值/SHA，因此其执行 UNKNOWN 保留，不能假称独审员复跑了 41 项或重算哈希。Codex 实际执行层：41 项 -W error exit0、同进程无插桩基准逐轮 exact dict、原 bin 重建与最终 clean keys SHA 绑定，以及 375 个保护资产逐 SHA 复算。C08 的运行事实由 raw、debug agent、permissions 和 export 补闭合；C09 最终 seal/return 在审计之后完成，不要求模型自证其会话或预判未来产物。

## 非阻塞观察处理

| 原意见 | Codex 裁定与处理 |
|---|---|
| 补丁注释未单列 O(n²) 内存 | 07_AUTHOR_ANALYSIS.md 和 README 已明确距离表 O(n²)；最终报告同样列出。无需为非阻塞注释重写已测试源码。 |
| spacing_min inclusive 描述 | JSON 本身写明 in the legacy generator；仅旧分支含嵌套 hypot/next，新分支标量 min。最终报告/作者分析明确基线分支和 inclusive 边界，不改旧 profile 字节。 |
| processor 空串、基准轮次漂移 | 原记录保留，另加 04_environment_supplement.json，来自本机 PROCESSOR_IDENTIFIER/逻辑 CPU 数/machine。公开原样本和中位数；未观测到的热、频率、affinity 原因 UNKNOWN，不声称绝对精度。 |
| 25 格 line 表观小幅变慢 | 原成功/整体共线路径源码相同，0.1ms 量级测量不当回退或加速证据；正式表使用失败兜底有解/非共线无解，line 原样本保留。 |
| 01_baseline/manifest/return 不可读 | 指定文件中 source_summary 提供前置摘要；目录拒绝是预设只读权限。完整库存和 09B manifest 由作者实际核验；审计后 seal/return 由 Codex 单独执行，不以模型 UNKNOWN 当 FAIL。 |
| 作者失败尝试范围 | 本轮回归首次只有本机 socket WinError10013，未出现本轮 temp 失败；temp/fixture 失败属于 09B 历史。两阶段区分，初次 Git Bash 启动失败也留存。 |

## 最终逐项裁决

C01：09B 164 项 manifest 全过；起始 master/347a5bf05ee82766436382f4fc3d1a8ed15c1132，全文件含 untracked/ignored SHA 库存；保护资产前置全部不变，最终 seal 再检查。

C02：60 候选两类路径独立剖析，枚举 next/hypot/min/np.all/SVD/排序有秒数和次数；min 为 inclusive、np.all 为混合项、标量门控/循环残余未完全拆分，计数开销公开，不相加或当运行时基准。

C03/C04：仅失败兜底优化，原成功与 describe 不改。原序、精确距离、单调间距剪枝、原叉积关系和门控等价；基线穷举 full-dict 对比覆盖所有已定义场景，41 项与正式基准未发现偏离。

C05：原 35 项字节未变，加 6 个差分测试，最终 05_regression_03 41 项 -W error 全过；身份/purity/15cm/v1/v2/v3 回归保持。只检查 3.8 语法，不冒称板端 NumPy1.17 执行。

C06：25/60/100 有解/非共线无解/整体共线，同输入同环境各三轮交替无 mock。100 有解中位 43.03058→2.83566秒（15.17x），无解 42.70000→4.70254秒（9.08x）。最坏仍 O(n⁴)，无全输入时限保证，生产时延 NOT_RUN。

C07：原 121647 四 ROI、11 clean 格与 selector 完整 dict 不变，原 TLS P95 超限保持；有效 TLS BLOCKED、物理成因 UNKNOWN。

C08：独审完成、无逻辑 FAIL，执行 UNKNOWN 如实保留，真实模型/会话/权限由作者事实记录闭合。

C09：需要 finalize.py 执行后才能 PASS；最终 report/verdict 应依赖实际 append-only return、起止保护资产和 manifest 逐 SHA 复算，不以本文件先验声明已封存。

E01 BLOCKED；D01 NOT_RUN。无生产接入/CL2-10/B2/B3/采集/设备或物理结论授权。
