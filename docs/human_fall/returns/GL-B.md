## 2026-10-05 GL-B R1 / OpenCode / SUBMITTED

# GL-B R1 回传（质量/可信度模块；实现者自述）

状态 SUBMITTED。B 实现期自检发现并修复 1 个本单内缺陷（required 区缺失未入 hard gates → valid 误真）。实现者已停写（按用户 2026-10-05「一次性做下去」指示，自验后直接进入 GL-C；指定独审可在后续批量进行）。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-B（AGL-B-01..05）/ R1 / OpenCode CLI（模型自报 opencode-go/deepseek-v4.1-flash）/ 2026-10-05（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA：`docs/human_fall/tickets/GL-B_adaptive_quality.md` v1，SHA256=3f6f68cadc245fe152b93a19b078a279221e135f0ac15219393ae56b83de7539（未改动）。
- 起始 branch/HEAD / 工作树：master / 8676bb479d4ae35cf22075cfe70225cf2220572a（提交时不变）/ 无已跟踪文件修改；index 中 adaptive_ground\* 与 evidence\* 出现外部 staged 状态（非本 writer 操作，未动 index）。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail`（复用冻结原语 residual_stats/_tangent_basis/digest 等，无新依赖，单模块+单测试文件）。
- 证据目录：`docs/human_fall/evidence/2026-10-05_agl_b_r1/`。

## B 前置闭合（A 独审登记的两项非阻断观察）

| 观察 | 处理 |
|---|---|
| region_codes 无 SHA/未入 domain_id | `selection.py`：构建计算 `region_codes_sha256`、validate 重算、并入 `domain_id` 内容绑定、引用摘要同步 |
| validate_plane_estimate 未比对 sign_anchor | `contracts.py`：传入 domain 时要求 `estimate.sign_anchor == domain.spatial_basis.up_axis` |

A 专项（7/7）与全量回归在改动后仍通过（见 11 日志）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| B 自检缺陷（required 区缺失） | 只为「存在的」required 区建 gate；缺失区仅写入 region 记录与原因，未进 hard_gate_results → hard_ok 未受影响，valid 误为 true | `evaluate_quality` required-missing 路径（bad ROI/多ROI缺失场景） | `quality.py` 增加 `required_region_present` gate（passed=False）+ 原因映射 `GL_REQUIRED_REGION_MISSING` | 存在区行为不变；缺失区必 valid=False |

其余为规划内新增能力，实现前诊断/操作矩阵见 00_diag.md（全域 oracle、离群体未裁尾、低 RMS 退化、config 关系、caller/reload）。

## 实际变更

| 文件 | 本轮用途与修改 | 提交源码 SHA256 |
|---|---|---|
| `core/adaptive_ground/selection.py` | 前置：region_codes_sha256/绑定/引用 | c360875267f8c70a0f612d4a3cd15b627ff57b4f6dd44bbb6b9f67b97605aa95 |
| `core/adaptive_ground/contracts.py` | 前置：sign_anchor 比对 | bc862be48a3574297d5a65eb910a5bee2f49d7c250e3ffd886fff00d32bc8ea2 |
| `core/adaptive_ground/quality.py` | 新增：QualityReport/7 分项/hard gates/区域门 | 965faa8a8eb8faafc8936417846bea43045ed5138925eb543a6d987b602d70b9 |
| `tests/test_agl_b_quality.py` | 新增：6 用例（oracle/退化/score/区域/P02/追溯） | 850f3a7994add0b84b91dfac5463f9e786be567109cea2a222c83222725a4af1 |

## 逐条验收

| 验收ID / 入口 | 类型 | 命令/位置 | 结果（自验）/退出码 | 日志 |
|---|---|---|---|---|
| AGL-B-01 | offline synthetic | test_full_and_region_oracle_untruncated_denominators | PASS：全域与逐区 RMS/P95/MAD/support 独立标量 oracle 差 ≤1e-12；点/支持分母显式；RANSAC full=全域重算，inlier-only RMS 差分证明未顶替 | 10_ 日志 |
| AGL-B-02 | offline synthetic | test_hard_gates_reject_low_rms_degenerates | PASS：共线→上游无效；窄带 λ/跨度门拒；25 点低 RMS 拒；单格 1600 点低 RMS 拒（valid=False） | 10_ |
| AGL-B-03 | offline synthetic | test_score_bounds_monotonicity_and_config_relations | PASS：12 个配置负例全拒；噪声单调（q_rms/confidence）；分项 [0,1]；hard fail raw_score>0 但 confidence=0、valid=False | 10_ |
| AGL-B-04 | offline synthetic + P02 fixture | test_required_region_fail... / test_p02_leave_one_out_fail_preserved | PASS：四区整体好+3% 坏区(+8cm)→invalid、REGION_FAILED、其余区 PASS；35° 陡面 tilt 拒；required 缺失拒；P02 留一区 FAIL 精确复现（#1/#3 P95>5cm、#2 PASS、#4 RMS/P95/support FAIL，与已发布 cm 值差 ≤5e-6m） | 10_ |
| AGL-B-05 | offline synthetic | test_traceability_binding_no_stale_leak | PASS：report_id 可重算、JSON 安全；篡改 estimate/domain/anchor 原子拒；重复评估逐位相同；新 config 新 ID、无旧 score 泄漏 | 10_ |
| AGL-B-S01 | — | 基线/诊断/回归/SHA/停写 | 流程完成（自验）；指定独审 NOT_RUN（待批量派发）；不接 runtime | 00/30 |

回归：B 专项 Ran 6 / OK / exit 0；全量 Ran 471 / OK / exit 0（465+6）。冻结 10 依赖 blob=基线；HEAD 不变；未动已跟踪文件。

## 未闭合与限制

- 指定二审未跑（按用户一次性指示连续开发，批量复审）；未伪报。
- 极窄/覆盖等阈值仍为测试所用显式配置（DRAFT 语义）；GL-F 用真实数据冻结 profile；B 不写运行 YAML。
- 置信度：`confidence_geo` 为启发式指数，非正确概率；hard fail 一律 0。
- 后续：C（一致性仲裁）按用户指示直接启动；D/E 依序；不启动 H/I；设备/物理 NOT_RUN。

## 交给复审

- 证据索引：00_baseline.txt、00_diag.md、10_test_agl_b_log.txt、11_regression_after_b.txt、30_scope_check.txt。
- 源码差异与 SHA：见上表与 30；前置闭合两项为 A 文件最小增量（region SHA / sign_anchor）。
- 当前工单下一步：批量指定只读二审（A R2 + B R1），通过后收口；C 由本轮连续开发提交后另行追加回传。
