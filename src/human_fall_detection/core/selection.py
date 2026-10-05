"""Board-side selection request/ack backend (HF-05).

Only three actions are accepted: ``select``, ``release`` and
``capture_baseline``. Every request must carry ``schema_version=1`` and is bound
to a ``request_id``, the session, the source ``time_epoch``, a candidate
``snapshot_id`` and a ``selection_version``; a bare pixel box is never accepted
as a metric position. The backend is the single authority on whether a selection
succeeded.

Freshness/protocol rules (HF04-06 R2): registration and request receive times
must be finite in one monotonic domain; a future snapshot (negative age), an
expired snapshot, a cross-epoch request, an unknown schema, a non-integer
version and a mismatched calibration are all rejected *before* any state
change. The calibration version is derived from the board-side snapshot, never
trusted from the client. A new/cleared target invalidates any previous ready
baseline. Idempotency is preserved: a repeated ``request_id`` with identical
content returns the original ack and is not executed twice; the same id with
different content is rejected.
"""

import json
import math
from collections import deque

try:  # pragma: no cover - import shim
    from core.baseline import StanceBaselineCollector
except ImportError:  # pragma: no cover
    from baseline import StanceBaselineCollector

ACTIONS = ("select", "release", "capture_baseline")
ACK_KIND = "selection_ack"
SCHEMA_VERSION = 1

DEFAULT_SETTINGS = {
    "snapshot_ttl_s": 2.0,
    "request_cache_size": 64,
    "snapshot_cache_size": 16,
}

REASON_UNKNOWN = "unknown_action"
REASON_MISSING_FIELD = "missing_field"
REASON_SESSION_MISMATCH = "session_mismatch"
REASON_CONFLICT = "request_id_conflict"
REASON_NONMONOTONIC = "nonmonotonic_time"
REASON_INVALID_RECEIVE = "invalid_receive_time"
REASON_INVALID_EPOCH = "invalid_time_epoch"
REASON_UNSUPPORTED_SCHEMA = "unsupported_schema_version"
REASON_UNKNOWN_SNAPSHOT = "unknown_snapshot"
REASON_STALE_SNAPSHOT = "stale_snapshot"
REASON_FUTURE_SNAPSHOT = "snapshot_in_future"
REASON_EPOCH_MISMATCH = "epoch_mismatch"
REASON_UNKNOWN_CANDIDATE = "unknown_candidate"
REASON_INSUFFICIENT_QUALITY = "insufficient_candidate_quality"
REASON_STALE_VERSION = "stale_selection_version"
REASON_INVALID_VERSION = "invalid_selection_version"
REASON_CALIBRATION_MISMATCH = "calibration_mismatch"
REASON_NOT_LOCKED = "target_not_locked"
REASON_TRACK_MISMATCH = "track_mismatch"


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown selection setting: " + str(key))
        resolved[key] = value
    if float(resolved["snapshot_ttl_s"]) <= 0.0:
        raise ValueError("snapshot_ttl_s must be positive")
    resolved["snapshot_ttl_s"] = float(resolved["snapshot_ttl_s"])
    resolved["request_cache_size"] = int(resolved["request_cache_size"])
    resolved["snapshot_cache_size"] = int(resolved["snapshot_cache_size"])
    if resolved["request_cache_size"] <= 0 or resolved["snapshot_cache_size"] <= 0:
        raise ValueError("cache sizes must be positive")
    return resolved


def _finite(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


class SelectionBackend:
    def __init__(self, session_id, tracker, baseline=None, settings=None):
        self.session_id = session_id
        self.tracker = tracker
        self.baseline = baseline if baseline is not None else StanceBaselineCollector(session_id)
        self.settings = resolve_settings(settings)
        self.time_epoch = tracker.time_epoch if tracker.time_epoch is not None else 0
        self._snapshots = {}
        self._snapshot_order = deque()
        self._requests = {}
        self._request_order = deque()
        self._last_receive_s = None
        self._track_counter = 0

    def set_epoch(self, time_epoch):
        self.time_epoch = int(time_epoch)
        self.tracker.note_epoch(self.time_epoch)
        self.baseline.invalidate("time_epoch_changed")

    def register_snapshot(self, snapshot, receive_s):
        snapshot_id = snapshot.get("snapshot_id")
        if not snapshot_id:
            raise ValueError("snapshot needs a snapshot_id")
        receive = _finite(receive_s)
        if receive is None:
            raise ValueError("snapshot receive time must be finite")
        self._snapshots[snapshot_id] = {"receive_s": receive,
                                        "time_epoch": snapshot.get("time_epoch"),
                                        "snapshot": snapshot}
        self._snapshot_order.append(snapshot_id)
        while len(self._snapshot_order) > self.settings["snapshot_cache_size"]:
            self._snapshots.pop(self._snapshot_order.popleft(), None)

    def _ack(self, request, accepted, reason, *, track_id=None, selection_version=None,
             candidate_id=None, baseline=None, idempotent_replay=False):
        return {
            "kind": ACK_KIND,
            "schema_version": SCHEMA_VERSION,
            "request_id": request.get("request_id"),
            "action": request.get("action"),
            "session_id": self.session_id,
            "time_epoch": self.time_epoch,
            "accepted": bool(accepted),
            "reason": reason,
            "track_id": track_id,
            "candidate_id": candidate_id,
            "selection_version": selection_version,
            "baseline": baseline,
            "idempotent_replay": bool(idempotent_replay),
        }

    def _remember(self, request, ack):
        request_id = request["request_id"]
        content = json.dumps(request, sort_keys=True)
        self._requests[request_id] = {"content": content, "ack": ack}
        self._request_order.append(request_id)
        while len(self._request_order) > self.settings["request_cache_size"]:
            self._requests.pop(self._request_order.popleft(), None)

    def lookup_cached(self, request):
        """Return the prior ack/conflict for an already-handled request_id, else None.

        A pure cache read: it executes no action and applies no clock/epoch/
        schema/version/freshness gate, so a caller can replay a terminal receipt
        even when the required input is now stale or the ground monitor is
        unavailable. Identical content replays the original ack with
        ``idempotent_replay=True``; different content for the same id is
        ``request_id_conflict``. A question that was never cached returns None
        and must still pass all normal gates.
        """
        if not isinstance(request, dict):
            return None
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return None
        cached = self._requests.get(request_id)
        if cached is None:
            return None
        try:
            content = json.dumps(request, sort_keys=True)
        except (TypeError, ValueError):
            content = None
        if content == cached["content"]:
            replay = dict(cached["ack"])
            replay["idempotent_replay"] = True
            return replay
        return self._ack(request, False, REASON_CONFLICT)

    def handle(self, request, receive_s):
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return self._ack(request, False, REASON_MISSING_FIELD)

        cached = self.lookup_cached(request)
        if cached is not None:
            return cached

        receive = _finite(receive_s)
        if receive is None:
            return self._ack(request, False, REASON_INVALID_RECEIVE)
        action = request.get("action")
        if action not in ACTIONS:
            return self._ack(request, False, REASON_UNKNOWN)
        if request.get("session_id") != self.session_id:
            return self._ack(request, False, REASON_SESSION_MISMATCH)
        if not _is_int(request.get("schema_version")) \
                or request.get("schema_version") != SCHEMA_VERSION:
            return self._ack(request, False, REASON_UNSUPPORTED_SCHEMA)
        epoch = request.get("time_epoch")
        if not _is_int(epoch):
            return self._ack(request, False, REASON_INVALID_EPOCH)
        if epoch != self.time_epoch:
            return self._ack(request, False, REASON_EPOCH_MISMATCH)
        if self._last_receive_s is not None and receive < self._last_receive_s:
            return self._ack(request, False, REASON_NONMONOTONIC)
        self._last_receive_s = receive

        if action == "select":
            ack = self._select(request, receive)
        elif action == "release":
            ack = self._release(request)
        else:
            ack = self._capture_baseline(request, receive)
        self._remember(request, ack)
        return ack

    def _expected_version(self, request):
        version = request.get("selection_version")
        if not _is_int(version):
            return None, self._ack(request, False, REASON_INVALID_VERSION)
        current = int(self.tracker.selection_version)
        if version < current:
            return None, self._ack(request, False, REASON_STALE_VERSION)
        if version > current:
            return None, self._ack(request, False, REASON_INVALID_VERSION)
        return current, None

    def _snapshot_entry(self, request, receive_s):
        snapshot_id = request.get("snapshot_id")
        if not snapshot_id:
            return None, self._ack(request, False, REASON_MISSING_FIELD)
        entry = self._snapshots.get(snapshot_id)
        if entry is None:
            return None, self._ack(request, False, REASON_UNKNOWN_SNAPSHOT)
        age = receive_s - entry["receive_s"]
        if age < 0.0:
            return None, self._ack(request, False, REASON_FUTURE_SNAPSHOT)
        if age > self.settings["snapshot_ttl_s"]:
            return None, self._ack(request, False, REASON_STALE_SNAPSHOT)
        if entry["time_epoch"] != self.time_epoch:
            return None, self._ack(request, False, REASON_EPOCH_MISMATCH)
        return entry, None

    def _lookup_candidate(self, request, receive_s):
        entry, error = self._snapshot_entry(request, receive_s)
        if error is not None:
            return None, None, error
        candidate_id = request.get("candidate_id")
        if not candidate_id:
            return None, None, self._ack(request, False, REASON_MISSING_FIELD)
        for candidate in entry["snapshot"].get("candidates", []):
            if candidate.get("candidate_id") == candidate_id:
                return entry, candidate, None
        return None, None, self._ack(request, False, REASON_UNKNOWN_CANDIDATE)

    @staticmethod
    def _snapshot_calibration(entry):
        calibration = (entry["snapshot"].get("calibration") or {})
        return calibration.get("calibration_id")

    def _select(self, request, receive_s):
        current, error = self._expected_version(request)
        if error is not None:
            return error
        entry, candidate, error = self._lookup_candidate(request, receive_s)
        if error is not None:
            return error
        quality = candidate.get("quality") or {}
        if not quality.get("sufficient_points", False):
            return self._ack(request, False, REASON_INSUFFICIENT_QUALITY)
        board_calibration = self._snapshot_calibration(entry)
        requested_calibration = request.get("calibration_version")
        if requested_calibration is not None and requested_calibration != board_calibration:
            return self._ack(request, False, REASON_CALIBRATION_MISMATCH)
        self.baseline.invalidate("target_changed")
        source_stamp_s = (entry["snapshot"].get("source") or {}).get("source_stamp_s")
        self._track_counter += 1
        track_id = "t{:04d}".format(self._track_counter)
        new_version = current + 1
        self.tracker.select(track_id, self.time_epoch, candidate=candidate,
                            calibration_version=board_calibration,
                            selection_version=new_version,
                            source_stamp_s=source_stamp_s, receive_s=receive_s)
        return self._ack(request, True, None, track_id=track_id,
                         selection_version=new_version,
                         candidate_id=candidate.get("candidate_id"))

    def _release(self, request):
        current, error = self._expected_version(request)
        if error is not None:
            return error
        requested_track = request.get("track_id")
        if requested_track is not None and requested_track != self.tracker.track_id:
            return self._ack(request, False, REASON_TRACK_MISMATCH,
                             selection_version=current)
        self.tracker.release()
        self.tracker.selection_version = current + 1
        self.baseline.invalidate("target_released")
        return self._ack(request, True, None, selection_version=current + 1,
                         track_id=None)

    def _capture_baseline(self, request, receive_s):
        current, error = self._expected_version(request)
        if error is not None:
            return error
        if self.tracker.track_status != "locked":
            return self._ack(request, False, REASON_NOT_LOCKED,
                             selection_version=current)
        requested_track = request.get("track_id")
        if requested_track is not None and requested_track != self.tracker.track_id:
            return self._ack(request, False, REASON_TRACK_MISMATCH,
                             selection_version=current)
        start_source_s = self.tracker.last_measured_source()
        if start_source_s is None:
            start_source_s = receive_s
        self.baseline.start(self.tracker.track_id, self.tracker.calibration_version,
                            start_source_s=start_source_s,
                            operator_confirmed=bool(request.get("operator_confirmed")),
                            time_epoch=self.time_epoch,
                            selection_version=current,
                            action_generation=self.tracker.action_generation)
        return self._ack(request, True, None, track_id=self.tracker.track_id,
                         selection_version=current,
                         baseline=self.baseline.snapshot())
