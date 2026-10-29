"""Attribute each Falling clip to "input lost upstream" vs "input present, no trigger".

Consumes the per-frame ledger (fall_observation_ledger.py) plus the raw crop of
the fall-like actions, and reports, per sequence:

* the frozen window contract (>=10 consecutive valid frames, <=0.5 s gaps);
* whether the posture actually changes inside the observed frames, or inside a
  zero-length stretch of the actor crop.

Posture is taken from the actor crop only: camera-frame height above the
lowest observed foot level, plus the inclination of the long principal axis
against sensor +z.  Sensor +z is verified as "up" on standing clips; it is a
sensor-frame statement, not a physical calibration of any IFW192S mount.
Whole-clip labels stay clip-level; no frame-level fall ground truth is invented.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import tarfile

import numpy as np

MINIMUM_POINTS = 10
MINIMUM_FRAMES = 10
UPRIGHT_MAX_INCL = 30.0
LYING_MIN_INCL = 65.0
# A lying body is flat: its vertical span is body thickness.  A crop that holds
# two standing actors is wide *and* ~1.6 m tall, so the span rule keeps
# interaction actions from masquerading as "low posture".
LYING_MAX_SPAN = 1.10


def load_ledger(directory):
    run = json.loads((directory / 'RUN.json').read_text(encoding='utf-8'))
    records = {}
    with (directory / 'OBSERVATIONS.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            records[row['sequence']] = row
    return run, records


def load_labels(core):
    with tarfile.open(core, 'r:') as tar:
        def table(name):
            with tar.extractfile(name) as stream:
                return list(csv.DictReader(io.StringIO(stream.read().decode('utf-8'))))
        labels = table('labels.csv')
        test = {row['seq_id'] for row in table('splits/xsub_test.csv')}
    return {row['seq_id']: {'person': row['person'], 'action': row['action'],
                            'split': 'test' if row['seq_id'] in test else 'train'} for row in labels}


def inclination(axis):
    return float(np.degrees(np.arccos(np.clip(abs(axis[2]), 0.0, 1.0))))


def posture(points, offsets, stamps, index):
    block = points[offsets[index]:offsets[index + 1], :3]
    if len(block) < 3:
        return None
    centre = block.mean(0)
    values, vectors = np.linalg.eigh((block - centre).T @ (block - centre) / len(block))
    axis = vectors[:, int(np.argmax(values))]
    return {'f': index, 't': float(stamps[index]), 'n': int(len(block)),
            'top': float(block[:, 2].max()), 'bottom': float(block[:, 2].min()),
            'incl': inclination(axis), 'centre_z': float(centre[2])}


def gaps(record):
    """Contiguous stretches of frames without a usable actor crop."""
    out, start = [], None
    bad = set(record['zero_frames']) | set(record['short_frames'])
    for i in range(record['frames']):
        if i in bad:
            if start is None:
                start = i
        elif start is not None:
            out.append([start, i - 1])
            start = None
    if start is not None:
        out.append([start, record['frames'] - 1])
    return out


def analyse_clip(raw, record):
    """Classify where the posture change of one clip lives.

    The long principal axis of a standing actor is vertical (inclination ~0-20
    deg against sensor +z) and of a lying actor horizontal (~80-90 deg).  A clip
    only carries descent evidence when an upright frame and a lying frame are
    separated by no unusable frame.
    """
    points, offsets, stamps = raw['points'], raw['frame_offsets'], raw['timestamps_bag']
    frames = [posture(points, offsets, stamps, i) for i in range(len(stamps))]
    valid = [f for f in frames if f is not None and f['n'] >= MINIMUM_POINTS]
    if not valid:
        return {'posture': 'NO_VALID_FRAME', 'gaps': gaps(record)}
    floor = min(f['bottom'] for f in valid)
    tallest = max(f['top'] - f['bottom'] for f in valid)
    for f in frames:
        if f is not None:
            f['height'] = round(f['top'] - floor, 4)
            f['span'] = round(f['top'] - f['bottom'], 4)
    present = {f['f']: f for f in valid}
    missing = set()
    for start, stop in gaps(record):
        missing.update(range(start, stop + 1))
    upright = [f['f'] for f in valid if f['incl'] <= UPRIGHT_MAX_INCL]
    lying = [f['f'] for f in valid if f['incl'] >= LYING_MIN_INCL]
    runs = [run for run in record['valid_runs'] if len(run)]
    # Descent evidence inside one uninterrupted run of usable frames beats any
    # later dropout: once the actor lies still, the crop may drop out without
    # erasing the transition that was already seen.
    observed, gap_run, recovery = None, None, False
    for index, run in enumerate(runs):
        series = [present[i]['incl'] for i in run if i in present]
        if not series or min(series) > UPRIGHT_MAX_INCL or max(series) < LYING_MIN_INCL:
            continue
        first_up = min(i for i in run if i in present and present[i]['incl'] <= UPRIGHT_MAX_INCL)
        last_lie = max(i for i in run if i in present and present[i]['incl'] >= LYING_MIN_INCL)
        if first_up < last_lie:
            observed = index
            break
        if last_lie < first_up and observed is None:
            recovery = True
    if not lying:
        posture_class, blocking = 'NEVER_LYING', []
    elif not upright:
        posture_class, blocking = 'LOW_WITHOUT_UPRIGHT', []
    elif observed is not None:
        posture_class, blocking = 'DESCENT_OBSERVED', []
    else:
        up_runs = [i for i, run in enumerate(runs)
                   if any(i2 in present and present[i2]['incl'] <= UPRIGHT_MAX_INCL for i2 in run)]
        lie_runs = [i for i, run in enumerate(runs)
                    if any(i2 in present and present[i2]['incl'] >= LYING_MIN_INCL for i2 in run)]
        if up_runs and lie_runs and min(up_runs) < max(lie_runs):
            posture_class, blocking = 'DESCENT_INSIDE_GAP', []
            blocking = sorted(missing)
        elif recovery:
            posture_class, blocking = 'LIES_THEN_UPRIGHT', []
        else:
            posture_class, blocking = 'LIES_THEN_UPRIGHT', []
    inclinations = [f['incl'] for f in valid]
    return {'posture': posture_class,
            'start_incl': round(inclinations[0], 1), 'end_incl': round(inclinations[-1], 1),
            'min_incl': round(min(inclinations), 1), 'max_incl': round(max(inclinations), 1),
            'tallest_span': round(tallest, 4), 'floor_z': round(floor, 4),
            'upright_frames': upright[:8] + (['...'] if len(upright) > 8 else []),
            'lying_frames': lying[:8] + (['...'] if len(lying) > 8 else []),
            'blocking_frames': blocking[:40],
            'gaps': gaps(record),
            'first_valid': valid[0]['f'], 'last_valid': valid[-1]['f'],
            'series': [[f['f'], round(f['t'], 3), f['n'], round(f['height'], 3), round(f['incl'], 1)]
                       for f in frames if f is not None]}


def clip_posture(record):
    """Inclination and vertical span per usable frame, straight from the ledger."""
    out = []
    for frame in record['per_frame']:
        shape = frame.get('shape')
        if frame['n'] < MINIMUM_POINTS or not shape:
            continue
        out.append((inclination(shape['axis']), shape['zspan']))
    return out


def clip_inclinations(record):
    """Inclination per usable frame straight from the ledger (no raw needed)."""
    out = []
    for frame in record['per_frame']:
        shape = frame.get('shape')
        if frame['n'] < MINIMUM_POINTS or not shape:
            continue
        out.append(inclination(shape['axis']))
    return out


def posture_by_action(records, labels):
    """How often an action ever reaches a low posture, over the whole package."""
    table = {}
    for sequence, record in records.items():
        action = labels[sequence]['action']
        values = clip_posture(record)
        if not values:
            continue
        incls = [v[0] for v in values]
        row = table.setdefault(action, {'clips': 0, 'with_upright': 0, 'with_low': 0, 'medians': []})
        row['clips'] += 1
        row['with_upright'] += int(min(incls) <= UPRIGHT_MAX_INCL)
        row['with_low'] += int(any(i >= LYING_MIN_INCL and span <= LYING_MAX_SPAN for i, span in values))
        row['medians'].append(float(np.median(incls)))
    for row in table.values():
        medians = row.pop('medians')
        row['median_of_clip_medians'] = round(float(np.median(medians)), 1)
        row['upright_fraction'] = round(row['with_upright'] / row['clips'], 3)
        row['low_fraction'] = round(row['with_low'] / row['clips'], 3)
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--positive', default='Falling')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)

    run, records = load_ledger(args.ledger)
    labels = load_labels(args.core)
    raw_dir = args.ledger / 'RAW'

    rows = []
    for seq, record in sorted(records.items()):
        meta = labels[seq]
        row = {'sequence': seq, 'action': meta['action'], 'person': meta['person'],
               'split': meta['split'], 'frames': record['frames'],
               'zero_frames': len(record['zero_frames']), 'short_frames': len(record['short_frames']),
               'longest_valid_run': record['longest_valid_run'],
               'windows': record['window_count'], 'gaps': gaps(record),
               'duration_s': record['duration_s'], 'median_dt_s': record['median_dt_s']}
        path = raw_dir / (seq + '.npz')
        if path.exists():
            with np.load(path, allow_pickle=False) as raw:
                row['geometry'] = analyse_clip({k: raw[k] for k in raw.files}, record)
        rows.append(row)

    positives = [r for r in rows if r['action'] == args.positive]
    histogram = {}
    for r in rows:
        name = (r.get('geometry') or {}).get('posture', 'NO_RAW')
        histogram[name] = histogram.get(name, 0) + 1
    summary = {'ledger': str(args.ledger), 'sensor': run['sensor'],
               'archive_sha256': run['archive_sha256'],
               'rule': {'minimum_points': MINIMUM_POINTS, 'minimum_frames': MINIMUM_FRAMES,
                        'max_gap_s': run['max_gap_s'],
                        'upright_max_incl': UPRIGHT_MAX_INCL, 'lying_min_incl': LYING_MIN_INCL,
                        'lying_max_span': LYING_MAX_SPAN},
               'frame_labels': 'UNKNOWN',
               'clips': len(rows), 'posture_histogram': histogram,
               'posture_by_action': posture_by_action(records, labels),
               'positive_clips': len(positives),
               'positive_without_window': [r['sequence'] for r in positives if r['windows'] == 0],
               'positive_descent_observed': [r['sequence'] for r in positives
                                             if r.get('geometry', {}).get('posture') == 'DESCENT_OBSERVED'],
               'positive_descent_in_gap': [r['sequence'] for r in positives
                                           if r.get('geometry', {}).get('posture') == 'DESCENT_INSIDE_GAP'],
               'rows': rows}
    (args.out / 'ATTRIBUTION.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                               encoding='utf-8')
    print('clips', len(rows), 'positives', len(positives),
          'no-window', len(summary['positive_without_window']),
          'descent-observed', len(summary['positive_descent_observed']),
          'descent-in-gap', len(summary['positive_descent_in_gap']))


if __name__ == '__main__':
    main()