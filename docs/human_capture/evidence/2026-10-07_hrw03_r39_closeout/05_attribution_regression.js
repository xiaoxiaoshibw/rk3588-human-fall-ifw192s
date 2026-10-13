"use strict";
const fs=require('fs'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration');
const d=R.read(__dirname+'/03_confirmation_attribution_r2.json'),rows=[];
function test(name,fn){try{fn();rows.push({name,result:'PASS'});}catch(e){rows.push({name,result:'FAIL',error:e.stack});}}
test('A04 exhaustive original confirmation cohort and one primary attribution per row',()=>{
    assert.equal(d.rows.length,257);assert.equal(d.rows.filter(v=>v.change==='new_green').length,61);
    assert.equal(d.rows.filter(v=>v.change==='new_purple').length,70);assert.equal(d.rows.filter(v=>v.change==='disappeared').length,126);
    assert.equal(Object.values(d.categories).reduce((a,b)=>a+b,0),257);
    assert.equal(new Set(d.rows.map(v=>v.id)).size,257);
});
test('A05 incidental cleanup cannot claim causality for reference-dominant removal',()=>{
    const affected=d.rows.filter(v=>v.initial_category==='CLEANUP_SIDE_EFFECT');assert.equal(affected.length,7);
    assert(affected.every(v=>v.removed_by_mechanism.REGISTRATION_TRANSFORM_REFERENCE_MATCH>0&&v.attribution_category==='REFERENCE_ABSORPTION'));
});
test('A06 time confirmation survives instantaneous NON_HUMAN by saved votes; not GT person',()=>{
    const c=d.rows.find(v=>v.id==='f65:new_green:P0:S0');assert(c);
    assert.equal(c.P.joint,'NON_HUMAN');assert.equal(c.S.joint,'NON_HUMAN');assert.equal(c.attribution_category,'TRACK_ID_REASSIGNMENT');
    assert.equal(c.P_votes.reduce((a,b)=>a+b,0),2);assert.equal(c.S_votes.reduce((a,b)=>a+b,0),3);
    assert.equal(c.semantic_GT,'UNKNOWN');assert.equal(c.true_human_track_continuity,'UNKNOWN');
});
test('A07 late clean candidate loss is history loss with same large point support',()=>{
    const c=d.rows.find(v=>v.id==='f146:disappeared:P0:S0');assert.equal(c.shared_points,3293);
    assert.equal(c.points_lost_from_matched_cluster,3);assert.equal(c.attribution_category,'TRACK_ID_REASSIGNMENT');
    assert.equal(c.P_votes.reduce((a,b)=>a+b,0),3);assert.equal(c.S_votes.reduce((a,b)=>a+b,0),2);
});
test('A08 no arithmetic corruption in metrics; absent geometry remains explicit null/UNKNOWN',()=>{
    const walk=v=>{if(typeof v==='number')assert(Number.isFinite(v));else if(Array.isArray(v))v.forEach(walk);else if(v&&typeof v==='object')Object.values(v).forEach(walk);};
    walk(d);const s=R.read(__dirname+'/06_shadow_results.json');walk(s);
    assert(s.P.frames.every(f=>Number.isFinite(f.cleanup_split_delta)));assert(s.S.frames.every(f=>Number.isFinite(f.cleanup_split_delta)));
});
fs.writeFileSync(__dirname+'/05_attribution_regression.json',R.serialize(rows),{flag:'wx'});console.log(R.serialize(rows));process.exitCode=rows.some(v=>v.result==='FAIL')?1:0;
