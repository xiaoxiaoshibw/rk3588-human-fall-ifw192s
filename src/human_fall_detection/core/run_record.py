"""Run-level operational records for the field-trial node (additive only).

This module never decides anything: it observes the state payloads the node
already publishes and appends *operational* records to a per-run JSONL file.

It exists because the algorithm only persists ``confirmed`` fall events
(``core/fall_state.py``), while a field trial needs to explain:

- target acquisition / release transitions,
- baseline collection / ready / reset,
- why a frame was "not determinable" (observability + reason codes),
- short-lived *suspected* hints **without** turning them into algorithm events,
- worker / input / service health changes,
- periodic performance summaries.

Every record is bound to the run identity (``run_id`` / ``release_id`` /
``scene_id``), the session, the track and the measured source frame, so a page
reconnect can never replay an old hint as a new alarm: notifications carry a
monotonically increasing ``notification_id``.

Pure stdlib so the board's Python 3.8 / NumPy 1.17 environment can run it.
"""

import json
import os
import time

RECORD_KIND = "run_record"
SCHEMA_VERSION = 1

# fall_status values that the state machine can produce; kept here so a record
# reader does not need to import the algorithm module.
_FALL_ORDER = ("unknown", "upright", "descending", "low_posture_unclassified",
               "suspected", "recovering", "confirmed")


def _percentile(sorted_values, fraction):
    """Nearest-rank percentile over an already sorted, non-empty list."""
    if not sorted_values:
        return None
    index = int(round(fraction * (len(sorted_values) - 1)))
    return float(sorted_values[max(0, min(index, len(sorted_values) - 1))])


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return float(value)


def _source_of(state):
    source = state.get("source") if isinstance(state, dict) else None
    if not isinstance(source, dict):
        return None
    return {"seq": source.get("seq"), "stamp_secs": _finite(source.get("stamp_secs")),
            "stamp_nsecs": _finite(source.get("stamp_nsecs")),
            "frame_id": source.get("frame_id")}


def _reason_key(state):
    codes = state.get("reason_codes")
    if not isinstance(codes, (list, tuple)):
        return ()
    return tuple(sorted(str(code) for code in codes if code))


class RunRecorder:
    """Append operational records for one node run; never raises to the caller."""

    def __init__(self, path, *, run_id, release_id=None, scene_id=None, session_id=None,
                 max_bytes=8 * 1024 * 1024, max_archives=4, perf_interval_s=30.0,
                 wall_fn=None):
        self.path = str(path)
        self.run_id = str(run_id)
        self.release_id = None if release_id is None else str(release_id)
        self.scene_id = None if scene_id is None else str(scene_id)
        self.session_id = None if session_id is None else str(session_id)
        self.max_bytes = int(max_bytes)
        self.max_archives = max(0, int(max_archives))
        self.perf_interval_s = float(perf_interval_s)
        self._wall_fn = wall_fn or time.time
        self._seq = 0
        self._records = 0
        self._notifications = 0
        self._archive = 0
        self._bytes = 0
        self._handle = None
        self.started_wall = self._wall_fn()
        self.write_error = None
        self.last_notification = None
        self._last = {}
        self._perf_samples = {"process_s": [], "receive_to_finish_s": [],
                              "queue_age_s": [], "queue_dropped": []}
        self._perf_window_started = self.started_wall
        self._perf_windows = 0
        self._perf_last_sample = None
        self._perf_dropped_base = None
        self._perf_frame_count = 0
        self._open()

    # -- file plumbing ---------------------------------------------------
    def _open(self):
        try:
            directory = os.path.dirname(os.path.abspath(self.path))
            if directory:
                os.makedirs(directory, exist_ok=True)
            self._handle = open(self.path, "a", encoding="utf-8")
            try:
                self._bytes = os.path.getsize(self.path)
            except OSError:
                self._bytes = 0
        except OSError as exc:
            self._handle = None
            self.write_error = "open_failed: %s" % exc

    def _rotate(self):
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass
            self._handle = None
        base = self.path
        try:
            os.replace(base, "%s.%d" % (base, self._archive + 1))
        except OSError as exc:
            self.write_error = "rotate_failed: %s" % exc
        self._archive += 1
        # Keep the archive count bounded; drop only this run's own archives.
        stale = self._archive - self.max_archives
        if stale > 0:
            try:
                os.remove("%s.%d" % (base, stale))
            except OSError:
                pass
        self._open()

    def _write(self, record):
        record = dict(record)
        record.setdefault("kind", RECORD_KIND)
        record.setdefault("schema_version", SCHEMA_VERSION)
        record["run_id"] = self.run_id
        record["release_id"] = self.release_id
        record["scene_id"] = self.scene_id
        if self.session_id is not None:
            record.setdefault("session_id", self.session_id)
        self._seq += 1
        record["seq"] = self._seq
        record["ts_wall"] = self._wall_fn()
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"),
                          allow_nan=False, default=str)
        if self._handle is None:
            self._open()
        if self._handle is None:
            return None
        try:
            self._handle.write(line + "\n")
            self._handle.flush()
            self._bytes += len(line.encode("utf-8")) + 1
            self._records += 1
        except (OSError, ValueError) as exc:
            self.write_error = "write_failed: %s" % exc
            return None
        if self._bytes >= self.max_bytes:
            self._rotate()
        return record

    # -- public API ------------------------------------------------------
    def start(self, meta=None):
        payload = dict(meta or {})
        payload["event"] = "run_start"
        payload["started_wall"] = self.started_wall
        payload["pid"] = os.getpid()
        return self._write(payload)

    def stop(self, reason, detail=None):
        record = {"event": "run_stop", "reason": str(reason),
                  "detail": detail if isinstance(detail, dict) else None}
        result = self._write(record)
        self.close()
        return result

    def close(self):
        self._flush_performance(force=True)
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError:
                pass
            self._handle = None

    def report(self):
        return {
            "run_id": self.run_id,
            "release_id": self.release_id,
            "scene_id": self.scene_id,
            "started_wall": self.started_wall,
            "records": self._records,
            "notifications": self._notifications,
            "last_notification": self.last_notification,
            "write_error": self.write_error,
            "log_bytes": self._bytes,
            "perf_windows": self._perf_windows,
        }

    # -- state observation ----------------------------------------------
    def observe(self, state, performance=None):
        """Append records for any transition visible in ``state`` (never raises)."""
        try:
            return self._observe(state, performance)
        except Exception as exc:  # noqa: BLE001 - diagnostics must not break the node
            self.write_error = "observe_failed: %s" % exc
            return []

    def _observe(self, state, performance):
        if not isinstance(state, dict):
            return []
        emitted = []
        session = state.get("session_id")
        if session is not None and self.session_id is None:
            self.session_id = str(session)
        binding = {
            "session_id": session,
            "time_epoch": state.get("time_epoch"),
            "track_id": state.get("track_id"),
            "action_generation": state.get("action_generation"),
            "selection_version": state.get("selection_version"),
            "source": _source_of(state),
        }

        target = state.get("track_status") or "unselected"
        previous = self._last.get("target")
        if target != previous:
            acquisition = state.get("acquisition") or {}
            emitted.append(self._emit(
                "target", "target_transition", previous, target, binding,
                detail={"acquisition_status": acquisition.get("status"),
                        "acquisition_reason": acquisition.get("reason"),
                        "requires_reselection": state.get("requires_reselection"),
                        "history_reset_reason": state.get("history_reset_reason")}))

        baseline = state.get("baseline") or {}
        baseline_key = [baseline.get("status"), baseline.get("reason")]
        previous = self._last.get("baseline")
        if baseline_key != previous:
            emitted.append(self._emit(
                "baseline", "baseline_transition", previous, baseline_key, binding,
                detail={"status": baseline.get("status"), "reason": baseline.get("reason"),
                        "sample_count": baseline.get("sample_count"),
                        "track_id": baseline.get("track_id"),
                        "calibration_version": baseline.get("calibration_version")}))

        fall = state.get("fall_status")
        fall_previous = self._last.get("fall")
        if fall != fall_previous:
            fall_block = state.get("fall_state") or {}
            emitted.append(self._emit(
                "fall", "fall_transition", fall_previous, fall, binding,
                detail={"state_since_source_s": fall_block.get("state_since_source_s"),
                        "reason_codes": fall_block.get("reason_codes"),
                        "confirmed_enabled": state.get("confirmed_enabled"),
                        "mode_verified": state.get("mode_verified")}))

        observability = state.get("observability")
        previous = self._last.get("observability")
        if observability != previous:
            emitted.append(self._emit(
                "observability", "observability_transition", previous, observability, binding,
                detail={"sensor_quality": _cloud_quality(state)}))

        reasons = _reason_key(state)
        previous = self._last.get("reasons")
        if reasons != previous:
            emitted.append(self._emit(
                "reasons", "reason_change", _jsonable(previous), reasons, binding,
                detail={"reason_codes": list(reasons)}))

        input_source = state.get("input_source") or {}
        mode = input_source.get("mode") if isinstance(input_source, dict) else None
        previous = self._last.get("input_source")
        if mode != previous:
            emitted.append(self._emit(
                "input_source", "input_source_change", previous, mode, binding,
                detail={"input_source": input_source}))

        worker = state.get("worker") or {}
        worker_key = bool(worker.get("healthy")) if isinstance(worker, dict) \
            and "healthy" in worker else None
        previous = self._last.get("worker")
        if worker_key != previous:
            emitted.append(self._emit(
                "worker", "worker_transition", previous, worker_key, binding,
                detail={"worker": worker}))

        emitted.extend(self._note_suspected(fall, fall_previous, state, binding))
        self._observe_performance(performance)
        return [record for record in emitted if record is not None]

    def _note_suspected(self, fall, previous, state, binding):
        """Suspected hints get their own id so a page reload cannot replay them."""
        records = []
        if fall == previous:
            return records
        if previous == "suspected" and self.last_notification is not None:
            fall_block = state.get("fall_state") or {}
            notice = dict(self.last_notification)
            record = self._write({
                "event": "suspected_notification",
                "action": "end",
                "notification_id": notice.get("notification_id"),
                "started_wall": notice.get("started_wall"),
                "duration_s": max(0.0, self._wall_fn() - float(notice.get("started_wall") or 0.0)),
                "to_state": fall,
                "binding": binding,
                "detail": {"reason_codes": fall_block.get("reason_codes"),
                           "height_median_m": _finite(
                               (fall_block.get("features") or {}).get("height_median_m")),
                           "state_since_source_s": fall_block.get("state_since_source_s")},
            })
            self.last_notification = dict(notice, ended_wall=self._wall_fn(), end_state=fall)
            self._last["notification_closed"] = notice.get("notification_id")
            records.append(record)
        if fall == "suspected" and previous != "suspected":
            self._notifications += 1
            notification_id = "%s:suspected:%d" % (self.run_id, self._notifications)
            fall_block = state.get("fall_state") or {}
            notice = {
                "notification_id": notification_id,
                "kind": "suspected_fall_hint",
                "state": "suspected",
                "started_wall": self._wall_fn(),
                "track_id": state.get("track_id"),
                "action_generation": state.get("action_generation"),
                "source": _source_of(state),
                "reason_codes": list(_reason_key(state)),
                "height_median_m": _finite((fall_block.get("features") or {}).get(
                    "height_median_m")),
                "confirmed_enabled": state.get("confirmed_enabled"),
            }
            record = self._write({
                "event": "suspected_notification",
                "action": "start",
                "notification_id": notification_id,
                "state": "suspected",
                "binding": binding,
                "detail": {"fall_status": fall,
                           "reason_codes": fall_block.get("reason_codes"),
                           "height_median_m": notice["height_median_m"],
                           "state_since_source_s": fall_block.get("state_since_source_s"),
                           "confirmed_enabled": state.get("confirmed_enabled"),
                           "mode_verified": state.get("mode_verified")},
            })
            self.last_notification = notice
            records.append(record)
        return records

    def _observe_performance(self, performance):
        if not isinstance(performance, dict):
            return
        # Close the previous window before this sample is added, so a sample
        # always belongs to exactly one window.
        if self._wall_fn() - self._perf_window_started >= self.perf_interval_s:
            self._flush_performance()
        # Status/watchdog publications can reuse the last completed frame.
        finish = _finite(performance.get("process_finish_s"))
        if finish is not None:
            identity = (performance.get("frame_count"), finish)
            if identity == self._perf_last_sample:
                return
            self._perf_last_sample = identity
        samples = self._perf_samples
        for key in ("process_s", "receive_to_finish_s", "queue_age_s"):
            value = _finite(performance.get(key))
            if value is not None:
                if key == "process_s":
                    self._perf_frame_count += 1
                samples[key].append(value)
                if len(samples[key]) > 4096:
                    del samples[key][:-2048]
        dropped = performance.get("queue_dropped")
        if isinstance(dropped, int) and not isinstance(dropped, bool):
            if self._perf_dropped_base is None:
                self._perf_dropped_base = dropped
            samples["queue_dropped"].append(dropped)
            if len(samples["queue_dropped"]) > 4096:
                del samples["queue_dropped"][1:-2048]

    def _flush_performance(self, force=False):
        if not force and not any(self._perf_samples.values()):
            return
        now = self._wall_fn()
        window_s = now - self._perf_window_started
        if window_s <= 0 and not force:
            return
        summary = {}
        for key, values in self._perf_samples.items():
            if not values:
                continue
            if key == "queue_dropped":
                summary["queue_dropped_last"] = int(values[-1])
                summary["queue_dropped_first"] = int(values[0])
                # Carry the preceding window's last counter across the boundary.
                summary["queue_dropped_delta_base"] = self._perf_dropped_base
                summary["queue_dropped_delta"] = int(values[-1]) - self._perf_dropped_base
                self._perf_dropped_base = int(values[-1])
                summary["queue_dropped_samples"] = len(values)
                continue
            ordered = sorted(values)
            summary[key] = {
                "samples": len(ordered),
                "p50": _percentile(ordered, 0.50),
                "p95": _percentile(ordered, 0.95),
                "p99": _percentile(ordered, 0.99),
                "max": ordered[-1],
            }
        count = self._perf_frame_count
        record = {
            "event": "performance_window",
            "window_s": round(window_s, 3),
            "frames": count,
            "frame_rate_hz": (count / window_s) if window_s > 0 else None,
            "summary": summary,
        }
        self._write(record)
        self._perf_windows += 1
        self._perf_window_started = now
        self._perf_frame_count = 0
        for key in self._perf_samples:
            self._perf_samples[key] = []

    def _emit(self, key, event, previous, current, binding, detail=None):
        self._last[key] = current
        return self._write({
            "event": event,
            "from": _jsonable(previous),
            "to": _jsonable(current),
            "binding": binding,
            "detail": detail,
        })


def _jsonable(value):
    if isinstance(value, tuple):
        return list(value)
    return value


def _cloud_quality(state):
    quality = state.get("sensor_quality") or {}
    cloud = quality.get("cloud") if isinstance(quality, dict) else None
    if not isinstance(cloud, dict):
        return None
    return {"status": cloud.get("status"), "age_s": _finite(cloud.get("age_s")),
            "stamp_status": cloud.get("stamp_status")}
