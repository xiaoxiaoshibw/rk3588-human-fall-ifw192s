# 07 · R3.7 总结（Cross-Session Registration Productionization Design）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full（`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 状态：**SUBMITTED（设计交付）/ 未 ACCEPTED**；R3.7 为 design-only 轮，全部实现/测试条目 = NOT_RUN。

> **复审修订 R1（2026-10-07，独立复审后）**：§4 第 4/6 条例证与 sanity 常量已按复审重算同步（同会话 job 差最大 ≈1.54°；`|t|` **0.20 m**、`|t_z|` **0.15 m**）；修订明细见 01/03 文内记录与 [returns/HR-W03.md](../../returns/HR-W03.md)「R3.7 复审修订 R1」。

## 1. 一句话结论

已把"B 级跨 session registration 进入生产"所需的全部契约冻结为可实现、可审计、可回退的设计：**坐标系与方向（cur→ref）唯一化、不可变 SHA 绑定 artifact（含 refmap/code/leveling 绑定与失效即 STALE）、四族 confidence gate（含历史分布推导的 sanity bounds）、六状态机、fail-closed fallback（SAFE_FOREGROUND_ONLY）、帧标签式重复变换防护**；并给出 R3.8 shadow 的双分支方案、golden/故障用例与预注册判定门。**本轮零 production 改动、零 matcher 改动、零 ICP 重估。**

## 2. 交付物与核心内容

| 文件 | 核心冻结内容 |
|---|---|
| `00_baseline_and_scope.md` | 授权边界（禁调 matcher 等）、基线 SHA（本轮实测复核）、R3.6/E-1/R9 冻结前置 |
| `01_coordinate_contract.md` | RAW→LEVELED→REFERENCE→FOREGROUND 定义；**REFERENCE_FRAME := reference 会话的 LEVELED_SESSION**；`p_ref = R_cur_to_ref·p_leveled + t_cur_to_ref` 唯一方向；帧身份 = artifact 级；canonical B 数值与容差；I1–I7 不变式 |
| `02_registration_artifact_spec.md` | `captures/registration/<src>__to__<ref>/`（4 文件：registration/diagnostics/provenance/manifest）；独占创建、永不覆盖；`artifact_id = sha256(registration.json 字节)`；session/leveling/refmap/code 绑定与 `refmap_digest_v1`；载入校验顺序；显式选择（无 auto-latest） |
| `03_confidence_gate_design.md` | A 支撑 / B 几何（含盆地消解、方向自检）/ C holdout / D sanity；**`reg_gate_v1` 全常量 + 推导数据（D1–D6）**；三档 band 与聚合；fail-closed（缺指标→REJECT） |
| `04_failure_and_fallback_matrix.md` | 六状态机；SAFE 语义；F1–F22 失败矩阵；重复变换/错误码/原因码词表；`[REG]` 日志契约；回退路线 |
| `05_shadow_integration_plan.md` | R3.8 双分支（P/S）+ 对账分支 A；WD01/WD02/f55/f150/f155/f160/clean controls；F1–F5 故障用例；S1–S7 预注册判定门 |
| `06_test_matrix.md` | T37（21 项）+ T38（12 项）+ T39（8 项）测试矩阵与证据入口 |
| `07_r37_summary.md` | 本文件 |

## 3. 对用户 8 项要求的逐条映射

| 要求 | 落点 |
|---|---|
| ① frame 契约冻结（RAW→…→FOREGROUND；方向 current→reference） | 01 §1–§3；canonical B 数值 §3.2 |
| ② Registration artifact（不可变；SHA 绑定 session/leveling/background/算法/时间戳） | 02 全篇；`refmap_digest_v1` §4.3；绑定失效 → STALE（04 F8–F12） |
| ③ Confidence gate（支撑量/几何条件/holdout/合理性；盆地分歧 → AMBIGUOUS 不静默） | 03 §2–§4；盆地规则 §4.2 与 `WEAK_OBSERVABILITY` |
| ④ 状态机（UNAVAILABLE/VALIDATING/VALID/DEGRADED/REJECTED/STALE；仅 VALID 进生产） | 04 §1；DEGRADED = shadow only |
| ⑤ fallback（宁可背景性能下降，不错误吸人；SAFE_FOREGROUND_ONLY） | 04 §2；窗语 = R3.6 条件 A 口径 |
| ⑥ 重复变换防护（frame 标签 + `ERR_DUPLICATE_REGISTRATION`） | 01 §4；04 §4.1；T37-19 |
| ⑦ R3.8 shadow（双链并行、逐帧 equivalence、golden + wrong/stale/missing 故障） | 05 §1–§6；故障用例 §4；等价门 §5.1 |
| ⑧ 测试矩阵 | 06 全篇 |

（R3.10 residual 归因 / R3.11 matcher 优化：未启动，边界在 §6 保持。）

## 4. 关键设计决策（含理由）

1. **REFERENCE_FRAME 不做新定义**，直接取 reference 会话的 LEVELED_SESSION——消除"另定义的 world/reference 系"这一类长期歧义。
2. **artifact_id 用文件字节 sha**，不引入跨语言 float 规范化问题；`manifest.json` 作为完整性锚点（对齐 `captures/leveled` 习惯）。
3. **显式选择、无 auto-latest**：production 的失败模式是"静默换 artifact"，v1 直接不给自动解析器。
4. **registration 存在时 leveling 选择改由 artifact 绑定（按 transform_id）**，旁路 mtime 规则——本仓实测同会话不同 job 的配平解差最大 ≈1.54° roll（202456），mtime 换底座是真实风险（01 §5、04 §4.3）。
5. **gate 新增方向自检（04 §4.4）**：正交性检查无法发现"转置+逆平移"的 writer 方向 bug，用前向/反向残差对比补上（T37-05b）。
6. **sanity bounds 由历史分布推导**：`limit = ceil(2×max_observed)`，observed 取 D1（audited pair 四解法）∪D2（同场候选会话 TLS-direct 两两）——roll 6° / pitch 3° / yaw 5° / θ 7° / |t| 0.20 m / |t_z| 0.15 m。
7. **gate 阈值一律进 artifact 快照**，代码里不放魔法数；修订只能新 profile id（03 §5）。
8. **DEGRADED 允许 shadow、禁止生产**；audited pair 的最终 gate 结果不预判（03 §6），若 WARN 需用户裁决后才谈 R3.9。

## 5. 阈值来源与 PROVISIONAL 清单

- 已锚定（有实测出处）：sanity bounds（D1∪D2）；fit/holdout 残差带（D3：好解 11.0–14.5 mm，坏解 29.9/38.8 mm）；自一致/竞争盆地门（D4）；支撑绝对量下限（D5）；实现硬下限的 ≥10× 处理（D6）。
- **PROVISIONAL（R3.8 实测后必须复核/冻结，未冻结禁止 R3.9）**：`n_correspondence`、`inlier_ratio`、`coverage_xy`、`max_sector_share`、`condition_number`、`eig_ratio`。
- 样本限制（如实登记）：D1 为单 pair 四解；D2 为 6 个候选 pair（场景身份沿用 GL-V01/W03 既有记录，本轮未再证明）；阈值随新 pair 数据升版重导。

## 6. 未决事项（R3.8 及之后）

1. artifact writer 的实现归属与命名（建议与 `leveling.py` 同族的离线 job；R3.8 工单定）；
2. `reg_gate_v1` PROVISIONAL 常量冻结（R3.8 实测 audited pair 后）；
3. audited pair gate 实测状态（若 WARN/DEGRADED → R3.9 需用户裁决）；
4. R3.9 语义确认：registration 接入 = registered 路径 + reference 分支（`background = reference_static OR online_static`，matcher 零改动）；
5. 生成 `captures/registration/<pair>/` 属新数据产物（非 production 代码修改），R3.8 工单中明确授权与落盘路径；
6. R3.10（geometry/missing/sparse 三分单）与 R3.11（matcher 改进）**未启动**；R3.7–R3.9 期间 matcher 冻结不变。

## 7. 边界声明（本轮）

- 未改任何 production/测试代码；未 commit；未采集/部署/联网；未触碰 matcher/ICP/参数/阈值实现。
- 只读检查（SHA 复核、矩阵表示转换、历史分布推导）全部基于既有 artifact；R3.6/R9 digest 未被覆盖或重算。
- 设备/物理/生产接入结论一律 NOT_RUN；整体待 Codex/用户独立复审。
