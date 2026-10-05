const {createWorld,HF}=require('./codex_runtime_harness');
const assert=require('assert');
const fs=require('fs');
const path=require('path');
const results=[];
const clone=o=>JSON.parse(JSON.stringify(o));
function fixture(){
  const snap={kind:'candidate_snapshot',schema_version:1,session_id:'s',time_epoch:0,snapshot_id:'snap7',
    source:{seq:7,stamp_secs:100,stamp_nsecs:1,frame_id:'innolidar'}, units:{length:'m',angle:'rad'},
    calibration:{calibration_id:'cal1',schema_version:1,ground_status:'valid',ground_derived_id:'gd1'},
    coordinate:{source_frame:'innolidar',ground_derived_id:'gd1',horizontal_basis:'ground_tangent'},
    ground:{status:'valid',frame:'innolidar'},
    candidates:[{candidate_id:'c0000',point_count:80,center_source_m:[3,0,-.5],bbox_source_min_m:[2.8,-.2,-1],bbox_source_max_m:[3.2,.2,.5],
      center_ground_m:[3,0,1],bbox_ground_min_m:[2.8,-.2,.5],bbox_ground_max_m:[3.2,.2,2],bbox_ground_from:'actual_points'}],
    ground_render:{kind:'ground_render',schema_version:1,from_frame:'innolidar',to_frame:'ground_local',units:'m',
      calibration_id:'cal1',geometry_schema_version:1,ground_derived_id:'gd1',R:[[1,0,0],[0,1,0],[0,0,1]],t:[0,0,1.5],
      support:{kind:'support_region',schema_version:1,frame:'ground_local',ground_derived_id:'gd1',polygon:[[0,0],[4,0],[4,2],[0,2]]}}};
  const state={kind:'target_state',schema_version:1,session_id:'s',time_epoch:0,selection_version:1,track_id:'t1',track_status:'locked',
    fall_status:'upright',observability:'valid',position_source_m:[3,0,-.5],position_predicted:false,
    bbox_source_min_m:[2.8,-.2,-1],bbox_source_max_m:[3.2,.2,.5],source:clone(snap.source),calibration:clone(snap.calibration),
    baseline:{status:'ready'},recent_events:[],sensor_quality:{ground_monitor:{status:'ok'},ground_verifier_available:true}};
  return {snap,state};
}
function worldWith(f=fixture()){const w=createWorld();w.message('state',f.state);w.raw();w.message('candidates',f.snap);w.frame();w.context.__review.hfRenderState();w.context.__hf.channelReady=true;return w;}
function check(id,name,fn){try{const observed=fn();results.push({id,name,result:'PASS',observed});}catch(e){results.push({id,name,result:'FAIL',error:e.message});}}
check('V01','missing R/t never identity',()=>assert.notStrictEqual(HF.parseGroundRender({...fixture().snap,ground_render:null}).status,'ready'));
check('V02','exact requested ground.support_polygon entry',()=>{const s=fixture().snap;s.coordinate.ground=clone(s.ground_render);s.ground.support_polygon=[[0,0,0],[4,0,0],[4,2,0],[0,2,0]];s.ground.support_polyline=[[0,0,0],[4,2,0]];delete s.ground_render;const r=HF.parseGroundRender(s);assert.strictEqual(r.status,'ready');assert.ok(r.support&&r.support.polygon);});
for(const status of ['unknown','none'])check('V06','valid transform + '+status+' ground refuses mode',()=>{const f=fixture();f.snap.calibration.ground_status=status;f.snap.ground.status=status;const w=worldWith(f);w.context.__review.hfSetMode('ground');assert.strictEqual(w.context.__hf.coordMode,'source');});
check('V06','unsupported calibration schema refuses mode',()=>{const f=fixture();f.snap.calibration.schema_version=2;f.snap.ground_render.geometry_schema_version=2;const w=worldWith(f);w.context.__review.hfSetMode('ground');assert.strictEqual(w.context.__hf.coordMode,'source');});
check('V06','verifier unavailable clears observed status',()=>{const f=fixture();f.state.sensor_quality.ground_monitor={status:'unknown',reason:'verifier_unavailable'};f.state.sensor_quality.ground_verifier_available=false;const w=worldWith(f);assert.strictEqual(w.$('hfFall').textContent,'unknown');assert.strictEqual(w.$('hfPos').textContent,'--');});
check('V07','no candidate snapshot + ready baseline clears current status',()=>{const f=fixture();const w=createWorld();w.message('state',f.state);w.raw();w.frame();w.context.__review.hfRenderState();assert.strictEqual(w.$('hfFall').textContent,'unknown');assert.strictEqual(w.$('hfPos').textContent,'--');assert.strictEqual(w.$('hfBaseline').textContent,'ready');});
check('V07','candidate list empty + ready baseline clears current status',()=>{const f=fixture();f.snap.candidates=[];const w=worldWith(f);assert.strictEqual(w.$('hfFall').textContent,'unknown');assert.strictEqual(w.$('hfPos').textContent,'--');});
check('V05','list closure same IDs changed candidate content rejected',()=>{const f=fixture();const closed=clone(f.snap);const w=worldWith(f);f.snap=clone(f.snap);f.snap.candidates[0].bbox_source_min_m[0]=0;w.message('candidates',f.snap);w.frame();const n=w.sent.length;w.context.__review.hfSelectCandidate(closed,'c0000');assert.strictEqual(w.sent.length,n);});
check('V05','same IDs changed R/t rejected',()=>{const f=fixture();const closed=clone(f.snap);const w=worldWith(f);f.snap=clone(f.snap);f.snap.ground_render.t[0]=10;w.message('candidates',f.snap);w.frame();const n=w.sent.length;w.context.__review.hfSelectCandidate(closed,'c0000');assert.strictEqual(w.sent.length,n);});
check('V05','caller mutation after rendered button rejected',()=>{const f=fixture();const w=worldWith(f);w.context.__review.hfRenderCandidates();const b=w.$('hfCands').children.at(-1);f.snap.candidates[0].bbox_source_min_m[0]=1;const current=w.context.__hf.candidates.values().next().value.snap;current.candidates[0].bbox_source_min_m[0]=1;const n=w.sent.length;b.onclick();assert.strictEqual(w.sent.length,n);});
check('V06','silent expiry refuses old choice; history retained',()=>{const f=fixture();f.state.recent_events=[{kind:'fall_event',schema_version:1,event_id:'e1',fall_status:'suspected'}];const w=worldWith(f);w.tick(2500);const n=w.sent.length;w.context.__review.hfSelectCandidate(f.snap,'c0000');assert.strictEqual(w.sent.length,n);assert.strictEqual(w.$('hfFall').textContent,'unknown');assert.strictEqual(w.context.__hf.events.length,1);});
check('V06','disconnect preserves history and refuses old choice',()=>{const f=fixture();f.state.recent_events=[{kind:'fall_event',schema_version:1,event_id:'e1',fall_status:'suspected'}];const w=worldWith(f);w.context.client.live=false;w.context.hfConnectionState(false);const n=w.sent.length;w.context.__review.hfSelectCandidate(f.snap,'c0000');assert.strictEqual(w.sent.length,n);assert.strictEqual(w.context.__hf.events.length,1);});
check('V06','future foreign snapshot cannot change current frame R/t',()=>{const f=fixture();const w=worldWith(f);w.context.__review.hfSetMode('ground');const p=Array.from(w.context.positions);const s=clone(f.snap);s.source.seq=8;s.snapshot_id='snap8';s.ground_render.t[0]=20;w.message('candidates',s);assert.deepStrictEqual(Array.from(w.context.positions),p);});
check('V03','mode labels/current position use ground coordinates',()=>{const w=worldWith();w.context.__review.hfSetMode('ground');w.context.__review.hfRenderState();assert.ok(w.$('hfPos').textContent.includes('1.00'));assert.ok(!w.$('hfCoord').textContent.includes('雷达坐标 innolidar'));});
check('V04','DPR-only overlay backing changes after frame',()=>{const w=worldWith();w.context.devicePixelRatio=2;w.frame();assert.strictEqual(w.$('hfOverlay').width,1600);assert.strictEqual(w.$('hfOverlay').height,1200);});
check('V04','CSS resize reprojection uses current camera and rect',()=>{const w=worldWith();w.frame();const a=w.context.__review.hfBoxRect([2.8,-.2,-1],[3.2,.2,.5]);w.$('view3d').clientWidth=400;w.$('gl').clientWidth=400;w.context.resize3d();w.frame();const b=w.context.__review.hfBoxRect([2.8,-.2,-1],[3.2,.2,.5]);assert.notDeepStrictEqual(a,b);});
check('V02','budget 3001/9000 supports has provenance and <=3000',()=>{for(const n of [3001,9000]){const b=HF.supportBudget(Array.from({length:n},(_,i)=>[i,0]),3000);assert.ok(b.count<=3000);assert.strictEqual(b.total,n);assert.strictEqual(b.sampled_from,n);assert.strictEqual(new Set(b.indices).size,b.count);}});
fs.writeFileSync(path.join(__dirname,'codex_independent_results.json'),JSON.stringify(results,null,2));
for(const r of results)console.log(r.result+' '+r.id+' '+r.name+(r.error?' :: '+r.error:''));
console.log(JSON.stringify({pass:results.filter(x=>x.result==='PASS').length,fail:results.filter(x=>x.result==='FAIL').length}));
process.exitCode=results.some(r=>r.result==='FAIL')?1:0;
