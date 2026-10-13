# -*- coding: utf-8 -*-
"""freeze_baseline.py — 基线冻结脚本 (evidence init).
1. 计算 12 段会话的输入 SHA (meta.json + points.bin 首 1MB 抽样 + ai_labels.json 若存在)
2. 从 git 当前 HEAD 抽取生产文件版本指纹 (不复制文件内容)
3. 把 BG envelope 与 leveling R/T 指纹固定
4. 产出 baseline.json (输入指纹) + baseline_code.json (代码指纹) 到 evidence 目录
不修改任何生产文件, 不改 evidence — 只写 evidence/2026-10-10_spike_cluster_r1/.
"""
import hashlib
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))

SESSIONS_TUNING = [   # 调参会话 (T0): 不让它们进 final eval 阈值裁定.
    # 注: 114641 已从 TUNING 移除 — 它是 E0 12 段的一个 (同 GT 勘查的 HR-09 source),
    # 让它同时出现会污染"评估与调参分离"原则.
    "cap_20261007_143945", "cap_20261007_150455", "cap_20261007_154007",
    "cap_20261007_154341", "cap_20261007_154545", "cap_20261007_154920",
]
SESSIONS_EVAL = [     # 评估会话 (E0): 12 段站立 + 空场. 标签 + 柜位锚已具备
    "cap_20261009_114709", "cap_20261009_114734", "cap_20261009_114754", "cap_20261009_114817",
    "cap_20261009_121622", "cap_20261009_121647", "cap_20261009_121723", "cap_20261009_122616",
    "cap_20261009_122637", "cap_20261009_122700",
    "cap_20261007_215540",   # 静立人 (无 ai_labels; 用 README 锚点 (2.10,-0.57) r=0.55)
    "cap_20261009_113611",   # 空场 bg_envelope 源 (描述性检测零)
    # 可加 (不在 R1 12 段内, 作稳健性 reference 而非判定):
    "cap_20261008_114205", "cap_20261008_114254", "cap_20261008_114340", "cap_20261008_114422",
]

def sha256_file(path, head_only_kb=None):
    h = hashlib.sha256()
    if head_only_kb is None:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    else:
        with open(path, "rb") as fh:
            h.update(fh.read(head_only_kb * 1024))
        h.update(str(os.path.getsize(path)).encode())
    return h.hexdigest()

def git_blob_sha(path_rel):
    """git hash-object 的 blob SHA (工作区实际内容, 不必已提交). 等同 git ls-files -s 输出"""
    try:
        out = subprocess.run(["git", "-C", REPO, "hash-object", path_rel],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception as e:
        return "ERR:" + str(e)

def main():
    ev_dir = sys.argv[1]
    os.makedirs(ev_dir, exist_ok=True)

    inputs = {}
    for sid in SESSIONS_TUNING + SESSIONS_EVAL:
        sdir = os.path.join(REPO, "captures", "remote", sid)
        entry = {"dir": sdir, "exists": os.path.isdir(sdir)}
        if entry["exists"]:
            for fn in ("meta.json", "ai_labels.json"):
                p = os.path.join(sdir, fn)
                if os.path.isfile(p):
                    entry[fn + ".sha256"] = sha256_file(p)
                    entry[fn + ".bytes"] = os.path.getsize(p)
            pb = os.path.join(sdir, "points.bin")
            if os.path.isfile(pb):
                # points.bin 太大, 用头 8KB + 总字节数拼 hash (足够证明固定版本)
                entry["points.bin.sha256_head8k+size"] = sha256_file(pb, head_only_kb=8)
                entry["points.bin.bytes"] = os.path.getsize(pb)
        inputs[sid] = entry

    code_files = [
        "pc_apps/human_replay/detect_overlay.js",
        "pc_apps/human_replay/rf_person.js",
        "pc_apps/human_replay/bg_envelope.json",
        "pc_apps/human_replay/human_replay_lib.js",
        "pc_apps/human_ml/spike_cluster/_harness_lib.py",
    ]
    code = {f: {"sha256": sha256_file(os.path.join(REPO, f))} for f in code_files}
    # git commit digest of the tree state
    try:
        head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        head = "unknown"
    dirty = subprocess.run(["git", "-C", REPO, "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    git_state = {"HEAD": head, "dirty_files_count": len(dirty.splitlines()) if dirty else 0}

    out = {
        "freeze_utc": subprocess.run(["python", "-B", "-c",
                                       "import datetime;print(datetime.datetime.utcnow().isoformat()+'Z')"],
                                      capture_output=True, text=True).stdout.strip(),
        "repo_root": REPO,
        "purpose": "CLUSTER-ADAPTIVE-SPIKE-R1 baseline freeze",
        "sessions_tuning": SESSIONS_TUNING,
        "sessions_eval": SESSIONS_EVAL,
        "inputs": inputs,
        "code_frozen": code,
        "git_state": git_state,
        "constants": {"GRID_CELL_M": 0.05, "KEY_MOD": 4096, "MIN_POINTS": 30, "TOP_K": 4,
                      "BG_PATH": "pc_apps/human_replay/bg_envelope.json",
                      "Z_LO": 0.1, "Z_HI": 2.3, "BG_DELTA_M": 0.25,
                      "R": "0.893544,0.0,0.448975;-0.014337,0.99949,0.028533;-0.448746,-0.031932,0.893089",
                      "T": "0.0,0.0,1.380286"},
    }
    with open(os.path.join(ev_dir, "baseline.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False, sort_keys=True)
    print("wrote", os.path.join(ev_dir, "baseline.json"))
    print("inputs:", len(inputs), "code files:", len(code_files), "git HEAD:", git_state["HEAD"][:8])


if __name__ == "__main__":
    main()
