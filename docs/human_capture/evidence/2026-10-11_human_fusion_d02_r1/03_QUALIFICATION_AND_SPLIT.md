# HFUS-D02 数据资格报告 + split 草案 + 人工审核清单（2026-10-11 r1）

由 `sidequests/human_fusion_lab_next/next/review/build_review_package.py` 真实跑出，
产物在 `sidequests/human_fusion_lab_next/next/review/review_out/`。
本报告数字与 `review_package.manifest.json` 对账一致（jsonl sha256 前缀 50f8e273…，对抗性复审修复后重跑）。

**硬保证（机器侧，可复核）**：2309 条待审记录中，无一条 `review_status=reviewed`，
无一条 `qualification=BOUND_HUMAN_REVIEWED`（`validate_no_human_auto` 硬门 + 回读测试断言）；
跨 fold exact_duplicate = 0，cross_fold_hashes = 0，dup_pairs = 0。原始 GT / captures 未被修改。

## 一、待审包资格分布（真实，修复后重跑）

| 评测资格 | 条数 | 含义（机器建议，非人工裁定） |
|---|---:|---|
| PROPAGATED_CONDITIONAL | 1818 | 全部 S1 propagated 家具/背景对象，待人工复核 |
| PARTIAL | 395 | 非穷尽窗的已标 PERSON（S3near/S3far/S4/S5/S7/S8 主体） |
| UNKNOWN | 60 | S6 漏检帧 7（bg_loss 2 + no_candidate 5）+ S8 静止窗候选 53 |
| INVALID_BINDING | 36 | S9 全部对象（`aaaa…` 占位 → 绑定不可信） |
| **合计** | **2309** | |

授权点名覆盖核实（**修复后真实落盘**）：
- S6 授权点名 f128/129/130/171/187/188 加上邻帧 91/127/172/173：
  f187/f188 → `UNKNOWN bg_loss`；f91/f128/f129/f130/f171 → `UNKNOWN no_candidate`；
  邻帧 f127/f172/f173（无失败层证据）→ `PARTIAL coverage_gap`。
  （对抗性复审发现初版把 7 帧错打 coverage_gap；已修 root cause——build() 恒 `has_candidate=True`
  致 qualify 的 bg_loss/no_candidate 分支被 PARTIAL 吞掉，现按证据置 False 命中正确分支。）
- S9 双人：36 对象**全部为** `INVALID_BINDING`（双人身份/成员/SHA 绑定存疑 → BLOCKED）。
- S1 家具：1824 对象按 `propagated`(1818) + `human`(6) 全部登记，**未把传播 1515 次当独立家具数**；
  其中 `model_suspect_negatives=0`、`reviewed_negatives=0`、`unknown_negatives=1824`。

## 二、负例诚实分级（关键）

| 负例档 | 数量 | 说明 |
|---|---:|---|
| reviewed_negatives（已审、可进 val/test） | **0** | 当前**无任何**经人工确认的独立负例 |
| model_suspect_negatives（模型误检疑似） | **0** | D02 不跑检测器，故无“模型误检”性质候选 |
| unknown_negatives（未知来源） | **1824** | S1 家具/背景（1818 propagated + 6 human 待复核） |
| folded_to_val_or_test（无证据却进 val/test） | **0** | 无复制凑数发生 |

→ **语义结论（BLOCKED）**：val/test/stress 仍无**有效人工负例**；S1 家具必须先经**人工复核独立负例性**，
否则不能充当 val/test 负例分母。与诊断报告“val/test 无有效负例”一致，本轮未制造新证据。

## 三、split 草案（机器建议；同会话不跨 fold，无复制负例）

| fold | 会话 | 依据 |
|---|---|---|
| train | S1(175227), S3near(175429), S4(175804), S5(175943) | 沿用 AUDIT 现有 split |
| validation | S3far(175553) | 沿用 |
| test | S7(180337), S8(180557) | 沿用 |
| stress | S6(180235) | 沿用（漏检压力） |
| blocked | S9(180751) | 破绑定，禁入任何 fold |

- 同会话整进单 fold（9 会话互斥分布）；不复制负例入不同 fold（exact_duplicate=0 已证）。
- **开放风险**：诊断报告指出早期 `train_person_rf.py:56` 曾复制负例、`:85` 跨 fold 指派；
  本草案只保证**新待审包**无泄漏，不证明存量 XGB 训练折无历史复制。该问题交 owner（Codex/D05a）。

## 四、人工仍须完成的审核清单（语义晋级前置）

每一项解锁对应的资格升级；全部未完成前，对应语义保持 BLOCKED。

1. **S1 家具独立负例复核**（解锁 reviewed_negatives>0）：
   - 1818 个 propagated 对象需人工确认是否**独立家具**（非同一家具跨帧重复传播）。
   - GT_V3 出现 `source=propagated` 却 `review_status=reviewed`，与 gt_lib 协议（propagated 永不 reviewed）冲突；
     需人工裁定这 1824 个对象的真实来源。**（登记交 owner：该协议矛盾非 D02 裁定）**
2. **S9 双人身份/成员/SHA**（解锁 S9 资格）：重新人工标注或复核 capture 绑定，
   解除 `aaaa…` 占位；确认 track P1/P2 成员与穿越帧身份。当前 BLOCKED。
3. **S8/S4 ≥20s 连续静止窗**（解锁静止资格）：当前 GT 最长静止段仅 1.76s，
   需人工补标连续静止窗，否则该验收项 BLOCKED。
4. **val/test 负例补齐**：S3far/S7/S8 需人工标注确认独立负例（不可复制 train 负例）。
5. **S6 GT_V2/V3 与 V1 一致性**（登记交 owner）：AUDIT 冻结 V1，V2/V3 未审，需 Codex 对齐。

## 五、最终索引映射 → D01 冻结 schema（待接入，BLOCKED）

本任务按授权第 6 条：**最终索引映射与导出必须使用 Codex D01 发布的冻结 schema/version/SHA；
接口未发布时记录待接入，不自行猜测 compact/raw/leveled 索引关系**。

当前状态：D01 冻结 schema/version/SHA **尚未发布**（Unified Plan 中 D01 为 P0 未执行）。
因此本待审包的成员索引记录采用**如实双域记录**（`member_point_compact` = GT 原样 leveled-compact；
`member_point_raw` = 经 `gt_lib.split_frame_indices` 等价算法映射回的 raw28 点号），
并同时在 manifest 记录每会话 `{meta, points}` 双 SHA，待 D01 冻结契约发布后按其 schema 重导出对齐。
**在 D01 契约发布前，最终索引映射导出 = BLOCKED（待接入），不自行定版。**

## 六、可复跑入口与冻结事实

- 复跑：`python -B sidequests/human_fusion_lab_next/next/review/build_review_package.py`
  （默认 `--created-iso 2026-10-11T00:00:00Z` 固定时间戳保 SHA 稳定；`--limit N` 调试）。
- 测试：`python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/next/review -p "test_*.py"` = **17/17 PASS, exit 0**。
- 输入冻结：9 会话 `{meta, points}` 双 SHA 见 `review_package.manifest.json.input_sha256_map`。
