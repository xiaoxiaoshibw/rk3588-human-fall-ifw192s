'use strict';
/* Isolated same-source diagnostic. Existing P/REF/v2 functions only. No loader changes. */
const fs=require('fs'),path=require('path');
const ROOT=path.resolve(__dirname,'../../../..');
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib'));
const REG=require(path.join(ROOT,'pc_apps/human_replay/registration'));
const out=process.argv[2]?path.resolve(process.argv[2]):null;
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const old=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_02_r1');
const ps=path.join(ROOT,'sidequests/human_fusion_lab_next/pointset/r01');
const meta=sid=>read(path.join(ROOT,'captures/remote',sid,'meta.json'));
function cloud(sid,R,t,alignment){
 const m=meta(sid),b=fs.readFileSync(path.join(ROOT,'captures/remote',sid,'points.bin'));
 if(b.length!==m.total_points*28)throw Error('source size');
 return m.frames.map(f=>{const values=[],ids=[];
  for(let k=0;k<f.count_points;k++){const o=(f.offset_points+k)*28;
   let q=[0,1,2].map(i=>b.readFloatLE(o+i*4));const intensity=b.readFloatLE(o+12);
   if(!q.every(Number.isFinite)||!Number.isFinite(intensity)||q.every(v=>v===0))continue;
   const d=Math.hypot(...q);if(d<PL.PIPE.range_min_m||d>PL.PIPE.range_max_m)continue;
   q=R.map((r,i)=>r.reduce((s,v,j)=>s+v*q[j],0)+t[i]);
   if(alignment){const a=alignment,R2=[a.R.slice(0,3),a.R.slice(3,6),a.R.slice(6,9)];q=R2.map((r,i)=>r.reduce((s,v,j)=>s+v*q[j],0)+a.t[i]);}
   values.push(...q,intensity);ids.push(k);
  }
  return {buf:Float32Array.from(values),ids,frame:f};
 });
}
function subset(input,fg){
 const ids=[];let j=0;
 for(let k=0;k<input.buf.length&&j<fg.length;k+=4){
  if([0,1,2,3].every(c=>input.buf[k+c]===fg[j+c])){ids.push(input.ids[k/4]);j+=4;}
 }
 if(j!==fg.length)throw Error('ordered source binding');return ids;
}
function execute(sid,refsid,R,t,refR,refT,align,note){
 const input=cloud(sid,R,t),refs=cloud(refsid,refR,refT,align);
 const split={FIT:[],CALIBRATION:[],HOLDOUT:[]};refs.forEach((_,i)=>split[['FIT','CALIBRATION','HOLDOUT'][i%3]].push(i));
 const map=PL.build_reference_map(split.FIT.map(i=>refs[i].buf),{drop_ground:false});
 const keys=new Map([...map.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
 const fd=fs.openSync(path.join(out,sid+'_ab_indices.jsonl'),'wx');
 const roi=read(path.join(ps,'output/catalog.json')).roi_xy;
 try{
  for(let i=0;i<input.length;i++){
   // Existing P baseline is full-recording static. Keep it explicitly retrospective/noncausal.
   // Qualified diagnostics use only the already observed bounded prefix, never a permanent person map.
   const causal=PL.build_static_map(input.slice(Math.max(0,i-10),i).map(c=>c.buf));
   const c=input[i],arms={A_P:PL.extract_foreground(c.buf,causal),B_FROZEN:PL.extract_foreground(c.buf,keys),
                         C_V2_DIAGNOSTIC:PL.extract_foreground_fused(c.buf,keys,causal)};
   const results=Object.fromEntries(Object.entries(arms).map(([k,v])=>[k,subset(c,v.fg_xyzi)]));
   fs.writeSync(fd,JSON.stringify({sid,frame:i,t:c.frame.stamp_sec+c.frame.stamp_nanosec*1e-9,source_count:c.frame.count_points,
       domain_source_indices:c.ids,arms:results,roi,body_parts:'UNKNOWN',human_confirmed:null,events:null})+'\n');
  }
 }finally{fs.closeSync(fd);}
 const empty=[];
 for(const i of split.HOLDOUT){const fg=PL.extract_foreground_fused(refs[i].buf,keys,null);empty.push({frame:i,fg:fg.n_fg});}
 const report={sid,reference:refsid,split,reference_keys:keys.size,frames:input.length,R,t,refR,refT,alignment:align,
  coordinate_frame:'COMMON_SOURCE_LEVELED',units:'m',source:REG.sessionBinding(ROOT,sid),reference_source:REG.sessionBinding(ROOT,refsid),
  PIPE:{...PL.PIPE},roi_status:'USER_APPROXIMATION_PENDING_COORDINATE_REVIEW; no expansion',
  A_context:'existing extract_foreground; causal ephemeral previous <=10 frames; NOT identical to production whole-recording map',
  B_context:'empty FIT-only immutable reference; threshold existing 0.12 m; HOLDOUT unused in map or tuning',
  C_context:'existing extract_foreground_fused; DIAGNOSTIC_ONLY; fusionKeys gate not bypassed in any official consumer',
  causality:'No future action frames; reference recording is offline calibration. No action permanently self-modeled.',
  empty_holdout:empty,registration_note:note,physical_scene_review:'BLOCKED',
  input_sha_binding:REG.codeBinding(ROOT),ground_rule:'Common diagnostic -0.25m workspace for all arms; no z<0.1m blanket crop. Thin-ground identity UNKNOWN.'};
 fs.writeFileSync(path.join(out,sid+'_ab_manifest.json'),JSON.stringify(report,null,2),{flag:'wx'});
 console.log('AB',sid,input.length,'frames',keys.size,'reference keys');
}
module.exports={cloud,subset};
if(require.main===module){const ground=PL.PIPE.ground_keep_below_m;
try{
 PL.PIPE.ground_keep_below_m=-.25; // isolated process only; source/default remains unchanged.
 const m=read(path.join(old,'cap_20261013_094333_foreground.json'));
 const ref=read(path.join(old,'cap_20261013_131958_foreground.json'));
 execute(m.sid,'cap_20261013_131958',m.transform.R,m.transform.t,ref.transform.R,ref.transform.t,m.background.alignment,
         'historical static overlap .9477; physical/registration gate separate, provisional reference->source alignment');
 const cat=read(path.join(ps,'output/catalog.json'));
 execute('cap_20261010_180557','cap_20261010_175227',cat.R,cat.T,cat.R,cat.T,null,
         'historical common REF_RT; physical scene equivalence not independently reviewed');
 PL.PIPE.ground_keep_below_m=ground; // loader must use unchanged official config for all binding gates.
 const states=[];
 for(const d of fs.readdirSync(path.join(ROOT,'captures/registration'))){const loaded=REG.load(path.join(ROOT,'captures/registration',d),{root:ROOT});states.push({path:d,state:loaded.state,reasons:loaded.reasons,
   fusion_default:REG.fusionKeys(false,loaded)===null,fusion_enabled:REG.fusionKeys(true,loaded)!==null});}
 const newdir=path.join(out,'registration_094333_131958_v1');
 if(fs.existsSync(newdir)){const l=REG.load(newdir,{root:ROOT});states.push({path:newdir,state:l.state,reasons:l.reasons,geometry:l.registration?.quality,
   binding_status:['STALE','UNAVAILABLE'].includes(l.state)?l.state:'BOUND_CURRENT_INPUT_REFERENCE_CODE',
   human_qualification:'BLOCKED_NO_W03_REVIEWED_GT; unrelated to geometry gate',fusion_default:REG.fusionKeys(false,l)===null,
   fusion_enabled:REG.fusionKeys(true,l)!==null});}
 fs.writeFileSync(path.join(out,'ARTIFACT_STATES.json'),JSON.stringify(states,null,2),{flag:'wx'});
}finally{PL.PIPE.ground_keep_below_m=ground;}}
