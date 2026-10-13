'use strict';
/* R3 逐帧真实可视化（CC 主线，离线零依赖 SVG，浏览器可看，不占用/不修改 Demo）。
 * 对指定 (sid, model, 帧号) 渲染 俯视XY / 侧视XZ / 3D 三视图于一张 SVG：
 *   灰=场景原始点  蓝=前景  绿=确认人  黄=弱人候选  红=拒绝  青圈=GT人  紫=确认轨迹
 *   重复ID：竞争同一 track 的候选描亮黄框 + 「同ID」警示；漏检：GT 人圈加粗 + 「MISS」。
 * 真实点云全部来自 captures/remote（只读），绝非合成。 */
const fs=require('fs'),path=require('path');
const D=require('./core/data_loader'),S=require('./core/schema'),L=require('./core/leveling');
const {createDetector}=require('./detector');
const {objects,rawMap}=require('./export');
const crypto=require('crypto');
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'results/AUDIT.json'),'utf8'));
const ROOT=process.env.HF_REPO_ROOT||path.resolve(__dirname,'../..');
const OUTDIR=process.argv[2]?path.resolve(process.argv[2]):path.join(__dirname,'results','R3_VIZ');
fs.mkdirSync(OUTDIR,{recursive:true});
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');

function projection(kind,cx,cy,half,W,H){
  if(kind==='top')return (x,y,z)=>[W/2+(x-cx)/half*(W*0.46), H/2-(y-cy)/half*(H*0.46)];
  if(kind==='side')return (x,y,z)=>[W/2+(x-cx)/half*(W*0.46), H*0.92-Math.max(0,Math.min(2.4,z))/2.4*(H*0.84)];
  const ang=0.6,tilt=0.55;
  return (x,y,z)=>{const a=(x-cx)*Math.cos(ang)-(y-cy)*Math.sin(ang),b=(x-cx)*Math.sin(ang)+(y-cy)*Math.cos(ang);
    return [W/2+a/half*(W*0.46), H*0.86-(b*Math.cos(tilt)+z*Math.sin(tilt))/half*(H*0.6)];};
}

function frameState(sid,model,fi){
  const rec=audit.sessions.find(r=>r.sid===sid);
  const session=D.load_session(path.join(ROOT,'captures/remote',sid));
  const det=createDetector(model); const gen=det.begin(sid);
  let doc=null; const d0=audit.docs[sid];
  if(rec.eligible&&d0&&d0.session_id===sid&&d0.review_status==='reviewed'){
    const buf=fs.readFileSync(rec.gt_path);
    if(crypto.createHash('sha256').update(buf).digest('hex')===rec.gt_sha256)doc=d0;
  }
  let st=null,cloud=null;
  for(let i=0;i<=fi;i++){
    const f=session.frames[i];
    const d=det.tick(S.make_frame_context({session_id:sid,session_generation:gen,frame_index:i,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta}));
    if(i===fi){
      const contract=det.engine.report().coordinate_contract;
      L.level_frame(f.xyzi,contract.R,contract.T,contract.already_leveled);
      const gtObjs=doc?(objects(doc,i,rawMap(f.xyzi))||[]):[];
      cloud=f.xyzi; // xyzi 已是 Float32Array（XYX... 每点4分量），n_points = length/4
      let fg=new Set();
      try{const rep=det.engine.report();(rep.fusion_final_fg_ids||[]).forEach(x=>fg.add(x));}catch(e){}
      st={n_points:f.n_points||(f.xyzi.length/4),candidates:d._candidates||[],tracks:(d._tracks||[]).filter(t=>t.active),
        foreground:fg,gt_persons:gtObjs.filter(g=>g.class_name==='PERSON').map(g=>({id:g.id,x:g.x,y:g.y,radius:g.radius||0.4})),
        has_gt:!!doc};
    }
  }
  return {st,cloud,has_gt:st.has_gt};
}

function render(job){
  const {sid,model,frame:fi}=job;
  const {st,cloud,has_gt}=frameState(sid,model,fi);
  // 范围（用全部点拟合 XY）
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
  for(let i=0;i<st.n_points;i++){const x=cloud[i*4],y=cloud[i*4+1];if(!Number.isFinite(x)||Math.abs(x)>20||Math.abs(y)>20)continue;if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}
  if(x0>x1){x0=-6;x1=6;y0=-6;y1=6;}
  let cx=(x0+x1)/2,cy=(y0+y1)/2,half=Math.max((x1-x0)/2,(y1-y0)/2,2.5);
  // 重复ID / 漏检
  const assign={};for(const c of st.candidates){if(c.track_id!=null){(assign[c.track_id]=assign[c.track_id]||[]).push(c.candidate_id);}}
  const dupIds=new Set(Object.keys(assign).filter(k=>assign[k].length>1));
  const gtMiss=new Set();
  for(const g of st.gt_persons){if(!st.candidates.some(c=>['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.classifier_decision)&&Math.hypot(c.centroid.x-g.x,c.centroid.y-g.y)<=0.75))gtMiss.add(g.id);}
  // 缺陷聚焦缩放：有重复ID→聚焦竞争簇点集包围盒；有漏检→聚焦漏检 GT 邻域；否则全屋。
  if(dupIds.size){
    const focusIdx=[];for(const c of st.candidates)if(dupIds.has(c.track_id))focusIdx.push(...(c.point_indices||[]));
    let fx0=1e9,fx1=-1e9,fy0=1e9,fy1=-1e9;
    for(const i of focusIdx){const x=cloud[i*4],y=cloud[i*4+1];if(!Number.isFinite(x))continue;if(x<fx0)fx0=x;if(x>fx1)fx1=x;if(y<fy0)fy0=y;if(y>fy1)fy1=y;}
    if(fx0<=fx1){cx=(fx0+fx1)/2;cy=(fy0+fy1)/2;half=Math.max((fx1-fx0)/2,(fy1-fy0)/2,0.9)+0.6;}
  }else if(gtMiss.size){
    const g=st.gt_persons.find(g=>gtMiss.has(g.id));
    if(g){cx=g.x;cy=g.y;half=1.6;}
  }
  // 视图
  const W=560,H=430,GAP=10,TOP=34;
  const panels=[['top','俯视 XY'],['side','侧视 XZ'],['persp','3D']];
  let body='';
  panels.forEach(([kind,label],pi)=>{
    const px=10+pi*(W+GAP), py=TOP;
    const proj=projection(kind,cx,cy,half,W,H);
    body+=`<g transform="translate(${px},${py})">`;
    body+=`<rect x="0" y="0" width="${W}" height="${H}" fill="#101a26" stroke="#293444"/>`;
    body+=`<text x="8" y="18" fill="#9eb4cc" font-size="13" font-family="sans-serif">${label}</text>`;
    // 原始场景点
    let pts='';
    for(let i=0;i<st.n_points;i++){const x=cloud[i*4],y=cloud[i*4+1],z=cloud[i*4+2];if(!Number.isFinite(x)||Math.abs(x)>20||Math.abs(y)>20)continue;const p=proj(x,y,z);if(p[0]<0||p[0]>W||p[1]<0||p[1]>H)continue;pts+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="0.9"/>`;}
    body+=`<g fill="#5b7186" opacity="0.55">${pts}</g>`;
    // 前景
    let fg='';
    for(const i of st.foreground){const x=cloud[i*4],y=cloud[i*4+1],z=cloud[i*4+2];if(!Number.isFinite(x))continue;const p=proj(x,y,z);if(p[0]<0||p[0]>W||p[1]<0||p[1]>H)continue;fg+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="1.2"/>`;}
    if(fg)body+=`<g fill="#5aa0e6" opacity="0.5">${fg}</g>`;
    // 候选
    for(const c of st.candidates){
      const col=c.classifier_decision==='CONFIRMED_HUMAN'?'#42e896':c.classifier_decision==='HUMAN_CANDIDATE'?'#ffd257':'#ef6f79';
      let cp='';
      for(const i of (c.point_indices||[])){const x=cloud[i*4],y=cloud[i*4+1],z=cloud[i*4+2];if(!Number.isFinite(x))continue;const p=proj(x,y,z);if(p[0]<0||p[0]>W||p[1]<0||p[1]>H)continue;cp+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="1.7"/>`;}
      body+=`<g fill="${col}">${cp}</g>`;
      const pc=proj(c.centroid.x,c.centroid.y,c.centroid.z);
      const dup=dupIds.has(c.track_id);
      body+=`<text x="${(pc[0]+5).toFixed(1)}" y="${(pc[1]-5).toFixed(1)}" fill="${dup?'#ffe600':col}" font-size="11" font-weight="bold" font-family="sans-serif">${esc(c.track_id||'?')}${c.classifier_decision==='CONFIRMED_HUMAN'?' ✓':''}${dup?' 同ID':''}</text>`;
      if(dup)body+=`<circle cx="${pc[0].toFixed(1)}" cy="${pc[1].toFixed(1)}" r="12" fill="none" stroke="#ffe600" stroke-width="2.5"/>`;
    }
    // GT 人圈
    for(const g of st.gt_persons){
      const p=proj(g.x,g.y,0);const miss=gtMiss.has(g.id);
      body+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="${((g.radius||0.4)/half*(W*0.46)).toFixed(1)}" fill="none" stroke="#2fd6e8" stroke-width="${miss?3.5:1.5}" stroke-dasharray="${miss?'':'4 3'}" opacity="0.9"/>`;
      if(miss)body+=`<text x="${(p[0]+6).toFixed(1)}" y="${(p[1]-8).toFixed(1)}" fill="#2fd6e8" font-size="12" font-weight="bold" font-family="sans-serif">MISS GT</text>`;
    }
    // 轨迹
    for(const t of st.tracks){if(!t.human_confirmed||t.lost)continue;const p=proj(t.x,t.y,t.z);body+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.5" fill="#c78cff"/>`;}
    body+=`</g>`;
  });
  const wTop=10+panels.length*(W+GAP),Htot=TOP+H+16;
  const flags=(dupIds.size?` · <tspan fill="#ffe600">同帧重复ID:${[...dupIds].join('|')}</tspan>`:'')+(gtMiss.size?` · <tspan fill="#2fd6e8">漏检GT:${gtMiss.size}</tspan>`:'');
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${wTop+10}" height="${Htot}" viewBox="0 0 ${wTop+10} ${Htot}">`+
    `<rect width="100%" height="100%" fill="#0b1017"/>`+
    `<text x="12" y="22" fill="#dce8f5" font-size="15" font-weight="bold" font-family="sans-serif">${esc(sid)} · ${esc(model)} · f${fi} · GT:${has_gt?'已绑':'未知'}${flags} · 候选${st.candidates.length} 确认轨迹${st.tracks.filter(t=>t.human_confirmed&&!t.lost).length}</text>`+
    body+`</svg>`;
  const fn=`${sid}_${model}_f${fi}`+(dupIds.size?'_DUPID':'')+(gtMiss.size?'_MISS':'')+'.svg';
  fs.writeFileSync(path.join(OUTDIR,fn),svg);
  console.log('WROTE',fn,'| dupID',[...dupIds].join('|')||'无','miss',gtMiss.size,'cands',st.candidates.length,'npts',st.n_points);
}

const jobs=JSON.parse(process.env.R3_JOBS||fs.readFileSync(path.join(__dirname,'r3_viz_jobs.json'),'utf8'));
for(const j of jobs){try{render(j);}catch(e){console.error('FAIL',j.sid,j.frame,e.message);}}
console.log('R3_VIZ_DONE -> '+OUTDIR);
