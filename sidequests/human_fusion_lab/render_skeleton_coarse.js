'use strict';
/* 粗骨架真实节点可视化（CC 主线，离线只读 + 新证据，不修 skeleton/fusion/冻结参数）。
 * 用 fusion 已 CONFIRMED_HUMAN 人簇的真实成员点，调 skeleton.observe() 提取
 * 胸/骨盆/下身三槽的"区域中位点 + 点支撑"，渲染 侧视XZ + 3D 两视图，并把节点连成骨架线。
 * honesty：节点是"点支撑区域中位数"，不是解剖关节；HEAD 不画（需人工 HEAD_CONFIRMED）；
 * 标定 UNCALIBRATED；只显示 support_n>=node_min_points 且未被跨度门拒绝的节点。 */
const fs=require('fs'),path=require('path');
const cp=require('child_process');
const D=require('./core/data_loader'),S=require('./core/schema'),L=require('./core/leveling');
const {createDetector}=require('./detector');
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'results/AUDIT.json'),'utf8'));
const crypto=require('crypto');
const ROOT=process.env.HF_REPO_ROOT||path.resolve(__dirname,'../..');
const SKEL=path.resolve(ROOT,'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1');
const OUTDIR=path.resolve(ROOT,'docs/human_capture/evidence/2026-10-11_cc_mainline_r1/skeleton_coarse');
fs.mkdirSync(OUTDIR,{recursive:true});
const PARAMS=JSON.parse(fs.readFileSync(path.join(SKEL,'prototype_params_v1.json'),'utf8'));

/* 收集某帧的全部 CONFIRMED_HUMAN 人簇 member（含 leveled xyz） */
function frameClusters(sid,model,fi){
  const session=D.load_session(path.join(ROOT,'captures/remote',sid));
  const det=createDetector(model); const gen=det.begin(sid);
  let out=null;
  for(let i=0;i<=fi;i++){
    const f=session.frames[i];
    const d=det.tick(S.make_frame_context({session_id:sid,session_generation:gen,frame_index:i,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta}));
    if(i===fi){
      const contract=det.engine.report().coordinate_contract;
      const lv=L.level_frame(f.xyzi,contract.R,contract.T,contract.already_leveled);
      const members=[];
      for(const c of (d._candidates||[])){
        if(c.classifier_decision!=='CONFIRMED_HUMAN')continue;
        const rows=Array.from(c.point_indices||[]);
        if(rows.length<PARAMS.node_min_points)continue;
        members.push({candidate_id:c.candidate_id,track_id:c.track_id||null,n:rows.length,
          receipt:{rows:rows.slice()},global_rows:rows.map(r=>`${c.candidate_id}:${fi}:${r}`),
          xyz:rows.map(r=>[lv[r*4],lv[r*4+1],lv[r*4+2]]),invalid_source_rows:[],
          centroid:[c.centroid.x,c.centroid.y,c.centroid.z]});
      }
      out={members,cloud:f.xyzi,n_points:f.n_points||(f.xyzi.length/4)};
    }
  }
  return out;
}

/* Python 提取真实节点（observe() 直调，绕开空 review visibility 门控——仅做离线粗骨架可视化，非验收） */
function extractNodes(memberObj){
  const driver=`
import json,sys,importlib.util
spec=importlib.util.spec_from_file_location('skel',r'${path.join(SKEL,'skeleton.py').replace(/\\/g,'/')}')
skel=importlib.util.module_from_spec(spec);spec.loader.exec_module(skel)
params=json.load(open(r'${path.join(SKEL,'prototype_params_v1.json').replace(/\\/g,'/')}',encoding='utf-8'))
import numpy as np
m=json.load(sys.stdin)
try:
    norm=skel.normalize(m,params)
    xyz=np.asarray(norm['xyz'])
    res={}
    for name,(lo,hi) in params['bands_m'].items():
        ids=np.flatnonzero((xyz[:,2]>=lo)&(xyz[:,2]<hi)).tolist()
        ob=skel.observe(norm,ids,params)
        res[name]={'valid':bool(ob['valid']),'support_n':int(ob.get('support_n',0)),'reason':ob.get('reason'),'xyz':ob.get('xyz')}
    print(json.dumps(res))
except Exception as e:
    print(json.dumps({'error':type(e).__name__+':'+str(e)[:200]}))
`;
  const r=cp.spawnSync('python',['-I','-c',driver],{input:JSON.stringify(memberObj),encoding:'utf-8',maxBuffer:1<<27});
  try{return JSON.parse((r.stdout||'').trim().split('\n').pop());}catch(e){return {error:'parse:'+e.message,stderr:(r.stderr||'').slice(0,200)};}
}

function render(job){
  const {sid,model,frame:fi}=job;
  const fc=frameClusters(sid,model,fi);
  if(!fc||!fc.members.length){console.log('SKIP',sid,fi,'no confirmed cluster');return;}
  const cloud=fc.cloud;const W=720,H=560,GAP=10,TOP=44;
  // 范围：用全部 Confirmed 簇质心 + 点
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
  const allIdx=[];for(const m of fc.members)allIdx.push(...m.receipt.rows);
  for(const i of allIdx){const x=cloud[i*4],y=cloud[i*4+1];if(!Number.isFinite(x))continue;if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}
  const cx=(x0+x1)/2,cy=(y0+y1)/2,half=Math.max((x1-x0)/2,(y1-y0)/2,0.9)+0.7;
  const projSide=(x,y,z)=>[W/2+(x-cx)/half*(W*0.44),H*0.9-Math.max(0,Math.min(2.4,z))/2.4*(H*0.82)];
  const ang=0.6,tilt=0.55;
  const proj3=(x,y,z)=>{const a=(x-cx)*Math.cos(ang)-(y-cy)*Math.sin(ang),b=(x-cx)*Math.sin(ang)+(y-cy)*Math.cos(ang);return [W/2+a/half*(W*0.44),H*0.84-(b*Math.cos(tilt)+z*Math.sin(tilt))/half*(H*0.58)];};
  const NODE_COL={UPPER_TORSO:'#ff9d5c',CHEST:'#ffd257',PELVIS_REGION:'#42e896',LOWER_REGION:'#5aa0e6'};
  const NODE_ORDER=['UPPER_TORSO','CHEST','PELVIS_REGION','LOWER_REGION'];
  let panels='';
  [['side','侧视 XZ',projSide],['persp','3D',proj3]].forEach(([kind,label,proj],pi)=>{
    const px=10+pi*(W+GAP);
    panels+=`<g transform="translate(${px},${TOP})">`;
    panels+=`<rect width="${W}" height="${H}" fill="#101a26" stroke="#293444"/>`;
    panels+=`<text x="8" y="20" fill="#9eb4cc" font-size="14" font-family="sans-serif">${label} · 粗骨架(区域中位点,非解剖关节)</text>`;
    // 参考地面线 z=0
    const g0=proj(cx-8,0,0),g1=proj(cx+8,0,0);
    panels+=`<line x1="${g0[0]}" y1="${g0[1]}" x2="${g1[0]}" y2="${g1[1]}" stroke="#3c5068" stroke-width="1" stroke-dasharray="4 3"/>`;
    // 人簇点
    for(const m of fc.members){
      let pts='';
      for(const r of m.receipt.rows){const x=cloud[r*4],y=cloud[r*4+1],z=cloud[r*4+2];if(!Number.isFinite(x))continue;const p=proj(x,y,z);pts+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="1.3"/>`;}
      panels+=`<g fill="#7f93a8" opacity="0.5">${pts}</g>`;
      // 提取节点
      const nodes=extractNodes(m);
      m._nodes=nodes;
      const validPts=NODE_ORDER.map(nm=>({nm,n:nodes[nm]})).filter(o=>o.n&&o.n.valid&&o.n.xyz);
      // 骨架连线（自上而下）
      if(validPts.length>=2){
        let path='';
        validPts.forEach((o,i)=>{const p=proj(...o.n.xyz);path+=(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)+' ';});
        panels+=`<path d="${path}" fill="none" stroke="#e2a6ff" stroke-width="2" opacity="0.8"/>`;
      }
      // 节点球
      for(const o of validPts){
        const p=proj(...o.n.xyz);
        panels+=`<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="7" fill="${NODE_COL[o.nm]}" stroke="#0b1017" stroke-width="1.5"/>`;
        panels+=`<text x="${(p[0]+9).toFixed(1)}" y="${(p[1]+4).toFixed(1)}" fill="${NODE_COL[o.nm]}" font-size="12" font-weight="bold" font-family="sans-serif">${o.nm.replace('_REGION','')}(${o.n.support_n})</text>`;
      }
      // 标签
      const pc=proj(...m.centroid);
      panels+=`<text x="${(pc[0]-10).toFixed(1)}" y="16" fill="#dce8f5" font-size="12" font-family="sans-serif">${m.candidate_id} n=${m.n}${m.track_id?' '+m.track_id:''}</text>`;
    }
    panels+=`</g>`;
  });
  const wTop=10+2*(W+GAP),Htot=TOP+H+14;
  const anyValid=fc.members.some(m=>m._nodes&&Object.entries(m._nodes).some(([k,v])=>v.valid&&k!=='HEAD'));
  const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${wTop+10}" height="${Htot}" viewBox="0 0 ${wTop+10} ${Htot}">`+
    `<rect width="100%" height="100%" fill="#0b1017"/>`+
    `<text x="12" y="22" fill="#dce8f5" font-size="15" font-weight="bold" font-family="sans-serif">${esc(sid)} · f${fi} · 可验证粗骨架(胸/骨盆/下身区域中位点)</text>`+
    `<text x="12" y="40" fill="${anyValid?'#42e896':'#ef6f79'}" font-size="12" font-family="sans-serif">标定:UNCALIBRATED · 节点=点支撑中位数 非解剖关节 · HEAD不显示(需人工HEAD_CONFIRMED) · 上身跨度&gt;0.8m节点按冻结参数拒绝显示</text>`+
    panels+`</svg>`;
  const fn=`skeleton_${sid}_f${fi}.svg`;
  fs.writeFileSync(path.join(OUTDIR,fn),svg);
  const stat=fc.members.map(m=>({c:m.candidate_id,n:m.n,validNodes:NODE_ORDER.filter(k=>m._nodes&&m._nodes[k]&&m._nodes[k].valid),reject:NODE_ORDER.filter(k=>m._nodes&&m._nodes[k]&&!m._nodes[k].valid).map(k=>k+':'+(m._nodes[k].reason||''))}));
  console.log('WROTE',fn,JSON.stringify(stat));
}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
const jobs=[
  {sid:'cap_20261010_175429',model:'xgb69_candidate',frame:100},
  {sid:'cap_20261010_180557',model:'xgb69_candidate',frame:200},
  {sid:'cap_20261010_180235',model:'xgb69_candidate',frame:60}
];
for(const j of jobs){try{render(j);}catch(e){console.error('FAIL',j.sid,j.frame,e.message);}}
console.log('SKELETON_COARSE_DONE -> '+OUTDIR);
