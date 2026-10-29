"""Measured-only evidence plots; absent measurements break every curve."""
import numpy as np
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import EV, SK, save, jsonlines
from experiment import source, roi, WINDOWS

groups=['RAW_OLD','FG_OLD','RAW_NEW','FG_NEW']
suffix=sys.argv[1] if len(sys.argv)>1 else ''
cases={}
fig,axes=plt.subplots(4,2,figsize=(15,12),constrained_layout=True)
src=source()
try:
    for row,g in enumerate(groups):
        records=jsonlines(EV/(g+'_FRAMES.jsonl'))
        for col,k in enumerate(('CHEST','OUTER_A')):
            values=np.asarray([r['nodes'][k]['xyz'] if r['nodes'][k]['valid'] else [np.nan]*3 for r in records])
            for j in range(3):axes[row,col].plot(np.arange(386),values[:,j],label='RAW '+'XYZ'[j]+' measured',lw=.8)
            axes[row,col].axvspan(183,334,color='green',alpha=.1)
            axes[row,col].set(title=g+' '+k+' / gaps = missing; no auxiliary positions',xlabel='0-based source frame',ylabel='RAW coordinate (m)',xlim=(0,385))
            axes[row,col].axvspan(0,100,color='gray',alpha=.1)
            axes[row,col].legend(fontsize=7);axes[row,col].grid(alpha=.2)
        maxima={}
        for window,(lo,hi) in {'full':[0,386],'hold':[183,334]}.items():
            steps=[]
            for a,b in zip(records[lo:hi],records[lo+1:hi]):
                for k in SK.SLOTS:
                    na,nb=a['nodes'][k],b['nodes'][k]
                    if na['valid'] and nb['valid']:steps.append(dict(from_frame=a['fi'],to_frame=b['fi'],node=k,mm=float(np.linalg.norm(np.asarray(nb['xyz'])-na['xyz'])*1000)))
            maxima[window]=max(steps,key=lambda r:r['mm']) if steps else None
        fis=sorted({188,189}|{r[key] for r in maxima.values() if r for key in ('from_frame','to_frame')})
        cases[g]=dict(maxima=maxima,frames=fis,f188_189={k:[records[fi]['nodes'][k] for fi in (188,189)] for k in SK.SLOTS})
        fg,axs=plt.subplots(1,len(fis),figsize=(4*len(fis),5),constrained_layout=True,squeeze=False)
        for col,fi in enumerate(fis):
            ax=axs[0,col];p,rows=roi(src.frame(fi));ax.scatter(p[:,0],p[:,2],s=.5,c='#b9b9b9',label='Raw ROI context')
            current=records[fi];valid=[];missing=[];byrow={int(r):j for j,r in enumerate(rows)}
            for j,k in enumerate(SK.SLOTS):
                n=current['nodes'][k];color=plt.get_cmap('tab20')(j)
                if n['valid']:
                    ids=[byrow[r] for r in n['support_rows']]
                    ax.scatter(p[ids,0],p[ids,2],s=2,color=color,alpha=.45)
                    ax.scatter(n['xyz'][0],n['xyz'][2],s=30,color=color,marker='o',edgecolor='black',linewidth=.3)
                    ax.annotate(k,(n['xyz'][0],n['xyz'][2]),fontsize=5)
                    valid.append(k)
                else:missing.append(k)
            ax.set(title=g+' f'+str(fi)+' / valid '+str(len(valid)),xlabel='RAW X (m)',ylabel='RAW Z (m)',xlim=(.7,2.45),ylim=(-.45,1.9));ax.set_aspect('equal');ax.grid(alpha=.2)
            ax.text(.02,.02,'Missing: '+', '.join(missing),transform=ax.transAxes,fontsize=5,wrap=True)
        fg.suptitle('Point supported regional measurements and their raw source support; no prediction or display fill')
        with (EV/(g+'_CASES'+suffix+'.png')).open('xb') as f:fg.savefig(f,dpi=150)
        plt.close(fg)
    with (EV/('MEASURED_TIME_SERIES'+suffix+'.png')).open('xb') as f:fig.savefig(f,dpi=150)
    plt.close(fig)
    save('JUMP_CASES'+suffix+'.json',cases)
finally:src.close()
