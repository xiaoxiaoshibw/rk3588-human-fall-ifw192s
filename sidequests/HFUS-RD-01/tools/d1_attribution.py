# -*- coding: utf-8 -*-
"""D1 分层归因（流式）。

对每个 reviewed PERSON GT 对象（逐帧）：
  n_gt / 在 valid 中 / 在 bg_kept、final、readmitted、no_reference_*UNKNOWN*
  理由中、被候选覆盖、被接受候选覆盖、被确认 track 帧覆盖。

对候选：n、决策、RF prob、GT 覆盖率/纯度（用 ledger 自带 gt_hits，已验
= 点集交集语义），记入 oracle 诊断基础表（每候选一行落盘 parquet/npz，
后续 fusion 消融直接复用）。

S9 只探索不进判定；S1 无 GT → 只记候选侧 FP 统计。

输出：
  work/d1_per_frame.jsonl    — 每帧一行（小）
  work/d1_candidates.jsonl   — 每候选一行（含 prob、n、GT 覆盖、分桶）
  work/d1_gt_objects.jsonl   — 每 GT 对象一行（点级保留账本 + 桶）
  evidence/D1_LAYER_SUMMARY.json — 汇总（分子/分母齐备）
"""
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

NPOINT_BUCKET = [(0, 14), (15, 29), (30, 59), (60, 10 ** 9)]
REASON_UNKNOWN = [k for k in [
    "no_reference_XY_support_UNKNOWN",
    "no_reference_XY_support_UNKNOWN_r0.6"]]


def bucket_of(n):
    for i, (lo, hi) in enumerate(NPOINT_BUCKET):
        if lo <= n <= hi:
            return i
    return len(NPOINT_BUCKET) - 1


def main():
    os.makedirs(C.WORK, exist_ok=True)
    os.makedirs(C.EVIDENCE, exist_ok=True)
    f_frm = open(os.path.join(C.WORK, "d1_per_frame.jsonl"), "w",
                 encoding="utf-8")
    f_cand = open(os.path.join(C.WORK, "d1_candidates.jsonl"), "w",
                  encoding="utf-8")
    f_gt = open(os.path.join(C.WORK, "d1_gt_objects.jsonl"), "w",
                encoding="utf-8")
    summary = {}

    for sid in C.SIDS:
        gt = C.load_gt(sid)
        objs_by_frame = collections.defaultdict(list)
        if gt is not None:
            for o in gt["objects"]:
                if (o["class_name"] == "PERSON"
                        and o["review_status"] == "reviewed"
                        and o["source"] == "human"):
                    objs_by_frame[o["frame_idx"]].append(o)
        ssum = {
            "sid": sid, "short": C.SID_SHORT[sid],
            "gt_present": gt is not None,
            "frames": 0, "frames_with_gt": 0,
            "gt_obj_total": 0,
            # 分子分母账本（点级）
            "gt_pts_total": 0, "gt_pts_valid": 0, "gt_pts_bg_kept": 0,
            "gt_pts_final": 0, "gt_pts_readmitted": 0,
            "gt_pts_unknown_reason": 0,
            # 对象级（GT 覆盖率 ≥10% 视为"被候选触及"）
            "gt_obj_covered_proposal": 0, "gt_obj_covered_accepted": 0,
            "gt_obj_covered_confirmed30": 0,
            # RF 独立误拒（候选覆盖到 GT 但 prob<0.55）
            "oracle_reject_rf_low": 0,
            # 候选侧
            "cand_total": 0, "cand_accepted": 0,
            "cand_pure_fp": 0,  # 候选与任何 reviewed GT 无交集（S1 全体）
            "track_frames": 0,
            "per_bucket_gt_obj": [0] * 5,
            "per_bucket_gt_covered": [0] * 5,
            "per_bucket_cand": [0] * 5,
            "per_bucket_cand_fp": [0] * 5,
        }

        mm = None
        for rec in C.iter_ledger(sid, fields=[
                "frame_index", "sid", "stages", "candidates", "gt",
                "tracks", "raw_n", "valid_n"]):
            fi = rec["frame_index"]
            ssum["frames"] += 1
            M = C.stages_masks(rec)
            rM = C.reason_masks(rec)
            unk = np.concatenate([rM[k] for k in rM if k.startswith(
                "no_reference_XY_support_UNKNOWN")]) if any(
                    k.startswith("no_reference_XY_support_UNKNOWN")
                    for k in rM) else np.empty(0, dtype=np.int64)
            valid_set = set(M["valid_ids"].tolist())
            bg_set = set(M["bg_kept_ids"].tolist())
            fin_set = set(M["final_ids"].tolist())
            read_set = set(M["readmitted_ids"].tolist()) if len(
                M.get("readmitted_ids", [])) else set()
            unk_set = set(unk.tolist())

            # 候选账本
            cands = rec.get("candidates", [])
            cand_idx_sets = [np.asarray(c["raw_indices"], dtype=np.int64)
                             for c in cands]
            accepted = [i for i, c in enumerate(cands)
                        if c["decision"] in ("HUMAN_CANDIDATE",
                                             "CONFIRMED_HUMAN")]
            confirmed_tracks = [t for t in rec.get("tracks", [])
                                if t.get("human_confirmed")]
            if confirmed_tracks:
                ssum["track_frames"] += 1
            ssum["cand_total"] += len(cands)
            ssum["cand_accepted"] += len(accepted)

            if mm is None:
                _x, _i, mm = C.read_frame_xyz(sid, 0)
            raw_of_leaf, mm = C.raw_of_leaf_frame(sid, fi, mm=mm)

            # GT 对象账
            glist = objs_by_frame.get(fi, [])
            ssum["frames_with_gt"] += 1 if glist else 0
            for o in glist:
                raw_idx = C.gt_raw_indices(o, raw_of_leaf)
                idx_list = raw_idx.tolist()
                n_gt = len(idx_list)
                ssum["gt_obj_total"] += 1
                ssum["gt_pts_total"] += n_gt
                in_valid = sum(i in valid_set for i in idx_list)
                in_bg = sum(i in bg_set for i in idx_list)
                in_fin = sum(i in fin_set for i in idx_list)
                in_read = sum(i in read_set for i in idx_list)
                in_unk = sum(i in unk_set for i in idx_list)
                ssum["gt_pts_valid"] += in_valid
                ssum["gt_pts_bg_kept"] += in_bg
                ssum["gt_pts_final"] += in_fin
                ssum["gt_pts_readmitted"] += in_read
                ssum["gt_pts_unknown_reason"] += in_unk
                # 候选覆盖（含 proposal/accpeted 两层）
                best_prop, best_acc = 0.0, 0.0
                best_prop_prob = None
                gt_set = set(idx_list)
                for ci, c in enumerate(cands):
                    inter = len(gt_set & set(cand_idx_sets[ci].tolist()))
                    if inter == 0:
                        continue
                    cov = inter / n_gt
                    if cov > best_prop:
                        best_prop = cov
                        best_prop_prob = c["prob"]
                    if ci in accepted and cov > best_acc:
                        best_acc = cov
                b = bucket_of(n_gt)
                ssum["per_bucket_gt_obj"][b] += 1
                if best_prop >= 0.1:
                    ssum["gt_obj_covered_proposal"] += 1
                    ssum["per_bucket_gt_covered"][b] += 1
                if best_acc >= 0.1:
                    ssum["gt_obj_covered_accepted"] += 1
                if best_prop >= 0.1 and best_prop_prob is not None \
                        and best_prop_prob < 0.55:
                    ssum["oracle_reject_rf_low"] += 1
                f_gt.write(json.dumps({
                    "sid": sid, "frame": fi, "obj": o["id"],
                    "n_gt": n_gt, "bucket": b,
                    "pts_valid": in_valid, "pts_bg": in_bg,
                    "pts_final": in_fin, "pts_unknown_reason": in_unk,
                    "cov_proposal": round(best_prop, 4),
                    "cov_accepted": round(best_acc, 4),
                }, ensure_ascii=False) + "\n")

            # 候选行（含 RF prob、gt_hits 覆盖纯度、分桶、FP 标记）
            reviewed_known = len(glist) > 0
            for ci, c in enumerate(cands):
                n = c["n"]
                b = bucket_of(n)
                ssum["per_bucket_cand"][b] += 1
                hits = c.get("gt_hits") or []
                gh = max(hits, key=lambda h: h["coverage"]) if hits else None
                is_fp_known = (not hits)  # 与任何 reviewed GT 无交集
                if is_fp_known:
                    ssum["per_bucket_cand_fp"][b] += 1
                    ssum["cand_pure_fp"] += 1
                f_cand.write(json.dumps({
                    "sid": sid, "frame": fi, "cand": c["id"],
                    "n": n, "bucket": b, "prob": round(c["prob"], 5),
                    "decision": c["decision"], "src": c.get("source"),
                    "x": round(c["x"], 3), "y": round(c["y"], 3),
                    "z": round(c["z"], 3),
                    "gt_cov": round(gh["coverage"], 4) if gh else 0.0,
                    "gt_purity": round(gh["purity"], 4) if gh else 0.0,
                    "gt_id": gh["id"] if gh else None,
                    "reviewed_frame": reviewed_known,
                }, ensure_ascii=False) + "\n")
        ssum["ratio_gt_valid"] = _r(ssum["gt_pts_valid"], ssum["gt_pts_total"])
        ssum["ratio_gt_bg"] = _r(ssum["gt_pts_bg_kept"], ssum["gt_pts_valid"])
        ssum["ratio_gt_final"] = _r(ssum["gt_pts_final"],
                                    ssum["gt_pts_bg_kept"])
        summary[sid] = ssum
        print("[D1] %s done frames=%d gt_obj=%d" % (
            sid, ssum["frames"], ssum["gt_obj_total"]))

    f_frm.close(); f_cand.close(); f_gt.close()
    with open(os.path.join(C.EVIDENCE, "D1_LAYER_SUMMARY.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print("[D1] SUMMARY written")


def _r(a, b):
    return round(a / b, 4) if b else None


if __name__ == "__main__":
    main()
