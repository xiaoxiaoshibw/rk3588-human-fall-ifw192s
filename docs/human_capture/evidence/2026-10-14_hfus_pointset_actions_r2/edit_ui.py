from pathlib import Path

here = Path('D:/Code/ldiar/sidequests/human_fusion_lab_next/pointset/r01')
html = (here/'index.html').read_text(encoding='utf8')
html = html.replace('<div id="controls">', '<div id="researchControls"><select id="variant" aria-label="实验方案"><option value="baseline">R1旧基线 · 当前默认</option><option value="point12">实验：局部前景12cm</option><option value="point20">实验：局部前景20cm</option><option value="component20">实验：20cm整碎片</option><option value="low20">实验：20cm含贴地</option><option value="axis">实验：有界历史体轴方向</option></select><label><input id="diagnose" type="checkbox">五层同帧对照 · 原始/删除/前景/旧目标/未选</label><select id="case" aria-label="诊断帧"><option value="">诊断帧导航</option></select><span id="version">R2 · 默认保留R1 · 新方案未晋级</span></div><div id="controls">')
html = html.replace('<div id="metrics"></div>', '<div id="metrics"></div><section id="diagnosticPanel" hidden><p id="layerStatus"></p><div id="layers"></div><p id="sourceHover">在小图点击可查看当帧显示点的源索引；拖动同步旋转。</p><a id="sourceDownload" href="#">下载五层全量源索引（NPZ）</a><details><summary>局部未选碎片与风险（身份UNKNOWN）</summary><pre id="fragmentDetails"></pre></details></section>')
html = html.replace('[hidden]{', '#researchControls{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:12px;align-items:center}#layers{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}#layers canvas{height:220px}#layers h3{font-size:13px;min-height:38px}#fragmentDetails{white-space:pre-wrap;max-height:240px;overflow:auto}#sourceHover{min-height:22px}@media(max-width:850px){#layers{grid-template-columns:repeat(2,minmax(0,1fr))}}[hidden]{')
(here/'index.html').write_text(html, encoding='utf8')

js = (here/'app.js').read_text(encoding='utf8')
js = js.replace('let reviewedParts=new Map();', 'let reviewedParts=new Map(), diagnostic=null, experiment=null, baselineRecord=null;')
js = js.replace('function draw(){canvas.width', 'function draw(){drawLayers();canvas.width')
js = js.replace("ctx.fillStyle=selected.has(id)?'#ffdf67':", "ctx.fillStyle=experiment?.added_members.some(m=>m.source_index===id)?'#ff9b43':selected.has(id)?'#ffdf67':")
js = js.replace("for(const t of texts){", "if(baselineRecord&&$('dataset').value==='actions'){const old=baselineRecord.body_3d[0];texts.push(`旧目标 ${old?.point_count??0} / 当前 ${obj?.point_count??0} 点`,`方案 ${$('variant').selectedOptions[0].textContent}`);if(experiment){const s=experiment.stats;texts.push(`成员 +${s.added_count} / -${s.deleted_count}`,`粗节点 ${s.valid_nodes}/13 · 人体精度/家具污染率 UNKNOWN`,`方向 ${s.direction_source} · 非预测关节`);}}for(const t of texts){")
start = js.index('async function loadFrame('); end = js.index('\nfunction stop()', start)
js = js[:start]+'''async function loadFrame(value){
const token=++request;fi=Math.max(0,Math.min(current.frame_count-1,value));if(current.available_frames)fi=current.available_frames.reduce((a,b)=>Math.abs(b-fi)<Math.abs(a-fi)?b:a);
$('time').value=fi;record=null;obj=null;diagnostic=null;experiment=null;baselineRecord=null;reviewedParts.clear();draw();
try{const binding=`sid=${current.session_id}&fi=${fi}`,isActions=$('dataset').value==='actions',variant=$('variant').value;
const [data,labels,diag,exp]=await Promise.all([api('/api/frame?'+binding),api('/api/parts?'+binding),isActions&&$('diagnose').checked?api('/api/diagnostic?'+binding):null,isActions&&variant!=='baseline'?api('/api/experiment?'+binding+'&variant='+variant):null]);
if(token!==request)return;baselineRecord=data;diagnostic=diag;experiment=exp;record=exp?{...data,body_3d:exp.body_3d,posture:exp.posture}:data;
for(const r of labels.records)for(const id of r.source_indices)reviewedParts.set(id,r.part_class);
$('sourceDownload').href='/api/source-members?'+binding+'&dataset=actions';updateObjects();if(labels.rejected?.length)$('message').textContent=`${labels.rejected.length} 条标注绑定无效，未作为人工审核显示。`;
}catch(e){if(token!==request)return;record=null;obj=null;diagnostic=null;experiment=null;baselineRecord=null;reviewedParts.clear();draw();$('status').textContent=e.message;stop();}}
''' + js[end:]
js = js.replace("async function initialize(){try{stop();request++;record=null;obj=null;draw();catalog=await api('/api/catalog');actions=await api('/api/actions');", "async function initialize(){try{stop();const setup=++request;record=null;obj=null;diagnostic=null;experiment=null;baselineRecord=null;draw();const nextCatalog=await api('/api/catalog');if(setup!==request)return;const nextActions=await api('/api/actions');if(setup!==request)return;catalog=nextCatalog;actions=nextActions;")
js = js.replace("$('parts').hidden=isActions;", "$('parts').hidden=isActions;$('researchControls').hidden=!isActions;")
js = js.replace("$('dataset').onchange=initialize;", """
const layerNames={raw:'原始有效点',background_removed:'背景删除点',foreground:'完整前景成员',target:'R1旧目标',unselected:'未选碎片/噪声'};
const layerColors={raw:'#8294a6',background_removed:'#e37c69',foreground:'#8daa70',target:'#12cadd',unselected:'#bb83ca'};
for(const key of Object.keys(layerNames)){const box=document.createElement('div'),title=document.createElement('h3'),c=document.createElement('canvas');title.id='layerTitle_'+key;c.id='layer_'+key;c.setAttribute('aria-label',layerNames[key]);box.append(title,c);$('layers').append(box);
c.onpointerdown=canvas.onpointerdown;c.onpointermove=canvas.onpointermove;c.onwheel=canvas.onwheel;c.onpointerup=e=>{drag=null;if(moved||!diagnostic)return;const rect=c.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;const layer=diagnostic.layers[key];let best=-1,d=10;for(let i=0;i<layer.points.length;i++){const q=layerProject(layer.points[i],c),gap=Math.hypot(q[0]-x,q[1]-y);if(gap<d){best=i;d=gap;}}if(best>=0)$('sourceHover').textContent=`AI_INFERRED检查 · ${diagnostic.sid} / f${diagnostic.fi} / source ${layer.display_source_indices[best]} · ${layerNames[key]} · 身份UNKNOWN`;};}
function layerProject(p,c){const q=project(p),ratio=Math.min(c.width/canvas.width,c.height/canvas.height);return [c.width/2+(q[0]-canvas.width/2)*ratio,c.height/2+(q[1]-canvas.height/2)*ratio];}
function drawLayers(){const show=$('dataset').value==='actions'&&$('diagnose').checked;$('diagnosticPanel').hidden=!show;
for(const key of Object.keys(layerNames)){const c=$('layer_'+key);if(!c)continue;c.width=c.clientWidth||240;c.height=c.clientHeight||220;const cx=c.getContext('2d');cx.clearRect(0,0,c.width,c.height);const layer=diagnostic?.layers[key];$('layerTitle_'+key).textContent=layerNames[key]+(layer?` · ${layer.count} 点 / 显示 ${layer.display_count}${layer.sampled?'（采样）':''}`:' · 等待同帧数据');if(!layer)continue;cx.fillStyle=layerColors[key];for(const p of layer.points){const q=layerProject(p,c);cx.fillRect(q[0],q[1],1.5,1.5);}}
if(diagnostic){$('layerStatus').textContent=`${diagnostic.sid} / f${diagnostic.fi} · 五层使用同一源帧和坐标 · 原始层为有效量程点；高度范围外另存outside_domain · 五层是R1处理路径，主图展示所选方案；人体精度/污染率UNKNOWN`;$('fragmentDetails').textContent=JSON.stringify({risks:diagnostic.risk_status,axis:diagnostic.body_axis_ambiguity,near_removed:diagnostic.near_removed_source_indices,fragments:diagnostic.fragments.map(f=>({...f,source_indices:f.source_indices.slice(0,12)})),experiment:experiment?.stats,added_members:experiment?.added_members,direction:obj?.skeleton.direction},null,2);}}
$('variant').onchange=()=>{stop();loadFrame(fi);};$('diagnose').onchange=()=>{stop();loadFrame(fi);};
$('case').onchange=async()=>{if(!$('case').value)return;const [sid,f]=$('case').value.split('/');const s=catalog.sessions.find(s=>s.session_id===sid);await choose(s);await loadFrame(Number(f));};
api('/api/research').then(r=>{for(const c of r.cases.filter(c=>c.roles[0]!=='AXIS_OR_NEIGHBOR')){const o=document.createElement('option');o.value=c.sid+'/'+c.fi;o.textContent=c.sid.slice(-6)+' / f'+c.fi+' · '+c.roles.join(' / ');$('case').append(o);}}).catch(e=>{$('version').textContent='R2研究尚未完成：'+e.message;});
$('dataset').onchange=initialize;""")
(here/'app.js').write_text(js, encoding='utf8')
