import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from paths import OUT,OLD

sid='cap_20261013_094333'
old=json.loads((OLD/'process_v2.json').read_text(encoding='utf8'))
new=json.loads((OUT/'process.json').read_text(encoding='utf8'))
sources=[]
for directory,process in [(OLD,old),(OUT,new)]:
    m=json.loads((directory/(sid+'_foreground.json')).read_text(encoding='utf8'))
    p=np.memmap(directory/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
    sources.append((m,p,process))
def draw(ax,index,frame,axes):
    m,p,r=sources[index];f=m['frames'][frame];row=r['rows'][frame]
    q=p[f['offset']:f['offset']+f['count'],:3][row['source_fg_indices']]
    ax.scatter(q[:,axes[0]],q[:,axes[1]],s=1,color='#7893a6')
    sk=row['skeleton'];nodes=sk['nodes'];edges=sk.get('display_edges',sk.get('edges',[]))
    for a,b in edges:
        a=nodes[a].get('display_xyz',nodes[a]['xyz']);b=nodes[b].get('display_xyz',nodes[b]['xyz'])
        if a is not None and b is not None:ax.plot([a[axes[0]],b[axes[0]]],[a[axes[1]],b[axes[1]]],color='#c45f2e',linewidth=2)
    ax.set_xlim(.3,2.7);ax.set_ylim((0,2.4) if axes[1]==1 else (0,1.9));ax.grid(alpha=.2)
    ax.set_title(('OLD' if index==0 else 'NEW')+' f%d / %d pts / %d nodes'%(frame,len(q),sum(n['valid'] for n in nodes.values())),fontsize=10)
fig,grid=plt.subplots(2,2,figsize=(12,8))
for ax,index,axes in [(grid[0,0],0,(0,2)),(grid[0,1],1,(0,2)),(grid[1,0],0,(0,1)),(grid[1,1],1,(0,1))]:draw(ax,index,10,axes)
fig.tight_layout();fig.savefig(OUT/'F10_BEFORE_AFTER.png',dpi=150);plt.close(fig)
fig,grid=plt.subplots(2,6,figsize=(18,7))
for i in range(2):
    for ax,frame in zip(grid[i],[40,47,71,108,109,118]):draw(ax,i,frame,(0,2))
fig.tight_layout();fig.savefig(OUT/'TRANSITION_BEFORE_AFTER.png',dpi=140);plt.close(fig)
report={}
for label,process in [('old',old),('new',new)]:
    rows=process['rows'];stats={}
    for key in process['skeleton_slots']:
        measured=[];display=[];switches=0
        for a,b in zip(rows,rows[1:]):
            x=a['skeleton']['nodes'][key];y=b['skeleton']['nodes'][key]
            switches+=x['valid']!=y['valid']
            if x['valid'] and y['valid']:measured.append(float(np.linalg.norm(np.array(x['xyz'])-y['xyz'])))
            u=x.get('display_xyz',x['xyz']);v=y.get('display_xyz',y['xyz'])
            if u is not None and v is not None:display.append(float(np.linalg.norm(np.array(u)-v)))
        stats[key]={'valid':sum(r['skeleton']['nodes'][key]['valid'] for r in rows),'toggles':int(switches),
                    'raw_jump_p95_m':float(np.quantile(measured,.95)) if measured else None,
                    'display_jump_p95_m':float(np.quantile(display,.95)) if display else None}
    turns=[]
    for a,b in zip(rows,rows[1:]):
        x=a['skeleton'].get('axis');y=b['skeleton'].get('axis')
        if x is not None and y is not None:turns.append(float(np.degrees(np.arccos(np.clip(np.dot(x,y),-1,1)))))
    report[label]={'nodes':stats,'axis_max_step_deg':max(turns),'events':process['events'],
                   'observed':sum(r['observed'] for r in rows),'no_nodes_frames':[r['frame'] for r in rows if not any(n['valid'] for n in r['skeleton']['nodes'].values())]}
with (OUT/'COMPARISON.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
print(json.dumps({k:{'axis_max':v['axis_max_step_deg'],'observed':v['observed'],'endA':v['nodes']['END_A'],'zero':v['no_nodes_frames']} for k,v in report.items()}))
