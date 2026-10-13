# -*- coding: utf-8 -*-
# 帧号与 fold 级统计 + suggestions 汇总 + D02-02 覆盖核对
import json, os
from collections import Counter, defaultdict
BASE = r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_d02_r1"
OUT  = r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify"
def load(p):
    with open(p,"r",encoding="utf-8") as f: return json.load(f)

pk = load(os.path.join(BASE,"package_01","review_package.json"))["records"]
# fold 分布
fold = Counter(r["fold"] for r in pk)
# per-session frames sorted
s_frames = defaultdict(list)
for r in pk:
    s_frames[r["session_id"]].append(r["frame"])
# binding 状态全量
bind = Counter()
for r in pk: bind[r.get("original_gt_binding","<none>")] += 1
# suggestions 跨记录汇总
sug_stat = {
    "n_records_with_suggestions":0,
    "total_suggestions":0,
    "label_source":Counter(),"original_review_status":Counter(),
    "qualification":Counter(),"source_is_independent_review":Counter(),
    "original_class":Counter(),"review_status_suggestion":Counter(),
    "known_negative_records":0,
}
for r in pk:
    if r.get("known_negative"): sug_stat["known_negative_records"]+=1
    sgs = r.get("suggestions") or []
    if sgs: sug_stat["n_records_with_suggestions"]+=1
    for sg in sgs:
        sug_stat["total_suggestions"]+=1
        for k in ("label_source","original_review_status","qualification","source_is_independent_review","original_class"):
            sug_stat[k][str(sg.get(k,"<none>"))]+=1
        sug_stat["review_status_suggestion" if "review_status_suggestion" in sug_stat else "review_status"][str(sg.get("review_status","<none>"))]+=1
# D02-02 要求对照
# S6 = cap_20261010_175804 (主控侧 fold=train, 194 帧) — 检查 128/129/130/171/187/188
# S4 = cap_20261010_175553 (validation, 5 帧) — 期望 20s 连续窗
# S8 = cap_20261010_180557 (test, 194 帧) — 期望 20s 连续窗
# S5 = cap_20261010_175943 (train, 43) — 低覆盖
# S7 = cap_20261010_180235 (stress, 12) — 低覆盖
# S1 = cap_20261010_175227 (train, 14) — 首中末变化点
REQ = {"S6":[("cap_20261010_175804",[128,129,130,171,187,188])]}
s6f = sorted(s_frames.get("cap_20261010_175804",[]))
s6d02 = {f: (f in s6f) for f in [128,129,130,171,187,188]}
s4f = sorted(s_frames.get("cap_20261010_175553",[]))
s8f = sorted(s_frames.get("cap_20261010_180557",[]))
s1f = sorted(s_frames.get("cap_20261010_175227",[]))
s5f = sorted(s_frames.get("cap_20261010_175943",[]))
s7f = sorted(s_frames.get("cap_20261010_180235",[]))
out = {
 "fold_counts": dict(fold),
 "binding_counts": dict(bind),
 "suggestions_summary": {
   "n_records_with_suggestions":sug_stat["n_records_with_suggestions"],
   "total_suggestions":sug_stat["total_suggestions"],
   "known_negative_records":sug_stat["known_negative_records"],
   "label_source":dict(sug_stat["label_source"]),
   "original_review_status":dict(sug_stat["original_review_status"]),
   "qualification":dict(sug_stat["qualification"]),
   "source_is_independent_review":dict(sug_stat["source_is_independent_review"]),
   "original_class":dict(sug_stat["original_class"]),
   "suggestion_review_status":dict(sug_stat["review_status_suggestion"]),
 },
 "frames": {
   "S1_175227_first_last_count": [s1f[0] if s1f else None, s1f[-1] if s1f else None, len(s1f)],
   "S1_frames": s1f,
   "S4_175553_n_frames": len(s4f), "S4_frames": s4f,
   "S5_175943_n_frames": len(s5f), "S5_frames_min_max": [s5f[0] if s5f else None, s5f[-1] if s5f else None],
   "S6_175804_n_frames": len(s6f), "S6_D0202_required_frames_present": s6d02,
   "S7_180235_n_frames": len(s7f), "S7_frames_min_max": [s7f[0] if s7f else None, s7f[-1] if s7f else None],
   "S8_180557_n_frames": len(s8f), "S8_frames_first_last": [s8f[0] if s8f else None, s8f[-1] if s8f else None],
 },
}
json.dump(out, open(os.path.join(OUT,"frame_coverage.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("ok")
