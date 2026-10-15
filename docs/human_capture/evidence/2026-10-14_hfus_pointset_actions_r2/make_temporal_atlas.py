import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

H=Path('D:/Code/ldiar/sidequests/human_fusion_lab_next/pointset/r01');sys.path.insert(0,str(H))
from research_actions import E, RESULT, OUT, load, read, frame_points
folder=E/'temporal_atlas';folder.mkdir()
diag=read(E/'DIAGNOSIS.json');cat=read(OUT/'catalog.json');prior=Path(read(OUT/'RUN_MANIFEST.json')['config']['background_experiment'])
for rec in cat['sessions'][:-1]:
    sid=rec['session_id'];meta,raw,_=load(sid);reg=read(prior/(sid+'_registration.json'))
    cases=[c for c in diag['cases'] if c['sid']==sid and c['roles'][0]!='AXIS_OR_NEIGHBOR']
    fig=plt.figure(figsize=(12,len(cases)*2.5))
    for ri,c in enumerate(cases):
        fi=c['fi'];_,p=frame_points(raw,meta['frames'][fi],reg)
        d=read(RESULT/sid/f'{fi:04d}.json')
        with np.load(RESULT/sid/f'{fi:04d}_sources.npz') as sets:
            layers=[(sets['unselected'],'#c49fcb',.6),(np.array(d['near_removed_source_indices'],dtype=int),'#e6816d',.6),(sets['target'],'#079cae',1.)]
        for col,dims in enumerate([(0,1),(0,2),None]):
            ax=fig.add_subplot(len(cases),3,ri*3+col+1,projection='3d' if dims is None else None)
            for ids,color,size in layers:
                q=p[ids]
                if dims is None:ax.scatter(*q.T,s=size,c=color);ax.set(xlim=(.3,2.8),ylim=(-.4,2.2),zlim=(-.25,2.2));ax.view_init(elev=25,azim=135)
                else:ax.scatter(q[:,dims[0]],q[:,dims[1]],s=size,c=color);ax.set(xlim=(.3,2.8),ylim=(-.4,2.2),xlabel='XYZ'[dims[0]]+' m',ylabel='XYZ'[dims[1]]+' m')
            ax.set_title(f"f{fi} / {','.join(c['roles'])}",fontsize=9)
    fig.suptitle(sid+' · target cyan / unselected purple / nearby removed red · identity UNKNOWN',fontsize=12)
    fig.tight_layout();fig.savefig(folder/(sid+'.png'),dpi=110);plt.close(fig)
    print(sid,'cases',len(cases),flush=True)
