# GL03 R6：最后的G03父输入分类收敛

用户手动派发指定DeepSeek V4.1 Flash，Codex不自动启动。工作目录D:/Code/ldiar，单生产写入者；证据用evidence/2026-10-02_gl03_r6/，保留旧失败。先读AGENTS.md、WORKFLOW.md、GL03_ACCEPTANCE v1、RETURN_TEMPLATE.md、ponytail。

必读R5 evidence/2026-10-02_gl03_r5/codex_review_01/CODEX_REVIEW.md、PLAN_REVIEW.md、closure_checks.py与14b_closure_checks.txt，以及R5 00_diag.md/22_source_manifest.json。当前G04/G05已独立PASS，不再重做固定standalone/prospective reload。唯一待修G03：完整artifact kind缺失/null且schema99仍被当旧最小摘要投影。

先按PLAN_REVIEW完成输入分类设计和全部组合检查映射，再实现。Codex承认上一轮legacy结构定义不充分；现在按已审规则先分类再验证：合法kind或完整产物专属块走完整validator，kind/schema/ID损坏不能降级；真旧最小摘要仍走兼容路径，支持字段/版本及完整块标志见该报告。不把所有无kind对象都当legacy，也不让旧合法摘要被强制升级完整artifact。不得补造kind/偷偷改schema来通过，不新增schema/框架或全局迁移。

仅必要calibration分类及有效回归；preserve node_runtime.py的R5已过逻辑，除非同根因确需改且诊断列明。先R5 closure分类反例及PLAN表正/负例，再原9/4/10/8/4、受影响GL03/主线/follow回归；原断言/旧检查只读。O01/UI不受影响时核SHA后沿用，别凑测试数量。记录真实命令/exit/source SHA和12行矩阵、未跟踪范围。

按RETURN_TEMPLATE在D:/Code/ldiar/docs/human_fall/returns/GL-03.md末尾追加“OpenCode GL03 R6”，状态只SUBMITTED/BLOCKED，不自行总体PASS；完成停止写入。G06/O01真实身份BLOCKED、D01 NOT_RUN，分离默认关闭。不要重复修G04/G05或引入新的算法里程碑。

不改冻结config/driver/webui/原始数据/旧证据/外部human_capture/支线，不reset/checkout/clean/commit/push，不联网板端/部署/采集/GL04/模型切换/认证数据库操作。
