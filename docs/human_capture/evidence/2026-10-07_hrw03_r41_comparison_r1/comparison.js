"use strict";
const D=window.COMPARE_DATA,$=id=>document.getElementById(id),panes=[],cache=new Map();
const state={index:D.available.findIndex(f=>f.frame===55),frame:null,active:0,playing:false,loading:false,wanted:null,timer:null};
const cases=[{f:17,label:'f17 · 大比例删除',text:'P 的候选簇有1523点，S没有可分类簇。1407点被参考背景匹配删除；另63点仍在 cleanup 后但未组成可分类簇。该簇是真人、静态物还是混合，仍需人工判断。'},
{f:55,label:'f55 · 候选拆分',text:'P 的一个3190点候选，对应S的1987点与454点两个候选。共享原始点分别1977/354。半径缩小后通过几何门，可能去粘连，也可能拆碎同一人体；GT未闭合。'},
{f:63,label:'f63 · 近地点损失',text:'本帧干净窗口损失18点：17点在对齐后越过既有z=0.10m裁剪边界，1点命中reference。粉色审计标记在两侧叠加原位置，不代表保留点；脚、鞋、地面或混合语义仍为UNKNOWN。'},
{f:65,label:'f65 · 确认票变化',text:'主体候选的本帧 joint 两侧都是NON_HUMAN，但历史票P=2、S=3，因此S仍带track确认。历史确认不等于这一帧已识别到真人。'},
{f:102,label:'f102 · 小重叠合并',text:'S0保留P1的全部2865点，又包含P2的22点。按原始点有交集即算边的规则形成merge；这22点只占S0约0.76%，不能直接称真人融合。'},
{f:105,label:'f105 · 点保留，票变',text:'主体P候选2607点全部保留，S另外增加5点。P历史3票、S2票，确认行仍可能消失。这里不能把确认消失解释为人体点云丢失。'},
{f:146,label:'f146 · 三点裁剪',text:'主体两侧共享3293点，3点被workspace裁剪，S另增加6点。本帧joint两侧均确认，但P有3票、S仅2票，时序确认不同。'},
{f:151,label:'f151 · 网格粘连',text:'P的两个候选共享3280/587点到S0。S半径扩大至0.827m并失败。仅变换P候选点、没有删除点的诊断也会merge，说明固定XY网格重分箱参与粘连。'}];
function error(msg){$('error').style.display='block';$('error').textContent=msg;state.playing=false;clearTimeout(state.timer);$('play').textContent='▶ 播放';}
for(const item of D.available)$('frame').add(new Option('f'+item.frame+' / seq '+item.seq,item.frame));
for(const c of cases){const b=document.createElement('button');b.textContent=c.label;b.dataset.frame=c.f;b.onclick=()=>{stop();goFrame(c.f);};$('cases').appendChild(b);}
const inv=D.transform.rotation_row_major,rotation=new THREE.Matrix4().set(inv[0],inv[3],inv[6],0,inv[1],inv[4],inv[7],0,inv[2],inv[5],inv[8],0,0,0,0,1),translation=D.transform.translation_m;
function toSource(p){return [inv[0]*(p[0]-translation[0])+inv[3]*(p[1]-translation[1])+inv[6]*(p[2]-translation[2]),inv[1]*(p[0]-translation[0])+inv[4]*(p[1]-translation[1])+inv[7]*(p[2]-translation[2]),inv[2]*(p[0]-translation[0])+inv[5]*(p[1]-translation[1])+inv[8]*(p[2]-translation[2])];}
try {
for(const name of ['P','S']){
    const node=$('pane'+name),scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(48,1,.02,100);camera.up.set(0,0,1);
    const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0x0e1928);node.appendChild(renderer.domElement);
    const controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.dampingFactor=.12;controls.addEventListener('start',()=>{state.active=name==='P'?0:1;});
    const grid=new THREE.GridHelper(12,48,0x34485f,0x213044);grid.rotation.x=Math.PI/2;scene.add(grid);scene.add(new THREE.AxesHelper(.6));
    panes.push({name,node,scene,camera,renderer,controls,objects:[]});
}
}catch(e){error('点云渲染初始化失败：'+e.message+'。可继续查看下方真实统计，浏览器需支持WebGL。');}
function fit(){if(!panes.length)return;let c,r;switch($('focus').value){case 'person':c=[1.5,.3,.8];r=3;break;case 'static':c=[3.5,-.76,.85];r=3;break;default:c=[2.4,-.1,.9];r=5.2;}
    for(const p of panes){p.controls.target.set(...c);const v=$('view').value;
        if(v==='top'){p.camera.up.set(1,0,0);p.camera.position.set(c[0],c[1],r+1);}
        else{p.camera.up.set(0,0,1);if(v==='front')p.camera.position.set(c[0]-r,c[1],c[2]+.15);else if(v==='side')p.camera.position.set(c[0],c[1]-r,c[2]+.15);else p.camera.position.set(c[0]-r*.75,c[1]-r*.75,c[2]+r*.6);}
        p.camera.lookAt(p.controls.target);p.controls.update();}state.active=0;
}
function cloud(p,xyz,color,size,alpha=1,overlay=false){if(!xyz.length)return;const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(xyz,3));
    const mat=new THREE.PointsMaterial({color,size,sizeAttenuation:true,transparent:alpha<1,opacity:alpha,depthWrite:alpha===1,depthTest:!overlay}),obj=new THREE.Points(geo,mat);obj.renderOrder=overlay?2:0;p.scene.add(obj);p.objects.push(obj);}
function candidateColor(c){return c.joint==='CONFIRMED_HUMAN'&&c.confirmed?0x32d5b4:c.joint==='NON_HUMAN'?0x8998ad:0x76aaff;}
function render(){if(!state.frame)return;const f=state.frame,data=D.frames[f.frame];
    for(const p of panes){for(const o of p.objects){p.scene.remove(o);o.geometry.dispose();o.material.dispose();}p.objects=[];
        const coords={grey:[],candidate:[],confirmed:[],context:[],difference:[]},visibleClusters=new Set();let kept=0,lost=0,gained=0;
        for(const row of f.points){const xyz=row.slice(1,4),retained=p.name==='P'?row[9]:row[10],ci=p.name==='P'?row[11]:row[12],diff=p.name==='P'?row[9]&&!row[10]:row[10]&&!row[9];
            if(retained){kept++;if(ci!==null)visibleClusters.add(ci);const c=ci===null?null:data[p.name].clusters[ci];coords[!c||c.joint==='NON_HUMAN'?'grey':c.joint==='CONFIRMED_HUMAN'&&c.confirmed?'confirmed':'candidate'].push(...xyz);}else if($('context').checked)coords.context.push(...xyz);
            if(diff&&$('diff').checked)coords.difference.push(...xyz);if(row[9]&&!row[10])lost++;if(row[10]&&!row[9])gained++;
        }
        cloud(p,coords.context,0x3d4c60,.013,.35);cloud(p,coords.grey,0x8998ad,.018,.75);cloud(p,coords.candidate,0x76aaff,.021);cloud(p,coords.confirmed,0x32d5b4,.023);
        cloud(p,coords.difference,p.name==='P'?0xff6375:0xf0b857,.032,1,true);
        if($('diff').checked)cloud(p,data.loss.flatMap(v=>v.xyz),0xff4db1,.06,1,true);
        if($('boxes').checked)for(const [ci,c] of data[p.name].clusters.entries()){if(!visibleClusters.has(ci))continue;const geo=new THREE.BoxGeometry(Math.max(.12,c.width*2),Math.max(.12,c.depth*2),Math.max(.12,c.height)),mat=new THREE.MeshBasicMaterial({color:candidateColor(c),wireframe:true,transparent:true,opacity:.5}),box=new THREE.Mesh(geo,mat),center=[c.cx,c.cy,c.zmin+c.height/2];
            if(p.name==='S'){box.quaternion.setFromRotationMatrix(rotation);box.position.set(...toSource(center));}else box.position.set(...center);p.scene.add(box);p.objects.push(box);}
        $('local'+p.name).textContent='局部证据 '+f.points.length.toLocaleString()+' 点 · 本分支保留 '+kept.toLocaleString()+' · '+(p.name==='P'?'S未保留 '+lost:'S新增保留 '+gained);
    }
    $('frameInfo').textContent='f'+f.frame+' / seq '+f.seq;$('frame').value=f.frame;$('slider').value=state.index;
    $('countPoints').textContent=data.P.post.toLocaleString()+' → '+data.S.post.toLocaleString();$('countClusters').textContent=data.P.clusters.length+' → '+data.S.clusters.length;
    $('countConfirmed').textContent=data.P.clusters.filter(c=>c.confirmed).length+' → '+data.S.clusters.filter(c=>c.confirmed).length;
    const body=$('clusters');body.replaceChildren();for(const name of ['P','S'])for(const [i,c] of data[name].clusters.entries()){
        const tr=document.createElement('tr'),track=data[name].tracks.find(t=>t.id===c.track),values=[name+' / '+i,'#'+c.track,c.n.toLocaleString(),c.height.toFixed(2)+' / '+c.radius.toFixed(2),c.joint==='CONFIRMED_HUMAN'?'人形证据':c.joint==='NON_HUMAN'?'NON_HUMAN':'候选',track?track.votes.join(' '):'—'];
        for(const v of values){const td=document.createElement('td');td.textContent=v;tr.appendChild(td);}tr.children[4].innerHTML='';const tag=document.createElement('span');tag.className='tag'+(c.joint==='CONFIRMED_HUMAN'?' yes':c.joint==='HUMAN_CANDIDATE'?' candidate':'');tag.textContent=values[4]+(c.confirmed?' · track确认':'');tr.children[4].appendChild(tag);body.appendChild(tr);
    }
    const example=cases.find(c=>c.f===f.frame);$('insight').replaceChildren();const title=document.createElement('strong');title.textContent=example?example.label:'对比同一帧的保留点与候选';$('insight').appendChild(title);$('insight').appendChild(document.createTextNode(example?example.text:'P/S前景点、候选成员与历史确认可能同时变化。删除点、新增点及候选拓扑都有迹可循；真实人体身份与连续性仍需人工GT。'));
    $('topology').textContent='候选 overlap · split '+data.topology.split+' / merge '+data.topology.merge;
    $('changes').replaceChildren();const relevant=data.changes.filter(c=>c.category!=='STATIC_REMOVAL_EXPECTED');for(const r of relevant){const div=document.createElement('div');const words={new_green:'新增 track确认行',new_purple:'新增瞬时人形证据行',disappeared:'P确认行消失'};div.textContent=words[r.change]+' · P'+r.Pidx+' ↔ S'+r.Sidx+' · 原始点交集 '+r.shared+' · 真人语义 UNKNOWN';$('changes').appendChild(div);}
    if(!relevant.length){const div=document.createElement('div');div.textContent=data.changes.length?'本帧变化仅有已登记 WD01 静态区域的期望移除。':'本帧没有记录到非静态confirmation变化行。';$('changes').appendChild(div);}
    for(const b of $('cases').children)b.classList.toggle('active',Number(b.dataset.frame)===f.frame);chart();
}
function stop(){state.playing=false;clearTimeout(state.timer);$('play').textContent='▶ 播放';}
function schedule(){clearTimeout(state.timer);if(state.playing)state.timer=setTimeout(()=>{if(state.index>=D.available.length-1){stop();return;}go(state.index+1);},1000/Number($('speed').value));}
function go(index){state.index=Math.max(0,Math.min(D.available.length-1,index));state.wanted=D.available[state.index].frame;$('slider').value=state.index;loadWanted();}
function goFrame(frame){go(D.available.reduce((best,f,i)=>Math.abs(f.frame-frame)<Math.abs(D.available[best].frame-frame)?i:best,0));}
function loadWanted(){if(state.loading)return;const frame=state.wanted;if(cache.has(frame)){state.frame=cache.get(frame);render();schedule();return;}
    state.loading=true;for(const name of ['P','S'])$('local'+name).textContent='正在读取 f'+frame+'…';const script=document.createElement('script');script.src='../2026-10-07_hrw03_r39_closeout/viewer_frames/f'+frame+'.js';
    script.onload=()=>{script.remove();state.loading=false;const fr=window.HR_FRAME;if(!fr||fr.frame!==frame){error('证据帧身份不一致，请刷新。');return;}cache.set(frame,fr);if(cache.size>4)cache.delete(cache.keys().next().value);if(state.wanted!==frame){loadWanted();return;}state.frame=fr;render();schedule();};
    script.onerror=()=>{script.remove();state.loading=false;error('未能读取 f'+frame+' 的局部证据。请保留项目目录相对结构，并用浏览器打开本页。');};document.head.appendChild(script);
}
function chart(){const w=1000,h=96,pad=28,max=Math.max(...D.frames.flatMap(f=>[f.P.post,f.S.post])),x=f=>pad+f/164*(w-pad*2),y=n=>h-17-n/max*(h-29);let svg='<svg viewBox="0 0 1000 96" preserveAspectRatio="none" aria-label="全165帧前景点数量对比">';
    for(const value of [0,max])svg+='<line x1="28" y1="'+y(value)+'" x2="972" y2="'+y(value)+'" stroke="#e5ecf3"/><text x="0" y="'+(y(value)+3)+'" fill="#8191a4" font-size="9">'+(value/1000).toFixed(1)+'k</text>';
    for(const name of ['P','S'])svg+='<polyline fill="none" stroke="'+(name==='P'?'#7893b8':'#00b496')+'" stroke-width="1.8" points="'+D.frames.map(f=>x(f.frame)+','+y(f[name].post)).join(' ')+'"/>';
    const f=state.frame?.frame??55;svg+='<line x1="'+x(f)+'" y1="5" x2="'+x(f)+'" y2="82" stroke="#263c53" stroke-dasharray="3 3"/><text x="28" y="94" fill="#8191a4" font-size="9">f0</text><text x="950" y="94" fill="#8191a4" font-size="9">f164</text></svg>';$('chart').innerHTML=svg;
}
$('frame').onchange=()=>{stop();goFrame(Number($('frame').value));};$('slider').oninput=()=>{stop();go(Number($('slider').value));};$('prev').onclick=()=>{stop();go(state.index-1);};$('next').onclick=()=>{stop();go(state.index+1);};$('play').onclick=()=>{if(state.playing){stop();return;}state.playing=true;$('play').textContent='Ⅱ 暂停';schedule();};$('speed').onchange=schedule;
$('home').onclick=fit;$('focus').onchange=fit;$('view').onchange=fit;for(const id of ['context','boxes','diff'])$(id).onchange=render;
$('chart').onclick=e=>{const rect=$('chart').getBoundingClientRect(),v=(e.clientX-rect.left)/rect.width;stop();goFrame(Math.round(Math.max(0,Math.min(1,(v-.028)/.944))*164));};
function animate(){requestAnimationFrame(animate);if(!panes.length)return;const active=panes[state.active];active.controls.update();for(const p of panes){if(p!==active){p.camera.position.copy(active.camera.position);p.camera.quaternion.copy(active.camera.quaternion);p.camera.up.copy(active.camera.up);p.controls.target.copy(active.controls.target);}
    const w=p.node.clientWidth,h=p.node.clientHeight;if(p.renderer.domElement.width!==Math.round(w*p.renderer.getPixelRatio())||p.renderer.domElement.height!==Math.round(h*p.renderer.getPixelRatio()))p.renderer.setSize(w,h,false);p.camera.aspect=w/h;p.camera.updateProjectionMatrix();p.renderer.render(p.scene,p.camera);}}
window.addEventListener('keydown',e=>{if(['INPUT','SELECT','BUTTON'].includes(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();$('play').click();}else if(e.code==='ArrowRight')$('next').click();else if(e.code==='ArrowLeft')$('prev').click();});
fit();chart();go(state.index);animate();
