## 2026-10-05 GL-C R1 / OpenCode / SUBMITTED

# GL-C R1 回传（三估计器一致性仲裁；实现者自述）

状态 SUBMITTED。按用户「一次性做下去」指示，自验后直接进入 GL-D。指定独审待批量进行。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-C（AGL-C-01..05）/ R1 / OpenCode CLI（模型自报 opencode-go/deepseek-v4.1-flash）/ 2026-10-05。
- 验收表：`tickets/GL-C_adaptive_consensus.md` v1，SHA256=216fcdd2f08cc30bc081389c18a5860ed944a43f8b198310e0e860625e8c2af5。
- 起始 branch/HEAD：master / 8676bb479d4ae35cf22075cfe70225cf2220572a（不变）；无已跟踪文件修改。
- ponytail 路径：`C:\Users\30680\.config\opencode\skills\ponytail`（复用 digest/canonical_plane/validate 原语；无新依赖；单模块+单测试文件）。
- 证据：`evidence/2026-10-05_agl_c_r1/`。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| C 自检（实现期）| `_member` 对质量摘要键集过严，`quality_summary` 的 `quality_report_id` 被拒 | B→C 桥接 | `consensus.py` 允许可选附加键（精确白名单） | 无报告内容语义变化 |
| 设计要点（非缺陷）| 边界测试初版用「pitch 增量=法向夹角」近似（roll≠0 时夹角≈cos(roll)·Δpitch；RANSAC raw 与 TLS 有固有小幅差） | 测试构造 | 统一 reference 角 + roll=0 基座，使增量=绝对角 | 产品代码阈值语义不变 |

实现前诊断/操作矩阵见 00_diag.md。

## 实际变更

| 文件 | 用途 | SHA256 |
|---|---|---|
| `core/adaptive_ground/consensus.py` | 新增：pairwise/家族/支持簇/GOOD-DEGRADED-BAD/选择/score cap | eb583d1ab269716ea045341f4d5e12653c98428525e434e8888297ab1905dbc4 |
| `tests/test_agl_c_consensus.py` | 新增 5 用例（oracle/边界矩阵/家族/非传递+顺序/P02 实景） | 72be58acdd2f874de1a9148f775e74ee0c08ed3d3c6edcc424880b60f102c8ed |

## 逐条验收（自验）

| ID | 结果 | 证据 |
|---|---|---|
| AGL-C-01 | PASS | pairwise 角/offset/pitch/roll 与独立标量 oracle ≤1e-12；n≈−n 翻转后与未翻转结果 ≤1e-12（非 180°）；domain/units/frame/config/epoch 错配全部 raise |
| AGL-C-02 | PASS | 真实 A+B 管线 3/3 GOOD（selected=tls、families=[ls,robust]、update=true、confidence=min 成员）；3 仅 degraded 门→DEGRADED；.4999/.5001/1.4999/1.5001 边界语义唯一 |
| AGL-C-03 | PASS | LS 对+RANSAC 远→DEGRADED LS-only、update=false、reason GL_ROBUST_DIVERGENCE（不二票压鲁棒）；TLS/SVD 数值不一致 numeric_check_ok=false 且原因可见；跨家族+enabled→受 限 candidate（update=true）；LS-only 默认 false、flag 可显式开 |
| AGL-C-04 | PASS | A≈B/B≈C/A−C 远→BAD（两个最大簇，不并三）；全横向法向（无方向）→BAD+GL_NORMAL_INVALID；插入序重排输出逐位相同；tie-break 固定（等分 tls，svd 高取胜 svd） |
| AGL-C-05 | PASS | cap：DEGRADED confidence=min(成员,.7)；BAD=0；selected/支持簇/原因完整；report_id 可重算、JSON 安全；P02 实景 0.74136°→DEGRADED、整体非 GOOD |
| AGL-C-S01 | 流程完成（自验）；独审 NOT_RUN | 00_diag/30_scope/日志 |

回归：专项 5/OK/exit 0；全量 476/OK/exit 0（471+5）。

## 未闭合与限制

- 指定独审待批量；不伪报；不接 runtime。
- last_good×LS-only 的“有/无资格”细判属 GL-D（C 只给 update_candidate_allowed 标志）；非传递簇的保守 BAD 不提供自动恢复，需 D 的恢复窗口。
- 阈值仍为测试显式配置（DRAFT）；GL-F 冻结 profile。

## 交给复审

- 证据：00_diag.md、10_test_agl_c_log.txt、11_regression_after_c.txt、30_scope_check.txt。
- 下一步：GL-D 由本轮连续开发继续提交回传。
