# GL03 R5：经设计复审的固定reference上下文

用户手动派发指定DeepSeek V4.1 Flash，Codex不自动启动/重试。工作目录D:/Code/ldiar，单生产写入者；新证据仅evidence/2026-10-02_gl03_r5/，旧证据保留。读根AGENTS.md、WORKFLOW.md、GL03_ACCEPTANCE v1、RETURN_TEMPLATE.md、ponytail技能。

先读R4的evidence/2026-10-02_gl03_r4/codex_review_01/CODEX_REVIEW.md、PLAN_REVIEW.md、context_checks.py与14_context_checks.txt，以及R4 00_diag.md/17_source_manifest.json。本次已按连续失败要求完成本地调用链/设计审查，不重复原四方法补丁策略，不擅自改模型。

先设计后实施：在R5 00_diag.md逐行写清PLAN_REVIEW操作表对应的实际函数、固定来源、prospective有效绑定、校验/比较/赋值顺序与失效消费者。检查所有列明操作组合后再写生产代码。规则已明确，不需要用户例行确认；真实契约矛盾先记录交Codex审查。

集中修两处共享根因（已有G03/G04/G05）：

1. startup保留的standalone输入必须固定/解绑，reload不能重新读caller；reload前比较父canonical及实际有效reference绑定，不能仅比较canonical。合法unknown artifact+standalone路径必须保持支持。已复现caller改x1→9、same-ID reload返回changed=false、随后occluded source错8m。同ID实际变化在任何副作用前拒绝；same-ID相同输入保持；合法新ID采用新artifact T并原有资格失效。快照/预测都消费同份有效绑定；known→unknown fallback只从固定startup副本，不重新读取caller。
2. 父记录显式错误kind必须不可用/拒绝，不能绕过严格验证冒充legacy；父frames.lidar与T.from/实际source须一致。保留无kind旧最小摘要、合法standalone和unknown原义，不强迫所有摘要升级完整artifact、不新增schema。复用现有严格工具；内部R/t合法不能替代跨记录绑定。

只改必要calibration/node_runtime及有效回归；保留R4原十方法已闭合部分、G01/G02/O01。原context_checks和旧断言只读，不降要求。先原9/4/10/8和R4新增4方法→覆盖locked/occluded/pending/同或新ID/无新帧status/request/invalid恢复→当前主线/follow必要回归。scope/SHA包括未跟踪源码，命令/exit全留真实日志。不要重复不受影响UI/O01来凑数量；沿用证据须核SHA/依赖适用性。

不修改config/driver/webui/原始数据/旧证据/外部支线；不reset/checkout/clean/commit/push、不部署/采集/联网板端/GL04/模型切换/DB或认证修改。现场G06/O01身份继续BLOCKED，D01 NOT_RUN，分离默认关闭。

按RETURN_TEMPLATE在D:/Code/ldiar/docs/human_fall/returns/GL-03.md末尾追加“OpenCode GL03 R5”，逐ID及12行矩阵说明结果，状态只SUBMITTED/BLOCKED，不自行总体PASS。完成列出变更/SHA/证据/未闭合后停止写入。若明确规则仍无法闭合，提交具体设计落实位置和失败轨迹，不盲目循环相同补丁。
