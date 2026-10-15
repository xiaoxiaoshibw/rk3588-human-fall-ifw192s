"""Read-only static-anchor audit before changing the same-page scene experiment."""
import argparse
from pathlib import Path
import numpy as np
import yaml
from actions import HERE, OUT, read, dump, load, sha
from core import roi_mask
from research_actions import frame_points
from research_scene_change import domain
from scene_change import FrozenSurfaces


def initial_anchors(model, p, valid):
    ids = np.flatnonzero(valid)
    sample = ids[np.linspace(0, len(ids)-1, min(len(ids), model.cfg['anchor_limit']), dtype=int)] if len(ids) else ids
    d, ix = model.tree.query(p[sample]); keep = (d <= model.tau*model.cfg['anchor_radius_tau']) & model.planar[ix]
    sample, ix = sample[keep], ix[keep]
    residual = np.abs(np.einsum('ij,ij->i', p[sample]-model.centers[ix], model.normals[ix]))
    return sample[residual <= np.quantile(residual, model.cfg['anchor_trim_quantile'])] if len(residual) else sample


def main(output, geometry_ledger=None):
    output.mkdir(parents=True, exist_ok=False)
    cat = read(OUT/'catalog.json'); cfg = read(OUT/'RUN_MANIFEST.json')['config']
    prior = Path(cfg['background_experiment']); controls = yaml.safe_load((HERE/'config_scene_change.yaml').read_text(encoding='utf8'))
    model = FrozenSurfaces(np.load(prior/'background.npz')['xyz'], cat['background']['tolerance_m'], controls)
    limits = read(HERE/'action_research_scenechange_guarded/CALIBRATION.json')['limits']
    records = []; hashes_all = {}
    if geometry_ledger:
        from scene_geometry_ledger import GeometryLedger
        cache = GeometryLedger(geometry_ledger)
    else: cache = None
    for rec in cat['sessions']:
        sid = rec['session_id']
        if not cache:
            meta, raw, hashes = load(sid)
            assert hashes == rec['source_sha256']; hashes_all[sid] = hashes
        reg = None if sid == cat['background']['session'] else read(prior/(sid+'_registration.json'))
        frames = rec['available_frames']
        picks = sorted(set([frames[0], frames[len(frames)//2], frames[-1]]+[i for i in [30, 124, 192] if i in frames]))
        for fi in picks:
            if cache: q,p,_ = cache.frame(sid,fi)
            else: q, p = frame_points(raw, meta['frames'][fi], reg)
            valid = domain(q, p, cfg)
            anchors = initial_anchors(model, p, valid); inside = roi_mask(p, cfg['roi_xy'])
            old = read(HERE/'action_research_scenechange_guarded'/sid/f'{fi:04d}.json')
            candidate = np.array(old['selection']['selected_source_indices'], int)
            anchor_ids = np.flatnonzero(valid & ~inside)
            _, new = model.compensate(p[anchor_ids], limits)
            records.append({'sid':sid,'fi':fi,'initial_anchor_count':len(anchors),
                'initial_anchors_inside_activity_roi':int(inside[anchors].sum()),
                'initial_anchors_overlap_candidate':int(len(np.intersect1d(anchors,candidate))),
                'candidate_overlap_identity':'GEOMETRIC_CANDIDATE_NOT_HUMAN_GT',
                'old_vibration':old['vibration'],'outside_roi_vibration':new,
                'outside_roi_input_rows':anchor_ids.tolist(), 'initial_anchor_source_rows':anchors.tolist()})
        print(sid, len(picks), 'diagnosed', flush=True)
    dump(output/'DIAGNOSIS.json', {'frames':records,'inputs':hashes_all,'config':cfg,'controls':controls,
         'command':'diagnose_scene_static.py --out '+str(output),
         'code_sha256':{'diagnose_scene_static.py':sha(HERE/'diagnose_scene_static.py'),'scene_change.py':sha(HERE/'scene_change.py')},
         'threshold_changes':False,'human_identity':'UNKNOWN','action_frames_used_for_calibration':False})
    if cache: dump(output/'GEOMETRY_CACHE_PROVENANCE.json',cache.provenance())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--geometry-ledger',type=Path)
    args=parser.parse_args();main(args.out,args.geometry_ledger)
