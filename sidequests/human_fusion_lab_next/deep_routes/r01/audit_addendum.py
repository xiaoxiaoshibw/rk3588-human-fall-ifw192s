"""Review rework: explicit denominators, paired transitions, all-depth CSR."""
import argparse
import importlib.util
from pathlib import Path
import numpy as np
from probe import read, write, sha
from depth_probe import axial
_spec=importlib.util.spec_from_file_location('deep_route_summary',Path(__file__).with_name('summarize.py'))
_summary=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_summary)
quant=_summary.quant

def main(e):
    assert __debug__
    # Distinct rays in ONE coarse pixel: radial minimum != axial minimum.
    synthetic=np.array([[1.,.01,0],[1.00001,0.,0]])
    _,near,pr=axial(synthetic,64,256)
    assert pr['nearest'].tolist()==[1] and near.tolist()==[0]
    m=read(e/'RUN_MANIFEST.json');old=Path(m['old_evidence']);names=list(m['candidates'])
    rows=read(e/'attempt_r2/PILOT_ROWS.json');by={(r['sid'],r['fi'],r['route']):r for r in rows}
    common=[]
    for sid,frames in m['samples'].items():
        for fi in frames:
            if all(by[sid,fi,n]['slot_jump_m'] is not None for n in names):common.append((sid,fi))
    paired={n:{'common_transitions':len(common),'slot_jump_m':quant([by[sid,fi,n]['slot_jump_m'] for sid,fi in common]),
               'no_candidate_frames':sum(r['selected_count']==0 for r in rows if r['route']==n),
               'candidate_without_axis_frames':sum(r['selected_count']>0 and r['axis_missing'] for r in rows if r['route']==n),
               'candidate_frames':sum(r['selected_count']>0 for r in rows if r['route']==n)} for n in names}
    out=e/'axial_audit_r2';out.mkdir(exist_ok=False);axial_rows=[]
    for sid,frames in m['samples'].items():
        folder=out/sid;folder.mkdir()
        for fi in frames:
            with np.load(old/'common'/sid/f'{fi:04d}.npz') as d:
                source=np.flatnonzero(d['valid']);raw=d['raw_xyz'][source].copy()
            for h,w in m['projection_resolutions']:
                image,near,pr=axial(raw,h,w);starts=pr['offsets'][:-1]
                xx=raw[pr['members'],0]
                span=np.maximum.reduceat(xx,starts)-np.minimum.reduceat(xx,starts) if len(starts) else np.empty(0)
                np.savez_compressed(folder/f'{fi:04d}_{h}x{w}.npz',depth_forward_x_m=image,valid_mask=np.isfinite(image),
                    nearest_source_rows=source[near],pixels=pr['pixels'],offsets=pr['offsets'],
                    all_source_members=source[pr['members']],outside_source_rows=source[pr['outside']],axial_depth_span_m=span)
                axial_rows.append({'sid':sid,'fi':fi,'h':h,'w':w,'nearest_changed_vs_radial_sort':int(np.count_nonzero(near!=pr['nearest'])),
                                   'axial_multi_depth_pixels':int(np.count_nonzero(span>.17)),'input_valid_points':len(source),
                                   'outside_valid_points':len(pr['outside']),'outside_fraction':len(pr['outside'])/len(source)})
        print(sid,'all resolutions axial audit complete',flush=True)
    projection=read(e/'attempt_r2/PROJECTION_ROWS.json');projected={}
    for kind in ['sphere','angular_crop','pinhole']:
        for h,w in m['projection_resolutions']:
            a=[r for r in projection if r['kind']==kind and r['h']==h and r['w']==w]
            projected[f'{kind}_{h}x{w}']={'outside_valid_fraction':quant([r['outside']/r['input_points'] for r in a]),
                'empty_pixel_fraction':quant([r['empty_pixel_fraction'] for r in a]),
                'denominator':'per-frame valid source points (finite and frozen range-valid), not all raw rows; nearest-loss uses in-view members',
                'nearest_loss_fraction':quant([r['nearest_only_loss_fraction'] for r in a])}
    write(e/'REVIEW_ADDENDUM.json',{'paired_geometry':paired,'common_transition_keys':common,'projection_denominators':projected,
         'axial_rows':axial_rows,'axial_vs_radial_synthetic':'different-ray same-pixel counterexample PASS; not sensor evidence',
         'provenance':'AI read-only source review is separate from author run; not independent experimental rerun',
         'source_sha256':sha(Path(__file__))})
    print('Review addendum complete',len(common),'common transitions',len(axial_rows),'axial frames',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);main(p.parse_args().evidence.resolve())
