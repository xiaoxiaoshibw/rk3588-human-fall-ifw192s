# C1 独立复审指令 R2（OpenCode opencode-go/deepseek-v4.1-flash）

**你是独立审计员，不是实施者。** 只读、判定、给证据锚；不改任何代码/证据。时间盒 ≤ 5 分钟（一轮）。

**【执行方式】** 本文件即你的完整任务书。通读全文 → 按"证据根"只读核对（可用只读工具查看 `docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization/` 下任何文件，**不得修改**）→ 直接输出**最终 Markdown 复审报告全文**作为你的回复（无需再向我提问或等待）。报告即你的回复正文。

## 本轮性质（与 R1 的区别，先读这句）
R1（2026-10-09）是**实施轮**（用户授权"一次性完成 8 项"），产出 FINAL_REPORT.md 后被你 FAIL 并返修。
本 R2（2026-10-10）是**复核轮**：在**现行代码**上独立重取证据，判定 R1 的结论是否仍然成立 + 闭环 R1 的全部 FAIL。
**不要把它当新实施轮要求新设计/新实现**；你的任务是审计这轮"复核+重跑"是否诚实、完整、可复现。

## 证据根
`D:/Code/ldiar/docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization/`
- **旧 r1 实施轮产物**（已冻结，SHA 见根 SHA_MANIFEST.sha256）：FINAL_REPORT.md / ab/ / attribution*/ / rf_v2/ / flicker_analysis.json / workspace/
- **本 R2 复核轮产物**：r2/REVIEW_AND_RERUN_R2.md（主报告）、r2/C1_REVIEW_PROMPT_R2.md（本文件）、r2/SHA_MANIFEST_R2.sha256（110 文件，零自引用）

## R2 复核轮的可复现性主张（请重点攻击这些）
1. **探针重跑逐位一致**：R2 重跑 production probe（12 jsonl）+ v2 硬门 probe（12 jsonl），与旧 r1 evidence **24/24 cmp IDENTICAL** → 主张"生产自 R1 后零污染、探针确定"。
2. **锚点 SHA 未变**：`b2a_shadow_probe.js 74b4a272…` / `detect_overlay.js 585d2964…` / `human_pipe_lib.js 8b50a221…`(≡ B2-A protected_snapshot) / `rf_person_v1.json 4c83db11…` / `bg_envelope.json 28afdaa4…`，与 R1 复审基线逐位一致。
3. **13/13 锚点**：`label_audit/report.md` 现行重取仍全 PASS（find_hot/find_clusters/associate 数值指纹一致 + TRACK_GATE/TTL/MIN_AGE/BG_CELL/z带/+0.25/min30/top4/claimed/阈值档）。
4. **JS 单测**：detect_overlay 36/36、human_pipe_lib 38/38、panel 全 PASS。
5. **旧证据完整性**：旧 manifest 68/69 一致，唯一 FAILED = manifest 自身（自引用不可能——任何 manifest 无法含自身哈希）。R2 已改为零自引用 manifest。

## R1 的 FAIL → R2 是否闭环（逐条裁定）
| R1 裁定 | R2 处置 | 请你裁定 CLOSED/OPEN |
|---|---|---|
| #1 Wilson 帧级伪重复（915=6段，0.994→段级0.61） | rf_v2/gate_by_session.md 段级 n=6 重算，作废 gate_confidence.md，下界 0.61 如实暴露 | |
| #2 泄漏审计方向反/域混合 | leakage_slice.md 簇级单域 + wilson_perfeature.md importances 诊断；"泄漏已排除"降级为"域内不可证，需域外 holdout" | |
| #3 v_airoi=100% 循环论证 | 降为不作独立证据，仅以 v_p（生产拓扑 98.1–99.1%）为可信项 | |
| #4 furniture_tracks 命名/悬空引用 | repair_r1 更名 furniture_reentry_episodes（一次 id 出/灭段）；flicker_analysis.json 入证据根 | |
| #5 推理耗时定性 | ab/summary.md 补结构性估算 + JS/Py prob 差上限 0.0500 | |
| A1 mf_v2 空目录 | 已删 | |
| A2 零动态真值 | 动态召回标 UNKNOWN（不制造假 GT） | |

## 审查重点（只看能不能被拆解）
1. **复核轮有效性**：R2 重跑产物与旧 evidence 逐位一致，是否足以证明"生产未污染"？还是一致性只说明"探针确定"、不能排除"R1 的探针本身就偏离生产"？（提示：核对 label_audit 的数值指纹比对是真比对还是恒真）
2. **53 维特征 bug**：`workspace/c1_rf_v2.py` v2e 段 51 维 vstack 53 维执行期崩溃，导致新特征消融无法复跑。这是否影响 C1→C2 判定？（C1 未授权新特征，但对 C2 透明度）
3. **动态=UNKNOWN 的处理**：把动态真人召回标 UNKNOWN 而非凑数，是诚实还是回避 C1 核心目标？
4. **硬门 n_pts≥500 的域限**：person 仅 ≤2.5m、家具仅同批柜面，段级 Wilson 下界 0.61。R2 主张"域内安全预过滤"是否过度？

## 必须遵守的输出
- 仅 Markdown 表 + bullet，无热词。每条裁定 PASS/FAIL/BLOCKED + 证据锚（文件路径+行 或 json 键）。
- 先回答"R2 复核轮是否可信"（可复现性 5 主张逐条），再逐条闭环 R1，最后 5 个审查重点。
- 最终结论两行：**(a) C1 = PASS/FAIL/BLOCKED**；**(b) 进入 C2 = YES/NO + 一段主理由**。
