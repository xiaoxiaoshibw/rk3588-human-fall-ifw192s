# R05前置因果纠正（2026-10-12）

两个只读代理/root/cause_review与/root/d05_audit实际读ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md，未写或重跑。主控也实际重读源码与连续账本。当前真正加载background/engine_b.js，不是core/engine.js的旧背景实现。

原bank已排除含retained的PA候选直接刷新。家具R02split/R04fast全304帧：375高分候选=103纯cleanup+272含retention；57刷新帧均存在纯cleanup高分候选，bank确认数最大3。f40 a_40_1 n176、retained0、readmitted0、prob.9602、家具点纯度1；f30–31/41–42含retention高分但bank不刷新。模式是独立误接受再次播种与有限延续，**不是已经实证的直接恢复续票**。

near全258帧R02/R04高分834=415纯cleanup+419含retention；93刷新帧。f220–224真人候选retained585/793、512/733、479/850、433/867、359/997且strictTP；这五帧bank未刷新，人体anchor最后f219/confirmation3。原R03分类门影响前序播种导致后序恢复损失，不能用全拒retained修家具。

原报告“银行可不断由确认续命/自维持”只支持“独立FG误分类可周期性重新建立，随后有限恢复”，不能据此断言retained直接刷新。历史报告和评分不覆盖，本次将此语义纠正追加回传。

内部PIPE Tracker同帧可多候选同ID，票及EMA可受MERGED/RETAINED影响；原银行锚点来自t.x/y。实际发生频率/偏移尚未测得，因此R05登记真实事件对拍，只改单次合法bank刷新锚点取当前FG证明候选，不改票门或TTL。

主控只读探针：far f5/f7/f8实际PA混簇11696/11699/11741点，合格上层核心均1，26/27/27cells、4477/4472/4472高点，split_log为空；相应已审human coverage约.976、purity约.53。现有多核分离不触发的原因已定位，不能泛化成所有分离无效。f40/f80/f463另有实际分离，不仅挑失败图。

诊断执行曾出现Python临时open未闭合的ResourceWarning（exit0但不称clean检查）；随后使用with读同一账本、-B -W error复核退出0。一次读取不存在的r03/analyze.py退出1，实际文件analysis_v1/analyze.py已重新定位；不将缺失路径当证据。这些探针不改变任何文件或评分。
