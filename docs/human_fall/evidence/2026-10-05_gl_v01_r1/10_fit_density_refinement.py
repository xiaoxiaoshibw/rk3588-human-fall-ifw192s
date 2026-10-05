"""Exclude sparse XY cells using every FIT frame; do not inspect holdout rows."""
import json
from pathlib import Path
import sys
import uuid
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
import leveling as W
from leveling_quality import rotation

evidence = Path(__file__).resolve().parent
sid = "cap_20261004_203349"
selection = json.loads((evidence / (sid + "_fit_roi_selection.json")).read_text(encoding="utf-8"))
remote = ROOT / "captures" / "remote"; outroot = ROOT / "captures" / "leveled"
directory, meta, binding = W.source(remote, sid)
records = np.memmap(directory / "points.bin", dtype="u1", mode="r")
xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=records, strides=(28, 4))
cells = selection["candidate_cells"]
for cell in cells:
    cell["fit_frame_counts"] = []
for ordinal, frame in enumerate(meta["frames"]):
    if ordinal in selection["excluded_ordinals"]:
        continue
    points = xyz[frame["offset_points"]:frame["offset_points"]+frame["count_points"]].astype("f8")
    points = points[np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)]
    display = points @ rotation(26, 0).T
    for cell in cells:
        xl, xh, yl, yh = cell["bounds"]
        cell["fit_frame_counts"].append(int(np.count_nonzero((display[:,0]>=xl)&(display[:,0]<xh)&(display[:,1]>=yl)&(display[:,1]<yh))))
usable = [cell for cell in cells if min(cell["fit_frame_counts"]) >= 30]
if len(usable) < 4:
    raise RuntimeError("FIT frames have fewer than four adequately sampled cells")
chosen = [min(usable, key=lambda c: (c["rms_m"], -c["count"]))]
center = lambda c: np.array([(c["bounds"][0]+c["bounds"][1])/2, (c["bounds"][2]+c["bounds"][3])/2])
while len(chosen) < 4:
    chosen.append(max([c for c in usable if c not in chosen], key=lambda c: (min(float(np.linalg.norm(center(c)-center(s))) for s in chosen), -c["rms_m"])))
W.dump(evidence / "10_fit_density_selection.json", {"sid":sid,"min_points_per_fit_frame":30,
       "excluded_ordinals":selection["excluded_ordinals"],"candidate_cells":cells,"chosen":chosen,
       "reason":"previous far cell FIT mean only22 points; sparse sampling requires FIT-only minimum-density gate; keep previous holdout19 failure"})
config = {"pitch_deg":26.,"roll_deg":0.,"physical_height_m":1.14,"ground_confirmed":True,
          "regions":[c["bounds"] for c in chosen],
          "basis":"离线FIT帧自动选完整XY区域并要求每个FIT帧至少30点，3留出帧未用于此次选区；全高度保留。原稀疏区19点留出失败与既有曝光保留，非物理标定。"}
request = W.validate_request({"schema":1,"sid":sid,"source":binding,"config":config})
job_id = uuid.uuid4().hex
print(job_id,config["regions"],flush=True)
report,artifacts = W.run_job(remote,outroot,request,job_id,lambda m:print(m,flush=True))
summary = {"sid":sid,"job_id":job_id,"recommended":report["recommended"],"artifacts":list(artifacts),
           "methods":{n:{"valid":a["valid"],"reject_reasons":a["reject_reasons"],"full":a.get("full")} for n,a in report["estimators"].items()}}
W.dump(evidence / "10_fit_density_result.json",summary)
print(json.dumps(summary,ensure_ascii=False),flush=True)
