// Existing C08/V07: explicit provenance and prediction lifecycle consumers.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {createRequire}=require('module');
const code=fs.readFileSync(path.join(__dirname,'codex_full_review.js'),'utf8');
const prefix=code.slice(0,code.indexOf("check('V01'"));
const {fixture,worldWith}=new Function('require','module','__dirname',prefix+';return {fixture,worldWith};')(
    createRequire(path.join(__dirname,'codex_full_review.js')),{exports:{}},__dirname);
const {HF}=require('./codex_runtime_harness');
const rows=[];
function observe(w){const t=w.context.__review.hfBoxes.target;return {position:w.$('hfPos').textContent,fall:w.$('hfFall').textContent,prediction:w.$('hfPred').textContent,track:w.$('hfTrack').textContent,target_visible:!!(t&&t.line.visible),target_color:t?t.line.material.color.getHexString():null};}
function check(name,run){let actual;try{run(x=>actual=x);rows.push({id:'V07/V09',matrix:'C08',name,actual,result:'PASS'});}catch(e){rows.push({id:'V07/V09',matrix:'C08',name,actual,result:'FAIL',error:e.message});}}
for(const from of ['unavailable','predicted'])check('explicit source provenance '+from+' cannot read as current measured XYZ',capture=>{
    const f=fixture();f.state.position_source_from=from;f.state.position_predicted=false;
    const w=worldWith(f);const o=observe(w);capture({valid_state:HF.validState(f.state),...o});
    assert.strictEqual(o.position,'--','explicit non-actual source position must be unavailable');
    assert.ok(!o.prediction.includes('实测'),'explicit non-actual source position cannot be labelled measured');
    assert.strictEqual(o.fall,'unknown');
});
check('bbox flag alone does not erase actual_points raw center',capture=>{
    const f=fixture();f.state.bbox_observed=false;f.state.position_source_from='actual_points';
    const o=observe(worldWith(f));capture(o);assert.ok(o.position.includes('3.00'));assert.strictEqual(o.fall,'unknown');
});
check('legacy omitted provenance retains current source XYZ',capture=>{
    const f=fixture();delete f.state.position_source_from;delete f.state.bbox_observed;
    const o=observe(worldWith(f));capture(o);assert.ok(o.position.includes('3.00'));assert.strictEqual(o.fall,'upright');
});
for(const status of ['lost','ambiguous','unselected','locked'])check(status+' is not a valid occluded prediction',capture=>{
    const f=fixture();f.snap.candidates=[];Object.assign(f.state,{track_status:status,position_predicted:true,prediction_stale:false,position_source_from:'predicted',prediction_age_s:0.5});
    if(status==='unselected')f.state.track_id=null;
    const o=observe(worldWith(f));capture({valid_state:HF.validState(f.state),...o});
    assert.strictEqual(o.target_visible,false,'inactive/non-occluded target cannot reappear through prediction diagnostic');
    assert.strictEqual(o.position,'--');assert.strictEqual(o.fall,'unknown');
});
check('explicit stale occluded prediction cannot redraw retained bbox',capture=>{
    const f=fixture();Object.assign(f.state,{track_status:'occluded',position_predicted:true,prediction_stale:true,position_source_from:'predicted',prediction_age_s:9});
    const o=observe(worldWith(f));capture(o);assert.strictEqual(o.target_visible,false,'stale prediction cannot remain a current diagnostic box');
});
check('fresh occluded empty-candidate prediction retains grey diagnostic',capture=>{
    const f=fixture();f.snap.candidates=[];Object.assign(f.state,{track_status:'occluded',position_predicted:true,prediction_stale:false,position_source_from:'predicted',prediction_age_s:0.5});
    const o=observe(worldWith(f));capture(o);assert.strictEqual(o.target_visible,true);assert.strictEqual(o.target_color,'6b7a90');assert.strictEqual(o.position,'--');assert.strictEqual(o.fall,'unknown');
});
fs.writeFileSync(path.join(__dirname,'98_codex_lifecycle_results.json'),JSON.stringify(rows,null,2),{flag:'wx'});
for(const r of rows)console.log(r.result+' '+r.name+(r.error?' :: '+r.error:''));
console.log(JSON.stringify({pass:rows.filter(r=>r.result==='PASS').length,fail:rows.filter(r=>r.result==='FAIL').length}));
process.exitCode=rows.some(r=>r.result==='FAIL')?1:0;
