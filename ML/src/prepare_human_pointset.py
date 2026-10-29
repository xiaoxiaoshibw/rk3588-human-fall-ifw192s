"""Audit raw MM-Fi crops; emit training-compatible cache only with bound extrinsics.

No fitting, axis guessing or source archive mutation. Missing/empty crops remain
in the audit and prevent cache publication, rather than dropping hard frames.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import numpy as np

from human_pointset import crop_rows, sample_rows


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def run(archive, out, sequences=None, transform=None, margin=0.25, points=256, prepare=False):
    matrix = np.eye(4)
    contract = {'status': 'unverified_identity', 'scope': 'direct-coordinate negative diagnostic'}
    if transform is not None:
        contract = json.loads(transform.read_text(encoding='utf-8'))
        matrix = np.asarray(contract['joint_to_lidar'], dtype=np.float64)
    if prepare:
        if contract.get('status') != 'verified' or contract.get('units') != 'm':
            raise ValueError('Cache requires explicit verified metre-unit extrinsics; audit needs no verification')
        evidence = contract['evidence']
        path = (transform.parent / evidence['path']).resolve()
        if sha(path) != evidence['sha256']:
            raise ValueError('Extrinsic evidence SHA mismatch')
    out.mkdir(parents=True, exist_ok=False)
    groups, failures, counts = {}, [], []
    frames = 0
    with zipfile.ZipFile(archive) as source, (out/'frames.jsonl').open('x', encoding='utf-8') as ledger:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP names')
        by_sequence = {}
        for name in names:
            match = re.fullmatch(r'(E\d{2}/S\d{2}/A\d{2})/lidar/frame(\d+)\.bin', name)
            if match:
                by_sequence.setdefault(match[1], []).append((int(match[2]), name))
        chosen = sorted(by_sequence) if sequences is None else sorted(set(sequences))
        if not chosen or set(chosen) - set(by_sequence):
            raise ValueError('Missing requested sequences')
        for sequence in chosen:
            members = sorted(by_sequence[sequence])
            gt_name = sequence + '/ground_truth.npy'
            gt_raw = source.read(gt_name)
            joints = np.load(io.BytesIO(gt_raw), allow_pickle=False)
            if (joints.shape != (len(members), 17, 3) or
                    [i for i, _ in members] != list(range(1, len(members) + 1)) or
                    not np.isfinite(joints).all()):
                raise ValueError('Joint/frame count, numbering or finite-value mismatch: ' + sequence)
            sampled = []
            for index, name in members:
                raw = source.read(name)  # zipfile verifies each consumed member CRC.
                if len(raw) % 24:
                    raise ValueError('Invalid XYZ byte count: ' + name)
                cloud = np.frombuffer(raw, dtype='<f8').reshape(-1, 3)
                selected = crop_rows(cloud, joints[index-1], matrix, margin)
                count = len(selected)
                record = {'member': name, 'frame_index_1based': index, 'gt_index_0based': index-1,
                          'source_sha256': hashlib.sha256(raw).hexdigest(), 'gt_member': gt_name,
                          'gt_sha256': hashlib.sha256(gt_raw).hexdigest(), 'source_points': len(cloud),
                          'crop_points': count, 'crop_source_rows': selected.tolist(),
                          'status': 'ok' if count >= 10 else 'insufficient_crop',
                          'label_kind': 'inherited_sequence_action; GT-conditioned input'}
                if count < 10:
                    failures.append(name)
                elif prepare:
                    local = sample_rows(cloud[selected], points, name)
                    record['sample_source_rows'] = selected[local].tolist()
                    sampled.append(cloud[selected[local]].astype(np.float32))
                ledger.write(json.dumps(record, allow_nan=False) + '\n')
                counts.append(count)
                frames += 1
            if prepare and len(sampled) == len(members):
                groups[sequence] = np.asarray(sampled)
    published = prepare and not failures
    if published:
        with (out/('points%d.npz' % points)).open('xb') as stream:
            np.savez_compressed(stream, **groups)
    result = {'archive': str(archive), 'archive_sha256': sha(archive), 'sequences': chosen, 'frames': frames,
              'transform': contract, 'transform_sha256': sha(transform) if transform else None,
              'margin_input_units': margin, 'points_per_frame': points,
              'crop': 'axis-aligned joint envelope expanded on each side; no normalization',
              'crop_counts_min_median_max': [int(min(counts)), float(np.median(counts)), int(max(counts))],
              'insufficient_frames': len(failures), 'cache_published': published,
              'cache_sha256': sha(out/('points%d.npz' % points)) if published else None,
              'scope': 'GT oracle diagnostic, not deployable person segmentation or point GT',
              'evaluation': 'Oracle GT cropping at test time must be labelled separately from GT-free inference',
              'IFW192S_action_accuracy': 'UNKNOWN', 'fall_recall': 'UNKNOWN'}
    dump(out/'INPUT.json', result)
    print(json.dumps({k: result[k] for k in ['frames', 'insufficient_frames', 'cache_published', 'crop_counts_min_median_max']}), flush=True)
    if prepare and failures:
        raise ValueError('Insufficient crops; audit retained, no partial cache published')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sequences', nargs='+')
    parser.add_argument('--transform', type=Path)
    parser.add_argument('--margin', type=float, default=0.25)
    parser.add_argument('--points', type=int, default=256)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    run(args.archive, args.output, args.sequences, args.transform, args.margin, args.points, args.prepare)
