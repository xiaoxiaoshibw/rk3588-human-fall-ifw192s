'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),E=require('./core/engine'),Old=require('./core/engine_r4'),S=require('./core/schema'),D=require('./core/data_loader');
const e=new E.UnifiedEngine({mode:'FUSION'});e.rf={extract:(sub,i)=>{assert.strictEqual(sub.n,3);assert.deepStrictEqual(Array.from(sub.x),[1,2,3]);return new Float32Array(51);},predict_person:()=>.8};
const ac=S.make_candidate({candidate_id:'a',point_indices:Uint32Array.from([8,2]),point_count:2,centroid:{x:1,y:0,z:1},scores:{}});ac._fusion_positions=[{frame_pos:0,intensity:1},{frame_pos:1,intensity:2}];ac.rf51_prob=.9;
const out=e._fusion_organize({}, {cls_scores:[]},{cands:[ac],final_ids:[8,2,5],fg_final:Float32Array.from([1,0,1,1,2,0,1,2,3,0,1,3])},[{centroid:{x:1,y:0,z:1},frame_positions:[1,2],frame_intens:[2,3],rf51_prob:.6,is_person:true}]);
assert.deepStrictEqual(Array.from(out[0].point_indices),[8,2,5]);assert.strictEqual(out[0].point_count,3);assert.deepStrictEqual(out[0].bbox,{min:[1,0,1],max:[3,0,1]});assert.strictEqual(out[0].centroid.x,1);assert.strictEqual(out[0].scoring_centroid.x,2);
const ROOT=path.resolve(__dirname,'../..'),audit=JSON.parse(fs.readFileSync(path.join(__dirname,'results/AUDIT.json')));let frames=0,unions=0;
for(const rec of audit.sessions){const session=D.load_session(path.join(ROOT,'captures/remote',rec.sid)),old=new Old.UnifiedEngine({mode:'FUSION'}),now=new E.UnifiedEngine({mode:'FUSION'}),g1=old.begin_session(rec.sid),g2=now.begin_session(rec.sid);
 for(const f of session.frames){const mk=g=>S.make_frame_context({session_id:rec.sid,session_generation:g,frame_index:f.index,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta});const a=old.tick(mk(g1)),b=now.tick(mk(g2));
 const semantic=d=>d._candidates.map(c=>({id:c.candidate_id,centroid:c.centroid,prob:c.scores.rf51.prob,decision:c.classifier_decision,track_id:c.track_id,track_confirmed:c.track_confirmed}));assert.deepStrictEqual(semantic(a),semantic(b));assert.deepStrictEqual(a._tracks,b._tracks);assert.deepStrictEqual(a._events,b._events);
 for(const c of b._candidates){assert.strictEqual(c.point_count,c.point_indices.length);assert.strictEqual(new Set(c.point_indices).size,c.point_count);if(c.fusion_source_SRC==='A+B')unions++;}frames++;
 }console.log('PARITY',rec.sid,session.frames.length);
}
fs.writeFileSync(path.join(__dirname,'results/R5_TEST.json'),JSON.stringify({status:'PASS',frames,merged_candidates:unions,checks:['ordered union duplicate removal','public count/bbox','association anchor parity','all candidate probabilities decisions tracks events parity']},null,2));console.log('PASS',frames,unions);
