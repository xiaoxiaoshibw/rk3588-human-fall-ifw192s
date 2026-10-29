"""Admission gate for a fall dataset: is the event actually observable?

A clip-level "fall" label is not evidence.  The LaserAct audit showed that 26 of
30 clips labelled Falling never contain an upright posture at all, so a model
trained or scored on them measures "body on the floor", not a fall.  This gate
answers one question per clip, from geometry only:

    can a causal detector see an upright body, then a body on the floor, with no
    unusable frame in between and enough real time for the transition?

This is a geometry diagnostic, NOT sensor visibility or evaluation eligibility.
A failed rule must never remove a true event from end-to-end recall, or turn a
fall-labelled clip into a negative. All attempted captures stay in the ledger.

Input is one npz per clip with the same layout the rest of ML/ uses:
`points` (N,4), `frame_offsets` (F+1,), `timestamps_bag` (F,).
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from fall_observation_ledger import frame_shape

UPRIGHT_MAX_INCL = 30.0
LYING_MIN_INCL = 65.0
LYING_MAX_SPAN = 1.10
MINIMUM_POINTS = 10
MAX_GAP_S = 0.5
MIN_EVENT_S = 0.6  # Legacy argument only; a long unsampled interval is not descent evidence.

VERDICTS = ('OK', 'NO_VALID_FRAME', 'NEVER_UPRIGHT', 'NEVER_LOW', 'EVENT_IN_GAP',
            'TOO_SHORT')


def _inclination(axis):
    return float(math.degrees(math.acos(min(1.0, abs(float(axis[2]))))))


def frame_evidence(points, offsets, stamps, minimum_points=MINIMUM_POINTS):
    """Per frame: inclination, vertical span, usable flag, timestamp."""
    points, offsets, stamps = validate_clip(points, offsets, stamps)
    rows = []
    for index in range(len(stamps)):
        block = points[offsets[index]:offsets[index + 1], :3]
        if len(block) < minimum_points or not np.isfinite(block).all():
            rows.append({'f': index, 't': float(stamps[index]), 'n': int(len(block)),
                         'incl': None, 'span': None})
            continue
        shape = frame_shape(block)
        rows.append({'f': index, 't': float(stamps[index]), 'n': int(len(block)),
                     'incl': _inclination(shape['axis']), 'span': float(shape['zspan'])})
    return rows


def validate_clip(points, offsets, stamps):
    """Validate source layout before slicing; clocks must be strictly increasing."""
    points, offsets, stamps = np.asarray(points), np.asarray(offsets), np.asarray(stamps)
    if (points.ndim != 2 or points.shape[1] not in (3, 4) or
            offsets.ndim != 1 or offsets.dtype.kind not in 'iu' or
            stamps.ndim != 1 or len(offsets) != len(stamps) + 1 or
            offsets[0] != 0 or offsets[-1] != len(points) or
            np.any(offsets[1:] < offsets[:-1]) or not np.isfinite(stamps).all() or
            np.any(np.diff(stamps) <= 0)):
        raise ValueError('Invalid point layout or non-increasing timestamps')
    return points, offsets.astype(np.int64), stamps.astype(np.float64)


def _runs(rows, max_gap_s):
    """Contiguous usable frames, split by dropouts and by real time gaps."""
    runs, current = [], []
    for row in rows:
        if row['incl'] is None:
            if current:
                runs.append(current)
                current = []
            continue
        if current and row['t'] - current[-1]['t'] > max_gap_s:
            runs.append(current)
            current = []
        current.append(row)
    if current:
        runs.append(current)
    return runs


def screen_clip(points, offsets, stamps, upright_max=UPRIGHT_MAX_INCL,
                lying_min=LYING_MIN_INCL, lying_max_span=LYING_MAX_SPAN,
                minimum_points=MINIMUM_POINTS, max_gap_s=MAX_GAP_S,
                min_event_s=MIN_EVENT_S):
    if (not all(math.isfinite(v) for v in (upright_max, lying_min, lying_max_span,
                                          max_gap_s, min_event_s)) or
            not 0 <= upright_max < lying_min <= 90 or lying_max_span <= 0 or
            max_gap_s <= 0 or min_event_s < 0 or
            not isinstance(minimum_points, int) or isinstance(minimum_points, bool) or minimum_points < 3):
        raise ValueError('Invalid geometry diagnostic thresholds')
    points, offsets, stamps = validate_clip(points, offsets, stamps)
    rows = frame_evidence(points, offsets, stamps, minimum_points)
    usable = [row for row in rows if row['incl'] is not None]
    metrics = {'frames': len(rows), 'usable_frames': len(usable),
               'duration_s': round(float(stamps[-1] - stamps[0]), 3) if len(stamps) > 1 else 0.0,
               'fps': round(1.0 / float(np.median(np.diff(stamps))), 2) if len(stamps) > 2 else None}
    if not usable:
        return {'verdict': 'NO_VALID_FRAME', 'reasons': ['no frame with enough points'],
                'metrics': metrics}

    upright = [row for row in usable if row['incl'] <= upright_max]
    low = [row for row in usable if row['incl'] >= lying_min and row['span'] <= lying_max_span]
    metrics.update({'upright_frames': len(upright), 'low_frames': len(low),
                    'min_incl': round(min(r['incl'] for r in usable), 1),
                    'max_incl': round(max(r['incl'] for r in usable), 1),
                    'max_span': round(max(r['span'] for r in usable), 3)})
    if not upright:
        return {'verdict': 'NEVER_UPRIGHT', 'reasons': ['no frame in upright band'],
                'metrics': metrics}
    if not low:
        tall_low = [row for row in usable
                    if row['incl'] >= lying_min and row['span'] > lying_max_span]
        reason = ('low inclination only on a tall crop (probably two actors)'
                  if tall_low else 'no frame in lying band')
        return {'verdict': 'NEVER_LOW', 'reasons': [reason], 'metrics': metrics}

    runs = _runs(rows, max_gap_s)
    metrics['longest_run_s'] = round(max(run[-1]['t'] - run[0]['t'] for run in runs), 3)
    ordered_pair = any(u['f'] < low[-1]['f'] for u in upright)
    if not ordered_pair:
        return {'verdict': 'NEVER_LOW',
                'reasons': ['body only reaches the floor before standing'], 'metrics': metrics}
    continuous_pair = False
    for run in runs:
        last_up = None
        for end, row in enumerate(run):
            if row['incl'] <= upright_max:
                last_up = end
            if last_up is None or row['incl'] < lying_min or row['span'] > lying_max_span:
                continue
            continuous_pair = True
            middle = [r for r in run[last_up + 1:end] if upright_max < r['incl'] < lying_min]
            if middle:
                metrics.update(descent_frames=len(middle),
                               transition_s=round(row['t'] - run[last_up]['t'], 3),
                               transition_from_frame=run[last_up]['f'], transition_to_frame=row['f'])
                return {'verdict': 'OK', 'reasons': [], 'metrics': metrics}
    if continuous_pair:
        metrics['descent_frames'] = 0
        return {'verdict': 'TOO_SHORT', 'reasons': ['no sampled intermediate posture'], 'metrics': metrics}
    first_low = next(r['f'] for r in low if any(u['f'] < r['f'] for u in upright))
    last_up = max(u['f'] for u in upright if u['f'] < first_low)
    metrics['blocking_frames'] = [r['f'] for r in rows[last_up + 1:first_low] if r['incl'] is None]
    return {'verdict': 'EVENT_IN_GAP', 'reasons': ['transition crosses unusable frames or timestamp gap'],
            'metrics': metrics}


def load_clip(path):
    with np.load(path, allow_pickle=False) as raw:
        return raw['points'], raw['frame_offsets'], raw['timestamps_bag']


def screen_directory(clips, manifest=None, out=None, **kwargs):
    manifest = manifest or {}
    rows = []
    for path in sorted(Path(clips).glob('*.npz')):
        points, offsets, stamps = load_clip(path)
        result = screen_clip(points, offsets, stamps, **kwargs)
        entry = dict(manifest.get(path.stem, {}), clip=path.stem, **result)
        rows.append(entry)
    counts = {}
    for row in rows:
        counts[row['verdict']] = counts.get(row['verdict'], 0) + 1
    summary = {'scope': 'geometry_diagnostic_only; not visibility or recall eligibility',
               'clips': len(rows), 'verdicts': counts,
               'ok_fraction': round(counts.get('OK', 0) / len(rows), 3) if rows else 0.0,
               'rule': {'upright_max_incl': kwargs.get('upright_max', UPRIGHT_MAX_INCL),
                        'lying_min_incl': kwargs.get('lying_min', LYING_MIN_INCL),
                        'lying_max_span': kwargs.get('lying_max_span', LYING_MAX_SPAN),
                        'minimum_points': kwargs.get('minimum_points', MINIMUM_POINTS),
                        'max_gap_s': kwargs.get('max_gap_s', MAX_GAP_S),
                        'transition_requirement': 'measured intermediate posture in one continuous run'},
               'rows': rows}
    if out:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'GATE.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                       encoding='utf-8')
    return summary


def read_manifest(path):
    """CSV with a `clip` column plus optional `subject`, `label`, `kind`."""
    if not path:
        return {}
    with open(path, encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if rows and 'clip' not in rows[0]:
        raise ValueError('manifest needs a clip column')
    return {row['clip']: {k: v for k, v in row.items() if k != 'clip' and v != ''} for row in rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clips', type=Path, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    summary = screen_directory(args.clips, read_manifest(args.manifest), args.out)
    print('clips %d ok %.3f %s' % (summary['clips'], summary['ok_fraction'], summary['verdicts']))


if __name__ == '__main__':
    main()
