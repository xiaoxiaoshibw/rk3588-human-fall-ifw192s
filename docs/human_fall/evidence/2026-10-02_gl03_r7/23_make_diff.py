#!/usr/bin/env python3
"""GL-03 R7: reconstruct the pre-R7 (R6-submitted) sources by exact reverse
editing and emit a verified unified diff. Fails when a reverse edit or the
reconstructed SHA-256 does not match the R6 submission manifest."""
import difflib
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
R6 = {
    "src/human_fall_detection/core/calibration.py":
        "913cc2df8f87965e9060789394b90a3d41a82b896a14264dc6788a438d50090c",
    "src/human_fall_detection/core/lidar_candidates.py":
        "318abc786f49bb5d87e0a1e2030c017a2e489d302a038a814e56203fdd5bf1c5",
    "src/human_fall_detection/core/node_runtime.py":
        "889ead5e24ea9553cb728d403fc2e47fd42634ba15a920124314225b0f13b06f",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py":
        "63eabfd5c1970e2046cb9419f57381815a1621af677d0395d56e30ef426c2a8d",
}

CALIBRATION = [
    (r'''def calibration_reference_transform(calibration):
    """The artifact-owned lidar->reference transform, or None when unknown.

    A non-object ``transforms`` container or child record yields ``None`` here
    rather than a raw ``AttributeError``; structural qualification refuses such
    damage before a reference binding is consumed, so this is only a safeguard.
    A legal ``unknown``/absent record keeps the original no-canonical meaning.
    """
    if not isinstance(calibration, dict):
        return None
    transforms = calibration.get("transforms")
    if not isinstance(transforms, dict):
        return None
    record = transforms.get("T_reference_lidar")
    if isinstance(record, dict) and record.get("status") != "unknown":
        return record
    return None
''',
     r'''def calibration_reference_transform(calibration):
    """The artifact-owned lidar->reference transform, or None when unknown."""
    if not isinstance(calibration, dict):
        return None
    record = (calibration.get("transforms") or {}).get("T_reference_lidar")
    if isinstance(record, dict) and record.get("status") != "unknown":
        return record
    return None
'''),
    (r'''def _has_full_artifact_shape(calibration):
    return any(key in calibration for key in FULL_ARTIFACT_KEYS)


def _legacy_summary_reason(summary):
    """Reason a legacy minimal summary is unusable, else ``None``.

    A true summary (no full-product block, no ``kind``) keeps the original
    compatibility semantics: the optional containers and frame labels may be
    absent/``None`` (an empty object also means "undeclared"), and an absent or
    legal-``unknown`` canonical child keeps the standalone fallback. But every
    *declared* field must have its declared type -- a container is an object, a
    frame name is a non-empty string and the canonical child is an object -- and
    the explicitly present ``schema_version`` must be the supported one. A
    damaged container/child is refused here instead of surfacing a raw
    ``AttributeError`` in a later consumer, and is never mistaken for "no
    canonical record" (which would wrongly re-enable the standalone fallback).
    """
    if "schema_version" in summary:
        version = summary.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int) \
                or version != SCHEMA_VERSION:
            return "reference_calibration_invalid"
    frames = summary.get("frames")
    if frames is not None and not isinstance(frames, dict):
        return "reference_calibration_invalid"
    if isinstance(frames, dict):
        for label in ("lidar", "reference"):
            if label in frames:
                value = frames.get(label)
                if value is not None \
                        and (not isinstance(value, str) or not value):
                    return "reference_calibration_invalid"
    transforms = summary.get("transforms")
    if transforms is not None and not isinstance(transforms, dict):
        return "reference_calibration_invalid"
    if isinstance(transforms, dict) and "T_reference_lidar" in transforms:
        record = transforms.get("T_reference_lidar")
        if record is not None and not isinstance(record, dict):
            return "reference_calibration_invalid"
    return None


def resolve_reference_transform(calibration=None, transform=None, frame_id=None):
''',
     r'''def _has_full_artifact_shape(calibration):
    return any(key in calibration for key in FULL_ARTIFACT_KEYS)


def resolve_reference_transform(calibration=None, transform=None, frame_id=None):
'''),
    (r'''    explicit non-artifact ``kind`` is refused. Only a true minimal summary (no
    full-product block, no ``kind``, supported-or-absent ``schema_version``,
    declared containers/labels/child of the declared types) keeps the legacy
    path. The effective record itself must be fully qualified''',
     r'''    explicit non-artifact ``kind`` is refused. Only a true minimal summary (no
    full-product block, no ``kind``, supported-or-absent ``schema_version``)
    keeps the legacy path. The effective record itself must be fully qualified'''),
    (r'''        elif kind is not None:
            # Explicit non-artifact kind: a damaged/foreign record, never a
            # legacy minimal summary (which has no ``kind``).
            return None, "reference_calibration_invalid"
        else:
            # True minimal summary: the explicitly present version and every
            # declared container/label/canonical child must have their declared
            # types before any consumer reads them (GL-03 G03).
            reason = _legacy_summary_reason(parent)
            if reason is not None:
                return None, reason
''',
     r'''        elif kind is not None:
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
'''),
    (r'''    declared_lidar = None
    reference_frame = None
    if parent is not None and isinstance(parent.get("frames"), dict):
        declared_lidar = parent["frames"].get("lidar")
        reference_frame = parent["frames"].get("reference")
    if isinstance(declared_lidar, str) and declared_lidar:
        # Cross-record binding: the producing ``from`` frame cannot contradict
        # the parent artifact's declared lidar frame (GL-03 G03), even when the
        # caller supplies no frame_id (node startup/reload binding). A declared
        # non-string label was already refused by the structural guard, so it
        # can never silently skip this comparison.
        declared = effective.get("from_frame")
        if isinstance(declared, str) and declared and declared != declared_lidar:
            return None, "reference_from_frame_mismatch"
    to_frame = effective.get("to_frame")
''',
     r'''    declared_lidar = None
    if parent is not None:
        declared_lidar = (parent.get("frames") or {}).get("lidar")
    if isinstance(declared_lidar, str) and declared_lidar:
        # Cross-record binding: the producing ``from`` frame cannot contradict
        # the parent artifact's declared lidar frame (GL-03 G03), even when the
        # caller supplies no frame_id (node startup/reload binding).
        declared = effective.get("from_frame")
        if isinstance(declared, str) and declared and declared != declared_lidar:
            return None, "reference_from_frame_mismatch"
    reference_frame = None
    if parent is not None:
        reference_frame = (parent.get("frames") or {}).get("reference")
    to_frame = effective.get("to_frame")
'''),
    (r'''    frames = artifact.get("frames")
    if not isinstance(frames, dict):
        raise GeometryCalibrationError("frames must be an object")
    lidar_frame = frames.get("lidar")
    if not isinstance(lidar_frame, str) or not lidar_frame:
        raise GeometryCalibrationError("frames.lidar must be a non-empty string")
    reference_frame = frames.get("reference")
    if reference_frame is not None \
            and (not isinstance(reference_frame, str) or not reference_frame):
        raise GeometryCalibrationError(
            "frames.reference must be null or a non-empty string")
    for field in ("transforms", "rotations"):
        container = artifact.get(field)
        if container is not None and not isinstance(container, dict):
            raise GeometryCalibrationError(field + " must be an object")
    for name, record in (artifact.get("transforms") or {}).items():
        if not isinstance(record, dict):
            raise GeometryCalibrationError(
                "transform record must be an object: " + str(name))
        if record.get("status") != "unknown":
            recovered = make_transform(record.get("rotation"),
                                       record.get("translation_m"),
                                       record.get("from_frame"),
                                       record.get("to_frame"),
                                       units=record.get("units", "m"),
                                       evidence=record.get("evidence"),
                                       note=record.get("note"))
            if recovered["status"] != record.get("status"):
                raise GeometryCalibrationError("transform status mismatch: " + name)
        else:
            _check_distinct_frames(record.get("from_frame"), record.get("to_frame"))
    for name, record in (artifact.get("rotations") or {}).items():
        if not isinstance(record, dict):
            raise GeometryCalibrationError(
                "rotation record must be an object: " + str(name))
        if record.get("status") != "unknown":
''',
     r'''    frames = artifact.get("frames")
    if not isinstance(frames, dict) or not frames.get("lidar"):
        raise GeometryCalibrationError("frames.lidar is required")
    for name, record in (artifact.get("transforms") or {}).items():
        if record.get("status") != "unknown":
            recovered = make_transform(record.get("rotation"),
                                       record.get("translation_m"),
                                       record.get("from_frame"),
                                       record.get("to_frame"),
                                       units=record.get("units", "m"),
                                       evidence=record.get("evidence"),
                                       note=record.get("note"))
            if recovered["status"] != record.get("status"):
                raise GeometryCalibrationError("transform status mismatch: " + name)
        else:
            _check_distinct_frames(record.get("from_frame"), record.get("to_frame"))
    for name, record in (artifact.get("rotations") or {}).items():
        if record.get("status") != "unknown":
'''),
]

LIDAR_CANDIDATES = [
    (r'''    # A damaged/non-object parent ``frames`` block was already refused as an
    # unusable reference binding; the coordinate metadata must stay readable
    # (null) instead of raising here (GL-03 G03).
    declared_frames = calibration.get("frames") \
        if isinstance(calibration, dict) else None
    reference_label = declared_frames.get("reference") \
        if isinstance(declared_frames, dict) else None
    coordinate = {
        "source_frame": frame_id,
        "reference_frame": reference_label or None,
''',
     r'''    coordinate = {
        "source_frame": frame_id,
        "reference_frame": (calibration or {}).get("frames", {}).get("reference")
        if calibration and calibration.get("frames", {}).get("reference") else None,
'''),
]

PATCHES = {
    "src/human_fall_detection/core/calibration.py": CALIBRATION,
    "src/human_fall_detection/core/lidar_candidates.py": LIDAR_CANDIDATES,
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reverse(relative, text):
    for old, new in PATCHES.get(relative, []):
        count = text.count(old)
        assert count == 1, (relative, count, old[:70])
        text = text.replace(old, new)
    if relative.endswith("test_gl03_candidates_geometry.py"):
        marker = "\n    def test_full_parent_labels_must_be_frame_names"
        start = text.index(marker)
        end = text.index("\n\nclass GroundGeometryTest", start)
        text = text[:start] + text[end:]
    return text


report = []
diff_text = []
for relative, sha6 in R6.items():
    current = (ROOT / relative).read_text(encoding="utf-8")
    old = reverse(relative, current)
    digest = sha(old)
    report.append("{} reconstructed {} expected {} {}".format(
        relative, digest, sha6, "OK" if digest == sha6 else "MISMATCH"))
    assert digest == sha6, relative
    diff_text.extend(difflib.unified_diff(
        old.splitlines(keepends=True), current.splitlines(keepends=True),
        fromfile="a/" + relative, tofile="b/" + relative))
(HERE / "23_reconstruct_check.txt").write_text(
    "\n".join(report) + "\n", encoding="utf-8")
(HERE / "23_source_diff.patch").write_text(
    "".join(diff_text), encoding="utf-8")
print("\n".join(report))
print("R7 diff lines:", len(diff_text))
sys.exit(0)
