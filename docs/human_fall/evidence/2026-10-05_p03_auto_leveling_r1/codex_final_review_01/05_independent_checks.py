"""Read-only P03 scope gate. Does not execute archived code or write source/data."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
SUBMISSION = HERE.parent
GLW = ROOT / "docs/human_fall/evidence/2026-10-05_gl_w01_r1"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    return {"command": ["git", *args], "exit_code": result.returncode,
            "stdout": result.stdout.decode("utf-8", "replace"),
            "stderr": result.stderr.decode("utf-8", "replace")}


def snapshot(stage):
    listed = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    assert listed["exit_code"] == 0, listed
    files = {}
    for name in sorted(set(listed["stdout"].split("\0")) - {""}):
        path = ROOT / name
        if path.is_relative_to(HERE):
            continue
        try:
            if path.is_symlink():
                files[name] = {"symlink": str(path.readlink())}
            elif path.is_file():
                files[name] = {"sha256": sha(path), "bytes": path.stat().st_size}
            else:
                files[name] = {"state": "missing_or_nonregular"}
        except OSError as exc:
            files[name] = {"error": type(exc).__name__ + ": " + str(exc)}
    # Explicit ignored executable and original inputs, absent from git ls-files.
    extra = [ROOT / "pc_apps/console/dist/Console.exe"]
    extra += list((ROOT / "captures/remote").glob("*/meta.json"))
    extra += list((ROOT / "captures/remote").glob("*/points.bin"))
    for path in extra:
        if path.is_file():
            files[path.relative_to(ROOT).as_posix()] = {
                "sha256": sha(path), "bytes": path.stat().st_size}
    expected = json.loads((SUBMISSION / "13_SHA.txt").read_text("utf-8-sig"))
    comparison = {name: {"expected": value, "actual": sha(ROOT / name),
                         "match": value == sha(ROOT / name)}
                  for name, value in expected.items()}
    document = {"stage": stage, "time_utc": datetime.now(timezone.utc).isoformat(),
                "branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
                "submission_sha_comparison": comparison, "files": files}
    if stage == "after":
        before = json.loads((HERE / "01_sha_before.txt").read_text("utf-8"))
        document["changed_files"] = [name for name in sorted(set(files) | set(before["files"]))
                                     if files.get(name) != before["files"].get(name)]
    filename = "01_sha_before.txt" if stage == "before" else "02_sha_after.txt"
    with (HERE / filename).open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"stage": stage, "files": len(files),
                      "submission_sha_all_match": all(c["match"] for c in comparison.values()),
                      "changed_files": document.get("changed_files")}, ensure_ascii=False))


def boundary():
    frozen = json.loads((GLW / "25_archive_runtime_final.json").read_text("utf-8"))
    executable = ROOT / "pc_apps/console/dist/Console.exe"
    diagnostic = GLW / "Console_diagnostic.exe"
    live_archive = CArchiveReader(str(executable))
    old_archive = CArchiveReader(str(diagnostic))
    old_hashes = json.loads((GLW / "22_final_source_sha.json").read_text("utf-8"))["source_sha256"]
    comparisons = {}
    for name in ("leveling.py", "leveling.js", "leveling.html", "replay.js"):
        key = "human_replay\\" + name
        live = live_archive.extract(key)
        old = old_archive.extract(key)
        source_name = "pc_apps/human_replay/" + name
        comparisons[name] = {"live_embedded_sha256": hashlib.sha256(live).hexdigest(),
                             "current_source_sha256": sha(ROOT / source_name),
                             "diagnostic_embedded_sha256": hashlib.sha256(old).hexdigest(),
                             "glw_source_sha256": old_hashes.get(source_name),
                             "live_embedded_equals_source": live == (ROOT / source_name).read_bytes(),
                             "live_embedded_equals_diagnostic": live == old}
    protected = {}
    for name, entry in live_archive.toc.items():
        if name.startswith("human_replay\\") and name in old_archive.toc:
            leaf = name.split("\\", 1)[1]
            if leaf not in {"leveling.py", "leveling.js", "leveling.html", "leveling_test.py",
                            "replay.js", "LEVELING_README.md"}:
                protected[name] = live_archive.extract(name) == old_archive.extract(name)
    document = {"scope_gate": "FAIL", "reason": "console exe repacked with P03 source",
                "previous_exe_sha256": frozen["exe_sha256"], "previous_bytes": frozen["bytes"],
                "current_exe_sha256": sha(executable), "current_bytes": executable.stat().st_size,
                "current_exe_mtime_ns": executable.stat().st_mtime_ns,
                "embedded_source_comparisons": comparisons,
                "protected_archive_members_unchanged": protected,
                "attribution": "repack actor and authorization not established by this evidence",
                "gate_rule": "user final-review prompt section 1.2: REWORK, do not run per-ID checks"}
    assert document["current_exe_sha256"] != document["previous_exe_sha256"]
    assert comparisons["leveling.py"]["live_embedded_equals_source"]
    assert not comparisons["leveling.py"]["live_embedded_equals_diagnostic"]
    with (HERE / "07_boundary_checks.json").open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
    print(json.dumps(document, ensure_ascii=False, indent=2))
    # Exit 1 deliberately signifies the mandatory scope-gate failure.
    return 1


if __name__ == "__main__":
    if sys.argv[1] in ("before", "after"):
        snapshot(sys.argv[1])
    else:
        sys.exit(boundary())
