"""Query IDs are ephemeral. Only unique current measurements can supply event rows."""
import copy
from collections import deque
import numpy as np
import torch
from torch import nn


class Association:
    def __init__(self, gate=.65, max_gap=.5):
        self.gate = gate; self.max_gap = max_gap
        self.tracks = {}; self.time = None; self.counter = 0

    def update(self, t, observations):
        if not np.isfinite(t): raise ValueError('Finite device time')
        reset = self.time is not None and (t <= self.time or t-self.time > self.max_gap)
        if reset: self.tracks = {}
        self.time = t
        self.tracks = {k:v for k, v in self.tracks.items() if t-v['strong_time'] <= self.max_gap}
        seen = set(); obs = []
        for item in observations:
            x = copy.deepcopy(item); p = np.asarray(x['center'], dtype=float)
            ids = x['rows']
            if p.shape != (3,) or not np.isfinite(p).all() or not isinstance(ids, list) or any(type(i) is not int or i < 0 or i in seen for i in ids) or len(ids) != len(set(ids)):
                raise ValueError('Finite center/disjoint current source rows required')
            seen.update(ids); obs.append(x)
        candidates = [[key for key, v in self.tracks.items() if np.linalg.norm(np.asarray(x['center'])-v['center']) <= self.gate] for x in obs]
        claims = {key:sum(key in c for c in candidates) for key in self.tracks}
        outputs = []
        for x, c in zip(obs, candidates):
            ident = None; state = 'UNKNOWN_ASSOCIATION'; reliable = x.get('reliable') is True
            if len(c) == 1 and claims[c[0]] == 1:
                ident = c[0]; state = 'MEASURED' if reliable else 'WEAK'
            elif not c and reliable:
                self.counter += 1; ident = self.counter; state = 'MEASURED'
            # Merges/splits invalidate all involved identities, so later unique
            # observations start fresh instead of reviving an ambiguous history.
            if len(c) > 1 or any(claims[k] > 1 for k in c):
                for k in c: self.tracks.pop(k, None)
            if ident is not None and reliable:
                self.tracks[ident] = dict(center=np.array(x['center']), strong_time=t)
            outputs.append(dict(identity=ident, state=state, event_rows=x['rows'] if state == 'MEASURED' else [], reset=reset))
        return outputs


class CausalGRU(nn.Module):
    """Untrained interface, not used as learned state in E0 results."""
    def __init__(self, features=8, hidden=32):
        super().__init__(); self.gru = nn.GRU(features+1, hidden, batch_first=True); self.head = nn.Linear(hidden, 4)
        self.history = deque(maxlen=8); self.identity = None; self.time = None

    def step(self, t, identity, features, observed=True):
        if not np.isfinite(t): raise ValueError('Finite device time')
        if identity != self.identity or (self.time is not None and (t <= self.time or t-self.time > 1)):
            self.history.clear()
        self.identity = identity; self.time = t
        self.history = deque([x for x in self.history if 0 <= t-x[0] <= 1], maxlen=8)
        x = torch.as_tensor(features, dtype=torch.float32)
        if x.shape != (8,) or not torch.isfinite(x).all(): raise ValueError('Finite state feature shape')
        if identity is None:
            self.history.clear(); return None
        self.history.append((t, torch.cat([x if observed else x*0, torch.tensor([float(observed)])])))
        sequence = torch.stack([a[1] for a in self.history])[None]
        result, _ = self.gru(sequence)
        return self.head(result[:, -1])
