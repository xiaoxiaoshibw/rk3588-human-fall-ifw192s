# HF-MAINLINE-POINTS-01 计划交付入口

当前唯一计划：[v3](../../HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V3.md)。其正文为审核输入冻结版本，保留原句；§7“另存v2”属于审者记录的非阻断文字瑕疵，后续修订应另存下一版本，不在已审文件上回填。

最终审核：[OpenCode v3 PLAN_PASS](OPENCODE_REVIEW_V3.md)。[v1 PLAN_REVISE](OPENCODE_REVIEW_V1.md)、[v2 PLAN_PASS](OPENCODE_REVIEW_V2.md)及原jsonl均保留。模型为CLI请求opencode-go/deepseek-v4.1-flash，底层权重无法独立核验；实际会话ses_ec70e508effetHHugD31AJrhdh。

[三轮作者分析](ANALYSIS_ROUNDS.md) · [80帧本轮上下文留出](CONTEXT_HOLDOUT_V2.json) · [审核工具事件核验](REVIEW_EXECUTION_AUDIT.json) · [331条保护项首尾核验](READONLY_FINAL_CHECK.json) · [跨仓依赖当前SHA](CROSS_REPO_DEPENDENCY_SHA_AT_PLAN.json)。其中80帧历史已见，只作本轮context holdout，不支撑泛化。

仅完成计划和计划审核。实现、算法实验、浏览器效果均NOT_RUN；完整身份精度与生产晋级BLOCKED，R1默认不变。下一轮实施顺序P0基线与绑定→P1删点账本→P2候选消融→P3原页效果→P4全帧与返工。批准的是计划，不是算法性能或工单ACCEPTED。

本轮写入新计划v1–v3、证据与回传，并在WORKFLOW/HC README/REVIEW_LOG顶部登记；无算法/GT/录制/服务/全局OpenCode配置修改。登记前权威文档字节备份位于*.before_plan_entry。首命令参数错误exit1，第一次正确运行因快照初始化停滞被终止；后续关闭单次snapshot后真实完成三轮审核。原stdout/stderr/退出码都保留，不将启动失败改为审核成功。
