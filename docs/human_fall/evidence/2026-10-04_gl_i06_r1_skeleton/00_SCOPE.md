# GL-I06 R1 skeleton / 00_SCOPE（验收范围映射，计划态）

2026-10-04。逐条引用 GLI06_ACCEPTANCE.md v1 的要求文字，标出**本 skeleton 对该条的计划处置**：

- `[ ] PLANNED` — 本骨架的 R0 计划已覆盖该条要素，待实施单冻结后执行（本骨架自身无任何运行结果）。
- `[ ] RESERVED` — 本骨架明确不安排：条件门未触发、物理/设备范围外、或属流程/独审环节由指定角色另行履行。
- `[ ] NOT_RUN` — 需要运行但当前既未运行也未被本骨架排程。

勾选一律留空 `[ ]`：本骨架不声称任何条目的任何结果，不预填 PASS/FAIL。各条**当前真实状态**以 GLI06_ACCEPTANCE.md 与已有 returns 记录为准；本表仅是计划映射，不回填、不覆盖既有结果。

## A 组（验收条目）

| ID | 引用要求与反例 / 检查 | 本 skeleton 处置 |
|---|---|---|
| A01 | 复用冻结基线；source/FIT/settings/seed/raw sequence SHA对拍；raw与各variant精炼W域明确；禁止结果冒称同数学 | [ ] PLANNED — §2 要素 3 已列入账本计划；与既有 R1 提交对拍结果的合并/作废由 Codex 裁定后实施单确认 |
| A02 | 逐阶段拒绝账本，区分先验/采样退化/支持/精炼/实际见证竞争/预算；reason汇总不替代真实计数 | [ ] PLANNED — schema 草案见 `planning/rejection_ledger_schema.md` |
| A03 | 全合格见证处理完整，ALL/NEAR/BEST_ONLY独立oracle；ties/中间best/非传递链/late不能吞；精确合并多重性/指标域明示 | [ ] PLANNED — 独立 oracle 设计草案见 `planning/oracle_design.md` |
| A04 | R0有偏证据才研究2/3轮TLS，保持同sampled精炼域/全FIT仅支持重算；K正常完成不稳定与总LO资源缺口分开，振荡/后轮越界不静默回退且不得closed；未触发时核条件门、实验NOT_RUN并独审确认不适用 | [ ] RESERVED — 属 R0 之后的条件门路线；本骨架不排程（既有 R1 提交是否覆盖、条件门状态，由 Codex/用户裁定） |
| A05 | 支持数/截断残差/覆盖分列；best_support始终全W最大支持，J不得改NEAR锚点/吞竞争；零尺度/NaN/共线/错误单位/source/caller变更拒或未决 | [ ] PLANNED — 评分分列与非法输入负例入 R0 实施矩阵；其中鲁棒尾部/IRLS 条件分支 [ ] RESERVED（门未触发） |
| A06 | 预定噪声/墙桌/双平面/密度/链/tie/late/预算×3seed/置换；GT误差、最差独立区域、额外未决与误闭合；三个validation frame_group独立；开发/方法选择与最终holdout分离，曝光后不冒称未见 | [ ] PLANNED — 场景矩阵要素列入实施单范围；本骨架不建数据、不封 holdout |
| A07 | 至少3重复、stage/LO/serialization计时、独立内存峰值；收益/退化/成本可据以采用或否定，无收益不伪改进；桌面不称RK3588性能 | [ ] PLANNED — 记录口径列入实施约束；本骨架无任何计时/内存数据 |

## S / B / D 组

| ID | 引用要求与反例 / 检查 | 本 skeleton 处置 |
|---|---|---|
| S01 | ponytail/先diag/单writer/新编号不可覆盖/首尾含untracked SHA；实际指定Go Flash/defaultDB二审；旧数学/输入/driver/UI/HR冻结 | [ ] RESERVED — 流程/独审条目：ponytail 与首尾 SHA 由实施人（Codex）在实施单履行；指定 Go Flash/defaultDB 独审不在本骨架，本轮不启动任何会话/probe |
| B01 | source up/高度/ROI身份未核时physical=false，研究closed不能变ground.valid/candidate资格 | 状态引用（不入本表勾选）：GLI06 v1 当前标 BLOCKED（物理资料缺失）；本骨架不解除、不触碰 |
| D01 | 不采集/部署/设备运行/production接入，板端算法性能未跑 | 状态引用（不入本表勾选）：GLI06 v1 当前标 NOT_RUN；本骨架无设备/部署动作 |

## Q 组（组合关联行）

| 行 | 引用组合关联及映射 | 本 skeleton 处置 |
|---|---|---|
| Q01 | startup/source/schema/settings/NaN/单位/caller同路径或ID异内容/旧out → A01/A05/S01 | [ ] PLANNED — 负例域列入 R0 输入矩阵草案 |
| Q02 | all/near/best_only×tie/链/弱distinct/晚best×完整/预算缺口 → A02/A03 | [ ] PLANNED — oracle 三域与未决语义入 `planning/oracle_design.md` |
| Q03 | 一次/2轮/3轮TLS×同精炼域/稳定/振荡/两周期/后轮越先验/K完成不收敛/资源未处理 → A04/A05 | [ ] RESERVED — 同 A04，条件门路线不排程 |
| Q04 | 同支持不同残差/小J但NEAR distinct/权重零尺度/混杂尾部 → A03/A05 | [ ] PLANNED — 同支持/J 域分离入 oracle 设计；权重/混杂尾部分支 [ ] RESERVED（门未触发） |
| Q05 | 固定6类以上场景×3seed/原置换/真实WHAT_IF/独立validation源组 → A06/B01 | [ ] PLANNED — 场景×seed×置换要素列入实施范围；真实 WHAT_IF 单列、不冒称未见 holdout |
| Q06 | 成本与采用/否定/新语义版本/停写/probe/真实二审/冻结 → A07/S01 | [ ] RESERVED — probe/二审不启动；本骨架唯一停写动作是 `99_STOP_WRITE.md` |

附注：本表与既有 R1 提交/独审记录（`docs/human_fall/returns/GL-I06.md` 及相关 evidence run_root）是计划层与已提交层的两份文档；PLANNED 不表示推翻或重交既有 PASS，RESERVED 不表示该条已关闭。任何 PASS/FAIL 的改写只属于未来实施单与指定独审。
