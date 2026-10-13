"""Verify corrected DOI and an upstream classifier at the already frozen commit."""
import hashlib
import json
import urllib.request
from pathlib import Path

out = Path(__file__).resolve().parent / "research"
requests = [
    ("crossref_10.3390_s23104720_verified.json", "https://api.crossref.org/works/10.3390%2Fs23104720"),
    ("koide3__hdl_people_tracking/src/kidono_human_classifier.cpp", "https://raw.githubusercontent.com/koide3/hdl_people_tracking/2d125167ca2b0935b8075032b943edf11d996788/src/kidono_human_classifier.cpp"),
]
rows = []
for name, url in requests:
    path = out / name
    if path.exists():
        body = path.read_bytes()
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "HUMAN-FUSION-read-only-research/1.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            body = response.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(body)
    row = {"path": name, "url": url, "sha256": hashlib.sha256(body).hexdigest()}
    if name.endswith(".json"):
        row["title"] = json.loads(body)["message"]["title"]
    rows.append(row)
    print(row)
rows.append({"excluded_doi": "10.3390/s23104781", "reason": "Initial DOI guess resolves to unrelated transformer-fault article. Preserved raw lookup but excluded from report citations."})
with (out / "supplement_manifest.json").open("x", encoding="utf-8") as handle:
    json.dump(rows, handle, ensure_ascii=False, indent=2)
