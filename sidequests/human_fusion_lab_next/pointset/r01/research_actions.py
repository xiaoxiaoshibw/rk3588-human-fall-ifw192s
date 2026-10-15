"""R2 source-bound diagnosis first; no changes to frozen r01 algorithms or outputs."""
import argparse
import copy
import platform
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from actions import HERE, ROOT, OUT, R, T, load, read, dump, sha, choose
from core import cluster, roi_mask

E = ROOT/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2'
RESULT = HERE/'action_research_r2'
COLORS = ['#8294a6', '#e37c69', '#8daa70', '#12a4bb', '#bb83ca']
LAYERS = ['raw', 'background_removed', 'foreground', 'target', 'unselected']


def frame_points(raw, f, reg):
    q = raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8')
    p = q@R.T+T
    if reg:
        p = p@np.array(reg['R']).reshape(3, 3).T+reg['t']
    return q, p


def masks(q, p, tree, tau, cfg):
    radius = np.linalg.norm(q, axis=1)
    valid = np.isfinite(q).all(axis=1)&np.any(q != 0, axis=1)&(radius > cfg['range_min_m'])&(radius < cfg['range_max_m'])
    domain = valid&(p[:, 2] >= cfg['z_min_m'])&(p[:, 2] <= cfg['z_max_m'])
    dist = np.full(len(p), np.inf)
    dist[domain] = tree.query(p[domain])[0]
    fg = np.flatnonzero(domain&(dist > tau))
    return valid, domain, dist, fg


def display(p, ids, cap=6000):
    sample = ids[np.linspace(0, len(ids)-1, min(cap, len(ids)), dtype=int)] if len(ids) else ids
    return {'count': len(ids), 'display_count': len(sample), 'sampled': len(ids) > cap,
            'points': np.round(p[sample], 4).tolist(), 'display_source_indices': sample.tolist()}


def plot_layers(p, layers, sid, fi):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(17, 9))
    target = p[layers['target']]
    center = np.median(target, axis=0) if len(target) else np.array([1.5, 1., .8])
    bounds = [(center[0]-1.6, center[0]+1.6), (center[1]-1.6, center[1]+1.6), (-.28, 2.3)]
    for i, name in enumerate(LAYERS):
        # Full members in fixed central view; offscreen points remain in source archive.
        q = p[layers[name]]
        for row, dims in enumerate([(0, 1), (0, 2)]):
            ax = fig.add_subplot(3, 5, row*5+i+1)
            ax.scatter(q[:, dims[0]], q[:, dims[1]], s=.8, c=COLORS[i], rasterized=True)
            ax.set(xlim=bounds[dims[0]], ylim=bounds[dims[1]], xlabel='XYZ'[dims[0]]+' (m)', ylabel='XYZ'[dims[1]]+' (m)')
            ax.grid(alpha=.2)
            if row == 0:
                ax.set_title(name+' · '+str(len(q)))
        ax = fig.add_subplot(3, 5, 11+i, projection='3d')
        keep = np.all((q >= [b[0] for b in bounds])&(q <= [b[1] for b in bounds]), axis=1)
        q = q[keep]
        ax.scatter(*q.T, s=.6, c=COLORS[i], rasterized=True)
        ax.set(xlim=bounds[0], ylim=bounds[1], zlim=bounds[2], xlabel='X m', ylabel='Y m', zlabel='Z m')
        ax.view_init(elev=25, azim=135)
    fig.suptitle(f'{sid} / f{fi} · AI_INFERRED inspection, identity UNKNOWN · same source and transform')
    fig.tight_layout()
    fig.savefig(E/'figures'/f'{sid}_{fi:04d}.png', dpi=120)
    plt.close(fig)


def diagnose():
    if not (E/'BASELINE_BEFORE.json').exists():
        raise ValueError('Complete preservation baseline first')
    if RESULT.exists():
        raise ValueError('Research output already exists; never overwrite evidence')
    RESULT.mkdir(); (E/'figures').mkdir()
    cat = read(OUT/'catalog.json'); manifest = read(OUT/'RUN_MANIFEST.json'); cfg = manifest['config']
    prior = Path(cfg['background_experiment']); bg = prior/'background.npz'
    assert sha(bg) == cat['background']['background_file_sha256']
    assert sha(HERE/'core.py') == manifest['code_sha256']['core.py']
    assert sha(HERE/'config.yaml') == manifest['code_sha256']['config.yaml']
    tree = cKDTree(np.load(bg)['xyz']); tau = cat['background']['tolerance_m']
    cases = []; allstats = []; ambiguity = []; sources = {}
    for rec in cat['sessions']:
        sid = rec['session_id']; meta, raw, hashes = load(sid); assert hashes == rec['source_sha256']; sources[sid] = hashes
        reg = None if sid == cat['background']['session'] else read(prior/(sid+'_registration.json'))
        folder = RESULT/sid; folder.mkdir()
        summary = read(OUT/sid/'summary.json')['frames']
        chosen = {rec['available_frames'][0]: ['START'], rec['available_frames'][-1]: ['RECOVERY_OR_END']}
        low = min(summary, key=lambda r: r['height_p90'] if r['height_p90'] is not None else np.inf)['fi']
        chosen.setdefault(low, []).append('MINIMUM_P90')
        for fi in [max(0, low-10), min(rec['frame_count']-1, low+10), rec['frame_count']//2]:
            if fi in rec['available_frames']: chosen.setdefault(fi, []).append('TRANSITION_CONTEXT')
        bad = [r['fi'] for r in summary if r['selected_points'] and not r['valid_nodes']]
        ambiguity += [{'sid': sid, 'fi': f} for f in bad]
        if bad: chosen.setdefault(bad[len(bad)//2], []).append('AXIS_AMBIGUITY')
        reviewframes = set(chosen)
        for fi in bad:
            reviewframes.update(f for f in [fi-1, fi, fi+1] if f in rec['available_frames'])
        last_center = None; last_t = None; last_seen = None
        for fi in rec['available_frames']:
            baseline = read(OUT/sid/f'{fi:04d}.json'); f = meta['frames'][fi]; q, p = frame_points(raw, f, reg)
            valid, domain, dist, fg = masks(q, p, tree, tau, cfg); groups, _ = cluster(p[fg], cfg)
            assert len(fg) == baseline['fg_count']
            t = baseline['t_sec']
            if last_t is not None and t-last_t > cfg['max_gap_s']: last_center = None; last_seen = None
            if last_seen is not None and t-last_seen > cfg['max_gap_s']: last_center = None
            winner = choose(groups, p, fg, cfg, last_center, None)
            ids = np.array(baseline['selection']['selected_source_indices'], dtype=int)
            assert np.array_equal(fg[groups[winner[1]]] if winner else np.array([], dtype=int), ids)
            if winner: last_center = winner[2][:2]; last_seen = t
            last_t = t
            layers = {'raw': np.flatnonzero(valid), 'background_removed': np.flatnonzero(domain&(dist <= tau)),
                      'foreground': fg, 'target': ids, 'unselected': np.setdiff1d(fg, ids)}
            np.savez_compressed(folder/f'{fi:04d}_sources.npz', **layers,
                                outside_domain=np.flatnonzero(valid&~domain))
            parts = []; near_removed = np.array([], dtype=int); near_noise = np.array([], dtype=int)
            if len(ids):
                target_tree = cKDTree(p[ids])
                for gi, g in enumerate(groups):
                    members = fg[g]
                    if winner and gi == winner[1]: continue
                    d = target_tree.query(p[members])[0]
                    parts.append({'cluster': gi, 'source_indices': members.tolist(), 'count': len(members),
                                  'min_target_distance_m': float(d.min()), 'p90_target_distance_m': float(np.quantile(d, .9)),
                                  'roi_fraction': float(roi_mask(p[members], cfg['roi_xy']).mean()),
                                  'z_quantiles_m': np.quantile(p[members, 2], [.1, .5, .9]).tolist(), 'identity': 'UNKNOWN'})
                rm = layers['background_removed']
                near_removed = rm[target_tree.query(p[rm])[0] <= .12]
                covered = np.concatenate([fg[g] for g in groups]) if groups else np.array([], dtype=int)
                noise = np.setdiff1d(fg, covered)
                near_noise = noise[target_tree.query(p[noise])[0] <= .20]
            stats = {'sid': sid, 'fi': fi, 't_sec': t, 'target_count': len(ids), 'fragment_count': len(parts),
                     'near_fragments_20cm': sum(a['min_target_distance_m'] <= .20 for a in parts),
                     'near_removed_count': len(near_removed), 'near_noise_count': len(near_noise),
                     'valid_nodes': sum(n['valid'] for o in baseline['body_3d'] for n in o['skeleton']['nodes'].values()),
                     'association_id': baseline['body_3d'][0]['id'] if len(ids) else None}
            allstats.append(stats)
            row = {'sid': sid, 'fi': fi, 'source_sha256': hashes, 'source_frame': f, 't_sec': t,
                   'coordinate_frame': baseline['coordinate_frame'], 'layers': {k: display(p, v) for k, v in layers.items()},
                   'fragments': parts, 'near_removed_source_indices': near_removed.tolist(), 'near_noise_source_indices': near_noise.tolist(),
                   'stats': stats, 'semantic_provenance': 'AI_INFERRED', 'human_precision': None, 'furniture_contamination_rate': None,
                   'risk_status': {k: 'UNKNOWN' for k in ['background_overdeletion', 'body_fragmentation', 'furniture_contact', 'wrong_cluster', 'occlusion']},
                   'body_axis_ambiguity': 'OBSERVED' if fi in bad else 'NOT_OBSERVED_BY_BASELINE',
                   'note': 'Proximity is an inspection cue, not human identity. Full membership in sources.npz; displays explicitly sampled.'}
            dump(folder/f'{fi:04d}.json', row)
            if fi in reviewframes:
                cases.append({'sid': sid, 'fi': fi, 'roles': chosen.get(fi, ['AXIS_OR_NEIGHBOR']), 'stats': stats,
                              'provenance': 'AI_INFERRED', 'identity': 'UNKNOWN'})
            if fi in chosen: plot_layers(p, layers, sid, fi)
        print('DIAGNOSED', sid, len(rec['available_frames']), 'ambiguity', len(bad), flush=True)
    assert len(allstats) == 1966 and len(ambiguity) == 79
    dump(RESULT/'catalog.json', cat)
    dump(E/'DIAGNOSIS.json', {'status': 'SOURCE_REPRODUCED', 'frames': allstats, 'cases': cases, 'ambiguity_frames': ambiguity,
                             'human_precision': None, 'furniture_contamination_rate': None, 'sources': sources})
    dump(E/'DIAGNOSTIC_MANIFEST.json', {'config': cfg, 'code_sha256': {n: sha(HERE/n) for n in ['core.py', 'actions.py', 'research_actions.py']},
         'registrations': {r['session_id']: sha(prior/(r['session_id']+'_registration.json')) for r in cat['sessions'][:-1]},
         'background_sha256': sha(bg), 'python': platform.python_version(), 'numpy': np.__version__,
         'holdout_policy': '32 original mod3=2 only; no experiment selection from holdout', 'roi_changed': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['diagnose'])
    args = parser.parse_args()
    diagnose()
