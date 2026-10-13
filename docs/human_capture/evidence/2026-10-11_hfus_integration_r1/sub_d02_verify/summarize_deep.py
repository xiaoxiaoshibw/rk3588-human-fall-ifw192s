# -*- coding: utf-8 -*-
# 从 deep_summary.json 精简到关键事实
import json
d = json.load(open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/deep_summary.json","r",encoding="utf-8"))
o = {}
for k in ["package_01/MANIFEST.json","package_01/qualification.json","rec_values","rec_first"]:
    o[k]=d[k]
# split 精简
sp = d["package_01/split_manifest.json"]
o["split_status"]=sp.get("status"); o["split_scope"]=sp.get("scope")
o["split_session_fold"]=sp.get("session_fold")
sess = sp.get("sessions")
o["split_sessions_keys"] = list(sess.keys()) if isinstance(sess,dict) else type(sess).__name__
if isinstance(sess,dict):
    o["split_per_session_count"]={k:(v.get("n_records") or v.get("count") or len(v.get("records",[])) if isinstance(v,dict) else len(v)) for k,v in sess.items()}
o["rec_S9"]=[{k:v for k,v in r.items() if k!="suggestions"} for r in d["rec_S9"]]
o["rec_S1"]=[{k:v for k,v in r.items() if k!="suggestions"} for r in d["rec_S1"]]
# suggestions 结构（first only，截断）
r0 = d["rec_first"].get("suggestions")
if isinstance(r0,dict):
    o["rec_first_suggestions_keys"]=list(r0.keys())
    o["rec_first_suggestions_summary"]={k:(len(v) if isinstance(v,list) else (v if not isinstance(v,(dict,list)) else "complex")) for k,v in r0.items()}
elif isinstance(r0,list):
    o["rec_first_suggestions_len"]=len(r0); o["rec_first_suggestions0"]=r0[0] if r0 else None
else:
    o["rec_first_suggestions"]=r0
o["coverage_PRIORITY_head"]=d["coverage_PRIORITY_head"]
o["coverage_frames_by_session"]=d["coverage_frames_by_session"]
o["coverage_records_0_nosugg"]={k:v for k,v in d["coverage_records_detail"][0].items() if k!="suggestions"}
json.dump(o, open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/deep_keyfacts.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("ok")
