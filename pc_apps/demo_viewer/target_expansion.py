"""Conservative display-only expansion of a measured target for offline replay.

A relaxed foreground component may contain ground or furniture. It is a separate
candidate, never passed to tracking, coordinates or the fall state machine.
"""
import numpy as np
from core.range_denoise import denoise
from core.range_components import label_components


def supplemental(frame, background, record, basis, offset, delta_m=.20):
    if delta_m not in (.15, .20):
        raise ValueError('unsupported display-only background threshold')
    rows=record['target_source_rows']; tid=record['target_track_id']
    result=dict(status='no_target', source_rows=[], added=0, reason='no_target')
    if not rows or tid is None:
        return result
    seed=frame.valid & np.isin(frame.source_rows,np.asarray(rows,dtype=np.int64))
    with np.errstate(invalid='ignore'):
        mask=frame.valid & background.known & ((background.mean_m-frame.range_m)>delta_m)
        mask &= (frame.range_m>=.1) & (frame.range_m<=8.)
    if delta_m == .15:
        # Exploration only: exclude newly added near-ground returns; true feet
        # may also be excluded because the fitted plane is not verified.
        cells=np.flatnonzero(mask)
        xyz=frame.xyz[frame.source_rows.ravel()[cells]].astype(float)
        heights=xyz @ np.asarray(basis)[2] + float(offset)
        mask.ravel()[cells[heights < .10]]=False
        mask |= seed
    cleaned=denoise(frame,mask)['mask']
    if delta_m == .15:
        cleaned |= seed
    labels,components=label_components(frame,cleaned,min_points=1)
    ids=np.unique(labels[seed]); ids=ids[ids>=0]
    if not len(ids):
        return dict(status='unavailable', source_rows=[], added=0, reason='seed_not_in_relaxed_foreground')
    proposed=np.unique(np.concatenate([components[int(i)]['source_rows'] for i in ids]))
    target=np.asarray(rows,dtype=np.int64)
    # Refuse a whole component when it touches another observed track: dropping
    # its rows alone would conceal a collision and still swallow its background.
    competing=[]
    for track in record['tracks']:
        if track['track_id']!=tid and track.get('observed') and track.get('source_rows'):
            if np.intersect1d(proposed,np.asarray(track['source_rows'],dtype=np.int64)).size:
                competing.append(track['track_id'])
    if competing:
        return dict(status='ambiguous',source_rows=[],added=0,reason='other_observed_track',competing=competing)
    extra=np.setdiff1d(proposed,target,assume_unique=False)
    if len(proposed)>3*len(target):
        return dict(status='ambiguous',source_rows=[],added=0,reason='expanded_points_exceed_threefold')
    points=frame.xyz[proposed].astype(float) @ np.asarray(basis).T
    points[:,2]+=float(offset)
    if len(points) and (max(np.ptp(points[:,0]),np.ptp(points[:,1]))>2.5 or np.ptp(points[:,2])>2.7):
        return dict(status='ambiguous',source_rows=[],added=0,reason='expanded_envelope_exceeded')
    return dict(status='candidate' if len(extra) else 'no_addition', source_rows=extra.tolist(),
                added=int(len(extra)),reason='relaxed_foreground_seeded_component')
