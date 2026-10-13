"""Freeze only audit dependencies into a new local workspace, without touching originals."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
LAB=ROOT/"sidequests/human_fusion_lab"
SNAP=OUT/"workspace"
assert not SNAP.exists()
files=[*LAB.glob("core/*.js"),*LAB.glob("human_replay/*.js"),*LAB.glob("human_replay/*.json"),
       LAB/"detector.js",LAB/"export.js",LAB/"unique_tracker.js",LAB/"results/AUDIT.json",LAB/"models/xgb69_candidate.json"]
manifest={}
for p in files:
    q=SNAP/p.relative_to(LAB)
    q.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(p,q)
    manifest[str(p.relative_to(ROOT)).replace("\\","/")]={"snapshot":str(q.relative_to(OUT)),"sha256":hashlib.sha256(q.read_bytes()).hexdigest()}
with (OUT/"snapshot_manifest.json").open("x",encoding="utf-8") as f:json.dump(manifest,f,indent=2)
print("frozen",len(manifest),"dependencies")
