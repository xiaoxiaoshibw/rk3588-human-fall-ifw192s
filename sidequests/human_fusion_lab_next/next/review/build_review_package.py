# -*- coding: utf-8 -*-
"""HFUS-D02 待审包构建主控 CLI —— 唯一可复跑工具入口。

把 review_loader / review_export / review_split / review_qualify 黏合成端到端流水线：
  真实会话 meta+GT 只读加载 → SHA 绑定校验 → 抽取授权目标帧的 GT 对象 →
  leveled-compact → raw28 成员映射 → 机器 qualify(绝不人工) →
  导出 待审包 JSONL + manifest + split 草案 + 负例报告 + 资格报告。

硬门（与 schema/qualify 单一事实源一致）：
  * 机器永不写 review_status=reviewed，永不产生 BOUND_HUMAN_REVIEWED；
  * 不覆盖原始 GT，不复制负例凑数；
  * S9 破绑定 → INVALID_BINDING；S1 大量 propagated → PROPAGATED_CONDITIONAL；
  * S8 无 ≥20s 静止窗 → 该目标 BLOCKED（在资格报告说明）。

只读：captures/remote/**、pc_apps/human_replay/gt_store/**。
输出：本目录 review_out/ 与 docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import review_loader as L          # noqa: E402
import review_export as E          # noqa: E402
import review_split as SP          # noqa: E402
import review_qualify as Q         # noqa: E402
import review_schema as SC         # noqa: E402

# 仓库根（本文件位于 sidequests/human_fusion_lab_next/next/review/）
REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
GT_STORE = os.path.join(REPO_ROOT, "pc_apps", "human_replay", "gt_store")
CAPTURES = os.path.join(REPO_ROOT, "captures", "remote")
EVIDENCE = os.path.join(REPO_ROOT, "docs", "human_capture", "evidence",
                        "2026-10-11_human_fusion_d02_r1")
REVIEW_OUT = os.path.join(_THIS_DIR, "review_out")

# ---- 会话定义表（按 AUDIT.json 冻结 GT 版本；S1=GT_V3, S9=GT_V2, 其余 GT_V1）----
SESSIONS = [
    {"name": "S1", "sid": "cap_20261010_175227", "gt": "GT_V3.json",
     "fold": "train", "exhaustive": False},
    {"name": "S3near", "sid": "cap_20261010_175429", "gt": "GT_V1.json",
     "fold": "train", "exhaustive": False},
    {"name": "S3far", "sid": "cap_20261010_175553", "gt": "GT_V1.json",
     "fold": "validation", "exhaustive": False},
    {"name": "S4", "sid": "cap_20261010_175804", "gt": "GT_V1.json",
     "fold": "train", "exhaustive": False},
    {"name": "S5", "sid": "cap_20261010_175943", "gt": "GT_V1.json",
     "fold": "train", "exhaustive": False},
    {"name": "S6", "sid": "cap_20261010_180235", "gt": "GT_V1.json",
     "fold": "stress", "exhaustive": False},
    {"name": "S7", "sid": "cap_20261010_180337", "gt": "GT_V1.json",
     "fold": "test", "exhaustive": False},
    {"name": "S8", "sid": "cap_20261010_180557", "gt": "GT_V1.json",
     "fold": "test", "exhaustive": True},   # long-still 近似穷尽窗
    {"name": "S9", "sid": "cap_20261010_180751", "gt": "GT_V2.json",
     "fold": "blocked", "exhaustive": False},  # 破绑定 → blocked
]

# S6 授权重点帧（无候选帧及其邻帧），来源诊断报告/ATTRIBUTION
S6_PRIORITY_FRAMES = sorted({
    91, 92, 128, 129, 130, 131, 170, 171, 172, 186, 187, 188, 189,
    # 加上无候选帧本身（邻帧 ±1）
    90, 127, 128, 129, 130, 131, 169, 170, 171, 172, 173, 186, 187, 188, 189,
})
S6_BG_LOSS_FRAMES = {187, 188}   # 缺参考删除主因帧
S6_NO_CANDIDATE_FRAMES = {91, 128, 129, 130, 171}  # proposal 打死帧


def _gt_path_for(sid, gt_name):
    return os.path.join(GT_STORE, sid, gt_name)


def _select_objects_for_session(name, sess_meta, gt, sid):
    """按会话返回 [(obj, frame_idx, kwargs_extra)] 待审对象样本。

    只抽样授权目标帧/区间；不把全部 84MB S1 全帧倒入。返回元组 (规范化obj, frame_idx, extra)。
    """
    objs = gt["objects"]
    out = []
    frames = sess_meta["frames"]

    def frame_idx_of(o):
        fi = o.get("frame_idx")
        return fi if isinstance(fi, int) else None

    if name == "S6":
        for o in objs:
            if o.get("class_name") != "PERSON":
                continue
            fi = frame_idx_of(o)
            if fi in S6_PRIORITY_FRAMES:
                extra = {}
                if fi in S6_BG_LOSS_FRAMES:
                    extra["bg_loss"] = True
                if fi in S6_NO_CANDIDATE_FRAMES:
                    extra["no_candidate"] = True
                out.append((o, fi, extra))
    elif name == "S8":
        # 静止窗：取全部 PERSON 帧（仅 53），机器将判断连续性 -> 实则无 ≥20s
        for o in objs:
            if o.get("class_name") == "PERSON":
                out.append((o, frame_idx_of(o), {"still_window": True}))
    elif name == "S9":
        # 破绑定：全部对象登记为未知来源候选
        for o in objs:
            out.append((o, frame_idx_of(o), {"two_person_suspect": True}))
    elif name == "S1":
        # 空场/家具负例：首段/中段/末段各抽 5 帧 + 全部 FURNITURE 对象（待人工核独立负例）
        n = sess_meta["n_frames"]
        picks = set(range(0, min(5, n))) | set(range(n // 2 - 2, n // 2 + 3)) \
            | set(range(max(0, n - 5), n))
        byfi = {}
        for o in objs:
            fi = frame_idx_of(o)
            byfi.setdefault(fi, []).append(o)
        for fi in sorted(byfi):
            if fi in picks or len(byfi[fi]) > 1:
                for o in byfi[fi]:
                    out.append((o, fi, {"furniture_candidate": True}))
    else:
        # S3near/S3far/S4/S5/S7：全部已标 PERSON 对象（数量少）
        for o in objs:
            if o.get("class_name") == "PERSON":
                out.append((o, frame_idx_of(o), {}))
    return out


def _load_and_bind(sess_def):
    """加载会话 meta + GT + 绑定。返回 (sess_def_enriched, session_meta, gt)。失败 raise。"""
    sid = sess_def["sid"]
    sdir = os.path.join(CAPTURES, sid)
    sess_meta = L.load_session_meta(sdir)
    gt_path = _gt_path_for(sid, sess_def["gt"])
    gt = L.load_gt(gt_path, sess_meta["points_sha256"], sess_meta["meta_sha256"])
    return sess_meta, gt


def build(created_iso, limit=None, verbose=False):
    records = []
    split_sessions = []
    negative_candidates = []
    qual_items_for_report = []   # 供资格报告

    for sd in SESSIONS:
        name, sid = sd["name"], sd["sid"]
        sess_meta, gt = _load_and_bind(sd)
        binding_ok = gt["binding_ok"]
        per_frames = {f["bag_time_sec"]: i for i, f in enumerate(sess_meta["frames"])}
        # frame_idx -> bag_time
        frames = sess_meta["frames"]

        def ts_of(fi):
            return frames[fi]["bag_time_sec"] if 0 <= fi < len(frames) else None

        # 一次构建每帧 compact 映射的缓存在按需
        maps_cache = {}

        def maps_for(fi):
            if fi not in maps_cache:
                fobj = frames[fi]
                xyz = L.read_frame_xyz(sess_meta["points_path"], fobj["offset_points"],
                                       fobj["count_points"], sess_meta["stride_bytes"])
                maps_cache[fi] = L.build_compact_maps(xyz)
            return maps_cache[fi]

        selected = _select_objects_for_session(sd["name"], sess_meta, gt, sid)
        if limit:
            selected = selected[:limit]

        n_pos_frames = len({o.get("frame_idx") for o in gt["objects"]
                            if o.get("class_name") == "PERSON"})
        n_neg = len([o for o in gt["objects"]
                     if o.get("class_name") in ("FURNITURE", "BACKGROUND")])

        split_sessions.append({
            "session_id": sid, "name": name, "n_frames": sess_meta["n_frames"],
            "n_positive_frames": n_pos_frames, "n_negative_candidates": n_neg,
            "eligible": binding_ok and sid != "cap_20261010_180751",
            "role_hint": sd["fold"], "reason": gt["binding_reason"] if not binding_ok else None,
        })

        for o, fi, extra in selected:
            if fi is None or not (0 <= fi < len(frames)):
                continue
            src = o.get("source") or SC.SOURCE_HUMAN  # 缺 source 保守仍视为 human 待复核
            if src == "propagated":
                label_source = SC.SOURCE_PROPAGATED
            elif src == "model":
                label_source = SC.SOURCE_MODEL_SUSPECT
            elif src == SC.SOURCE_LABEL_DERIVED or (
                    isinstance(src, str) and src.startswith("LABEL_DERIVED")):
                label_source = SC.SOURCE_LABEL_DERIVED
            else:
                label_source = SC.SOURCE_HUMAN

            # compact → raw 成员映射（绑定破时仍尝试 decode，但资格标 INVALID）
            mp = maps_for(fi)
            dec = L.object_member_raw_indices(o.get("raw_point_indices"), mp["raw_of_leaf"])
            member_raw = sorted(set(dec["raw_indices"]))
            member_compact = L.decode_indices(o.get("raw_point_indices"))

            # has_candidate 语义：D02 不跑检测器，故默认无法证实候选存在。
            # 对已有证据的确证漏检帧（S6 f187/188 bg_loss, f91/128/129/130/171 no_candidate），
            # 依据 ATTRIBUTION/诊断报告将 has_candidate=False，让 qualify 命中 bg_loss / no_candidate
            # （资格 UNKNOWN + 具体 reason），而非被非穷尽 PARTIAL/coverage_gap 吃掉。
            _bg = extra.get("bg_loss", False)
            _nc = extra.get("no_candidate", False)
            q = Q.qualify_record(
                label_source=label_source,
                sha_binding_ok=binding_ok,
                exhaustive=sd["exhaustive"],
                has_gt_human=(o.get("class_name") == "PERSON"),
                has_candidate=not (_bg or _nc),
                bg_loss=_bg,
                propagated=(label_source == SC.SOURCE_PROPAGATED),
                two_person_suspect=extra.get("two_person_suspect", False),
                low_purity=extra.get("furniture_candidate", False),
            )
            rec = {
                "session_id": sid, "frame_idx": fi, "timestamp_s": ts_of(fi),
                "index_domain": SC.INDEX_DOMAIN_COMPACT,
                "member_point_raw": member_raw,
                "member_point_compact": member_compact,
                "label_source": label_source,
                "review_status": q["review_status"],
                "qualification": q["qualification"],
                "reason": q["reason"], "class_name": o.get("class_name"),
            }
            records.append(rec)
            qual_items_for_report.append({
                "session_id": sid, "name": name, "frame_idx": fi,
                "qualification": q["qualification"], "reason": q["reason"],
                "review_status": q["review_status"], "label_source": label_source,
            })
            # 负例候选（FURNITURE/BACKGROUND 或 model_suspect）
            if o.get("class_name") in ("FURNITURE", "BACKGROUND") or \
                    label_source == SC.SOURCE_MODEL_SUSPECT:
                negative_candidates.append({
                    "candidate_id": "%s:f%d:%s" % (sid, fi, o.get("object_id", "?")),
                    "session_id": sid, "fold": sd["fold"],
                    "label_source": label_source,
                    "review_status": q["review_status"],
                    "qualification": q["qualification"],
                })

    # attach dedup_hash + raw_input_sha per session 并导出
    input_sha_map = {}
    for sd in SESSIONS:
        sess_meta, _gt = _load_and_bind(sd)
        input_sha_map[sd["sid"]] = {
            "meta": sess_meta["meta_sha256"], "points": sess_meta["points_sha256"]}

    out_records = []
    for r in records:
        rr = dict(r)
        rr["raw_input_sha256"] = input_sha_map[r["session_id"]]
        out_records.append(E.make_review_item(
            session_id=rr["session_id"], frame_idx=rr["frame_idx"],
            timestamp_s=rr["timestamp_s"], raw_input_sha256=rr["raw_input_sha256"],
            index_domain=rr["index_domain"], member_point_raw=rr["member_point_raw"],
            member_point_compact=rr["member_point_compact"], label_source=rr["label_source"],
            review_status=rr["review_status"], qualification=rr["qualification"],
            reason=rr["reason"], class_name=rr["class_name"]))

    # 硬门：机器产物不得出现 reviewed/BOUND
    Q.validate_no_human_auto(out_records)

    os.makedirs(REVIEW_OUT, exist_ok=True)
    os.makedirs(EVIDENCE, exist_ok=True)

    pkg = E.write_package(out_records, REVIEW_OUT, "review_package", created_iso)

    # split 草案
    split_draft = SP.build_split_draft(split_sessions)
    session_fold = SP.session_fold_map(split_draft)
    records_for_dedup = []
    for r in out_records:
        records_for_dedup.append({
            "session_id": r["session_id"],
            "fold": session_fold.get(r["session_id"], "blocked"),
            "dedup_hash": r["dedup_hash"], "class_name": r["class_name"],
        })
    dedup_report = SP.cross_fold_exact_duplicate_check(records_for_dedup)

    neg_report = SP.negative_evidence_report(negative_candidates)

    # 落盘 split 草案 + 报告（也放 evidence 一份只读副本）
    E._atomic_write(os.path.join(REVIEW_OUT, "split_draft.json"),
                    json.dumps(split_draft, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    E._atomic_write(os.path.join(REVIEW_OUT, "dedup_report.json"),
                    json.dumps(dedup_report, ensure_ascii=False, indent=2) + "\n")
    E._atomic_write(os.path.join(REVIEW_OUT, "negative_evidence_report.json"),
                    json.dumps(neg_report, ensure_ascii=False, indent=2) + "\n")
    E._atomic_write(os.path.join(REVIEW_OUT, "qualify_items.json"),
                    json.dumps(qual_items_for_report, ensure_ascii=False, indent=2) + "\n")

    summary = {
        "n_records": len(out_records),
        "manifest": pkg["manifest"],
        "dedup_exact_duplicate": dedup_report["exact_duplicate"],
        "dedup_cross_fold_hashes": len(dedup_report["cross_fold_hashes"]),
        "negative_counts": {k: len(v) for k, v in neg_report.items()
                            if isinstance(v, list)},
        "split_folds": {k: len(v) for k, v in split_draft["folds"].items()},
        "evidence_dir": EVIDENCE,
        "review_out": REVIEW_OUT,
    }
    if verbose:
        print(json.dumps({k: summary[k] for k in
                          ("n_records", "dedup_exact_duplicate",
                           "negative_counts", "split_folds")},
                         ensure_ascii=False, indent=2))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="HFUS-D02 待审包构建")
    ap.add_argument("--created-iso", default="2026-10-11T00:00:00Z",
                    help="包创建时间戳（默认固定，保证可复跑 SHA 稳定）")
    ap.add_argument("--limit", type=int, default=None, help="调试用：每会话最多取 N 条")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    summary = build(created_iso=args.created_iso, limit=args.limit, verbose=args.verbose)
    # 资格/摘要落 evidence
    E._atomic_write(os.path.join(EVIDENCE, "02_BUILD_SUMMARY.json"),
                    json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
