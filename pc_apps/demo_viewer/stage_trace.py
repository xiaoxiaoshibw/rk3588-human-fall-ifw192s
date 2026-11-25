"""Reproducible, display-only row provenance for the offline replay.

All ownership labels are geometric associations, never ground truth.
"""
import hashlib
import numpy as np
from core.range_denoise import denoise


def row_digest(rows):
    rows = np.sort(np.asarray(rows, dtype='<i8'))
    return dict(count=int(len(rows)), sha256=hashlib.sha256(rows.tobytes()).hexdigest())


def trace_frame(frame, background, record, components, basis, offset, extra, exploration):
    valid = frame.valid
    background_result = background.foreground(frame)
    changed = background_result['mask']
    with np.errstate(invalid='ignore'):
        in_range = (frame.range_m >= .1) & (frame.range_m <= 8.)
    foreground = changed & in_range
    cleaned = denoise(frame, foreground)['mask']
    target = np.asarray(record['target_source_rows'], dtype=np.int64)
    others = [t for t in record['tracks'] if t['track_id'] != record['target_track_id']
              and t.get('observed') and t.get('source_rows')]

    def describe(rows, geometry=False):
        rows = np.sort(np.asarray(rows, dtype=np.int64))
        result = row_digest(rows)
        if geometry and len(rows):
            points = frame.xyz[rows].astype(float) @ np.asarray(basis).T
            points[:, 2] += float(offset)
            result['min_m'] = np.min(points, axis=0).tolist()
            result['max_m'] = np.max(points, axis=0).tolist()
        return result

    def grid(mask):
        return describe(frame.source_rows[mask], True)

    stages = dict(grid_valid=grid(valid), known_background=grid(valid & background.known),
                  unknown_background=grid(valid & ~background.known),
                  background_rejected=grid(valid & background.known & ~changed),
                  foreground_out_of_range=grid(changed & ~in_range),
                  foreground=grid(foreground), denoise_rejected=grid(foreground & ~cleaned),
                  denoise_kept=grid(cleaned))
    comp = []
    for c in components:
        rows = c['source_rows']
        item = describe(rows, True)
        item.update(id=int(c['component_id']), retained=bool(c['retained']),
                    target_overlap=int(np.intersect1d(rows, target).size),
                    other_tracks=[t['track_id'] for t in others
                                  if np.intersect1d(rows, t['source_rows']).size])
        comp.append(item)
    observed = [dict(track_id=t['track_id'], **describe(t['source_rows'], True)) for t in others]
    masks = dict(unknown_background=valid & ~background.known,
                 background_rejected=valid & background.known & ~changed,
                 foreground_out_of_range=changed & ~in_range,
                 denoise_rejected=foreground & ~cleaned, denoise_kept=cleaned)
    def provenance(rows):
        rows = np.asarray(rows, dtype=np.int64)
        result = {name: describe(np.intersect1d(rows, frame.source_rows[mask]))
                  for name, mask in masks.items()}
        if len(rows):
            heights = frame.xyz[rows].astype(float) @ np.asarray(basis)[2] + float(offset)
            result['below_0_10m'] = describe(rows[heights < .10])
        else:
            result['below_0_10m'] = describe([])
        return result
    return dict(raw_count=int(len(frame.xyz)),
                decode_rejected={name: describe(rows) for name, rows in frame.rejected.items()},
                stages=stages, components=comp, target=describe(target, True),
                other_observed_tracks=observed, supplemental=describe(extra, True),
                exploration=describe(exploration, True),
                candidate_provenance=dict(target=provenance(target), supplemental=provenance(extra),
                                          exploration=provenance(exploration)),
                foreground_delta_m=float(background.delta_m), semantic='UNKNOWN',
                note='Grid rows are nearest-return selections; component associations do not establish human ownership.')
