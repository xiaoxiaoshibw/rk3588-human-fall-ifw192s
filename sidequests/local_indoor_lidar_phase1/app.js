'use strict';
const $=id=>document.getElementById(id), views=[], scenes=[], cameras=[], controls=[], pointGroups=[];
let catalog=null,data=null,timer=null,syncing=false;
const status=s=>$('status').textContent=s;
for(let i=0;i<3;i++){
 const el=$('v'+i),scene=new THREE.Scene();scene.background=new THREE.Color('#101b29');
 const camera=new THREE.PerspectiveCamera(55,el.clientWidth/el.clientHeight,.01,100);camera.up.set(0,0,1);
 const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(el.clientWidth,el.clientHeight);el.appendChild(renderer.domElement);
 const control=new THREE.OrbitControls(camera,renderer.domElement);control.enableDamping=false;
 const grid=new THREE.GridHelper(20,40,0x47617a,0x243b50);grid.rotation.x=Math.PI/2;scene.add(grid);scene.add(new THREE.AxesHelper(1));
 const group=new THREE.Group();scene.add(group);scenes.push(scene);cameras.push(camera);controls.push(control);views.push(renderer);pointGroups.push(group);
 control.addEventListener('change',()=>{if(syncing)return;syncing=true;for(let j=0;j<3;j++)if(j!==i){cameras[j].position.copy(camera.position);cameras[j].quaternion.copy(camera.quaternion);controls[j].target.copy(control.target);controls[j].update();}syncing=false;});
}
function home(){syncing=true;for(let i=0;i<3;i++){cameras[i].position.set(8,-9,8);controls[i].target.set(1.5,0,.6);controls[i].update();}syncing=false;}
home();
function animate(){requestAnimationFrame(animate);for(let i=0;i<3;i++){const el=$('v'+i);if(views[i].domElement.width!==Math.floor(el.clientWidth*views[i].getPixelRatio())){views[i].setSize(el.clientWidth,el.clientHeight);cameras[i].aspect=el.clientWidth/el.clientHeight;cameras[i].updateProjectionMatrix();}views[i].render(scenes[i],cameras[i]);}}animate();
function clear(){data=null;for(const group of pointGroups){while(group.children.length){const o=group.children[0];group.remove(o);if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose();}}for(let i=0;i<3;i++)$('c'+i).textContent='无当前结果';$('binding').textContent='';$('counts').textContent='';$('candidate').replaceChildren();$('candidateInfo').textContent='无当前候选';$('members').removeAttribute('href');$('attest').checked=false;$('basis').value='';$('scope').value='';$('cls').value='UNKNOWN';$('occlusion').checked=false;$('ambiguity').checked=true;$('missing').checked=true;$('complete').checked=false;}
const latest=new LatestFrame(clear);
function stop(){clearInterval(timer);timer=null;$('play').textContent='播放';}
function option(el,value,label){const o=new Option(label,value);el.add(o);}
function fillFrames(){const sid=$('sid').value;$('fi').replaceChildren();for(const fi of catalog.manifest.sources[sid].available)option($('fi'),fi,'f'+fi);}
function addPoints(panel,indices,colorFn,size=.035){if(!indices.length)return;const xyz=new Float32Array(indices.length*3),rgb=new Float32Array(indices.length*3);indices.forEach((id,j)=>{xyz.set(data.xyz[id],j*3);const c=new THREE.Color(colorFn(id));rgb.set([c.r,c.g,c.b],j*3);});const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.BufferAttribute(xyz,3));geom.setAttribute('color',new THREE.BufferAttribute(rgb,3));pointGroups[panel].add(new THREE.Points(geom,new THREE.PointsMaterial({size,vertexColors:true})));}
function hue(k){return new THREE.Color().setHSL((k*.618+.12)%1,.75,.6).getHex();}
function box(panel,c,color){const lo=new THREE.Vector3(...c.min),hi=new THREE.Vector3(...c.max);const h=new THREE.Box3Helper(new THREE.Box3(lo,hi),color);pointGroups[panel].add(h);}
function candidateInfo(){if(!data)return;const c=data.row.candidates.find(c=>c.id===Number($('candidate').value));if(!c)return;const reviews=data.reviews.filter(r=>r.candidate_id===c.id);$('candidateInfo').textContent=JSON.stringify(c,null,2)+'\n源行均为帧内0基；完整列表由链接查询，非min/max区间的全部点。\n人工候选级记录（不改写算法UNKNOWN）：'+JSON.stringify(reviews,null,2);$('members').href='/api/members?sid='+encodeURIComponent(data.row.sid)+'&fi='+data.row.fi+'&candidate='+c.id;}
function render(payload){data=payload;for(const group of pointGroups){while(group.children.length){const o=group.children[0];group.remove(o);if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose();}}
 $('queue').value=catalog.queue.tasks.some(t=>t.sid===data.row.sid&&t.fi===data.row.fi)?data.row.sid+'/'+data.row.fi:'';
 const n=data.xyz.length,step=$('full').checked?1:Math.max(1,Math.ceil(n/20000)),ids=[];for(let i=0;i<n;i+=step)ids.push(i);
 addPoints(0,ids,()=>0x9eb8cf);addPoints(1,ids,()=>0x7c91a8);
 if($('room').checked)addPoints(2,ids,()=>0x374e63,.025);
 // Candidate members are always all shown; room-only layer follows the declared stride.
 const members=[];for(let i=0;i<n;i++)if(data.cluster[i]>=0)members.push(i);
 addPoints(2,members,i=>data.terminal[i]===5?0xffd166:hue(data.cluster[i]),.048);
 for(const c of data.row.candidates)if($('boxes').checked)box(2,c,c.selected?0xffd166:hue(c.id));
 for(const r of data.reviews){const c=data.row.candidates.find(c=>c.id===r.candidate_id);if(c)box(1,c,r.class==='HUMAN_ONLY'?0x71df94:r.class==='NONHUMAN'?0x73bcff:0xffbf69);}
 if(!data.reviews.length){const proposal=data.row.candidates.find(c=>c.selected);if(proposal)box(1,proposal,0xffbf69);}
 $('c0').textContent=`原始 ${data.row.raw_count} / 有限 ${n} / 显示 ${ids.length}；有限源行每 ${step} 行取1，非有限剔除 ${data.nonfinite_display_excluded}；可切全点。`;
 $('c1').textContent=`本帧真实提交 ${data.reviews.length} 条；${data.reviews.length?'候选级，待质量核验':'琥珀框=AI几何待审建议，不是GT'}；未审点 UNKNOWN；历史标签未晋升。`;
 $('c2').textContent=`实际簇 ${data.row.candidates.length} / 全成员 ${members.length} 点；黄色=原R1单目标，其他颜色=未选簇。无人体概率。`;
 const m=catalog.manifest;$('binding').textContent=`session=${data.row.sid}  frame=${data.row.fi}  run=${data.row.run}\n原始meta SHA=${data.row.source_sha256.meta}\n原始points SHA=${data.row.source_sha256.points}\n本帧raw28 SHA=${data.row.frame_bytes_sha256}\n坐标=${m.coordinate}\nR=${JSON.stringify(m.R)} T=${JSON.stringify(m.T)}\n注册=${data.row.sid===m.empty_sid?'无':m.assets[Object.keys(m.assets).find(p=>p.endsWith(data.row.sid+'_registration.json'))]}\n背景SHA=${m.background.sha256} tau=${m.tau}  cfg=${m.cfg_id} manifest SHA=${data.manifest_sha256}`;
 $('counts').replaceChildren();data.row.terminal_counts.forEach((count,i)=>{const el=document.createElement('span');el.textContent=m.reasons[i]+': '+count;$('counts').append(el);});
 const selected=$('candidate').value;$('candidate').replaceChildren();for(const c of data.row.candidates)option($('candidate'),c.id,`C${c.id} · ${c.count}点${c.selected?' · R1选中':''}`);if([...$('candidate').options].some(o=>o.value===selected))$('candidate').value=selected;candidateInfo();
 status(`同帧已绑定 · ${data.row.sid} / f${data.row.fi} · 待审核疑点，非识别成功/失败 · 当前全局真实提交 ${catalog.human_reviews.length}`);
}
async function load(){const token=latest.begin();status('加载中，旧结果已清空…');try{
 if($('mode').value!=='R1')throw Error('BLOCKED：旧RF输入与训练坐标/高度带契约尚未合格；没有人体预测。');
 const sid=$('sid').value,fi=Number($('fi').value);const response=await fetch('/api/frame?sid='+encodeURIComponent(sid)+'&fi='+fi,{signal:token.signal});const p=await response.json();
 if(!latest.accept(token.id))return;if(!response.ok)throw Error(p.error);
 if(p.row.sid!==sid||p.row.fi!==fi||p.manifest_sha256!==catalog.manifest_sha256)throw Error('响应版本/帧绑定不一致');
 render(p);
 }catch(e){if(!latest.accept(token.id))return;latest.invalidate();stop();status('结果已清空：'+e.message);}}
function move(delta){const el=$('fi');const index=Math.max(0,Math.min(el.options.length-1,el.selectedIndex+delta));if(index===el.selectedIndex){stop();return;}el.selectedIndex=index;load();}
$('focusCandidate').onclick=()=>{if(!data)return;const c=data.row.candidates.find(c=>c.id===Number($('candidate').value));if(!c)return;const center=c.min.map((v,i)=>(v+c.max[i])/2),span=Math.max(...c.max.map((v,i)=>v-c.min[i]),.5);syncing=true;for(let i=0;i<3;i++){controls[i].target.set(...center);cameras[i].position.set(center[0]+span*1.7,center[1]-span*2,center[2]+span*1.1);controls[i].update();}syncing=false;};
$('sid').onchange=()=>{stop();fillFrames();load();};$('fi').onchange=()=>{stop();load();};$('prev').onclick=()=>{stop();move(-1);};$('next').onclick=()=>{stop();move(1);};$('reload').onclick=()=>load();$('home').onclick=home;
$('play').onclick=()=>{if(timer)return stop();$('play').textContent='暂停';timer=setInterval(()=>{if(data)move(1);},600);};
for(const n of ['full','room','boxes'])$(n).onchange=()=>{if(data)render(data);};$('mode').onchange=()=>{stop();load();};$('candidate').onchange=candidateInfo;
function jump(value){stop();const [sid,fi]=value.split('/');$('sid').value=sid;fillFrames();$('fi').value=fi;load();}
$('jumpQueue').onclick=()=>{if($('queue').value)jump($('queue').value);else status('当前帧不在固定24帧队列；请先选择待审项。');};$('jumpCase').onclick=()=>jump($('cases').value);
$('review').onsubmit=async e=>{e.preventDefault();stop();if(!data)return;const bound=data;try{
 const record={schema:'local-human-review/1',sid:bound.row.sid,fi:bound.row.fi,source_sha256:bound.row.source_sha256,
 reviewer:$('reviewer').value.trim(),date:$('date').value,basis:$('basis').value.trim(),scope:$('scope').value.trim(),label_version:'LIDAR_LOCAL_CANDIDATE_V1',granularity:'CANDIDATE_LEVEL',candidate_id:Number($('candidate').value),class:$('cls').value,
 occlusion:$('occlusion').checked,ambiguity:$('ambiguity').checked,missing_labels:$('missing').checked,frame_complete:$('complete').checked,human_attestation:$('attest').checked};
 const response=await fetch('/api/human-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(record)});const result=await response.json();if(!response.ok)throw Error(result.error);
 catalog.human_reviews.push(result);$('attest').checked=false;$('basis').value='';$('reviewMessage').textContent='已追加真实人员提交，仍待质量核验；未自动转为点级GT或训练资格。';await load();
 }catch(err){latest.invalidate();status('提交失败，旧结果已清空：'+err.message);$('reviewMessage').textContent=err.message;}};
async function init(){try{const response=await fetch('/api/catalog');catalog=await response.json();if(!response.ok)throw Error(catalog.error);for(const sid of Object.keys(catalog.manifest.sources))option($('sid'),sid,sid);fillFrames();
 option($('queue'),'','当前帧不在固定24帧队列');for(const task of catalog.queue.tasks)option($('queue'),task.sid+'/'+task.fi,task.sid+' / f'+task.fi+' · 待人工');
 const all=catalog.ledger.slice().sort((a,b)=>b.candidates-a.candidates);for(const row of all.slice(0,20))option($('cases'),row.sid+'/'+row.fi,`${row.sid} / f${row.fi} · ${row.candidates}簇（待审核）`);
 $('date').value='2026-10-15';await load();}catch(e){latest.invalidate();status('启动失败：'+e.message);}}
init();
