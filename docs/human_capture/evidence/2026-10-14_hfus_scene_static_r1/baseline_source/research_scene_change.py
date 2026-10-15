"""Same-page, independent scene-change candidate experiment; exclusive output."""
import argparse
import copy
import sys
import time
from pathlib import Path
import numpy as np
import yaml
from actions import HERE, OUT, ROOT, read, dump, sha, load, choose, Posture, describe_object
from core import cluster, roi_mask
from research_actions import frame_points
from scene_change import FrozenSurfaces


def domain(raw, p, cfg):
    radius = np.linalg.norm(raw, axis=1)
    return (np.isfinite(raw).all(axis=1) & np.any(raw != 0, axis=1)
            & (radius > cfg['range_min_m']) & (radius < cfg['range_max_m'])
            & (p[:, 2] >= cfg['z_min_m']) & (p[:, 2] <= cfg['z_max_m']))


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    cat = read(OUT/'catalog.json'); cfg = read(OUT/'RUN_MANIFEST.json')['config']
    controls = yaml.safe_load((HERE/'config_scene_change.yaml').read_text(encoding='utf8'))
    prior = Path(cfg['background_experiment']); bgmeta = read(prior/'background.json')
    if sha(prior/'background.npz') != cat['background']['background_file_sha256']:
        raise ValueError('Frozen background drift')
    before = {str(HERE/n): sha(HERE/n) for n in ['core.py', 'actions.py', 'config.yaml', 'config_actions.yaml']}
    before.update({str(prior/n): sha(prior/n) for n in ['background.npz', 'background.json']})
    model = FrozenSurfaces(np.load(prior/'background.npz')['xyz'], bgmeta['tolerance_m'], controls)
    # Geometry comes from FIT only; pose envelope comes from empty CAL only.
    meta, raw, hashes = load(cat['background']['session'])
    expected = next(r['source_sha256'] for r in cat['sessions'] if r['session_id'] == cat['background']['session'])
    if hashes != expected: raise ValueError('Empty source drift')
    calibration = []
    for fi in bgmeta['calibration']:
        q, p = frame_points(raw, meta['frames'][fi], None)
        _, diag = model.compensate(p[domain(q, p, cfg)])
        calibration.append({'fi': fi, **diag})
    usable = [r for r in calibration if r['status'] == 'COMPENSATED']
    # A voxel half-edge is positional map quantisation, not an action-tuned margin.
    typical_range = float(np.median(np.linalg.norm(model.xyz, axis=1)))
    limits = {'translation_m': float(np.quantile([r['translation_m'] for r in usable], controls['envelope_quantile'])) + cfg['voxel_m']/2,
              'rotation_rad': float(np.quantile([r['rotation_rad'] for r in usable], controls['envelope_quantile'])) + cfg['voxel_m']/2/typical_range} if usable else {'translation_m': 0., 'rotation_rad': 0.}
    dump(output/'CALIBRATION.json', {'frames': calibration, 'limits': limits,
         'fit_background_sha256': sha(prior/'background.npz'), 'planar_background_voxels': int(model.planar.sum()),
         'surface_tolerance_m': model.tau, 'holdout_used_for_calibration': False,
         'coordinate_status': 'NOMINAL_OFFLINE_NOT_PHYSICAL_CALIBRATION'})
    rows = []; sessions = []; codes = {}
    for rec in cat['sessions']:
        sid = rec['session_id']; meta, raw, hashes = load(sid)
        if hashes != rec['source_sha256']: raise ValueError('Action source drift')
        reg = None if sid == cat['background']['session'] else read(prior/(sid+'_registration.json'))
        if reg and reg['gate']['status'] != 'PASS': raise ValueError('Rejected alignment')
        folder = output/sid; folder.mkdir()
        last = seen = last_t = None; state = Posture(cfg); generation = 0
        for fi in rec['available_frames']:
            base = read(OUT/sid/f'{fi:04d}.json'); q, p = frame_points(raw, meta['frames'][fi], reg)
            nominal = p.copy()
            valid = domain(q, p, cfg)
            _, diag = model.compensate(p[valid], limits)
            if diag['status'] == 'COMPENSATED':
                p = p @ np.array(diag['R']).T + diag['t']
            codes[diag['status']] = codes.get(diag['status'], 0)+1
            valid = domain(q, p, cfg)
            fg, matched, dist, surface_extra, ambiguous = model.split_pose_hypotheses(nominal, p, valid)
            # Independent current 3D components, never an attachment to R1's winner.
            groups, _ = cluster(p[fg], cfg); t = base['t_sec']
            reset = last_t is not None and (t <= last_t or t-last_t > cfg['max_gap_s'])
            if reset or (seen is not None and t-seen > cfg['max_gap_s']):
                last = seen = None; state = Posture(cfg)
            winner = choose(groups, p, fg, cfg, last, None)
            ids = fg[groups[winner[1]]] if winner else np.empty(0, int)
            body = []
            if winner:
                if last is None: generation += 1
                last = winner[2][:2]; seen = t
                body = [describe_object(p, ids, dist, p[np.setdiff1d(fg, ids)], model.tau, cfg, 'CHANGE-'+str(generation))]
                body[0]['semantic_identity'] = 'UNKNOWN_GEOMETRIC_PERSON_CANDIDATE'
            posture = state.update(t, p[ids] if len(ids) else None); last_t = t
            oldids = np.array(base['selection']['selected_source_indices'], int)
            sample = fg[np.linspace(0, len(fg)-1, min(1800, len(fg)), dtype=int)] if len(fg) else []
            record = copy.deepcopy(base)
            record.update(variant='scene_change', body_3d=body, full_3d=body, roi_3d=body,
                 posture=posture, foreground_display=np.round(p[sample], 4).tolist(), fg_count=len(fg),
                 added_members=[], connection_evidence=[], background_removed=int(matched.sum()),
                 roi_fg_count=int(roi_mask(p[fg], cfg['roi_xy']).sum()), vibration=diag,
                 selection={'selected_source_indices': ids.tolist(), 'candidate_count': len(groups),
                            'removed_background': int(matched.sum()), 'rejected_foreground': len(fg)-len(ids),
                            'uses_future_action_points': False},
                 scene_change={'surface_extra_removed': surface_extra, 'new_source_indices': fg.tolist(),
                    'matched_source_indices': np.flatnonzero(matched).tolist(), 'background_updated': False,
                    'pose_ambiguous_indices': np.flatnonzero(ambiguous).tolist(),
                    'pose_ambiguity_identity': 'UNKNOWN_NOT_PROVEN_SCENE_EMERGENCE',
                    'body_identity': 'UNKNOWN', 'calibration_file': 'CALIBRATION.json'},
                 delta={'old_count': len(oldids), 'new_count': len(ids),
                        'added_count': len(np.setdiff1d(ids, oldids)), 'removed_count': len(np.setdiff1d(oldids, ids))})
            assert len(np.unique(ids)) == len(ids) and np.all(np.isin(ids, fg)) and not matched[ids].any()
            dump(folder/f'{fi:04d}.json', record)
            rows.append({'sid': sid, 'fi': fi, 'domain': int(valid.sum()), 'fg': len(fg),
                'baseline_fg': base['fg_count'], 'target': len(ids), 'baseline_target': len(oldids),
                'candidate_count': len(groups), 'surface_extra_removed': surface_extra,
                'pose_ambiguous_points': int(ambiguous.sum()),
                'vibration': diag, 'source_members_verified': True,
                'human_precision': None, 'furniture_contamination': None})
        if load(sid)[2] != hashes: raise ValueError('Source changed during run')
        sessions.append(sid); print(sid, len(rec['available_frames']), 'complete', flush=True)
    preserved = {p: sha(Path(p)) == h for p, h in before.items()}
    if not all(preserved.values()): raise ValueError('Frozen implementation changed during run')
    dump(output/'SUMMARY.json', {'frames': rows, 'sessions': sessions, 'status': 'DEVELOPMENT',
         'vibration_status_counts': codes, 'elapsed_s': time.perf_counter()-start, 'preservation': preserved,
         'input_sha256': {r['session_id']: r['source_sha256'] for r in cat['sessions']},
         'configuration': {'frozen_r1': cfg, 'scene_change': controls}, 'command': sys.argv,
         'code_sha256': {n: sha(HERE/n) for n in ['scene_change.py', 'research_scene_change.py', 'config_scene_change.yaml']},
         'python': sys.version, 'numpy': np.__version__, 'semantic_accuracy': 'NOT_EVALUATED',
         'skills': ['C:/Users/30680/.codex/skills/ponytail/SKILL.md', 'C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md']})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args().out)
