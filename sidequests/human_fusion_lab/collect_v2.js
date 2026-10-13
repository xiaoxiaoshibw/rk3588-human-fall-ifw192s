'use strict';
// Preserve the failed freeze check and all 18 completed runs; collect new outputs.
const fs=require('fs'),path=require('path'),assert=require('assert'),{Runtime,audit,MODELS}=require('./v2_runtime');
const out=path.resolve(__dirname,'../../docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1'),rows=[],cases=[],observations=[],r=new Runtime();
for(const rec of audit.sessions)for(const model of ['rf51_baseline','xgb69_candidate']){
 const run=JSON.parse(fs.readFileSync(path.join(out,rec.sid+'__'+model+'.json')));rows.push(run.summary);
 for(const f of run.frames){
  const kind=f.events.includes('PERSON_MISS')?'PERSON_MISS':f.events.includes('FURNITURE_FALSE_POSITIVE')?'FURNITURE_FALSE_POSITIVE':f.events.includes('MODEL_DISAGREEMENT')?'MODEL_DISAGREEMENT':f.diff?.candidates.tp&&f.diff.candidates.fn===0?'SUCCESS':f.gt_status==='UNKNOWN'?'GT_UNKNOWN':null;
  if(kind&&!cases.some(c=>c.sid===rec.sid&&c.model===model&&c.kind===kind))cases.push({sid:rec.sid,activity:rec.activity,model,index:f.index,kind,events:f.events,gt_diff:f.diff,url:'http://127.0.0.1:8798/?sid='+rec.sid+'&model='+model+'&index='+f.index});
 }
 const f=r.frame(rec.sid,model,20),f0=r.frame(rec.sid,model,0),again=r.frame(rec.sid,model,20);assert.deepEqual(f.candidates,again.candidates);r.reset();assert.deepEqual(r.frame(rec.sid,model,20).candidates,again.candidates);
}
for(const rec of audit.sessions){
 const doc=audit.docs[rec.sid];if(!doc)continue;const keys=Object.keys(doc.frames_objects).map(Number).sort((a,b)=>a-b),sample=[keys[0],keys[Math.floor(keys.length/2)],keys.at(-1)];
 for(const index of [...new Set(sample)]){
  const f=r.frame(rec.sid,'xgb69_candidate',index);for(const c of f.candidates.filter(c=>c.gt_hits.some(h=>h.class_name==='PERSON'&&h.purity>=.8)))observations.push({sid:rec.sid,index,id:c.id,shape:c.shape,gt_hits:c.gt_hits,limits:'GT-pure candidate point support is not anatomical visibility GT'});
 }
}
const caseDetails=[];
for(const c of cases.filter(c=>['PERSON_MISS','FURNITURE_FALSE_POSITIVE','MODEL_DISAGREEMENT'].includes(c.kind))){const f=r.frame(c.sid,c.model,c.index);caseDetails.push({...c,layer_observations:f.layer_observations,candidates:f.candidates.map(({indices,...v})=>v)});}
const write=(name,value)=>fs.writeFileSync(path.join(out,name),JSON.stringify(value,null,2),{flag:'wx'});
write('COMPARISON.json',{status:'FULL_REPLAY_SOFTWARE_CHECKS_PASS_FREEZE_BLOCKED',threshold_accepted:.35,threshold_strong:.55,gate_m:.75,models:MODELS,rows,holdout_status:audit.holdout_status,freeze:JSON.parse(fs.readFileSync(path.join(out,'FREEZE_CHECK.json'))),limits:'S1 is training furniture, no independently held-out furniture session. Sparse annotations not full-session GT. TP/FP/FN use XY one-to-one gate, furniture FP separately requires >=80% point overlap.'});
write('CASES.json',cases);write('CASE_DETAILS.json',caseDetails);
write('OBSERVABILITY.json',{selection:'First, middle and last annotated ordinal in each session, predetermined without consulting model success. Candidate pure support >=80%. Missing candidates remain absent; this is not anatomical accuracy evaluation.',calibration:'UNCALIBRATED',anatomical_keypoints:'NOT_ESTIMATED',limbs:'UNKNOWN',pose:'UNKNOWN',observations});
console.log('Collected',rows.length,'runs',rows.reduce((s,r)=>s+r.frames,0),'ticks',cases.length,'cases',observations.length,'sampled geometric observations; freeze BLOCKED');
