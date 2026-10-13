'use strict';
// One-variable causal probe in the frozen workspace. No production mutation.
const fs=require('fs'),path=require('path'),assert=require('assert');
const W=path.join(__dirname,'workspace'),ROOT=path.resolve(__dirname,'../../../..');
const code=fs.readFileSync(path.join(W,'core/engine.js'),'utf8'),needle='if(bg===undefined||bg<-9)continue;';
assert.strictEqual(code.split(needle).length-1,2);
// For unknown-reference cells only, allow existing z-banded points into both branches.
// This does not declare them HUMAN or change any geometry/classifier/track threshold.
fs.writeFileSync(path.join(W,'core/engine_keep_unknown.js'),code.split(needle).join('if(bg===undefined||bg<-9)bg=z-0.251;'),{flag:'wx'});
const detector=fs.readFileSync(path.join(W,'detector.js'),'utf8');
fs.writeFileSync(path.join(W,'detector_keep_unknown.js'),detector.replace("require('./core/engine')","require('./core/engine_keep_unknown')"),{flag:'wx'});
const A=JSON.parse(fs.readFileSync(path.join(W,'results/AUDIT.json'))),D=require(path.join(W,'core/data_loader')),S=require(path.join(W,'core/schema'));
const {objects,rawMap}=require(path.join(W,'export')),EV=require(path.join(W,'core/evaluate_fusion_gt'));
const runs=[];
for(const sid of ['cap_20261010_175227','cap_20261010_175429','cap_20261010_180235']){
 const rec=A.sessions.find(r=>r.sid===sid),session=D.load_session(path.join(ROOT,'captures/remote',sid));
 assert.strictEqual(session.meta_sha256,rec.input_sha256.meta);assert.strictEqual(session.points_sha256,rec.input_sha256.points);
 for(const variant of ['baseline','keep_unknown']){
  const det=require(path.join(W,variant==='baseline'?'detector.js':'detector_keep_unknown.js')).createDetector('xgb69_candidate');
  assert(!det.fallback);require(path.join(W,'unique_tracker')).install(det.engine);const gen=det.begin(sid);
  const out={sid,variant,frames:session.frames.length,known:0,unknown:0,candidate:{tp:0,fp:0,fn:0},track:{tp:0,fp:0,fn:0},fn_frames:[],candidate_points:[],duplicate_ids:0};
  for(const f of session.frames){
   const d=det.tick(S.make_frame_context({session_id:sid,session_generation:gen,frame_index:f.index,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta}));
   if(new Set(d._candidates.map(c=>c.track_id)).size!==d._candidates.length)out.duplicate_ids++;
   const gt=objects(A.docs[sid],f.index,rawMap(f.xyzi));if(!gt){out.unknown++;continue;}out.known++;
   const person=gt.filter(o=>o.class_name==='PERSON'),pred=d._candidates.filter(c=>['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.classifier_decision)).map(c=>({x:c.centroid.x,y:c.centroid.y}));
   const cm=EV.count(person,pred,.75),tm=EV.count(person,d._tracks.filter(t=>t.human_confirmed&&t.lost===0),.75);
   for(const k of ['tp','fp','fn']){out.candidate[k]+=cm[k];out.track[k]+=tm[k];}if(cm.fn)out.fn_frames.push(f.index);
   if(sid.endsWith('180235')&&[91,187,188].includes(f.index))out.candidate_points.push({frame:f.index,candidates:d._candidates.map(c=>({n:c.point_count,prob:c.scores.rf51.prob,gt_hit:Array.from(c.point_indices).filter(i=>person.some(o=>o.indices.includes(i))).length}))});
  }
  const historical=JSON.parse(fs.readFileSync(path.join(ROOT,'docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1',sid+'__xgb69_candidate.json'))).summary;
  if(variant==='baseline')for(const k of ['tp','fp','fn']){assert.strictEqual(out.candidate[k],historical.candidate[k]);assert.strictEqual(out.track[k],historical.track[k]);}
  runs.push(out);console.log(JSON.stringify({sid,variant,known:out.known,candidate:out.candidate,track:out.track,fn_frames:out.fn_frames}));
 }
}
fs.writeFileSync(path.join(__dirname,'missing_reference_ab.json'),JSON.stringify({model:'xgb69_candidate',tracker:'UniqueTracker',variable:'missing-reference discard versus preserve as unclassified points',runs,limits:'Retrospective known frames only; S1 train negatives; XY one-to-one 0.75 m gate; no claim to independent furniture generalization or production acceptance.'},null,2),{flag:'wx'});
