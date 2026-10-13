# -*- coding: utf-8 -*-
import json
d = json.load(open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/keyfacts.json","r",encoding="utf-8"))
o = {}
# 精简 manifest_no_files（去掉 inputs/sources 里的长列表只保字段名）
mnf = d["manifest_no_files"]
o["manifest_schema"]=mnf.get("schema")
o["manifest_record_count"]=mnf.get("record_count")
o["manifest_ponytail"]=mnf.get("ponytail")
for k in ("interfaces","sources","inputs","models"):
    v=mnf.get(k)
    o["manifest_"+k+"_keys"]=list(v.keys()) if isinstance(v,dict) else type(v).__name__
o["manifest_inputs_brief"]=mnf.get("inputs")
o["manifest_sources_brief"]=mnf.get("sources")
o["manifest_models_brief"]=mnf.get("models")
o["manifest_files_count"]=d["manifest_files_count"]
o["manifest_files_sample"]=d["manifest_files_sample"]
o["rec_values"]=d["rec_values"]
o["rec_first"]={k:v for k,v in d["rec_first"].items() if k not in ("compact_to_raw","raw_to_compact","inputs")}
o["rec_first_inputs_keys"]=list(d["rec_first"].get("inputs",{}).keys()) if isinstance(d["rec_first"].get("inputs"),dict) else None
o["rec_first_inputs_summary"]=d["rec_first"].get("inputs")
o["rec_S9"]=[{k:v for k,v in r.items() if k not in ("compact_to_raw","raw_to_compact","inputs")} for r in d["rec_S9"]]
o["rec_S1"]=[{k:v for k,v in r.items() if k not in ("compact_to_raw","raw_to_compact","inputs")} for r in d["rec_S1"]]
o["rec_first_suggestions_keys"]=d.get("rec_first_suggestions_keys")
o["rec_first_suggestions_summary"]=d.get("rec_first_suggestions_summary")
o["split_status"]=d.get("split_status"); o["split_scope"]=d.get("split_scope")
o["split_session_fold"]=d.get("split_session_fold")
o["split_per_session_count"]=d.get("split_per_session_count")
o["qualification"]=d["qualification"]
# coverage priority：只保 status/source/ranking/limits + priorities 结构
cp = d["coverage_PRIORITY_head"]
o["cov_status"]=cp.get("status"); o["cov_source"]=cp.get("source"); o["cov_ranking"]=cp.get("ranking"); o["cov_limits"]=cp.get("limits")
pr=cp.get("priorities")
o["cov_priorities_n"]=len(pr) if isinstance(pr,list) else None
if isinstance(pr,list) and pr:
    o["cov_priorities_0"]=pr[0]; o["cov_priorities_all"]=[{k:v for k,v in p.items() if k in ("session_id","frame","reason","priority","need","target")} for p in pr]
o["coverage_frames_by_session"]=d["coverage_frames_by_session"]
o["coverage_records_0_nosugg"]=d["coverage_records_0_nosugg"]
json.dump(o, open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/keyfacts2.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("ok")
