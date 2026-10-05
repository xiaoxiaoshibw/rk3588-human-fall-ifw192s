"""GL-E01 R1 independent manifest SHA, freeze and tracked/untracked scope check.

Verifies the submission manifest's own digest and every listed file hash against
disk, diffs the before/submitted baselines, and compares the current
tracked+untracked scope to the submitted baseline.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
ROOT = OUT.parents[4]
MANIFEST = RUN / "09_submission_manifest.json"
BEFORE = RUN / "00_before_baseline.json"
SUBMITTED = RUN / "10_submitted_baseline.json"
EXPLICIT = ["captures/remote/cap_20261002_163621/meta.json",
            "captures/remote/cap_20261002_163621/points.bin",
            "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot():
    paths = set(subprocess.check_output(
        ["git", "ls-files", "-c", "-o", "--exclude-standard", "-z"], cwd=ROOT
    ).decode("utf-8").split("\0")) - {""}
    paths.update(EXPLICIT)
    files = {}
    for rel in sorted(paths):
        p = ROOT / rel
        try:
            if p.is_symlink():
                files[rel] = {"symlink": os.readlink(p)}
            elif p.is_file():
                files[rel] = {"sha256": sha(p), "size": p.stat().st_size}
            else:
                files[rel] = {"missing_or_nonregular": True}
        except OSError as exc:
            st = p.lstat()
            files[rel] = {"unreadable_winerror": getattr(exc, "winerror", None),
                          "lstat_mode": st.st_mode, "size": st.st_size,
                          "attributes": getattr(st, "st_file_attributes", None)}
    return files


def key(d):
    if "sha256" in d:
        return "file:" + d["sha256"]
    if "symlink" in d:
        return "symlink:" + d["symlink"]
    return "other"


def main():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_sha = sha(MANIFEST)
    listed = {}
    for rel, declared in man["files"].items():
        p = ROOT / rel
        actual = sha(p) if p.is_file() else None
        listed[rel] = dict(declared=declared, actual=actual, match=declared == actual)

    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    submitted = json.loads(SUBMITTED.read_text(encoding="utf-8"))
    bf, sf = before["files"], submitted["files"]
    only_before = sorted(set(bf) - set(sf))
    only_sub = sorted(set(sf) - set(bf))
    changed = sorted(k for k in set(bf) & set(sf) if key(bf[k]) != key(sf[k]))

    current = snapshot()
    cur_only = sorted(set(current) - set(sf))
    sf_only = sorted(set(sf) - set(current))
    cur_changed = sorted(k for k in set(current) & set(sf)
                         if key(current[k]) != key(sf[k]))

    result = dict(
        kind="gle01_r1_independent_manifest_scope", schema=1,
        manifest_sha256=manifest_sha,
        manifest_head=man["head"], submitted_head=submitted["head"],
        before_head=before["head"], current_head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        manifest_files=len(man["files"]),
        manifest_all_listed_match=all(v["match"] for v in listed.values()),
        manifest_listed_mismatches=[k for k, v in listed.items() if not v["match"]],
        baseline_before_to_submitted=dict(only_in_before=only_before,
                                          only_in_submitted=only_sub,
                                          changed=changed),
        current_vs_submitted=dict(only_in_current=cur_only,
                                  only_in_submitted=sf_only,
                                  changed=cur_changed),
        current_file_count=len(current))
    (OUT / "06_manifest_scope_check.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(dict(manifest_sha=manifest_sha[:16],
                          listed_match=result["manifest_all_listed_match"],
                          mismatches=result["manifest_listed_mismatches"],
                          before_to_sub_added=len(only_sub),
                          before_to_sub_removed=len(only_before),
                          before_to_sub_changed=len(changed),
                          current_vs_sub_added=len(cur_only),
                          current_vs_sub_removed=len(sf_only),
                          current_vs_sub_changed=len(cur_changed),
                          heads=[result["before_head"][:9],
                                 result["submitted_head"][:9],
                                 result["current_head"][:9]])))


if __name__ == "__main__":
    main()
