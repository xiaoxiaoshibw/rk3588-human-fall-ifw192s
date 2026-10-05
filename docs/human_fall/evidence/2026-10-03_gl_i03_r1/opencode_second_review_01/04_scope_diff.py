"""Independent scope check: diff snapshot manifests and current tree."""
import hashlib
import json
from pathlib import Path

ROOT = Path(r"D:\Code\ldiar")
EV = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i03_r1"


def load(name):
    return json.loads((EV / name).read_text(encoding="utf-8"))


def files(manifest):
    return manifest.get("files", {})


def diff(old, new):
    changed, added, removed = [], [], []
    for path, meta in new.items():
        if path not in old:
            added.append(path)
        elif meta.get("sha256") != old[path].get("sha256") or meta.get("missing_or_nonregular") != old[path].get("missing_or_nonregular"):
            changed.append(path)
    for path in old:
        if path not in new:
            removed.append(path)
    return changed, added, removed


pairs = [
    ("18_codex_before_manifest.json", "26_codex_after_manifest.json"),
    ("18_codex_before_manifest.json", "28_before_second_review_manifest.json"),
]
report = {}
for old_name, new_name in pairs:
    old, new = files(load(old_name)), files(load(new_name))
    changed, added, removed = diff(old, new)
    report[old_name + " -> " + new_name] = {
        "changed": changed, "added": added, "removed": removed}

# Current tree vs after-implementation snapshot (drift during review).
snap = files(load("28_before_second_review_manifest.json"))
drift = []
for path, meta in snap.items():
    ref = ROOT / path
    if meta.get("missing_or_nonregular"):
        continue
    try:
        data = ref.read_bytes()
    except OSError as exc:
        drift.append((path, "unreadable:" + str(exc)[:40]))
        continue
    digest = hashlib.sha256(data).hexdigest()
    if digest != meta.get("sha256"):
        drift.append((path, "changed"))
report["current_vs_28_drift"] = drift
print(json.dumps(report, indent=2))
