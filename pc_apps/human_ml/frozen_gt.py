"""Read frozen workbench objects without changing GT or capture files."""
import hashlib
import json
import pathlib
import re

import numpy as np
from render_person_label import R, T

REPO = pathlib.Path(__file__).resolve().parents[2]
SIDS = ["cap_20261010_" + s for s in
        ("175227", "175429", "175553", "175804", "175943", "180235", "180337", "180557", "180751")]


def read_json(path):
    with pathlib.Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    with pathlib.Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1, allow_nan=False)


def decode_indices(v):
    def run(parts):
        if len(parts) % 3:
            raise ValueError("invalid run header")
        result = []
        for a, d, n in zip(parts[0::3], parts[1::3], parts[2::3]):
            if not all(type(x) is int for x in (a, d, n)) or a < 0 or d < 1 or n < 1 or n > 1000000:
                raise ValueError("invalid index run")
            result.extend(range(a, a + d * n, d))
        return result
    if not isinstance(v, list) or not v:
        raise ValueError("missing indices")
    if v[0] == "s":
        out = v[1:]
    elif v[0] == "r" and len(v) == 4:
        out = run(v[1:])
    elif v[0] == "m" and len(v) == 3:
        out = run(v[1]) + v[2]
    else:
        raise ValueError("unknown index encoding")
    if not out or any(type(i) is not int or i < 0 for i in out) or len(set(out)) != len(out):
        raise ValueError("empty/duplicate/invalid compact indices")
    return np.asarray(out, dtype=np.int64)


def audit_session(sid, store, capture):
    manifest_path = store / sid / "manifest.json"
    m = read_json(manifest_path)
    usable = [v for v in m["versions"] if v.get("annotator") != "e2e"]
    # A contaminated session must not stop evaluation of other independent sessions.
    # Keep the rejected current file for audit only; eligibility stays false.
    v = usable[-1] if usable else m["versions"][-1]
    if not re.fullmatch(r"V[1-9][0-9]*", v["version"]):
        raise ValueError("invalid version")
    p = manifest_path.parent / ("GT_" + v["version"] + ".json")
    doc = read_json(p)
    meta = read_json(capture / sid / "meta.json")
    actual = {"meta": sha(capture / sid / "meta.json"), "points": sha(capture / sid / "points.bin")}
    issues, warnings = ([] if usable else ["NO_USABLE_NON_E2E_VERSION"]), []
    if sha(p) != v["sha256"]:
        issues.append("GT_SHA_MISMATCH")
    if doc.get("session_sha256") != actual:
        issues.append("SESSION_SHA_MISMATCH_OR_MISSING")
    if doc.get("session_id") != sid or doc.get("schema_version") != "gt_workbench/1":
        issues.append("SCHEMA_OR_SESSION_MISMATCH")
    if doc.get("review_status") != "reviewed" or len(doc["objects"]) != v["object_count"]:
        issues.append("REVIEW_OR_OBJECT_COUNT")
    if doc.get("gt_level") != "HUMAN_VERIFIED":
        warnings.append("STALE_OR_MISSING_GT_LEVEL; validated review/binding determine eligibility")
    if meta.get("leveling"):
        issues.append("ALREADY_LEVELED_CAPTURE_UNSUPPORTED")
    if meta.get("point_stride_bytes") != 28:
        issues.append("STRIDE_NOT_28")
    counts, referenced = {}, []
    for f, ids in doc["frames_objects"].items():
        fi = int(f)
        if fi < 0 or fi >= len(meta["frames"]):
            issues.append("FRAME_OUT_OF_RANGE:" + f)
            continue
        tracks = set()
        for oid in ids:
            referenced.append(oid)
            o = doc["objects"].get(oid, {})
            cls = o.get("class_name")
            counts[cls] = counts.get(cls, 0) + 1
            if (o.get("frame_idx") != fi or o.get("object_id") != oid or
                    o.get("session_id") != sid or o.get("review_status") != "reviewed" or
                    o.get("source") not in ("human", "propagated") or
                    o.get("coordinate_frame") != "leveled-IFW192S" or
                    o.get("leveling_transform_id") != "render_person_label.R/T" or
                    cls not in ("PERSON", "FURNITURE", "BACKGROUND", "UNKNOWN")):
                issues.append("OBJECT_CONTRACT:" + oid)
            if cls == "PERSON":
                tid = o.get("track_id")
                if not tid or tid in tracks:
                    issues.append("PERSON_TRACK:" + oid)
                tracks.add(tid)
            try:
                idx = decode_indices(o.get("raw_point_indices"))
                if len(idx) != o.get("point_count") or idx.max() >= meta["frames"][fi]["count_points"]:
                    issues.append("POINT_COUNT_OR_RAW_BOUND:" + oid)
            except (ValueError, TypeError):
                issues.append("INDICES:" + oid)
    if set(referenced) != set(doc["objects"]) or len(referenced) != len(set(referenced)):
        issues.append("FRAME_OBJECT_MAP")
    record = {"sid": sid, "gt_path": str(p), "version": v["version"],
              "gt_sha256": sha(p), "manifest_sha256": sha(manifest_path), "input_sha256": actual,
              "declared_session_sha256": doc.get("session_sha256"),
              "skipped_versions": [x for x in m["versions"] if x.get("annotator") == "e2e"],
              "counts": counts, "annotated_frames": len(doc["frames_objects"]),
              "total_frames": len(meta["frames"]), "issues": sorted(set(issues)), "warnings": warnings,
              "eligible": not issues}
    return record, doc, meta


def compact_frame(raw, f):
    seg = raw[f["offset_points"]:f["offset_points"] + f["count_points"], :4]
    valid = np.isfinite(seg[:, :3]).all(axis=1) & np.any(seg[:, :3] != 0, axis=1)
    seg = seg[valid]
    return np.column_stack((seg[:, :3].astype(np.float64) @ R.T + T, seg[:, 3])).astype(np.float32)


def export_samples(record, doc, meta, capture):
    if not record["eligible"]:
        return [], {"excluded": record["issues"]}
    raw = np.memmap(capture / record["sid"] / "points.bin", dtype="<f4", mode="r").reshape(-1, 7)
    from frame_feature import extract_features
    samples, duplicates = [], 0
    for f in sorted(doc["frames_objects"], key=int):
        points = compact_frame(raw, meta["frames"][int(f)])
        seen = set()
        for oid in doc["frames_objects"][f]:
            o = doc["objects"][oid]
            if o["class_name"] not in ("PERSON", "FURNITURE"):
                continue
            idx = decode_indices(o["raw_point_indices"])
            if idx.max() >= len(points):
                raise ValueError("COMPACT_INDEX_OUT_OF_RANGE:" + oid)
            key = (o["class_name"], tuple(sorted(idx.tolist())))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            crop = points[idx]
            if not np.isfinite(crop).all():
                raise ValueError("NONFINITE_CROP:" + oid)
            fv = extract_features(crop)
            samples.append({"session_id": record["sid"], "frame_index": int(f), "object_id": oid,
                            "track_id": o.get("track_id"), "label": int(o["class_name"] == "PERSON"),
                            "class_name": o["class_name"], "point_count": len(idx),
                            "crop_algorithm": "frozen_gt_exact_compact_indices/v1",
                            "gt_version": record["version"], "gt_sha256": record["gt_sha256"],
                            "session_sha256": record["input_sha256"], "fv": fv.tolist()})
    return samples, {"duplicates_removed": duplicates, "samples": len(samples)}
