"""Authorized two-session evaluation. Preserve auto failures, explicit ROI comparison."""
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
import leveling as W

evidence = Path(__file__).resolve().parent
remote = ROOT / "captures" / "remote"
outroot = ROOT / "captures" / "leveled"
reference = json.loads((outroot / "27f870c6c7be43f4b9dc50121a5fc03f" / "report.json").read_text(encoding="utf-8"))
results = []
for sid in ("cap_20261004_203349", "cap_20261004_203135"):
    _, _, binding = W.source(remote, sid)
    for mode in ("auto", "reference_roi_comparison"):
        if mode == "auto":
            config = {"pitch_deg": 26., "roll_deg": 0., "physical_height_m": 1.14, "mode": "auto"}
        else:
            config = {**reference["config"], "basis": "离线数值对照：继承202456同场景四个XY区域，未独立核验本会话地面身份；保留auto失败，不作物理标定声明。"}
        request = W.validate_request({"schema": 1, "sid": sid, "source": binding, "config": config})
        job_id = uuid.uuid4().hex
        entry = {"sid": sid, "mode": mode, "job_id": job_id}
        began = time.monotonic()
        print(sid, mode, job_id, flush=True)
        try:
            report, artifacts = W.run_job(remote, outroot, request, job_id, lambda msg: print(msg, flush=True))
            entry.update(recommended=report["recommended"], methods={n: {"valid": a["valid"], "reject_reasons": a["reject_reasons"], "full": a.get("full")} for n, a in report["estimators"].items()}, artifacts=list(artifacts))
        except Exception as exc:
            entry["error"] = str(exc)
        entry["seconds"] = time.monotonic() - began
        results.append(entry)
        W.dump(evidence / (sid + "_" + mode + ".json"), entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if entry.get("recommended"):
            break
W.dump(evidence / "06_two_session_results.json", results)
