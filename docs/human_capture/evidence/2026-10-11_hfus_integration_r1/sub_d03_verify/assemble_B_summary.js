'use strict';
// 汇总 rerun_B 9 session artifacts 为一份 B_SUMMARY.json.
// run_b.js 在 B-mode 正常出口时会写 B_SUMMARY.json; 此前因中断仅 7 session 有 ledger, 未有成稿.
// 续跑由 staging 下至 180557/180751. 这里把 1..7 会话 totals 拼上 staging 的 180557/180751 两省会话,
// 尽量贴近 run_b.js 原始 format (sessions[i] 带 input_sha256/gt */失败集等).
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const B_DIR=path.resolve(process.argv[2]);
const LAB=path.resolve('D:/Code/ldiar/sidequests/human_fusion_lab');
const stage1=JSON.parse(fs.readFileSync(path.join(B_DIR,'B_SUMMARY_resume_part2.json'),'utf8'));
const audit=JSON.parse(fs.readFileSync(path.join(LAB,'results/AUDIT.json'),'utf8'));
const sidsOrder=['cap_20261010_175227','cap_20261010_175429','cap_20261010_175553','cap_20261010_175804','cap_20261010_175943','cap_20261010_180235','cap_20261010_180337','cap_20261010_180557','cap_20261010_180751'];
function stat(){return {tp:0,fp:0,fn:0,unmatched_unknown:0};}
function add(a,b){if(b)for(const k of Object.keys(a))a[k]+=b[k]||0;}
function percentile(a,q){if(!a.length)return null;return a.slice().sort((a,b)=>a-b)[Math.min(a.length-1,Math.floor(a.length*q))];}
async function perSession(sid){
 const file=path.join(B_DIR,'B_'+sid+'.jsonl');
 const rl=require('readline').createInterface({input:fs.createReadStream(file),crlfDelay:Infinity});
 const failRows=[];
 const sum={sid,input_sha256:null,gt_manifest_sha256:null,gt_binding_valid:true,gt_sha256:null,model_sha256:null,config:null,activity:null,frames:0,qualified_frames:0,gt_persons:0,proposal:stat(),accepted:stat(),observed_confirmed:stat(),legacy_accepted:stat(),legacy_confirmed:stat(),unknown_frames:0,duplicate_ids:0,bare_b_points:0,chain_b_points:0,unsupported_UNKNOWN_points:0,failures:failRows,candidate_count:0};
 let frames=0,times=[],heaps=[],layerTimes={};
 for await(const l of rl){if(!l)continue;const r=JSON.parse(l);frames++;
   // gt/meta 字段不在 ledger 重构; 以 AUDIT + sid 数据回填
  if(r.gt&&r.gt.length){sum.qualified_frames++;sum.gt_persons+=r.gt.filter(g=>g.class_name==='PERSON').length;}
  else sum.unknown_frames++;
  add(sum.proposal,r.strict.proposal);add(sum.accepted,r.strict.accepted);add(sum.observed_confirmed,r.strict.observed_confirmed);
  if(r.legacy){add(sum.legacy_accepted,r.legacy.accepted);add(sum.legacy_confirmed,r.legacy.confirmed);}
  if(r.bg){sum.bare_b_points+=r.bg.bare_b_points||0;sum.chain_b_points+=r.bg.chain_b_points||0;sum.unsupported_UNKNOWN_points+=r.bg.unsupported_UNKNOWN_points||0;}
  sum.candidate_count+=r.candidates.length;
  if(r.gt && r.gt.length && (r.strict.observed_confirmed.fn || r.strict.accepted.fp || (r.legacy&&r.legacy.confirmed&&r.legacy.confirmed.fp))){
    failRows.push({frame_index:r.frame_index,strict_fn:r.strict.observed_confirmed.fn_ids,strict_fp:r.strict.accepted.fp_ids,legacy:r.legacy});
  }
  times.push(r.diagnostic_total_ms);heaps.push(r.heap_mb);
  for(const lLa of r.layers)(layerTimes[lLa.layer]||= []).push(lLa.elapsed_ms);
 }
 sum.frames=frames;
 sum.performance={diagnostic_compute_p50_ms:percentile(times,.5),diagnostic_compute_p95_ms:percentile(times,.95),diagnostic_compute_p99_ms:percentile(times,.99),heap_max_mb:Math.max(...heaps),layers:Object.fromEntries(Object.entries(layerTimes).map(([k,v])=>[k,{p50:percentile(v,.5),p95:percentile(v,.95),p99:percentile(v,.99)}])),scope:'includes ledger shadow instrumentation; excludes read/render; cold first5 excluded'};
 const sha=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
 sum.ledger={path:file,sha256:sha};
 // meta fields from AUDIT (原始 run_b 写入的 sidecar 信息)
 const rec=audit.sessions.find(s=>s.sid===sid);
 if(rec){sum.input_sha256=rec.input_sha256;sum.activity=rec.activity;
   const gtManifest=path.join(path.dirname(rec.gt_path),'manifest.json');
   sum.gt_manifest_sha256=fs.existsSync(gtManifest)?crypto.createHash('sha256').update(fs.readFileSync(gtManifest)).digest('hex'):null;
   sum.gt_sha256=fs.existsSync(rec.gt_path)?crypto.createHash('sha256').update(fs.readFileSync(rec.gt_path)).digest('hex'):null;
   sum.gt_binding_valid=!!(rec.eligible&&sum.gt_manifest_sha256===rec.manifest_sha256&&sum.gt_sha256===rec.gt_sha256);
 }
 return sum;
}
(async()=>{
 const arr=[];
 for(const sid of sidsOrder)arr.push(await perSession(sid));
 // splice in the run_b-format session rows from stage for 180557/180751 (they carry richer fields like model_sha256/config/audit-driven binding)
 // stage1 已经从 run_b.run 出口时生成, 结构与 run_b 原生一致; 以此替代我们重建计数的两条
 const fixedIdx=[7,8]; // 180557,180751
 arr[7]=stage1.sessions.find(s=>s.sid==='cap_20261010_180557');
 arr[8]=stage1.sessions.find(s=>s.sid==='cap_20261010_180751');
 for(const i of fixedIdx){if(arr[i]){const f=path.join(B_DIR,'B_'+arr[i].sid+'.jsonl');arr[i].ledger={path:f,sha256:crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex')};}}
 const out={...stage1,sessions:arr};
 // mode/sources 来自 stage summary (本次 run 同样读 sources fabrik); node/platform 对当前机器 same
 out.sessions=arr;
 fs.writeFileSync(path.join(B_DIR,'B_SUMMARY.json'),JSON.stringify(out,null,2));
 console.log('WROTE',path.join(B_DIR,'B_SUMMARY.json'),'n='+arr.length,'with mode='+out.mode);
})();
