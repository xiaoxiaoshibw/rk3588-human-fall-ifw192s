#!/usr/bin/env python3
"""Emit a reviewable unified diff of the four R4-changed files.

The human_fall_detection package is untracked, so git cannot diff it. This
script reconstructs the pre-R4 text from the exact reverse edit pairs applied
this round (asserting each applies once) and prints difflib unified diffs.
Read-only: it writes nothing to the source tree.
"""
import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
P = "src/human_fall_detection"
TARGETS = [
    f"{P}/core/calibration.py",
    f"{P}/core/node_runtime.py",
    f"{P}/tests/test_gl03_candidates_geometry.py",
]

OLD_LOAD = '''def _load_transform(transform):
    if not isinstance(transform, dict) or transform.get("status") == "unknown":
        raise GeometryCalibrationError("transform is unknown")
    matrix = validate_rotation(transform.get("rotation"))
    meters = _numeric_array(transform.get("translation_m"), (3,), "translation_m")
    return matrix, meters
'''

NEW_LOAD = OLD_LOAD + '''

def validate_known_transform(transform):
    """Return a deep-copied, fully qualified known transform, else raise.

    Numeric R/t alone is not a qualification (GL-03 G03): a known transform
    must carry explicit non-empty distinct frames, the canonical direction,
    metres, an explicit evidence source and a status consistent with that
    evidence, besides the rigid rotation/plausible translation checks. It
    reuses :func:`make_transform` as the one strict constructor, so a record
    that could never have been built is never treated as usable. The input is
    not mutated; the copy is what a caller may bind.
    """
    if not isinstance(transform, dict) or transform.get("status") == "unknown":
        raise GeometryCalibrationError("transform is unknown")
    if transform.get("units") != UNITS["length"]:
        raise GeometryCalibrationError(
            "transform units must be " + repr(UNITS["length"]))
    recovered = make_transform(transform.get("rotation"),
                               transform.get("translation_m"),
                               transform.get("from_frame"),
                               transform.get("to_frame"),
                               units=transform.get("units", "m"),
                               evidence=transform.get("evidence"),
                               note=transform.get("note"))
    if recovered["status"] != transform.get("status"):
        raise GeometryCalibrationError(
            "transform status disagrees with its evidence source")
    direction = transform.get("direction")
    if direction is not None and direction != recovered["direction"]:
        raise GeometryCalibrationError("transform direction is not supported")
    return copy.deepcopy(transform)
'''

NEW_RESOLVER = '''    The geometry artifact owns the installation transform: when it carries a
    known ``T_reference_lidar`` a standalone caller transform that disagrees
    with that record is a conflict and is never silently preferred; with no
    known artifact record a legal standalone transform keeps the legacy
    support. A full artifact is validated end-to-end first, so a damaged,
    newer-version or id-less parent can never supply reference coordinates; an
    old minimal calibration summary (no ``kind``) keeps the legacy path. The
    effective record itself must be fully qualified (frames/direction/units/
    status/evidence/R/t), not merely numerically loadable, and a record whose
    ``from_frame`` differs from the actual producing ``frame_id``, or whose
    ``to_frame`` disagrees with the declared ``frames.reference``, can never
    supply reference coordinates. Returns ``(record_or_None, reason_or_None)``
    with a deep-copied record; an unusable reference is reported as ``None``
    (and the caller publishes null reference fields) rather than raising, so
    the ordinary no-reference/source-only path is unchanged.
    """
    parent = calibration if isinstance(calibration, dict) else None
    if parent is not None and parent.get("kind") == KIND:
        try:
            parent = validate_geometry_calibration(copy.deepcopy(parent))
        except (GeometryCalibrationError, TypeError, AttributeError, KeyError):
            return None, "reference_calibration_invalid"
    canonical = calibration_reference_transform(parent)
    if canonical is not None:
        try:
            effective = validate_known_transform(canonical)
        except (GeometryCalibrationError, TypeError, ValueError):
            return None, "reference_transform_invalid"
        if isinstance(transform, dict) and transform.get("status") != "unknown" \\
                and not _same_transform_record(transform, effective):
            return None, "reference_transform_conflict"
    elif isinstance(transform, dict) and transform.get("status") != "unknown":
        try:
            effective = validate_known_transform(transform)
        except (GeometryCalibrationError, TypeError, ValueError):
            return None, "reference_transform_invalid"
    else:
        return None, None
    if isinstance(frame_id, str) and frame_id:
        recorded = effective.get("from_frame")
        if isinstance(recorded, str) and recorded and recorded != frame_id:
            return None, "reference_from_frame_mismatch"
    reference_frame = None
    if parent is not None:
        reference_frame = (parent.get("frames") or {}).get("reference")
    to_frame = effective.get("to_frame")
    if reference_frame and isinstance(to_frame, str) and to_frame \\
            and to_frame != reference_frame:
        return None, "reference_to_frame_mismatch"
    return effective, None
'''

OLD_RESOLVER = '''    The geometry artifact owns the installation transform: when it carries a
    known ``T_reference_lidar`` a standalone caller transform that disagrees
    with that record is a conflict and is never silently preferred; with no
    known artifact record a legal standalone transform keeps the legacy
    support. A record whose ``from_frame`` differs from the actual producing
    ``frame_id``, or whose ``to_frame`` disagrees with the declared
    ``frames.reference``, can never supply reference coordinates. Returns
    ``(record_or_None, reason_or_None)``; an unusable reference is reported as
    ``None`` (and the caller publishes null reference fields) rather than
    raising, so the ordinary no-reference/source-only path is unchanged.
    """
    canonical = calibration_reference_transform(calibration)
    if canonical is not None:
        effective = canonical
        if isinstance(transform, dict) and transform.get("status") != "unknown" \\
                and not _same_transform_record(transform, canonical):
            return None, "reference_transform_conflict"
    elif isinstance(transform, dict) and transform.get("status") != "unknown":
        effective = transform
    else:
        return None, None
    if isinstance(frame_id, str) and frame_id:
        recorded = effective.get("from_frame")
        if isinstance(recorded, str) and recorded and recorded != frame_id:
            return None, "reference_from_frame_mismatch"
    reference_frame = None
    if isinstance(calibration, dict):
        reference_frame = (calibration.get("frames") or {}).get("reference")
    to_frame = effective.get("to_frame")
    if reference_frame and isinstance(to_frame, str) and to_frame \\
            and to_frame != reference_frame:
        return None, "reference_to_frame_mismatch"
    try:
        _load_transform(effective)
    except (GeometryCalibrationError, TypeError, ValueError):
        return None, "reference_transform_invalid"
    return effective, None
'''

NEW_IMPORT = '''    from core.calibration import (build_geometry_calibration,
                                  calibration_reference_transform,
                                  ground_context_calibration,
                                  ground_context_from_calibration,
                                  resolve_reference_transform,
                                  validate_ground_derived,
                                  validate_geometry_calibration,
                                  _same_transform_record,
                                  _validate_ground_derived_consistency
                                  as validate_ground_derived_consistency_guard)
'''
OLD_IMPORT = '''    from core.calibration import (build_geometry_calibration,
                                  calibration_reference_transform,
                                  ground_context_calibration,
                                  ground_context_from_calibration,
                                  resolve_reference_transform,
                                  validate_ground_derived,
                                  validate_geometry_calibration,
                                  _validate_ground_derived_consistency
                                  as validate_ground_derived_consistency_guard)
'''

NEW_IMPORT2 = '''    from calibration import (build_geometry_calibration,
                             calibration_reference_transform,
                             ground_context_calibration,
                             ground_context_from_calibration,
                             resolve_reference_transform,
                             validate_ground_derived,
                             validate_geometry_calibration,
                             _same_transform_record,
                             _validate_ground_derived_consistency
                             as validate_ground_derived_consistency_guard)
'''
OLD_IMPORT2 = '''    from calibration import (build_geometry_calibration,
                             calibration_reference_transform,
                             ground_context_calibration,
                             ground_context_from_calibration,
                             resolve_reference_transform,
                             validate_ground_derived,
                             validate_geometry_calibration,
                             _validate_ground_derived_consistency
                             as validate_ground_derived_consistency_guard)
'''

NEW_STARTUP = '''        self.transform = transform
        if transform is not None \\
                and calibration_reference_transform(self.calibration) is not None:
            # A startup that supplies an explicit transform next to an artifact
            # that already owns T_reference_lidar must not silently discard the
            # explicit one: a disagreement is an explicit refusal here (GL-03
            # G03). Later reloads keep the artifact-authoritative behaviour and
            # adopt the new artifact's own T without being blocked by the old
            # standalone parameter.
            _binding, _reason = resolve_reference_transform(self.calibration,
                                                            transform)
            if _reason == "reference_transform_conflict":
                raise ValueError(
                    "explicit reference transform conflicts with the "
                    "calibration artifact; a full artifact owns its "
                    "T_reference_lidar")
        # Effective lidar->reference binding actually used by snapshots and
'''
OLD_STARTUP = '''        self.transform = transform
        # Effective lidar->reference binding actually used by snapshots and
'''

NEW_APPLY = '''            new_id = self._block_id(resolved_block)
            new_version = new_calibration.get("calibration_id")
            previous_reference = calibration_reference_transform(self.calibration)
            new_reference = calibration_reference_transform(new_calibration)
            same_reference = (previous_reference is None
                              and new_reference is None) \\
                or _same_transform_record(previous_reference, new_reference)
            if new_version == previous_version and not same_reference:
                # The same calibration id with a different actual reference
                # transform is a contradiction, not a reload: the old snapshot/
                # track eligibility was built with the old matrix and must not
                # silently continue under the new one (GL-03 G04/G05). Refuse
                # before any side effect; a new calibration id is required.
                raise ValueError(
                    "calibration id {!r} already has a different reference "
                    "transform; a new calibration id is required".format(
                        new_version))
            changed = (new_version != previous_version) or (new_id != previous_id)
'''
OLD_APPLY = '''            new_id = self._block_id(resolved_block)
            new_version = new_calibration.get("calibration_id")
            changed = (new_version != previous_version) or (new_id != previous_id)
'''

TEST_OLD_MARK = "class GroundGeometryTest(unittest.TestCase):"
TEST_BEFORE, TEST_AFTER = None, None


def reverse_edits(text, pairs):
    working = text
    for old, new in reversed(pairs):
        if new not in working:
            raise AssertionError("forward text not present: " + repr(new[:80]))
        working = working.replace(new, old, 1)
    return working


def main():
    PACKAGE = ROOT / P
    before = {}
    calibration = (PACKAGE / "core/calibration.py").read_text(encoding="utf-8")
    before[f"{P}/core/calibration.py"] = reverse_edits(
        calibration, [(OLD_LOAD, NEW_LOAD), (OLD_RESOLVER, NEW_RESOLVER)])
    node = (PACKAGE / "core/node_runtime.py").read_text(encoding="utf-8")
    before[f"{P}/core/node_runtime.py"] = reverse_edits(
        node, [(OLD_IMPORT, NEW_IMPORT), (OLD_IMPORT2, NEW_IMPORT2),
               (OLD_STARTUP, NEW_STARTUP), (OLD_APPLY, NEW_APPLY)])
    tests = (PACKAGE / "tests/test_gl03_candidates_geometry.py").read_text(
        encoding="utf-8")
    start = tests.index("class ReferenceQualificationTest")
    end = tests.index(TEST_OLD_MARK)
    added = tests[start:end]
    before[f"{P}/tests/test_gl03_candidates_geometry.py"] = \
        tests[:start] + tests[end:]
    for relative in TARGETS:
        current = (ROOT / relative).read_text(encoding="utf-8")
        old = before[relative]
        diff = difflib.unified_diff(
            old.splitlines(keepends=True), current.splitlines(keepends=True),
            fromfile=relative + " (R3)", tofile=relative + " (R4)")
        text = "".join(diff)
        if not text:
            raise AssertionError("no diff for " + relative)
        print(text)
    print("# added test class lines:", len(added.splitlines()))


if __name__ == "__main__":
    main()
