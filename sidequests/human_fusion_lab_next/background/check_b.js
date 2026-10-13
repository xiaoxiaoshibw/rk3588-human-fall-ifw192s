'use strict';
const assert=require('assert'),B=require('./detector_b'),L=require('../../human_fusion_lab/core/leveling'),S=require('../../human_fusion_lab/core/schema');
const ref={staticKeys:new Map([[1,{x:1,y:1,z:.2,occ:1}]]),columns:new Map([['6,6',[{x:1,y:1,z:.2,occ:1}]]]),coordinate:{...L.REF_RT,already_leveled:false}},det=B.createDetector(ref),e=det.engine;
assert.throws(()=>B.createDetector(null));
const cloud=new Float32Array([1,1,1,2,10,10,1,2,NaN,NaN,NaN,1]);const out=B.select(cloud,e.pipe,ref.staticKeys,ref.columns);
assert.deepEqual(Array.from(out.bare_keep),[1,1,0]);assert.deepEqual(Array.from(out.keep),[1,0,0]);assert.deepEqual(out.states,['UNKNOWN','UNKNOWN','UNKNOWN']);assert.equal(out.reasons[1],'no_reference_XY_support_UNKNOWN');
// Actual PB must process common PA residual even when old envelope has no cells.
e.begin_session('check');e._ref_env={};const n=35,fg=new Float32Array(n*4);for(let i=0;i<n;i++)fg.set([1+(i%5)*.005,1+Math.floor(i/5)*.005,1+i*.01,10],i*4);
const a={final_ids:Array.from({length:n},(_,i)=>i),fg_final:fg,cands:[]};const diag=S.make_diagnostics('check');const items=e._fusion_b_chain({frame_index:0},fg,diag,a);assert.equal(items.length,1);assert.equal(items[0].point_count,35);assert.equal(diag.layers.find(l=>l.layer==='foreground_b').out_points,35);
// Invalid sensor rows cannot become T after translation, including retention.
const fc={...ref.coordinate,already_leveled:false};const lv=e._level(new Float32Array([0,0,0,1,1,1,1,2]),fc);assert(Number.isNaN(lv[0]));
console.log('BG_B_CHECK_PASS missing_reference / unsupported_UNKNOWN / shared_PB / sensor_invalid');
