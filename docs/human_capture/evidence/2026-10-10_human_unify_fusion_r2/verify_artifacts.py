"""Final source, model and complete-run verification; no source/GT writes."""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    with p.open(encoding="utf-8") as f:
        return json.load(f)


summary = read(HERE / "runs_03/SUMMARY.json")
for name, value in summary["source_sha256"].items():
    assert sha(ROOT / name) == value, name + " changed since runs"
for name, value in read(HERE / "SUBMITTED_SOURCE_SHA.json").items():
    assert sha(ROOT / name) == value, name + " changed since submission"
before = read(HERE / "before.json")
for name in ("pc_apps/human_ml/frame_feature.py", "pc_apps/human_replay/rf_person.js", "pc_apps/human_replay/rf_person_v1.json"):
    assert sha(ROOT / name) == before["files"][name], name + " frozen contract changed"
assert len(summary["runs"]) == 72
for r in summary["runs"]:
    p = HERE / "runs_03" / r["sid"] / (r["version"] + "__" + r["mode"] + ".json")
    data = read(p)
    meta = read(ROOT / "captures/remote" / r["sid"] / "meta.json")
    assert len(data["frames"]) == len(meta["frames"]) == r["frames"]
    assert [f["frame_index"] for f in data["frames"]] == list(range(r["frames"]))
    assert data["source_sha256"] == summary["source_sha256"]
for p in (HERE / "runs_03/gt_snapshot").glob("*/GT_*.json"):
    m = read(p.parent / "manifest.json")
    v = [v for v in m["versions"] if v["annotator"] != "e2e"][-1]
    assert sha(p) == v["sha256"]
files = list((HERE / "train_02").rglob("*")) + list((HERE / "runs_03").rglob("*"))
manifest = {str(p.relative_to(HERE)).replace("\\", "/"): sha(p) for p in sorted(files) if p.is_file()}
with (HERE / "ARTIFACT_MANIFEST.json").open("x", encoding="utf-8") as f:
    json.dump(manifest, f, indent=1)
print("VERIFIED", len(summary["runs"]), "complete runs", len(manifest), "immutable artifacts; frozen v1 contract unchanged")
