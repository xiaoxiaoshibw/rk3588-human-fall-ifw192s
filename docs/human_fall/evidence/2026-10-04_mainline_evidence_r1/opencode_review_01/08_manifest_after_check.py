"""GL-E01 R1 manifest/source SHA after the review (start/end freeze proof)."""
import hashlib
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent
RUN = OUT.parent
ROOT = OUT.parents[4]
MANIFEST = RUN / "09_submission_manifest.json"
FROZEN = ["captures/remote/cap_20261002_163621/meta.json",
          "captures/remote/cap_20261002_163621/points.bin",
          "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz",
          "src/human_capture/core/bag2session.py",
          "src/human_fall_detection/core/capture_input.py",
          "docs/human_fall/GLE01_ACCEPTANCE.md",
          "docs/human_fall/returns/GL-E01.md"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    start = json.loads((OUT / "06_manifest_scope_check.json").read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_sha_after = sha(MANIFEST)
    frozen = {rel: dict(actual=sha(ROOT / rel),
                        in_manifest=man["files"].get(rel),
                        match=man["files"].get(rel) == sha(ROOT / rel))
              for rel in FROZEN}
    # EXPECTED_SHA inside the author/independent remote scripts is unchanged.
    src_scripts = {}
    for rel in ["docs/human_fall/evidence/2026-10-04_mainline_evidence_r1/03_read_bag_chain.py",
                "docs/human_fall/evidence/2026-10-04_mainline_evidence_r1/opencode_review_01/01_remote_raw_probe.py"]:
        src_scripts[rel] = sha(ROOT / rel)
    result = dict(
        kind="gle01_r1_manifest_after", schema=1,
        manifest_sha256_start=start["manifest_sha256"],
        manifest_sha256_after=manifest_sha_after,
        manifest_unchanged=start["manifest_sha256"] == manifest_sha_after,
        head_now=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True).strip(),
        frozen=frozen, frozen_all_match=all(v["match"] for v in frozen.values()),
        review_scripts_sha256=src_scripts,
        source_start_end_note="manifest 'start' is the submission-recorded sha; "
                              "'after' recomputed post-review")
    (OUT / "08_manifest_after_check.json").write_text(json.dumps(result, indent=2),
                                                      encoding="utf-8")
    print(json.dumps(dict(manifest_unchanged=result["manifest_unchanged"],
                          frozen_all_match=result["frozen_all_match"],
                          manifest_after=manifest_sha_after[:16],
                          head=result["head_now"][:9])))


if __name__ == "__main__":
    main()
