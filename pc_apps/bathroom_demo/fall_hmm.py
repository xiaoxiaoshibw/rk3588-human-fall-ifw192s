"""Small, causal HMM for bathroom fall state (NumPy, Python 3.8).

Why an HMM here:
  - the radar measures noisy height / span / vertical velocity, not the state;
  - the useful state space is tiny (upright, sitting, descending, lying,
    recovering), so a few hundred parameters are enough;
  - hand-set priors can run without training, and a supervised fit only counts
    transitions/emissions (Laplace smoothing), not gradient descent.

It is deliberately not a point-cloud network. The input is the tracked target's
geometry, the same features the rule state machine uses. A fall candidate still
needs real bathroom data to validate false alarms and misses.

States: 0 upright, 1 sitting, 2 descending, 3 lying, 4 recovering.
Observations are factorised categorical bins:
  height p90: <0.5 / 0.5-0.9 / 0.9-1.3 / >=1.3 m
  span:       <0.5 / 0.5-1.0 / >=1.0 m
  vertical velocity: <-0.5 / -0.5..0.5 / >0.5 m/s
  inclination: <30 / 30-60 / >=60 deg / missing
"""
import json
import math
from collections import deque

import numpy as np

STATES = ("upright", "sitting", "descending", "lying", "recovering")
N_STATES = len(STATES)
H_BINS = 4
S_BINS = 3
V_BINS = 3
A_BINS = 4

# Rows sum to 1 after normalisation in __init__.
DEFAULT_TRANSITION = np.array([
    [0.940, 0.030, 0.020, 0.005, 0.005],  # upright
    [0.080, 0.900, 0.010, 0.005, 0.005],  # sitting
    [0.020, 0.080, 0.600, 0.280, 0.020],  # descending
    [0.005, 0.005, 0.020, 0.900, 0.070],  # lying
    [0.400, 0.050, 0.020, 0.030, 0.500],  # recovering
], dtype=np.float64)

DEFAULT_EMISSION = {
    "upright": dict(h=[0.00, 0.00, 0.15, 0.85], s=[0.00, 0.10, 0.90],
                    v=[0.02, 0.93, 0.05], a=[0.80, 0.15, 0.02, 0.03]),
    "sitting": dict(h=[0.00, 0.35, 0.55, 0.10], s=[0.05, 0.65, 0.30],
                    v=[0.02, 0.95, 0.03], a=[0.25, 0.55, 0.15, 0.05]),
    "descending": dict(h=[0.10, 0.35, 0.45, 0.10], s=[0.05, 0.45, 0.50],
                       v=[0.55, 0.40, 0.05], a=[0.15, 0.45, 0.35, 0.05]),
    "lying": dict(h=[0.75, 0.25, 0.00, 0.00], s=[0.80, 0.20, 0.00],
                  v=[0.02, 0.96, 0.02], a=[0.05, 0.30, 0.60, 0.05]),
    "recovering": dict(h=[0.05, 0.35, 0.45, 0.15], s=[0.05, 0.45, 0.50],
                       v=[0.05, 0.35, 0.60], a=[0.20, 0.50, 0.25, 0.05]),
}


def _normalise_rows(a):
    a = np.asarray(a, dtype=np.float64)
    s = a.sum(axis=-1, keepdims=True)
    if np.any(s <= 0):
        raise ValueError("probability rows must be positive")
    return a / s


def height_bin(value):
    if value is None or not math.isfinite(value):
        return 0
    if value < 0.5:
        return 0
    if value < 0.9:
        return 1
    if value < 1.3:
        return 2
    return 3


def span_bin(value):
    if value is None or not math.isfinite(value):
        return 0
    if value < 0.5:
        return 0
    if value < 1.0:
        return 1
    return 2


def velocity_bin(value):
    if value is None or not math.isfinite(value):
        return 1
    if value < -0.5:
        return 0
    if value > 0.5:
        return 2
    return 1


def angle_bin(value):
    if value is None or not math.isfinite(value):
        return 3
    if value < 30.0:
        return 0
    if value < 60.0:
        return 1
    return 2


class FallHMM(object):
    def __init__(self, transition=None, emission=None, initial=None,
                 min_event_points=100, min_visible_ratio=0.25,
                 fall_hold_s=0.30, long_lie_s=30.0, clear_upright_s=1.0):
        self.transition = _normalise_rows(DEFAULT_TRANSITION if transition is None else transition)
        if self.transition.shape != (N_STATES, N_STATES):
            raise ValueError("transition must be 5x5")
        source = DEFAULT_EMISSION if emission is None else emission
        self.emission = {}
        for state in STATES:
            row = source[state]
            self.emission[state] = dict(
                h=_normalise_rows(row["h"]), s=_normalise_rows(row["s"]),
                v=_normalise_rows(row["v"]), a=_normalise_rows(row["a"]),
            )
        self.initial = _normalise_rows(np.asarray(
            [0.90, 0.05, 0.03, 0.01, 0.01] if initial is None else initial))
        if self.initial.shape != (N_STATES,):
            raise ValueError("initial must have 5 entries")
        self.min_event_points = int(min_event_points)
        self.min_visible_ratio = float(min_visible_ratio)
        self.fall_hold_s = float(fall_hold_s)
        self.long_lie_s = float(long_lie_s)
        self.clear_upright_s = float(clear_upright_s)
        self.reset()

    def reset(self):
        self.alpha = self.initial.copy()
        self.count_history = deque()
        self.height_history = deque()
        self.last_stamp = None
        self.lying_since = None
        self.active = None
        self.upright_since = None
        self.seen_context = False
        self.last_state = "unknown"
        self.last_probs = {state: float(self.alpha[i]) for i, state in enumerate(STATES)}

    def observation(self, features, stamp):
        height = float(features["height_p90"])
        span = float(features["height_span"])
        velocity = 0.0
        if self.last_stamp is not None and stamp > self.last_stamp:
            velocity = (height - self.height_history[-1][1]) / (stamp - self.last_stamp)
        self.height_history.append((stamp, height))
        while self.height_history and stamp - self.height_history[0][0] > 2.0:
            self.height_history.popleft()
        angle = features.get("inclination_deg")
        return (height_bin(height), span_bin(span), velocity_bin(velocity),
                angle_bin(angle)), velocity

    def _emission_vector(self, obs):
        h, s, v, a = obs
        out = np.zeros(N_STATES, dtype=np.float64)
        for i, state in enumerate(STATES):
            row = self.emission[state]
            out[i] = row["h"][h] * row["s"][s] * row["v"][v] * row["a"][a]
        return np.maximum(out, 1e-12)

    def update(self, stamp, features):
        """One causal forward step. Returns a plain result dict."""
        self.last_stamp = stamp
        if features is None:
            self.alpha = self.alpha @ self.transition
            self.alpha /= self.alpha.sum()
            self.state = "unknown"
            self.last_probs = {s: float(self.alpha[i]) for i, s in enumerate(STATES)}
            return dict(state="unknown", probabilities=self.last_probs,
                        observed=False, velocity=None, fall_suspected=None,
                        long_lie_suspected=None)

        obs, velocity = self.observation(features, stamp)
        count = int(features["count"])
        self.count_history.append((stamp, count))
        while self.count_history and stamp - self.count_history[0][0] > 10.0:
            self.count_history.popleft()
        peak = max(c for _, c in self.count_history) if self.count_history else count
        ratio = count / float(max(1, peak))
        observed = count >= self.min_event_points and ratio >= self.min_visible_ratio

        # Predict, then correct only when the target is sufficiently visible.
        # A fragment or an occluded limb is not evidence for either fall or normal.
        self.alpha = self.alpha @ self.transition
        if observed:
            self.alpha = self.alpha * self._emission_vector(obs)
        self.alpha /= self.alpha.sum()
        probs = {s: float(self.alpha[i]) for i, s in enumerate(STATES)}
        state = STATES[int(np.argmax(self.alpha))] if observed else "unknown"
        if probs["upright"] >= 0.5 or probs["sitting"] >= 0.5:
            self.seen_context = True
        if state == "lying" and not self.seen_context:
            # A person already low at track birth (entering frame, partial
            # limb, camera starts with someone on the floor) is not a fall.
            state = "low_unconfirmed"
        self.last_probs = probs
        if state == "upright":
            self.upright_since = stamp if self.upright_since is None else self.upright_since
            if self.active is not None and stamp - self.upright_since >= self.clear_upright_s:
                self.active = None
                self.lying_since = None
        else:
            self.upright_since = None

        fall = None
        long_lie = None
        if observed and self.seen_context and probs["lying"] >= 0.5:
            if self.lying_since is None:
                self.lying_since = stamp
            held = stamp - self.lying_since
            if held + 1e-9 >= self.long_lie_s:
                self.active = "long_lie_suspected"
                long_lie = dict(source_stamp_s=stamp, probability=probs["lying"],
                                held_s=held)
            elif held + 1e-9 >= self.fall_hold_s and self.active is None:
                self.active = "fall_suspected"
                fall = dict(source_stamp_s=stamp, probability=probs["lying"],
                            held_s=held)
        elif not observed:
            # Do not extend a hold through an occlusion; keep the event but do
            # not create a new one until the target is visible again.
            self.lying_since = None
        else:
            self.lying_since = None

        if self.active is not None:
            state = self.active
        return dict(state=state, probabilities=probs, observed=observed,
                    velocity=velocity, fall_suspected=fall,
                    long_lie_suspected=long_lie)


def fit_hmm(sequences, alpha=1.0):
    """Supervised count fit: sequences = [(states, observations), ...].

    observations are (height_bin, span_bin, velocity_bin, angle_bin) tuples.
    With 18 events and 60 negatives this is intentionally trivial; it is a
    small-data baseline, not a replacement for independent validation.
    """
    trans = np.full((N_STATES, N_STATES), alpha, dtype=np.float64)
    emit = {s: dict(h=np.full(H_BINS, alpha), s=np.full(S_BINS, alpha),
                    v=np.full(V_BINS, alpha), a=np.full(A_BINS, alpha))
            for s in STATES}
    initial = np.full(N_STATES, alpha, dtype=np.float64)
    for states, obs in sequences:
        if not states:
            continue
        initial[states[0]] += 1.0
        for i, state in enumerate(states):
            if i + 1 < len(states):
                trans[state, states[i + 1]] += 1.0
            h, s, v, a = obs[i]
            emit[STATES[state]]["h"][h] += 1.0
            emit[STATES[state]]["s"][s] += 1.0
            emit[STATES[state]]["v"][v] += 1.0
            emit[STATES[state]]["a"][a] += 1.0
    return FallHMM(transition=trans, emission=emit, initial=initial)


def save_params(path, hmm):
    doc = dict(
        states=list(STATES),
        transition=hmm.transition.tolist(),
        initial=hmm.initial.tolist(),
        emission={s: {k: np.asarray(v).tolist() for k, v in hmm.emission[s].items()}
                  for s in STATES},
        note="hand-set or count-fit HMM; validate on independent bathroom data",
    )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)