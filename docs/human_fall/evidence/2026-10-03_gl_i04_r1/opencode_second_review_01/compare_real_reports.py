"""Independent comparison of author real report vs reviewer rerun (read-only)."""
import hashlib
import json
from pathlib import Path

RUN = Path(r"D:/Code/ldiar/docs/human_fall/evidence/2026-10-03_gl_i04_r1")
A = RUN / "12_real_final"
B = RUN / "opencode_second_review_01/12_real_final_rerun"


def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


out = {}
for name in ("diagnostic.json", "source_indices.jsonl", "local_source.svg", "diagnostic.md"):
    out[name] = {"author": sha(A / name), "rerun": sha(B / name),
                 "equal": sha(A / name) == sha(B / name)}

a = json.loads((A / "diagnostic.json").read_text(encoding="utf-8"))
b = json.loads((B / "diagnostic.json").read_text(encoding="utf-8"))
keys = sorted(set(a) | set(b))
diff = [k for k in keys if a.get(k) != b.get(k)]
out["top_level_key_diffs"] = diff
out["reproducible_all_fields"] = not diff
# Core semantic fields used by acceptance.
for k in ("experiments", "temporal", "box_frame_records", "observation_plane",
          "PCA_reference", "rotation", "conditional_26deg", "extrinsic",
          "sidecar_count", "physical_verified", "tail_identity", "spatial_bins"):
    out.setdefault("field_equal", {})[k] = a.get(k) == b.get(k)
print(json.dumps(out, indent=2))
