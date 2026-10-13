'use strict';
// Read-only R2 reuse: never invoke historical main/prepare/run entry points.
const fs=require('fs'), path=require('path'), crypto=require('crypto'), readline=require('readline');
const OUT=__dirname, ROOT=path.resolve(OUT,'../../../..');
const R2=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_hrsemshadow_r2');
const digest=b=>crypto.createHash('sha256').update(b).digest('hex');
function hash(p){const fd=fs.openSync(p,'r'),h=crypto.createHash('sha256'),b=Buffer.alloc(4<<20);try{let n;while((n=fs.readSync(fd,b,0,b.length,null)))h.update(b.subarray(0,n));}finally{fs.closeSync(fd);}return h.digest('hex');}
function need(ok,code,loc){if(!ok)throw Error(code+': '+loc);}
function save(p,v){fs.writeFileSync(p,JSON.stringify(v)+'\n',{flag:'wx'});}
function read(p){return JSON.parse(fs.readFileSync(p,'utf8'));}
const windows=[
 ['cap_20261008_114205','REF_SHADOW',112,131,'development','80a4bd6fe3a4476fa099b053d74de8be'],
 ['cap_20261008_114254','REF_SHADOW',125,144,'development','abe747de448a4974ad9e7a6e1c70bac4'],
 ['cap_20261008_114340','V2',130,149,'validation','9d389dc38cb84343b66f97db2198dbbb'],
 ['cap_20261008_114422','V2',87,106,'hard_case','24a7ba629d904f63af03ecdaadb9a9ec'],
 ['cap_20261008_114819','WORKSPACE',132,151,'empty_control','6e87c6e4146f48ba84e24c801820e5e1'],
 ['cap_20261008_114819','V2_IDENTITY',132,151,'empty_control','6e87c6e4146f48ba84e24c801820e5e1']];
async function loadAuthority(){
 need(hash(path.join(R2,'delivery_manifest.json'))==='f853ae60e8b0fb1c4714502a30a3e1fde877927609b9fa0a85735b1d703e537f','R2_DELIVERY_SHA','manifest');
 const manifest=read(path.join(R2,'delivery_manifest.json'));
 for(const [p,v] of Object.entries(manifest.files))need(hash(path.join(R2,p))===v.sha256,'R2_DELIVERY_SHA',p);
 need(hash(path.join(R2,'review_binding.js'))==='70c04bffdb5d94c52c499364798b0f9ee8288a023e7476ffc6eb0d5d38ae8623','R2_TOOL_SHA','review_binding.js');
 // Protect transitive imports before loading the trusted tool.
 const bp=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/pass3/binding.json');
 need(hash(bp)==='2f0f3aaaf6b6c62aedcf5b02de30539da13cc0afce324d7dc4fba44ccdb26416','BINDING_SHA',bp);
 for(const [p,h] of Object.entries(read(bp).pipeline.files))need(hash(path.join(ROOT,p))===h,'IMPORT_SHA',p);
 const B={...require(path.join(R2,'review_binding.js')),R:require(path.join(ROOT,'pc_apps/human_replay/registration.js'))},a=await B.authority();
 need(hash(path.join(B.R1,'pass3/frames.jsonl'))==='1fd51da3a0d04223c85e26f27c726dd599c171e1e4431fc97d896717d566a4db','FRAME_AUTHORITY_SHA','frames');
 return {B,a,manifest};
}
function member(B,a,c){
 const receipt=B.receipt(a,c),src=B.source(a,c.sid),f=src.meta.frames[c.ordinal];
 need(c.stamp_sec===f.stamp_sec&&c.stamp_nanosec===f.stamp_nanosec,'STAMP_MISMATCH',c.id);
 need(c.global_rows.length===c.rows.length&&c.global_rows.every((r,i)=>r===f.offset_points+c.rows[i]),'GLOBAL_ROWS_MISMATCH',c.id);
 const xyz=[],invalid=[];
 for(const row of c.rows){
  const at=(f.offset_points+row)*28;let q=[0,1,2].map(j=>src.raw.readFloatLE(at+j*4));
  if(!q.every(Number.isFinite)||q.every(v=>v===0))invalid.push(row);
  for(const [r,t] of [[src.tf.R.flat(),src.tf.t],...(src.b.transform?[[src.b.transform.rotation_row_major,src.b.transform.translation_m]]:[])])
   q=[0,1,2].map(j=>Math.fround(r[j*3]*q[0]+r[j*3+1]*q[1]+r[j*3+2]*q[2]+t[j]));
  xyz.push(q.map(v=>Number.isFinite(v)?v:null));
 }
 return {receipt,global_rows:c.global_rows,xyz,invalid_source_rows:invalid,
  machine_identity:c.reference_assignment,semantic_diagnostic:c.semantic.label||c.semantic.status||'UNKNOWN',
  label:'UNREVIEWED',person_id:null,reviewer:null};
}
async function prepare(){
 const {B,a,manifest}=await loadAuthority(),frames=[],keys=new Map();
 for(const [sid,branch,lo,hi,split,job] of windows){
  const b=a.binding.sessions.find(s=>s.sid===sid);need(b.job===job,'JOB_MISMATCH',sid);
  for(let ordinal=lo;ordinal<=hi;ordinal++){
   const id=[sid,branch,ordinal].join('/');const f={id,sid,branch,ordinal,split,job,clusters:[],status:'BLOCKED_GT'};
   frames.push(f);keys.set(id,f);
  }
 }
 // Pre-register before reconstructing any node; preserve even no-cluster frames.
 const split={version:1,unique_raw_frames:100,branch_rows:120,observed_previously:true,
  blind_test:false,windows:windows.map(w=>({sid:w[0],branch:w[1],lo:w[2],hi:w[3],split:w[4],job:w[5]})),frames:frames.map(f=>({...f}))};
 const splitPath=path.join(OUT,'split_manifest.json');
 if(fs.existsSync(splitPath))need(B.R.identity(read(splitPath))===B.R.identity(split),'PREREGISTRATION_DRIFT','split');
 else save(splitPath,split);
 const registration=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/registration_results.json');
 need(hash(registration)===a.binding.previous_inputs['registration_results.json'],'DIAGNOSTIC_SHA','registration_results');
 for(const d of read(registration)){
  const b=a.binding.sessions.find(s=>s.sid===d.sid);
  need(d.leveling_job===b.job&&B.R.identity(d.transform)===B.R.identity(b.transform),'DIAGNOSTIC_MATRIX_MISMATCH',d.sid);
 }
 for await(const line of readline.createInterface({input:fs.createReadStream(path.join(B.R1,'pass3/frames.jsonl')),crlfDelay:Infinity})){
  if(!line)continue;const old=JSON.parse(line),f=keys.get([old.sid,old.mode,old.ordinal].join('/'));if(!f)continue;
  need(!f.source_frame,'DUPLICATE_FRAME',f.id);const src=B.source(a,f.sid),rawf=src.meta.frames[f.ordinal];
  need(rawf.seq===old.seq&&rawf.offset_points===old.source_offset_points&&rawf.count_points===old.counts.source,'FRAME_SOURCE_MISMATCH',f.id);
  need(rawf.stamp_sec===old.stamp_sec&&rawf.stamp_nanosec===old.stamp_nanosec,'FRAME_STAMP_MISMATCH',f.id);
  f.source_frame=rawf;f.invalid_source_rows=old.invalid_source_rows;f.counts=old.counts;f.small_components=old.small_components;
  f.coordinate_id=B.R.identity({source:src.b.source,leveling:src.b.leveling_sha,transform:src.b.transform,branch:f.branch});
 }
 for(const c of a.clusters.values()){const f=keys.get(B.key(c));if(f)f.clusters.push(member(B,a,c));}
 fs.mkdirSync(path.join(OUT,'frames'));
 const entries=[];let n=0,points=0,invalid=0;
 for(let i=0;i<frames.length;i++){
  const f=frames[i];need(f.source_frame,'FRAME_MISSING',f.id);
  need(f.clusters.length===f.counts.candidates,'CANDIDATE_COUNT',f.id);
  const name='frames/f'+i+'.json';save(path.join(OUT,name),f);
  entries.push({id:f.id,file:name,sha256:hash(path.join(OUT,name)),sid:f.sid,branch:f.branch,ordinal:f.ordinal,split:f.split,
   seq:f.source_frame.seq,clusters:f.clusters.map(c=>({id:c.receipt.id,n:c.receipt.rows.length,member_sha256:c.receipt.member_sha256}))});
  for(const c of f.clusters){n++;points+=c.receipt.rows.length;invalid+=c.invalid_source_rows.length;}
 }
 const sources={};for(const sid of new Set(windows.map(w=>w[0]))){const s=B.source(a,sid);sources[sid]={binding:s.b,tf:s.tf,
  layout:s.meta.point_layout,time_domain:s.meta.time_domain,human_annotations:s.meta.human_annotations||[],source_meta_annotations_count:(s.meta.human_annotations||[]).length};}
 save(path.join(OUT,'input_manifest.json'),{version:1,authority:B.PINS,r2_delivery_sha256:hash(path.join(R2,'delivery_manifest.json')),
  r2_tool_sha256:hash(path.join(R2,'review_binding.js')),binding:a.binding,registration_results_sha256:hash(registration),
  sources,entries,summary:{unique_raw_frames:100,branch_rows:120,clusters:n,member_points:points,invalid_member_rows:invalid},
  trust:'trusted source code pins + independent raw rebuild; labels not established by receipt'});
 save(path.join(OUT,'identity_gt.json'),{kind:'hr_skeleton_offline_gt',schema:1,source:'unreviewed',reviewer:null,created_iso:null,records:[],status:'BLOCKED_GT'});
 save(path.join(OUT,'node_review.json'),{source:'unreviewed',records:[],status:'BLOCKED_GT'});
 console.log('INPUT_BOUND',JSON.stringify({frames:frames.length,clusters:n,points,invalid,source_annotations:Object.values(sources).map(s=>s.source_meta_annotations_count)}));
}
function checkNodes(r,valid){
 need(r.nodes&&typeof r.nodes==='object','NODE_REVIEW_REQUIRED',r.id);
 for(const name of ['HEAD','UPPER_TORSO','CHEST','PELVIS_REGION','LOWER_REGION','LOWER_A','LOWER_B']){
  const v=r.nodes[name];need(v&&['VISIBLE','INVISIBLE','UNCERTAIN'].includes(v.visibility),'NODE_VISIBILITY_REQUIRED',r.id+'/'+name);
  need(Array.isArray(v.region_rows)&&new Set(v.region_rows).size===v.region_rows.length&&v.region_rows.every(row=>valid.has(row)),'REGION_ROWS_INVALID',r.id+'/'+name);
  need(v.visibility!=='VISIBLE'||v.region_rows.length>0,'VISIBLE_REGION_REQUIRED',r.id+'/'+name);
  need(typeof v.reason==='string'&&v.reason.trim(),'VISIBILITY_REASON_REQUIRED',r.id+'/'+name);
 }
}
async function validate(file){
 const {B,a}=await loadAuthority(),gt=read(file),input=read(path.join(OUT,'input_manifest.json'));
 need(gt.kind==='hr_skeleton_offline_gt'&&gt.schema===1,'SIDECAR_SCHEMA','root');
 need(gt.input_binding===digest(fs.readFileSync(path.join(OUT,'input_manifest.json'))),'INPUT_BINDING_MISMATCH','root');
 need(gt.source==='human'&&typeof gt.reviewer==='string'&&gt.reviewer.trim()&&!/synthetic|test only/i.test(gt.reviewer)&&gt.created_iso,'REAL_REVIEW_REQUIRED','root');
 need(Array.isArray(gt.records)&&gt.records.length,'EMPTY_REVIEW','root');
 const allowed=new Set(input.entries.flatMap(e=>e.clusters.map(c=>c.id)));
 const seen=new Set(),personFrames=new Set();
 for(const r of gt.records){
  need(allowed.has(r.id),'OUTSIDE_PREREGISTRATION',r.id);need(!seen.has(r.id),'DUPLICATE_ID',r.id);seen.add(r.id);
  B.validate({kind:'hr_sem_shadow_gt',schema:1,binding_version:2,source:'human',reviewer:gt.reviewer,created_iso:gt.created_iso,
   authority:B.PINS,binding:a.binding,clusters:[r],points:[]},a);
  need(typeof r.track_epoch==='string'&&r.track_epoch.trim()&&r.continuity==='human_confirmed','CONTINUITY_REQUIRED',r.id);
  if(r.label==='PERSON'){
   const personFrame=[r.sid,r.mode,r.ordinal,r.person_id].join('/');
   need(!personFrames.has(personFrame),'DUPLICATE_PERSON_FRAME',r.id);personFrames.add(personFrame);
  }
  const c=a.clusters.get(r.id),m=member(B,a,c),valid=new Set(c.rows.filter(row=>!m.invalid_source_rows.includes(row)));
  checkNodes(r,valid);
 }
 console.log('SIDECAR_BOUND',JSON.stringify({records:seen.size,label_truth:'requires actual human review; validation proves binding only'}));
}
module.exports={loadAuthority,member,validate,checkNodes,windows};
if(require.main===module)(process.argv[2]==='validate'?validate(process.argv[3]):prepare()).catch(e=>{console.error(e.stack);process.exitCode=1;});
