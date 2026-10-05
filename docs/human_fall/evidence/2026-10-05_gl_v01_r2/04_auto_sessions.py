"""All three sessions: new automatic detector; manual ROI used only after detection."""
import json
from pathlib import Path
import sys
import time
import uuid
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
import leveling as W
import validation as V

evidence = Path(__file__).resolve().parent
remote, outroot = ROOT / "captures" / "remote", ROOT / "captures" / "leveled"
reference = json.loads((outroot / "27f870c6c7be43f4b9dc50121a5fc03f" / "report.json").read_text(encoding="utf-8"))
results = []
for sid in V.SESSIONS:
    _, _, binding = W.source(remote, sid)
    request = W.validate_request({"schema":1,"sid":sid,"source":binding,
        "config":{"pitch_deg":26.,"roll_deg":0.,"physical_height_m":1.14,"mode":"auto"}})
    job_id = uuid.uuid4().hex; began = time.monotonic()
    print(sid,job_id,flush=True)
    entry = {"sid":sid,"job_id":job_id}
    try:
        report, artifacts = W.run_job(remote,outroot,request,job_id,lambda message:print(message,flush=True))
        entry.update(regions=report["config"]["regions"],candidate=report["config"]["auto_candidate"],
                     recommended=report["recommended"],artifacts=list(artifacts),
                     estimators={n:{"valid":a["valid"],"reject_reasons":a["reject_reasons"],"full":a.get("full")} for n,a in report["estimators"].items()})
        if sid == "cap_20261004_202456":
            a,b = report["estimators"]["tls"],reference["estimators"]["tls"]
            entry["manual_reference_check"] = {"angle_deg":float(np.degrees(np.arccos(np.clip(np.dot(a["normal_source"],b["normal_source"]),-1,1)))),
                "offset_gap_m":abs(a["offset_source_m"]-b["offset_source_m"]),
                "reference_regions":reference["config"]["regions"],"used_for_detection":False}
    except Exception as exc:
        entry["error"] = str(exc)
    entry["seconds"] = time.monotonic()-began; results.append(entry)
    W.dump(evidence / (sid+"_auto_result.json"),entry)
    print(json.dumps(entry,ensure_ascii=False),flush=True)
W.dump(evidence / "04_auto_results.json",results)
