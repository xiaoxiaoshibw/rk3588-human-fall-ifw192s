"""Expected failure against frozen implementation, prior to fixed tests."""
from association import OLD

ts=[dict(track_id='A',position_m=[0,0,0]),dict(track_id='B',position_m=[.45,0,0])]
cs=[dict(candidate_id='X',position_m=[.4,0,0]),dict(candidate_id='Y',position_m=[-.4,0,0])]
r=OLD.associate_tracks(ts,cs)
print(r,flush=True)
assert not {m['candidate_id'] for m in r['matches']} & set(r['ambiguous_candidate_ids']), 'CONFIRMED_FROZEN_CONTRACT_DEFECT'
