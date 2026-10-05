# GL-I05 R2收口 / 2026-10-04 / 软件独审PASS

唯一验收 GLI05_ACCEPTANCE.md v1：**C01–C06、E01–E02、S01、Q01–Q10 PASS；B01/B02 BLOCKED，D01/D02 NOT_RUN。整单未ACCEPTED。** 无活动writer，无新软件FAIL或生产接入/部署/采集授权。本单为GL-I05离线研究，不是GL-05设备阶段。

有效提交 research_01/11_submission_manifest.json（76 SHA）；实际算法二审 opencode_second_review_01/00_review.md；最终有效独审 opencode_second_review_02/00_review.md。后者对证据保全偏差完成新编号不可变复验，不能仅引用前者自报PASS。

## 改动与验证

只新R2目录，Codex单研究writer（ponytail实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md）。修复BEST_ONLY无向关系漏报、oracle非法settings/单位法向检查、near竞争归因、旧GL-I04同序列对照；补五阶段×三重复成本及独立内存测量；空间页来源/seq/残差/点击索引/独占输出全部修复。冻结生产src/tests/config、driver/UI/HR、批准draft/NPZ/capture、GL-I04/R1证据保持。

38 case：36 synthetic（六类型×三seed×两顺序）+2真实WHAT_IF；三路raw序列digest一致，全部终态与oracle一致、无误闭合；弱distinct六个dominant正例仅为synthetic，真实approved/negative-X仍unresolved。独立scalar4000序列0失配；17作者自检PASS仅作部分证据。

源点页有效路径 research_01/spatial_02/source_review.html：89帧×四box，356全统计，351255源索引点XYZ与原NPZ逐行精确一致（21_codex_source_audit.json）；残差与模型公式浮点误差≤6.66e-16（不是位级相等声明）。实际页面JS的vm消费者检查通过点击/索引/平面/frame/box/显示预算；真实浏览器DPR未测。

有效成本台账 research_01/experiment_results_identity_verified.json，原始14_experiment_run/exit=0。每case三重复；单独tracemalloc不混入基准。negative-X本机研究search中位0.342659s，峰值112881317 bytes；approved中位0.087870s，峰值105733394 bytes。一次call将全source转float64并复用，无refine结果cache。R1同研究阶段negative-X为14.814s，不能据此宣称冻结fit端到端或RK3588性能；阶段、报告内容与成本边界均明确。R1“46s”没有制品，不沿用为已验证依据。

生产回归复用R1 `05_checks_meta.json`：423 fall/2 follow exit0，源码/config/tests SHA不变（独立09_frozen_compare.json），不无依据重复测试。Python3.8 AST通过；目标板Python3.8.10/NumPy1.17.4实际运行NOT_RUN。

## 指定二审与证据历史

1. R1 fresh probe14.718s成功，二审987.890s/exit0，集中REWORK并保留原提交。
2. R2 fresh probe12.453s成功，算法二审940.140s/exit0/stop，session ses_efd3cf9eaffeanm7dK1RLUGDvQ，23_review_session.json核实际Go Flash/defaultDB。该review_01内部编辑/复用自己的检查器输出，违反已明确证据保全步骤，不能将其过程直接标完全合规。
3. Codex从关闭的追加式20_second_review.jsonl恢复27个脚本版本及26条命令输出到24_review_history_final，原检查器误判/修订不抹除。使用最后正确字节新编号复制，25_run_review_checks.py拒绝重跑/覆盖并验证检查器首尾SHA。
4. 新probe10.891s成功，再交Go Flash/defaultDB不可变复验：155.906s/exit0/stop，session ses_efd29d375ffeh5FIoGvw4SS2G2，29_revalidation_session.json核实模型/provider；13命令exit0，检查器start=end，首尾作者76 SHA相同，全部ID/Q确认PASS。28_immutable_revalidation_meta.json与execution_manifest.json保存原始身份/命令，最终报告review_02/00_review.md一次写入。

二审报告两处路径/标签说明：`cases_with_pair_count_diff=44`是44处指标数量对比，不是44 case；Q07录制/掩码审计实际在本run_root根目录 `08_assets_audit.json`（不在research_01）。oracle用完整W多重集合，原型pair计数用exact-signature代表集；holds/终态不变，全多重性保留在trace/produced/merged_exact，不宣称pair计数相等。

30_scope_check.json：生产/旧证据/数据无意外改动，branch/HEAD master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6保持。收口的验收结果、TASK状态、回传与入口是允许的行政更新，旧提交manifest不追改；最终34_verify.json另记行政差异与代码冻结。

## 采用决策与下一步边界

采用为**离线研究原型与证据工具**，不接运行时、不放行标定candidate/ground.status。相似不是等价；精确成员去重可保持关系性质，首锚充分证书可能假拒；闭合只覆盖有限已见序列，未见假设未排除。预算/未处理/trace缺口永不以晚强best清除。

不采用refine-reuse cache：同sample-inlier mask不能单独证明全fit support、up/height/settings/source/code上下文；当前dtype单call复用已有明显成本改善，无持久cache状态或碰撞命中逻辑。后续若研究缓存须先有完整成员/依赖证明，不能为了验收新增缓存。

物理下一步所需证据：原bag/layout原件与提取链校验；2026-10-02录制绑定的SDK/driver配置SHA与实际source→world/ground旋转平移、world-up表达和点云原点高度；四固定区域的独立地面身份。7条本地metadata清单、录制窗口、提取时间和unknown见08_assets_audit.json，历史9月30六零配置、PCA法向、光学窗口高度均不能代替这些资料。本轮不启动新录制/设备/网络/部署，GL04实际DPR/正式页边界保持。

流程复盘：R1自验共享oracle遗漏diagnostic顺序与消费链；本轮改为独立scalar、每个plane消费者和文件身份检查，集中一次修复。review_01自改检查器问题通过版本恢复与一次性新编号执行器纠偏，今后只读二审默认先固定脚本、失败新编号，不依赖口头“不要覆盖”。所有历史FAIL与服务/审查过程独立记录，不把检查器笔误或程序性偏差伪装成算法返工。
