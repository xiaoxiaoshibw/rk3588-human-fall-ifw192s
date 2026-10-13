# -*- coding: utf-8 -*-
"""HFUS-D02 机器建议 qualification / review_status 决策模块（纯函数，不读盘）。

单一事实源在 review_schema：资格级别与状态映射一律经
machine_default_review_status / machine_default_qualification 取得；
本模块只负责任务书规定的分支排序与 reason 选择。

硬门：机器永远只产出 draft / unreviewed，绝不产出 reviewed；
绝不产出 BOUND_HUMAN_REVIEWED（人工专属）。
"""
from __future__ import annotations

from review_schema import (
    REVIEW_DRAFT,
    REVIEW_REVIEWED,
    REVIEW_UNREVIEWED,
    QUAL_BOUND_HUMAN_REVIEWED,
    QUAL_PROPAGATED_CONDITIONAL,
    QUAL_UNKNOWN,
    REASON_BG_LOSS,
    REASON_BROKEN_SHA_BINDING,
    REASON_CANDIDATE_FN,
    REASON_COVERAGE_GAP,
    REASON_LOW_PURITY_MIXED,
    REASON_NO_CANDIDATE,
    REASON_PROPAGATED_NOT_REVIEWED,
    REASON_TWO_PERSON_IDENTITY,
    SOURCE_MODEL_SUSPECT,
    SOURCE_PROPAGATED,
    machine_default_qualification,
    machine_default_review_status,
)


def qualify_record(*, label_source, sha_binding_ok, exhaustive, has_gt_human,
                   has_candidate, bg_loss=False, propagated=False,
                   two_person_suspect=False, low_purity=False):
    """对单条待审记录给出机器建议 {review_status, qualification, reason}。

    分支顺序即优先级（任务书冻结）；命中即返回。
    """
    # 1) SHA 绑定破：即便 source=human 也不能给 draft（草稿意味着可审，绑定都破了无从审起）
    if not sha_binding_ok:
        return {
            "review_status": REVIEW_UNREVIEWED,
            "qualification": machine_default_qualification(
                label_source, sha_binding_ok=False, exhaustive=exhaustive),
            "reason": REASON_BROKEN_SHA_BINDING,
        }
    # 2) 双人身份存疑：资格钉 UNKNOWN（不随 exhaustive 落 PARTIAL，身份问题解决前不可计量）
    if two_person_suspect:
        return {
            "review_status": REVIEW_UNREVIEWED,
            "qualification": QUAL_UNKNOWN,
            "reason": REASON_TWO_PERSON_IDENTITY,
        }
    # 3) 传播标签：有条件资格，等人工复核；映射走 schema 单一事实源
    if propagated:
        return {
            "review_status": machine_default_review_status(SOURCE_PROPAGATED),
            "qualification": machine_default_qualification(
                SOURCE_PROPAGATED, sha_binding_ok=True, exhaustive=exhaustive),
            "reason": REASON_PROPAGATED_NOT_REVIEWED,
        }
    # 4) 模型误检疑似：低纯度混合簇保留待审、不默认负；否则按候选被打死
    if label_source == SOURCE_MODEL_SUSPECT:
        return {
            "review_status": machine_default_review_status(label_source),
            "qualification": machine_default_qualification(
                label_source, sha_binding_ok=True, exhaustive=exhaustive),
            "reason": REASON_LOW_PURITY_MIXED if low_purity else REASON_CANDIDATE_FN,
        }
    # 5) 有 GT 人但无候选：S6 f187 背景层删残 / f128 proposal 打死；任务是草稿让人补证据
    if has_gt_human and not has_candidate:
        return {
            "review_status": REVIEW_DRAFT,
            "qualification": QUAL_UNKNOWN,
            "reason": REASON_BG_LOSS if bg_loss else REASON_NO_CANDIDATE,
        }
    # 6) 非穷尽窗：资格 PARTIAL 走 schema 映射；reason 用冻结的覆盖缺口常量
    if not exhaustive:
        return {
            "review_status": machine_default_review_status(label_source),
            "qualification": machine_default_qualification(
                label_source, sha_binding_ok=True, exhaustive=False),
            "reason": REASON_COVERAGE_GAP,
        }
    # 7) 兜底：草稿待审，无机器可判定原因
    return {
        "review_status": REVIEW_DRAFT,
        "qualification": QUAL_UNKNOWN,
        "reason": None,
    }


def batch_qualify(list_of_kwargs):
    """批量机器建议；保序，长度与输入一致。"""
    return [qualify_record(**kw) for kw in list_of_kwargs]


def validate_no_human_auto(records):
    """硬门断言：机器结果里不允许出现 reviewed / BOUND_HUMAN_REVIEWED。

    唯一豁免：记录带显式 human_override 标记（人工回读时打的旗）。
    违例即 raise AssertionError，给上层回读兜底。
    """
    for i, rec in enumerate(records):
        if rec.get("human_override"):
            continue
        assert rec.get("review_status") != REVIEW_REVIEWED, (
            "records[%d] 机器路径出现 reviewed（非人工 override）：%r" % (i, rec))
        assert rec.get("qualification") != QUAL_BOUND_HUMAN_REVIEWED, (
            "records[%d] 机器路径出现 BOUND_HUMAN_REVIEWED：%r" % (i, rec))


if __name__ == "__main__":
    # 最小自测：合成 kwargs，不读真实 captures；任一断言失败即非零退出。
    # S9 broken sha（aaaa…占位）→ 绑定破，最高优先级
    r = qualify_record(label_source="human", sha_binding_ok=False, exhaustive=True,
                       has_gt_human=True, has_candidate=False)
    assert r == {"review_status": "unreviewed", "qualification": "INVALID_BINDING",
                 "reason": "broken_sha_binding"}, r
    # 双人身份存疑（优先级高于 propagated / suspect）
    r = qualify_record(label_source="human", sha_binding_ok=True, exhaustive=True,
                       has_gt_human=True, has_candidate=True, two_person_suspect=True)
    assert r == {"review_status": "unreviewed", "qualification": "UNKNOWN",
                 "reason": "two_person_identity"}, r
    # propagated → 有条件资格
    r = qualify_record(label_source="propagated", sha_binding_ok=True, exhaustive=True,
                       has_gt_human=True, has_candidate=True, propagated=True)
    assert r == {"review_status": "unreviewed",
                 "qualification": "PROPAGATED_CONDITIONAL",
                 "reason": "propagated_not_reviewed"}, r
    # model_suspect 普通 → candidate_fn；低纯度 → low_purity_mixed
    base = dict(label_source="model_suspect", sha_binding_ok=True, exhaustive=True,
                has_gt_human=False, has_candidate=True)
    r = qualify_record(**base)
    assert r["reason"] == "candidate_fn" and r["review_status"] == "unreviewed", r
    r = qualify_record(low_purity=True, **base)
    assert r["reason"] == "low_purity_mixed", r
    # S6 f187 bg_loss 路径：有 GT 人、无候选、背景层删残
    r = qualify_record(label_source="human", sha_binding_ok=True, exhaustive=True,
                       has_gt_human=True, has_candidate=False, bg_loss=True)
    assert r == {"review_status": "draft", "qualification": "UNKNOWN",
                 "reason": "bg_loss"}, r
    # f128 no_candidate 路径：同上有候选缺失但无背景证据
    r = qualify_record(label_source="human", sha_binding_ok=True, exhaustive=True,
                       has_gt_human=True, has_candidate=False)
    assert r == {"review_status": "draft", "qualification": "UNKNOWN",
                 "reason": "no_candidate"}, r
    # 非穷尽 → PARTIAL / coverage_gap
    r = qualify_record(label_source="human", sha_binding_ok=True, exhaustive=False,
                       has_gt_human=True, has_candidate=True)
    assert r["qualification"] == "PARTIAL" and r["reason"] == "coverage_gap", r
    # 兜底
    r = qualify_record(label_source="human", sha_binding_ok=True, exhaustive=True,
                       has_gt_human=True, has_candidate=True)
    assert r == {"review_status": "draft", "qualification": "UNKNOWN",
                 "reason": None}, r

    # batch_qualify 保序保长
    kws = [
        dict(label_source="human", sha_binding_ok=False, exhaustive=True,
             has_gt_human=True, has_candidate=False),
        dict(label_source="human", sha_binding_ok=True, exhaustive=True,
             has_gt_human=True, has_candidate=True),
    ]
    out = batch_qualify(kws)
    assert len(out) == 2 and out[0]["reason"] == "broken_sha_binding" \
        and out[1]["reason"] is None, out
    # 正常机器输出必过硬门
    validate_no_human_auto(out)

    # 人工尝试注入 reviewed → 硬门拒绝
    bad = [dict(out[1], review_status="reviewed")]
    try:
        validate_no_human_auto(bad)
        raise SystemExit("FAIL: reviewed 未被拒绝")
    except AssertionError:
        pass
    # 注入 BOUND_HUMAN_REVIEWED → 拒绝
    bad = [dict(out[1], qualification="BOUND_HUMAN_REVIEWED")]
    try:
        validate_no_human_auto(bad)
        raise SystemExit("FAIL: BOUND_HUMAN_REVIEWED 未被拒绝")
    except AssertionError:
        pass
    # 显式 human_override 标记 → 豁免（人工回读合法路径）
    validate_no_human_auto([dict(out[1], review_status="reviewed",
                                 qualification="BOUND_HUMAN_REVIEWED",
                                 human_override=True)])
    print("review_qualify selftest OK")
