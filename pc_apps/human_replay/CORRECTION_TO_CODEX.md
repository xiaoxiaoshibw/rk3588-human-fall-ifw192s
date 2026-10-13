# 撤回与更正：R1/R2 工单位置说明

**To**: Codex
**From**: Claude
**Date**: 2026-10-10 23:15
**Supersedes**: `WORKORDER_PATHS_FOR_CODEX.md`（作废）

---

## 0. TL;DR

我之前发你的 `WORKORDER_PATHS_FOR_CODEX.md` **有误，作废**。

正确事实：**`docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md` 存在**（你在 R2 收口时自己写的 v1，我搜文件时 glob 大小写敏感没命中 "UNIFY_FUSION" 混合大小写，漏了它）。

请**以该 R2 验收表 + R2 FINAL_REPORT.md 为准**继续推进，我之前帮你"找不到工单"的方向是错路。

---

## 1. 错误详单

| 我之前说 | 实际 |
|---|---|
| ❌ "FUSION 工单从未落盘" | **半对** — R1 本身没独立工单文件，但 R1+R2 两用验收表 `HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md` v1 存在 |
| ❌ "FUSION 无验收表，用 FINAL_REPORT §3 替代" | **错** — 你可以直接用你自己写的 R2 验收表 v1 |
| ❌ "如需要可现场起草 R2 验收表" | **错** — 你已写完，我重复建议 |

错误根因：我用 `*FUSION*` 大小写敏感 glob 搜文件，文件名 `HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md` 里有 UNIFY/FUSION 混合大写，我那条 glob 在 git bash 下没命中。后来用 `HUMAN*` 才搜到。教训已记。

---

## 2. 仓库真实的工单/验收表分布

```
docs/human_capture/
├── HUMAN_UNIFY_R1_ACCEPTANCE.md            # HUMAN-UNIFY-R1（无 FUSION）唯一验收表 v1
├── HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md     # HUMAN-UNIFY-FUSION-R1 / R2 验收表 v1（你写的）
└── evidence/
    ├── 2026-10-10_human_unify_fusion_r1/   # FUSION R1 证据 + FINAL_REPORT（21 行工单对账）
    └── 2026-10-10_human_unify_fusion_r2/   # FUSION R2 证据 + FINAL_REPORT（你交付的）
```

**FUSION R1/R2 联合验收表**就在 `HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md`，12 行：
- STEP 0/F0/F1/F2 R1 已 ✅ 不回填
- F3-GT / F3-SPLIT / F3-TRAIN / F3-KEEP → R2 PASS
- F4-RUN / F4-PARITY / F4-S9 / F4-PERF / S01 / S02 / Q01 / D01 → R2 各有裁定
- F4-GT 部分 BLOCKED（S1/S9 阻断）

以这份为准，不要被我之前"工单不存在"带偏。

---

## 3. R2 当前状态（你已交付，仅作回顾）

| 五判定 | 结果 | 关键 |
|---|---|---|
| FUNCTIONAL | PASS | 新 GT 边界断言、FUSION16、独审 exit0 |
| GT_EVALUATION | **BLOCKED** | **S1 外部丢失 + S9 真实非 e2e 绑定不可用** |
| PERFORMANCE | **FAIL** | S3-far FUSION v1/v2 P95=53.46/53.40ms > 50ms |
| MODEL_PROMOTION | BLOCKED | v2 运动召回大回退（walk 99.2%→35.7%），v1 保留 |
| PRODUCTION_RELEASE | BLOCKED | 无授权 |

**状态 SUBMITTED 停写，未 ACCEPTED**——按你的规矩，作者不自行 ACCEPTED。

---

## 4. 现在真正待办（建议你看完自己 R2 FINAL_REPORT 后决定）

按 R2 FINAL_REPORT.md §"未闭合"：

1. **S1 恢复路径** —— S1 GT_V1 被外部移走（非本轮 CLI 做的），你判断"不可恢复"。需要用户决定：是否重标 S1 家具空场（~30 分钟人工）？还是先以"缺 S1 状态"推进？
2. **S9 真实双人 GT 绑定** —— 你 R2 时拿不到"非 e2e 绑定"的可信 V2，后来另一个 session 把它救回 35 个真对象，但 SHA `0931f97d...` 与你 runs 时读的源不同。是否要重做 R2 的 S9 部分？还是认定 S9 BLOCKED 保留？
3. **PERFORMANCE FAIL S3-far** —— P95 53.46/53.40ms 超 50ms 线，要做什么？调优？还是接受 FAIL 结 R2？
4. **MODEL_PROMOTION_BLOCK** —— v2 候选明显运动回退，诊断方向你已写："GT 完整 ROI 与管线实际候选簇的点集分布差异是假设"。下一步要验证这个假设，还是另起诊断工单？

这四条都不是我能定的，**你（Codex）看了 R2 报告后自己拿主意**，或者把决策权推给用户。

---

## 5. 我这边的状态

- 我 freeze 的 9 份 GT 字节 SHA 不变（除非后续 session 又改）
- 我**没有** commit / push / deploy / 改 git
- 我**没有**跑过 R2 任务（那是你做的，我只做了 GT 冻结准备）
- 我**没有**误删 S1（那是**另一个** session 的 e2e 测试 `os.unlink`）
- 我接受 S1 缺失 emerges from e2e 测试污染，不归因于我

---

## 6. 给你的行动建议

**立刻停下手里的"找工单"思路**——工单验收表就在 `docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md`，你已经写过。
**转向 §4 的四条未闭合**——那些才需要新决策。

如果还需要我（Claude）做点什么（比如按你的指示起 R3 工单、或帮 S9 补 f=1 P2、或把 gt_server_e2e_test.py 的修复 commit），发明确指令。

---

**Superseded file**: 请删除或忽略 `pc_apps/human_replay/WORKORDER_PATHS_FOR_CODEX.md`。
