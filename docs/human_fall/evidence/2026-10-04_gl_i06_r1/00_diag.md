# GL-I06 R1 写前集中诊断 / 2026-10-04

唯一表：docs/human_fall/GLI06_ACCEPTANCE.md v1。Codex唯一研究writer；实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md。只新本目录；returns/GL-I06.md仅最终追加。生产/配置/原始与批准输入/旧证据/driver/UI/HR只读。无commit/reset/checkout/clean/设备操作。

已完整阅读WORKFLOW v2、NEXT_STAGE_PLAN v2、ALGORITHM_DESIGN v1、验收v1，ground.py、ground_diagnostics.py及GL-I05 R2 search/oracle/experiment/check。复用 ground_diagnostics.replay_sequence/refine_hypothesis/replay_frozen_search、GL-I05 R2 search_events，避免新造RANSAC。旧代表在raw阶段相似替换、最多8个，在精炼后相似去重；相似不传递，不能视其输出为完整W。ground_degenerate汇总不能替代逐draw计数。

| ID | 实际入口/顺序与当前缺口 | 本轮检查/证据计划 | 保留行为 |
|---|---|---|---|
| A01 | replay_sequence先清finite/zero、source rows→均衡采样→固定RNG；旧fit与R2同序列 | source/FIT/settings/up/height/sample/raw SHA；原fit/replay candidates对拍；每variant独立W | 固定门、同sampled TLS域，全FIT只支持 |
| A02 | replay raw拒绝→R2 refine→exact merge/retained/unprocessed | 每假设raw/旧代表动作/精炼轮/资源事件，计数恒等式 | 区分prior、degenerate、support、competition、representative、resource |
| A03 | R2 search_events调用向量oracle，不是独立标量参照 | 独立math标量ALL/NEAR/BEST_ONLY；全W与unique域分列；链/ties/late/弱distinct | best_support全W最大；BEST_ONLY无放行 |
| A04 | 单次TLS存在硬阈值截取成员偏差的可能，尚需实际反例 | R0先保存最小偏差证据；门触发才新编号K2/K3，逐轮方向/height/ratio/support/member；cycle/nonconverged与LO缺口分开 | 正常跑满K不代表收敛；越界不退回成功 |
| A05 | residual_stats已有未截断stats；缺J/空间覆盖 | 全FIT J、source cell覆盖与支持分列；NaN/zero/单位/源身份/修改/共线；IRLS只混杂尾部偏差证据后 | J不改NEAR/阈值，不删见证 |
| A06 | 旧36case有三hold groups，但本单硬场景更多；89帧已曝光 | 预定clean/8mm/35mm/wall/table/dual/density/missing/line/band × seeds7/19/41 ×输入置换；事件顺序置换；GT/3独立空间区域；开发/封存final明确隔离 | 不按残差筛holdout；真实只WHAT_IF |
| A07 | 旧cost不能代替新variant | 3独立重复sampling/raw/refine/LO/decision/serialization；另进程Windows PeakWorkingSet；最差GT/region、额外未决、误闭合与否定结论 | 不称RK3588速率/端到端加速 |
| S01 | 当前dirty含untracked；本目录尚无实现 | 首尾all tracked/untracked SHA含ignored source；不可覆盖写入；停止后manifest/return→一次无工具probe→指定Go Flash/defaultDB只读独审 | 不换model/DB/auth；独审修订新编号 |
| B01 | up/point-origin/地面身份未核 | 所有研究physical=false且无ground.valid产物 | 窗口高度不当点云原点高度 |
| D01 | 未授权设备操作 | NOT_RUN，检查范围 | 不采集/部署/production接入 |
| Q01 | A01/A05/S01 | startup/同内容/source/settings/caller同路径异内容/schema/NaN/单位/旧out；全部新证据拒覆盖 | 无跨调用缓存 |
| Q02 | A02/A03 | all/near/best_only×tie/链/weak/late×完整/每预算0、边界、耗尽 | 无吞端点/晚候选 |
| Q03 | A04/A05 | K1/2/3×stable/nonstable/cycle/later prior/LO不足；数值真实fixture与状态注入分列 | 保留最后有效见证但unresolved |
| Q04 | A03/A05 | equal-support J排序、低J distinct、零尺度、混杂尾部条件门 | 评分仅诊断 |
| Q05 | A06/B01 | 上述固定场景×3seed/置换，独立frame_group/空间分布、真实原批准先验及历史WHAT_IF明确标记 | 独立GT不由oracle定义 |
| Q06 | A07/S01 | 重复/内存/冻结/采用门/停写/probe/指定二审 | 不自动下一单 |

生命周期矩阵裁剪：纯离线无ROS startup/reload/tracking状态，源文件身份和caller修改仍覆盖；新ID/同ID不同内容等价于重算SHA、拒旧out，不赋资格/缓存。损坏schema/source/units必须拒绝。输入变换不靠拟合猜测。

预登记：K1为冻结单次TLS，K2/K3仅条件触发；稳定=sampled内点成员集合不变；每个variant正常完成但仍变化则nonconverged，出现已见非相邻成员集合cycle；资源总LO预算按TLS调用计，未处理仍unresolved。GT n=[0,0,1],d=1.4为合成标签；table/dual不是单地面真值。主要指标为单平面GT误差/最差独立区域误差/跨seed稳定性，在无误闭合和资源闭合前提下比较；无收益或有退化不采用。最终holdout单独固定生成种子1707/1719/1741，开发只用7/19/41；方法冻结后新编号一次曝光，若之后方法变化需新独立holdout。
