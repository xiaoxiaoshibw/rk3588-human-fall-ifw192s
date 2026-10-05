"""Independent baseline BEFORE/AFTER and frozen-anchor check (read-only)."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(r"D:/Code/ldiar")
RUN = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1"
start = json.loads((RUN / "03_start_baseline.json").read_text(encoding="utf-8"))
end = json.loads((RUN / "23_submission_baseline.json").read_text(encoding="utf-8"))
new_source = [
    "src/human_fall_detection/core/ground_diagnostics.py",
    "src/human_fall_detection/scripts/diagnose_gli04_geometry.py",
    "src/human_fall_detection/tests/test_gli04_geometry.py",
]
anchors = {
    "src/human_fall_detection/scripts/evaluate_gli02_candidate.py": "fddeeee0b4c6e014b608b64d8805b90997977b0e6eee357d6cc28f02726322c8",
    "src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml": "16c9d983c0202bb122be300db6faf70e7415300756392569acafa7d444cd49aa",
    "src/human_fall_detection/tests/test_gli03_candidate_override.py": "6433fa21200d1cbae0236c3701e31a5ec7b96d6d34549279909cacb6d948eccb",
    "src/human_fall_detection/core/ground.py": "2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3",
    "src/human_fall_detection/core/calibration.py": "d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3",
    "src/human_fall_detection/core/capture_input.py": "56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16",
    "captures/remote/cap_20261002_163621/meta.json": "675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692",
    "captures/remote/cap_20261002_163621/points.bin": "b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff",
}


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


changes = {p: {"start": start["files"].get(p), "end": end["files"].get(p)}
           for p in set(start["files"]) | set(end["files"])
           if start["files"].get(p) != end["files"].get(p)}
protected_prefixes = ("src/human_fall_detection/", "src/inno_", "webui/", "config/", "captures/",
                      "docs/human_fall/evidence/2026-10-03_gl_i02_r1/",
                      "docs/human_fall/evidence/2026-10-03_gl_i03_r1/")
protected_changed = [p for p in changes if p.startswith(protected_prefixes)
                    and p in start["files"] and p not in new_source]

# current post-submission drift vs end baseline for protected paths
drift = []
for rel, val in end["files"].items():
    if not rel.startswith(protected_prefixes):
        continue
    p = ROOT / rel
    now = {"symlink": str(p.resolve())} if p.is_symlink() else ({"sha256": sha(rel), "size": p.stat().st_size}
                                                                if p.is_file() else {"missing": True})
    if val != now:
        drift.append(rel)

tracked = set(subprocess.check_output(
    ["git", "ls-files", "-c", "-o", "--exclude-standard"], cwd=ROOT, text=True).splitlines())
out = {
    "head_start": start["head"], "head_end": end["head"],
    "start_files": len(start["files"]), "end_files": len(end["files"]),
    "new_source_absent_start": [p for p in new_source if p not in start["files"]],
    "new_source_present_end": [p for p in new_source if p in end["files"]],
    "changed_entries_total": len(changes),
    "protected_changed": protected_changed,
    "changes_sample": sorted(changes)[:15],
    "anchors_match": {p: sha(p) == v for p, v in anchors.items()},
    "post_submission_protected_drift": drift,
    "new_source_current_sha": {p: sha(p) for p in new_source},
}
out["ok"] = (out["head_start"] == out["head_end"] == "cbd0be1c86a1051a9a5800dfb7263f842896e1e6"
             and len(out["new_source_absent_start"]) == 3 and len(out["new_source_present_end"]) == 3
             and not protected_changed and all(out["anchors_match"].values()) and not drift)
print(json.dumps(out, indent=2))
print("\nALL_OK:", out["ok"])
