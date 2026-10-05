# GL03 R7：父/旧摘要结构资格集中修复

用户手动派指定DeepSeek V4.1 Flash；Codex不自动启动。D:/Code/ldiar，单生产写入者，新证据evidence/2026-10-02_gl03_r7/。读AGENTS.md、WORKFLOW、GL03_ACCEPTANCE v1、RETURN_TEMPLATE、ponytail。

先读R6 codex_review_01/CODEX_REVIEW.md、PLAN_REVIEW.md、input_matrix_checks.py、14d_field_matrix.txt及R6 00_diag/22_source_manifest。R6分类已独立PASS，G04/G05仍PASS；不要重做已过功能。唯一根因是父/summary结构类型未在消费前验证。

按PLAN_REVIEW完整结构表先集中诊断，列实际validator/resolver/helper消费者与缺失/None/合法/错误container或label/declared child组合及检查，然后实施：
1. 完整父frames.lidar非空str必需、reference为None或非空str；不能用truthiness及isinstance失败后跳过绑定。
2. 旧最小摘要保持缺省/原支持None和合法空对象兼容，存在frames/transforms时类型必须正确。坏container在.get前明确拒绝或unavailable，不裸AttributeError。
3. canonical子记录区分缺失/合法unknown/known与损坏，坏字符串/list/数字不能视为无canonical后回退standalone；合法unknown/无记录回退保留。复用原严格record和frame binding，不用catch-all吞错误。

最小改必要calibration资格与回归；node_runtime的889ead5e已过绑定保持，除非同根因确需改并说明。R6分类、legacy普通扩展、原断言/旧检查不改。先R6结构矩阵全部组合和原9/4/10/8/4/3，再受影响GL03/主线/follow/必要GL02回归，按固定ID与12行矩阵记录命令/exit/source SHA。UI/O01不受影响时核SHA沿用，别凑数量。完整范围包括未跟踪源码，外部probe/human_capture文件不动。

在docs/human_fall/returns/GL-03.md按模板末尾追加“OpenCode GL03 R7”，只SUBMITTED/BLOCKED，不总体PASS，完成停止写入。G06/O01真实身份BLOCKED、D01 NOT_RUN；不启动GL04/部署/采集/联网板端/模型切换/认证DB变更，不改冻结config/driver/webui/原始数据/旧证据/外部支线，不commit/push/reset/checkout/clean。
