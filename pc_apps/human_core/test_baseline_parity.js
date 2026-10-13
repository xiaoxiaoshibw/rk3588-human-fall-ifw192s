/* 原A pipeline/原B完整on_frame逐帧独立对拍。--out仅接受不存在的结果文件。 */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const E=require('./engine.js'),D=require('./data_loader.js'),S=require('./schema.js'),L=require('./leveling.js');
const frozen_source=require('./runner.js').source_sha();
const ids=['cap_20261004_203135','cap_20261004_203349','cap_20261007_143945','cap_20261007_154007','cap_20261009_113611','cap_20261009_114641','cap_20261009_114709','cap_20261009_114817','cap_20261009_121622'];
const results=[];
const model=fs.readFileSync('pc_apps/human_replay/rf_person_v1.json','utf8'),bg=JSON.parse(fs.readFileSync('pc_apps/human_replay/bg_envelope.json','utf8'));
for(const sid of ids){
 const s=D.load_session(path.join('captures/remote',sid));
 const contract=L.resolve_contract({meta:s.meta},L.REF_RT);
 const leveled=s.frames.map(f=>L.level_frame(f.xyzi,contract.R,contract.T,contract.already_leveled));
 const a=new E.UnifiedEngine({mode:'BASE_A'});a.begin_session(sid);a.set_online_background(s.frames.map(f=>f.xyzi),{meta:s.meta});
 const b=new E.UnifiedEngine({mode:'BASE_B'});b.begin_session(sid);
 const pipe=E.load_production('human_pipe_lib.js'),ctx={static_keys:pipe.build_static_map(leveled.map(f=>pipe.denoise(f))),tracker:new pipe.Tracker()};
 const original=E.load_production('detect_overlay.js'),rf=E.load_production('rf_person.js');rf.init(model);
 let originalCalls=[],lastCall;
 original.init({bgEnvelopeJson:bg,rf:{extract:(sub,intensity)=>{lastCall={sub,intensity:Array.from(intensity)};originalCalls.push(lastCall);return rf.extract(sub,intensity);},predict_person:fv=>{const score=rf.predict_person(fv);lastCall.score=score;return score;}}});
 original.set_leveled_in_s(true);
 for(let i=0;i<s.frames.length;i++){
  const f=s.frames[i],fc=S.make_frame_context({session_id:sid,session_generation:1,frame_index:i,timestamp:f.timestamp,xyzi:f.xyzi,meta:s.meta});
  const da=a.tick(fc),ra=pipe.pipeline_frame(leveled[i],i,ctx);
  assert.deepEqual(da._candidates.map(c=>c._pipe_f),ra.clusters,sid+' A候选/特征/证据');
  assert.deepEqual(a.report().tracks,ctx.tracker.tracks,sid+' A全部track');assert.deepEqual(da._events,ra.events,sid+' A事件');
  const db=b.tick(fc),buf=new Float32Array(leveled[i].length/4*7);
  for(let k=0;k<leveled[i].length/4;k++)buf.set(leveled[i].subarray(k*4,k*4+4),k*7);
  originalCalls=[];
  const state={geo:{},frames:[{start_pts:0,count:leveled[i].length/4}],idx:0,buf_f32:buf,meta:{leveling:{}},fps:10};original.on_frame(state);
  assert.equal(db._candidates.length,originalCalls.length,sid+' B簇数');
  db._candidates.forEach((c,j)=>{
   const call=originalCalls[j],idx=Array.from(c.point_indices);
   assert.deepEqual(idx.map(k=>leveled[i][k*4]),Array.from(call.sub.x),sid+' B X/index');
   assert.deepEqual(idx.map(k=>leveled[i][k*4+1]),Array.from(call.sub.y),sid+' B Y/index');
   assert.deepEqual(idx.map(k=>leveled[i][k*4+2]),Array.from(call.sub.z),sid+' B Z/index');
   assert.deepEqual(idx.map(k=>leveled[i][k*4+3]),call.intensity,sid+' B intensity');
   assert.equal(c.scores.rf51.prob,call.score,sid+' B RF');
  });
  const expected=original._dbg_state.tracks.map(t=>({id:t.id,x:t.cx,y:t.cy,z:t.zmax,r90:t.r90,n:t.n,age:t.age,born:t.born,miss:t.miss}));
  const actual=db._tracks.map(t=>({id:t.id,x:t.x,y:t.y,z:t.z,r90:t.r90,n:t.n,age:t.age,born:t.born_idx,miss:t.lost}));
  assert.deepEqual(actual,expected,sid+' B关联/中心/寿命');
  const confirmed=expected.filter(t=>t.miss===0&&t.age>=3).map(t=>t.id);
  assert.deepEqual(db._tracks.filter(t=>t.human_confirmed).map(t=>t.id),confirmed,sid+' B确认');
  const hudIds=(state.hud_extra.match(/#\d+/g)||[]).map(x=>Number(x.slice(1))).sort((x,y)=>x-y);
  assert.deepEqual(hudIds,confirmed.slice().sort((x,y)=>x-y),sid+' B HUD确认ID集合');
  db._candidates.filter(c=>c.track_id!==null).forEach(c=>{
   const t=expected.find(t=>t.id===c.track_id);
   assert(t && t.miss===0,sid+' B candidate指向当帧生产track');
   assert.equal(t.x,c.centroid.x,sid+' B candidate中心X');assert.equal(t.y,c.centroid.y,sid+' B candidate中心Y');assert.equal(t.n,c.point_count,sid+' B candidate点数');
  });
  // 每个accepted候选还需回填生产track id；同簇n/cx/cy可能重复时按当前一对一集合比较。
  const coreIds=db._candidates.filter(c=>c.scores.rf51.prob>=.55).map(c=>c.track_id).sort((x,y)=>x-y);
  const productionIds=expected.filter(t=>t.miss===0).map(t=>t.id).sort((x,y)=>x-y);
  assert.deepEqual(coreIds,productionIds,sid+' B候选ID');
 }
 results.push({session:sid,frames:s.frames.length,A:'PASS',B:'PASS',input_sha256:{points:s.points_sha256,meta:s.meta_sha256}});
 console.log('PASS '+sid+' '+s.frames.length+' frames A/B');
 assert.deepEqual(require('./runner.js').source_sha(),frozen_source,'依赖在对拍期间变化，本批不可验收');
}
const outIndex=process.argv.indexOf('--out');if(outIndex>=0)fs.writeFileSync(process.argv[outIndex+1],JSON.stringify({note:'同一明确配平输入；不冒称真实浏览器UI/物理验证',source_sha256:frozen_source,results},null,2),{flag:'wx'});
console.log('== baseline_parity: '+results.length+' sessions PASS ==');
