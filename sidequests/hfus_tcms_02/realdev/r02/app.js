'use strict';
const $=id=>document.getElementById(id);
let data=null,selected=null,requestSerial=0,renderCount=0,lastSignature=null;
const edges=[];for(let i=0;i<8;i++)for(let j=i+1;j<8;j++)if([1,2,4].includes(i^j))edges.push([i,j]);
const picks={raw:[],local:[]};
async function api(url){const r=await fetch(url);const x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x;}
function json(id,value){$(id).textContent=JSON.stringify(value,null,2);}
function signature(d){return JSON.stringify([d.fi,d.tag,d.current.map(x=>[x.source_row,x.raw_xyz,x.local_xyz]),d.candidates.map(x=>[x.id,x.center,x.obb_corners]),d.track.center]);}
function project(p,w,h){const [x,y,z]=p,cam=$('camera').value,s=+$('zoom').value;let a,b;
 if(cam==='top'){a=x-2.5;b=y-1;}else if(cam==='front'){a=y-1;b=z-.3;}else if(cam==='side'){a=x-2.5;b=z-.3;}else{a=x-2.5+(y-1)*.35;b=z-.3-(y-1)*.28;}
 return [w/2+a*s,h/2-b*s];}
function rawCorners(c){const a=[];for(const x of [c.min[0],c.max[0]])for(const y of [c.min[1],c.max[1]])for(const z of [c.min[2],c.max[2]])a.push([x,y,z]);return a;}
function draw(which){const canvas=$(which),rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1,w=rect.width,h=rect.height;
 canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.fillStyle='#0c1521';ctx.fillRect(0,0,w,h);picks[which]=[];
 const field=which==='raw'?'raw_xyz':'local_xyz';
 function point(p,color,size=1.4,row=null){if(!p||p.some(v=>v===null||!Number.isFinite(v)))return;const q=project(p,w,h);if(q[0]<0||q[0]>w||q[1]<0||q[1]>h)return;ctx.fillStyle=color;ctx.fillRect(q[0]-size/2,q[1]-size/2,size,size);if(row!==null)picks[which].push({x:q[0],y:q[1],row});}
 function line(a,b,color,width=1){const p=project(a,w,h),q=project(b,w,h);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...p);ctx.lineTo(...q);ctx.stroke();}
 function text(p,t,color){const q=project(p,w,h);ctx.fillStyle=color;ctx.font='12px system-ui';ctx.fillText(t,q[0]+4,q[1]-4);}
 for(let k=-5;k<=12;k++){line([k,-5,0],[k,12,0],'#233447');line([-5,k,0],[12,k,0],'#233447');}
 const origin=[0,0,0];for(const [p,t,c] of [[[1,0,0],'X','#ef7777'],[[0,1,0],'Y','#74e5b2'],[[0,0,1],'Z','#73aaff']]){line(origin,p,c,2);text(p,t,c);}
 const R=data.transform.R,t=data.transform.t,n=data.transform.plane.normal,d=data.transform.plane.d_m;
 const o=n.map(v=>-d*v);const u=R[0],v=R[1];function plane(a,b){return o.map((x,i)=>x+a*u[i]+b*v[i]);}
 if(which==='raw'){line(o,o.map((x,i)=>x+n[i]),'#f6bb6a',3);text(o.map((x,i)=>x+n[i]),'n (历史候选)','#f6bb6a');for(let a=0;a<=5;a++)line(plane(a,-2),plane(a,3),'#735c3c');}
 else{line([0,0,0],[0,0,1],'#f6bb6a',3);text([0,0,1],'n_local / z=0','#f6bb6a');}
 if($('map').checked)for(const p of data.map)point(p[field],p.visible?'#2fcbbd':'#29777d',2);
 if($('support').checked)for(const p of data.map_support)point(p[field],'#b68edb',2);
 if($('current').checked)for(const p of data.current)if(p.valid)point(p[field],p.candidate_id>=0?'#ffc67c':(p.flags&16)?'#98ef95':'#b2c1ce',p.candidate_id>=0?2.5:1.5,p.source_row);
 const cs=which==='raw'?data.raw_candidates:data.candidates;
 if($('boxes').checked)for(const c of cs){const corners=which==='raw'?rawCorners(c):c.obb_corners;for(const [a,b]of edges)line(corners[a],corners[b],'#d99445');point(c.center,'#fff0a1',5);text(c.center,`C${c.id} (${c.count})`,'#ffd295');}
 const track=which==='raw'?data.raw_track:data.track;
 if($('tracks').checked){let previous=null;for(const p of data.trajectory){const pos=which==='raw'?p.raw_center:p.local_center;if(previous)line(previous,pos,'#6ec587',2);previous=pos;}if(track.center){const pred=track.state==='PREDICTED';point(track.center,pred?'#ff8fcc':'#8df2a0',9);text(track.center,`历史 ${track.state}`,pred?'#ff8fcc':'#8df2a0');}}
 if(selected){point(selected[field],'#ff497b',10);text(selected[field],`row ${selected.source_row}`,'#ff8fa7');}
}
function render(){if(!data)return;const before=signature(data);draw('raw');draw('local');renderCount++;if(before!==signature(data))throw Error('Camera mutated coordinate state');
 const diagnostic={fi:data.fi,raw_frame:data.raw_tag.frame,local_frame:data.tag.frame,transform_id:data.tag.transform_id,coordinate_version:data.tag.coordinate_version,render_count:renderCount,camera:$('camera').value,coordinate_signature_unchanged:lastSignature===before,raw_local_numerically_different:data.current.filter(x=>x.valid).some(x=>x.raw_xyz.some((v,i)=>Math.abs(v-x.local_xyz[i])>.01)),raw_drawn:picks.raw.length,local_drawn:picks.local.length,map_drawn:data.map.length,box_count:data.candidates.length,track_state:data.track.state,selection_source_row:selected?.source_row??null,qualification:false};json('diagnostics',diagnostic);
 $('status').textContent=`已加载帧 ${data.fi} / 779 · RAW 与候选配平同步 · ${data.state} / ${data.mode}`;
}
async function showFrame(fi){const serial=++requestSerial;$('status').textContent=`正在加载帧 ${fi}`;selected=null;$('point').textContent='点选或反查当前帧源行';$('surfaceInfo').textContent='反查当前帧可用的M0支持';
 try{const d=await api('/api/frame?fi='+fi);if(serial!==requestSerial)return;data=d;lastSignature=signature(data);$('fi').value=fi;$('cases').value=String(fi);
 $('rawTitle').textContent=`RAW · fi ${fi} · innolidar`;$('localTitle').textContent=`候选配平 · fi ${fi} · candidate_local`;
 $('summary').textContent=`全量计算 ${d.original_denominator} 行（包括无效/零行）；仅显示抽样 ${d.display.sample_rows} 行。M0 ${d.map.length}/${d.display.full_map_surfaces} 面；原图 build_end=${d.map_available_after_fi}，首显示=${d.map_first_display_fi}。\n冻结轨迹 ${d.track.state}，旧确认仅历史证据，新坐标身份未确认。全场残差不是地面质量；历史相容带也不是验证集。`;
 json('versions',{transform_id:d.tag.transform_id,coordinate_version:d.tag.coordinate_version,R:d.transform.R,t_m:d.transform.t,plane:d.transform.plane,provenance:d.transform.reuse,source_sha256:d.source_sha256,geometry_validated:false,ground_identity_confirmed:false,physical_verified:false,runtime_eligible:false,physical_height_m:null,scene_residual:d.scene_residual,legacy_selected_band_residual:d.legacy_band_residual});render();
 }catch(e){$('status').textContent='ERROR '+e.message;throw e;}}
async function query(row){const serial=requestSerial,fi=data.fi,tag=data.tag;try{const result=await api(`/api/source?fi=${fi}&row=${row}&transform_id=${tag.transform_id}&coordinate_version=${encodeURIComponent(tag.coordinate_version)}`);
 if(serial!==requestSerial||data.fi!==fi||data.tag.coordinate_version!==tag.coordinate_version)return;
 if(result.fi!==fi||result.tag.transform_id!==tag.transform_id||result.tag.coordinate_version!==tag.coordinate_version)throw Error('Point frame/version mismatch');
 selected=result;$('row').value=row;json('point',selected);render();}catch(e){if(serial===requestSerial)json('point',{error:e.message});}}
for(const which of ['raw','local'])$(which).onclick=e=>{const rect=$(which).getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;let best=null,d2=100;for(const p of picks[which]){const d=(p.x-x)**2+(p.y-y)**2;if(d<d2){d2=d;best=p;}}if(best)query(best.row);};
$('load').onclick=()=>showFrame(+$('fi').value);$('prev').onclick=()=>showFrame(Math.max(0,data.fi-1));$('next').onclick=()=>showFrame(Math.min(779,data.fi+1));$('cases').onchange=()=>showFrame(+$('cases').value);$('query').onclick=()=>query(+$('row').value);
async function querySurface(){const serial=requestSerial,fi=data.fi,tag=data.tag;try{const result=await api(`/api/surface?fi=${fi}&id=${+$('surface').value}&transform_id=${tag.transform_id}&coordinate_version=${encodeURIComponent(tag.coordinate_version)}`);
 if(serial!==requestSerial||data.fi!==fi||data.tag.coordinate_version!==tag.coordinate_version)return;
 if(result.tag.fi!==fi||result.tag.transform_id!==tag.transform_id||result.tag.coordinate_version!==tag.coordinate_version)throw Error('Surface frame/version mismatch');json('surfaceInfo',result);
 }catch(e){if(serial===requestSerial)json('surfaceInfo',{error:e.message});}}
$('querySurface').onclick=querySurface;
for(const id of ['camera','zoom','current','map','support','boxes','tracks'])$(id).onchange=render;
window.addEventListener('resize',render);
(async()=>{const c=await api('/api/catalog');for(const fi of c.cases){const o=document.createElement('option');o.value=fi;o.textContent='fi '+fi;$('cases').append(o);}const fi=Number(new URLSearchParams(location.search).get('fi')||430);await showFrame(fi);})();
