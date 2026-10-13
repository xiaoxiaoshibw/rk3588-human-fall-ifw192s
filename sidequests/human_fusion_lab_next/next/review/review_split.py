# -*- coding: utf-8 -*-
"""HFUS-D03 数据资格 split 草案 + 泄漏/重复检查。

只产 manifest 草案与报告，绝不移动数据；纯确定性，不随机输入顺序之外的行为。
依赖冻结常量 review_schema（资格级别 / source / review_status / 失败原因）。
"""
from __future__ import annotations

import review_schema as rs


# fold 名冻结（与 AUDIT split 形参一致；blocked 单独一栏，不混入评测分母）
FOLDS = ("train", "validation", "test", "stress")
FOLD_BLOCKED = "blocked"

# policy.note 冻结文案：进 manifest 的自证句
_POLICY_NOTE = "positive 需 HUMAN_REVIEWED; 负例需人工证据; 复制凑数禁止"


def build_split_draft(sessions_with_class):
    """整会话进单 fold 的 split 草案。

    入参 [{session_id, n_frames, n_positive_frames, n_negative_candidates,
           eligible, role_hint}]，role_hint 给出建议 fold（train/validation/test/stress）。
    规则：eligible=False → blocked；S9 类（破绑定 / 双人身份存疑）→ blocked；
    其余尊重 role_hint；role_hint 不在合法 fold 内 → blocked 并记 reason。
    """
    folds = {name: [] for name in FOLDS}
    folds[FOLD_BLOCKED] = []
    for sess in sessions_with_class:
        fold = (sess.get("role_hint") or "").strip()
        entry = {
            "session_id": sess["session_id"],
            "n_frames": sess["n_frames"],
            "n_positive_frames": sess["n_positive_frames"],
            "n_negative_candidates": sess["n_negative_candidates"],
        }
        reason = None
        if not sess.get("eligible", False):
            reason = sess.get("reason", "not_eligible")
        elif fold == FOLD_BLOCKED:
            reason = sess.get("reason", "explicit_blocked")
        elif fold not in FOLDS:
            reason = "bad_role_hint"
        if reason is not None:
            entry["reason"] = reason
            folds[FOLD_BLOCKED].append(entry)
        else:
            folds[fold].append(entry)
    return {
        "folds": folds,
        "policy": {"positive_purity": 1.0, "note": _POLICY_NOTE},
    }


def cross_fold_exact_duplicate_check(records_iterable):
    """按 dedup_hash 查跨 fold 泄漏 + 同 fold 内重复。

    记录 {session_id, fold, dedup_hash, class_name}。
    exact_duplicate>0 即违例（同 hash 出现在 >1 fold）；同 fold 重复只报告不违例。
    """
    by_hash = {}
    dup_pairs = []
    cross_fold_hashes = set()
    for rec in records_iterable:
        h = rec["dedup_hash"]
        prev = by_hash.setdefault(h, [])
        for old in prev:
            pair = (old["session_id"], rec["session_id"], h, old["fold"], rec["fold"])
            dup_pairs.append(pair)
            if old["fold"] != rec["fold"]:
                cross_fold_hashes.add(h)
        prev.append(rec)
    # by_hash 输出为 {hash: [(session_id, fold), ...]} 摘要
    by_hash_summary = {h: [(r["session_id"], r["fold"]) for r in rs_]
                       for h, rs_ in by_hash.items()}
    return {
        "exact_duplicate": len(cross_fold_hashes),
        "cross_fold_hashes": sorted(cross_fold_hashes),
        "dup_pairs": dup_pairs,
        "by_hash": by_hash_summary,
    }


def negative_evidence_report(candidates):
    """负例候选分级：人工证据 / 模型误检疑似 / 未知。

    入参 [{candidate_id, session_id, fold, label_source, review_status, qualification}]。
    - 破绑定优先：qualification==INVALID_BINDING（SHA 占位/破）→ model_suspect_negatives，
      即便 source==human 也不能算人工证据（绑定不可信）。
    - 人工负例：label_source==human 且 review_status==reviewed（机器绝不写 reviewed，
      故本档只能通过人工 GT 达成）→ reviewed_negatives。
    - 模型误检疑似：label_source==model_suspect → model_suspect_negatives。
    - 其余 → unknown_negatives（不可进 val/test 分母）。
    folded_to_val_or_test：没硬证据却被排进 validation/test 的负例，全部点名。
    """
    reviewed_neg = []
    model_suspect = []
    unknown = []
    folded = []
    for cand in candidates:
        src = cand.get("label_source")
        status = cand.get("review_status")
        qual = cand.get("qualification")
        if qual == rs.QUAL_INVALID_BINDING:
            model_suspect.append(cand["candidate_id"])
        elif src == rs.SOURCE_HUMAN and status == rs.REVIEW_REVIEWED:
            reviewed_neg.append(cand["candidate_id"])
        elif src == rs.SOURCE_MODEL_SUSPECT:
            model_suspect.append(cand["candidate_id"])
        else:
            unknown.append(cand["candidate_id"])
        is_human_ok = (src == rs.SOURCE_HUMAN and status == rs.REVIEW_REVIEWED
                       and qual != rs.QUAL_INVALID_BINDING)
        if cand.get("fold") in ("validation", "test") and not is_human_ok:
            folded.append(cand["candidate_id"])
    return {
        "reviewed_negatives": reviewed_neg,
        "model_suspect_negatives": model_suspect,
        "unknown_negatives": unknown,
        "folded_to_val_or_test": folded,
    }


def session_fold_map(split_draft):
    """{session_id: fold} 反查表。"""
    out = {}
    for fold_name, entries in split_draft["folds"].items():
        for entry in entries:
            out[entry["session_id"]] = fold_name
    return out


# ---------------------------------------------------------------------------
# 最小自测：合成 3 会话（其一 S9 破绑定进 blocked）、跨 fold 同 hash 检出、
# 干净情况 0 泄漏、负例分级 human 与 model_suspect 分开。
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # --- build_split_draft ---
    sessions = [
        {"session_id": "S1", "n_frames": 100, "n_positive_frames": 50,
         "n_negative_candidates": 10, "eligible": True, "role_hint": "train"},
        {"session_id": "S2", "n_frames": 80, "n_positive_frames": 40,
         "n_negative_candidates": 8, "eligible": True, "role_hint": "validation"},
        {"session_id": "S9", "n_frames": 90, "n_positive_frames": 30,
         "n_negative_candidates": 5, "eligible": False,
         "role_hint": "test", "reason": rs.REASON_BROKEN_SHA_BINDING},
        {"session_id": "S3", "n_frames": 60, "n_positive_frames": 20,
         "n_negative_candidates": 4, "eligible": True, "role_hint": "weird_fold"},
    ]
    draft = build_split_draft(sessions)
    assert [e["session_id"] for e in draft["folds"]["train"]] == ["S1"]
    assert [e["session_id"] for e in draft["folds"]["validation"]] == ["S2"]
    blocked_ids = [e["session_id"] for e in draft["folds"]["blocked"]]
    assert blocked_ids == ["S9", "S3"], blocked_ids
    assert draft["folds"]["blocked"][0]["reason"] == rs.REASON_BROKEN_SHA_BINDING
    assert draft["folds"]["blocked"][1]["reason"] == "bad_role_hint"
    assert draft["policy"]["positive_purity"] == 1.0
    assert draft["policy"]["note"] == _POLICY_NOTE

    m = session_fold_map(draft)
    assert m == {"S1": "train", "S2": "validation", "S9": "blocked", "S3": "blocked"}

    # --- cross_fold_exact_duplicate_check: 干净路径 ---
    clean_records = [
        {"session_id": "S1", "fold": "train", "dedup_hash": "h1", "class_name": "person"},
        {"session_id": "S1", "fold": "train", "dedup_hash": "h2", "class_name": "person"},
        {"session_id": "S2", "fold": "validation", "dedup_hash": "h3", "class_name": "person"},
    ]
    res_clean = cross_fold_exact_duplicate_check(clean_records)
    assert res_clean["exact_duplicate"] == 0
    assert res_clean["dup_pairs"] == []
    assert res_clean["by_hash"]["h1"] == [("S1", "train")]

    # 同 fold 重复（不违例，但报告）
    same_fold_dup = clean_records + [
        {"session_id": "S1", "fold": "train", "dedup_hash": "h1", "class_name": "person"},
    ]
    res_same = cross_fold_exact_duplicate_check(same_fold_dup)
    assert res_same["exact_duplicate"] == 0, res_same
    assert len(res_same["dup_pairs"]) == 1
    assert res_same["dup_pairs"][0][2] == "h1"
    assert res_same["by_hash"]["h1"] == [("S1", "train"), ("S1", "train")]

    # 跨 fold 同 hash → 违例
    leak_records = clean_records + [
        {"session_id": "S9", "fold": "test", "dedup_hash": "h1", "class_name": "person"},
    ]
    res_leak = cross_fold_exact_duplicate_check(leak_records)
    assert res_leak["exact_duplicate"] == 1, res_leak
    assert res_leak["cross_fold_hashes"] == ["h1"]
    assert len(res_leak["dup_pairs"]) == 1

    # --- negative_evidence_report ---
    cands = [
        {"candidate_id": "c1", "session_id": "S1", "fold": "validation",
         "label_source": rs.SOURCE_HUMAN, "review_status": rs.REVIEW_REVIEWED,
         "qualification": rs.QUAL_BOUND_HUMAN_REVIEWED},
        {"candidate_id": "c2", "session_id": "S1", "fold": "validation",
         "label_source": rs.SOURCE_MODEL_SUSPECT, "review_status": rs.REVIEW_UNREVIEWED,
         "qualification": rs.QUAL_UNKNOWN},
        {"candidate_id": "c3", "session_id": "S2", "fold": "train",
         "label_source": rs.SOURCE_MODEL, "review_status": rs.REVIEW_UNREVIEWED,
         "qualification": rs.QUAL_UNKNOWN},
        {"candidate_id": "c4", "session_id": "S2", "fold": "test",
         "label_source": rs.SOURCE_MODEL, "review_status": rs.REVIEW_REVIEWED,  # review 虚标但 source 非 human
         "qualification": rs.QUAL_UNKNOWN},
        {"candidate_id": "c5", "session_id": "S9", "fold": "test",
         "label_source": rs.SOURCE_HUMAN, "review_status": rs.REVIEW_REVIEWED,
         "qualification": rs.QUAL_INVALID_BINDING},
    ]
    rep = negative_evidence_report(cands)
    assert rep["reviewed_negatives"] == ["c1"], rep
    assert rep["model_suspect_negatives"] == ["c2", "c5"], rep
    assert rep["unknown_negatives"] == ["c3", "c4"], rep
    # c2/c4/c5 都是无人工复核证据却躺进了 val/test 的负例
    assert rep["folded_to_val_or_test"] == ["c2", "c4", "c5"], rep

    print("review_split selftest OK")
