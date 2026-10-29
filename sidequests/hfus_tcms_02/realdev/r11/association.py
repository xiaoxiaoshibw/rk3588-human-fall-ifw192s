"""Isolated contract correction; reuse frozen gate/scoring implementation.

Frozen consumers: core/tracking.py (one locked track), r08/wire.py (multi-track).
Only the S07 adapter imports this module. Neither frozen caller is modified.
"""
import numpy as np
from common import W

OLD = W.association_module()

def associate_tracks(tracks, candidates, dt_s=0., settings=None):
    for records, key in ((tracks, 'track_id'), (candidates, 'candidate_id')):
        if len({r[key] for r in records}) != len(records):
            raise ValueError('duplicate ' + key)
    result = OLD.associate_tracks(tracks, candidates, dt_s, settings)
    at = set(result['ambiguous_track_ids'])
    ac = set(result['ambiguous_candidate_ids'])
    # The frozen implementation only marks the nearest two. Include every
    # near-equivalent choice so a third candidate cannot seed a new track.
    for tr in tracks:
        p = OLD._position(tr)
        if p is None: continue
        scored = []
        for c in candidates:
            q = OLD._position(c)
            if q is None or not OLD._size_ok(tr, c, result['settings']): continue
            d = float(np.linalg.norm(q-p))
            if d <= result['gate_m']: scored.append((d, c['candidate_id']))
        if len(scored) < 2: continue
        best = min(x[0] for x in scored)
        near = [cid for d, cid in scored if d-best < result['settings']['ambiguity_margin_m']]
        if len(near) >= 2:
            at.add(tr['track_id']); ac.update(near)
    for match in result['matches']:
        if match['candidate_id'] in ac: at.add(match['track_id'])
    matches = [m for m in result['matches'] if m['track_id'] not in at and m['candidate_id'] not in ac]
    mt = {m['track_id'] for m in matches}; mc = {m['candidate_id'] for m in matches}
    result.update(matches=matches, ambiguous_track_ids=sorted(at,key=str), ambiguous_candidate_ids=sorted(ac,key=str),
                  unmatched_track_ids=sorted({t['track_id'] for t in tracks}-at-mt,key=str),
                  unmatched_candidate_ids=sorted({c['candidate_id'] for c in candidates if OLD._position(c) is not None}-ac-mc,key=str))
    return result

def expire(active, fi, t, ttl):
    kept = []
    for tr in active:
        if t-tr['last_t'] > ttl:
            tr['events'].append(dict(fi=fi, old=tr['state'], new='LOST', reason='TTL_EXPIRED'))
            tr['state'] = 'LOST'
        else: kept.append(tr)
    return kept

