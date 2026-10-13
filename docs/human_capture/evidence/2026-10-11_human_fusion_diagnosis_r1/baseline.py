"""Read-only Git inventory; output is confined to this new evidence directory."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent

def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])

def digest(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def inventory():
    paths = sorted(set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode("utf-8").split("\0")) - {""})
    rows = {}
    for rel in paths:
        p = ROOT / rel
        if OUT in p.parents:
            continue
        try:
            if p.is_file():
                before = p.stat()
                sha = digest(p)
                after = p.stat()
                rows[rel] = {"sha256": sha, "bytes": after.st_size, "mtime_ns": after.st_mtime_ns,
                             "stable_during_read": (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)}
            else:
                rows[rel] = {"missing_or_nonregular": True}
        except OSError as e:
            rows[rel] = {"error": str(e)}
    return {"utc": datetime.now(timezone.utc).isoformat(), "branch": git("branch", "--show-current").decode().strip(),
            "head": git("rev-parse", "HEAD").decode().strip(), "scope": "Git tracked plus nonignored untracked; ignored audit inputs separately hashed", "files": rows}

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "before"
    assert mode in ("before", "after")
    result = inventory()
    dest = OUT / ("baseline_" + mode + ".json")
    assert not dest.exists(), "Evidence is append-only; choose a new round"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / ("git_status_" + mode + ".txt")).write_bytes(git("status", "--short", "--untracked-files=all"))
    print(json.dumps({"mode": mode, "branch": result["branch"], "head": result["head"], "entries": len(result["files"]),
                      "unstable": [k for k, v in result["files"].items() if v.get("stable_during_read") is False]}))
    if mode == "after":
        old = json.loads((OUT / "baseline_before.json").read_text(encoding="utf-8"))
        changed = [k for k, v in old["files"].items() if result["files"].get(k) != v]
        content_changed = [k for k in changed if old["files"][k].get("sha256") != result["files"].get(k, {}).get("sha256")]
        delta = {"content_changed": content_changed, "metadata_only_changed": sorted(set(changed) - set(content_changed)),
                 "new_external_paths": sorted(set(result["files"]) - set(old["files"])), "head_changed": old["head"] != result["head"]}
        (OUT / "baseline_delta.json").write_text(json.dumps(delta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(delta, ensure_ascii=False))
