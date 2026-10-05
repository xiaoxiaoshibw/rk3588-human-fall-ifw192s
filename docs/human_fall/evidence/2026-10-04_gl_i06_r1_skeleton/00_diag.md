# GL-I06 R1 skeleton / 00_diag（计划诊断，NOT_RUN）

2026-10-04。本文件是 R1 skeleton 轮的诊断占位：只定结构，不进算法。本轮未运行任何实验、未实现任何代码、未启动任何 probe/独审。

## §1 任务范围声明（什么不做）

本轮（R1 skeleton）明确的负数清单：

- 不运行任何算法实验；不写任何 Python 源码或测试（只 Markdown / JSON schema 草案）。
- 不复制、不改写、不引用 `src/human_fall_detection/core/ground.py` 的函数体实现；若后续需要提及既有接口，只提函数名，不抄实现。
- 不修改 `src/human_fall_detection/core/` 下任何文件。
- 不修改 `config/`、`geometry.yaml`、`default.yaml`、`human_fall.yaml`、`perception.yaml`。
- 不修改 `docs/human_fall/returns/` 下任何已有文件（GL-I06.md 的历史 R1 段落原样保留）。
- 不启动任何 OpenCode 会话、probe 或独审；S01 的独审部分本轮及本骨架均 NOT_RUN。
- 不采集、不部署、不运行设备、不做生产接入（D01 NOT_RUN；B01 物理 BLOCKED 不由本骨架解除）。
- 不预填任何验收 ID 的结果、不写「预计 PASS」。
- 不 commit、不 push；本轮结束于 `99_STOP_WRITE.md`。

补充说明（非本轮决定，仅记录事实）：GL-I06 的 R1 主线（R0 账本 + K1/K2/K3 有界 TLS 对照）已由 Codex 提交并在 `docs/human_fall/returns/GL-I06.md` 登记独审 PASS。本 skeleton 不是重做该路线上任何已完成实验，而是按本轮用户指令交付规划骨架；若 Codex/用户裁定该路线已被覆盖，本骨架对应的 ring 计划随之作废或转向设计 §3 中尚未触发的条件分支（例如鲁棒尾部/IRLS ring R2 的前置）——该决定不在本轮。

## §2 R0 关卡拒绝账本 shadow 计划要素

R0 的目标（来源：GROUND_LEVELING_ALGORITHM_DESIGN.md §5、AI_PROMPT_GLI06_CODEX_R1.md）：保持同 source / selector / settings / seed / sampled rows / raw 假设序列，只做逐关卡拒绝账本 + 冻结 fitter 对照，证明处理完整性与旧拒绝来源，诊断真实见证竞争 / 旧代表保守性 / 预算缺口。R0 成功后才有条件开 R1（有界 2/3 轮 TLS）——注意本验收路线与 Codex 完成路线的重叠须由 Codex 裁定，见 §1 补充说明。

计划要素（草案编号，实施单另行冻结）：

1. **账本骨架**：逐关卡拒绝账本，schema 见 `planning/rejection_ledger_schema.md`。关卡为：prior_reject / sample_degenerate / support_reject / refine_reject / witness_competition / budget_unprocessed。reason 计数分层，汇总不替代真实计数（A02）。
2. **对照域**：raw 假设序列（W_raw）与各 variant 完整精炼后序列（W_refined）分开标识；拒绝事件挂在第一次拒绝它的关卡上，不误闭合、不跨关迁移。
3. **冻结与堪比性**：source/FIT/settings/seed/raw sequence 各自 SHA 入账；variant 定义见 `planning/variant_naming.md`。
4. **输入负例面**（Q01 关系域）：startup / source / schema / settings / NaN / 单位 / caller 同路径或同 ID 异内容 / 重复 run_root / 旧 out 目录。
5. **oracle 输入**：账本 JSON + variant W 序列交给独立 oracle，设计草案见 `planning/oracle_design.md`。
6. **预算语义**：budget 耗尽导致的「未处理」单列 `budget_unprocessed`，与「处理后精炼未收敛」分开记账，两者皆不得 closed（设计 §3 末段）。
7. **文献环**：遇到困难时按设计 §7 联网闭环——先保存最小反例与违反 ID，再检索一手来源，记录 URL/访问日期/版本/适用前提。

## §3 variant_id 命名规则草案

完整规则与逐条设计映射见 `planning/variant_naming.md`。要点摘录：

- variant_id 既标识「账本区间」，也标识「精炼域」：换精炼域（如全 FIT 直接精炼）必须另立 variant，不与均衡 sampled 域混记（设计 §3 精炼主路线）。
- 每 variant 预先固定 K（算法轮数）与所有超参；部分 K 已经实施的（tls_k2/tls_k3）留待 Codex 裁定是否重排。
- 冻结基线 variant 命名为 `frozen_baseline`；旧已审变体（0.05/8）仅显式选择时入场，不改默认（设计 §3 输入与采样行）。
- R1 ring（某种候选精炼路线）一轮只动一个因素；因素叠加必须另立 variant_id（设计 §5：每轮单因素，独立 variant_id，不把方法名拼成大架构）。
