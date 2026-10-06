"""GL-S02 real job ledger: full run_job on 223757 through the auto (v3) entry."""
import json
import sys
import time
import uuid
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
import leveling as W  # noqa: E402

SID = "cap_20261002_223757"
OUT = Path(__file__).resolve().parent
REMOTE, OUTROOT = ROOT / "captures" / "remote", ROOT / "captures" / "leveled"


def main():
    began = time.monotonic()
    _, _, binding = W.source(REMOTE, SID)
    request = W.validate_request({"schema": 1, "sid": SID, "source": binding,
                                  "config": {"pitch_deg": 26., "roll_deg": 0.,
                                             "physical_height_m": 1.14, "mode": "auto"}})
    job_id = uuid.uuid4().hex
    print("job", job_id, flush=True)
    record = {"sid": SID, "job_id": job_id}
    try:
        report, artifacts = W.run_job(REMOTE, OUTROOT, request, job_id,
                                      lambda m: print(m, flush=True))
        config = report["config"]
        record["regions"] = config["regions"]
        record["candidate_kind"] = config["auto_candidate"]["kind"]
        record["candidate_roi"] = config["auto_candidate"].get("roi")
        record["recommended"] = report["recommended"]
        record["artifacts"] = list(artifacts)
        record["estimators"] = {n: {"valid": a["valid"], "reject_reasons": a["reject_reasons"],
                                    "full": {k: a["full"][k] for k in ("count", "rms_m", "p95_m", "support_ratio")
                                             } if a.get("full") else None}
                                for n, a in report["estimators"].items()}
        record["artifact_dirs"] = sorted(p.name for p in (Path(OUTROOT) / job_id).iterdir())
        record["full_frame_files"] = {n: sorted(p.name for p in (Path(OUTROOT) / job_id / n).iterdir())
                                      for n in artifacts}
    except Exception as exc:
        record["error"] = str(exc)
    record["seconds"] = round(time.monotonic() - began, 2)
    n, target = 3, OUT / "07_run_job_223757.json"
    while target.exists():
        target = OUT / ("07_run_job_223757_r%d.json" % n)
        n += 1
    W.dump(target, record)
    print(json.dumps(record, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
