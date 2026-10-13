# -*- coding: utf-8 -*-
import json
d = json.load(open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/deep_keyfacts.json","r",encoding="utf-8"))
o = {}
for k in ["rec_values","rec_first","rec_S9","rec_S1","split_status","split_scope","split_session_fold",
          "split_per_session_count","coverage_PRIORITY_head","coverage_frames_by_session","coverage_records_0_nosugg",
          "rec_first_suggestions_keys","rec_first_suggestions_summary","rec_first_suggestions_len","rec_first_suggestions0"]:
    if k in d: o[k]=d[k]
# MANIFEST 去掉 files（只保 record_count/schema/interfaces/sources/inputs/models/ponytail）
m = d["package_01/MANIFEST.json"]
o["manifest_no_files"] = {k:v for k,v in m.items() if k!="files"}
fl = m.get("files",[])
if isinstance(fl,dict):
    o["manifest_files_count"]=len(fl); o["manifest_files_sample"]=list(fl.items())[:3]
else:
    o["manifest_files_count"]=len(fl); o["manifest_files_sample"]=fl[:3]
q = d["package_01/qualification.json"]
o["qualification"]=q
json.dump(o, open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/keyfacts.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("ok")
