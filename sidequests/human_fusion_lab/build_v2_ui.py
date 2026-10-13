"""Derive V2 directly from the existing V1 viewer; do not rewrite its replay flow."""
from pathlib import Path

base = Path(__file__).parent
html = (base / 'demo.html').read_text(encoding='utf-8')
html = html.replace('Demo V1 · 本地隔离研究 · CPU 回放', 'Demo V2 · 真实会话离线回放 · UNCALIBRATED')
html = html.replace('</style>', '''
.views{display:grid;grid-template-columns:1.5fr 1fr;gap:8px}.views canvas{height:28vh}.views .primary{grid-row:span 2}.views .primary canvas{height:60vh}.viewtitle{color:#a9c3dd;margin:4px}#annotation{padding:10px;background:#182739}#annotation input{width:64px}#cases{max-width:340px}#rows tr{cursor:pointer}#rows tr:hover{background:#243448}
</style>''')
html = html.replace('<canvas id="view" aria-label="三维点云、候选与 GT"></canvas>', '''<div class="views"><div class="primary"><div class="viewtitle">3D · 同帧 / 同候选</div><canvas id="view" aria-label="三维点云、候选与 GT"></canvas></div><div><div class="viewtitle">俯视 XY</div><canvas id="viewTop" aria-label="俯视点云"></canvas></div><div><div class="viewtitle">侧视 XZ</div><canvas id="viewSide" aria-label="侧视点云"></canvas></div></div>''')
html = html.replace('<button id="reset">', '<button id="prev">上一帧</button><button id="next">下一帧</button><button id="reset">')
html = html.replace('<button id="top">', '<button id="focus">聚焦人体 / 当前候选</button><button id="top">')
html = html.replace('<label><input id="cand"', '<label><input id="fg" type="checkbox">背景过滤后点集</label><label><input id="cls" type="checkbox" checked>分类着色</label><label><input id="proxy" type="checkbox">粗几何轴（非解剖关节）</label><label><input id="cand"')
html = html.replace('<h3>候选 / Track ID</h3>', '''<h3>定位真实案例</h3><select id="cases" aria-label="案例"><option value="">选择成功 / 漏检 / 家具误检 / 高风险帧</option></select><h3>同一候选模型对比</h3><small>分数列顺序：RF51原 / RF51研 / RF69 / XGB69。0.35弱候选、0.55强分类；模型切换后候选会随管线状态变化。</small>''')
html = html.replace('<th>分数 / 点数</th>', '<th>四模型分数 / 点数</th>')
html = html.replace('<p id="detail"></p>', '''<p id="detail"></p><div id="annotation"><b>2D / 3D 人工标注草稿</b><p>先暂停。开启圈点后，在任一视图拖出矩形；选择的是当前真实点的投影。3D框可进一步限制深度。草稿不自动成为可信GT。</p><label><input id="mark" type="checkbox">圈点模式</label><select id="label"><option>PERSON</option><option>FURNITURE</option><option>BACKGROUND</option><option>UNKNOWN</option></select><input id="actor" placeholder="P1"><p>3D框最小 XYZ <input id="xmin" value="-20"><input id="ymin" value="-20"><input id="zmin" value="-20"><br>最大 XYZ <input id="xmax" value="20"><input id="ymax" value="20"><input id="zmax" value="20"></p><button id="box">用3D框选点</button><button id="saveAnn">保存本帧草稿</button><button id="clearAnn">撤销本帧草稿</button><button id="exportAnn">下载标注</button><label>导入草稿<input id="importAnn" type="file" accept="application/json"></label><p id="annStatus">尚未圈点</p></div>''')
html = html.replace("const $=id=>document.getElementById(id),cv=$('view'),ctx=cv.getContext('2d');", "const $=id=>document.getElementById(id);let cv=$('view'),ctx=cv.getContext('2d'),viewMode='3d',timer=null,focus=[0,0];const annotations=new Map();let marked=[];")
html = html.replace("function project(x,y,z){", "function project(x,y,z){x-=focus[0];y-=focus[1];if(viewMode==='top')return [cv.width*.5+x*scale,cv.height*.6-y*scale];if(viewMode==='side')return [cv.width*.5+x*scale,cv.height*.8-z*scale];")
html = html.replace('function draw(){', "function draw(){for(const [id,mode] of [['view','3d'],['viewTop','top'],['viewSide','side']]){cv=$(id);ctx=cv.getContext('2d');viewMode=mode;drawView();}cv=$('view');ctx=cv.getContext('2d');viewMode='3d';}\nfunction drawView(){")
html = html.replace("if($('cand').checked)", "if($('fg').checked)for(const id of frame.foreground)dot(cloud[id*4],cloud[id*4+1],cloud[id*4+2],'#8fb8ff',2);\n if($('cand').checked)")
html = html.replace("const color=c.decision===", "const color=!$('cls').checked?'#b7d2ec':c.decision===")
html = html.replace("if($('gt').checked)", "for(const id of marked)dot(cloud[id*4],cloud[id*4+1],cloud[id*4+2],'#ffffff',3);\n if($('proxy').checked)for(const c of frame.candidates){if(c.decision==='NON_HUMAN')continue;const nodes=c.shape.nodes.filter(n=>n.position);ctx.strokeStyle='#ffae69';ctx.beginPath();nodes.forEach((n,j)=>{const p=project(...n.position);if(j)ctx.lineTo(...p);else ctx.moveTo(...p);text(...n.position,n.name,'#ffae69');});ctx.stroke();}\n if($('gt').checked)")
html = html.replace('point_count:c.n,', 'point_count:c.n,same_candidate_scores:c.scores,shape:c.shape,')
html = html.replace('GT_status:frame.gt_status,', 'GT_status:frame.gt_status,layer_observations:frame.layer_observations,')
html = html.replace("c.prob.toFixed(3)+' / '+c.n", "Object.values(c.scores).map(v=>v.toFixed(2)).join(' / ')+' · '+c.n")
html = html.replace("'\\nGT：'+v.gt_status", "'\\n标定：'+v.calibration+'（采用既有研究R/T，物理精度未验收）\\nGT：'+v.gt_status")
html = html.replace("+(pendingFallbackNote?", "+'\\n风险定位：'+v.events.join(', ')+(pendingFallbackNote?")
html = html.replace('cloud=new Float32Array(b);', "cloud=new Float32Array(b);marked=[];$('annStatus').textContent='尚未圈点；本帧草稿 '+(annotations.get(v.sid+':'+v.index)||[]).length+' 个';")
html = html.replace('setTimeout(update,100/', 'timer=setTimeout(update,100/')
html = html.replace("async function change(){epoch++;", "async function change(){clearTimeout(timer);epoch++;await json('/api/reset');focus=[0,0];scale=60;")
html = html.replace("$('play').onclick=()=>{playing=!playing;", "$('play').onclick=()=>{clearTimeout(timer);playing=!playing;")
html = html.replace("$('seek').onchange=()=>{epoch++;", "$('seek').oninput=()=>{clearTimeout(timer);epoch++;")
html = html.replace("['raw','cand','gt','track']", "['raw','fg','cls','proxy','cand','gt','track']")
html = html.replace("cv.onpointerdown=e=>{drag=", "cv.onpointerdown=e=>{if($('mark').checked)return;drag=")
html = html.replace("cv.onpointermove=e=>{if(!drag)", "cv.onpointermove=e=>{if($('mark').checked)return;if(!drag)")
html = html.replace('update();}).catch', "index=Math.max(0,Number(q.get('index'))||0);update();}).catch")
extra = r'''
function step(delta){clearTimeout(timer);epoch++;playing=false;$('play').textContent='播放';index=Math.max(0,Math.min(Number($('seek').max),index+delta));history.clear();if(!busy)update();}
$('focus').onclick=()=>{if(!frame)return;const c=frame.candidates.find(c=>c.id===selected)||frame.gt.find(g=>g.class_name==='PERSON')||frame.candidates.find(c=>c.decision==='CONFIRMED_HUMAN')||frame.candidates[0];if(c){focus=[c.x,c.y];scale=110;draw();}};
$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);
json('/api/cases').then(rows=>{for(const [i,c] of rows.entries()){const o=document.createElement('option');o.value=i;o.textContent=c.kind+' · '+c.activity+' · f'+c.index;$('cases').append(o);} $('cases').onchange=async()=>{if($('cases').value==='')return;const c=rows[Number($('cases').value)];$('session').value=c.sid;$('model').value=c.model;await change();index=c.index;epoch++;if(!busy)update();};});
function annotationStatus(){ $('annStatus').textContent='圈选 '+marked.length+' 个真实点；尚未保存';draw();}
for(const [id,mode] of [['view','3d'],['viewTop','top'],['viewSide','side']]){
 let start=null;const canvas=$(id);
 canvas.addEventListener('pointerdown',e=>{if(!$('mark').checked)return;clearTimeout(timer);playing=false;$('play').textContent='播放';const r=canvas.getBoundingClientRect();start=[(e.clientX-r.left)*devicePixelRatio,(e.clientY-r.top)*devicePixelRatio];canvas.setPointerCapture(e.pointerId);});
 canvas.addEventListener('pointerup',e=>{if(!start||!frame||!cloud)return;const r=canvas.getBoundingClientRect(),end=[(e.clientX-r.left)*devicePixelRatio,(e.clientY-r.top)*devicePixelRatio];cv=canvas;ctx=cv.getContext('2d');viewMode=mode;marked=[];for(let i=0;i<cloud.length;i+=4){const xyz=Array.from(cloud.subarray(i,i+3));if(!xyz.every(Number.isFinite)||Math.abs(xyz[0])>20||Math.abs(xyz[1])>20)continue;const p=project(...xyz);if(p.every((v,k)=>v>=Math.min(start[k],end[k])&&v<=Math.max(start[k],end[k])))marked.push(i/4);}start=null;annotationStatus();});
}
$('box').onclick=()=>{if(!cloud)return;const lo=['xmin','ymin','zmin'].map(id=>Number($(id).value)),hi=['xmax','ymax','zmax'].map(id=>Number($(id).value));if(!lo.concat(hi).every(Number.isFinite)||lo.some((v,k)=>v>hi[k]))return $('annStatus').textContent='3D框范围无效';marked=[];for(let i=0;i<cloud.length;i+=4)if([0,1,2].every(k=>Number.isFinite(cloud[i+k])&&cloud[i+k]>=lo[k]&&cloud[i+k]<=hi[k]))marked.push(i/4);annotationStatus();};
$('saveAnn').onclick=()=>{if(!frame||!marked.length)return $('annStatus').textContent='请先圈选真实点';if($('label').value==='PERSON'&&!$('actor').value.trim())return $('annStatus').textContent='请填人体编号，如P1';const key=frame.sid+':'+frame.index,arr=annotations.get(key)||[];arr.push({session_id:frame.sid,frame_index:frame.index,class_name:$('label').value,track_id:$('actor').value.trim(),source:'human',review_status:'DRAFT_UNREVIEWED',raw_point_indices:marked.slice(),index_domain:'raw_28B_row',coordinate_contract:frame.coordinate,session_sha256:frame.input_sha256,created_iso:new Date().toISOString()});annotations.set(key,arr);$('annStatus').textContent='已保存本帧草稿 '+arr.length+' 个；离开前请下载';};
$('clearAnn').onclick=()=>{if(!frame)return;annotations.delete(frame.sid+':'+frame.index);marked=[];$('annStatus').textContent='已撤销本帧草稿';draw();};
$('exportAnn').onclick=()=>{const b=new Blob([JSON.stringify({schema:'fusion_demo_v2/raw_row_draft/1',trusted_gt:false,annotations:Array.from(annotations.values()).flat()},null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='fusion_v2_annotations.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
$('importAnn').onchange=async e=>{try{const doc=JSON.parse(await e.target.files[0].text());if(doc.schema!=='fusion_demo_v2/raw_row_draft/1'||!Array.isArray(doc.annotations))throw Error('草稿格式不匹配');const staged=new Map();for(const a of doc.annotations){if(!/^cap_\d{8}_\d{6}$/.test(a.session_id)||!Number.isSafeInteger(a.frame_index)||a.frame_index<0||!Array.isArray(a.raw_point_indices)||!a.raw_point_indices.every(i=>Number.isSafeInteger(i)&&i>=0)||!['PERSON','FURNITURE','BACKGROUND','UNKNOWN'].includes(a.class_name)||a.index_domain!=='raw_28B_row'||a.source!=='human')throw Error('草稿字段不合法');if(a.session_id===frame?.sid&&(a.session_sha256?.meta!==frame.input_sha256.meta||a.session_sha256?.points!==frame.input_sha256.points))throw Error('会话SHA不匹配');const key=a.session_id+':'+a.frame_index,arr=staged.get(key)||[];arr.push(a);staged.set(key,arr);}for(const [k,v] of staged)annotations.set(k,v);$('annStatus').textContent='导入 '+doc.annotations.length+' 个草稿；GT资格仍未审核';}catch(err){$('annStatus').textContent=err.message;}};
window.addEventListener('beforeunload',e=>{if(annotations.size){e.preventDefault();e.returnValue='标注草稿尚在页内，请先下载';}});
'''
html = html.replace('</script>', extra + '\n</script>')
(base / 'demo_v2.html').write_text(html, encoding='utf-8')
print('Derived Demo V2 from V1')
