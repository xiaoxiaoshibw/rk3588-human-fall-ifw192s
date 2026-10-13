# -*- coding: utf-8 -*-
import json
d = json.load(open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/keyfacts2.json","r",encoding="utf-8"))
o = {}
def strip_bigsug(r):
    if not isinstance(r,dict): return r
    rr = dict(r)
    if "suggestions" in rr:
        s = rr["suggestions"]
        if isinstance(s,list):
            rr["suggestions_n"]=len(s)
            rr["suggestions_brief"]=[{k:v for k,v in sg.items() if k!="compact_indices"} | {"compact_indices_n":len(sg.get("compact_indices",[]))} for sg in s]
        elif isinstance(s,dict):
            rr["suggestions_keys"]=list(s.keys())
    return rr
o["rec_first_brief"]=strip_bigsug(d["rec_first"])
o["rec_S9_brief"]=[strip_bigsug(r) for r in d["rec_S9"]]
o["rec_S1_brief"]=[strip_bigsug(r) for r in d["rec_S1"]]
o["rec_first_inputs_summary"]=d["rec_first_inputs_summary"]
o["split_session_fold"]=d["split_session_fold"]
o["split_per_session_count"]=d["split_per_session_count"]
o["qualification"]=d["qualification"]
o["cov_status"]=d.get("cov_status");o["cov_source"]=d.get("cov_source");o["cov_ranking"]=d.get("cov_ranking")
o["cov_priorities_n"]=d.get("cov_priorities_n")
o["cov_priorities_0"]=d.get("cov_priorities_0")
o["coverage_frames_by_session"]=d["coverage_frames_by_session"]
o["coverage_records_0_brief"]=strip_bigsug(d["coverage_records_0_nosugg"])
o["rec_first_suggestions_keys"]=d.get("rec_first_suggestions_keys")
o["rec_first_suggestions_summary"]=d.get("rec_first_suggestions_summary")
json.dump(o, open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/keyfacts3.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("ok")
