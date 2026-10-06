"""GL-D（AGL-D-01..06）：六状态、时间序列、限速、恢复、事件与 freeze 不变量。"""
import copy
import json
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.adaptive_ground.controller import (EVENT_FIELDS, LevelingController,
                                             validate_controller_decision)
from core.adaptive_ground.temporal import (angle_between_deg, limit_step,
                                           resolve_temporal_config)

CONFIG = {"window_size": 5, "ema_alpha": 0.15, "degraded_ema_alpha": 0.05,
          "acquire_frames": 10, "recover_frames": 10, "min_cohort_duration_s": 0.8,
          "max_pitch_deg": 60.0, "max_roll_deg": 30.0,
          "max_delta_pitch_per_frame": 0.25, "max_delta_roll_per_frame": 0.25,
          "max_angle_step_deg": 0.25, "max_delta_angle_per_second": 1.0,
          "max_angle_rate_deg_s": 1.0, "raw_jump_reject_deg": 5.0,
          "pending_rebase_max_deg": 2.0, "offset_policy": "gated_observed",
          "max_offset_step_m": 0.01, "max_offset_rate_m_s": 0.02,
          "raw_offset_jump_reject_m": 0.05, "max_frame_gap_s": 0.30,
          "max_hold_age_s": 2.0}


def temporal_config(**overrides):
    config = dict(CONFIG)
    config.update(overrides)
    return config


def observation(ordinal, stamp, status="GOOD", target=None, update=True,
                confidence=0.9, epoch="epoch-a", session="s1"):
    frame = {"stream_instance_id": "stream:d", "session_id": session,
             "reference_epoch": 0, "ordinal": ordinal, "seq": ordinal,
             "source_frame": "innolidar", "source_stamp": float(stamp),
             "time_domain": "device_seconds"}
    return {"frame_key": frame, "stamp_s": float(stamp), "epoch_key": epoch,
            "consensus_status": status, "update_candidate": update,
            "confidence": confidence, "target": target}


def target(pitch, roll=0.0, offset=1.32):
    return {"pitch_deg": pitch, "roll_deg": roll, "offset_m": offset}


def feed(controller, count, start_ordinal, start_stamp, dt=0.1, pitch=26.0,
         roll=0.0, offset=1.32, **kwargs):
    decisions = []
    for index in range(count):
        decisions.append(controller.process(observation(
            start_ordinal + index, start_stamp + index * dt,
            target=target(pitch, roll, offset), **kwargs)))
    return decisions


class AglDControllerTest(unittest.TestCase):
    def test_init_acquisition_and_first_stable_AGL_D_01(self):
        controller = LevelingController(temporal_config())
        decisions = feed(controller, 9, 0, 0.0)
        for decision in decisions:
            self.assertFalse(decision["applied"])
            self.assertIsNone(decision["last_good"])
            self.assertIsNone(decision["last_good_age_s"])
        self.assertEqual(controller.state, "ACQUIRING")
        final = controller.process(observation(9, 0.9, target=target(26.0)))
        self.assertTrue(final["applied"])
        self.assertEqual(final["state"], "STABLE")
        self.assertAlmostEqual(controller.last_good["pitch_deg"], 26.0, places=9)
        self.assertEqual(controller.accept_revision, 1)
        interrupted = LevelingController(temporal_config())
        feed(interrupted, 4, 0, 0.0)
        interrupted.process(observation(4, 0.4, status="BAD", target=None))
        self.assertEqual(len(interrupted.pending), 0)
        feed(interrupted, 9, 5, 0.5)
        self.assertIsNone(interrupted.last_good)
        final = interrupted.process(observation(14, 1.4, target=target(26.0)))
        self.assertTrue(final["applied"])
        short = LevelingController(temporal_config())
        feed(short, 10, 0, 0.0, dt=0.05)
        self.assertIsNone(short.last_good)
        feed(short, 7, 10, 0.5, dt=0.05)
        self.assertIsNotNone(short.last_good)
        self.assertEqual(short.state, "STABLE")

    def test_filter_rate_limits_and_bad_no_pollution_AGL_D_02(self):
        controller = LevelingController(temporal_config())
        feed(controller, 10, 0, 0.0)
        baseline = copy.deepcopy(controller.last_good)
        controller.process(observation(10, 1.0, status="BAD", target=None))
        self.assertEqual(controller.last_good, baseline)
        tracking = LevelingController(temporal_config())
        feed(tracking, 10, 0, 0.0)
        previous = tracking.last_good["pitch_deg"]
        steps = []
        for index in range(1, 31):
            tracking.process(observation(10 + index, 1.0 + index * 0.1,
                                         target=target(26.18)))
            step = abs(tracking.last_good["pitch_deg"] - previous)
            steps.append(step)
            previous = tracking.last_good["pitch_deg"]
        self.assertLessEqual(max(steps), 0.1 + 1e-9)
        self.assertLess(abs(tracking.last_good["pitch_deg"] - 26.18), 0.01)
        resolved = resolve_temporal_config(temporal_config())
        small = limit_step({"pitch_deg": 26.0, "roll_deg": 0.0},
                           {"pitch_deg": 26.5, "roll_deg": 0.0}, 0.05, resolved)
        moved_small = angle_between_deg({"pitch_deg": 26.0, "roll_deg": 0.0},
                                        small["proposal"])
        self.assertLessEqual(moved_small, 0.05 + 1e-9)
        self.assertTrue(small["limited"])
        large = limit_step({"pitch_deg": 26.0, "roll_deg": 0.0},
                           {"pitch_deg": 26.5, "roll_deg": 0.0}, 0.3, resolved)
        moved_large = angle_between_deg({"pitch_deg": 26.0, "roll_deg": 0.0},
                                        large["proposal"])
        self.assertLessEqual(moved_large, 0.25 + 1e-9)
        offsets = LevelingController(temporal_config())
        feed(offsets, 10, 0, 0.0)
        before_offset = offsets.last_good["offset_m"]
        offset_steps = []
        for index in range(1, 16):
            offsets.process(observation(10 + index, 1.0 + index * 0.1,
                                        target=target(26.0, 0.0, 1.34)))
            offset_steps.append(abs(offsets.last_good["offset_m"] - before_offset))
            before_offset = offsets.last_good["offset_m"]
        self.assertLessEqual(max(offset_steps), 0.002 + 1e-9)
        self.assertGreater(offsets.last_good["offset_m"] - 1.32, 1e-6)

    def test_hold_invariants_jump_reject_and_age_AGL_D_03(self):
        controller = LevelingController(temporal_config())
        feed(controller, 10, 0, 0.0)
        snapshot = copy.deepcopy(controller.last_good)
        revision = controller.accept_revision
        decision = controller.process(observation(10, 1.0, status="BAD", target=None))
        self.assertEqual(decision["state"], "HOLD")
        self.assertEqual(controller.last_good, snapshot)
        self.assertEqual(controller.accept_revision, revision)
        decision = controller.process(observation(11, 1.1, target=target(34.0)))
        self.assertEqual(decision["primary_reason"], "GL_ANGLE_JUMP")
        self.assertEqual(decision["state"], "HOLD")
        self.assertEqual(controller.last_good, snapshot)
        self.assertEqual(controller.accept_revision, revision)
        offset_case = LevelingController(temporal_config())
        feed(offset_case, 10, 0, 0.0)
        decision = offset_case.process(observation(10, 1.0, target=target(26.0, 0.0, 1.52)))
        self.assertEqual(decision["primary_reason"], "GL_OFFSET_JUMP")
        self.assertEqual(offset_case.last_good, snapshot)
        blank = LevelingController(temporal_config())
        decision = blank.process(observation(0, 0.0, status="BAD", target=None))
        self.assertIsNone(blank.last_good)
        self.assertEqual(blank.state, "INIT")
        self.assertFalse(decision["applied"])
        tick = controller.on_tick(3.4)
        self.assertFalse(tick["fresh"])
        self.assertFalse(tick["eligible_for_geometry"])
        self.assertEqual(tick["primary_reason"], "GL_TRANSFORM_STALE")
        self.assertEqual(controller.last_good, snapshot)
        tick = controller.on_tick(1.5)
        self.assertTrue(tick["fresh"])
        self.assertTrue(tick["eligible_for_geometry"])

    def test_recovery_rebase_and_no_ema_swallow_AGL_D_04(self):
        controller = LevelingController(temporal_config())
        feed(controller, 10, 0, 0.0)
        controller.process(observation(10, 1.0, status="BAD", target=None))
        decision = controller.process(observation(11, 1.1, target=target(26.0)))
        self.assertEqual(decision["state"], "RECOVERING")
        self.assertFalse(decision["applied"])
        for index in range(12, 20):
            decision = controller.process(observation(index, index * 0.1,
                                                      target=target(26.0)))
            self.assertFalse(decision["applied"], index)
        decision = controller.process(observation(20, 2.0, target=target(26.0)))
        self.assertTrue(decision["applied"])
        self.assertEqual(controller.state, "STABLE")
        self.assertEqual(controller.accept_revision, 2)
        controller.process(observation(21, 2.1, status="BAD", target=None))
        self.assertEqual(controller.state, "HOLD")
        controller.process(observation(22, 2.2, target=target(26.0)))
        gap = controller.process(observation(23, 2.9, target=target(26.0)))
        self.assertEqual(gap["primary_reason"], "GL_FRAME_GAP")
        self.assertEqual(controller.state, "HOLD")
        controller.process(observation(24, 3.0, target=target(26.0)))
        duplicate = controller.process(observation(24, 3.0, target=target(26.0)))
        self.assertEqual(duplicate["primary_reason"], "GL_DUPLICATE_FRAME")
        self.assertEqual(controller.state, "HOLD")
        rebase = LevelingController(temporal_config())
        feed(rebase, 10, 0, 0.0)
        new_pose = 27.5
        decision = rebase.process(observation(10, 1.0, target=target(new_pose)))
        self.assertFalse(decision["applied"])
        self.assertIn("GL_PENDING_REBASE", decision["reason_codes"])
        values = [rebase.last_good["pitch_deg"]]
        for index in range(11, 21):
            decision = rebase.process(observation(index, index * 0.1,
                                                  target=target(new_pose)))
            values.append(rebase.last_good["pitch_deg"])
        self.assertTrue(decision["applied"])
        for index in range(21, 61):
            rebase.process(observation(index, index * 0.1, target=target(new_pose)))
            values.append(rebase.last_good["pitch_deg"])
        self.assertEqual(rebase.state, "STABLE")
        self.assertLess(abs(rebase.last_good["pitch_deg"] - new_pose), 0.02)
        self.assertLessEqual(float(np.max(np.abs(np.diff(values)))), 0.1 + 1e-9)
        swallow = LevelingController(temporal_config())
        feed(swallow, 10, 0, 0.0)
        before = copy.deepcopy(swallow.last_good)
        decision = swallow.process(observation(10, 1.0, target=target(32.0)))
        self.assertEqual(decision["primary_reason"], "GL_ANGLE_JUMP")
        self.assertEqual(swallow.state, "HOLD")
        self.assertEqual(swallow.last_good, before)

    def test_epoch_freeze_unfreeze_lifecycle_AGL_D_05(self):
        controller = LevelingController(temporal_config())
        feed(controller, 10, 0, 0.0)
        revision = controller.accept_revision
        decision = controller.process(observation(10, 1.0, target=target(26.0),
                                                  epoch="epoch-b"))
        self.assertEqual(controller.state, "INIT")
        self.assertIsNone(controller.last_good)
        self.assertEqual(decision["primary_reason"], "GL_CONFIG_CHANGED")
        self.assertEqual(controller.controller_epoch, 1)
        self.assertEqual(controller.accept_revision, revision)
        feed(controller, 10, 11, 1.1, epoch="epoch-b")
        self.assertEqual(controller.state, "STABLE")
        frozen_value = copy.deepcopy(controller.last_good)
        decision = controller.freeze("manual maintenance", now_s=2.1)
        self.assertTrue(decision["freeze_latched"])
        self.assertEqual(decision["state"], "HOLD")
        decision = controller.process(observation(21, 2.2, target=target(26.5),
                                                  epoch="epoch-b"))
        self.assertEqual(decision["primary_reason"], "GL_MANUAL_FREEZE")
        self.assertEqual(controller.last_good, frozen_value)
        decision = controller.unfreeze(now_s=2.3)
        self.assertEqual(decision["state"], "RECOVERING")
        decision = controller.process(observation(22, 2.4, target=target(26.0),
                                                  epoch="epoch-b"))
        self.assertFalse(decision["applied"])
        for index in range(23, 33):
            decision = controller.process(observation(index, 2.4 + (index - 22) * 0.1,
                                                      target=target(26.0),
                                                      epoch="epoch-b"))
        self.assertTrue(decision["applied"])
        self.assertEqual(controller.state, "STABLE")
        blank = LevelingController(temporal_config())
        blank.freeze("pre", now_s=0.0)
        blank.unfreeze(now_s=0.1)
        self.assertEqual(blank.state, "INIT")

    def test_config_refusals_AGL_D_S01(self):
        for override in ({"window_size": 4}, {"window_size": 1},
                         {"ema_alpha": 0.0}, {"ema_alpha": 1.5},
                         {"max_angle_rate_deg_s": 2.0},
                         {"acquire_frames": 3}, {"recover_frames": 4},
                         {"min_cohort_duration_s": 0.0},
                         {"offset_policy": "raw"},
                         {"pending_rebase_max_deg": 6.0},
                         {"max_offset_step_m": 0.2},
                         {"degraded_ema_alpha": True},
                         {"unknown": 1}):
            with self.assertRaises(ValueError, msg=str(override)):
                resolve_temporal_config(temporal_config(**override))

    def test_events_json_and_determinism_AGL_D_06(self):
        def run_timeline():
            controller = LevelingController(temporal_config())
            decisions = feed(controller, 10, 0, 0.0)
            decisions.append(controller.process(observation(10, 1.0, status="BAD",
                                                            target=None)))
            decisions.append(controller.process(observation(11, 1.1,
                                                            target=target(26.0))))
            decisions.append(controller.process(observation(11, 1.1,
                                                            target=target(26.0))))
            decisions.append(controller.on_tick(4.0))
            decisions.append(controller.freeze("maint", now_s=4.1))
            decisions.append(controller.unfreeze(now_s=4.2))
            controller.process(observation(12, 4.3, target=target(26.0)))
            return controller, decisions

        controller, decisions = run_timeline()
        for decision in decisions:
            validate_controller_decision(decision)
            json.dumps(decision, allow_nan=False)
        for event in controller.events:
            self.assertEqual(set(event), set(EVENT_FIELDS))
            self.assertEqual(event["input_kind"], "tick" if event["tick_index"]
                             is not None else event["input_kind"])
            if event["input_kind"] == "tick":
                self.assertIsNone(event["frame_key"])
                self.assertIsNone(event["frame_digest"])
                self.assertIsNone(event["stamp_s"])
                self.assertIsInstance(event["tick_index"], int)
            else:
                self.assertIsNotNone(event["action"])
                self.assertIsInstance(event["accept_revision"], int)
                self.assertIsInstance(event["controller_epoch"], int)
            if event["input_kind"] == "frame" and event["frame_key"] is not None:
                self.assertEqual(event["time_domain"], "device_seconds")
        json.dumps(controller.events, allow_nan=False)
        twin, twin_decisions = run_timeline()
        self.assertEqual(twin.events, controller.events)
        self.assertEqual(twin_decisions, decisions)


if __name__ == '__main__':
    unittest.main()
