"""A07 删除执行（用户确认后）：只删 captures/remote/<sid> 未配平副本，留证。

用法：
    python -B -W error apply_deletion.py --out <evidence_dir> cap_..._164522 cap_..._094302
前置：10_DELETION_CANDIDATES.json 中该 sid recommendation=delete_candidate；
删除前记录目录清单/大小/SHA，删除后复核 captures/leveled 产物仍在。
"""
import argparse
import json
import shutil
import time
from pathlib import Path

from common import LEVELED, REMOTE, sha256_file

JOBS = {"cap_20261014_164522": "363473a9e2e64649994dca11b2b26929",
        "cap_20261013_094302": "53bfb3ca7bdc44b3b04084da998d7c65"}


def snapshot(sid):
    directory = REMOTE / sid
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            files[path.relative_to(directory).as_posix()] = path.stat().st_size
    return {"sid": sid, "path": str(directory), "files": files,
            "bytes_total": sum(files.values()),
            "meta_sha256": sha256_file(directory / "meta.json") if "meta.json" in files else None,
            "points_sha256": sha256_file(directory / "points.bin") if "points.bin" in files else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--candidates", required=True, help="10_DELETION_CANDIDATES.json path")
    parser.add_argument("sids", nargs="+")
    parser.add_argument("--confirmation", default="user confirmed in session (question tool): 按建议删 2 段")
    args = parser.parse_args()
    out = Path(args.out)
    candidates = json.loads(Path(args.candidates).read_text(encoding="utf8"))
    allowed = {row["sid"]: row for row in candidates["candidates"]
               if row["recommendation"] == "delete_candidate"}
    for sid in args.sids:
        if sid not in allowed:
            raise ValueError(sid + ": not a delete_candidate in " + args.candidates)
    before_remote = sorted(p.name for p in REMOTE.iterdir() if p.is_dir())
    pre = [snapshot(sid) for sid in args.sids]
    deleted = []
    for sid in args.sids:
        directory = REMOTE / sid
        shutil.rmtree(directory)
        deleted.append({"sid": sid, "removed": not directory.exists(), "at_unix": time.time()})
    after_remote = sorted(p.name for p in REMOTE.iterdir() if p.is_dir())
    jobs_state = {}
    for sid in args.sids:
        job = JOBS[sid]
        manifest = json.loads((LEVELED / job / "manifest.json").read_text(encoding="utf8"))
        jobs_state[sid] = {"job_id": job, "still_present": (LEVELED / job).is_dir(),
                           "artifacts": sorted((manifest.get("artifacts") or {}).keys()),
                           "report_sha256": manifest.get("report_sha256")}
    payload = {"confirmation": args.confirmation, "policy": candidates["rule"],
               "pre_delete": pre, "deleted": deleted,
               "remote_before_count": len(before_remote), "remote_after_count": len(after_remote),
               "remote_before": before_remote, "remote_after": after_remote,
               "leveled_kept": jobs_state,
               "leveled_jobs_on_disk": sorted(p.name for p in LEVELED.iterdir() if p.is_dir())}
    with (out / "11_DELETION_EXECUTED.json").open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"deleted": [d["sid"] for d in deleted],
                      "remote_before": len(before_remote), "remote_after": len(after_remote),
                      "leveled_kept": {k: v["still_present"] for k, v in jobs_state.items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
