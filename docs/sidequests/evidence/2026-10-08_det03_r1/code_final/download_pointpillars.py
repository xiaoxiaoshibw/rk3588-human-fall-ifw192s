"""Download an immutable upstream inference implementation and its own checkpoint."""
import hashlib
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parent / "artifacts" / "upstream"
root.mkdir(parents=True, exist_ok=True)
commit = "620e6b0d07e4cb37b7b0114f26b934e8be92a0ba"
records = []
for name in ("pointpillars/model/pointpillars.py", "pointpillars/model/anchors.py",
             "pretrained/epoch_160.pth", "pointpillars/dataset/demo_data/val/000134.bin", "LICENSE"):
    url = "https://raw.githubusercontent.com/zhulf0804/PointPillars/" + commit + "/" + name
    target = root / Path(name).name
    if target.exists():
        raise FileExistsError(target)
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read()
    target.write_bytes(data)
    records.append({"url": url, "file": target.name, "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest()})
    print(target.name, len(data), flush=True)
(root / "provenance.json").write_text(json.dumps({"commit": commit, "files": records}, indent=2), encoding="utf-8")
