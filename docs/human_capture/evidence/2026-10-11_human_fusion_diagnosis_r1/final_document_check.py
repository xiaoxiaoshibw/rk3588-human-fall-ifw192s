"""Check completed deliverable links and frozen evidence; no new model inference."""
import hashlib
import json
import re
from pathlib import Path

out = Path(__file__).resolve().parent
root = out.parents[3]
docs = [out / n for n in ["REPORT.md", "CLAUDE_TASKBOOK.md", "RESEARCH_NOTES.md", "INTEGRITY.md", "00_SCOPE.md"]]
docs.append(root / "docs/human_capture/returns/HUMAN-FUSION-DIAG.md")
missing = []
links = 0
for doc in docs:
    for target in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "#")):
            continue
        path = re.sub(r":\d+$", "", target)
        path = Path(path) if re.match(r"^[A-Z]:/", path) else doc.parent / path
        links += 1
        if not path.exists():
            missing.append({"document": str(doc), "target": target})
copies = []
for name in ["snapshot_manifest.json", "late_snapshot_manifest.json"]:
    for source, row in json.loads((out / name).read_text(encoding="utf-8")).items():
        p = out / row["snapshot"]
        with p.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        copies.append({"manifest": name, "path": row["snapshot"], "unchanged": actual == row["sha256"]})
result = {"links_checked": links, "missing_local_links": missing, "copies_checked": len(copies),
          "changed_copies": [c for c in copies if not c["unchanged"]],
          "acceptance_sha256": hashlib.sha256((out / "ACCEPTANCE.md").read_bytes()).hexdigest(),
          "report_sha256": hashlib.sha256((out / "REPORT.md").read_bytes()).hexdigest(),
          "limits": "Completed-document and snapshot integrity only. Whole live tree drift already recorded BLOCKED."}
with (out / "final_document_check.json").open("x", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False))
assert not missing and not result["changed_copies"]
