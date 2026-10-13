# HFUS-D02 待审帧目标清单（种子/依据 · 2026-10-11 r1）

本清单是 D02 待审包构建的输入依据，全部由只读证据确证，非本轮新跑算法得出。
来源标注到具体证据文件。

## 会话名 ↔ 落盘 cap_* 映射（质量分母合计 2605 帧）

来源：`sidequests/human_fusion_lab/results/AUDIT.json`、诊断报告 `docs/human_capture/evidence/2026-10-11_human_fusion_diagnosis_r1/REPORT.md`。

| 会话 | sid | 活动 | 总帧 | 已标/合格 | UNKNOWN | GT 版本(AUDIT冻结) | 绑定 |
|---|---|---|---|---|---|---|---|
| S1 空场/家具 | cap_20261010_175227 | empty-room | 304 | 304(FURN/BKG) | 0 | GT_V3 | OK |
| S3near 近景 | cap_20261010_175429 | near | 258 | 258 | 0 | GT_V1 | OK |
| S3far 远景 | cap_20261010_175553 | far | 464 | 99 | ~365 | GT_V1 | OK |
| S4 walk-stop | cap_20261010_175804 | walk-stop | 239 | 11 | ~228 | GT_V1 | OK |
| S5 turn | cap_20261010_175943 | turn | 202 | 6 | ~196 | GT_V1 | OK |
| S6 occlusion | cap_20261010_180235 | occlusion | 238 | 71 | 167 | GT_V1(另有V2/V3未审) | OK |
| S7 far5m | cap_20261010_180337 | far5m | 251 | 12 | ~239 | GT_V1 | OK |
| S8 long-still | cap_20261010_180557 | long-still | 523 | 53 | ~470 | GT_V1 | OK |
| S9 双人 | cap_20261010_180751 | two-person | 126 | 0 | 126 | GT_V2 | **BROKEN(aaaa…)** |

合计已标/合格观察=814，PERSON 观察=510，UNKNOWN 帧=1791（诊断报告 §资格表）。

## S6 重点待审帧（授权“f128/129/130/171/187/188 及相邻帧”）

来源：诊断报告 lines 137-147 + ATTRIBUTION（gate_xy=0.75, proposal_cov=0.1）。
RF 无候选帧 = [91,128,129,130,171,187,188]；XGB 无候选帧 = [128,129,130,171,187,188]。
f187/f188 的 234/245 缺参考删除在诊断报告 line 11/12 与统一计划 §1 D01 验收中均已点名。

| 帧 | RAW人体GT | crop | missing-ref | 包络 | BG后残 | 失败层 | 纳入理由 |
|---|---|---|---|---|---|---|---|
| f91 | 303 | 5 | 241 | 2 | 55 | PROPOSAL(<60) | 授权邻帧；retention 后 XGB 恢复298的对照 |
| f128 | 33 | 1 | 2 | 12 | 18 | PROPOSAL(no valid comp) | 授权点名；GT 15–33 点 |
| f129 | 22 | 0 | 0 | 13 | 9 | PROPOSAL(17<60) | 授权点名 |
| f130 | 19 | 0 | 0 | 9 | 10 | PROPOSAL(18<60) | 授权点名 |
| f171 | 36 | 0 | 8 | 4 | 24 | PROPOSAL(31<60) | 授权点名；细粒度也未救回 |
| f187 | 260 | 8 | **234** | 9 | 9 | **BG（缺参考）** | 授权点名；缺参考删除主因 |
| f188 | 268 | 6 | **245** | 3 | 14 | **BG（缺参考）** | 授权点名 |

构建时另抽 f128±1、f187±1、f188±1、以及 f171、f91 邻帧作 context。S6 同时存在未审计 GT_V2/GT_V3，本工具按 AUDIT 冻结 GT_V1 标记，V2/V3 问题登记给 owner(Codex/D01)，不在 D02 裁定。

## S4/S8 连续静止窗（授权“≥20 秒连续静止窗”）

来源：诊断报告 lines 59-63。S4 11/239=4.60%(24.67s)，S8 53/523=10.13%(54.12s)，但诊断明确指出“不能据此证明完整一分钟静止”。
→ 本工具产**候选连续窗**（按 GT 帧连续、无 uncertain_intervals 截断筛选），标 qualification=PARTIAL/UNKNOWN，交人工确认是否构成有效 ≥20s 静止窗。未人工确认不入 val/test 静止资格分母。

## S5/S7 低覆盖区间（授权）

S5 6/202=2.97%(20.83s)、S7 12/251=4.78%(25.90s)。标 reason=coverage_gap / low_coverage，机器 qualification=UNKNOWN。

## S1 首/中/末 + 家具变化点（授权）

S1 空场/家具（FURN1520+BKG304）。用于负例来源但**不得把同五家具传播 1515 次当独立家具数**。作者抽取首段(f0–fN)、中段、末段、以及 polygon/track 目标变化帧作为家具身份变化点候选，全部需人工确认是否独立负例。

## S9 双人（授权“成员、身份、SHA 绑定”）

- GT_V2.session_sha256.points = "aaaa…"(64个a) 占位 → **INVALID_BINDING**，不能证明标签对应当前 capture。
- 36 个 PERSON 对象 / 18 帧（LAYER 报告甚至声明 126 帧 total、both_person 帧≥2track）未独立核实。
- 修复草稿 S9_GT_PROVENANCE_DRAFT.json `source:"LABEL_DERIVED:GT_V2-broken-binding"` / review_status=DRAFT_UNREVIEWED / trusted_gt=false。
→ 双人身份/continuous track/member 全部 BLOCKED；本工具的待审包只把 S9 作为 **未知来源候选** 登记，机器 qualification=INVALID_BINDING/UNKNOWN。

## 资格/分母与 split 现状（核对项 #7 输入）

来源 AUDIT.splits / 诊断报告 lines 73-81：
- 现有 split: train=[175227,175429,175804,175943] / validation=[175553] / test=[180337,180557] / stress=[180235] / blocked=[180751]。整会话单 fold。
- 负例：train known neg 566；validation S3far neg 0/UNKNOWN 1,635；test S7+S8 neg 0/UNKNOWN 1,680；stress S6 neg 0/UNKNOWN 574。val/test/stress 无有效人工负例。
- 真实风险：早期 RF train_person_rf.py:56 复制负例、:85 跨 fold 指派（泄漏证据）；当前 XGB 未证有同样问题，但未知。
→ D02 split 草案禁止复制负例，requires cross-fold exact_duplicate==0。

## 不在本任务裁定的问题（登记交 owner）

| 问题 | 现状/发现 | 应交 owner |
|---|---|---|
| S6 GT_V2/V3 与 V1 双版本不一致 | AUDIT 冻结 V1；V2/V3 未审 | Codex / D01 |
| 8400 万点 S1 GT 是否全人工逐帧 | source=human 不证明第二人复核 | 用户人工审核 |
| leveled-compact 域命名误导 | 字段叫 raw_point_indices 实为 compact | Codex（文档级） |
| early RF 跨fold负例复制 | train_person_rf.py:56/85 | Codex / D05a |
| 集合统计分母口径 | 2605/814/1791 已确证 | 本任务资格报告引用 |
