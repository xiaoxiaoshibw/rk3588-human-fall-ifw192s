"""Point-membership GT channel for TCMS-02 purity/recall (schema v1).

This closes the tooling gap recorded in
``docs/human_fall/evidence/2026-10-18_hfus_ai_gt_real_01_r1/CAPABILITY_GAP.md``:
the existing AI-GT tools label picked points, not a frame's source-row
membership. This tool only defines/validates/audits the channel and scores it
once labels exist. It never fabricates labels: no labels => metrics are null and
status is ``UNKNOWN``.

Schema ``hf_point_membership_v1``::

    {"schema": "hf_point_membership_v1",
     "sid": "cap_20261018_110029",
     "source": {"meta_sha256": "...", "points_sha256": "..."},
     "frame": 341,
     "labels": [{"source_row": 16782973, "label": "HUMAN"},
                {"source_row": 16782977, "label": "NON_HUMAN"},
                {"source_row": 16782978, "label": "UNCERTAIN"}],
     "meta": {"annotator": "...", "model_id": "...", "protocol": "AI_GT_PROTOCOL_V1",
              "blind": true}}

Scoring rules (frozen):
- The evaluated universe is ``predicted_rows ∪ HUMAN labels``. A predicted row
  without a label makes the result ``INCOMPLETE`` (it could be TP or FP; calling
  it FP would be fabricated). ``UNCERTAIN`` rows are reported and excluded.
- purity = TP / (TP + FP); recall = TP / (TP + FN); both null when the
  denominator is zero (never coerced to 0 or 1).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "hf_point_membership_v1"
LABELS = ("HUMAN", "NON_HUMAN", "UNCERTAIN")
FORBIDDEN_META_KEYS = {"candidates", "foreground", "predictions", "tracks", "skeleton",
                       "regions", "nodes", "overlay", "score", "labels"}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def validate_labels(doc):
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ValueError("schema must be " + SCHEMA)
    if not isinstance(doc.get("sid"), str) or not doc["sid"]:
        raise ValueError("sid is required")
    if not isinstance(doc.get("frame"), int) or doc["frame"] < 0:
        raise ValueError("frame must be a non-negative integer")
    source = doc.get("source")
    if not isinstance(source, dict) or not source.get("meta_sha256") or not source.get("points_sha256"):
        raise ValueError("source.meta_sha256 and source.points_sha256 are required")
    labels = doc.get("labels")
    if not isinstance(labels, list) or not labels:
        raise ValueError("labels must be a non-empty list")
    rows = set()
    for item in labels:
        if not isinstance(item, dict):
            raise ValueError("each label must be an object")
        row = item.get("source_row")
        if not isinstance(row, int) or row < 0:
            raise ValueError("source_row must be a non-negative integer")
        rows.add(row)
        if item.get("label") not in LABELS:
            raise ValueError("label must be one of " + "/".join(LABELS))
    return doc


def frame_bounds(meta_path, frame):
    meta = read(meta_path)
    frames = meta.get("frames")
    if not isinstance(frames, list) or not 0 <= frame < len(frames):
        raise ValueError("frame outside meta")
    entry = frames[frame]
    start = int(entry["offset_points"])
    return start, start + int(entry["count_points"])


def audit(labels_doc, meta_path=None):
    validate_labels(labels_doc)
    seen = {}
    conflicts = []
    for item in labels_doc["labels"]:
        seen.setdefault(item["source_row"], set()).add(item["label"])
    for row, values in seen.items():
        if len(values) > 1:
            conflicts.append({"source_row": row, "labels": sorted(values)})
    report = {"schema": SCHEMA, "sid": labels_doc["sid"], "frame": labels_doc["frame"],
              "label_count": len(labels_doc["labels"]),
              "counts": {name: sum(1 for item in labels_doc["labels"] if item["label"] == name)
                         for name in LABELS},
              "conflicts": conflicts, "binding": "DECLARED"}
    meta = labels_doc.get("meta") or {}
    leaked = sorted(set(meta) & FORBIDDEN_META_KEYS)
    report["forbidden_meta_keys"] = leaked
    if meta_path is not None:
        bounds = frame_bounds(meta_path, labels_doc["frame"])
        outside = [item["source_row"] for item in labels_doc["labels"]
                   if not bounds[0] <= item["source_row"] < bounds[1]]
        report["frame_bounds"] = list(bounds)
        report["outside_frame_rows"] = outside[:20]
        report["outside_frame_count"] = len(outside)
    report["ok"] = (not conflicts and not leaked
                    and not report.get("outside_frame_count"))
    return report


def score(labels_doc, predicted_doc):
    validate_labels(labels_doc)
    if not isinstance(predicted_doc, dict):
        raise ValueError("prediction must be an object")
    if predicted_doc.get("sid") != labels_doc["sid"] or predicted_doc.get("frame") != labels_doc["frame"]:
        raise ValueError("prediction sid/frame does not match labels")
    predicted = predicted_doc.get("rows")
    if not isinstance(predicted, list) or any(not isinstance(row, int) or row < 0 for row in predicted):
        raise ValueError("prediction rows must be non-negative integers")
    predicted = set(predicted)
    truth = {}
    for item in labels_doc["labels"]:
        row = item["source_row"]
        if row in truth and truth[row] != item["label"]:
            raise ValueError("conflicting labels for source_row %d" % row)
        truth[row] = item["label"]
    human = {row for row, label in truth.items() if label == "HUMAN"}
    non_human = {row for row, label in truth.items() if label == "NON_HUMAN"}
    uncertain = {row for row, label in truth.items() if label == "UNCERTAIN"}
    unlabeled = predicted - set(truth)
    tp = len(predicted & human)
    fp = len(predicted & non_human)
    fn = len(human - predicted)
    result = {
        "schema": SCHEMA, "sid": labels_doc["sid"], "frame": labels_doc["frame"],
        "counts": {"TP": tp, "FP": fp, "FN": fn,
                   "uncertain_predicted": len(predicted & uncertain),
                   "unlabeled_predicted": len(unlabeled)},
        "coverage": {"labeled_rows": len(truth), "predicted_rows": len(predicted),
                     "unlabeled_predicted": len(unlabeled)},
        "purity": (tp / (tp + fp)) if (tp + fp) else None,
        "recall": (tp / (tp + fn)) if (tp + fn) else None,
        "status": "SCORED" if not unlabeled else "INCOMPLETE",
    }
    if unlabeled:
        result["purity"] = None
        result["recall"] = None
        result["reason"] = "UNLABELED_PREDICTED_ROWS"
    if not human and not predicted:
        result["status"] = "INCOMPLETE"
        result["reason"] = "EMPTY_UNIVERSE"
        result["purity"] = None
        result["recall"] = None
    return result


def selfcheck(out):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError("output already exists")
    out.mkdir(parents=True)
    source = {"meta_sha256": "0" * 64, "points_sha256": "1" * 64}
    labels = {"schema": SCHEMA, "sid": "SYNTHETIC", "source": source, "frame": 0,
              "labels": [{"source_row": row, "label": "HUMAN"} for row in range(10)]
                        + [{"source_row": row, "label": "NON_HUMAN"} for row in range(10, 20)]
                        + [{"source_row": 20, "label": "UNCERTAIN"}]}
    predicted = {"sid": "SYNTHETIC", "frame": 0, "rows": [0, 1, 2, 3, 4, 5, 10, 11, 20]}
    result = score(labels, predicted)
    checks = {
        "tp": result["counts"]["TP"] == 6,
        "fp": result["counts"]["FP"] == 2,
        "fn": result["counts"]["FN"] == 4,
        "purity": abs(result["purity"] - 0.75) < 1e-12,
        "recall": abs(result["recall"] - 0.6) < 1e-12,
        "scored": result["status"] == "SCORED",
    }
    incomplete = score({"schema": SCHEMA, "sid": "SYNTHETIC", "source": source, "frame": 0,
                        "labels": [{"source_row": 0, "label": "HUMAN"}]},
                       {"sid": "SYNTHETIC", "frame": 0, "rows": [0, 1]})
    checks["incomplete_is_null"] = (incomplete["status"] == "INCOMPLETE"
                                    and incomplete["purity"] is None and incomplete["recall"] is None)
    conflict = {"schema": SCHEMA, "sid": "SYNTHETIC", "source": source, "frame": 0,
                "labels": [{"source_row": 1, "label": "HUMAN"},
                           {"source_row": 1, "label": "NON_HUMAN"}]}
    checks["conflict_detected"] = not audit(conflict)["ok"]
    no_labels = {"schema": SCHEMA, "sid": "SYNTHETIC", "source": source, "frame": 0, "labels": []}
    try:
        validate_labels(no_labels)
        checks["empty_rejected"] = False
    except ValueError:
        checks["empty_rejected"] = True
    result.update(kind="point_membership_selfcheck", checks=checks,
                  ok=all(checks.values()))
    write(out / "SELFCHECK.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("validate")
    p.add_argument("--labels", required=True)
    p = sub.add_parser("audit")
    p.add_argument("--labels", required=True)
    p.add_argument("--meta")
    p.add_argument("--out")
    p = sub.add_parser("score")
    p.add_argument("--labels", required=True)
    p.add_argument("--pred", required=True)
    p.add_argument("--out")
    p = sub.add_parser("selfcheck")
    p.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.mode == "validate":
        validate_labels(read(args.labels))
        print("VALID")
        return 0
    if args.mode == "audit":
        result = audit(read(args.labels), args.meta)
    elif args.mode == "score":
        result = score(read(args.labels), read(args.pred))
    else:
        result = selfcheck(args.out)
        args.out = None          # selfcheck already wrote SELFCHECK.json
    if getattr(args, "out", None):
        write(args.out, result)
    print(json.dumps({key: result[key] for key in result
                      if key in ("status", "ok", "counts", "purity", "recall", "conflicts")},
                     ensure_ascii=False))
    return 0 if result.get("ok", result.get("status") == "SCORED") else 1


if __name__ == "__main__":
    sys.exit(main())
