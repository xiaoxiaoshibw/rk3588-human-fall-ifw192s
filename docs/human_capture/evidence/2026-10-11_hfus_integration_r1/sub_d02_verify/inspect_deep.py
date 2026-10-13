# -*- coding: utf-8 -*-
# 深入到 record 层：绑定状态/SHA/坐标域/frame/S9逐对象/覆盖粒度
import json, os
BASE = r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_d02_r1"
def load(p):
    with open(p, "r", encoding="utf-8") as f: return json.load(f)
out = {}

# package_01 small files 全量打印
for fn in ["MANIFEST.json","qualification.json","split_manifest.json"]:
    out["package_01/"+fn] = load(os.path.join(BASE,"package_01",fn))

rp = load(os.path.join(BASE,"package_01","review_package.json"))
recs = rp["records"]
# 字段值集合（小基数）
def collect(keys):
    c = {}
    for r in recs:
        for k in keys:
            if k in r:
                c.setdefault(k,set()).add(str(r[k])[:80])
    return {k:sorted(v)[:20] for k,v in c.items()}
out["rec_values"] = collect(["schema_version","schema_contract","coordinate","index_version","review_status","exhaustive","fold"])
# 每条记录的 binding 结构（抽 S9/S1/first）
def samp(r):
    keep = {k:r.get(k) for k in ("name","session_id","frame","seq","fold","coordinate","index_version","raw_count","valid_count","timestamp_s","exhaustive","known_negative","review_status",
                                 "original_gt_binding","inputs","suggestions","raw_frame_sha256")}
    # raw_frame_sha256 截短
    if isinstance(keep.get("raw_frame_sha256"),str): keep["raw_frame_sha256"]=keep["raw_frame_sha256"][:16]+"..."
    return keep
out["rec_first"] = samp(recs[0])
out["rec_S9"] = [samp(r) for r in recs if r.get("session_id","").endswith("180751")][:3]
out["rec_S1"] = [samp(r) for r in recs if r.get("session_id","").endswith("175227")]

# split
out["split_session_fold_map"] = out.get("package_01/split_manifest.json")

# coverage 明细
cp = load(os.path.join(BASE,"coverage_package_01","COVERAGE_PRIORITY.json"))
out["coverage_PRIORITY_head"] = {k:cp[k] for k in cp}
cov = load(os.path.join(BASE,"coverage_package_01","review_package.json"))["records"]
out["coverage_records_detail"] = [samp(r) for r in cov[:8]]
out["coverage_sessions_frames"] = {(r["session_id"]):0 for r in cov}
frames_by_s = {}
for r in cov:
    frames_by_s.setdefault(r["session_id"],[]).append(r["frame"])
out["coverage_frames_by_session"] = {k:sorted(v) for k,v in frames_by_s.items()}

json.dump(out, open(r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d02_verify/deep_summary.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("ok")
