"""Verify the pre-dispatch tree, including untracked/ignored protected assets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "docs/human_capture/evidence/2026-10-11_hfus_integration_r1/BASELINE_BEFORE.json"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def check():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    changes, errors = [], []
    for row in baseline["files"]:
        path = ROOT / row["path"]
        try:
            same = (os.readlink(path) == row["symlink"] if "symlink" in row
                    else digest(path) == row["sha256"])
            if not same:
                changes.append(row["path"])
        except OSError as exc:
            errors.append({"path": row["path"], "error": str(exc)})
    # README is the only preexisting file authorized for this execution's writes.
    protected = [p for p in changes if p != "docs/human_capture/README.md"]
    old_paths = {row["path"] for row in baseline["files"]}
    new_paths = []
    for base, directories, names in os.walk(ROOT, followlinks=False):
        directories[:] = [d for d in directories if d != ".git"
                          and not (Path(base) / d).is_symlink()
                          and not os.path.isjunction(Path(base) / d)]
        new_paths.extend((Path(base) / name).relative_to(ROOT).as_posix()
                         for name in names
                         if (Path(base) / name).relative_to(ROOT).as_posix() not in old_paths)
    source_prefix = "sidequests/human_fusion_lab_next/"
    allowed_prefixes = tuple(source_prefix + name + "/"
                             for name in ("contracts", "eval", "review", "background", "integration"))
    allowed_prefixes += ("docs/human_capture/evidence/2026-10-11_hfus_",)
    allowed_files = {source_prefix + "README.md", source_prefix + "run.py"}
    for item in ("D01", "D02", "D03", "INTEGRATION"):
        allowed_files.add("docs/human_capture/HFUS_" + item + "_ACCEPTANCE_V1.md")
        allowed_files.add("docs/human_capture/returns/HFUS-" + item + ".md")
    unauthorized_new = [p for p in new_paths if p not in allowed_files
                        and not p.startswith(allowed_prefixes)]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    return {"baseline_sha256": digest(BASELINE), "checked_files": len(baseline["files"]),
            "changed_preexisting_paths": changes, "protected_changes": protected,
            "new_paths": sorted(new_paths), "unauthorized_new_paths": sorted(unauthorized_new),
            "errors": errors, "head": head, "branch": branch,
            "head_unchanged": head == baseline["head"],
            "branch_unchanged": branch == baseline["branch"],
            "status": "PASS" if not protected and not errors and not unauthorized_new and head == baseline["head"]
                      and branch == baseline["branch"] else "BLOCKED"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
