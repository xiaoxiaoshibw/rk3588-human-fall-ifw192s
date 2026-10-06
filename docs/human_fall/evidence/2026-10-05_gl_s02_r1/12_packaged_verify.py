"""GL-S02 packaged-exe verification (dist/Console.exe own service).

Same routes as GL-S01 08_packaged_verify.py, but the v3 expectation on 223757
is SUCCESS (state ready, three methods valid, recommended=tls), not a failure.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
OUTNAME = sys.argv[2] if len(sys.argv) > 2 else "13_packaged_verify.json"
OUT = Path(__file__).resolve().parent


def request(method, path, body=None):
    url = "http://127.0.0.1:%d%s" % (PORT, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    results = {"port": PORT, "checks": []}

    def check(name, ok, detail=""):
        results["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
        print("%s %s | %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)

    try:
        status, sessions = request("GET", "/api/validation/sessions")
        sids = [row["sid"] for row in sessions["sessions"]]
        check("packaged validation sessions", status == 200 and len(sids) == 4
              and "cap_20261002_223757" in sids, str(sids))

        _, source = request("GET", "/api/validation/source?sid=cap_20261002_223757")
        body = {"schema": 1, "sid": "cap_20261002_223757", "source": source["source"],
                "config": {"pitch_deg": 26., "roll_deg": 0., "physical_height_m": 1.14,
                           "mode": "auto"}}
        status, started = request("POST", "/api/validation/run", body)
        check("packaged auto run accepted", status == 202 and started.get("job_id"), str(started))

        job, began = None, time.time()
        while time.time() - began < 600:
            _, job = request("GET", "/api/validation/job?id=%s&sid=cap_20261002_223757"
                             % started["job_id"])
            if job.get("state") != "running":
                break
            time.sleep(2.)
        job = job or {}
        report = job.get("report") or {}
        estimators = report.get("estimators", {})
        candidate = (report.get("config") or {}).get("auto_candidate", {})
        check("packaged 223757 v3 success",
              job.get("state") == "ready"
              and candidate.get("kind") == "lowest_floor_sheet_v3_fine_roi"
              and report.get("recommended") == "tls"
              and all(e.get("valid") for e in estimators.values()),
              "state=%s kind=%s recommended=%s estimators=%s"
              % (job.get("state"), candidate.get("kind"), report.get("recommended"),
                 {n: e.get("valid") for n, e in estimators.items()}))
    finally:
        (OUT / OUTNAME).write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    if not all(item["pass"] for item in results["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
