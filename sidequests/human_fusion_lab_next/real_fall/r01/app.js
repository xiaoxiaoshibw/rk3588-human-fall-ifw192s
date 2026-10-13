'use strict';
const $=id=>document.getElementById(id);let info,current,index=0,playing=false,token=0,busy=false;
const names={unknown:'未知 / 初始化',upright:'直立',descending:'下降',low_posture_unclassified:'低姿态',suspected:'疑似倒地',confirmed:'确认',recovering:'恢复'};
function makeView(id){const host=$(id),scene=new THREE.Scene();scene.background=new THREE.Color(0x0b1b29);
 const camera=new THREE.PerspectiveCamera(45,host.clientWidth/host.clientHeight,.01,50);camera.up.set(0,0,1);
 const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setSize(host.clientWidth,host.clientHeight);host.appendChild(renderer.domElement);
 const control=new THREE.OrbitControls(camera,renderer.domElement);control.target.set(1.3,1,.7);
 const grid=new THREE.GridHelper(10,50,0x456677,0x263d4d);grid.rotation.x=Math.PI/2;scene.add(grid);
 const group=new THREE.Group();scene.add(group);const view={host,scene,camera,renderer,control,group};
 function animate(){requestAnimationFrame(animate);control.update();renderer.render(scene,camera);}animate();return view;}
const views=[makeView('scene'),makeView('target')];
function camera(kind){for(const v of views){v.control.target.set(1.3,1,.7);
 if(kind==='side')v.camera.position.set(1.3,-5,.9);else if(kind==='top'){v.camera.position.set(1.3,1,7);v.control.target.set(1.3,1,0);}else v.camera.position.set(5,-4,3.5);v.control.update();}}
camera('fit');
function cloud(v,pts,color,size){if(!pts.length)return;const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(pts.flat(),3));
 const material=new THREE.PointsMaterial({color,size,sizeAttenuation:true});v.group.add(new THREE.Points(geometry,material));}
function draw(){if(!current)return;for(const v of views){while(v.group.children.length){const o=v.group.children[0];v.group.remove(o);o.geometry.dispose();o.material.dispose();}}
 const r=current.row,color=r.state.state==='suspected'?0xff8866:0x6de5c5;
 cloud(views[0],current[$('mode').value],0x65889e,.018);cloud(views[0],current.target,color,.022);cloud(views[1],current.target,color,.025);
 $('track').textContent=r.track_id||'UNKNOWN';$('state').textContent=names[r.state.state]||r.state.state;$('state').className=r.state.state==='suspected'?'alert':'';
 $('height').textContent=r.candidate?r.candidate.height_m.p90.toFixed(2)+' m':'—';$('count').textContent=current.target.length;
 $('events').textContent=info.events.length+' 次（固定结果）';$('frame').value=r.frame;$('timeline').value=r.frame;
 $('status').textContent=`帧 ${r.frame} / 163 · ${r.t.toFixed(2)} s · ${r.reason}`+(r.prototype_alert?' · 本帧产生原型倒地告警':'');}
async function load(i){const n=++token;busy=true;index=Math.max(0,Math.min(info.frames-1,i));$('status').textContent='正在加载帧 '+index;
 try{const res=await fetch('/api/frame?i='+index);if(!res.ok)throw Error('帧请求失败 '+res.status);const data=await res.json();if(n!==token)return;current=data;draw();}
 catch(e){playing=false;$('play').textContent='播放';$('status').textContent=e.message;current=null;for(const v of views){while(v.group.children.length){const o=v.group.children[0];v.group.remove(o);o.geometry.dispose();o.material.dispose();}}}
 finally{if(n===token)busy=false;}}
$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'暂停':'播放';};
$('prev').onclick=()=>load(index-1);$('next').onclick=()=>load(index+1);
$('frame').onchange=()=>load(Number($('frame').value));$('timeline').oninput=()=>load(Number($('timeline').value));
$('alarm').onclick=()=>{playing=false;$('play').textContent='播放';if(info.events.length)load(info.events[0].frame);};
$('reset').onclick=()=>{playing=false;$('play').textContent='播放';load(0);};$('mode').onchange=draw;
for(const k of ['side','top','fit'])$(k).onclick=()=>camera(k);
setInterval(()=>{if(playing&&!busy){if(index>=info.frames-1){playing=false;$('play').textContent='播放';}else load(index+1);}},110);
window.addEventListener('resize',()=>{for(const v of views){v.camera.aspect=v.host.clientWidth/v.host.clientHeight;v.camera.updateProjectionMatrix();v.renderer.setSize(v.host.clientWidth,v.host.clientHeight);}});
fetch('/api/info').then(r=>{if(!r.ok)throw Error('来源请求失败');return r.json();}).then(data=>{info=data;$('info').textContent=JSON.stringify(info,null,2);load(0);}).catch(e=>{$('status').textContent=e.message;for(const id of ['play','next','prev','alarm','reset'])$(id).disabled=true;});
