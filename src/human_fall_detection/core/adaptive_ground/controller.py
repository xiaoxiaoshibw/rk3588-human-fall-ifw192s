"""AGL-D 六状态控制器（纯 core）。

INIT/ACQUIRING/STABLE/DEGRADED/HOLD/RECOVERING；validated cohort → median →
EMA → 限速 → 原子接受；last_good/age/manual freeze/恢复窗口；结构化事件。
时间显式输入（source stamp + 本地 tick）；不接触旧 GroundMonitor latch；
不输出展示 transform 的实际应用（GL-E）、不接 runtime。
"""
import copy
import math

from ..ground_evidence import digest, keys, number, require, text
from .contracts import validate_frame_key
from .temporal import (angle_between_deg, ema_step, limit_offset, limit_step,
                       resolve_temporal_config, sliding_median, temporal_config_id,
                       validate_candidate)

STATES = ("INIT", "ACQUIRING", "STABLE", "DEGRADED", "HOLD", "RECOVERING")
OBSERVATION_FIELDS = ("frame_key", "stamp_s", "epoch_key", "consensus_status",
                      "update_candidate", "confidence", "target")
DECISION_FIELDS = ("kind", "schema", "state", "consensus_status", "frame_key",
                   "controller_epoch", "accept_revision", "update_allowed", "applied",
                   "fresh", "last_good_age_s", "freeze_latched",
                   "eligible_for_geometry", "primary_reason", "reason_codes",
                   "last_good", "filter", "rebase_pending")
EVENT_FIELDS = ("event_seq", "input_kind", "frame_key", "frame_digest", "stamp_s",
                "time_domain", "state_before", "state_after", "action", "applied",
                "reason_codes", "accept_revision", "controller_epoch", "tick_index")

REASON_OK = "GL_OK"
REASON_HOLD = "GL_HOLD_LAST_GOOD"
REASON_ANGLE_JUMP = "GL_ANGLE_JUMP"
REASON_OFFSET_JUMP = "GL_OFFSET_JUMP"
REASON_RATE = "GL_RATE_LIMIT"
REASON_TIME_INVALID = "GL_TIME_INVALID"
REASON_GAP = "GL_FRAME_GAP"
REASON_DUPLICATE = "GL_DUPLICATE_FRAME"
REASON_EPOCH = "GL_CONFIG_CHANGED"
REASON_FREEZE = "GL_MANUAL_FREEZE"
REASON_RECOVERING = "GL_RECOVERING"
REASON_STALE = "GL_TRANSFORM_STALE"
REASON_NO_CONSENSUS = "GL_NO_CONSENSUS"
REASON_NORMAL = "GL_NORMAL_INVALID"
REASON_PENDING_REBASE = "GL_PENDING_REBASE"
REASON_ACQUIRING = "GL_ACQUIRING"


class LevelingController(object):
    """单线程事务：每个输入/tick/控制操作产生一个决策与对应事件。"""

    def __init__(self, config, controller_epoch=0):
        self.resolved = resolve_temporal_config(config)
        self.config_id = temporal_config_id(self.resolved)
        require(type(controller_epoch) is int and controller_epoch >= 0,
                "controller_epoch must be a nonnegative integer")
        self.controller_epoch = controller_epoch
        self.state = "INIT"
        self.pending = []
        self.pending_start_s = None
        self.rebase = []
        self.rebase_start_s = None
        self.rebase_target = None
        self.cohort = []
        self.ema = None
        self.last_good = None
        self.accept_revision = 0
        self.last_valid_time = None
        self.last_frame_digest = None
        self.freeze_latched = False
        self.epoch_key = None
        self.events = []
        self._seq = 0

    # ------------------------------------------------------------------ 基础
    def _event(self, action, *, input_kind, state_before, state_after, applied,
               reason_codes, frame_key=None, frame_digest=None, stamp_s=None,
               tick_index=None):
        self._seq += 1
        self.events.append({
            "event_seq": self._seq, "input_kind": input_kind,
            "frame_key": copy.deepcopy(frame_key), "frame_digest": frame_digest,
            "stamp_s": stamp_s,
            "time_domain": frame_key["time_domain"] if frame_key else None,
            "state_before": state_before, "state_after": state_after,
            "action": action, "applied": bool(applied),
            "reason_codes": list(reason_codes),
            "accept_revision": self.accept_revision,
            "controller_epoch": self.controller_epoch, "tick_index": tick_index})

    def _age(self, now_s):
        if self.last_good is None or now_s is None:
            return None
        return float(now_s) - float(self.last_good["stamp_s"])

    def _decision(self, now_s, *, consensus_status, frame_key, applied, update_allowed,
                  reasons, primary, filter_info=None, state=None):
        age = self._age(now_s)
        fresh = bool(age is not None and age <= self.resolved["max_hold_age_s"])
        return {"kind": "adaptive_leveling_decision", "schema": 1,
                "state": self.state if state is None else state,
                "consensus_status": consensus_status,
                "frame_key": copy.deepcopy(frame_key),
                "controller_epoch": self.controller_epoch,
                "accept_revision": self.accept_revision,
                "update_allowed": bool(update_allowed), "applied": bool(applied),
                "fresh": fresh, "last_good_age_s": age,
                "freeze_latched": self.freeze_latched,
                "eligible_for_geometry": bool(fresh),
                "primary_reason": primary, "reason_codes": list(reasons),
                "last_good": copy.deepcopy(self.last_good),
                "filter": copy.deepcopy(filter_info),
                "rebase_pending": len(self.rebase)}

    def _reset_all(self):
        self.state = "INIT"
        self.pending = []
        self.pending_start_s = None
        self.rebase = []
        self.rebase_start_s = None
        self.rebase_target = None
        self.cohort = []
        self.ema = None
        self.last_good = None
        self.last_frame_digest = None

    def _commit(self, proposal, offset_m, stamp_s, frame_digest):
        revision = self.accept_revision + 1
        transform_id = "agl-transform:" + digest({
            "config_id": self.config_id, "controller_epoch": self.controller_epoch,
            "revision": revision, "pitch_deg": proposal["pitch_deg"],
            "roll_deg": proposal["roll_deg"], "offset_m": offset_m,
            "frame_digest": frame_digest, "epoch_key": self.epoch_key})
        self.last_good = {"pitch_deg": float(proposal["pitch_deg"]),
                          "roll_deg": float(proposal["roll_deg"]),
                          "offset_m": float(offset_m), "stamp_s": float(stamp_s),
                          "frame_digest": frame_digest, "transform_id": transform_id,
                          "accept_revision": revision,
                          "controller_epoch": self.controller_epoch}
        self.accept_revision = revision

    def _filtered_update(self, candidate, stamp_s, alpha):
        window = (self.cohort + [candidate])[-self.resolved["window_size"]:]
        median = sliding_median(window)
        base = self.ema if self.ema is not None else self.last_good
        filtered = ema_step(base, median, alpha)
        dt_rate = stamp_s - self.last_good["stamp_s"]
        if not math.isfinite(dt_rate) or dt_rate <= 0.0:
            return None
        angle = limit_step(self.last_good, filtered, dt_rate, self.resolved)
        offset = limit_offset(self.last_good["offset_m"], filtered["offset_m"], dt_rate,
                              self.resolved)
        return {"window": window, "median": median, "filtered": filtered,
                "angle": angle, "offset": offset, "dt_s": dt_rate}

    def _apply_filtered(self, candidate, stamp_s, frame_digest, alpha):
        proposal = self._filtered_update(candidate, stamp_s, alpha)
        if proposal is None:
            return None
        self._commit(proposal["angle"]["proposal"], proposal["offset"]["value"],
                     stamp_s, frame_digest)
        self.ema = dict(proposal["filtered"])
        self.cohort = proposal["window"]
        info = {"median": proposal["median"], "filtered": proposal["filtered"],
                "allowed_angle_step_deg": proposal["angle"]["allowed_angle_step_deg"],
                "angle_limited": proposal["angle"]["limited"],
                "offset_limited": proposal["offset"]["limited"],
                "dt_s": proposal["dt_s"]}
        return info

    # ------------------------------------------------------------------ 主事务
    def process(self, observation):
        keys(observation, OBSERVATION_FIELDS, "observation")
        frame_key = copy.deepcopy(observation["frame_key"])
        validate_frame_key(frame_key)
        stamp = number(observation["stamp_s"], "stamp_s")
        require(stamp == float(frame_key["source_stamp"]), "stamp / frame key mismatch")
        text(observation["epoch_key"], "epoch_key")
        status = observation["consensus_status"]
        require(status in ("GOOD", "DEGRADED", "BAD"), "consensus status")
        require(type(observation["update_candidate"]) is bool,
                "update_candidate must be bool")
        confidence = number(observation["confidence"], "confidence")
        require(0.0 <= confidence <= 1.0, "confidence out of range")
        target = observation["target"]
        if target is None:
            require(status == "BAD", "GOOD/DEGRADED observation needs a target")
        else:
            require(status != "BAD", "BAD observation cannot carry a target")
            target = validate_candidate(target, "target")
            if abs(target["pitch_deg"]) > self.resolved["max_pitch_deg"] \
                    or abs(target["roll_deg"]) > self.resolved["max_roll_deg"]:
                target = None
                status = "BAD"
        state_before = self.state
        frame_digest = digest(frame_key)

        if self.epoch_key is None:
            self.epoch_key = observation["epoch_key"]
            self._event("EPOCH_ADOPTED", input_kind="frame", state_before=state_before,
                        state_after=self.state, applied=False,
                        reason_codes=[REASON_EPOCH], frame_key=frame_key,
                        frame_digest=frame_digest, stamp_s=stamp)
        elif observation["epoch_key"] != self.epoch_key:
            self.epoch_key = observation["epoch_key"]
            self.controller_epoch += 1
            self._reset_all()
            self._event("EPOCH_RESET", input_kind="frame", state_before=state_before,
                        state_after="INIT", applied=False, reason_codes=[REASON_EPOCH],
                        frame_key=frame_key, frame_digest=frame_digest, stamp_s=stamp)
            return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                                  applied=False, update_allowed=False,
                                  reasons=[REASON_EPOCH], primary=REASON_EPOCH)

        if self.freeze_latched:
            self.last_valid_time = stamp
            self._event("FROZEN_HELD", input_kind="frame", state_before=state_before,
                        state_after="HOLD", applied=False, reason_codes=[REASON_FREEZE],
                        frame_key=frame_key, frame_digest=frame_digest, stamp_s=stamp)
            return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                                  applied=False, update_allowed=False,
                                  reasons=[REASON_FREEZE], primary=REASON_FREEZE,
                                  state="HOLD")

        if frame_digest == self.last_frame_digest:
            self.pending = []
            self.pending_start_s = None
            self.rebase = []
            self.rebase_start_s = None
            self.rebase_target = None
            if self.state in ("STABLE", "DEGRADED", "RECOVERING"):
                self.state = "HOLD"
            self._event("DUPLICATE", input_kind="frame", state_before=state_before,
                        state_after=self.state, applied=False,
                        reason_codes=[REASON_DUPLICATE], frame_key=frame_key,
                        frame_digest=frame_digest, stamp_s=stamp)
            return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                                  applied=False, update_allowed=False,
                                  reasons=[REASON_DUPLICATE], primary=REASON_DUPLICATE)
        self.last_frame_digest = frame_digest

        reasons = []
        if target is None and status == "BAD" and REASON_NORMAL not in reasons \
                and abs(confidence) >= 0.0 and observation["target"] is not None:
            reasons.append(REASON_NORMAL)
        if self.last_valid_time is not None:
            dt = stamp - self.last_valid_time
            if dt <= 0.0:
                self.pending = []
                self.pending_start_s = None
                self.rebase = []
                self.rebase_start_s = None
                self.rebase_target = None
                if self.state in ("STABLE", "DEGRADED", "RECOVERING"):
                    self.state = "HOLD"
                self._event("TIME_INVALID", input_kind="frame",
                            state_before=state_before, state_after=self.state,
                            applied=False, reason_codes=[REASON_TIME_INVALID],
                            frame_key=frame_key, frame_digest=frame_digest, stamp_s=stamp)
                return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                                      applied=False, update_allowed=False,
                                      reasons=[REASON_TIME_INVALID],
                                      primary=REASON_TIME_INVALID)
            if dt > self.resolved["max_frame_gap_s"]:
                self.pending = []
                self.pending_start_s = None
                self.rebase = []
                self.rebase_start_s = None
                self.rebase_target = None
                if self.state in ("STABLE", "DEGRADED", "RECOVERING"):
                    self.state = "HOLD"
                self.last_valid_time = stamp
                self._event("FRAME_GAP", input_kind="frame",
                            state_before=state_before, state_after=self.state,
                            applied=False, reason_codes=[REASON_GAP],
                            frame_key=frame_key, frame_digest=frame_digest, stamp_s=stamp)
                return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                                      applied=False, update_allowed=False,
                                      reasons=[REASON_GAP], primary=REASON_GAP)
        self.last_valid_time = stamp

        applied = False
        update_allowed = False
        filter_info = None
        action = "HELD"

        if status == "GOOD":
            effective = dict(target)
            if self.resolved["offset_policy"] == "frozen_observed" \
                    and self.last_good is not None:
                effective["offset_m"] = self.last_good["offset_m"]
            if self.last_good is not None:
                raw_angle = angle_between_deg(self.last_good, effective)
                raw_offset = abs(effective["offset_m"] - self.last_good["offset_m"])
                if raw_angle >= self.resolved["raw_jump_reject_deg"]:
                    self.pending = []
                    self.pending_start_s = None
                    self.rebase = []
                    self.rebase_start_s = None
                    self.rebase_target = None
                    if self.state in ("STABLE", "DEGRADED", "RECOVERING"):
                        self.state = "HOLD"
                    self._event("ANGLE_JUMP", input_kind="frame",
                                state_before=state_before, state_after=self.state,
                                applied=False, reason_codes=[REASON_ANGLE_JUMP],
                                frame_key=frame_key, frame_digest=frame_digest,
                                stamp_s=stamp)
                    return self._decision(stamp, consensus_status=status,
                                          frame_key=frame_key, applied=False,
                                          update_allowed=False,
                                          reasons=[REASON_ANGLE_JUMP],
                                          primary=REASON_ANGLE_JUMP)
                if raw_offset >= self.resolved["raw_offset_jump_reject_m"]:
                    self.pending = []
                    self.pending_start_s = None
                    self.rebase = []
                    self.rebase_start_s = None
                    self.rebase_target = None
                    if self.state in ("STABLE", "DEGRADED", "RECOVERING"):
                        self.state = "HOLD"
                    self._event("OFFSET_JUMP", input_kind="frame",
                                state_before=state_before, state_after=self.state,
                                applied=False, reason_codes=[REASON_OFFSET_JUMP],
                                frame_key=frame_key, frame_digest=frame_digest,
                                stamp_s=stamp)
                    return self._decision(stamp, consensus_status=status,
                                          frame_key=frame_key, applied=False,
                                          update_allowed=False,
                                          reasons=[REASON_OFFSET_JUMP],
                                          primary=REASON_OFFSET_JUMP)
            if self.state == "INIT":
                self.state = "ACQUIRING"
                self.pending = [effective]
                self.pending_start_s = stamp
                action = "PENDING_ACQUIRE"
                reasons.append(REASON_ACQUIRING)
            elif self.state == "ACQUIRING":
                if self.pending and angle_between_deg(
                        self.pending[-1], effective) >= self.resolved["raw_jump_reject_deg"]:
                    self.pending = [effective]
                    self.pending_start_s = stamp
                else:
                    self.pending.append(effective)
                if self.pending_start_s is None:
                    self.pending_start_s = stamp
                duration = stamp - self.pending_start_s
                if len(self.pending) >= self.resolved["acquire_frames"] \
                        and duration >= self.resolved["min_cohort_duration_s"]:
                    median = sliding_median(
                        self.pending[-self.resolved["window_size"]:])
                    self._commit(median, median["offset_m"], stamp, frame_digest)
                    self.ema = dict(median)
                    self.cohort = list(self.pending[-self.resolved["window_size"]:])
                    self.pending = []
                    self.pending_start_s = None
                    self.state = "STABLE"
                    applied = True
                    update_allowed = True
                    action = "ACCEPTED"
                    reasons.append(REASON_OK)
                else:
                    action = "PENDING_ACQUIRE"
                    reasons.append(REASON_ACQUIRING)
            elif self.state == "STABLE":
                raw_angle = angle_between_deg(self.last_good, effective)
                if self.rebase_target is not None:
                    if angle_between_deg(self.rebase_target, effective) \
                            > self.resolved["pending_rebase_max_deg"]:
                        self.rebase_target = None
                        self.rebase = []
                        self.rebase_start_s = None
                        raw_angle = angle_between_deg(self.last_good, effective)
                    else:
                        info = self._apply_filtered(self.rebase_target, stamp,
                                                    frame_digest,
                                                    self.resolved["ema_alpha"])
                        if info is None:
                            return self._time_invalid_return(state_before, status,
                                                             frame_key, frame_digest,
                                                             stamp, reasons)
                        applied = True
                        update_allowed = True
                        filter_info = info
                        action = "ACCEPTED"
                        reasons.append(REASON_OK)
                        if info["angle_limited"] or info["offset_limited"]:
                            reasons.append(REASON_RATE)
                        if angle_between_deg(self.last_good, self.rebase_target) \
                                <= self.resolved["max_angle_step_deg"]:
                            self.rebase_target = None
                if not applied:
                    if raw_angle <= self.resolved["max_angle_step_deg"]:
                        self.rebase = []
                        self.rebase_start_s = None
                        info = self._apply_filtered(effective, stamp, frame_digest,
                                                    self.resolved["ema_alpha"])
                        if info is None:
                            return self._time_invalid_return(state_before, status,
                                                             frame_key, frame_digest,
                                                             stamp, reasons)
                        applied = True
                        update_allowed = True
                        filter_info = info
                        action = "ACCEPTED"
                        reasons.append(REASON_OK)
                        if info["angle_limited"] or info["offset_limited"]:
                            reasons.append(REASON_RATE)
                    else:
                        if self.rebase_start_s is None:
                            self.rebase_start_s = stamp
                        if self.rebase and angle_between_deg(
                                self.rebase[-1], effective) \
                                >= self.resolved["raw_jump_reject_deg"]:
                            self.rebase = [effective]
                            self.rebase_start_s = stamp
                        else:
                            self.rebase.append(effective)
                        duration = stamp - self.rebase_start_s
                        if len(self.rebase) >= self.resolved["recover_frames"] \
                                and duration >= self.resolved["min_cohort_duration_s"]:
                            self.rebase_target = sliding_median(
                                self.rebase[-self.resolved["window_size"]:])
                            self.rebase = []
                            self.rebase_start_s = None
                            info = self._apply_filtered(self.rebase_target, stamp,
                                                        frame_digest,
                                                        self.resolved["ema_alpha"])
                            if info is None:
                                return self._time_invalid_return(state_before, status,
                                                                 frame_key, frame_digest,
                                                                 stamp, reasons)
                            applied = True
                            update_allowed = True
                            filter_info = info
                            action = "ACCEPTED"
                            reasons.extend([REASON_OK, REASON_PENDING_REBASE])
                            if info["angle_limited"] or info["offset_limited"]:
                                reasons.append(REASON_RATE)
                        else:
                            action = "PENDING_REBASE"
                            reasons.append(REASON_PENDING_REBASE)
            elif self.state == "DEGRADED":
                self.state = "RECOVERING"
                self.pending = [effective]
                self.pending_start_s = stamp
                self.rebase = []
                self.rebase_start_s = None
                self.rebase_target = None
                action = "RECOVERING_START"
                reasons.append(REASON_RECOVERING)
            elif self.state == "HOLD":
                self.state = "RECOVERING"
                self.pending = [effective]
                self.pending_start_s = stamp
                action = "RECOVERING_START"
                reasons.append(REASON_RECOVERING)
            elif self.state == "RECOVERING":
                if self.pending and angle_between_deg(
                        self.pending[-1], effective) >= self.resolved["raw_jump_reject_deg"]:
                    self.pending = [effective]
                    self.pending_start_s = stamp
                else:
                    self.pending.append(effective)
                if self.pending_start_s is None:
                    self.pending_start_s = stamp
                duration = stamp - self.pending_start_s
                if len(self.pending) >= self.resolved["recover_frames"] \
                        and duration >= self.resolved["min_cohort_duration_s"]:
                    self.cohort = list(self.pending[-self.resolved["window_size"]:])
                    self.ema = None
                    info = self._apply_filtered(effective, stamp, frame_digest,
                                                self.resolved["ema_alpha"])
                    if info is None:
                        return self._time_invalid_return(state_before, status,
                                                         frame_key, frame_digest,
                                                         stamp, reasons)
                    self.pending = []
                    self.pending_start_s = None
                    self.state = "STABLE"
                    applied = True
                    update_allowed = True
                    filter_info = info
                    action = "ACCEPTED"
                    reasons.append(REASON_OK)
                    if info["angle_limited"] or info["offset_limited"]:
                        reasons.append(REASON_RATE)
                else:
                    action = "PENDING_RECOVER"
                    reasons.append(REASON_RECOVERING)
        elif status == "DEGRADED":
            if self.state in ("STABLE", "DEGRADED") \
                    and observation["update_candidate"] and self.last_good is not None:
                if self.state == "STABLE":
                    self.state = "DEGRADED"
                    self.cohort = []
                    self.rebase = []
                    self.rebase_start_s = None
                    self.rebase_target = None
                info = self._apply_filtered(target, stamp, frame_digest,
                                            self.resolved["degraded_ema_alpha"])
                if info is None:
                    return self._time_invalid_return(state_before, status, frame_key,
                                                     frame_digest, stamp, reasons)
                applied = True
                update_allowed = True
                filter_info = info
                action = "ACCEPTED_DEGRADED"
                reasons.append(REASON_OK)
                if info["angle_limited"] or info["offset_limited"]:
                    reasons.append(REASON_RATE)
            else:
                if self.state == "STABLE":
                    self.state = "DEGRADED"
                elif self.state == "RECOVERING":
                    self.state = "HOLD"
                    self.pending = []
                    self.pending_start_s = None
                elif self.state == "ACQUIRING":
                    self.pending = []
                    self.pending_start_s = None
                self.rebase = []
                self.rebase_start_s = None
                self.rebase_target = None
                action = "DEGRADED_KEEP"
        else:
            self.pending = []
            self.pending_start_s = None
            self.rebase = []
            self.rebase_start_s = None
            self.rebase_target = None
            if self.state in ("STABLE", "DEGRADED", "RECOVERING"):
                self.state = "HOLD"
            action = "HELD"
            reasons.append(REASON_NO_CONSENSUS)

        primary = next((code for code in reasons if code not in
                        (REASON_OK, REASON_ACQUIRING, REASON_RECOVERING,
                         REASON_PENDING_REBASE)), None)
        self._event(action, input_kind="frame", state_before=state_before,
                    state_after=self.state, applied=applied, reason_codes=reasons,
                    frame_key=frame_key, frame_digest=frame_digest, stamp_s=stamp)
        return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                              applied=applied, update_allowed=update_allowed,
                              reasons=reasons, primary=primary, filter_info=filter_info)

    def _time_invalid_return(self, state_before, status, frame_key, frame_digest,
                             stamp, reasons):
        self._event("TIME_INVALID", input_kind="frame", state_before=state_before,
                    state_after=self.state, applied=False,
                    reason_codes=[REASON_TIME_INVALID], frame_key=frame_key,
                    frame_digest=frame_digest, stamp_s=stamp)
        return self._decision(stamp, consensus_status=status, frame_key=frame_key,
                              applied=False, update_allowed=False,
                              reasons=[REASON_TIME_INVALID],
                              primary=REASON_TIME_INVALID)

    # ------------------------------------------------------------------ tick/控制
    def on_tick(self, now_s):
        now = number(now_s, "now_s")
        reasons = []
        age = self._age(now)
        if age is not None and age > self.resolved["max_hold_age_s"]:
            reasons.append(REASON_STALE)
        self._event("TICK", input_kind="tick", state_before=self.state,
                    state_after=self.state, applied=False, reason_codes=reasons,
                    tick_index=self._seq + 1)
        return self._decision(now, consensus_status=None, frame_key=None, applied=False,
                              update_allowed=False, reasons=reasons,
                              primary=(REASON_STALE if reasons else None))

    def freeze(self, reason_text, now_s=None):
        text(reason_text, "freeze reason")
        if not self.freeze_latched:
            self.freeze_latched = True
            self._event("FROZEN", input_kind="control", state_before=self.state,
                        state_after="HOLD", applied=False, reason_codes=[reason_text])
        now = now_s if now_s is not None else self.last_valid_time
        return self._decision(now, consensus_status=None, frame_key=None, applied=False,
                              update_allowed=False, reasons=[reason_text],
                              primary=reason_text, state="HOLD")

    def unfreeze(self, now_s=None):
        if self.freeze_latched:
            self.freeze_latched = False
            self.rebase = []
            self.rebase_start_s = None
            self.rebase_target = None
            self.pending = []
            self.pending_start_s = None
            if self.last_good is not None:
                self.state = "RECOVERING"
            else:
                self.state = "INIT"
            self._event("UNFROZEN", input_kind="control", state_before="HOLD",
                        state_after=self.state, applied=False,
                        reason_codes=[REASON_RECOVERING])
        now = now_s if now_s is not None else self.last_valid_time
        return self._decision(now, consensus_status=None, frame_key=None, applied=False,
                              update_allowed=False, reasons=[], primary=None)


def validate_controller_decision(decision):
    keys(decision, DECISION_FIELDS, "decision")
    require(decision["kind"] == "adaptive_leveling_decision"
            and type(decision["schema"]) is int and decision["schema"] == 1,
            "decision kind/schema")
    require(decision["state"] in STATES, "decision state")
    require(type(decision["update_allowed"]) is bool and type(decision["applied"]) is bool
            and type(decision["fresh"]) is bool and type(decision["freeze_latched"]) is bool
            and type(decision["eligible_for_geometry"]) is bool, "decision flags")
    require(type(decision["controller_epoch"]) is int
            and type(decision["accept_revision"]) is int, "decision revisions")
    require(decision["last_good_age_s"] is None
            or number(decision["last_good_age_s"], "age") >= 0.0, "decision age")
    require(isinstance(decision["reason_codes"], list)
            and all(isinstance(item, str) and item for item in decision["reason_codes"]),
            "decision reasons")
    return None
