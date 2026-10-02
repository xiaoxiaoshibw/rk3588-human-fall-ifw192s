"""Recompute the R7 pre-work manifest and report changed files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
before = json.loads((HERE / "00_before_manifest.json").read_text(encoding="utf-8"))

after = {}
for rel in sorted(before):
    path = ROOT / rel
    after[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

changed = sorted(rel for rel in before if after[rel] != before[rel])
(HERE / "20_after_manifest.json").write_text(
    json.dumps(after, indent=2, sort_keys=True) + "\n", encoding="utf-8")
lines = ["changed files ({}):".format(len(changed))]
for rel in changed:
    lines.append("  M {}".format(rel))
(HERE / "21_scope_diff.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
