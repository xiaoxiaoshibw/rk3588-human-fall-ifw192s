#!/usr/bin/env python3
"""GL-03 R5: reconstruct the pre-R5 (R4-submitted) files by exact reverse
editing and emit a verified unified diff. Fails when a reverse edit or the
reconstructed SHA-256 does not match the R4 submission manifest."""
import difflib
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
R4 = {
    "src/human_fall_detection/core/calibration.py":
        "a2d06194248dfeee404fa9ec412d295876dd9318c26850540e800737a070ac24",
    "src/human_fall_detection/core/node_runtime.py":
        "9bd65ff9adf82b520cb588d234cb75b69418a25febb7b2e7b6ef124aec3e15b8",
    "src/human_fall_detection/tests/test_gl03_candidates_geometry.py":
        "1e7edb6b72b6ff8ad356231988524fdfd568856f28edcda3747feabc6072842b",
}

CALIBRATION = [
    (r"""    old minimal calibration summary (no ``kind``) keeps the legacy path, while
    a record that carries an explicit non-artifact ``kind`` is refused instead
    of being mistaken for that legacy summary. The effective record itself must
    be fully qualified (frames/direction/units/status/evidence/R/t), not merely
    numerically loadable, and a record whose ``from_frame`` differs from the
    actual producing ``frame_id`` or from the parent's declared ``frames.lidar``,
    or whose ``to_frame`` disagrees with the declared ``frames.reference``, can
    never supply reference coordinates. Returns
    ``(record_or_None, reason_or_None)``
""",
     r"""    old minimal calibration summary (no ``kind``) keeps the legacy path. The
    effective record itself must be fully qualified (frames/direction/units/
    status/evidence/R/t), not merely numerically loadable, and a record whose
    ``from_frame`` differs from the actual producing ``frame_id``, or whose
    ``to_frame`` disagrees with the declared ``frames.reference``, can never
    supply reference coordinates. Returns ``(record_or_None, reason_or_None)``
"""),
    (r"""    if parent is not None and parent.get("kind") is not None \
            and parent.get("kind") != KIND:
        # An explicit non-artifact kind is a damaged/foreign record, never a
        # legacy minimal summary (which has no ``kind``): it must not bypass
        # the supported-parent validation below (GL-03 G03).
        return None, "reference_calibration_invalid"
    if parent is not None and parent.get("kind") == KIND:
""",
     r"""    if parent is not None and parent.get("kind") == KIND:
"""),
    (r"""    if isinstance(frame_id, str) and frame_id:
        declared = effective.get("from_frame")
        if isinstance(declared, str) and declared and declared != frame_id:
            return None, "reference_from_frame_mismatch"
    declared_lidar = None
    if parent is not None:
        declared_lidar = (parent.get("frames") or {}).get("lidar")
    if isinstance(declared_lidar, str) and declared_lidar:
        # Cross-record binding: the producing ``from`` frame cannot contradict
        # the parent artifact's declared lidar frame (GL-03 G03), even when the
        # caller supplies no frame_id (node startup/reload binding).
        declared = effective.get("from_frame")
        if isinstance(declared, str) and declared and declared != declared_lidar:
            return None, "reference_from_frame_mismatch"
""",
     r"""    if isinstance(frame_id, str) and frame_id:
        recorded = effective.get("from_frame")
        if isinstance(recorded, str) and recorded and recorded != frame_id:
            return None, "reference_from_frame_mismatch"
"""),
]

PROSPECTIVE = r'''    def _prospective_reference_binding(self, calibration):
        """Resolve the effective reference binding for a candidate artifact.

        A full artifact that owns a known ``T_reference_lidar`` is authoritative:
        a reload adopts the new artifact's transform and never publishes a new
        calibration id with the old matrix. Without a known artifact record the
        *fixed startup copy* of the standalone transform keeps the legacy
        support; the caller's live dict is never re-read (GL-03 G05). The
        returned record is validated/deep-copied by the shared resolver.
        """
        standalone = None if calibration_reference_transform(calibration) \
            else self.transform
        return resolve_reference_transform(calibration, standalone)

    def _resolve_reference_binding(self):
        """Bind the effective reference transform for the live artifact."""
        return self._prospective_reference_binding(self.calibration)
'''

ORIGINAL_BINDING = r'''    def _resolve_reference_binding(self):
        """Bind the artifact-owned reference transform, else the standalone one.

        A full artifact that owns a known ``T_reference_lidar`` is authoritative:
        on a context reload the new artifact's transform replaces any earlier
        caller-supplied record (the core is unbound from the caller and never
        publishes a new calibration id with the old matrix). Without a known
        artifact record the legal standalone transform keeps its legacy support.
        """
        standalone = None if calibration_reference_transform(self.calibration) \
            else self.transform
        return resolve_reference_transform(self.calibration, standalone)
'''

NODE_RUNTIME = [
    (r"""import copy
import hashlib
""",
     r"""import hashlib
"""),
    (r"""        # The standalone caller transform is frozen (deep-copied) at the
        # node's ownership boundary: a later in-place caller edit is not a
        # reload authorization, so every reload may only re-read this fixed
        # copy, never the caller's live dict (GL-03 G05).
        self.transform = copy.deepcopy(transform) if transform is not None else None
        if self.transform is not None \
                and calibration_reference_transform(self.calibration) is not None:
""",
     r"""        self.transform = transform
        if transform is not None \
                and calibration_reference_transform(self.calibration) is not None:
"""),
    (r"""            _binding, _reason = resolve_reference_transform(self.calibration,
                                                            self.transform)
""",
     r"""            _binding, _reason = resolve_reference_transform(self.calibration,
                                                            transform)
"""),
    (r"""        # one the fixed standalone copy keeps the legacy support.
""",
     r"""        # one the legal standalone caller transform keeps the legacy support.
"""),
    (PROSPECTIVE, ORIGINAL_BINDING),
    (r"""            previous_reference = calibration_reference_transform(self.calibration)
            new_reference = calibration_reference_transform(new_calibration)
            same_reference = (previous_reference is None
                              and new_reference is None) \
                or _same_transform_record(previous_reference, new_reference)
            # Prospective effective binding, resolved before any assignment:
            # the new artifact's known T wins; otherwise the fixed startup
            # standalone copy is used, never the caller's live dict. A same-id
            # reload whose declared parent record *or* actual effective binding
            # would change is a contradiction, not a reload (GL-03 G04/G05).
            new_binding, new_binding_reason = \
                self._prospective_reference_binding(new_calibration)
            same_binding = (self._reference_transform is None
                            and new_binding is None) \
                or _same_transform_record(self._reference_transform, new_binding)
            if new_version == previous_version \
                    and not (same_reference and same_binding):
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
            record = {"kind": "ground_derived_lifecycle",
                      "previous_id": previous_id, "ground_derived_id": new_id,
                      "previous_calibration_version": previous_version,
                      "calibration_version": new_version,
                      "changed": bool(changed)}
            # Atomic switch: only after validation succeeded; the consumed
            # ground/derived come from the same canonical artifact so the
            # published id can never disagree with the consumed records, and
            # snapshots/predictions bind exactly the prospective record that
            # was just validated and compared (no re-read of any live source).
            self.calibration = new_calibration
            self.ground, self.ground_derived = resolved_ground, resolved_block
            self._reference_transform = new_binding
            self._reference_reason = new_binding_reason
""",
     r"""            previous_reference = calibration_reference_transform(self.calibration)
            new_reference = calibration_reference_transform(new_calibration)
            same_reference = (previous_reference is None
                              and new_reference is None) \
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
            record = {"kind": "ground_derived_lifecycle",
                      "previous_id": previous_id, "ground_derived_id": new_id,
                      "previous_calibration_version": previous_version,
                      "calibration_version": new_version,
                      "changed": bool(changed)}
            # Atomic switch: only after validation succeeded; the consumed
            # ground/derived come from the same canonical artifact so the
            # published id can never disagree with the consumed records.
            self.calibration = new_calibration
            self.ground, self.ground_derived = resolved_ground, resolved_block
            # Re-resolve the reference binding from the adopted artifact before
            # any new frame: a new version must never publish its id with the
            # previous version's T.
            self._reference_transform, self._reference_reason = \
                self._resolve_reference_binding()
"""),
]

PATCHES = {
    "src/human_fall_detection/core/calibration.py": CALIBRATION,
    "src/human_fall_detection/core/node_runtime.py": NODE_RUNTIME,
}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reverse(relative, text):
    pairs = PATCHES.get(relative, [])
    for old, new in pairs:
        count = text.count(old)
        assert count == 1, (relative, count, old[:60])
        text = text.replace(old, new)
    if relative.endswith("test_gl03_candidates_geometry.py"):
        marker = "\n    def test_wrong_kind_full_artifact_is_not_legacy_summary"
        start = text.index(marker)
        end = text.index("\n\nclass GroundGeometryTest", start)
        text = text[:start] + text[end:]
        text = text.replace(", make_unknown_transform)", ")", 1)
    return text


report = []
diff_text = []
for relative, sha4 in R4.items():
    current = (ROOT / relative).read_text(encoding="utf-8")
    old = reverse(relative, current)
    digest = sha(old)
    report.append("{} reconstructed {} expected {} {}".format(
        relative, digest, sha4, "OK" if digest == sha4 else "MISMATCH"))
    assert digest == sha4, relative
    diff_text.extend(difflib.unified_diff(
        old.splitlines(keepends=True), current.splitlines(keepends=True),
        fromfile="a/" + relative, tofile="b/" + relative))
(HERE / "23_reconstruct_check.txt").write_text(
    "\n".join(report) + "\n", encoding="utf-8")
(HERE / "23_source_diff.patch").write_text(
    "".join(diff_text), encoding="utf-8")
print("\n".join(report))
print("R5 diff lines:", len(diff_text))
sys.exit(0)
