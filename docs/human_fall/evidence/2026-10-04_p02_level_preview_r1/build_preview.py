"""Observed-plane offline leveling; preserves raw data and measured height."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
from core.calibration import apply_transform, invert_transform, validate_rotation
from core.joint_leveling import joint_rotation


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def write(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def stats(z):
    return {'count': len(z), 'rms_m': float(np.sqrt(np.mean(z ** 2))),
            'p95_abs_m': float(np.percentile(np.abs(z), 95)),
            'median_m': float(np.median(z)), 'std_m': float(np.std(z)),
            'support_fraction_005': float(np.mean(np.abs(z) <= .05))}


def main():
    assert not (OUT / '01_DISPLAY_MODEL.json').exists(), 'immutable outputs already exist'
    baseline = load(OUT / '00_BASELINE.json')
    for name, expected in baseline['current_inputs'].items():
        assert sha(ROOT / name) == expected, name
    audit = load(ROOT / 'docs/human_fall/evidence/2026-10-04_p02_bias_review_r1/00_SOURCE_AUDIT.json')
    selection = load(ROOT / 'docs/human_fall/evidence/2026-10-04_p02_ground_r2/01_SELECTION.json')
    normal, offset = np.array(audit['source_normal']), audit['source_d_m']
    rotation = joint_rotation(audit['pitch_deg_source_ground_gauge'], audit['roll_deg_source_ground_gauge'])
    validate_rotation(rotation)
    assert np.max(np.abs(rotation @ normal - [0, 0, 1])) < 1e-12
    model = {'kind': 'observed_ground_display_leveling', 'schema': 1, 'status': 'research_display',
             'from_frame': 'innolidar', 'to_frame': 'ground_display_roi3', 'units': 'm',
             'direction': 'p_to=R@p_from+t', 'convention': 'active column vectors; R=Rx(roll)@Ry(pitch)',
             'pitch_deg': audit['pitch_deg_source_ground_gauge'], 'roll_deg': audit['roll_deg_source_ground_gauge'],
             'yaw_deg': 0, 'rotation': rotation.tolist(), 'translation_m': [0., 0., offset],
             'plane_source': {'normal': normal.tolist(), 'offset_m': offset},
             'physical_measurement': {'height_m': 1.14, 'method': 'user laser rangefinder',
                                      'measurement_datum_to_point_origin': 'not_bound'},
             'physical_verified': False, 'extrinsics_verified': False, 'runtime_eligible': False,
             'coverage': 'frozen annotator #3 VAL, A/C data; wider ground unverified'}
    model['model_id'] = 'display:' + hashlib.sha256(json.dumps(model, sort_keys=True).encode()).hexdigest()
    initial = np.array(selection['display_transform']['matrix_rowmajor'])
    rois = {'#1': [1.04, 1.75, -.93, -.45], '#2': [1.94, 2.40, -.94, .07],
            '#3': [1.32, 1.76, -.38, .20], '#4': [2.64, 3.31, -.57, .19]}
    pools, previews, frames, frozen = {}, [], [], []
    errors = {'forward_z': 0., 'inverse_xyz': 0., 'signed_residual': 0.}
    for label, sid in [('A', selection['A']['session']), ('B', 'cap_20261004_203135'), ('C', selection['C']['session'])]:
        directory = ROOT / 'captures/remote' / sid
        for filename in ['meta.json', 'points.bin']:
            expected = selection['input_sha_check'][str(directory / filename)]
            assert sha(directory / filename) == expected
        meta = load(directory / 'meta.json')
        raw = np.memmap(directory / 'points.bin', dtype='u1', mode='r')
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        rows_all, source_all = [], []
        for ordinal, frame in enumerate(meta['frames']):
            lo, count = frame['offset_points'], frame['count_points']
            points = xyz[lo:lo + count].astype(float); rows = np.arange(lo, lo + count, dtype=np.int64)
            valid = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)
            points, rows = points[valid], rows[valid]
            before = points @ initial[:3, :3].T + initial[:3, 3]
            after = apply_transform(points, model)
            errors['forward_z'] = max(errors['forward_z'], float(np.max(np.abs(after[:, 2] - (points @ normal + offset)))))
            errors['inverse_xyz'] = max(errors['inverse_xyz'], float(np.max(np.abs(apply_transform(after, invert_transform(model)) - points))))
            entry = {'session': sid, 'state': label, 'ordinal': ordinal, 'seq': frame['seq'], 'valid_count': len(rows), 'regions': {}}
            for region, (xl, xh, yl, yh) in rois.items():
                mask = (before[:, 0] >= xl) & (before[:, 0] <= xh) & (before[:, 1] >= yl) & (before[:, 1] <= yh)
                if mask.any():
                    pools.setdefault((label, region), []).append(after[mask, 2])
                    entry['regions'][region] = stats(after[mask, 2])
                if region == '#3' and label in ['A', 'C']:
                    rows_all.append(rows[mask]); source_all.append(points[mask])
                    frozen.append((label, ordinal, rows[mask], points[mask], after[mask]))
            frames.append(entry)
            if ordinal in [0, len(meta['frames']) // 2, len(meta['frames']) - 1]:
                # Visual samples only; all numerical checks above retain all valid points.
                visible = (before[:, 0] >= .3) & (before[:, 0] <= 4) & (np.abs(before[:, 1]) <= 1.2)
                indices = np.flatnonzero(visible); indices = indices[np.linspace(0, len(indices) - 1, min(len(indices), 1800), dtype=int)]
                colors = ((before[indices, 0] >= 1.32) & (before[indices, 0] <= 1.76)
                          & (before[indices, 1] >= -.38) & (before[indices, 1] <= .20)).astype(int)
                previews.append({'name': label + ' frame ' + str(ordinal), 'source': points[indices].tolist(),
                                 'before': before[indices].tolist(), 'after': after[indices].tolist(), 'roi3': colors.tolist()})
        if label in ['A', 'C']:
            assert hashlib.sha256(np.concatenate(rows_all).tobytes()).hexdigest() == selection[label]['row_index_sha256']
            assert len(np.vstack(source_all)) == selection[label]['points_selected']
        for filename in ['meta.json', 'points.bin']:
            assert sha(directory / filename) == selection['input_sha_check'][str(directory / filename)]
    combined_source = np.vstack([f[3] for f in frozen]); combined_after = np.vstack([f[4] for f in frozen])
    assert len(combined_source) == 101948 and errors['forward_z'] < 1e-12 and errors['inverse_xyz'] < 1e-12
    centered = combined_source - combined_source.mean(axis=0)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    fitted = vt[-1] if vt[-1] @ normal > 0 else -vt[-1]
    assert np.max(np.abs(fitted - normal)) < 1e-12
    errors['signed_residual'] = float(np.max(np.abs(combined_after[:, 2] - (combined_source @ normal + offset))))
    summary = {'model_id': model['model_id'], 'all_frames_processed': len(frames),
               'confirmed_roi3_A_C_count': len(combined_source), 'roi3_ground_z_stats': stats(combined_after[:, 2]),
               'other_regions_domain': 'whole XY footprints, all heights; NOT confirmed ground error',
               'state_region_z': {label + region: stats(np.concatenate(values)) for (label, region), values in pools.items()},
               'checks': errors, 'regional_coverage': 'only #3 ground rows physically anchored; other scene footprints diagnostic'}
    write('01_DISPLAY_MODEL.json', model); write('02_METRICS.json', summary); write('03_FRAME_STATS.json', frames)
    with (OUT / '04_FROZEN_LEVELED_POINTS.npz').open('xb') as stream:
        np.savez_compressed(stream, source=combined_source, leveled=combined_after,
                            source_rows=np.concatenate([f[2] for f in frozen]),
                            session_code=np.concatenate([np.full(len(f[2]), 0 if f[0] == 'A' else 2, dtype=np.uint8) for f in frozen]),
                            frame_ordinal=np.concatenate([np.full(len(f[2]), f[1], dtype=np.int16) for f in frozen]))
    preview = previews[0]; fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for row, axis in enumerate([0, 1]):
        for col, name in enumerate(['before', 'after']):
            cloud = np.asarray(preview[name]); roi = np.array(preview['roi3'], dtype=bool); ax = axes[row, col]
            ax.scatter(cloud[~roi, axis], cloud[~roi, 2], s=2, color='#a5aeb7', alpha=.6)
            ax.scatter(cloud[roi, axis], cloud[roi, 2], s=8, color='#dc7c19', label='ROI #3')
            ax.axhline(0, color='#b52525', lw=1); ax.set_ylim(-.55, .65)
            ax.set_xlabel(('X' if axis == 0 else 'Y') + ' (m)'); ax.set_ylabel('Z (m)')
            ax.set_title('Nominal display (26 deg, 1.34 m)' if name == 'before' else 'ROI #3 observed-plane leveling')
            ax.grid(alpha=.2); ax.legend(loc='upper right')
    fig.suptitle('Same source rows; measured height remains 1.14 m; other regions unverified')
    fig.savefig(OUT / '05_BEFORE_AFTER.png', dpi=160); plt.close(fig)
    reference = {'kind': 'annotator_display_reference', 'pitch_deg': 26., 'roll_deg': 0.,
                 'display_z_translation_m': 1.34, 'physical_height_record_m': 1.14,
                 'rotation': initial[:3, :3].tolist(), 'translation_m': initial[:3, 3].tolist(),
                 'source': 'pc_apps/human_replay/annotator.html buildMatrix', 'runtime_eligible': False}
    write('05_REFERENCE_MODEL.json', reference)
    template = (OUT / 'preview_template.html').read_text(encoding='utf-8')
    payload = json.dumps({'model': model, 'reference': reference, 'metrics': summary, 'frames': previews}, ensure_ascii=True).replace('<', '\\u003c')
    with (OUT / '06_PREVIEW.html').open('x', encoding='utf-8') as stream:
        stream.write(template.replace('__PAYLOAD__', payload))
    write('07_SUBMISSION.json', {'files': {p.name: sha(p) for p in OUT.iterdir() if p.is_file()}, 'status': 'SUBMITTED_author_verified'})
    print(json.dumps({'frames': len(frames), 'roi3': summary['roi3_ground_z_stats'], 'checks': errors}, indent=2))


if __name__ == '__main__':
    main()
