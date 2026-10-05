# GL-I05 R1 Codex集中诊断（独立二审进行中）

不是收口/ACCEPTED，不启动新里程碑。研究writer仍停写；本文件只记读审与后续最小修复设计，待指定二审停止后合并缺陷。ponytail已读 C:/Users/30680/.codex/skills/ponytail/SKILL.md。

已复现（04_codex_audit.json）：

| 根因族 | ID/Q | 原预期与实际 | 最小修复/验证 |
|---|---|---|---|
| pair方向和信任边界 | C01/C02/C04/Q01-Q04 | BEST_ONLY应检查所有best/tie与近优关系；best index大于other时被continue跳过。oracle接受NaN setting、零/非unit法向。原型直接调用该oracle，作者等值比较不能发现共享缺陷 | 无向distinct对过滤双方是否best；冻结settings解析；单位法向/有限字段检查；独立scalar参考覆盖best首/末、ties/所有顺序及非法输入 |
| 研究比较和归因缺口 | C02/C03/C04/Q03-Q06 | 本单应实际比较GL-I04包络原型，experiment只比较冻结fit和replay_frozen_search，未调用旧research原型；actual near-distinct未进入reasons | 同source/selector/settings/seed/抽样digest复用旧原型；保留原status，记录证书不足/实际竞争/预算；同序列手算和清洁/低噪/弱dominant正例 |
| 成本证据不全 | C06/Q05/Q07 | 只有baseline_fit/research_search/scoreboard_total，缺sampling/raw/refine/decision/serialization拆分、重复成本样本、内存峰值、cache不采用依赖审计 | 原型仅加perf_counter计时与refine_calls；至少3重复、tracemalloc峰值、明示不同阶段不冒称端到端；无cache代码/依赖说明及成员mask实验 |
| 空间输出契约 | E01/C02/Q01/Q08/Q09 | 356/356计数匹配，但plane切换仍color(r[6])；approved的posthoc PCA错误标为human prior；无点读取handler；main直接覆盖既有HTML | 新root/独占out，只读身份/sidecar验证；实际posthoc origin；从XYZ按所选plane重算显示残差；点击/索引读取；empty与全部frame统计闭合，非法row/alias/组拒绝 |
| 本地录制资料与状态 | E02/S01/Q09/Q10 | 仅口头无新材料，缺有界本地检索清单；验收/TASK仍DRAFT_READY；manifest仅CLI_RECOVERY因显式恢复登记异动 | 比对GL-I04末基线和当前capture元数据索引，时间窗口/提取/配置/SDK链逐项unknown与SHA；审查完成后更新唯一表/指针/回传附记，保留提交manifest原字节 |

R2若需实施：Codex单研究writer；新目录 evidence/2026-10-04_gl_i05_r2/research_01/，从R1复制五个脚本后最小根因修复，不覆盖R1。生产src/tests/config/原NPZ/draft/GL-I04/UI/driver/HR只读。不存在缓存所以Q07哈希碰撞/cache满实现不适用，但须有依赖/未缓存对照依据；ROS reload/GL02生命周期不适用且记录理由。设备/物理B01/B02仍BLOCKED，D01/D02 NOT_RUN。

组合逐行：Q01合法/非法身份与out；Q02无状态重跑/points/settings/caller/report变更；Q03所有指标/tie/.8/预算；Q04 0/4/8与0/6/12全排列；Q05六场景×3seed×原/置换×重复；Q06晚best/晚distinct与四预算0/边界/耗尽；Q07无cache依赖/相同不同mask对照；Q08逐frame/四box/empty/alias/显示budget；Q09录制时间与未知物理层；Q10提交停写/probe/指定二审/首尾SHA。不得由软件研究解除物理门。
