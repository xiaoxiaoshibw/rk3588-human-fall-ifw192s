# HFUS-GROUND-OBSERVABILITY-RD-01

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-GROUND-OBSERVABILITY-RD-01 / r1 第一批（E0+E1 只读测量）/ OpenCode（用户本聊天派发并指定为本项唯一生产 writer）/ 2026-10-17
- 验收表路径 / 版本 / SHA（提交时记录）：`docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1/ACCEPTANCE_V1.md`（唯一现行表，OB01–OB10）；SHA 见 `results/MANIFEST.json → artifact_sha256`
- 执行方式 / 实际会话与模型（可得才填）：OpenCode 本机离线会话，opencode-go/mimo-v2.6-pro；命令与退出码见 MANIFEST.json
- 状态：**SUBMITTED**，非 ACCEPTED。软件（只读测量）逐条自验 PASS；设备/物理 NOT_RUN；人体/地面身份/独立效果 BLOCKED。
- 起始 branch/HEAD / 工作树 / 范围内用户差异 / 源码与配置SHA证据：master / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`（与 PLAN_CHECK 基线一致）/ 历史脏树保留、未 commit/push/reset/clean / 本轮仅新增下列文件 / 源码与产物 SHA 全量记录于 `results/MANIFEST.json`
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full；策略 RESEARCH=观测性/几何未知 + ENGINEERING=来源核验与只读追溯，RESEARCH 下按 AI_DEVELOPMENT_POLICY 保留必要中间诊断）

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| OB08/类别9 地面"找不到" | `_holdout_gate` 支持率门 `min_holdout_support=0.5` 的分母是全场景 holdout 点，地面点占比天花板 ~22–25% → 正确地面平面被判 `ground_holdout_failed`（4/4 例） | core/ground.fit_ground_plane 消费者：旧地面自动入口、constrained 前置资格；导致任何真实房间地面进入 INVALID 状态 | 本轮**不修复**（旧门只读）；属派发实施项的候选修复，须新验收版本 | 旧门、旧 FAIL、旧数值全部保留不翻案 |
| OB02/类别1 采样口径 | "0.5°×0.5°"被当成规则网格；实测无任何网格锁定（0.5° 锁定率 0.17），角度近连续 0.02° 量化 | 一切 2D 表示（距离图/BEV）的邻接语义；距离图只能作组织/提案 | 方法学约束写入 LIDAR_OBSERVABILITY §2 | 5.24cm@6m 作为有效间距换算值获实测支持（5.46cm），不删除 |
| OB04 多帧口径 | 角度覆盖 1 帧饱和、体素覆盖持续增长被混为一谈 | 多帧建模/背景建模的覆盖估计 | 分账曲线 E0_SUMMARY.accumulation_C | 不把多帧点数增加等同分辨率提高 |

同类调用者核查：`fit_ground_plane` 的 holdout 门同样作用于 constrained 入口之前的自动拟合路径（core/ground.py 单一实现，无第二份拷贝）；`ground_diagnostics.residual_stats` 为纯函数被本批只读复用，未改动。

## 实际变更

全部为**新增**文件，无一行既有文件被修改：

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `sidequests/hfus_ground_obs/r01/source_io.py` | 只读会话读取（strides 只取每行 0..11B）+ 排他写护栏 | 新增 | 见 MANIFEST.json code_sha256 |
| `sidequests/hfus_ground_obs/r01/e0_density.py` | E0 角度结构/间距/累积/理论表 | 新增 | 同上 |
| `sidequests/hfus_ground_obs/r01/e1_ground_obs.py` | E1 地面存在性/径向间距/旧入口复现/五态掩码 | 新增 | 同上 |
| `sidequests/hfus_ground_obs/r01/e1_old_holdout.py` | 旧入口 holdout/support 门细节（OB08 根因） | 新增 | 同上 |
| `sidequests/hfus_ground_obs/r01/test_measure.py` | 5 项合成夹具自检 | 新增 | 同上 |
| `docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1/*` | PROTOCOL_V1（运行前冻结）/ACCEPTANCE_V1/三份报告/results/* | 新增 | 见 MANIFEST.json artifact_sha256 |
| `docs/human_fall/returns/HFUS-GROUND-OBSERVABILITY-RD-01.md` | 本回传 | 新增 | — |
| `docs/human_fall/WORKFLOW.md` | 顶部新增本工单条目（历史条目原字节保留） | 追加一行条目 | — |

源数据零写：`data/`、`captures/`、旧证据、生产源码、`pc_apps/human_replay/leveling.py` 写入入口均未触碰。单位米；角度度；坐标 RAW（未应用任何配平）。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| OB01 源冻结/零写/拒覆盖 | offline | `python -B -W error e0_density.py`、`e1_ground_obs.py`（内含 sha256 重算）+ test_measure 护栏用例 | PASS，exit 0 | meta `eeb336b8…82ad4`、points `254c481f…f84f1`，与 r01 SOURCE_PREFLIGHT 冻结值一致；MANIFEST.json |
| OB02 角度结构/行守恒 | offline | e0_density.py frame_metrics | PASS，exit 0 | E0_SUMMARY.frames_A：31 帧守恒全 PASS；锁定率 0.172@0.5°；步进 0.02°；el 2370 层 |
| OB03 间距/覆盖 | offline | e0_density.py spacing_by_band | PASS，exit 0 | E0_SUMMARY.spacing_B：NN 中位 2.17→6.37cm（2→8m）vs 理想 1.75–6.98cm |
| OB04 多帧累积 | offline | e0_density.py accumulation | PASS，exit 0 | E0_SUMMARY.accumulation_C：角度 +1.5%、体素 +117%、逐帧新增 3449→27-30 |
| OB05 理论表 | offline | e0_density.py theory | PASS，exit 0 | E0_SUMMARY.theory_E：546 行 MODEL_ESTIMATE，假设列分列 |
| OB06 地面存在性/五态 | offline | e1_ground_obs.py | PASS，exit 0 | E1_SUMMARY.ground_presence + E1_MASK.npz：带行 1,892,649（26.35%）；掩码 2529/622/153/8/0 |
| OB07 径向间距 vs 公式 | offline | e1_ground_obs.py | PASS，exit 0 | E1_SUMMARY.ground_radial_spacing：0.0088/0.0179/0.191/0.0269m vs 公式 0.04–0.24m |
| OB08 旧入口复现 | offline | e1_ground_obs.py + e1_old_holdout.py（只读 core.ground） | PASS，exit 0 | E1_OLD_ENTRY_DETAIL：4/4 ground_holdout_failed，支持率 0.22–0.25<0.5，支持 rms 0.020–0.025 |
| OB09 支持对比/软先验/互检 | offline | e1_ground_obs.py numeric_crosscheck | PASS，exit 0 | 自算 vs residual_stats 差 <1e-5（同族互检）；TLS 先验带来源 SHA 记录，未提升为标定 |
| OB10 报告/追溯 | offline | 三份 MD + MANIFEST.json | PASS，exit 0 | LIDAR_OBSERVABILITY / GROUND_FAILURE_ANALYSIS / CURRENT_STATE_AUDIT |

回归与保留失败：`python -B -W error -m unittest test_measure -v` 5/5 exit 0；`python -B -W error e0_density.py` 首跑 exit 1（theory() AttributeError，已修）、`python -B -W error e1_ground_obs.py` 首跑 exit 1（IndentationError，已修）——两次失败保留在终端与 MANIFEST.commands，不删不改口径。预算：E0 33.95s、E1 8.9s、旧门细节 <5s，均 ≤180s probe 上限；峰值 RSS 未测（Windows，NOT_MEASURED，如实记录）。

## 未闭合与限制

- 未满足的验收ID：无（OB01–OB10 自验 PASS）；但 PASS 仅限"只读测量与来源追溯"，不覆盖任何效果。
- 契约允许的算法/证据限制：无 GT → 识别指标 null；泊松命中为 MODEL_ESTIMATE；带内 RMS 有选择偏差不作验证指标；ring/timestamp/intensity 未解释；NO_RETURN 与遮挡阴影不可分。
- 范围外新需求及后续建议：第二批（E2 多帧地面融合、E3 表示对比、E4 人体几何、文献综述、五路线评分、NEXT_STAGE_DEVELOPMENT_PLAN、FINAL_RECOMMENDATION）未派发；旧 holdout 门修复与 PLAN S0–S5 实施须另行派发并建新验收。
- 设备/物理未跑项：安装高度、重力方向、法向朝向、板端可行性、独立 D 全部 NOT_RUN/BLOCKED。

## 交给Codex独立复审

- 现行验收表与本轮变更记录：`ACCEPTANCE_V1.md`（唯一现行表）+ 本回传；WORKFLOW 顶部新条目。
- 根因诊断/完整入口检查证据：GROUND_FAILURE_ANALYSIS §3（旧门支持率根因，4 案例 + holdout 细节）；CURRENT_STATE_AUDIT §3 类别表。
- 源码差异与SHA证据：`results/MANIFEST.json`（code/artifact/source SHA 全量）；无既有文件改动。
- 原始日志索引：results/MANIFEST_E0.json、MANIFEST_E1.json、MANIFEST.json commands（含两次 exit 1 保留）。
- 当前工单下一步：等用户派发第二批或 PLAN 实施；本回传不自动启动任何实现。
