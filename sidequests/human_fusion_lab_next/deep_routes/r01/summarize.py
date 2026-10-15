"""Diagnostic summaries/figures; source-members, not semantic accuracy."""
import argparse
from pathlib import Path
import sys
import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from probe import read, write, sha, Shadow, pixels, projection_stats, ROOT

def quant(values):
    a=[v for v in values if v is not None]
    return None if not a else dict(zip(['P50','P95','max'],map(float,[np.quantile(a,.5),np.quantile(a,.95),max(a)])))

def main(e):
    attempt=e/'attempt_r2';manifest=read(attempt/'RUN_MANIFEST.json');old=Path(manifest['old_evidence'])
    rows=read(attempt/'PILOT_ROWS.json');projection=read(attempt/'PROJECTION_ROWS.json')
    names=list(manifest['candidates']);result={};overlap=[]
    for sid,frames in manifest['samples'].items():
        for fi in frames:
            folder=attempt/'pilot'/sid
            with np.load(folder/f'{fi:04d}_dbscan_members.npz') as d:baseline=d['selected'].copy()
            for name in names:
                with np.load(folder/f'{fi:04d}_{name}_members.npz') as d:ids=d['selected'].copy()
                inter=len(np.intersect1d(ids,baseline));overlap.append({'sid':sid,'fi':fi,'route':name,
                    'baseline_removed':len(baseline)-inter,'baseline_added':len(ids)-inter,
                    'baseline_retained_fraction':inter/len(baseline) if len(baseline) else None,
                    'meaning':'agreement with diagnostic control, NOT human recall/precision'})
    for name in names:
        a=[r for r in rows if r['route']==name];b=[r for r in overlap if r['route']==name]
        result[name]={'frames':len(a),'selected_total':sum(r['selected_count'] for r in a),'missing':sum(r['selected_count']==0 for r in a),
                      'axis_missing':sum(r['axis_missing'] for r in a),'slot_jump_m':quant([r['slot_jump_m'] for r in a]),
                      'slot_comparable_transitions':sum(r['slot_jump_m'] is not None for r in a),
                      'conditional_stage_ms':quant([r['ms'] for r in a]),'selected_count':quant([r['selected_count'] for r in a]),
                      'control_removed_total':sum(r['baseline_removed'] for r in b),'control_added_total':sum(r['baseline_added'] for r in b),
                      'by_session':{s:{'frames':sum(r['sid']==s for r in a),'axis_missing':sum(r['axis_missing'] for r in a if r['sid']==s),
                                       'selected_total':sum(r['selected_count'] for r in a if r['sid']==s)} for s in manifest['samples']}}
    projections={}
    for kind in ['sphere','angular_crop','pinhole']:
        for h,w in manifest['projection_resolutions']:
            a=[r for r in projection if r['kind']==kind and r['h']==h and r['w']==w]
            projections[f'{kind}_{h}x{w}']={key:quant([r[key] for r in a]) for key in ['nearest_only_loss_fraction','empty_pixel_fraction','outside','multi_depth_pixels','max_depth_spread_m']}
    # Robustness of a candidate classifier is not evidence for human semantics.
    torch.set_num_threads(1);net=Shadow();weight=ROOT/'sidequests/human_fusion_lab/models/pointnet_shadow.pt'
    net.load_state_dict(torch.load(weight,map_location='cpu',weights_only=True));net.eval();rotation=[]
    for sid,frames in manifest['samples'].items():
        for fi in frames:
            with np.load(attempt/'pilot'/sid/f'{fi:04d}_dbscan_members.npz') as d:ids=d['selected'].copy()
            if not len(ids):continue
            with np.load(old/'common'/sid/f'{fi:04d}.npz') as d:q=d['xyz'][ids].copy()
            q=q[np.floor(np.arange(256)*len(q)/256).astype(int)].astype(np.float32);q-=q.mean(axis=0)
            probabilities=[]
            for angle in [0.,np.pi/2,np.pi]:
                matrix=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]],dtype=np.float32)
                tensor=(q@matrix.T).T[None].copy()
                with torch.inference_mode():probabilities.append(float(net(torch.from_numpy(tensor)).sigmoid().item()))
            rotation.append({'sid':sid,'fi':fi,'yaw0_90_180_probabilities':probabilities,'spread':max(probabilities)-min(probabilities),
                             'role':'synthetic rigid input transformation of same source IDs; NOT new sensor observations/GT'})
    write(e/'COMPARE_SUMMARY.json',{'routes':result,'projection':projections,'classification_yaw_probability_spread':quant([r['spread'] for r in rotation]),
                                  'semantic_metrics':'BLOCKED_NO_POINT_INSTANCE_JOINT_GT','promotion':'NO_WINNER_FROM_PILOT',
                                  'timing_scope':'incremental shared-stage diagnostic, not complete pipelines; projection/IO/classifier parity excluded; do not rank complete latency',
                                  'data_scope':'148 development frames; reset windows; not full-session/unseen evaluation'})
    write(e/'MEMBER_DIFFERENCES.json',overlap);write(e/'CLASSIFIER_ROTATION.json',rotation)
    sid='cap_20261013_082623';fi=195
    with np.load(old/'common'/sid/f'{fi:04d}.npz') as d:points=d['xyz'].copy();raw=d['raw_xyz'][d['valid']].copy()
    fig,axes=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
    for ax,kind in zip(axes,['sphere','angular_crop','pinhole']):
        pr=pixels(raw,256,1024,kind);image=np.full(256*1024,np.nan);image[pr['pixels']]=np.linalg.norm(raw[pr['nearest']],axis=1)
        mesh=ax.imshow(image.reshape(256,1024),vmin=0,vmax=15,cmap='viridis',aspect='auto');s=projection_stats(raw,pr,256,1024)
        ax.set_title(f'{kind}\nnearest-only discards {s["nearest_only_loss_fraction"]:.1%} in-view points');ax.set_xlabel('pixel u');ax.set_ylabel('pixel v')
    fig.colorbar(mesh,ax=axes,label='Measured nearest range (m)',shrink=.7)
    fig.suptitle('Sensor XYZ projection: 082623 / f195; holes are UNKNOWN, no completion')
    fig.savefig(e/'PROJECTION_0195.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,4,figsize=(16,8),layout='constrained')
    with np.load(attempt/'pilot'/sid/f'{fi:04d}_dbscan_members.npz') as d:fg=d['foreground'].copy()
    for column,name in enumerate(names):
        with np.load(attempt/'pilot'/sid/f'{fi:04d}_{name}_members.npz') as d:ids=d['selected'].copy()
        for row,(xx,yy) in enumerate([(0,1),(0,2)]):
            ax=axes[row,column];ax.scatter(points[fg,xx],points[fg,yy],s=.3,c='#bbb',rasterized=True)
            ax.scatter(points[ids,xx],points[ids,yy],s=1,c='#0571b0',rasterized=True);ax.set_aspect('equal')
            ax.set_xlim(0,3.5);ax.set_ylim((-.5,3.5) if row==0 else (-.5,2.5));ax.set_title(f'{name}: selected {len(ids)}')
            ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)' if row==0 else 'Z (m)')
    fig.suptitle('Same frozen B input; blue=current selected source rows, gray=foreground\nDisplay crop only; no semantic GT; no point coordinate changes')
    fig.savefig(e/'ROUTES_0195.png',dpi=150);plt.close(fig)
    write(e/'SUMMARY_BINDING.json',{'source_sha256':sha(Path(__file__)),'probe_sha256':sha(Path(__file__).with_name('probe.py')),
          'input_sha256':{str(p.relative_to(e)):sha(p) for p in [attempt/'RUN_MANIFEST.json',attempt/'PREFLIGHT.json',attempt/'PILOT_ROWS.json',attempt/'PROJECTION_ROWS.json']},
          'output_sha256':{p.name:sha(p) for p in e.glob('*.png')}})
    print('Summary / same-member rotation probe / two figures complete',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);main(p.parse_args().evidence.resolve())
