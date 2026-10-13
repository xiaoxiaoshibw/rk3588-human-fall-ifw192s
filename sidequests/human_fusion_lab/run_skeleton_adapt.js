'use strict';
/* 骨架可观测性打通（CC 主线，离线只读探测 + 新证据，不修 skeleton、不修 fusion）。
 * 思想：把 fusion 九会话中"已确认的人候选/track"的真实成员点，按 skeleton.py 的
 * normalize() 成员格式适配（rows/global_rows/xyz/invalid_source_rows），评估固定站立 Z 带
 * 在真实点云上的节点可观测性（UPPER_TORSO/CHEST/PELVIS/LOWER；HEAD 需人工 HEAD_CONFIRMED，不自主）。
 * honesty：只用 GT-reviewed 会话的人簇做"正例可观测性"探测；泛化/解剖精度 = UNKNOWN。 */
const fs=require('fs'),path=require('path');
const cp=require('child_process');
const D=require('./core/data_loader'),S=require('./core/schema'),L=require('./core/leveling');
const {createDetector}=require('./detector');
const {objects,rawMap}=require('./export');
const crypto=require('crypto');
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'results/AUDIT.json'),'utf8'));
const ROOT=process.env.HF_REPO_ROOT||path.resolve(__dirname,'../..');
const SKEL_DIR=path.resolve(ROOT,'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1');
const OUTDIR=path.resolve(ROOT,'docs/human_capture/evidence/2026-10-11_cc_mainline_r1/skeleton_adapt');
fs.mkdirSync(OUTDIR,{recursive:true});
const PARAMS=JSON.parse(fs.readFileSync(path.join(SKEL_DIR,'prototype_params_v1.json'),'utf8'));

/* 从 fusion 确认人簇收集 member（skeleton.normalize 输入形态）。
 * 仅取 track_confirmed 或 CONFIRMED_HUMAN 的人候选；点用 leveled XYZ。 */
function collectMembers(sid,model){
  const rec=audit.sessions.find(r=>r.sid===sid);
  const session=D.load_session(path.join(ROOT,'captures/remote',sid));
  const det=createDetector(model); const gen=det.begin(sid);
  let doc=null; const d0=audit.docs[sid];
  if(rec.eligible&&d0&&d0.session_id===sid&&d0.review_status==='reviewed'){
    const buf=fs.readFileSync(rec.gt_path);
    if(crypto.createHash('sha256').update(buf).digest('hex')===rec.gt_sha256)doc=d0;
  }
  const members=[];
  for(let fi=0;fi<session.frames.length;fi++){
    const f=session.frames[fi];
    const d=det.tick(S.make_frame_context({session_id:sid,session_generation:gen,frame_index:fi,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta}));
    const contract=det.engine.report().coordinate_contract;
    const lv=L.level_frame(f.xyzi,contract.R,contract.T,contract.already_leveled);
    const personGtIds=new Set();
    if(doc){for(const g of (objects(doc,fi,rawMap(f.xyzi))||[]))if(g.class_name==='PERSON')personGtIds.add(g.id);}
    for(const c of (d._candidates||[])){
      const isPerson=c.classifier_decision==='CONFIRMED_HUMAN';
      if(!isPerson)continue;
      const rows=Array.from(c.point_indices||[]);
      if(rows.length<PARAMS.node_min_points)continue;
      const xyz=rows.map(i=>[lv[i*4],lv[i*4+1],lv[i*4+2]]);
      members.push({
        sid,model,frame_index:fi,candidate_id:c.candidate_id,track_id:c.track_id||null,
        track_confirmed:!!c.track_confirmed,decision:c.classifier_decision,n:rows.length,
        timestamp:f.timestamp,
        receipt:{rows:rows.slice()},
        global_rows:rows.map(r=>c.track_id?`${c.track_id}:${fi}:${r}`:`${c.candidate_id}:${fi}:${r}`),
        xyz,
        invalid_source_rows:[],
        gt_present:personGtIds.size>0
      });
    }
  }
  return members;
}

/* 评估单 member 的 Z 带节点可观测性（只用固定带，不自主 HEAD）。 */
function evalObservability(m){
  const z=m.xyz.map(p=>p[2]).filter(Number.isFinite);
  if(z.length<PARAMS.node_min_points)return {observable:false,reason:'INSUFFICIENT_POINTS',n:z.length};
  const zmin=Math.min(...z),zmax=Math.max(...z),span=zmax-zmin;
  const bands={};
  for(const name of ['UPPER_TORSO','CHEST','PELVIS_REGION','LOWER_REGION']){
    const [lo,hi]=PARAMS.bands_m[name];
    const cnt=z.filter(v=>v>=lo&&v<hi).length;
    bands[name]={count:cnt,ok:cnt>=PARAMS.node_min_points};
  }
  const observable=bands.UPPER_TORSO.ok||bands.CHEST.ok||bands.PELVIS_REGION.ok||bands.LOWER_REGION.ok;
  return {observable,reason:observable?'Z_BAND_SUPPORT':'NO_BAND_REACH_MIN_POINTS',
    n:z.length,z_min:+zmin.toFixed(3),z_max:+zmax.toFixed(3),z_span:+span.toFixed(3),bands};
}

/* Python 侧跑 skeleton 真实节点（对可观测 member 子样本），传 member JSON。 */
function runPythonNodes(membersFile,outFile){
  const py=path.join(SKEL_DIR,'skeleton.py');
  const driver=`
import json,sys,importlib.util
spec=importlib.util.spec_from_file_location('skel',r'${py.replace(/\\/g,'/')}')
skel=importlib.util.module_from_spec(spec);spec.loader.exec_module(skel)
params=json.load(open(r'${path.join(SKEL_DIR,'prototype_params_v1.json').replace(/\\/g,'/')}',encoding='utf-8'))
members=json.load(open(r'${membersFile.replace(/\\/g,'/')}',encoding='utf-8'))
out=[]
for m in members:
    review={} # 非 HEAD 槽用固定 Z 带，无需 review；HEAD 留 BLOCKED
    try:
        norm=skel.normalize(m,params)
        nodes=skel.nodes(norm,review,params)
        rec={'candidate_id':m['candidate_id'],'track_id':m['track_id'],'frame_index':m['frame_index'],'n':m['n']}
        for k,v in nodes.items():
            rec[k]={'valid':v['valid'],'support_n':v.get('support_n',0),'reason':v.get('reason'),'xyz':v.get('xyz')}
        out.append(rec)
    except Exception as e:
        out.append({'candidate_id':m.get('candidate_id'),'frame_index':m.get('frame_index'),'error':type(e).__name__+':'+str(e)[:120]})
json.dump(out,open(r'${outFile.replace(/\\/g,'/')}','w',encoding='utf-8'),ensure_ascii=False)
`;
spawnPython(driver,outFile);
}
function spawnPython(driver,outFile){
  const r=cp.spawnSync('python',['-I','-c',driver],{encoding:'utf-8',maxBuffer:1<<28});
  if(r.status!==0){fs.writeFileSync(outFile,JSON.stringify({error:'python failed',stderr:(r.stderr||'').slice(0,500)},null,1));}
}

function main(){
  const report={generated_at:new Date().toISOString(),params_sha:crypto.createHash('sha256').update(JSON.stringify(PARAMS)).digest('hex'),
    scope:'fusion confirmed-person clusters -> skeleton Z-band node observability probe; read-only; HEAD blocked (needs manual HEAD_CONFIRMED); generalization UNKNOWN',
    sessions:[]};
  const jobs=[['cap_20261010_175429','xgb69_candidate'],['cap_20261010_180557','xgb69_candidate'],['cap_20261010_180235','xgb69_candidate']];
  for(const [sid,model] of jobs){
    const members=collectMembers(sid,model);
    const sess={sid,model,confirmed_person_candidates:members.length,members_observability:[]};
    let obsN=0;const sample=[];
    for(const m of members){
      const ob=evalObservability(m);
      sess.members_observability.push({frame:m.frame_index,candidate:m.candidate_id,n:m.n,z_span:ob.z_span??null,observable:ob.observable,reason:ob.reason,bands:ob.bands,gt_present:m.gt_present});
      if(ob.observable){obsN++;if(sample.length<40)sample.push(m);}
    }
    sess.observable_count=obsN;
    sess.observable_ratio=members.length?+(obsN/members.length).toFixed(3):0;
    // 保存子样本供 python 真实节点
    const memFile=path.join(OUTDIR,`members_${sid}.json`);
    fs.writeFileSync(memFile,JSON.stringify(sample));
    const nodeFile=path.join(OUTDIR,`nodes_${sid}.json`);
    runPythonNodes(memFile,nodeFile);
    sess.python_nodes_file=`nodes_${sid}.json`;
    // 汇总 python 结果
    try{
      const nodes=JSON.parse(fs.readFileSync(nodeFile,'utf8'));
      const stat={run:nodes.length,with_chest:nodes.filter(r=>r.CHEST&&r.CHEST.valid).length,with_upper:nodes.filter(r=>r.UPPER_TORSO&&r.UPPER_TORSO.valid).length,
        with_pelvis:nodes.filter(r=>r.PELVIS_REGION&&r.PELVIS_REGION.valid).length,with_lower:nodes.filter(r=>r.LOWER_REGION&&r.LOWER_REGION.valid).length,
        errors:nodes.filter(r=>r.error).length};
      sess.python_node_stats=stat;
    }catch(e){sess.python_node_stats={error:e.message};}
    report.sessions.push(sess);
    console.log(`SKELETON ${sid} ${model}: confirmed=${members.length} observable=${obsN} (${sess.observable_ratio}) chest=${sess.python_node_stats.with_chest||'?'} upper=${sess.python_node_stats.with_upper||'?'} pelvis=${sess.python_node_stats.with_pelvis||'?'}`);
  }
  fs.writeFileSync(path.join(OUTDIR,'skeleton_observability_report.json'),JSON.stringify(report,null,1));
  console.log('SKELETON_ADAPT_DONE -> '+OUTDIR);
}
main();
