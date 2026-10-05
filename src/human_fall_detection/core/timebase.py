"""Time-base bookkeeping for the HF point-cloud / IMU / device streams (HF-02).

Design rules (see docs/human_fall/CONTRACT.md section 4, frozen):

- Source stamps are device seconds with an unanchored origin. Raw integer
  ``sec``/``nsec`` pairs and the node receive time are always preserved; no UTC
  label is ever attached.
- The HF-01 stamp classification (``first/ok/repeated/regressed/forward_jump/
  invalid``) is reused, not reimplemented. ``repeated/regressed/forward_jump``
  rebuild the epoch and clear temporal history; ``invalid`` avoids the epoch
  change and keeps the previous valid comparison baseline.
- Freshness is computed from a caller-provided clock: ``time.monotonic`` for
  online nodes, message/bag time for offline replay. This module never reads
  the wall clock itself. Pairing additionally requires a usable ``now``: an
  expired stream, an invalid receive time or a currently invalid frame never
  falls back to cached observations.
- Same-looking stamps, equal ``frame_id`` or a good fit of receive times are NOT
  proof of a shared clock. A physical offset correction is only allowed when
  explicit evidence (vendor time convention or a controlled common event) is
  supplied; otherwise the mapping stays ``unknown``.
- A verified mapping binds an ordered stream pair and is stored as
  ``stamp[second] = stamp[first] + offset_s``. Pairing compares corrected
  residuals (raw stamps are always kept) and both argument orders work.
  ``controlled_common_event`` evidence applies only to the epoch it was
  measured in; ``vendor_protocol`` is a permanent device relation and survives
  later epoch rebuilds.
"""

import math
from collections import deque

from sensor_health import (check_stamp, finite_or_none, raw_stamp, stamp_seconds,
                           valid_stamp)

KIND = "timebase"
SCHEMA_VERSION = 1
SOURCE_TIME_DOMAIN = "device_stamp_s_unanchored"
CLOCK_DOMAINS = ("monotonic", "message_time")
UNIT_MISMATCH_RATIO = 1e6
SYNC_EVIDENCE = ("vendor_protocol", "controlled_common_event")
# A vendor protocol describes a permanent device relation; a controlled common
# event measures one offset in one clock epoch only.
PERMANENT_SYNC_EVIDENCE = ("vendor_protocol",)
MAX_ABS_OFFSET_S = 86400.0
MAX_SYNC_UNCERTAINTY_S = 86400.0
UNVERIFIED_SYNC_CODE = "clock_cross_stream_unverified"
UNVERIFIED_PAIRING_CODE = "cross_stream_pairing_unverified"
SYNC_EPOCH_INVALIDATED_CODE = "sync_evidence_epoch_invalidated"
PAIRING_TIME_INVALID_CODE = "pairing_time_invalid"
UNIT_MISMATCH_CODE = "unit_mismatch_suspected"


def split_device_seconds(value):
    """Split float device seconds into an (sec, nsec) pair, carrying at 1e9.

    The C++ publish path rounds the fractional part; when the fraction rounds
    up to a full second the result must carry instead of emitting ``nsec=1e9``.
    Returns ``None`` for non-finite or negative input (never fabricates a pair).
    """
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(seconds) or seconds < 0.0:
        return None
    sec = int(math.floor(seconds))
    # floor(x + 0.5) mirrors C++ std::round (half away from zero), which the
    # publish path uses; Python's built-in round() is banker's rounding.
    nsec = int(math.floor((seconds - sec) * 1e9 + 0.5))
    if nsec >= 1000000000:
        nsec -= 1000000000
        sec += 1
    return sec, nsec


def linear_fit(xs, ys):
    """Least-squares fit y = slope*x + intercept with an RMS residual.

    Used for receive-time vs source-time transparency only: a good fit of one
    stream says nothing about cross-stream physical synchronisation.
    """
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0.0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    intercept = mean_y - slope * mean_x
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    rms = math.sqrt(sum(r * r for r in residuals) / count)
    return {"slope": slope, "intercept": intercept, "rms_residual_s": rms,
            "samples": count}


def _median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return 0.5 * (ordered[middle - 1] + ordered[middle])


def stamp_from_health_block(block):
    """Read raw sec/nsec from a ``/human_fall/health`` topic block.

    Frozen v1 blocks carry ``stamp_secs``/``stamp_nsecs``. Pre-freeze DRAFT
    samples (first ``hf01_verify`` round) may lack them; this reader then falls
    back to splitting ``source_stamp_s`` without rewriting the original data.
    """
    if not isinstance(block, dict):
        return None
    secs = block.get("stamp_secs")
    nsecs = block.get("stamp_nsecs")
    if secs is None and nsecs is None:
        source = block.get("source_stamp_s")
        split = split_device_seconds(source) if source is not None else None
        if split is None:
            return None
        return {"stamp_secs": split[0], "stamp_nsecs": split[1],
                "source_stamp_s": float(source), "compatibility": "draft_source_stamp_s"}
    if not valid_stamp((secs, nsecs)):
        return {"stamp_secs": secs, "stamp_nsecs": nsecs, "source_stamp_s": None,
                "compatibility": "frozen_stamp_fields"}
    return {"stamp_secs": int(secs), "stamp_nsecs": int(nsecs),
            "source_stamp_s": stamp_seconds((secs, nsecs)),
            "compatibility": "frozen_stamp_fields"}


class TimeStream:
    """Per-stream source stamp state with a bounded traceability cache."""

    def __init__(self, label, timeout_s, required=False, max_forward_jump_s=30.0,
                 cache_size=32):
        self.label = label
        self.timeout_s = float(timeout_s)
        self.required = bool(required)
        self.max_forward_jump_s = float(max_forward_jump_s)
        self.cache_size = max(1, int(cache_size))
        self.entries = deque(maxlen=self.cache_size)
        self.messages = 0
        self.first_receive_s = None
        # last_receive_s stays the last *legal* receive baseline; receive_status
        # describes the current frame's receive quality separately, so an
        # invalid receive time cannot masquerade as a fresh observation.
        self.last_receive_s = None
        self.receive_status = "none"
        self.last_stamp = None
        self.stamp_status = "none"
        self.stamp_reason = None
        self.stamp_secs = None
        self.stamp_nsecs = None
        self.source_stamp_s = None
        self.frame_id = None

    def note(self, seq, stamp, now, frame_id=None):
        """Classify one raw stamp; returns (entry, discontinuity)."""
        receive = finite_or_none(now)
        self.messages += 1
        if receive is not None and self.first_receive_s is None:
            self.first_receive_s = receive
        if receive is not None:
            self.last_receive_s = receive
        self.receive_status = "ok" if receive is not None else "invalid"
        if frame_id is not None:
            self.frame_id = frame_id
        try:
            secs, nsecs = raw_stamp(stamp)
        except (TypeError, ValueError, OverflowError):
            secs, nsecs = None, None
        if secs is None or nsecs is None:
            status, reason, discontinuity = "invalid", self.label + "_stamp_invalid", False
        else:
            status, reason, discontinuity = check_stamp(
                self.label, self.last_stamp, (secs, nsecs), self.max_forward_jump_s)
        self.stamp_status = status
        self.stamp_reason = reason
        self.stamp_secs = secs
        self.stamp_nsecs = nsecs
        if status == "invalid":
            self.source_stamp_s = None
        else:
            self.last_stamp = (secs, nsecs)
            self.source_stamp_s = stamp_seconds((secs, nsecs))
        entry = {"seq": seq, "stamp_secs": secs, "stamp_nsecs": nsecs,
                 "source_stamp_s": finite_or_none(self.source_stamp_s),
                 "time_received_s": receive, "stamp_status": status,
                 "stamp_reason": reason, "frame_id": frame_id}
        if discontinuity:
            self.entries.clear()
        self.entries.append(entry)
        return entry, discontinuity

    def clear_history(self):
        self.entries.clear()

    def recent(self, count=None):
        if count is None:
            return list(self.entries)
        return list(self.entries)[-max(0, int(count)):]

    def valid_entries(self):
        """Stamps with a legal source value; history/traceability, not online use."""
        return [entry for entry in self.entries if entry["source_stamp_s"] is not None]

    def usable_entries(self, now):
        """Observations acceptable for online pairing at ``now``.

        An entry needs a valid receive time and an age inside the stream
        timeout; a replay clock that moves backwards makes the age negative and
        the entry unusable instead of being clamped to fresh.
        """
        reference = finite_or_none(now)
        if reference is None:
            return []
        usable = []
        for entry in self.valid_entries():
            received = entry["time_received_s"]
            if received is None:
                continue
            age = reference - received
            if 0.0 <= age <= self.timeout_s:
                usable.append(entry)
        return usable

    def freshness(self, now):
        """Freshness of the *current* frame, never inherited from an older one.

        The last legal receive time remains the age baseline, but if the most
        recent frame itself arrived with a missing/non-finite receive time the
        stream is ``stale`` with no age instead of appearing fresh on the
        strength of the previous frame.
        """
        reference = finite_or_none(now)
        if self.messages == 0:
            return "no_data", None
        if self.receive_status != "ok" or self.last_receive_s is None or reference is None:
            return "stale", None
        age = reference - self.last_receive_s
        if age < 0.0 or age > self.timeout_s:
            return "stale", age
        return "fresh", age

    def current(self):
        return {"label": self.label, "required": self.required, "messages": self.messages,
                "frame_id": self.frame_id, "stamp_status": self.stamp_status,
                "stamp_reason": self.stamp_reason, "stamp_secs": self.stamp_secs,
                "stamp_nsecs": self.stamp_nsecs,
                "source_stamp_s": finite_or_none(self.source_stamp_s),
                "receive_status": self.receive_status,
                "history_size": len(self.entries)}


class TimebaseSession:
    """Session-level epoch, freshness and bounded-cache pairing.

    ``clock_domain`` labels which clock the caller passes as ``now``:
    ``monotonic`` for online nodes, ``message_time`` for offline replay driven
    by message/bag time. The module itself reads no clock.
    """

    def __init__(self, session_id, clock_domain="monotonic", max_forward_jump_s=30.0,
                 cache_size=32):
        if clock_domain not in CLOCK_DOMAINS:
            raise ValueError("clock_domain must be one of " + repr(CLOCK_DOMAINS))
        self.session_id = session_id
        self.clock_domain = clock_domain
        self.max_forward_jump_s = float(max_forward_jump_s)
        self.cache_size = max(1, int(cache_size))
        self.time_epoch = 0
        self.epoch_reason = None
        self.streams = {}
        self.sync = {"cross_stream_same_clock_verified": False,
                     "host_anchor_verified": False,
                     "physical_offset_s": None,
                     "offset_uncertainty_s": None,
                     "offset_evidence": "none",
                     "offset_first_label": None,
                     "offset_second_label": None,
                     "offset_time_epoch": None,
                     "evidence_records": []}

    def register(self, label, timeout_s, required=False):
        if label in self.streams:
            raise ValueError("stream already registered: " + str(label))
        self.streams[label] = TimeStream(label, timeout_s, required,
                                         self.max_forward_jump_s, self.cache_size)
        return self.streams[label]

    def note(self, label, seq, stamp, now, frame_id=None):
        """Feed one raw stamp; rebuild the epoch on repeated/regressed/jump.

        An invalid stamp never bumps the epoch and keeps the previous valid
        comparison baseline. An epoch rebuild clears the temporal history and
        suspends epoch-bound (controlled) mapping evidence, so pairing cannot
        silently keep using an offset measured before the clock restart.
        """
        stream = self.streams.get(label)
        if stream is None:
            raise KeyError("unknown stream: " + str(label))
        entry, discontinuity = stream.note(seq, stamp, now, frame_id)
        if discontinuity:
            self.time_epoch += 1
            self.epoch_reason = entry["stamp_reason"]
            for other in self.streams.values():
                if other is not stream:
                    other.clear_history()
            self._refresh_sync()
        entry["time_epoch"] = self.time_epoch
        return {"label": label, "stamp_status": entry["stamp_status"],
                "stamp_reason": entry["stamp_reason"],
                "source_stamp_s": entry["source_stamp_s"],
                "time_epoch": self.time_epoch,
                "epoch_reset": bool(discontinuity),
                "cross_stream_same_clock_verified":
                    self.sync["cross_stream_same_clock_verified"]}

    def unit_mismatch(self):
        """Compare recent stamp scales/rates of every registered pair."""
        valid = {label: stream.valid_entries() for label, stream in self.streams.items()}
        ratios = []
        labels = sorted(self.streams)
        for index, first in enumerate(labels):
            for second in labels[index + 1:]:
                first_entries, second_entries = valid[first], valid[second]
                if len(first_entries) < 2 or len(second_entries) < 2:
                    continue
                first_scale = _median([abs(entry["source_stamp_s"]) for entry in first_entries])
                second_scale = _median([abs(entry["source_stamp_s"]) for entry in second_entries])
                first_rate = _median([first_entries[i]["source_stamp_s"] - first_entries[i - 1]["source_stamp_s"]
                                      for i in range(1, len(first_entries))])
                second_rate = _median([second_entries[i]["source_stamp_s"] - second_entries[i - 1]["source_stamp_s"]
                                       for i in range(1, len(second_entries))])
                ratios.append({"pair": [first, second],
                               "scale_ratio": self._safe_ratio(first_scale, second_scale),
                               "rate_ratio": self._safe_ratio(first_rate, second_rate)})
        suspected = any(
            (item["scale_ratio"] is not None
             and (item["scale_ratio"] > UNIT_MISMATCH_RATIO
                  or item["scale_ratio"] < 1.0 / UNIT_MISMATCH_RATIO))
            or (item["rate_ratio"] is not None
                and (item["rate_ratio"] > UNIT_MISMATCH_RATIO
                     or item["rate_ratio"] < 1.0 / UNIT_MISMATCH_RATIO))
            for item in ratios)
        return suspected, ratios

    @staticmethod
    def _safe_ratio(first, second):
        if first is None or second is None or second == 0.0:
            return None
        return first / second

    def clock_fit(self, label):
        """Fit receive time against source stamp for one stream.

        Result is explicitly ``transport_fit_only``: a linear fit cannot verify
        a shared hardware clock or a physical offset.
        """
        stream = self.streams.get(label)
        if stream is None:
            raise KeyError("unknown stream: " + str(label))
        entries = [entry for entry in stream.valid_entries()
                   if entry["time_received_s"] is not None]
        fit = linear_fit([entry["source_stamp_s"] for entry in entries],
                         [entry["time_received_s"] for entry in entries])
        if fit is None:
            return {"label": label, "classification": "insufficient_data", "fit": None}
        fit = dict(fit)
        fit["classification"] = "transport_fit_only"
        return {"label": label, "classification": "transport_fit_only", "fit": fit}

    def _record_applies(self, record):
        return (record["evidence"] in PERMANENT_SYNC_EVIDENCE
                or record["time_epoch"] == self.time_epoch)

    def _refresh_sync(self):
        active = None
        for record in self.sync["evidence_records"]:
            if self._record_applies(record):
                active = record
        self.sync["cross_stream_same_clock_verified"] = active is not None
        self.sync["physical_offset_s"] = active["offset_s"] if active else None
        self.sync["offset_uncertainty_s"] = active["uncertainty_s"] if active else None
        self.sync["offset_evidence"] = active["evidence"] if active else "none"
        self.sync["offset_first_label"] = active["first_label"] if active else None
        self.sync["offset_second_label"] = active["second_label"] if active else None
        self.sync["offset_time_epoch"] = active["time_epoch"] if active else None

    def _active_mapping(self, first_label, second_label):
        """Latest verified record for this exact stream pair, or None."""
        for record in reversed(self.sync["evidence_records"]):
            if ({record["first_label"], record["second_label"]}
                    == {first_label, second_label} and self._record_applies(record)):
                return record
        return None

    def _pair_ever_verified(self, first_label, second_label):
        return any({record["first_label"], record["second_label"]}
                   == {first_label, second_label}
                   for record in self.sync["evidence_records"])

    @staticmethod
    def _mapping_report(record):
        return {"first_label": record["first_label"],
                "second_label": record["second_label"],
                "offset_s": record["offset_s"],
                "uncertainty_s": record["uncertainty_s"],
                "evidence": record["evidence"],
                "time_epoch": record["time_epoch"],
                "direction": "second = first + offset_s"}

    def apply_sync_evidence(self, evidence, offset_s=None, uncertainty_s=None, note=None,
                            first_label=None, second_label=None):
        """Record a physical offset mapping for one ordered stream pair.

        The accepted mapping is ``stamp[second_label] = stamp[first_label] +
        offset_s``: a positive offset means the second stream's clock reads
        ahead. With exactly two registered streams the pair is inferred in
        registration order; with more streams the labels are required so a
        local evidence cannot be spread over every registered stream.
        Receive-time fits, similar stamps or equal frame_ids are rejected here;
        without accepted evidence the mapping stays ``unknown``. The record is
        bound to the session, stream pair and current ``time_epoch``: a later
        epoch rebuild suspends controlled-event records and keeps them in the
        evidence history.
        """
        if evidence not in SYNC_EVIDENCE:
            raise ValueError(
                "unsupported sync evidence {!r}; only vendor_protocol or "
                "controlled_common_event may support a physical offset".format(evidence))
        if offset_s is None:
            raise ValueError("offset_s must be a finite number; state 0.0 explicitly")
        offset = float(offset_s)
        if not math.isfinite(offset) or abs(offset) > MAX_ABS_OFFSET_S:
            raise ValueError("offset_s must be finite and |offset_s| <= "
                             + repr(MAX_ABS_OFFSET_S))
        uncertainty = None if uncertainty_s is None else float(uncertainty_s)
        if uncertainty is not None and (not math.isfinite(uncertainty)
                                        or uncertainty < 0.0
                                        or uncertainty > MAX_SYNC_UNCERTAINTY_S):
            raise ValueError("uncertainty_s must be finite, >= 0 and <= "
                             + repr(MAX_SYNC_UNCERTAINTY_S))
        if (first_label is None) != (second_label is None):
            raise ValueError("provide both stream labels or neither")
        if first_label is None:
            if len(self.streams) != 2:
                raise ValueError("explicit stream labels required unless exactly two "
                                 "streams are registered")
            first_label, second_label = list(self.streams)
        for label in (first_label, second_label):
            if label not in self.streams:
                raise ValueError("unknown stream: " + str(label))
        if first_label == second_label:
            raise ValueError("a sync mapping needs two distinct streams")
        record = {"evidence": evidence, "offset_s": offset,
                  "uncertainty_s": uncertainty, "note": note,
                  "first_label": first_label, "second_label": second_label,
                  "session_id": self.session_id, "time_epoch": self.time_epoch}
        self.sync["evidence_records"].append(record)
        self._refresh_sync()
        return dict(self.sync)

    def pair(self, first_label, second_label, tolerance_s, now=None):
        """Nearest corrected-stamp pairing within a tolerance, never blocking.

        A verified mapping ``stamp[second] = stamp[first] + offset_s`` is
        applied before comparing, so physically corresponding samples match
        even when raw stamps differ, and raw-close but physically offset
        samples are excluded. ``delta_s`` is the raw |second - first| stamp
        difference; ``residual_s`` is the corrected |second - first - offset|
        actually compared against ``tolerance_s``. Both raw stamps are kept.

        Online input is validated, not silently served from cache: the caller
        must pass ``now`` in the session clock domain (monotonic online,
        message time in replay); expired streams, invalid receive times,
        currently invalid frames and entries from an older epoch are refused
        with a reason, and the call never waits for data.
        """
        missing = [label for label in (first_label, second_label)
                   if label not in self.streams]
        if missing:
            raise KeyError("unknown stream: " + ", ".join(missing))
        first, second = self.streams[first_label], self.streams[second_label]
        suspected, ratios = self.unit_mismatch()
        if suspected:
            return {"status": "unit_mismatch_suspected", "pairs": [],
                    "reason": UNIT_MISMATCH_CODE, "ratios": ratios, "mapping": None}
        record = self._active_mapping(first_label, second_label)
        if record is None:
            reason = (SYNC_EPOCH_INVALIDATED_CODE
                      if self._pair_ever_verified(first_label, second_label)
                      else UNVERIFIED_PAIRING_CODE)
            return {"status": "unverified_domain", "pairs": [],
                    "reason": reason, "ratios": ratios, "mapping": None}
        mapping = self._mapping_report(record)
        tolerance = float(tolerance_s)
        if not math.isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("tolerance_s must be finite and >= 0")
        if finite_or_none(now) is None:
            return {"status": "invalid_now", "pairs": [],
                    "reason": PAIRING_TIME_INVALID_CODE, "ratios": ratios,
                    "mapping": mapping}
        for stream in (first, second):
            if stream.receive_status == "invalid":
                return {"status": "input_receive_invalid", "pairs": [],
                        "reason": stream.label + "_receive_time_invalid",
                        "ratios": ratios, "mapping": mapping}
            status, _ = stream.freshness(now)
            if status != "fresh":
                return {"status": "input_not_fresh", "pairs": [],
                        "reason": stream.label + "_" + status, "ratios": ratios,
                        "mapping": mapping}
            if stream.stamp_status == "invalid" or stream.source_stamp_s is None:
                return {"status": "current_frame_invalid", "pairs": [],
                        "reason": stream.label + "_stamp_invalid", "ratios": ratios,
                        "mapping": mapping}
        first_entries = [entry for entry in first.usable_entries(now)
                         if entry.get("time_epoch") == self.time_epoch]
        second_entries = [entry for entry in second.usable_entries(now)
                          if entry.get("time_epoch") == self.time_epoch]
        if not first_entries or not second_entries:
            return {"status": "insufficient_data", "pairs": [], "reason": None,
                    "ratios": ratios, "mapping": mapping}
        offset = float(record["offset_s"])

        def to_reference(label, value):
            return value - offset if label == record["second_label"] else value

        consumed = set()
        pairs = []
        for entry in first_entries:
            entry_reference = to_reference(first_label, entry["source_stamp_s"])
            best_index = None
            best_residual = None
            for index, candidate in enumerate(second_entries):
                if index in consumed:
                    continue
                residual = abs(entry_reference
                               - to_reference(second_label, candidate["source_stamp_s"]))
                if residual <= tolerance and (best_residual is None or residual < best_residual):
                    best_index, best_residual = index, residual
            if best_index is not None:
                consumed.add(best_index)
                matched = second_entries[best_index]
                pairs.append({"first": dict(entry), "second": dict(matched),
                              "delta_s": abs(matched["source_stamp_s"]
                                             - entry["source_stamp_s"]),
                              "residual_s": best_residual,
                              "offset_s": offset})
        return {"status": "paired" if pairs else "no_match", "pairs": pairs,
                "reason": None, "ratios": ratios, "mapping": mapping}

    def reason_codes(self, now):
        codes = []
        for label in sorted(self.streams):
            stream = self.streams[label]
            status, _ = stream.freshness(now)
            if status == "no_data":
                codes.append(label + "_no_data")
            elif status == "stale":
                codes.append(label + "_stale")
            if stream.receive_status == "invalid":
                codes.append(label + "_receive_time_invalid")
            if stream.stamp_reason:
                codes.append(stream.stamp_reason)
        suspected, _ = self.unit_mismatch()
        if suspected:
            codes.append(UNIT_MISMATCH_CODE)
        if not self.sync["cross_stream_same_clock_verified"]:
            codes.append(UNVERIFIED_SYNC_CODE)
            if self.sync["evidence_records"]:
                codes.append(SYNC_EPOCH_INVALIDATED_CODE)
        if not self.sync["host_anchor_verified"]:
            codes.append("host_anchor_unverified")
        return codes

    def snapshot(self, now):
        streams = {}
        for label in sorted(self.streams):
            stream = self.streams[label]
            status, age = stream.freshness(now)
            block = stream.current()
            block.update({"status": status, "age_s": finite_or_none(age)})
            streams[label] = block
        suspected, ratios = self.unit_mismatch()
        return {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "clock_domain": self.clock_domain,
            "time_epoch": self.time_epoch,
            "epoch_reason": self.epoch_reason,
            "source_time_domain": SOURCE_TIME_DOMAIN,
            "normalized_stamp_s": None,
            "sync": {"cross_stream_same_clock_verified":
                     self.sync["cross_stream_same_clock_verified"],
                     "host_anchor_verified": self.sync["host_anchor_verified"],
                     "physical_offset_s": finite_or_none(self.sync["physical_offset_s"]),
                     "offset_uncertainty_s":
                         finite_or_none(self.sync["offset_uncertainty_s"]),
                     "offset_evidence": self.sync["offset_evidence"],
                     "offset_first_label": self.sync["offset_first_label"],
                     "offset_second_label": self.sync["offset_second_label"],
                     "offset_time_epoch": self.sync["offset_time_epoch"],
                     "evidence_records": [dict(record)
                                          for record in self.sync["evidence_records"]]},
            "unit_ratios": ratios,
            "unit_mismatch_suspected": suspected,
            "streams": streams,
            "reason_codes": self.reason_codes(now),
        }
