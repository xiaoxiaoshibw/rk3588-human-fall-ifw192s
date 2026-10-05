# GL-I06 R1 / SUBMITTED / 作者代码停写

唯一验收GLI06_ACCEPTANCE.md v1；Codex唯一研究writer。实际ponytail路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。
branch master / HEAD cbd0be1c86a1051a9a5800dfb7263f842896e1e6；首尾完整tracked/untracked及显式ignored输入SHA见01/16基线，范围外变化0。

采用结论：保留冻结单次TLS，不采用K2/K3。开发62case、额外固定source12case、最终封存种子30case、107项集中契约探针。测试数仅台账，逐ID结果如下。
K2/K3单假设偏差可减少，但分别新增10/6个开发未决；完整W与不同精炼W域明确，误闭合0。最终holdout为合成，不是当前89帧的真实物理留出。

| ID | 自验 | 证据 / 限制 |
|---|---|---|
| A01 | PASS | R0 62cases source/FIT/settings/raw/sample SHA；K1与旧W全等；active05真实WHAT_IF一次转换后W/metrics全等。 |
| A02 | PASS | raw per draw拒绝、旧代表动作、refine/成员/merge/资源detail完整；report counts是旧callback adapter计数，非收敛计数。 |
| A03 | PASS | math scalar独立oracle+合成GT；full W指标和stored subset分域；ties/chain/late/weak与每预算边界。 |
| A04 | PASS | R0已证0.827°截取偏差→K2/K3同sampled域；每轮重查，正常不收敛/注入cycle/later越界/LO gap单列；均不伪closed。 |
| A05 | PASS | full W support最大、全FIT J/覆盖分列；schema/caller/source/units/NaN/zero/line/旧out；IRLS条件实验NOT_RUN，未声称鲁棒收益。 |
| A06 | PASS | 10类×3seed×置换，固定source另3RANSAC seed；三独立validation groups及空间bounds；未筛holdout；freeze后1707/1719/1741首次最终合成holdout30case。 |
| A07 | PASS | 3次active计时每K、12case三重复，分阶段/序列化；另进程Windows memory peak；GT/最差区域/稳定/误闭合/额外未决；不称板端或端到端加速。 |
| S01 | NOT_RUN | ponytail/先diag/单writer/不可覆盖/首尾SHA完成；指定Go Flash/defaultDB实际独审待执行，故当前NOT_RUN。 |
| B01 | BLOCKED | 真实up、point-origin高度、地面身份未核；physical=false、ground_valid=false。 |
| D01 | NOT_RUN | 不生产接入/设备运行/部署/采集；RK3588性能NOT_RUN。 |
| Q01 | PASS | checks_05身份/输入/不可覆盖/无缓存；schema bool及空序列非法K/LO拒绝。 |
| Q02 | PASS | scalar全相似/链/中best/ties/weak/late×四预算0/边界/不足。 |
| Q03 | PASS | 数值非收敛与资源独立；注入solver-state cycle不是实际TLS振荡证据。 |
| Q04 | PASS | 同支持J仅诊断，小J distinct不吞；鲁棒权重/零尺度权重计算NOT_RUN，条件适用由独审确认。 |
| Q05 | PASS | 硬场景/seed/置换/固定source/真实WHAT_IF/validation独立；真实最终留出NOT_RUN。 |
| Q06 | NOT_RUN | 成本/否定/冻结/停写已完成，实际probe/独审当前NOT_RUN。 |

开发最差单平面GT/独立区域：
K1：法向 0.411852478°，offset 0.011593347m，区域RMS 0.043115929m / P95 0.081146612m。
K2：法向 0.323418439°，offset 0.002930087m，区域RMS 0.043116771m / P95 0.079318112m。
K3：法向 0.280728624°，offset 0.002742756m，区域RMS 0.043092672m / P95 0.079168339m。

独立memory（整进程含imports，不是算法增量）：
K1 PeakWorkingSet 71970816 bytes / PeakPrivateCommit 733319168 bytes。
K2 PeakWorkingSet 78929920 bytes / PeakPrivateCommit 739872768 bytes。
K3 PeakWorkingSet 91549696 bytes / PeakPrivateCommit 753819648 bytes。

活动源码：refinement_05.py；入口checks_05/publish_04/fixed_source_02/holdout_03/cost_memory_03。01–04历史修订均保留；只有_01/02首次数值源码运行及_04/_05完整发布/最终入口实际使用，未执行修订不是试验结果。
活动R1台账r1_case_*_02.json来自不可变_01数值记录；_02追加full-W vector/scalar复核、J/覆盖和额外决策计时。active05真实K1及合成完整入口复核相同W。
所有最终holdout数值源码SHA与method_freeze_01.json相同；无曝光后调参。冻结源码与生产423/2旧回归仍匹配，不重跑代替独审。
日志已关闭；19_manifest_01.json为全部作者本轮文件+冻结依赖SHA（排除manifest自身），接着追加return后停止代码写入。独审新检查只在opencode_review_01，独审失败不自动返工/切模型。
