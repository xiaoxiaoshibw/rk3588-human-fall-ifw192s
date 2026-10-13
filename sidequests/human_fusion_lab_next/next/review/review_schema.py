# -*- coding: utf-8 -*-
"""HFUS-D02 待审包 schema 常量与纯函数。

字段命名对齐权威 GT 协议 sidequests/human_fusion_lab/human_replay/gt_lib.js
(gt_workbench/1) 的两字段：source / review_status。
机器建议的标签永远只是草稿：review_status ∈ {draft, unreviewed}。
绝不自动写 reviewed；绝不覆盖原始 GT。
资格级别（evaluation qualification）冻结自 docs/human_capture/HUMAN_FUSION_UNIFIED_PLAN.md §4.1。
"""

# --- GT 协议两字段（与 gt_lib make_object 一致）---
# source：标签来源。gt_lib 原生值为 human/model/propagated；
# LABEL_DERIVED 作为来源字符串字面值承载（S9 修复草稿同法），不写进 review_status。
SOURCE_HUMAN = "human"
SOURCE_MODEL = "model"
SOURCE_PROPAGATED = "propagated"
SOURCE_LABEL_DERIVED = "LABEL_DERIVED"        # 由标签再派生（不可当真值）
SOURCE_MODEL_SUSPECT = "model_suspect"        # 模型误检疑似（无人工证据）

# review_status：审核状态机；机器只会产生 draft/unreviewed，永不产生 reviewed。
REVIEW_DRAFT = "draft"
REVIEW_UNREVIEWED = "unreviewed"
REVIEW_REVIEWED = "reviewed"                  # 只允许人工写入；本工具绝不生成

# --- 评测资格级别（文档级评测分母状态，非 gt_lib 落盘字段）---
QUAL_BOUND_HUMAN_REVIEWED = "BOUND_HUMAN_REVIEWED"       # 绑定且人工复核（仅人工能置）
QUAL_PROPAGATED_CONDITIONAL = "PROPAGATED_CONDITIONAL"   # 传播、有条件
QUAL_PARTIAL = "PARTIAL"                                  # 局部/非穷尽
QUAL_UNKNOWN = "UNKNOWN"                                  # 未审/不可证
QUAL_INVALID_BINDING = "INVALID_BINDING"                  # SHA/绑定破（如 S9 aaaa…）

# --- 索引域：全流程唯一 GT 写盘域 = leveled-compact；候选/engine 域 = 帧内 raw 点号 ---
INDEX_DOMAIN_RAW28 = "raw28_row"        # raw 点号域（帧内 0..n_points-1，候选/engine point_indices）
INDEX_DOMAIN_COMPACT = "leveled_compact"  # GT 写盘域（finite&&any!=0 过滤后 0..n-1）
INDEX_DOMAIN_LEVELED = "leveled_xyzi"   # leveling 后 xyzi；与 raw 1:1 同序，不独立编号

# --- 失败原因（机器可判定部分）；其余人工补 ---
REASON_NO_CANDIDATE = "no_candidate"              # 有 GT 人体但 classifier 前无候选（proposal 打死）
REASON_BG_LOSS = "bg_loss"                        # 背景层删至残点数过低（S6 f187/188）
REASON_CANDIDATE_FN = "candidate_fn"              # 有候选但被分类/评分打死
REASON_LOW_PURITY_MIXED = "low_purity_mixed"      # 低纯度混合簇，保留待审不默认负
REASON_PROPAGATED_NOT_REVIEWED = "propagated_not_reviewed"
REASON_BROKEN_SHA_BINDING = "broken_sha_binding"  # declared sha ≠ capture（S9 aaaa…）
REASON_COVERAGE_GAP = "coverage_gap"              # 连续覆盖不足
REASON_LOW_COVERAGE = "low_coverage"              # 低覆盖区间
REASON_TWO_PERSON_IDENTITY = "two_person_identity"  # 双人身份/成员/SHA 存疑


def machine_default_review_status(source):
    """机器建议的 review_status 纯映射：绝不产出 reviewed。

    gt_lib validate_doc 拒绝 source=model 且 reviewed；propagated 恒为 unreviewed。
    即便 source==human，机器也只标 draft（source=human 不证明第二人复核，§4.1）。
    """
    if source in (SOURCE_MODEL, SOURCE_PROPAGATED, SOURCE_LABEL_DERIVED,
                  SOURCE_MODEL_SUSPECT):
        return REVIEW_UNREVIEWED
    return REVIEW_DRAFT


def machine_default_qualification(source, sha_binding_ok, exhaustive):
    """机器建议的评测资格。机器永不产出 BOUND_HUMAN_REVIEWED（人工专属）。

    BROKEN 绑定 → INVALID_BINDING；传播 → PROPAGATED_CONDITIONAL；
    非穷尽窗 → PARTIAL；其余 UNKNOWN。
    """
    if not sha_binding_ok:
        return QUAL_INVALID_BINDING
    if source == SOURCE_PROPAGATED:
        return QUAL_PROPAGATED_CONDITIONAL
    if not exhaustive:
        return QUAL_PARTIAL
    return QUAL_UNKNOWN
