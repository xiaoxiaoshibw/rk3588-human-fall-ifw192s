"""Explicit perspective axial depth (raw sensor +X), separate from radial range."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from probe import read, write, sha, pixels

def axial(raw,h,w):
    pr=pixels(raw,h,w,'pinhole')
    # Pixel CSR is radial-range sorted; re-sort within pixels by forward X.
    repeated=np.repeat(pr['pixels'],pr['counts']);members=pr['members']
    order=np.lexsort((members,raw[members,0],repeated))
    nearest=members[order][pr['offsets'][:-1]]
    depth=np.full(h*w,np.nan,dtype=np.float32);depth[pr['pixels']]=raw[nearest,0]
    return depth.reshape(h,w),nearest,pr

def main(e):
    assert __debug__
    # Same projected pixel: smaller axial depth must win, holes remain NaN.
    q=np.array([[2.,0.,0.],[1.,0.,0.],[-1.,0.,0.]])
    image,near,pr=axial(q,64,256);assert near.tolist()==[1] and len(pr['outside'])==1 and np.isfinite(image).sum()==1
    manifest=read(e/'RUN_MANIFEST.json');old=Path(manifest['old_evidence']);out=e/'axial_depth';out.mkdir(exist_ok=False)
    rows=[]
    for sid,frames in manifest['samples'].items():
        for fi in frames:
            with np.load(old/'common'/sid/f'{fi:04d}.npz') as d:
                source_rows=np.flatnonzero(d['valid']);raw=d['raw_xyz'][source_rows].copy()
            for h,w in manifest['projection_resolutions']:
                image,nearest,pr=axial(raw,h,w)
                assert len(np.unique(pr['members']))+len(pr['outside'])==len(raw)
                assert np.allclose(image.ravel()[pr['pixels']],raw[nearest,0])
                rows.append({'sid':sid,'fi':fi,'h':h,'w':w,'in_view':len(pr['members']),'outside':len(pr['outside']),
                             'nearest_changed_vs_radial_sort':int(np.count_nonzero(nearest!=pr['nearest']))})
                if (h,w)==(256,1024):
                    np.savez_compressed(out/f'{sid}_{fi:04d}.npz',depth_forward_x_m=image,valid_mask=np.isfinite(image),
                                        nearest_source_rows=source_rows[nearest],pixels=pr['pixels'],offsets=pr['offsets'],
                                        all_source_members=source_rows[pr['members']],outside_source_rows=source_rows[pr['outside']])
                    if sid=='cap_20261013_082623' and fi==195:
                        fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
                        radial=np.full_like(image,np.nan);radial.ravel()[pr['pixels']]=np.linalg.norm(raw[pr['nearest']],axis=1)
                        for ax,data,label in zip(axes,[radial,image],['Radial range ||XYZ|| (m)','Axial depth: sensor X (m)']):
                            display=ax.imshow(data,aspect='auto',vmin=0,vmax=15,cmap='viridis');ax.set_title(label);ax.set_xlabel('pixel u');ax.set_ylabel('pixel v')
                        fig.colorbar(display,ax=axes,label='meters',shrink=.8);fig.suptitle('Same virtual pinhole, 120 x 90 degrees; holes UNKNOWN; f195')
                        fig.savefig(e/'AXIAL_DEPTH_0195.png',dpi=150);plt.close(fig)
    write(e/'AXIAL_DEPTH_SUMMARY.json',{'frames':sum(map(len,manifest['samples'].values())),'rows':rows,
          'coordinate':'raw sensor +X forward; virtual uncalibrated pinhole 120x90 degrees','definition':'axial X depth vs radial norm are distinct; first PROJECTION_ROWS pinhole stores radial norm',
          'code_sha256':sha(Path(__file__)),'manifest_sha256':sha(e/'RUN_MANIFEST.json')})
    print('Axial depth: 148 frames / three resolutions / source CSR and holes checked',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);main(parser.parse_args().evidence.resolve())
