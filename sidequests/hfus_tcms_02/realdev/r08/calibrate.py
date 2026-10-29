"""Persistent per-edge calibration for reused r04 region edges.

This module only measures region-to-region lengths supplied by the caller. It
does not extract nodes, infer anatomy, or turn display values into evidence.
"""
import math


DEFAULT_CONFIG = {
    "window_max_samples": 20,
    "min_samples_collecting_to_calibrating": 5,
    "min_samples_calibrated": 15,
    "relative_std_max": 0.05,
    "absolute_std_max_m": 0.02,
    "drift_ratio_band": [0.6, 1.7],
    "drift_min_samples": 3,
}


class EdgeCalibrator:
    def __init__(self, edge, config):
        self.edge = tuple(edge)
        self.config = dict(config)
        self.values = []
        self.state = "COLLECTING"
        self.ever_calibrated = False
        self.first_calibrated_fi = None
        self.post_calibration_values = []
        self.episodes = []
        self.open_episode = None
        self.last_fi = None
        self.last_measurement = None

    def _stats(self):
        n = len(self.values)
        if not n:
            return dict(n=0, mean=None, std=None, relative_std=None)
        mean = sum(self.values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in self.values) / n)
        return dict(n=n, mean=mean, std=std,
                    relative_std=(std / mean) if mean > 0 else None)

    def _episode_summary(self, values, start_fi, end_fi):
        n = len(values)
        if not n:
            return None
        mean = sum(values) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / n)
        windows = [values[i:i + 15] for i in range(0, n, 15) if len(values[i:i + 15]) == 15]
        means = [sum(w) / len(w) for w in windows]
        if len(means) >= 2:
            mm = sum(means) / len(means)
            cross = math.sqrt(sum((x - mm) ** 2 for x in means) / len(means))
        else:
            cross = None
        return dict(edge=list(self.edge), start_frame=start_fi, end_frame=end_fi,
                    n=n, mean=mean, raw_std_m=std,
                    raw_relative_std=(std / mean) if mean > 0 else None,
                    window_size=15, window_means=means,
                    cross_window_std_m=cross)

    def _finish_episode(self, fi):
        if self.open_episode is None:
            return None
        episode = self._episode_summary(self.open_episode["values"],
                                        self.open_episode["start_frame"], fi)
        if episode is not None:
            self.episodes.append(episode)
        self.open_episode = None
        return episode

    def _transition(self, new_state, fi, reason):
        old = self.state
        if old != new_state:
            if old == "CALIBRATED" and self.open_episode is not None:
                self._finish_episode(fi - 1 if fi > self.open_episode["start_frame"] else fi)
            self.state = new_state
            if new_state == "CALIBRATED":
                self.open_episode = dict(start_frame=fi, values=list(self.values))
            return dict(fi=fi, edge=list(self.edge), old=old, new=new_state,
                        reason=reason, measurement=self.last_measurement,
                        mean=self._stats()["mean"], std=self._stats()["std"],
                        n=len(self.values))
        return None

    def update(self, fi, measurement):
        """Consume at most one measurement and return an auditable snapshot."""
        self.last_fi = fi
        self.last_measurement = measurement
        event = None
        drift = None
        if measurement is not None:
            value = float(measurement)
            if not math.isfinite(value) or value <= 0:
                raise ValueError("edge measurement must be positive and finite")
            stats_before = self._stats()
            if (stats_before["n"] >= self.config["drift_min_samples"]
                    and stats_before["mean"] is not None):
                ratio = value / stats_before["mean"]
                low, high = self.config["drift_ratio_band"]
                if ratio < low or ratio > high:
                    drift = dict(fi=fi, edge=list(self.edge), old_state=self.state,
                                 measurement=value, mean_before=stats_before["mean"],
                                 ratio=ratio, band=[low, high],
                                 reason="SINGLE_FRAME_RATIO_OUTSIDE_BAND")
                    self.values = []
                    event = self._transition("DRIFT_RESET", fi,
                                             "SINGLE_FRAME_RATIO_OUTSIDE_BAND")
                    snapshot = self.snapshot(fi)
                    snapshot["accepted"] = False
                    snapshot["drift"] = drift
                    return snapshot, event, drift
            self.values.append(value)
            if len(self.values) > self.config["window_max_samples"]:
                self.values.pop(0)
            stats = self._stats()
            if self.ever_calibrated:
                self.post_calibration_values.append(value)
            if self.open_episode is not None and self.state == "CALIBRATED":
                self.open_episode["values"].append(value)
            n = stats["n"]
            if n < self.config["min_samples_collecting_to_calibrating"]:
                new_state, reason = "COLLECTING", "INSUFFICIENT_SAMPLES"
            elif n < self.config["min_samples_calibrated"]:
                new_state, reason = "CALIBRATING", "ACCUMULATING_SAMPLES"
            elif (stats["relative_std"] <= self.config["relative_std_max"]
                  and stats["std"] <= self.config["absolute_std_max_m"]):
                new_state, reason = "CALIBRATED", "REL_STD_AND_ABS_STD_WITHIN_LIMIT"
            else:
                new_state, reason = "CALIBRATING", "REL_STD_OR_ABS_STD_ABOVE_LIMIT"
            event = self._transition(new_state, fi, reason)
            if new_state == "CALIBRATED" and not self.ever_calibrated:
                self.ever_calibrated = True
                self.first_calibrated_fi = fi
        snapshot = self.snapshot(fi)
        snapshot["accepted"] = measurement is not None and drift is None
        snapshot["drift"] = drift
        return snapshot, event, drift

    def snapshot(self, fi=None):
        stats = self._stats()
        episodes = list(self.episodes)
        if self.open_episode is not None:
            current = self._episode_summary(self.open_episode["values"],
                                            self.open_episode["start_frame"],
                                            fi if fi is not None else self.last_fi)
            if current is not None:
                episodes.append(current)
        stable = [e for e in episodes if e["raw_std_m"] <= 0.02]
        return dict(edge=list(self.edge), frame=fi, state=self.state,
                    mean=stats["mean"], std=stats["std"],
                    sigma=stats["std"], relative_std=stats["relative_std"],
                    n=stats["n"], measurement=self.last_measurement,
                    ever_calibrated=self.ever_calibrated,
                    first_calibrated_frame=self.first_calibrated_fi,
                    calibration_episodes=episodes,
                    stable_calibration_episodes=stable,
                    best_calibration_episode=(
                        min(stable, key=lambda e: e["raw_std_m"]) if stable else None))


class CalibrationLayer:
    def __init__(self, edges, config=None):
        cfg = dict(DEFAULT_CONFIG)
        if config:
            unknown = set(config) - set(cfg)
            if unknown:
                raise ValueError("unknown calibration config: " + repr(sorted(unknown)))
            cfg.update(config)
        self.config = cfg
        self.edges = [tuple(e) for e in edges]
        self.calibrators = {e: EdgeCalibrator(e, cfg) for e in self.edges}
        self.events = []
        self.drifts = []
        self.frames = []

    def update(self, fi, measurements):
        snapshots = {}
        for edge in self.edges:
            snap, event, drift = self.calibrators[edge].update(
                fi, measurements.get(edge))
            snapshots[edge] = snap
            if event:
                self.events.append(event)
            if drift:
                self.drifts.append(drift)
        frame = dict(frame=fi, edges={
            "%s|%s" % edge: snapshots[edge] for edge in self.edges})
        self.frames.append(frame)
        return frame

    def summary(self):
        out = {}
        for edge in self.edges:
            cal = self.calibrators[edge]
            snap = cal.snapshot()
            values = cal.post_calibration_values
            if values:
                mean = sum(values) / len(values)
                std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
            else:
                mean = None
                std = None
            snap.update(post_calibration_std=std,
                        post_calibration_n=len(values),
                        post_calibration_mean=mean)
            out["%s|%s" % edge] = snap
        return dict(config=self.config, edges=out,
                    state_events=list(self.events), drift_events=list(self.drifts),
                    ever_calibrated_edges=sum(v["ever_calibrated"]
                                              for v in out.values()),
                    all_edges_have_history=all(v["n"] > 0 for v in out.values()))


if __name__ == "__main__":
    layer = CalibrationLayer([("A", "B")])
    first = None
    for i in range(20):
        frame = layer.update(i, {("A", "B"): 0.5})
        if frame["edges"]["A|B"]["state"] == "CALIBRATED" and first is None:
            first = i
    frame = layer.update(20, {("A", "B"): 1.2})
    assert frame["edges"]["A|B"]["state"] == "DRIFT_RESET"
    assert layer.summary()["drift_events"]
    assert first == 14
    edge_summary = layer.summary()["edges"]["A|B"]
    assert edge_summary["calibration_episodes"]
    assert edge_summary["best_calibration_episode"]["raw_std_m"] == 0.0
    print("calibrate self-check PASS")
