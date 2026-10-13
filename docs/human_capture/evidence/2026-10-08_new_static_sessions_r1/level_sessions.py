"""Reuse unchanged offline leveling; all derivatives stay in this evidence round."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
import uuid

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "pc_apps/human_replay"))
import leveling as L

SIDS = ["cap_20261008_" + t for t in ("114819", "114205", "114254", "114340", "114422")]


def write(name, value):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def baseline():
    names = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT).decode().split("\0")
    files = {}
    for name in sorted(set(names) - {""}):
        p = ROOT / name
        if p.is_symlink():
            files[name] = {"symlink": str(p.readlink())}
        elif p.is_file():
            files[name] = {"sha256": L.sha(p), "size": p.stat().st_size}
        else:
            files[name] = {"missing": True}
    write("00_baseline.json", {
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT).decode().strip(),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT).decode(),
        "files": files, "inventory": "git tracked + untracked excluding ignored; captures inputs bound separately",
        "created": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "ponytail": "C:/Users/30680/.codex/skills/ponytail/SKILL.md",
        "field_report": {"furniture_and_lidar_moved": False, "human_sessions": "standing throughout"}})


if __name__ == "__main__":
    baseline()
    results = []
    for sid in SIDS:
        try:
            _, meta, binding = L.source(ROOT / "captures/remote", sid)
            req = L.validate_request({"schema": 1, "sid": sid, "source": binding,
                "config": {"pitch_deg": 26., "roll_deg": 0., "physical_height_m": 1.14, "mode": "auto"}})
            job = uuid.uuid4().hex
            print("START", sid, job, flush=True)
            report, artifacts = L.run_job(ROOT / "captures/remote", OUT / "leveling", req, job,
                lambda message: print(sid, message, flush=True))
            item = {"sid": sid, "name": meta.get("name"), "job": job, "source": binding,
                    "frames": len(meta["frames"]), "duration": meta["duration_sec"],
                    "recommended": report["recommended"], "consensus": report["consensus"],
                    "fit_point_count": report["fit_point_count"], "estimators": report["estimators"],
                    "pairwise": report["pairwise"], "artifacts": artifacts}
            write(sid + "_leveling.json", item)
            results.append(item)
            print("DONE", sid, report["recommended"], flush=True)
        except Exception as exc:
            traceback.print_exc()
            item = {"sid": sid, "error": str(exc)}
            write(sid + "_leveling_failure.json", item)
            results.append(item)
    write("leveling_results.json", results)
    assert all("error" not in r for r in results), "See preserved leveling failures"
