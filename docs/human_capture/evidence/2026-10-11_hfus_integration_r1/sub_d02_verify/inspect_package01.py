# -*- coding: utf-8 -*-
# sub_d02_verify: 主控侧 D02 package_01 / coverage_package_01 只读体检
# ponytail: 单脚本完成 step1 全部统计；只读证据文件，不写回
import json, sys, os
from collections import Counter, defaultdict

BASE = r"D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_d02_r1"

def load(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def summarize_records_source(obj, label):
    # review_package.json 顶层结构可能为 {"records":[...]} 或 list
    if isinstance(obj, list):
        return obj
    for k in ("records", "items", "entries"):
        if k in obj and isinstance(obj[k], list):
            return obj[k]
    raise KeyError("%s: 找不到 records list，顶层键=%s" % (label, list(obj.keys())[:20]))

def main():
    out = {}

    # --- package_01 ---
    pdir = os.path.join(BASE, "package_01")
    manifest = load(os.path.join(pdir, "MANIFEST.json"))
    qual = load(os.path.join(pdir, "qualification.json"))
    split = load(os.path.join(pdir, "split_manifest.json"))
    dedup = load(os.path.join(pdir, "dedup_report.json"))
    # review_package.json 19MB，单独加载，只统计不拷贝
    rp = load(os.path.join(pdir, "review_package.json"))
    recs = summarize_records_source(rp, "package_01/review_package.json")
    n = len(recs)

    # 顶层 schema 键（从第一条记录推断 + 全量并集）
    union_keys = set()
    for r in recs[:50] + recs[-50:]:
        union_keys.update(r.keys())
    # 全量统计资格标签 & 负例分级
    qual_label = Counter()
    neg_grade  = Counter()
    per_sess   = Counter()
    sess_obj_cnt = defaultdict(int)
    sess_label = defaultdict(Counter)
    for r in recs:
        s = r.get("session") or r.get("session_id") or r.get("session_name") or "?"
        per_sess[s] += 0
        sess_obj_cnt[s] += 1
        # 机器资格标签
        for key in ("machine_qualification","qualification","qual_label","machine_label"):
            if key in r:
                v = r[key]
                v = v if isinstance(v,str) else json.dumps(v,sort_keys=True)[:60]
                qual_label[(key,v)] += 1
                sess_label[s][v] += 1
                break
        # 负例分级
        for key in ("negative_grade","neg_grade","negative_class","neg_class","negative_label"):
            if key in r:
                v = r[key]
                v = v if isinstance(v,str) else json.dumps(v,sort_keys=True)[:60]
                neg_grade[(key,v)] += 1
                break
    out["package_01"] = {
        "n_records": n,
        "manifest_top_keys": list(manifest.keys())[:30],
        "manifest_n_records": manifest.get("n_records") or manifest.get("records_count"),
        "rp_top_keys": list(rp.keys())[:30] if isinstance(rp,dict) else None,
        "record_keys_union_sample50": sorted(union_keys),
        "qualification_top": qual,
        "split_top_keys": list(split.keys())[:30],
        "dedup_report": dedup,
        "qual_label_counts": {"%s=%s"%k:v for k,v in qual_label.most_common()},
        "neg_grade_counts": {"%s=%s"%k:v for k,v in neg_grade.most_common()},
        "per_session_counts": dict(sess_obj_cnt),
        "per_session_label": {s:dict(c) for s,c in sess_label.items()},
    }
    # split 细节
    # 可能结构 {"folds":{train:[...session],...},...} 或 {"train":[...rec],...}
    if "folds" in split:
        out["package_01"]["split_folds"] = {k:(len(v) if isinstance(v,(list,dict)) else v) for k,v in split["folds"].items()}
    for k in ("train","val","test","stress","blocked","exact_duplicate","exact_duplicates"):
        if k in split:
            v = split[k]
            out["package_01"]["split_%s"%k] = (len(v) if isinstance(v,(list,dict)) else v)

    # S9 / S1 核查
    s9 = [r for r in recs if "180751" in str(r.get("session",""))+str(r.get("session_id","")) ]
    s1 = [r for r in recs if "175227" in str(r.get("session",""))+str(r.get("session_id","")) ]
    def labels_of(rows):
        c = Counter()
        for r in rows:
            for key in ("machine_qualification","qualification","qual_label","machine_label"):
                if key in r: c[str(r[key])] += 1; break
        return dict(c)
    out["package_01"]["S9_obj_count"] = len(s9)
    out["package_01"]["S9_labels"] = labels_of(s9)
    out["package_01"]["S1_obj_count"] = len(s1)
    out["package_01"]["S1_labels"] = labels_of(s1)

    # --- coverage_package_01 ---
    cdir = os.path.join(BASE, "coverage_package_01")
    cm = load(os.path.join(cdir, "MANIFEST.json"))
    cp = load(os.path.join(cdir, "COVERAGE_PRIORITY.json"))
    crp = load(os.path.join(cdir, "review_package.json"))
    crecs = summarize_records_source(crp, "coverage/review_package.json")
    cqual = Counter()
    cneg  = Counter()
    cps   = defaultdict(int)
    for r in crecs:
        s = str(r.get("session") or r.get("session_id") or "?")
        cps[s] += 1
        for key in ("machine_qualification","qualification","qual_label","machine_label"):
            if key in r:
                v = r[key]; v=str(v); cqual[v]+=1; break
        for key in ("negative_grade","neg_grade","negative_class","neg_class","negative_label"):
            if key in r:
                v=str(r[key]); cneg[v]+=1; break
    out["coverage_package_01"] = {
        "n_records": len(crecs),
        "manifest_top_keys": list(cm.keys())[:30],
        "cp_top_keys": list(cp.keys())[:30],
        "per_session_counts": dict(cps),
        "qual_label_counts": dict(cqual.most_common()),
        "neg_grade_counts": dict(cneg.most_common()),
    }
    # coverage 是否含 D02-02 指定帧检查（session×frame 覆盖粗查）
    # coverage review_package records 是否有 frame 键？
    ckeys=set()
    for r in crecs[:20]: ckeys.update(r.keys())
    out["coverage_package_01"]["record_keys_sample20"] = sorted(ckeys)

    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=1, default=str))

if __name__ == "__main__":
    main()
