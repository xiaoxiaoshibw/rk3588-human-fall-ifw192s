# -*- coding: utf-8 -*-
"""HFUS-D02 待审包导出：把待审对象记录落成 JSONL + manifest，支持回读校验。

机器永不写 reviewed；QUAL_INVALID_BINDING 来自 sha 绑定破坏；
原子写 = 先写临时文件再 os.replace（同目录 rename，跨平台原子）。
不复用 loader：为保持单文件可独立自测，依赖仅 stdlib + review_schema。
"""
import hashlib
import json
import os
import tempfile

from review_schema import (
    REVIEW_DRAFT,
    REVIEW_UNREVIEWED,
    REVIEW_REVIEWED,
    REASON_NO_CANDIDATE,  # noqa: F401  # 仅为 import 可见性，不用强制
)


# ---------- 单条记录 ----------

def content_hash_for_dedup(session_id, frame_idx, member_point_raw_sorted, class_name):
    """跨帧/跨 fold 查 exactly-duplicate 的稳定 hash。

    成员点集合 + (session,frame,class) 联合决定：相同输入必然同 hash。
    """
    body = "%s|%s|%s|%s" % (
        session_id,
        frame_idx,
        class_name,
        ",".join(str(int(v)) for v in sorted(member_point_raw_sorted)),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def make_review_item(
    session_id,
    frame_idx,
    timestamp_s,
    raw_input_sha256,
    index_domain,
    member_point_raw,
    member_point_compact,
    label_source,
    review_status,
    qualification,
    reason,
    class_name,
):
    """生成单条待审对象记录 dict。

    校验：
      - review_status 不得为 'reviewed'（机器永不写人工）
      - member_point_raw 不得含负数或重复
    """
    if review_status == REVIEW_REVIEWED:
        raise ValueError("review_status 不得为 reviewed（机器永不写人工）")
    member_point_raw = [int(v) for v in member_point_raw]
    if any(v < 0 for v in member_point_raw):
        raise ValueError("member_point_raw 不得含负数")
    if len(set(member_point_raw)) != len(member_point_raw):
        raise ValueError("member_point_raw 不得含重复值")

    member_point_compact = [int(v) for v in member_point_compact]
    dedup_hash = content_hash_for_dedup(
        session_id, frame_idx, sorted(member_point_raw), class_name
    )

    return {
        "session_id": session_id,
        "frame_idx": int(frame_idx),
        "timestamp_s": float(timestamp_s),
        "raw_input_sha256": raw_input_sha256,  # {meta, points} 引用
        "index_domain": index_domain,
        "member_point_raw": member_point_raw,
        "member_point_compact": member_point_compact,
        "label_source": label_source,
        "review_status": review_status,
        "qualification": qualification,
        "reason": reason,
        "class_name": class_name,
        "dedup_hash": dedup_hash,
    }


# ---------- 原子写 ----------

def _reason_key(reason):
    # None 兜底记录不能进 JSON sort_keys（None<str 会 TypeError），归一为可读键
    return "(none)" if reason is None else str(reason)


def _atomic_write(path, text):
    """写临时文件再 os.replace，保证读侧永远看到完整文件。"""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------- 整包 ----------

def write_package(records, out_dir, base_name, created_iso):
    """写 <base>.jsonl + <base>.manifest.json，返回 dict(jsonl_path, manifest_path, manifest)。"""
    os.makedirs(out_dir, exist_ok=True)
    jsonl_path = os.path.join(out_dir, base_name + ".jsonl")
    manifest_path = os.path.join(out_dir, base_name + ".manifest.json")

    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    jsonl_text = "\n".join(lines) + ("\n" if lines else "")
    jsonl_sha = hashlib.sha256(jsonl_text.encode("utf-8")).hexdigest()

    per_session = {}
    per_reason = {}
    per_qualification = {}
    input_sha_map = {}
    for r in records:
        sid = r["session_id"]
        per_session[sid] = per_session.get(sid, 0) + 1
        rk = _reason_key(r["reason"])
        per_reason[rk] = per_reason.get(rk, 0) + 1
        q = r["qualification"]
        per_qualification[q] = per_qualification.get(q, 0) + 1
        # 同一 session 的 raw_input_sha256 由调用方保证一致；冲突时后者覆盖（防呆抛错更安全）
        if sid in input_sha_map and input_sha_map[sid] != r["raw_input_sha256"]:
            raise ValueError("session %s 的 raw_input_sha256 前后不一致" % sid)
        input_sha_map[sid] = r["raw_input_sha256"]

    manifest = {
        "package_base": base_name,
        "created_iso": created_iso,
        "n_records": len(records),
        "per_session": per_session,
        "per_reason": per_reason,
        "per_qualification": per_qualification,
        "input_sha256_map": input_sha_map,
        "output_jsonl_sha256": jsonl_sha,
        "manifest_sha256_of_jsonl": jsonl_sha,  # manifest 也带 jsonl 内容 hash 便于对账
    }

    _atomic_write(jsonl_path, jsonl_text)
    _atomic_write(
        manifest_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "jsonl_path": jsonl_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def read_package(jsonl_path):
    """回读 JSONL，顺带统计 dedup_hash 重复。"""
    records = []
    seen_hashes = set()
    dup_hashes = set()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            records.append(r)
            h = r.get("dedup_hash")
            if h in seen_hashes:
                dup_hashes.add(h)
            else:
                seen_hashes.add(h)
    return {
        "records": records,
        "n": len(records),
        "seen_hashes": seen_hashes,
        "dup_hashes": dup_hashes,
    }


# ---------- 便捷聚合器 ----------

def export_review_items(item_skeletons, input_sha256_map, created_iso, out_dir, base_name):
    """把 list[dict] 骨架逐条 make_review_item，再 write_package，返回 manifest。

    骨架字段对应 make_review_item 的实参；raw_input_sha256 上层从 input_sha256_map 注入。
    """
    records = []
    for s in item_skeletons:
        sid = s["session_id"]
        rec = make_review_item(
            session_id=sid,
            frame_idx=s["frame_idx"],
            timestamp_s=s["timestamp_s"],
            raw_input_sha256=input_sha256_map[sid],
            index_domain=s["index_domain"],
            member_point_raw=s["member_point_raw"],
            member_point_compact=s["member_point_compact"],
            label_source=s["label_source"],
            review_status=s["review_status"],
            qualification=s["qualification"],
            reason=s["reason"],
            class_name=s["class_name"],
        )
        records.append(rec)
    out = write_package(records, out_dir, base_name, created_iso)
    return out["manifest"]


# ---------- 最小自测 ----------

if __name__ == "__main__":
    import shutil

    from review_schema import (
        INDEX_DOMAIN_RAW28,
        QUAL_INVALID_BINDING,
        QUAL_PROPAGATED_CONDITIONAL,
        QUAL_UNKNOWN,
        SOURCE_MODEL,
        SOURCE_MODEL_SUSPECT,
        SOURCE_PROPAGATED,
        machine_default_review_status,
    )

    tmpdir = tempfile.mkdtemp(prefix="review_export_selftest_")
    try:
        sha_a = {"meta": "a" * 64, "points": "b" * 64}
        sha_b = {"meta": "c" * 64, "points": "d" * 64}

        # 1) 合成 3 条记录（不同 session/frame/成员）
        r1 = make_review_item(
            session_id="sess_A",
            frame_idx=10,
            timestamp_s=1.5,
            raw_input_sha256=sha_a,
            index_domain=INDEX_DOMAIN_RAW28,
            member_point_raw=[3, 1, 2],
            member_point_compact=[0, 1, 2],
            label_source=SOURCE_MODEL,
            review_status=machine_default_review_status(SOURCE_MODEL),
            qualification=QUAL_UNKNOWN,
            reason="candidate_fn",
            class_name="person",
        )
        r2 = make_review_item(
            session_id="sess_A",
            frame_idx=11,
            timestamp_s=1.6,
            raw_input_sha256=sha_a,
            index_domain=INDEX_DOMAIN_RAW28,
            member_point_raw=[5],
            member_point_compact=[4],
            label_source=SOURCE_PROPAGATED,
            review_status=machine_default_review_status(SOURCE_PROPAGATED),
            qualification=QUAL_PROPAGATED_CONDITIONAL,
            reason="propagated_not_reviewed",
            class_name="person",
        )
        r3 = make_review_item(
            session_id="sess_B",
            frame_idx=0,
            timestamp_s=0.0,
            raw_input_sha256=sha_b,
            index_domain=INDEX_DOMAIN_RAW28,
            member_point_raw=[100, 200],
            member_point_compact=[9, 10],
            label_source=SOURCE_MODEL_SUSPECT,
            review_status=machine_default_review_status(SOURCE_MODEL_SUSPECT),
            qualification=QUAL_INVALID_BINDING,
            reason="broken_sha_binding",
            class_name="person",
        )
        assert r1["review_status"] == REVIEW_UNREVIEWED
        assert r3["review_status"] == REVIEW_UNREVIEWED

        # 2) make_review_item 拒绝 reviewed
        try:
            make_review_item(
                session_id="s", frame_idx=0, timestamp_s=0.0,
                raw_input_sha256=sha_a, index_domain=INDEX_DOMAIN_RAW28,
                member_point_raw=[0], member_point_compact=[0],
                label_source=SOURCE_MODEL, review_status=REVIEW_REVIEWED,
                qualification=QUAL_UNKNOWN, reason="x", class_name="person",
            )
            raise SystemExit("应拒绝 reviewed")
        except ValueError:
            pass

        # 3) 拒绝重复/负成员
        for bad in ([[1, 1], [-1]]):
            try:
                make_review_item(
                    session_id="s", frame_idx=0, timestamp_s=0.0,
                    raw_input_sha256=sha_a, index_domain=INDEX_DOMAIN_RAW28,
                    member_point_raw=bad, member_point_compact=[0, 1],
                    label_source=SOURCE_MODEL, review_status=REVIEW_UNREVIEWED,
                    qualification=QUAL_UNKNOWN, reason="x", class_name="person",
                )
                raise SystemExit("应拒绝坏成员 %r" % bad)
            except ValueError:
                pass

        # 4) 两条内容相同 -> dedup_hash 相同（乱序成员也算同）
        h1 = content_hash_for_dedup("s", 1, [3, 1, 2], "person")
        h2 = content_hash_for_dedup("s", 1, [1, 2, 3], "person")
        assert h1 == h2

        # 5) write + read 回环
        out = write_package([r1, r2, r3], tmpdir, "pkg", "2026-10-11T00:00:00Z")
        # 5b) reason=None（机器兜底）也必须能排序写入 manifest，不 TypeError
        r_none = make_review_item(
            session_id="sess_A", frame_idx=99, timestamp_s=9.9,
            raw_input_sha256=sha_a, index_domain=INDEX_DOMAIN_RAW28,
            member_point_raw=[7], member_point_compact=[3],
            label_source=SOURCE_MODEL, review_status=REVIEW_DRAFT,
            qualification=QUAL_UNKNOWN, reason=None, class_name="person",
        )
        out_none = write_package([r_none], tmpdir, "pkg_none", "2026-10-11T00:00:00Z")
        assert out_none["manifest"]["per_reason"] == {"(none)": 1}

        man = out["manifest"]
        assert man["n_records"] == 3
        assert man["per_session"] == {"sess_A": 2, "sess_B": 1}
        assert man["per_qualification"][QUAL_INVALID_BINDING] == 1

        back = read_package(out["jsonl_path"])
        assert back["n"] == 3
        assert not back["dup_hashes"]

        # 对账：manifest 里的 output_jsonl_sha256 == 实读 jsonl 文件 sha256
        with open(out["jsonl_path"], "rb") as f:
            file_sha = hashlib.sha256(f.read()).hexdigest()
        assert file_sha == man["output_jsonl_sha256"]
        assert man["manifest_sha256_of_jsonl"] == file_sha

        # 6) export_review_items 聚合器
        skeletons = [
            {
                "session_id": "sess_A",
                "frame_idx": 10,
                "timestamp_s": 1.5,
                "index_domain": INDEX_DOMAIN_RAW28,
                "member_point_raw": [1, 2, 3],
                "member_point_compact": [0, 1, 2],
                "label_source": SOURCE_MODEL,
                "review_status": REVIEW_UNREVIEWED,
                "qualification": QUAL_UNKNOWN,
                "reason": "candidate_fn",
                "class_name": "person",
            }
        ]
        man2 = export_review_items(
            skeletons,
            input_sha256_map={"sess_A": sha_a},
            created_iso="2026-10-11T00:00:00Z",
            out_dir=tmpdir,
            base_name="pkg2",
        )
        assert man2["n_records"] == 1
        assert man2["input_sha256_map"] == {"sess_A": sha_a}

        print("review_export selftest OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
