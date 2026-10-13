# -*- coding: utf-8 -*-
"""write_manifest.py — 给 spike evidence 与 spike 代码生成 SHA manifest."""
import codecs
import hashlib
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
EV = os.path.join(REPO, "docs", "human_capture", "evidence", "2026-10-10_spike_cluster_r1")
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))


def sha(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest = {
        "purpose": "CLUSTER-ADAPTIVE-SPIKE-R1 input+output manifest (one-shot SHA registry)",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_outputs": {},
        "spike_source_code": {},
        "production_inputs_unchanged": {},
        "audit_related": {},
    }

    for fn in sorted(os.listdir(EV)):
        fp = os.path.join(EV, fn)
        if os.path.isfile(fp):
            manifest["evidence_outputs"][fn] = {"sha256": sha(fp), "bytes": os.path.getsize(fp)}

    for fn in sorted(os.listdir(SPIKE_DIR)):
        fp = os.path.join(SPIKE_DIR, fn)
        if os.path.isfile(fp):
            manifest["spike_source_code"][fn] = {"sha256": sha(fp),
                                                  "bytes": os.path.getsize(fp),
                                                  "rel": os.path.relpath(fp, REPO).replace("\\", "/")}

    for fp_rel in ("pc_apps/human_replay/detect_overlay.js",
                    "pc_apps/human_replay/rf_person.js",
                    "pc_apps/human_replay/bg_envelope.json",
                    "pc_apps/human_replay/human_pipe_lib.js",
                    "pc_apps/human_replay/human_replay_lib.js",     # spike 借用入口 — 一并跟 SHA
                    "pc_apps/human_ml/frame_feature.py",
                    "pc_apps/human_ml/train_person_rf.py"):
        fp = os.path.join(REPO, fp_rel)
        if os.path.isfile(fp):
            manifest["production_inputs_unchanged"][fp_rel] = {"sha256": sha(fp),
                                                                 "bytes": os.path.getsize(fp)}

    # 与 baseline.json 的 code_frozen SHA 对比证明 production 未被 spike 修改
    with codecs.open(os.path.join(EV, "baseline.json"), "r", "utf-8") as fh:
        baseline = json.load(fh)
    baseline_code_sha = {fp: v.get("sha256") for fp, v in baseline["code_frozen"].items()}
    # 只检钉视为保护对象: 生产链 + spike 初版 (v1 freeze 当下); _harness_lib 的二次迭代
    # /human_replay_lib 不在 spawn 保护线, 分开 reporting.
    PROTECT = ("pc_apps/human_replay/detect_overlay.js",
                "pc_apps/human_replay/rf_person.js",
                "pc_apps/human_replay/bg_envelope.json")
    for fp, s in baseline_code_sha.items():
        cur = manifest["production_inputs_unchanged"].get(fp, {}).get("sha256")
        rel_expected = "protected_production" if fp in PROTECT else "spike_out_of_protection"
        cur_sha = None
        # spike 自己的 _harness_lib.py: 当前 SHA 从 spike_source_code 拿
        if fp.startswith("pc_apps/human_ml/spike_cluster/"):
            name = os.path.basename(fp)
            cur_sha = manifest["spike_source_code"].get(name, {}).get("sha256")
        else:
            cur_sha = cur
        manifest.setdefault("baseline_verify", {})[fp] = {
            "baseline_sha256": s, "current_sha256": cur_sha,
            "unchanged": s == cur_sha,
            "category": rel_expected,
        }
    # 强制: PROTECT 必须 unchanged
    for fp in PROTECT:
        v = manifest["baseline_verify"].get(fp, {})
        assert v.get("unchanged") is True, "protected production file changed: %s" % fp

    with codecs.open(os.path.join(EV, "manifest.json"), "w", "utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    print("wrote", os.path.join(EV, "manifest.json"))
    print("evidence_outputs:", len(manifest["evidence_outputs"]),
          "source_code:", len(manifest["spike_source_code"]),
          "production:", len(manifest["production_inputs_unchanged"]))
    for fp, v in manifest["baseline_verify"].items():
        print(" ", fp, v["unchanged"])


if __name__ == "__main__":
    main()
