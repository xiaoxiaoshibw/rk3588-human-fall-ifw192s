import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from paths import OUT

r=json.loads((OUT/'process.json').read_text(encoding='utf8'));sid=r['sid']
m=json.loads((OUT/(sid+'_foreground.json')).read_text(encoding='utf8'))
p=np.memmap(OUT/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
for name,axes in [('side',(0,2)),('top',(0,1))]:
 fig,grid=plt.subplots(4,4,figsize=(16,12))
 for ax,i in zip(grid.flat,np.linspace(0,163,16,dtype=int)):
  row=r['rows'][i];f=m['frames'][i];q=p[f['offset']:f['offset']+f['count']][row['source_fg_indices']]
  ax.scatter(q[:,axes[0]],q[:,axes[1]],s=1,color='#748ea0')
  sk=row['skeleton'];nodes=sk['nodes']
  for a,b in sk.get('edges',[]):
   points=np.array([nodes[a]['xyz'],nodes[b]['xyz']]);ax.plot(points[:,axes[0]],points[:,axes[1]],color='#d76131',linewidth=2)
  valid=np.array([n['xyz'] for n in nodes.values() if n['valid']]).reshape(-1,3)
  ax.scatter(valid[:,axes[0]],valid[:,axes[1]],s=15,color='#20a592')
  ax.set_xlim(.1,2.7);ax.set_ylim((0,2.3) if axes[1]==1 else (0,1.9));ax.grid(alpha=.2)
  ax.set_title('f%d %.2fs / %d nodes / %s'%(i,row['t'],len(valid),row['state']['state']),fontsize=9)
 fig.suptitle('Real target + supported body regions / NOT calibrated anatomical joints')
 fig.tight_layout();fig.savefig(OUT/('PROCESS_'+name.upper()+'.png'),dpi=130);plt.close(fig)
print('contact sheets ready')
