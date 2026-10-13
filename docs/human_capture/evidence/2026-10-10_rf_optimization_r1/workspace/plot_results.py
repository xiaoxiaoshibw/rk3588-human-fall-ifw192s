import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
with (HERE/'run01/results.json').open(encoding='utf8') as f: data=json.load(f)
fig,axes=plt.subplots(2,3,figsize=(12,7),sharex=True,sharey=True,layout='constrained')
routes=['rf_v2','rf_v3','gbdt']
for i,ax in enumerate(axes.ravel()):
    for route,color in zip(routes,['#0072B2','#D55E00','#009E73']):
        fold=data['routes'][route]['folds'][i]
        curve=fold['pr_curve']
        ax.step(curve['recall'],curve['precision'],where='post',color=color,label=route)
        m=fold['metrics']
        ax.scatter([m['recall']],[m['precision']],color=color,s=22)
    ax.axhline(.95,color='.6',ls='--',lw=.8)
    ax.set(xlim=(0,1.02),ylim=(0,1.02),xlabel='Recall (weak labels)',ylabel='Precision (weak labels)')
    ax.set_title(fold['holdout'].replace('cap_20261009_','') +
                 (' / positives only' if fold['metrics']['tn']+fold['metrics']['fp']==0 else ''))
    ax.grid(alpha=.15)
axes[0,0].legend(loc='lower left',fontsize=9)
fig.suptitle('Session-held-out PR curves | same room, static, unverified candidate labels\nDots: thresholds selected only on inner folds; not eligible for production',fontsize=12)
for ext in ['png','svg']:
    path=HERE/'run01'/('pr_session_curves.'+ext)
    if path.exists(): raise FileExistsError(path)
    fig.savefig(path,dpi=170)
plt.close(fig)
