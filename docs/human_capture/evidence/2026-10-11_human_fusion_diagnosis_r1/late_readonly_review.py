"""Read-only review of concurrently published V3; no training, replay or source edits."""
import hashlib
import json
import shutil
from pathlib import Path
import numpy as np
import onnxruntime as ort

out = Path(__file__).resolve().parent
root = out.parents[3]
lab = root / "sidequests/human_fusion_lab"
v3 = root / "docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1"
copy_root = out / "late_snapshot"
copy_root.mkdir(exist_ok=False)
manifest = {}

def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def freeze(path):
    path = Path(path)
    rel = path.relative_to(root)
    dest = copy_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    before = digest(path)
    shutil.copy2(path, dest)
    after = digest(path)
    assert before == after == digest(dest), "Concurrent input mutation: " + str(rel)
    manifest[str(rel)] = {"sha256": before, "snapshot": str(dest.relative_to(out))}
    return dest

def read(path):
    return json.loads(freeze(path).read_text(encoding="utf-8"))

bg = read(v3 / "BG_GROUPS_EVAL.json")
cc = read(v3 / "CONTROLLED_COMPARISON.json")
attr = read(v3 / "LAYER_ATTRIBUTION_cap_20261010_180235_f91_128_B.json")
cand = read(v3 / "CANDIDATE_IMPROVE_S6.json")
read(v3 / "TRAIN_BG_REPORT.json")
read(v3 / "S9_GT_REPAIR.json")
for rel in [
    "sidequests/human_fusion_lab_v3/core/bg_groups.js",
    "sidequests/human_fusion_lab_v3/v3_runtime.js",
    "sidequests/human_fusion_lab_v3/tools/eval_bg_groups.js",
    "sidequests/human_fusion_lab_v3/tools/eval_controlled_comparison.py",
    "sidequests/human_fusion_lab_v3/tools/export_bg_candidates.js",
    "sidequests/human_fusion_lab_v3/tools/layer_attribution.js",
    "sidequests/human_fusion_lab_v3/tools/candidate_improve_s6.js",
    "sidequests/human_fusion_lab_v3/README.md",
    "docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/REPORT_FINAL.md",
    "docs/human_capture/evidence/2026-10-11_cc_mainline_r1/02_SKELETON_STATE_AND_ADAPT.md",
    "docs/human_capture/evidence/2026-10-11_cc_mainline_r1/03_SUMMARY.md",
    "sidequests/human_fusion_lab/run_skeleton_adapt.js",
    "sidequests/human_fusion_lab/render_skeleton_coarse.js",
    "sidequests/human_fusion_lab/train.py",
]:
    freeze(root / rel)

audit = read(lab / "results/AUDIT.json")
rows = []
for sid in sum(audit["splits"].values(), []):
    path = lab / "results" / (sid + ".jsonl")
    if path.exists():
        copied = freeze(path)
        rows.extend(json.loads(line) for line in copied.read_text(encoding="utf-8").splitlines() if line.strip())
known = [r for r in rows if r["label"] is not None]
model_path = freeze(lab / "models/pointnet_shadow.onnx")
opt = ort.SessionOptions()
opt.intra_op_num_threads = 4
opt.inter_op_num_threads = 1
sess = ort.InferenceSession(str(model_path), sess_options=opt, providers=["CPUExecutionProvider"])
cloud = np.asarray([r["points"] for r in known], dtype=np.float32)

def predict(cloud):
    batches = []
    for start in range(0, len(cloud), 64):
        x = cloud[start:start + 64].transpose(0, 2, 1).copy()
        logits = sess.run(["logit"], {"points": x})[0].reshape(-1)
        batches.append(1 / (1 + np.exp(-logits)))
    return np.concatenate(batches)

def metric(labels, probabilities, threshold=0.55):
    y = np.asarray(labels)
    pred = np.asarray(probabilities) >= threshold
    return {"tp": int((pred & (y == 1)).sum()), "fp": int((pred & (y == 0)).sum()),
            "fn": int((~pred & (y == 1)).sum()), "tn": int((~pred & (y == 0)).sum())}

uncentered = predict(cloud)
centered = predict(cloud - cloud.mean(axis=1, keepdims=True))
pointnet = {}
for split, sids in audit["splits"].items():
    ix = [i for i, r in enumerate(known) if r["sid"] in sids]
    if not ix:
        continue
    pointnet[split] = {"n": len(ix), "uncentered_v3": metric([known[i]["label"] for i in ix], uncentered[ix]),
                      "centered_training_contract": metric([known[i]["label"] for i in ix], centered[ix])}
    expected = cc["splits"][split]["models"]["pointnet_shadow"]
    assert pointnet[split]["uncentered_v3"] == {k: expected[k] for k in ["tp", "fp", "fn", "tn"]}

b_rows = [json.loads(line) for line in freeze(v3 / "cap_20261010_175227_bg.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
xgb = read(lab / "models/xgb69_candidate.json")

def tree(t, x):
    while "leaf" not in t:
        ix = int(t["split"].lstrip("f"))
        nxt = t["missing"] if not np.isfinite(x[ix]) else (t["yes"] if x[ix] < np.float32(t["split_condition"]) else t["no"])
        t = next(c for c in t["children"] if c["nodeid"] == nxt)
    return t["leaf"]

neg = [r for r in b_rows if r["label"] == 0]
probs = []
for r in neg:
    x = np.asarray(r["features"] + r["extended"], dtype=np.float32)
    margin = xgb["base_margin"] + sum(tree(t, x) for t in xgb["trees"])
    probs.append(1 / (1 + np.exp(-margin)))
b_score = metric([0] * len(neg), probs)
expected = cc["xgb_b_group_furniture_falsification"]["xgb_on_B_S1_furniture"]
assert b_score["fp"] == expected["fp"] and b_score["tn"] == expected["tn"]

original = json.loads((out / "historical_v2_recalculation.json").read_text(encoding="utf-8"))
current_summaries = []
for row in original["summaries"]:
    path = root / "docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1" / (row["sid"] + "__" + row["model"] + ".json")
    before = digest(path)
    current = json.loads(path.read_text(encoding="utf-8"))["summary"]
    assert before == digest(path)
    current_summaries.append({"path": str(path.relative_to(root)), "sha256": before,
        "summary": current, "candidate_counts_equal": row["candidate"] == current["candidate"],
        "track_counts_equal": row["track"] == current["track"]})

result = {"scope": "Late V3 source/artifact audit plus 859 fixed-row PointNet inference and 608 B-furniture XGB rescoring. No training or pipeline replay.",
    "background_actual": [{"sid": s["sid"], "groups": s["groups"]} for s in bg["sessions"]],
    "v3_layer_attribution": attr, "v3_candidate_result": cand, "pointnet_preprocessing_ab": pointnet,
    "b_furniture_xgb_rescore": {"n": len(neg), **b_score}, "current_v2_summaries": current_summaries,
    "limits": ["B furniture labels inherited same-session overlap GT; independent furniture generalization UNKNOWN.",
        "No new V3 detector integration, browser run or skeleton accuracy test.", "V3 report loss percentages do not imply downstream detection gains."]}
with (out / "late_review.json").open("x", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
with (out / "late_snapshot_manifest.json").open("x", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(json.dumps({"pointnet": pointnet, "B_xgb": b_score, "v2_count_drift": [r["path"] for r in current_summaries if not r["candidate_counts_equal"] or not r["track_counts_equal"]], "snapshots": len(manifest)}, ensure_ascii=False))
