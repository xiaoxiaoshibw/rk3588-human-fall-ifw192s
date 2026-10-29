"""Causal research filters. Rule-initialized states are hypotheses, never GT.

Portable Python 3.8 + NumPy; no ROS, scipy, sklearn or network access.
"""
import copy
import math
import numpy as np

POSTURES = ['STANDING', 'SITTING', 'CROUCHING', 'LYING', 'TRANSITION', 'UNKNOWN']
EVENTS = ['NORMAL', 'POSSIBLE_FALL', 'POST_FALL', 'RECOVERY', 'UNKNOWN']


def normalize(x):
    x = np.asarray(x, dtype=float)
    total = x.sum()
    if not np.isfinite(x).all() or np.any(x < 0) or total <= 0:
        raise ValueError('Finite nonnegative probability mass required')
    return x / total


def transition(a, dt, step=.1):
    """Reference-step matrix, integer powers + fractional interpolation.

    ponytail: piecewise discrete interpolation, not a fitted continuous generator.
    """
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError('Positive finite elapsed seconds required')
    n = int(dt / step)
    f = dt / step - n
    return np.linalg.matrix_power(a, n) @ ((1-f)*np.eye(len(a)) + f*a)


class HMM:
    def __init__(self, initial, matrix):
        self.initial = normalize(initial)
        self.a = np.asarray(matrix, dtype=float).copy()
        if self.a.shape != (len(self.initial), len(self.initial)) or not np.isfinite(self.a).all() or np.any(self.a < 0) or not np.allclose(self.a.sum(1), 1):
            raise ValueError('Row-stochastic square matrix required')
        self.p = self.initial.copy()

    def update(self, emission, dt=None):
        e = normalize(emission)
        if e.shape != self.p.shape:
            raise ValueError('Emission dimension mismatch')
        prior = self.p if dt is None else self.p @ transition(self.a, dt)
        self.p = normalize(prior * np.maximum(e, 1e-300))
        return self.p.copy()

    def viterbi(self, emissions, times):
        if len(emissions) != len(times):
            raise ValueError('Time/emission length mismatch')
        if not len(times):
            return []
        emissions = np.array([normalize(e) for e in emissions])
        score = np.log(np.maximum(self.initial, 1e-300)) + np.log(np.maximum(emissions[0], 1e-300))
        back = []
        for i in range(1, len(times)):
            a = transition(self.a, times[i]-times[i-1])
            candidates = score[:, None] + np.log(np.maximum(a, 1e-300))
            parent = candidates.argmax(0)
            back.append(parent)
            score = candidates[parent, np.arange(len(score))] + np.log(np.maximum(emissions[i], 1e-300))
            score -= score.max()
        path = [int(score.argmax())]
        for b in reversed(back):
            path.append(int(b[path[-1]]))
        return path[::-1]


class HSMM:
    """Online explicit-duration filter, Weibull survival S(t)=exp(-(t/scale)^shape).

    Cohorts retain actual start timestamps; no fixed-FPS duration assumption.
    Capped support forces exit at max_duration_s (declared in config).
    """
    def __init__(self, cfg):
        self.cfg = copy.deepcopy(cfg)
        self.a = np.asarray(cfg['matrix'], dtype=float)
        self.scale = np.asarray(cfg['duration_scale_s'], dtype=float)
        self.shape = np.asarray(cfg['duration_shape'], dtype=float)
        self.initial = normalize(cfg['initial'])
        k = len(self.initial)
        if self.a.shape != (k, k) or not np.isfinite(self.a).all() or np.any(self.a < 0) or not np.allclose(self.a.sum(1), 1) or np.any(np.diag(self.a) != 0):
            raise ValueError('HSMM exit matrix must be stochastic without self transitions')
        if self.scale.shape != (k,) or self.shape.shape != (k,) or not np.isfinite(self.scale).all() or not np.isfinite(self.shape).all() or np.any(self.scale <= 0) or np.any(self.shape <= 0):
            raise ValueError('Positive duration parameters required')
        self.mass = None
        self.starts = None
        self.last = None

    def update(self, emission, t):
        e = normalize(emission)
        if e.shape != self.initial.shape or not np.isfinite(t):
            raise ValueError('Invalid HSMM observation')
        if self.last is None:
            self.mass = (self.initial*e)[:, None]
            self.starts = np.array([t])
        else:
            if t <= self.last:
                raise ValueError('Monotonic HSMM time required')
            # Bounded physical substeps allow multiple renewals across a sparse interval.
            # ponytail: right-endpoint renewal approximation; refine max_step_s if needed.
            count = int(math.ceil((t-self.last)/self.cfg.get('max_step_s', .02)))
            grid = np.linspace(self.last, t, count+1)
            for old_t, new_t in zip(grid[:-1], grid[1:]):
                before = np.maximum(0, old_t-self.starts)[None, :]
                after = (new_t-self.starts)[None, :]
                log_ratio = -((after/self.scale[:, None])**self.shape[:, None] - (before/self.scale[:, None])**self.shape[:, None])
                survive = np.exp(np.maximum(log_ratio, -745))
                survive[:, after[0] >= self.cfg['max_duration_s']] = 0
                exiting = (self.mass*(1-survive)).sum(1) @ self.a
                self.mass = np.column_stack((self.mass*survive, exiting))
                self.starts = np.r_[self.starts, new_t]
                keep = (self.mass.sum(0) > 1e-300) & (new_t-self.starts <= self.cfg['max_duration_s'])
                self.mass = self.mass[:, keep]
                self.starts = self.starts[keep]
            self.mass *= e[:, None]
        total = self.mass.sum()
        if not np.isfinite(total) or total <= 0:
            raise ValueError('Impossible HSMM emission: zero posterior mass')
        self.mass /= total
        self.last = t
        return self.mass.sum(1)


def geometry(points):
    p = np.asarray(points, dtype=float)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
        raise ValueError('Finite N by 3 points required')
    if len(p) < 3:
        return None
    lo, hi = np.quantile(p, [.02, .98], axis=0)
    span = hi-lo
    center = p.mean(0)
    values, vectors = np.linalg.eigh(np.cov(p.T, bias=True))
    tilt = None if values[-1] <= 1e-10 or values[-1]-values[-2] < .1*values[-1] else float(np.degrees(np.arccos(np.clip(abs(vectors[2, -1]), 0, 1))))
    volume = float(np.prod(span))
    return dict(height=float(span[2]), width=float(max(span[:2])), depth=float(min(span[:2])),
                zmin=float(p[:, 2].min()), zmax=float(p[:, 2].max()), z90=float(np.quantile(p[:, 2], .9)),
                center=center.tolist(), centroid_z=float(center[2]), volume=volume, count=len(p),
                density=len(p)/max(volume, 1e-6), tilt_deg=tilt, low_fraction=float((p[:, 2] < .6).mean()),
                eigen_ratio=float(values[-1]/max(values.sum(), 1e-10)), bbox=[lo.tolist(), hi.tolist()])


def posture_emission(f, cfg):
    if f is None:
        return np.array([.01, .01, .01, .01, .01, .95])
    # Rule prototypes are deliberately NOT semantic training or calibrated likelihoods.
    x = np.array([f['z90'], f['height']])
    mu = np.asarray(cfg['means_z90_height'])
    sd = np.asarray(cfg['std_z90_height'])
    logp = -.5*np.sum(((x-mu)/sd)**2, axis=1)-np.log(sd).sum(1)
    if f.get('vertical_velocity') is not None and abs(f['vertical_velocity']) > cfg['fast_speed_mps']:
        logp[4] += 2
    logp -= logp.max()
    e = np.exp(logp)
    if f['tilt_deg'] is None or f['count'] < cfg['weak_points']:
        e[-1] += e.sum()
    return normalize(e+1e-8)


class Track:
    def __init__(self, cfg):
        self.cfg = copy.deepcopy(cfg)
        self.reset()

    def reset(self):
        c = self.cfg
        self.posture = HMM(c['posture']['initial'], c['posture']['matrix'])
        self.presence = HMM([.25, .25, .5], c['presence_matrix'])
        self.hsmm = HSMM(c['event'])
        ec = c['event']
        # Match each Weibull's mean with a geometric HMM mean, at reference step .1s.
        means = np.array([s*math.gamma(1+1/k) for s,k in zip(ec['duration_scale_s'],ec['duration_shape'])])
        hazard = np.minimum(.99, .1/means)
        matrix = np.asarray(ec['matrix'])*hazard[:,None]+np.diag(1-hazard)
        self.event_hmm = HMM(ec['initial'], matrix)
        self.last = self.previous = self.seen = self.armed = None
        self.ema = None
        self.votes = []
        self.hysteresis = False
        self.low_since = None
        self.stable = 0
        self.last_class = None
        self.emitted = False
        self.mc = self.presence.initial.copy()

    def update(self, t, feature, rf):
        if not np.isfinite(t) or (rf is not None and (not np.isfinite(rf) or not 0 <= rf <= 1)):
            raise ValueError('Invalid time or RF probability')
        reset = self.last is not None and (t <= self.last or t-self.last > self.cfg['reset_gap_s'])
        if reset:
            self.reset()
        dt = None if self.last is None else t-self.last
        f = copy.deepcopy(feature)
        if f is not None:
            numeric = ['height', 'width', 'depth', 'z90', 'centroid_z', 'count']
            if any(k not in f or not np.isfinite(f[k]) for k in numeric) or np.asarray(f.get('center')).shape != (3,) or not np.isfinite(f['center']).all():
                raise ValueError('Finite complete physical feature required')
            if min(f['height'], f['width'], f['depth']) < 0 or f['count'] < 3 or (f.get('tilt_deg') is not None and (not np.isfinite(f['tilt_deg']) or not 0 <= f['tilt_deg'] <= 90)):
                raise ValueError('Invalid physical feature range')
        if f is not None and rf is None:
            raise ValueError('Observed candidate needs RF')
        if f is not None:
            f.update(vertical_velocity=None, horizontal_velocity=None, height_velocity=None, tilt_velocity=None)
            if self.previous is not None and dt:
                prev = self.previous
                f['vertical_velocity'] = (f['centroid_z']-prev['centroid_z'])/dt
                f['horizontal_velocity'] = float(np.linalg.norm(np.array(f['center'][:2])-prev['center'][:2])/dt)
                f['height_velocity'] = (f['height']-prev['height'])/dt
                if f['tilt_deg'] is not None and prev['tilt_deg'] is not None:
                    f['tilt_velocity'] = (f['tilt_deg']-prev['tilt_deg'])/dt
            self.seen = t
        missing_age = None if self.seen is None else t-self.seen
        base = None if f is None else rf >= self.cfg['rf_threshold']
        if f is None:
            self.previous = None
            self.armed = None
            self.low_since = None
            self.emitted = False
        else:
            alpha = 1 if self.ema is None else 1-math.exp(-(dt or .1)/self.cfg['ema_tau_s'])
            self.ema = rf if self.ema is None else self.ema+alpha*(rf-self.ema)
            self.hysteresis = rf >= (self.cfg['hysteresis_off'] if self.hysteresis else self.cfg['hysteresis_on'])
            self.previous = copy.deepcopy(f)
        self.votes.append((t, base))
        self.votes = [(a, b) for a, b in self.votes if t-a <= self.cfg['vote_window_s']]
        observed_votes = [b for _, b in self.votes if b is not None]
        hold = f is None and missing_age is not None and missing_age <= self.cfg['hold_s'] and self.hysteresis
        if f is None and not hold:
            self.ema = None
            self.hysteresis = False
        cls = int(np.argmax(posture_emission(f, self.cfg['posture'])))
        self.stable = self.stable+1 if f is not None and cls == self.last_class else (1 if f is not None else 0)
        self.last_class = cls
        ep = posture_emission(f, self.cfg['posture'])
        pp = self.posture.update(ep, dt)
        pe = [.01, .01, .98] if f is None else [max(rf, .001), max(1-rf, .001), .03]
        # MC observes discrete RF bins; HMM presence consumes continuous RF likelihoods.
        mc_prior = self.mc if dt is None else self.mc @ transition(self.presence.a, dt)
        mc_obs = np.array([.05, .05, .05]); mc_obs[2 if base is None else (0 if base else 1)] = .9
        self.mc = normalize(mc_prior*mc_obs)
        pr = self.presence.update(pe, dt)
        low = f is not None and f['z90'] < self.cfg['low_z90_m'] and f['height'] < self.cfg['low_height_m']
        fast = False
        if f is not None and not low and f['z90'] > 1.1 and rf >= self.cfg['rf_threshold']:
            if self.armed is None or f['centroid_z'] >= self.armed[1]:
                self.armed = (t, f['centroid_z'])
        if self.armed and t-self.armed[0] > self.cfg['armed_s']:
            self.armed = None
        if low:
            if self.low_since is None:
                self.low_since = t
            if self.armed:
                delta = t-self.armed[0]
                fast = delta > 0 and self.armed[1]-f['centroid_z'] >= self.cfg['min_drop_m'] and (self.armed[1]-f['centroid_z'])/delta >= self.cfg['posture']['fast_speed_mps']
        else:
            self.low_since = None
        if f is None:
            ee = [.01, .001, .001, .001, .987]
        elif low and fast:
            ee = [.02, .75, .20, .01, .02]
        elif low:
            ee = [.5, .005, .05 if self.emitted else .005, .005, .05]
        elif self.emitted:
            ee = [.2, .001, .001, .75, .048]
        else:
            ee = [.96, .001, .001, .008, .03]
        hp = self.hsmm.update(ee, t)
        eh = self.event_hmm.update(ee, dt)
        candidate = bool(low and fast and t-self.low_since >= self.cfg['low_hold_s'] and not self.emitted and hp[1]+hp[2] >= self.cfg['event_probability'])
        if candidate:
            self.emitted = True
        if f is not None and not low and hp[3] > .5:
            self.emitted = False
        self.last = t
        return dict(feature=f, reset=reset, missing=f is None, missing_age_s=missing_age, stable_frames=self.stable,
                    baseline=base, ema=None if f is None else self.ema >= self.cfg['rf_threshold'],
                    vote=None if not observed_votes or f is None else sum(observed_votes) > len(observed_votes)/2,
                    hysteresis=None if f is None else self.hysteresis, hold_prediction=bool(hold),
                    mc=self.mc.tolist(), presence=pr.tolist(), emission=ep.tolist(), posture=pp.tolist(),
                    hsmm=hp.tolist(), event_emission=normalize(ee).tolist(), event_hmm=eh.tolist(),
                    event=EVENTS[int(hp.argmax())], candidate=candidate, confirmed=False)


def sequence(rows, cfg, start=0):
    """Track cache keyed by session AND upstream ID. Decode each contiguous segment."""
    tracks = {}; outputs = []; segments = []; active_segments = {}
    for row in rows[start:]:
        key = (row['sid'], row['track_id'])
        if key not in tracks:
            tracks[key] = Track(cfg)
        model = tracks[key]
        out = model.update(row['time'], row['feature'], row['rf'])
        if key not in active_segments or out['reset']:
            if key in active_segments:
                segments.append(active_segments[key])
            active_segments[key] = []
        out.update(fi=row['fi'], time=row['time'], track_id=row['track_id'], sid=row['sid'], rf=row['rf'])
        outputs.append(out); active_segments[key].append(len(outputs)-1)
    segments.extend(active_segments.values())
    for ids in segments:
        hmm = HMM(cfg['posture']['initial'], cfg['posture']['matrix'])
        path = hmm.viterbi([outputs[i]['emission'] for i in ids], [outputs[i]['time'] for i in ids])
        for i, state in zip(ids, path):
            outputs[i]['offline_viterbi'] = POSTURES[state]
    return outputs
