"""Nine independent human-only/reference previews, each with boxes and supported skeleton."""
import json
from run import HERE, OUT

catalog = json.loads((OUT/'catalog.json').read_text(encoding='utf-8'))
cards = []
for s in catalog['sessions']:
    summary = json.loads((OUT/s['session_id']/'summary.json').read_text(encoding='utf-8'))
    fi = next((f['fi'] for f in summary['frames'] if f['reference_persons']), 0)
    row = json.loads((OUT/s['session_id']/f'{fi:04d}.json').read_text(encoding='utf-8'))
    if row['reference']:
        bodies = row['reference']
        mode = '已有人工人体点集 · 非自动提取'
    else:
        bodies = [c for c in row['full_3d'] if c['rf_xyz_prob'] >= .55]
        mode = '自动候选 · 纯度未验证' if bodies else '当前无人体候选'
    cards.append({'activity': s['activity'], 'sid': s['session_id'], 'fi': fi, 't': row['t_sec'], 'mode': mode,
                  'reference_status': s['reference_status'], 'objects': bodies})
template = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>九会话人体动作独立展示</title>
<style>body{background:#111b26;color:#dce8ef;font:14px system-ui;margin:24px}h1{font-size:24px}#grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}.card{background:#182737;padding:14px;border:1px solid #3e5468}h2{font-size:16px;margin:0 0 8px}canvas{width:100%;height:310px;touch-action:none}small{color:#a5b8c9}a{color:#70d9e3}.note{color:#f5cd79}</style>
<h1>九会话人体动作 · 独立展示</h1><p>每张图保留所选人体参照或自动候选，附当前点集框与点支撑骨架；拖动可旋转。</p><p class="note">人工参照与自动候选分别标明。动作标题为录制说明。骨架解剖身份、部位精度和自动纯人体精度尚未验证；S9没有有效人工参照。</p><p><a href="http://127.0.0.1:8941/">进入逐帧回放与评分工作台</a></p><div id="grid"></div>
<script>
const cards=__CARDS__;
for(const card of cards){const box=document.createElement('section');box.className='card';const title=document.createElement('h2');title.textContent=card.activity;box.append(title);const info=document.createElement('p');info.textContent=card.mode+' · f'+card.fi+' · '+card.t.toFixed(2)+' s';box.append(info);const canvas=document.createElement('canvas');box.append(canvas);const note=document.createElement('small');note.textContent=card.reference_status+' · '+card.objects.map(o=>o.point_count+' 点').join(' / ');box.append(note);document.getElementById('grid').append(box);
const ctx=canvas.getContext('2d');let yaw=-.45,pitch=.35,drag=null;const bodies=card.objects;
let low=[0,0,0],high=[1,1,2];if(bodies.length){low=[0,1,2].map(i=>Math.min(...bodies.map(o=>o.bbox.min[i])));high=[0,1,2].map(i=>Math.max(...bodies.map(o=>o.bbox.max[i])));}const center=low.map((v,i)=>(v+high[i])/2),scale=240/Math.max(1,...high.map((v,i)=>v-low[i]));
function project(p){let x=p[0]-center[0],y=p[1]-center[1],z=p[2]-center[2],a=Math.cos(yaw)*x-Math.sin(yaw)*y,b=Math.sin(yaw)*x+Math.cos(yaw)*y;return[canvas.width/2+a*scale,canvas.height/2+(Math.sin(pitch)*b-Math.cos(pitch)*z)*scale];}
function line(a,b,c,w){a=project(a);b=project(b);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.strokeStyle=c;ctx.lineWidth=w;ctx.stroke();}
function draw(){canvas.width=canvas.clientWidth;canvas.height=310;ctx.clearRect(0,0,canvas.width,310);if(!bodies.length){ctx.fillStyle='#9cadbc';ctx.fillText('空场：无人体点集',30,155);}for(const o of bodies){ctx.fillStyle=card.mode.startsWith('已有')?'#9eaaff':'#55d3df';for(const p of o.points){const q=project(p);ctx.fillRect(...q,2,2);}const a=o.bbox.min,b=o.bbox.max,v=[[a[0],a[1],a[2]],[b[0],a[1],a[2]],[b[0],b[1],a[2]],[a[0],b[1],a[2]],[a[0],a[1],b[2]],[b[0],a[1],b[2]],[b[0],b[1],b[2]],[a[0],b[1],b[2]]];for(const[i,j]of[[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]])line(v[i],v[j],'#ffc56b',1);for(const[a,b]of o.skeleton.edges)line(o.skeleton.nodes[a].xyz,o.skeleton.nodes[b].xyz,'#ff84b1',2);for(const n of Object.values(o.skeleton.nodes))if(n.valid){const q=project(n.xyz);ctx.fillStyle='#ffb8d0';ctx.beginPath();ctx.arc(...q,3,0,2*Math.PI);ctx.fill();}}}
canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};canvas.onpointermove=e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.01;pitch=Math.max(-.1,Math.min(Math.PI/2,pitch+(e.clientY-drag[1])*.01));drag=[e.clientX,e.clientY];draw();};canvas.onpointerup=()=>drag=null;new ResizeObserver(draw).observe(canvas);draw();}
</script></html>'''
(OUT/'gallery.html').write_text(template.replace('__CARDS__', json.dumps(cards, ensure_ascii=False, separators=(',', ':'))), encoding='utf-8')
print('Nine independent body previews written')
