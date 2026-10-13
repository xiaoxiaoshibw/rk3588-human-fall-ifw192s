"use strict";
const manifest=window.HR_MANIFEST,pointLabels=new Map(),clusterLabels=new Map(),continuity=new Map();
const pointOptions=['UNKNOWN','FOOT_SHOE','LOWER_LEG','GROUND_RESIDUE','HUMAN_GROUND_MIXED','REGISTRATION_REFERENCE_MISMATCH'];
const clusterOptions=['UNKNOWN','PERSON','STATIC_OBJECT','MIXED'];
const colors={person:0x51e3a5,lost:0xff4d60,otherLost:0xffb950,bg:0x718091,ref:0x71a3ff};
const el=id=>document.getElementById(id),panes=[],panels=[...document.querySelectorAll('.pane')];let current=null,active=0,selectedPoint=null,request=0;
for(const [i,node] of panels.entries()) {
    const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(55,1,.01,150);camera.up.set(0,0,1);
    const renderer=new THREE.WebGLRenderer({antialias:true});renderer.setClearColor(0x111922);renderer.setPixelRatio(Math.min(devicePixelRatio,2));node.appendChild(renderer.domElement);
    const controls=new THREE.OrbitControls(camera,renderer.domElement);controls.addEventListener('start',()=>{active=i;});
    const grid=new THREE.GridHelper(10,100,0x536074,0x263544);grid.rotation.x=Math.PI/2;scene.add(grid);scene.add(new THREE.AxesHelper(.5));
    panes.push({scene,camera,renderer,controls,groups:[]});
}
function fit(center=null) {
    const c=center??current?.centers[0]??[1.5,0];selectedPoint=center;
    for(const p of panes){p.controls.target.set(c[0],c[1],.8);p.camera.position.set(c[0]+2,c[1]-3,2.3);p.controls.update();}active=0;
}
function cloud(p,coords,color,size) {
    if(!coords.length)return;const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));
    const mat=new THREE.PointsMaterial({color,size,sizeAttenuation:true}),obj=new THREE.Points(geo,mat);p.scene.add(obj);p.groups.push(obj);
}
function renderClouds() {
    for(const [i,p] of panes.entries()) {
        for(const obj of p.groups){p.scene.remove(obj);obj.geometry.dispose();obj.material.dispose();}p.groups=[];
        const groups={person:[],lost:[],otherLost:[],bg:[],ref:[]};
        for(const row of current.points) {
            const native=i===1&&el('nativeS').checked,xyz=row.slice(native?4:1,native?7:4);
            const candidate=(i===1?row[12]:row[11])!==null,absorbed=row[15]===1;
            const label=absorbed?'lost':i===2&&row[7]&&!row[8]?'otherLost':candidate?'person':'bg';groups[label].push(...xyz);
        }
        if(el('ref').checked)for(const v of current.reference_voxels)groups.ref.push(...(i===1&&el('nativeS').checked?[v.x,v.y,v.z]:v.source_xyz));
        for(const [k,v] of Object.entries(groups))cloud(p,v,colors[k],k==='lost'?.045:k==='ref'?.028:.014);
    }
    el('status').textContent=`${manifest.session} · frame index ${current.frame} / ROS seq ${current.seq} · ${current.points.length} 个局部原始点（未抽稀）· 本帧 ${manifest.absorbed.filter(p=>p.frame===current.frame).length} 个 clean 损失点 · ${manifest.confirmation.filter(p=>p.frame===current.frame).length} 个确认变化行`;
}
function showFrame(frame,center=null) {
    const token=++request;el('status').textContent='正在读取 frame '+frame;const script=document.createElement('script');
    script.src='viewer_frames/f'+frame+'.js';script.onload=()=>{script.remove();if(token!==request)return;current=window.HR_FRAME;el('frame').value=frame;renderClouds();fit(center);};
    script.onerror=()=>{el('status').textContent='frame 加载失败：'+frame;script.remove();};document.head.appendChild(script);
}
function picker(id,options,map){const s=document.createElement('select');for(const x of options)s.add(new Option(x,x));s.addEventListener('change',()=>map.set(id,s.value));return s;}
for(const f of manifest.frames)el('frame').add(new Option('f'+f.frame+' / seq '+f.seq+(f.clean?' · clean':''),f.frame));
for(const p of manifest.absorbed) {
    const row=el('points').insertRow(),b=document.createElement('button');b.textContent='f'+p.frame+' / p'+p.original_point_index;
    b.onclick=()=>{el('info').textContent=JSON.stringify(p,null,2);showFrame(p.frame,p.source_xyz);};row.insertCell().appendChild(b);
    row.insertCell().textContent=p.source_xyz.map(v=>v.toFixed(6)).join(', ');row.insertCell().textContent=p.mechanism+' / '+(p.P_path.track??'无候选');
    row.insertCell().appendChild(picker(p.id,pointOptions,pointLabels));
}
for(const c of manifest.confirmation) {
    const row=el('confirmations').insertRow(),b=document.createElement('button');b.textContent=c.id+' / '+c.P_track_id+'→'+c.S_track_id;
    b.onclick=()=>{el('info').textContent=JSON.stringify(c,null,2);showFrame(c.frame,c.P?.source_centroid??c.S?.source_centroid);};row.insertCell().appendChild(b);
    row.insertCell().textContent=c.attribution_category;row.insertCell().appendChild(picker(c.id,clusterOptions,clusterLabels));
    row.insertCell().appendChild(picker(c.id,['UNKNOWN','PRESERVED','FRAGMENTED','LOST','STATIC_NOT_HUMAN'],continuity));
}
el('frame').onchange=()=>showFrame(Number(el('frame').value));el('home').onclick=()=>fit();el('nativeS').onchange=el('ref').onchange=()=>renderClouds();
el('export').onclick=()=>{
    const reviewer=el('reviewer').value.trim();if(!reviewer){el('info').textContent='请填写标注人；标签不会写入 captures。';return;}
    const labels={kind:'hrw03_closeout_gt',schema:1,source:'human',reviewer,created_iso:new Date().toISOString(),session_id:manifest.session,
        artifact_id:manifest.artifact_id,source_session:manifest.input_binding.source_session,source_leveling:manifest.input_binding.source_leveling,
        points:manifest.absorbed.map(p=>({id:p.id,frame:p.frame,frame_seq:p.frame_seq,point_index:p.original_point_index,label:pointLabels.get(p.id)??'UNKNOWN'})),
        confirmations:manifest.confirmation.map(c=>({id:c.id,frame:c.frame,P_track_id:c.P_track_id,S_track_id:c.S_track_id,label:clusterLabels.get(c.id)??'UNKNOWN',continuity:continuity.get(c.id)??'UNKNOWN'}))};
    const url=URL.createObjectURL(new Blob([JSON.stringify(labels,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;
    a.download='hrw03_r39_gt_'+Date.now()+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
function animate(){requestAnimationFrame(animate);panes[active].controls.update();for(const [i,p] of panes.entries()) {
    if(i!==active){p.camera.position.copy(panes[active].camera.position);p.camera.quaternion.copy(panes[active].camera.quaternion);p.controls.target.copy(panes[active].controls.target);}
    const node=panels[i];p.renderer.setSize(node.clientWidth,node.clientHeight,false);p.camera.aspect=node.clientWidth/node.clientHeight;p.camera.updateProjectionMatrix();p.renderer.render(p.scene,p.camera);
}}animate();showFrame(63);
