"""Bounded OpenCode default DB probe + read-only independent review."""
import datetime
import json
import pathlib
import subprocess
import time

HERE = pathlib.Path(__file__).parent
CLI = r"C:\Users\30680\AppData\Roaming\npm\opencode.cmd"
MODEL = "opencode-go/deepseek-v4.1-flash"


def call(name, prompt, timeout):
    start = time.monotonic()
    result = {"model": MODEL, "agent": "plan", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (HERE / (name + ".jsonl")).open("x", encoding="utf-8") as log:
        p = subprocess.Popen([CLI, "run", "--agent", "plan", "-m", MODEL, "--format", "json", prompt],
                             stdout=log, stderr=subprocess.STDOUT)
        try:
            result["exit"] = p.wait(timeout=timeout)
            result["timeout"] = False
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], stdout=log, stderr=subprocess.STDOUT, check=False)
            result["exit"] = p.wait()
            result["timeout"] = True
    result["elapsed_seconds"] = time.monotonic() - start
    with (HERE / (name + "_status.json")).open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(name, result, flush=True)
    return result


probe = call("review_probe_01", "Reply PROBE_OK only. Do not use any tools.", 55)
if probe["exit"] or probe["timeout"] or "PROBE_OK" not in (HERE / "review_probe_01.jsonl").read_text(encoding="utf-8"):
    raise SystemExit("Q01 service probe BLOCKED")
call("opencode_review_01", (HERE / "opencode_review_prompt_01.md").read_text(encoding="utf-8"), 600)
