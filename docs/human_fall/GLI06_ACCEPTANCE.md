# GL-I06 有界精炼与竞争诊断研究 / 唯一验收草表 v1

状态：DRAFT_READY / 未执行。来源GROUND_LEVELING_ALGORITHM_DESIGN.md、既有GL-I05完整见证契约及用户“设计好算法，遇困难网上找”。只新evidence研究，不改生产算法/配置/数据/旧证据；独审后最多建议candidate-only新单。

| ID | 要求与反例 / 检查 | 当前结果 |
|---|---|---|
| A01 | 复用冻结基线；source/FIT/settings/seed/raw sequence SHA对拍；raw与各variant精炼W域明确；禁止结果冒称同数学 | NOT_RUN |
| A02 | 逐阶段拒绝账本，区分先验/采样退化/支持/精炼/实际见证竞争/预算；reason汇总不替代真实计数 | NOT_RUN |
| A03 | 全合格见证处理完整，ALL/NEAR/BEST_ONLY独立oracle；ties/中间best/非传递链/late不能吞；精确合并多重性/指标域明示 | NOT_RUN |
| A04 | R0有偏证据才研究2/3轮TLS，保持同sampled精炼域/全FIT仅支持重算；K正常完成不稳定与总LO资源缺口分开，振荡/后轮越界不静默回退且不得closed；未触发时核条件门、实验NOT_RUN并独审确认不适用 | NOT_RUN |
| A05 | 支持数/截断残差/覆盖分列；best_support始终全W最大支持，J不得改NEAR锚点/吞竞争；零尺度/NaN/共线/错误单位/source/caller变更拒或未决 | NOT_RUN |
| A06 | 预定噪声/墙桌/双平面/密度/链/tie/late/预算×3seed/置换；GT误差、最差独立区域、额外未决与误闭合；三个validation frame_group独立；开发/方法选择与最终holdout分离，曝光后不冒称未见 | NOT_RUN |
| A07 | 至少3重复、stage/LO/serialization计时、独立内存峰值；收益/退化/成本可据以采用或否定，无收益不伪改进；桌面不称RK3588性能 | NOT_RUN |
| S01 | ponytail/先diag/单writer/新编号不可覆盖/首尾含untracked SHA；实际指定Go Flash/defaultDB二审；旧数学/输入/driver/UI/HR冻结 | NOT_RUN |
| B01 | source up/高度/ROI身份未核时physical=false，研究closed不能变ground.valid/candidate资格 | BLOCKED（物理资料缺失） |
| D01 | 不采集/部署/设备运行/production接入，板端算法性能未跑 | NOT_RUN |

| 行 | 组合关联ID | 当前结果 |
|---|---|---|
| Q01 | startup/source/schema/settings/NaN/单位/caller同路径或ID异内容/旧out → A01/A05/S01 | NOT_RUN |
| Q02 | all/near/best_only×tie/链/弱distinct/晚best×完整/预算缺口 → A02/A03 | NOT_RUN |
| Q03 | 一次/2轮/3轮TLS×同精炼域/稳定/振荡/两周期/后轮越先验/K完成不收敛/资源未处理 → A04/A05 | NOT_RUN |
| Q04 | 同支持不同残差/小J但NEAR distinct/权重零尺度/混杂尾部 → A03/A05 | NOT_RUN |
| Q05 | 固定6类以上场景×3seed/原置换/真实WHAT_IF/独立validation源组 → A06/B01 | NOT_RUN |
| Q06 | 成本与采用/否定/新语义版本/停写/probe/真实二审/冻结 → A07/S01 | NOT_RUN |

ROS生命周期与结果缓存不适用，文件身份/完整处理/预算/资格不得裁剪。缺现场资料不阻研究软件PASS，但不解除B01。实验当前均NOT_RUN，计划/论文阅读不是新算法已通过。
