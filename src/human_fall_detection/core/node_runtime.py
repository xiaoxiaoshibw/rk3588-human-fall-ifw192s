"""Pure, ROS-free runtime core for the HF-07 node and HF-11 bridge.

Everything here works on arrays and plain dicts so the whole chain can be tested
on Windows without ROS; ``scripts/human_fall_node.py`` is only message plumbing
around :class:`FallNodeCore`. The core reuses the HF-04..06 modules:

- the HF-01/HF-02 stamp classification and epoch rebuild (``core.timebase``);
- candidate snapshots (``core.lidar_candidates.build_snapshot``);
- the operator selection/ack backend and stance baseline (``core.selection``,
  ``core.baseline``);
- tracking and the rule-based fall state machine (``core.tracking``,
  ``core.features``, ``core.fall_state``).

Composition rules that this layer (not the pure modules) must enforce:

- The **required** cloud input gates everything: an invalid/repeated/expired
  current cloud frame cannot produce a selectable snapshot, and a request that
  arrives while the required input is stale/invalid is rejected even inside the
  snapshot TTL. Release is still allowed so the operator can clear a target.
- The auxiliary IMU/device clock is tracked in a **separate** time base: a
  repeat/reset on the unverified auxiliary stream must not bump the geometry
  cloud epoch or invalidate the operator's selection epoch.
- A select request bound to an older snapshot is accepted only when the
  requested candidate has a **unique continuous match** in the latest valid
  snapshot; a disappeared/ambiguous target is rejected rather than locked from
  a cached position.
- Every observation and baseline sample carries the full binding set
  (session/track/epoch/selection/generation/calibration) so the strict
  ``baseline_applies`` guard can actually succeed without being relaxed.
- Events are JSON-validated before being remembered, so a non-serializable
  event can never poison later state publication; a duplicate (already
  persisted) event is not re-published as new.
"""

import copy
import hashlib
import json
import math
import os
import threading
from collections import deque

import numpy as np

try:  # pragma: no cover - import shim exercised through the package/tests
    from core.baseline import StanceBaselineCollector
    from core.calibration import (build_geometry_calibration,
                                  calibration_reference_transform,
                                  ground_context_calibration,
                                  ground_context_from_calibration,
                                  resolve_reference_transform,
                                  validate_ground_derived,
                                  validate_geometry_calibration,
                                  _same_transform_record,
                                  _validate_ground_derived_consistency
                                  as validate_ground_derived_consistency_guard)
    from core.fall_state import FallStateMachine
    from core.features import FeatureExtractor
    from core.ground import GroundMonitor, validate_ground_plane
    from core.lidar_candidates import build_snapshot, ground_frame_eligible
    from core.selection import SelectionBackend
    from core.timebase import TimebaseSession
    from core.tracking import TargetTracker
except ImportError:  # pragma: no cover
    from baseline import StanceBaselineCollector
    from calibration import (build_geometry_calibration,
                             calibration_reference_transform,
                             ground_context_calibration,
                             ground_context_from_calibration,
                             resolve_reference_transform,
                             validate_ground_derived,
                             validate_geometry_calibration,
                             _same_transform_record,
                             _validate_ground_derived_consistency
                             as validate_ground_derived_consistency_guard)
    from fall_state import FallStateMachine
    from features import FeatureExtractor
    from ground import GroundMonitor, validate_ground_plane
    from lidar_candidates import build_snapshot, ground_frame_eligible
    from selection import SelectionBackend
    from timebase import TimebaseSession
    from tracking import TargetTracker

STATE_KIND = "target_state"
SCHEMA_VERSION = 1
SOURCE_TIME_DOMAIN = "device_stamp_s_unanchored"
METHOD = "lidar_geometry"
INPUT_PROFILE = "lidar_geometry"
MALFORMED_REQUEST = "malformed_request"
REASON_REQUIRED_UNAVAILABLE = "required_cloud_unavailable"
REASON_CANDIDATE_NOT_CURRENT = "candidate_not_current"
CLOCK_DOMAINS = ("monotonic", "message_time")
GATED_ACTIONS = ("select", "capture_baseline")


def finite_or_none(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def dumps_strict(payload):
    return json.dumps(payload, allow_nan=False)


def derive_ground_calibration(ground, fallback_frame="innolidar"):
    """A stable parameter-version record for a standalone (ground-only) config.

    A validated ground without an explicit geometry-calibration artifact still
    needs a non-empty ``calibration_id`` so the strict baseline binding can
    succeed. The id is a content hash of the validated ground, so it is stable
    across runs and only identifies the parameter set; ``reference_frame`` is
    null and every physical verification flag stays false (this does NOT claim
    the extrinsics or the ground physics were verified). Returns ``None`` when
    no valid ground is available or the record cannot be built.
    """
    if not isinstance(ground, dict) or ground.get("status") != "valid":
        return None
    lidar = ground.get("frame") or fallback_frame
    try:
        payload = json.dumps(ground, sort_keys=True, separators=(",", ":"),
                             allow_nan=False)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return build_geometry_calibration(
            "ground-only-" + digest, "unset", lidar, reference_frame=None,
            ground=ground)
    except Exception:  # noqa: BLE001 - a bad artifact must not fabricate a version
        return None


def project_snapshot_for_ros(snapshot):
    """Return a new browser-facing copy without the large offline-evidence arrays.

    The per-candidate ``evidence_indices`` list (one index per cluster point) is
    only useful for offline review, not for the web overlay, and dominates the
    ``/human_fall/candidates`` JSON size. This copies the snapshot and each
    candidate into fresh dicts and drops that one field, so the algorithm's
    cached/selection snapshot is never mutated and the same input still produces
    the same algorithm result. All other fields (ids, center, bbox, point_count,
    quality, source/session/epoch) are preserved.
    """
    if not isinstance(snapshot, dict):
        return snapshot
    projected = dict(snapshot)
    candidates = []
    for candidate in snapshot.get("candidates", []):
        if isinstance(candidate, dict):
            item = dict(candidate)
            item.pop("evidence_indices", None)
            candidates.append(item)
        else:
            candidates.append(candidate)
    projected["candidates"] = candidates
    return projected


def sample_point_data(data, point_step, row_step, height, width,
                      stride=4, max_points=12000):
    """Stride-sample raw PointCloud2 point bytes for a read-only display stream.

    Returns ``(sampled_bytes, selected_count, total_count)`` or ``(None, 0, 0)``
    for an unusable layout. Each selected point is copied whole (``point_step``
    bytes), so fields, XYZ units, endianness and the coordinate frame are
    unchanged. Organized rows are addressed with ``row_step`` (handles row
    padding). The input buffer is never modified; an invalid/empty layout never
    fabricates a display cloud.
    """
    try:
        point_step = int(point_step)
        row_step = int(row_step)
        height = int(height)
        width = int(width)
        stride = int(stride)
        max_points = int(max_points)
    except (TypeError, ValueError):
        return None, 0, 0
    if point_step <= 0 or width <= 0 or height <= 0 or stride <= 0 or max_points <= 0:
        return None, 0, 0
    if row_step < point_step * width:
        return None, 0, 0
    total = height * width
    needed = (height - 1) * row_step + width * point_step
    try:
        buffer = bytes(data)
    except (TypeError, ValueError):
        return None, 0, 0
    if len(buffer) < needed:
        return None, 0, 0
    out = bytearray()
    count = 0
    for index in range(0, total, stride):
        if count >= max_points:
            break
        row = index // width
        col = index % width
        offset = row * row_step + col * point_step
        out += buffer[offset:offset + point_step]
        count += 1
    if count == 0:
        return None, 0, 0
    return bytes(out), count, total


def frame_age_exceeded(receive_s, now_s, timeout_s):
    """True when a frame received at ``receive_s`` is already over ``timeout_s``.

    A pure, injectable-clock predicate so the ROS worker can re-check freshness
    with a fresh ``time.monotonic()`` read *after* a slow decode/compute instead
    of trusting the pre-compute clock. A missing receive time counts as stale.
    """
    if receive_s is None:
        return True
    return (now_s - receive_s) > timeout_s


class LatestFrameQueue:
    """Bounded (size-1) latest-frame buffer so callbacks never block on compute."""

    def __init__(self, maxlen=1):
        self._lock = threading.Lock()
        self._items = deque(maxlen=max(1, int(maxlen)))
        self._event = threading.Event()
        self.dropped = 0

    def put(self, item):
        with self._lock:
            if self._items:
                self.dropped += 1
            self._items.append(item)
            self._event.set()

    def take(self):
        with self._lock:
            item = self._items.pop() if self._items else None
            if not self._items:
                self._event.clear()
            return item

    def wait(self, timeout):
        return self._event.wait(timeout)

    def wake(self):
        self._event.set()


class EventLog:
    """Append-only JSONL event store with de-duplication and explicit failure.

    ``append`` returns ``(persisted, reason)``. The event is only remembered
    after it passes ``allow_nan=False`` serialization, so a non-JSON value can
    never be queued into ``recent`` and break later state publication. The event
    is remembered even when the disk write fails (never re-emitted as new), but
    the failure is surfaced as ``degraded`` instead of being reported as a save.
    Loading an existing file on construction means a restarted node never
    replays stored events as fresh ones.
    """

    def __init__(self, path, recent_size=64):
        self.path = path
        self.recent = deque(maxlen=max(1, int(recent_size)))
        self.ids = set()
        self.degraded = False
        self.degrade_reason = None
        self.written = 0
        self._load()

    def _load(self):
        if not self.path or not os.path.isfile(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    event_id = event.get("event_id")
                    if event_id and event_id not in self.ids:
                        self.ids.add(event_id)
                        self.recent.append(event)
                        self.written += 1
        except OSError as exc:
            self.degraded = True
            self.degrade_reason = "event_log_read_failed:{}".format(exc)

    def has(self, event_id):
        return event_id is not None and event_id in self.ids

    def append(self, event):
        event_id = event.get("event_id")
        if event_id is None or event_id in self.ids:
            return False, "duplicate"
        try:
            content = dumps_strict(event)
        except (TypeError, ValueError) as exc:
            self.degraded = True
            self.degrade_reason = "event_log_not_serializable:{}".format(exc)
            return False, self.degrade_reason
        self.ids.add(event_id)
        self.recent.append(event)
        if not self.path:
            self.degraded = True
            self.degrade_reason = "event_log_path_unset"
            return False, self.degrade_reason
        try:
            directory = os.path.dirname(os.path.abspath(self.path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(content + "\n")
            self.written += 1
            return True, None
        except OSError as exc:
            self.degraded = True
            self.degrade_reason = "event_log_write_failed:{}".format(exc)
            return False, self.degrade_reason

    def report(self):
        return {"path": self.path, "degraded": bool(self.degraded),
                "reason": self.degrade_reason, "persisted_count": self.written,
                "recent_count": len(self.recent)}


class FallNodeCore:
    """One-frame-at-a-time geometry/selection/fall runtime (no ROS here)."""

    def __init__(self, session_id, settings=None, ground=None, calibration=None,
                 transform=None, background=None, event_path=None,
                 recent_events=64, expected_frame="innolidar",
                 cloud_timeout_s=0.6, imu_timeout_s=0.3, device_timeout_s=0.6,
                 max_forward_jump_s=30.0, clock_domain="monotonic"):
        sections = settings or {}
        self.session_id = session_id
        self.settings = sections
        self.expected_frame = expected_frame
        # Actual source frame of the most recent processed cloud. The shared
        # ground source-frame guard compares it against the bound ground plane so
        # a plane fitted in another lidar frame can never back this frame's
        # height/ground measurements (defaults to the expected frame at boot).
        self._current_frame = expected_frame
        if calibration is not None:
            # Startup strict validation, identical to apply_ground_context: any
            # explicitly supplied artifact is validated end-to-end (including a
            # strict calibration_id/version), so a damaged record can never load
            # green at boot by falling back to the ground-only path. Everything
            # the core consumes (ground/derived/id/monitor) is bound to the
            # canonical validated artifact, never to the caller's raw dict.
            self.calibration = validate_geometry_calibration(calibration)
            self.ground, self.ground_derived = ground_context_from_calibration(
                self.calibration)
        else:
            if ground is not None:
                try:
                    validate_ground_plane(ground,
                                          expected_frame=expected_frame)
                except ValueError as exc:
                    raise ValueError(
                        "invalid standalone ground record: " + str(exc)) from None
            # Ground-only config: derive a stable parameter version (physical
            # verification flags stay false) so the baseline binding is usable;
            # the consumed ground is re-bound from the canonical artifact,
            # never the caller's dict.
            self.calibration = derive_ground_calibration(ground, expected_frame) \
                or calibration
            self.ground, self.ground_derived = ground_context_from_calibration(
                self.calibration)
        # The standalone caller transform is frozen (deep-copied) at the
        # node's ownership boundary: a later in-place caller edit is not a
        # reload authorization, so every reload may only re-read this fixed
        # copy, never the caller's live dict (GL-03 G05).
        self.transform = copy.deepcopy(transform) if transform is not None else None
        if self.transform is not None \
                and calibration_reference_transform(self.calibration) is not None:
            # A startup that supplies an explicit transform next to an artifact
            # that already owns T_reference_lidar must not silently discard the
            # explicit one: a disagreement is an explicit refusal here (GL-03
            # G03). Later reloads keep the artifact-authoritative behaviour and
            # adopt the new artifact's own T without being blocked by the old
            # standalone parameter.
            _binding, _reason = resolve_reference_transform(self.calibration,
                                                            self.transform)
            if _reason == "reference_transform_conflict":
                raise ValueError(
                    "explicit reference transform conflicts with the "
                    "calibration artifact; a full artifact owns its "
                    "T_reference_lidar")
        # Effective lidar->reference binding actually used by snapshots and
        # predictions. An artifact-owned transform is authoritative; without
        # one the fixed standalone copy keeps the legacy support.
        self._reference_transform, self._reference_reason = \
            self._resolve_reference_binding()
        self.background = background
        # Candidate local ground frame (GL-02). Purely additive: it never sets a
        # physical/extrinsic flag. The id is the switch key for lifecycle
        # invalidation; the monitor is only meaningful with a frozen transform.
        self._ground_derived_id = self._block_id(self.ground_derived)
        self.ground_monitor = GroundMonitor() if self.ground_derived else None
        self.ground_monitor_report = None
        self.ground_lifecycle = []
        self.clock_domain = clock_domain if clock_domain in CLOCK_DOMAINS else "monotonic"
        self._lock = threading.RLock()
        self.tracker = TargetTracker(session_id, sections.get("tracking"))
        self.features = FeatureExtractor(session_id, sections.get("features"))
        self.fall = FallStateMachine(session_id, sections.get("fall"))
        self.baseline = StanceBaselineCollector(session_id, sections.get("baseline"))
        self.selection = SelectionBackend(session_id, self.tracker, self.baseline,
                                          sections.get("selection"))
        self.candidate_settings = sections.get("candidates")
        # Required cloud and auxiliary streams live in separate time bases so an
        # unverified IMU/device clock reset cannot rewind the geometry epoch.
        self.cloud_timebase = TimebaseSession(session_id, self.clock_domain,
                                              max_forward_jump_s=max_forward_jump_s)
        self.cloud_timebase.register("cloud", cloud_timeout_s, required=True)
        self.aux_timebase = TimebaseSession(session_id, self.clock_domain,
                                            max_forward_jump_s=max_forward_jump_s)
        self.aux_timebase.register("imu", imu_timeout_s, required=False)
        self.aux_timebase.register("device", device_timeout_s, required=False)
        self.event_log = EventLog(event_path, recent_events)
        self.imu_quality = {"messages": 0, "finite": None, "last_receive_s": None}
        self.device_quality = {"messages": 0, "last_receive_s": None}
        self._last_candidate = None
        self._last_snapshot_id = None
        self._latest_valid_snapshot = None
        self._baseline_request_id = None
        self._baseline_status = self.baseline.status
        self._last_state = None
        self.frame_count = 0
        self.invalid_frames = 0

    @staticmethod
    def _expected_lidar_frame(ground, calibration):
        if isinstance(calibration, dict):
            frame = (calibration.get("frames") or {}).get("lidar")
            if frame:
                return frame
        if isinstance(ground, dict):
            return ground.get("frame")
        return None

    @staticmethod
    def _block_from_calibration(calibration):
        if isinstance(calibration, dict):
            block = calibration.get("ground_derived")
            if isinstance(block, dict):
                return block
        return None

    @staticmethod
    def _block_id(block):
        if isinstance(block, dict):
            return block.get("ground_derived_id")
        return None

    def _context_version_pair(self):
        calibration_id = (self.calibration or {}).get("calibration_id")
        return (calibration_id, self._ground_derived_id)

    def _prospective_reference_binding(self, calibration):
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

    def _resolve_new_context(self, ground, calibration, ground_derived):
        """Validate the requested change first; return the canonical binding.

        Every supported entry shape ends in exactly one call to
        :func:`~core.calibration.ground_context_calibration`, so every path
        publishes the same canonical calibration/ground/derived records and a
        consistent (calibration_id, ground_derived_id) pair. Returns
        ``(new_calibration, resolved_ground, resolved_block)`` — the caller
        only binds on success.
        """
        if calibration is not None and (ground is not None
                                        or ground_derived is not None):
            raise ValueError(
                "a full calibration artifact cannot be combined with "
                "ground/ground_derived arguments; the artifact is already a "
                "complete ground context")
        if calibration is not None:
            # Full artifact: validated end-to-end (parent ground, transforms/
            # verification and the embedded derived block, including the
            # cross-record consistency). Nothing partial is adopted.
            return validate_geometry_calibration(calibration), None, None
        if ground_derived is not None:
            if ground is None:
                raise ValueError(
                    "a bare ground_derived update is incomplete: supply the "
                    "matching parent ground (build a full artifact when the "
                    "parent is not at hand)")
            expected_frame = self._expected_lidar_frame(ground, self.calibration)
            try:
                validate_ground_plane(ground, expected_frame=expected_frame)
            except ValueError as exc:
                raise ValueError(
                    "invalid accompanying ground record: " + str(exc)) from None
            validated_derived = validate_ground_derived(ground_derived)
            validate_ground_derived_consistency_guard(ground, validated_derived)
            new_calibration = ground_context_calibration(
                ground, validated_derived, parent_calibration=self.calibration,
                fallback_frame=self.expected_frame)
            return new_calibration, None, None
        if ground is not None:
            expected_frame = self._expected_lidar_frame(ground, self.calibration)
            try:
                validate_ground_plane(ground, expected_frame=expected_frame)
            except ValueError as exc:
                raise ValueError("invalid ground record: " + str(exc)) from None
            if self.ground_derived is not None:
                validate_ground_derived_consistency_guard(
                    ground, self.ground_derived)
            new_calibration = ground_context_calibration(
                ground, self.ground_derived, parent_calibration=self.calibration,
                fallback_frame=self.expected_frame)
            return new_calibration, None, None
        # No new geometry: re-validate the active context (a same-id reload is
        # not a free pass for damage) and re-bind to the canonical artifact.
        new_calibration = ground_context_calibration(
            self.ground, self.ground_derived,
            parent_calibration=self.calibration,
            fallback_frame=self.expected_frame)
        return new_calibration, None, None

    def apply_ground_context(self, ground=None, calibration=None,
                             ground_derived=None):
        """Explicit startup/reload boundary for the ground local frame (GL-02).

        Validation runs *completely first* through one path
        (:meth:`_resolve_new_context`) so a full artifact, a paired
        ground+derived update and a bare ground update all yield exactly one
        canonical calibration artifact — the published
        ``calibration_id``/``ground_derived_id`` always matches the
        ground/derived the core actually consumes. The live context
        (``calibration``/``ground``/``ground_derived``/``_ground_derived_id``/
        monitor) is then swapped atomically. A bare derived block without its
        accompanying parent ground is refused outright (it cannot leave a
        live old ground/old id mixed with a new derived transform). Context
        validity invalidation keys on ``(calibration_id, ground_derived_id)``:
        a legal new version of the same geometry also retires old
        baseline/snapshot/request/tracker eligibility, while old events and
        the source seq/stamp/epoch semantics are kept. There is deliberately
        no generic hot-update framework: this is one explicit boundary.
        """
        with self._lock:
            previous_version, previous_id = self._context_version_pair()
            # Validation first, nothing is assigned before it succeeds; the
            # returned artifact is canonical and deep-copied from the caller.
            new_calibration, _, _ = self._resolve_new_context(
                ground, calibration, ground_derived)
            resolved_ground, resolved_block = ground_context_from_calibration(
                new_calibration)
            new_id = self._block_id(resolved_block)
            new_version = new_calibration.get("calibration_id")
            previous_reference = calibration_reference_transform(self.calibration)
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
            if changed:
                invalidated = ["baseline", "snapshots", "positions", "requests",
                               "action_history"]
                self._ground_derived_id = new_id
                self.ground_monitor = GroundMonitor() if resolved_block else None
                self.ground_monitor_report = None
                # An accepted capture belongs to the *old* context. Settle it
                # with its original request binding before the binding is
                # cleared, so a version switch can never silently erase an
                # accepted request without a terminal receipt. This explicit
                # pure API has no ROS reload caller, so the receipt is handed
                # back on the lifecycle record; the existing invalidate below
                # still resets eligibility/caches for the new version.
                baseline_ack = None
                if self.baseline.status == "pending":
                    self.baseline._fail("ground_derived_changed")
                    baseline_ack = self._baseline_completion_ack()
                # Baseline/selection eligibility for the old frame is retired
                # (its history stays in ``retired``); positions/snapshots/requests
                # and the tracker's own position are all cleared so no stale
                # geometry can be re-published under the new frame. Old events
                # and the source seq/stamp/epoch are preserved.
                self.baseline.invalidate("ground_derived_changed")
                self._baseline_request_id = None
                self._baseline_status = self.baseline.status
                if baseline_ack is not None:
                    record["baseline_ack"] = baseline_ack
                self.selection._snapshots.clear()
                self.selection._snapshot_order.clear()
                self.selection._requests.clear()
                self.selection._request_order.clear()
                if self.tracker.track_id is not None:
                    self.tracker.release("ground_derived_changed")
                self._latest_valid_snapshot = None
                self._last_snapshot_id = None
                self._last_candidate = None
                self._last_state = None
                record["invalidated"] = invalidated
            else:
                # Geometry delta is None but the geometry id may have changed
                # (e.g. re-bound same calibration content under a new version):
                # only the monitor state follows the geometry id.
                if new_id != previous_id:
                    self._ground_derived_id = new_id
                    self.ground_monitor = GroundMonitor() if resolved_block else None
                    self.ground_monitor_report = None
            self.ground_lifecycle.append(record)
            return record

    # -- auxiliary stream bookkeeping (never gates the required geometry) ----

    def note_imu(self, receive_s, stamp, frame_id, finite):
        with self._lock:
            self.aux_timebase.note("imu", None, stamp, receive_s, frame_id)
            self.imu_quality["messages"] += 1
            self.imu_quality["finite"] = finite
            self.imu_quality["last_receive_s"] = finite_or_none(receive_s)

    def note_device(self, receive_s, stamp, frame_id):
        with self._lock:
            self.aux_timebase.note("device", None, stamp, receive_s, frame_id)
            self.device_quality["messages"] += 1
            self.device_quality["last_receive_s"] = finite_or_none(receive_s)

    # -- per-frame processing -------------------------------------------------

    def process(self, points, receive_s, *, seq=None, stamp_secs=None,
                stamp_nsecs=None, frame_id=None, now=None):
        """Process one decoded cloud frame; returns snapshot/state/event payloads.

        ``points`` is an ``(N,3)`` array or ``None`` for a frame that could not be
        decoded. ``now`` is the caller's current clock value; it drives freshness
        and the published ``time_received_s``. An invalid stamp or undecodable
        frame yields a diagnostic snapshot but is never registered as a valid,
        selectable snapshot, and its candidates never reach the tracker/fall
        history (the target is reported unobservable/unknown instead).
        """
        now = finite_or_none(now)
        if now is None:
            now = finite_or_none(receive_s) or 0.0
        receive = finite_or_none(receive_s)
        frame = frame_id or self.expected_frame
        with self._lock:
            self._current_frame = frame
            note = self.cloud_timebase.note("cloud", seq, (stamp_secs, stamp_nsecs),
                                            receive_s, frame)
            if note["epoch_reset"]:
                self.selection.set_epoch(self.cloud_timebase.time_epoch)
            return self._process_locked(points, receive, now, seq, stamp_secs,
                                        stamp_nsecs, frame)

    def _process_locked(self, points, receive, now, seq, stamp_secs, stamp_nsecs,
                        frame):
        stream = self.cloud_timebase.streams["cloud"]
        epoch = self.cloud_timebase.time_epoch
        self.frame_count += 1
        frame_valid = bool(points is not None and stream.stamp_status != "invalid")
        snapshot = None
        candidates = []
        if points is not None:
            snapshot = build_snapshot(
                points, self.candidate_settings, session_id=self.session_id,
                time_epoch=epoch, snapshot_id=self._snapshot_id(seq, receive),
                seq=seq, stamp_secs=stamp_secs, stamp_nsecs=stamp_nsecs,
                source_stamp_s=stream.source_stamp_s, frame_id=frame,
                ground=self.ground, calibration=self.calibration,
                transform=self._reference_transform, background=self.background)
            if frame_valid:
                self.selection.register_snapshot(snapshot, receive if receive is not None else now)
                self._last_snapshot_id = snapshot["snapshot_id"]
                self._latest_valid_snapshot = snapshot
                candidates = snapshot["candidates"]
            else:
                self.invalid_frames += 1
        else:
            self.invalid_frames += 1

        if self.ground_monitor is not None:
            if frame_valid and points is not None:
                try:
                    self.ground_monitor_report = self.ground_monitor.feed(
                        points, self.ground_derived)
                except (ValueError, TypeError) as exc:  # diagnostics never fatal
                    self.ground_monitor.note_invalid()
                    self.ground_monitor_report = {
                        "status": "unknown", "reason": "monitor_error:" + str(exc)}
            else:
                # Stream gap / invalid frame: drop the continuity run and the
                # stored verdict so a stale shift cannot be mistaken for a
                # current one.
                self.ground_monitor.note_invalid()
                self.ground_monitor_report = {"status": "unknown",
                                              "reason": "no_current_frame"}

        source_stamp_s = stream.source_stamp_s if frame_valid else None
        ground_context_unavailable = self._ground_context_unavailable()
        if ground_context_unavailable:
            # A degraded/unknown/recalibration ground context invalidates the
            # *ground-dependent* chain at the source: the current candidate
            # never reaches the tracker/feature extractor/fall machine and the
            # tracker's continuous observation run ages (no new measured
            # height/geometry), while the tracker state machine itself stays
            # intact. Source frames, the tracker identity and old events are
            # kept; the ordinary IMU degraded check elsewhere is untouched.
            candidates = []
        track_state = self.tracker.update(candidates, epoch,
                                          source_stamp_s=source_stamp_s,
                                          receive_s=receive)
        observed = None
        # Candidate ids are local to each frame. Only a successful association
        # can turn a same-named current candidate into this track's measurement.
        if (frame_valid and not ground_context_unavailable
                and track_state["track_status"] == "locked"
                and not track_state["position_predicted"]
                and track_state["candidate_id"] is not None):
            for candidate in candidates:
                if candidate["candidate_id"] == track_state["candidate_id"]:
                    observed = candidate
                    break
        if ground_context_unavailable:
            # The previous frame's cached candidate must never keep publishing
            # position/geometry while the ground context is degraded/unknown.
            observed = None
            self._last_candidate = None
        elif observed is not None:
            self._last_candidate = observed
        elif not track_state.get("track_id"):
            # Released/unselected: drop the cached geometry so a later frame
            # cannot keep publishing the previous target's position.
            self._last_candidate = None

        baseline_ack = None
        if ground_context_unavailable:
            # Settle the baseline *before* the feature/fall consumers read it, so
            # a pending capture fails (with its terminal ack) and a ready
            # eligibility retires on the very frame the ground context is lost,
            # never after this frame's consumers already saw it.
            baseline_ack = self._cancel_baseline_on_ground_loss()
        feature_block = self.features.update({
            "candidate": observed,
            "track_id": track_state["track_id"],
            "track_status": track_state["track_status"],
            "position_predicted": track_state["position_predicted"],
            "time_epoch": epoch,
            "session_id": self.session_id,
            "selection_version": track_state["selection_version"],
            "action_generation": track_state["action_generation"],
            "calibration_version": track_state["calibration_version"],
            "source_stamp_s": source_stamp_s,
        }, None if ground_context_unavailable else self.baseline.baseline)

        if not ground_context_unavailable:
            baseline_ack = self._feed_baseline(observed, track_state,
                                               source_stamp_s, receive, epoch)

        fall_block = self.fall.update(feature_block, {
            "source_stamp_s": source_stamp_s,
            "time_epoch": epoch,
            "session_id": self.session_id,
            "selection_version": track_state["selection_version"],
            "action_generation": track_state["action_generation"],
            "calibration_version": track_state["calibration_version"],
            "track_id": track_state["track_id"],
            "track_status": track_state["track_status"],
        }, None if ground_context_unavailable else self.baseline.baseline)

        new_event = fall_block.get("new_event")
        if new_event is not None:
            persisted, reason = self.event_log.append(new_event)
            if reason == "duplicate":
                new_event = None

        state = self._state_payload(now, snapshot, frame_valid, track_state,
                                    feature_block, fall_block, observed)
        self._last_state = state
        return {"snapshot": snapshot, "state": state, "event": new_event,
                "baseline_ack": baseline_ack}

    def _snapshot_id(self, seq, receive):
        if seq is not None:
            return "seq:{}".format(seq)
        return "recv:{:.6f}".format(receive if receive is not None else 0.0)

    def _source_frame_mismatch(self):
        """True when a bound context belongs to a different source frame.

        A non-empty ``ground['frame']`` or reference ``from_frame`` that differs
        from the current non-empty source frame is a hard mismatch: the bound
        plane/transform can never back this frame. The reference binding is
        guarded with or without a ground plane, and a contradictory
        ``to_frame``/invalid record is refused at bind time. A missing ground,
        missing reference or missing frame keeps the legacy path (no-ground is
        degraded, not invalid).
        """
        current = self._current_frame
        if not (isinstance(current, str) and current):
            return False
        if isinstance(self.ground, dict):
            recorded = self.ground.get("frame")
            if isinstance(recorded, str) and recorded and recorded != current:
                return True
        if self._reference_reason in ("reference_to_frame_mismatch",
                                      "reference_transform_invalid"):
            return True
        if isinstance(self._reference_transform, dict):
            recorded = self._reference_transform.get("from_frame")
            if isinstance(recorded, str) and recorded and recorded != current:
                return True
        return False

    def _ground_context_unavailable(self):
        """True when this frame's ground context cannot support measurements.

        A ``ground_monitor_report`` of ``degraded`` / ``recalibration_required``
        / ``unknown`` (a sustained shift, a breaking plane, or a no-current-frame
        stream gap) means the bound ground-derived evidence no longer backs any
        *ground-dependent* measurement (height-above-ground, baseline, fall).
        Without a derived block the monitor stays out of this: no-ground is a
        pre-existing degraded path and must not be forced invalid here.

        A source-frame mismatch is different and always invalidates, with or
        without a derived block: the bound plane was fitted in another lidar
        frame, so it can never back this frame's height/ground chain. This closes
        the sibling leak where only the outer ground geometry was gated while the
        legacy height/observability/selection chain still stayed valid.
        """
        if self._source_frame_mismatch():
            return True
        if self.ground_derived is None:
            return False
        report = self.ground_monitor_report
        if not isinstance(report, dict):
            return False
        return report.get("status") in ("degraded", "recalibration_required",
                                        "unknown")

    def _feed_baseline(self, observed, track_state, source_stamp_s, receive, epoch):
        if self.baseline.status != "pending":
            return None
        observation = {
            "track_id": track_state["track_id"],
            "calibration_version": track_state["calibration_version"],
            "ground_relative": bool(observed and observed.get("ground_relative_available")),
            "point_count": None if observed is None else observed.get("point_count"),
            "height_m": None if observed is None else observed.get("height_m"),
            "position_m": None if observed is None else observed.get("center_source_m"),
        }
        self.baseline.feed(observation, source_stamp_s=source_stamp_s,
                           predicted=track_state["position_predicted"],
                           occluded=track_state["track_status"] != "locked")
        if self.baseline.status != self._baseline_status:
            previous = self._baseline_status
            self._baseline_status = self.baseline.status
            if previous == "pending" and self.baseline.status in ("ready", "failed"):
                return self._baseline_completion_ack()
        return None

    def _cancel_baseline_on_ground_loss(self):
        """Settle the baseline the moment the ground context fails.

        A pending capture accepted while the monitor was ok must not dangle
        once the ground context becomes unknown/degraded/holds the latch: the
        in-memory samples collected before the failure are kept as history but
        never stitched with later post-recovery samples, and the original
        ``request_id`` gets a bounded, terminal ``accepted=False`` ack through
        the same ``baseline_ack`` path as a normal completion.

        A *ready* baseline is a ground-relative measurement too, so its
        eligibility is retired here as well (the artifact is preserved in
        ``retired``; a later same-version recovery must re-capture and can never
        reuse the old ready). ``invalidate`` is idempotent once the collector is
        idle/empty, so this never retires the same baseline twice or re-emits a
        terminal ack. The source-stamp sampling clock is not advanced by this
        failure.
        """
        if self.baseline.status == "pending":
            self.baseline._fail("ground_monitor_unavailable")
            self._baseline_status = self.baseline.status
            return self._baseline_completion_ack()
        if self.baseline.status == "ready":
            self.baseline.invalidate("ground_monitor_unavailable")
            self._baseline_status = self.baseline.status
        return None

    def _baseline_completion_ack(self):
        status = self.baseline.status
        return {
            "kind": "selection_ack",
            "schema_version": SCHEMA_VERSION,
            "request_id": self._baseline_request_id,
            "action": "capture_baseline",
            "session_id": self.session_id,
            "time_epoch": self.selection.time_epoch,
            "accepted": status == "ready",
            "reason": None if status == "ready" else self.baseline.reason,
            "track_id": self.baseline.track_id,
            "candidate_id": None,
            "selection_version": self.baseline.selection_version,
            "baseline": self.baseline.snapshot(),
            "idempotent_replay": False,
        }

    # -- request handling -----------------------------------------------------

    def _reject(self, request, reason):
        return {
            "kind": "selection_ack", "schema_version": SCHEMA_VERSION,
            "request_id": request.get("request_id"), "action": request.get("action"),
            "session_id": self.session_id, "time_epoch": self.selection.time_epoch,
            "accepted": False, "reason": reason, "track_id": None,
            "candidate_id": None, "selection_version": None, "baseline": None,
            "idempotent_replay": False}

    def _required_input_reason(self, receive_s):
        """Reason the required cloud input is currently unusable, or None."""
        if self._latest_valid_snapshot is None:
            return REASON_REQUIRED_UNAVAILABLE
        stream = self.cloud_timebase.streams["cloud"]
        if stream.stamp_status == "invalid":
            return stream.stamp_reason or "cloud_stamp_invalid"
        status, _age = stream.freshness(receive_s)
        if status != "fresh":
            return "cloud_" + status
        return None

    def _candidate_current(self, request):
        """True when the requested candidate has a unique current match.

        A select bound to an older snapshot is only allowed when the requested
        candidate still matches exactly one candidate in the latest valid
        snapshot (bounded-continuity), so a disappeared or ambiguous person is
        never locked from a cached position.
        """
        latest = self._latest_valid_snapshot
        if latest is None:
            return False, REASON_REQUIRED_UNAVAILABLE
        snapshot_id = request.get("snapshot_id")
        cache = getattr(self.selection, "_snapshots", {})
        entry = cache.get(snapshot_id) if snapshot_id else None
        requested = None
        if entry is not None:
            for candidate in entry["snapshot"].get("candidates", []):
                if candidate.get("candidate_id") == request.get("candidate_id"):
                    requested = candidate
                    break
        if requested is None:
            return True, None  # let the backend report unknown_snapshot/candidate
        if latest.get("snapshot_id") == snapshot_id:
            return True, None
        center = np.asarray(requested.get("center_source_m"), dtype=np.float64)
        gate = float(self.tracker.settings["gate_m"])
        matches = 0
        for candidate in latest.get("candidates", []):
            position = candidate.get("center_source_m")
            if position is None:
                continue
            if float(np.linalg.norm(np.asarray(position, dtype=np.float64) - center)) <= gate:
                matches += 1
        if matches == 1:
            return True, None
        return False, REASON_CANDIDATE_NOT_CURRENT

    def handle_request(self, request, receive_s, now_fn=None):
        with self._lock:
            # The caller may have sampled ``receive_s`` before queueing behind a
            # long frame computation. Once the lock is held, re-read the same
            # machine clock so gating uses the real handling time, not the
            # pre-wait arrival time (``now_fn`` is an injectable monotonic clock).
            if now_fn is not None:
                clamped = finite_or_none(now_fn())
                receive_s = 0.0 if clamped is None else clamped
            if not isinstance(request, dict):
                return self._reject({"request_id": None, "action": None},
                                    MALFORMED_REQUEST)
            # Idempotent replay is resolved before any freshness/monitor gate: a
            # repeated request_id must return its original cached receipt (or
            # request_id_conflict) even when the required cloud is now stale or
            # the ground monitor is unavailable. A pure cache read executes no
            # action and an id that was never cached still passes every gate.
            cached = self.selection.lookup_cached(request)
            if cached is not None:
                return cached
            action = request.get("action")
            if action in GATED_ACTIONS:
                reason = self._required_input_reason(receive_s)
                if reason is not None:
                    return self._reject(request, reason)
                # A source-frame mismatch means the bound plane belongs to a
                # different lidar frame: no gated action may start against it
                # (this is the sibling leak the outer ground-geometry gate did
                # not close). The capture-specific monitor degradation keeps its
                # existing refusal below; release stays ungated.
                if self._source_frame_mismatch():
                    return self._reject(request, "ground_frame_mismatch")
            if action == "select":
                okay, why = self._candidate_current(request)
                if not okay:
                    return self._reject(request, why)
            elif action == "capture_baseline" \
                    and self._ground_context_unavailable():
                # Ground monitor unknown/degraded/latched: a pending capture
                # would be skipped forever by _feed_baseline. Refuse now with an
                # explicit terminal ack (unchanged GL-02 behaviour).
                return self._reject(request, "ground_monitor_unavailable")
            ack = self.selection.handle(request, receive_s)
            if (ack.get("accepted") and action == "capture_baseline"
                    and self.baseline.status == "pending"):
                self._baseline_request_id = request.get("request_id")
                self._baseline_status = "pending"
            if ack.get("accepted") and action in ("select", "release"):
                # An accepted select/release changes the bound target *now*, with
                # no new cloud yet. The cached measurement state still belongs to
                # the previous binding, so a freshness refresh must not keep
                # publishing the old track_id/ground box. Drop the measurement
                # cache: ``status_state`` then rebuilds from the current tracker
                # binding with no observed candidate (never a fabricated
                # measurement), while an idempotent replay above stays a pure
                # cache read and re-executes nothing.
                self._last_state = None
                self._last_candidate = None
            return ack

    # -- payload assembly -----------------------------------------------------

    def _ground_valid(self):
        # monitor degradation/recalibration feeds the same gate as a missing
        # ground-plane record: it must downgrade observability (and so position,
        # selection- and baseline-eligibility), not just decorate a quality field.
        if bool(self.ground_monitor_report) \
                and self.ground_monitor_report.get("status") in (
                        "degraded", "recalibration_required", "unknown"):
            return False
        return ground_frame_eligible(self.ground, self._current_frame)

    def _observability(self, stream, frame_valid, now):
        status, _age = stream.freshness(now)
        if (not frame_valid or self._latest_valid_snapshot is None
                or stream.stamp_status == "invalid" or status != "fresh"):
            return "invalid"
        if self._ground_context_unavailable():
            # Ground-context failure is a *measurement* invalidation, not a
            # mere degradation: downstream consumers (webui enum) only know
            # valid/degraded/invalid, and this is the "invalid" (must-mask)
            # level. Position/bbox/fall state are masked by _mask_unobservable.
            return "invalid"
        if not self._ground_valid():
            return "degraded"
        if self.imu_quality["messages"] and self.imu_quality["finite"] is False:
            return "degraded"
        return "valid"

    def _mask_unobservable(self, state):
        """Scrub a state that must not claim a fresh measurement.

        Applied whenever the required cloud is missing/illegal/stale: the public
        fall status becomes ``unknown``, no last-measured position/range/bbox or
        prediction is reported, and the nested ``target_features``/
        ``fall_state`` blocks agree that the target is not observable. Stored
        history (``recent_events``) is left untouched. A later valid frame
        rebuilds the full measured state normally.
        """
        state["fall_status"] = "unknown"
        state["position_source_m"] = None
        state["position_reference_m"] = None
        state["position_source_from"] = "unavailable"
        state["position_predicted"] = False
        state["prediction_age_s"] = None
        state["prediction_stale"] = False
        state["velocity_m_s"] = None
        state["bbox_source_min_m"] = None
        state["bbox_source_max_m"] = None
        state["bbox_reference_min_m"] = None
        state["bbox_reference_max_m"] = None
        state["bbox_observed"] = False
        state["center_ground_m"] = None
        state["bbox_ground_min_m"] = None
        state["bbox_ground_max_m"] = None
        state["bbox_ground_from"] = "unavailable"
        state["range_m"] = None
        state["coordinate"] = None
        features = state.get("target_features")
        if isinstance(features, dict):
            features = dict(features)
            features["observable"] = False
            features["reason"] = features.get("reason") or "not_observable"
            features["height_m"] = None
            features["height_median_m"] = None
            features["horizontal_extent_m"] = None
            state["target_features"] = features
        fall_state = state.get("fall_state")
        if isinstance(fall_state, dict):
            fall_state = dict(fall_state)
            fall_state["fall_status"] = "unknown"
            fall_state["state"] = "unknown"
            fall_state["new_event"] = None
            state["fall_state"] = fall_state
        return state

    def _state_payload(self, now, snapshot, frame_valid, track_state, feature_block,
                       fall_block, observed):
        bbox_min = bbox_max = None
        bbox_ref_min = bbox_ref_max = None
        position_source = None
        position_reference = None
        position_predicted = bool(track_state.get("position_predicted"))
        position_source_from = "unavailable"
        ground_min = ground_max = ground_center = None
        ground_from = "unavailable"
        ground_derived_id = self._ground_derived_id
        range_block = None
        bbox_observed = False
        has_target = track_state.get("track_id") is not None
        predicted = bool(has_target and track_state.get("track_status") == "occluded"
                         and track_state.get("position_predicted")
                         and not track_state.get("prediction_stale")
                         and track_state.get("position_m") is not None)
        candidate = observed if observed is not None else \
            (self._last_candidate if predicted else None)
        if candidate is not None:
            bbox_min = candidate.get("bbox_source_min_m")
            bbox_max = candidate.get("bbox_source_max_m")
            bbox_ref_min = candidate.get("bbox_reference_min_m")
            bbox_ref_max = candidate.get("bbox_reference_max_m")
            position_source = candidate.get("center_source_m")
            position_reference = candidate.get("center_reference_m")
            ground_min = candidate.get("bbox_ground_min_m")
            ground_max = candidate.get("bbox_ground_max_m")
            ground_center = candidate.get("center_ground_m")
            ground_from = candidate.get("bbox_ground_from")
            range_block = candidate.get("range_m")
            bbox_observed = observed is not None
            if observed is not None and position_source is not None:
                position_source_from = "actual_points"
        if not has_target:
            # Released/unselected: no live target position/range/box is claimed.
            bbox_min = bbox_max = None
            bbox_ref_min = bbox_ref_max = None
            position_source = position_reference = range_block = None
            ground_min = ground_max = ground_center = None
            ground_from = "unavailable"
            bbox_observed = False
        elif predicted:
            # Prediction is anchored in the tracker's fixed domain, which prefers
            # the reference center when a reference transform exists. It must be
            # inverse-transformed back to source coordinates before it is reported
            # as ``position_source_m``; if there is no usable inverse the source
            # position is explicitly unavailable (never mislabelled).
            range_block = None  # no current measured range during occlusion
            bbox_observed = False
            position_predicted = True
            # A predicted pose is not a current actual point set: the ground
            # geometry is reported as unavailable, never as actual_points.
            ground_min = ground_max = ground_center = None
            ground_from = "unavailable"
            predicted_position = self._prediction_in_source(track_state.get("position_m"))
            if predicted_position is None:
                position_source = None
                position_reference = track_state.get("position_m")
                position_source_from = "unavailable"
            else:
                position_source = predicted_position
                position_reference = None
                position_source_from = "predicted"
                if candidate is not None:
                    previous = candidate.get("center_source_m")
                    if previous is not None:
                        delta = [predicted_position[i] - previous[i] for i in range(3)]
                        if bbox_min is not None:
                            bbox_min = [bbox_min[i] + delta[i] for i in range(3)]
                        if bbox_max is not None:
                            bbox_max = [bbox_max[i] + delta[i] for i in range(3)]
                    # The reference bbox travels with the prediction in the
                    # tracker's fixed domain, not at the last measured location.
                    # When the tracker has no measured reference box to translate
                    # the reference fields are explicitly null (never a stale box
                    # at the wrong position).
                    tracker_position = track_state.get("position_m")
                    previous_ref = candidate.get("center_reference_m")
                    if tracker_position is not None and previous_ref is not None \
                            and bbox_ref_min is not None and bbox_ref_max is not None:
                        delta_ref = [tracker_position[i] - previous_ref[i]
                                     for i in range(3)]
                        bbox_ref_min = [bbox_ref_min[i] + delta_ref[i]
                                        for i in range(3)]
                        bbox_ref_max = [bbox_ref_max[i] + delta_ref[i]
                                        for i in range(3)]
                    else:
                        bbox_ref_min = bbox_ref_max = None

        reasons = []
        for code in list(track_state.get("reason_codes") or []) \
                + list(fall_block.get("reason_codes") or []) \
                + self.cloud_timebase.reason_codes(now) \
                + self.aux_timebase.reason_codes(now):
            if code and code not in reasons:
                reasons.append(code)
        ground_context_unavailable = self._ground_context_unavailable()
        if ground_context_unavailable and "ground_monitor_unavailable" not in reasons:
            reasons.append("ground_monitor_unavailable")
        if not self._ground_valid() and "ground_unavailable" not in reasons:
            reasons.append("ground_unavailable")

        calibration_id = (self.calibration or {}).get("calibration_id")
        source = None if snapshot is None else snapshot.get("source")
        observability = self._observability(
            self.cloud_timebase.streams["cloud"], frame_valid, now)
        state = {
            "kind": STATE_KIND,
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "time_epoch": track_state.get("time_epoch"),
            "frame_id": None if source is None else source.get("frame_id"),
            "source_time_domain": SOURCE_TIME_DOMAIN,
            "clock_domain": self.clock_domain,
            "normalized_stamp_s": None,
            "time_received_s": finite_or_none(now),
            "snapshot_id": self._last_snapshot_id,
            "source": source,
            "method": METHOD,
            "input_profile": INPUT_PROFILE,
            "target_kind": "human_like" if track_state.get("track_id") else None,
            "selection_source": "operator" if track_state.get("track_id") else None,
            "observability": observability,
            "reason_codes": reasons,
            "track_id": track_state.get("track_id"),
            "track_status": track_state.get("track_status"),
            "fall_status": fall_block.get("fall_status"),
            "position_source_m": position_source,
            "position_reference_m": position_reference,
            "position_source_from": position_source_from,
            "position_predicted": position_predicted,
            "prediction_age_s": finite_or_none(track_state.get("prediction_age_s")),
            "prediction_stale": bool(track_state.get("prediction_stale")),
            "velocity_m_s": track_state.get("velocity_m_s"),
            "bbox_source_min_m": bbox_min,
            "bbox_source_max_m": bbox_max,
            "bbox_reference_min_m": bbox_ref_min,
            "bbox_reference_max_m": bbox_ref_max,
            "bbox_observed": bbox_observed,
            "center_ground_m": ground_center,
            "bbox_ground_min_m": ground_min,
            "bbox_ground_max_m": ground_max,
            "bbox_ground_from": ground_from,
            "ground_derived_id": ground_derived_id,
            "range_m": range_block,
            "coordinate": None if snapshot is None else snapshot.get("coordinate"),
            "ground": None if snapshot is None else snapshot.get("ground"),
            "calibration": {
                "calibration_id": calibration_id,
                "ground_status": None if not isinstance(self.ground, dict)
                else self.ground.get("status"),
                "schema_version": (self.calibration or {}).get("schema_version"),
            },
            "selection_version": track_state.get("selection_version"),
            "action_generation": track_state.get("action_generation"),
            "history_reset_reason": fall_block.get("history_reset_reason"),
            "requires_reselection": bool(track_state.get("requires_reselection")),
            "baseline": self.baseline.snapshot(),
            "baseline_version": (self.baseline.baseline or {}).get("baseline_version"),
            "mode_verified": bool(self.fall.settings["mode_verified"]),
            "allow_confirmed": bool(self.fall.settings["allow_confirmed"]),
            "confirmed_enabled": bool(self.fall.confirmed_enabled),
            "sensor_quality": self._sensor_quality(now),
            "event_persistence": self.event_log.report(),
            "recent_events": list(self.event_log.recent),
            "limitations": fall_block.get("limitations"),
            "target_features": feature_block,
            "fall_state": fall_block,
        }
        if observability == "invalid":
            self._mask_unobservable(state)
        elif track_state.get("track_status") in ("lost", "ambiguous"):
            state["position_predicted"] = False
            state["prediction_stale"] = True
            state["velocity_m_s"] = None
            # lost/ambiguous has no current actual candidate: it must not publish
            # a stale ground box/center as a current measurement.
            state["center_ground_m"] = None
            state["bbox_ground_min_m"] = None
            state["bbox_ground_max_m"] = None
            state["bbox_ground_from"] = "unavailable"
        return state

    def _prediction_in_source(self, position_m):
        """Map a tracker prediction back to source coordinates (or None).

        The tracker prefers the reference center when a reference transform is
        configured, so an occluded prediction is a reference-frame value. This
        returns the source-frame value via the inverse transform; with no usable
        transform it returns None rather than passing a reference value off as a
        source position.
        """
        if position_m is None:
            return None
        if not isinstance(self._reference_transform, dict):
            # No bound reference transform: the tracker predicts in source
            # coordinates. Never fall back to an unbound/raw caller transform.
            return [float(value) for value in position_m]
        try:
            from core.calibration import invert_transform, apply_transform
        except ImportError:  # pragma: no cover
            from calibration import invert_transform, apply_transform
        try:
            inverse = invert_transform(self._reference_transform)
            point = np.asarray(position_m, dtype=np.float64)[None, :]
            return [float(value) for value in apply_transform(point, inverse)[0]]
        except (ValueError, TypeError):
            return None

    def _sensor_quality(self, now):
        quality = {}
        cloud = self.cloud_timebase.streams["cloud"]
        status, age = cloud.freshness(now)
        quality["cloud"] = {"status": status, "age_s": finite_or_none(age),
                            "stamp_status": cloud.stamp_status,
                            "stamp_reason": cloud.stamp_reason,
                            "messages": cloud.messages}
        for label in ("imu", "device"):
            stream = self.aux_timebase.streams[label]
            status, age = stream.freshness(now)
            quality[label] = {"status": status, "age_s": finite_or_none(age),
                              "stamp_status": stream.stamp_status,
                              "stamp_reason": stream.stamp_reason,
                              "messages": stream.messages}
        quality["ground_valid"] = self._ground_valid()
        quality["ground_status"] = None if not isinstance(self.ground, dict) \
            else self.ground.get("status")
        quality["calibration_version"] = (self.calibration or {}).get("calibration_id")
        quality["device_motion"] = "unknown"
        if self.ground_derived is not None:
            quality["ground_derived_id"] = self._ground_derived_id
            quality["ground_monitor"] = self.ground_monitor_report
        return quality

    def status_state(self, now):
        """A state payload when no new cloud arrived (freshness refresh only).

        The measurement contents are those of the last processed frame; only the
        receive time, freshness and reason codes are recomputed, so a stalled
        stream is reported as stale/invalid instead of holding a green lock.
        A stall also settles an in-progress baseline collection on the
        receive-side monotonic clock: the pending capture is cancelled with a
        terminal ack instead of waiting for a frame that may never come, and
        the source-stamp sampling duration is not advanced by receive seconds.
        """
        now = finite_or_none(now) or 0.0
        with self._lock:
            # Watchdog side of the monitor: a stale/no-new-frame stream also
            # invalidates the current ground-observation window, so the same
            # recalibration latch rules apply as when the frame is absent.
            stream = self.cloud_timebase.streams["cloud"]
            status, _age = stream.freshness(now)
            baseline_ack = None
            if self.ground_monitor is not None and status != "fresh":
                self.ground_monitor.note_invalid()
                self.ground_monitor_report = {"status": "unknown",
                                              "reason": "no_current_frame"}
                # Settle the pending capture (or retire a ready eligibility) on
                # this receive-side clock even when no new cloud frame ever
                # arrives; the terminal ack rides the state payload as a minimal
                # additive field.
                baseline_ack = self._cancel_baseline_on_ground_loss()

            if self._last_state is None:
                state = self._state_payload(now, None, False,
                                            self.tracker.snapshot(), {}, {}, None)
            else:
                state = dict(self._last_state)
                state["time_received_s"] = finite_or_none(now)
                state["sensor_quality"] = self._sensor_quality(now)
                state["event_persistence"] = self.event_log.report()
                state["recent_events"] = list(self.event_log.recent)
                state["baseline"] = self.baseline.snapshot()
                state["observability"] = self._observability(
                    self.cloud_timebase.streams["cloud"],
                    self._latest_valid_snapshot is not None, now)
                reasons = []
                for code in (self.cloud_timebase.reason_codes(now)
                             + self.aux_timebase.reason_codes(now)
                             + list(state.get("reason_codes") or [])):
                    if code and code not in reasons:
                        reasons.append(code)
                if self._ground_context_unavailable() \
                        and "ground_monitor_unavailable" not in reasons:
                    reasons.append("ground_monitor_unavailable")
                state["reason_codes"] = reasons
                if state["observability"] == "invalid":
                    # A stalled/illegal required stream must not keep publishing
                    # the last measured position/range/box or a stale fall state.
                    self._mask_unobservable(state)
            if baseline_ack is not None:
                # Additive-only: a watchdog-cancelled capture surfaces its
                # terminal selection_ack beside the state (same ack shape as a
                # frame-driven completion; existing consumers can ignore it).
                state["baseline_ack"] = baseline_ack
            return state
