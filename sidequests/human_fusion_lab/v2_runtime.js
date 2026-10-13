'use strict';
// V1 pipeline and weights are read-only; V2 owns its tracker and diagnostics.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const D=require('./core/data_loader'),S=require('./core/schema'),L=require('./core/leveling');
const {createDetector,treeRF,treeXGB}=require('./detector'),{UniqueTracker}=require('./unique_tracker');
const {subset,extra,objects,rawMap}=require('./export'),EV=require('./core/evaluate_fusion_gt');
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'results/AUDIT.json')));
const ROOT=process.env.HF_REPO_ROOT||path.resolve(__dirname,'../..');
const MODELS=['rf51_baseline','rf51_candidate','rf69_candidate','xgb69_candidate'];
const weights=Object.fromEntries(MODELS.slice(1).map(n=>[n,JSON.parse(fs.readFileSync(path.join(__dirname,'models',n+'.json')))]));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function score(m,x){return m.kind==='rf'?m.trees.reduce((s,t)=>s+treeRF(t,x),0)/m.trees.length:1/(1+Math.exp(-(m.base_margin+m.trees.reduce((s,t)=>s+treeXGB(t,x),0))));}
function fixedDetector(model){
 const det=createDetector(model);if(det.fallback)throw Error(det.fallback);
 const eng=det.engine,base=eng._tick_fusion;
 eng._tick_fusion=function(...args){
  // Also applies after engine-level segment/reset transitions, not only begin().
  if(!(this.fusion_ctx.tracker instanceof UniqueTracker))this.fusion_ctx.tracker=new UniqueTracker(this.cfg.fusion_cfg);
  return base.apply(this,args);
 };
 let fg=[];const a=eng._fusion_a_chain;
 eng._fusion_a_chain=function(...args){const r=a.apply(this,args);fg=Array.from(r.final_ids);return r;};
 det.foreground=()=>fg;
 return det;
}
function shape(cloud,ids){
 const pts=ids.map(i=>[cloud[i*4],cloud[i*4+1],cloud[i*4+2]]).filter(p=>p.every(Number.isFinite));
 if(pts.length<20)return {status:'INSUFFICIENT_POINTS',support:pts.length,nodes:[],limbs:'UNKNOWN',pose:'UNKNOWN'};
 const zs=pts.map(p=>p[2]).sort((a,b)=>a-b),lo=zs[Math.floor(zs.length*.05)],hi=zs[Math.floor(zs.length*.95)],height=hi-lo;
 const bands=[[.8,1,'upper_surface'],[.4,.65,'middle_surface'],[.15,.35,'lower_surface']];
 const nodes=bands.map(([a,b,name])=>{const sub=pts.filter(p=>p[2]>=lo+a*height&&p[2]<=lo+b*height);return {name,support:sub.length,position:sub.length>=5?[0,1,2].map(k=>sub.reduce((s,p)=>s+p[k],0)/sub.length):null};});
 return {status:'GEOMETRIC_PROXY_ONLY',support:pts.length,height_p90_m:height,nodes,limbs:'UNKNOWN',anatomical_keypoints:'NOT_ESTIMATED',pose:'UNKNOWN',calibration:'UNCALIBRATED'};
}
class Runtime {
 constructor(){this.state=null;this.featureRF=createDetector('rf51_baseline').engine.rf;}
 reset(){this.state=null;}
 load(sid,model){
  const rec=audit.sessions.find(r=>r.sid===sid);if(!rec||!MODELS.includes(model))throw Error('invalid session/model');
  const session=D.load_session(path.join(ROOT,'captures/remote',sid));
  if(session.meta_sha256!==rec.input_sha256.meta||session.points_sha256!==rec.input_sha256.points)throw Error('Capture SHA changed');
  const det=fixedDetector(model);let doc=audit.docs[sid]||null;
  // Frozen GT must still match its file, capture binding and review claim today.
  const valid=rec.eligible&&doc&&doc.session_id===sid&&doc.review_status==='reviewed'&&fs.existsSync(rec.gt_path)&&hash(fs.readFileSync(rec.gt_path))===rec.gt_sha256&&doc.session_sha256?.meta===session.meta_sha256&&doc.session_sha256?.points===session.points_sha256;
  if(!valid)doc=null;
  this.state={sid,model,rec,session,det,doc,generation:det.begin(sid),last:-1,diag:null};
 }
 frame(sid,model,index){
  if(!this.state||this.state.sid!==sid||this.state.model!==model)this.load(sid,model);
  const st=this.state,n=st.session.frames.length;
  if(!Number.isSafeInteger(index)||index<0||index>=n)throw Error('frame out of range');
  if(index<st.last){st.generation=st.det.begin(sid);st.last=-1;}
  for(let i=st.last+1;i<=index;i++){const f=st.session.frames[i];st.diag=st.det.tick(S.make_frame_context({session_id:sid,session_generation:st.generation,frame_index:i,timestamp:f.timestamp,xyzi:f.xyzi,meta:st.session.meta}));st.last=i;}
  const d=st.diag,f=st.session.frames[index],co=st.det.engine.report().coordinate_contract,lv=L.level_frame(f.xyzi,co.R,co.T,co.already_leveled);
  const gt=objects(st.doc,index,rawMap(f.xyzi)),person=(gt||[]).filter(g=>g.class_name==='PERSON');
  const candidates=d._candidates.map(c=>{
   const ids=Array.from(c.point_indices),[sub,it]=subset(lv,ids),x51=Array.from(this.featureRF.extract(sub,it)),x69=Float32Array.from(x51.concat(extra(sub)));
   const scores={rf51_baseline:this.featureRF.predict_person(Float32Array.from(x51))};
   for(const name of MODELS.slice(1))scores[name]=score(weights[name],weights[name].n_features===51?Float32Array.from(x51):x69);
   const hits=(gt||[]).map(g=>{const set=new Set(g.indices);return {id:g.id,class_name:g.class_name,purity:ids.filter(i=>set.has(i)).length/ids.length};}).filter(h=>h.purity>0);
   return {id:c.candidate_id,indices:ids,n:c.point_count,x:c.centroid.x,y:c.centroid.y,z:c.centroid.z,prob:c.scores.rf51.prob,decision:c.classifier_decision,source:c.fusion_source_SRC,track_id:c.track_id,track_confirmed:c.track_confirmed,scores,gt_hits:hits,shape:shape(lv,ids)};
  });
  const pred=candidates.filter(c=>['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.decision));
  const diff=gt?{candidates:EV.count(person,pred,.75),tracks:EV.count(person,d._tracks.filter(t=>t.human_confirmed&&t.lost===0),.75),gate_m:.75}:null;
  const fgSet=new Set(st.det.foreground());
  const layer_observations=person.map(g=>{
   const ids=new Set(g.indices),hits=candidates.map(c=>({c,coverage:c.indices.filter(i=>ids.has(i)).length/g.indices.length}));
   const proposals=hits.filter(h=>h.coverage>=.1&&Math.hypot(h.c.x-g.x,h.c.y-g.y)<=.75),accepted=proposals.filter(h=>h.c.prob>=.35),tracked=accepted.filter(h=>h.c.track_confirmed);
   const foreground_points=g.indices.filter(i=>fgSet.has(i)).length;
   return {id:g.id,raw_points:g.indices.length,foreground_points,retention:foreground_points/g.indices.length,best_candidate_coverage:Math.max(0,...hits.map(h=>h.coverage)),loss:!foreground_points?'BG_OR_CLEANUP':!proposals.length?'PROPOSAL':!accepted.length?'CLASSIFIER':!tracked.length?'TRACKER':'NONE',limits:'A-chain final foreground includes cleanup/retained; no claim to isolate background from cleanup'};
  });
  const events=[];
  if(!gt)events.push('GT_UNKNOWN');
  if(diff?.candidates.fn)events.push('PERSON_MISS');
  for(const c of pred)if(c.gt_hits.some(h=>h.class_name==='FURNITURE'&&h.purity>=.8))events.push('FURNITURE_FALSE_POSITIVE');
  if(diff?.candidates.fp)events.push('UNMATCHED_PREDICTION');
  if(candidates.some(c=>Math.min(...Object.values(c.scores))<.35&&Math.max(...Object.values(c.scores))>=.55))events.push('MODEL_DISAGREEMENT');
  const tids=candidates.map(c=>c.track_id);if(new Set(tids).size!==tids.length)throw Error('same-frame duplicate track ID');
  return {sid,index,total:n,n_points:f.n_points,detector:model,generation:st.generation,ms:d.total_ms,gt_status:gt?'REVIEWED_BOUND_OBSERVATION':'UNKNOWN',gt_diff:diff,gt:(gt||[]).map(({indices,...g})=>g),candidates,tracks:d._tracks,foreground:st.det.foreground(),layer_observations,coordinate:co,calibration:'UNCALIBRATED',comparison:'SAME_CURRENT_CANDIDATE_POINTS; fixed current pipeline proposals, no independent replay claim',events:[...new Set(events)],input_sha256:st.rec.input_sha256,xyzi:lv};
 }
}
module.exports={Runtime,audit,MODELS,shape,fixedDetector};
