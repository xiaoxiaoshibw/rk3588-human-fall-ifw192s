'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const {Runtime,audit,MODELS,shape,fixedDetector}=require('./v2_runtime'),EV=require('./core/evaluate_fusion_gt');
const out=path.resolve(__dirname,'../../docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1');fs.mkdirSync(out,{recursive:true});
assert.equal(shape(new Float32Array(0),[]).status,'INSUFFICIENT_POINTS');
const config=require('./core/fusion').DEFAULT_FUSION_CFG,{UniqueTracker}=require('./unique_tracker');
const tracker=new UniqueTracker(config),mk=x=>({centroid:{x,y:0,z:1},classifier_decision:'CONFIRMED_HUMAN',fusion_source_SRC:'A',track_segment:0});
for(let i=0;i<5;i++){const cs=[mk(0),mk(.05)];tracker.tick(i,cs);assert.equal(new Set(cs.map(c=>c.track_id)).size,2);assert(tracker.tracks.every(t=>t.votes.length===i+1));}
for(let i=5;i<40;i++)tracker.tick(i,[]);assert(tracker.tracks.every(t=>!t.active));
const rows=[],cases=[],observability=[],r=new Runtime();
const plus=(a,b)=>{for(const k of ['tp','fp','fn'])a[k]+=b[k];};
for(const rec of audit.sessions)for(const model of ['rf51_baseline','xgb69_candidate']){
 const summary={sid:rec.sid,activity:rec.activity,model,frames:rec.total_frames,gt_known:0,gt_unknown:0,duplicate_ids:0,candidate:{tp:0,fp:0,fn:0},track:{tp:0,fp:0,fn:0},furniture_false_positive:0,same_candidate: Object.fromEntries(MODELS.map(m=>[m,{tp:0,fp:0,fn:0}])),risks:{},ms:[]},fr=[];
 for(let i=0;i<rec.total_frames;i++){
  const f=r.frame(rec.sid,model,i);assert.equal(new Set(f.candidates.map(c=>c.track_id)).size,f.candidates.length);
  assert(f.candidates.every(c=>c.indices.length===c.n&&c.indices.every(i=>i>=0&&i<f.n_points)&&Object.values(c.scores).every(v=>Number.isFinite(v)&&v>=0&&v<=1)));
  if(f.gt_diff){summary.gt_known++;plus(summary.candidate,f.gt_diff.candidates);plus(summary.track,f.gt_diff.tracks);for(const m of MODELS)plus(summary.same_candidate[m],EV.count(f.gt.filter(g=>g.class_name==='PERSON'),f.candidates.filter(c=>c.scores[m]>=.35),.75));}else summary.gt_unknown++;
  summary.furniture_false_positive+=f.candidates.filter(c=>c.prob>=.35&&c.gt_hits.some(h=>h.class_name==='FURNITURE'&&h.purity>=.8)).length;
  for(const event of f.events)summary.risks[event]=(summary.risks[event]||0)+1;
  summary.ms.push(f.ms);
  const kind=f.events.includes('PERSON_MISS')?'PERSON_MISS':f.events.includes('FURNITURE_FALSE_POSITIVE')?'FURNITURE_FALSE_POSITIVE':f.events.includes('MODEL_DISAGREEMENT')?'MODEL_DISAGREEMENT':f.gt_diff?.candidates.tp&&f.gt_diff.candidates.fn===0?'SUCCESS':f.gt_status==='UNKNOWN'?'GT_UNKNOWN':null;
  if(kind&&!cases.some(c=>c.sid===rec.sid&&c.model===model&&c.kind===kind))cases.push({sid:rec.sid,activity:rec.activity,model,index:i,kind,events:f.events,gt_diff:f.gt_diff,url:'http://127.0.0.1:8798/?sid='+rec.sid+'&model='+model+'&index='+i});
  if(model==='xgb69_candidate')for(const c of f.candidates.filter(c=>c.gt_hits.some(h=>h.class_name==='PERSON'&&h.purity>=.8)))observability.push({sid:rec.sid,index:i,id:c.id,n:c.n,height:c.shape.height_p90_m,nodes:c.shape.nodes.map(n=>({name:n.name,support:n.support})),limbs:'UNKNOWN',anatomical_keypoints:'NOT_ESTIMATED'});
  fr.push({index:i,events:f.events,gt_status:f.gt_status,diff:f.gt_diff,candidates:f.candidates.map(c=>({id:c.id,n:c.n,track_id:c.track_id,prob:c.prob,scores:c.scores,gt_hits:c.gt_hits}))});
 }
 const before=r.frame(rec.sid,model,20),back=r.frame(rec.sid,model,0),again=r.frame(rec.sid,model,20);assert.equal(back.index,0);assert.deepEqual(before.candidates,again.candidates);
 r.reset();const fresh=r.frame(rec.sid,model,20);assert.deepEqual(fresh.candidates,again.candidates);
 summary.p95_detection_ms=summary.ms.slice().sort((a,b)=>a-b)[Math.floor(summary.ms.length*.95)];delete summary.ms;rows.push(summary);
 fs.writeFileSync(path.join(out,rec.sid+'__'+model+'.json'),JSON.stringify({summary,frames:fr}));
 console.log(rec.activity,model,'known',summary.gt_known,'unknown',summary.gt_unknown,JSON.stringify(summary.candidate),'duplicate=0');
}
const protectedFiles=Object.entries(JSON.parse(fs.readFileSync(path.join(out,'BASELINE.json'))).files).filter(([name,v])=>v.sha256&&(name.startsWith('pc_apps/')||name.startsWith('src/')||name.startsWith('webui/')||name.startsWith('captures/')||name.startsWith('sidequests/human_fusion_lab/results/')||name.startsWith('docs/human_capture/evidence/2026-10-11_q01_review_r1/')));
const crypto=require('crypto'),root=path.resolve(__dirname,'../..');let changed=[];
for(const [name,v] of protectedFiles){const file=path.join(root,name);if(!fs.existsSync(file)){changed.push(name);continue;}const h=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');if(h!==v.sha256)changed.push(name);}
fs.writeFileSync(path.join(out,'FREEZE_CHECK.json'),JSON.stringify({checked:protectedFiles.length,changed},null,2));assert.deepEqual(changed,[]);
fs.writeFileSync(path.join(out,'COMPARISON.json'),JSON.stringify({status:'PASS_SOFTWARE_SELF_CHECK',threshold_accepted:.35,threshold_strong:.55,gate_m:.75,holdout_status:audit.holdout_status,rows},null,2));
fs.writeFileSync(path.join(out,'CASES.json'),JSON.stringify(cases,null,2));
fs.writeFileSync(path.join(out,'OBSERVABILITY.json'),JSON.stringify({status:'GEOMETRIC_PROXY_ONLY',calibration:'UNCALIBRATED',observations:observability},null,2));
console.log('V2_FULL_REPLAY_PASS',rows.length,'runs',cases.length,'cases',observability.length,'person-pure geometry observations');
