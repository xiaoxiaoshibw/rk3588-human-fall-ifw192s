'use strict';
// Read frozen code, replay the full prefix, and record losses before classification.
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const W=path.join(__dirname,'workspace'),ROOT=path.resolve(__dirname,'../../../..');
const D=require(path.join(W,'core/data_loader')),L=require(path.join(W,'core/leveling')),S=require(path.join(W,'core/schema'));
const {objects,rawMap}=require(path.join(W,'export')),EV=require(path.join(W,'core/evaluate_fusion_gt'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const sid='cap_20261010_180235',audit=JSON.parse(fs.readFileSync(path.join(W,'results/AUDIT.json'))),rec=audit.sessions.find(r=>r.sid===sid);
assert.strictEqual(sha(rec.gt_path),rec.gt_sha256);
const doc=JSON.parse(fs.readFileSync(rec.gt_path)),session=D.load_session(path.join(ROOT,'captures/remote',sid));
assert.strictEqual(session.meta_sha256,rec.input_sha256.meta);assert.strictEqual(session.points_sha256,rec.input_sha256.points);
const all=[];
for(const model of ['rf51_baseline','xgb69_candidate']){
 const det=require(path.join(W,'detector')).createDetector(model);assert(!det.fallback);const eng=det.engine;
 require(path.join(W,'unique_tracker')).install(eng);
 const gen=det.begin(sid),rows=[];let current={};
 const clean=eng.pipe.cleanup_isolated_fg,cf=eng.pipe.cluster_features,achain=eng._fusion_a_chain,bchain=eng._fusion_b_chain;
 eng.pipe.cleanup_isolated_fg=function(points){const out=clean(points);current.cleanup_out=out;return out;};
 eng.pipe.cluster_features=function(cl){const out=cf(cl);current.features.push({keys:cl.keys,n:out.n,ok:out.ok,reason:out.reason||null});return out;};
 eng._fusion_a_chain=function(...args){const out=achain.apply(this,args);current.a=out;return out;};
 eng._fusion_b_chain=function(...args){const out=bchain.apply(this,args);current.b=out;return out;};
 for(const f of session.frames){
  current={features:[]};const diag=det.tick(S.make_frame_context({session_id:sid,session_generation:gen,frame_index:f.index,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta}));
  const co=eng.report().coordinate_contract,lv=L.level_frame(f.xyzi,co.R,co.T,co.already_leveled),obs=objects(doc,f.index,rawMap(f.xyzi));if(!obs)continue;
  // cleanup preserves the point sequence; duplicate coordinates retain separate row identity.
  const hot=[],removed={height:[],missing_reference:[],envelope_margin:[]};
  for(let i=0;i<f.n_points;i++){const x=lv[4*i],y=lv[4*i+1],z=lv[4*i+2],bg=eng._ref_env[eng.overlay._test.grid_key(x,y)];
   if(z<=.1||z>=2.3)removed.height.push(i);else if(bg===undefined||bg<-9)removed.missing_reference.push(i);else if(z<=bg+.25)removed.envelope_margin.push(i);else hot.push(i);}
  const cleaned=[],out=current.cleanup_out.xyzi;let cursor=0;
  for(let j=0;j<out.length/4;j++){
   while(cursor<hot.length&&!Array.from({length:4},(_,d)=>Object.is(lv[hot[cursor]*4+d],out[j*4+d])).every(Boolean))cursor++;
   assert(cursor<hot.length,'cleanup subsequence');cleaned.push(hot[cursor++]);
  }
  const sets={hot:new Set(hot),cleaned:new Set(cleaned),final:new Set(current.a.final_ids)};
  for(const g of obs.filter(o=>o.class_name==='PERSON')){
   const gs=new Set(g.indices),hit=ids=>ids.filter(i=>gs.has(i)).length;
   const pre=current.features.map(c=>({...c,gt_hit:hit(current.a.final_ids.filter((id,k)=>c.keys.includes(eng.pipe.key_vox(current.a.fg_final[k*4],current.a.fg_final[k*4+1]))))})).filter(c=>c.gt_hit);
   const bs=current.b.map(c=>({n:c.point_count,gt_hit:hit(c.raw_indices),prob:c.rf51_prob})).filter(c=>c.gt_hit);
   const cs=diag._candidates.map(c=>({id:c.candidate_id,n:c.point_count,gt_hit:hit(Array.from(c.point_indices)),distance:Math.hypot(c.centroid.x-g.x,c.centroid.y-g.y),prob:c.scores.rf51.prob,decision:c.classifier_decision,track_confirmed:c.track_confirmed})).filter(c=>c.gt_hit);
   const row={model,frame:f.index,object:g.id,raw:g.indices.length,height_removed:hit(removed.height),missing_reference_removed:hit(removed.missing_reference),envelope_margin_removed:hit(removed.envelope_margin),bg_kept:hit(hot),cleanup_kept:hit(cleaned),final_with_retention:hit(current.a.final_ids),a_components:pre,b_components:bs,final_candidates:cs,
    candidate_metric:EV.count([g],diag._candidates.filter(c=>['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.classifier_decision)).map(c=>({x:c.centroid.x,y:c.centroid.y})),.75)};
   assert.strictEqual(row.raw,row.height_removed+row.missing_reference_removed+row.envelope_margin_removed+row.bg_kept);
   row.has_proposal=cs.some(c=>c.gt_hit/row.raw>=.1&&c.distance<=.75);row.has_accepted=row.has_proposal&&cs.some(c=>c.gt_hit/row.raw>=.1&&c.distance<=.75&&['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.decision));
   rows.push(row);
  }
 }
 assert.strictEqual(rows.length,71);all.push({model,frames:session.frames.length,observations:rows});
 console.log(model,'238 prefix ticks, 71 GT observations; no proposal frames:',rows.filter(r=>!r.has_proposal).map(r=>r.frame));
}
assert.strictEqual(sha(rec.gt_path),rec.gt_sha256);for(const [name,key] of [['meta.json','meta'],['points.bin','points']])assert.strictEqual(sha(path.join(ROOT,'captures/remote',sid,name)),rec.input_sha256[key]);
const dest=path.join(__dirname,'s6_stage_probe.json');fs.writeFileSync(dest,JSON.stringify({input_sha:rec.input_sha256,gt_sha:rec.gt_sha256,thresholds:{accepted:.35,strong:.55,overlap_coverage:.1,xy_match:.75},runs:all,limits:'Stage counts are bound GT row support. Greedy XY matches are not segmentation accuracy or physical validation. All unannotated frames UNKNOWN.'},null,2),{flag:'wx'});
