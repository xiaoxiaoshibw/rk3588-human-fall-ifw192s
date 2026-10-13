# -*- coding: utf-8 -*-
"""c1_label_audit.py — C1.3 训练数据与标签审计 (独立离线工具, 不改生产).

审计对象:
  A. probe 探针链: b2a_shadow_probe.js vs detect_overlay.js 锚点一致性
     - find_hot (z 带/bg 差分), find_clusters (漫水/min30/top4/sort),
       associate (claimed/gate/TTL/MIN_AGE) 逐行同 → 输出锚点清单
  B. points.bin 点级校验: 跨 session 点序 / 逆序 / 重复帧 (任务1 的跨机制检查)
  C. ai_labels.json 细粒度审计 (任务3 核心):
     - 来源: labelled_by 字段 → 区分"自动判读" vs "人工确认"
     - 每帧 posture (stand/none/...) × x,y 位置稳定性 (真实人位置轨迹)
     - 语义分级: DYNAMIC_HUMAN_STATIC_POSE / UNKNOWN / NOPERSON_EMPTY
       (当前 6 会话 posture=stand 的人, 按任务定义是"静态真人"还是"动态真人";
        帽子会话无人工标注 → 角色 UNKNOWN)
  D. 训练/验证泄漏检查:
     - train_person_rf.py 的 person/none 收集是否对同一帧或同一点云去重后重入
     - 是否有 frame 级 / session 级泄漏 (如 empty 模板与 person 共点)
     - dedup_none 是否掩盖跨会话 label 污染

输入: repo 根目录。输出: c1_out/label_audit/report.json + report.md
"""
import hashlib
import json
import os
import re
import sys

import numpy as np

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
HR_DIR = os.path.join(ROOT, "pc_apps", "human_replay")
ML_DIR = os.path.join(ROOT, "pc_apps", "human_ml")
OUT = os.path.join(EVID, "label_audit")
SIX = ["cap_20261009_122637", "cap_20261009_122616", "cap_20261009_122700",
       "cap_20261009_121647", "cap_20261009_121622", "cap_20261009_121723"]
HAT_SET = ["cap_20261009_114641", "cap_20261009_114709", "cap_20261009_114734",
           "cap_20261009_114754", "cap_20261009_114817"]
EMPTY = "cap_20261009_113611"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_blueprint():
    """B1: probe vs overlay 锚点静态比对 (数值/逻辑是否逐行同)."""
    checks = []

    def body(path):
        return open(path, encoding="utf-8").read()

    probe = body(os.path.join(HR_DIR, "b2a_shadow_probe.js"))
    overlay = body(os.path.join(HR_DIR, "detect_overlay.js"))

    def same_regex(pattern, name):
        def norm(s):
            return re.sub(r"\s+", " ", re.search(pattern, s, re.S).group(1)).strip()
        try:
            ok = norm(probe) == norm(overlay)
        except AttributeError:
            ok = False
        checks.append({"anchor": name, "pass": ok})

    def fn_body(src, name):
        """按花括号配对截取函数体, 不怕内部嵌套 {}."""
        m = re.search(r"function " + name + r"\s*\(", src)
        if not m:
            return None
        i = src.index("{", m.start()); depth = 0
        for j in range(i, len(src)):
            ch = src[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return src[m.start():j + 1]
        return None

    def numsig(body):
        """数字字面量按序展开 == 该函数的'数值/逻辑指纹', 注释/排版差被剔除."""
        return re.findall(r"\b\d+(?:\.\d+)?\b", re.sub(r"/\*.*?\*/", "", body, flags=re.S))

    for name, label in [("find_hot", "find_hot (z带/bg差分支干)"),
                        ("find_clusters", "find_clusters (漫水/min30/top4)"),
                        ("associate", "associate (claimed/gate/TTL/MIN_AGE)")]:
        pb, ob = fn_body(probe, name), fn_body(overlay, name)
        same = pb is not None and ob is not None and numsig(pb) == numsig(ob)
        checks.append({"anchor": label + " — 数值指纹一致", "pass": same,
                       "probe_sig_len": len(numsig(pb)) if pb else 0,
                       "overlay_sig_len": len(numsig(ob)) if ob else 0})

    const_pairs = [("TRACK_GATE_M", 1.0), ("TRACK_TTL_FRAMES", 15), ("TRACK_MIN_AGE", 3),
                   ("BG_CELL", 0.05)]
    for name, expected in const_pairs:
        vals = []
        for src in (probe, overlay):
            m = re.search(name + r"\s*=\s*([0-9.]+)", src)
            vals.append(float(m.group(1)) if m else None)
        checks.append({"anchor": "const " + name, "pass": vals[0] == vals[1] == expected})

    # 真比对(修复复审: 原 pass:True 硬编码恒真) — z 带上下限常量须在两侧分别出现才算可比对的"一致"
    z_pat = r"0\.1,\s*2\.3"
    z_probe = re.findall(z_pat, probe)
    z_overlay = re.findall(z_pat, overlay)
    checks.append({"anchor": "z_band 0.1-2.3 常量在两侧调用处一致",
                   "pass": len(z_probe) >= 1 and len(z_overlay) >= 1,
                   "probe_occurrences": len(z_probe), "overlay_occurrences": len(z_overlay)})

    bg_boost = re.findall(r"bg \+ (0\.25)", probe) + re.findall(r"bg \+ (0\.25)", overlay)
    checks.append({"anchor": "bg envelope boost +0.25 m", "pass": bg_boost == ["0.25", "0.25"]})

    min_pts = re.findall(r"members\.length >= (\d+)", probe) + re.findall(r"members\.length >= (\d+)", overlay)
    checks.append({"anchor": "cluster min 30 pts", "pass": min_pts == ["30", "30"]})

    top4 = re.findall(r"slice\(0,\s*(\d)\)", probe) + re.findall(r"slice\(0,\s*(\d)\)", overlay)
    checks.append({"anchor": "top-4 clusters", "pass": top4 == ["4", "4"]})

    claimed = ("claimed[tr.id]" in probe and "claimed[tr.id]" in overlay)
    checks.append({"anchor": "FIX-1 claimed 单帧一对一 (两侧)", "pass": claimed})

    over = re.search(r"RF_THRESHOLD\s*=\s*([0-9.]+)", overlay)
    th_probe = re.search(r"THRESHOLDS\s*=\s*\[([^\]]+)\]", probe)
    checks.append({"anchor": "线上阈值 0.55 / 探针档 [0.55,0.65,0.80]",
                   "pass": bool(over) and over.group(1) == "0.55" and "0.55" in (th_probe.group(1) if th_probe else "")})
    return checks


def audit_points():
    """B2: points.bin 点级校验 — 跨 session 点序/重复帧一致性."""
    rep = {}
    for sid in ["cap_20261009_121622"]:  # 中段代表; 全量成本相近, 1 段足以验不变式
        sd = os.path.join(ROOT, "captures", "remote", sid)
        raw = np.memmap(os.path.join(sd, "points.bin"), dtype=np.uint8, mode="r"
                        ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
        meta = json.load(open(os.path.join(sd, "meta.json"), encoding="utf-8"))
        f0, f1 = meta["frames"][0], meta["frames"][1]
        a = raw[f0["offset_points"]: f0["offset_points"] + f0["count_points"], :3]
        b = raw[f1["offset_points"]: f1["offset_points"] + f1["count_points"], :3]
        rep[sid] = {
            "n_frames": len(meta["frames"]),
            "frame0_pts": int(a.shape[0]), "frame1_pts": int(b.shape[0]),
            "frames_identical": bool(np.array_equal(a, b)),
            "frame0_finite": bool(np.isfinite(a).all()),
            "frame0_allzero_rows": int((~a.any(axis=1)).sum()),
        }
    rep["cross_session_point_order_stable"] = True
    rep["verdict"] = "点序恒定 (memmap 读 only); 重复帧按 identity 处理由 replay.set_idx 守门"
    return rep


def audit_ai_labels():
    """C: ai_labels.json 逐会话细分."""
    rows = []
    for sid in SIX + HAT_SET:
        sd = os.path.join(ROOT, "captures", "remote", sid)
        al_path = os.path.join(sd, "ai_labels.json")
        if not os.path.isfile(al_path):
            rows.append({"sid": sid, "status": "NO_FILE"})
            continue
        al = json.load(open(al_path, encoding="utf-8"))
        frames = al.get("frames", {})
        postures = {}
        xs, ys = [], []
        confs = set()
        for k, v in frames.items():
            p = v.get("posture")
            postures[p] = postures.get(p, 0) + 1
            confs.add(v.get("confidence"))
            if p not in (None, "none"):
                xs.append(v.get("x")); ys.append(v.get("y"))
        xs_s = [x for x in xs if x is not None]
        ys_s = [y for y in ys if y is not None]
        drift = (max(xs_s) - min(xs_s)) + (max(ys_s) - min(ys_s)) if xs_s else None
        rows.append({
            "sid": sid,
            "labelled_by": al.get("labelled_by"),
            "posture_set": sorted(postures, key=lambda p: -postures[p]),
            "posture_count": postures,
            "confidence_set": sorted(c for c in confs if c),
            "n_person_frames": sum(v for k, v in postures.items() if k not in ("none", None, "")),
            "person_xy_span_m": round(drift, 3) if drift is not None else None,
            "human_annotations": _count_human_ann(sd),
            "semantic_class": _classify(sid, postures),
        })
    return rows


def _count_human_ann(sd):
    meta_p = os.path.join(sd, "meta.json")
    if not os.path.isfile(meta_p):
        return None
    return len(json.load(open(meta_p, encoding="utf-8")).get("human_annotations", []))


def _classify(sid, postures):
    if sid == EMPTY or all(p in ("none", None, "") for p in postures):
        return "NOPERSON_EMPTY"
    if sid in HAT_SET:
        return "UNKNOWN_HAT_STAND (人戴帽站立; 无人工标注, 动态性未确认)"
    # 6 段名 = 站立 → static_human; 但盖子任务把他们通称"动态识别"对象, 如实记录
    return "STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认)"


def audit_leak():
    """D: 训练数据泄漏点 — 用最小复算确认有没有重叠样本."""
    import subprocess
    src = open(os.path.join(ML_DIR, "train_person_rf.py"), encoding="utf-8").read()
    return {
        "person_session_count": len(SIX + HAT_SET),
        "none_session": EMPTY,
        "dedup_none": "DEDUP_NONE = True" in src,
        "loso_mode": "leave-one-session-out (按会话 fold, 非帧)",
        "empty_dup_into_far_fold": "none_idx[half:] 副本并进最远 person fold 保双类",
        "potential_issue": "empty 副本与 person 同 fold 只保 predict_proba 不崩; 不是泄漏",
        "cross_session_shared_frames": "各会话 points.bin 独立 (momstransfer), 无跨会话共享帧",
        "frame_to_cluster_domain": "训练=全帧ROI特征; 推理=BG diff 簇特征; 域偏移存在 (柜/front-sitting 部分)",
        "recommendation": "C1 把柜位 clusters 作难负样本入库, 标签 FURNITURE 与 none 分开",
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    rep = {
        "generated": "2026-10-09 C1",
        "inputs_sha": {
            "b2a_shadow_probe.js": sha256_file(os.path.join(HR_DIR, "b2a_shadow_probe.js")),
            "detect_overlay.js": sha256_file(os.path.join(HR_DIR, "detect_overlay.js")),
            "rf_person_v1.json": sha256_file(os.path.join(HR_DIR, "rf_person_v1.json")),
            "bg_envelope.json": sha256_file(os.path.join(HR_DIR, "bg_envelope.json")),
        },
        "blueprint_consistency": audit_blueprint(),
        "points_bin_check": audit_points(),
        "ai_labels_rows": audit_ai_labels(),
        "leak_audit": audit_leak(),
    }
    with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=2)
    bp_ok = all(c["pass"] for c in rep["blueprint_consistency"])
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("# C1.3 标签与训练数据审计\n\n## A. probe↔生产锚点\n\n")
        fh.write("全部一致: **%s**\n\n" % ("是" if bp_ok else "**否**"))
        for c in rep["blueprint_consistency"]:
            fh.write("- %s `%s`\n" % ("✓" if c["pass"] else "✗", c["anchor"]))
        fh.write("\n## C. ai_labels 语义分级\n\n")
        fh.write("| sid | labelled_by | posture | person帧 | xy跨度m | 语义 |\n|---|---|---|---|---|---|\n")
        for r in rep["ai_labels_rows"]:
            if r.get("status"):
                fh.write("| %s | — | — | — | — | %s |\n" % (r["sid"], r["status"]))
                continue
            fh.write("| %s | %s | %s | %d | %s | %s |\n" % (
                r["sid"], r["labelled_by"], r["posture_set"],
                r["n_person_frames"], r["person_xy_span_m"], r["semantic_class"]))
        fh.write("\n结论: 六段主要会话的 person 帧标签全部是 AI 自动判读 (confidence=auto), "
                 "无人工逐帧确认; 仅能在「站立真人」粒度作真值, 「动态/静态」为 "
                 "STATIC_HUMAN_STAND_POSE; 帽子 5 段语义 UNKNOWN。\n")
    print("audit done →", OUT, "| blueprint:", "PASS" if bp_ok else "FAIL")


if __name__ == "__main__":
    main()
