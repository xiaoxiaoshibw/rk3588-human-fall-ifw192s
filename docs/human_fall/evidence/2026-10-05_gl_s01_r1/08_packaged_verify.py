"""GL-S01 packaged-exe verification (dist/gl_s01/Console.exe own service).

Talks to the HTTP service the packaged exe starts (same validation routes the
console page uses) and confirms v2 classification on 223757.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8901
OUTNAME = sys.argv[2] if len(sys.argv) > 2 else "09_packaged_verify.json"
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
        while time.time() - began < 300:
            _, job = request("GET", "/api/validation/job?id=%s&sid=cap_20261002_223757"
                             % started["job_id"])
            if job.get("state") != "running":
                break
            time.sleep(1.)
        error = (job or {}).get("error", "")
        check("packaged 223757 classification",
              bool(job) and job.get("state") == "failed"
              and error.startswith("INSUFFICIENT_CLEAN_ROI_SUPPORT"),
              "state=%s error=%s" % ((job or {}).get("state"), error[:140]))
    finally:
        (OUT / OUTNAME).write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    if not all(item["pass"] for item in results["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
