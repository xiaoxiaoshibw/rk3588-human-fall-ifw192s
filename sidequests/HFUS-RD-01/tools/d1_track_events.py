# -*- coding: utf-8 -*-
"""D1 补遗：跟踪层事件账（确认延迟 / 断档 / ID 切换近似）。

口径（预登记）：
  per-frame confirmed track_id 集合来自 ledger tracks[].human_confirmed。
  GT 关联：候选带 track_id 与 GT 交集≥0.5 覆盖的帧，该 track 在该帧记为
  GT-绑定 confirmed。birth=该 GT 对象(track_id)的 confirmed 帧首次出现；
  confirm_delay_frames = birth_frame - GT 首帧 frame_idx。
  ID 切换近似：同一 GT track_id 相邻 confirmed 帧之间 track_id 变化次数。
输出 evidence/D1_TRACK_EVENTS.json（每会话一行）。
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

OUT = os.path.join(C.EVIDENCE, "D1_TRACK_EVENTS.json")


def main():
    report = {}
    for sid in C.SIDS:
        gt = C.load_gt(sid)
        if sid == "cap_20261010_180751":
            report[sid] = {"explore_only": True}
            continue
        if gt is None:
            report[sid] = {"gt": False}
            continue
        gt_track_ids = set()
        first_frame_of_gt = {}         # GT track_id -> 首次 frame_idx
        for o in gt["objects"]:
            if (o["class_name"] == "PERSON" and o["review_status"] == "reviewed"
                    and o["source"] == "human"):
                gt_track_ids.add(o["track_id"])
                first_frame_of_gt.setdefault(
                    o["track_id"], o["frame_idx"])
                first_frame_of_gt[o["track_id"]] = min(
                    first_frame_of_gt[o["track_id"]], o["frame_idx"])
        # 每帧: confirmed track_id 集合 + 哪个 track 与 GT 相交
        frames = defaultdict(set)      # fi -> set(confirmed track ids)
        gt_bound_track_by_frame = defaultdict(set)  # fi -> set(track ids bound to GT)
        for rec in C.iter_ledger(sid, fields=["frame_index", "tracks",
                                              "candidates"]):
            fi = rec["frame_index"]
            # 显式使用 c["track_confirmed"]（ledger 已按 fusion 3票窗打标）
            for c in rec.get("candidates", []):
                if (c.get("track_confirmed")
                        and c.get("track_id")
                        and any(h["coverage"] >= 0.5
                                for h in (c.get("gt_hits") or []))):
                    gt_bound_track_by_frame[fi].add(c["track_id"])
            conf = {t.get("id") for t in rec.get("tracks", [])
                    if t.get("human_confirmed")}
            frames[fi] = conf
        # delay / ID-switch
        delays = {}
        for tid, f0 in first_frame_of_gt.items():
            appeared = [fi for fi in sorted(gt_bound_track_by_frame)
                        if fi >= f0]
            delays[tid] = (appeared[0] - f0) if appeared else None
        all_frames = sorted(frames)
        id_switches = 0
        flicker = 0
        gaps = 0
        last_conf = None
        for i, fi in enumerate(all_frames):
            conf_now = gt_bound_track_by_frame.get(fi, set())
            if last_conf is not None:
                if not conf_now and last_conf:
                    flicker += 1
                elif conf_now and last_conf \
                        and not (conf_now & last_conf):
                    id_switches += 1
            if conf_now:
                last_conf = conf_now
        report[sid] = {
            "gt_track_ids": sorted(t for t in gt_track_ids if t),
            "first_frame_of_gt": first_frame_of_gt,
            "confirm_delay_frames_per_track": delays,
            "frames_with_any_gt_bound_conf": len(gt_bound_track_by_frame),
            "frames_total": len(all_frames),
            "id_switch_events_approx": id_switches,
            "flicker_lost_events_approx": flicker,
        }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("[D1-TRK] written")


if __name__ == "__main__":
    main()
