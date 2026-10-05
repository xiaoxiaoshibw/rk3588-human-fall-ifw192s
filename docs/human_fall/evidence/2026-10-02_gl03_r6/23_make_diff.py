#!/usr/bin/env python3
"""GL-03 R6: reconstruct the pre-R6 (R5-submitted) sources by exact reverse
editing and emit a verified unified diff. Fails when a reverse edit or the
reconstructed SHA-256 does not match the R5 submission manifest."""
import difflib
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
R5 = {
    "src/human_fall_detection/core/calibration.py":
        "1c1d40ef908e07a4d3979d19228dd520e0c2d299cf429710a9d2084233b6bbad",
    "src/human_fall_detection/core/node_runtime.py":
        "889ead5e24ea9553cb728d403fc2e47fd42634ba15a920124314225b0f13b06f",
    "src/human_fall_detection/core/lidar_candidates.py":
        "318abc786f49bb5d87e0a1e2030c017a2e489d302a038a814e56203fdd5bf1c5",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py":
        "6c0ce2f646462f4095d23436a495bb2fe0cf10b813e70766b270a5e60d9c6399",
}

R6_BLOCK = r'''# Constructor-exclusive full-product blocks (GL-03 G03 input classification):
# a complete geometry-calibration artifact always carries these, so their
# presence marks a full product whose missing/null ``kind`` is damage, not a
# legacy minimal summary. The summary-visible fields (calibration_id,
# schema_version, ground_status, ground_derived_id, frames, transforms, note)
# are deliberately not markers, and unknown ordinary extensions are not
# blacklisted.
FULL_ARTIFACT_KEYS = ("units", "created_at_utc", "rotations", "verification",
                      "status", "input", "ground", "ground_derived",
                      "sensor_height_m")


def _has_full_artifact_shape(calibration):
    return any(key in calibration for key in FULL_ARTIFACT_KEYS)


def resolve_reference_transform(calibration=None, transform=None, frame_id=None):
    """Effective lidar->reference transform for a producing frame, or ``None``.

    The geometry artifact owns the installation transform: when it carries a
    known ``T_reference_lidar`` a standalone caller transform that disagrees
    with that record is a conflict and is never silently preferred; with no
    known artifact record a legal standalone transform keeps the legacy
    support. Inputs are classified before validation: a supported artifact
    ``kind`` or the constructor-exclusive full-product blocks force the full
    validator, so deleting/nulling the ``kind`` of a complete product or an
    unsupported schema/identity can never be downgraded to the legacy path; an
    explicit non-artifact ``kind`` is refused. Only a true minimal summary (no
    full-product block, no ``kind``, supported-or-absent ``schema_version``)
    keeps the legacy path. The effective record itself must be fully qualified
    (frames/direction/units/status/evidence/R/t), not merely numerically
    loadable, and a record whose ``from_frame`` differs from the actual
    producing ``frame_id`` or from the parent's declared ``frames.lidar``, or
    whose ``to_frame`` disagrees with the declared ``frames.reference``, can
    never supply reference coordinates. Returns
    ``(record_or_None, reason_or_None)``
    with a deep-copied record; an unusable reference is reported as ``None``
    (and the caller publishes null reference fields) rather than raising, so
    the ordinary no-reference/source-only path is unchanged.
    """
    parent = calibration if isinstance(calibration, dict) else None
    if parent is not None:
        kind = parent.get("kind")
        if kind == KIND or (kind is None and _has_full_artifact_shape(parent)):
            # A supported kind -- or a complete product whose kind was removed/
            # nulled -- must pass the supported validator end-to-end; a
            # different/unknown schema or a damaged identity is refused, never
            # silently treated as legacy (GL-03 G03).
            try:
                parent = validate_geometry_calibration(copy.deepcopy(parent))
            except (GeometryCalibrationError, TypeError, AttributeError,
                    KeyError):
                return None, "reference_calibration_invalid"
        elif kind is not None:
            # Explicit non-artifact kind: a damaged/foreign record, never a
            # legacy minimal summary (which has no ``kind``).
            return None, "reference_calibration_invalid"
        elif "schema_version" in parent:
            # True minimal summary: an explicitly present version must be the
            # one this module supports; a missing version keeps the old
            # compatibility path (a 99/True/float version is not v1).
            version = parent.get("schema_version")
            if isinstance(version, bool) or not isinstance(version, int) \
                    or version != SCHEMA_VERSION:
                return None, "reference_calibration_invalid"
'''

R5_BLOCK = r'''def resolve_reference_transform(calibration=None, transform=None, frame_id=None):
    """Effective lidar->reference transform for a producing frame, or ``None``.

    The geometry artifact owns the installation transform: when it carries a
    known ``T_reference_lidar`` a standalone caller transform that disagrees
    with that record is a conflict and is never silently preferred; with no
    known artifact record a legal standalone transform keeps the legacy
    support. A full artifact is validated end-to-end first, so a damaged,
    newer-version or id-less parent can never supply reference coordinates; an
    old minimal calibration summary (no ``kind``) keeps the legacy path, while
    a record that carries an explicit non-artifact ``kind`` is refused instead
    of being mistaken for that legacy summary. The effective record itself must
    be fully qualified (frames/direction/units/status/evidence/R/t), not merely
    numerically loadable, and a record whose ``from_frame`` differs from the
    actual producing ``frame_id`` or from the parent's declared ``frames.lidar``,
    or whose ``to_frame`` disagrees with the declared ``frames.reference``, can
    never supply reference coordinates. Returns
    ``(record_or_None, reason_or_None)``
    with a deep-copied record; an unusable reference is reported as ``None``
    (and the caller publishes null reference fields) rather than raising, so
    the ordinary no-reference/source-only path is unchanged.
    """
    parent = calibration if isinstance(calibration, dict) else None
    if parent is not None and parent.get("kind") is not None \
            and parent.get("kind") != KIND:
        # An explicit non-artifact kind is a damaged/foreign record, never a
        # legacy minimal summary (which has no ``kind``): it must not bypass
        # the supported-parent validation below (GL-03 G03).
        return None, "reference_calibration_invalid"
    if parent is not None and parent.get("kind") == KIND:
        try:
            parent = validate_geometry_calibration(copy.deepcopy(parent))
        except (GeometryCalibrationError, TypeError, AttributeError, KeyError):
            return None, "reference_calibration_invalid"
'''


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reverse(relative, text):
    if relative.endswith("core/calibration.py"):
        assert text.count(R6_BLOCK) == 1, relative
        text = text.replace(R6_BLOCK, R5_BLOCK)
    elif relative.endswith("test_gl03_candidates_geometry.py"):
        marker = ("\n    def test_full_artifact_missing_kind_cannot_hide_"
                  "behind_legacy_path")
        start = text.index(marker)
        end = text.index("\n\nclass GroundGeometryTest", start)
        text = text[:start] + text[end:]
    return text


report = []
diff_text = []
for relative, sha5 in R5.items():
    current = (ROOT / relative).read_text(encoding="utf-8")
    old = reverse(relative, current)
    digest = sha(old)
    report.append("{} reconstructed {} expected {} {}".format(
        relative, digest, sha5, "OK" if digest == sha5 else "MISMATCH"))
    assert digest == sha5, relative
    diff_text.extend(difflib.unified_diff(
        old.splitlines(keepends=True), current.splitlines(keepends=True),
        fromfile="a/" + relative, tofile="b/" + relative))
(HERE / "23_reconstruct_check.txt").write_text(
    "\n".join(report) + "\n", encoding="utf-8")
(HERE / "23_source_diff.patch").write_text(
    "".join(diff_text), encoding="utf-8")
print("\n".join(report))
print("R6 diff lines:", len(diff_text))
sys.exit(0)
