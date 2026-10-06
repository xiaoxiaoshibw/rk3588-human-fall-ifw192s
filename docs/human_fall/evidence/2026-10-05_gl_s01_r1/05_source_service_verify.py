"""GL-S01 addendum: verify the source-run console service path end to end.

Starts the same module the source console uses (`runpy` on
human_replay_lib.py, Handler on an ephemeral port) and exercises the real
validation HTTP routes: sessions -> saved-report restore -> auto run on
223757 -> classified failure. No packaged exe is touched; no 8901 conflict.
"""
import json
import runpy
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REPLAY = ROOT / "pc_apps" / "human_replay"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPLAY))


def request(port, method, path, body=None):
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main():
    module = runpy.run_path(str(REPLAY / "human_replay_lib.py"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), module["Handler"])
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    results = {"port": port, "checks": []}

    def check(name, ok, detail=""):
        results["checks"].append({"name": name, "pass": bool(ok), "detail": detail})
        print("%s %s | %s" % ("PASS" if ok else "FAIL", name, detail), flush=True)

    try:
        status, sessions = request(port, "GET", "/api/validation/sessions")
        sids = [row["sid"] for row in sessions["sessions"]]
        check("validation sessions route", status == 200 and len(sids) == 4
              and "cap_20261002_223757" in sids, str(sids))

        status, latest = request(port, "GET", "/api/validation/latest?sid=cap_20261004_203349")
        check("saved-report restore (203349)", status == 200 and latest.get("state") == "ready",
              "status=%s floor_identified=%s job=%s" % (status, latest.get("floor_identified"),
                                                        latest.get("job_id")))

        _, source = request(port, "GET", "/api/validation/source?sid=cap_20261002_223757")
        body = {"schema": 1, "sid": "cap_20261002_223757", "source": source["source"],
                "config": {"pitch_deg": 26., "roll_deg": 0., "physical_height_m": 1.14,
                           "mode": "auto"}}
        status, started = request(port, "POST", "/api/validation/run", body)
        check("auto run accepted via validation route", status == 202 and started.get("job_id"),
              str(started))

        job, began = None, time.time()
        while time.time() - began < 300:
            _, job = request(port, "GET", "/api/validation/job?id=%s&sid=cap_20261002_223757"
                             % started["job_id"])
            if job.get("state") != "running":
                break
            time.sleep(1.)
        error = (job or {}).get("error", "")
        check("223757 classified via source service",
              bool(job) and job.get("state") == "failed"
              and error.startswith("INSUFFICIENT_CLEAN_ROI_SUPPORT"),
              "state=%s error=%s" % ((job or {}).get("state"), error[:140]))
    finally:
        server.shutdown()
        server.server_close()
        (OUT / "07_source_service_verify.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    if not all(item["pass"] for item in results["checks"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
