import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from prepare import OUT

sid='cap_20261013_094333'
m=json.loads((OUT/(sid+'_foreground.json')).read_text(encoding='utf8'))
p=np.memmap(OUT/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
for name,axes in [('side_xz',(0,2)),('front_yz',(1,2)),('top_xy',(0,1))]:
 fig,grid=plt.subplots(4,4,figsize=(16,12))
 for ax,i in zip(grid.flat,np.linspace(0,len(m['frames'])-1,16,dtype=int)):
  f=m['frames'][i];q=p[f['offset']:f['offset']+f['count']]
  q=q[(q[:,0]>-.2)&(q[:,0]<2.8)&(q[:,1]>-.2)&(q[:,1]<2.3)]
  ax.scatter(q[:,axes[0]],q[:,axes[1]],s=2,c=q[:,2],cmap='turbo',vmin=0,vmax=2)
  ax.set_xlim((-.2,2.8) if axes[0]==0 else (-.2,2.3));ax.set_ylim((-.2,2.3) if axes[1]==1 else (0,2.5))
  ax.set_title('f%d / %.2fs / %d pts'%(i,f['t'],len(q)),fontsize=10);ax.grid(alpha=.2)
 fig.suptitle('REAL POINTS / '+name+' / startup background with visually excluded target box')
 fig.tight_layout();fig.savefig(OUT/(sid+'_'+name+'_foreground.png'),dpi=130);plt.close(fig)
print('FG views written')
