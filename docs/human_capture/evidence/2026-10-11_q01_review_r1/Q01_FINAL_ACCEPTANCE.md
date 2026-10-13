# Q01 最终裁决 — HUMAN-FUSION-UNIFY-R2

2026-10-11 · 裁决物：`sidequests/human_fusion_lab/`（ISOLATED 研究轮）

## 裁决：**CONDITIONALLY ACCEPTED（研究版）**

不是 7/7 通过就自动 ACCEPTED——本轮经历了真实独立审查与缺陷闭环（1×P0 + 1×P1 + 1×P2 修复 + 1×P2 接受残留）后才给出。

| 判项 | 裁决 | 证据 |
|---|---|---|
| P0 清零 | **PASS**（1 真实 P0 已修到候选级并复测；作者+独立审查一致） | Q01-F01；作者全量 mismatch 0/6520；OpenCode hook 复现并独立复验 0 |
| 关键契约验证 | **PASS**（9/9 九问全 PASS 或 FIXED；无 FAIL 未闭环） | `Q01_INDEPENDENT_REVIEW.md` 对照矩阵 |
| 独立审查实际完成 | **COMPLETED**（opencode-go/deepseek-v4.1-flash 真实产物）+| `opencode_review_report.md`、`opencode_findings.json`（两次 run，第二次前台产出） |
| 浏览器交互 E2E | **PASS**（干净环境 10/10，真 Chrome CDP 非 dump-dom） | `Q01_BROWSER_E2E.json`；`cdp_e2e.js` exit 0 |
| 会话/六算法/索引/状态清除契约 | **PASS** | Q01-F03/F05/F06/F07（作者+OpenCode 一致） |
| R7 泄漏 | **PASS（会话级无泄漏）**；前瞻泛化 UNKNOWN（残留） | Q01-F08 / Q01R-07 |
| R8 UNKNOWN 计入成功 | **PASS（未计入）**；DISPLAY 真人损失 UNKNOWN（残留） | Q01-F09 / Q01R-08 |
| 研究版交付 | **ACCEPTED** | 本轮 |
| 生产接入 | **BLOCKED（持续）** | Q01-F10 / Q01R-10 |
| 物理/设备验收 | **NOT_RUN** | 本轮无 RK3588/NPU/采集 |

## 结论

**HUMAN-FUSION-UNIFY-R2 研究版 ISOLATED ACCEPTED**——前提是接受以下残留：
1. **geometry(post) 是研究型后处理对照**（确认轨迹禁用、不进入生产基线、轨迹召回结论仅限非 geometry 模型）；
2. **R7 是 RETROSPECTIVE_SESSION_HOLDOUT**，跨场景/陌生人员前瞻泛化 UNKNOWN；
3. **R8 DISPLAY 层真人显示损失 UNKNOWN**（无物理 GT）；
4. **生产接入继续 BLOCKED**（RKNN/NPU/RK3588 未实测、S9 GT 不符、DISPLAY 未知、无生产链授权改动）；
5. 浏览器交互仍有 2 项 BLOCKED（循环播放 loop+tracker-reset 专用断言、网络故障注入恢复），未伪造 PASS。

## 生产接入保持 BLOCKED 的依据

`✶` geometry 仅研究对照（Q01R-02）；R7 回顾性 holdout；R8 DISPLAY 真人损失 UNKNOWN；RKNN/NPU/RK3588 未实测（`NOT_RUN/UNKNOWN`）；S9 GT 绑定不符 `BLOCKED`；本轮无生产识别链授权改动。多项 BLOCKED/UNKNOWN 未清零前，**不得**把任何 fusion_lab 模型推广为生产默认或部署到 RK3588。

## R9 开发优先级（建议，不在本轮闭环内执行）

| 优先级 | 方向 | 动作 | 解锁什么 |
|---|---|---|---|
| **R9-1（最高）** | 清残留 P2：geometry(post) 轨迹语义闭环 | 改 `core/human_pipe_lib.js classify_human` 提供可选 CONFIRMED_HUMAN 通道 **或** engine 暴露后处理钩子，让 detector 能在不伪造的前提下重算 tracker 确认。**前提：获得授权改动冻结/生产识别链**——本轮未授权。 | geometry 从"仅候选级对照"升级为可作轨迹对照 |
| **R9-2（高）** | 真实端到端召回 | 把 R7 升级为**前瞻采集**：陌生人员/独立家具/未见过场景的新会话，按 frozen 规则盲评 | RETROSPECTIVE_SESSION_HOLDOUT → 前瞻；解锁"泛化"结论 |
| **R9-3（高）** | DISPLAY 层真人损失 | 物理 GT（人工标注显示帧） + 真实浏览器显示帧对比，量化"真人 DISPLAY 损失" | R802 DISPLAY 从 UNKNOWN 转可测 |
| **R9-4（中）** | RK3588/NPU 实测 | 把 xgb69_candidate 部署到 RK3588、测 CPU/NPU 时延与内存、RKNN 转换 | 解锁生产部署评估（但仍需 R9-2/R9-3） |
| **R9-5（中）** | 浏览器 E2E 补漏 | 补循环播放 loop+tracker-reset 专用断言、网络故障注入恢复 | Q01_BROWSER_E2E 的 2 个 BLOCKED 清零 |
| **R9-6（中）** | S9 有效 GT | 解决 S9 SESSION_SHA_MISMATCH（重新采集或修复 GT 绑定） | S9 评价 BLOCKED → 可测双人交叉 |
| **R9-7（低）** | 生产识别链正式改动 | 需明确授权；把 fusion_lab 中确认无误的 detector/server 语义回流 `pc_apps/` | 生产版本发布（此前持续 BLOCKED） |

**当前不发布生产版本不在 Q01 闭环内推进 R9**——R9-1/R9-7 都需明确冻结模块或生产识别链授权。
