"""Independent source-row/stat recomputation and submission scope helpers."""
import ast
import collections
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PACKAGE = ROOT / "src/human_fall_detection"
sys.path.insert(0, str(PACKAGE))
from core.capture_input import load_adapted, select_group_region


def main():
    report = json.loads((OUT / "12_real_final/diagnostic.json").read_text(encoding="utf-8"))
    manifest, points = load_adapted(str(ROOT / "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz"))
    mapped = collections.defaultdict(list)
    with (OUT / "12_real_final/source_indices.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            group = manifest["frame_groups"][row["frame_group"]]
            pooled = row["pooled_row"]
            assert group["rows"][0] <= pooled < group["rows"][1]
            assert row["frame_row"] == pooled - group["rows"][0]
            assert row["frame_ordinal"] == group["ordinal"] and row["seq"] == group["seq"]
            assert row["source_xyz_m"] == points[pooled].astype(float).tolist()
            mapped[(row["box"], row["frame_group"])].append(row)
    draft = report["approved_draft"]
    boxes = {"FIT": draft["fit_region"]["bounds"]}
    boxes.update({r["region_id"]: r["bounds"] for r in draft["validation_regions"]})
    normal = np.asarray(report["observation_plane"]["normal"])
    offset = report["observation_plane"]["offset_m"]
    for record in report["box_frame_records"]:
        key = (record["box"], record["frame_group"])
        selector = dict(boxes[key[0]], frame_group=key[1])
        rows = select_group_region(points, manifest, selector)
        assert rows.tolist() == [row["pooled_row"] for row in mapped[key]]
        stats = record["stats"]
        assert len(rows) == stats["count"]
        assert sum(cell["stats"]["count"] for cell in record["source_xyz_bins"]) == len(rows)
        signed = points[rows].astype(float) @ normal + offset
        assert abs(stats["rms_m"] - float(np.sqrt(np.mean(signed ** 2)))) < 1e-12
        assert abs(stats["p95_m"] - float(np.percentile(np.abs(signed), 95))) < 1e-12
        assert stats["support_count"] == int(np.count_nonzero(np.abs(signed) <= report["support_tail_threshold_m"]))
        assert record["display_count"] <= report["display_budget_per_box_frame"]
        assert record["display_rows"] == [row["pooled_row"] for row in mapped[key] if row["displayed"]]
        assert np.allclose(signed, [row["signed_residual_m"] for row in mapped[key]], atol=1e-12, rtol=0)
    old = json.loads((OUT / "05_real_diagnostic/diagnostic.json").read_text(encoding="utf-8"))
    for key in ("box_frame_records", "temporal", "experiments"):
        assert old[key] == report[key], key
    paths = [PACKAGE / "core/ground_diagnostics.py", PACKAGE / "scripts/diagnose_gli04_geometry.py",
             PACKAGE / "tests/test_gli04_geometry.py", OUT / "research_01/search_prototype.py",
             OUT / "research_01/experiment.py"]
    imports = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 8))
        imports[str(path)] = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(name and any(term in name.lower() for term in ("ros", "yaml", "browser"))
                   for name in imports[str(paths[0])])
    result = {"sidecar_rows": sum(len(rows) for rows in mapped.values()),
              "box_frame_records": len(report["box_frame_records"]), "source_mapping_and_full_stats": "PASS",
              "initial_final_reproducibility": "PASS", "python38_AST": "PASS", "imports": imports,
              "local_python": sys.version, "local_numpy": np.__version__, "board_run": False}
    with (OUT / "14_audit_results.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in result.items() if key != "imports"}))


if __name__ == "__main__":
    main()
